from __future__ import annotations

import json
from pathlib import Path
import zipfile

TEXT_EXTENSIONS = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".vue": "Vue",
    ".java": "Java",
    ".go": "Go",
    ".cpp": "C++",
    ".c": "C",
    ".cs": "C#",
    ".php": "PHP",
    ".rb": "Ruby",
    ".rs": "Rust",
    ".kt": "Kotlin",
    ".swift": "Swift",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".md": "Markdown",
    ".sql": "SQL",
    ".xml": "XML",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".sh": "Shell",
}

IGNORED_SEGMENTS = {
    "node_modules",
    ".git",
    "dist",
    "build",
    "target",
    "__pycache__",
    ".idea",
    ".vscode",
}


def _is_ignored(name: str) -> bool:
    parts = [part for part in name.replace("\\", "/").split("/") if part]
    return any(part in IGNORED_SEGMENTS for part in parts)


def _safe_decode(data: bytes) -> str | None:
    for encoding in ("utf-8", "utf-8-sig", "gbk", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


def analyze_code_archive(file_path: str) -> dict:
    path = Path(file_path)
    suffix = path.suffix.lower()
    result = {
        "archive_format": suffix.lstrip(".") or "unknown",
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

    if suffix != ".zip":
        result["risk_level"] = "medium"
        result["risk_flags"] = ["archive_format_not_supported_for_scan"]
        return result

    ext_counter: dict[str, int] = {}
    lang_counter: dict[str, int] = {}
    try:
        with zipfile.ZipFile(path, "r") as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                if _is_ignored(info.filename):
                    continue
                result["total_files"] += 1
                result["total_bytes"] += int(info.file_size or 0)
                ext = Path(info.filename).suffix.lower()
                if ext:
                    ext_counter[ext] = ext_counter.get(ext, 0) + 1
                if ext not in TEXT_EXTENSIONS:
                    continue

                with zf.open(info, "r") as f:
                    raw = f.read()
                text = _safe_decode(raw)
                if text is None:
                    continue
                line_count = len(text.splitlines())
                result["source_file_count"] += 1
                result["total_lines"] += line_count
                lang = TEXT_EXTENSIONS[ext]
                lang_counter[lang] = lang_counter.get(lang, 0) + line_count
    except zipfile.BadZipFile:
        result["risk_level"] = "high"
        result["risk_flags"] = ["invalid_zip_archive"]
        return result

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
        risk_flags.append("empty_archive")
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
    if any(item["extension"] in {".min.js", ".map"} for item in result["top_extensions"]):
        risk_flags.append("bundled_assets_present")
        risk_level = "medium" if risk_level == "low" else risk_level

    result["risk_flags"] = risk_flags
    result["risk_level"] = risk_level
    return result


def dumps_summary(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False)


def loads_summary(data: str | None) -> dict:
    if not data:
        return {}
    try:
        payload = json.loads(data)
        return payload if isinstance(payload, dict) else {}
    except json.JSONDecodeError:
        return {}
