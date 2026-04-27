from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import AttachmentMetadata


SCHEMA = """
CREATE TABLE IF NOT EXISTS loan_attachments (
    loan_id TEXT NOT NULL,
    attachment_id TEXT NOT NULL,
    title TEXT NOT NULL,
    created_date TEXT,
    created_by TEXT,
    processed INTEGER NOT NULL DEFAULT 0,
    processed_at TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (loan_id, attachment_id)
);

CREATE INDEX IF NOT EXISTS idx_loan_attachments_processed
ON loan_attachments(processed);

CREATE TABLE IF NOT EXISTS processing_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    loan_id TEXT,
    attachment_id TEXT,
    status TEXT NOT NULL,
    message TEXT NOT NULL,
    fields_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


class DocumentStore:
    def __init__(self, database_path: Path, event_log_path: Path | None = None) -> None:
        self.database_path = database_path
        self.event_log_path = event_log_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        if self.event_log_path:
            self.event_log_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    def upsert_attachment(self, record: AttachmentMetadata) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO loan_attachments (
                    loan_id, attachment_id, title, created_date, created_by
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(loan_id, attachment_id) DO UPDATE SET
                    title = excluded.title,
                    created_date = excluded.created_date,
                    created_by = excluded.created_by,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    record.loan_id,
                    record.attachment_id,
                    record.title,
                    record.created_at.isoformat() if record.created_at else None,
                    record.created_by,
                ),
            )

    def is_processed(self, loan_id: str, attachment_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT processed FROM loan_attachments
                WHERE loan_id = ? AND attachment_id = ?
                """,
                (loan_id, attachment_id),
            ).fetchone()
        return bool(row and row["processed"])

    def mark_processed(
        self,
        loan_id: str,
        attachment_id: str,
        extracted_fields: dict[str, str | None],
        mapped_fields: dict[str, str],
        dry_run: bool,
    ) -> None:
        field_payload = {
            "extracted_fields": extracted_fields,
            "mapped_fields": mapped_fields,
            "dry_run": dry_run,
        }
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE loan_attachments
                SET processed = 1,
                    processed_at = CURRENT_TIMESTAMP,
                    last_error = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE loan_id = ? AND attachment_id = ?
                """,
                (loan_id, attachment_id),
            )
            conn.execute(
                """
                INSERT INTO processing_events (
                    loan_id, attachment_id, status, message, fields_json
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    loan_id,
                    attachment_id,
                    "processed",
                    "Attachment processed." if dry_run else "Attachment processed and loan fields updated.",
                    json.dumps(field_payload, sort_keys=True),
                ),
            )
        self._append_jsonl_event(
            loan_id=loan_id,
            attachment_id=attachment_id,
            status="processed",
            message="Attachment processed." if dry_run else "Attachment processed and loan fields updated.",
            fields=field_payload,
        )

    def mark_failed(self, loan_id: str, attachment_id: str, error: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE loan_attachments
                SET last_error = ?, updated_at = CURRENT_TIMESTAMP
                WHERE loan_id = ? AND attachment_id = ?
                """,
                (error, loan_id, attachment_id),
            )
            conn.execute(
                """
                INSERT INTO processing_events (
                    loan_id, attachment_id, status, message, fields_json
                )
                VALUES (?, ?, ?, ?, NULL)
                """,
                (loan_id, attachment_id, "failed", error),
            )
        self._append_jsonl_event(
            loan_id=loan_id,
            attachment_id=attachment_id,
            status="failed",
            message=error,
            fields=None,
        )

    def _append_jsonl_event(
        self,
        *,
        loan_id: str,
        attachment_id: str,
        status: str,
        message: str,
        fields: dict[str, object] | None,
    ) -> None:
        if not self.event_log_path:
            return
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "loan_id": loan_id,
            "attachment_id": attachment_id,
            "status": status,
            "message": message,
            "fields": fields,
        }
        with self.event_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True, default=str) + "\n")

