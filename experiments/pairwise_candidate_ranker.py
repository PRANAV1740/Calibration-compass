"""
CalibrationCompass - Pairwise Candidate Ranker

Instead of predicting absolute fidelity, learn:

    Is candidate A better than candidate B?

Training:
    Whole circuits 0,1,3,4,6,7,9

Testing:
    Completely unseen circuits 2,5,8

For every circuit/backend group:
    6 candidates -> 15 candidate pairs

Each pair is represented by feature differences:

    features(A) - features(B)

The model learns which direction tends to produce
the better candidate.

At test time:
    each candidate is compared against every other candidate
    and receives a predicted win score.

The candidate with the highest total predicted wins
is selected.
"""

from pathlib import Path
from itertools import combinations

import numpy as np
import pandas as pd
from xgboost import XGBClassifier


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

RANDOM_STATE = 42


# ============================================================
# HELPER
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


# ============================================================
# START
# ============================================================

print("=" * 90)
print("CALIBRATIONCOMPASS - PAIRWISE CANDIDATE RANKER")
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

df["backend"] = (
    df["backend"]
    .astype(str)
)


required = [
    "circuit_id",
    "backend",
    "candidate_seed",
    "actual_fidelity",
    "esp",
]

df = df.dropna(
    subset=required
).reset_index(
    drop=True
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
# TRAIN / TEST SPLIT
# ============================================================

all_circuits = sorted(
    df["circuit_id"]
    .unique()
    .tolist()
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

train_mask = df[
    "circuit_id"
].isin(
    train_circuits
)

test_mask = df[
    "circuit_id"
].isin(
    test_circuits
)

train_df = df[
    train_mask
].copy()

test_df = df[
    test_mask
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
# BUILD FEATURE MATRIX
# ============================================================

DROP_COLUMNS = {
    "circuit_id",
    "candidate_seed",
    "actual_fidelity",
}


# Remove raw physical identifiers.
for column in df.columns:

    lower = column.lower()

    if lower == "physical_qubits":

        DROP_COLUMNS.add(column)

    elif lower == "mapping":

        DROP_COLUMNS.add(column)

    elif lower.endswith("_physical"):

        DROP_COLUMNS.add(column)


feature_df = df.drop(
    columns=[
        column
        for column in DROP_COLUMNS
        if column in df.columns
    ],
    errors="ignore"
).copy()


# ============================================================
# DUPLICATE FEATURE CHECK
# ============================================================

if feature_df.columns.duplicated().any():

    feature_df = feature_df.loc[
        :,
        ~feature_df.columns.duplicated(
            keep="first"
        )
    ].copy()


# ============================================================
# MISSING INDICATORS
# ============================================================

missing_columns = []

for column in feature_df.columns:

    if feature_df[column].isna().any():

        missing_columns.append(
            column
        )

        indicator = (
            f"{column}__missing"
        )

        feature_df[indicator] = (
            feature_df[column]
            .isna()
            .astype(float)
        )


print(
    f"\nFeatures containing missing values: "
    f"{len(missing_columns)}"
)


# ============================================================
# CATEGORICAL ENCODING
# ============================================================

categorical_columns = (
    feature_df
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

    feature_df = pd.get_dummies(
        feature_df,
        columns=categorical_columns,
        dummy_na=True
    )


# ============================================================
# REMOVE DUPLICATE FEATURES AGAIN
# ============================================================

if feature_df.columns.duplicated().any():

    feature_df = feature_df.loc[
        :,
        ~feature_df.columns.duplicated(
            keep="first"
        )
    ].copy()


# ============================================================
# REMOVE REMAINING NON-NUMERIC COLUMNS
# ============================================================

non_numeric = (
    feature_df
    .select_dtypes(
        exclude=[
            np.number,
            "bool",
        ]
    )
    .columns
    .tolist()
)


if non_numeric:

    print(
        "\nDropping remaining non-numeric columns:"
    )

    for column in non_numeric:

        print(
            f"  - {column}"
        )

    feature_df = feature_df.drop(
        columns=non_numeric
    )


# ============================================================
# CONVERT TO FLOAT
# ============================================================

feature_df = feature_df.astype(
    float
)


print(
    f"\nFinal feature count: "
    f"{feature_df.shape[1]}"
)

print(
    f"Feature matrix shape: "
    f"{feature_df.shape}"
)


# ============================================================
# BUILD PAIRWISE TRAINING DATA
# ============================================================

print("\n")
print("=" * 90)
print("BUILDING PAIRWISE TRAINING DATA")
print("=" * 90)


X_pairs = []

y_pairs = []

pair_metadata = []


for (circuit, backend), group in train_df.groupby(
    ["circuit_id", "backend"],
    sort=True
):

    group_indices = (
        group.index
        .tolist()
    )

    # --------------------------------------------------------
    # All candidate pairs
    # --------------------------------------------------------

    for idx_a, idx_b in combinations(
        group_indices,
        2
    ):

        features_a = (
            feature_df
            .loc[idx_a]
            .values
        )

        features_b = (
            feature_df
            .loc[idx_b]
            .values
        )

        fidelity_a = (
            df
            .loc[
                idx_a,
                "actual_fidelity"
            ]
        )

        fidelity_b = (
            df
            .loc[
                idx_b,
                "actual_fidelity"
            ]
        )


        # ====================================================
        # A - B
        # ====================================================

        difference_ab = (
            features_a
            -
            features_b
        )


        if fidelity_a > fidelity_b:

            label_ab = 1

        elif fidelity_a < fidelity_b:

            label_ab = 0

        else:

            # Equal fidelity:
            # ignore this pair.
            continue


        X_pairs.append(
            difference_ab
        )

        y_pairs.append(
            label_ab
        )

        pair_metadata.append(
            {
                "circuit_id": circuit,
                "backend": backend,
                "candidate_a":
                    df.loc[
                        idx_a,
                        "candidate_seed"
                    ],
                "candidate_b":
                    df.loc[
                        idx_b,
                        "candidate_seed"
                    ],
            }
        )


        # ====================================================
        # B - A
        # ====================================================

        difference_ba = (
            features_b
            -
            features_a
        )

        X_pairs.append(
            difference_ba
        )

        y_pairs.append(
            1 - label_ab
        )

        pair_metadata.append(
            {
                "circuit_id": circuit,
                "backend": backend,
                "candidate_a":
                    df.loc[
                        idx_b,
                        "candidate_seed"
                    ],
                "candidate_b":
                    df.loc[
                        idx_a,
                        "candidate_seed"
                    ],
            }
        )


X_pairs = np.asarray(
    X_pairs,
    dtype=float
)

y_pairs = np.asarray(
    y_pairs,
    dtype=int
)


print(
    f"\nPairwise training samples: "
    f"{len(X_pairs)}"
)

print(
    f"Pairwise features: "
    f"{X_pairs.shape[1]}"
)

print(
    f"Positive labels: "
    f"{int(y_pairs.sum())}"
)

print(
    f"Negative labels: "
    f"{int(len(y_pairs) - y_pairs.sum())}"
)


# ============================================================
# TRAIN CLASSIFIER
# ============================================================

print("\n")
print("=" * 90)
print("TRAINING PAIRWISE MODEL")
print("=" * 90)


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


model.fit(
    X_pairs,
    y_pairs
)


print(
    "\nTraining completed."
)


# ============================================================
# EVALUATE PAIRWISE ACCURACY ON TRAINING DATA
# ============================================================

train_pair_prob = model.predict_proba(
    X_pairs
)[:, 1]

train_pair_prediction = (
    train_pair_prob >= 0.5
).astype(int)

pairwise_training_accuracy = (
    train_pair_prediction
    ==
    y_pairs
).mean()


print(
    f"\nPairwise training accuracy: "
    f"{pairwise_training_accuracy:.2%}"
)


# ============================================================
# TEST CANDIDATE RANKING
# ============================================================

print("\n")
print("=" * 90)
print("RANKING TEST CANDIDATES")
print("=" * 90)


selection_records = []

candidate_prediction_records = []


for (circuit, backend), group in test_df.groupby(
    ["circuit_id", "backend"],
    sort=True
):

    group_indices = (
        group.index
        .tolist()
    )


    candidate_scores = []


    # --------------------------------------------------------
    # Compare every candidate with every other candidate
    # --------------------------------------------------------

    for idx_a in group_indices:

        wins = []

        opponents = []

        for idx_b in group_indices:

            if idx_a == idx_b:
                continue

            features_a = (
                feature_df
                .loc[idx_a]
                .values
            )

            features_b = (
                feature_df
                .loc[idx_b]
                .values
            )

            difference = (
                features_a
                -
                features_b
            ).reshape(
                1,
                -1
            )

            probability = model.predict_proba(
                difference
            )[0, 1]

            wins.append(
                probability
            )

            opponents.append(
                df.loc[
                    idx_b,
                    "candidate_seed"
                ]
            )


        # Average predicted probability
        # of beating every other candidate.

        win_score = (
            np.mean(wins)
            if wins
            else 0.0
        )


        candidate_seed = df.loc[
            idx_a,
            "candidate_seed"
        ]

        actual_fidelity = df.loc[
            idx_a,
            "actual_fidelity"
        ]

        esp = df.loc[
            idx_a,
            "esp"
        ]


        candidate_scores.append(
            {
                "index": idx_a,
                "candidate_seed":
                    candidate_seed,
                "pairwise_score":
                    win_score,
                "actual_fidelity":
                    actual_fidelity,
                "esp":
                    esp,
            }
        )


    # --------------------------------------------------------
    # Best pairwise candidate
    # --------------------------------------------------------

    candidate_scores_sorted = sorted(
        candidate_scores,
        key=lambda x:
            x["pairwise_score"],
        reverse=True
    )


    selected = (
        candidate_scores_sorted[0]
    )


    # --------------------------------------------------------
    # Oracle
    # --------------------------------------------------------

    oracle = max(
        candidate_scores,
        key=lambda x:
            x["actual_fidelity"]
    )


    # --------------------------------------------------------
    # ESP
    # --------------------------------------------------------

    esp_candidate = max(
        candidate_scores,
        key=lambda x:
            x["esp"]
    )


    # --------------------------------------------------------
    # Selection result
    # --------------------------------------------------------

    selection_records.append(
        {
            "circuit_id": circuit,

            "backend": backend,

            "oracle_candidate":
                oracle["candidate_seed"],

            "oracle_fidelity":
                oracle["actual_fidelity"],

            "esp_candidate":
                esp_candidate["candidate_seed"],

            "esp_fidelity":
                esp_candidate[
                    "actual_fidelity"
                ],

            "pairwise_candidate":
                selected["candidate_seed"],

            "pairwise_fidelity":
                selected[
                    "actual_fidelity"
                ],
        }
    )


    # --------------------------------------------------------
    # Save candidate-level scores
    # --------------------------------------------------------

    for candidate in candidate_scores:

        candidate_prediction_records.append(
            {
                "circuit_id": circuit,

                "backend": backend,

                "candidate_seed":
                    candidate[
                        "candidate_seed"
                    ],

                "pairwise_score":
                    candidate[
                        "pairwise_score"
                    ],

                "esp":
                    candidate["esp"],

                "actual_fidelity":
                    candidate[
                        "actual_fidelity"
                    ],
            }
        )


comparison = pd.DataFrame(
    selection_records
)


candidate_predictions = pd.DataFrame(
    candidate_prediction_records
)


# ============================================================
# ACCURACY
# ============================================================

comparison["esp_correct"] = (
    comparison["esp_candidate"]
    ==
    comparison["oracle_candidate"]
)

comparison["pairwise_correct"] = (
    comparison["pairwise_candidate"]
    ==
    comparison["oracle_candidate"]
)


esp_accuracy = (
    comparison["esp_correct"]
    .mean()
)

pairwise_accuracy = (
    comparison["pairwise_correct"]
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

comparison["pairwise_regret"] = (
    comparison["oracle_fidelity"]
    -
    comparison["pairwise_fidelity"]
)


# ============================================================
# PRINT RESULTS
# ============================================================

print("\n")
print("=" * 90)
print("PAIRWISE CANDIDATE RESULTS")
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
    f"Pairwise selection accuracy: "
    f"{pairwise_accuracy:.2%}"
)

print(
    f"\nESP average regret: "
    f"{comparison['esp_regret'].mean():.6f}"
)

print(
    f"Pairwise average regret: "
    f"{comparison['pairwise_regret'].mean():.6f}"
)

print(
    f"\nESP maximum regret: "
    f"{comparison['esp_regret'].max():.6f}"
)

print(
    f"Pairwise maximum regret: "
    f"{comparison['pairwise_regret'].max():.6f}"
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
            "pairwise_candidate",
            "oracle_fidelity",
            "esp_fidelity",
            "pairwise_fidelity",
            "esp_regret",
            "pairwise_regret",
        ]
    ].to_string(
        index=False
    )
)


# ============================================================
# IMPROVEMENT
# ============================================================

improved = comparison[
    comparison["pairwise_regret"]
    <
    comparison["esp_regret"]
]

same = comparison[
    comparison["pairwise_regret"]
    ==
    comparison["esp_regret"]
]

worse = comparison[
    comparison["pairwise_regret"]
    >
    comparison["esp_regret"]
]


print("\n")
print("=" * 90)
print("ESP VS PAIRWISE MODEL")
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
# FEATURE IMPORTANCE
# ============================================================

importance = pd.DataFrame(
    {
        "feature": feature_df.columns,

        "importance":
            model.feature_importances_,
    }
).sort_values(
    "importance",
    ascending=False
).reset_index(
    drop=True
)


print("\n")
print("=" * 90)
print("TOP PAIRWISE FEATURES")
print("=" * 90)

print(
    importance
    .head(20)
    .to_string(index=False)
)


# ============================================================
# SAVE CANDIDATE PREDICTIONS
# ============================================================

prediction_file = (
    RESULTS_DIR
    /
    "pairwise_candidate_predictions.csv"
)

candidate_predictions.to_csv(
    prediction_file,
    index=False
)


# ============================================================
# SAVE SELECTION RESULTS
# ============================================================

selection_file = (
    RESULTS_DIR
    /
    "pairwise_candidate_selection.csv"
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
    /
    "pairwise_candidate_feature_importance.csv"
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