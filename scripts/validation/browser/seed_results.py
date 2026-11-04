"""Create an account with the runs the browser checks need, through the real stack.

    python scripts/validation/browser/seed_results.py --out <file>
Writes "EMAIL=...\nPASSWORD=..." to <file> (keep it outside the repository). The runs are
three classification models on one iris dataset and one ONNX regression model, each executed
in the sandbox exactly as a user would run them.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from system_tests import Api, Fixtures  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("--base-url", default="http://localhost:8000")
parser.add_argument("--out", required=True)
args = parser.parse_args()

fixtures = Fixtures()
api = Api(args.base_url).register_and_login()
runs = [(fixtures.iris_bytes[name], name, fixtures.iris_csv, "species")
        for name in ("rf_iris.pkl", "logreg_iris.joblib", "dtree_iris.pkl")]
runs.append((fixtures.linreg_onnx, "linreg.onnx", fixtures.housing_csv, "price"))
for model, name, csv, target in runs:
    evaluation_id, status = api.evaluate(model, name, csv, target)
    print(name, evaluation_id, status["status"])
    assert status["status"] == "SUCCEEDED"
Path(args.out).write_text(f"EMAIL={api.email}\nPASSWORD={api.password}\n")
