from qiskit import QuantumCircuit, transpile
from qiskit_ibm_runtime import fake_provider


# ============================================================
# 1. CREATE A SMALL TEST CIRCUIT
# ============================================================

qc = QuantumCircuit(5)

qc.h(0)
qc.cx(0, 1)
qc.cx(1, 2)
qc.cx(2, 3)
qc.cx(3, 4)


# ============================================================
# 2. USE ONE IBM FAKE BACKEND
# ============================================================

backend = fake_provider.FakeTorino()


# ============================================================
# 3. CREATE TWO DIFFERENT COMPILATION CANDIDATES
# ============================================================

candidate_a = transpile(
    qc,
    backend=backend,
    optimization_level=1,
    layout_method="sabre",
    routing_method="sabre",
    seed_transpiler=11
)


candidate_b = transpile(
    qc,
    backend=backend,
    optimization_level=1,
    layout_method="sabre",
    routing_method="sabre",
    seed_transpiler=33
)


# ============================================================
# 4. PRINT BASIC INFORMATION
# ============================================================

print("=" * 70)
print("CALIBRATIONCOMPASS - MAPPING INSPECTOR")
print("=" * 70)


# ============================================================
# 5. PRINT THE LAYOUT OBJECT
# ============================================================

print("\nCANDIDATE A")
print("-" * 70)

print("Layout object:")
print(candidate_a.layout)

print("\nCandidate A circuit:")
print(candidate_a)


print("\n")
print("=" * 70)


print("\nCANDIDATE B")
print("-" * 70)

print("Layout object:")
print(candidate_b.layout)

print("\nCandidate B circuit:")
print(candidate_b)


# ============================================================
# 6. INSPECT AVAILABLE LAYOUT INFORMATION
# ============================================================

print("\n")
print("=" * 70)
print("LAYOUT DETAILS")
print("=" * 70)


for name, circuit in [
    ("Candidate A", candidate_a),
    ("Candidate B", candidate_b)
]:

    print(f"\n{name}")

    layout = circuit.layout

    if layout is None:

        print("No layout information found.")

        continue

    print(
        "\nLayout type:"
    )

    print(
        type(layout)
    )


    print(
        "\nAvailable layout attributes:"
    )

    for attribute in dir(layout):

        if (
            not attribute.startswith("_")
        ):

            print(
                attribute
            )


print("\n")
print("=" * 70)
print("INSPECTION COMPLETE")
print("=" * 70)