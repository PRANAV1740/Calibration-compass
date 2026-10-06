from pathlib import Path
from itertools import combinations
import numpy as np
import pandas as pd
from xgboost import XGBClassifier

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "results" / "candidate_features_v2.csv"
OUT = BASE / "results" / "conservative_pairwise_results.csv"

ESP_MARGIN_THRESHOLD = 0.01
PAIRWISE_ADVANTAGE_THRESHOLD = 0.02
RANDOM_STATE = 42


def build_features(df):
    drop = {"circuit_id", "candidate_seed", "actual_fidelity"}

    for c in df.columns:
        if c.lower() == "physical_qubits" or c.lower() == "mapping" or c.lower().endswith("_physical"):
            drop.add(c)

    X = df.drop(columns=[c for c in drop if c in df.columns]).copy()

    X = X.loc[:, ~X.columns.duplicated()]

    for c in list(X.columns):
        if X[c].isna().any():
            X[f"{c}__missing"] = X[c].isna().astype(float)

    cats = X.select_dtypes(include=["object", "string", "category"]).columns.tolist()

    if cats:
        X = pd.get_dummies(X, columns=cats, dummy_na=True)

    X = X.loc[:, ~X.columns.duplicated()]

    non_numeric = X.select_dtypes(
        exclude=[np.number, "bool"]
    ).columns.tolist()

    if non_numeric:
        X = X.drop(columns=non_numeric)

    return X.astype(float)


def make_pairs(train_df, X):
    XP = []
    y = []

    for _, group in train_df.groupby(["circuit_id", "backend"]):
        ids = group.index.tolist()

        for a, b in combinations(ids, 2):
            fa = X.loc[a].values
            fb = X.loc[b].values

            ya = train_df.loc[a, "actual_fidelity"]
            yb = train_df.loc[b, "actual_fidelity"]

            if ya == yb:
                continue

            d = fa - fb
            label = 1 if ya > yb else 0

            XP.append(d)
            y.append(label)
            XP.append(-d)
            y.append(1 - label)

    return np.asarray(XP), np.asarray(y)


def train_model(train_df, X):
    XP, y = make_pairs(train_df, X)

    model = XGBClassifier(
        objective="binary:logistic",
        n_estimators=200,
        learning_rate=0.03,
        max_depth=2,
        min_child_weight=5,
        subsample=0.8,
        colsample_bytree=0.7,
        reg_alpha=0.5,
        reg_lambda=5.0,
        random_state=RANDOM_STATE,
        eval_metric="logloss",
        tree_method="hist",
    )

    model.fit(XP, y)
    return model


def pairwise_scores(group, X, model):
    scores = []

    ids = group.index.tolist()

    for a in ids:
        probs = []

        for b in ids:
            if a == b:
                continue

            d = (
                X.loc[a].values -
                X.loc[b].values
            ).reshape(1, -1)

            probs.append(
                model.predict_proba(d)[0, 1]
            )

        scores.append({
            "candidate": group.loc[a, "candidate_seed"],
            "pairwise": np.mean(probs),
            "esp": group.loc[a, "esp"],
            "fidelity": group.loc[a, "actual_fidelity"],
        })

    return pd.DataFrame(scores)


print("=" * 80)
print("CALIBRATIONCOMPASS - CONSERVATIVE PAIRWISE OVERRIDE")
print("=" * 80)

df = pd.read_csv(DATA)

df = df.rename(columns={
    "circuit": "circuit_id",
    "seed": "candidate_seed",
    "fidelity": "actual_fidelity",
    "ESP": "esp",
})

df["circuit_id"] = pd.to_numeric(df["circuit_id"], errors="coerce")
df["candidate_seed"] = pd.to_numeric(df["candidate_seed"], errors="coerce")
df["actual_fidelity"] = pd.to_numeric(df["actual_fidelity"], errors="coerce")
df["esp"] = pd.to_numeric(df["esp"], errors="coerce")
df["backend"] = df["backend"].astype(str)

df = df.dropna(
    subset=[
        "circuit_id",
        "candidate_seed",
        "actual_fidelity",
        "esp",
    ]
).reset_index(drop=True)

df = df.sort_values(
    ["circuit_id", "backend", "candidate_seed"]
).reset_index(drop=True)

X = build_features(df)

circuits = sorted(df["circuit_id"].unique())

results = []

for n, test_circuit in enumerate(circuits, 1):

    print(
        f"[{n}/{len(circuits)}] "
        f"Testing circuit {int(test_circuit)}..."
    )

    train_df = df[df.circuit_id != test_circuit]
    test_df = df[df.circuit_id == test_circuit]

    model = train_model(train_df, X)

    for backend, group in test_df.groupby("backend"):

        scores = pairwise_scores(
            group,
            X,
            model
        )

        esp = scores.loc[
            scores["esp"].idxmax()
        ]

        pairwise = scores.loc[
            scores["pairwise"].idxmax()
        ]

        oracle = scores.loc[
            scores["fidelity"].idxmax()
        ]

        esp_sorted = scores.sort_values(
            "esp",
            ascending=False
        )

        esp_margin = (
            esp_sorted.iloc[0]["esp"]
            -
            esp_sorted.iloc[1]["esp"]
        )

        pairwise_advantage = (
            pairwise["pairwise"]
            -
            scores.loc[
                scores["candidate"] == esp["candidate"],
                "pairwise"
            ].iloc[0]
        )

        use_pairwise = (
            pairwise["candidate"] != esp["candidate"]
            and
            esp_margin <= ESP_MARGIN_THRESHOLD
            and
            pairwise_advantage >= PAIRWISE_ADVANTAGE_THRESHOLD
        )

        selected = pairwise if use_pairwise else esp

        results.append({
            "circuit_id": test_circuit,
            "backend": backend,
            "oracle_candidate": oracle["candidate"],
            "oracle_fidelity": oracle["fidelity"],
            "esp_candidate": esp["candidate"],
            "esp_fidelity": esp["fidelity"],
            "pairwise_candidate": pairwise["candidate"],
            "pairwise_fidelity": pairwise["fidelity"],
            "selected_candidate": selected["candidate"],
            "selected_fidelity": selected["fidelity"],
            "esp_margin": esp_margin,
            "pairwise_advantage": pairwise_advantage,
            "used_pairwise": use_pairwise,
        })


results = pd.DataFrame(results)

results["esp_correct"] = (
    results["esp_candidate"]
    == results["oracle_candidate"]
)

results["pairwise_correct"] = (
    results["pairwise_candidate"]
    == results["oracle_candidate"]
)

results["selected_correct"] = (
    results["selected_candidate"]
    == results["oracle_candidate"]
)

results["esp_regret"] = (
    results["oracle_fidelity"]
    - results["esp_fidelity"]
)

results["pairwise_regret"] = (
    results["oracle_fidelity"]
    - results["pairwise_fidelity"]
)

results["selected_regret"] = (
    results["oracle_fidelity"]
    - results["selected_fidelity"]
)

print("\n" + "=" * 80)
print("RESULTS")
print("=" * 80)

print(
    f"\nESP accuracy: "
    f"{results.esp_correct.mean():.2%}"
)

print(
    f"Pairwise accuracy: "
    f"{results.pairwise_correct.mean():.2%}"
)

print(
    f"Conservative hybrid accuracy: "
    f"{results.selected_correct.mean():.2%}"
)

print(
    f"\nESP average regret: "
    f"{results.esp_regret.mean():.6f}"
)

print(
    f"Pairwise average regret: "
    f"{results.pairwise_regret.mean():.6f}"
)

print(
    f"Conservative hybrid average regret: "
    f"{results.selected_regret.mean():.6f}"
)

print(
    f"\nESP maximum regret: "
    f"{results.esp_regret.max():.6f}"
)

print(
    f"Conservative hybrid maximum regret: "
    f"{results.selected_regret.max():.6f}"
)

print(
    f"\nPairwise overrides: "
    f"{int(results.used_pairwise.sum())}/{len(results)}"
)

print("\n" + "=" * 80)
print("THRESHOLDS")
print("=" * 80)

print(
    f"\nESP margin <= "
    f"{ESP_MARGIN_THRESHOLD}"
)

print(
    f"Pairwise advantage >= "
    f"{PAIRWISE_ADVANTAGE_THRESHOLD}"
)

print("\n" + "=" * 80)
print("DONE")
print("=" * 80)

results.to_csv(OUT, index=False)

print(f"\nSaved: {OUT}")