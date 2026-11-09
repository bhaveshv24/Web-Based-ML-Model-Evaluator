"""TSMP-22: the RTM consistency checker passes on the real documents and catches broken ones.

The checker is scripts/validation/check_rtm.py. Each negative case copies the documents to a
temporary directory, breaks one thing and expects the matching problem to be reported.
"""

import importlib.util
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("check_rtm", ROOT / "scripts/validation/check_rtm.py")
check_rtm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_rtm)


def test_the_committed_documents_are_consistent(capsys):
    assert check_rtm.main() == 0, capsys.readouterr().out


@pytest.fixture
def docs_copy(tmp_path, monkeypatch):
    copy = tmp_path / "docs"
    for path in check_rtm.REPORTS:
        if path.exists():
            (copy / path.name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(path, copy / path.name)
    names = ("RTM", "REGISTER", "VALIDATION")
    for name in names:
        monkeypatch.setattr(check_rtm, name, copy / getattr(check_rtm, name).name)
    monkeypatch.setattr(check_rtm, "REPORTS", [copy / p.name for p in check_rtm.REPORTS])

    def problems_after(path_name, old, new):
        target = copy / path_name
        text = target.read_text()
        assert old in text, old
        target.write_text(text.replace(old, new, 1))
        check_rtm.main()

    return problems_after


@pytest.mark.parametrize(
    ("document", "old", "new", "expected"),
    [
        (
            "TSMP-22_REQUIREMENTS_TRACEABILITY_MATRIX.md",
            "::test_registration_rejects_weak_password_and_hashes_strong_password",
            "::test_registration_that_does_not_exist",
            "test_registration_that_does_not_exist not in tests/test_auth_history_workspaces.py",
        ),
        (
            "TSMP-22_REQUIREMENTS_TRACEABILITY_MATRIX.md",
            "`backend/accounts/managers.py`",
            "`backend/accounts/no_such_module.py`",
            "source path does not exist: backend/accounts/no_such_module.py",
        ),
        (
            "TSMP-22_REQUIREMENTS_TRACEABILITY_MATRIX.md",
            "| FR-027 |",
            "| FR-099 |",
            "no row for FR-027",
        ),
        (
            "TSMP-22_REQUIREMENTS_TRACEABILITY_MATRIX.md",
            "| DEF-13 | Low | UI-05 (supports FR-022) | Closed |",
            "| DEF-13 | Low | UI-05 (supports FR-022) | Open |",
            "RTM defect table: DEF-13 is ('Low', 'Open'), register says ('Low', 'Closed')",
        ),
        (
            "TSMP-22_VALIDATION_REPORT.md",
            "**All** | **48**",
            "**All** | **47**",
            "Validation report: 'All' row says",
        ),
        (
            "TSMP-21_TEST_EXECUTION_REPORT.md",
            "`gitleaks-history.log`",
            "`gitleaks-missing.log`",
            "evidence file not found in the repository: gitleaks-missing.log",
        ),
        (
            "TSMP-21_TEST_EXECUTION_REPORT.md",
            "DEF-13",
            "DEF-14",
            "cites DEF-14, which is not in the defect register",
        ),
    ],
    ids=[
        "unknown-test",
        "missing-source",
        "missing-row",
        "defect-status",
        "totals",
        "evidence",
        "defect-id",
    ],
)
def test_broken_documents_are_reported(docs_copy, capsys, document, old, new, expected):
    docs_copy(document, old, new)
    output = capsys.readouterr().out
    assert expected in output, output
    assert output.splitlines()[-1].startswith("FAIL")


def test_a_gitignored_local_file_does_not_count_as_evidence(monkeypatch, capsys):
    # Regression: coverage.xml existed locally but is gitignored, so CI could not find it.
    tracked = check_rtm.repository_files()
    assert tracked is not None and "docs/evidence/tsmp-21/gitleaks-history.log" in tracked
    without = tracked - {"docs/evidence/tsmp-21/gitleaks-history.log"}
    monkeypatch.setattr(check_rtm, "repository_files", lambda: without)
    assert check_rtm.main() == 1
    assert (
        "evidence file not found in the repository: gitleaks-history.log" in capsys.readouterr().out
    )
