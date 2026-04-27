from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import FIELD_DEFINITIONS


DEFAULT_ATTACHMENT_TYPES = ("application/pdf",)


@dataclass(frozen=True)
class AuthConfig:
    instance: str
    smart_client_user: str
    smart_client_password: str
    client_id: str
    client_secret: str
    api_server: str
    token_path: str = "/oauth2/v1/token"

    @property
    def token_url(self) -> str:
        return _join_url(self.api_server, self.token_path)


@dataclass(frozen=True)
class EndpointConfig:
    loans_path: str = "/encompass/v3/loans"
    attachments_path_template: str = "/encompass/v3/loans/{loan_id}/attachments"
    attachment_download_path_template: str = (
        "/encompass/v3/loans/{loan_id}/attachments/content"
    )
    attachment_download_body_field: str = "attachmentId"
    loan_update_path_template: str = "/encompass/v3/loans/{loan_id}"
    modified_after_query_param: str = "modifiedAfter"
    created_after_query_param: str = "createdAfter"
    page_limit_query_param: str = "limit"
    page_offset_query_param: str = "offset"
    page_size: int = 100


@dataclass(frozen=True)
class AiConfig:
    provider: str = "regex"
    model: str = "gpt-4o-mini"
    api_key: str | None = None
    endpoint: str = "https://api.openai.com/v1/chat/completions"
    timeout_seconds: int = 120


@dataclass(frozen=True)
class StorageConfig:
    database_path: Path = Path("data/encompass_agent.sqlite3")
    download_dir: Path = Path("data/downloads")
    log_path: Path = Path("data/agent-events.jsonl")


@dataclass(frozen=True)
class AgentConfig:
    auth: AuthConfig
    endpoints: EndpointConfig = field(default_factory=EndpointConfig)
    ai: AiConfig = field(default_factory=AiConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    lookback_days: int = 31
    dry_run: bool = False
    field_mapping: dict[str, str] = field(default_factory=dict)

    @property
    def request_timeout_seconds(self) -> int:
        return self.ai.timeout_seconds


def load_config(env: dict[str, str] | None = None) -> AgentConfig:
    values = env or os.environ
    storage = StorageConfig(
        database_path=Path(values.get("AGENT_DATABASE_PATH", "data/encompass_agent.sqlite3")),
        download_dir=Path(values.get("AGENT_DOWNLOAD_DIR", "data/downloads")),
        log_path=Path(values.get("AGENT_LOG_PATH", "data/agent-events.jsonl")),
    )
    return AgentConfig(
        auth=AuthConfig(
            instance=_required(values, "ENCOMPASS_INSTANCE"),
            smart_client_user=_required(values, "ENCOMPASS_SMART_CLIENT_USER"),
            smart_client_password=_required(values, "ENCOMPASS_SMART_CLIENT_PASSWORD"),
            client_id=_required(values, "ENCOMPASS_CLIENT_ID"),
            client_secret=_required(values, "ENCOMPASS_CLIENT_SECRET"),
            api_server=_required(values, "ENCOMPASS_API_SERVER"),
            token_path=values.get("ENCOMPASS_TOKEN_PATH", "/oauth2/v1/token"),
        ),
        endpoints=EndpointConfig(
            loans_path=values.get("ENCOMPASS_LOANS_PATH", "/encompass/v3/loans"),
            attachments_path_template=values.get(
                "ENCOMPASS_ATTACHMENTS_PATH_TEMPLATE",
                "/encompass/v3/loans/{loan_id}/attachments",
            ),
            attachment_download_path_template=values.get(
                "ENCOMPASS_ATTACHMENT_DOWNLOAD_PATH_TEMPLATE",
                "/encompass/v3/loans/{loan_id}/attachments/content",
            ),
            attachment_download_body_field=values.get(
                "ENCOMPASS_ATTACHMENT_DOWNLOAD_BODY_FIELD", "attachmentId"
            ),
            loan_update_path_template=values.get(
                "ENCOMPASS_LOAN_UPDATE_PATH_TEMPLATE",
                "/encompass/v3/loans/{loan_id}",
            ),
            modified_after_query_param=values.get(
                "ENCOMPASS_MODIFIED_AFTER_QUERY_PARAM", "modifiedAfter"
            ),
            created_after_query_param=values.get("ENCOMPASS_CREATED_AFTER_QUERY_PARAM", "createdAfter"),
            page_limit_query_param=values.get("ENCOMPASS_PAGE_LIMIT_QUERY_PARAM", "limit"),
            page_offset_query_param=values.get("ENCOMPASS_PAGE_OFFSET_QUERY_PARAM", "offset"),
            page_size=int(values.get("ENCOMPASS_PAGE_SIZE", "100")),
        ),
        ai=AiConfig(
            provider=values.get("AI_PROVIDER", "regex"),
            model=values.get("AI_MODEL", "gpt-4o-mini"),
            api_key=values.get("AI_API_KEY"),
            endpoint=values.get("AI_ENDPOINT", "https://api.openai.com/v1/chat/completions"),
            timeout_seconds=int(values.get("AI_TIMEOUT_SECONDS", "120")),
        ),
        storage=storage,
        lookback_days=int(values.get("AGENT_LOOKBACK_DAYS", "31")),
        dry_run=_parse_bool(values.get("AGENT_DRY_RUN", "false")),
        field_mapping=_load_field_mapping(values),
    )


def _load_field_mapping(values: dict[str, str]) -> dict[str, str]:
    raw_json = values.get("FIELD_MAPPING_JSON")
    file_path = values.get("FIELD_MAPPING_FILE") or values.get(
        "AGENT_FIELD_MAPPING_PATH", "config/field_mapping.json"
    )
    data: dict[str, Any] = {}
    if raw_json:
        data = json.loads(raw_json)
    elif Path(file_path).exists():
        data = json.loads(Path(file_path).read_text(encoding="utf-8"))
    mapping = {field.key: data.get(field.key, "") for field in FIELD_DEFINITIONS}
    mapping.update({str(key): str(value) for key, value in data.items() if value})
    return mapping


def _required(values: dict[str, str], name: str) -> str:
    value = values.get(name)
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _parse_bool(value: str) -> bool:
    return value.lower() in {"1", "true", "yes", "y", "on"}


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"
