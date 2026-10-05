from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
from qiskit_ibm_runtime.fake_provider import FakeSherbrooke


# --------------------------------------------------
# 1. Create a simple quantum circuit
# --------------------------------------------------

qc = QuantumCircuit(3, 3)

qc.h(0)
qc.cx(0, 1)
qc.cx(1, 2)

qc.measure([0, 1, 2], [0, 1, 2])


print("Original circuit:")
print(qc)


# --------------------------------------------------
# 2. Load a fake IBM quantum computer
# --------------------------------------------------

backend = FakeSherbrooke()

print("\nBackend:")
print(backend.name)


# --------------------------------------------------
# 3. Transpile our circuit for that backend
# --------------------------------------------------

transpiled_qc = transpile(
    qc,
    backend=backend,
    optimization_level=1
)

print("\nTranspiled circuit:")
print(transpiled_qc)


# --------------------------------------------------
# 4. Create a noisy simulator based on the backend
# --------------------------------------------------

simulator = AerSimulator.from_backend(backend)


# --------------------------------------------------
# 5. Run the circuit
# --------------------------------------------------

job = simulator.run(
    transpiled_qc,
    shots=2000
)

result = job.result()

counts = result.get_counts()


# --------------------------------------------------
# 6. Show the result
# --------------------------------------------------

print("\nMeasurement results:")
print(counts)

print("\nTEST COMPLETE!")