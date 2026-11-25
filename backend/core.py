"""CalibrationCompass core analysis logic.

This module holds the calibration-aware backend/mapping selection logic that
previously lived inside the Streamlit dashboard. It has no UI dependencies so it
can be served from a FastAPI process on Render.

IBM Quantum credentials are read from environment variables:

    IBM_QUANTUM_TOKEN   IBM Quantum API token (required for live calls)
    IBM_CHANNEL         Runtime channel (default: ibm_quantum_platform)
    IBM_INSTANCE        Instance / plan (default: open-instance)
"""

import math
import os
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

# Load backend/.env into the environment for local development. On Render the
# env vars are set in the dashboard, no .env exists, and existing env vars are
# never overridden, so this is a no-op there.
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).with_name(".env"))
except ImportError:
    pass

import pandas as pd
from qiskit import transpile
from qiskit.qasm2 import loads as qasm2_loads
from qiskit_ibm_runtime import QiskitRuntimeService

BACKENDS = ["ibm_fez", "ibm_kingston", "ibm_marrakesh"]

PRESETS = {
    "bell": (
        'OPENQASM 2.0;\n'
        'include "qelib1.inc";\n'
        'qreg q[2];\n'
        'creg c[2];\n'
        'h q[0];\n'
        'cx q[0],q[1];\n'
        'measure q[0] -> c[0];\n'
        'measure q[1] -> c[1];'
    ),
    "ghz": (
        'OPENQASM 2.0;\n'
        'include "qelib1.inc";\n'
        'qreg q[3];\n'
        'creg c[3];\n'
        'h q[0];\n'
        'cx q[0],q[1];\n'
        'cx q[1],q[2];\n'
        'measure q[0] -> c[0];\n'
        'measure q[1] -> c[1];\n'
        'measure q[2] -> c[2];'
    ),
    "ring": (
        'OPENQASM 2.0;\n'
        'include "qelib1.inc";\n'
        'qreg q[3];\n'
        'creg c[3];\n'
        'h q[0];\n'
        'cx q[0],q[1];\n'
        'cx q[1],q[2];\n'
        'cx q[2],q[0];\n'
        'measure q[0] -> c[0];\n'
        'measure q[1] -> c[1];\n'
        'measure q[2] -> c[2];'
    ),
}


@lru_cache(maxsize=1)
def get_service():
    """Build (and cache) a QiskitRuntimeService from environment config."""
    channel = os.environ.get("IBM_CHANNEL", "ibm_quantum_platform")
    instance = os.environ.get("IBM_INSTANCE", "open-instance")
    token = os.environ.get("IBM_QUANTUM_TOKEN")

    kwargs = {"channel": channel}
    if token:
        kwargs["token"] = token
    if instance:
        kwargs["instance"] = instance

    return QiskitRuntimeService(**kwargs)


def analyze_candidate(compiled, props):
    """Score a compiled circuit against a backend's live calibration data."""
    used_qubits = set()
    measured_qubits = set()
    gate_errors = []
    two_q_errors = []
    two_q_edges = []
    gate_count = 0
    two_q_count = 0

    for item in compiled.data:
        operation = item.operation
        physical = [compiled.find_bit(q).index for q in item.qubits]
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

    readout_targets = measured_qubits or used_qubits
    readout_errors = []

    for q in sorted(readout_targets):
        try:
            error = props.readout_error(q)
        except Exception:
            error = None

        if error is not None:
            readout_errors.append(error)

    readout_success = 1.0
    for error in readout_errors:
        readout_success *= (1.0 - error)
    readout_loss = 1.0 - readout_success

    gate_success = 1.0
    for error in gate_errors:
        gate_success *= (1.0 - error)
    gate_loss = 1.0 - gate_success

    combined_risk = 1.0 - ((1.0 - readout_loss) * (1.0 - gate_loss))

    return {
        "physical_qubits": sorted(used_qubits),
        "measured_qubits": sorted(measured_qubits),
        "readout_loss": readout_loss,
        "max_readout": max(readout_errors) if readout_errors else 0.0,
        "gate_loss": gate_loss,
        "gate_error_sum": sum(gate_errors),
        "2Q_gate_error_sum": sum(two_q_errors),
        "combined_risk": combined_risk,
        "gate_count": gate_count,
        "2Q_gates": two_q_count,
        "2Q_edges": [list(edge) for edge in two_q_edges],
        "depth": compiled.depth(),
    }


def analyze_backends(circuit, backend_names):
    """Two-stage calibration-aware evaluation across the selected backends."""
    service = get_service()

    fast_seeds = [11, 33, 55]

    stage1_results = []
    final_results = []
    status_rows = []
    backend_data = {}

    for backend_name in backend_names:
        try:
            backend = service.backend(backend_name)
            status = backend.status()

            status_rows.append({
                "Backend": backend_name,
                "Status": status.status_msg,
                "Operational": status.operational,
                "Pending jobs": status.pending_jobs,
            })

            if not status.operational or circuit.num_qubits > backend.num_qubits:
                continue

            props = backend.properties(refresh=True)
            backend_data[backend_name] = (backend, props)

            for seed in fast_seeds:
                try:
                    compiled = transpile(
                        circuit,
                        backend=backend,
                        optimization_level=1,
                        layout_method="sabre",
                        routing_method="sabre",
                        seed_transpiler=seed,
                    )

                    stage1_results.append({
                        "backend": backend_name,
                        "candidate": seed,
                        **analyze_candidate(compiled, props),
                    })

                except Exception:
                    continue

        except Exception as exc:
            status_rows.append({
                "Backend": backend_name,
                "Status": f"Error: {exc}",
                "Operational": False,
                "Pending jobs": None,
            })

    if not stage1_results:
        return pd.DataFrame(), pd.DataFrame(status_rows)

    stage1_df = pd.DataFrame(stage1_results)

    shortlist = (
        stage1_df
        .sort_values("combined_risk")
        .groupby("backend")
        .head(1)
        .copy()
    )

    for _, candidate in shortlist.iterrows():
        backend_name = candidate["backend"]
        seed = int(candidate["candidate"])

        try:
            backend, props = backend_data[backend_name]

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
                age_minutes = math.nan
            else:
                timestamp = calibration_time
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
                age_minutes = (
                    datetime.now(timezone.utc) - timestamp
                ).total_seconds() / 60.0

            final_results.append({
                "backend": backend_name,
                "candidate": seed,
                "calibration_time": str(calibration_time),
                "calibration_age": age_minutes,
                **analyze_candidate(compiled, props),
            })

        except Exception:
            continue

    return pd.DataFrame(final_results), pd.DataFrame(status_rows)


def _clean(value):
    """Make a value JSON-safe (NaN/inf -> None)."""
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def run_analysis(qasm_text, backend_names):
    """End-to-end analysis returning a JSON-serializable result dict.

    Raises ValueError for user/input errors (mapped to HTTP 400 upstream).
    """
    if not backend_names:
        raise ValueError("Select at least one backend.")

    try:
        circuit = qasm2_loads(qasm_text)
    except Exception as exc:
        raise ValueError(f"QASM parsing failed: {exc}")

    if circuit.num_qubits == 0:
        raise ValueError("The circuit contains no qubits.")

    results_df, status_df = analyze_backends(circuit, backend_names)

    circuit_info = {
        "logical_qubits": circuit.num_qubits,
        "depth": circuit.depth(),
        "operations": int(sum(circuit.count_ops().values())),
        "diagram": str(circuit.draw(output="text")),
    }

    status = status_df.to_dict(orient="records") if not status_df.empty else []

    if results_df.empty:
        return {
            "circuit": circuit_info,
            "status": status,
            "results": [],
            "recommendation": None,
            "confidence": None,
            "message": (
                "No operational backend could run this circuit. "
                "Check backend status above."
            ),
        }

    results_df = results_df.sort_values("combined_risk").reset_index(drop=True)
    best = results_df.iloc[0]

    if len(results_df) > 1:
        margin = (
            results_df.iloc[1]["combined_risk"] - best["combined_risk"]
        )
    else:
        margin = math.nan

    if math.isnan(margin):
        confidence_label = "Single option"
    elif margin >= 0.010:
        confidence_label = "Strong preference"
    elif margin >= 0.003:
        confidence_label = "Moderate preference"
    else:
        confidence_label = "Close call"

    results = []
    for row in results_df.to_dict(orient="records"):
        results.append({k: _clean(v) for k, v in row.items()})

    recommendation = {
        "backend": best["backend"],
        "candidate": int(best["candidate"]),
        "physical_qubits": best["physical_qubits"],
        "combined_risk": _clean(float(best["combined_risk"])),
        "readout_loss": _clean(float(best["readout_loss"])),
        "gate_loss": _clean(float(best["gate_loss"])),
        "2Q_gates": int(best["2Q_gates"]),
        "depth": int(best["depth"]),
        "calibration_age": _clean(float(best["calibration_age"])),
        "calibration_time": best.get("calibration_time"),
    }

    confidence = {
        "label": confidence_label,
        "margin": _clean(float(margin)) if not math.isnan(margin) else None,
        "final_candidates": len(results_df),
    }

    return {
        "circuit": circuit_info,
        "status": status,
        "results": results,
        "recommendation": recommendation,
        "confidence": confidence,
        "message": None,
    }
