FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    AGENT_DATABASE_PATH=/data/encompass_ai_agent.sqlite3 \
    AGENT_DOWNLOAD_DIR=/data/downloads \
    AGENT_LOG_PATH=/data/agent-events.jsonl \
    AGENT_FIELD_MAPPING_PATH=/app/config/field_mapping.json

WORKDIR /app

RUN groupadd --system encompass-agent \
    && useradd --system --gid encompass-agent --home-dir /app encompass-agent \
    && mkdir -p /data/downloads \
    && chown -R encompass-agent:encompass-agent /app /data

COPY pyproject.toml README.md ./
COPY src ./src
COPY config ./config

RUN python -m pip install --upgrade pip \
    && python -m pip install .

USER encompass-agent
VOLUME ["/data"]

ENTRYPOINT ["encompass-ai-agent"]
