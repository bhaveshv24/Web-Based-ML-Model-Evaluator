"""Per-job input workspace (FR-016, SEC-005, BR-06, NFR-006).

Each job gets a fresh directory with an unguessable name that is mounted read-only into its
own container and nowhere else. Only the model copy and the feature matrix X are written
there; ground-truth labels never are. Files are copied from the media volume with symlink,
containment, size and checksum checks, so a tampered or swapped upload cannot redirect the
worker to other files. Cleanup is idempotent.
"""

from __future__ import annotations

import errno
import hashlib
import logging
import os
import secrets
import shutil
import stat
import sys
from contextlib import contextmanager
from pathlib import Path

from django.conf import settings

from ..errors import ErrorCode, EvaluationError

logger = logging.getLogger("evaluations.sandbox")

MODEL_FILENAMES = {".pkl": "model.pkl", ".joblib": "model.joblib", ".onnx": "model.onnx"}
FEATURES_FILENAME = "X.csv"
ALLOWED_NAMES = frozenset({*MODEL_FILENAMES.values(), FEATURES_FILENAME})
COPY_CHUNK = 1024 * 1024
DIR_MODE = 0o711  # sandbox user may traverse but not list; it only opens known names
FILE_MODE = 0o644


def _input_error(detail: str) -> EvaluationError:
    return EvaluationError(ErrorCode.INVALID_INPUT, detail)


@contextmanager
def open_trusted(source: Path, *, allowed_root: Path, max_bytes: int):
    """Open an uploaded file only if it is a regular, non-symlinked file inside allowed_root."""
    root = allowed_root.resolve()
    try:
        resolved = source.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise _input_error("A stored input file is missing.") from exc
    if not resolved.is_relative_to(root):
        raise _input_error("A stored input file is outside the upload area.")
    try:
        fd = os.open(source, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise _input_error("A stored input file is a symbolic link.") from exc
        raise _input_error("A stored input file could not be opened.") from exc
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise _input_error("A stored input is not a regular file.")
        if info.st_size > max_bytes:
            raise _input_error("A stored input file exceeds the size limit.")
        yield handle


def read_trusted(source: Path, *, allowed_root: Path, max_bytes: int, sha256: str) -> bytes:
    with open_trusted(source, allowed_root=allowed_root, max_bytes=max_bytes) as handle:
        content = handle.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise _input_error("A stored input file exceeds the size limit.")
    if sha256 and hashlib.sha256(content).hexdigest() != sha256:
        raise _input_error("A stored input file failed its integrity check.")
    return content


class JobWorkspace:
    def __init__(self, path: Path, host_path: Path, base: Path) -> None:
        self.path = path
        self.host_path = host_path
        self._base = base

    @classmethod
    def create(cls, job_id: str) -> JobWorkspace:
        base = Path(settings.SANDBOX_WORK_DIR)
        base.mkdir(parents=True, exist_ok=True)
        if base.is_symlink():
            raise EvaluationError(ErrorCode.SANDBOX_UNAVAILABLE, "Workspace root is unsafe.")
        name = f"{job_id}-{secrets.token_hex(8)}"
        path = base / name
        os.mkdir(path, 0o700)  # fails if it exists: no two jobs ever share a directory
        os.chmod(path, DIR_MODE)
        host_path = Path(settings.SANDBOX_HOST_WORK_DIR) / name
        logger.info("job=%s workspace created", job_id)
        return cls(path, host_path, base.resolve())

    def _target(self, name: str) -> Path:
        if name not in ALLOWED_NAMES:
            raise ValueError("Unexpected workspace file name")
        return self.path / name

    def _create_file(self, name: str):
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(self._target(name), flags, 0o600)
        os.fchmod(fd, FILE_MODE)
        return os.fdopen(fd, "wb")

    def stage_copy(
        self, source: Path, name: str, *, allowed_root: Path, max_bytes: int, sha256: str
    ) -> Path:
        """Copy an upload into the workspace, verifying size and SHA-256 while copying."""
        digest = hashlib.sha256()
        copied = 0
        with open_trusted(source, allowed_root=allowed_root, max_bytes=max_bytes) as src:
            with self._create_file(name) as dst:
                while chunk := src.read(COPY_CHUNK):
                    copied += len(chunk)
                    if copied > max_bytes:
                        raise _input_error("A stored input file exceeds the size limit.")
                    digest.update(chunk)
                    dst.write(chunk)
        if sha256 and digest.hexdigest() != sha256:
            raise _input_error("A stored input file failed its integrity check.")
        return self._target(name)

    def write_bytes(self, name: str, content: bytes) -> Path:
        with self._create_file(name) as handle:
            handle.write(content)
        return self._target(name)

    def cleanup(self) -> bool:
        """Remove the workspace. Safe to call repeatedly; never follows a swapped-in symlink."""
        path = self.path
        if not os.path.lexists(path):
            return True
        if path.is_symlink() or path.resolve().parent != self._base:
            logger.error("workspace %s is not a job directory; refusing to delete", path.name)
            return False
        errors: list[str] = []

        def _record(_function, _failed_path, exc):
            error = exc[1] if isinstance(exc, tuple) else exc
            errors.append(type(error).__name__)

        if sys.version_info >= (3, 12):
            shutil.rmtree(path, onexc=_record)
        else:  # pragma: no cover - Python 3.11 (CI) uses the older callback name
            shutil.rmtree(path, onerror=_record)
        if errors or os.path.lexists(path):
            logger.error("workspace %s cleanup incomplete: %s", path.name, ",".join(errors))
            return False
        logger.info("workspace %s removed", path.name)
        return True


def remove_stale_workspaces(active_job_ids: set[str], *, older_than_seconds: float, now: float):
    """Delete leftover job directories (crashed workers). Returns how many were removed."""
    base = Path(settings.SANDBOX_WORK_DIR)
    if not base.is_dir() or base.is_symlink():
        return 0
    removed = 0
    for entry in base.iterdir():
        job_id = entry.name.rsplit("-", 1)[0]
        if job_id in active_job_ids or entry.is_symlink() or not entry.is_dir():
            continue
        try:
            age = now - entry.lstat().st_mtime
        except OSError:
            continue
        if age < older_than_seconds:
            continue
        if JobWorkspace(entry, entry, base.resolve()).cleanup():
            removed += 1
    return removed
