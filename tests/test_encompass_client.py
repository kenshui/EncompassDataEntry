from pathlib import Path

from encompass_ai_agent.config import AgentConfig, AuthConfig
from encompass_ai_agent.encompass import EncompassClient


def test_download_attachment_pdf_sends_attachment_id_in_body(tmp_path, monkeypatch):
    config = AgentConfig(
        auth=AuthConfig(
            instance="instance",
            smart_client_user="user",
            smart_client_password="password",
            client_id="client-id",
            client_secret="client-secret",
            api_server="https://encompass.example",
        )
    )
    client = EncompassClient(config)
    captured = {}

    def fake_request_bytes_path(path: str, *, method: str = "GET", body=None, headers=None):
        captured["path"] = path
        captured["method"] = method
        captured["body"] = body
        captured["headers"] = headers
        return b"%PDF-test"

    monkeypatch.setattr(client, "_request_bytes_path", fake_request_bytes_path)

    destination = client.download_attachment_pdf(
        "loan-1",
        "attachment-1",
        tmp_path / "loan-1" / "attachment-1.pdf",
    )

    assert destination == Path(tmp_path / "loan-1" / "attachment-1.pdf")
    assert destination.read_bytes() == b"%PDF-test"
    assert captured["path"] == "/encompass/v3/loans/loan-1/attachments/content"
    assert captured["method"] == "POST"
    assert captured["body"] == b'{"attachmentId": "attachment-1"}'
    assert captured["headers"] == {"Content-Type": "application/json"}
