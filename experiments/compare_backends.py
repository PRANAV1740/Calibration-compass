from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
from qiskit_ibm_runtime import fake_provider


# ==================================================
# 1. Create our quantum circuit
# ==================================================

qc = QuantumCircuit(3, 3)

qc.h(0)
qc.cx(0, 1)
qc.cx(1, 2)

qc.measure([0, 1, 2], [0, 1, 2])


# ==================================================
# 2. Choose IBM fake backends
# ==================================================

backend_classes = [
    "FakeSherbrooke",
    "FakeTorino",
    "FakeFez",
]


# ==================================================
# 3. Run the same circuit on every backend
# ==================================================

for backend_name in backend_classes:

    print("\n" + "=" * 60)
    print(f"BACKEND: {backend_name}")
    print("=" * 60)

    # Check whether this backend exists
    if not hasattr(fake_provider, backend_name):
        print("This backend is not available in your installation.")
        continue

    BackendClass = getattr(fake_provider, backend_name)
    backend = BackendClass()

    # ------------------------------------------------
    # Transpile
    # ------------------------------------------------

    transpiled_qc = transpile(
        qc,
        backend=backend,
        optimization_level=1
    )

    # ------------------------------------------------
    # Count circuit information
    # ------------------------------------------------

    operations = transpiled_qc.count_ops()

    # Count common two-qubit gates
    two_qubit_gates = 0

    for gate in ["cx", "ecr", "cz", "swap"]:
        two_qubit_gates += operations.get(gate, 0)

    depth = transpiled_qc.depth()

    # ------------------------------------------------
    # Create noisy simulator
    # ------------------------------------------------

    simulator = AerSimulator.from_backend(backend)

    # ------------------------------------------------
    # Run
    # ------------------------------------------------

    job = simulator.run(
        transpiled_qc,
        shots=2000
    )

    result = job.result()
    counts = result.get_counts()

    # ------------------------------------------------
    # Calculate simple success probability
    # ------------------------------------------------

    correct_000 = counts.get("000", 0)
    correct_111 = counts.get("111", 0)

    success_probability = (
        correct_000 + correct_111
    ) / 2000

    # ------------------------------------------------
    # Print results
    # ------------------------------------------------

    print(f"Backend name: {backend.name}")
    print(f"Circuit depth: {depth}")
    print(f"Two-qubit gates: {two_qubit_gates}")
    print(f"Success probability: {success_probability:.4f}")

    print("\nMeasurement results:")
    print(counts)


print("\n" + "=" * 60)
print("EXPERIMENT COMPLETE")
print("=" * 60)