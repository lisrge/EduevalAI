from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.base import SessionLocal
from app.models.document_import import DocumentImportBatch
from app.models.user import User
from app.services.document_import_service import build_import_initial_password, reset_import_batch_user_passwords


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset imported users' passwords for a document import batch.")
    parser.add_argument("--batch-id", type=int, required=True, help="Document import batch id")
    parser.add_argument(
        "--out",
        type=str,
        default="",
        help="Optional CSV output path for exported credentials",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview affected users and passwords without updating the database",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        batch = (
            db.query(DocumentImportBatch)
            .filter(DocumentImportBatch.id == args.batch_id)
            .first()
        )
        if batch is None:
            print(f"batch not found: {args.batch_id}")
            return 1
        if args.dry_run:
            credentials = []
            seen: set[str] = set()
            for row in batch.files:
                payload = json.loads(row.parsed_json or "{}")
                for member in payload.get("members") or []:
                    sid = str((member or {}).get("student_id") or "").strip()
                    if not sid or sid in seen:
                        continue
                    seen.add(sid)
                    user = db.query(User).filter_by(student_id=sid).first()
                    if user is None:
                        continue
                    credentials.append(
                        {
                            "real_name": user.real_name,
                            "student_id": user.student_id,
                            "initial_password": build_import_initial_password(user.student_id),
                        }
                    )
        else:
            credentials = reset_import_batch_user_passwords(db, batch)
    finally:
        db.close()

    print(f'{"preview users" if args.dry_run else "reset users"}: {len(credentials)}')
    if not credentials:
        return 0

    if args.out:
        output_path = Path(args.out)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8-sig", newline="") as fp:
            writer = csv.writer(fp)
            writer.writerow(["real_name", "student_id", "initial_password"])
            for item in credentials:
                writer.writerow([item["real_name"], item["student_id"], item["initial_password"]])
        print(f"credentials exported: {output_path}")
    else:
        for item in credentials:
            print(f'{item["real_name"]},{item["student_id"]},{item["initial_password"]}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
