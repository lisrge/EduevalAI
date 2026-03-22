from __future__ import annotations

from pathlib import Path

from docx import Document
from pypdf import PdfReader


def extract_text(file_path: str) -> tuple[str, str | None]:
    path = Path(file_path)
    suffix = path.suffix.lower().lstrip(".")

    try:
        if suffix in {"txt", "md", "log", "csv"}:
            return path.read_text(encoding="utf-8", errors="ignore"), None

        if suffix == "pdf":
            reader = PdfReader(str(path))
            chunks: list[str] = []
            for page in reader.pages:
                chunks.append(page.extract_text() or "")
            text = "\n".join(chunks).strip()
            return text, None

        if suffix == "docx":
            doc = Document(str(path))
            chunks = [p.text for p in doc.paragraphs if p.text]
            text = "\n".join(chunks).strip()
            return text, None

        return "", "unsupported file type"
    except Exception as exc:
        return "", str(exc)

