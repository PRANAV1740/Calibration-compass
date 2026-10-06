from qiskit import QuantumCircuit, transpile
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2

print("Connecting to IBM Quantum...")

service = QiskitRuntimeService(
    channel="ibm_quantum_platform",
    instance="open-instance"
)

backend = service.backend("ibm_fez")

print(f"Backend: {backend.name}")

# Bell-state circuit
qc = QuantumCircuit(2)
qc.h(0)
qc.cx(0, 1)
qc.measure_all()

# Transpile for the real backend
qc_isa = transpile(qc, backend=backend, optimization_level=1)

print("Submitting job to QPU...")

sampler = SamplerV2(mode=backend)

job = sampler.run([qc_isa], shots=512)

print(f"Job ID: {job.job_id()}")
print("Waiting for QPU result...")

result = job.result()

counts = result[0].data.meas.get_counts()

print("\nQPU RESULT:")
print(counts)

print("\nQPU execution successful.")