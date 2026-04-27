from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import AgentConfig
from .models import AttachmentMetadata, LoanSummary

LOGGER = logging.getLogger(__name__)


class EncompassApiError(RuntimeError):
    """Raised when the Encompass API returns an unexpected response."""


class EncompassClient:
    """Small stdlib HTTP client for the Encompass workflow.

    Endpoint paths are configurable so the agent can be deployed into customers'
    private networks without hard-coding tenant-specific routing details.
    """

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self._token: str | None = None
        self._token_expires_at: datetime | None = None

    def get_token(self, *, force_refresh: bool = False) -> str:
        if not force_refresh and self._token:
            return self._token

        body = urllib.parse.urlencode(
            {
                "grant_type": "password",
                "instance": self.config.auth.instance,
                "username": self.config.auth.smart_client_user,
                "password": self.config.auth.smart_client_password,
                "client_id": self.config.auth.client_id,
                "client_secret": self.config.auth.client_secret,
            }
        ).encode("utf-8")
        response = self._request(
            self.config.auth.token_url,
            method="POST",
            body=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            authenticated=False,
        )
        token = response.get("access_token")
        if not token:
            raise EncompassApiError("Token response did not include access_token")
        self._token = str(token)
        return self._token

    def get_recent_loans(self, start_date: datetime, end_date: datetime) -> list[LoanSummary]:
        records: list[dict[str, Any]] = []
        offset = 0
        while True:
            query = urllib.parse.urlencode(
                {
                    self.config.endpoints.modified_after_query_param: _format_timestamp(start_date),
                    self.config.endpoints.created_after_query_param: _format_timestamp(start_date),
                    self.config.endpoints.page_limit_query_param: self.config.endpoints.page_size,
                    self.config.endpoints.page_offset_query_param: offset,
                }
            )
            payload = self._request_json_path(f"{self.config.endpoints.loans_path}?{query}")
            page_records = _as_list(payload, "loans")
            records.extend(page_records)
            if len(page_records) < self.config.endpoints.page_size:
                break
            offset += self.config.endpoints.page_size

        loans: list[LoanSummary] = []
        for item in records:
            loan_id = _first_present(item, "loanId", "id", "guid")
            if not loan_id:
                LOGGER.warning("Skipping loan record without loan id: %s", item)
                continue
            loans.append(
                LoanSummary(
                    loan_id=str(loan_id),
                    modified_at=_optional_datetime(_first_present(item, "modifiedAt", "lastModified")),
                    created_at=_optional_datetime(_first_present(item, "createdAt", "dateCreated")),
                )
            )
        return loans

    def get_attachments(self, loan_id: str) -> list[AttachmentMetadata]:
        payload = self._request_json_path(
            self.config.endpoints.attachments_path_template.format(
                loan_id=urllib.parse.quote(loan_id)
            )
        )
        records = _as_list(payload, "attachments")
        attachments: list[AttachmentMetadata] = []
        for item in records:
            attachment_id = _first_present(item, "attachmentId", "id", "entityId")
            if not attachment_id:
                LOGGER.warning("Skipping attachment without attachment id for loan %s: %s", loan_id, item)
                continue
            attachments.append(
                AttachmentMetadata(
                    loan_id=loan_id,
                    attachment_id=str(attachment_id),
                    title=str(_first_present(item, "title", "name", "documentTitle") or ""),
                    created_at=_optional_datetime(_first_present(item, "createdAt", "dateCreated")),
                    created_by=str(_first_present(item, "createdBy", "createdByName", "userName") or ""),
                )
            )
        return attachments

    def download_attachment_pdf(self, loan_id: str, attachment_id: str, destination: Path) -> Path:
        url_path = self.config.endpoints.attachment_download_path_template.format(
            loan_id=urllib.parse.quote(loan_id),
            attachment_id=urllib.parse.quote(attachment_id),
        )
        content = self._request_bytes_path(url_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        return destination

    def update_loan_fields(self, loan_id: str, field_values: dict[str, Any]) -> dict[str, Any]:
        if not field_values:
            LOGGER.info("No extracted fields to update for loan %s", loan_id)
            return {"updated": False, "reason": "no_fields"}
        body = json.dumps({"fields": field_values}).encode("utf-8")
        return self._request_json_path(
            self.config.endpoints.loan_update_path_template.format(
                loan_id=urllib.parse.quote(loan_id)
            ),
            method="PATCH",
            body=body,
            headers={"Content-Type": "application/json"},
        )

    def _request_json_path(
        self,
        path: str,
        *,
        method: str = "GET",
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any] | list[Any]:
        return self._request(self._build_url(path), method=method, body=body, headers=headers)

    def _request_bytes_path(self, path: str) -> bytes:
        return self._request_bytes(self._build_url(path))

    def _build_url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return f"{self.config.auth.api_server.rstrip('/')}/{path.lstrip('/')}"

    def _request(
        self,
        url: str,
        *,
        method: str = "GET",
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
        authenticated: bool = True,
    ) -> dict[str, Any] | list[Any]:
        content = self._request_bytes(url, method=method, body=body, headers=headers, authenticated=authenticated)
        if not content:
            return {}
        try:
            return json.loads(content.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise EncompassApiError(f"Expected JSON response from {url}") from exc

    def _request_bytes(
        self,
        url: str,
        *,
        method: str = "GET",
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
        authenticated: bool = True,
    ) -> bytes:
        request_headers = {"Accept": "application/json", **(headers or {})}
        if authenticated:
            request_headers["Authorization"] = f"Bearer {self.get_token()}"
        request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.config.ai.timeout_seconds) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise EncompassApiError(f"{method} {url} failed with {exc.code}: {details}") from exc
        except urllib.error.URLError as exc:
            raise EncompassApiError(f"{method} {url} failed: {exc.reason}") from exc


def _as_list(payload: dict[str, Any] | list[Any], key: str) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    value = payload.get(key)
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(payload.get("data"), list):
        return [item for item in payload["data"] if isinstance(item, dict)]
    return []


def _first_present(item: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in item and item[key] not in (None, ""):
            return item[key]
    return None


def _optional_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        LOGGER.debug("Could not parse datetime value %r", value)
        return None


def _format_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
