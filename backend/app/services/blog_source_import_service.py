from __future__ import annotations

from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.models.blog import BlogSource
from app.models.user import User


def _normalize_url(url: str | None) -> str:
    value = str(url or "").strip()
    if not value:
        return ""
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return parsed._replace(fragment="").geturl()


def _upsert_source(
    db: Session,
    user_id: int,
    source_url: str,
    source_type: str,
    site_name: str = "",
) -> bool:
    normalized = _normalize_url(source_url)
    if not normalized:
        return False
    existing = db.query(BlogSource).filter(BlogSource.user_id == user_id, BlogSource.source_url == normalized).first()
    if existing:
        changed = False
        if source_type and existing.source_type != source_type:
            existing.source_type = source_type
            changed = True
        if site_name and existing.site_name != site_name:
            existing.site_name = site_name
            changed = True
        if not existing.is_active:
            existing.is_active = True
            changed = True
        if changed:
            db.add(existing)
        return changed
    db.add(
        BlogSource(
            user_id=user_id,
            source_url=normalized,
            source_type=source_type,
            site_name=site_name,
            is_active=True,
        )
    )
    return True


def import_blog_sources_from_draft_content(
    db: Session,
    user: User,
    content: dict | None,
) -> dict[str, int]:
    payload = content or {}
    created_or_updated = 0

    project_blog_url = _normalize_url(payload.get("project_blog_url"))
    if project_blog_url:
        if _upsert_source(db, user.id, project_blog_url, "project_group", site_name="Auto Imported Project Blog"):
            created_or_updated += 1

    member_urls = payload.get("member_blog_urls") or []
    if not isinstance(member_urls, list):
        member_urls = [member_urls]
    member_urls = [_normalize_url(item) for item in member_urls]
    member_urls = [item for item in member_urls if item]

    participants = payload.get("participants") or []
    if not isinstance(participants, list):
        participants = []

    personal_candidate = ""
    if len(member_urls) == 1:
        personal_candidate = member_urls[0]
    elif participants and len(member_urls) == len(participants):
        owner_index = None
        for index, participant in enumerate(participants):
            sid = str((participant or {}).get("student_id") or "").strip()
            if sid and sid == str(user.student_id or "").strip():
                owner_index = index
                break
        if owner_index is not None and 0 <= owner_index < len(member_urls):
            personal_candidate = member_urls[owner_index]

    if personal_candidate:
        if _upsert_source(db, user.id, personal_candidate, "personal", site_name="Auto Imported Personal Blog"):
            created_or_updated += 1

    return {
        "imported_count": created_or_updated,
        "project_url_count": 1 if project_blog_url else 0,
        "personal_url_count": 1 if personal_candidate else 0,
    }
