from qiskit import QuantumCircuit, transpile
from qiskit_ibm_runtime import QiskitRuntimeService


print("=" * 90)
print("CALIBRATIONCOMPASS - INSPECT SAVED HARDWARE JOBS")
print("=" * 90)

service = QiskitRuntimeService(
    channel="ibm_quantum_platform",
    instance="open-instance"
)

JOBS = {
    "ibm_fez": "db2cmf42ljfc73d496a0",
    "ibm_kingston": "db2cmjk2ljfc73d496e0",
    "ibm_marrakesh": "db2cmnnr11fs7396hmq0"
}

SEEDS = [11, 22, 33, 44, 55, 66]


def make_circuits():

    bell = QuantumCircuit(3)
    bell.h(0)
    bell.cx(0, 1)

    ring = QuantumCircuit(3)
    ring.h(0)
    ring.cx(0, 1)
    ring.cx(1, 2)
    ring.cx(2, 0)

    return [
        ("Bell", bell),
        ("Ring", ring)
    ]


for backend_name, job_id in JOBS.items():

    print()
    print("-" * 90)
    print("BACKEND:", backend_name)
    print("JOB:", job_id)
    print("-" * 90)

    backend = service.backend(backend_name)
    job = service.job(job_id)

    print("Job status:", job.status())

    result = job.result()

    circuits = make_circuits()

    index = 0

    for circuit_name, base_circuit in circuits:

        for seed in SEEDS:

            print()
            print(
                f"{circuit_name:<8} "
                f"candidate {seed}"
            )

            counts = result[index].data.meas.get_counts()

            keys = list(counts.keys())

            if keys:

                print(
                    "Count key example:",
                    keys[0]
                )

                print(
                    "Bitstring length:",
                    len(keys[0])
                )

            print(
                "Total shots:",
                sum(counts.values())
            )

            compiled = transpile(
                base_circuit,
                backend=backend,
                optimization_level=3,
                layout_method="sabre",
                routing_method="sabre",
                seed_transpiler=seed
            )

            active_qubits = set()

            for item in compiled.data:

                for q in item.qubits:

                    physical_index = (
                        compiled.find_bit(q).index
                    )

                    active_qubits.add(
                        physical_index
                    )

            print(
                "Active physical qubits:",
                sorted(active_qubits)
            )

            if compiled.layout is not None:

                try:

                    mapping = (
                        compiled.layout
                        .final_index_layout()
                    )

                    print(
                        "Final mapping:",
                        [
                            int(mapping[i])
                            for i in range(3)
                        ]
                    )

                except Exception as exc:

                    print(
                        "Final mapping unavailable:",
                        exc
                    )

            else:

                print(
                    "Final mapping: layout is None"
                )

            index += 1


print()
print("=" * 90)
print("DONE")
print("=" * 90)