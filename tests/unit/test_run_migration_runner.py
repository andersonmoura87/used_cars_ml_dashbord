"""Testes unitários das decisões locais do migration runner."""

import hashlib
from pathlib import Path

from scripts import run_migration as runner
from scripts.run_migration import _migration_content, _migration_identifier


def test_checksum_uses_exact_file_bytes(tmp_path):
    migration = tmp_path / "001_bytes.sql"
    raw = b"\xef\xbb\xbfSELECT 'a;b';\r\n"
    migration.write_bytes(raw)

    sql, checksum = _migration_content(migration)

    assert sql == "SELECT 'a;b';\r\n"
    assert checksum == hashlib.sha256(raw).hexdigest()


def test_schema_and_migration_with_same_basename_have_distinct_portable_ids(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    schema = tmp_path / "sql" / "schemas" / "001_shared.sql"
    migration = tmp_path / "sql" / "migrations" / "001_shared.sql"
    schema.parent.mkdir(parents=True)
    migration.parent.mkdir(parents=True)
    schema.touch()
    migration.touch()

    schema_id = _migration_identifier(schema)
    migration_id = _migration_identifier(migration)

    assert schema_id == "schemas/001_shared.sql"
    assert migration_id == "migrations/001_shared.sql"
    assert schema_id != migration_id
    assert "\\" not in schema_id + migration_id
    assert not Path(schema_id).is_absolute()
    assert not Path(migration_id).is_absolute()


def test_external_file_uses_deterministic_portable_fallback(tmp_path):
    migration = tmp_path / "nested" / "001_external.sql"
    migration.parent.mkdir()
    migration.touch()

    identifier = _migration_identifier(migration)

    assert identifier == "external/001_external.sql"
    assert "\\" not in identifier
    assert not Path(identifier).is_absolute()
