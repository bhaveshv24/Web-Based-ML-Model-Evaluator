"""Build the USA-01 participant kit: the model and dataset files used in the scenarios.

    python scripts/validation/usability/make_kit.py --out <folder outside the repository>

Files are produced by the same fixtures as the system tests (system_tests.Fixtures). The
models are trained with the scikit-learn version pinned in the sandbox image, so they load in
the sandbox. Every participant gets an identical copy of the folder. Requires the dev extras.
"""

import argparse
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from system_tests import Fixtures  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("--out", required=True)
args = parser.parse_args()

out = Path(args.out)
out.mkdir(parents=True, exist_ok=True)
fixtures = Fixtures()
files = {
    # S1 primary task and S3 comparison: three classifiers trained on iris.
    "iris_random_forest.pkl": fixtures.iris_bytes["rf_iris.pkl"],
    "iris_logistic_regression.joblib": fixtures.iris_bytes["logreg_iris.joblib"],
    "iris_decision_tree.pkl": fixtures.iris_bytes["dtree_iris.pkl"],
    "iris.csv": fixtures.iris_csv,
    # S2 recovery task: a dataset that does not match the iris models (13 features, not 4).
    "wine.csv": fixtures.wine_csv,
}
lines = []
for name, content in files.items():
    (out / name).write_bytes(content)
    lines.append(f"{hashlib.sha256(content).hexdigest()}  {name}")
(out / "SHA256SUMS").write_text("\n".join(lines) + "\n")
print("\n".join(lines))
print(f"Kit written to {out}")
