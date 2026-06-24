from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from urllib.parse import urlparse

from fastapi import HTTPException
import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.gitee_profile import UserGiteeProfile
from app.models.repository import RepoBinding, RepoCommitSnapshot
from app.models.submission import AssignmentSubmission
from app.models.user import User
from app.services.code_analysis_service import TEXT_EXTENSIONS, _is_ignored, _safe_decode, analyze_code_archive
from app.services.csdn_crawler_service import (
    PLAYWRIGHT_AVAILABLE,
    is_port_open,
    parse_cdp_port,
    start_chrome_if_needed,
)

GITEE_API_BASE = "https://gitee.com/api/v5"
LANGUAGE_COLORS = [
    "#2563eb",
    "#7c3aed",
    "#f97316",
    "#14b8a6",
    "#ef4444",
    "#0f766e",
    "#eab308",
    "#64748b",
]


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


def _archive_download_urls(binding: RepoBinding, branch: str) -> list[str]:
    safe_branch = (branch or "").strip() or "master"
    return [
        f"https://gitee.com/{binding.repo_owner}/{binding.repo_name}/repository/archive/{safe_branch}.zip",
        f"https://gitee.com/{binding.repo_owner}/{binding.repo_name}/repository/archive/{safe_branch}?format=zip",
    ]


def _candidate_branches(binding: RepoBinding) -> list[str]:
    branches: list[str] = []
    for candidate in (binding.default_branch, "master", "main"):
        name = str(candidate or "").strip()
        if name and name not in branches:
            branches.append(name)
    return branches or ["master", "main"]


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


def _fetch_graph_payload(binding: RepoBinding, branch: str) -> tuple[dict, str]:
    errors: list[str] = []
    for candidate in _candidate_branches(binding):
        graph_json_url = f"https://gitee.com/{binding.repo_owner}/{binding.repo_name}/graph/{candidate}.json"
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
                    return payload, candidate
        except Exception as exc:
            errors.append(f"{candidate}:{exc}")
        try:
            payload = _fetch_graph_payload_via_browser(binding, candidate)
            if isinstance(payload, dict) and isinstance(payload.get("commits"), list):
                return payload, candidate
        except Exception as exc:
            errors.append(f"{candidate}:browser:{exc}")
    raise HTTPException(status_code=502, detail=f"gitee graph fetch failed: {' | '.join(errors[:6])}")


def _fetch_commits_via_api(binding: RepoBinding, max_pages: int = 3, per_page: int = 50) -> tuple[list[dict], str]:
    errors: list[str] = []
    normalized_per_page = max(1, min(int(per_page or 50), 100))
    normalized_pages = max(1, int(max_pages or 1))
    for candidate in _candidate_branches(binding):
        all_items: list[dict] = []
        try:
            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                for page in range(1, normalized_pages + 1):
                    response = client.get(
                        _commit_list_url(binding),
                        params={
                            "sha": candidate,
                            "per_page": normalized_per_page,
                            "page": page,
                        },
                        headers={
                            "Accept": "application/json,text/plain,*/*",
                            "User-Agent": "Mozilla/5.0",
                        },
                    )
                    response.raise_for_status()
                    payload = response.json()
                    if not isinstance(payload, list):
                        raise ValueError("invalid commits payload")
                    if not payload:
                        break
                    all_items.extend(payload)
                    if len(payload) < normalized_per_page:
                        break
            if all_items:
                return all_items, candidate
            errors.append(f"{candidate}:empty")
        except Exception as exc:
            errors.append(f"{candidate}:{exc}")
    raise HTTPException(status_code=502, detail=f"gitee commits api failed: {' | '.join(errors[:6])}")


def _extract_commit_hash(item: dict) -> str:
    return str(item.get("id") or item.get("sha") or "").strip()


def _extract_author_info(item: dict) -> dict:
    author_info = item.get("author") or {}
    if isinstance(author_info, dict) and author_info:
        return author_info
    commit_info = item.get("commit") or {}
    author_info = commit_info.get("author") or {}
    return author_info if isinstance(author_info, dict) else {}


def _extract_committed_at(item: dict) -> datetime | None:
    raw = item.get("date")
    if not raw:
        raw = ((item.get("commit") or {}).get("author") or {}).get("date")
    if not raw:
        return None
    return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).replace(tzinfo=None)


def _extract_message(item: dict) -> str | None:
    message = item.get("message")
    if not message:
        message = ((item.get("commit") or {}).get("message") or "").strip()
    value = str(message or "").strip()
    return value or None


def _extract_html_url(binding: RepoBinding, commit_hash: str, item: dict) -> str:
    html_url = str(item.get("html_url") or "").strip()
    if html_url:
        return html_url
    return f"https://gitee.com/{binding.repo_owner}/{binding.repo_name}/commit/{commit_hash}"


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
        commits, resolved_branch = _fetch_commits_via_api(binding, max_pages=max_pages, per_page=per_page)
    except HTTPException:
        payload, resolved_branch = _fetch_graph_payload(binding, (binding.default_branch or "").strip() or "master")
        commits = list(payload.get("commits") or [])
        if max_pages > 0 and per_page > 0:
            commits = commits[: max_pages * per_page]

    try:

        for item in commits:
            commit_hash = _extract_commit_hash(item)
            if not commit_hash or commit_hash in existing_hashes:
                continue

            author_info = _extract_author_info(item)
            committed_at = _extract_committed_at(item)
            if not committed_at:
                continue
            additions, deletions, changed_files = _extract_commit_stats(item)

            db.add(
                RepoCommitSnapshot(
                    binding_id=binding.id,
                    commit_hash=commit_hash,
                    author_name=author_info.get("name"),
                    author_email=author_info.get("email"),
                    message=_extract_message(item),
                    committed_at=committed_at,
                    html_url=_extract_html_url(binding, commit_hash, item),
                    additions=additions,
                    deletions=deletions,
                    changed_files=changed_files,
                )
            )
            existing_hashes.add(commit_hash)
            inserted += 1

        if resolved_branch and str(binding.default_branch or "").strip() != resolved_branch:
            binding.default_branch = resolved_branch
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


def _serialize_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False)


def _load_cached_analysis(binding: RepoBinding) -> dict | None:
    raw = str(binding.analysis_summary_json or "").strip()
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def load_cached_repo_insight_snapshot(binding: RepoBinding | None) -> dict | None:
    if binding is None:
        return None
    return _load_cached_analysis(binding)


def repo_insight_needs_refresh(binding: RepoBinding | None, cached: dict | None = None) -> bool:
    if binding is None:
        return False
    payload = cached if cached is not None else _load_cached_analysis(binding)
    if not payload:
        return True
    generated_at = binding.analysis_generated_at
    if generated_at is None:
        return True
    if binding.last_sync_at and binding.last_sync_at > generated_at:
        return True
    max_age_hours = max(1, int(get_settings().repo_analysis_max_age_hours or 12))
    return (datetime.utcnow() - generated_at) >= timedelta(hours=max_age_hours)


def _download_repo_archive(binding: RepoBinding) -> str:
    errors: list[str] = []
    headers = {
        "Accept": "application/zip,application/octet-stream,*/*",
        "User-Agent": "Mozilla/5.0",
    }
    for branch in _candidate_branches(binding):
        for url in _archive_download_urls(binding, branch):
            suffix = f"-{binding.repo_owner}-{binding.repo_name}-{branch}.zip"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                temp_path = tmp.name
            try:
                with httpx.Client(timeout=90.0, follow_redirects=True) as client:
                    response = client.get(url, headers=headers)
                    response.raise_for_status()
                    Path(temp_path).write_bytes(response.content)
                if Path(temp_path).stat().st_size <= 0:
                    raise RuntimeError("empty archive")
                return temp_path
            except Exception as exc:
                errors.append(f"{branch}:{exc}")
                try:
                    Path(temp_path).unlink(missing_ok=True)
                except Exception:
                    pass
    raise HTTPException(status_code=502, detail=f"gitee archive download failed: {' | '.join(errors[:4])}")


def _clone_repo_to_tempdir(binding: RepoBinding) -> str:
    git_bin = shutil.which("git")
    if not git_bin:
        raise RuntimeError("git executable not found")
    last_error = "unknown"
    for branch in _candidate_branches(binding):
        temp_root = tempfile.mkdtemp(prefix=f"gitee-repo-{binding.id}-")
        repo_dir = str(Path(temp_root) / "repo")
        try:
            result = subprocess.run(
                [git_bin, "clone", "--depth", "1", "--branch", branch, binding.repo_url, repo_dir],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=180,
                check=False,
            )
            if result.returncode == 0 and Path(repo_dir).exists():
                return repo_dir
            last_error = (result.stderr or result.stdout or "").strip() or f"clone failed on branch {branch}"
        finally:
            if not Path(repo_dir).exists():
                shutil.rmtree(temp_root, ignore_errors=True)
    raise RuntimeError(last_error)


def _analyze_code_directory(directory_path: str) -> dict:
    result = {
        "archive_format": "git_clone",
        "total_files": 0,
        "source_file_count": 0,
        "total_lines": 0,
        "total_bytes": 0,
        "dominant_language": None,
        "risk_level": "unknown",
        "risk_flags": [],
        "top_extensions": [],
        "languages": {},
    }
    root = Path(directory_path)
    ext_counter: dict[str, int] = {}
    lang_counter: dict[str, int] = {}
    for file_path in root.rglob("*"):
        if not file_path.is_file():
            continue
        relative_name = file_path.relative_to(root).as_posix()
        if _is_ignored(relative_name):
            continue
        result["total_files"] += 1
        try:
            file_size = int(file_path.stat().st_size or 0)
        except Exception:
            file_size = 0
        result["total_bytes"] += file_size
        ext = file_path.suffix.lower()
        if ext:
            ext_counter[ext] = ext_counter.get(ext, 0) + 1
        if ext not in TEXT_EXTENSIONS:
            continue
        try:
            raw = file_path.read_bytes()
        except Exception:
            continue
        text = _safe_decode(raw)
        if text is None:
            continue
        line_count = len(text.splitlines())
        result["source_file_count"] += 1
        result["total_lines"] += line_count
        lang = TEXT_EXTENSIONS[ext]
        lang_counter[lang] = lang_counter.get(lang, 0) + line_count

    result["languages"] = lang_counter
    result["top_extensions"] = [
        {"extension": ext, "count": count}
        for ext, count in sorted(ext_counter.items(), key=lambda item: item[1], reverse=True)[:8]
    ]
    if lang_counter:
        result["dominant_language"] = max(lang_counter.items(), key=lambda item: item[1])[0]

    risk_flags: list[str] = []
    risk_level = "low"
    if result["total_files"] == 0:
        risk_flags.append("empty_repository")
        risk_level = "high"
    if result["source_file_count"] == 0:
        risk_flags.append("no_detected_source_files")
        risk_level = "high"
    elif result["total_lines"] < 50:
        risk_flags.append("very_small_codebase")
        risk_level = "medium" if risk_level == "low" else risk_level
    if result["total_files"] > 0 and result["source_file_count"] / max(result["total_files"], 1) < 0.2:
        risk_flags.append("low_source_file_ratio")
        risk_level = "medium" if risk_level == "low" else risk_level

    result["risk_flags"] = risk_flags
    result["risk_level"] = risk_level
    return result


def _build_member_profile_map(db: Session, submission: AssignmentSubmission) -> dict[str, dict]:
    student_ids = [str(member.student_id or "").strip() for member in list(submission.members or []) if str(member.student_id or "").strip()]
    if not student_ids:
        return {}
    users = db.query(User).filter(User.student_id.in_(student_ids)).all()
    user_map = {str(user.student_id or "").strip(): user for user in users}
    profiles = (
        db.query(UserGiteeProfile)
        .filter(UserGiteeProfile.student_id.in_(student_ids))
        .all()
    )
    profile_map = {str(profile.student_id or "").strip(): profile for profile in profiles}
    data: dict[str, dict] = {}
    for student_id in student_ids:
        user = user_map.get(student_id)
        profile = profile_map.get(student_id)
        data[student_id] = {
            "user_id": int(user.id) if user else None,
            "real_name": str(user.real_name or "").strip() if user else "",
            "gitee_login": str(profile.gitee_login or "").strip() if profile else "",
            "gitee_display_name": str(profile.gitee_display_name or "").strip() if profile else "",
            "gitee_profile_url": str(profile.gitee_profile_url or "").strip() if profile else "",
        }
    return data


def _build_repo_member_workloads(db: Session, binding: RepoBinding) -> list[dict]:
    submission: AssignmentSubmission = binding.submission
    profile_map = _build_member_profile_map(db, submission)
    members = list(submission.members or [])
    member_lookup: dict[int, dict] = {}
    author_name_map: dict[str, int] = {}
    author_email_map: dict[str, int] = {}
    for member in members:
        student_id = str(member.student_id or "").strip()
        profile = profile_map.get(student_id, {})
        aliases_name = _split_aliases(member.git_author_names)
        aliases_email = _split_aliases(member.git_author_emails)
        gitee_login = str(profile.get("gitee_login") or "").strip()
        gitee_display_name = str(profile.get("gitee_display_name") or "").strip()
        if gitee_login and gitee_login.lower() not in aliases_name:
            aliases_name.append(gitee_login.lower())
        if gitee_display_name and gitee_display_name.lower() not in aliases_name:
            aliases_name.append(gitee_display_name.lower())
        if not aliases_name:
            aliases_name.append(str(member.student_name or "").strip().lower())
        member_lookup[member.id] = {
            "user_id": profile.get("user_id"),
            "member_id": member.id,
            "student_id": student_id,
            "real_name": profile.get("real_name") or member.student_name,
            "gitee_login": gitee_login,
            "gitee_display_name": gitee_display_name or gitee_login,
            "contribution_source": member.contribution_source or "mixed",
            "commit_count": 0,
            "additions": 0,
            "deletions": 0,
            "changed_files": 0,
            "workload_value": 0,
            "workload_percent": 0.0,
        }
        for alias in aliases_name:
            author_name_map.setdefault(alias, member.id)
        for alias in aliases_email:
            author_email_map.setdefault(alias, member.id)

    for commit in list(binding.commits or []):
        author_name = str(commit.author_name or "").strip().lower()
        author_email = str(commit.author_email or "").strip().lower()
        member_id = author_email_map.get(author_email) if author_email else None
        if member_id is None and author_name:
            member_id = author_name_map.get(author_name)
        if member_id is None or member_id not in member_lookup:
            continue
        item = member_lookup[member_id]
        item["commit_count"] += 1
        item["additions"] += int(commit.additions or 0)
        item["deletions"] += int(commit.deletions or 0)
        item["changed_files"] += int(commit.changed_files or 0)

    total_workload = 0
    for item in member_lookup.values():
        churn = int(item["additions"] or 0) + int(item["deletions"] or 0)
        if churn <= 0:
            churn = (int(item["changed_files"] or 0) * 20) + (int(item["commit_count"] or 0) * 10)
        item["workload_value"] = churn
        total_workload += churn
    for item in member_lookup.values():
        item["workload_percent"] = round((float(item["workload_value"]) / max(total_workload, 1)) * 100, 1) if total_workload > 0 else 0.0
    return sorted(
        member_lookup.values(),
        key=lambda row: (-float(row["workload_percent"]), -int(row["workload_value"]), row["student_id"]),
    )


def _build_language_rows(summary: dict) -> list[dict]:
    languages = summary.get("languages") or {}
    if not isinstance(languages, dict):
        languages = {}
    total_lines = int(summary.get("total_lines") or 0)
    rows: list[dict] = []
    for index, (language, lines) in enumerate(sorted(languages.items(), key=lambda item: item[1], reverse=True)):
        line_count = int(lines or 0)
        rows.append(
            {
                "language": str(language or "Unknown"),
                "lines": line_count,
                "percent": round((line_count / max(total_lines, 1)) * 100, 1) if total_lines > 0 else 0.0,
                "color": LANGUAGE_COLORS[index % len(LANGUAGE_COLORS)],
            }
        )
    return rows


def build_repo_insight_snapshot(db: Session, binding: RepoBinding, *, refresh: bool = False) -> dict:
    if not refresh:
        cached = _load_cached_analysis(binding)
        if cached:
            return cached

    cleanup_path = None
    try:
        repo_dir = _clone_repo_to_tempdir(binding)
        cleanup_path = str(Path(repo_dir).parent)
        code_summary = _analyze_code_directory(repo_dir)
    except Exception:
        archive_path = _download_repo_archive(binding)
        cleanup_path = archive_path
        code_summary = analyze_code_archive(archive_path)
    finally:
        try:
            if cleanup_path:
                path_obj = Path(cleanup_path)
                if path_obj.is_dir():
                    shutil.rmtree(path_obj, ignore_errors=True)
                else:
                    path_obj.unlink(missing_ok=True)
        except Exception:
            pass

    code_payload = {
        "archive_format": str(code_summary.get("archive_format") or "zip"),
        "total_files": int(code_summary.get("total_files") or 0),
        "source_file_count": int(code_summary.get("source_file_count") or 0),
        "total_lines": int(code_summary.get("total_lines") or 0),
        "total_bytes": int(code_summary.get("total_bytes") or 0),
        "estimated_kb": round(int(code_summary.get("total_bytes") or 0) / 1024, 1),
        "dominant_language": code_summary.get("dominant_language"),
        "risk_level": str(code_summary.get("risk_level") or "unknown"),
        "risk_flags": list(code_summary.get("risk_flags") or []),
        "languages": _build_language_rows(code_summary),
    }
    members = _build_repo_member_workloads(db, binding)
    risk_flags = list(code_payload["risk_flags"])
    if any(not str(item.get("gitee_login") or "").strip() for item in members):
        risk_flags.append("members_without_gitee_profile")
    if all(float(item.get("workload_percent") or 0) == 0 for item in members) and members:
        risk_flags.append("no_mapped_member_workload")
    payload = {
        "binding_id": binding.id,
        "repo_url": binding.repo_url,
        "sync_status": binding.sync_status,
        "last_sync_at": binding.last_sync_at.isoformat() if binding.last_sync_at else None,
        "analysis_generated_at": datetime.utcnow().isoformat(),
        "code_summary": code_payload,
        "members": members,
        "risk_flags": sorted(set(risk_flags)),
    }
    binding.analysis_summary_json = _serialize_json(payload)
    binding.analysis_generated_at = datetime.utcnow()
    db.add(binding)
    db.commit()
    db.refresh(binding)
    return payload


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
