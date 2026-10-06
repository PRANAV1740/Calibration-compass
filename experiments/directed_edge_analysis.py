import numpy as np

from qiskit import QuantumCircuit, transpile
from qiskit_ibm_runtime import fake_provider


# ============================================================
# SAME CIRCUIT
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
# DIRECTED CZ ERROR
# ============================================================

def get_cz_error(backend, q0, q1):

    try:
        props = backend.target["cz"][(q0, q1)]

        if props is not None:
            return props.error

    except (KeyError, TypeError):
        pass

    return None


# ============================================================
# ANALYZE
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

    directed_counts = {}

    for instruction in transpiled.data:

        if instruction.operation.name != "cz":
            continue

        q0 = transpiled.find_bit(
            instruction.qubits[0]
        ).index

        q1 = transpiled.find_bit(
            instruction.qubits[1]
        ).index

        directed_edge = (q0, q1)

        directed_counts[directed_edge] = (
            directed_counts.get(directed_edge, 0) + 1
        )

    print()
    print("=" * 90)
    print(f"SEED {seed}")
    print("=" * 90)

    print(
        f"{'DIRECTION':<15}"
        f"{'USES':>10}"
        f"{'CZ ERROR':>15}"
        f"{'EXPOSURE':>15}"
    )

    print("-" * 90)

    total_exposure = 0.0

    for edge, uses in sorted(directed_counts.items()):

        q0, q1 = edge

        error = get_cz_error(
            backend,
            q0,
            q1
        )

        if error is None:
            print(
                f"{q0}->{q1:<10}"
                f"{uses:>10}"
                f"{'N/A':>15}"
                f"{'N/A':>15}"
            )
            continue

        exposure = uses * error
        total_exposure += exposure

        print(
            f"{q0}->{q1:<10}"
            f"{uses:>10}"
            f"{error:>15.6f}"
            f"{exposure:>15.6f}"
        )

    print("-" * 90)

    print(
        "TOTAL DIRECTED CZ EXPOSURE:",
        f"{total_exposure:.6f}"
    )


# ============================================================
# RUN
# ============================================================

backend = fake_provider.FakeTorino()

circuit = make_random_circuit(20000)

print("=" * 90)
print("CALIBRATIONCOMPASS - DIRECTED CZ ANALYSIS")
print("=" * 90)

for seed in [22, 33]:

    analyze(
        seed,
        circuit,
        backend
    )

print()
print("=" * 90)
print("ANALYSIS COMPLETE")
print("=" * 90)