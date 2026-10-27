# Web-Based ML Model Evaluator

Team 13's Software Engineering Level 3 mini-project: a secure browser-based application that evaluates already-trained tabular ML models against a CSV test dataset, presents trusted metrics and charts, compares models on the same dataset, and exports PDF/JSON reports.

## Project baseline

The approved Version 1 scope supports scikit-learn (`.pkl`, `.joblib`) and ONNX (`.onnx`) model artifacts, classification and regression CSV datasets, JWT authentication/RBAC, evaluation history, isolated Docker execution, model comparison, and report export. Model training, GPU inference, deep-learning frameworks, and image/video/NLP pipelines are out of scope.

The repository follows the approved four-module ownership model:

| Module | Functional area | Owner |
|---|---|---|
| M1 | Authentication and Workspace Management | Atharva Anand |
| M2 | Dataset Ingestion and Schema Pre-Validation | Atharva Rakesh Bidre |
| M3 | Sandboxed Model Execution and Metrics Engine | Ayush M Shetty |
| M4 | Model Benchmarking, Visual Analytics and Report Export | Bhavesh Velluru |

## Current increment

This foundation increment adds executable, dependency-light domain services for:

- model filename/size/signature validation;
- CSV header, duplicate-column, row-limit and missing-feature checks;
- task-type detection;
- trusted classification and regression metrics;
- comparison guards and best-per-metric selection;
- sanitized failure messages;
- a requirements-to-sprint Jira backlog and CI quality gate.

The domain services remain dependency-light, while the M1 increment now adds a Django REST API for secure JWT authentication, private evaluation history and evaluator workspaces. PostgreSQL and Redis are wired through Docker Compose; SQLite remains available for isolated tests and local development.

## M1 API

The versioned endpoints implemented for MLE-02 through MLE-04 are:

- `POST /api/v1/auth/register`, `/auth/login`, `/auth/token/refresh`, `/auth/logout`
- `GET /api/v1/evaluations` with `status`, `task_type`, `from`, `to` and `page` filters
- `GET` or `DELETE /api/v1/evaluations/{id}` with owner-only object access
- `GET` or `POST /api/v1/workspaces` for EVALUATOR/ADMIN accounts
- `POST /api/v1/workspaces/{id}/members` and `GET /api/v1/workspaces/{id}/evaluations`

Access JWTs expire after 15 minutes. Refresh JWTs expire after seven days, rotate on refresh and are blacklisted after rotation or logout. Login is limited to five attempts per minute for each IP/email combination.

## Run the tests

```bash
python3 -m pytest -q
```

Install the development dependencies first with `python3 -m pip install -e '.[dev]'`.

## Run the API with Docker Compose

```bash
cp .env.example .env
# Replace both placeholder secrets in .env before starting the stack.
docker compose up --build
```

The Compose topology is `api -> PostgreSQL` for persistence and `api -> Redis` for the scheduled Celery/evaluation layer. Secrets are read from `.env`, which is ignored by Git and must never be committed.

## Planned runtime stack

- React + Vite + TypeScript + Tailwind + Recharts
- Django + Django REST Framework + SimpleJWT
- Celery + Redis
- PostgreSQL 15
- Docker Compose and a hardened per-job sandbox container
- ReportLab, GitHub Actions, SonarQube-compatible coverage, Postman/Newman

See [docs/JIRA_BACKLOG.md](docs/JIRA_BACKLOG.md) for the three Jira delivery sprints and the mapping back to the six two-week academic sprints in the approved SRS/SAD/STP.

## Security boundary

Pickle and joblib uploads are executable content. They must never be imported or unpickled by the web process. Compatibility inspection and prediction run only in the locked-down sandbox described by SEC-005; ground-truth labels and metric computation remain outside that container.

