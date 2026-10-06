import pandas as pd
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
FILE = BASE / "results" / "multi_circuit_validation.csv"

df = pd.read_csv(FILE)

rows = []

for (circuit, backend), group in df.groupby(
    ["circuit", "backend"]
):

    spread = (
        group["fidelity"].max()
        - group["fidelity"].min()
    )

    corr = group["fidelity"].corr(
        group["avg_readout"]
    )

    rows.append({
        "circuit": circuit,
        "backend": backend,
        "fidelity_spread": spread,
        "readout_correlation": corr,
        "best_fidelity": group["fidelity"].max(),
        "worst_fidelity": group["fidelity"].min()
    })

results = pd.DataFrame(rows)

print("=" * 80)
print("CALIBRATIONCOMPASS - CIRCUIT/BACKEND MAPPING SENSITIVITY")
print("=" * 80)

print(
    results.sort_values(
        "fidelity_spread",
        ascending=False
    ).to_string(index=False)
)

print("\nAverage mapping spread:")
print(
    f"{results['fidelity_spread'].mean():.6f}"
)

print("\nLargest mapping-sensitive cases:")
print(
    results.sort_values(
        "fidelity_spread",
        ascending=False
    ).head(5).to_string(index=False)
)

print("\nAverage readout/fidelity correlation:")
print(
    f"{results['readout_correlation'].mean():.4f}"
)

out = BASE / "results" / "mapping_sensitivity.csv"
results.to_csv(out, index=False)

print(f"\nSaved: {out}")
print("\nDONE")