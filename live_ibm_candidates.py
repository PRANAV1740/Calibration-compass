from qiskit import QuantumCircuit, transpile
from qiskit_ibm_runtime import QiskitRuntimeService
import pandas as pd

SEEDS = [11, 22, 33, 44, 55, 66]

service = QiskitRuntimeService()

backend = service.backend("ibm_fez")
props = backend.properties(refresh=True)

qc = QuantumCircuit(3, 3)
qc.h(0)
qc.cx(0, 1)
qc.cx(1, 2)
qc.measure([0, 1, 2], [0, 1, 2])

rows = []

for seed in SEEDS:

    compiled = transpile(
        qc,
        backend=backend,
        optimization_level=3,
        layout_method="sabre",
        routing_method="sabre",
        seed_transpiler=seed,
    )

    layout = compiled.layout.final_index_layout()

    physical = [
        layout[i]
        for i in range(3)
    ]

    readout = [
        props.readout_error(q)
        for q in physical
    ]

    rows.append({
        "candidate": seed,
        "mapping": physical,
        "avg_readout": sum(readout) / len(readout),
        "max_readout": max(readout),
        "depth": compiled.depth(),
        "2Q_gates": sum(
            1
            for inst in compiled.data
            if inst.operation.num_qubits == 2
        )
    })


df = pd.DataFrame(rows)

df = df.sort_values(
    "avg_readout"
)

print("=" * 80)
print("CALIBRATIONCOMPASS - LIVE IBM CANDIDATES")
print("=" * 80)

print(
    df.to_string(index=False)
)

print("\nLowest readout-risk candidate:")
print(
    int(df.iloc[0]["candidate"])
)

print("\nHighest readout-risk candidate:")
print(
    int(df.iloc[-1]["candidate"])
)

print("\nDONE")