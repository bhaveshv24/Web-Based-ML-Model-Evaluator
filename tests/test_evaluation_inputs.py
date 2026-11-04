"""BR-06 / FR-010 at execution time: the worker re-validates the CSV and strips the target."""

import pytest
from evaluations.errors import ErrorCode, EvaluationError
from evaluations.inputs import split_features_and_labels


def test_target_is_removed_from_features_and_kept_as_labels():
    features, x_csv, labels = split_features_and_labels(
        b"\xef\xbb\xbfa,label,b\n1,yes,2\n\n3,no,4\n", "label"
    )
    assert features == ["a", "b"]
    assert x_csv == b"a,b\n1,2\n3,4\n"
    assert labels == ["yes", "no"]
    assert b"yes" not in x_csv and b"label" not in x_csv


@pytest.mark.parametrize(
    ("content", "target", "message"),
    [
        (b"\xff\xfe\x00bad", "y", "UTF-8"),
        (b"", "y", "no header"),
        (b"a,a,y\n1,2,3\n", "y", "duplicate"),
        (b"a,,y\n1,2,3\n", "y", "duplicate"),
        (b"a,b\n1,2\n", "y", "not in the dataset"),
        (b"y\n1\n", "y", "no feature columns"),
        (b"a,y\n1,2,3\n", "y", "Row 2 has the wrong number"),
        (b"a,b,y\n1, ,3\n", "y", "Row 2 has a missing feature"),
        (b"a,y\n", "y", "no data rows"),
        (b'a,y\n"1,2\n', "y", "wrong number of fields"),
    ],
)
def test_malformed_datasets_fail_with_invalid_input(content, target, message):
    with pytest.raises(EvaluationError) as raised:
        split_features_and_labels(content, target)
    assert raised.value.code == ErrorCode.INVALID_INPUT
    assert message in raised.value.detail


def test_row_limit_is_enforced(monkeypatch):
    monkeypatch.setattr("evaluations.inputs.DATASET_ROW_LIMIT", 2)
    with pytest.raises(EvaluationError, match="INVALID_INPUT"):
        split_features_and_labels(b"a,y\n1,1\n2,2\n3,3\n", "y")
