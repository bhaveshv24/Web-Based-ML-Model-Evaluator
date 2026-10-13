from ingestion.validators import (
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
