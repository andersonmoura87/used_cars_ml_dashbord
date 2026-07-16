"""
Testes unitários para scripts/quality_trend.py (UCM-26).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from scripts.quality_trend import (
    build_trend,
    filter_by_days,
    load_ge_summaries,
    load_history,
    load_pipeline_stats,
    main,
    render_markdown,
    write_outputs,
    _parse_ts,
)


def _entry(suite: str, pass_rate: float, success: bool = True, ts: str = "20260716_120000") -> dict:
    return {
        "suite": suite,
        "timestamp": ts,
        "evaluated_at": f"2026-07-16T12:00:00+00:00",
        "success": success,
        "evaluated": 10,
        "successful": int(pass_rate * 10),
        "failed": 10 - int(pass_rate * 10),
        "pass_rate": pass_rate,
    }


class TestParseTs:
    def test_iso(self):
        dt = _parse_ts("2026-07-16T12:00:00")
        assert dt is not None
        assert dt.year == 2026

    def test_compact(self):
        dt = _parse_ts("20260716_120000")
        assert dt is not None

    def test_invalid(self):
        assert _parse_ts("not-a-date") is None


class TestLoadHistory:
    def test_empty_missing(self, tmp_path):
        assert load_history(tmp_path / "missing.jsonl") == []

    def test_loads_lines(self, tmp_path):
        path = tmp_path / "h.jsonl"
        path.write_text(
            json.dumps(_entry("raw", 1.0)) + "\n"
            + json.dumps(_entry("clean", 0.9)) + "\n"
            + "not-json\n"
        )
        entries = load_history(path)
        assert len(entries) == 2


class TestLoadGeSummaries:
    def test_loads_files(self, tmp_path):
        (tmp_path / "ge_summary_raw_cars_suite_20260716.json").write_text(
            json.dumps(_entry("raw_cars_suite", 0.95))
        )
        entries = load_ge_summaries(tmp_path)
        assert len(entries) == 1
        assert entries[0]["suite"] == "raw_cars_suite"


class TestLoadPipelineStats:
    def test_loads(self, tmp_path):
        (tmp_path / "pipeline_1.json").write_text(json.dumps({
            "pipeline_end": "2026-07-16T12:00:00",
            "duration_seconds": 10,
            "total_input_records": 100,
            "total_clean_records": 90,
            "total_removed_records": 10,
            "ge_raw_passed": True,
            "ge_clean_passed": True,
        }))
        stats = load_pipeline_stats(tmp_path)
        assert len(stats) == 1
        assert stats[0]["input_rows"] == 100


class TestBuildTrend:
    def test_healthy_no_alerts(self):
        entries = [
            _entry("raw_cars_suite", 1.0),
            _entry("clean_cars_suite", 1.0),
        ]
        trend = build_trend(entries, [], days=30)
        assert trend["status"] in ("healthy", "no_data") or trend["overview"]["alert_count"] == 0
        assert "raw_cars_suite" in trend["suites"]
        assert trend["suites"]["raw_cars_suite"]["avg_pass_rate"] == 1.0

    def test_degraded_low_pass_rate(self):
        entries = [_entry("clean_cars_suite", 0.5, success=False)]
        trend = build_trend(entries, [], days=30)
        assert trend["status"] == "degraded"
        assert len(trend["alerts"]) >= 1

    def test_trend_delta_degradation(self):
        # 4 pontos: primeiros bons, últimos ruins
        entries = [
            {**_entry("raw_cars_suite", 1.0), "evaluated_at": "2026-07-01T00:00:00+00:00"},
            {**_entry("raw_cars_suite", 1.0), "evaluated_at": "2026-07-02T00:00:00+00:00"},
            {**_entry("raw_cars_suite", 0.5), "evaluated_at": "2026-07-03T00:00:00+00:00"},
            {**_entry("raw_cars_suite", 0.5), "evaluated_at": "2026-07-04T00:00:00+00:00"},
        ]
        trend = build_trend(entries, [], days=90)
        delta = trend["suites"]["raw_cars_suite"]["trend_delta"]
        assert delta < 0
        assert any("Degradação" in a for a in trend["alerts"])

    def test_no_data(self):
        trend = build_trend([], [], days=30)
        assert trend["status"] == "no_data"


class TestRenderMarkdown:
    def test_contains_sections(self):
        trend = build_trend([_entry("raw_cars_suite", 0.95)], [], days=30)
        md = render_markdown(trend)
        assert "# Data Quality Trend" in md
        assert "## Suites" in md
        assert "## Alerts" in md
        assert "raw_cars_suite" in md


class TestWriteOutputs:
    def test_writes_files(self, tmp_path):
        trend = build_trend([_entry("raw", 1.0)], [])
        paths = write_outputs(
            trend,
            tmp_path / "quality_trend.json",
            tmp_path / "QUALITY_TREND.md",
        )
        assert all(p.exists() for p in paths)
        assert "pass_rate" in paths[0].read_text() or "suites" in paths[0].read_text()


class TestMain:
    def test_stdout(self, tmp_path, capsys):
        history = tmp_path / "h.jsonl"
        history.write_text(json.dumps(_entry("raw_cars_suite", 1.0)) + "\n")
        rc = main([
            "--history", str(history),
            "--quality-dir", str(tmp_path),
            "--metadata-dir", str(tmp_path / "meta"),
            "--stdout",
        ])
        assert rc == 0
        assert "Data Quality Trend" in capsys.readouterr().out

    def test_writes_and_fail_on_degraded(self, tmp_path):
        history = tmp_path / "h.jsonl"
        history.write_text(json.dumps(_entry("clean", 0.4, success=False)) + "\n")
        out_json = tmp_path / "trend.json"
        out_md = tmp_path / "trend.md"
        rc = main([
            "--history", str(history),
            "--quality-dir", str(tmp_path),
            "--metadata-dir", str(tmp_path / "meta"),
            "--output-json", str(out_json),
            "--output-md", str(out_md),
            "--fail-on-degraded",
        ])
        assert rc == 1
        assert out_json.exists()
        assert out_md.exists()

    def test_github_output(self, tmp_path, monkeypatch):
        history = tmp_path / "h.jsonl"
        history.write_text(json.dumps(_entry("raw", 1.0)) + "\n")
        gh = tmp_path / "out.txt"
        monkeypatch.setenv("GITHUB_OUTPUT", str(gh))
        rc = main([
            "--history", str(history),
            "--quality-dir", str(tmp_path),
            "--metadata-dir", str(tmp_path / "meta"),
            "--output-json", str(tmp_path / "t.json"),
            "--output-md", str(tmp_path / "t.md"),
        ])
        assert rc == 0
        content = gh.read_text()
        assert "quality_status=" in content
