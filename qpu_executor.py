from qiskit import QuantumCircuit, transpile
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2


def _normalise_status(status):
    name = getattr(status, "name", None)
    if name:
        return str(name).upper()
    return str(status).rsplit(".", 1)[-1].upper()


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
    job = sampler.run([circuit_isa], shots=shots)

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
    status = _normalise_status(job.status())

    if status in {"ERROR", "FAILED"}:
        try:
            error = job.error_message()
        except Exception as exc:
            error = f"Could not retrieve error details: {exc}"

        return {
            "status": status,
            "ready": False,
            "terminal": True,
            "error": error
        }

    if status in {"CANCELLED", "CANCELED"}:
        return {
            "status": status,
            "ready": False,
            "terminal": True,
            "error": "The QPU job was cancelled."
        }

    if status != "DONE":
        return {
            "status": status,
            "ready": False,
            "terminal": False,
            "error": None
        }

    result = job.result()
    data = result[0].data

    counts = {
        register_name: register_data.get_counts()
        for register_name, register_data in data.items()
        if callable(getattr(register_data, "get_counts", None))
    }

    if not counts:
        raise ValueError(
            "No measurement counts were returned. "
            "Check that the submitted circuit measures into classical registers."
        )

    return {
        "status": status,
        "ready": True,
        "terminal": True,
        "counts": counts,
        "error": None
    }
