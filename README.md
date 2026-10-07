# CalibrationCompass

## Calibration-Aware Quantum Circuit Compilation and Backend Selection

CalibrationCompass is a quantum circuit optimization and backend-selection system designed to answer a practical question in real quantum computing:

> **Given a quantum circuit and several available quantum backends, where should the circuit run, and which mapping should be used to give it the best chance of producing a reliable result under the current hardware conditions?**

Instead of treating transpilation as a purely circuit-level optimization problem, CalibrationCompass considers the **current calibration state of the hardware**, the **quality of physical qubits and connections**, and the **sensitivity of the circuit to different qubit mappings**.

The system combines live IBM Quantum backend calibration data with Qiskit transpilation to produce a calibration-aware recommendation.

---

# 1. The Problem

Running a quantum circuit on real quantum hardware is not as simple as choosing the backend with the largest number of qubits.

Real quantum processors are noisy and their performance changes over time.

Different physical qubits can have different:

- Readout errors
- Gate errors
- T1 relaxation times
- T2 coherence times
- Gate durations
- Connectivity characteristics
- Calibration ages

At the same time, a logical circuit can often be mapped to the physical hardware in many different ways.

Two transpiled versions of the **same logical circuit** can therefore produce significantly different hardware results.

This creates two related optimization problems:

### Backend selection

Which available quantum processor is currently the most suitable for the circuit?

### Mapping selection

Once a backend is selected, which logical-to-physical qubit mapping should be used?

Traditional compilation can optimize gate count, depth, routing, and hardware connectivity, but these optimizations do not necessarily identify the best backend under changing calibration conditions.

---

# 2. Our Approach

CalibrationCompass evaluates candidate execution plans by combining:

1. **Circuit structure**
2. **Live backend calibration information**
3. **Physical qubit quality**
4. **Two-qubit interaction exposure**
5. **Readout risk**
6. **Candidate logical-to-physical mappings**
7. **Calibration age**
8. **Qiskit transpilation results**

The system then ranks the available candidates and explains why a particular backend and mapping were recommended.

The goal is not simply:

> "Find the shortest circuit."

The goal is:

> **"Find a hardware execution plan that balances circuit requirements with the current reliability of the hardware."**

---

# 3. What Makes CalibrationCompass Different?

IBM and Qiskit already provide sophisticated transpilation and routing techniques.

CalibrationCompass focuses on a different layer of the problem.

Instead of assuming that the backend is already chosen, CalibrationCompass asks:

> **Which backend and candidate mapping should we choose before execution?**

The project therefore explores:

### Cross-backend selection

Different processors can have substantially different performance for the same circuit.

### Calibration-aware selection

Hardware quality changes over time, so a decision based only on static topology or qubit count can become outdated.

### Mapping sensitivity

Different SABRE transpiler seeds can generate different physical mappings for the same circuit.

### Explainability

The system reports the physical qubits, two-qubit connections, calibration age, and calibration-related risk behind a recommendation.

### Real hardware validation

The project was tested against live IBM Quantum hardware rather than relying only on simulator results.

---

# 4. System Architecture

The overall workflow is:

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
                         │ 2Q Gates             │
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
                 │ T1                         │
                 │ T2                         │
                 │ Gate duration              │
                 │ Calibration age            │
                 └──────────────┬─────────────┘
                                │
                                ▼
                 ┌────────────────────────────┐
                 │ Candidate Generation       │
                 │                            │
                 │ SABRE mappings             │
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
                 │ Explanation                │
                 └──────────────┬─────────────┘
                                │
                                ▼
                    ┌────────────────────────┐
                    │ Optional QPU Execution │
                    └────────────────────────┘
```

---

# 5. Two-Stage Transpilation Strategy

Evaluating many routing candidates can become expensive because every candidate requires transpilation.

CalibrationCompass therefore uses a two-stage strategy.

## Stage 1: Fast Screening

For each backend, several candidate seeds are evaluated using a lower-cost transpilation configuration.

Current implementation:

- 3 IBM Quantum backends
- 3 initial SABRE seeds per backend
- Optimization level 1

This produces:

```text
3 backends × 3 candidates = 9 initial candidates
```

The purpose of this stage is to quickly identify promising candidates.

## Stage 2: Deep Refinement

The strongest candidate from each backend is then retranspiled using:

- Optimization level 3
- SABRE layout
- SABRE routing
- The same candidate seed

This produces:

```text
3 best candidates × deep refinement = 3 final candidates
```

Therefore the normal workflow becomes:

```text
9 fast candidates
        ↓
3 finalists
        ↓
3 deep transpilation runs
        ↓
3 final candidates
        ↓
Recommendation
```

This reduces the number of expensive optimization-level-3 transpilation runs while preserving a meaningful search over backend and mapping candidates.

---

# 6. Why Mapping Matters

A logical quantum circuit can often be mapped onto a physical processor in many different ways.

For example:

```text
Logical circuit:

q0 ──■────H────
     │
q1 ──X─────────
```

could be mapped to different physical qubits:

```text
Candidate A:

logical q0 → physical 22
logical q1 → physical 23
```

or:

```text
Candidate B:

logical q0 → physical 33
logical q1 → physical 34
```

Even when the physical qubit sets are similar, assigning logical operations to different physical qubits can expose the circuit to different error characteristics.

Our experiments demonstrate that this can produce large differences in observed circuit fidelity.

---

# 7. Candidate Generation

CalibrationCompass uses Qiskit's SABRE-based transpilation process with different transpiler seeds to generate candidate mappings.

A candidate is characterized by properties such as:

- Backend
- Candidate seed
- Physical qubits used
- Circuit depth
- Number of two-qubit gates
- Two-qubit physical edges used
- Readout error exposure
- Gate error exposure
- T1 characteristics
- T2 characteristics
- Calibration age

This allows candidates to be compared using both circuit and hardware information.

---

# 8. Calibration-Aware Risk

CalibrationCompass calculates a hardware-risk score from calibration characteristics.

The purpose of the score is not to claim an exact hardware fidelity.

Instead, the score is used as a **relative indicator of hardware risk**.

Conceptually:

```text
Lower calibration risk
        ↓
More attractive candidate
        ↓
Higher expected reliability
```

The recommendation therefore answers:

> "Which candidate appears safest according to the currently available calibration information?"

rather than:

> "Which candidate is guaranteed to have the highest experimental fidelity?"

This distinction is important because quantum hardware behaviour is stochastic and calibration data is only a snapshot of the processor.

---

# 9. Live IBM Quantum Backends

During development and validation, CalibrationCompass was tested with live IBM Quantum backends including:

- `ibm_fez`
- `ibm_kingston`
- `ibm_marrakesh`

The exact calibration values are intentionally treated as **time-dependent**.

A backend that is preferable today may not remain preferable after calibration changes.

This is one of the main motivations for making the recommendation calibration-aware.

---

# 10. Experimental Validation

The project was evaluated through multiple stages.

## 10.1 Initial Backend Benchmark

A three-qubit GHZ experiment produced:

| Backend | Observed Fidelity |
|---|---:|
| Sherbrooke | 93.00% |
| Torino | 75.80% |
| Fez | **96.25%** |

This showed that backend choice alone can create a substantial performance difference.

---

# 11. Calibration Drift Experiment

A synthetic calibration-drift experiment was created to test whether backend selection should change when hardware conditions change.

Under the baseline conditions, Fez was preferred.

When the assumed readout error of one Fez qubit was progressively increased, the preferred backend changed.

The drift sweep demonstrated that:

```text
Stable calibration
        ↓
Fez preferred

Increasing calibration degradation
        ↓
Risk increases

Large degradation
        ↓
Sherbrooke becomes preferable
```

This demonstrates the core motivation behind calibration-aware backend selection.

---

# 12. Circuit-Type Benchmark

Different circuit structures respond differently to hardware noise.

A benchmark across several circuit families produced:

| Circuit | Sherbrooke | Torino | Fez |
|---|---:|---:|---:|
| GHZ | 91.11% | 75.18% | **94.32%** |
| QFT-like | **99.95%** | 99.86% | 99.86% |
| QAOA-like | 99.37% | 99.42% | **99.62%** |
| Hardware-efficient | 98.97% | 95.32% | **99.73%** |

The important observation is that **there is no universally best backend for every circuit**.

Circuit structure matters.

---

# 13. Candidate Mapping Benchmark

The project evaluated multiple transpilation candidates for each backend.

The benchmark contained:

```text
180 candidate executions
```

The observed fidelity spread was large.

| Backend | Minimum Fidelity | Maximum Fidelity | Gap |
|---|---:|---:|---:|
| Sherbrooke | 29.34% | 99.23% | 69.89 pts |
| Torino | 27.62% | 98.67% | 71.05 pts |
| Fez | 46.40% | 99.66% | 53.27 pts |

This is one of the strongest experimental observations from the project.

The same logical circuit can behave very differently depending on its physical mapping.

---

# 14. Candidate-Level Selection

A calibration-aware ESP-style selector was compared against an oracle that knows the experimentally best candidate.

For the candidate-level benchmark:

```text
Oracle decisions: 30
```

Results:

| Metric | Calibration-Based Selector |
|---|---:|
| Oracle selection accuracy | 73.33% |
| Average regret | 0.00564 |
| Maximum regret | 0.08932 |

The result shows that calibration features provide useful predictive information, but they do not perfectly determine experimental fidelity.

---

# 15. Pairwise Candidate Model

A pairwise candidate-ranking approach was also evaluated.

Cross-validation results:

| Metric | ESP | Pairwise Model |
|---|---:|---:|
| Selection accuracy | 73.33% | 70.00% |
| Average regret | 0.00564 | **0.00369** |
| Maximum regret | 0.08932 | **0.02512** |

The pairwise model reduced regret in the tested cross-validation dataset, although its selection accuracy was lower.

This experiment helped identify an important lesson:

> Better prediction of numerical fidelity does not automatically mean better selection accuracy.

---

# 16. Why the Final Product Does Not Depend on the ML Selector

Machine-learning models were tested for backend and candidate selection.

They were useful for experimentation, but the final real-hardware evaluation showed that a purely trained selector was not reliable enough to serve as the main product decision-maker.

On the final real-hardware dataset, the ML selector performed substantially worse than the calibration baseline.

Therefore, CalibrationCompass deliberately does **not** present the ML model as a guaranteed optimizer.

Instead, the product uses the more interpretable:

> **Live calibration-risk recommendation approach**

The ML experiments remain valuable as evidence that the problem is difficult and that hardware measurements alone do not perfectly predict future experimental fidelity.

---

# 17. Real Hardware Dataset

A real IBM Quantum hardware dataset was constructed using:

- Bell circuits
- GHZ circuits
- Ring-style circuits
- Multiple IBM Quantum backends
- Multiple transpilation candidates

The final dataset contained:

```text
54 real-hardware observations
```

Average fidelity by circuit type:

| Circuit Type | Mean Fidelity |
|---|---:|
| Bell | 94.45% |
| GHZ | 89.40% |
| Ring | 89.53% |

Average fidelity by backend:

| Backend | Mean Fidelity |
|---|---:|
| ibm_fez | **93.50%** |
| ibm_kingston | 92.22% |
| ibm_marrakesh | 87.66% |

Overall:

```text
Minimum observed fidelity ≈ 47.98%
Maximum observed fidelity ≈ 98.23%
```

These results further demonstrate the effect of backend and mapping choice.

---

# 18. Live Hardware Mapping Validation

A live validation experiment evaluated six candidate mappings on each of three IBM Quantum backends.

Best candidates observed:

| Backend | Best Candidate | Fidelity |
|---|---|---:|
| ibm_fez | C33 | 97.10% |
| ibm_kingston | C66 | 97.34% |
| ibm_marrakesh | C55 | **97.75%** |

An important observation was that the globally best candidate was not always the one selected by the simplest calibration score.

In this experiment:

```text
Simple calibration recommendation
            ↓
ibm_kingston / C66

Observed best hardware result
            ↓
ibm_marrakesh / C55
```

This validates the project's main limitation:

> Calibration is useful for making a hardware-risk-aware recommendation, but it cannot perfectly predict stochastic QPU performance.

---

# 19. Mapping Sensitivity

A separate mapping experiment demonstrated that different transpiler seeds can produce very different outcomes.

For example, on the same circuit and backend, candidate seeds produced results ranging from very high fidelity to substantially degraded fidelity.

A live validation sample showed:

```text
ibm_torino

Candidate 11 → 89.84%
Candidate 22 → 93.80%
Candidate 33 → 22.28%
Candidate 44 → 79.90%
Candidate 55 → 85.82%
Candidate 66 → 91.40%
```

This demonstrates why selecting only a backend is not sufficient.

The mapping itself can matter significantly.

---

# 20. Noise Ablation

To understand what was driving candidate differences, noise-ablation experiments separated:

- Readout effects
- Gate errors
- Thermal effects

For one representative mapping comparison, the observed candidate gap was dominated by readout effects.

This supports including readout-related hardware information when comparing candidates.

It also highlights why a single hardware metric is insufficient.

---

# 21. Calibration Age Matters

Calibration values are snapshots.

During live hardware validation, calibration snapshot ages differed between backends.

Example observations included calibration ages of roughly:

```text
Fez        ≈ 63.5 minutes
Kingston   ≈ 79.1 minutes
Marrakesh  ≈ 20.2 minutes
```

This means two backends can have calibration information that is not equally recent.

CalibrationCompass therefore exposes calibration age as part of the recommendation context.

---

# 22. Recommendation Confidence

CalibrationCompass also reports a qualitative recommendation confidence.

The current interface uses the difference between the best and next-best calibration-risk scores.

The displayed levels are:

```text
Risk margin >= 0.010
→ Strong preference

Risk margin >= 0.003
→ Moderate preference

Risk margin < 0.003
→ Close call
```

This is deliberately **not** presented as a probability of success.

It represents the strength of the ranking according to the calibration-risk metric.

---

# 23. User Interface

CalibrationCompass includes an interactive Streamlit dashboard.

The dashboard allows the user to:

- Enter an OpenQASM 2.0 circuit
- Upload a `.qasm` file
- Load example Bell, GHZ, and Ring circuits
- View circuit analysis
- Select from live IBM Quantum backends
- Analyze calibration information
- Generate candidate mappings
- Compare candidate risks
- View physical qubits and two-qubit edges
- Inspect calibration age
- View the recommended backend and candidate
- Submit a selected candidate to IBM Quantum hardware
- Check the status of a submitted QPU job
- Inspect returned measurement counts

---

# 24. Dashboard Workflow

The dashboard follows this process:

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
Stage 1 fast screening
   ↓
Select finalists
   ↓
Stage 2 deep refinement
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

# 25. QPU Execution

CalibrationCompass supports optional execution on real IBM Quantum hardware.

The execution workflow is intentionally asynchronous:

```text
Submit circuit
      ↓
Receive IBM Job ID
      ↓
Job enters queue
      ↓
Check status later
      ↓
Retrieve result when complete
```

This prevents the dashboard from blocking while the quantum job waits in the IBM Quantum queue.

The returned result can include measurement counts such as:

```text
00
01
10
11
```

For example, an initial real-QPU GHZ-style validation produced:

```text
00 → 240
11 → 238
01 → 14
10 → 20
```

with approximately:

```text
93.36% of shots in the expected 00/11 outcomes
```

---

# 26. Technical Stack

## Quantum Computing

- Qiskit
- Qiskit Aer
- Qiskit IBM Runtime
- Qiskit IBM Transpiler
- IBM Quantum hardware

## Programming

- Python 3.13
- NumPy
- pandas

## Machine Learning Experiments

- XGBoost
- scikit-learn
- SHAP

## Visualization

- Matplotlib
- Streamlit

## Deployment / Project Infrastructure

- Git
- GitHub
- Vercel deployment experiments

---

# 27. Project Structure

The repository contains the main application, live hardware utilities, experimental studies, and saved results.

```text
Calibration-compass/
│
├── dashboard.py
├── calibrationcompass.py
├── qpu_executor.py
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
├── train_final_real_model.py
├── train_real_model.py
├── validate_live_selection.py
├── live_model_test.py
│
├── collect_real_dataset.py
├── build_real_dataset_v2.py
├── rebuild_real_dataset_clean.py
├── fix_bell_dataset.py
├── fix_clean_bell.py
│
├── inspect_saved_jobs.py
├── check_ibm_connection.py
│
├── experiments/
│   ├── backend benchmarking
│   ├── calibration experiments
│   ├── drift experiments
│   ├── candidate benchmarking
│   ├── mapping analysis
│   ├── ML experiments
│   ├── noise analysis
│   └── QPU execution
│
└── results/
    ├── benchmark datasets
    ├── candidate evaluations
    ├── calibration analysis
    ├── mapping validation
    ├── ML experiments
    └── real hardware results
```

The `experiments/` directory contains the detailed research and validation scripts used during development.

The `results/` directory contains the generated datasets and experimental outputs supporting the conclusions described in this README.

---

# 28. Installation

## Clone the repository

```powershell
git clone https://github.com/PRANAV1740/Calibration-compass.git
cd Calibration-compass
```

## Create a virtual environment

```powershell
python -m venv qenv
```

Activate it:

```powershell
.\qenv\Scripts\Activate.ps1
```

## Install dependencies

The tested development environment uses Qiskit 2.4.2.

```powershell
pip install "qiskit==2.4.2"
pip install qiskit-aer
pip install qiskit-ibm-runtime
pip install qiskit-ibm-transpiler
pip install numpy pandas scikit-learn xgboost shap matplotlib streamlit
```

---

# 29. Configure IBM Quantum

CalibrationCompass can use IBM Quantum Runtime for live backend information and optional QPU execution.

Configure your IBM Quantum account through the Qiskit Runtime service.

Example:

```python
from qiskit_ibm_runtime import QiskitRuntimeService

QiskitRuntimeService.save_account(
    channel="ibm_quantum_platform",
    token="YOUR_IBM_QUANTUM_API_KEY",
    instance="open-instance",
    overwrite=True
)
```

Never commit your API key to GitHub.

The key should remain private and should never be placed directly inside `dashboard.py` or any other tracked source file.

---

# 30. Test the IBM Quantum Connection

Run:

```powershell
python check_ibm_connection.py
```

A successful connection should allow CalibrationCompass to access the configured IBM Quantum instance and retrieve available backends.

---

# 31. Run CalibrationCompass Locally

From the project directory:

```powershell
streamlit run dashboard.py
```

Streamlit will start the local application and provide a browser URL, normally similar to:

```text
http://localhost:8501
```

---

# 32. Using the Dashboard

### Step 1

Enter an OpenQASM 2.0 circuit.

### Step 2

Alternatively, upload a `.qasm` file.

### Step 3

Use one of the example circuits:

- Bell
- GHZ
- Ring

### Step 4

Run the analysis.

### Step 5

CalibrationCompass retrieves the current backend information.

### Step 6

The system evaluates candidate mappings using the two-stage transpilation strategy.

### Step 7

The dashboard displays:

- Recommended backend
- Recommended candidate
- Calibration risk
- Recommendation confidence
- Physical qubits
- Two-qubit edges
- Calibration age
- Candidate ranking

### Step 8

A selected candidate can optionally be submitted to real IBM Quantum hardware.

---

# 33. Important Design Decision

CalibrationCompass intentionally separates:

### Hardware-risk estimation

from

### Actual experimental fidelity

The calibration-risk score is derived from hardware properties and circuit exposure.

It is therefore useful for:

- Ranking candidates
- Explaining hardware risk
- Detecting potentially poor choices
- Comparing current backend conditions

It is **not** a deterministic predictor of the exact fidelity that the QPU will produce.

---

# 34. Limitations

Quantum hardware is stochastic and calibration data is incomplete.

Therefore:

### Calibration data is not the complete noise model

There are many hardware effects that are not completely captured by the simplified ranking score.

### Calibration changes over time

A recommendation can become less relevant as the device is recalibrated.

### Hardware results are probabilistic

The same circuit can produce different results across repeated executions.

### Mapping effects are circuit-dependent

A physical qubit that works well for one circuit is not necessarily optimal for another.

### Candidate search is limited

CalibrationCompass evaluates a selected set of transpilation candidates rather than every possible logical-to-physical mapping.

### Machine learning is not yet reliable enough as the primary selector

The ML experiments demonstrated interesting predictive behaviour but did not outperform the calibration-based strategy consistently enough to justify making ML the main decision mechanism.

---

# 35. What We Learned

The experiments led to several important conclusions.

## Backend choice matters

Different IBM Quantum processors can produce noticeably different results for the same logical circuit.

## Mapping choice matters

Different transpiler seeds can generate dramatically different physical execution plans.

## Calibration matters

Changes in assumed or observed hardware quality can change which backend appears preferable.

## No single metric is sufficient

Readout error, gate error, T1, T2, circuit depth, gate count, connectivity, and mapping exposure all provide partial information.

## Better compilation is not automatically better execution

A circuit with a smaller depth or fewer operations does not necessarily produce the highest experimental fidelity.

## Prediction is harder than ranking

Even sophisticated ML models can struggle because real QPU behaviour contains stochastic and time-dependent effects.

## Explainability is important

For a hardware recommendation system, showing the selected backend and the physical properties behind the recommendation is often more useful than simply returning one unexplained answer.

---

# 36. Future Work

CalibrationCompass can be extended in several directions.

### Larger candidate search

Evaluate more SABRE seeds and more layout candidates.

### More advanced calibration features

Include additional backend parameters and spatial correlations between physical qubits.

### Temporal modelling

Track calibration history rather than treating each calibration snapshot independently.

### Better noise modelling

Incorporate richer error models and crosstalk information.

### Adaptive candidate search

Use early candidate results to decide which additional mappings should be explored.

### Circuit-specific weighting

Automatically determine which calibration features matter most for different circuit families.

### Online learning

Use newly collected QPU results to continuously improve the recommendation strategy.

### Multi-objective optimization

Optimize not only fidelity risk but also:

- Execution time
- Queue time
- Circuit depth
- Number of gates
- Backend availability

---

# 37. Reproducibility

The repository contains the scripts used to perform the major experiments described in this README.

The most important categories include:

```text
Backend comparison
Calibration analysis
Calibration drift
Candidate benchmarking
Mapping sensitivity
Noise ablation
Real hardware validation
Machine learning experiments
QPU execution
```

The generated CSV files in `results/` contain the experimental outputs used for analysis.

This allows the project to be inspected from:

```text
Source code
      ↓
Experimental scripts
      ↓
Generated datasets
      ↓
Analysis
      ↓
Dashboard recommendation
```

---

# 38. Project Philosophy

CalibrationCompass is built around a simple principle:

> **Quantum compilation should consider the condition of the hardware, not only the structure of the circuit.**

A circuit that is theoretically equivalent can behave very differently on different physical resources.

Therefore, compilation and hardware selection should be considered together.

---

# 39. Current Status

CalibrationCompass currently provides:

- Live IBM Quantum backend discovery
- Live calibration retrieval
- OpenQASM 2.0 input
- QASM file upload
- Example Bell/GHZ/Ring circuits
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
- ML research experiments

The current product direction is a:

> **Calibration-aware quantum backend and mapping recommender**

rather than a guaranteed hardware-fidelity predictor.

---

# 40. Repository

GitHub:

https://github.com/PRANAV1740/Calibration-compass

---

# 41. Conclusion

CalibrationCompass explores a practical problem in real-world quantum computing:

> **Given a circuit and multiple imperfect quantum processors, how can we make a better execution choice using the hardware information available right now?**

The project demonstrates that:

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

The experimental results show that backend and mapping choices can materially affect observed quantum-circuit fidelity.

CalibrationCompass therefore treats quantum hardware as a **dynamic environment** rather than a fixed target.

The long-term goal is to make quantum circuit execution more adaptive, explainable, and hardware-aware.
