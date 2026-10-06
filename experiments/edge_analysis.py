import numpy as np

from qiskit import QuantumCircuit, transpile
from qiskit_ibm_runtime import fake_provider


# ============================================================
# SAME CIRCUIT GENERATOR
# ============================================================

def make_random_circuit(seed):
    rng = np.random.default_rng(seed)

    num_qubits = int(rng.integers(4, 9))
    circuit_depth = int(rng.integers(3, 9))

    qc = QuantumCircuit(num_qubits, num_qubits)

    for _ in range(circuit_depth):

        for q in range(num_qubits):

            choice = rng.integers(0, 3)

            if choice == 0:
                qc.h(q)

            elif choice == 1:
                qc.ry(
                    float(rng.uniform(0, 2 * np.pi)),
                    q
                )

            else:
                qc.rz(
                    float(rng.uniform(0, 2 * np.pi)),
                    q
                )

        number_of_entangling_gates = max(
            1,
            num_qubits // 2
        )

        for _ in range(number_of_entangling_gates):

            q1, q2 = rng.choice(
                num_qubits,
                size=2,
                replace=False
            )

            qc.cx(int(q1), int(q2))

    qc.measure(
        range(num_qubits),
        range(num_qubits)
    )

    return qc


# ============================================================
# GET CZ CALIBRATION ERROR
# ============================================================

def get_cz_error(backend, q0, q1):

    try:
        props = backend.target["cz"][(q0, q1)]

        if props is not None:
            return props.error

    except (KeyError, TypeError):
        pass

    try:
        props = backend.target["cz"][(q1, q0)]

        if props is not None:
            return props.error

    except (KeyError, TypeError):
        pass

    return None


# ============================================================
# ANALYZE ONE CANDIDATE
# ============================================================

def analyze(seed, circuit, backend):

    transpiled = transpile(
        circuit,
        backend=backend,
        optimization_level=1,
        layout_method="sabre",
        routing_method="sabre",
        seed_transpiler=seed
    )

    edge_counts = {}

    for instruction in transpiled.data:

        if instruction.operation.name != "cz":
            continue

        q0 = transpiled.find_bit(
            instruction.qubits[0]
        ).index

        q1 = transpiled.find_bit(
            instruction.qubits[1]
        ).index

        edge = tuple(sorted((q0, q1)))

        edge_counts[edge] = (
            edge_counts.get(edge, 0) + 1
        )

    rows = []

    for edge, count in sorted(edge_counts.items()):

        q0, q1 = edge

        error = get_cz_error(
            backend,
            q0,
            q1
        )

        if error is None:
            continue

        rows.append({
            "seed": seed,
            "physical_edge": f"{q0}-{q1}",
            "q0": q0,
            "q1": q1,
            "uses": count,
            "cz_error": error,
            "edge_success": 1.0 - error,
            "exposure": count * error
        })

    return rows


# ============================================================
# RUN
# ============================================================

CIRCUIT_SEED = 20000

backend = fake_provider.FakeTorino()

circuit = make_random_circuit(
    CIRCUIT_SEED
)

all_rows = []

for seed in [22, 33]:

    all_rows.extend(
        analyze(
            seed,
            circuit,
            backend
        )
    )


# ============================================================
# PRINT
# ============================================================

print("=" * 90)
print("CALIBRATIONCOMPASS - EDGE ANALYSIS")
print("=" * 90)

for seed in [22, 33]:

    print()
    print("=" * 90)
    print(f"CANDIDATE SEED {seed}")
    print("=" * 90)

    rows = [
        r for r in all_rows
        if r["seed"] == seed
    ]

    print(
        f"{'EDGE':<12}"
        f"{'USES':>8}"
        f"{'CZ ERROR':>14}"
        f"{'EXPOSURE':>14}"
    )

    print("-" * 90)

    for row in rows:

        print(
            f"{row['physical_edge']:<12}"
            f"{row['uses']:>8}"
            f"{row['cz_error']:>14.6f}"
            f"{row['exposure']:>14.6f}"
        )

    total_exposure = sum(
        r["exposure"]
        for r in rows
    )

    print("-" * 90)

    print(
        f"TOTAL CZ EXPOSURE: "
        f"{total_exposure:.6f}"
    )


print()
print("=" * 90)
print("ANALYSIS COMPLETE")
print("=" * 90)