"""REL-01: inject a stale RUNNING row and orphan container, then kill/restart the worker."""

import json
import subprocess
import sys
import time
import uuid


def command(*parts):
    return subprocess.run(parts, check=True, capture_output=True, text=True).stdout.strip()


def django(expression):
    return command("docker", "compose", "exec", "-T", "api", "python", "manage.py",
                   "shell", "-c", expression)


def main():
    job_id = str(uuid.uuid4())
    create = (
        "import uuid; from datetime import timedelta; from django.utils import timezone; "
        "from accounts.models import User; from evaluations.models import Evaluation; "
        "owner=User.objects.get(email='perf-0@example.test'); "
        f"Evaluation.objects.create(id=uuid.UUID('{job_id}'), owner=owner, status='RUNNING', "
        "started_at=timezone.now()-timedelta(seconds=200), run_token=uuid.uuid4())"
    )
    django(create)
    command("docker", "run", "-d", "--name", f"ml-evaluator-orphan-{job_id}",
            "--network", "none", "--label", f"ml-evaluator.job={job_id}",
            "--entrypoint", "sleep", "ml-evaluator-sandbox:1.0", "3600")
    started = time.monotonic()
    try:
        command("docker", "compose", "kill", "-s", "SIGKILL", "worker")
        command("docker", "compose", "up", "-d", "worker")
        deadline = started + 240
        while time.monotonic() < deadline:
            status = django(
                "from evaluations.models import Evaluation; "
                f"print(Evaluation.objects.get(id='{job_id}').status)"
            ).splitlines()[-1]
            containers = command("docker", "ps", "-aq", "--filter",
                                 f"label=ml-evaluator.job={job_id}")
            if status == "FAILED" and not containers:
                print(json.dumps({"case": "REL-01", "job_id": job_id,
                                  "status": status, "orphan_containers": 0,
                                  "recovered_seconds": round(time.monotonic()-started, 1),
                                  "passed": True}, indent=2))
                return 0
            time.sleep(5)
        raise AssertionError(f"recovery missed deadline: status={status}, container={containers}")
    finally:
        subprocess.run(["docker", "rm", "-f", f"ml-evaluator-orphan-{job_id}"],
                       capture_output=True, check=False)


if __name__ == "__main__":
    sys.exit(main())
