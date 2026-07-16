"""
Testes unitários para scripts/notify_etl.py (UCM-26).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from scripts.notify_etl import (
    build_slack_payload,
    find_latest_pipeline_metadata,
    load_from_metadata,
    main,
    send_slack,
)


class TestBuildSlackPayload:
    def test_success_payload(self):
        payload = build_slack_payload(
            "success",
            duration_seconds=12.5,
            input_rows=1000,
            clean_rows=900,
            ge_raw_passed=True,
            ge_clean_passed=True,
        )
        assert "attachments" in payload
        assert payload["attachments"][0]["color"] == "good"
        titles = [f["title"] for f in payload["attachments"][0]["fields"]]
        assert "Duração" in titles
        assert "Linhas input" in titles

    def test_failure_payload_with_error(self):
        payload = build_slack_payload("failure", error="GE clean failed")
        assert payload["attachments"][0]["color"] == "danger"
        assert "GE clean failed" in payload["attachments"][0]["text"]

    def test_warning_with_drift(self):
        payload = build_slack_payload(
            "warning",
            drift_detected=True,
            drift_score=0.42,
        )
        fields = {f["title"]: f["value"] for f in payload["attachments"][0]["fields"]}
        assert "Drift" in fields
        assert "0.420" in fields["Drift"]


class TestLoadFromMetadata:
    def test_loads_fields(self, tmp_path):
        meta = {
            "duration_seconds": 30.0,
            "total_input_records": 5000,
            "total_clean_records": 4800,
            "total_removed_records": 200,
            "ge_raw_passed": True,
            "ge_clean_passed": False,
        }
        path = tmp_path / "pipeline_x.json"
        path.write_text(json.dumps(meta))
        result = load_from_metadata(path)
        assert result["status"] == "warning"
        assert result["input_rows"] == 5000
        assert result["ge_clean_passed"] is False

    def test_success_when_ge_ok(self, tmp_path):
        path = tmp_path / "pipeline_ok.json"
        path.write_text(json.dumps({
            "ge_raw_passed": True,
            "ge_clean_passed": True,
            "duration_seconds": 1,
        }))
        assert load_from_metadata(path)["status"] == "success"


class TestFindLatest:
    def test_none_when_missing(self, tmp_path):
        assert find_latest_pipeline_metadata(tmp_path) is None

    def test_picks_newest(self, tmp_path):
        import os
        a = tmp_path / "pipeline_a.json"
        b = tmp_path / "pipeline_b.json"
        a.write_text("{}")
        b.write_text("{}")
        os.utime(a, (1_700_000_000, 1_700_000_000))
        os.utime(b, (1_800_000_000, 1_800_000_000))
        assert find_latest_pipeline_metadata(tmp_path) == b


class TestSendSlack:
    def test_success_http(self):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("scripts.notify_etl.urlopen", return_value=mock_resp):
            assert send_slack({"text": "hi"}, "https://hooks.slack.com/test") is True

    def test_http_error(self):
        from urllib.error import HTTPError
        err = HTTPError("https://x", 400, "Bad", hdrs=None, fp=MagicMock(read=lambda: b"bad"))
        with patch("scripts.notify_etl.urlopen", side_effect=err):
            assert send_slack({"text": "hi"}, "https://hooks.slack.com/test") is False


class TestMain:
    def test_dry_run(self, capsys):
        rc = main(["--status", "success", "--duration", "10", "--dry-run"])
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert "attachments" in out

    def test_noop_without_webhook(self, monkeypatch):
        monkeypatch.delenv("SLACK_WEBHOOK", raising=False)
        rc = main(["--status", "failure", "--error", "boom"])
        assert rc == 0

    def test_from_metadata(self, tmp_path, capsys):
        path = tmp_path / "pipeline_1.json"
        path.write_text(json.dumps({
            "duration_seconds": 5,
            "total_input_records": 100,
            "total_clean_records": 90,
            "ge_raw_passed": True,
            "ge_clean_passed": True,
        }))
        rc = main(["--from-metadata", str(path), "--dry-run"])
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out["attachments"][0]["color"] == "good"

    def test_missing_status_returns_1(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "scripts.notify_etl.find_latest_pipeline_metadata",
            lambda: None,
        )
        rc = main([])
        assert rc == 1
