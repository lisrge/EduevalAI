from __future__ import annotations

import base64
import subprocess
from dataclasses import dataclass
from html import escape
from pathlib import Path

from docx import Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.core.config import get_settings
from app.services.file_service import ensure_storage_dirs


class PreviewError(Exception):
    pass


@dataclass
class PreviewResult:
    path: str
    media_type: str


def _iter_block_items(document: Document):
    parent = document.element.body
    for child in parent.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, document)
        elif isinstance(child, CT_Tbl):
            yield Table(child, document)


def _node_images_html(node, doc: Document) -> str:
    try:
        part = doc.part
    except Exception:
        return ""

    try:
        r_ids = node.xpath(".//a:blip/@r:embed")
    except Exception:
        return ""

    imgs: list[str] = []
    for rid in r_ids:
        rel = getattr(part, "related_parts", {}).get(rid)
        if not rel:
            continue
        blob = getattr(rel, "blob", None)
        if not blob:
            continue
        content_type = getattr(rel, "content_type", None) or "image/png"
        b64 = base64.b64encode(blob).decode("ascii")
        imgs.append(
            "<img "
            f"src='data:{content_type};base64,{b64}' "
            "style='max-width:220px;max-height:120px;display:block;margin-top:6px;"
            "border:1px solid rgba(180,200,230,0.8);border-radius:10px;background:#ffffff;'"
            "/>"
        )
    return "".join(imgs)


def _docx_to_html(input_path: Path, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / f"{input_path.stem}.html"
    if out.exists() and out.stat().st_mtime >= input_path.stat().st_mtime:
        return out

    doc = Document(str(input_path))
    parts: list[str] = []
    for block in _iter_block_items(doc):
        if isinstance(block, Paragraph):
            text = (block.text or "").strip()
            imgs = _node_images_html(block._p, doc)
            if text or imgs:
                parts.append(f"<p>{escape(text)}{imgs}</p>" if text else f"<p>{imgs}</p>")
            continue
        if isinstance(block, Table):
            rows: list[str] = []
            for row in block.rows:
                cells: list[str] = []
                for cell in row.cells:
                    text = escape((cell.text or "").strip()).replace("\n", "<br/>")
                    imgs = _node_images_html(cell._tc, doc)
                    if text and imgs:
                        cells.append(f"<td><div>{text}</div>{imgs}</td>")
                    elif imgs:
                        cells.append(f"<td>{imgs}</td>")
                    else:
                        cells.append(f"<td>{text}</td>")
                rows.append("<tr>" + "".join(cells) + "</tr>")
            parts.append("<table>" + "".join(rows) + "</table>")

    body = "\n".join(parts) if parts else "<p>(空文档)</p>"
    html = (
        "<!doctype html><html><head><meta charset='utf-8'/>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'/>"
        "<title>Application Preview</title>"
        "<style>"
        "body{font-family:Segoe UI,PingFang SC,sans-serif;margin:0;padding:20px;line-height:1.65;color:#1b2430;background:#ffffff;}"
        "body[data-theme='dark']{color:#e5e7eb;background:#0b1220;}"
        "p{margin:0 0 10px 0;}"
        "table{width:100%;border-collapse:collapse;margin:12px 0;}"
        "td{border:1px solid rgba(180,200,230,0.8);padding:8px;vertical-align:top;}"
        "body[data-theme='dark'] td{border-color:rgba(60,80,110,0.9);}"
        "body[data-theme='dark'] img{background:#111b2d;border-color:rgba(60,80,110,0.9);}"
        "</style></head><body>"
        "<script>(function(){try{var t=new URLSearchParams(location.search).get('theme');if(t){document.body.setAttribute('data-theme',t);}}catch(e){}})();</script>"
        f"{body}"
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

    if suffix in {"doc", "xls", "xlsx", "ppt", "pptx", "pps", "ppsx"}:
        out_dir = settings.preview_storage_path
        pdf_path = _run_soffice_convert(src, out_dir)
        return PreviewResult(path=str(pdf_path), media_type="application/pdf")

    raise PreviewError("unsupported preview type")
