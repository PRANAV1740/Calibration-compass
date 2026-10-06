import numpy as np

from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
from qiskit_ibm_runtime import fake_provider
from qiskit.quantum_info import hellinger_fidelity


# ============================================================
# SAME CIRCUIT GENERATOR
# ============================================================

def make_random_circuit(seed):
    rng = np.random.default_rng(seed)

    num_qubits = int(rng.integers(4, 9))
    circuit_depth = int(rng.integers(3, 9))

    qc = QuantumCircuit(num_qubits, num_qubits)

    for _ in range(circuit_depth):

        for q in range(num_qubits):

            choice = rng.integers(0, 3)

            if choice == 0:
                qc.h(q)

            elif choice == 1:
                qc.ry(
                    float(rng.uniform(0, 2 * np.pi)),
                    q
                )

            else:
                qc.rz(
                    float(rng.uniform(0, 2 * np.pi)),
                    q
                )

        number_of_entangling_gates = max(
            1,
            num_qubits // 2
        )

        for _ in range(number_of_entangling_gates):

            q1, q2 = rng.choice(
                num_qubits,
                size=2,
                replace=False
            )

            qc.cx(
                int(q1),
                int(q2)
            )

    qc.measure(
        range(num_qubits),
        range(num_qubits)
    )

    return qc


# ============================================================
# SETTINGS
# ============================================================

CIRCUIT_SEED = 20000
SHOTS = 50000

backend = fake_provider.FakeTorino()

circuit = make_random_circuit(CIRCUIT_SEED)

simulator = AerSimulator()

ideal_distributions = {}
noisy_distributions = {}

# ============================================================
# GENERATE CANDIDATES
# ============================================================

for candidate_seed in [22, 33]:

    print()
    print("=" * 80)
    print(f"CANDIDATE {candidate_seed}")
    print("=" * 80)

    transpiled = transpile(
        circuit,
        backend=backend,
        optimization_level=1,
        layout_method="sabre",
        routing_method="sabre",
        seed_transpiler=candidate_seed
    )

    # --------------------------------------------------------
    # IDEAL
    # --------------------------------------------------------

    ideal_result = simulator.run(
        transpiled,
        shots=SHOTS,
        seed_simulator=12345
    ).result()

    ideal_counts = ideal_result.get_counts()

    ideal_total = sum(ideal_counts.values())

    ideal_probabilities = {
        key: value / ideal_total
        for key, value in ideal_counts.items()
    }

    ideal_distributions[candidate_seed] = (
        ideal_probabilities
    )

    # --------------------------------------------------------
    # NOISY
    # --------------------------------------------------------

    noisy_simulator = AerSimulator.from_backend(
        backend
    )

    noisy_result = noisy_simulator.run(
        transpiled,
        shots=SHOTS,
        seed_simulator=54321
    ).result()

    noisy_counts = noisy_result.get_counts()

    noisy_total = sum(noisy_counts.values())

    noisy_probabilities = {
        key: value / noisy_total
        for key, value in noisy_counts.items()
    }

    noisy_distributions[candidate_seed] = (
        noisy_probabilities
    )

    # --------------------------------------------------------
    # CANDIDATE'S OWN FIDELITY
    # --------------------------------------------------------

    self_fidelity = hellinger_fidelity(
        ideal_probabilities,
        noisy_probabilities
    )

    print(
        "Ideal vs noisy fidelity:",
        f"{self_fidelity:.6f}"
    )

    # --------------------------------------------------------
    # TOP IDEAL STATES
    # --------------------------------------------------------

    print("\nTop ideal output states:")

    top_states = sorted(
        ideal_probabilities.items(),
        key=lambda x: x[1],
        reverse=True
    )[:10]

    for state, probability in top_states:

        print(
            f"  {state}: "
            f"{probability:.6f}"
        )


# ============================================================
# COMPARE THE TWO IDEAL CIRCUITS
# ============================================================

ideal_a = ideal_distributions[22]
ideal_b = ideal_distributions[33]

all_states = set(ideal_a) | set(ideal_b)

ideal_a_complete = {
    state: ideal_a.get(state, 0.0)
    for state in all_states
}

ideal_b_complete = {
    state: ideal_b.get(state, 0.0)
    for state in all_states
}

ideal_equivalence = hellinger_fidelity(
    ideal_a_complete,
    ideal_b_complete
)


# ============================================================
# COMPARE THE TWO NOISY CIRCUITS
# ============================================================

noisy_a = noisy_distributions[22]
noisy_b = noisy_distributions[33]

all_states = set(noisy_a) | set(noisy_b)

noisy_a_complete = {
    state: noisy_a.get(state, 0.0)
    for state in all_states
}

noisy_b_complete = {
    state: noisy_b.get(state, 0.0)
    for state in all_states
}

noisy_similarity = hellinger_fidelity(
    noisy_a_complete,
    noisy_b_complete
)


# ============================================================
# PRINT SUMMARY
# ============================================================

print()
print("=" * 80)
print("CANDIDATE EQUIVALENCE TEST")
print("=" * 80)

print()
print(
    "Hellinger fidelity between IDEAL outputs:",
    f"{ideal_equivalence:.6f}"
)

print(
    "Hellinger fidelity between NOISY outputs:",
    f"{noisy_similarity:.6f}"
)

print()
print("Interpretation:")

if ideal_equivalence > 0.99:
    print(
        "The two candidates produce essentially "
        "the same ideal computation."
    )

else:
    print(
        "The two candidates produce noticeably "
        "different ideal output distributions."
    )

print()
print("=" * 80)
print("ANALYSIS COMPLETE")
print("=" * 80)