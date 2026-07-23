"""
Testes — scripts/check_secrets.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from scripts.check_secrets import check_secrets, main, render_checklist


class TestCheckSecrets:
    def test_etl_scope_missing_db(self, monkeypatch):
        for k in ("DB_PASSWORD", "DB_USER", "DB_HOST", "DB_NAME"):
            monkeypatch.delenv(k, raising=False)
        errors, _ = check_secrets("production", scopes={"etl"})
        assert any("DB_PASSWORD" in e for e in errors)

    def test_etl_scope_rejects_weak_password(self, monkeypatch):
        monkeypatch.setenv("DB_PASSWORD", "postgres")
        monkeypatch.setenv("DB_USER", "postgres")
        monkeypatch.setenv("DB_HOST", "localhost")
        monkeypatch.setenv("DB_NAME", "used_cars")
        errors, _ = check_secrets("production", scopes={"etl"})
        assert any("inseguro" in e for e in errors)

    def test_etl_scope_ok(self, monkeypatch):
        monkeypatch.setenv("DB_PASSWORD", "a" * 32)
        monkeypatch.setenv("DB_USER", "postgres")
        monkeypatch.setenv("DB_HOST", "db.example.com")
        monkeypatch.setenv("DB_NAME", "used_cars")
        errors, _ = check_secrets("production", scopes={"etl"})
        assert errors == []

    def test_cd_scope_requires_ssh(self, monkeypatch):
        for k in ("SSH_HOST", "SSH_USERNAME", "SSH_PRIVATE_KEY"):
            monkeypatch.delenv(k, raising=False)
        errors, _ = check_secrets("production", scopes={"cd"})
        assert len(errors) >= 3

    def test_api_scope_requires_api_key_in_prod(self, monkeypatch):
        monkeypatch.delenv("API_KEY", raising=False)
        monkeypatch.delenv("REDIS_PASSWORD", raising=False)
        errors, _ = check_secrets("production", scopes={"api"})
        assert any("API_KEY" in e for e in errors)


class TestMain:
    def test_checklist(self, capsys):
        assert main(["--checklist"]) == 0
        assert "Secrets Checklist" in capsys.readouterr().out

    def test_fails_without_secrets(self, monkeypatch, tmp_path):
        monkeypatch.delenv("DB_PASSWORD", raising=False)
        monkeypatch.delenv("DB_USER", raising=False)
        monkeypatch.delenv("DB_HOST", raising=False)
        monkeypatch.delenv("DB_NAME", raising=False)
        rc = main([
            "--environment", "production",
            "--scope", "etl",
            "--dotenv", str(tmp_path / "missing.env"),
        ])
        assert rc == 1


class TestRenderChecklist:
    def test_contains_tables(self):
        md = render_checklist()
        assert "DB_PASSWORD" in md
        assert "openssl" in md
