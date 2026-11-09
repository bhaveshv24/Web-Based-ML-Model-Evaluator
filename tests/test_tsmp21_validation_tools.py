"""TSMP-21 validation tooling: NFR-004 availability probe and PORT-01 portability check.

These scripts produce evidence, so their arithmetic and pass/fail rules are tested here. No
Docker or database is needed: the probe runs against a local HTTP server that this test starts.
"""

import argparse
import importlib.util
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/validation/{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


probe = load("availability_probe")
portability = load("portability_check")


def sample(up, maintenance=False):
    return {"up": up, "maintenance": maintenance}


def test_availability_excludes_planned_maintenance_and_applies_the_99_percent_target():
    samples = [sample(True)] * 99 + [sample(False)] + [sample(False, maintenance=True)] * 5
    summary = probe.summarize(samples)
    assert summary["samples_total"] == 105 and summary["samples_in_maintenance"] == 5
    assert summary["availability"] == 0.99 and summary["meets_target"] is True
    summary = probe.summarize([sample(True)] * 98 + [sample(False)] * 2)
    assert summary["availability"] == 0.98 and summary["meets_target"] is False


def test_availability_without_counted_samples_is_not_a_pass():
    summary = probe.summarize([sample(False, maintenance=True)])
    assert summary["availability"] is None and summary["meets_target"] is None


def test_durations_and_maintenance_windows_are_parsed_strictly():
    assert probe.parse_duration("90m") == 5400 and probe.parse_duration("2h") == 7200
    assert probe.parse_duration("45") == 45
    start, end = probe.parse_window("2026-11-20T10:00:00+00:00/2026-11-20T10:15:00+00:00")
    assert (end - start).total_seconds() == 900
    for bad in (
        "2026-11-20T10:00:00/2026-11-20T10:15:00",
        "2026-11-20T11:00+00:00/2026-11-20T10:00+00:00",
    ):
        with pytest.raises(argparse.ArgumentTypeError):
            probe.parse_window(bad)


class FakeStack(BaseHTTPRequestHandler):
    api_status = 401

    def do_GET(self):  # noqa: N802 (http.server API)
        code = 200 if self.path == "/results" else type(self).api_status
        self.send_response(code)
        self.end_headers()

    def log_message(self, *args):
        pass


@pytest.fixture
def stack():
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeStack)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.mark.parametrize(("api_status", "up"), [(401, True), (500, False), (200, False)])
def test_a_sample_is_up_only_when_the_api_requires_authentication(
    stack, tmp_path, monkeypatch, api_status, up
):
    monkeypatch.setattr(FakeStack, "api_status", api_status)
    out = tmp_path / "probe.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "probe",
            "--base-url",
            stack,
            "--duration",
            "0.05",
            "--interval",
            "0.1",
            "--out",
            str(out),
        ],
    )
    assert probe.main() == (0 if up else 1)
    result = json.loads(out.read_text())
    assert result["requirement"] == "NFR-004"
    assert [s["up"] for s in result["samples"]] == [up]


def test_unreachable_stack_is_down():
    assert probe.probe("http://127.0.0.1:9", "/results", timeout=1)[0] is None


def test_portability_report_fails_only_on_required_checks():
    report = portability.Report()
    report.record("optional", False, "missing", required=False)
    assert report.passed and report.results[0]["status"] == "WARN"
    report.record("required", False, "missing")
    assert not report.passed


def test_portability_reads_env_files_without_exposing_values(tmp_path):
    env = tmp_path / ".env"
    env.write_text("# comment\nDJANGO_SECRET_KEY=replace-with-a-long-random-value\nA = b=c\n")
    values = portability.env_values(env)
    assert values == {"DJANGO_SECRET_KEY": "replace-with-a-long-random-value", "A": "b=c"}
    assert values["DJANGO_SECRET_KEY"].startswith(portability.PLACEHOLDER_PREFIX)
