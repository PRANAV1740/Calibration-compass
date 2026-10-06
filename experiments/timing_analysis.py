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

            qc.cx(
                int(q1),
                int(q2)
            )

    qc.measure(
        range(num_qubits),
        range(num_qubits)
    )

    return qc


# ============================================================
# ANALYZE CANDIDATE
# ============================================================

def analyze(seed, circuit, backend):

    circuit_scheduled = transpile(
        circuit,
        backend=backend,
        optimization_level=1,
        layout_method="sabre",
        routing_method="sabre",
        scheduling_method="alap",
        seed_transpiler=seed
    )

    print()
    print("=" * 90)
    print(f"SEED {seed}")
    print("=" * 90)

    print("\nBASIC STATISTICS")
    print("-" * 90)

    print("Depth:", circuit_scheduled.depth())
    print("Gate counts:", dict(circuit_scheduled.count_ops()))

    # --------------------------------------------------------
    # TOTAL CIRCUIT DURATION
    # --------------------------------------------------------

    print("\nTIMING")
    print("-" * 90)

    try:
        print("Circuit duration:", circuit_scheduled.duration)
        print("Circuit unit:", circuit_scheduled.unit)
    except Exception as e:
        print("Could not read circuit duration:", e)

    # --------------------------------------------------------
    # DELAY EXPOSURE PER QUBIT
    # --------------------------------------------------------

    delay_by_qubit = {}

    for instruction in circuit_scheduled.data:

        if instruction.operation.name != "delay":
            continue

        duration = instruction.operation.duration

        for q in instruction.qubits:

            physical = circuit_scheduled.find_bit(q).index

            delay_by_qubit[physical] = (
                delay_by_qubit.get(physical, 0)
                + duration
            )

    print("\nIDLE / DELAY EXPOSURE")
    print("-" * 90)

    print(
        f"{'PHYSICAL':<12}"
        f"{'IDLE DT':>15}"
        f"{'T1(us)':>15}"
        f"{'T2(us)':>15}"
    )

    for physical in sorted(delay_by_qubit):

        try:
            props = backend.qubit_properties(physical)

            t1 = (
                props.t1 * 1e6
                if props.t1 is not None
                else np.nan
            )

            t2 = (
                props.t2 * 1e6
                if props.t2 is not None
                else np.nan
            )

        except Exception:
            t1 = np.nan
            t2 = np.nan

        print(
            f"{physical:<12}"
            f"{delay_by_qubit[physical]:>15}"
            f"{t1:>15.2f}"
            f"{t2:>15.2f}"
        )

    total_idle = sum(
        delay_by_qubit.values()
    )

    print()
    print("Total idle/delay exposure across qubits:", total_idle)

    # --------------------------------------------------------
    # T2-WEIGHTED IDLE EXPOSURE
    # --------------------------------------------------------

    weighted_idle = 0.0

    for physical, idle_dt in delay_by_qubit.items():

        try:
            props = backend.qubit_properties(physical)

            if props.t2 is not None and props.t2 > 0:

                # Convert dt to seconds
                dt = backend.dt

                idle_seconds = idle_dt * dt

                weighted_idle += (
                    idle_seconds / props.t2
                )

        except Exception:
            pass

    print(
        "T2-weighted idle exposure:",
        f"{weighted_idle:.8f}"
    )


# ============================================================
# RUN
# ============================================================

backend = fake_provider.FakeTorino()

circuit = make_random_circuit(20000)

print("=" * 90)
print("CALIBRATIONCOMPASS - TIMING ANALYSIS")
print("=" * 90)

print("Circuit seed: 20000")
print("Logical qubits:", circuit.num_qubits)

for seed in [22, 33]:

    analyze(
        seed,
        circuit,
        backend
    )

print()
print("=" * 90)
print("TIMING ANALYSIS COMPLETE")
print("=" * 90)