"""TSMP-22 consistency checker for the RTM, defect register and validation reports.

    python scripts/validation/check_rtm.py          # exit 1 and one line per problem

Checks:
  1. Requirement IDs: FR-001..027, SEC-001..010 and NFR-001..011 each have exactly one RTM row
     with a valid status, and no document cites an unknown requirement ID.
  2. Source paths cited in the RTM exist.
  3. Test references exist: `file.py::test_name` must be defined in that file (`::name` resolves
     against the previous file in the same cell), DOCKER: tests in test_sandbox_docker.py,
     SYS: cases in system_tests.py, UI: cases in results_dashboard.mjs.
  4. Defects: every DEF-nn cited anywhere is in the register; the RTM defect table lists every
     defect with the same severity and status; each strict xfail names an open defect.
  5. Evidence files cited by name in the reports exist under docs/evidence/tsmp-21/.
  6. The validation report's coverage totals equal the statuses counted in the RTM.
Standard library only.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
EVIDENCE = DOCS / "evidence/tsmp-21"
RTM = DOCS / "TSMP-22_REQUIREMENTS_TRACEABILITY_MATRIX.md"
REGISTER = DOCS / "TSMP-21_DEFECT_REGISTER.md"
VALIDATION = DOCS / "TSMP-22_VALIDATION_REPORT.md"
REPORTS = [
    RTM,
    REGISTER,
    VALIDATION,
    DOCS / "TSMP-21_TEST_EXECUTION_REPORT.md",
    DOCS / "TSMP_PROGRESS.md",
    DOCS / "TSMP-21_USABILITY_PROTOCOL.md",
]
EXPECTED = (
    [f"FR-{n:03d}" for n in range(1, 28)]
    + [f"SEC-{n:03d}" for n in range(1, 11)]
    + [f"NFR-{n:03d}" for n in range(1, 12)]
)
STATUSES = ("NOT IMPLEMENTED", "NOT VERIFIED", "VERIFIED", "PARTIAL")
REQ_ID = re.compile(r"\b(FR|SEC|NFR)-(\d{3})\b")
SOURCE = re.compile(r"`((?:backend|sandbox|scripts|tests|\.github)/[^`\s*{]+)`")
TEST_REF = re.compile(r"`(?:(test_\w+\.py))?::(test_\w+?)(_?\*)?`")
EVIDENCE_NAME = re.compile(r"`([\w./-]+\.(?:log|json|csv|html|xml|png|pdf))`")
# Names of files this project writes as evidence (API paths and source files also end in .json
# or .html, so only these are checked).
EVIDENCE_PREFIXES = (
    "bandit",
    "browser-",
    "coverage",
    "docker-suite",
    "gitleaks",
    "junit",
    "makemigrations",
    "nfr004",
    "perf01",
    "pip-audit",
    "port01",
    "pytest",
    "ruff",
    "screenshots/",
    "system-",
    "usa01",
    "attempt1",
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def table_rows(text: str, prefix: str) -> list[list[str]]:
    rows = []
    for line in text.splitlines():
        if line.startswith(f"| {prefix}"):
            rows.append([cell.strip() for cell in line.strip().strip("|").split(" | ")])
    return rows


def rtm_statuses(rtm: str, problems: list[str]) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for prefix in ("FR-0", "SEC-0", "NFR-0"):
        for cells in table_rows(rtm, prefix):
            rid = cells[0]
            if rid in statuses:
                problems.append(f"RTM: {rid} has more than one row")
            found = next((s for s in STATUSES if f"**{s}**" in cells[-1]), None)
            if found is None:
                problems.append(f"RTM: {rid} has no valid status in its last column")
            statuses[rid] = found or "?"
    for rid in EXPECTED:
        if rid not in statuses:
            problems.append(f"RTM: no row for {rid}")
    return statuses


def check_requirement_ids(problems: list[str]) -> None:
    known = set(EXPECTED)
    for path in REPORTS:
        for match in REQ_ID.finditer(read(path)):
            rid = match.group(0)
            if rid not in known:
                problems.append(f"{path.name}: unknown requirement ID {rid}")


def check_sources(rtm: str, problems: list[str]) -> int:
    paths = set(SOURCE.findall(rtm))
    for rel in sorted(paths):
        if not (ROOT / rel).exists():
            problems.append(f"RTM: source path does not exist: {rel}")
    return len(paths)


def defined_tests(path: Path) -> set[str]:
    return set(re.findall(r"^\s*(?:async\s+)?def (test_\w+)", read(path), re.MULTILINE))


def check_tests(rtm: str, problems: list[str]) -> int:
    tests_dir = ROOT / "tests"
    per_file = {p.name: defined_tests(p) for p in tests_dir.glob("test_*.py")}
    everywhere = set().union(*per_file.values())
    checked = 0
    for line in rtm.splitlines():
        if not line.startswith("|"):
            continue
        for cell in line.split(" | "):
            current = None
            for match in TEST_REF.finditer(cell):
                file, name, wildcard = match.groups()
                current = file or current
                pool = per_file.get(current, set()) if current else everywhere
                if current and current not in per_file:
                    problems.append(f"RTM: test file does not exist: tests/{current}")
                    continue
                prefix = name.rstrip("_") if wildcard else None
                ok = any(t.startswith(prefix) for t in pool) if prefix else name in pool
                checked += 1
                if not ok:
                    where = f"tests/{current}" if current else "tests/"
                    problems.append(f"RTM: test {name}{'*' if wildcard else ''} not in {where}")
    docker = defined_tests(tests_dir / "test_sandbox_docker.py")
    for name in set(re.findall(r"DOCKER:(test_\w+?)(?:_\*|\*)?`", rtm)):
        checked += 1
        if not any(t == name or t.startswith(name.rstrip("_")) for t in docker):
            problems.append(f"RTM: DOCKER test {name} not in tests/test_sandbox_docker.py")
    system = read(ROOT / "scripts/validation/system_tests.py")
    browser = read(ROOT / "scripts/validation/browser/results_dashboard.mjs")
    for kind, source, pattern in (
        ("SYS", system, r"`SYS:([^`]+)`"),
        ("UI", browser, r"`UI:([^`*]+)`"),
    ):
        for case in set(re.findall(pattern, rtm)) - {"<ID>"}:
            checked += 1
            if f'"{case}"' not in source:
                problems.append(f"RTM: {kind} case {case!r} is not defined in its script")
    return checked


def register_defects(register: str) -> dict[str, tuple[str, str]]:
    defects = {}
    for cells in table_rows(register, "DEF-"):
        status = re.sub(r"[*]|\(.*\)", "", cells[-1]).strip().split()[0]
        defects[cells[0]] = (cells[1], status)
    return defects


def check_defects(register: str, rtm: str, problems: list[str]) -> int:
    defects = register_defects(register)
    if not defects:
        problems.append("Defect register: no summary table found")
        return 0
    for path in REPORTS + [ROOT / "README.md"]:
        for ref in set(re.findall(r"\bDEF-\d{2}\b", read(path))):
            if ref not in defects:
                problems.append(f"{path.name}: cites {ref}, which is not in the defect register")
    section = rtm.split("## 5. Defect-to-requirement links", 1)[-1].split("\n## ", 1)[0]
    rtm_defects = {cells[0]: (cells[1], cells[-1]) for cells in table_rows(section, "DEF-")}
    for ref, (severity, status) in defects.items():
        if ref not in rtm_defects:
            problems.append(f"RTM defect table: {ref} is missing")
        elif rtm_defects[ref] != (severity, status):
            problems.append(
                f"RTM defect table: {ref} is {rtm_defects[ref]}, register says {(severity, status)}"
            )
    for path in (ROOT / "tests").glob("test_*.py"):
        for reason in re.findall(r"xfail\(\s*strict=True,\s*reason=\"([^\"]+)\"", read(path)):
            for ref in re.findall(r"DEF-\d{2}", reason):
                if defects.get(ref, ("", ""))[1] != "Open":
                    problems.append(f"{path.name}: strict xfail cites {ref}, which is not Open")
    return len(defects)


def check_evidence(problems: list[str]) -> int:
    names = set()
    for path in REPORTS:
        for name in EVIDENCE_NAME.findall(read(path)):
            base = name.removeprefix("docs/evidence/tsmp-21/")
            if "*" in name or "<" in name or not base.startswith(EVIDENCE_PREFIXES):
                continue
            names.add((path.name, name))
    for doc, name in sorted(names):
        candidates = [EVIDENCE / name, ROOT / name, DOCS / name]
        if not any(c.exists() for c in candidates) and not list(EVIDENCE.rglob(Path(name).name)):
            problems.append(f"{doc}: evidence file not found: {name}")
    return len(names)


def check_totals(statuses: dict[str, str], problems: list[str]) -> None:
    counts = Counter(statuses.values())
    row = next((line for line in read(VALIDATION).splitlines() if line.startswith("| **All**")), "")
    numbers = [int(n) for n in re.findall(r"\*\*(\d+)", row)]
    if len(numbers) != 5:
        problems.append("Validation report: coverage summary 'All' row not found")
        return
    order = ("VERIFIED", "PARTIAL", "NOT VERIFIED", "NOT IMPLEMENTED")
    expected = [len(statuses)] + [counts[s] for s in order]
    if numbers != expected:
        problems.append(
            f"Validation report: 'All' row says total/verified/partial/not verified/"
            f"not implemented = {numbers}, the RTM counts {expected}"
        )


def main() -> int:
    problems: list[str] = []
    rtm = read(RTM)
    statuses = rtm_statuses(rtm, problems)
    check_requirement_ids(problems)
    sources = check_sources(rtm, problems)
    tests = check_tests(rtm, problems)
    defects = check_defects(read(REGISTER), rtm, problems)
    evidence = check_evidence(problems)
    check_totals(statuses, problems)
    for problem in problems:
        print(f"FAIL {problem}")
    counts = Counter(statuses.values())
    print(
        f"{'FAIL' if problems else 'PASS'}: {len(statuses)} requirements "
        f"({', '.join(f'{counts[s]} {s.lower()}' for s in STATUSES[::-1])}), "
        f"{sources} source paths, {tests} test references, {defects} defects, "
        f"{evidence} evidence references, {len(problems)} problems"
    )
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
