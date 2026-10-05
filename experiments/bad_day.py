from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
from qiskit_ibm_runtime import fake_provider
from qiskit.transpiler import InstructionProperties


# ============================================================
# 1. Create our GHZ circuit
# ============================================================

qc = QuantumCircuit(3, 3)

qc.h(0)
qc.cx(0, 1)
qc.cx(1, 2)

qc.measure([0, 1, 2], [0, 1, 2])


# ============================================================
# 2. Function to run a circuit on a backend
# ============================================================

def run_backend(backend):
    """
    Transpile and simulate the circuit on the given backend.
    """

    transpiled = transpile(
        qc,
        backend=backend,
        initial_layout=[0, 1, 2],
        optimization_level=1
    )

    simulator = AerSimulator.from_backend(backend)

    job = simulator.run(
        transpiled,
        shots=2000
    )

    result = job.result()
    counts = result.get_counts()

    success = (
        counts.get("000", 0) +
        counts.get("111", 0)
    ) / 2000

    return success, transpiled, counts


# ============================================================
# 3. Load three IBM fake backends
# ============================================================

backends = {
    "Sherbrooke": fake_provider.FakeSherbrooke(),
    "Torino": fake_provider.FakeTorino(),
    "Fez": fake_provider.FakeFez(),
}


# ============================================================
# 4. NORMAL DAY
# ============================================================

print("=" * 65)
print("NORMAL DAY")
print("=" * 65)

normal_results = {}

for name, backend in backends.items():

    success, transpiled, counts = run_backend(backend)

    normal_results[name] = success

    print(f"\n{name}")
    print(f"Success probability: {success:.4f}")
    print(f"Depth: {transpiled.depth()}")
    print(f"Two-qubit gates: "
          f"{transpiled.count_ops().get('ecr', 0) + transpiled.count_ops().get('cx', 0) + transpiled.count_ops().get('cz', 0)}")


# ============================================================
# 5. CREATE A SYNTHETIC "BAD DAY" FOR FEZ
# ============================================================

print("\n" + "=" * 65)
print("CREATING SYNTHETIC BAD DAY FOR FEZ")
print("=" * 65)

fez = backends["Fez"]

# We will make physical qubit 1's readout substantially worse.
bad_qubit = 1
drift_factor = 8


# ------------------------------------------------------------
# Change the readout error
# ------------------------------------------------------------

measure_properties = fez.target["measure"][(bad_qubit,)]

if measure_properties is not None and measure_properties.error is not None:

    old_error = measure_properties.error

    new_error = min(
        old_error * drift_factor,
        0.50
    )

    fez.target.update_instruction_properties(
        instruction="measure",
        qargs=(bad_qubit,),
        properties=InstructionProperties(
            duration=measure_properties.duration,
            error=new_error
        )
    )

    print(f"\nFez qubit {bad_qubit} readout error:")
    print(f"Before: {old_error:.6f}")
    print(f"After:  {new_error:.6f}")

else:
    print("\nCould not find readout error for the selected qubit.")


# ============================================================
# 6. BAD DAY RESULTS
# ============================================================

print("\n" + "=" * 65)
print("BAD DAY RESULTS")
print("=" * 65)

bad_results = {}

for name, backend in backends.items():

    success, transpiled, counts = run_backend(backend)

    bad_results[name] = success

    print(f"\n{name}")
    print(f"Success probability: {success:.4f}")
    print(f"Depth: {transpiled.depth()}")
    print(f"Measurement results: {counts}")


# ============================================================
# 7. FINAL COMPARISON
# ============================================================

print("\n" + "=" * 65)
print("COMPARISON")
print("=" * 65)

print("\nBackend        Normal Day       Bad Day       Change")
print("-" * 65)

for name in backends:

    normal = normal_results[name]
    bad = bad_results[name]
    change = bad - normal

    print(
        f"{name:<14}"
        f"{normal:.4f}            "
        f"{bad:.4f}        "
        f"{change:+.4f}"
    )


print("\nEXPERIMENT COMPLETE")