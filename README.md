\# CalibrationCompass



\*\*CalibrationCompass\*\* is a quantum hardware selection and mapping tool that helps determine \*\*where and how a quantum circuit should be executed\*\* based on current IBM Quantum backend calibration data.



Instead of compiling a circuit for a single backend, CalibrationCompass evaluates multiple available backends and candidate mappings, analyzes calibration-related risks, and recommends the most suitable execution option.



\## Problem



Quantum hardware is not uniform.



Different QPUs can have different:



\- Readout errors

\- Gate errors

\- T1 and T2 coherence times

\- Gate durations

\- Calibration states

\- Physical qubit quality



Even on the same backend, different logical-to-physical qubit mappings can produce significantly different results.



A circuit that performs well on one backend or mapping may perform worse on another.



\## Our Approach



CalibrationCompass combines:



1\. \*\*Live IBM Quantum calibration data\*\*

2\. \*\*Cross-backend comparison\*\*

3\. \*\*Multiple transpilation candidates\*\*

4\. \*\*Physical-qubit mapping analysis\*\*

5\. \*\*Calibration-risk scoring\*\*

6\. \*\*Explainable recommendations\*\*

7\. \*\*Optional real QPU execution\*\*



The goal is not to claim a perfect fidelity prediction, but to provide a practical, calibration-aware recommendation before execution.



\## Two-Stage Transpilation



To reduce analysis time, CalibrationCompass uses a two-stage transpilation strategy.



\### Stage 1: Fast screening



For each backend, several candidate mappings are generated using:



\- Optimization level 1

\- SABRE layout/routing

\- Multiple transpiler seeds



\### Stage 2: Deep refinement



The best candidate from each backend is then recompiled using:



\- Optimization level 3

\- The selected transpiler seed



This reduces unnecessary high-cost transpilation while preserving candidate diversity.



For the current configuration:



\- 3 backends

\- 3 fast candidates per backend

\- 1 refined candidate per backend

\- 12 total transpilation passes instead of 18



\## System Flow



```text

Quantum Circuit

&#x20;     |

&#x20;     v

Circuit Analysis

&#x20;     |

&#x20;     v

Live Backend Calibration Data

&#x20;     |

&#x20;     v

Fast Candidate Screening

&#x20;     |

&#x20;     v

Best Candidate per Backend

&#x20;     |

&#x20;     v

Deep Transpilation Refinement

&#x20;     |

&#x20;     v

Calibration-Risk Analysis

&#x20;     |

&#x20;     v

Recommended Backend + Mapping

&#x20;     |

&#x20;     v

Optional IBM Quantum Execution

