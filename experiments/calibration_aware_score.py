"""
CalibrationCompass - Calibration-Aware Candidate Scoring

ESP is used as the baseline.

CalibrationCompass adds mapping-aware penalties based on:
    - readout risk
    - two-qubit edge risk
    - one-qubit/SX risk
    - two-qubit gate risk

Weights are learned ONLY from training circuits.

Test circuits are completely unseen.
"""

from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_FILE = (
    BASE_DIR
    / "results"
    / "candidate_features_v2.csv"
)

RESULTS_DIR = BASE_DIR / "results"

TEST_CIRCUITS = [2, 5, 8]


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def find_column(df, names, description):

    for name in names:

        if name in df.columns:
            return name

    raise ValueError(
        f"\nCould not find {description}.\n"
        f"Tried: {names}\n\n"
        f"Available columns:\n{list(df.columns)}"
    )


def numeric_column(df, name):

    if name in df.columns:

        return pd.to_numeric(
            df[name],
            errors="coerce"
        )

    return pd.Series(
        np.nan,
        index=df.index
    )


def minmax_normalize(values):

    values = pd.to_numeric(
        values,
        errors="coerce"
    ).astype(float)

    if values.isna().all():

        return pd.Series(
            0.0,
            index=values.index
        )

    median_value = values.median()

    values = values.fillna(
        median_value
    )

    minimum = values.min()
    maximum = values.max()

    if (
        not np.isfinite(minimum)
        or
        not np.isfinite(maximum)
        or
        maximum - minimum < 1e-12
    ):

        return pd.Series(
            0.0,
            index=values.index
        )

    return (
        (values - minimum)
        /
        (maximum - minimum)
    )


# ============================================================
# START
# ============================================================

print("=" * 90)
print("CALIBRATIONCOMPASS - CALIBRATION-AWARE SCORE")
print("=" * 90)


# ============================================================
# LOAD DATA
# ============================================================

if not DATA_FILE.exists():

    raise FileNotFoundError(
        f"\nDataset not found:\n{DATA_FILE}"
    )


df = pd.read_csv(
    DATA_FILE
)

print(
    f"\nRows: {len(df)}"
)

print(
    f"Columns: {len(df.columns)}"
)


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

    print(
        "\nRemoving duplicate columns:"
    )

    print(
        sorted(set(duplicates))
    )

    df = df.loc[
        :,
        ~df.columns.duplicated(
            keep="first"
        )
    ].copy()


# ============================================================
# CLEAN DATA
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

df["backend"] = df[
    "backend"
].astype(str)


required_columns = [
    "circuit_id",
    "backend",
    "candidate_seed",
    "actual_fidelity",
    "esp",
]


before_rows = len(df)

df = df.dropna(
    subset=required_columns
).reset_index(
    drop=True
)

removed_rows = (
    before_rows
    -
    len(df)
)

if removed_rows > 0:

    print(
        f"\nRemoved {removed_rows} "
        f"incomplete rows."
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
).reset_index(
    drop=True
)


# ============================================================
# BUILD CALIBRATION RISK COMPONENTS
# ============================================================

# ------------------------------------------------------------
# READOUT RISK
# ------------------------------------------------------------

if "weighted_readout_total" in df.columns:

    readout_risk = numeric_column(
        df,
        "weighted_readout_total"
    )

elif "weighted_readout_2q" in df.columns:

    readout_risk = numeric_column(
        df,
        "weighted_readout_2q"
    )

else:

    readout_columns = [
        col
        for col in df.columns
        if col.startswith("logical_")
        and col.endswith("_readout")
    ]

    if readout_columns:

        readout_risk = (
            df[readout_columns]
            .apply(
                pd.to_numeric,
                errors="coerce"
            )
            .mean(axis=1)
        )

    else:

        readout_risk = pd.Series(
            0.0,
            index=df.index
        )


# ------------------------------------------------------------
# EDGE RISK
# ------------------------------------------------------------

if "edge_exposure" in df.columns:

    edge_risk = numeric_column(
        df,
        "edge_exposure"
    )

elif "max_edge_error" in df.columns:

    edge_risk = numeric_column(
        df,
        "max_edge_error"
    )

else:

    edge_risk = pd.Series(
        0.0,
        index=df.index
    )


# ------------------------------------------------------------
# ONE-QUBIT / SX RISK
# ------------------------------------------------------------

if "weighted_sx_total" in df.columns:

    sx_risk = numeric_column(
        df,
        "weighted_sx_total"
    )

elif "avg_sx_error" in df.columns:

    if "one_qubit_gates" in df.columns:

        sx_risk = (
            numeric_column(
                df,
                "avg_sx_error"
            )
            *
            numeric_column(
                df,
                "one_qubit_gates"
            )
        )

    else:

        sx_risk = numeric_column(
            df,
            "avg_sx_error"
        )

else:

    sx_risk = pd.Series(
        0.0,
        index=df.index
    )


# ------------------------------------------------------------
# TWO-QUBIT GATE RISK
# ------------------------------------------------------------

if "two_qubit_gates" in df.columns:

    two_qubit_count = numeric_column(
        df,
        "two_qubit_gates"
    )

else:

    two_qubit_count = pd.Series(
        1.0,
        index=df.index
    )


if "avg_cz_error" in df.columns:

    gate_risk = (
        numeric_column(
            df,
            "avg_cz_error"
        )
        *
        two_qubit_count
    )

elif "max_cz_error" in df.columns:

    gate_risk = (
        numeric_column(
            df,
            "max_cz_error"
        )
        *
        two_qubit_count
    )

else:

    gate_risk = pd.Series(
        0.0,
        index=df.index
    )


# ============================================================
# ADD RAW RISK FEATURES
# ============================================================

df["cc_readout_risk"] = readout_risk

df["cc_edge_risk"] = edge_risk

df["cc_sx_risk"] = sx_risk

df["cc_gate_risk"] = gate_risk


risk_columns = [
    "cc_readout_risk",
    "cc_edge_risk",
    "cc_sx_risk",
    "cc_gate_risk",
]


# ============================================================
# FILL MISSING RISK VALUES
# ============================================================

for column in risk_columns:

    median_value = df[column].median()

    if pd.isna(median_value):

        median_value = 0.0

    df[column] = df[column].fillna(
        median_value
    )


# ============================================================
# WITHIN-CIRCUIT/BACKEND NORMALIZATION
# ============================================================

print(
    "\nCreating within-group normalized features..."
)

df["cc_esp_norm"] = 0.0

df["cc_readout_norm"] = 0.0

df["cc_edge_norm"] = 0.0

df["cc_sx_norm"] = 0.0

df["cc_gate_norm"] = 0.0


for (circuit, backend), group in df.groupby(
    ["circuit_id", "backend"],
    sort=True
):

    idx = group.index

    df.loc[
        idx,
        "cc_esp_norm"
    ] = minmax_normalize(
        group["esp"]
    ).values

    df.loc[
        idx,
        "cc_readout_norm"
    ] = minmax_normalize(
        group["cc_readout_risk"]
    ).values

    df.loc[
        idx,
        "cc_edge_norm"
    ] = minmax_normalize(
        group["cc_edge_risk"]
    ).values

    df.loc[
        idx,
        "cc_sx_norm"
    ] = minmax_normalize(
        group["cc_sx_risk"]
    ).values

    df.loc[
        idx,
        "cc_gate_norm"
    ] = minmax_normalize(
        group["cc_gate_risk"]
    ).values


# ============================================================
# NOW CREATE TRAIN / TEST DATA
# ============================================================
#
# IMPORTANT:
# This happens AFTER the normalized columns are created.
# That fixes the KeyError from the previous version.
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


train_df = df[
    df["circuit_id"].isin(
        train_circuits
    )
].copy()

test_df = df[
    df["circuit_id"].isin(
        test_circuits
    )
].copy()


print(
    f"\nTraining circuits: "
    f"{train_circuits}"
)

print(
    f"Testing circuits: "
    f"{test_circuits}"
)

print(
    f"\nTraining rows: "
    f"{len(train_df)}"
)

print(
    f"Testing rows: "
    f"{len(test_df)}"
)


# ============================================================
# CALIBRATIONCOMPASS SCORE
# ============================================================

def calculate_score(
    frame,
    readout_weight,
    edge_weight,
    sx_weight,
    gate_weight,
):

    return (
        frame["cc_esp_norm"]
        -
        readout_weight
        *
        frame["cc_readout_norm"]
        -
        edge_weight
        *
        frame["cc_edge_norm"]
        -
        sx_weight
        *
        frame["cc_sx_norm"]
        -
        gate_weight
        *
        frame["cc_gate_norm"]
    )


# ============================================================
# WEIGHT EVALUATION
# ============================================================

def evaluate_weights(
    frame,
    readout_weight,
    edge_weight,
    sx_weight,
    gate_weight,
):

    correct = 0

    total = 0

    regrets = []

    for (_, _), group in frame.groupby(
        ["circuit_id", "backend"],
        sort=True
    ):

        scores = calculate_score(
            group,
            readout_weight,
            edge_weight,
            sx_weight,
            gate_weight,
        )

        selected_idx = scores.idxmax()

        oracle_idx = group[
            "actual_fidelity"
        ].idxmax()

        selected_candidate = group.loc[
            selected_idx,
            "candidate_seed"
        ]

        oracle_candidate = group.loc[
            oracle_idx,
            "candidate_seed"
        ]

        selected_fidelity = group.loc[
            selected_idx,
            "actual_fidelity"
        ]

        oracle_fidelity = group.loc[
            oracle_idx,
            "actual_fidelity"
        ]

        if (
            selected_candidate
            ==
            oracle_candidate
        ):

            correct += 1

        total += 1

        regrets.append(
            oracle_fidelity
            -
            selected_fidelity
        )

    accuracy = (
        correct / total
        if total > 0
        else 0.0
    )

    average_regret = (
        np.mean(regrets)
        if regrets
        else np.inf
    )

    return (
        accuracy,
        average_regret
    )


# ============================================================
# LEARN WEIGHTS
# ============================================================

print("\n")
print("=" * 90)
print("LEARNING CALIBRATION WEIGHTS")
print("=" * 90)


# Use a moderate grid so the experiment finishes quickly.

weight_values = np.arange(
    0.0,
    2.01,
    0.2
)


best_accuracy = -1.0

best_regret = np.inf

best_weights = None

tested_combinations = 0


for readout_weight in weight_values:

    for edge_weight in weight_values:

        for sx_weight in weight_values:

            for gate_weight in weight_values:

                accuracy, regret = evaluate_weights(
                    train_df,
                    readout_weight,
                    edge_weight,
                    sx_weight,
                    gate_weight,
                )

                tested_combinations += 1

                better = False

                if (
                    accuracy
                    >
                    best_accuracy
                ):

                    better = True

                elif (
                    accuracy
                    ==
                    best_accuracy
                    and
                    regret
                    <
                    best_regret
                ):

                    better = True

                if better:

                    best_accuracy = accuracy

                    best_regret = regret

                    best_weights = (
                        readout_weight,
                        edge_weight,
                        sx_weight,
                        gate_weight,
                    )


print(
    f"\nWeight combinations tested: "
    f"{tested_combinations}"
)

print(
    f"\nBest training accuracy: "
    f"{best_accuracy:.2%}"
)

print(
    f"Best training average regret: "
    f"{best_regret:.6f}"
)


readout_weight = best_weights[0]

edge_weight = best_weights[1]

sx_weight = best_weights[2]

gate_weight = best_weights[3]


print(
    "\nLearned weights:"
)

print(
    f"  Readout: "
    f"{readout_weight:.2f}"
)

print(
    f"  Edge: "
    f"{edge_weight:.2f}"
)

print(
    f"  SX: "
    f"{sx_weight:.2f}"
)

print(
    f"  Gate: "
    f"{gate_weight:.2f}"
)


# ============================================================
# APPLY FINAL SCORE TO EVERY CANDIDATE
# ============================================================

df["calibrationcompass_score"] = calculate_score(
    df,
    readout_weight,
    edge_weight,
    sx_weight,
    gate_weight,
)


# ============================================================
# TEST EVALUATION
# ============================================================

test_results = df[
    df["circuit_id"].isin(
        test_circuits
    )
].copy()


records = []


for (circuit, backend), group in test_results.groupby(
    ["circuit_id", "backend"],
    sort=True
):

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

            "cc_candidate":
                cc["candidate_seed"],

            "cc_fidelity":
                cc["actual_fidelity"],

            "cc_score":
                cc["calibrationcompass_score"],
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
# RESULTS
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


# ============================================================
# DECISION TABLE
# ============================================================

print("\n")
print("=" * 90)
print("DECISION COMPARISON")
print("=" * 90)

print(
    comparison[
        [
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
    ].to_string(
        index=False
    )
)


# ============================================================
# IMPROVEMENT COUNT
# ============================================================

improved = comparison[
    comparison["cc_regret"]
    <
    comparison["esp_regret"]
]

same = comparison[
    comparison["cc_regret"]
    ==
    comparison["esp_regret"]
]

worse = comparison[
    comparison["cc_regret"]
    >
    comparison["esp_regret"]
]


print("\n")
print("=" * 90)
print("ESP VS CALIBRATIONCOMPASS")
print("=" * 90)

print(
    f"\nImproved over ESP: "
    f"{len(improved)}/{len(comparison)}"
)

print(
    f"Same as ESP: "
    f"{len(same)}/{len(comparison)}"
)

print(
    f"Worse than ESP: "
    f"{len(worse)}/{len(comparison)}"
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
    "cc_readout_risk",
    "cc_edge_risk",
    "cc_sx_risk",
    "cc_gate_risk",
    "cc_esp_norm",
    "cc_readout_norm",
    "cc_edge_norm",
    "cc_sx_norm",
    "cc_gate_norm",
    "calibrationcompass_score",
]


prediction_file = (
    RESULTS_DIR
    /
    "calibration_aware_score_predictions.csv"
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
    /
    "calibration_aware_score_selection.csv"
)


comparison.to_csv(
    selection_file,
    index=False
)


# ============================================================
# SAVE WEIGHTS
# ============================================================

weights_file = (
    RESULTS_DIR
    /
    "calibration_aware_weights.csv"
)


weights_df = pd.DataFrame(
    {
        "component": [
            "readout",
            "edge",
            "sx",
            "gate",
        ],

        "weight": [
            readout_weight,
            edge_weight,
            sx_weight,
            gate_weight,
        ],
    }
)


weights_df.to_csv(
    weights_file,
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
    weights_file
)

print("\n")
print("=" * 90)
print("DONE")
print("=" * 90)