from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

import httpx
from sqlalchemy import case
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.blog import BlogPost
from app.models.submission import AssignmentSubmission, SubmissionMember
from app.models.teacher_review_assignment import TeacherReviewAssignment
from app.models.teacher_score import TeacherScoreRecord
from app.models.user import User
from app.schemas.blog import BlogPostInfo
from app.schemas.teacher_score import (
    MemberBlogSummary,
    SubmissionBlogSummary,
    TeacherAssigneeInfo,
    TeacherAssignmentUpdateResponse,
    TeacherGroupScoreRecommendation,
    TeacherMemberAggregateInfo,
    TeacherMemberBlogItem,
    TeacherMemberBlogListResponse,
    TeacherMemberScoreInfo,
    TeacherMemberScoreRecommendation,
    TeacherReviewQueueItem,
    TeacherScoreAggregate,
    TeacherScoreInfo,
    TeacherScoreRecommendation,
    TeacherSubmissionReview,
)
from app.schemas.workload import SubmissionWorkloadSummary, WorkloadMemberSummary
from app.services.workload_service import build_submission_workload_summary


def _fallback_blog_summary(text: str) -> str:
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    if not normalized:
        return ""
    return normalized[:160] + ("..." if len(normalized) > 160 else "")


def _generate_blog_summary(text: str, title: str, project_context: str = "") -> str:
    settings = get_settings()
    content = re.sub(r"\s+", " ", str(text or "")).strip()
    if not content:
        return ""
    if not settings.model_base_url or not settings.model_api_key:
        return _fallback_blog_summary(content)

    prompt = (
        "你是教师评分场景中的项目博客摘要助手。"
        "请基于下面的博客内容，输出一段 80-160 字的中文摘要。"
        "只保留和项目工作、问题、进度、实现结果相关的信息，不要输出列表、标题或客套话。"
        f"\n项目上下文：{project_context or '未知'}"
        f"\n博客标题：{title or '未命名博客'}"
        f"\n博客正文：{content[:8000]}"
    )
    try:
        response = httpx.post(
            settings.model_base_url.rstrip("/") + "/chat/completions",
            headers={"Authorization": f"Bearer {settings.model_api_key}", "Content-Type": "application/json"},
            json={
                "model": settings.model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
            },
            timeout=45.0,
        )
        response.raise_for_status()
        message = (
            response.json()
            .get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        summary = re.sub(r"\s+", " ", str(message or "")).strip()
        return summary[:240]
    except Exception:
        return _fallback_blog_summary(content)


def ensure_teacher_blog_summary(post: BlogPost, project_context: str = "") -> str:
    summary = str(post.summary or post.summary_text or "").strip()
    if summary:
        return summary
    content = str(post.content_md or post.content_text or "").strip()
    summary = _generate_blog_summary(content, post.title, project_context)
    if summary:
        post.summary_text = summary
        post.summary = summary
    return summary


def build_submission_blog_summary(db: Session, submission: AssignmentSubmission) -> SubmissionBlogSummary:
    members: list[SubmissionMember] = list(submission.members or [])
    if not members:
        return SubmissionBlogSummary()

    # 获取所有成员的用户ID
    member_student_ids = [str(m.student_id).strip() for m in members if str(m.student_id).strip()]
    member_map = {str(m.student_id).strip(): m for m in members}

    blog_summary = SubmissionBlogSummary()

    if member_student_ids:
        # 查询成员用户
        from app.models.user import User
        users = db.query(User).filter(User.student_id.in_(member_student_ids)).all()
        user_id_map = {u.id: u for u in users}
        student_id_to_user_id = {u.student_id: u.id for u in users}

        # 查询所有成员的博客
        user_ids = list(student_id_to_user_id.values())
        if user_ids:
            posts = (
                db.query(BlogPost)
                .filter(BlogPost.user_id.in_(user_ids))
                .order_by(BlogPost.published_at.desc(), BlogPost.created_at.desc())
                .all()
            )

            # 按学生分组
            blogs_by_student: dict[str, list[BlogPost]] = {}
            for post in posts:
                user = user_id_map.get(post.user_id)
                if user:
                    blogs_by_student.setdefault(user.student_id, []).append(post)

            # 构建成员博客摘要
            for member in members:
                sid = str(member.student_id).strip()
                member_blogs = blogs_by_student.get(sid, [])
                low_quality_count = sum(
                    1 for p in member_blogs
                    if (p.is_mostly_code or str(p.category) == "code_dump" or str(p.status) == "abnormal")
                )

                member_summary = MemberBlogSummary(
                    student_id=sid,
                    student_name=member.student_name or "",
                    blog_count=len(member_blogs),
                    low_quality_count=low_quality_count,
                    blogs=[
                        BlogPostInfo(
                            id=p.id,
                            user_id=p.user_id,
                            source_id=p.source_id,
                            title=p.title,
                            url=p.url,
                            status=p.status,
                            category=p.category,
                            summary_text=p.summary or p.summary_text,
                            work_items=[],
                            published_at=p.published_at,
                            word_count=p.word_count,
                            code_block_count=p.code_block_count,
                            number_count=p.number_count,
                            is_mostly_code=p.is_mostly_code,
                            is_popular_science=p.is_popular_science,
                            created_at=p.created_at,
                            updated_at=p.updated_at,
                        )
                        for p in member_blogs
                    ],
                )

                blog_summary.member_blogs.append(member_summary)
                blog_summary.total_blog_count += len(member_blogs)
                blog_summary.total_low_quality_count += low_quality_count

    return blog_summary


def _clamp_score(value: object, default: int = 0) -> int:
    try:
        score = int(round(float(value)))
    except Exception:
        score = default
    return max(0, min(100, score))


def _round_score(value: object) -> float:
    try:
        return round(float(value or 0), 1)
    except Exception:
        return 0.0


def percent_to_five_scale(value: object) -> int:
    try:
        normalized = Decimal(str(float(value or 0) / 20))
    except Exception:
        normalized = Decimal("0")
    rounded = normalized.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return max(0, min(5, int(rounded)))


def compute_group_total_values(project_display_score: object, project_innovation_score: object, key_highlight_score: object) -> float:
    return round(
        (_clamp_score(project_display_score) * 0.5)
        + (_clamp_score(project_innovation_score) * 0.3)
        + (_clamp_score(key_highlight_score) * 0.2),
        1,
    )


def compute_personal_total_values(personal_work_difficulty_score: object, live_demo_score: object) -> float:
    # 用户给出的 B 分权重是 30% + 10%，这里归一化回 0-100 百分制。
    return round(
        ((_clamp_score(personal_work_difficulty_score) * 30) + (_clamp_score(live_demo_score) * 10)) / 40,
        1,
    )


def compute_final_score_values(group_total_score: object, personal_total_score: object) -> float:
    return round(min(float(group_total_score or 0), float(personal_total_score or 0)), 1)


def compute_group_total_score(record: TeacherScoreRecord) -> float:
    return compute_group_total_values(
        record.project_display_score,
        record.project_innovation_score,
        record.key_highlight_score,
    )


def _member_name_map(submission: AssignmentSubmission | None) -> dict[str, str]:
    items: dict[str, str] = {}
    for member in list(getattr(submission, "members", []) or []):
        sid = str(getattr(member, "student_id", "") or "").strip()
        if sid:
            items[sid] = str(getattr(member, "student_name", "") or "")
    return items


def _parse_json_list(value: str | None) -> list[dict]:
    try:
        data = json.loads(str(value or "[]"))
    except Exception:
        data = []
    return [item for item in data if isinstance(item, dict)]


def parse_teacher_member_scores(
    record: TeacherScoreRecord,
    submission: AssignmentSubmission | None = None,
) -> list[TeacherMemberScoreInfo]:
    group_total_score = compute_group_total_score(record)
    raw_items = _parse_json_list(record.member_scores_json)
    raw_map = {
        str(item.get("student_id", "")).strip(): item
        for item in raw_items
        if str(item.get("student_id", "")).strip()
    }
    name_map = _member_name_map(submission)
    student_ids = list(name_map.keys()) or list(raw_map.keys())
    items: list[TeacherMemberScoreInfo] = []
    for sid in student_ids:
        raw = raw_map.get(sid, {})
        difficulty = _clamp_score(raw.get("personal_work_difficulty_score", 0))
        live_demo = _clamp_score(raw.get("live_demo_score", 100), default=100)
        personal_total = compute_personal_total_values(difficulty, live_demo)
        items.append(
            TeacherMemberScoreInfo(
                student_id=sid,
                student_name=name_map.get(sid, str(raw.get("student_name", "") or "")),
                personal_work_difficulty_score=difficulty,
                live_demo_score=live_demo,
                comment=str(raw.get("comment", "") or "").strip() or None,
                personal_total_score=personal_total,
                final_score=compute_final_score_values(group_total_score, personal_total),
            )
        )
    return items


def build_teacher_member_aggregates(
    records: list[TeacherScoreRecord],
    submission: AssignmentSubmission | None = None,
) -> list[TeacherMemberAggregateInfo]:
    name_map = _member_name_map(submission)
    student_ids = list(name_map.keys())
    if not student_ids:
        return []

    avg_group_total = round(
        sum(compute_group_total_score(item) for item in records) / max(len(records), 1),
        1,
    ) if records else 0.0
    member_score_map: dict[str, list[TeacherMemberScoreInfo]] = {sid: [] for sid in student_ids}
    for record in records:
        for item in parse_teacher_member_scores(record, submission):
            sid = str(item.student_id or "").strip()
            if sid in member_score_map:
                member_score_map[sid].append(item)

    result: list[TeacherMemberAggregateInfo] = []
    for sid in student_ids:
        items = member_score_map.get(sid, [])
        average_personal = round(
            sum(float(item.personal_total_score or 0) for item in items) / max(len(items), 1),
            1,
        ) if items else 0.0
        capped_final = compute_final_score_values(avg_group_total, average_personal)
        result.append(
            TeacherMemberAggregateInfo(
                student_id=sid,
                student_name=name_map.get(sid, ""),
                score_count=len(items),
                average_personal_score=average_personal,
                capped_final_score=capped_final,
                five_scale_score=percent_to_five_scale(capped_final),
            )
        )
    return result


def compute_total_score(record: TeacherScoreRecord, submission: AssignmentSubmission | None = None) -> float:
    group_total_score = compute_group_total_score(record)
    member_scores = parse_teacher_member_scores(record, submission)
    if not member_scores:
        return group_total_score
    return round(
        sum(compute_final_score_values(group_total_score, item.personal_total_score) for item in member_scores) / len(member_scores),
        1,
    )


def to_teacher_score_info(record: TeacherScoreRecord, submission: AssignmentSubmission | None = None) -> TeacherScoreInfo:
    teacher = getattr(record, "teacher", None)
    return TeacherScoreInfo(
        id=record.id,
        submission_id=record.submission_id,
        teacher_user_id=record.teacher_user_id,
        teacher_student_id=getattr(teacher, "student_id", "") or "",
        project_display_score=_clamp_score(record.project_display_score),
        project_innovation_score=_clamp_score(record.project_innovation_score),
        key_highlight_score=_clamp_score(record.key_highlight_score),
        member_scores=parse_teacher_member_scores(record, submission),
        comment=record.comment,
        group_total_score=compute_group_total_score(record),
        total_score=_round_score(record.total_score),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def build_teacher_score_aggregate(
    records: list[TeacherScoreRecord],
    submission: AssignmentSubmission | None = None,
) -> TeacherScoreAggregate:
    if not records:
        return TeacherScoreAggregate()

    count = len(records)
    member_aggregates = build_teacher_member_aggregates(records, submission)
    average_member_personal = round(
        sum(float(item.average_personal_score or 0) for item in member_aggregates) / len(member_aggregates),
        2,
    ) if member_aggregates else 0
    average_member_final = round(
        sum(float(item.capped_final_score or 0) for item in member_aggregates) / len(member_aggregates),
        2,
    ) if member_aggregates else 0
    average_five_scale = round(
        sum(float(item.five_scale_score or 0) for item in member_aggregates) / len(member_aggregates),
        2,
    ) if member_aggregates else 0
    return TeacherScoreAggregate(
        assigned_teacher_count=0,
        score_count=count,
        average_total_score=average_member_final,
        average_group_total_score=round(sum(compute_group_total_score(item) for item in records) / count, 2),
        average_project_display_score=round(sum(_clamp_score(item.project_display_score) for item in records) / count, 2),
        average_project_innovation_score=round(sum(_clamp_score(item.project_innovation_score) for item in records) / count, 2),
        average_key_highlight_score=round(sum(_clamp_score(item.key_highlight_score) for item in records) / count, 2),
        average_member_personal_score=average_member_personal,
        average_five_scale_score=average_five_scale,
    )


def find_my_teacher_score(records: list[TeacherScoreRecord], user_id: int) -> TeacherScoreRecord | None:
    for item in records:
        if int(item.teacher_user_id) == int(user_id):
            return item
    return None


def build_assignee_info(records: list[TeacherReviewAssignment]) -> list[TeacherAssigneeInfo]:
    items: list[TeacherAssigneeInfo] = []
    for record in records:
        teacher = getattr(record, "teacher", None)
        if not teacher:
            continue
        items.append(
            TeacherAssigneeInfo(
                teacher_user_id=record.teacher_user_id,
                teacher_student_id=teacher.student_id,
            )
        )
    return items


def build_teacher_review(
    db: Session,
    submission: AssignmentSubmission,
    my_user: User,
    submission_detail,
) -> TeacherSubmissionReview:
    records = list(submission.teacher_scores or [])
    assignees = list(submission.teacher_assignments or [])
    my_score = find_my_teacher_score(records, my_user.id)
    assigned_teacher_ids = {item.teacher_user_id for item in assignees}
    aggregate = build_teacher_score_aggregate(records, submission)
    member_aggregates = build_teacher_member_aggregates(records, submission)
    aggregate.assigned_teacher_count = len(assigned_teacher_ids)
    workload: SubmissionWorkloadSummary = build_submission_workload_summary(submission)
    blog_summary: SubmissionBlogSummary = build_submission_blog_summary(db, submission)
    ai_recommendation = get_teacher_score_recommendation_snapshot(submission, workload, blog_summary)
    return TeacherSubmissionReview(
        submission=submission_detail,
        workload=workload,
        blog_summary=blog_summary,
        my_score=to_teacher_score_info(my_score, submission) if my_score else None,
        ai_recommendation=ai_recommendation,
        aggregate=aggregate,
        member_aggregates=member_aggregates,
        all_scores=[to_teacher_score_info(item, submission) for item in records],
        assigned_teachers=build_assignee_info(assignees),
        assigned_to_me=my_user.id in assigned_teacher_ids,
    )


def build_teacher_queue_item(
    submission: AssignmentSubmission,
    my_user: User,
    submission_summary,
) -> TeacherReviewQueueItem:
    records = list(submission.teacher_scores or [])
    assignees = list(submission.teacher_assignments or [])
    my_score = find_my_teacher_score(records, my_user.id)
    assigned_teacher_ids = {item.teacher_user_id for item in assignees}
    aggregate = build_teacher_score_aggregate(records, submission)
    aggregate.assigned_teacher_count = len(assigned_teacher_ids)
    return TeacherReviewQueueItem(
        submission=submission_summary,
        my_score=to_teacher_score_info(my_score, submission) if my_score else None,
        aggregate=aggregate,
        reviewed_by_me=my_score is not None,
        assigned_teachers=build_assignee_info(assignees),
        assigned_to_me=my_user.id in assigned_teacher_ids,
    )


def build_teacher_assignment_response(submission: AssignmentSubmission) -> TeacherAssignmentUpdateResponse:
    aggregate = build_teacher_score_aggregate(list(submission.teacher_scores or []), submission)
    aggregate.assigned_teacher_count = len(list(submission.teacher_assignments or []))
    return TeacherAssignmentUpdateResponse(
        message="teacher assignments updated",
        assigned_teachers=build_assignee_info(list(submission.teacher_assignments or [])),
        aggregate=aggregate,
    )


def build_teacher_member_blog_list(
    db: Session,
    submission: AssignmentSubmission,
    student_id: str,
) -> TeacherMemberBlogListResponse:
    sid = str(student_id or "").strip()
    member = next((item for item in list(submission.members or []) if str(item.student_id or "").strip() == sid), None)
    if member is None:
        raise ValueError("submission member not found")

    user = db.query(User).filter(User.student_id == sid).first()
    if user is None:
        return TeacherMemberBlogListResponse(
            submission_id=submission.id,
            student_id=sid,
            student_name=member.student_name or sid,
            project_name=submission.project_name,
            group_name=submission.group_name,
            total_blog_count=0,
            blogs=[],
        )

    rows = (
        db.query(BlogPost)
        .filter(BlogPost.user_id == user.id)
        .order_by(
            case((BlogPost.published_at.is_(None), 1), else_=0).asc(),
            BlogPost.published_at.asc(),
            BlogPost.created_at.asc(),
            BlogPost.id.asc(),
        )
        .all()
    )
    blogs: list[TeacherMemberBlogItem] = []
    mutated = False
    for row in rows:
        before = str(row.summary_text or row.summary or "").strip()
        summary = ensure_teacher_blog_summary(row, submission.project_name or submission.group_name or "")
        if summary and summary != before:
            mutated = True
        blogs.append(
            TeacherMemberBlogItem(
                id=row.id,
                title=row.title,
                url=row.url,
                status=row.status,
                category=row.category,
                summary_text=summary,
                published_at=row.published_at,
                word_count=row.word_count,
                is_mostly_code=row.is_mostly_code,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
        )
    if mutated:
        db.commit()
    return TeacherMemberBlogListResponse(
        submission_id=submission.id,
        student_id=sid,
        student_name=member.student_name or sid,
        project_name=submission.project_name,
        group_name=submission.group_name,
        total_blog_count=len(blogs),
        blogs=blogs,
    )


def serialize_member_scores_payload(payload_member_scores: list[dict] | list[object], submission: AssignmentSubmission) -> str:
    existing_map = {}
    for item in payload_member_scores or []:
        sid = str(getattr(item, "student_id", None) or (item.get("student_id") if isinstance(item, dict) else "")).strip()
        if not sid:
            continue
        existing_map[sid] = item

    serialized: list[dict] = []
    for member in list(submission.members or []):
        sid = str(member.student_id or "").strip()
        raw = existing_map.get(sid)
        if raw is None:
            difficulty = 0
            live_demo = 100
            comment = None
        else:
            if isinstance(raw, dict):
                difficulty = raw.get("personal_work_difficulty_score", 0)
                live_demo = raw.get("live_demo_score", 100)
                comment = raw.get("comment")
            else:
                difficulty = getattr(raw, "personal_work_difficulty_score", 0)
                live_demo = getattr(raw, "live_demo_score", 100)
                comment = getattr(raw, "comment", None)
        serialized.append(
            {
                "student_id": sid,
                "student_name": member.student_name or "",
                "personal_work_difficulty_score": _clamp_score(difficulty),
                "live_demo_score": _clamp_score(live_demo, default=100),
                "comment": str(comment or "").strip() or None,
            }
        )
    return json.dumps(serialized, ensure_ascii=False)


def _compact_text(text: object, limit: int = 1200) -> str:
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit] + "..."


def _get_evidence_int(member: WorkloadMemberSummary, label: str) -> int:
    for item in list(member.evidence or []):
        if str(item.label or "") == label:
            digits = re.findall(r"-?\d+", str(item.value or ""))
            if digits:
                try:
                    return int(digits[0])
                except Exception:
                    return 0
    return 0


def _build_teacher_score_context(
    submission: AssignmentSubmission,
    workload: SubmissionWorkloadSummary,
    blog_summary: SubmissionBlogSummary,
) -> str:
    assets = ", ".join(sorted({str(asset.asset_type or "") for asset in list(submission.assets or []) if str(asset.asset_type or "").strip()}))
    code = getattr(submission, "code_analysis", None)
    repo = getattr(submission, "repo_binding", None)
    repo_commits = list(getattr(repo, "commits", []) or [])
    repo_analysis = {}
    try:
        repo_analysis = json.loads(str(getattr(repo, "analysis_summary_json", "") or "{}"))
        if not isinstance(repo_analysis, dict):
            repo_analysis = {}
    except Exception:
        repo_analysis = {}
    repo_lines = [
        f"{idx + 1}. {str(commit.author_name or '').strip()} / +{int(commit.additions or 0)} -{int(commit.deletions or 0)} / {_compact_text(commit.message, 120)}"
        for idx, commit in enumerate(repo_commits[:12])
    ]
    repo_code_summary = repo_analysis.get("code_summary") if isinstance(repo_analysis.get("code_summary"), dict) else {}
    repo_language_summary = "；".join(
        [
            f"{item.get('language')} {item.get('percent')}%"
            for item in list(repo_code_summary.get("languages") or [])[:6]
            if isinstance(item, dict)
        ]
    ) or "无"
    repo_member_map = {
        str(item.get("student_id", "")).strip(): item
        for item in list(repo_analysis.get("members") or [])
        if isinstance(item, dict) and str(item.get("student_id", "")).strip()
    }
    members_by_blog = {str(item.student_id): item for item in list(blog_summary.member_blogs or [])}
    member_sections: list[str] = []
    for member in list(workload.members or []):
        member_blog = members_by_blog.get(str(member.student_id), None)
        repo_member = repo_member_map.get(str(member.student_id), {})
        blog_lines = []
        for blog in list(getattr(member_blog, "blogs", []) or [])[:6]:
            blog_lines.append(f"- {blog.title}: {_compact_text(blog.summary_text, 180)}")
        member_sections.append(
            "\n".join(
                [
                    f"成员：{member.student_name}（{member.student_id}）",
                    f"角色：{member.project_role or '未填写'}；贡献来源：{member.contribution_source}",
                    f"工作概要：{_compact_text(member.summary_text, 240)}",
                    f"个人概述：{_compact_text(member.personal_statement, 220)}",
                    (
                        f"Gitee昵称：{repo_member.get('gitee_login') or '未绑定'}；"
                        f"代码工作量：{int(repo_member.get('workload_value') or 0)}；"
                        f"占比：{float(repo_member.get('workload_percent') or 0):.1f}%"
                    ),
                    f"识别工作项：{'；'.join(list(member.work_items or [])[:8]) or '无'}",
                    f"博客数：{member.blog_post_count}；博客工作项：{member.blog_work_item_count}；Git提交：{_get_evidence_int(member, 'Git commits')}；Git新增：{_get_evidence_int(member, 'Git additions')} 行",
                    f"博客摘要：{' '.join(blog_lines) if blog_lines else '无'}",
                ]
            )
        )
    return "\n\n".join(
        [
            f"项目名称：{submission.project_name or '未填写'}",
            f"小组名称：{submission.group_name or '未填写'}",
            f"提交说明：{_compact_text(submission.statement_text, 500)}",
            f"完整性状态：{submission.completeness_status}；附件类型：{assets or '无'}；成员数：{len(list(submission.members or []))}",
            (
                f"代码分析：总文件 {getattr(code, 'total_files', 0)}，源文件 {getattr(code, 'source_file_count', 0)}，"
                f"总代码行 {getattr(code, 'total_lines', 0)}，主语言 {getattr(code, 'dominant_language', '') or '未知'}，"
                f"风险 {getattr(code, 'risk_level', '') or 'unknown'}，标记 {'；'.join(list(getattr(code, 'risk_flags', []) or [])[:8]) or '无'}"
            ),
            (
                f"仓库：{getattr(repo, 'repo_url', '') or '未绑定'}；同步状态：{getattr(repo, 'sync_status', '') or 'unknown'}；"
                f"最近提交：{' | '.join(repo_lines) if repo_lines else '暂未抓到提交记录'}"
            ),
            (
                f"Gitee代码概览：总代码行 {int(repo_code_summary.get('total_lines') or 0)}，"
                f"总文件 {int(repo_code_summary.get('total_files') or 0)}，"
                f"源文件 {int(repo_code_summary.get('source_file_count') or 0)}，"
                f"估计体积 {float(repo_code_summary.get('estimated_kb') or 0):.1f} KB，"
                f"主语言 {repo_code_summary.get('dominant_language') or '未知'}，"
                f"语言分布 {repo_language_summary}"
            ),
            f"博客总量：{blog_summary.total_blog_count}；低质量博客：{blog_summary.total_low_quality_count}",
            "成员材料：\n" + "\n\n".join(member_sections),
        ]
    )


def _fallback_teacher_score_recommendation(
    submission: AssignmentSubmission,
    workload: SubmissionWorkloadSummary,
    blog_summary: SubmissionBlogSummary,
) -> TeacherScoreRecommendation:
    code = getattr(submission, "code_analysis", None)
    total_lines = int(getattr(code, "total_lines", 0) or 0)
    total_work_items = sum(int(item.blog_work_item_count or 0) for item in list(workload.members or []))
    total_commits = sum(_get_evidence_int(item, "Git commits") for item in list(workload.members or []))
    project_display_score = _clamp_score(
        55
        + min(int(blog_summary.total_blog_count or 0) * 3, 15)
        + min(len(str(submission.statement_text or "").strip()) // 80, 15)
        + (10 if str(submission.completeness_status or "").lower() == "complete" else 0)
    )
    project_innovation_score = _clamp_score(
        48
        + min(total_work_items * 2, 18)
        + min(total_lines // 300, 16)
        + (8 if str(submission.project_name or submission.statement_text or "").find("大模型") >= 0 else 0)
    )
    key_highlight_score = _clamp_score(
        50
        + min(total_commits * 2, 18)
        + min(total_lines // 400, 16)
        - min(int(blog_summary.total_low_quality_count or 0) * 5, 15)
    )
    group_total_score = compute_group_total_values(project_display_score, project_innovation_score, key_highlight_score)
    member_items: list[TeacherMemberScoreRecommendation] = []
    for member in list(workload.members or []):
        difficulty = _clamp_score(
            48
            + min(int(member.blog_work_item_count or 0) * 3, 18)
            + min(_get_evidence_int(member, "Git commits") * 2, 14)
            + min(_get_evidence_int(member, "Git additions") // 150, 14)
        )
        personal_total = compute_personal_total_values(difficulty, 100)
        member_items.append(
            TeacherMemberScoreRecommendation(
                student_id=member.student_id,
                student_name=member.student_name,
                personal_work_difficulty_score=difficulty,
                live_demo_score=100,
                personal_total_score=personal_total,
                final_score=compute_final_score_values(group_total_score, personal_total),
                reason="基于博客工作项、Git 活跃度、代码体量和个人说明进行了规则推荐；现场展示效果按要求默认 100。",
            )
        )
    return TeacherScoreRecommendation(
        source_model=get_settings().model_name,
        generated_at=datetime.utcnow(),
        needs_human_review=True,
        overview="当前为规则推荐值，建议老师结合现场展示和实际代码质量人工校正。",
        group=TeacherGroupScoreRecommendation(
            project_display_score=project_display_score,
            project_innovation_score=project_innovation_score,
            key_highlight_score=key_highlight_score,
            group_total_score=group_total_score,
            reason="结合提交完整性、博客产出、工作项、代码规模和仓库活跃度生成规则推荐值。",
        ),
        members=member_items,
    )


def _generate_teacher_score_recommendation(
    submission: AssignmentSubmission,
    workload: SubmissionWorkloadSummary,
    blog_summary: SubmissionBlogSummary,
) -> TeacherScoreRecommendation:
    settings = get_settings()
    if not settings.model_base_url or not settings.model_api_key:
        return _fallback_teacher_score_recommendation(submission, workload, blog_summary)

    prompt = (
        "你是教师项目评分推荐助手，请根据给定材料给出教师评分推荐值。"
        "评分规则：\n"
        "1. 小组分数 A：项目展示度和完整性 50%，项目创新性 30%，关键亮点 20%。\n"
        "2. 个人分数 B：个人工作难度 30%，现场展示效果 10%。现场展示效果不需要分析，固定推荐 100。\n"
        "3. 所有原始单项分都是 0-100 的整数。\n"
        "4. B 分请按百分制归一化：personal_total_score=(difficulty*30+100*10)/40。\n"
        "5. 最终分数 final_score=min(A分, B分)。\n"
        "只返回 JSON，字段结构必须为："
        '{"overview":"","needs_human_review":false,"group":{"project_display_score":0,"project_innovation_score":0,"key_highlight_score":0,"reason":""},'
        '"members":[{"student_id":"","personal_work_difficulty_score":0,"reason":""}]}\n\n'
        f"材料如下：\n{_build_teacher_score_context(submission, workload, blog_summary)[:15000]}"
    )
    try:
        response = httpx.post(
            settings.model_base_url.rstrip("/") + "/chat/completions",
            headers={"Authorization": f"Bearer {settings.model_api_key}", "Content-Type": "application/json"},
            json={
                "model": settings.model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
            },
            timeout=90.0,
        )
        response.raise_for_status()
        content = (
            response.json()
            .get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        parsed = json.loads(str(content or "{}"))
        group = parsed.get("group") or {}
        group_display_score = _clamp_score(group.get("project_display_score", 0))
        group_innovation_score = _clamp_score(group.get("project_innovation_score", 0))
        key_highlight_score = _clamp_score(group.get("key_highlight_score", 0))
        group_total_score = compute_group_total_values(group_display_score, group_innovation_score, key_highlight_score)
        member_name_map = _member_name_map(submission)
        members_raw = parsed.get("members") if isinstance(parsed.get("members"), list) else []
        member_raw_map = {
            str(item.get("student_id", "")).strip(): item
            for item in members_raw
            if isinstance(item, dict) and str(item.get("student_id", "")).strip()
        }
        member_items: list[TeacherMemberScoreRecommendation] = []
        for sid, student_name in member_name_map.items():
            raw = member_raw_map.get(sid, {})
            difficulty = _clamp_score(raw.get("personal_work_difficulty_score", 0))
            personal_total = compute_personal_total_values(difficulty, 100)
            member_items.append(
                TeacherMemberScoreRecommendation(
                    student_id=sid,
                    student_name=student_name,
                    personal_work_difficulty_score=difficulty,
                    live_demo_score=100,
                    personal_total_score=personal_total,
                    final_score=compute_final_score_values(group_total_score, personal_total),
                    reason=_compact_text(raw.get("reason", ""), 240),
                )
            )
        return TeacherScoreRecommendation(
            source_model=settings.model_name,
            generated_at=datetime.utcnow(),
            needs_human_review=bool(parsed.get("needs_human_review", False)),
            overview=_compact_text(parsed.get("overview", ""), 400),
            group=TeacherGroupScoreRecommendation(
                project_display_score=group_display_score,
                project_innovation_score=group_innovation_score,
                key_highlight_score=key_highlight_score,
                group_total_score=group_total_score,
                reason=_compact_text(group.get("reason", ""), 320),
            ),
            members=member_items,
        )
    except Exception:
        return _fallback_teacher_score_recommendation(submission, workload, blog_summary)


def _recommendation_to_dict(recommendation: TeacherScoreRecommendation) -> dict:
    return {
        "source_model": recommendation.source_model,
        "generated_at": recommendation.generated_at.isoformat() if recommendation.generated_at else None,
        "needs_human_review": recommendation.needs_human_review,
        "overview": recommendation.overview,
        "group": recommendation.group.model_dump(),
        "members": [item.model_dump() for item in recommendation.members],
    }


def _recommendation_from_dict(data: dict | None) -> TeacherScoreRecommendation:
    payload = dict(data or {})
    generated_at = payload.get("generated_at")
    if isinstance(generated_at, str) and generated_at:
        try:
            payload["generated_at"] = datetime.fromisoformat(generated_at)
        except Exception:
            payload["generated_at"] = None
    return TeacherScoreRecommendation.model_validate(payload)


def load_cached_teacher_score_recommendation(submission: AssignmentSubmission) -> TeacherScoreRecommendation | None:
    raw = str(getattr(submission, "teacher_review_ai_json", "") or "").strip()
    if not raw:
        return None
    try:
        return _recommendation_from_dict(json.loads(raw))
    except Exception:
        return None


def teacher_score_recommendation_needs_refresh(
    submission: AssignmentSubmission,
    recommendation: TeacherScoreRecommendation | None = None,
) -> bool:
    item = recommendation or load_cached_teacher_score_recommendation(submission)
    if item is None:
        return True
    generated_at = item.generated_at
    if generated_at is None:
        return True
    updated_at = getattr(submission, "updated_at", None)
    if updated_at and generated_at < updated_at:
        return True
    max_age_hours = max(1, int(get_settings().teacher_score_refresh_max_age_hours or 24))
    return generated_at <= (datetime.utcnow() - timedelta(hours=max_age_hours))


def get_teacher_score_recommendation_snapshot(
    submission: AssignmentSubmission,
    workload: SubmissionWorkloadSummary,
    blog_summary: SubmissionBlogSummary,
) -> TeacherScoreRecommendation:
    cached = load_cached_teacher_score_recommendation(submission)
    if cached is not None:
        return cached
    return _fallback_teacher_score_recommendation(submission, workload, blog_summary)


def refresh_teacher_score_recommendation(
    db: Session,
    submission: AssignmentSubmission,
) -> TeacherScoreRecommendation:
    workload: SubmissionWorkloadSummary = build_submission_workload_summary(submission)
    blog_summary: SubmissionBlogSummary = build_submission_blog_summary(db, submission)
    recommendation = _generate_teacher_score_recommendation(submission, workload, blog_summary)
    submission.teacher_review_ai_json = json.dumps(_recommendation_to_dict(recommendation), ensure_ascii=False)
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return recommendation


def ensure_teacher_score_recommendation(
    db: Session,
    submission: AssignmentSubmission,
    workload: SubmissionWorkloadSummary,
    blog_summary: SubmissionBlogSummary,
) -> TeacherScoreRecommendation:
    cached = load_cached_teacher_score_recommendation(submission)
    if cached is not None and not teacher_score_recommendation_needs_refresh(submission, cached):
        return cached
    recommendation = _generate_teacher_score_recommendation(submission, workload, blog_summary)
    try:
        submission.teacher_review_ai_json = json.dumps(_recommendation_to_dict(recommendation), ensure_ascii=False)
        db.add(submission)
        db.commit()
        db.refresh(submission)
    except Exception:
        db.rollback()
    return recommendation
