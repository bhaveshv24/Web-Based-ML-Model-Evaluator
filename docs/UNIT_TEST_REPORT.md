# Unit Test Report

Team 13 | 9 November 2026 | Final verification on main

The source-file hashes are recorded in [source-manifest.json](evidence/final/source-manifest.json). Raw outputs identify the actual environments and execution times.

## Result

121 passed, 0 failures, 0 errors and 0 skipped. Runtime 10.402 seconds. This is the dedicated unit/service subset.

## Scope and method

Pytest executed pure metric, task-detection, validation, comparison and sandbox-policy/runner tests. Policy tests use a simulated daemon; runner-script tests use trusted generated model fixtures. Real Docker, HTTP and database integration checks are reported separately in the system/full-suite report.

| Test file | Cases | Outcome |
| --- | --- | --- |
| tests.test_comparison_security | 4 | PASS |
| tests.test_ingestion | 16 | PASS |
| tests.test_metric_engine | 40 | PASS |
| tests.test_metrics | 4 | PASS |
| tests.test_sandbox_policy | 44 | PASS |
| tests.test_sandbox_runner_script | 13 | PASS |

## Evidence and reproduction

[JUnit XML](evidence/final/unit-junit.xml), [console log](evidence/final/unit.log).

Run `pytest tests/test_metrics.py tests/test_metric_engine.py tests/test_ingestion.py tests/test_comparison_security.py tests/test_sandbox_policy.py tests/test_sandbox_runner_script.py --junitxml=unit-junit.xml`. One upstream SciPy deprecation warning was recorded.
