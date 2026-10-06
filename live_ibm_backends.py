from qiskit_ibm_runtime import QiskitRuntimeService

print("=" * 80)
print("CALIBRATIONCOMPASS - LIVE IBM BACKENDS")
print("=" * 80)

service = QiskitRuntimeService()

backends = service.backends(
    simulator=False,
    operational=True
)

print(f"\nAvailable operational backends: {len(backends)}\n")

for backend in backends:
    print(
        f"{backend.name:25} "
        f"{backend.num_qubits:4} qubits"
    )

print("\nDONE")