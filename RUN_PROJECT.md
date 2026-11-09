# Run the project

## On this Mac

Open Docker Desktop and wait until its engine is running. The private `.env` is already
configured on this machine and is ignored by Git. It selects the existing
`mle-finalization` Compose project so its database and uploads are reused.

```bash
cd /Users/bvell/Documents/GitHub/Web-Based-ML-Model-Evaluator
docker compose up --build -d
```

Wait for startup/migrations, then open **http://localhost:5173**. Register a normal account
or sign in. Upload a compatible trained model and CSV, select the target, run the
compatibility check and start evaluation. Results, comparisons and downloads are in the
web application. Docker runs its supporting services and isolated model execution.

```bash
docker compose ps
docker compose logs --tail=100 api worker frontend
```

## Stop it

```bash
docker compose down
```

Database and uploaded-file volumes are preserved. Do not add `-v` unless you intend to
delete that project's persisted data. Docker Desktop can keep unrelated projects running.

## First setup on another machine

Install Docker Desktop (or Docker Engine plus Compose on Linux), start it, clone the
repository and open a terminal in its root. Copy `.env.example` to `.env` and replace both
secret placeholders with independent random values before startup. Never commit `.env`.

```bash
cp .env.example .env
```

On macOS/Linux the example uses `${PWD}/sandbox-jobs`; run Compose from the repository
root. On Windows set `SANDBOX_HOST_WORK_DIR` to an absolute path shared with Docker
Desktop, such as `C:/Users/you/ml-evaluator-jobs`. Then run:

```bash
docker compose up --build -d
```

The Compose stack builds the frontend, API/worker and sandbox image, initializes the job
folder, applies migrations and starts its database/queue/scheduler. A separate Python or
Node installation is unnecessary for this Docker startup. Full Windows/browser validation
remains subject to the limitations recorded in the final checklist.

Use **http://localhost:5173** for the app. Port 8000 is the API, and `/results` there is an
earlier dashboard. The optional HTTPS deployment is documented in README.

## Supported demo inputs

Models: `.pkl`, `.joblib` or `.onnx`, at most 100 MiB. CSV: at most 50 MiB / 500,000 rows,
with matching feature schema and the correct selected target. Use models compatible with
the pinned sandbox dependencies (scikit-learn 1.5.2 / ONNX Runtime 1.19.2). The application
evaluates trained models; it does not train them.

If ports 5173/8000 are occupied, check `docker ps` before starting a duplicate stack. If a
job fails, inspect the worker log and confirm Docker/sandbox readiness; never load an
unknown uploaded pickle directly in the web process to bypass isolation.
