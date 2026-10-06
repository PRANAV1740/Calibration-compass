import numpy as np
import pandas as pd

from qiskit import qasm2, transpile
from qiskit_aer import AerSimulator
from qiskit_ibm_runtime.fake_provider import (
    FakeFez,
    FakeSherbrooke,
    FakeTorino,
)

SEEDS = [11, 22, 33, 44, 55, 66]

BACKENDS = {
    "Fez": FakeFez(),
    "Sherbrooke": FakeSherbrooke(),
    "Torino": FakeTorino(),
}

QASM = """OPENQASM 2.0;
include "qelib1.inc";

qreg q[3];
creg c[3];

h q[0];
cx q[0],q[1];
cx q[1],q[2];

measure q[0] -> c[0];
measure q[1] -> c[1];
measure q[2] -> c[2];
"""


def probabilities(counts, shots):
    return {
        k: v / shots
        for k, v in counts.items()
    }


def hellinger_fidelity(p, q):
    keys = set(p) | set(q)

    overlap = sum(
        np.sqrt(
            p.get(k, 0.0) *
            q.get(k, 0.0)
        )
        for k in keys
    )

    return overlap ** 2


print("=" * 80)
print("CALIBRATIONCOMPASS - LIVE CANDIDATE FIDELITY")
print("=" * 80)

backend_name = input(
    "\nBackend (Fez / Sherbrooke / Torino): "
).strip()

if backend_name not in BACKENDS:
    raise ValueError("Invalid backend.")

backend = BACKENDS[backend_name]

circuit = qasm2.loads(QASM)

# Ideal reference
ideal_sim = AerSimulator()
ideal_result = ideal_sim.run(
    circuit,
    shots=5000,
    seed_simulator=1234
).result()

ideal_counts = ideal_result.get_counts()
ideal_probs = probabilities(
    ideal_counts,
    5000
)

rows = []

for seed in SEEDS:

    compiled = transpile(
        circuit,
        backend=backend,
        optimization_level=3,
        layout_method="sabre",
        routing_method="sabre",
        seed_transpiler=seed,
    )

    noisy_sim = AerSimulator.from_backend(
        backend
    )

    result = noisy_sim.run(
        compiled,
        shots=5000,
        seed_simulator=seed
    ).result()

    noisy_counts = result.get_counts()

    noisy_probs = probabilities(
        noisy_counts,
        5000
    )

    fidelity = hellinger_fidelity(
        ideal_probs,
        noisy_probs
    )

    rows.append({
        "candidate_seed": seed,
        "depth": compiled.depth(),
        "two_qubit_gates": sum(
            1
            for inst in compiled.data
            if inst.operation.name in ["cx", "cz", "ecr"]
        ),
        "fidelity": fidelity,
    })


df = pd.DataFrame(rows)

df = df.sort_values(
    "fidelity",
    ascending=False
)

print("\nCandidate results:\n")

print(
    df.to_string(index=False)
)

best = df.iloc[0]

print(
    f"\nBEST CANDIDATE: "
    f"{int(best['candidate_seed'])}"
)

print(
    f"BEST FIDELITY: "
    f"{best['fidelity']:.6f}"
)

print("\nDONE")