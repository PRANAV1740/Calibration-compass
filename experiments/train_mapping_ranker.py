"""
CalibrationCompass - Mapping-Aware Candidate Ranker

Goal:
Choose the best transpilation/layout candidate for each
(circuit, backend) pair using calibration-aware features.

This script:
1. Loads candidate_features_v2.csv
2. Splits by whole circuits so test circuits are unseen
3. Builds missing-value indicators
4. Handles categorical columns correctly
5. Removes duplicate feature names
6. Trains XGBoost ranking model
7. Compares:
      - Oracle
      - ESP baseline
      - Mapping-aware ranker
8. Calculates selection accuracy and regret
9. Saves predictions, selection results, and feature importance
"""

from pathlib import Path

import numpy as np
import pandas as pd
from xgboost import XGBRanker


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = BASE_DIR / "results" / "candidate_features_v2.csv"
RESULTS_DIR = BASE_DIR / "results"

# Whole circuits used for testing.
# These must NOT appear in training.
TEST_CIRCUITS = [2, 5, 8]

RANDOM_STATE = 42


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def find_column(df, candidates, description):
    """
    Find the first matching column from a list of possible names.
    """
    for col in candidates:
        if col in df.columns:
            return col

    raise ValueError(
        f"Could not find {description}.\n"
        f"Tried: {candidates}\n"
        f"Available columns:\n{list(df.columns)}"
    )


def selection_accuracy(group_df, selected_column, actual_column):
    """
    Calculate how often the model/baseline selected
    the actual best candidate.
    """

    correct = 0
    total = 0

    records = []

    for (circuit, backend), group in group_df.groupby(
        ["circuit_id", "backend"],
        sort=True
    ):
        group = group.copy()

        oracle_idx = group[actual_column].idxmax()
        selected_idx = group[selected_column].idxmax()

        oracle_candidate = group.loc[oracle_idx, "candidate_seed"]
        selected_candidate = group.loc[selected_idx, "candidate_seed"]

        oracle_fidelity = group.loc[oracle_idx, actual_column]
        selected_fidelity = group.loc[selected_idx, actual_column]

        regret = oracle_fidelity - selected_fidelity

        is_correct = oracle_candidate == selected_candidate

        if is_correct:
            correct += 1

        total += 1

        records.append(
            {
                "circuit_id": circuit,
                "backend": backend,
                "oracle_candidate": oracle_candidate,
                "selected_candidate": selected_candidate,
                "oracle_fidelity": oracle_fidelity,
                "selected_fidelity": selected_fidelity,
                "regret": regret,
                "correct": is_correct,
            }
        )

    accuracy = correct / total if total else 0.0

    return accuracy, pd.DataFrame(records)


# ============================================================
# START
# ============================================================

print("=" * 90)
print("CALIBRATIONCOMPASS - MAPPING-AWARE RANKER")
print("=" * 90)


# ============================================================
# LOAD DATA
# ============================================================

if not DATA_FILE.exists():
    raise FileNotFoundError(
        f"\nDataset not found:\n{DATA_FILE}\n\n"
        "Make sure candidate_features_v2.csv exists in results."
    )

df = pd.read_csv(DATA_FILE)

print(f"\nRows: {len(df)}")
print(f"Columns: {len(df.columns)}")


# ============================================================
# FIND IMPORTANT COLUMNS
# ============================================================

circuit_col = find_column(
    df,
    ["circuit_id", "circuit"],
    "circuit ID"
)

backend_col = find_column(
    df,
    ["backend"],
    "backend"
)

candidate_col = find_column(
    df,
    ["candidate_seed", "seed", "candidate"],
    "candidate seed"
)

target_col = find_column(
    df,
    ["actual_fidelity", "fidelity"],
    "actual fidelity"
)

esp_col = find_column(
    df,
    ["esp", "ESP", "esp_score"],
    "ESP score"
)


# Normalize the important column names
df = df.rename(
    columns={
        circuit_col: "circuit_id",
        backend_col: "backend",
        candidate_col: "candidate_seed",
        target_col: "actual_fidelity",
        esp_col: "esp",
    }
)


# ============================================================
# BASIC CLEANING
# ============================================================

# Remove completely empty rows
df = df.dropna(axis=0, how="all").reset_index(drop=True)

# Remove duplicate column names if the CSV itself contains them.
# This prevents XGBoost from crashing later.
duplicate_mask = df.columns.duplicated()

if duplicate_mask.any():
    duplicate_names = df.columns[duplicate_mask].tolist()

    print(
        "\nDuplicate columns found in CSV and removed:"
    )
    print(sorted(set(duplicate_names)))

    df = df.loc[:, ~df.columns.duplicated()].copy()


# Make sure key columns have usable values
df["circuit_id"] = pd.to_numeric(
    df["circuit_id"],
    errors="coerce"
)

df["candidate_seed"] = pd.to_numeric(
    df["candidate_seed"],
    errors="coerce"
)

df["actual_fidelity"] = pd.to_numeric(
    df["actual_fidelity"],
    errors="coerce"
)

df["esp"] = pd.to_numeric(
    df["esp"],
    errors="coerce"
)

df["backend"] = df["backend"].astype(str)


# Remove rows missing the essential information
required = [
    "circuit_id",
    "backend",
    "candidate_seed",
    "actual_fidelity",
    "esp",
]

before = len(df)

df = df.dropna(
    subset=required
).reset_index(drop=True)

removed = before - len(df)

if removed:
    print(f"\nRemoved {removed} incomplete rows.")


# ============================================================
# SORT DATA
# ============================================================

# Each ranking group must be contiguous.
# A group = one circuit + one backend.
df = df.sort_values(
    by=[
        "circuit_id",
        "backend",
        "candidate_seed",
    ]
).reset_index(drop=True)


# ============================================================
# TRAIN / TEST SPLIT
# ============================================================

all_circuits = sorted(
    df["circuit_id"].unique().tolist()
)

test_circuits = [
    c for c in TEST_CIRCUITS
    if c in all_circuits
]

train_circuits = [
    c for c in all_circuits
    if c not in test_circuits
]

train_df = df[
    df["circuit_id"].isin(train_circuits)
].copy()

test_df = df[
    df["circuit_id"].isin(test_circuits)
].copy()


print(f"\nTraining circuits: {train_circuits}")
print(f"Testing circuits: {test_circuits}")

print(f"\nTraining rows: {len(train_df)}")
print(f"Testing rows: {len(test_df)}")


# ============================================================
# BUILD FEATURE TABLE
# ============================================================

# Columns that are identifiers / targets and must NOT be used
# as ML features.

DROP_COLUMNS = {
    "circuit_id",
    "candidate_seed",
    "actual_fidelity",
    "esp",
}


# Drop columns that directly reveal physical mapping IDs.
#
# Examples:
# logical_0_physical
# logical_1_physical
# physical_qubits
#
# Raw physical IDs should not be treated as meaningful numeric
# quantities by the model.

mapping_columns_to_drop = []

for col in df.columns:

    lower = col.lower()

    if lower == "physical_qubits":
        mapping_columns_to_drop.append(col)

    elif lower == "mapping":
        mapping_columns_to_drop.append(col)

    elif lower.endswith("_physical"):
        mapping_columns_to_drop.append(col)


DROP_COLUMNS.update(mapping_columns_to_drop)


# Keep only columns which actually exist
DROP_COLUMNS = [
    col
    for col in DROP_COLUMNS
    if col in df.columns
]


X_all = df.drop(
    columns=DROP_COLUMNS,
    errors="ignore"
).copy()


# ============================================================
# HANDLE DUPLICATE FEATURE NAMES
# ============================================================

if X_all.columns.duplicated().any():

    duplicates = X_all.columns[
        X_all.columns.duplicated()
    ].tolist()

    print(
        "\nDuplicate feature names detected before encoding:"
    )
    print(sorted(set(duplicates)))

    X_all = X_all.loc[
        :,
        ~X_all.columns.duplicated(keep="first")
    ].copy()


# ============================================================
# MISSING VALUE INDICATORS
# ============================================================

# Explicitly tell the model whether a feature was missing.
#
# We do NOT replace missing values with zero.
# XGBoost can handle NaN values natively.

missing_columns = []

for col in X_all.columns:

    if X_all[col].isna().any():

        missing_columns.append(col)

        indicator_name = f"{col}__missing"

        X_all[indicator_name] = (
            X_all[col].isna().astype(float)
        )


print(
    f"\nFeatures with missing values: "
    f"{len(missing_columns)}"
)

if missing_columns:

    print(
        "Missing-value indicator columns added."
    )


# ============================================================
# HANDLE CATEGORICAL FEATURES
# ============================================================

# Backend is categorical.
#
# We deliberately encode it exactly once here.
# This avoids the duplicate backend_Fez /
# backend_Sherbrooke / backend_Torino problem.

categorical_columns = X_all.select_dtypes(
    include=[
        "object",
        "string",
        "category"
    ]
).columns.tolist()


if categorical_columns:

    print(
        "\nCategorical columns encoded:"
    )

    for col in categorical_columns:
        print(f"  - {col}")

    X_all = pd.get_dummies(
        X_all,
        columns=categorical_columns,
        dummy_na=True
    )


# ============================================================
# FINAL DUPLICATE CHECK
# ============================================================

if X_all.columns.duplicated().any():

    duplicates = X_all.columns[
        X_all.columns.duplicated()
    ].tolist()

    print(
        "\nDuplicate columns after encoding:"
    )
    print(sorted(set(duplicates)))

    X_all = X_all.loc[
        :,
        ~X_all.columns.duplicated(keep="first")
    ].copy()


# ============================================================
# REMOVE ANY REMAINING NON-NUMERIC COLUMNS
# ============================================================

remaining_non_numeric = X_all.select_dtypes(
    exclude=[np.number, "bool"]
).columns.tolist()

if remaining_non_numeric:

    print(
        "\nDropping remaining non-numeric columns:"
    )

    for col in remaining_non_numeric:
        print(f"  - {col}")

    X_all = X_all.drop(
        columns=remaining_non_numeric
    )


# ============================================================
# CONVERT TO FLOAT
# ============================================================

X_all = X_all.astype(float)


# ============================================================
# FINAL SANITY CHECK
# ============================================================

if X_all.columns.duplicated().any():

    raise RuntimeError(
        "Duplicate columns still exist after preprocessing."
    )

if not all(
    np.issubdtype(dtype, np.number)
    for dtype in X_all.dtypes
):

    raise RuntimeError(
        "Some features are still non-numeric."
    )


print(
    f"\nFinal ML feature count: {X_all.shape[1]}"
)

print(
    f"Final feature matrix shape: {X_all.shape}"
)


# ============================================================
# ALIGN TRAIN / TEST USING ORIGINAL DATA INDICES
# ============================================================

train_mask = df["circuit_id"].isin(
    train_circuits
)

test_mask = df["circuit_id"].isin(
    test_circuits
)

X_train = X_all.loc[
    train_mask
].copy()

X_test = X_all.loc[
    test_mask
].copy()

y_train = df.loc[
    train_mask,
    "actual_fidelity"
].astype(float).values

y_test = df.loc[
    test_mask,
    "actual_fidelity"
].astype(float).values


# ============================================================
# BUILD RANKING GROUPS
# ============================================================

def get_groups(frame):
    """
    Return group sizes for XGBoost ranking.

    Each group corresponds to:
        one circuit + one backend

    We expect six candidate seeds per group.
    """

    groups = []

    for _, group in frame.groupby(
        ["circuit_id", "backend"],
        sort=True
    ):
        groups.append(len(group))

    return groups


train_groups = get_groups(train_df)
test_groups = get_groups(test_df)


print(
    f"\nTraining ranking groups: "
    f"{len(train_groups)}"
)

print(
    f"Testing ranking groups: "
    f"{len(test_groups)}"
)

print(
    f"Candidates per training group: "
    f"{sorted(set(train_groups))}"
)

print(
    f"Candidates per testing group: "
    f"{sorted(set(test_groups))}"
)


# ============================================================
# CHECK GROUPS
# ============================================================

if sum(train_groups) != len(X_train):

    raise RuntimeError(
        "Training group sizes do not match training rows."
    )

if sum(test_groups) != len(X_test):

    raise RuntimeError(
        "Testing group sizes do not match testing rows."
    )

if len(set(train_groups)) != 1 or train_groups[0] != 6:

    raise RuntimeError(
        "Expected exactly 6 candidates per training group."
    )

if len(set(test_groups)) != 1 or test_groups[0] != 6:

    raise RuntimeError(
        "Expected exactly 6 candidates per testing group."
    )


# ============================================================
# TRAIN XGBOOST RANKER
# ============================================================

print("\nTraining mapping-aware XGBoost ranker...")

model = XGBRanker(
    objective="rank:pairwise",
    n_estimators=300,
    learning_rate=0.05,
    max_depth=4,
    min_child_weight=1,
    subsample=0.8,
    colsample_bytree=0.8,
    reg_lambda=1.0,
    random_state=RANDOM_STATE,
    tree_method="hist",
    eval_metric="ndcg",
)


model.fit(
    X_train,
    y_train,
    group=train_groups
)


print("Training completed.")


# ============================================================
# PREDICTIONS
# ============================================================

ranker_scores = model.predict(
    X_all
)


df["ranker_score"] = ranker_scores


# ============================================================
# ESP SELECTION
# ============================================================

df["esp_selected_marker"] = 0.0

for (circuit, backend), group in df.groupby(
    ["circuit_id", "backend"],
    sort=True
):

    best_idx = group["esp"].idxmax()

    df.loc[
        best_idx,
        "esp_selected_marker"
    ] = 1.0


# ============================================================
# RANKER SELECTION
# ============================================================

df["ranker_selected_marker"] = 0.0

for (circuit, backend), group in df.groupby(
    ["circuit_id", "backend"],
    sort=True
):

    best_idx = group["ranker_score"].idxmax()

    df.loc[
        best_idx,
        "ranker_selected_marker"
    ] = 1.0


# ============================================================
# TEST-SET EVALUATION
# ============================================================

test_results = df[
    df["circuit_id"].isin(test_circuits)
].copy()


# ------------------------------------------------------------
# Oracle candidate
# ------------------------------------------------------------

oracle_rows = []

for (circuit, backend), group in test_results.groupby(
    ["circuit_id", "backend"],
    sort=True
):

    oracle_idx = group["actual_fidelity"].idxmax()
    oracle = group.loc[oracle_idx]

    oracle_rows.append(
        {
            "circuit_id": circuit,
            "backend": backend,
            "oracle_candidate": oracle["candidate_seed"],
            "oracle_fidelity": oracle["actual_fidelity"],
        }
    )

oracle_df = pd.DataFrame(oracle_rows)


# ------------------------------------------------------------
# ESP candidate
# ------------------------------------------------------------

esp_rows = []

for (circuit, backend), group in test_results.groupby(
    ["circuit_id", "backend"],
    sort=True
):

    best_idx = group["esp"].idxmax()
    best = group.loc[best_idx]

    esp_rows.append(
        {
            "circuit_id": circuit,
            "backend": backend,
            "esp_candidate": best["candidate_seed"],
            "esp_fidelity": best["actual_fidelity"],
            "esp_score": best["esp"],
        }
    )

esp_df = pd.DataFrame(esp_rows)


# ------------------------------------------------------------
# Ranker candidate
# ------------------------------------------------------------

ranker_rows = []

for (circuit, backend), group in test_results.groupby(
    ["circuit_id", "backend"],
    sort=True
):

    best_idx = group["ranker_score"].idxmax()
    best = group.loc[best_idx]

    ranker_rows.append(
        {
            "circuit_id": circuit,
            "backend": backend,
            "ranker_candidate": best["candidate_seed"],
            "ranker_fidelity": best["actual_fidelity"],
            "ranker_score": best["ranker_score"],
        }
    )

ranker_df = pd.DataFrame(ranker_rows)


# ============================================================
# COMBINE RESULTS
# ============================================================

comparison = oracle_df.merge(
    esp_df,
    on=["circuit_id", "backend"],
    how="left"
)

comparison = comparison.merge(
    ranker_df,
    on=["circuit_id", "backend"],
    how="left"
)


# ============================================================
# ACCURACY
# ============================================================

comparison["esp_correct"] = (
    comparison["esp_candidate"]
    ==
    comparison["oracle_candidate"]
)

comparison["ranker_correct"] = (
    comparison["ranker_candidate"]
    ==
    comparison["oracle_candidate"]
)


esp_accuracy = comparison[
    "esp_correct"
].mean()

ranker_accuracy = comparison[
    "ranker_correct"
].mean()


# ============================================================
# REGRET
# ============================================================

comparison["esp_regret"] = (
    comparison["oracle_fidelity"]
    -
    comparison["esp_fidelity"]
)

comparison["ranker_regret"] = (
    comparison["oracle_fidelity"]
    -
    comparison["ranker_fidelity"]
)


# ============================================================
# PRINT RESULTS
# ============================================================

print("\n")
print("=" * 90)
print("TEST RESULTS")
print("=" * 90)

print(
    f"\nTest decisions: {len(comparison)}"
)

print(
    f"\nESP selection accuracy: "
    f"{esp_accuracy:.2%}"
)

print(
    f"Mapping-aware ranker selection accuracy: "
    f"{ranker_accuracy:.2%}"
)


print(
    f"\nESP average regret: "
    f"{comparison['esp_regret'].mean():.6f}"
)

print(
    f"Ranker average regret: "
    f"{comparison['ranker_regret'].mean():.6f}"
)


print(
    f"\nESP maximum regret: "
    f"{comparison['esp_regret'].max():.6f}"
)

print(
    f"Ranker maximum regret: "
    f"{comparison['ranker_regret'].max():.6f}"
)


# ============================================================
# WORST CASES
# ============================================================

print("\n")
print("=" * 90)
print("LARGEST RANKER REGRETS")
print("=" * 90)

worst = comparison.sort_values(
    "ranker_regret",
    ascending=False
).head(10)

for _, row in worst.iterrows():

    print(
        f"\nCircuit {int(row['circuit_id'])} | "
        f"{row['backend']}"
    )

    print(
        f"Oracle candidate: {int(row['oracle_candidate'])} "
        f"-> {row['oracle_fidelity']:.6f}"
    )

    print(
        f"ESP candidate: {int(row['esp_candidate'])} "
        f"-> {row['esp_fidelity']:.6f}"
    )

    print(
        f"Ranker candidate: {int(row['ranker_candidate'])} "
        f"-> {row['ranker_fidelity']:.6f}"
    )

    print(
        f"Ranker regret: "
        f"{row['ranker_regret']:.6f}"
    )


# ============================================================
# FEATURE IMPORTANCE
# ============================================================

importance = pd.DataFrame(
    {
        "feature": X_all.columns,
        "importance": model.feature_importances_,
    }
).sort_values(
    "importance",
    ascending=False
).reset_index(drop=True)


print("\n")
print("=" * 90)
print("TOP FEATURES")
print("=" * 90)

print(
    importance.head(20).to_string(
        index=False
    )
)


# ============================================================
# SAVE PREDICTIONS
# ============================================================

prediction_columns = [
    "circuit_id",
    "backend",
    "candidate_seed",
    "esp",
    "ranker_score",
    "actual_fidelity",
]

prediction_output = df[
    prediction_columns
].copy()

prediction_file = (
    RESULTS_DIR /
    "mapping_ranker_predictions.csv"
)

prediction_output.to_csv(
    prediction_file,
    index=False
)


# ============================================================
# SAVE SELECTION COMPARISON
# ============================================================

selection_file = (
    RESULTS_DIR /
    "mapping_ranker_selection.csv"
)

comparison.to_csv(
    selection_file,
    index=False
)


# ============================================================
# SAVE FEATURE IMPORTANCE
# ============================================================

importance_file = (
    RESULTS_DIR /
    "mapping_ranker_feature_importance.csv"
)

importance.to_csv(
    importance_file,
    index=False
)


# ============================================================
# FINAL SUMMARY
# ============================================================

print("\n")
print("=" * 90)
print("FILES SAVED")
print("=" * 90)

print(
    f"\n{prediction_file}"
)

print(
    f"{selection_file}"
)

print(
    f"{importance_file}"
)


print("\n")
print("=" * 90)
print("DONE")
print("=" * 90)