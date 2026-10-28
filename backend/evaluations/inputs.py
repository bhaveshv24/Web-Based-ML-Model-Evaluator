"""Worker-side input preparation: split the dataset into X and y (SAD 5.1 step 1, BR-06).

The CSV was validated at upload (FR-009/010) but is re-checked here because the worker must
not trust anything it did not read itself: the file is opened through the containment and
checksum checks, the target column snapshotted at submission is removed from the features,
and only X is written to the sandbox workspace. The labels stay in worker memory.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from ingestion.validators import DATASET_LIMIT_BYTES, DATASET_ROW_LIMIT, MODEL_LIMIT_BYTES

from .errors import ErrorCode, EvaluationError
from .models import Evaluation
from .sandbox.workspace import FEATURES_FILENAME, MODEL_FILENAMES, JobWorkspace, read_trusted


@dataclass(frozen=True)
class PreparedInputs:
    model_filename: str
    labels: list[str]
    feature_names: list[str]

    @property
    def rows(self) -> int:
        return len(self.labels)


def _invalid(detail: str) -> EvaluationError:
    return EvaluationError(ErrorCode.INVALID_INPUT, detail)


def split_features_and_labels(content: bytes, target: str) -> tuple[list[str], bytes, list[str]]:
    """Return (feature names, X as CSV bytes, raw labels). Raises EvaluationError."""
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise _invalid("The dataset is not UTF-8 encoded.") from exc
    reader = csv.reader(io.StringIO(text, newline=""))
    try:
        header = [name.strip() for name in next(reader)]
    except StopIteration as exc:
        raise _invalid("The dataset has no header.") from exc
    except csv.Error as exc:
        raise _invalid("The dataset could not be parsed.") from exc
    if len(set(header)) != len(header) or any(not name for name in header):
        raise _invalid("The dataset header has empty or duplicate column names.")
    if target not in header:
        raise _invalid("The selected target column is not in the dataset.")
    target_index = header.index(target)
    features = [name for i, name in enumerate(header) if i != target_index]
    if not features:
        raise _invalid("The dataset has no feature columns.")

    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(features)
    labels: list[str] = []
    try:
        for line_number, row in enumerate(reader, start=2):
            if not row:
                continue
            if len(row) != len(header):
                raise _invalid(f"Row {line_number} has the wrong number of fields.")
            if len(labels) >= DATASET_ROW_LIMIT:
                raise _invalid(f"The dataset exceeds {DATASET_ROW_LIMIT} rows.")
            feature_values = [value for i, value in enumerate(row) if i != target_index]
            if any(value.strip() == "" for value in feature_values):
                raise _invalid(f"Row {line_number} has a missing feature value.")
            labels.append(row[target_index])
            writer.writerow(feature_values)
    except csv.Error as exc:
        raise _invalid("The dataset could not be parsed.") from exc
    if not labels:
        raise _invalid("The dataset has no data rows.")
    return features, out.getvalue().encode("utf-8"), labels


def prepare_inputs(evaluation: Evaluation, workspace: JobWorkspace) -> PreparedInputs:
    model, dataset = evaluation.model_artifact, evaluation.dataset
    if model is None or dataset is None:
        raise _invalid("The model or dataset of this evaluation was deleted.")
    model_filename = MODEL_FILENAMES.get(model.extension)
    if model_filename is None:
        raise _invalid("Unsupported model format.")
    media_root = Path(settings.MEDIA_ROOT)

    workspace.stage_copy(
        Path(model.file.path),
        model_filename,
        allowed_root=media_root / "models",
        max_bytes=MODEL_LIMIT_BYTES,
        sha256=evaluation.model_sha256 or model.sha256,
    )
    content = read_trusted(
        Path(dataset.file.path),
        allowed_root=media_root / "datasets",
        max_bytes=DATASET_LIMIT_BYTES,
        sha256=evaluation.dataset_sha256 or dataset.sha256,
    )
    target = evaluation.target_column or dataset.target_column
    features, x_csv, labels = split_features_and_labels(content, target)
    workspace.write_bytes(FEATURES_FILENAME, x_csv)
    return PreparedInputs(model_filename, labels, features)
