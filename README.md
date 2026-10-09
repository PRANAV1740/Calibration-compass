# CalibrationCompass

## Calibration-Aware Quantum Circuit Compilation and Backend Selection

CalibrationCompass is a quantum circuit optimization and backend-selection system designed for execution on noisy quantum hardware.

Its central question is:

> **Given a quantum circuit and several available quantum backends, which backend and physical mapping should be used to make the most hardware-aware execution choice under current calibration conditions?**

Instead of treating transpilation as only a circuit-optimization problem, CalibrationCompass considers the current condition of the hardware, the physical qubits selected by the transpiler, and the calibration-related risk associated with those resources.

The project combines Qiskit transpilation, live IBM Quantum calibration information, candidate mapping search, and an explainable ranking system.

---

## 1. The Problem

Running the same logical quantum circuit on real quantum processors can produce different results.

This happens because real QPUs are noisy and because their physical qubits do not all behave identically.

Important hardware properties include:

- Readout error
- Gate error
- T1 relaxation time
- T2 coherence time
- Gate duration
- Connectivity
- Calibration age

There is another important source of variation: **logical-to-physical qubit mapping**.

A logical circuit can often be mapped to several different physical qubit sets or layouts. Two transpiled versions of the same circuit can therefore experience different hardware error characteristics.

This creates two connected decisions:

### Backend selection

Which available processor is the most suitable for the circuit right now?

### Mapping selection

Once a backend is considered, which logical-to-physical mapping is the most attractive?

CalibrationCompass addresses both decisions.

---

## 2. Core Idea

The system evaluates candidate execution plans using:

1. Circuit structure
2. Live backend calibration information
3. Physical qubit quality
4. Readout error exposure
5. Gate-error exposure
6. Logical-to-physical mapping
7. Two-qubit interaction exposure
8. Calibration age

The current dashboard converts the relevant readout and gate-error exposure into a **calibration-risk score** and uses that score to rank candidates.

The goal is not:

> "Find the shortest circuit."

The goal is:

> **"Find a hardware execution plan that is better aligned with the current condition of the available quantum hardware."**

---

## 3. What Makes CalibrationCompass Different?

Qiskit and IBM Quantum already provide advanced transpilation and routing capabilities.

CalibrationCompass focuses on a higher-level execution decision:

> **Which backend and which candidate mapping should we choose before execution?**

The project therefore combines:

### Cross-backend selection

The same circuit can behave differently on different processors.

### Calibration-aware selection

Hardware conditions change over time, so a useful decision should consider current calibration data.

### Mapping sensitivity

Different SABRE transpiler seeds can produce different physical mappings for the same logical circuit.

### Explainability

The system shows the selected backend, candidate, physical qubits, two-qubit edges, calibration age, and calibration-related risk.

### Real hardware validation

The project includes experiments performed on live IBM Quantum hardware in addition to simulator-based studies.

---

## 4. System Architecture

```text
                         ┌──────────────────────┐
                         │   User Quantum       │
                         │      Circuit         │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │ Circuit Analysis     │
                         │                      │
                         │ Qubits               │
                         │ Depth                │
                         │ 2Q gates             │
                         │ Circuit structure    │
                         └──────────┬───────────┘
                                    │
                                    ▼
              ┌────────────────────────────────────────┐
              │       IBM Quantum Backends             │
              │                                        │
              │ ibm_fez                               │
              │ ibm_kingston                          │
              │ ibm_marrakesh                         │
              └───────────────┬────────────────────────┘
                              │
                              ▼
                 ┌────────────────────────────┐
                 │ Live Calibration Data      │
                 │                            │
                 │ Readout error              │
                 │ Gate error                 │
                 │ Calibration timestamp      │
                 │ Other backend properties    │
                 └──────────────┬─────────────┘
                                │
                                ▼
                 ┌────────────────────────────┐
                 │ Candidate Generation       │
                 │                            │
                 │ SABRE seeds                │
                 │ Physical qubits            │
                 │ 2Q interaction exposure    │
                 └──────────────┬─────────────┘
                                │
                                ▼
                 ┌────────────────────────────┐
                 │ Two-Stage Transpilation    │
                 │                            │
                 │ Stage 1: fast screening    │
                 │ Stage 2: deep refinement   │
                 └──────────────┬─────────────┘
                                │
                                ▼
                 ┌────────────────────────────┐
                 │ Calibration-Aware Ranking  │
                 │                            │
                 │ Risk score                 │
                 │ Candidate ranking          │
                 │ Backend comparison         │
                 └──────────────┬─────────────┘
                                │
                                ▼
                 ┌────────────────────────────┐
                 │ Recommendation             │
                 │                            │
                 │ Backend + Candidate        │
                 │ Physical mapping           │
                 │ Explanation                │
                 └──────────────┬─────────────┘
                                │
                                ▼
                    ┌────────────────────────┐
                    │ Optional QPU Execution │
                    └────────────────────────┘
```

---

## 5. Two-Stage Transpilation

Evaluating a large number of candidates can be expensive because every candidate requires transpilation.

CalibrationCompass therefore uses two stages.

### Stage 1: Fast Screening

The current dashboard evaluates:

- 3 IBM Quantum backends
- 3 SABRE seeds per backend
- Optimization level 1

This creates:

```text
3 backends × 3 candidates = 9 initial candidates
```

The purpose is to quickly identify the strongest candidate for each backend.

### Stage 2: Deep Refinement

The best Stage 1 candidate from each backend is retranspiled using:

- Optimization level 3
- SABRE layout
- SABRE routing
- The same candidate seed

This creates:

```text
3 finalists × deep refinement = 3 final candidates
```

Overall:

```text
9 fast candidates
        ↓
3 finalists
        ↓
3 deep refinements
        ↓
3 final candidates
        ↓
Recommendation
```

This reduces the number of expensive optimization-level-3 transpilation runs compared with deeply transpiling every initial candidate.

---

## 6. Why Mapping Matters

A logical circuit can have multiple physically valid mappings.

For example:

```text
Logical circuit

q0 ──■────H────
     │
q1 ──X─────────
```

can be mapped to different physical qubits:

```text
Candidate A

logical q0 → physical 22
logical q1 → physical 23
```

or:

```text
Candidate B

logical q0 → physical 33
logical q1 → physical 34
```

These candidates can expose the circuit to different readout and gate-error conditions.

Our experiments found that candidate mapping can produce **substantial differences in observed fidelity**, even for the same logical circuit and backend.

---

## 7. Candidate Generation

CalibrationCompass uses Qiskit's SABRE-based transpilation process with different transpiler seeds to generate candidate mappings.

A candidate contains information such as:

- Backend
- Candidate seed
- Physical qubits used
- Circuit depth
- Gate count
- Two-qubit gate count
- Two-qubit physical edges
- Readout-error exposure
- Gate-error exposure

The candidate is then evaluated using the current calibration information available for that backend.

---

## 8. Current Calibration-Risk Model

The dashboard's current ranking is deliberately interpretable.

For every candidate, it calculates:

### Readout loss

A multiplicative estimate based on the readout error of the physical qubits involved in the measured circuit.

### Gate loss

A multiplicative estimate based on the gate-error values associated with the gates in the transpiled candidate.

### Combined calibration risk

The dashboard combines these losses into a single relative risk value.

Conceptually:

```text
Lower calibration risk
        ↓
More attractive candidate
```

This score is a **relative hardware-risk indicator**.

It is not an exact prediction of experimental fidelity.

---

## 9. Live IBM Quantum Backends

The live dashboard currently evaluates:

- `ibm_fez`
- `ibm_kingston`
- `ibm_marrakesh`

The calibration values are retrieved from IBM Quantum at analysis time.

Because hardware is continuously recalibrated, the exact values can change between runs.

The backend selected today therefore does not have to be the backend selected tomorrow.

---

# 10. Experimental Validation

The project was validated in both simulated-noise environments and on live IBM Quantum hardware.

It is important to distinguish these two categories.

### Simulator-based experiments

Several early benchmarks use Qiskit's fake IBM backends together with Aer noise models.

These are useful for controlled experimentation and rapid benchmarking.

### Real hardware experiments

Separate datasets were collected by submitting circuits to live IBM Quantum QPUs.

These results are used to evaluate how well calibration-aware recommendations correspond to actual hardware behaviour.

---

## 10.1 Simulator Backend Benchmark

A three-qubit GHZ circuit was evaluated using Qiskit's fake IBM backends and Aer noise models.

| Backend | Simulated Fidelity |
|---|---:|
| Sherbrooke | 93.00% |
| Torino | 75.80% |
| Fez | **96.25%** |

These are **simulated noisy-backend results, not live QPU measurements**.

They demonstrate that backend characteristics can produce substantially different outcomes for the same logical circuit.

---

## 10.2 Calibration Drift Experiment

A synthetic calibration-drift experiment tested whether changing hardware conditions could change the preferred backend.

At baseline conditions, Fez was preferred.

When the assumed readout error of one Fez qubit was progressively increased, the preferred backend changed.

Conceptually:

```text
Baseline conditions
        ↓
Fez preferred

Increasing readout degradation
        ↓
Fez risk increases

Large degradation
        ↓
Sherbrooke becomes preferable
```

This experiment illustrates why backend selection should not rely only on static topology.

---

## 10.3 Circuit-Type Benchmark

Different circuit structures respond differently to hardware noise.

Using fake IBM backends and Aer noise models:

| Circuit | Sherbrooke | Torino | Fez |
|---|---:|---:|---:|
| GHZ | 91.11% | 75.18% | **94.32%** |
| QFT-like | **99.95%** | 99.86% | 99.86% |
| QAOA-like | 99.37% | 99.42% | **99.62%** |
| Hardware-efficient | 98.97% | 95.32% | **99.73%** |

The key result is that there is **no single backend that is best for every circuit type** in this benchmark.

---

## 10.4 Candidate Mapping Benchmark

Multiple candidate mappings were evaluated for each fake backend.

The benchmark contained:

```text
180 candidate evaluations
```

The observed fidelity spread was:

| Backend | Minimum Fidelity | Maximum Fidelity | Best-Worst Gap |
|---|---:|---:|---:|
| Sherbrooke | 29.34% | 99.23% | 69.89 pts |
| Torino | 27.62% | 98.67% | 71.05 pts |
| Fez | 46.40% | 99.66% | 53.27 pts |

This is strong evidence that the physical mapping can materially affect circuit behaviour.

---

## 10.5 Calibration-Based Candidate Selection

A calibration-based ESP-style selector was compared with an oracle that knows which candidate achieved the highest observed fidelity in the benchmark.

For 30 candidate decisions:

| Metric | Calibration-Based Selector |
|---|---:|
| Oracle selection accuracy | 73.33% |
| Average regret | 0.00564 |
| Maximum regret | 0.08932 |

The result shows that calibration information contains useful predictive signal, but it does not perfectly determine the experimentally best candidate.

---

## 10.6 Pairwise Candidate Model

A pairwise ranking model was also tested.

Cross-validation results:

| Metric | ESP | Pairwise Model |
|---|---:|---:|
| Selection accuracy | 73.33% | 70.00% |
| Average regret | 0.00564 | **0.00369** |
| Maximum regret | 0.08932 | **0.02512** |

The pairwise model reduced regret on this cross-validation experiment, although it did not improve selection accuracy.

This reinforced an important lesson:

> Better prediction of a numerical value does not automatically produce better candidate-selection decisions.

---

# 11. Machine-Learning Findings

Machine-learning models were investigated for backend and candidate selection.

The experiments were useful for understanding the problem, but the final real-hardware dataset showed that the trained ML selector was not reliable enough to be the primary production decision-maker.

In the final three-circuit real-hardware leave-one-circuit-out evaluation:

```text
ML selection accuracy          = 0.00%
Calibration baseline accuracy  = 33.33%
```

The average regret was also much worse for the ML selector:

```text
ML average regret              ≈ 0.1737
Calibration average regret     ≈ 0.0173
```

This is why the current product does **not** present the ML model as the main selector.

Instead, the deployed recommendation is based on the more interpretable live calibration-risk approach.

The ML work remains part of the research contribution because it demonstrates how difficult it is to predict stochastic QPU behaviour from limited calibration snapshots.

---

# 12. Real Hardware Dataset

A real-hardware dataset was collected using:

- Bell circuits
- GHZ circuits
- Ring circuits
- Multiple IBM Quantum backends
- Multiple transpilation candidates

The final dataset contains:

```text
54 real-hardware observations
```

Mean fidelity by circuit type:

| Circuit Type | Mean Fidelity |
|---|---:|
| Bell | 94.45% |
| GHZ | 89.40% |
| Ring | 89.53% |

Mean fidelity by backend:

| Backend | Mean Fidelity |
|---|---:|
| ibm_fez | **93.50%** |
| ibm_kingston | 92.22% |
| ibm_marrakesh | 87.66% |

Observed range:

```text
Minimum fidelity ≈ 47.98%
Maximum fidelity ≈ 98.23%
```

These measurements came from real IBM Quantum hardware executions.

---

# 13. Live Hardware Mapping Validation

A live QPU experiment evaluated six candidate mappings on each of three IBM Quantum backends.

Best observed candidates:

| Backend | Best Candidate | Observed Fidelity |
|---|---|---:|
| ibm_fez | C33 | 97.10% |
| ibm_kingston | C66 | 97.34% |
| ibm_marrakesh | C55 | **97.75%** |

The globally best observed candidate was not always the candidate with the lowest calibration-risk score.

In this experiment:

```text
Lowest simple calibration risk
        ↓
ibm_kingston / C66

Highest observed hardware fidelity
        ↓
ibm_marrakesh / C55
```

This is an important validation result because it shows the difference between:

```text
Calibration-based risk estimation
```

and:

```text
Actual experimental QPU fidelity
```

Calibration data is useful, but it is not a perfect fidelity oracle.

---

# 14. Mapping Sensitivity on Live Hardware

A separate live validation experiment evaluated six candidates on several backends.

One representative set of results was:

| Backend | Candidate | Observed Fidelity |
|---|---:|---:|
| Fez | C11 | 96.58% |
| Fez | C22 | 96.08% |
| Fez | C33 | 96.68% |
| Fez | C44 | 44.64% |
| Fez | C55 | 96.16% |
| Fez | C66 | 89.74% |
| Sherbrooke | C11 | 90.76% |
| Sherbrooke | C22 | 42.34% |
| Sherbrooke | C33 | 86.42% |
| Sherbrooke | C44 | 94.80% |
| Sherbrooke | C55 | 74.26% |
| Sherbrooke | C66 | 89.66% |
| Torino | C11 | 89.84% |
| Torino | C22 | 93.80% |
| Torino | C33 | **22.28%** |
| Torino | C44 | 79.90% |
| Torino | C55 | 85.82% |
| Torino | C66 | 91.40% |

These results demonstrate that different transpilation candidates can have very different hardware outcomes.

---

# 15. Noise Ablation

Noise-ablation experiments were used to investigate which error source contributed most strongly to one representative candidate difference.

The experiment separated:

- Full noise
- Readout-only effects
- Gate-only effects
- Thermal effects

For the representative mapping comparison, the observed candidate gap was dominated by readout effects.

This supports including readout information in candidate evaluation.

It also reinforces that no single calibration metric fully describes a QPU.

---

# 16. Calibration Age

Calibration information is a time-dependent snapshot.

During live hardware validation, the calibration ages differed between backends.

Representative observations were approximately:

```text
Fez        ≈ 63.5 minutes
Kingston   ≈ 79.1 minutes
Marrakesh  ≈ 39.6 minutes
```

Calibration age is therefore exposed in the application so that users can see how recent the underlying hardware information is.

---

# 17. Recommendation Confidence

The dashboard provides a qualitative recommendation-strength indicator.

The current thresholds are:

```text
Risk margin >= 0.010
→ Strong preference

Risk margin >= 0.003
→ Moderate preference

Risk margin < 0.003
→ Close call
```

This is intentionally described as **ranking confidence**, not a probability that the circuit will succeed.

A "Strong preference" means the calibration-risk ranking separates the leading candidate more clearly from the next candidate.

---

# 18. Dashboard

CalibrationCompass provides an interactive Streamlit dashboard.

The interface supports:

- OpenQASM 2.0 input
- `.qasm` file upload
- Bell example circuit
- GHZ example circuit
- Ring example circuit
- Circuit analysis
- Live IBM Quantum backend status
- Live calibration retrieval
- Candidate mapping generation
- Two-stage transpilation
- Calibration-risk ranking
- Backend comparison
- Physical-qubit inspection
- Two-qubit-edge inspection
- Calibration-age inspection
- Recommendation confidence
- Optional QPU submission
- QPU job-status checking
- Measurement-count inspection

---

# 19. Dashboard Workflow

```text
Input QASM
    ↓
Parse circuit
    ↓
Analyze circuit structure
    ↓
Load live IBM backends
    ↓
Retrieve calibration data
    ↓
Generate candidate mappings
    ↓
Stage 1: fast screening
    ↓
Select best candidate per backend
    ↓
Stage 2: deep refinement
    ↓
Calculate calibration risk
    ↓
Rank candidates
    ↓
Explain recommendation
    ↓
Optional QPU execution
```

---

# 20. QPU Execution

CalibrationCompass supports optional execution on IBM Quantum hardware.

The execution flow is asynchronous:

```text
Submit circuit
      ↓
Receive IBM Job ID
      ↓
Job enters queue
      ↓
Check status
      ↓
Retrieve result when ready
```

This prevents the dashboard from blocking while the QPU job waits in the IBM Quantum queue.

A representative early real-QPU GHZ-style execution returned:

```text
00 → 240
11 → 238
01 → 14
10 → 20
```

From 512 shots, the expected `00`/`11` outcomes accounted for approximately:

```text
93.36%
```

---

# 21. Important Design Decision

CalibrationCompass separates:

### Calibration-risk estimation

from:

### Actual experimental fidelity

The calibration-risk score is derived from available hardware properties and candidate exposure.

It is useful for:

- Relative candidate ranking
- Hardware-risk explanation
- Current backend comparison
- Showing why one candidate is preferred

It is **not** a deterministic predictor of the exact fidelity a QPU will produce.

This distinction is central to the design of the system.

---

# 22. Limitations

### Calibration data is incomplete

The current score does not represent the complete physical noise environment of a QPU.

### Calibration changes over time

A recommendation can change after recalibration.

### QPU results are stochastic

Repeated executions can produce different results.

### Mapping effects are circuit-dependent

A mapping that works well for one circuit may not be optimal for another.

### Candidate search is limited

CalibrationCompass evaluates a selected set of candidates rather than every possible logical-to-physical mapping.

### The current risk score is heuristic

It is intentionally interpretable and lightweight rather than a full noise model.

### ML is not yet reliable enough as the main selector

The final real-hardware validation did not support using the trained ML model as the primary product decision-maker.

---

# 23. What We Learned

## Backend choice matters

Different quantum processors can produce different results for the same logical circuit.

## Mapping choice matters

Different transpiler seeds can produce dramatically different physical execution plans.

## Calibration matters

Changing hardware conditions can change the relative attractiveness of a backend or mapping.

## No single metric is sufficient

Readout error, gate error, circuit structure, connectivity, calibration age, and mapping exposure each provide only part of the picture.

## Better compilation does not automatically mean better hardware execution

Lower depth or fewer gates do not guarantee the highest observed fidelity.

## Prediction is harder than ranking

Real QPU behaviour is stochastic and time-dependent.

## Explainability matters

A hardware recommendation is more useful when the system also shows the physical qubits, mapping, calibration age, and risk behind the decision.

---

# 24. Installation

## Requirements

- Python 3.13 (tested locally with Python 3.13.15)
- Git

## Clone the repository

```powershell
git clone https://github.com/PRANAV1740/Calibration-compass.git
cd Calibration-compass
```

## Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

## Install dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The requirements.txt file records the direct package versions used in the tested environment.

---

# 25. IBM Quantum Configuration

CalibrationCompass uses IBM Quantum Runtime for live backend information and optional QPU execution.

Configure the IBM Quantum account through Qiskit Runtime:

```python
from qiskit_ibm_runtime import QiskitRuntimeService

QiskitRuntimeService.save_account(
    channel="ibm_quantum_platform",
    token="YOUR_IBM_QUANTUM_API_KEY",
    instance="open-instance",
    overwrite=True
)
```

**Never commit the API key to GitHub.**

Do not place the real key inside `dashboard.py`, this README, or any other tracked file.

---

# 26. Test the IBM Quantum Connection

Run:

```powershell
python check_ibm_connection.py
```

A successful connection allows the project to retrieve the configured IBM Quantum backends.

---

# 27. Run the Dashboard

From the project directory:

```powershell
streamlit run dashboard.py
```

Streamlit normally opens the application at:

```text
http://localhost:8501
```

---

# 28. Using the Dashboard

### 1. Enter a circuit

Paste an OpenQASM 2.0 circuit into the input area.

### 2. Or upload a QASM file

Use the `.qasm` upload option.

### 3. Or use an example

Choose:

- Bell
- GHZ
- Ring

### 4. Run the analysis

CalibrationCompass analyzes the circuit and retrieves live backend information.

### 5. Review the recommendation

The dashboard displays:

- Recommended backend
- Candidate
- Calibration risk
- Recommendation confidence
- Physical qubits
- Two-qubit edges
- Calibration age
- Candidate ranking

### 6. Optionally run on hardware

Submit the selected candidate to IBM Quantum and check the job status later.

---

# 29. Project Structure

The repository contains the application, live-hardware utilities, experiments, and saved results.

```text
Calibration-compass/
│
├── dashboard.py
├── calibrationcompass.py
├── qpu_executor.py
├── check_ibm_connection.py
│
├── live_ibm_backends.py
├── live_ibm_calibration.py
├── live_ibm_candidates.py
├── live_calibration_score.py
├── live_qasm_recommender.py
├── live_mapping_analysis.py
├── live_mapping_validation.py
├── live_backend_mapping_selection.py
├── live_drift_check.py
│
├── train_model.py
├── train_hard_model.py
├── train_real_model.py
├── train_final_real_model.py
├── live_model_test.py
├── validate_live_selection.py
│
├── collect_real_dataset.py
├── build_real_dataset_v2.py
├── rebuild_real_dataset_clean.py
│
├── experiments/
│   ├── backend comparison
│   ├── calibration analysis
│   ├── calibration drift
│   ├── candidate benchmarking
│   ├── mapping analysis
│   ├── noise analysis
│   ├── ML experiments
│   └── QPU experiments
│
└── results/
    ├── benchmark datasets
    ├── calibration analysis
    ├── candidate evaluations
    ├── mapping validation
    ├── ML results
    └── real-hardware results
```

The `experiments/` directory contains the research and validation scripts used during development.

The `results/` directory contains the datasets and outputs supporting the experimental conclusions.

---

# 30. Reproducibility

The project includes experiments covering:

```text
Backend comparison
Calibration analysis
Calibration drift
Candidate benchmarking
Candidate ranking
Mapping sensitivity
Noise ablation
Real hardware validation
Machine-learning experiments
QPU execution
```

The generated CSV files in `results/` provide the data used for the reported analyses.

The project can therefore be followed through:

```text
Source code
     ↓
Experiments
     ↓
Datasets
     ↓
Analysis
     ↓
Calibration-aware recommendation
     ↓
Optional QPU validation
```

---

# 31. Future Work

### Larger candidate search

Evaluate more transpiler seeds and more layout candidates.

### Richer calibration features

Include more backend properties and spatial relationships between physical qubits.

### Temporal modelling

Track calibration history instead of treating every snapshot independently.

### Better noise modelling

Include richer error information and crosstalk-related effects.

### Adaptive candidate search

Use early candidate results to decide which mappings deserve additional evaluation.

### Circuit-specific weighting

Learn which hardware characteristics matter most for different circuit families.

### Online learning

Use new QPU results to improve the recommendation system over time.

### Multi-objective optimization

Consider additional execution objectives such as:

- Queue time
- Execution time
- Circuit depth
- Gate count
- Backend availability
- Calibration risk

---

# 32. Current Status

CalibrationCompass currently provides:

- Live IBM Quantum backend discovery
- Live calibration retrieval
- OpenQASM 2.0 input
- QASM file upload
- Bell/GHZ/Ring example circuits
- Circuit analysis
- Candidate mapping generation
- Two-stage transpilation
- Calibration-aware candidate ranking
- Recommendation confidence
- Physical mapping explanation
- Calibration-age reporting
- Optional QPU submission
- Asynchronous QPU job checking
- Real hardware validation
- Experimental datasets
- Machine-learning research experiments

The current product direction is:

> **A calibration-aware quantum backend and mapping recommender**

rather than a guaranteed hardware-fidelity predictor.

---

# 33. Live Demo

The project deployment URL may change as deployment configuration evolves.

Current repository homepage:

https://calibrationcompass.vercel.app/

---

# 34. Repository

GitHub:

https://github.com/PRANAV1740/Calibration-compass

---

# 35. Conclusion

CalibrationCompass explores a practical problem in real-world quantum computing:

> **Given a circuit and multiple imperfect quantum processors, how can we make a better execution choice using the hardware information available right now?**

The project shows that:

```text
Circuit structure
        +
Backend selection
        +
Physical mapping
        +
Live calibration
        +
Candidate comparison
        ↓
Better-informed execution decisions
```

The experimental results show that both backend choice and physical mapping can materially affect observed quantum-circuit fidelity.

CalibrationCompass therefore treats the quantum processor as a **dynamic environment** rather than a fixed target.

The long-term goal is to make quantum circuit execution more adaptive, explainable, and hardware-aware.
