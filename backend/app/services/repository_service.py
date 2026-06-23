from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
import re
from urllib.parse import urlparse

from fastapi import HTTPException
import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.repository import RepoBinding, RepoCommitSnapshot
from app.models.submission import AssignmentSubmission
from app.services.csdn_crawler_service import (
    PLAYWRIGHT_AVAILABLE,
    is_port_open,
    parse_cdp_port,
    start_chrome_if_needed,
)

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


def _browser_fetch_json(page, url: str):
    return page.evaluate(
        """async ({ url }) => {
            const response = await fetch(url, {
                method: 'GET',
                credentials: 'include',
                headers: {
                    'Accept': 'application/json, text/plain, */*',
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            const text = await response.text();
            let payload = null;
            try {
                payload = JSON.parse(text);
            } catch (error) {
                payload = text;
            }
            return { ok: response.ok, status: response.status, payload };
        }""",
        {"url": url},
    )


def _fetch_graph_payload_via_browser(binding: RepoBinding, branch: str) -> dict:
    if not PLAYWRIGHT_AVAILABLE:
        raise HTTPException(status_code=500, detail="playwright is not available")

    from playwright.sync_api import sync_playwright

    settings = get_settings()
    host, port = parse_cdp_port(settings.blog_cdp_url)
    if not is_port_open(host, port) and settings.blog_launch_chrome:
        start_chrome_if_needed(settings)

    graph_url = f"https://gitee.com/{binding.repo_owner}/{binding.repo_name}/graph/{branch}"
    graph_json_url = f"https://gitee.com/{binding.repo_owner}/{binding.repo_name}/graph/{branch}.json"
    playwright = sync_playwright().start()
    browser = None
    context = None
    page = None
    owns_browser = False
    try:
        if is_port_open(host, port):
            browser = playwright.chromium.connect_over_cdp(settings.blog_cdp_url)
            context = browser.contexts[0] if browser.contexts else browser.new_context(viewport={"width": 1440, "height": 900})
        else:
            browser = playwright.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage", "--disable-infobars"],
            )
            owns_browser = True
            context = browser.new_context(
                viewport={"width": 1440, "height": 900},
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
                ignore_https_errors=True,
            )
            context.add_init_script(
                """
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en']});
                window.chrome = {runtime: {}};
                """
            )
        page = context.new_page()
        page.set_default_timeout(60000)
        page.goto(graph_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2500)
        resp = _browser_fetch_json(page, graph_json_url)
        if not resp.get("ok") or not isinstance(resp.get("payload"), dict):
            raise HTTPException(status_code=502, detail=f"gitee graph browser fetch failed: status={resp.get('status')}")
        return resp["payload"]
    finally:
        try:
            if page:
                page.close()
        except Exception:
            pass
        try:
            if context and owns_browser:
                context.close()
        except Exception:
            pass
        try:
            if browser and owns_browser:
                browser.close()
        except Exception:
            pass
        try:
            playwright.stop()
        except Exception:
            pass


def _fetch_graph_payload(binding: RepoBinding, branch: str) -> dict:
    graph_json_url = f"https://gitee.com/{binding.repo_owner}/{binding.repo_name}/graph/{branch}.json"
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            response = client.get(
                graph_json_url,
                headers={
                    "Accept": "application/json,text/plain,*/*",
                    "User-Agent": "Mozilla/5.0",
                },
            )
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, dict) and isinstance(payload.get("commits"), list):
                return payload
    except Exception:
        pass
    return _fetch_graph_payload_via_browser(binding, branch)


def _extract_commit_stats(item: dict) -> tuple[int, int, int]:
    additions = item.get("additions")
    deletions = item.get("deletions")
    changed_files = item.get("changed_files")
    try:
        additions = int(additions or 0)
    except (TypeError, ValueError):
        additions = 0
    try:
        deletions = int(deletions or 0)
    except (TypeError, ValueError):
        deletions = 0
    try:
        changed_files = int(changed_files or 0)
    except (TypeError, ValueError):
        changed_files = 0
    return additions, deletions, changed_files


def sync_gitee_repo(db: Session, binding: RepoBinding, max_pages: int = 3, per_page: int = 50) -> int:
    inserted = 0
    existing_hashes = {
        item[0]
        for item in db.query(RepoCommitSnapshot.commit_hash).filter(RepoCommitSnapshot.binding_id == binding.id).all()
    }

    try:
        branch = (binding.default_branch or "").strip() or "master"
        payload = _fetch_graph_payload(binding, branch)
        commits = list(payload.get("commits") or [])
        if max_pages > 0 and per_page > 0:
            commits = commits[: max_pages * per_page]

        for item in commits:
            commit_hash = str(item.get("id") or "").strip()
            if not commit_hash or commit_hash in existing_hashes:
                continue

            author_info = item.get("author") or {}
            committed_at_raw = item.get("date")
            if not committed_at_raw:
                continue
            committed_at = datetime.fromisoformat(str(committed_at_raw).replace("Z", "+00:00")).replace(tzinfo=None)
            additions, deletions, changed_files = _extract_commit_stats(item)

            db.add(
                RepoCommitSnapshot(
                    binding_id=binding.id,
                    commit_hash=commit_hash,
                    author_name=author_info.get("name"),
                    author_email=author_info.get("email"),
                    message=(item.get("message") or "").strip() or None,
                    committed_at=committed_at,
                    html_url=f"https://gitee.com/{binding.repo_owner}/{binding.repo_name}/commit/{commit_hash}",
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
    except HTTPException as exc:
        db.rollback()
        binding.sync_status = "failed"
        binding.last_error = str(exc.detail or exc)
        binding.last_sync_at = datetime.utcnow()
        db.add(binding)
        db.commit()
        db.refresh(binding)
        raise
    except Exception as exc:
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
    author_name_map: dict[str, dict] = {}
    author_email_map: dict[str, dict] = {}
    for member in contribution.get("members") or []:
        for alias in member.get("git_author_names") or []:
            author_name_map.setdefault(alias.lower(), member)
        for alias in member.get("git_author_emails") or []:
            author_email_map.setdefault(alias.lower(), member)

    def summarize(messages: list[str], fallback: str) -> str:
        cleaned: list[str] = []
        for message in messages:
            first_line = (message or "").splitlines()[0].strip()
            first_line = re.sub(r"^(feat|fix|docs|refactor|test|chore|style|perf)(\([^)]*\))?[:：]\s*", "", first_line, flags=re.I)
            if first_line and first_line not in cleaned:
                cleaned.append(first_line)
        if not cleaned:
            return fallback
        return "；".join(cleaned[:6])[:500]

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
                "additions": 0,
                "deletions": 0,
                "changed_files": 0,
                "authors": set(),
                "mapped_students": set(),
                "unmapped_authors": set(),
                "risk_flags": set(),
                "messages": [],
                "members": {},
            }
        item = bucket[week_key]
        item["commit_count"] += 1
        item["additions"] += int(commit.additions or 0)
        item["deletions"] += int(commit.deletions or 0)
        item["changed_files"] += int(commit.changed_files or 0)
        if commit.message:
            item["messages"].append(commit.message)
        if commit.author_name:
            item["authors"].add(commit.author_name)
        author_name = (commit.author_name or "").strip().lower()
        author_email = (commit.author_email or "").strip().lower()
        member = author_email_map.get(author_email) if author_email else None
        if member is None and author_name:
            member = author_name_map.get(author_name)
        if member:
            student_name = member["student_name"]
            item["mapped_students"].add(student_name)
            member_stat = item["members"].setdefault(
                student_name,
                {"student_name": student_name, "commit_count": 0, "additions": 0, "deletions": 0, "changed_files": 0, "messages": []},
            )
            member_stat["commit_count"] += 1
            member_stat["additions"] += int(commit.additions or 0)
            member_stat["deletions"] += int(commit.deletions or 0)
            member_stat["changed_files"] += int(commit.changed_files or 0)
            if commit.message:
                member_stat["messages"].append(commit.message)
        else:
            item["unmapped_authors"].add(commit.author_name or commit.author_email or commit.commit_hash[:8])
        if item["unmapped_authors"]:
            item["risk_flags"].add("unmapped_git_authors_present")
        if item["commit_count"] > 0 and not item["mapped_students"]:
            item["risk_flags"].add("git_activity_without_student_mapping")

    rows = []
    for _, value in sorted(bucket.items(), key=lambda item: item[0], reverse=True):
        authors = sorted(value["authors"])
        member_rows = []
        for member in sorted(value["members"].values(), key=lambda row: (-row["commit_count"], row["student_name"])):
            member_rows.append(
                {
                    "student_name": member["student_name"],
                    "commit_count": member["commit_count"],
                    "additions": member["additions"],
                    "deletions": member["deletions"],
                    "changed_files": member["changed_files"],
                    "work_summary": summarize(member["messages"], "有代码提交，但提交说明不足。"),
                }
            )
        if value["commit_count"] >= 5 or value["additions"] + value["deletions"] >= 300:
            progress_status = "active"
        elif value["commit_count"] >= 2 or value["additions"] + value["deletions"] >= 50:
            progress_status = "steady"
        else:
            progress_status = "limited"
        rows.append(
            {
                "week_label": value["week_label"],
                "week_start": value["week_start"],
                "week_end": value["week_end"],
                "commit_count": value["commit_count"],
                "additions": value["additions"],
                "deletions": value["deletions"],
                "changed_files": value["changed_files"],
                "progress_status": progress_status,
                "work_summary": summarize(value["messages"], "本周有代码提交，但提交说明不足。"),
                "active_authors": len(authors),
                "authors": authors,
                "members": member_rows,
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


def build_member_commit_histories(binding: RepoBinding) -> dict:
    submission: AssignmentSubmission = binding.submission
    histories: dict[int, dict] = {}
    author_name_map: dict[str, int] = {}
    author_email_map: dict[str, int] = {}
    for member in submission.members:
        names = _split_aliases(member.git_author_names) or [member.student_name.lower()]
        emails = _split_aliases(member.git_author_emails)
        if not emails and member.student_id:
            emails.append(str(member.student_id).lower())
        histories[member.id] = {
            "member_id": member.id,
            "student_name": member.student_name,
            "student_id": member.student_id,
            "project_role": member.project_role,
            "commit_count": 0,
            "additions": 0,
            "deletions": 0,
            "changed_files": 0,
            "commits": [],
        }
        for alias in names:
            author_name_map.setdefault(alias, member.id)
        for alias in emails:
            author_email_map.setdefault(alias, member.id)

    unmapped = []
    for commit in binding.commits:
        name = (commit.author_name or "").strip().lower()
        email = (commit.author_email or "").strip().lower()
        member_id = author_email_map.get(email) if email else None
        if member_id is None and name:
            member_id = author_name_map.get(name)
        if member_id is None or member_id not in histories:
            unmapped.append(commit)
            continue
        history = histories[member_id]
        history["commit_count"] += 1
        history["additions"] += int(commit.additions or 0)
        history["deletions"] += int(commit.deletions or 0)
        history["changed_files"] += int(commit.changed_files or 0)
        history["commits"].append(commit)
    return {"members": list(histories.values()), "unmapped_commits": unmapped}


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
            "matched_changed_files": 0,
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
            item["matched_changed_files"] += int(commit.changed_files or 0)
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
