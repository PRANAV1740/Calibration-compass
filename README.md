\# CalibrationCompass



\## Calibration-Aware Quantum Circuit Compilation and Backend Selection



CalibrationCompass is a quantum circuit optimization and backend-selection system designed to answer a practical question in real quantum computing:



> \*\*Given a quantum circuit and several available quantum backends, where should the circuit run, and which mapping should be used to give it the best chance of producing a reliable result under the current hardware conditions?\*\*



Instead of treating transpilation as a purely circuit-level optimization problem, CalibrationCompass considers the \*\*current calibration state of the hardware\*\*, the \*\*quality of physical qubits and connections\*\*, and the \*\*sensitivity of the circuit to different qubit mappings\*\*.



The system combines live IBM Quantum backend calibration data with Qiskit transpilation to produce a calibration-aware recommendation.



\---



\# 1. The Problem



Running a quantum circuit on real quantum hardware is not as simple as choosing the backend with the largest number of qubits.



Real quantum processors are noisy and their performance changes over time.



Different physical qubits can have different:



\- Readout errors

\- Gate errors

\- T1 relaxation times

\- T2 coherence times

\- Gate durations

\- Connectivity characteristics

\- Calibration ages



At the same time, a logical circuit can often be mapped to the physical hardware in many different ways.



Two transpiled versions of the \*\*same logical circuit\*\* can therefore produce significantly different hardware results.



This creates two related optimization problems:



\### Backend selection



Which available quantum processor is currently the most suitable for the circuit?



\### Mapping selection



Once a backend is selected, which logical-to-physical qubit mapping should be used?



Traditional compilation can optimize gate count, depth, routing, and hardware connectivity, but these optimizations do not necessarily identify the best backend under changing calibration conditions.



\---



\# 2. Our Approach



CalibrationCompass evaluates candidate execution plans by combining:



1\. \*\*Circuit structure\*\*

2\. \*\*Live backend calibration information\*\*

3\. \*\*Physical qubit quality\*\*

4\. \*\*Two-qubit interaction exposure\*\*

5\. \*\*Readout risk\*\*

6\. \*\*Candidate logical-to-physical mappings\*\*

7\. \*\*Calibration age\*\*

8\. \*\*Qiskit transpilation results\*\*



The system then ranks the available candidates and explains why a particular backend and mapping were recommended.



The goal is not simply:



> "Find the shortest circuit."



The goal is:



> \*\*"Find a hardware execution plan that balances circuit requirements with the current reliability of the hardware."\*\*



\---



\# 3. What Makes CalibrationCompass Different?



IBM and Qiskit already provide sophisticated transpilation and routing techniques.



CalibrationCompass focuses on a different layer of the problem.



Instead of assuming that the backend is already chosen, CalibrationCompass asks:



> \*\*Which backend and candidate mapping should we choose before execution?\*\*



The project therefore explores:



\### Cross-backend selection



Different processors can have substantially different performance for the same circuit.



\### Calibration-aware selection



Hardware quality changes over time, so a decision based only on static topology or qubit count can become outdated.



\### Mapping sensitivity



Different SABRE transpiler seeds can generate different physical mappings for the same circuit.



\### Explainability



The system reports the physical qubits, two-qubit connections, calibration age, and calibration-related risk behind a recommendation.



\### Real hardware validation



The project was tested against live IBM Quantum hardware rather than relying only on simulator results.



\---



\# 4. System Architecture



The overall workflow is:



```text

&#x20;                        ┌──────────────────────┐

&#x20;                        │   User Quantum       │

&#x20;                        │      Circuit         │

&#x20;                        └──────────┬───────────┘

&#x20;                                   │

&#x20;                                   ▼

&#x20;                        ┌──────────────────────┐

&#x20;                        │ Circuit Analysis     │

&#x20;                        │                      │

&#x20;                        │ Qubits               │

&#x20;                        │ Depth                │

&#x20;                        │ 2Q Gates             │

&#x20;                        │ Circuit structure    │

&#x20;                        └──────────┬───────────┘

&#x20;                                   │

&#x20;                                   ▼

&#x20;             ┌────────────────────────────────────────┐

&#x20;             │       IBM Quantum Backends             │

&#x20;             │                                        │

&#x20;             │ ibm\_fez                               │

&#x20;             │ ibm\_kingston                          │

&#x20;             │ ibm\_marrakesh                         │

&#x20;             └───────────────┬────────────────────────┘

&#x20;                             │

&#x20;                             ▼

&#x20;                ┌────────────────────────────┐

&#x20;                │ Live Calibration Data      │

&#x20;                │                            │

&#x20;                │ Readout error              │

&#x20;                │ Gate error                 │

&#x20;                │ T1                         │

&#x20;                │ T2                         │

&#x20;                │ Gate duration              │

&#x20;                │ Calibration age            │

&#x20;                └──────────────┬─────────────┘

&#x20;                               │

&#x20;                               ▼

&#x20;                ┌────────────────────────────┐

&#x20;                │ Candidate Generation       │

&#x20;                │                            │

&#x20;                │ SABRE mappings             │

&#x20;                │ Physical qubits            │

&#x20;                │ 2Q interaction exposure     │

&#x20;                └──────────────┬─────────────┘

&#x20;                               │

&#x20;                               ▼

&#x20;                ┌────────────────────────────┐

&#x20;                │ Two-Stage Transpilation    │

&#x20;                │                            │

&#x20;                │ Stage 1: fast screening    │

&#x20;                │ Stage 2: deep refinement   │

&#x20;                └──────────────┬─────────────┘

&#x20;                               │

&#x20;                               ▼

&#x20;                ┌────────────────────────────┐

&#x20;                │ Calibration-Aware Ranking  │

&#x20;                │                            │

&#x20;                │ Risk score                 │

&#x20;                │ Candidate ranking          │

&#x20;                │ Backend comparison         │

&#x20;                └──────────────┬─────────────┘

&#x20;                               │

&#x20;                               ▼

&#x20;                ┌────────────────────────────┐

&#x20;                │ Recommendation             │

&#x20;                │                            │

&#x20;                │ Backend + Candidate        │

&#x20;                │ Explanation                │

&#x20;                └──────────────┬─────────────┘

&#x20;                               │

&#x20;                               ▼

&#x20;                   ┌────────────────────────┐

&#x20;                   │ Optional QPU Execution │

&#x20;                   └────────────────────────┘

