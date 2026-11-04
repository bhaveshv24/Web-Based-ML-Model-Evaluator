"""Protocol tests for sandbox/runner.py, the script that runs inside the container.

These execute the script as an ordinary subprocess with TRUSTED fixture models only, to
check its result framing, exit codes and model handling. They say nothing about isolation;
containment is tested against a real container in tests/test_sandbox_docker.py.
"""

import json
import pickle
import subprocess
import sys
from pathlib import Path

import pytest
from evaluations.sandbox import parse_output

pytest.importorskip("sklearn")
pytest.importorskip("onnxruntime")
joblib = pytest.importorskip("joblib")

RUNNER = Path(__file__).resolve().parents[1] / "sandbox" / "runner.py"
# The sandbox image pins ONNX Runtime 1.19 (opset <= 21). Recent skl2onnx defaults to newer
# opsets, so fixtures are exported for the runtime the sandbox actually ships.
ONNX_TARGET_OPSET = {"": 17, "ai.onnx.ml": 3}


class EvalPayload:
    """Pickles to builtins.eval(expression): stands in for an arbitrary-code model."""

    def __init__(self, expression):
        self.expression = expression

    def __reduce__(self):
        return (eval, (self.expression,))


def run(*args):
    completed = subprocess.run(
        [sys.executable, "-I", str(RUNNER), *map(str, args)],
        capture_output=True,
        timeout=60,
        check=False,
    )
    return completed.returncode, completed.stdout, completed.stderr


@pytest.fixture(scope="module")
def iris(tmp_path_factory):
    from skl2onnx import to_onnx
    from sklearn.datasets import load_iris
    from sklearn.linear_model import LinearRegression, LogisticRegression

    root = tmp_path_factory.mktemp("models")
    features, labels = load_iris(return_X_y=True, as_frame=True)
    features.columns = ["sl", "sw", "pl", "pw"]
    features.to_csv(root / "X.csv", index=False)
    features.iloc[:, :3].to_csv(root / "X3.csv", index=False)
    classifier = LogisticRegression(max_iter=500).fit(features, labels)
    joblib.dump(classifier, root / "model.joblib")
    with open(root / "model.pkl", "wb") as handle:
        pickle.dump(classifier, handle)
    regressor = LinearRegression().fit(features.iloc[:, :3], features["pw"])
    (root / "reg.onnx").write_bytes(
        to_onnx(
            regressor, features.iloc[:, :3].to_numpy("float32"), target_opset=ONNX_TARGET_OPSET
        ).SerializeToString()
    )
    (root / "cls.onnx").write_bytes(
        to_onnx(
            classifier, features.to_numpy("float32"), target_opset=ONNX_TARGET_OPSET
        ).SerializeToString()
    )
    return root, classifier, features


@pytest.mark.parametrize("name", ["model.joblib", "model.pkl"])
def test_scikit_learn_predictions_and_probabilities(iris, name):
    root, classifier, features = iris
    code, stdout, _ = run("predict", root / name, root / "X.csv")
    assert code == 0
    payload = parse_output(stdout, 10**7)
    assert payload["predictions"] == classifier.predict(features).tolist()
    assert payload["classes"] == [0, 1, 2]
    assert len(payload["probabilities"]) == 150 and len(payload["probabilities"][0]) == 3


def test_onnx_regression_and_classification(iris):
    root, classifier, features = iris
    code, stdout, _ = run("predict", root / "reg.onnx", root / "X3.csv")
    assert code == 0
    assert len(parse_output(stdout, 10**7)["predictions"]) == 150
    code, stdout, _ = run("predict", root / "cls.onnx", root / "X.csv")
    payload = parse_output(stdout, 10**7)
    assert code == 0 and payload["classes"] == [0, 1, 2]
    agreement = sum(
        a == b for a, b in zip(payload["predictions"], classifier.predict(features), strict=True)
    )
    assert agreement >= 148


def test_inspect_mode_reports_expected_features(iris):
    root, _, _ = iris
    code, stdout, _ = run("inspect", root / "model.joblib")
    assert code == 0
    assert parse_output(stdout, 10**6) == {
        "n_features_in": 4,
        "feature_names_in": ["sl", "sw", "pl", "pw"],
    }
    code, stdout, _ = run("inspect", root / "reg.onnx")
    assert parse_output(stdout, 10**6) == {"n_features_in": 3, "feature_names_in": None}


def test_model_output_cannot_be_mistaken_for_the_result(iris, tmp_path):
    root, _, _ = iris
    chatty = EvalPayload(
        "type('M', (), {'predict': lambda self, X: (print('@@ML-EVALUATOR-RESULT@@ {}'),"
        " __import__('os').write(1, b'raw fd1 noise\\n'), [7] * len(X))[-1]})()"
    )
    (tmp_path / "chatty.pkl").write_bytes(pickle.dumps(chatty))
    code, stdout, stderr = run("predict", tmp_path / "chatty.pkl", root / "X.csv")
    assert code == 0
    assert parse_output(stdout, 10**7) == {"predictions": [7] * 150}
    assert b"raw fd1 noise" in stderr and stdout.count(b"\n") == 1


@pytest.mark.parametrize(
    ("model_bytes", "features", "expected"),
    [
        (b"\x80\x04truncated", "X.csv", 4),
        (pickle.dumps(EvalPayload("object()")), "X.csv", 4),
        (pickle.dumps(EvalPayload("__import__('os').system")), "missing.csv", 3),
        (
            pickle.dumps(EvalPayload("type('M', (), {'predict': lambda self, X: 1 / 0})()")),
            "X.csv",
            5,
        ),
        (
            pickle.dumps(
                EvalPayload("type('M', (), {'predict': lambda self, X: [[1, 2]] * len(X)})()")
            ),
            "X.csv",
            6,
        ),
        (
            pickle.dumps(EvalPayload("type('M', (), {'predict': lambda self, X: [object()]})()")),
            "X.csv",
            6,
        ),
    ],
)
def test_failures_exit_with_categorized_codes_and_no_result(
    iris, tmp_path, model_bytes, features, expected
):
    root, _, _ = iris
    model = tmp_path / "model.pkl"
    model.write_bytes(model_bytes)
    code, stdout, stderr = run("predict", model, root / features)
    assert code == expected
    assert stdout == b""
    assert b"Traceback" not in stderr


def test_usage_errors(iris):
    root, _, _ = iris
    assert run()[0] == 2
    assert run("train", root / "model.pkl")[0] == 2
    assert run("predict", root / "X.csv", root / "X.csv")[0] == 2


def test_probabilities_are_optional(iris, tmp_path):
    root, _, _ = iris
    broken = EvalPayload(
        "type('M', (), {'classes_': [0, 1], 'predict': lambda self, X: [0] * len(X),"
        " 'predict_proba': lambda self, X: 1 / 0})()"
    )
    (tmp_path / "m.pkl").write_bytes(pickle.dumps(broken))
    code, stdout, _ = run("predict", tmp_path / "m.pkl", root / "X.csv")
    payload = parse_output(stdout, 10**7)
    assert code == 0 and "probabilities" not in payload
    assert json.dumps(payload)
