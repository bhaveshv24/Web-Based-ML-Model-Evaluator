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

These services are intentionally independent of Django, PostgreSQL and Docker so they satisfy NFR-009 and can be tested in CI. The Django REST, Celery/Redis, sandbox, React and report layers are layered onto these services in the planned sprints.

## Run the tests

```bash
python3 -m pytest -q
```

The test suite uses only the Python standard library plus `pytest`.

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

