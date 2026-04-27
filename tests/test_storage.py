from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from encompass_ai_agent.models import AttachmentMetadata
from encompass_ai_agent.storage import DocumentStore


def test_store_tracks_processed_documents_and_events(tmp_path):
    log_path = tmp_path / "events.jsonl"
    store = DocumentStore(tmp_path / "agent.sqlite3", event_log_path=log_path)
    attachment = AttachmentMetadata(
        loan_id="loan-1",
        attachment_id="att-1",
        title="Closing Disclosure",
        created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        created_by="processor@example.com",
    )

    store.upsert_attachment(attachment)
    assert not store.is_processed("loan-1", "att-1")

    store.mark_processed(
        "loan-1",
        "att-1",
        extracted_fields={"loan_amount": "250000"},
        mapped_fields={"1109": "250000"},
        dry_run=False,
    )

    assert store.is_processed("loan-1", "att-1")
    with sqlite3.connect(tmp_path / "agent.sqlite3") as conn:
        event_count = conn.execute("SELECT COUNT(*) FROM processing_events").fetchone()[0]
    assert event_count == 1

    logged_event = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert logged_event["status"] == "processed"
    assert logged_event["loan_id"] == "loan-1"


def test_failed_document_remains_unprocessed(tmp_path):
    store = DocumentStore(tmp_path / "agent.sqlite3")
    store.upsert_attachment(
        AttachmentMetadata(
            loan_id="loan-1",
            attachment_id="att-1",
            title="Closing Disclosure",
            created_at=None,
            created_by=None,
        )
    )

    store.mark_failed("loan-1", "att-1", "bad pdf")

    assert not store.is_processed("loan-1", "att-1")
