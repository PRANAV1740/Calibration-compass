import math
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from qiskit import transpile
from qiskit.qasm2 import loads as qasm2_loads
from qiskit_ibm_runtime import QiskitRuntimeService
from qpu_executor import submit_to_qpu, get_qpu_result


st.set_page_config(
    page_title="CalibrationCompass",
    page_icon="🧭",
    layout="wide"
)

st.markdown(
    """
    <style>
    .main-title { font-size: 2.5rem; font-weight: 800; margin-bottom: 0; }
    .subtitle { font-size: 1rem; opacity: 0.7; margin-bottom: 1.5rem; }
    .recommendation {
        padding: 1.3rem;
        border-radius: 15px;
        border: 1px solid rgba(100, 150, 255, 0.35);
        background: rgba(80, 120, 220, 0.08);
    }
    .recommendation-label {
        font-size: 0.75rem;
        opacity: 0.65;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }
    .recommendation-main {
        font-size: 1.8rem;
        font-weight: 800;
        margin-top: 0.3rem;
    }
    </style>
    """,
    unsafe_allow_html=True
)

BACKENDS = [
    "ibm_fez",
    "ibm_kingston",
    "ibm_marrakesh"
]

BELL_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0],q[1];
measure q[0] -> c[0];
measure q[1] -> c[1];"""

GHZ_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
cx q[0],q[1];
cx q[1],q[2];
measure q[0] -> c[0];
measure q[1] -> c[1];
measure q[2] -> c[2];"""

RING_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
cx q[0],q[1];
cx q[1],q[2];
cx q[2],q[0];
measure q[0] -> c[0];
measure q[1] -> c[1];
measure q[2] -> c[2];"""


if "qasm_text" not in st.session_state:
    st.session_state.qasm_text = GHZ_QASM

if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = pd.DataFrame()

if "analysis_status" not in st.session_state:
    st.session_state.analysis_status = pd.DataFrame()

if "analysis_circuit" not in st.session_state:
    st.session_state.analysis_circuit = None

if "analysis_qasm" not in st.session_state:
    st.session_state.analysis_qasm = ""

if "qpu_job_id" not in st.session_state:
    st.session_state.qpu_job_id = None

if "uploaded_signature" not in st.session_state:
    st.session_state.uploaded_signature = ""


def set_circuit(qasm):
    st.session_state.qasm_text = qasm
    st.session_state.analysis_results = pd.DataFrame()
    st.session_state.analysis_status = pd.DataFrame()
    st.session_state.analysis_circuit = None
    st.session_state.analysis_qasm = ""
    st.session_state.qpu_job_id = None


@st.cache_resource
def get_service():
    return QiskitRuntimeService(
        channel="ibm_quantum_platform",
        instance="open-instance"
    )


def analyze_candidate(compiled, props):

    used_qubits = set()
    measured_qubits = set()

    gate_errors = []
    two_q_errors = []
    two_q_edges = []

    gate_count = 0
    two_q_count = 0

    for item in compiled.data:

        operation = item.operation

        physical = [
            compiled.find_bit(q).index
            for q in item.qubits
        ]

        name = operation.name.lower()

        if name == "measure":

            measured_qubits.update(
                physical
            )

            continue

        if name in [
            "barrier",
            "delay",
            "reset"
        ]:

            continue

        used_qubits.update(
            physical
        )

        gate_count += 1

        if len(physical) == 2:

            two_q_count += 1

            edge = tuple(
                sorted(physical)
            )

            if edge not in two_q_edges:
                two_q_edges.append(edge)

        try:

            error = props.gate_error(
                name,
                physical
            )

        except Exception:

            error = None

        if error is not None:

            gate_errors.append(
                error
            )

            if len(physical) == 2:

                two_q_errors.append(
                    error
                )

    readout_targets = (
        measured_qubits
        or used_qubits
    )

    readout_errors = []

    for q in sorted(
        readout_targets
    ):

        try:

            error = props.readout_error(
                q
            )

        except Exception:

            error = None

        if error is not None:

            readout_errors.append(
                error
            )

    readout_success = 1.0

    for error in readout_errors:

        readout_success *= (
            1.0 - error
        )

    readout_loss = (
        1.0
        -
        readout_success
    )

    max_readout = (
        max(readout_errors)
        if readout_errors
        else 0.0
    )

    gate_success = 1.0

    for error in gate_errors:

        gate_success *= (
            1.0 - error
        )

    gate_loss = (
        1.0
        -
        gate_success
    )

    combined_risk = (
        1.0
        -
        (
            (1.0 - readout_loss)
            *
            (1.0 - gate_loss)
        )
    )

    return {
        "physical_qubits":
            sorted(used_qubits),

        "measured_qubits":
            sorted(measured_qubits),

        "readout_loss":
            readout_loss,

        "max_readout":
            max_readout,

        "gate_loss":
            gate_loss,

        "gate_error_sum":
            sum(gate_errors),

        "2Q_gate_error_sum":
            sum(two_q_errors),

        "combined_risk":
            combined_risk,

        "gate_count":
            gate_count,

        "2Q_gates":
            two_q_count,

        "2Q_edges":
            two_q_edges,

        "depth":
            compiled.depth()
    }


def analyze_backends(
    circuit,
    backend_names
):

    service = get_service()

    fast_seeds = [
        11,
        33,
        55
    ]

    stage1_results = []
    final_results = []
    status_rows = []

    backend_data = {}

    # ========================================================
    # STAGE 1
    # ========================================================

    for backend_name in backend_names:

        try:

            backend = service.backend(
                backend_name
            )

            status = backend.status()

            status_rows.append({
                "Backend":
                    backend_name,

                "Status":
                    status.status_msg,

                "Operational":
                    status.operational,

                "Pending jobs":
                    status.pending_jobs
            })

            if (
                not status.operational
                or
                circuit.num_qubits
                >
                backend.num_qubits
            ):

                continue

            props = backend.properties(
                refresh=True
            )

            backend_data[
                backend_name
            ] = (
                backend,
                props
            )

            for seed in fast_seeds:

                try:

                    compiled = transpile(
                        circuit,
                        backend=backend,
                        optimization_level=1,
                        layout_method="sabre",
                        routing_method="sabre",
                        seed_transpiler=seed
                    )

                    stage1_results.append({
                        "backend":
                            backend_name,

                        "candidate":
                            seed,

                        **analyze_candidate(
                            compiled,
                            props
                        )
                    })

                except Exception:

                    continue

        except Exception as exc:

            status_rows.append({
                "Backend":
                    backend_name,

                "Status":
                    f"Error: {exc}",

                "Operational":
                    False,

                "Pending jobs":
                    None
            })

    if not stage1_results:

        return (
            pd.DataFrame(),
            pd.DataFrame(
                status_rows
            )
        )

    # ========================================================
    # STAGE 2
    # ========================================================

    stage1_df = pd.DataFrame(
        stage1_results
    )

    shortlist = (
        stage1_df
        .sort_values(
            "combined_risk"
        )
        .groupby(
            "backend"
        )
        .head(1)
        .copy()
    )

    for _, candidate in (
        shortlist.iterrows()
    ):

        backend_name = (
            candidate["backend"]
        )

        seed = int(
            candidate["candidate"]
        )

        try:

            backend, props = (
                backend_data[
                    backend_name
                ]
            )

            compiled = transpile(
                circuit,
                backend=backend,
                optimization_level=3,
                layout_method="sabre",
                routing_method="sabre",
                seed_transpiler=seed
            )

            calibration_time = (
                props.last_update_date
            )

            if calibration_time is not None:

                timestamp = (
                    calibration_time
                )

                if timestamp.tzinfo is None:

                    timestamp = (
                        timestamp.replace(
                            tzinfo=timezone.utc
                        )
                    )

                age_minutes = (
                    datetime.now(
                        timezone.utc
                    )
                    -
                    timestamp
                ).total_seconds() / 60.0

            else:

                age_minutes = math.nan

            final_results.append({
                "backend":
                    backend_name,

                "candidate":
                    seed,

                "calibration_time":
                    str(
                        calibration_time
                    ),

                "calibration_age":
                    age_minutes,

                **analyze_candidate(
                    compiled,
                    props
                )
            })

        except Exception:

            continue

    return (
        pd.DataFrame(
            final_results
        ),
        pd.DataFrame(
            status_rows
        )
    )


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="main-title">'
    '🧭 CalibrationCompass'
    '</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">'
    'Live calibration-aware quantum backend and mapping selection'
    '</div>',
    unsafe_allow_html=True
)


# ============================================================
# CIRCUIT
# ============================================================

st.subheader(
    "1. Quantum Circuit"
)

b1, b2, b3, b4 = st.columns(4)

with b1:

    st.button(
        "Bell",
        on_click=set_circuit,
        args=(BELL_QASM,)
    )

with b2:

    st.button(
        "GHZ",
        on_click=set_circuit,
        args=(GHZ_QASM,)
    )

with b3:

    st.button(
        "Ring",
        on_click=set_circuit,
        args=(RING_QASM,)
    )

with b4:

    uploaded = st.file_uploader(
        "Upload .qasm",
        type=["qasm"]
    )

if uploaded is not None:

    uploaded_text = (
        uploaded
        .read()
        .decode("utf-8")
    )

    if (
        st.session_state.uploaded_signature
        !=
        uploaded_text
    ):

        st.session_state.qasm_text = (
            uploaded_text
        )

        st.session_state.uploaded_signature = (
            uploaded_text
        )

        st.session_state.analysis_results = (
            pd.DataFrame()
        )

        st.session_state.analysis_status = (
            pd.DataFrame()
        )

        st.session_state.analysis_circuit = (
            None
        )

        st.session_state.analysis_qasm = (
            ""
        )

        st.session_state.qpu_job_id = (
            None
        )

qasm_text = st.text_area(
    "OpenQASM 2.0",
    key="qasm_text",
    height=240
)


# ============================================================
# BACKENDS
# ============================================================

st.subheader(
    "2. IBM Quantum Backends"
)

selected_backends = st.multiselect(
    "Select backends",
    BACKENDS,
    default=BACKENDS
)


# ============================================================
# ANALYZE
# ============================================================

run = st.button(
    "🧭 Analyze with Live Calibration",
    type="primary",
    use_container_width=True
)


if run:

    try:

        circuit = qasm2_loads(
            qasm_text
        )

    except Exception as exc:

        st.error(
            f"QASM parsing failed: {exc}"
        )

        st.stop()

    if circuit.num_qubits == 0:

        st.error(
            "The circuit contains no qubits."
        )

        st.stop()

    if not selected_backends:

        st.error(
            "Select at least one backend."
        )

        st.stop()

    with st.spinner(
        "Refreshing calibration data and evaluating candidates..."
    ):

        results_df, status_df = (
            analyze_backends(
                circuit,
                selected_backends
            )
        )

    st.session_state.analysis_results = (
        results_df
    )

    st.session_state.analysis_status = (
        status_df
    )

    st.session_state.analysis_circuit = (
        circuit
    )

    st.session_state.analysis_qasm = (
        qasm_text
    )

    st.session_state.qpu_job_id = (
        None
    )


# ============================================================
# DISPLAY
# ============================================================

results_df = (
    st.session_state.analysis_results
)

status_df = (
    st.session_state.analysis_status
)

circuit = (
    st.session_state.analysis_circuit
)


if (
    circuit is not None
    and
    not results_df.empty
    and
    st.session_state.analysis_qasm
    ==
    qasm_text
):

    # ========================================================
    # CIRCUIT ANALYSIS
    # ========================================================

    st.subheader(
        "3. Circuit Analysis"
    )

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Logical qubits",
        circuit.num_qubits
    )

    c2.metric(
        "Original depth",
        circuit.depth()
    )

    c3.metric(
        "Operations",
        sum(
            circuit.count_ops().values()
        )
    )

    with st.expander(
        "Show circuit"
    ):

        st.code(
            circuit.draw(
                output="text"
            )
        )


    # ========================================================
    # BACKEND STATUS
    # ========================================================

    st.subheader(
        "4. Backend Status"
    )

    if not status_df.empty:

        st.dataframe(
            status_df,
            use_container_width=True,
            hide_index=True
        )


    # ========================================================
    # SORT
    # ========================================================

    results_df = (
        results_df
        .sort_values(
            "combined_risk"
        )
        .reset_index(
            drop=True
        )
    )

    best = results_df.iloc[0]


    if len(results_df) > 1:

        second = results_df.iloc[1]

        margin = (
            second["combined_risk"]
            -
            best["combined_risk"]
        )

    else:

        margin = math.nan


    # ========================================================
    # CONFIDENCE
    # ========================================================

    if math.isnan(margin):

        confidence_label = (
            "Single option"
        )

    elif margin >= 0.010:

        confidence_label = (
            "Strong preference"
        )

    elif margin >= 0.003:

        confidence_label = (
            "Moderate preference"
        )

    else:

        confidence_label = (
            "Close call"
        )


    # ========================================================
    # RECOMMENDATION
    # ========================================================

    st.subheader(
        "5. CalibrationCompass Recommendation"
    )

    st.markdown(
        f"""
        <div class="recommendation">

        <div class="recommendation-label">
        Recommended execution target
        </div>

        <div class="recommendation-main">
        {best["backend"]}
        · Candidate {int(best["candidate"])}
        </div>

        <div>
        Physical qubits:
        {best["physical_qubits"]}
        </div>

        <div>
        Combined calibration risk:
        <b>
        {best["combined_risk"]:.6f}
        </b>
        </div>

        </div>
        """,
        unsafe_allow_html=True
    )


    # ========================================================
    # QPU EXECUTION
    # ========================================================

    if st.button(
        "Run Recommended Candidate on IBM QPU",
        use_container_width=True
    ):

        with st.spinner(
            "Submitting job to IBM Quantum..."
        ):

            try:

                qpu_result = (
                    submit_to_qpu(
                        st.session_state.analysis_qasm,
                        best["backend"],
                        int(best["candidate"]),
                        shots=512
                    )
                )

                st.session_state.qpu_job_id = (
                    qpu_result["job_id"]
                )

                st.success(
                    "Job submitted successfully."
                )

            except Exception as exc:

                st.error(
                    f"QPU submission failed: {exc}"
                )


    if st.session_state.qpu_job_id:

        st.write(
            "Current Job ID:",
            st.session_state.qpu_job_id
        )

        if st.button(
            "Check QPU Result",
            use_container_width=True
        ):

            with st.spinner(
                "Checking IBM Quantum..."
            ):

                try:

                    result = (
                        get_qpu_result(
                            st.session_state.qpu_job_id
                        )
                    )

                    if result["ready"]:

                        st.success(
                            "QPU result is ready."
                        )

                        st.write(
                            "Measurement counts:",
                            result["counts"]
                        )

                    else:

                        st.info(
                            f"Job is still running: "
                            f"{result['status']}"
                        )

                except Exception as exc:

                    st.error(
                        f"Could not retrieve result: {exc}"
                    )


    # ========================================================
    # CONFIDENCE
    # ========================================================

    st.markdown(
        "### Recommendation confidence"
    )

    cc1, cc2, cc3 = st.columns(3)

    cc1.metric(
        "Assessment",
        confidence_label
    )

    cc2.metric(
        "Risk margin",
        (
            f"{margin:.6f}"
            if not math.isnan(margin)
            else
            "N/A"
        )
    )

    cc3.metric(
        "Final candidates",
        len(results_df)
    )


    if confidence_label == "Close call":

        st.warning(
            "Close call: the top candidates have "
            "very similar calibration risk. Treat "
            "the recommendation as a preference, "
            "not a guarantee."
        )

    elif confidence_label == (
        "Moderate preference"
    ):

        st.info(
            "Moderate preference: the recommended "
            "candidate has a noticeable "
            "calibration-risk advantage."
        )

    elif confidence_label == (
        "Strong preference"
    ):

        st.success(
            "Strong preference: the recommended "
            "candidate has a clear "
            "calibration-risk advantage."
        )


    # ========================================================
    # KEY METRICS
    # ========================================================

    k1, k2, k3, k4 = (
        st.columns(4)
    )

    k1.metric(
        "Readout loss",
        f"{best['readout_loss']:.5f}"
    )

    k2.metric(
        "Gate loss",
        f"{best['gate_loss']:.5f}"
    )

    k3.metric(
        "2Q gates",
        int(
            best["2Q_gates"]
        )
    )

    k4.metric(
        "Compiled depth",
        int(
            best["depth"]
        )
    )


    # ========================================================
    # WHY
    # ========================================================

    st.markdown(
        "### Why this candidate?"
    )

    st.write(
        f"CalibrationCompass selected "
        f"**{best['backend']} candidate "
        f"{int(best['candidate'])}** because it "
        f"has the lowest combined live "
        f"calibration risk among the "
        f"{len(results_df)} final candidates."
    )

    st.write(
        f"Physical qubits: "
        f"{best['physical_qubits']}"
    )

    st.write(
        f"Exact 2Q interactions: "
        f"{best['2Q_edges']}"
    )

    st.write(
        f"Calibration age: "
        f"{best['calibration_age']:.1f} minutes"
    )


    # ========================================================
    # RANKING
    # ========================================================

    st.subheader(
        "6. Candidate Ranking"
    )

    ranking_columns = [
        "backend",
        "candidate",
        "physical_qubits",
        "readout_loss",
        "gate_loss",
        "combined_risk",
        "2Q_gates",
        "depth",
        "calibration_age"
    ]

    ranking_df = (
        results_df[
            ranking_columns
        ].copy()
    )

    ranking_df["candidate"] = (
        ranking_df[
            "candidate"
        ].astype(int)
    )

    ranking_df.columns = [
        "Backend",
        "Candidate",
        "Physical qubits",
        "Readout loss",
        "Gate loss",
        "Combined risk",
        "2Q gates",
        "Depth",
        "Calibration age (min)"
    ]

    st.dataframe(
        ranking_df,
        use_container_width=True,
        hide_index=True
    )


    # ========================================================
    # BEST PER BACKEND
    # ========================================================

    st.subheader(
        "7. Best Candidate Per Backend"
    )

    best_per_backend = (
        results_df
        .loc[
            results_df.groupby(
                "backend"
            )[
                "combined_risk"
            ].idxmin()
        ]
        .sort_values(
            "combined_risk"
        )
    )

    backend_display = (
        best_per_backend[
            [
                "backend",
                "candidate",
                "physical_qubits",
                "combined_risk",
                "readout_loss",
                "gate_loss"
            ]
        ]
        .copy()
    )

    backend_display.columns = [
        "Backend",
        "Candidate",
        "Physical qubits",
        "Combined risk",
        "Readout loss",
        "Gate loss"
    ]

    st.dataframe(
        backend_display,
        use_container_width=True,
        hide_index=True
    )


    # ========================================================
    # RISK CHART
    # ========================================================

    st.subheader(
        "8. Calibration Risk"
    )

    chart_df = (
        results_df[
            [
                "backend",
                "candidate",
                "combined_risk"
            ]
        ]
        .copy()
    )

    chart_df["label"] = (
        chart_df["backend"]
        +
        " · C"
        +
        chart_df[
            "candidate"
        ]
        .astype(int)
        .astype(str)
    )

    chart_df = (
        chart_df
        .set_index("label")
    )

    st.bar_chart(
        chart_df[
            "combined_risk"
        ]
    )


    # ========================================================
    # TECHNICAL DETAILS
    # ========================================================

    with st.expander(
        "Technical details"
    ):

        st.write(
            "Calibration timestamp:",
            best[
                "calibration_time"
            ]
        )

        st.write(
            "Average T1:",
            best["avg_t1"]
            if "avg_t1" in best
            else "Not calculated"
        )

        st.write(
            "Average T2:",
            best["avg_t2"]
            if "avg_t2" in best
            else "Not calculated"
        )

        st.write(
            "Total gate error:",
            best[
                "gate_error_sum"
            ]
        )

        st.write(
            "2Q gate error:",
            best[
                "2Q_gate_error_sum"
            ]
        )

        st.write(
            "Maximum readout error:",
            best[
                "max_readout"
            ]
        )


    # ========================================================
    # LIMITATION
    # ========================================================

    st.info(
        "CalibrationCompass is a live "
        "calibration-risk recommender. "
        "It does not guarantee the highest "
        "execution fidelity on hardware."
    )

else:

    st.info(
        "Paste an OpenQASM 2.0 circuit and click "
        "'Analyze with Live Calibration'."
    )