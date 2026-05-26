from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.blog import BlogCrawlRun, BlogPost, BlogSource
from app.models.user import User
from app.services.csdn_crawler_service import crawl_csdn_blog, normalize_csdn_home_input


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
    user.blog_crawl_status = "running"
    db.commit()
    db.refresh(run)
    db.refresh(user)
    return run


def run_user_blog_crawl(db: Session, user: User, admin: User) -> BlogCrawlRun:
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

    run = create_crawl_run(db, user, admin)
    run.status = "running"
    run.started_at = _utcnow()
    db.commit()

    try:
        with sync_playwright() as playwright:
            article_result, details, failures = crawl_csdn_blog(
                playwright=playwright,
                settings=settings,
                blog_home_url=run.blog_home_url,
                user_storage_dir=_user_storage_dir(user.id),
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

        for detail in details:
            row = (
                db.query(BlogPost)
                .filter(BlogPost.user_id == user.id, BlogPost.url == detail.url)
                .first()
            )
            article_uid = detail.url.rstrip("/").split("/")[-1].split("#")[0]
            if row is None:
                row = BlogPost(
                    user_id=user.id,
                    title=detail.title,
                    url=detail.url,
                    source="csdn",
                    article_uid=article_uid,
                    status="normal",
                    summary=detail.summary,
                    content_md=detail.content_md,
                    content_text=detail.content_text,
                    raw_html_path=str(detail.html_path),
                    screenshot_path=str(detail.screenshot_path),
                    published_at=detail.published_at,
                    capture_status=detail.capture_status,
                    capture_error=detail.capture_error,
                    capture_timestamp=detail.capture_timestamp,
                    review_status="pending",
                )
                db.add(row)
            else:
                row.title = detail.title
                row.source = "csdn"
                row.article_uid = article_uid
                row.summary = detail.summary
                row.content_md = detail.content_md
                row.content_text = detail.content_text
                row.raw_html_path = str(detail.html_path)
                row.screenshot_path = str(detail.screenshot_path)
                row.published_at = detail.published_at
                row.capture_status = detail.capture_status
                row.capture_error = detail.capture_error
                row.capture_timestamp = detail.capture_timestamp
                row.updated_at = _utcnow()

        run.finished_at = _utcnow()
        user.blog_crawl_status = "success" if run.status in {"success", "partial_success"} else "failed"
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
    text = re.sub(
        r"(?is)<pre.*?><code.*?>(.*?)</code></pre>",
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
    return deduped[:30]


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

    is_mostly_code = code_block_count >= 2 or (code_hits >= 12 and word_count < 120)
    is_popular_science = science_hits >= 2 and project_hits == 0
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


def _analyze_content(html: str, target_url: str) -> dict:
    markdownish = _html_to_markdownish(html)
    title = _extract_title(html, target_url)
    published_at = _extract_published_at(html)
    word_count = _count_words(markdownish)
    code_block_count = _count_code_blocks(markdownish)
    number_count = _count_numbers(markdownish)
    category, is_mostly_code, is_popular_science, status = _classify_blog(markdownish, code_block_count, word_count)
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
        "summary_text": summary_text,
        "work_items": work_items,
        "snapshot_hash": snapshot_hash,
    }


def crawl_blog_source(db: Session, source: BlogSource, max_posts: int = 20) -> dict:
    source_url = _normalize_url(source.source_url)
    if not source_url:
        raise HTTPException(status_code=400, detail="invalid blog source url")

    created_count = 0
    updated_count = 0
    crawled_count = 0
    now = datetime.utcnow()

    try:
        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            source_resp = client.get(source_url)
            source_resp.raise_for_status()
            source_html = source_resp.text
            candidate_links = _extract_post_links(source_url, source_html)
            if not candidate_links:
                candidate_links = [source_url]
            else:
                candidate_links = [source_url] + candidate_links[: max(0, max_posts - 1)]

            for target_url in candidate_links[:max_posts]:
                crawled_count += 1
                try:
                    resp = client.get(target_url)
                    resp.raise_for_status()
                except Exception:
                    continue
                payload = _analyze_content(resp.text, target_url)
                existing = (
                    db.query(BlogPost)
                    .filter(BlogPost.user_id == source.user_id, BlogPost.url == target_url)
                    .first()
                )
                if not existing:
                    existing = BlogPost(
                        user_id=source.user_id,
                        source_id=source.id,
                        title=payload["title"],
                        url=target_url,
                        status=payload["status"],
                        content_md=payload["content_md"],
                        category=payload["category"],
                        summary_text=payload["summary_text"],
                        work_items_json=dumps_work_items(payload["work_items"]),
                        snapshot_hash=payload["snapshot_hash"],
                        published_at=payload["published_at"],
                        word_count=payload["word_count"],
                        code_block_count=payload["code_block_count"],
                        number_count=payload["number_count"],
                        is_mostly_code=payload["is_mostly_code"],
                        is_popular_science=payload["is_popular_science"],
                        created_at=now,
                        updated_at=now,
                    )
                    db.add(existing)
                    created_count += 1
                else:
                    existing.source_id = source.id
                    existing.title = payload["title"]
                    existing.status = payload["status"]
                    existing.content_md = payload["content_md"]
                    existing.category = payload["category"]
                    existing.summary_text = payload["summary_text"]
                    existing.work_items_json = dumps_work_items(payload["work_items"])
                    existing.snapshot_hash = payload["snapshot_hash"]
                    existing.published_at = payload["published_at"]
                    existing.word_count = payload["word_count"]
                    existing.code_block_count = payload["code_block_count"]
                    existing.number_count = payload["number_count"]
                    existing.is_mostly_code = payload["is_mostly_code"]
                    existing.is_popular_science = payload["is_popular_science"]
                    existing.updated_at = now
                    updated_count += 1

        source.last_crawled_at = now
        source.last_error = None
        source.updated_at = now
        db.add(source)
        db.commit()
        db.refresh(source)
        return {
            "source": source,
            "crawled_count": crawled_count,
            "created_count": created_count,
            "updated_count": updated_count,
        }
    except httpx.HTTPError as exc:
        db.rollback()
        source.last_crawled_at = now
        source.last_error = str(exc)
        db.add(source)
        db.commit()
        db.refresh(source)
        raise HTTPException(status_code=502, detail=f"blog crawl failed: {exc}") from exc
