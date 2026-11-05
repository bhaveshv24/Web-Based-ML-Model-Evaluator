"""Model runner executed INSIDE the sandbox container (SAD 5.1 step 2).

Usage:
    runner.py predict /input/model.<pkl|joblib|onnx> /input/X.csv
    runner.py inspect /input/model.<pkl|joblib|onnx>

Loading a pickle/joblib file runs arbitrary code, which is why this script only ever runs in
the locked-down container: no network, read-only filesystem, non-root, resource limits, and
only the model and the feature matrix X mounted (the labels are never available here).

The result is written as one line ``@@ML-EVALUATOR-RESULT@@ <json>`` on the original stdout.
Everything else (including anything the model prints) is redirected to stderr. The worker
treats the result as untrusted and validates it before computing any metric.
Exit codes: 0 ok, 2 usage, 3 input unreadable, 4 model load failed, 5 prediction failed,
6 output could not be produced.
"""

from __future__ import annotations

import json
import numbers
import os
import sys

RESULT_MARKER = "@@ML-EVALUATOR-RESULT@@ "
EXIT_USAGE, EXIT_INPUT, EXIT_LOAD, EXIT_PREDICT, EXIT_OUTPUT = 2, 3, 4, 5, 6
ONNX_INPUT_TYPES = {
    "tensor(float)": "float32",
    "tensor(double)": "float64",
    "tensor(int64)": "int64",
    "tensor(int32)": "int32",
}


class RunnerFailure(Exception):
    def __init__(self, exit_code: int, reason: str) -> None:
        super().__init__(reason)
        self.exit_code = exit_code


class OnnxModel:
    """Minimal predict/predict_proba facade over an ONNX Runtime session."""

    def __init__(self, path: str) -> None:
        import onnxruntime as ort

        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        self.session = ort.InferenceSession(
            path, sess_options=options, providers=["CPUExecutionProvider"]
        )
        inputs = self.session.get_inputs()
        if len(inputs) != 1 or inputs[0].type not in ONNX_INPUT_TYPES:
            raise RunnerFailure(EXIT_LOAD, "only single numeric-tensor ONNX inputs are supported")
        self.input = inputs[0]
        shape = self.input.shape
        width = shape[1] if len(shape) == 2 else None
        self.n_features_in_ = width if isinstance(width, int) else None

    def run(self, frame):
        matrix = frame.to_numpy(dtype=ONNX_INPUT_TYPES[self.input.type])
        return self.session.run(None, {self.input.name: matrix})


def _load_model(path: str):
    extension = os.path.splitext(path)[1].lower()
    try:
        if extension == ".onnx":
            return OnnxModel(path)
        if extension in (".pkl", ".joblib"):
            import joblib

            return joblib.load(path)  # executes untrusted code: sandbox only
    except RunnerFailure:
        raise
    except BaseException as exc:  # noqa: BLE001 - any failure of untrusted code
        raise RunnerFailure(EXIT_LOAD, type(exc).__name__) from None
    raise RunnerFailure(EXIT_USAGE, "unsupported model extension")


def _read_features(path: str):
    try:
        import pandas as pd

        return pd.read_csv(path)
    except Exception as exc:  # noqa: BLE001
        raise RunnerFailure(EXIT_INPUT, type(exc).__name__) from None


def _one_dimensional(values):
    import numpy as np

    array = np.asarray(values)
    if array.ndim == 2 and array.shape[1] == 1:
        array = array.ravel()
    if array.ndim != 1:
        raise RunnerFailure(EXIT_OUTPUT, "multi-output predictions are not supported")
    return array.tolist()


def _onnx_predictions(model: OnnxModel, frame) -> dict:
    outputs = model.run(frame)
    result = {"predictions": _one_dimensional(outputs[0])}
    if len(outputs) > 1:
        probabilities = outputs[1]
        # skl2onnx ZipMap output: a list of {class: probability} dictionaries.
        if isinstance(probabilities, list) and probabilities and isinstance(probabilities[0], dict):
            classes = list(probabilities[0].keys())
            result["classes"] = classes
            result["probabilities"] = [[row[c] for c in classes] for row in probabilities]
    return result


def _sklearn_predictions(model, frame) -> dict:
    result = {"predictions": _one_dimensional(model.predict(frame))}
    classes = getattr(model, "classes_", None)
    predict_proba = getattr(model, "predict_proba", None)
    if classes is not None and callable(predict_proba):
        try:
            result["probabilities"] = predict_proba(frame).tolist()
            result["classes"] = _one_dimensional(classes)
        except Exception:  # noqa: BLE001 - probabilities are optional (UT-EXE-06)
            result.pop("probabilities", None)
    return result


def predict(model_path: str, features_path: str) -> dict:
    frame = _read_features(features_path)
    model = _load_model(model_path)
    try:
        if isinstance(model, OnnxModel):
            return _onnx_predictions(model, frame)
        if not callable(getattr(model, "predict", None)):
            raise RunnerFailure(EXIT_LOAD, "the loaded object has no predict method")
        return _sklearn_predictions(model, frame)
    except RunnerFailure:
        raise
    except BaseException as exc:  # noqa: BLE001
        raise RunnerFailure(EXIT_PREDICT, type(exc).__name__) from None


def inspect(model_path: str) -> dict:
    model = _load_model(model_path)
    count = getattr(model, "n_features_in_", None)
    names = getattr(model, "feature_names_in_", None)
    integral = isinstance(count, numbers.Integral) and not isinstance(count, bool)
    return {
        "n_features_in": int(count) if integral else None,
        "feature_names_in": [str(name) for name in names] if names is not None else None,
    }


def _emit(fd: int, payload: dict) -> None:
    try:
        line = (RESULT_MARKER + json.dumps(payload) + "\n").encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise RunnerFailure(EXIT_OUTPUT, type(exc).__name__) from None
    view = memoryview(line)
    while view:
        written = os.write(fd, view)
        view = view[written:]


def main(argv: list[str]) -> int:
    result_fd = os.dup(1)
    os.dup2(2, 1)  # model output can no longer interleave with the result channel
    sys.stdout = sys.stderr
    try:
        if len(argv) == 3 and argv[0] == "predict":
            payload = predict(argv[1], argv[2])
        elif len(argv) == 2 and argv[0] == "inspect":
            payload = inspect(argv[1])
        else:
            raise RunnerFailure(EXIT_USAGE, "usage: predict MODEL X | inspect MODEL")
        _emit(result_fd, payload)
    except RunnerFailure as failure:
        print(f"runner: {failure}", file=sys.stderr)
        return failure.exit_code
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
