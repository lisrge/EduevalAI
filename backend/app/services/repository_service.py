from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.repository import RepoBinding, RepoCommitSnapshot
from app.models.submission import AssignmentSubmission, SubmissionMember

GITEE_API_BASE = "https://gitee.com/api/v5"


def parse_gitee_repo_url(repo_url: str) -> tuple[str, str]:
    raw = (repo_url or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="repo_url is required")
    parsed = urlparse(raw)
    if "gitee.com" not in (parsed.netloc or ""):
        raise HTTPException(status_code=400, detail="only gitee repositories are supported")
    parts = [part for part in (parsed.path or "").split("/") if part]
    if len(parts) < 2:
        raise HTTPException(status_code=400, detail="invalid gitee repository url")
    owner = parts[0].strip()
    repo = parts[1].strip()
    if repo.endswith(".git"):
        repo = repo[:-4]
    if not owner or not repo:
        raise HTTPException(status_code=400, detail="invalid gitee repository url")
    return owner, repo


def upsert_repo_binding(
    db: Session,
    submission_id: int,
    repo_url: str,
    default_branch: str | None = None,
) -> RepoBinding:
    owner, repo = parse_gitee_repo_url(repo_url)
    binding = db.query(RepoBinding).filter(RepoBinding.submission_id == submission_id).first()
    if not binding:
        binding = RepoBinding(
            submission_id=submission_id,
            platform="gitee",
            repo_url=repo_url.strip(),
            repo_owner=owner,
            repo_name=repo,
            default_branch=(default_branch or "").strip() or None,
            sync_status="never_synced",
        )
        db.add(binding)
    else:
        binding.repo_url = repo_url.strip()
        binding.repo_owner = owner
        binding.repo_name = repo
        binding.default_branch = (default_branch or "").strip() or None
        if binding.auto_sync_enabled is None:
            binding.auto_sync_enabled = True
        binding.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(binding)
    return binding


def _commit_detail_url(binding: RepoBinding, commit_hash: str) -> str:
    return f"{GITEE_API_BASE}/repos/{binding.repo_owner}/{binding.repo_name}/commits/{commit_hash}"


def _commit_list_url(binding: RepoBinding) -> str:
    return f"{GITEE_API_BASE}/repos/{binding.repo_owner}/{binding.repo_name}/commits"


def sync_gitee_repo(db: Session, binding: RepoBinding, max_pages: int = 3, per_page: int = 50) -> int:
    inserted = 0
    existing_hashes = {
        item[0]
        for item in db.query(RepoCommitSnapshot.commit_hash).filter(RepoCommitSnapshot.binding_id == binding.id).all()
    }

    try:
        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            for page in range(1, max_pages + 1):
                params = {"page": page, "per_page": per_page}
                if binding.default_branch:
                    params["sha"] = binding.default_branch
                resp = client.get(_commit_list_url(binding), params=params)
                resp.raise_for_status()
                payload = resp.json()
                if not isinstance(payload, list) or not payload:
                    break

                for item in payload:
                    commit_hash = str(item.get("sha") or "").strip()
                    if not commit_hash or commit_hash in existing_hashes:
                        continue

                    commit_info = item.get("commit") or {}
                    author_info = commit_info.get("author") or {}
                    committed_at_raw = author_info.get("date")
                    if not committed_at_raw:
                        continue
                    committed_at = datetime.fromisoformat(str(committed_at_raw).replace("Z", "+00:00")).replace(tzinfo=None)

                    additions = 0
                    deletions = 0
                    changed_files = 0
                    try:
                        detail_resp = client.get(_commit_detail_url(binding, commit_hash))
                        detail_resp.raise_for_status()
                        detail = detail_resp.json()
                        stats = detail.get("stats") or {}
                        additions = int(stats.get("additions") or 0)
                        deletions = int(stats.get("deletions") or 0)
                        changed_files = len(detail.get("files") or [])
                    except Exception:
                        additions = 0
                        deletions = 0
                        changed_files = 0

                    db.add(
                        RepoCommitSnapshot(
                            binding_id=binding.id,
                            commit_hash=commit_hash,
                            author_name=author_info.get("name"),
                            author_email=author_info.get("email"),
                            message=(commit_info.get("message") or "").strip() or None,
                            committed_at=committed_at,
                            html_url=item.get("html_url"),
                            additions=additions,
                            deletions=deletions,
                            changed_files=changed_files,
                        )
                    )
                    existing_hashes.add(commit_hash)
                    inserted += 1

        binding.sync_status = "synced"
        binding.last_error = None
        binding.last_sync_at = datetime.utcnow()
        db.commit()
        db.refresh(binding)
        return inserted
    except httpx.HTTPError as exc:
        db.rollback()
        binding.sync_status = "failed"
        binding.last_error = str(exc)
        binding.last_sync_at = datetime.utcnow()
        db.add(binding)
        db.commit()
        db.refresh(binding)
        raise HTTPException(status_code=502, detail=f"gitee sync failed: {exc}") from exc


def build_weekly_stats(binding: RepoBinding) -> list[dict]:
    contribution = build_member_contribution_summary(binding)
    bucket: dict[tuple[int, int], dict] = {}
    member_week_map = contribution.get("member_week_map") or {}
    unmapped_week_map = contribution.get("unmapped_week_map") or {}
    for commit in binding.commits:
        iso_year, iso_week, _ = commit.committed_at.isocalendar()
        week_key = (iso_year, iso_week)
        monday = (commit.committed_at - timedelta(days=commit.committed_at.weekday())).date()
        sunday = monday + timedelta(days=6)
        if week_key not in bucket:
            bucket[week_key] = {
                "week_label": f"{iso_year}-W{iso_week:02d}",
                "week_start": monday.isoformat(),
                "week_end": sunday.isoformat(),
                "commit_count": 0,
                "authors": set(),
                "mapped_students": set(),
                "unmapped_authors": set(),
                "risk_flags": set(),
            }
        item = bucket[week_key]
        item["commit_count"] += 1
        if commit.author_name:
            item["authors"].add(commit.author_name)
        member_names = member_week_map.get(item["week_label"], set())
        for member_name in member_names:
            item["mapped_students"].add(member_name)
        for author_name in unmapped_week_map.get(item["week_label"], set()):
            item["unmapped_authors"].add(author_name)
        if item["unmapped_authors"]:
            item["risk_flags"].add("unmapped_git_authors_present")
        if item["commit_count"] > 0 and not item["mapped_students"]:
            item["risk_flags"].add("git_activity_without_student_mapping")

    rows = []
    for _, value in sorted(bucket.items(), key=lambda item: item[0], reverse=True):
        authors = sorted(value["authors"])
        rows.append(
            {
                "week_label": value["week_label"],
                "week_start": value["week_start"],
                "week_end": value["week_end"],
                "commit_count": value["commit_count"],
                "active_authors": len(authors),
                "authors": authors,
                "mapped_students": sorted(value["mapped_students"]),
                "unmapped_authors": sorted(value["unmapped_authors"]),
                "risk_flags": sorted(value["risk_flags"]),
            }
        )
    return rows


def _split_aliases(value: str | None) -> list[str]:
    if not value:
        return []
    result = []
    for raw in str(value).replace("\n", ",").split(","):
        item = raw.strip()
        if item:
            result.append(item.lower())
    return result


def build_member_contribution_summary(binding: RepoBinding) -> dict:
    submission: AssignmentSubmission = binding.submission
    members = list(submission.members or [])
    member_lookup: dict[int, dict] = {}
    author_name_map: dict[str, int] = {}
    author_email_map: dict[str, int] = {}
    member_week_map: dict[str, set[str]] = defaultdict(set)
    unmapped_week_map: dict[str, set[str]] = defaultdict(set)

    for member in members:
        aliases_name = _split_aliases(member.git_author_names) or [member.student_name.lower()]
        aliases_email = _split_aliases(member.git_author_emails)
        if not aliases_email and member.student_id:
            aliases_email.append(str(member.student_id).lower())
        member_lookup[member.id] = {
            "member_id": member.id,
            "student_name": member.student_name,
            "student_id": member.student_id,
            "project_role": member.project_role,
            "contribution_source": member.contribution_source or "mixed",
            "matched_commit_count": 0,
            "matched_additions": 0,
            "matched_deletions": 0,
            "matched_weeks": set(),
            "git_author_names": sorted(set(aliases_name)),
            "git_author_emails": sorted(set(aliases_email)),
            "has_repo_binding": bool(aliases_name or aliases_email),
        }
        for alias in aliases_name:
            author_name_map.setdefault(alias, member.id)
        for alias in aliases_email:
            author_email_map.setdefault(alias, member.id)

    unmapped_authors: set[str] = set()
    risk_flags: set[str] = set()
    for commit in binding.commits:
        week_label = f"{commit.committed_at.isocalendar()[0]}-W{commit.committed_at.isocalendar()[1]:02d}"
        author_name = (commit.author_name or "").strip().lower()
        author_email = (commit.author_email or "").strip().lower()
        member_id = None
        if author_email and author_email in author_email_map:
            member_id = author_email_map[author_email]
        elif author_name and author_name in author_name_map:
            member_id = author_name_map[author_name]

        if member_id and member_id in member_lookup:
            item = member_lookup[member_id]
            item["matched_commit_count"] += 1
            item["matched_additions"] += int(commit.additions or 0)
            item["matched_deletions"] += int(commit.deletions or 0)
            item["matched_weeks"].add(week_label)
            member_week_map[week_label].add(item["student_name"])
        else:
            display = commit.author_name or commit.author_email or commit.commit_hash[:8]
            unmapped_authors.add(display)
            unmapped_week_map[week_label].add(display)

    non_git_members = []
    for item in member_lookup.values():
        if item["contribution_source"] == "non_git":
            non_git_members.append(item["student_name"])
        elif item["contribution_source"] in {"git", "mixed"} and item["matched_commit_count"] == 0:
            risk_flags.add(f"member_without_git_activity:{item['student_name']}")

    if unmapped_authors:
        risk_flags.add("unmapped_git_authors_present")
    if non_git_members:
        risk_flags.add("non_git_members_present")

    members_payload = []
    for item in member_lookup.values():
        item["matched_weeks"] = sorted(item["matched_weeks"])
        members_payload.append(item)

    return {
        "members": members_payload,
        "unmapped_authors": sorted(unmapped_authors),
        "non_git_members": sorted(non_git_members),
        "risk_flags": sorted(risk_flags),
        "member_week_map": member_week_map,
        "unmapped_week_map": unmapped_week_map,
    }
