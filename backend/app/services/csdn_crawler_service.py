from __future__ import annotations

import random
import re
import socket
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, urlunparse

try:
    from playwright.sync_api import (
        BrowserContext,
        Page,
        Playwright,
        TimeoutError as PlaywrightTimeoutError,
    )
    PLAYWRIGHT_AVAILABLE = True
except Exception:
    BrowserContext = object
    Page = object
    Playwright = object
    PLAYWRIGHT_AVAILABLE = False

    class PlaywrightTimeoutError(Exception):
        pass

from app.core.config import Settings

ARTICLE_LINK_SELECTORS = (
    "a[href*='/article/details/']",
    "a[href*='article/details']",
    ".article-list a",
    ".blog-list-box a",
    "main a",
)

CONTENT_SELECTORS = (
    "#content_views",
    ".htmledit_views",
    "main",
    "article",
)

ARTICLE_TITLE_SELECTORS = (
    ".article-title-box h1",
    "h1.title-article",
    "h1",
)

TAG_SELECTORS = (
    ".tag-link",
    ".tag-box a",
    ".article-tags-box a",
    ".blog-tags-box a",
)

PUBLISH_TIME_SELECTORS = (
    'meta[itemprop="datePublished"]',
    'meta[property="article:published_time"]',
    ".article-info-box .time",
    ".bar-content .time",
    ".time",
)

COUNT_TEXT_PATTERNS = (
    r"原创\s*(\d+)\s*篇",
    r"文章数\s*(\d+)",
    r"共\s*(\d+)\s*篇",
)


def cleanup_csdn_extracted_text(value: str) -> str:
    text = (value or "").replace("\r\n", "\n").replace("\r", "\n")

    def drop_inline_sequence(match: re.Match) -> str:
        raw = (match.group(0) or "").strip()
        parts = [p for p in raw.split() if p.isdigit()]
        if len(parts) < 5:
            return match.group(0)
        nums = [int(p) for p in parts]
        if nums[0] == 1 and nums == list(range(1, len(nums) + 1)):
            return ""
        return match.group(0)

    text = re.sub(r"(?:\b\d+\b(?:\s+\b\d+\b){4,})", drop_inline_sequence, text)

    lines = [line.rstrip() for line in text.split("\n")]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()

    output: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.isdigit() and line == "1":
            j = i
            nums: list[int] = []
            while j < len(lines) and lines[j].strip().isdigit():
                nums.append(int(lines[j].strip()))
                j += 1
            if len(nums) >= 5 and nums == list(range(1, len(nums) + 1)):
                i = j
                continue
        output.append(lines[i])
        i += 1

    cleaned: list[str] = []
    blank = 0
    for line in output:
        if not line.strip():
            blank += 1
            if blank <= 2:
                cleaned.append("")
            continue
        blank = 0
        cleaned.append(line)

    return "\n".join(cleaned).strip()


@dataclass(slots=True)
class CsdnArticleListResult:
    total_blog_count: int | None
    articles: list[dict[str, str]]


@dataclass(slots=True)
class CsdnArticleDetail:
    title: str
    url: str
    summary: str
    content_text: str
    content_md: str
    raw_html: str
    tags: list[str]
    published_at: datetime | None
    capture_timestamp: datetime
    screenshot_path: Path
    html_path: Path
    capture_status: str
    capture_error: str


def normalize_csdn_home_input(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        raise ValueError("empty csdn blog identifier")
    if raw.startswith("http://") or raw.startswith("https://"):
        parsed = urlparse(raw)
        if not parsed.netloc.endswith("csdn.net"):
            raise ValueError("输入的 URL 不是有效的 CSDN 博客主页。")
        parts = [part for part in parsed.path.split("/") if part]
        if not parts:
            raise ValueError("无法从 URL 中解析用户名。")
        return f"https://blog.csdn.net/{parts[0]}"
    username = raw.strip("/ ")
    if not username or "/" in username or " " in username:
        raise ValueError("请输入有效的 CSDN 用户名或完整博客地址。")
    return f"https://blog.csdn.net/{username}"


def extract_username(home_url: str) -> str:
    parsed = urlparse(normalize_csdn_home_input(home_url))
    parts = [part for part in parsed.path.split("/") if part]
    if not parts:
        raise ValueError("无法从 URL 中解析用户名。")
    return parts[0]


def build_blog_home_url(home_url: str) -> str:
    username = extract_username(home_url)
    return f"https://blog.csdn.net/{username}?type=blog"


def build_article_list_url(home_url: str, page_no: int) -> str:
    username = extract_username(home_url)
    return f"https://blog.csdn.net/{username}/article/list/{page_no}"


def detect_chrome_executable() -> str | None:
    candidates = [
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
        Path.home() / r"AppData\Local\Google\Chrome\Application\chrome.exe",
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path.home() / r"AppData\Local\Microsoft\Edge\Application\msedge.exe",
        Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        Path("/usr/bin/google-chrome"),
        Path("/usr/bin/chromium"),
        Path("/usr/bin/chromium-browser"),
    ]
    for path in candidates:
        if path.exists():
            return str(path)
    return None


def parse_cdp_port(cdp_url: str) -> tuple[str, int]:
    parsed = urlparse(cdp_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or not parsed.port:
        raise ValueError(f"无效的 CDP 地址：{cdp_url}")
    return parsed.hostname, parsed.port


def is_port_open(host: str, port: int, timeout_seconds: float = 1.0) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout_seconds)
        return sock.connect_ex((host, port)) == 0


def start_chrome_if_needed(settings: Settings) -> subprocess.Popen[str] | None:
    host, port = parse_cdp_port(settings.blog_cdp_url)
    if is_port_open(host, port):
        return None
    if not settings.blog_launch_chrome:
        raise RuntimeError("未检测到 Chrome 调试端口，请先手动启动已登录 Chrome。")

    chrome_exe = settings.blog_chrome_exe or detect_chrome_executable()
    if not chrome_exe:
        raise FileNotFoundError("未找到 Chrome 可执行文件。")

    profile_dir = settings.blog_profile_storage_path
    profile_dir.mkdir(parents=True, exist_ok=True)

    command = [
        chrome_exe,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "about:blank",
    ]
    process = subprocess.Popen(command)
    deadline = time.time() + 60
    while time.time() < deadline:
        if is_port_open(host, port):
            return process
        if process.poll() is not None:
            time.sleep(1.0)
            if is_port_open(host, port):
                return process
            raise RuntimeError(f"Chrome/Edge 启动失败，退出码：{process.returncode}")
        time.sleep(0.5)
    raise RuntimeError("Chrome 已启动，但调试端口未在预期时间内就绪。")


class CsdnCrawler:
    def __init__(self, context: BrowserContext, settings: Settings) -> None:
        self.context = context
        self.settings = settings

    def collect_articles(self, home_url: str) -> CsdnArticleListResult:
        username = extract_username(home_url)
        page = self._new_page()
        seen_urls: set[str] = set()
        collected: list[dict[str, str]] = []
        total_blog_count: int | None = None

        try:
            blog_home_url = build_blog_home_url(home_url)
            if self._safe_goto(page, blog_home_url):
                total_blog_count = self._extract_blog_count(page)
                homepage_links = self._extract_links_from_list_page(page, username=username)
                for item in homepage_links:
                    if item["url"] not in seen_urls:
                        seen_urls.add(item["url"])
                        collected.append(item)

            for page_no in range(1, self.settings.blog_max_pages + 1):
                list_url = build_article_list_url(home_url, page_no)
                if not self._safe_goto(page, list_url):
                    break
                links = self._extract_links_from_list_page(page, username=username)
                fresh_links = [item for item in links if item["url"] not in seen_urls]
                if not fresh_links:
                    break
                for item in fresh_links:
                    seen_urls.add(item["url"])
                collected.extend(fresh_links)
        finally:
            page.close()

        return CsdnArticleListResult(total_blog_count=total_blog_count, articles=collected)

    def fetch_article_detail(
        self,
        article_url: str,
        fallback_title: str,
        user_storage_dir: Path,
        index: int,
    ) -> CsdnArticleDetail | None:
        page = self._new_page()
        try:
            for attempt in range(3):
                if not self._safe_goto(page, article_url):
                    continue
                self._wait_for_article_ready(page)
                title = self._extract_article_title(page) or fallback_title
                summary = self._extract_summary(page)
                content_text = self._extract_content_text(page)
                raw_html = page.content()
                if self._is_article_page_ready(title=title, content_text=content_text, raw_html=raw_html):
                    tags = self._extract_tags(page)
                    capture_timestamp = datetime.utcnow()
                    screenshot_path, html_path = self._build_output_paths(
                        user_storage_dir=user_storage_dir,
                        article_title=title,
                        capture_timestamp=capture_timestamp,
                        index=index,
                    )
                    self._prepare_page_for_capture(page)
                    page.screenshot(path=str(screenshot_path), full_page=True)
                    html_path.write_text(raw_html, encoding="utf-8")
                    return CsdnArticleDetail(
                        title=title,
                        url=article_url,
                        summary=summary,
                        content_text=content_text,
                        content_md=content_text,
                        raw_html=raw_html,
                        tags=tags,
                        published_at=self._extract_publish_time(page),
                        capture_timestamp=capture_timestamp,
                        screenshot_path=screenshot_path,
                        html_path=html_path,
                        capture_status="success",
                        capture_error="",
                    )
                page.wait_for_timeout(1500 * (attempt + 1))

            return None
        finally:
            page.close()

    def _new_page(self) -> Page:
        page = self.context.new_page()
        page.set_default_timeout(self.settings.blog_navigation_timeout_ms)
        page.set_default_navigation_timeout(self.settings.blog_navigation_timeout_ms)
        return page

    def _safe_goto(self, page: Page, url: str) -> bool:
        try:
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_timeout(self.settings.blog_page_load_wait_ms)
            return True
        except PlaywrightTimeoutError:
            return False

    def _extract_links_from_list_page(self, page: Page, username: str) -> list[dict[str, str]]:
        found: dict[str, dict[str, str]] = {}
        for selector in ARTICLE_LINK_SELECTORS:
            anchors = page.locator(selector)
            count = min(anchors.count(), 200)
            for index in range(count):
                anchor = anchors.nth(index)
                href = (anchor.get_attribute("href") or "").strip()
                title = self._extract_card_title(anchor)
                if not href or not title or "/article/details/" not in href:
                    continue
                absolute_url = self._normalize_article_url(href)
                if not self._looks_like_user_article(absolute_url, username):
                    continue
                found.setdefault(
                    absolute_url,
                    {"title": title, "url": absolute_url, "summary": self._extract_card_summary(anchor)},
                )
            if found:
                break
        return list(found.values())

    def _extract_card_title(self, anchor) -> str:
        try:
            card = anchor.locator("xpath=ancestor::*[contains(@class, 'article') or contains(@class, 'blog')][1]").first
            for selector in (".article-item-title", ".blog-text h4", "h4", "h2", "h3"):
                locator = card.locator(selector).first
                if locator.count() > 0:
                    text = self._normalize_text(locator.inner_text())
                    if text:
                        return text
        except Exception:
            pass
        try:
            return self._normalize_text(anchor.inner_text())
        except Exception:
            return ""

    def _extract_card_summary(self, anchor) -> str:
        try:
            card = anchor.locator("xpath=ancestor::*[contains(@class, 'article') or contains(@class, 'blog')][1]").first
            for selector in (".article-item-box .desc", ".blog-list-box .content", ".description"):
                locator = card.locator(selector).first
                if locator.count() > 0:
                    text = self._normalize_text(locator.inner_text())
                    if text:
                        return text
        except Exception:
            return ""
        return ""

    def _normalize_article_url(self, href: str) -> str:
        if href.startswith("//"):
            href = f"https:{href}"
        if href.startswith("/"):
            href = f"https://blog.csdn.net{href}"
        parsed = urlparse(href)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", parsed.query, ""))

    def _looks_like_user_article(self, url: str, username: str) -> bool:
        parsed = urlparse(url)
        if not parsed.netloc.endswith("csdn.net"):
            return False
        return parsed.path.strip("/").startswith(f"{username}/article/details/")

    def _extract_blog_count(self, page: Page) -> int | None:
        text = self._normalize_text(page.locator("body").first.inner_text())
        for pattern in COUNT_TEXT_PATTERNS:
            match = re.search(pattern, text)
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    continue
        return None

    def _extract_article_title(self, page: Page) -> str:
        for selector in ARTICLE_TITLE_SELECTORS:
            locator = page.locator(selector).first
            try:
                if locator.count() > 0:
                    text = self._normalize_text(locator.inner_text())
                    if text:
                        return text
            except Exception:
                continue
        return ""

    def _extract_summary(self, page: Page) -> str:
        for selector in ('meta[name="description"]', 'meta[property="og:description"]', ".article-info-box .desc"):
            locator = page.locator(selector).first
            try:
                if locator.count() == 0:
                    continue
                if selector.startswith("meta"):
                    content = locator.get_attribute("content")
                    if content:
                        return self._normalize_text(content)
                text = self._normalize_text(locator.inner_text())
                if text:
                    return text
            except Exception:
                continue
        return ""

    def _extract_tags(self, page: Page) -> list[str]:
        tags: list[str] = []
        seen: set[str] = set()
        for selector in TAG_SELECTORS:
            locators = page.locator(selector)
            try:
                count = min(locators.count(), 20)
            except Exception:
                count = 0
            for index in range(count):
                try:
                    text = self._normalize_text(locators.nth(index).inner_text())
                except Exception:
                    continue
                if text and text not in seen:
                    seen.add(text)
                    tags.append(text)
            if tags:
                break
        return tags

    def _extract_content_text(self, page: Page) -> str:
        for selector in CONTENT_SELECTORS:
            locator = page.locator(selector).first
            try:
                if locator.count() == 0:
                    continue
                text = cleanup_csdn_extracted_text(locator.inner_text())
                if text:
                    return text
            except Exception:
                continue
        return ""

    def _extract_publish_time(self, page: Page) -> datetime | None:
        for selector in PUBLISH_TIME_SELECTORS:
            locator = page.locator(selector).first
            try:
                if locator.count() == 0:
                    continue
                value = locator.get_attribute("content") if selector.startswith("meta") else locator.inner_text()
                if value:
                    return self._parse_datetime(self._normalize_text(value))
            except Exception:
                continue
        return None

    def _parse_datetime(self, value: str) -> datetime | None:
        if not value:
            return None
        value = value.replace("已于", "").replace("修改", "").strip()
        patterns = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S+08:00", "%Y-%m-%dT%H:%M:%S")
        for pattern in patterns:
            try:
                return datetime.strptime(value, pattern)
            except ValueError:
                continue
        return None

    def _wait_for_article_ready(self, page: Page) -> None:
        try:
            page.wait_for_load_state("load", timeout=min(self.settings.blog_navigation_timeout_ms, 15000))
        except PlaywrightTimeoutError:
            pass
        for selector in ARTICLE_TITLE_SELECTORS:
            try:
                page.locator(selector).first.wait_for(state="visible", timeout=6000)
                break
            except PlaywrightTimeoutError:
                continue
        for selector in CONTENT_SELECTORS:
            try:
                page.locator(selector).first.wait_for(state="attached", timeout=6000)
                break
            except PlaywrightTimeoutError:
                continue
        self._soft_scroll(page)

    def _prepare_page_for_capture(self, page: Page) -> None:
        try:
            page.wait_for_load_state("load", timeout=min(self.settings.blog_navigation_timeout_ms, 15000))
        except PlaywrightTimeoutError:
            pass
        self._soft_scroll(page)

    def _soft_scroll(self, page: Page) -> None:
        try:
            page.mouse.wheel(0, 1600)
            page.wait_for_timeout(800)
            page.mouse.wheel(0, -1600)
            page.wait_for_timeout(500)
        except Exception:
            pass

    def _is_article_page_ready(self, title: str, content_text: str, raw_html: str) -> bool:
        if not title:
            return False
        if content_text.strip():
            return True
        return len(raw_html) >= 15000 and "<body" in raw_html.lower()

    def _build_output_paths(
        self,
        user_storage_dir: Path,
        article_title: str,
        capture_timestamp: datetime,
        index: int,
    ) -> tuple[Path, Path]:
        screenshot_dir = user_storage_dir / "screenshots"
        html_dir = user_storage_dir / "html"
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        html_dir.mkdir(parents=True, exist_ok=True)
        ts = capture_timestamp.strftime("%Y%m%d_%H%M%S")
        safe_title = self._safe_name(article_title)
        screenshot_path = screenshot_dir / f"{ts}_{index:04d}_{safe_title}.png"
        html_path = html_dir / f"{ts}_{index:04d}_{safe_title}.html"
        return screenshot_path, html_path

    def _safe_name(self, value: str) -> str:
        value = re.sub(r'[\\/:*?"<>|]+', "_", value)
        value = re.sub(r"\s+", "_", value).strip("._ ")
        return value[:120] or "untitled"

    def _normalize_text(self, value: str) -> str:
        return re.sub(r"\s+", " ", value or "").strip()


def crawl_csdn_blog(
    playwright: Playwright,
    settings: Settings,
    blog_home_url: str,
    user_storage_dir: Path,
) -> tuple[CsdnArticleListResult, list[CsdnArticleDetail], list[dict[str, str]]]:
    host, port = parse_cdp_port(settings.blog_cdp_url)
    if not is_port_open(host, port):
        if settings.blog_launch_chrome:
            start_chrome_if_needed(settings)
        else:
            raise RuntimeError("未检测到 Chrome/Edge 调试端口，请先启动已登录的浏览器或开启自动启动。")
    browser = playwright.chromium.connect_over_cdp(settings.blog_cdp_url)
    try:
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        crawler = CsdnCrawler(context=context, settings=settings)
        article_result = crawler.collect_articles(blog_home_url)
        details: list[CsdnArticleDetail] = []
        failures: list[dict[str, str]] = []
        for index, article in enumerate(article_result.articles, start=1):
            time.sleep(random.uniform(settings.blog_min_delay_seconds, settings.blog_max_delay_seconds))
            detail = crawler.fetch_article_detail(
                article_url=article["url"],
                fallback_title=article["title"],
                user_storage_dir=user_storage_dir,
                index=index,
            )
            if detail is None:
                failures.append({"url": article["url"], "title": article["title"], "error": "detail page not ready"})
                continue
            details.append(detail)
        return article_result, details, failures
    finally:
        browser.close()
