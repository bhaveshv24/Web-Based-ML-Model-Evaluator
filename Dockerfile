FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN addgroup --system app && adduser --system --ingroup app app
WORKDIR /app

COPY pyproject.toml README.md ./
COPY backend ./backend
COPY manage.py ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir '.[runtime]'

USER app
EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
