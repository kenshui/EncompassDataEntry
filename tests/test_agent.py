from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from encompass_ai_agent.agent import EncompassAIAgent
from encompass_ai_agent.config import AgentConfig, AuthConfig, StorageConfig
from encompass_ai_agent.models import AttachmentMetadata, LoanSummary
from encompass_ai_agent.storage import DocumentStore


class FakeClient:
    def __init__(self, pdf_bytes: bytes) -> None:
        self.pdf_bytes = pdf_bytes
        self.updated_fields: list[tuple[str, dict[str, str]]] = []

    def get_recent_loans(self, start_date, end_date):
        return [LoanSummary("loan-1")]

    def get_attachments(self, loan_id: str):
        return [
            AttachmentMetadata(
                loan_id=loan_id,
                attachment_id="attachment-1",
                title="Closing Disclosure",
                created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
                created_by="Jane",
            )
        ]

    def download_attachment_pdf(self, loan_id: str, attachment_id: str, destination: Path):
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(self.pdf_bytes)
        return destination

    def update_loan_fields(self, loan_id: str, field_values: dict[str, str]):
        self.updated_fields.append((loan_id, field_values))
        return {"ok": True}


class FakeExtractor:
    def extract(self, text: str):
        return {"loan_amount": "250000", "processing_fee": None}


def test_agent_processes_new_attachment_once(tmp_path, monkeypatch):
    config = AgentConfig(
        auth=AuthConfig(
            instance="inst",
            smart_client_user="user",
            smart_client_password="pass",
            client_id="id",
            client_secret="secret",
            api_server="https://example.test",
        ),
        storage=StorageConfig(
            database_path=tmp_path / "agent.sqlite3",
            download_dir=tmp_path / "downloads",
            log_path=tmp_path / "events.jsonl",
        ),
        field_mapping={"loan_amount": "1109"},
    )
    client = FakeClient(b"%PDF-placeholder")
    store = DocumentStore(config.storage.database_path, config.storage.log_path)
    agent = EncompassAIAgent(config, client=client, store=store, extractor=FakeExtractor())
    monkeypatch.setattr("encompass_ai_agent.agent.extract_pdf_text", lambda _: "Loan Amount 250000")

    first_summary = agent.run()
    second_summary = agent.run()

    assert first_summary.attachments_processed == 1
    assert second_summary.attachments_skipped == 1
    assert client.updated_fields == [("loan-1", {"1109": "250000"})]
