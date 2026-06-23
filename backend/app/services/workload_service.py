from __future__ import annotations

from collections import defaultdict
from functools import lru_cache
import json
from pathlib import Path
import re

import httpx

from sqlalchemy.orm import object_session

from app.models.blog import BlogPost
from app.models.submission import AssignmentSubmission
from app.models.user import User
from app.core.config import get_settings
from app.schemas.workload import SubmissionWorkloadSummary, WorkloadEvidenceItem, WorkloadMemberSummary
from app.services.blog_crawler_service import loads_work_items
from app.services.repository_service import build_member_contribution_summary
from app.services.text_extractor import extract_text


def _clip_score(value: float) -> int:
    return max(0, min(100, round(value)))


def _build_blog_stats(submission: AssignmentSubmission) -> dict[str, dict]:
    session = object_session(submission)
    if session is None:
        return {}

    student_ids = sorted(
        {str(member.student_id or "").strip() for member in submission.members if str(member.student_id or "").strip()}
    )
    if not student_ids:
        return {}

    users = session.query(User).filter(User.student_id.in_(student_ids)).all()
    user_map = {str(user.student_id): int(user.id) for user in users}
    if not user_map:
        return {}

    posts = session.query(BlogPost).filter(BlogPost.user_id.in_(list(user_map.values()))).all()
    stats_map: dict[str, dict] = {
        student_id: {"post_count": 0, "code_dump_count": 0, "popular_science_count": 0, "work_item_count": 0}
        for student_id in student_ids
    }
    reverse_map = {int(user.id): str(user.student_id) for user in users}
    for post in posts:
        student_id = reverse_map.get(int(post.user_id))
        if not student_id:
            continue
        stats = stats_map.setdefault(
            student_id,
            {"post_count": 0, "code_dump_count": 0, "popular_science_count": 0, "work_item_count": 0},
        )
        stats["post_count"] += 1
        stats["code_dump_count"] += 1 if bool(post.is_mostly_code) or str(post.category or "") == "code_dump" else 0
        stats["popular_science_count"] += (
            1 if bool(post.is_popular_science) or str(post.category or "") == "popular_science" else 0
        )
        stats["work_item_count"] += len(loads_work_items(post.work_items_json))
    return stats_map


def _statement_work_items(value: str | None) -> list[str]:
    parts = re.split(r"[。！？!?；;\n]+", value or "")
    actions = ("完成", "实现", "负责", "设计", "开发", "修复", "测试", "部署", "调研", "编写", "优化", "联调")
    items = [part.strip()[:120] for part in parts if len(part.strip()) >= 4 and any(word in part for word in actions)]
    return list(dict.fromkeys(items))[:10]


def _material_bundle(submission: AssignmentSubmission) -> tuple[str, list[str]]:
    latest: dict[str, object] = {}
    for asset in sorted(submission.assets or [], key=lambda item: (item.asset_type, item.version_no), reverse=True):
        latest.setdefault(asset.asset_type, asset)
    text_chunks: list[str] = []
    evidence: list[str] = []
    for asset_type, asset in latest.items():
        evidence.append(f"{asset_type}: {asset.file_name} ({asset.file_size} bytes, v{asset.version_no})")
        path = Path(asset.file_path)
        if not path.is_file():
            continue
        text, error = extract_text(str(path))
        if not error and text.strip():
            text_chunks.append(f"【{asset_type}/{asset.file_name}】\n{text[:16000]}")
    return "\n\n".join(text_chunks)[:48000], evidence


@lru_cache(maxsize=128)
def _request_semantic_workload(payload_json: str) -> dict[str, dict]:
    settings = get_settings()
    if not settings.model_base_url or not settings.model_api_key:
        return {}
    payload = json.loads(payload_json)
    prompt = (
        "根据项目材料、个人陈述、Git统计和博客统计，为每位学生提取可核验的实际工作。"
        "不要把团队整体成果直接归给个人，不要仅因代码行数高就认定贡献高。"
        "只输出JSON对象：{\"members\":[{\"student_id\":\"\",\"summary\":\"\","
        "\"work_items\":[\"\"],\"evidence\":[\"\"],\"confidence\":\"high|medium|low\","
        "\"score_adjustment\":0}]}。score_adjustment范围-10到10。\n"
        + json.dumps(payload, ensure_ascii=False)
    )
    try:
        response = httpx.post(
            settings.model_base_url.rstrip("/") + "/chat/completions",
            headers={"Authorization": f"Bearer {settings.model_api_key}", "Content-Type": "application/json"},
            json={
                "model": settings.model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
            },
            timeout=60.0,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"].strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.I)
        parsed = json.loads(content)
        result: dict[str, dict] = {}
        for item in parsed.get("members") or []:
            student_id = str(item.get("student_id") or "").strip()
            if not student_id:
                continue
            result[student_id] = {
                "summary": str(item.get("summary") or "").strip()[:800],
                "work_items": [str(value).strip()[:160] for value in (item.get("work_items") or []) if str(value).strip()][:12],
                "evidence": [str(value).strip()[:160] for value in (item.get("evidence") or []) if str(value).strip()][:12],
                "confidence": str(item.get("confidence") or "low").strip().lower(),
                "score_adjustment": max(-10, min(10, int(item.get("score_adjustment") or 0))),
            }
        return result
    except Exception:
        return {}


def _semantic_workload_map(
    submission: AssignmentSubmission,
    contribution_summary: dict,
    blog_stats_map: dict[str, dict],
) -> tuple[dict[str, dict], list[str]]:
    material_text, material_evidence = _material_bundle(submission)
    contrib_by_id = {item["member_id"]: item for item in contribution_summary.get("members") or []}
    members = []
    for member in submission.members:
        members.append(
            {
                "student_id": member.student_id,
                "student_name": member.student_name,
                "project_role": member.project_role,
                "personal_statement": member.personal_statement,
                "declared_workload_percent": member.workload_percent,
                "git": contrib_by_id.get(member.id, {}),
                "blog": blog_stats_map.get(str(member.student_id), {}),
            }
        )
    payload = {
        "project_name": submission.project_name,
        "group_name": submission.group_name,
        "team_statement": submission.statement_text,
        "members": members,
        "submitted_material_text": material_text,
        "submitted_files": material_evidence,
    }
    return _request_semantic_workload(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)), material_evidence


def _summary_text(member: dict, has_repo_binding: bool) -> str:
    role = member.get("project_role") or "未填写角色"
    declared = member.get("declared_workload_percent") or 0
    blog_posts = int(member.get("blog_post_count") or 0)
    blog_work_items = int(member.get("blog_work_item_count") or 0)
    source = member.get("contribution_source") or "mixed"
    commits = int(member.get("matched_commit_count") or 0)
    additions = int(member.get("matched_additions") or 0)
    statement = re.sub(r"\s+", " ", str(member.get("personal_statement") or "")).strip()

    if statement:
        evidence_tail = f"Git 提交 {commits} 次、新增 {additions} 行；博客 {blog_posts} 篇、工作项 {blog_work_items} 条。"
        return f"{statement[:360]}{'…' if len(statement) > 360 else ''} {evidence_tail}"

    if source == "non_git":
        return f"主要按非 git 方式贡献，角色为{role}，申报工作占比{declared}% ，博客记录 {blog_posts} 篇，抽取工作项 {blog_work_items} 条，需结合材料人工复核。"
    if has_repo_binding:
        return f"角色为{role}，匹配到 {commits} 次 git 提交，累计新增 {additions} 行，博客记录 {blog_posts} 篇，抽取工作项 {blog_work_items} 条，申报工作占比{declared}% 。"
    return f"当前未绑定仓库，角色为{role}，暂按申报工作占比{declared}% 、博客记录 {blog_posts} 篇和个人陈述估算工作量。"


def build_submission_workload_summary(submission: AssignmentSubmission) -> SubmissionWorkloadSummary:
    has_repo_binding = bool(submission.repo_binding)
    contribution_summary = (
        build_member_contribution_summary(submission.repo_binding)
        if submission.repo_binding
        else {
            "members": [],
            "unmapped_authors": [],
            "non_git_members": [],
            "risk_flags": ["no_repo_bound"],
        }
    )

    blog_stats_map = _build_blog_stats(submission)
    semantic_map, submitted_material_evidence = _semantic_workload_map(
        submission, contribution_summary, blog_stats_map
    )
    member_contrib_map = {item["member_id"]: item for item in contribution_summary.get("members", [])}
    max_commits = max([int(item.get("matched_commit_count") or 0) for item in contribution_summary.get("members", [])] or [0])
    max_additions = max([int(item.get("matched_additions") or 0) for item in contribution_summary.get("members", [])] or [0])
    max_blog_posts = max([int(item.get("post_count") or 0) for item in blog_stats_map.values()] or [0])
    max_blog_work_items = max([int(item.get("work_item_count") or 0) for item in blog_stats_map.values()] or [0])

    risk_flags = list(contribution_summary.get("risk_flags") or [])
    members_payload: list[WorkloadMemberSummary] = []
    total_blog_posts = 0

    for member in submission.members:
        contrib = member_contrib_map.get(member.id, {})
        blog_stats = blog_stats_map.get(str(member.student_id or "").strip(), {})
        blog_post_count = int(blog_stats.get("post_count") or 0)
        blog_code_dump_count = int(blog_stats.get("code_dump_count") or 0)
        blog_popular_science_count = int(blog_stats.get("popular_science_count") or 0)
        blog_work_item_count = int(blog_stats.get("work_item_count") or 0)
        total_blog_posts += blog_post_count

        declared = member.workload_percent
        semantic = semantic_map.get(str(member.student_id or "").strip(), {})
        declared_score = int(declared or 0)
        statement_bonus = 10 if (member.personal_statement or "").strip() else 0
        blog_post_score = 0 if max_blog_posts <= 0 else (blog_post_count / max_blog_posts) * 10
        blog_work_item_score = 0 if max_blog_work_items <= 0 else (blog_work_item_count / max_blog_work_items) * 10
        blog_penalty = 6 if blog_code_dump_count > 0 and blog_work_item_count == 0 else 0

        if member.contribution_source == "non_git":
            base_score = declared_score * 0.55 + statement_bonus + blog_post_score + blog_work_item_score - blog_penalty
        else:
            commit_score = 0 if max_commits <= 0 else (int(contrib.get("matched_commit_count") or 0) / max_commits) * 30
            addition_score = 0 if max_additions <= 0 else (int(contrib.get("matched_additions") or 0) / max_additions) * 20
            base_score = declared_score * 0.3 + commit_score + addition_score + statement_bonus + blog_post_score + blog_work_item_score - blog_penalty
        base_score += int(semantic.get("score_adjustment") or 0)

        if has_repo_binding and member.contribution_source in {"git", "mixed"} and int(contrib.get("matched_commit_count") or 0) == 0:
            base_score -= 10
        if blog_code_dump_count > 0:
            risk_flags.append(f"blog_code_dump:{member.student_name}")
        if blog_post_count == 0:
            risk_flags.append(f"blog_missing:{member.student_name}")

        workload_index = _clip_score(base_score)
        fallback_work_items = _statement_work_items(member.personal_statement)
        work_items = semantic.get("work_items") or fallback_work_items
        summary_text = semantic.get("summary") or _summary_text(
            {
                "contribution_source": member.contribution_source or "mixed",
                "matched_commit_count": contrib.get("matched_commit_count") or 0,
                "matched_additions": contrib.get("matched_additions") or 0,
                "declared_workload_percent": declared,
                "project_role": member.project_role,
                "blog_post_count": blog_post_count,
                "blog_work_item_count": blog_work_item_count,
                "personal_statement": member.personal_statement,
            },
            has_repo_binding,
        )

        evidence = [
            WorkloadEvidenceItem(label="贡献来源", value=str(member.contribution_source or "mixed")),
            WorkloadEvidenceItem(label="申报占比", value=f"{declared or 0}%"),
            WorkloadEvidenceItem(label="角色", value=member.project_role or "未填写"),
            WorkloadEvidenceItem(label="个人陈述", value="已填写" if (member.personal_statement or "").strip() else "未填写"),
            WorkloadEvidenceItem(label="博客篇数", value=str(blog_post_count)),
            WorkloadEvidenceItem(label="博客工作项", value=str(blog_work_item_count)),
        ]
        if blog_code_dump_count > 0:
            evidence.append(WorkloadEvidenceItem(label="纯代码倾向", value=str(blog_code_dump_count)))
        if blog_popular_science_count > 0:
            evidence.append(WorkloadEvidenceItem(label="科普文章", value=str(blog_popular_science_count)))
        if has_repo_binding:
            evidence.extend(
                [
                    WorkloadEvidenceItem(label="Git commits", value=str(int(contrib.get("matched_commit_count") or 0))),
                    WorkloadEvidenceItem(label="Git additions", value=str(int(contrib.get("matched_additions") or 0))),
                    WorkloadEvidenceItem(label="Git deletions", value=str(int(contrib.get("matched_deletions") or 0))),
                    WorkloadEvidenceItem(label="活跃周次", value=", ".join(contrib.get("matched_weeks") or []) or "无"),
                ]
            )

        members_payload.append(
            WorkloadMemberSummary(
                member_id=member.id,
                student_name=member.student_name,
                student_id=member.student_id,
                project_role=member.project_role,
                contribution_source=member.contribution_source or "mixed",
                workload_index=workload_index,
                rank_order=0,
                declared_workload_percent=declared,
                blog_post_count=blog_post_count,
                blog_code_dump_count=blog_code_dump_count,
                blog_popular_science_count=blog_popular_science_count,
                blog_work_item_count=blog_work_item_count,
                summary_text=summary_text,
                work_items=work_items,
                material_evidence=semantic.get("evidence") or submitted_material_evidence,
                analysis_confidence=semantic.get("confidence") or ("statement_based" if fallback_work_items else "rule_based"),
                evidence=evidence,
            )
        )

    unique_risk_flags = []
    seen = set()
    for flag in risk_flags:
        if flag in seen:
            continue
        seen.add(flag)
        unique_risk_flags.append(flag)

    members_payload.sort(key=lambda item: (item.workload_index, item.student_id), reverse=True)
    for index, item in enumerate(members_payload, start=1):
        item.rank_order = index

    return SubmissionWorkloadSummary(
        submission_id=submission.id,
        project_name=submission.project_name,
        group_name=submission.group_name,
        has_repo_binding=has_repo_binding,
        risk_flags=unique_risk_flags,
        total_blog_posts=total_blog_posts,
        members=members_payload,
    )
