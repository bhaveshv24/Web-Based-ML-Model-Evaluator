# Sandbox image for untrusted model execution (FR-016, SEC-005, SAD 5.1).
# Build:  docker build -t ml-evaluator-sandbox:1.0 sandbox/
# For production, pin the base image by digest (python:3.11-slim-bookworm@sha256:...).
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY requirements.txt /opt/runner/requirements.txt
RUN pip install --no-cache-dir -r /opt/runner/requirements.txt \
    && pip uninstall -y pip setuptools wheel \
    && groupadd --gid 10001 sandbox \
    && useradd --uid 10001 --gid 10001 --no-create-home --home-dir /nonexistent \
       --shell /usr/sbin/nologin sandbox

COPY runner.py /opt/runner/runner.py
RUN chmod 0444 /opt/runner/runner.py /opt/runner/requirements.txt && chmod 0555 /opt/runner

# The worker also passes --user 10001:10001 and verifies it; this is the image default.
USER 10001:10001
WORKDIR /tmp
ENTRYPOINT ["python", "-I", "-B", "/opt/runner/runner.py"]
