from qiskit import QuantumCircuit, transpile
from qiskit_ibm_runtime import QiskitRuntimeService

print("=" * 90)
print("CALIBRATIONCOMPASS - LIVE BACKEND + MAPPING SELECTION")
print("=" * 90)

service = QiskitRuntimeService()

backends = [
    "ibm_fez",
    "ibm_kingston",
    "ibm_marrakesh"
]

seeds = [11, 22, 33, 44, 55, 66]

# Simple 3-qubit GHZ circuit
qc = QuantumCircuit(3)
qc.h(0)
qc.cx(0, 1)
qc.cx(1, 2)
qc.measure_all()

all_results = []

for backend_name in backends:

    print()
    print("-" * 90)
    print("Checking backend:", backend_name)
    print("-" * 90)

    backend = service.backend(backend_name)
    props = backend.properties(refresh=True)

    for seed in seeds:

        compiled = transpile(
            qc,
            backend=backend,
            optimization_level=3,
            layout_method="sabre",
            routing_method="sabre",
            seed_transpiler=seed
        )

        readout_qubits = set()
        gate_risk = 0.0
        two_qubit_count = 0

        # Examine the actual physical circuit
        for item in compiled.data:

            operation = item.operation
            qargs = item.qubits
            name = operation.name.lower()

            physical_indices = [
                compiled.find_bit(q).index
                for q in qargs
            ]

            # Readout calibration risk
            if name == "measure":
                for q in physical_indices:
                    readout_qubits.add(q)
                continue

            if name in ["barrier", "delay", "reset"]:
                continue

            # Count 2-qubit gates
            if len(physical_indices) == 2:
                two_qubit_count += 1

            # Gate calibration error
            try:
                gate_risk += props.gate_error(
                    name,
                    physical_indices
                )
            except Exception:
                pass

        # Sum readout errors for measured physical qubits
        readout_risk = 0.0

        for q in sorted(readout_qubits):
            try:
                readout_risk += props.readout_error(q)
            except Exception:
                pass

        total_risk = readout_risk + gate_risk

        all_results.append({
            "backend": backend_name,
            "candidate": seed,
            "mapping": sorted(readout_qubits),
            "readout_risk": readout_risk,
            "gate_risk": gate_risk,
            "total_risk": total_risk,
            "depth": compiled.depth(),
            "2Q_gates": two_qubit_count
        })


# ============================================================
# GLOBAL RANKING
# ============================================================

all_results.sort(key=lambda x: x["total_risk"])

print()
print("=" * 90)
print("GLOBAL CALIBRATION RANKING")
print("=" * 90)

print(
    f"{'backend':<16}"
    f"{'candidate':>10}"
    f"{'mapping':>22}"
    f"{'readout':>12}"
    f"{'gate':>12}"
    f"{'total':>12}"
)

for r in all_results:
    print(
        f"{r['backend']:<16}"
        f"{r['candidate']:>10}"
        f"{str(r['mapping']):>22}"
        f"{r['readout_risk']:>12.6f}"
        f"{r['gate_risk']:>12.6f}"
        f"{r['total_risk']:>12.6f}"
    )


# ============================================================
# BEST MAPPING FOR EACH BACKEND
# ============================================================

print()
print("=" * 90)
print("BEST MAPPING PER BACKEND")
print("=" * 90)

for backend_name in backends:

    candidates = [
        r for r in all_results
        if r["backend"] == backend_name
    ]

    best = min(
        candidates,
        key=lambda x: x["total_risk"]
    )

    print()
    print("Backend:", best["backend"])
    print("Candidate:", best["candidate"])
    print("Mapping:", best["mapping"])
    print("Readout risk:", f"{best['readout_risk']:.6f}")
    print("Gate risk:", f"{best['gate_risk']:.6f}")
    print("Total risk:", f"{best['total_risk']:.6f}")


# ============================================================
# FINAL CALIBRATIONCOMPASS DECISION
# ============================================================

best = all_results[0]

print()
print("=" * 90)
print("CALIBRATIONCOMPASS RECOMMENDATION")
print("=" * 90)

print("Backend:", best["backend"])
print("Candidate:", best["candidate"])
print("Mapping:", best["mapping"])
print("Readout risk:", f"{best['readout_risk']:.6f}")
print("Gate risk:", f"{best['gate_risk']:.6f}")
print("Total risk:", f"{best['total_risk']:.6f}")

print()
print("Reason:")
print(
    "This backend + mapping combination has the lowest "
    "combined live calibration risk among all tested candidates."
)

print()
print("DONE")