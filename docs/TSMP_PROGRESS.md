# TSMP-21 / TSMP-22 progress

Owner: Ayush M Shetty. Branch: `feature/TSMP-21-22-validation` (not merged into `main`; no pull
request yet). Last updated: 6 November 2026.

Percentages are counted from deliverables with evidence in `docs/evidence/tsmp-21/` or in CI.
They are not estimates.

## Summary

| Measure | Value |
|---|---|
| TSMP-21 activities | **80%**: 7 complete, 2 partial (half credit), 1 blocked, out of 10 |
| TSMP-21 acceptance criteria (MLE-21) | 2 of 4 met (≥ 90% pass; results recorded). Not met: 100% of High requirements, no open High defect |
| TSMP-22 traceability | **46 / 48 (96%)** requirements have every link their SRS method requires |
| TSMP-22 validation result | 41 verified, 5 partial, 1 not verified, 1 not implemented (85% verified) |
| STP planned cases (80) | 75 pass, 4 fail, 1 blocked (93.75%) |
| Automated checks executed | 382: pytest 341 (335 pass, 6 strict xfail), Docker 9, live system 15, Chrome 7, Firefox 7, CI smoke 3 |
| Open defects | 1 High (DEF-07), 0 Critical; Medium DEF-05, DEF-09, DEF-12; Low DEF-06, DEF-10 |
| Latest CI | Run 41868670661 on `10224fc`: all 4 jobs succeeded |

## TSMP-21 activities

| Activity | Status | Evidence | Remaining |
|---|---|---|---|
| Regression | COMPLETE | `pytest-core.log`, `junit-core.xml`, CI 41868670661 (335 passed, 96.37% coverage). Re-run locally on 6 Nov: same result | - |
| Security ST-SEC-01..13 | COMPLETE | 13/13 pass; `test_tsmp21_security.py`; pip-audit and Bandit retests; `gitleaks-history.log` (added 6 Nov) | - |
| Performance PERF-01..03 | COMPLETE | `perf01_*`, `system-results.json` | Caveat: one host, development server |
| Concurrency PERF-04 | COMPLETE | `system-results.json` | Caveat: 3 worker slots |
| Reliability REL-01 | COMPLETE | `system-results.json` | - |
| Usability USA-01 | BLOCKED | - | Needs MLE-17 UI and five participants |
| Portability PORT-01 / NFR-008 | PARTIAL | macOS and Ubuntu Compose; Chrome 7/7, Firefox 7/7 (6 Nov) | Windows (Docker Desktop) and Edge |
| Retention RET-01 | COMPLETE | `test_tsmp21_retention.py`, `system-results.json` | - |
| High/Critical defects | PARTIAL | DEF-01, DEF-02 closed | DEF-07 (teammates, MLE-17) |
| Retest of fixed defects | COMPLETE | 7/7 closed defects have regression tests and a retest | - |
| UI system tests (ST-AUTH-01/02, ST-ING-01, ST-EXE-01) | BLOCKED | API path passes | Rerun after MLE-17 |

## TSMP-22 deliverables

| Deliverable | Status | Notes |
|---|---|---|
| RTM rows for FR-001..027, SEC-001..010, NFR-001..011 | COMPLETE | 48 rows; every cited file and test checked to exist (6 Nov) |
| Defect-to-requirement table | COMPLETE | DEF-13 added on 6 Nov (13/13) |
| Traceability gaps listed | COMPLETE | RTM section 6 |
| Full chain for every requirement | PARTIAL | NFR-005 has no source code; NFR-004 and NFR-005 have no executed test |
| Validation report | COMPLETE | Corrected on 6 Nov (see change log) |

## Change log, 6 November 2026

- DEF-08 retest figures corrected to `system-results.json` (5.9 MB sent, 120.4 → 120.7 MiB) in
  the defect register and the validation report. They previously said 6.4 MB and
  106.9 → 107.1 MiB.
- RTM: DEF-13 added. DEF-07 row aligned with the defect register. FR-013 now cites its unit test
  `test_feature_count_mismatch_is_explicit` and the validator `validate_feature_compatibility`.
  Empty unit-test cells now say why there is no unit test (not an SRS method). SEC-009 states
  that it has no automated test. New section 6 lists every gap.
- `coverage.xml` reference corrected: the file is gitignored. The figure is in
  `pytest-core.log`, and the CI `coverage-xml` artifact of run 41868670661 is kept until
  2 February 2027.
- CI run 41868670661 recorded in the execution and validation reports.
- ST-SEC-12 claim "no secrets in Git history" now has evidence: gitleaks 8.18.4 over all refs,
  52 commits, no leaks (`gitleaks-history.log`).
- Firefox run of the 7 `/results` cases: 7/7 PASS (`browser-firefox/`). The browser script
  gained a `BROWSER` option (`chrome` default, `firefox`, `msedge`). Non-Chrome runs write to a
  separate folder, so the Chrome evidence is never overwritten.
- Consistency fixes: ST-SEC-05 case count (17, not "16 + 2"), wrong section references in the
  execution report, an explanation of the 7,377 vs 7,370 PERF-01 totals, DEF-01's 326-test count
  labelled as a point-in-time figure, and the audit's wrong claim that `pytest-core.log` is the
  baseline run.

## Not done, and why

| Item | Reason |
|---|---|
| Windows PORT-01 | No Windows machine or VM is available (the UTM VMs on the test machine are Linux) |
| Edge browser run | Microsoft Edge is not installed. The script is ready: `BROWSER=msedge` |
| USA-01, UI system tests | MLE-17 React SPA does not exist (DEF-07) |
| NFR-004 | Needs an operating window to measure availability |
| SonarQube (DEF-10) | No SonarQube or SonarCloud project is configured |

## Remaining blockers

| Blocker | Blocks | Owner |
|---|---|---|
| DEF-07: MLE-17 React SPA not implemented | USA-01, NFR-005, ST-AUTH-01/02, ST-ING-01, ST-EXE-01; FR-005 and FR-014 stay PARTIAL; MLE-21 exit criteria | M2 + M4 |
| DEF-05: evaluator cannot open member evaluations | BR-05, STP 11.1 matrix (5 strict xfails) | M1, M3, M4 |
| DEF-06: ADMIN superset role vs STP 11.1 | 1 strict xfail | Team decision |
| DEF-09: development server, no HTTPS | SEC-009 PARTIAL | Team sign-off (deployment change) |
| DEF-12: evaluation delete keeps uploads | FR-006 wording | Team decision |
| DEF-10: SonarQube gate | NFR-007 PARTIAL | Team / course infrastructure |
| Windows host and Edge | NFR-008 PARTIAL | Anyone with a Windows machine |
| NFR-004 operating window | NFR-004 NOT VERIFIED | Team |
| PR review and merge | Work is not on `main` | Ayush (open PR), module owners (review) |
