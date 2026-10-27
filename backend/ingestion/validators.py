from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import PurePath

MODEL_LIMIT_BYTES = 100 * 1024 * 1024
DATASET_LIMIT_BYTES = 50 * 1024 * 1024
DATASET_ROW_LIMIT = 500_000


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    expected: str | int | None = None
    actual: str | int | None = None


def _safe_suffix(filename: str) -> str:
    return PurePath(filename).suffix.lower()


def validate_model_upload(filename: str, size_bytes: int, prefix: bytes) -> list[ValidationIssue]:
    """Validate metadata without ever deserializing untrusted model content."""
    issues: list[ValidationIssue] = []
    suffix = _safe_suffix(filename)
    if suffix not in {".pkl", ".joblib", ".onnx"}:
        issues.append(
            ValidationIssue("MODEL_TYPE", "Unsupported model type", ".pkl/.joblib/.onnx", suffix)
        )
    if size_bytes > MODEL_LIMIT_BYTES:
        issues.append(
            ValidationIssue("MODEL_SIZE", "Model exceeds 100 MB", MODEL_LIMIT_BYTES, size_bytes)
        )
    if size_bytes <= 0:
        issues.append(
            ValidationIssue("MODEL_EMPTY", "Model file is empty", "> 0 bytes", size_bytes)
        )

    # ONNX is a protobuf message and must not look like a ZIP or pickle stream.
    # Pickle/joblib signatures are deliberately broad; safe inspection happens in the sandbox.
    if suffix == ".onnx" and (prefix.startswith(b"PK\x03\x04") or prefix.startswith(b"\x80")):
        issues.append(ValidationIssue("MODEL_SIGNATURE", "Content does not match ONNX extension"))
    if suffix in {".pkl", ".joblib"} and prefix.startswith(b"PK\x03\x04"):
        issues.append(
            ValidationIssue("MODEL_SIGNATURE", "Archive content is not accepted as a model")
        )
    return issues


@dataclass(frozen=True)
class DatasetSummary:
    columns: tuple[str, ...]
    rows: int
    suggested_target: str | None


def validate_csv_bytes(
    content: bytes,
    *,
    target_column: str | None = None,
    size_limit: int = DATASET_LIMIT_BYTES,
    row_limit: int = DATASET_ROW_LIMIT,
) -> tuple[DatasetSummary | None, list[ValidationIssue]]:
    issues: list[ValidationIssue] = []
    if len(content) > size_limit:
        return None, [
            ValidationIssue("DATASET_SIZE", "Dataset exceeds 50 MB", size_limit, len(content))
        ]
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None, [ValidationIssue("DATASET_ENCODING", "CSV must be UTF-8 encoded")]

    reader = csv.reader(io.StringIO(text, newline=""))
    try:
        header = next(reader)
    except StopIteration:
        return None, [ValidationIssue("DATASET_HEADER", "CSV header is required")]

    columns = [name.strip() for name in header]
    if not columns or any(not name for name in columns):
        issues.append(ValidationIssue("DATASET_HEADER", "Column names must be non-empty"))
    duplicates = sorted({name for name in columns if columns.count(name) > 1})
    if duplicates:
        issues.append(
            ValidationIssue(
                "DATASET_DUPLICATE_COLUMNS", f"Duplicate columns: {', '.join(duplicates)}"
            )
        )

    selected_target = target_column or (columns[-1] if columns else None)
    if selected_target and selected_target not in columns:
        issues.append(
            ValidationIssue("DATASET_TARGET", "Target column is not present", selected_target, None)
        )

    missing_by_column: dict[str, int] = {name: 0 for name in columns if name != selected_target}
    rows = 0
    for row in reader:
        rows += 1
        if rows > row_limit:
            issues.append(
                ValidationIssue("DATASET_ROWS", "Dataset exceeds row limit", row_limit, rows)
            )
            break
        if len(row) != len(columns):
            issues.append(
                ValidationIssue(
                    "DATASET_WIDTH",
                    f"Row {rows + 1} has the wrong number of fields",
                    len(columns),
                    len(row),
                )
            )
            continue
        for index, value in enumerate(row):
            name = columns[index]
            if name != selected_target and value.strip() == "":
                missing_by_column[name] += 1

    if rows == 0:
        issues.append(ValidationIssue("DATASET_EMPTY", "CSV must contain at least one data row"))
    for name, count in missing_by_column.items():
        if count:
            issues.append(
                ValidationIssue(
                    "DATASET_MISSING_FEATURE",
                    f"Feature column '{name}' has {count} missing value(s)",
                    0,
                    count,
                )
            )

    summary = DatasetSummary(tuple(columns), rows, selected_target)
    return summary, issues


def validate_feature_compatibility(
    expected: int, actual_columns: list[str], target_column: str
) -> list[ValidationIssue]:
    actual = len([name for name in actual_columns if name != target_column])
    if actual == expected:
        return []
    return [
        ValidationIssue(
            "FEATURE_COUNT", f"Expected {expected} features, got {actual}", expected, actual
        )
    ]
