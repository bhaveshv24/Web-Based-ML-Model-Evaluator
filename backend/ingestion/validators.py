from __future__ import annotations

import csv
import io
from collections import Counter
from dataclasses import dataclass
from pathlib import PurePath

MODEL_LIMIT_BYTES = 100 * 1024 * 1024
DATASET_LIMIT_BYTES = 50 * 1024 * 1024
DATASET_ROW_LIMIT = 500_000
DATASET_COLUMN_LIMIT = 1_000
COLUMN_NAME_LIMIT = 255  # matches Dataset.target_column / suggested_target max_length
MAX_REPORTED_ISSUES = (
    20  # stop collecting row-level issues so a hostile CSV cannot bloat a response
)
SIGNATURE_PREFIX_BYTES = 64


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    expected: str | int | None = None
    actual: str | int | None = None


def _safe_suffix(filename: str) -> str:
    return PurePath(filename).suffix.lower()


_JOBLIB_COMPRESSION_MAGIC = (
    b"\x78\x01",  # zlib (joblib compress=True)
    b"\x78\x5e",
    b"\x78\x9c",
    b"\x78\xda",
    b"\x1f\x8b",  # gzip
    b"BZh",  # bzip2
    b"\xfd7zXZ\x00",  # xz
    b"\x5d\x00\x00",  # lzma
    b"\x04\x22\x4d\x18",  # lz4 frame
)
_ONNX_MODEL_FIELDS = {  # ModelProto field number -> expected protobuf wire type
    1: 0, 2: 2, 3: 2, 4: 2, 5: 0, 6: 2, 7: 2, 8: 2, 14: 2, 20: 2,
}  # fmt: skip


def _looks_like_pickle(prefix: bytes) -> bool:
    """Binary pickle: PROTO opcode (0x80) followed by protocol 2-5."""
    return len(prefix) >= 2 and prefix[0] == 0x80 and 2 <= prefix[1] <= 5


def _read_varint(data: bytes, pos: int) -> tuple[int | None, int]:
    value = shift = 0
    while pos < len(data):
        byte = data[pos]
        pos += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, pos
        shift += 7
        if shift > 63:
            break
    return None, pos


def _looks_like_onnx(prefix: bytes) -> bool:
    """Walk the leading protobuf fields of a ModelProto without decoding the model.

    A real ONNX file starts with ir_version (field 1, varint) followed by known ModelProto
    fields. Random bytes that merely begin with 0x08 do not survive this walk.
    """
    tag, pos = _read_varint(prefix, 0)
    if tag != 0x08:  # field 1, wire type 0
        return False
    ir_version, pos = _read_varint(prefix, pos)
    if ir_version is None or not 1 <= ir_version <= 30:
        return False
    while pos < len(prefix):
        tag, pos = _read_varint(prefix, pos)
        if tag is None:
            return True  # prefix ended inside a tag; everything before it was valid
        field, wire = tag >> 3, tag & 7
        if _ONNX_MODEL_FIELDS.get(field) != wire:
            return False
        value, pos = _read_varint(prefix, pos)
        if value is None:
            return True  # prefix ended inside a value
        if wire == 2:
            if pos + value > len(prefix):
                return True  # field continues beyond the prefix we were given
            pos += value
    return True


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

    # Signatures are structural checks on the first bytes only. Nothing is ever deserialized;
    # deep inspection happens in the sandbox. Empty files are already reported as MODEL_EMPTY.
    if size_bytes > 0:
        if suffix == ".onnx" and not _looks_like_onnx(prefix):
            issues.append(
                ValidationIssue("MODEL_SIGNATURE", "Content does not match ONNX extension")
            )
        if suffix == ".pkl" and not _looks_like_pickle(prefix):
            issues.append(
                ValidationIssue("MODEL_SIGNATURE", "Content does not match a pickle stream")
            )
        if suffix == ".joblib" and not (
            _looks_like_pickle(prefix) or prefix.startswith(_JOBLIB_COMPRESSION_MAGIC)
        ):
            issues.append(
                ValidationIssue("MODEL_SIGNATURE", "Content does not match a joblib file")
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
    except csv.Error:
        return None, [ValidationIssue("DATASET_PARSE", "CSV could not be parsed")]

    columns = [name.strip() for name in header]
    if len(columns) > DATASET_COLUMN_LIMIT:
        return None, [
            ValidationIssue(
                "DATASET_COLUMNS",
                "Dataset has too many columns",
                DATASET_COLUMN_LIMIT,
                len(columns),
            )
        ]
    if not columns or any(not name for name in columns):
        issues.append(ValidationIssue("DATASET_HEADER", "Column names must be non-empty"))
    if any(len(name) > COLUMN_NAME_LIMIT for name in columns):
        issues.append(
            ValidationIssue(
                "DATASET_COLUMN_NAME", "Column name is too long", COLUMN_NAME_LIMIT, None
            )
        )
    duplicates = sorted(name for name, count in Counter(columns).items() if count > 1)
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
    try:
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
                if len(issues) >= MAX_REPORTED_ISSUES:
                    break
                continue
            for index, value in enumerate(row):
                name = columns[index]
                if name != selected_target and value.strip() == "":
                    missing_by_column[name] += 1
    except csv.Error:
        issues.append(
            ValidationIssue("DATASET_PARSE", f"CSV could not be parsed near row {rows + 1}")
        )

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
