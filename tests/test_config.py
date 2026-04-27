from pathlib import Path

from encompass_ai_agent.config import load_config


def base_env(tmp_path: Path) -> dict[str, str]:
    return {
        "ENCOMPASS_INSTANCE": "instance",
        "ENCOMPASS_SMART_CLIENT_USER": "user",
        "ENCOMPASS_SMART_CLIENT_PASSWORD": "password",
        "ENCOMPASS_CLIENT_ID": "client-id",
        "ENCOMPASS_CLIENT_SECRET": "client-secret",
        "ENCOMPASS_API_SERVER": "https://encompass.example",
        "AGENT_DATABASE_PATH": str(tmp_path / "agent.sqlite3"),
        "AGENT_DOWNLOAD_DIR": str(tmp_path / "downloads"),
        "AGENT_LOG_PATH": str(tmp_path / "events.jsonl"),
        "FIELD_MAPPING_JSON": '{"loan_amount": "1109", "processing_fee": "CX.PROCESSING"}',
    }


def test_load_config_reads_credentials_and_mapping(tmp_path: Path) -> None:
    config = load_config(base_env(tmp_path))

    assert config.auth.instance == "instance"
    assert config.auth.token_url == "https://encompass.example/oauth2/v1/token"
    assert config.field_mapping["loan_amount"] == "1109"
    assert config.field_mapping["processing_fee"] == "CX.PROCESSING"
