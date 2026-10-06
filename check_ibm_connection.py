from qiskit_ibm_runtime import QiskitRuntimeService

print("=" * 80)
print("CALIBRATIONCOMPASS - IBM QUANTUM CONNECTION TEST")
print("=" * 80)

try:
    service = QiskitRuntimeService()

    backends = service.backends()

    print("\nIBM Quantum connection: SUCCESS")
    print(f"Backends available: {len(backends)}")

    print("\nFirst available backends:")

    for backend in backends[:10]:
        print(
            f"- {backend.name} "
            f"({backend.num_qubits} qubits)"
        )

except Exception as e:

    print("\nIBM Quantum connection: FAILED")
    print("\nError:")
    print(e)

print("\nDONE")