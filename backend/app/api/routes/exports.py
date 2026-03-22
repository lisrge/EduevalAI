from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.models.application import ApplicationRecord
from app.services.export_service import build_csv_bytes, build_xlsx_bytes

router = APIRouter(prefix="/exports", tags=["exports"])


@router.get("/scores")
def export_scores(format: str = Query("csv", pattern="^(csv|xlsx)$"), db: Session = Depends(get_db)):
    records = db.query(ApplicationRecord).order_by(ApplicationRecord.id.asc()).all()
    rows: list[dict] = []
    for record in records:
        score = record.score_result
        rows.append(
            {
                "id": record.id,
                "student_name": record.student_name,
                "student_id": record.student_id,
                "project_title": record.project_title,
                "practicality_score": score.practicality_score if score else 0,
                "innovation_score": score.innovation_score if score else 0,
                "total_score": score.total_score if score else 0,
                "needs_human_review": score.needs_human_review if score else True,
            }
        )

    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    if format == "csv":
        content = build_csv_bytes(rows)
        return Response(
            content=content,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="scores_{stamp}.csv"'},
        )
    if format == "xlsx":
        content = build_xlsx_bytes(rows)
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="scores_{stamp}.xlsx"'},
        )

    raise HTTPException(status_code=400, detail="unsupported format")

