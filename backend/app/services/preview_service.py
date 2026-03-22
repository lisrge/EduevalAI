from __future__ import annotations

import subprocess
from dataclasses import dataclass
from html import escape
from pathlib import Path

from docx import Document

from app.core.config import get_settings
from app.services.file_service import ensure_storage_dirs


class PreviewError(Exception):
    pass


@dataclass
class PreviewResult:
    path: str
    media_type: str


def _docx_to_html(input_path: Path, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / f"{input_path.stem}.html"
    if out.exists() and out.stat().st_mtime >= input_path.stat().st_mtime:
        return out

    doc = Document(str(input_path))
    lines: list[str] = []
    for p in doc.paragraphs:
        text = (p.text or "").strip()
        if text:
            lines.append(text)

    body = "\n\n".join(lines)
    html = (
        "<!doctype html><html><head><meta charset='utf-8'/>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'/>"
        "<title>Application Preview</title>"
        "<style>"
        "body{font-family:Segoe UI,PingFang SC,sans-serif;margin:0;padding:20px;line-height:1.6;color:#1b2430;}"
        "pre{white-space:pre-wrap;word-break:break-word;font-family:inherit;margin:0;}"
        "</style></head><body>"
        f"<pre>{escape(body)}</pre>"
        "</body></html>"
    )
    out.write_text(html, encoding="utf-8")
    return out


def _run_soffice_convert(input_path: Path, output_dir: Path) -> Path:
    settings = get_settings()
    cmd = [
        settings.preview_converter_path,
        "--headless",
        "--convert-to",
        "pdf",
        "--outdir",
        str(output_dir),
        str(input_path),
    ]
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise PreviewError("preview converter not found") from exc
    except OSError as exc:
        raise PreviewError("preview converter failed to start") from exc
    if completed.returncode != 0:
        raise PreviewError(completed.stderr.strip() or completed.stdout.strip() or "convert failed")

    out = output_dir / f"{input_path.stem}.pdf"
    if not out.exists():
        candidates = list(output_dir.glob(f"{input_path.stem}*.pdf"))
        if candidates:
            return candidates[0]
        raise PreviewError("preview file not found after conversion")
    return out


def get_preview_file(file_path: str) -> PreviewResult:
    ensure_storage_dirs()
    settings = get_settings()

    src = Path(file_path)
    if not src.exists():
        raise PreviewError("source file not found")

    suffix = src.suffix.lower().lstrip(".")
    if suffix == "pdf":
        return PreviewResult(path=str(src), media_type="application/pdf")

    if suffix == "docx":
        out_dir = settings.preview_storage_path
        html_path = _docx_to_html(src, out_dir)
        return PreviewResult(path=str(html_path), media_type="text/html; charset=utf-8")

    raise PreviewError("unsupported preview type")
