FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend

# Fixed UID so the host-side sandbox job directory can be owned by the worker user.
RUN addgroup --system --gid 10002 app && adduser --system --uid 10002 --ingroup app app
WORKDIR /app
RUN install -d -o app -g app -m 0750 /app/media

COPY pyproject.toml README.md ./
COPY backend ./backend
COPY scripts ./scripts
COPY manage.py ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir '.[runtime]'

USER app
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4", "--threads", "4", "--timeout", "120"]
