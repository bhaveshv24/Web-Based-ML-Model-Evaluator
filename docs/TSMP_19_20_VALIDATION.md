# TSMP-19 / TSMP-20 validation record

## Requirements and executable evidence

| Case | Requirement | Check | Result available now |
| --- | --- | --- | --- |
| PERF-01 | NFR-001: 50 users, five minutes, p95 API latency <=500 ms, errors <1% | `scripts/performance/locustfile.py`, `check_load.py`, deployed Compose stack | Linux CI workflow; see its `sprint-3-performance` artifact |
| PERF-02 | NFR-002: 10,000 rows x 50 features, model >=20 MiB, job <=60 s | `scripts/performance/run_evaluations.py` measures server job duration | Linux CI workflow |
| PERF-03 | NFR-011: validate exactly 50 MiB CSV <=20 s | `scripts/performance/csv_50mb.py` | Local macOS Python 3.12: 52,428,800 bytes, 104,438 rows, 0.583 s, pass |
| PERF-04 | NFR-003: five jobs keep distinct results | `scripts/performance/run_evaluations.py` compares each concurrent result to its single-run baseline | Linux CI workflow |
| REL-01 | NFR-006: stale RUNNING job and orphan container recover within five minutes | `scripts/performance/crash_cleanup.py` injects the state, SIGKILLs/restarts worker, checks row/container | Linux CI workflow |
| PORT-01 | NFR-008: one Compose startup | `.github/workflows/performance.yml` builds and starts API, frontend, worker and sandbox, then checks browser route and auth API | Linux CI workflow; a second-OS installation still requires an actual Docker host |
| RET-01 | NFR-010: stored files older than 30 days removed | Daily Celery task and `tests/test_retention.py` age files to 31 days, check bytes and references | 2 local integration tests passed |
| CI gate | NFR-007: >=80% backend lines and no critical/blocker static findings | `ci.yml`: Ruff, Bandit, pip-audit, migrations, pytest coverage | Local: 267 passed, 10 infrastructure skips, 96.20% backend lines; Bandit high severity and pip-audit clean |

The approved SRS states **30 days** for retention; RET-01 checks files at day 31.
Evaluation history and checksum snapshots remain after upload files expire. Active
QUEUED/RUNNING jobs keep their inputs until a later daily purge. Generated JSON/PDF
downloads are rendered on demand; only file-backed `Report` rows need physical deletion.

The local 10 skipped tests require Docker or Redis. Their local skip does not count as
passing evidence. The Linux workflow performs the deployed checks; it requires a passing
run and review before the corresponding issues can be closed. The script's REL-01 setup
injects a stale database row and orphan container to exercise recovery after worker
termination; it does not originate from a naturally interrupted evaluation.

## Reproduce deployed validation

1. Configure `.env` from `.env.example` and run `docker compose up --build -d`.
2. Run `docker compose exec -T -e PERF_PASSWORD api python scripts/performance/seed_load.py`.
3. Run `PYTHONPATH=backend python scripts/performance/csv_50mb.py` and
   `python scripts/performance/run_evaluations.py` with `PERF_PASSWORD` set.
4. Run `locust -f scripts/performance/locustfile.py --headless -u 50 -r 10 -t 5m --host http://localhost:5173 --csv perf-load`, then
   `python scripts/performance/check_load.py perf-load_stats.csv`.
5. Run `python scripts/performance/crash_cleanup.py` on the disposable stack.

Use `WORKER_CONCURRENCY=5` for PERF-04. The CI workflow sets this and saves machine-readable
results. On a second operating system, record the OS, Docker/Compose versions, the startup
command, frontend/API smoke results and any failure before marking PORT-01 complete.
