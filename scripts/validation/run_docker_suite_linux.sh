#!/usr/bin/env bash
# TSMP-21: run the real-Docker containment suite from a Linux container on the Docker host.
#
# On macOS (Docker Desktop / Colima) the host's /tmp is not shared with the Docker VM, so the
# suite's /tmp job directories would be empty inside the sandbox. Running pytest in a Linux
# container that shares the VM's /tmp and Docker socket gives the same path on both sides,
# which is the production layout (Linux Docker host). On a Linux host, run the suite directly:
#   REQUIRE_DOCKER_TESTS=1 pytest -m docker -v
set -euo pipefail
repo="$(cd "$(dirname "$0")/../.." && pwd)"
out="${1:-$repo/docs/evidence/tsmp-21/docker-suite-linux.log}"
docker image inspect ml-evaluator-sandbox:1.0 >/dev/null
# --pid=host: IT-EXE-05 uses pgrep to prove the model's child processes died; it must see the
# Docker host's process table, not only this container's.
docker run --rm --pid=host \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /tmp:/tmp \
  -v "$repo":/src:ro \
  python:3.11-slim bash -c '
    set -euo pipefail
    apt-get update -qq && apt-get install -y -qq procps >/dev/null
    cp -r /src /work && cd /work && rm -rf .venv *.egg-info
    pip install -q --root-user-action=ignore -e ".[dev]" 2>&1 | grep -v notice || true
    python --version; uname -sr
    REQUIRE_DOCKER_TESTS=1 pytest -m docker -v -rs -p no:cacheprovider
  ' 2>&1 | tee "$out"
test -z "$(docker ps -aq --filter label=ml-evaluator.job)" && echo "No sandbox containers left behind." | tee -a "$out"
