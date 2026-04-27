# Encompass AI Agent

Production-ready Python agent for scanning Encompass loans, downloading new PDF
attachments, extracting mortgage fee fields with AI, and updating mapped fields
back to the loan record.

The agent is designed for customer private-network deployments:

- runs on a daily schedule with systemd timers or any enterprise scheduler;
- authenticates with Encompass using instance, smart client user/password,
client ID, client secret, and API server;
- persists every attachment in SQLite with a processed flag;
- downloads and reads only unprocessed PDFs;
- supports OpenAI-compatible private AI endpoints or a deterministic regex
fallback for testing;
- writes auditable event logs to SQLite and JSONL.

## Workflow

1. Request an Encompass access token.
2. Scan loans modified or created within the configured lookback window.
3. Retrieve attachment metadata for each loan.
4. Store `loan_id`, `attachment_id`, title, created date, created by, and
  processing status.
5. Skip attachments already processed by this agent.
6. Download new PDF attachments.
7. Extract the configured fields from PDF text.
8. Map extracted field names to customer Encompass loan field IDs.
9. PATCH the mapped fields back to the loan.
10. Log processing success or failure.

## Extracted fields

The built-in prompt and fallback extractor target these fields:

- Owner's Title Insurance Fees
- Lenders' Title Insurance Fees
- Recording Fees
- Transfer Taxes
- Transfer Tax City
- Processing Fee
- Underwriting Fee
- VOE fee
- Appraisal Fee
- Credit Report Fee
- Flood Certification
- Mortgage Insurance Premium
- Tax Service Fee
- Homeowner's Insurance Premium
- Prepaid Interest Amount
- Prepaid Interest Rate
- Homeowner's Insurance monthly cost
- Mortgage Insurance Cost
- Property Taxes
- Title-Courier Fee
- Title- Escrow Fee
- Title- Lender's Title Insurance Fee
- Title - Loan Tie In fee
- Title - Recording Service Fee
- Title - Title Endorsement Fees
- Sales Contract Price
- Loan Amount

## Installation

```bash
python3.11 -m venv .venv
. .venv/bin/activate
pip install -e .
```

For tests:

```bash
pip install -e ".[dev]"
pytest
```

## Configuration

Copy the example environment file and field mapping:

```bash
cp .env.example .env
cp config/field_mapping.example.json config/field_mapping.json
```

Set the required values:

```bash
ENCOMPASS_INSTANCE=customer-instance
ENCOMPASS_SMART_CLIENT_USER=api-user@example.com
ENCOMPASS_SMART_CLIENT_PASSWORD=...
ENCOMPASS_CLIENT_ID=...
ENCOMPASS_CLIENT_SECRET=...
ENCOMPASS_API_SERVER=https://api.elliemae.com
```

The field mapping file maps agent extraction keys to the customer's actual
Encompass loan schema fields. Replace the `CX.*` examples with production field
IDs before enabling updates.

### AI provider

Use a private OpenAI-compatible endpoint:

```bash
AI_PROVIDER=openai-compatible
AI_ENDPOINT=https://private-ai.example.com/v1/chat/completions
AI_API_KEY=...
AI_MODEL=your-approved-model
```

For local validation without an AI service, keep:

```bash
AI_PROVIDER=regex
AGENT_DRY_RUN=true
```

## Running

```bash
set -a
. ./.env
set +a
encompass-ai-agent --dry-run
```

When field mappings and permissions are verified:

```bash
AGENT_DRY_RUN=false encompass-ai-agent
```

## Docker

Build the image:

```bash
docker build -t encompass-ai-agent:local .
```

Run a one-off dry run with local configuration and a persistent data volume:

```bash
docker run --rm \
  --env-file .env \
  -v "$PWD/config:/app/config:ro" \
  -v "$PWD/data:/data" \
  encompass-ai-agent:local --dry-run
```

Or use Docker Compose:

```bash
docker compose up --build encompass-ai-agent
```

The container runs as a non-root user. Container defaults store SQLite,
downloaded PDFs, and JSONL logs under `/data`; `docker-compose.yml` mounts that
path to the local `data/` directory and mounts `config/field_mapping.json` into
the container as read-only configuration.

## Scheduling

Example systemd units are in `deploy/`.

```bash
sudo cp deploy/encompass-ai-agent.service /etc/systemd/system/
sudo cp deploy/encompass-ai-agent.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now encompass-ai-agent.timer
```

The default timer runs daily at 02:00 server local time. The service expects the
application under `/opt/encompass-ai-agent` and an environment file at
`/etc/encompass-ai-agent/env`.

## Data and audit tables

SQLite tables are created automatically:

- `loan_attachments`: one row per loan attachment, including title, created
date, created by, processed flag, processed timestamp, and last error.
- `processing_events`: append-only processing log with extracted and mapped
field JSON.

The agent also writes JSONL events to `AGENT_LOG_PATH` for SIEM ingestion or
operational review.

## Endpoint customization

Encompass environments can expose different routing or gateway paths. Override
these without code changes:

```bash
ENCOMPASS_TOKEN_PATH=/oauth2/v1/token
ENCOMPASS_LOANS_PATH=/encompass/v3/loans
ENCOMPASS_ATTACHMENTS_PATH_TEMPLATE=/encompass/v3/loans/{loan_id}/attachments
ENCOMPASS_ATTACHMENT_DOWNLOAD_PATH_TEMPLATE=/encompass/v3/loans/{loan_id}/attachments/content
ENCOMPASS_ATTACHMENT_DOWNLOAD_BODY_FIELD=attachmentId
ENCOMPASS_LOAN_UPDATE_PATH_TEMPLATE=/encompass/v3/loans/{loan_id}
```

PDF downloads POST the selected attachment ID in the JSON request body as
`{"attachmentId": "..."}` by default. Override
`ENCOMPASS_ATTACHMENT_DOWNLOAD_BODY_FIELD` if a customer's gateway expects a
different JSON property name.

Validate these paths against the customer's Encompass API version before
production use.