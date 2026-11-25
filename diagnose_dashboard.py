import traceback
from qiskit import transpile
from qiskit.qasm2 import loads
from qiskit_ibm_runtime import QiskitRuntimeService

service = QiskitRuntimeService(
    channel="ibm_quantum_platform",
    instance="open-instance"
)

qasm = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
cx q[0],q[1];
cx q[1],q[2];
measure q[0] -> c[0];
measure q[1] -> c[1];
measure q[2] -> c[2];
"""

circuit = loads(qasm)

for name in ["ibm_fez", "ibm_kingston", "ibm_marrakesh"]:
    print(f"\n{'=' * 50}\nBACKEND: {name}")

    try:
        backend = service.backend(name)
        status = backend.status()
        print("Status:", status.status_msg)

        if not status.operational:
            print("Skipping: backend is not operational.")
            continue

        print("Fetching calibration properties...")
        props = backend.properties(refresh=True)
        print("Properties retrieved:", props is not None)

        for level, seed in [(1, 11), (1, 33), (1, 55), (3, 11)]:
            try:
                compiled = transpile(
                    circuit,
                    backend=backend,
                    optimization_level=level,
                    layout_method="sabre",
                    routing_method="sabre",
                    seed_transpiler=seed,
                )
                print(
                    f"PASS | optimization={level} | seed={seed}"
                    f" | depth={compiled.depth()}"
                )
            except Exception as exc:
                print(f"FAIL | optimization={level} | seed={seed}")
                print(repr(exc))
                traceback.print_exc()

    except Exception as exc:
        print("BACKEND ERROR:", repr(exc))
        traceback.print_exc()
