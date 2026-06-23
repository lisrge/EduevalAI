from __future__ import annotations

import hashlib
import json
import re
import secrets
import string
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.blog import BlogSource
from app.models.document_import import DocumentImportBatch, DocumentImportFile
from app.models.group import UserGroup
from app.models.user import User
from app.services.auth_service import create_user_basic
from app.services.text_extractor import extract_text

URL_RE = re.compile(r"https?://[^\s|，。；;）)]+", re.I)
STUDENT_ID_RE = re.compile(r"(?<!\d)(\d{12})(?!\d)")


def _clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip(" |：:")


def _normalize_project(value: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", (value or "").lower())[:80]


def _group_key(project_name: str, member_ids: list[str]) -> str:
    seed = _normalize_project(project_name) + "|" + "|".join(sorted(set(member_ids)))
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]


def _field(text: str, labels: tuple[str, ...]) -> str:
    for label in labels:
        # Strategy 1: pipe/colon separator (structured tables)
        match = re.search(rf"(?im)^\s*{re.escape(label)}\s*[|：:]\s*([^\n|]+)", text)
        if match:
            return _clean(match.group(1))
        # Strategy 2: space separator followed by Chinese/alphanumeric content
        match = re.search(rf"(?im)^\s*{re.escape(label)}\s+([^\n|]{{2,120}})", text)
        if match:
            val = _clean(match.group(1))
            # Must contain actual content (CJK or alphanumeric)
            if not re.search(r"[一-鿿\w]", val):
                continue
            # Filter out values that are just adjacent labels (space match is too greedy)
            label_words = ("负责人", "手机号码", "指导教师", "团队名称", "项目名称", "成员", "参加人员")
            if val in label_words or all(w in label_words for w in val.split()):
                continue
            return val
    return ""


def _fallback_parse(text: str, file_name: str) -> dict:
    doc_type = "task" if "任务书" in file_name or "任务书" in text[:500] else "application"
    project_name = _field(text, ("项目名称", "项目名", "项目题目"))
    team_name = _field(text, ("团队名称", "小组名称", "组名"))
    leader_name = _field(text, ("负责人", "项目负责人", "组长", "团队负责人", "队长"))

    members: list[dict] = []
    seen_ids: set[str] = set()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for i, line in enumerate(lines):
        for sid in STUDENT_ID_RE.findall(line):
            if sid in seen_ids:
                continue
            parts = [_clean(part) for part in line.split("|") if _clean(part)]
            name = ""
            # Try same line: name before or after sid
            if sid in parts:
                index = parts.index(sid)
                if index > 0:
                    name = parts[index - 1]
            if not name:
                before = line.split(sid, 1)[0]
                candidates = re.findall(r"[\u4e00-\u9fff]{2,8}", before)
                name = candidates[-1] if candidates else ""
            # Also check nearby lines for a name (PDF tables often split cells across lines)
            if not name:
                for offset in (-1, 1):
                    ni = i + offset
                    if 0 <= ni < len(lines):
                        nearby_names = re.findall(r"[\u4e00-\u9fff]{2,4}", lines[ni])
                        if nearby_names and len(nearby_names[0]) >= 2:
                            name = nearby_names[0]
                            break
            members.append({"student_id": sid, "name": name, "blog_url": "", "role": ""})
            seen_ids.add(sid)

    urls = list(dict.fromkeys(URL_RE.findall(text)))
    gitee_url = next((url for url in urls if "gitee.com" in urlparse(url).netloc.lower()), "")

    # Extract member names from blog URL sections like "（1）张三：https://..."
    blog_name_map: dict[str, str] = {}  # url -> name
    blog_section = text
    for start_marker in ("个人博客地址", "成员个人博客地址", "博客地址", "成员博客"):
        if start_marker in text:
            blog_section = text.split(start_marker, 1)[1]
            break
    for end_marker in ("项目介绍", "实施计划", "预期成果", "项目仓库", "Gitee", "gitee"):
        if end_marker in blog_section:
            blog_section = blog_section.split(end_marker, 1)[0]
            break
    # Match patterns like: （1）张三：https://... or 1. 张三 https://... or 张三：https://...
    name_url_pairs = re.findall(
        r"(?:（?\d+）?[.、．\s]*)?([一-鿿]{2,6})[：:\s]+({http_url})".replace("{http_url}", URL_RE.pattern),
        blog_section,
    )
    for name, url in name_url_pairs:
        url = url.rstrip(")】〕,，。.;;")
        blog_name_map[url] = name
    # Also try simple "name：url" patterns anywhere in text
    if not blog_name_map:
        simple_pairs = re.findall(
            r"([一-鿿]{2,6})[：:]\s*({http_url})".replace("{http_url}", URL_RE.pattern),
            text,
        )
        for name, url in simple_pairs:
            url = url.rstrip(")】〕,，。.;;")
            blog_name_map[url] = name
    member_blog_section = text
    if "成员个人博客地址" in text:
        member_blog_section = text.split("成员个人博客地址", 1)[1]
        for end_marker in ("项目介绍", "实施计划", "预期成果"):
            if end_marker in member_blog_section:
                member_blog_section = member_blog_section.split(end_marker, 1)[0]
                break
    section_urls = list(dict.fromkeys(URL_RE.findall(member_blog_section)))
    blog_urls = [url for url in section_urls if "gitee.com" not in urlparse(url).netloc.lower()]
    if not blog_urls:
        blog_urls = [url for url in urls if "gitee.com" not in urlparse(url).netloc.lower()]
    for index, url in enumerate(blog_urls):
        if index < len(members):
            members[index]["blog_url"] = url
            # Fill in name from blog_name_map if name is missing
            if not members[index].get("name") and url in blog_name_map:
                members[index]["name"] = blog_name_map[url]

    if not leader_name and members:
        leader_name = members[0]["name"]
    for member in members:
        if member["name"] and member["name"] == leader_name:
            member["role"] = "组长"

    return {
        "document_type": doc_type,
        "project_name": project_name or Path(file_name).stem,
        "team_name": team_name,
        "leader_name": leader_name,
        "leader_student_id": next(
            (item["student_id"] for item in members if item["name"] == leader_name),
            members[0]["student_id"] if members else "",
        ),
        "members": members,
        "gitee_url": gitee_url,
    }


def _model_parse(text: str, file_name: str, fallback: dict) -> dict:
    settings = get_settings()
    if not settings.model_base_url or not settings.model_api_key:
        return fallback
    prompt = (
        "从创新实训申请书或任务书中提取项目组信息。没有项目组博客；URL若为gitee.com则是组级仓库，"
        "其他博客URL按文档顺序对应成员。只输出JSON："
        "{\"document_type\":\"application|task\",\"project_name\":\"\",\"team_name\":\"\","
        "\"leader_name\":\"\",\"leader_student_id\":\"\",\"gitee_url\":\"\","
        "\"members\":[{\"name\":\"\",\"student_id\":\"\",\"blog_url\":\"\",\"role\":\"\"}]}。\n"
        f"文件名：{file_name}\n正文：{text[:24000]}"
    )
    try:
        response = httpx.post(
            settings.model_base_url.rstrip("/") + "/chat/completions",
            headers={"Authorization": f"Bearer {settings.model_api_key}", "Content-Type": "application/json"},
            json={
                "model": settings.model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.0,
                "response_format": {"type": "json_object"},
            },
            timeout=60.0,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"].strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.I)
        parsed = json.loads(content)
        if not isinstance(parsed.get("members"), list):
            return fallback
        return parsed
    except Exception:
        return fallback


def parse_import_file(file_path: str, file_name: str) -> tuple[dict, str | None]:
    text, error = extract_text(file_path)
    if error or not text.strip():
        return {}, error or "document text is empty"
    fallback = _fallback_parse(text, file_name)

    def _is_bad_project_name(val: str) -> bool:
        """Check if the value looks like a label/header rather than a real project name."""
        if not val or val == Path(file_name).stem:
            return True
        # Contaminated by adjacent labels
        bad_words = ("负责人", "手机号码", "指导教师", "团队名称", "项目名称", "项目编号")
        for bw in bad_words:
            if bw in val:
                return True
        return False

    # If pdf2docx missed key fields or got bad values, also try pdfplumber and merge
    if not fallback.get("leader_name") or _is_bad_project_name(fallback.get("project_name", "")):
        try:
            from app.services.text_extractor import _extract_pdf_text_pdfplumber
            text2, _ = _extract_pdf_text_pdfplumber(file_path)
            if text2.strip():
                fallback2 = _fallback_parse(text2, file_name)
                for field in ("project_name", "team_name", "leader_name", "leader_student_id", "gitee_url"):
                    if not fallback.get(field) or _is_bad_project_name(fallback.get(field, "")):
                        fallback[field] = fallback2.get(field, "")
                # Merge members: prefer ones with names
                fb_members = {m["student_id"]: m for m in fallback.get("members", [])}
                for m2 in fallback2.get("members", []):
                    if m2["student_id"] not in fb_members:
                        fb_members[m2["student_id"]] = m2
                    elif m2.get("name") and not fb_members[m2["student_id"]].get("name"):
                        fb_members[m2["student_id"]] = m2
                fallback["members"] = list(fb_members.values())
        except Exception:
            pass

    parsed = _model_parse(text, file_name, fallback)
    members = []
    for raw in parsed.get("members") or []:
        sid = _clean(raw.get("student_id"))
        if not STUDENT_ID_RE.fullmatch(sid):
            continue
        members.append(
            {
                "student_id": sid,
                "name": _clean(raw.get("name")),
                "blog_url": _clean(raw.get("blog_url")),
                "role": _clean(raw.get("role")),
            }
        )
    parsed["members"] = list({item["student_id"]: item for item in members}.values())
    parsed["project_name"] = _clean(parsed.get("project_name")) or Path(file_name).stem
    parsed["team_name"] = _clean(parsed.get("team_name"))
    parsed["leader_name"] = _clean(parsed.get("leader_name"))
    parsed["leader_student_id"] = _clean(parsed.get("leader_student_id"))
    parsed["gitee_url"] = _clean(parsed.get("gitee_url"))
    parsed["document_type"] = "task" if str(parsed.get("document_type")) == "task" else "application"
    parsed["group_key"] = _group_key(parsed["project_name"], [item["student_id"] for item in parsed["members"]])
    return parsed, None


def merge_batch_groups(files: list[DocumentImportFile]) -> list[dict]:
    groups: dict[str, dict] = {}
    for row in files:
        if row.parse_status != "parsed":
            continue
        payload = json.loads(row.parsed_json or "{}")
        project_key = _normalize_project(payload.get("project_name") or "")
        key = project_key or row.group_key
        group = groups.setdefault(
            key,
            {
                "group_key": row.group_key,
                "project_name": payload.get("project_name") or "",
                "team_name": payload.get("team_name") or "",
                "leader_name": "",
                "leader_student_id": "",
                "gitee_url": "",
                "members": [],
                "application_file_ids": [],
                "task_file_ids": [],
                "warnings": [],
            },
        )
        if payload.get("document_type") == "task":
            group["task_file_ids"].append(row.id)
        else:
            group["application_file_ids"].append(row.id)
        for field in ("team_name", "leader_name", "leader_student_id", "gitee_url"):
            if payload.get(field) and not group.get(field):
                group[field] = payload[field]
        member_map = {item["student_id"]: item for item in group["members"]}
        for member in payload.get("members") or []:
            existing = member_map.get(member["student_id"])
            if existing:
                for field in ("name", "blog_url", "role"):
                    if member.get(field) and not existing.get(field):
                        existing[field] = member[field]
            else:
                group["members"].append(dict(member))
                member_map[member["student_id"]] = group["members"][-1]
        group["group_key"] = _group_key(group["project_name"], [item["student_id"] for item in group["members"]])
    for group in groups.values():
        if not group["application_file_ids"]:
            group["warnings"].append("missing_application_document")
        elif len(group["application_file_ids"]) > 1:
            group["warnings"].append("duplicate_application_documents")
        if not group["task_file_ids"]:
            group["warnings"].append("missing_task_document")
        elif len(group["task_file_ids"]) > 1:
            group["warnings"].append("duplicate_task_documents")
        if not group["members"]:
            group["warnings"].append("no_members_parsed")
        if not group["leader_student_id"]:
            group["warnings"].append("leader_not_identified")
        if any(not item.get("blog_url") for item in group["members"]):
            group["warnings"].append("member_blog_url_missing")
    return list(groups.values())


def _initial_password() -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(14))


def commit_import_batch(db: Session, batch: DocumentImportBatch, groups_override: list[dict] | None = None) -> dict:
    groups = groups_override or merge_batch_groups(list(batch.files))
    for group in groups:
        group["group_key"] = _group_key(
            group.get("project_name") or "",
            [item.get("student_id") or "" for item in group.get("members") or []],
        )
    credentials = []
    created_groups = 0
    updated_groups = 0
    skipped_duplicates = 0
    next_number = int(db.query(func.max(UserGroup.group_number)).scalar() or 0) + 1
    for parsed in groups:
        if not parsed["members"]:
            continue
        group = db.query(UserGroup).filter(UserGroup.import_key == parsed["group_key"]).first()
        if group is None and parsed.get("project_name"):
            candidates = db.query(UserGroup).filter(UserGroup.description == parsed["project_name"]).all()
            if len(candidates) == 1:
                group = candidates[0]
        if group is None:
            member_group_ids = {
                user.group_id
                for user in db.query(User).filter(
                    User.student_id.in_([item["student_id"] for item in parsed["members"]])
                ).all()
                if user.group_id
            }
            if len(member_group_ids) == 1:
                group = db.query(UserGroup).filter(UserGroup.id == next(iter(member_group_ids))).first()
        if group:
            skipped_duplicates += 1
            updated_groups += 1
            if not group.import_key:
                group.import_key = parsed["group_key"]
        else:
            desired_name = parsed["team_name"] or f"第{next_number}组"
            if db.query(UserGroup).filter(UserGroup.name == desired_name).first():
                desired_name = f"{desired_name}-{next_number}"
            group = UserGroup(
                group_number=next_number,
                name=desired_name,
                code=f"G{next_number:03d}",
                description=parsed["project_name"],
                repo_url=parsed["gitee_url"] or None,
                import_key=parsed["group_key"],
            )
            db.add(group)
            db.flush()
            next_number += 1
            created_groups += 1
        if parsed.get("gitee_url"):
            group.repo_url = parsed["gitee_url"]
        users_by_sid = {}
        for member in parsed["members"]:
            user = db.query(User).filter(User.student_id == member["student_id"]).first()
            if user is None:
                password = _initial_password()
                user = create_user_basic(db, member["student_id"], member["name"] or member["student_id"], password)
                credentials.append(
                    {"student_id": user.student_id, "real_name": user.real_name, "initial_password": password}
                )
            elif member.get("name") and not user.real_name:
                user.real_name = member["name"]
            user.group_id = group.id
            if member.get("blog_url"):
                user.blog_home_url = member["blog_url"]
                source = (
                    db.query(BlogSource)
                    .filter(BlogSource.user_id == user.id, BlogSource.source_url == member["blog_url"])
                    .first()
                )
                if source is None:
                    db.add(
                        BlogSource(
                            user_id=user.id,
                            source_url=member["blog_url"],
                            source_type="personal",
                            site_name="Imported Personal Blog",
                            is_active=True,
                        )
                    )
            users_by_sid[user.student_id] = user
        leader = users_by_sid.get(parsed.get("leader_student_id"))
        if leader is None and parsed.get("leader_name"):
            leader = next((user for user in users_by_sid.values() if user.real_name == parsed["leader_name"]), None)
        if leader is None and users_by_sid:
            leader = next(iter(users_by_sid.values()))
        group.leader_user_id = leader.id if leader else None
        for file_id in parsed["application_file_ids"]:
            row = db.query(DocumentImportFile).filter(DocumentImportFile.id == file_id).first()
            if row:
                row.group_key = parsed["group_key"]
                row.group_id = group.id
        for file_id in parsed["task_file_ids"]:
            row = db.query(DocumentImportFile).filter(DocumentImportFile.id == file_id).first()
            if row:
                row.group_key = parsed["group_key"]
                row.group_id = group.id
        db.commit()
    batch.status = "committed"
    batch.group_count = len(groups)
    batch.committed_group_count = created_groups + updated_groups
    batch.committed_at = datetime.utcnow()
    db.commit()
    return {
        "batch_id": batch.id,
        "created_group_count": created_groups,
        "updated_group_count": updated_groups,
        "duplicate_group_count": skipped_duplicates,
        "credentials": credentials,
    }
