from qiskit import QuantumCircuit, transpile
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2


def submit_to_qpu(qasm, backend_name, candidate_seed, shots=512):
    service = QiskitRuntimeService(
        channel="ibm_quantum_platform",
        instance="open-instance"
    )

    backend = service.backend(backend_name)

    circuit = QuantumCircuit.from_qasm_str(qasm)

    circuit_isa = transpile(
        circuit,
        backend=backend,
        optimization_level=3,
        layout_method="sabre",
        routing_method="sabre",
        seed_transpiler=int(candidate_seed)
    )

    sampler = SamplerV2(mode=backend)

    job = sampler.run(
        [circuit_isa],
        shots=shots
    )

    return {
        "backend": backend_name,
        "candidate_seed": int(candidate_seed),
        "job_id": job.job_id()
    }


def get_qpu_result(job_id):
    service = QiskitRuntimeService(
        channel="ibm_quantum_platform",
        instance="open-instance"
    )

    job = service.job(job_id)

    status = str(job.status())

    if status not in ["DONE", "JobStatus.DONE"]:
        return {
            "status": status,
            "ready": False
        }

    result = job.result()

    counts = result[0].data.c.get_counts()

    return {
        "status": status,
        "ready": True,
        "counts": counts
    }