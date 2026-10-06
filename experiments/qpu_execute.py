from qiskit import QuantumCircuit, transpile
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2


def run_on_qpu(qasm, backend_name, shots=512):
    service = QiskitRuntimeService(
        channel="ibm_quantum_platform",
        instance="open-instance"
    )

    backend = service.backend(backend_name)

    circuit = QuantumCircuit.from_qasm_str(qasm)

    circuit_isa = transpile(
        circuit,
        backend=backend,
        optimization_level=1
    )

    sampler = SamplerV2(mode=backend)

    job = sampler.run(
        [circuit_isa],
        shots=shots
    )

    result = job.result()

    counts = result[0].data.c.get_counts()

    return {
        "backend": backend_name,
        "job_id": job.job_id(),
        "counts": counts,
        "shots": shots
    }


if __name__ == "__main__":
    bell_qasm = """OPENQASM 2.0;
include "qelib1.inc";

qreg q[2];
creg c[2];

h q[0];
cx q[0],q[1];

measure q[0] -> c[0];
measure q[1] -> c[1];
"""

    print("Running test through reusable QPU executor...")

    result = run_on_qpu(
        bell_qasm,
        "ibm_fez",
        shots=512
    )

    print("\nBackend:", result["backend"])
    print("Job ID:", result["job_id"])
    print("Counts:", result["counts"])