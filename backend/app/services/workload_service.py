from __future__ import annotations

from collections import defaultdict

from sqlalchemy.orm import object_session

from app.models.blog import BlogPost
from app.models.submission import AssignmentSubmission
from app.models.user import User
from app.schemas.workload import SubmissionWorkloadSummary, WorkloadEvidenceItem, WorkloadMemberSummary
from app.services.blog_crawler_service import loads_work_items
from app.services.repository_service import build_member_contribution_summary


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


def _summary_text(member: dict, has_repo_binding: bool) -> str:
    role = member.get("project_role") or "未填写角色"
    declared = member.get("declared_workload_percent") or 0
    blog_posts = int(member.get("blog_post_count") or 0)
    blog_work_items = int(member.get("blog_work_item_count") or 0)
    source = member.get("contribution_source") or "mixed"
    commits = int(member.get("matched_commit_count") or 0)
    additions = int(member.get("matched_additions") or 0)

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

        if has_repo_binding and member.contribution_source in {"git", "mixed"} and int(contrib.get("matched_commit_count") or 0) == 0:
            base_score -= 10
        if blog_code_dump_count > 0:
            risk_flags.append(f"blog_code_dump:{member.student_name}")
        if blog_post_count == 0:
            risk_flags.append(f"blog_missing:{member.student_name}")

        workload_index = _clip_score(base_score)

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
                summary_text=_summary_text(
                    {
                        "contribution_source": member.contribution_source or "mixed",
                        "matched_commit_count": contrib.get("matched_commit_count") or 0,
                        "matched_additions": contrib.get("matched_additions") or 0,
                        "declared_workload_percent": declared,
                        "project_role": member.project_role,
                        "blog_post_count": blog_post_count,
                        "blog_work_item_count": blog_work_item_count,
                    },
                    has_repo_binding,
                ),
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
