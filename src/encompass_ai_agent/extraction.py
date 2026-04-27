from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol
from urllib import error, request

from .config import AgentConfig
from .models import FIELD_DEFINITIONS, FieldDefinition

LOG = logging.getLogger(__name__)


class DocumentExtractor(Protocol):
    def extract(self, text: str) -> dict[str, str | None]:
        """Extract configured fields from document text."""


@dataclass(frozen=True)
class ExtractionResult:
    values: dict[str, str | None]
    raw_response: str | None = None


class RegexFallbackExtractor:
    """Deterministic extractor used when no LLM endpoint is configured."""

    def __init__(self, fields: tuple[FieldDefinition, ...] = FIELD_DEFINITIONS):
        self.fields = fields

    def extract(self, text: str) -> dict[str, str | None]:
        values: dict[str, str | None] = {}
        for field in self.fields:
            values[field.key] = _find_value_near_label(text, [field.label, *field.aliases])
        return values


class OpenAICompatibleExtractor:
    """Extractor for private-network or hosted OpenAI-compatible chat APIs."""

    def __init__(self, config: AgentConfig, fields: tuple[FieldDefinition, ...] = FIELD_DEFINITIONS):
        if not config.ai.api_key and config.ai.provider == "openai":
            raise ValueError("AI_API_KEY must be configured when AI_PROVIDER=openai")
        self.config = config
        self.fields = fields

    def extract(self, text: str) -> dict[str, str | None]:
        prompt = _build_prompt(text, self.fields)
        body = {
            "model": self.config.ai.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You extract mortgage loan disclosure and fee data. "
                        "Return only valid JSON. Use null for missing values."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        }
        headers = {"Content-Type": "application/json"}
        if self.config.ai.api_key:
            headers["Authorization"] = f"Bearer {self.config.ai.api_key}"

        req = request.Request(
            self.config.ai.endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.config.ai.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except error.URLError as exc:
            raise RuntimeError(f"AI extraction request failed: {exc}") from exc

        content = _extract_chat_content(payload)
        parsed = json.loads(content)
        return _normalize_result_keys(parsed, self.fields)


def build_extractor(config: AgentConfig) -> DocumentExtractor:
    if config.ai.provider.lower() in {"openai", "openai-compatible", "compatible"}:
        return OpenAICompatibleExtractor(config)
    LOG.warning("AI_PROVIDER is set to regex; using deterministic fallback extraction")
    return RegexFallbackExtractor()


def _build_prompt(text: str, fields: tuple[FieldDefinition, ...]) -> str:
    field_lines = "\n".join(f"- {field.key}: {field.label}" for field in fields)
    return (
        "Extract the following fields from this PDF text. Return a JSON object whose keys "
        "match exactly the keys listed below. Return numeric amounts as strings exactly as "
        "shown when possible, without currency symbols unless they are part of the source.\n\n"
        f"Fields:\n{field_lines}\n\n"
        f"Document text:\n{text[:60000]}"
    )


def _extract_chat_content(payload: dict[str, Any]) -> str:
    if "choices" in payload:
        return str(payload["choices"][0]["message"]["content"])
    if "content" in payload:
        return str(payload["content"])
    if "response" in payload:
        return str(payload["response"])
    return json.dumps(payload)


def _normalize_result_keys(
    parsed: dict[str, Any], fields: tuple[FieldDefinition, ...]
) -> dict[str, str | None]:
    normalized: dict[str, str | None] = {}
    for field in fields:
        value = parsed.get(field.key)
        normalized[field.key] = None if value in ("", None) else str(value)
    return normalized


def _find_value_near_label(text: str, labels: list[str]) -> str | None:
    for label in labels:
        pattern = re.compile(
            rf"{re.escape(label)}\s*(?:[:\-]|\s)\s*(\$?\(?-?\d[\d,]*(?:\.\d+)?%?\)?)",
            flags=re.IGNORECASE,
        )
        match = pattern.search(text)
        if match:
            return _clean_value(match.group(1))
    return None


def _clean_value(value: str) -> str:
    cleaned = value.strip().replace("$", "").replace(",", "")
    if cleaned.endswith("%"):
        return cleaned
    try:
        return str(Decimal(cleaned))
    except InvalidOperation:
        return value.strip()
