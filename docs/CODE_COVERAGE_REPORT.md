# Code Coverage Report

Current task allocation: [Team ownership](TEAM_OWNERSHIP.md). Primary owners are Anand (01-04, 19-20), Bidre (05-08, 17-18), Ayush (09-12, 21-22), Bhavesh (13-16, 23-24). Module support and historical authorship remain distinct.


Team 13 | 9 November 2026 | Final verification on main

The source-file hashes are recorded in [source-manifest.json](evidence/final/source-manifest.json). Raw outputs identify the actual environments and execution times.

## Backend line coverage

**97.36%** = 2321 covered / 2384 executable lines. 63 lines were missed. The 80% backend line target passes.

The full branch-enabled suite passed 416 tests with zero failures, errors,
skips or expected failures. Coverage.py reports **96.50% combined
line-and-branch coverage**. That combined number is distinct from the line percentage above.

## Per-file line measurement

| Source file | Covered lines | Executable lines | Line coverage |
| --- | --- | --- | --- |
| backend/accounts/__init__.py | 0 | 0 | 100.00% |
| backend/accounts/apps.py | 4 | 4 | 100.00% |
| backend/accounts/managers.py | 16 | 16 | 100.00% |
| backend/accounts/migrations/0001_initial.py | 9 | 9 | 100.00% |
| backend/accounts/migrations/__init__.py | 0 | 0 | 100.00% |
| backend/accounts/models.py | 30 | 30 | 100.00% |
| backend/accounts/permissions.py | 18 | 18 | 100.00% |
| backend/accounts/serializers.py | 52 | 52 | 100.00% |
| backend/accounts/throttles.py | 9 | 9 | 100.00% |
| backend/accounts/urls.py | 3 | 3 | 100.00% |
| backend/accounts/views.py | 74 | 74 | 100.00% |
| backend/benchmarking/__init__.py | 0 | 0 | 100.00% |
| backend/benchmarking/comparison.py | 38 | 38 | 100.00% |
| backend/benchmarking/pdf.py | 90 | 91 | 98.90% |
| backend/benchmarking/reports.py | 18 | 19 | 94.74% |
| backend/benchmarking/urls.py | 4 | 4 | 100.00% |
| backend/benchmarking/views.py | 63 | 63 | 100.00% |
| backend/config/__init__.py | 2 | 2 | 100.00% |
| backend/config/celery.py | 6 | 6 | 100.00% |
| backend/config/exceptions.py | 21 | 23 | 91.30% |
| backend/config/settings.py | 67 | 68 | 98.53% |
| backend/config/urls.py | 4 | 4 | 100.00% |
| backend/config/wsgi.py | 0 | 4 | 0.00% |
| backend/evaluations/__init__.py | 0 | 0 | 100.00% |
| backend/evaluations/apps.py | 6 | 6 | 100.00% |
| backend/evaluations/audit.py | 12 | 12 | 100.00% |
| backend/evaluations/errors.py | 33 | 33 | 100.00% |
| backend/evaluations/executor.py | 111 | 118 | 94.07% |
| backend/evaluations/inputs.py | 71 | 76 | 93.42% |
| backend/evaluations/metrics/__init__.py | 4 | 4 | 100.00% |
| backend/evaluations/metrics/classification.py | 30 | 30 | 100.00% |
| backend/evaluations/metrics/engine.py | 84 | 87 | 96.55% |
| backend/evaluations/metrics/predictions.py | 79 | 79 | 100.00% |
| backend/evaluations/metrics/regression.py | 14 | 15 | 93.33% |
| backend/evaluations/metrics/roc.py | 28 | 29 | 96.55% |
| backend/evaluations/migrations/0001_initial.py | 8 | 8 | 100.00% |
| backend/evaluations/migrations/0002_evaluation_lifecycle.py | 6 | 6 | 100.00% |
| backend/evaluations/migrations/0003_comparison.py | 7 | 7 | 100.00% |
| backend/evaluations/migrations/0004_evaluationartifact_created_at_report_created_at.py | 9 | 10 | 90.00% |
| backend/evaluations/migrations/__init__.py | 0 | 0 | 100.00% |
| backend/evaluations/models.py | 65 | 66 | 98.48% |
| backend/evaluations/reaper.py | 38 | 40 | 95.00% |
| backend/evaluations/retention.py | 4 | 4 | 100.00% |
| backend/evaluations/sandbox/__init__.py | 7 | 7 | 100.00% |
| backend/evaluations/sandbox/base.py | 54 | 55 | 98.18% |
| backend/evaluations/sandbox/docker_runner.py | 129 | 139 | 92.81% |
| backend/evaluations/sandbox/workspace.py | 120 | 133 | 90.23% |
| backend/evaluations/security.py | 8 | 8 | 100.00% |
| backend/evaluations/serializers.py | 25 | 25 | 100.00% |
| backend/evaluations/services.py | 77 | 78 | 98.72% |
| backend/evaluations/signals.py | 10 | 10 | 100.00% |
| backend/evaluations/task_detection.py | 79 | 83 | 95.18% |
| backend/evaluations/tasks.py | 24 | 26 | 92.31% |
| backend/evaluations/urls.py | 3 | 3 | 100.00% |
| backend/evaluations/views.py | 97 | 97 | 100.00% |
| backend/ingestion/__init__.py | 0 | 0 | 100.00% |
| backend/ingestion/apps.py | 6 | 6 | 100.00% |
| backend/ingestion/compatibility.py | 31 | 31 | 100.00% |
| backend/ingestion/inspection.py | 28 | 28 | 100.00% |
| backend/ingestion/management/__init__.py | 0 | 0 | 100.00% |
| backend/ingestion/management/commands/__init__.py | 0 | 0 | 100.00% |
| backend/ingestion/management/commands/purge_expired.py | 7 | 7 | 100.00% |
| backend/ingestion/migrations/0001_initial.py | 9 | 9 | 100.00% |
| backend/ingestion/migrations/__init__.py | 0 | 0 | 100.00% |
| backend/ingestion/models.py | 46 | 46 | 100.00% |
| backend/ingestion/retention.py | 33 | 33 | 100.00% |
| backend/ingestion/signals.py | 10 | 10 | 100.00% |
| backend/ingestion/tasks.py | 5 | 5 | 100.00% |
| backend/ingestion/urls.py | 3 | 3 | 100.00% |
| backend/ingestion/validators.py | 139 | 140 | 99.29% |
| backend/ingestion/views.py | 136 | 137 | 99.27% |
| backend/workspaces/__init__.py | 0 | 0 | 100.00% |
| backend/workspaces/apps.py | 4 | 4 | 100.00% |
| backend/workspaces/migrations/0001_initial.py | 8 | 8 | 100.00% |
| backend/workspaces/migrations/__init__.py | 0 | 0 | 100.00% |
| backend/workspaces/models.py | 17 | 17 | 100.00% |
| backend/workspaces/serializers.py | 29 | 29 | 100.00% |
| backend/workspaces/urls.py | 3 | 3 | 100.00% |
| backend/workspaces/views.py | 37 | 37 | 100.00% |

## Method and evidence

Run `REQUIRE_DOCKER_TESTS=1 REQUIRE_REDIS_TESTS=1 pytest --cov=backend --cov-branch --cov-report=xml --cov-report=json --junitxml=junit.xml --cov-fail-under=80`. Measurement includes backend configuration and migrations as reported by the tool.

[Coverage XML](evidence/final/coverage.xml), [full JUnit XML](evidence/final/junit.xml), [console log](evidence/final/pytest.log). XML source paths were made relative to `backend` for portability without changing measured counts.
