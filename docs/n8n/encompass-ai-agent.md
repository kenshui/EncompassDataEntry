# n8n Encompass AI Agent

This folder contains an importable n8n workflow that implements the Encompass
AI agent flow:

1. Run daily on a schedule.
2. Authenticate to Encompass.
3. Find loans modified or created during the lookback window.
4. Fetch attachment metadata for each loan.
5. Track whether each attachment has already been processed.
6. Download new PDFs by sending the attachment ID in the request body.
7. Extract fields with an OpenAI-compatible chat endpoint.
8. Map extracted values to Encompass loan schema fields.
9. Patch mapped fields back to Encompass.
10. Record an audit event.

## Import

In n8n:

1. Open **Workflows**.
2. Select **Import from File**.
3. Import `workflows/encompass-ai-agent.n8n.json`.
4. Save the workflow.

## Required n8n environment variables

Set these environment variables for self-hosted n8n, or replace the expressions
in the workflow with your preferred n8n credential nodes.

| Variable | Purpose |
| --- | --- |
| `ENCOMPASS_INSTANCE` | Encompass instance name |
| `ENCOMPASS_SMART_CLIENT_USER` | Smart Client API user |
| `ENCOMPASS_SMART_CLIENT_PASSWORD` | Smart Client API password |
| `ENCOMPASS_CLIENT_ID` | API client ID |
| `ENCOMPASS_CLIENT_SECRET` | API client secret |
| `ENCOMPASS_API_SERVER` | Example: `https://concept.api.elliemae.com` |
| `AI_ENDPOINT` | OpenAI-compatible chat completion endpoint |
| `AI_API_KEY` | AI provider API key |
| `AI_MODEL` | Approved model name |

Optional variables:

| Variable | Default |
| --- | --- |
| `AGENT_LOOKBACK_DAYS` | `31` |
| `AGENT_DRY_RUN` | `true` |
| `ENCOMPASS_TOKEN_PATH` | `/oauth2/v1/token` |
| `ENCOMPASS_LOANS_PATH` | `/encompass/v3/loans` |
| `ENCOMPASS_ATTACHMENTS_PATH_TEMPLATE` | `/encompass/v3/loans/{loan_id}/attachments` |
| `ENCOMPASS_ATTACHMENT_DOWNLOAD_PATH_TEMPLATE` | `/encompass/v3/loans/{loan_id}/attachments/content` |
| `ENCOMPASS_ATTACHMENT_DOWNLOAD_BODY_FIELD` | `attachmentId` |
| `ENCOMPASS_LOAN_UPDATE_PATH_TEMPLATE` | `/encompass/v3/loans/{loan_id}` |

## Field mapping

The **Build Field Update Payload** code node contains the same default mapping
keys as `config/field_mapping.example.json`. Replace the `CX.*` placeholders
with the customer's real Encompass loan schema field IDs before disabling
dry-run mode.

## Processed-document tracking

The workflow uses n8n workflow static data for processed attachment tracking:

- key: `<loan_id>::<attachment_id>`
- value: attachment metadata, mapped fields, status, and timestamps

This works for a single n8n instance. For production clusters or high-volume
deployments, replace these nodes with a shared data store:

- **Check Processed Flag**
- **Prepare Processing Metadata**
- **Mark Processed**
- **Mark Failed**

Recommended production stores are Postgres, n8n Data Store, or another customer
approved database. Persist these fields:

- `loan_id`
- `attachment_id`
- `title`
- `created_at`
- `created_by`
- `processed`
- `processed_at`
- `last_error`
- `fields_json`

## PDF extraction

The workflow uses n8n's **Extract From File** node with the `pdf` operation to
convert the downloaded PDF binary into text before calling the AI endpoint.

If your n8n version does not include PDF support in that node, replace **Extract
PDF Text** with an approved community PDF parser, an internal OCR/document AI
service, or a small private service using the Python agent's `pypdf` extraction
logic.

## Dry-run and production updates

The workflow defaults to dry-run unless `AGENT_DRY_RUN=false`. In dry-run mode,
the update payload is built and logged, but the **Update Loan Fields** node is
skipped.

Before production use:

1. Confirm all endpoint paths with the customer's Encompass API version.
2. Confirm loan field mapping IDs.
3. Run against sandbox loans.
4. Review workflow execution logs and processed-document records.
5. Set `AGENT_DRY_RUN=false`.
