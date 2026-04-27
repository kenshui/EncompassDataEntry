from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from .config import AgentConfig
from .encompass import EncompassClient
from .extraction import DocumentExtractor, build_extractor
from .models import AgentRunSummary
from .pdf import extract_pdf_text
from .storage import DocumentStore

LOGGER = logging.getLogger(__name__)


class EncompassAIAgent:
    """Coordinates the daily Encompass document extraction workflow."""

    def __init__(
        self,
        config: AgentConfig,
        client: EncompassClient | None = None,
        store: DocumentStore | None = None,
        extractor: DocumentExtractor | None = None,
    ) -> None:
        self.config = config
        self.client = client or EncompassClient(config)
        self.store = store or DocumentStore(config.storage.database_path, config.storage.log_path)
        self.extractor = extractor or build_extractor(config)

    def run(self, since: datetime | None = None, dry_run: bool | None = None) -> AgentRunSummary:
        if since is None:
            since = datetime.now(timezone.utc) - timedelta(days=self.config.lookback_days)
        if dry_run is None:
            dry_run = self.config.dry_run

        LOGGER.info("Starting Encompass AI agent run for loans modified since %s", since.isoformat())
        loans = self.client.get_recent_loans(since, datetime.now(timezone.utc))
        summary = AgentRunSummary(loans_scanned=len(loans))

        for loan in loans:
            loan_id = loan.loan_id
            LOGGER.info("Scanning loan %s", loan_id)
            for attachment in self.client.get_attachments(loan_id):
                summary.attachments_seen += 1
                self.store.upsert_attachment(attachment)

                if self.store.is_processed(loan_id, attachment.attachment_id):
                    LOGGER.info("Skipping already processed attachment %s for loan %s", attachment.attachment_id, loan_id)
                    summary.attachments_skipped += 1
                    continue

                try:
                    self._process_attachment(loan_id, attachment.attachment_id, dry_run=dry_run)
                    summary.attachments_processed += 1
                    summary.field_updates_succeeded += 1
                except Exception as exc:  # noqa: BLE001 - per-document failures must not stop the daily batch.
                    LOGGER.exception(
                        "Failed to process attachment %s for loan %s",
                        attachment.attachment_id,
                        loan_id,
                    )
                    summary.field_updates_failed += 1
                    self.store.mark_failed(loan_id, attachment.attachment_id, str(exc))

        LOGGER.info("Agent run complete: %s", summary)
        return summary

    def _process_attachment(self, loan_id: str, attachment_id: str, dry_run: bool = False) -> None:
        pdf_path = self.config.storage.download_dir / _safe_path_part(loan_id) / f"{_safe_path_part(attachment_id)}.pdf"
        self.client.download_attachment_pdf(loan_id, attachment_id, pdf_path)
        pdf_bytes = pdf_path.read_bytes()
        text = extract_pdf_text(pdf_bytes)
        fields = self.extractor.extract(text)
        field_payload = {
            encompass_field_id: value
            for key, value in fields.items()
            if value not in (None, "")
            for encompass_field_id in [self.config.field_mapping.get(key)]
            if encompass_field_id
        }

        if not field_payload:
            raise ValueError("No mapped fields were extracted from the document")

        LOGGER.info("Extracted %d mapped fields from attachment %s", len(field_payload), attachment_id)
        if not dry_run:
            self.client.update_loan_fields(loan_id, field_payload)

        self.store.mark_processed(
            loan_id=loan_id,
            attachment_id=attachment_id,
            extracted_fields=fields,
            mapped_fields=field_payload,
            dry_run=dry_run,
        )


def _safe_path_part(value: str) -> str:
    return "".join(char if char.isalnum() or char in ("-", "_", ".") else "_" for char in value)
