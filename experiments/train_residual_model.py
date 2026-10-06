"""
CalibrationCompass - Mapping-Aware Residual Model

Goal:
Use ESP as the baseline and train ML to predict the
additional fidelity gain/loss caused by the selected mapping.

Final decision:

    final_score = ESP + predicted_residual

where:

    residual = actual_fidelity - ESP

The model is trained on whole circuits and tested on
completely unseen circuits.
"""

from pathlib import Path

import numpy as np
import pandas as pd
from xgboost import XGBRegressor


# ============================================================
# CONFIG
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_FILE = (
    BASE_DIR
    / "results"
    / "candidate_features_v2.csv"
)

RESULTS_DIR = BASE_DIR / "results"

TEST_CIRCUITS = [2, 5, 8]

RANDOM_STATE = 42


# ============================================================
# HELPER
# ============================================================

def find_column(df, candidates, description):

    for column in candidates:

        if column in df.columns:
            return column

    raise ValueError(
        f"\nCould not find {description}.\n"
        f"Tried: {candidates}\n\n"
        f"Available columns:\n{list(df.columns)}"
    )


# ============================================================
# START
# ============================================================

print("=" * 90)
print("CALIBRATIONCOMPASS - MAPPING-AWARE RESIDUAL MODEL")
print("=" * 90)


# ============================================================
# LOAD DATA
# ============================================================

if not DATA_FILE.exists():

    raise FileNotFoundError(
        f"\nDataset not found:\n{DATA_FILE}\n"
    )

df = pd.read_csv(DATA_FILE)

print(f"\nRows: {len(df)}")
print(f"Columns: {len(df.columns)}")


# ============================================================
# IDENTIFY IMPORTANT COLUMNS
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

fidelity_col = find_column(
    df,
    ["actual_fidelity", "fidelity"],
    "actual fidelity"
)

esp_col = find_column(
    df,
    ["esp", "ESP", "esp_score"],
    "ESP score"
)


# ============================================================
# NORMALIZE COLUMN NAMES
# ============================================================

df = df.rename(
    columns={
        circuit_col: "circuit_id",
        backend_col: "backend",
        candidate_col: "candidate_seed",
        fidelity_col: "actual_fidelity",
        esp_col: "esp",
    }
)


# ============================================================
# REMOVE DUPLICATE COLUMNS
# ============================================================

if df.columns.duplicated().any():

    duplicates = df.columns[
        df.columns.duplicated()
    ].tolist()

    print("\nRemoving duplicate columns:")
    print(sorted(set(duplicates)))

    df = df.loc[
        :,
        ~df.columns.duplicated(keep="first")
    ].copy()


# ============================================================
# CLEAN IMPORTANT DATA
# ============================================================

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


required_columns = [
    "circuit_id",
    "backend",
    "candidate_seed",
    "actual_fidelity",
    "esp",
]

before = len(df)

df = df.dropna(
    subset=required_columns
).reset_index(drop=True)

removed = before - len(df)

if removed > 0:

    print(
        f"\nRemoved {removed} incomplete rows."
    )


# ============================================================
# SORT
# ============================================================

df = df.sort_values(
    by=[
        "circuit_id",
        "backend",
        "candidate_seed",
    ]
).reset_index(drop=True)


# ============================================================
# CREATE RESIDUAL TARGET
# ============================================================

df["residual"] = (
    df["actual_fidelity"]
    -
    df["esp"]
)

print("\nResidual statistics:")

print(
    df["residual"].describe().to_string()
)


# ============================================================
# TRAIN / TEST CIRCUITS
# ============================================================

all_circuits = sorted(
    df["circuit_id"].unique().tolist()
)

test_circuits = [
    circuit
    for circuit in TEST_CIRCUITS
    if circuit in all_circuits
]

train_circuits = [
    circuit
    for circuit in all_circuits
    if circuit not in test_circuits
]

train_mask = df["circuit_id"].isin(
    train_circuits
)

test_mask = df["circuit_id"].isin(
    test_circuits
)

train_df = df.loc[
    train_mask
].copy()

test_df = df.loc[
    test_mask
].copy()

print(
    f"\nTraining circuits: {train_circuits}"
)

print(
    f"Testing circuits: {test_circuits}"
)

print(
    f"\nTraining rows: {len(train_df)}"
)

print(
    f"Testing rows: {len(test_df)}"
)


# ============================================================
# BUILD FEATURES
# ============================================================

# We do not give the model:
#
# circuit_id
# candidate_seed
# actual_fidelity
# residual
#
# candidate_seed is only an identifier.
# actual_fidelity/residual are targets.
#
# ESP IS retained because the model is specifically learning
# the correction to ESP.

DROP_COLUMNS = {
    "circuit_id",
    "candidate_seed",
    "actual_fidelity",
    "residual",
}


# ------------------------------------------------------------
# Remove raw physical ID columns
# ------------------------------------------------------------

for column in df.columns:

    lower = column.lower()

    if lower == "physical_qubits":

        DROP_COLUMNS.add(column)

    elif lower == "mapping":

        DROP_COLUMNS.add(column)

    elif lower.endswith("_physical"):

        DROP_COLUMNS.add(column)


X_all = df.drop(
    columns=[
        column
        for column in DROP_COLUMNS
        if column in df.columns
    ],
    errors="ignore"
).copy()


# ============================================================
# REMOVE DUPLICATE FEATURE NAMES
# ============================================================

if X_all.columns.duplicated().any():

    duplicates = X_all.columns[
        X_all.columns.duplicated()
    ].tolist()

    print(
        "\nDuplicate feature names found:"
    )

    print(
        sorted(set(duplicates))
    )

    X_all = X_all.loc[
        :,
        ~X_all.columns.duplicated(keep="first")
    ].copy()


# ============================================================
# MISSING VALUE INDICATORS
# ============================================================

missing_features = []

for column in X_all.columns:

    if X_all[column].isna().any():

        missing_features.append(column)

        indicator = (
            f"{column}__missing"
        )

        X_all[indicator] = (
            X_all[column]
            .isna()
            .astype(float)
        )


print(
    f"\nFeatures containing missing values: "
    f"{len(missing_features)}"
)

if missing_features:

    print(
        "Missingness indicators added."
    )


# ============================================================
# CATEGORICAL ENCODING
# ============================================================

categorical_columns = (
    X_all
    .select_dtypes(
        include=[
            "object",
            "string",
            "category",
        ]
    )
    .columns
    .tolist()
)

if categorical_columns:

    print(
        "\nCategorical columns encoded:"
    )

    for column in categorical_columns:

        print(
            f"  - {column}"
        )

    X_all = pd.get_dummies(
        X_all,
        columns=categorical_columns,
        dummy_na=True
    )


# ============================================================
# SECOND DUPLICATE CHECK
# ============================================================

if X_all.columns.duplicated().any():

    duplicates = X_all.columns[
        X_all.columns.duplicated()
    ].tolist()

    print(
        "\nDuplicate columns after encoding:"
    )

    print(
        sorted(set(duplicates))
    )

    X_all = X_all.loc[
        :,
        ~X_all.columns.duplicated(keep="first")
    ].copy()


# ============================================================
# DROP REMAINING NON-NUMERIC FEATURES
# ============================================================

non_numeric = X_all.select_dtypes(
    exclude=[
        np.number,
        "bool",
    ]
).columns.tolist()

if non_numeric:

    print(
        "\nDropping remaining non-numeric columns:"
    )

    for column in non_numeric:

        print(
            f"  - {column}"
        )

    X_all = X_all.drop(
        columns=non_numeric
    )


# ============================================================
# FLOAT CONVERSION
# ============================================================

X_all = X_all.astype(float)


# ============================================================
# FINAL FEATURE CHECK
# ============================================================

if X_all.columns.duplicated().any():

    raise RuntimeError(
        "Duplicate columns remain."
    )

if not all(
    np.issubdtype(dtype, np.number)
    for dtype in X_all.dtypes
):

    raise RuntimeError(
        "Non-numeric feature remains."
    )


print(
    f"\nFinal feature count: "
    f"{X_all.shape[1]}"
)

print(
    f"Feature matrix shape: "
    f"{X_all.shape}"
)


# ============================================================
# TRAIN / TEST MATRICES
# ============================================================

X_train = X_all.loc[
    train_mask
].copy()

X_test = X_all.loc[
    test_mask
].copy()

y_train = df.loc[
    train_mask,
    "residual"
].astype(float).values

y_test = df.loc[
    test_mask,
    "residual"
].astype(float).values


# ============================================================
# TRAIN MODEL
# ============================================================

print("\n")
print("=" * 90)
print("TRAINING RESIDUAL MODEL")
print("=" * 90)

model = XGBRegressor(
    objective="reg:squarederror",

    n_estimators=250,

    learning_rate=0.03,

    max_depth=2,

    min_child_weight=5,

    subsample=0.8,

    colsample_bytree=0.7,

    reg_alpha=0.5,

    reg_lambda=5.0,

    random_state=RANDOM_STATE,

    tree_method="hist",
)


model.fit(
    X_train,
    y_train
)

print(
    "\nTraining completed."
)


# ============================================================
# PREDICT RESIDUAL
# ============================================================

df["predicted_residual"] = (
    model.predict(X_all)
)


# ============================================================
# FINAL CALIBRATIONCOMPASS SCORE
# ============================================================

df["calibrationcompass_score"] = (
    df["esp"]
    +
    df["predicted_residual"]
)


# ============================================================
# TEST DATA
# ============================================================

test_results = df[
    df["circuit_id"].isin(
        test_circuits
    )
].copy()


# ============================================================
# SELECTION
# ============================================================

records = []


for (circuit, backend), group in test_results.groupby(
    ["circuit_id", "backend"],
    sort=True
):

    group = group.copy()


    # --------------------------------------------------------
    # ORACLE
    # --------------------------------------------------------

    oracle_idx = group[
        "actual_fidelity"
    ].idxmax()

    oracle = group.loc[
        oracle_idx
    ]


    # --------------------------------------------------------
    # ESP
    # --------------------------------------------------------

    esp_idx = group[
        "esp"
    ].idxmax()

    esp = group.loc[
        esp_idx
    ]


    # --------------------------------------------------------
    # CALIBRATIONCOMPASS
    # --------------------------------------------------------

    cc_idx = group[
        "calibrationcompass_score"
    ].idxmax()

    cc = group.loc[
        cc_idx
    ]


    # --------------------------------------------------------
    # RESULTS
    # --------------------------------------------------------

    records.append(
        {
            "circuit_id": circuit,

            "backend": backend,

            "oracle_candidate":
                oracle["candidate_seed"],

            "oracle_fidelity":
                oracle["actual_fidelity"],

            "esp_candidate":
                esp["candidate_seed"],

            "esp_fidelity":
                esp["actual_fidelity"],

            "esp_score":
                esp["esp"],

            "cc_candidate":
                cc["candidate_seed"],

            "cc_fidelity":
                cc["actual_fidelity"],

            "cc_score":
                cc["calibrationcompass_score"],

            "cc_predicted_residual":
                cc["predicted_residual"],
        }
    )


comparison = pd.DataFrame(
    records
)


# ============================================================
# ACCURACY
# ============================================================

comparison["esp_correct"] = (
    comparison["esp_candidate"]
    ==
    comparison["oracle_candidate"]
)

comparison["cc_correct"] = (
    comparison["cc_candidate"]
    ==
    comparison["oracle_candidate"]
)


esp_accuracy = (
    comparison["esp_correct"]
    .mean()
)

cc_accuracy = (
    comparison["cc_correct"]
    .mean()
)


# ============================================================
# REGRET
# ============================================================

comparison["esp_regret"] = (
    comparison["oracle_fidelity"]
    -
    comparison["esp_fidelity"]
)

comparison["cc_regret"] = (
    comparison["oracle_fidelity"]
    -
    comparison["cc_fidelity"]
)


# ============================================================
# PREDICTION ERROR
# ============================================================

test_results["predicted_fidelity"] = (
    test_results["esp"]
    +
    test_results["predicted_residual"]
)

residual_mae = np.mean(
    np.abs(
        test_results["residual"]
        -
        test_results["predicted_residual"]
    )
)

residual_rmse = np.sqrt(
    np.mean(
        (
            test_results["residual"]
            -
            test_results["predicted_residual"]
        ) ** 2
    )
)


# ============================================================
# PRINT RESULTS
# ============================================================

print("\n")
print("=" * 90)
print("CALIBRATIONCOMPASS TEST RESULTS")
print("=" * 90)

print(
    f"\nTest decisions: "
    f"{len(comparison)}"
)

print(
    f"\nESP selection accuracy: "
    f"{esp_accuracy:.2%}"
)

print(
    f"CalibrationCompass selection accuracy: "
    f"{cc_accuracy:.2%}"
)

print(
    f"\nESP average regret: "
    f"{comparison['esp_regret'].mean():.6f}"
)

print(
    f"CalibrationCompass average regret: "
    f"{comparison['cc_regret'].mean():.6f}"
)

print(
    f"\nESP maximum regret: "
    f"{comparison['esp_regret'].max():.6f}"
)

print(
    f"CalibrationCompass maximum regret: "
    f"{comparison['cc_regret'].max():.6f}"
)

print(
    f"\nResidual MAE: "
    f"{residual_mae:.6f}"
)

print(
    f"Residual RMSE: "
    f"{residual_rmse:.6f}"
)


# ============================================================
# DECISION-BY-DECISION TABLE
# ============================================================

print("\n")
print("=" * 90)
print("DECISION COMPARISON")
print("=" * 90)

display_columns = [
    "circuit_id",
    "backend",
    "oracle_candidate",
    "esp_candidate",
    "cc_candidate",
    "oracle_fidelity",
    "esp_fidelity",
    "cc_fidelity",
    "esp_regret",
    "cc_regret",
]


print(
    comparison[
        display_columns
    ].to_string(index=False)
)


# ============================================================
# WHERE CALIBRATIONCOMPASS IMPROVED ESP
# ============================================================

improved = comparison[
    comparison["cc_regret"]
    <
    comparison["esp_regret"]
]

worse = comparison[
    comparison["cc_regret"]
    >
    comparison["esp_regret"]
]


print("\n")
print("=" * 90)
print("ESP vs CALIBRATIONCOMPASS")
print("=" * 90)

print(
    f"\nCalibrationCompass improved "
    f"ESP on {len(improved)}/{len(comparison)} "
    f"test decisions."
)

print(
    f"CalibrationCompass was worse than ESP on "
    f"{len(worse)}/{len(comparison)} "
    f"test decisions."
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
print("TOP RESIDUAL-MODEL FEATURES")
print("=" * 90)

print(
    importance
    .head(20)
    .to_string(index=False)
)


# ============================================================
# SAVE PREDICTIONS
# ============================================================

prediction_columns = [
    "circuit_id",
    "backend",
    "candidate_seed",
    "esp",
    "actual_fidelity",
    "residual",
    "predicted_residual",
    "calibrationcompass_score",
]

prediction_file = (
    RESULTS_DIR
    / "residual_model_predictions.csv"
)

df[
    prediction_columns
].to_csv(
    prediction_file,
    index=False
)


# ============================================================
# SAVE SELECTION RESULTS
# ============================================================

selection_file = (
    RESULTS_DIR
    / "residual_model_selection.csv"
)

comparison.to_csv(
    selection_file,
    index=False
)


# ============================================================
# SAVE FEATURE IMPORTANCE
# ============================================================

importance_file = (
    RESULTS_DIR
    / "residual_model_feature_importance.csv"
)

importance.to_csv(
    importance_file,
    index=False
)


# ============================================================
# FINAL
# ============================================================

print("\n")
print("=" * 90)
print("FILES SAVED")
print("=" * 90)

print(
    f"\n{prediction_file}"
)

print(
    selection_file
)

print(
    importance_file
)

print("\n")
print("=" * 90)
print("DONE")
print("=" * 90)