# Branch Coverage Report

Team 13 | 9 November 2026 | Final verification on main

The source-file hashes are recorded in [source-manifest.json](evidence/final/source-manifest.json). Raw outputs identify the actual environments and execution times.

## Backend branch coverage

**92.67%** = 493 covered / 532 branch destinations.
There are 39 missed destinations and 37
partially exercised branch lines. These are measured gaps; the report does not claim 100%.

## Files with branch destinations

| Source file | Covered destinations | Total destinations | Branch coverage |
| --- | --- | --- | --- |
| backend/accounts/managers.py | 2 | 2 | 100.00% |
| backend/accounts/permissions.py | 4 | 4 | 100.00% |
| backend/accounts/serializers.py | 4 | 4 | 100.00% |
| backend/accounts/views.py | 8 | 8 | 100.00% |
| backend/benchmarking/comparison.py | 16 | 16 | 100.00% |
| backend/benchmarking/pdf.py | 39 | 40 | 97.50% |
| backend/benchmarking/reports.py | 3 | 4 | 75.00% |
| backend/benchmarking/views.py | 6 | 6 | 100.00% |
| backend/config/exceptions.py | 12 | 14 | 85.71% |
| backend/config/settings.py | 1 | 2 | 50.00% |
| backend/evaluations/errors.py | 2 | 2 | 100.00% |
| backend/evaluations/executor.py | 21 | 24 | 87.50% |
| backend/evaluations/inputs.py | 21 | 22 | 95.45% |
| backend/evaluations/metrics/classification.py | 8 | 8 | 100.00% |
| backend/evaluations/metrics/engine.py | 19 | 22 | 86.36% |
| backend/evaluations/metrics/predictions.py | 44 | 44 | 100.00% |
| backend/evaluations/metrics/regression.py | 1 | 2 | 50.00% |
| backend/evaluations/metrics/roc.py | 11 | 12 | 91.67% |
| backend/evaluations/migrations/0004_evaluationartifact_created_at_report_created_at.py | 3 | 4 | 75.00% |
| backend/evaluations/models.py | 2 | 2 | 100.00% |
| backend/evaluations/reaper.py | 10 | 12 | 83.33% |
| backend/evaluations/sandbox/base.py | 8 | 8 | 100.00% |
| backend/evaluations/sandbox/docker_runner.py | 28 | 32 | 87.50% |
| backend/evaluations/sandbox/workspace.py | 30 | 38 | 78.95% |
| backend/evaluations/services.py | 13 | 14 | 92.86% |
| backend/evaluations/signals.py | 1 | 2 | 50.00% |
| backend/evaluations/task_detection.py | 32 | 36 | 88.89% |
| backend/evaluations/views.py | 30 | 30 | 100.00% |
| backend/ingestion/compatibility.py | 6 | 6 | 100.00% |
| backend/ingestion/inspection.py | 4 | 4 | 100.00% |
| backend/ingestion/retention.py | 12 | 12 | 100.00% |
| backend/ingestion/signals.py | 1 | 2 | 50.00% |
| backend/ingestion/validators.py | 66 | 68 | 97.06% |
| backend/ingestion/views.py | 23 | 24 | 95.83% |
| backend/workspaces/serializers.py | 2 | 2 | 100.00% |

## Method and interpretation

The same final full-suite run enabled `--cov-branch`. A branch destination is an outgoing path measured by coverage.py, including exceptional and defensive paths. No separate branch threshold was specified in the course Part 3 handout. The repository enforces an 80% combined gate and separately reports the required line target.

[Coverage XML](evidence/final/coverage.xml) contains per-line condition coverage. [Full-suite log](evidence/final/pytest.log) lists missed paths.
