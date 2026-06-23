from __future__ import annotations

import hashlib
import json
import re
from contextlib import suppress
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.blog import BlogAuditItem, BlogCrawlRun, BlogPost, BlogSource
from app.models.group import UserGroup  # ensure FK metadata is loaded for users.group_id
from app.models.user import User
from app.services.csdn_crawler_service import (
    crawl_csdn_blog,
    is_port_open,
    normalize_csdn_home_input,
    parse_cdp_port,
    start_chrome_if_needed,
)


def _utcnow() -> datetime:
    return datetime.utcnow()


def _validate_blog_home_url(user: User) -> str:
    raw_value = (user.blog_home_url or "").strip()
    if not raw_value:
        raise ValueError("该用户未配置博客主页地址")
    return normalize_csdn_home_input(raw_value)


def _user_storage_dir(user_id: int) -> Path:
    settings = get_settings()
    return settings.blog_storage_path / f"user_{user_id}"


def _upsert_blog_audit(
    db: Session,
    user_id: int,
    url: str,
    title: str,
    published_at: datetime | None,
    analysis: dict,
    run_id: int | None = None,
) -> BlogAuditItem:
    row = db.query(BlogAuditItem).filter(BlogAuditItem.user_id == user_id, BlogAuditItem.url == url).first()
    if row is None:
        row = BlogAuditItem(user_id=user_id, url=url, first_seen_at=_utcnow())
        db.add(row)
    classification = _resolve_audit_classification(analysis)
    is_project = bool(analysis.get("is_project_training"))
    is_code = bool(analysis.get("is_mostly_code"))
    is_science = bool(analysis.get("is_popular_science"))
    has_work = bool(analysis.get("work_items"))
    row.run_id = run_id
    row.title = (title or url)[:255]
    row.published_at = published_at
    row.classification = classification
    row.is_project_training = is_project
    row.is_mostly_code = is_code
    row.is_popular_science = is_science
    row.has_actual_work = has_work
    row.last_seen_at = _utcnow()
    return row


def _resolve_audit_classification(analysis: dict) -> str:
    category = str(analysis.get("category") or "").strip().lower()
    if category in {"project_update", "project_code_dump", "project_science", "code_dump", "popular_science", "unrelated"}:
        return category
    is_project = bool(analysis.get("is_project_training"))
    is_code = bool(analysis.get("is_mostly_code"))
    is_science = bool(analysis.get("is_popular_science"))
    if is_project and is_code:
        return "project_code_dump"
    if is_project and is_science:
        return "project_science"
    if is_project:
        return "project_update"
    if is_science:
        return "popular_science"
    if is_code:
        return "code_dump"
    return "unrelated"


def re_evaluate_blog_posts(
    db: Session,
    posts: list[BlogPost],
) -> dict:
    if not posts:
        return {
            "total": 0,
            "updated": 0,
            "users": 0,
            "category_counts": {},
            "items": [],
        }

    user_ids = sorted({int(post.user_id) for post in posts})
    users = {
        int(user.id): user
        for user in db.query(User).filter(User.id.in_(user_ids)).all()
    }
    project_context_map = {
        user_id: _project_context_for_user(db, user)
        for user_id, user in users.items()
    }

    category_counts: dict[str, int] = {}
    items: list[dict] = []
    updated = 0

    for post in posts:
        content = post.content_md or post.content_text or ""
        analysis = analyze_project_blog(
            content,
            post.title,
            project_context_map.get(int(post.user_id), ""),
        )
        post.category = str(analysis.get("category") or post.category or "unrelated")
        post.summary = str(analysis.get("summary_text") or "")[:65535]
        post.summary_text = str(analysis.get("summary_text") or "")[:65535]
        post.work_items_json = dumps_work_items(analysis.get("work_items") or [])
        post.snapshot_hash = analysis.get("snapshot_hash")
        post.word_count = int(analysis.get("word_count") or 0)
        post.code_block_count = int(analysis.get("code_block_count") or 0)
        post.number_count = int(analysis.get("number_count") or 0)
        post.is_mostly_code = bool(analysis.get("is_mostly_code"))
        post.is_popular_science = bool(analysis.get("is_popular_science"))
        post.updated_at = _utcnow()
        _upsert_blog_audit(
            db=db,
            user_id=int(post.user_id),
            url=post.url,
            title=post.title,
            published_at=post.published_at,
            analysis=analysis,
            run_id=None,
        )
        category_counts[post.category] = category_counts.get(post.category, 0) + 1
        items.append({
            "id": int(post.id),
            "user_id": int(post.user_id),
            "category": post.category,
            "is_project_training": bool(analysis.get("is_project_training")),
            "is_mostly_code": bool(analysis.get("is_mostly_code")),
            "is_popular_science": bool(analysis.get("is_popular_science")),
            "work_item_count": len(analysis.get("work_items") or []),
        })
        updated += 1

    db.commit()
    return {
        "total": len(posts),
        "updated": updated,
        "users": len(user_ids),
        "category_counts": category_counts,
        "items": items,
    }


def _project_context_for_user(db: Session, user: User) -> str:
    from app.models.code_analysis import SubmissionCodeAnalysis
    from app.models.course import Assignment
    from app.models.repository import RepoBinding
    from app.models.submission import AssignmentSubmission, SubmissionMember
    from app.models.teacher_review_assignment import TeacherReviewAssignment
    from app.models.teacher_score import TeacherScoreRecord

    names: list[str] = []
    rows = (
        db.query(AssignmentSubmission)
        .outerjoin(SubmissionMember, SubmissionMember.submission_id == AssignmentSubmission.id)
        .filter(
            (AssignmentSubmission.submitter_user_id == user.id)
            | (SubmissionMember.student_id == user.student_id)
        )
        .order_by(AssignmentSubmission.updated_at.desc())
        .limit(10)
        .all()
    )
    for row in rows:
        if row.project_name and row.project_name.strip():
            names.append(row.project_name.strip())
    return "；".join(dict.fromkeys(names))


def create_crawl_run(db: Session, user: User, admin: User) -> BlogCrawlRun:
    blog_home_url = _validate_blog_home_url(user)
    run = BlogCrawlRun(
        user_id=user.id,
        blog_home_url=blog_home_url,
        status="queued",
        triggered_by_admin_id=admin.id,
        total_found=0,
        total_saved=0,
        total_failed=0,
        error_message="",
        created_at=_utcnow(),
    )
    db.add(run)
    user.blog_crawl_status = "queued"
    db.commit()
    db.refresh(run)
    db.refresh(user)
    return run


def run_user_blog_crawl(
    db: Session,
    user: User,
    admin: User,
    existing_run: BlogCrawlRun | None = None,
) -> BlogCrawlRun:
    settings = get_settings()
    if not settings.blog_crawler_enabled:
        raise ValueError("博客爬虫已禁用")
    if not user.blog_enabled:
        raise ValueError("该用户已禁用博客抓取")
    try:
        import asyncio
        import sys

        if sys.platform.startswith("win") and hasattr(asyncio, "WindowsProactorEventLoopPolicy"):
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        raise ValueError(f"博客爬虫依赖未安装（playwright）：{type(exc).__name__}: {exc}") from exc

    run = existing_run or create_crawl_run(db, user, admin)
    run.status = "running"
    run.started_at = _utcnow()
    db.commit()

    try:
        existing_urls = {
            row.url
            for row in db.query(BlogPost.url, BlogPost.screenshot_path)
            .filter(BlogPost.user_id == user.id, BlogPost.category == "project_update")
            .all()
            if row.url and row.screenshot_path and Path(row.screenshot_path).is_file()
        }
        for existing_post in db.query(BlogPost).filter(BlogPost.user_id == user.id).all():
            _upsert_blog_audit(
                db,
                user.id,
                existing_post.url,
                existing_post.title,
                existing_post.published_at,
                {
                    "is_project_training": existing_post.category == "project_update",
                    "is_mostly_code": bool(existing_post.is_mostly_code),
                    "is_popular_science": bool(existing_post.is_popular_science),
                    "work_items": loads_work_items(existing_post.work_items_json),
                },
                run.id,
            )
        db.commit()
        with sync_playwright() as playwright:
            article_result, details, failures = crawl_csdn_blog(
                playwright=playwright,
                settings=settings,
                blog_home_url=run.blog_home_url,
                user_storage_dir=_user_storage_dir(user.id),
                skip_urls=existing_urls,
            )

        run.total_found = len(article_result.articles)
        run.total_saved = len(details)
        run.total_failed = len(failures)
        if run.total_found == 0:
            run.status = "failed"
            run.error_message = "未抓取到任何文章，可能需要登录/验证码或博客地址无效。"
        else:
            if failures and details:
                run.status = "partial_success"
            elif failures and not details:
                run.status = "failed"
            elif not failures and not details and all(
                article.get("url") in existing_urls for article in article_result.articles
            ):
                run.status = "success"
            elif not failures and not details:
                run.status = "failed"
                run.error_message = "已发现文章但未成功抓取详情，可能需要登录/验证码。"
            else:
                run.status = "success"
        failure_text = "\n".join(
            f"{item['title']} | {item['url']} | {item['error']}" for item in failures
        )
        if failure_text:
            run.error_message = failure_text

        retained_urls: set[str] = set()
        rejected_details = []
        analyses_by_url: dict[str, dict] = {}
        project_context = _project_context_for_user(db, user)
        for i, detail in enumerate(details, start=1):
            analysis = analyze_project_blog(detail.content_md or detail.content_text, detail.title, project_context)
            analyses_by_url[detail.url] = analysis
            _upsert_blog_audit(
                db,
                user.id,
                detail.url,
                detail.title,
                detail.published_at,
                analysis,
                run.id,
            )
            if not analysis["is_project_training"]:
                rejected_details.append(detail)
                continue
            # Screenshot failure is not fatal — keep the article
            retained_urls.add(detail.url)
            # Skip if already saved successfully (from a previous partial crawl)
            existing = (
                db.query(BlogPost)
                .filter(BlogPost.user_id == user.id, BlogPost.url == detail.url)
                .first()
            )
            if existing and existing.screenshot_path and Path(existing.screenshot_path).is_file():
                continue  # already fully saved
            article_uid = detail.url.rstrip("/").split("/")[-1].split("#")[0]
            if existing is None:
                row = BlogPost(
                    user_id=user.id,
                    title=detail.title,
                    url=detail.url,
                    source="csdn",
                    article_uid=article_uid,
                    status="normal",
                    category="project_update",
                    summary=analysis["summary_text"],
                    summary_text=analysis["summary_text"],
                    work_items_json=dumps_work_items(analysis["work_items"]),
                    content_md=_sanitize_utf8mb4(detail.content_md),
                    content_text=_sanitize_utf8mb4(detail.content_text),
                    snapshot_hash=analysis["snapshot_hash"],
                    raw_html_path=str(detail.html_path),
                    screenshot_path=str(detail.screenshot_path),
                    published_at=detail.published_at,
                    word_count=analysis["word_count"],
                    code_block_count=analysis["code_block_count"],
                    number_count=analysis["number_count"],
                    is_mostly_code=analysis["is_mostly_code"],
                    is_popular_science=False,
                    capture_status=detail.capture_status,
                    capture_error=detail.capture_error,
                    capture_timestamp=detail.capture_timestamp,
                    review_status="pending",
                )
                db.add(row)
            else:
                existing.title = detail.title
                existing.source = "csdn"
                existing.article_uid = article_uid
                existing.status = "normal"
                existing.category = "project_update"
                existing.summary = analysis["summary_text"]
                existing.summary_text = analysis["summary_text"]
                existing.work_items_json = dumps_work_items(analysis["work_items"])
                existing.content_md = _sanitize_utf8mb4(detail.content_md)
                existing.content_text = _sanitize_utf8mb4(detail.content_text)
                existing.snapshot_hash = analysis["snapshot_hash"]
                existing.raw_html_path = str(detail.html_path)
                existing.screenshot_path = str(detail.screenshot_path)
                existing.published_at = detail.published_at
                existing.word_count = analysis["word_count"]
                existing.code_block_count = analysis["code_block_count"]
                existing.number_count = analysis["number_count"]
                existing.is_mostly_code = analysis["is_mostly_code"]
                existing.is_popular_science = False
                existing.capture_status = detail.capture_status
                existing.capture_error = detail.capture_error
                existing.capture_timestamp = detail.capture_timestamp
                existing.updated_at = _utcnow()

            # Commit after each article — crash never loses anything
            try:
                db.commit()
            except Exception:
                db.rollback()

        # The project archive must not retain unrelated articles or their snapshots.
        for detail in rejected_details:
            _remove_snapshot_files(detail.screenshot_path, detail.html_path)
            stale = db.query(BlogPost).filter(BlogPost.user_id == user.id, BlogPost.url == detail.url).first()
            if stale:
                _remove_snapshot_files(stale.screenshot_path, stale.raw_html_path)
                db.delete(stale)

        for stale in db.query(BlogPost).filter(BlogPost.user_id == user.id).all():
            if stale.url in retained_urls:
                continue
            screenshot_exists = bool(stale.screenshot_path) and Path(stale.screenshot_path).is_file()
            if stale.category == "project_update" and screenshot_exists:
                continue
            stale_analysis = analyses_by_url.get(stale.url) or analyze_project_blog(
                stale.content_md or stale.content_text, stale.title, project_context
            )
            if not stale_analysis["is_project_training"] or not screenshot_exists:
                _remove_snapshot_files(stale.screenshot_path, stale.raw_html_path)
                db.delete(stale)

        # SessionLocal disables autoflush, so flush pending inserts/deletes before
        # deriving the persisted project-blog count for this run.
        db.flush()
        run.total_saved = (
            db.query(BlogPost)
            .filter(BlogPost.user_id == user.id, BlogPost.category == "project_update")
            .count()
        )

        run.finished_at = _utcnow()
        user.blog_crawl_status = run.status
        user.blog_last_crawled_at = run.finished_at
        db.commit()
        db.refresh(run)
        db.refresh(user)
        return run
    except Exception as exc:
        db.rollback()
        run = db.query(BlogCrawlRun).filter(BlogCrawlRun.id == run.id).first()
        user = db.query(User).filter(User.id == user.id).first()
        if run:
            run.status = "failed"
            run.error_message = str(exc)
            run.finished_at = _utcnow()
        if user:
            user.blog_crawl_status = "failed"
            user.blog_last_crawled_at = _utcnow()
        db.commit()
        raise


def _sanitize_utf8mb4(text: str) -> str:
    """Clean text to only valid utf8mb3-safe characters for MySQL.

    Strips 4-byte UTF-8 chars (emoji, some CJK extensions) and
    control characters that cause MySQL insert errors.
    """
    if not text:
        return ""
    result = []
    for c in text:
        cp = ord(c)
        # Allow: tab, newline, carriage return, space through U+FFFF (BMP)
        if cp in (9, 10, 13) or (32 <= cp <= 0xFFFF):
            result.append(c)
    return "".join(result)


def dumps_work_items(items: list[str]) -> str:
    return json.dumps(items, ensure_ascii=False)


def loads_work_items(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    except Exception:
        return []
    return []


def build_blog_user_risk(
    post_count: int,
    published_dates: list[datetime],
    has_code_only: bool,
    has_empty_popular_science: bool,
    crawl_status: str,
    has_blog_url: bool,
) -> tuple[int | None, list[str]]:
    dated = sorted(published_dates, reverse=True)
    recent_eight = dated[:8]
    span_days = (max(recent_eight) - min(recent_eight)).days if len(recent_eight) >= 8 else None
    flags: list[str] = []
    if post_count < 8:
        flags.append("blog_count_below_8")
    if not has_blog_url:
        flags.append("blog_url_missing")
    if post_count >= 8 and len(recent_eight) < 8:
        flags.append("published_time_missing")
    if span_days is not None and span_days <= 7:
        flags.append("eight_posts_within_1_week")
    elif span_days is not None and span_days <= 14:
        flags.append("eight_posts_within_2_weeks")
    if has_code_only:
        flags.append("code_only_blog_present")
    if has_empty_popular_science:
        flags.append("empty_popular_science_present")
    if crawl_status in {"failed", "partial_success"}:
        flags.append("crawl_failed_retry_required")
    return span_days, flags


def resolve_blog_crawl_status(raw_status: str | None, saved_post_count: int = 0) -> str:
    status = str(raw_status or "").strip().lower() or "idle"
    if saved_post_count > 0 and status in {"failed", "partial_success", "cancelled"}:
        return "idle"
    return status


class _LinkExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() != "a":
            return
        for key, value in attrs:
            if key.lower() == "href" and value:
                self.links.append(str(value))


def _normalize_url(url: str) -> str:
    value = (url or "").strip()
    if not value:
        return ""
    parsed = urlparse(value)
    return parsed._replace(fragment="").geturl()


def _html_to_markdownish(html: str) -> str:
    text = html or ""
    text = re.sub(r"(?is)<script.*?>.*?</script>", "", text)
    text = re.sub(r"(?is)<style.*?>.*?</style>", "", text)
    # CSDN code blocks: <pre...><code...>actual code</code><div...buttons></div></pre>
    text = re.sub(
        r"(?is)<pre[^>]*>.*?<code[^>]*>(.*?)</code>.*?</pre>",
        lambda m: f"\n```text\n{unescape(re.sub(r'<.*?>', '', m.group(1)))}\n```\n",
        text,
    )
    text = re.sub(r"(?is)<br\s*/?>", "\n", text)
    text = re.sub(r"(?is)</(p|div|section|article|h1|h2|h3|h4|h5|h6|li|ul|ol|table|tr)>", "\n", text)
    text = re.sub(r"(?is)<li[^>]*>", "- ", text)
    text = re.sub(r"(?is)<[^>]+>", "", text)
    text = unescape(text)
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join([line for line in lines if line])


def _extract_title(html: str, fallback_url: str) -> str:
    patterns = [
        r'(?is)<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
        r'(?is)<meta[^>]+name=["\']title["\'][^>]+content=["\']([^"\']+)["\']',
        r"(?is)<title>(.*?)</title>",
        r"(?is)<h1[^>]*>(.*?)</h1>",
    ]
    for pattern in patterns:
        matched = re.search(pattern, html or "")
        if matched:
            title = re.sub(r"<.*?>", "", matched.group(1) or "").strip()
            if title:
                return unescape(title)
    return fallback_url


def _extract_published_at(html: str) -> datetime | None:
    patterns = [
        r'(?is)<meta[^>]+property=["\']article:published_time["\'][^>]+content=["\']([^"\']+)["\']',
        r'(?is)<meta[^>]+name=["\']publishdate["\'][^>]+content=["\']([^"\']+)["\']',
        r'(?is)<time[^>]+datetime=["\']([^"\']+)["\']',
        r"(?<!\d)(20\d{2}[-/]\d{1,2}[-/]\d{1,2}(?:[ T]\d{1,2}:\d{2}(?::\d{2})?)?)",
    ]
    for pattern in patterns:
        matched = re.search(pattern, html or "")
        if not matched:
            continue
        raw = str(matched.group(1)).strip().replace("/", "-").replace("Z", "+00:00")
        for candidate in [raw, raw.replace(" ", "T")]:
            try:
                return datetime.fromisoformat(candidate).replace(tzinfo=None)
            except Exception:
                continue
        try:
            return datetime.strptime(raw[:10], "%Y-%m-%d")
        except Exception:
            continue
    return None


def _extract_post_links(source_url: str, html: str) -> list[str]:
    parser = _LinkExtractor()
    parser.feed(html or "")
    base = urlparse(source_url)
    links: list[str] = []
    for href in parser.links:
        full = _normalize_url(urljoin(source_url, href))
        if not full:
            continue
        parsed = urlparse(full)
        if parsed.netloc != base.netloc:
            continue
        if full == _normalize_url(source_url):
            continue
        path = parsed.path.lower()
        if path.endswith((".css", ".js", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".ico", ".pdf", ".zip")):
            continue
        links.append(full)
    deduped = []
    seen = set()
    for link in links:
        if link in seen:
            continue
        seen.add(link)
        deduped.append(link)
    return deduped


def _is_pagination_url(url: str) -> bool:
    parsed = urlparse(url)
    value = f"{parsed.path}?{parsed.query}".lower()
    return bool(
        re.search(r"/(?:page|pages|article/list)/\d+(?:/|$)", parsed.path.lower())
        or re.search(r"(?:^|[?&])(?:page|p|page_no|pageno)=\d+(?:&|$)", f"?{parsed.query}".lower())
        or any(token in value for token in ("nextpage", "pageindex"))
    )


def _count_code_blocks(markdownish: str) -> int:
    return markdownish.count("```")


def _count_words(text: str) -> int:
    cn = re.findall(r"[\u4e00-\u9fff]", text or "")
    en = re.findall(r"[A-Za-z0-9_]+", text or "")
    return len(cn) + len(en)


def _count_numbers(text: str) -> int:
    return len(re.findall(r"\d+", text or ""))


def _summarize_text(text: str) -> str:
    lines = [
        line.strip("- ").strip()
        for line in (text or "").splitlines()
        if line.strip() and not line.strip().startswith("```")
    ]
    joined = " ".join(lines)
    return joined[:180] + ("..." if len(joined) > 180 else "")


def _remove_snapshot_files(*paths: str | Path | None) -> None:
    for value in paths:
        if not value:
            continue
        with suppress(OSError):
            Path(value).unlink(missing_ok=True)


def _extract_work_items(text: str) -> list[str]:
    keywords = ("完成", "修复", "实现", "联调", "部署", "设计", "编写", "撰写", "测试", "优化", "新增", "重构")
    items: list[str] = []
    for line in (text or "").splitlines():
        normalized = line.strip("- ").strip()
        if not normalized or len(normalized) < 6:
            continue
        if any(keyword in normalized for keyword in keywords):
            items.append(normalized[:80])
        if len(items) >= 8:
            break
    return items


def _classify_blog(text: str, code_block_count: int, word_count: int) -> tuple[str, bool, bool, str]:
    lower = text.lower()
    code_hits = sum(
        lower.count(keyword)
        for keyword in (
            "class ",
            "def ",
            "function ",
            "import ",
            "public ",
            "private ",
            "const ",
            "let ",
            "return ",
        )
    )
    science_hits = sum(text.count(keyword) for keyword in ("原理", "教程", "介绍", "科普", "概念", "什么是", "如何理解"))
    project_hits = sum(text.count(keyword) for keyword in ("本周", "进度", "完成", "修复", "联调", "任务", "项目", "实现", "提交"))

    non_code_lines = 0
    substantial_text_lines = 0
    in_code_block = False
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        if re.search(r"[\u4e00-\u9fffA-Za-z]", line):
            non_code_lines += 1
        if len(re.findall(r"[\u4e00-\u9fffA-Za-z0-9_]+", line)) >= 8:
            substantial_text_lines += 1

    has_meaningful_explanation = substantial_text_lines >= 2 or (non_code_lines >= 4 and word_count >= 120)
    code_density_high = code_block_count >= 4 or (code_block_count >= 2 and code_hits >= 20)
    code_density_extreme = code_block_count >= 6 or code_hits >= 40

    # 只有“几乎全是代码且没有像样说明”的文章，才算纯代码博客。
    is_mostly_code = bool(code_density_high and not has_meaningful_explanation)
    if code_density_extreme and non_code_lines <= 2:
        is_mostly_code = True
    # 纯科普仍算低质量，但判定要保守一些，避免把带项目说明的文章误伤。
    is_popular_science = science_hits >= 3 and project_hits == 0 and not has_meaningful_explanation
    if is_mostly_code:
        category = "code_dump"
        status = "abnormal"
    elif is_popular_science:
        category = "popular_science"
        status = "normal"
    elif project_hits >= 2:
        category = "project_update"
        status = "normal"
    else:
        category = "mixed"
        status = "normal"
    return category, is_mostly_code, is_popular_science, status


def _project_relevance(text: str, title: str = "", project_context: str = "") -> tuple[bool, int, list[str]]:
    content = f"{title}\n{text}".lower()
    explicit_terms = ("创新实训", "创新实践", "项目实训", "创新训练", "项目周报", "项目日志")
    activity_terms = ("完成", "实现", "修复", "新增", "联调", "测试", "部署", "设计", "重构", "优化", "提交")
    context_terms = ("本周", "这周", "进度", "任务", "分工", "团队", "小组", "模块", "功能", "需求", "项目")
    engineering_terms = ("智能体", "知识库", "前端", "后端", "接口", "数据库", "模型", "算法", "爬虫", "页面", "部署")
    explicit = [term for term in explicit_terms if term in content]
    activities = [term for term in activity_terms if term in content]
    contexts = [term for term in context_terms if term in content]
    engineering = [term for term in engineering_terms if term in content]
    context_keywords = [item.lower() for item in re.findall(r"[\u4e00-\u9fffA-Za-z0-9_]{2,}", project_context or "")]
    matched_context = [item for item in context_keywords if item in content]
    score = min(10, len(explicit) * 4 + len(activities) + len(contexts) + len(engineering) + len(matched_context) * 2)
    # Relaxed threshold: single activity + any context/engineering is enough
    # Image-heavy blogs often have few words but clear project intent
    is_project = bool(explicit) or bool(matched_context) or (
        len(activities) >= 1 and (len(contexts) >= 1 or len(engineering) >= 1)
    )
    reasons = [f"explicit:{item}" for item in explicit]
    reasons.extend(f"activity:{item}" for item in activities[:4])
    reasons.extend(f"context:{item}" for item in contexts[:3])
    reasons.extend(f"engineering:{item}" for item in engineering[:3])
    reasons.extend(f"project-match:{item}" for item in matched_context[:3])
    return is_project, score, reasons


def _semantic_project_analysis(text: str, title: str, project_context: str) -> dict | None:
    settings = get_settings()
    if not settings.model_base_url or not settings.model_api_key:
        return None
    # For image-heavy posts (few words), include HTML structure hints
    img_count = (text or '').count('<img') + (text or '').count('![](')
    word_count = len(re.findall(r'[一-鿿]', text or '')) + len(re.findall(r'[A-Za-z0-9_]+', text or ''))

    prompt = (
        "分析下面博客，完成三项任务：\n"
        "1. 判断是否属于学生创新实训/项目实训课程的个人工作记录\n"
        "2. 对博客内容做一段中文总结（100-200字）\n"
        "3. 对博客进行分类\n\n"
        "属于项目博客的情况（满足任一条即可）：\n"
        "- 明确提到项目名称、课程名称（创新实训/项目实训/软件学院实训等）\n"
        "- 记录了具体功能的开发、测试、部署、问题解决过程\n"
        "- 有截图/代码并附有工作说明\n"
        "- 记录了本周/本阶段的工作进度或任务分工\n\n"
        + (f"注意：这篇博客包含{img_count}张图片，属于图文并茂的工作记录，应判定为项目博客。" if img_count >= 3 and word_count < 300 else "") +
        "博客分类标准（所有博客默认属于项目实训，分类仅表示写作质量）：\n"
        "- project_update: 有实际工作描述、总结或解释。代码多但有文字说明也算。\n"
        "- project_code_dump: 项目相关但几乎全是代码粘贴，缺少工作描述。注意：只要有一段完整的工作描述（不是一两句话），就应该归为 project_update。\n"
        "- project_science: 项目相关但写成通用教程风格，缺少项目具体语境。\n"
        "- unrelated: 与项目实训完全无关（转载、纯通用教程等）\n\n"
        "重要：code_dump 和 science 是「写作质量问题」，不影响博客属于项目实训的事实。只有 unrelated 才不是项目博客。\n\n"
        "输出JSON：{\"is_project\":true/false,\"category\":\"project_update|code_dump|popular_science|unrelated\","
        "\"summary\":\"博客内容的中文总结\",\"work_items\":[\"具体工作项\"],\"reason\":\"判断理由\"}\n\n"
        f"已知项目名称：{project_context or '未知'}\n标题：{title}\n正文：{(text or '')[:10000]}"
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
            timeout=45.0,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"].strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.I)
        parsed = json.loads(content)
        model_category = str(parsed.get("category") or "").strip()
        valid_cats = {"project_update", "project_code_dump", "project_science", "code_dump", "popular_science", "unrelated"}
        if model_category not in valid_cats:
            model_category = "project_update" if parsed.get("is_project") else "unrelated"
        # Normalize old category names
        if model_category == "code_dump":
            model_category = "project_code_dump"
        elif model_category == "popular_science":
            model_category = "project_science"
        return {
            "is_project": bool(parsed.get("is_project")),
            "category": model_category,
            "summary": str(parsed.get("summary") or "").strip()[:500],
            "work_items": [str(item).strip()[:120] for item in (parsed.get("work_items") or []) if str(item).strip()][:12],
            "reason": str(parsed.get("reason") or "").strip()[:300],
        }
    except Exception:
        return None


def analyze_project_blog(text: str, title: str = "", project_context: str = "") -> dict:
    markdownish = text or ""
    word_count = _count_words(markdownish)
    code_block_count = _count_code_blocks(markdownish)
    number_count = _count_numbers(markdownish)
    _, is_mostly_code, is_popular_science, _ = _classify_blog(markdownish, code_block_count, word_count)
    is_project, relevance_score, relevance_reasons = _project_relevance(markdownish, title, project_context)
    model_cat = ""
    extracted_work_items = _extract_work_items(markdownish)
    semantic = _semantic_project_analysis(markdownish, title, project_context)
    if semantic is not None:
        is_project = semantic["is_project"]
        relevance_reasons = [f"model:{semantic['reason']}"] if semantic["reason"] else ["model"]
        # Use model's category classification
        model_cat = semantic.get("category", "")
        semantic_work_items = [str(item).strip() for item in (semantic.get("work_items") or []) if str(item).strip()]
        # Normalize model output to our categories
        if model_cat in ("code_dump", "project_code_dump"):
            if word_count >= 120 or len(semantic_work_items) >= 2 or len(extracted_work_items) >= 2:
                model_cat = "project_update"  # has enough text, promote
                is_mostly_code = False
            else:
                model_cat = "project_code_dump"
                is_mostly_code = True
                is_popular_science = False
        elif model_cat in ("popular_science", "project_science"):
            if len(semantic_work_items) >= 2 or len(extracted_work_items) >= 2 or word_count >= 180:
                model_cat = "project_update"
                is_mostly_code = False
                is_popular_science = False
            else:
                model_cat = "project_science"
                is_mostly_code = False
                is_popular_science = True
        elif model_cat == "unrelated":
            is_mostly_code = False
            is_popular_science = False
    else:
        # No semantic result — use keyword classification
        model_cat = "project_update" if is_project else "unrelated"
        if is_mostly_code:
            model_cat = "project_code_dump"
        elif is_popular_science:
            model_cat = "project_science"
    summary_text = (semantic or {}).get("summary") or _summarize_text(markdownish)
    work_items = (semantic or {}).get("work_items") or extracted_work_items
    return {
        "is_project_training": is_project,
        "category": model_cat if semantic else ("project_update" if is_project else "unrelated"),
        "relevance_score": relevance_score,
        "relevance_reasons": relevance_reasons,
        "summary_text": summary_text,
        "work_items": work_items,
        "snapshot_hash": hashlib.sha256(markdownish.encode("utf-8")).hexdigest(),
        "word_count": word_count,
        "code_block_count": code_block_count,
        "number_count": number_count,
        "is_mostly_code": is_mostly_code,
        "is_popular_science": is_popular_science,
    }


def _capture_project_snapshot(url: str, user_id: int, source_id: int, raw_html: str) -> tuple[str, str]:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        raise RuntimeError("project blog screenshots require Playwright") from exc

    settings = get_settings()
    token = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
    screenshot_dir = settings.blog_screenshot_storage_path / f"user_{user_id}"
    html_dir = settings.blog_html_storage_path / f"user_{user_id}"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    html_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = screenshot_dir / f"source_{source_id}_{token}.png"
    html_path = html_dir / f"source_{source_id}_{token}.html"

    with sync_playwright() as playwright:
        host, port = parse_cdp_port(settings.blog_cdp_url)
        if not is_port_open(host, port) and settings.blog_launch_chrome:
            start_chrome_if_needed(settings)
        uses_cdp = is_port_open(host, port)
        browser = (
            playwright.chromium.connect_over_cdp(settings.blog_cdp_url)
            if uses_cdp
            else playwright.chromium.launch(headless=True)
        )
        page = None
        try:
            context = browser.contexts[0] if uses_cdp and browser.contexts else browser.new_context(
                viewport={"width": 1440, "height": 1000}
            )
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=settings.blog_navigation_timeout_ms)
            page.wait_for_timeout(settings.blog_page_load_wait_ms)
            page.screenshot(path=str(screenshot_path), full_page=True)
        finally:
            if page is not None:
                page.close()
            if not uses_cdp:
                browser.close()
    html_path.write_text(raw_html, encoding="utf-8")
    return str(screenshot_path), str(html_path)


def _analyze_content(html: str, target_url: str, project_context: str = "") -> dict:
    markdownish = _html_to_markdownish(html)
    title = _extract_title(html, target_url)
    published_at = _extract_published_at(html)
    word_count = _count_words(markdownish)
    code_block_count = _count_code_blocks(markdownish)
    number_count = _count_numbers(markdownish)
    category, is_mostly_code, is_popular_science, status = _classify_blog(markdownish, code_block_count, word_count)
    semantic_analysis = analyze_project_blog(markdownish, title, project_context)
    is_project = semantic_analysis["is_project_training"]
    relevance_score = semantic_analysis["relevance_score"]
    relevance_reasons = semantic_analysis["relevance_reasons"]
    work_items = _extract_work_items(markdownish)
    summary_text = _summarize_text(markdownish)
    snapshot_hash = hashlib.sha256(markdownish.encode("utf-8")).hexdigest()
    return {
        "title": title,
        "content_md": markdownish,
        "published_at": published_at,
        "word_count": word_count,
        "code_block_count": code_block_count,
        "number_count": number_count,
        "category": category,
        "is_mostly_code": is_mostly_code,
        "is_popular_science": is_popular_science,
        "status": status,
        "summary_text": semantic_analysis["summary_text"] or summary_text,
        "work_items": semantic_analysis["work_items"] or work_items,
        "snapshot_hash": snapshot_hash,
        "is_project_training": is_project,
        "relevance_score": relevance_score,
        "relevance_reasons": relevance_reasons,
    }


def crawl_blog_source(db: Session, source: BlogSource, max_posts: int | None = None) -> dict:
    source_url = _normalize_url(source.source_url)
    if not source_url:
        raise HTTPException(status_code=400, detail="invalid blog source url")

    created_count = 0
    updated_count = 0
    crawled_count = 0
    filtered_count = 0
    screenshot_failed_count = 0
    now = datetime.utcnow()
    user = db.query(User).filter(User.id == source.user_id).first()
    project_context = _project_context_for_user(db, user) if user else ""
    analyses_by_url: dict[str, dict] = {}
    settings = get_settings()
    post_limit = max(1, int(max_posts or settings.blog_max_posts_per_source))

    try:
        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            listing_queue = [source_url]
            listing_seen: set[str] = set()
            candidate_links: list[str] = []
            candidate_seen: set[str] = set()
            while listing_queue and len(listing_seen) < int(settings.blog_max_pages):
                listing_url = listing_queue.pop(0)
                if listing_url in listing_seen:
                    continue
                listing_seen.add(listing_url)
                listing_resp = client.get(listing_url)
                listing_resp.raise_for_status()
                for link in _extract_post_links(listing_url, listing_resp.text):
                    if _is_pagination_url(link):
                        if link not in listing_seen and link not in listing_queue:
                            listing_queue.append(link)
                        continue
                    if link not in candidate_seen:
                        candidate_seen.add(link)
                        candidate_links.append(link)
                    if len(candidate_links) >= post_limit:
                        break
                if len(candidate_links) >= post_limit:
                    break
            if not candidate_links:
                candidate_links = [source_url]

            for target_url in candidate_links[:post_limit]:
                crawled_count += 1
                try:
                    resp = client.get(target_url)
                    resp.raise_for_status()
                except Exception:
                    continue
                payload = _analyze_content(resp.text, target_url, project_context)
                analyses_by_url[target_url] = payload
                _upsert_blog_audit(
                    db,
                    int(source.user_id),
                    target_url,
                    payload["title"],
                    payload["published_at"],
                    payload,
                )
                if not payload["is_project_training"]:
                    filtered_count += 1
                    stale = (
                        db.query(BlogPost)
                        .filter(BlogPost.user_id == source.user_id, BlogPost.url == target_url)
                        .first()
                    )
                    if stale:
                        _remove_snapshot_files(stale.screenshot_path, stale.raw_html_path)
                        db.delete(stale)
                    continue
                existing = (
                    db.query(BlogPost)
                    .filter(BlogPost.user_id == source.user_id, BlogPost.url == target_url)
                    .first()
                )
                try:
                    screenshot_path, html_path = _capture_project_snapshot(
                        target_url,
                        int(source.user_id),
                        int(source.id),
                        resp.text,
                    )
                except Exception:
                    screenshot_failed_count += 1
                    if not existing or not existing.screenshot_path or not Path(existing.screenshot_path).is_file():
                        continue
                    screenshot_path = existing.screenshot_path
                    html_path = existing.raw_html_path
                if not existing:
                    existing = BlogPost(
                        user_id=source.user_id,
                        source_id=source.id,
                        title=payload["title"],
                        url=target_url,
                        status="normal",
                        content_md=_sanitize_utf8mb4(payload["content_md"]),
                        category="project_update",
                        summary_text=payload["summary_text"],
                        work_items_json=dumps_work_items(payload["work_items"]),
                        snapshot_hash=payload["snapshot_hash"],
                        published_at=payload["published_at"],
                        word_count=payload["word_count"],
                        code_block_count=payload["code_block_count"],
                        number_count=payload["number_count"],
                        is_mostly_code=payload["is_mostly_code"],
                        is_popular_science=payload["is_popular_science"],
                        screenshot_path=screenshot_path,
                        raw_html_path=html_path,
                        capture_status="success",
                        capture_timestamp=now,
                        created_at=now,
                        updated_at=now,
                    )
                    db.add(existing)
                    created_count += 1
                else:
                    existing.source_id = source.id
                    existing.title = payload["title"]
                    existing.status = "normal"
                    existing.content_md = _sanitize_utf8mb4(payload["content_md"])
                    existing.category = "project_update"
                    existing.summary_text = payload["summary_text"]
                    existing.work_items_json = dumps_work_items(payload["work_items"])
                    existing.snapshot_hash = payload["snapshot_hash"]
                    existing.published_at = payload["published_at"]
                    existing.word_count = payload["word_count"]
                    existing.code_block_count = payload["code_block_count"]
                    existing.number_count = payload["number_count"]
                    existing.is_mostly_code = payload["is_mostly_code"]
                    existing.is_popular_science = payload["is_popular_science"]
                    existing.screenshot_path = screenshot_path
                    existing.raw_html_path = html_path
                    existing.capture_status = "success"
                    existing.capture_error = ""
                    existing.capture_timestamp = now
                    existing.updated_at = now
                    updated_count += 1

        source.last_crawled_at = now
        source.last_error = None
        source.updated_at = now
        db.add(source)

        for stale in db.query(BlogPost).filter(BlogPost.source_id == source.id).all():
            stale_analysis = analyses_by_url.get(stale.url) or analyze_project_blog(
                stale.content_md, stale.title, project_context
            )
            screenshot_exists = bool(stale.screenshot_path) and Path(stale.screenshot_path).is_file()
            if not stale_analysis["is_project_training"] or not screenshot_exists:
                _remove_snapshot_files(stale.screenshot_path, stale.raw_html_path)
                db.delete(stale)
        db.commit()
        db.refresh(source)
        return {
            "source": source,
            "crawled_count": crawled_count,
            "created_count": created_count,
            "updated_count": updated_count,
            "filtered_count": filtered_count,
            "screenshot_failed_count": screenshot_failed_count,
        }
    except httpx.HTTPError as exc:
        db.rollback()
        source.last_crawled_at = now
        source.last_error = str(exc)
        db.add(source)
        db.commit()
        db.refresh(source)
        raise HTTPException(status_code=502, detail=f"blog crawl failed: {exc}") from exc
