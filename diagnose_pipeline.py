import traceback
from datetime import datetime, timezone

import pandas as pd
from qiskit import transpile
from qiskit.qasm2 import loads
from qiskit_ibm_runtime import QiskitRuntimeService

BACKENDS = ["ibm_fez", "ibm_kingston", "ibm_marrakesh"]
SEEDS = [11, 33, 55]

QASM = """OPENQASM 2.0;
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

def analyze_candidate(compiled, props):
    used_qubits = set()
    measured_qubits = set()
    gate_errors = []
    two_q_errors = []
    gate_count = 0
    two_q_count = 0
    two_q_edges = []

    for item in compiled.data:
        operation = item.operation
        physical = [
            compiled.find_bit(q).index for q in item.qubits
        ]
        name = operation.name.lower()

        if name == "measure":
            measured_qubits.update(physical)
            continue
        if name in {"barrier", "delay", "reset"}:
            continue

        used_qubits.update(physical)
        gate_count += 1

        if len(physical) == 2:
            two_q_count += 1
            edge = tuple(sorted(physical))
            if edge not in two_q_edges:
                two_q_edges.append(edge)

        try:
            error = props.gate_error(name, physical)
        except Exception:
            error = None

        if error is not None:
            gate_errors.append(error)
            if len(physical) == 2:
                two_q_errors.append(error)

    targets = measured_qubits or used_qubits
    readout_errors = []

    for q in sorted(targets):
        try:
            error = props.readout_error(q)
        except Exception:
            error = None
        if error is not None:
            readout_errors.append(error)

    readout_success = 1.0
    for error in readout_errors:
        readout_success *= 1.0 - error

    gate_success = 1.0
    for error in gate_errors:
        gate_success *= 1.0 - error

    readout_loss = 1.0 - readout_success
    gate_loss = 1.0 - gate_success
    combined_risk = 1.0 - (
        (1.0 - readout_loss) * (1.0 - gate_loss)
    )

    return {
        "physical_qubits": sorted(used_qubits),
        "readout_loss": readout_loss,
        "gate_loss": gate_loss,
        "combined_risk": combined_risk,
        "gate_count": gate_count,
        "2Q_gates": two_q_count,
        "2Q_edges": two_q_edges,
        "depth": compiled.depth(),
    }

print("Connecting to IBM Quantum...")
service = QiskitRuntimeService(
    channel="ibm_quantum_platform",
    instance="open-instance"
)
circuit = loads(QASM)
stage1 = []
backend_data = {}

for name in BACKENDS:
    print(f"\n{'=' * 60}\nBACKEND: {name}")
    try:
        backend = service.backend(name)
        status = backend.status()
        print("Status:", status.status_msg)
        print("Operational:", status.operational)

        if not status.operational or circuit.num_qubits > backend.num_qubits:
            print("Skipped by dashboard's availability check.")
            continue

        props = backend.properties(refresh=True)
        backend_data[name] = (backend, props)
        print("Calibration properties loaded.")

        for seed in SEEDS:
            try:
                compiled = transpile(
                    circuit,
                    backend=backend,
                    optimization_level=1,
                    layout_method="sabre",
                    routing_method="sabre",
                    seed_transpiler=seed,
                )
                metrics = analyze_candidate(compiled, props)
                stage1.append({
                    "backend": name,
                    "candidate": seed,
                    **metrics,
                })
                print(
                    f"STAGE 1 PASS: seed={seed}, "
                    f"risk={metrics['combined_risk']:.6f}"
                )
            except Exception as exc:
                print(f"STAGE 1 FAIL: seed={seed}: {exc!r}")
                traceback.print_exc()

    except Exception as exc:
        print("BACKEND SETUP FAIL:", repr(exc))
        traceback.print_exc()

print("\n" + "=" * 60)
print("STAGE 1 TOTAL:", len(stage1))

if not stage1:
    print("No stage 1 candidates were generated.")
else:
    shortlist = (
        pd.DataFrame(stage1)
        .sort_values("combined_risk")
        .groupby("backend")
        .head(1)
    )
    final_rows = []

    for _, candidate in shortlist.iterrows():
        name = candidate["backend"]
        seed = int(candidate["candidate"])
        print(f"\nSTAGE 2: {name}, seed={seed}")

        try:
            backend, props = backend_data[name]
            compiled = transpile(
                circuit,
                backend=backend,
                optimization_level=3,
                layout_method="sabre",
                routing_method="sabre",
                seed_transpiler=seed,
            )

            calibration_time = props.last_update_date
            if calibration_time is None:
                age_minutes = float("nan")
            else:
                timestamp = calibration_time
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
                age_minutes = (
                    datetime.now(timezone.utc) - timestamp
                ).total_seconds() / 60.0

            metrics = analyze_candidate(compiled, props)
            final_rows.append({
                "backend": name,
                "candidate": seed,
                "calibration_time": str(calibration_time),
                "calibration_age": age_minutes,
                **metrics,
            })
            print("STAGE 2 PASS:", metrics)

        except Exception as exc:
            print("STAGE 2 FAIL:", repr(exc))
            traceback.print_exc()

    print("\nFINAL CANDIDATE COUNT:", len(final_rows))
    if final_rows:
        print(pd.DataFrame(final_rows).to_string(index=False))

print("\nDiagnostic finished. No QPU jobs were submitted.")
