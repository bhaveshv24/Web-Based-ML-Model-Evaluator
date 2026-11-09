# TSMP-21 / TSMP-22 progress

Owner: Ayush M Shetty. Branch: `feature/TSMP-21-22-validation` (not merged into `main`; no pull
request yet). Last updated: 6 November 2026.

Percentages are counted from deliverables with evidence in `docs/evidence/tsmp-21/` or in CI.
They are not estimates. Preparation work (protocols, tools) does not change an activity's
status. Only executed evidence does.

## Summary

| Measure | Value |
|---|---|
| TSMP-21 activities | **80%**: 7 complete, 2 partial (half credit), 1 blocked, out of 10. Unchanged by the 6 Nov work: portability still lacks Windows, and usability is still blocked |
| TSMP-21 acceptance criteria (MLE-21) | 2 of 4 met (≥ 90% pass; results recorded). Not met: 100% of High requirements, no open High defect |
| TSMP-22 traceability | **46 / 48 (96%)** requirements have every link their SRS method requires; 36 / 48 have every column filled (was 35) |
| TSMP-22 validation result | 41 verified, 5 partial, 1 not verified, 1 not implemented (85% verified). Unchanged |
| STP planned cases (80) | 75 pass, 4 fail, 1 blocked (93.75%) |
| pytest (6 Nov) | 388 collected: **381 pass, 7 strict xfail** (DEF-05 ×5, DEF-06, DEF-09), 0 fail; coverage 97.34% |
| Other automated checks | Docker containment 9, live system 15, browser 21 (Chrome, Firefox, Edge × 7), CI smoke 3, macOS portability check 3 smoke |
| Documentation consistency | `check_rtm.py` PASS: 48 requirements, 51 source paths, 184 test references, 13 defects, 46 evidence files |
| Open defects | 1 High (DEF-07), 0 Critical; Medium DEF-05, DEF-09, DEF-12; Low DEF-06, DEF-10 |
| Latest CI | See the change log below |

## TSMP-21 activities

| Activity | Status | Evidence | Remaining |
|---|---|---|---|
| Regression | COMPLETE | `pytest-core-2026-11-06.log` (381 pass), 47 test cases added on 6 Nov | - |
| Security ST-SEC-01..13 | COMPLETE | 13/13; plus `test_tsmp21_sec009.py` (12 pass, HTTPS strict xfail) and the gitleaks scan, now in CI | - |
| Performance PERF-01..03 | COMPLETE | `perf01_*`, `system-results.json` | Caveat: one host, development server |
| Concurrency PERF-04 | COMPLETE | `system-results.json` | Caveat: 3 worker slots |
| Reliability REL-01 | COMPLETE | `system-results.json` | - |
| Usability USA-01 | BLOCKED | Protocol, scenarios, templates and kit generator prepared (`TSMP-21_USABILITY_PROTOCOL.md`). Not executed | MLE-17 UI and five participants |
| Portability PORT-01 / NFR-008 | PARTIAL | macOS and Ubuntu Compose; Chrome, Firefox and Edge 7/7 each (macOS); `portability_check.py` | Windows (Docker Desktop) |
| Retention RET-01 | COMPLETE | `test_tsmp21_retention.py`, `system-results.json` | - |
| High/Critical defects | PARTIAL | DEF-01, DEF-02 closed | DEF-07 (teammates, MLE-17) |
| Retest of fixed defects | COMPLETE | 7/7 closed defects retested | - |
| UI system tests | BLOCKED | API path passes | Rerun after MLE-17 |

## TSMP-22 deliverables

| Deliverable | Status | Notes |
|---|---|---|
| RTM rows (48) | COMPLETE | New regression and SEC-009 tests linked to their requirements on 6 Nov |
| Automated consistency check | COMPLETE | `scripts/validation/check_rtm.py`, run in CI `core-tests` and `tooling-cross-os`; 9 tests prove it catches broken documents |
| Defect-to-requirement table | COMPLETE | 13/13, statuses checked against the register automatically |
| Full chain for every requirement | PARTIAL | NFR-005: no source (no frontend on any branch, checked 6 Nov). NFR-004: no executed test (no operating window, no uptime records) |
| Validation report | COMPLETE | Updated 6 Nov |

## Change log

### 6 November 2026 (second pass)

- **Regression tests:** `tests/test_tsmp21_regression.py`, 16 cases picked from the 83 uncovered
  lines (FR-001, FR-003, FR-004, FR-007..FR-011, SEC-004, SEC-006). Coverage 96.37% → 97.34%. No
  product code changed. One wrong test assumption was found and corrected; it was not a defect.
- **SEC-009:** `tests/test_tsmp21_sec009.py`, 13 cases. 12 pass (secrets from the environment,
  placeholders, Compose, `.env` untracked, secure defaults, no CORS grant, CI scans). One strict
  xfail tracks DEF-09 (HTTPS). SEC-009 stays PARTIAL.
- **Edge:** Microsoft Edge 157 installed with Homebrew and run: 7/7 PASS on the second
  attempt. The first attempt failed in the harness before any check ran; it is kept as evidence.
- **Usability:** `docs/TSMP-21_USABILITY_PROTOCOL.md`, `docs/usability/` (observation sheet with
  SUS, results and issue CSV templates), `scripts/validation/usability/make_kit.py`. No session
  run; no result claimed.
- **Portability:** `scripts/validation/portability_check.py`, which runs PORT-01 on any OS. macOS
  run: all required checks and 3/3 smoke PASS (`port01-macos-portability-check.json`). It is now
  used by CI `compose-smoke`.
- **NFR-004:** no monitoring evidence exists in the repository. `scripts/validation/availability_probe.py`
  added and tested. It was self-checked against the local stack, up (100%) and with the API
  stopped (0%). Those runs are not NFR-004 evidence and are not committed.
- **NFR-005:** no frontend on any branch or pull request; `/results` makes no register or upload
  calls. It stays NOT IMPLEMENTED.
- **RTM checker:** `scripts/validation/check_rtm.py` plus `tests/test_tsmp22_rtm_checker.py`. The
  first CI run showed the checker counted the gitignored local `coverage.xml` as evidence, so it
  passed locally but failed in CI. Fixed: it now only accepts files that are in the repository,
  and a regression test covers this.
- **CI:** `core-tests` now lints `scripts` and runs the RTM checker. `security-scan` adds a gitleaks
  full-history scan. `compose-smoke` uses `portability_check.py`. A new `tooling-cross-os` job
  (Windows and macOS) checks that the validation tools run there. It is not PORT-01.

### 6 November 2026 (first pass)

- DEF-08 figures corrected; DEF-13 added to the RTM; `coverage.xml` reference corrected; CI run
  41868670661 recorded; gitleaks scan; Firefox 7/7; consistency fixes (see commit `719602c`).

## Remaining blockers

| Blocker | Blocks | Owner |
|---|---|---|
| DEF-07: MLE-17 React SPA not implemented | USA-01, NFR-005, the 4 UI system tests; FR-005 and FR-014 stay PARTIAL; MLE-21 exit criteria | M2 + M4 |
| Five first-time participants | USA-01 (after MLE-17) | Team (STP owners M2 and M4) |
| DEF-05: evaluator cannot open member evaluations | BR-05; 5 strict xfails | M1, M3, M4 |
| DEF-06: ADMIN superset role vs STP 11.1 | 1 strict xfail | Team decision |
| DEF-09: development server, no HTTPS | SEC-009 PARTIAL; 1 strict xfail | Team sign-off (deployment change) |
| DEF-12: evaluation delete keeps uploads | FR-006 wording | Team decision |
| DEF-10: SonarQube gate | NFR-007 PARTIAL | Team / course infrastructure |
| Windows host with Docker Desktop | NFR-008 PARTIAL | Any teammate with Windows: `portability_check.py --fresh --up --smoke` |
| Defined operating window | NFR-004 NOT VERIFIED | Team, then run `availability_probe.py` for the window |
| PR review and merge | Work is not on `main` | Ayush (open PR), module owners (review) |
