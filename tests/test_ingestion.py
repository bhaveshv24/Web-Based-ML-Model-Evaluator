import time

from ingestion.validators import (
    DATASET_COLUMN_LIMIT,
    DATASET_LIMIT_BYTES,
    validate_csv_bytes,
    validate_feature_compatibility,
    validate_model_upload,
)


def codes(issues):
    return {issue.code for issue in issues}


def test_model_extension_allow_list():
    assert not validate_model_upload("model.pkl", 10, b"\x80\x04")
    assert "MODEL_TYPE" in codes(validate_model_upload("model.exe", 10, b"MZ"))


def test_disguised_archive_is_rejected():
    assert "MODEL_SIGNATURE" in codes(validate_model_upload("model.onnx", 10, b"PK\x03\x04"))


def test_valid_csv_summary_and_target_suggestion():
    summary, issues = validate_csv_bytes(b"a,b,species\n1,2,setosa\n3,4,virginica\n")
    assert issues == []
    assert summary and summary.rows == 2 and summary.suggested_target == "species"


def test_header_only_and_duplicates_are_reported():
    _, issues = validate_csv_bytes(b"a,b,a,target\n")
    assert {"DATASET_DUPLICATE_COLUMNS", "DATASET_EMPTY"} <= codes(issues)


def test_missing_feature_values_are_rejected_but_missing_target_is_not_counted():
    _, issues = validate_csv_bytes(b"age,target\n,yes\n22,\n")
    assert "DATASET_MISSING_FEATURE" in codes(issues)
    assert len([issue for issue in issues if issue.code == "DATASET_MISSING_FEATURE"]) == 1


def test_size_boundary():
    _, issues = validate_csv_bytes(b"a,target\n1,x\n", size_limit=5)
    assert "DATASET_SIZE" in codes(issues)
    assert DATASET_LIMIT_BYTES == 50 * 1024 * 1024


def test_feature_count_mismatch_is_explicit():
    issue = validate_feature_compatibility(4, ["a", "b", "c", "target"], "target")[0]
    assert issue.expected == 4 and issue.actual == 3


# ---- review follow-up (PR #27): validator-level regression tests
ONNX_PREFIX = b"\x08\x08\x12\x07pytorch\x1a\x032.1\x3a\x80\x01"


def test_wide_csv_is_rejected_in_linear_time():
    header = ",".join(f"c{i}" for i in range(100_000)).encode()
    started = time.monotonic()
    summary, issues = validate_csv_bytes(header + b"\n1\n")
    assert summary is None and codes(issues) == {"DATASET_COLUMNS"}
    assert time.monotonic() - started < 2


def test_column_limit_boundary_and_one_pass_duplicate_detection():
    ok = ",".join(f"c{i}" for i in range(DATASET_COLUMN_LIMIT)).encode()
    _, issues = validate_csv_bytes(ok + b"\n" + b",".join([b"1"] * DATASET_COLUMN_LIMIT) + b"\n")
    assert issues == []
    _, dup = validate_csv_bytes(b"a,b,a,b,t\n1,2,3,4,5\n")
    assert [i.message for i in dup if i.code == "DATASET_DUPLICATE_COLUMNS"] == [
        "Duplicate columns: a, b"
    ]


def test_csv_parser_errors_become_validation_issues():
    _, issues = validate_csv_bytes(b"a,t\n" + b"x" * 200_000 + b",1\n")
    assert "DATASET_PARSE" in codes(issues)
    summary, issues = validate_csv_bytes(b"x" * 200_000 + b",t\n1,2\n")
    assert summary is None and codes(issues) == {"DATASET_PARSE"}


def test_overlong_column_name_is_reported():
    _, issues = validate_csv_bytes(b"a," + b"n" * 300 + b"\n1,2\n")
    assert "DATASET_COLUMN_NAME" in codes(issues)


def test_row_issues_are_capped():
    _, issues = validate_csv_bytes(b"a,t\n" + b"1,2,3\n" * 10_000)
    assert len(issues) <= 20


def test_pickle_signature_requires_binary_pickle_header():
    assert not validate_model_upload("m.pkl", 50, b"\x80\x04\x95rest")
    assert not validate_model_upload("m.pkl", 50, b"\x80\x02rest")
    for junk in (b"plain text", b"\x80\x09x", b"\x80", b"\x00\x01\x02"):
        assert "MODEL_SIGNATURE" in codes(validate_model_upload("m.pkl", 50, junk))


def test_joblib_accepts_pickle_or_known_compression_headers():
    for header in (b"\x80\x04x", b"x\x9cdata", b"\x1f\x8bdata", b"BZh9data", b"\xfd7zXZ\x00d"):
        assert not validate_model_upload("m.joblib", 50, header)
    assert "MODEL_SIGNATURE" in codes(validate_model_upload("m.joblib", 50, b"not joblib"))


def test_onnx_signature_walks_protobuf_header():
    assert not validate_model_upload("m.onnx", 500, ONNX_PREFIX)
    assert not validate_model_upload("m.onnx", 500, ONNX_PREFIX[:3])  # truncated prefix is fine
    for junk in (
        b"\x08garbage-bytes",  # starts with 0x08 but is not protobuf
        b"\x08\x00\x12\x03abc",  # ir_version 0 is invalid
        b"\x08\x08\x7f\x00",  # unknown field after ir_version
        b"\x12\x07pytorch",  # does not begin with ir_version
        b"\x08",
    ):
        assert "MODEL_SIGNATURE" in codes(validate_model_upload("m.onnx", 500, junk)), junk


def test_empty_model_reports_empty_not_signature():
    assert codes(validate_model_upload("m.pkl", 0, b"")) == {"MODEL_EMPTY"}
