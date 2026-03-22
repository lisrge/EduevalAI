from __future__ import annotations

import csv
import io
from typing import Iterable

from openpyxl import Workbook


def build_csv_bytes(rows: Iterable[dict]) -> bytes:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "student_name", "student_id", "project_title", "practicality", "innovation", "total", "needs_review"])
    for row in rows:
        writer.writerow(
            [
                row.get("id"),
                row.get("student_name"),
                row.get("student_id"),
                row.get("project_title"),
                row.get("practicality_score"),
                row.get("innovation_score"),
                row.get("total_score"),
                1 if row.get("needs_human_review") else 0,
            ]
        )
    return output.getvalue().encode("utf-8-sig")


def build_xlsx_bytes(rows: Iterable[dict]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "scores"
    ws.append(["id", "student_name", "student_id", "project_title", "practicality", "innovation", "total", "needs_review"])
    for row in rows:
        ws.append(
            [
                row.get("id"),
                row.get("student_name"),
                row.get("student_id"),
                row.get("project_title"),
                row.get("practicality_score"),
                row.get("innovation_score"),
                row.get("total_score"),
                1 if row.get("needs_human_review") else 0,
            ]
        )
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()

