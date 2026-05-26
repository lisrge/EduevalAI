from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.models.blog import BlogPost, BlogSource
from app.models.document_draft import ApplicationDraft, TaskDraft
from app.models.user import User
from app.schemas.blog import (
    BlogCrawlResponse,
    BlogOverviewItem,
    BlogOverviewSummary,
    BlogPostDetail,
    BlogPostInfo,
    BlogSourceInfo,
    BlogSourcePayload,
)
from app.services.auth_service import get_user_by_token
from app.services.blog_crawler_service import crawl_blog_source, loads_work_items
from app.services.blog_source_import_service import import_blog_sources_from_draft_content

router = APIRouter(prefix="/blogs", tags=["blogs"])


def _bearer_token(authorization: str | None) -> str:
    if not authorization:
        return ""
    value = authorization.strip()
    if value.lower().startswith("bearer "):
        return value[7:].strip()
    return ""


def _current_user(authorization: str | None, db: Session) -> User:
    return get_user_by_token(db, _bearer_token(authorization))


def _require_admin(user: User) -> None:
    if str(user.role or "").lower() != "admin":
        raise HTTPException(status_code=403, detail="admin required")


def _source_info(row: BlogSource) -> BlogSourceInfo:
    return BlogSourceInfo(
        id=row.id,
        user_id=row.user_id,
        source_url=row.source_url,
        source_type=row.source_type,
        site_name=row.site_name,
        is_active=row.is_active,
        last_crawled_at=row.last_crawled_at,
        last_error=row.last_error,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _post_info(row: BlogPost, source_type: str = "personal") -> BlogPostInfo:
    return BlogPostInfo(
        id=row.id,
        user_id=row.user_id,
        source_id=row.source_id,
        title=row.title,
        url=row.url,
        status=row.status,
        category=row.category,
        source_type=source_type,
        summary_text=row.summary_text,
        work_items=loads_work_items(row.work_items_json),
        published_at=row.published_at,
        word_count=row.word_count,
        code_block_count=row.code_block_count,
        number_count=row.number_count,
        is_mostly_code=bool(row.is_mostly_code),
        is_popular_science=bool(row.is_popular_science),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("/admin/overview", response_model=BlogOverviewSummary)
def admin_blog_overview(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user(authorization, db)
    _require_admin(me)

    users = {item.id: item for item in db.query(User).order_by(User.id.asc()).all()}
    sources = db.query(BlogSource).order_by(BlogSource.id.asc()).all()
    posts = db.query(BlogPost).order_by(BlogPost.published_at.desc(), BlogPost.updated_at.desc()).all()

    source_count_map: dict[int, list[BlogSource]] = defaultdict(list)
    for source in sources:
        source_count_map[int(source.user_id)].append(source)

    post_source_type_map = {int(source.id): source.source_type for source in sources}
    post_map: dict[int, list[BlogPost]] = defaultdict(list)
    for post in posts:
        post_map[int(post.user_id)].append(post)

    items: list[BlogOverviewItem] = []
    for user_id, user in users.items():
        user_sources = source_count_map.get(int(user_id), [])
        user_posts = post_map.get(int(user_id), [])
        latest_published_at = None
        if user_posts:
            latest_published_at = max([item.published_at or item.updated_at for item in user_posts])
        work_item_count = sum(len(loads_work_items(item.work_items_json)) for item in user_posts)
        items.append(
            BlogOverviewItem(
                user_id=int(user_id),
                student_id=user.student_id,
                source_count=len(user_sources),
                active_source_count=sum(1 for item in user_sources if item.is_active),
                post_count=len(user_posts),
                project_blog_count=sum(
                    1
                    for item in user_posts
                    if post_source_type_map.get(int(item.source_id or 0), "personal") == "project_group"
                ),
                personal_blog_count=sum(
                    1
                    for item in user_posts
                    if post_source_type_map.get(int(item.source_id or 0), "personal") != "project_group"
                ),
                code_dump_count=sum(1 for item in user_posts if item.is_mostly_code or item.category == "code_dump"),
                popular_science_count=sum(
                    1 for item in user_posts if item.is_popular_science or item.category == "popular_science"
                ),
                work_item_count=work_item_count,
                latest_published_at=latest_published_at,
            )
        )

    return BlogOverviewSummary(
        total_sources=len(sources),
        total_posts=len(posts),
        total_code_dump_posts=sum(1 for item in posts if item.is_mostly_code or item.category == "code_dump"),
        total_popular_science_posts=sum(1 for item in posts if item.is_popular_science or item.category == "popular_science"),
        total_project_blog_posts=sum(
            1 for item in posts if post_source_type_map.get(int(item.source_id or 0), "personal") == "project_group"
        ),
        users=items,
    )


@router.get("/admin/users/{user_id}/sources", response_model=list[BlogSourceInfo])
def admin_list_user_blog_sources(
    user_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user(authorization, db)
    _require_admin(me)
    return [
        _source_info(item)
        for item in db.query(BlogSource).filter(BlogSource.user_id == user_id).order_by(BlogSource.updated_at.desc()).all()
    ]


@router.post("/admin/users/{user_id}/sources", response_model=BlogSourceInfo)
def admin_create_user_blog_source(
    user_id: int,
    payload: BlogSourcePayload,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user(authorization, db)
    _require_admin(me)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    source = BlogSource(
        user_id=user_id,
        source_url=(payload.source_url or "").strip(),
        source_type=(payload.source_type or "personal").strip() or "personal",
        site_name=(payload.site_name or "").strip(),
        is_active=bool(payload.is_active),
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return _source_info(source)


@router.put("/admin/blog-sources/{source_id}", response_model=BlogSourceInfo)
def admin_update_blog_source(
    source_id: int,
    payload: BlogSourcePayload,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user(authorization, db)
    _require_admin(me)
    source = db.query(BlogSource).filter(BlogSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="blog source not found")
    source.source_url = (payload.source_url or "").strip()
    source.source_type = (payload.source_type or "personal").strip() or "personal"
    source.site_name = (payload.site_name or "").strip()
    source.is_active = bool(payload.is_active)
    db.add(source)
    db.commit()
    db.refresh(source)
    return _source_info(source)


@router.post("/admin/blog-sources/{source_id}/crawl", response_model=BlogCrawlResponse)
def admin_crawl_blog_source(
    source_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user(authorization, db)
    _require_admin(me)
    source = db.query(BlogSource).filter(BlogSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="blog source not found")
    result = crawl_blog_source(db, source)
    return BlogCrawlResponse(
        message="blog crawl completed",
        source=_source_info(result["source"]),
        crawled_count=int(result["crawled_count"]),
        created_count=int(result["created_count"]),
        updated_count=int(result["updated_count"]),
    )


@router.post("/admin/crawl-all", response_model=dict)
def admin_crawl_all_blog_sources(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user(authorization, db)
    _require_admin(me)
    sources = db.query(BlogSource).filter(BlogSource.is_active == True).order_by(BlogSource.id.asc()).all()
    total_sources = 0
    total_posts = 0
    total_created = 0
    total_updated = 0
    for source in sources:
        result = crawl_blog_source(db, source)
        total_sources += 1
        total_posts += int(result["crawled_count"])
        total_created += int(result["created_count"])
        total_updated += int(result["updated_count"])
    return {
        "message": "all blog sources crawled",
        "source_count": total_sources,
        "crawled_count": total_posts,
        "created_count": total_created,
        "updated_count": total_updated,
    }


@router.post("/admin/users/{user_id}/import-draft-sources", response_model=dict)
def admin_import_blog_sources_from_drafts(
    user_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user(authorization, db)
    _require_admin(me)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="user not found")

    imported_count = 0
    draft_count = 0
    for row in db.query(ApplicationDraft).filter(ApplicationDraft.user_id == user_id).all():
        from app.services.document_draft_service import loads_content

        result = import_blog_sources_from_draft_content(db, user, loads_content(row.content_json))
        imported_count += int(result.get("imported_count") or 0)
        draft_count += 1
    for row in db.query(TaskDraft).filter(TaskDraft.user_id == user_id).all():
        from app.services.document_draft_service import loads_content

        result = import_blog_sources_from_draft_content(db, user, loads_content(row.content_json))
        imported_count += int(result.get("imported_count") or 0)
        draft_count += 1
    db.commit()
    return {
        "message": "draft blog sources imported",
        "draft_count": draft_count,
        "imported_count": imported_count,
    }


@router.get("/admin/users/{user_id}/posts", response_model=list[BlogPostInfo])
def admin_list_user_blog_posts(
    user_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user(authorization, db)
    _require_admin(me)
    sources = {int(item.id): item for item in db.query(BlogSource).filter(BlogSource.user_id == user_id).all()}
    rows = (
        db.query(BlogPost)
        .filter(BlogPost.user_id == user_id)
        .order_by(BlogPost.published_at.desc(), BlogPost.updated_at.desc())
        .all()
    )
    return [
        _post_info(row, source_type=getattr(sources.get(int(row.source_id or 0)), "source_type", "personal"))
        for row in rows
    ]


@router.get("/admin/posts/{post_id}", response_model=BlogPostDetail)
def admin_get_blog_post_detail(
    post_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user(authorization, db)
    _require_admin(me)
    row = db.query(BlogPost).filter(BlogPost.id == post_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="blog post not found")
    source = db.query(BlogSource).filter(BlogSource.id == row.source_id).first() if row.source_id else None
    info = _post_info(row, source_type=getattr(source, "source_type", "personal"))
    return BlogPostDetail(**info.model_dump(), content_md=row.content_md, snapshot_hash=row.snapshot_hash)


@router.get("/admin/posts/{post_id}/md")
def admin_get_blog_post_markdown(
    post_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user(authorization, db)
    _require_admin(me)
    row = db.query(BlogPost).filter(BlogPost.id == post_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="blog post not found")
    return PlainTextResponse(row.content_md or "", media_type="text/markdown; charset=utf-8")
