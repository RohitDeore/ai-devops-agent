"""
dashboard.py — Streamlit Dashboard
====================================
Interactive UI for the AI DevOps Autonomous Incident Response Agent.

Run with:
    streamlit run ui/dashboard.py

The dashboard imports the agent modules directly (no Flask required),
so it can be started independently of the API server.
"""

import sys
import os
import json
import time
from datetime import datetime
from typing import List, Dict, Optional, Tuple

import streamlit as st
import pandas as pd

# ---------------------------------------------------------------------------
# Path setup — make the project root importable
# ---------------------------------------------------------------------------
_UI_DIR      = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_UI_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from app.agent.observer  import LogObserver
from app.agent.analyzer  import LogAnalyzer
from app.agent.foundry_reasoner import get_reasoning_engine, FoundryReasoningEngine
from app.agent.reasoner  import ReasoningEngine
from app.agent.decision  import DecisionEngine
from app.agent.actuator  import ActionActuator
from app.agent.reporter  import IncidentReporter
from app.utils.helpers   import severity_icon
import importlib
import config
importlib.reload(config)  # force fresh read so new .env vars are always visible

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
LOG_FILE = os.path.join(_PROJECT_ROOT, config.LOG_FILE_PATH)

SEVERITY_COLORS: Dict[str, str] = {
    "CRITICAL": "#FF3B3B",
    "ERROR":    "#FF8C00",
    "WARNING":  "#FFD700",
    "INFO":     "#32CD32",
}

# ---------------------------------------------------------------------------
# Page config (must be first Streamlit call)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="AI DevOps Incident Response Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Cached agent components — reused across reruns
# ---------------------------------------------------------------------------
@st.cache_resource
def _load_agents(simulation_mode: bool = True) -> Dict:
    return {
        "observer":  LogObserver(LOG_FILE),
        "analyzer":  LogAnalyzer(),
        "reasoner":  ReasoningEngine(use_ai=config.USE_AI_REASONING, api_key=config.OPENAI_API_KEY, model=config.OPENAI_MODEL),
        "decision":  DecisionEngine(),
        "actuator":  ActionActuator(simulation_mode=simulation_mode),
        "reporter":  IncidentReporter(),
    }


agents = _load_agents()

# ---------------------------------------------------------------------------
# Pipeline helper
# ---------------------------------------------------------------------------

def run_pipeline(
    use_ai: bool = False,
    openai_key=None,
    foundry_endpoint=None,
    foundry_api_key=None,
    foundry_deployment=None,
) -> Tuple[List[str], Optional[Dict], List[Dict]]:
    """
    Execute Observe → Analyze → Reason → Decide → Act → Report.
    Reasoning engine is selected based on provided credentials.
    """
    # Select reasoning engine
    if foundry_endpoint and foundry_api_key:
        agents["reasoner"] = FoundryReasoningEngine(
            endpoint=foundry_endpoint,
            api_key=foundry_api_key,
            deployment=foundry_deployment or config.AZURE_FOUNDRY_DEPLOYMENT,
        )
    elif use_ai and openai_key:
        agents["reasoner"] = ReasoningEngine(use_ai=True, api_key=openai_key, model=config.OPENAI_MODEL)
    else:
        agents["reasoner"] = ReasoningEngine(use_ai=False)

    all_logs = agents["observer"].read_all_logs()
    if not all_logs:
        return [], None, []

    issues = agents["analyzer"].analyze_logs(all_logs)
    if not issues:
        return all_logs, None, []

    issues = agents["reasoner"].analyze_all_issues(issues, all_logs)
    issues = agents["decision"].decide_all(issues)
    issues = agents["actuator"].execute_all_actions(issues)

    reports = agents["reporter"].generate_all_reports(issues)
    summary = agents["reporter"].generate_summary_report(issues)

    return all_logs, summary, reports


# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    .metric-card {
        background: #1e1e2e;
        border-radius: 10px;
        padding: 16px;
        text-align: center;
    }
    .badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.78em;
        font-weight: 700;
        color: #fff;
    }
    .badge-critical { background: #FF3B3B; }
    .badge-error    { background: #FF8C00; }
    .badge-warning  { background: #c9a000; color: #000; }
    .badge-info     { background: #32CD32; color: #000; }
    .agent-loop     { font-size: 0.85em; color: #aaa; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 🤖 AI DevOps Agent")
    st.markdown("**v1.0.0** · Simulation Mode")
    st.divider()

    st.subheader("⚙️ Configuration")
    simulation_mode = st.toggle("Simulation Mode", value=True)

    reasoning_choice = st.radio(
        "Reasoning Engine",
        ["Rule-Based (free)", "OpenAI", "Azure AI Foundry"],
        index=0,
        help="Rule-Based is free. OpenAI and Foundry require credentials.",
    )

    openai_key_input   = None
    foundry_endpoint   = None
    foundry_api_key    = None
    foundry_deployment = None

    if reasoning_choice == "OpenAI":
        openai_key_input = st.text_input(
            "OpenAI API Key", type="password",
            value=config.OPENAI_API_KEY,
            placeholder="sk-…",
        )
        if openai_key_input:
            st.success("OpenAI key loaded ✓")

    elif reasoning_choice == "Azure AI Foundry":
        st.markdown("**Azure AI Foundry credentials**")
        foundry_endpoint   = st.text_input("Foundry Endpoint",   value=config.AZURE_FOUNDRY_ENDPOINT,  placeholder="https://<hub>.openai.azure.com/")
        foundry_api_key    = st.text_input("Foundry API Key",    value=config.AZURE_FOUNDRY_API_KEY,   type="password")
        foundry_deployment = st.text_input("Deployment Name",    value=config.AZURE_FOUNDRY_DEPLOYMENT, placeholder="gpt-4o-mini")
        if foundry_endpoint and foundry_api_key:
            st.success("Foundry credentials loaded ✓")
        else:
            st.warning("Enter endpoint + API key to enable Foundry reasoning.")

    use_ai_toggle = reasoning_choice == "OpenAI"

    st.divider()
    st.subheader("📁 Log File")
    st.code(LOG_FILE, language=None)

    stats = agents["observer"].get_log_stats()
    st.metric("Lines monitored", stats.get("total_lines", 0))
    st.metric("File size", f"{stats.get('file_size_bytes', 0):,} B")

    st.divider()
    st.markdown(
        "<div class='agent-loop'>"
        "👁️ Observe → 🔍 Analyze → 🧠 Reason<br>"
        "⚖️ Decide → ⚡ Act → 📋 Report"
        "</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------
st.title("🤖 AI DevOps Autonomous Incident Response Agent")
st.caption(
    "Automated log monitoring · root-cause analysis · self-healing remediation"
)
st.divider()

# ---------------------------------------------------------------------------
# KPI row — always visible
# ---------------------------------------------------------------------------
all_logs_now   = agents["observer"].read_all_logs()
preview_issues = agents["analyzer"].analyze_logs(all_logs_now) if all_logs_now else []
kpi_summary    = agents["analyzer"].get_issue_summary()

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("Log Lines",    len(all_logs_now))
kpi2.metric("Critical",     kpi_summary.get("CRITICAL", 0))
kpi3.metric("Errors",       kpi_summary.get("ERROR", 0))
kpi4.metric("Warnings",     kpi_summary.get("WARNING", 0))

st.divider()

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_logs, tab_analysis, tab_actions, tab_reports = st.tabs([
    "📋 Log Monitor",
    "🔍 Analysis",
    "⚡ Actions",
    "📊 Reports",
])


# ============================================================
# TAB 1 — LOG MONITOR
# ============================================================
with tab_logs:
    st.subheader("Real-Time Log Monitor")

    ctrl1, ctrl2 = st.columns([4, 1])
    with ctrl2:
        tail_n       = st.slider("Lines", 10, 200, 50, key="tail_slider")
        auto_refresh = st.checkbox("Auto-refresh (5 s)")
    with ctrl1:
        if st.button("🔄 Refresh", key="refresh_logs"):
            st.rerun()

    lines_to_show = all_logs_now[-tail_n:] if all_logs_now else []

    if lines_to_show:
        coloured_lines = []
        for line in lines_to_show:
            u = line.upper()
            if any(k in u for k in ("CRITICAL", "FATAL")):
                coloured_lines.append(f"🔴  {line}")
            elif any(k in u for k in ("ERROR", "FAILED", "FAILURE", "REFUSED")):
                coloured_lines.append(f"🟠  {line}")
            elif any(k in u for k in ("WARNING", "WARN", "TIMEOUT", "DEGRADED")):
                coloured_lines.append(f"🟡  {line}")
            else:
                coloured_lines.append(f"🟢  {line}")

        st.code("\n".join(coloured_lines), language=None)
    else:
        st.info("No log entries found. Ensure `logs/app.log` exists.")

    if auto_refresh:
        time.sleep(5)
        st.rerun()


# ============================================================
# TAB 2 — ANALYSIS
# ============================================================
with tab_analysis:
    st.subheader("Detected Issues & Root-Cause Analysis")

    run_col, _ = st.columns([2, 5])
    with run_col:
        run_clicked = st.button(
            "🤖 Run Agent Analysis", type="primary", key="run_analysis"
        )

    if run_clicked:
        with st.spinner("Running Observe → Analyze → Reason → Decide → Act …"):
            logs, summary, reports = run_pipeline(
                use_ai=use_ai_toggle,
                openai_key=openai_key_input,
                foundry_endpoint=foundry_endpoint,
                foundry_api_key=foundry_api_key,
                foundry_deployment=foundry_deployment,
            )
        st.session_state["logs"]    = logs
        st.session_state["summary"] = summary
        st.session_state["reports"] = reports
        st.session_state["ran"]     = True

        if summary:
            st.success(
                f"Analysis complete — **{summary['total_issues']}** issue(s) found, "
                f"**{summary['resolved_issues']}** resolved."
            )
        else:
            st.success("✅ No actionable issues detected — system appears healthy.")

    if st.session_state.get("ran") and st.session_state.get("reports"):
        reports  = st.session_state["reports"]
        summary  = st.session_state["summary"]

        # Mini KPIs
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Issues",    summary["total_issues"])
        m2.metric("Resolved",        summary["resolved_issues"])
        m3.metric("Open",            summary["open_issues"])
        m4.metric("Resolution Rate", summary["resolution_rate"])

        st.divider()
        st.markdown("#### Issue Details")

        for report in reports:
            sev   = report["severity"]
            icon  = severity_icon(sev)
            label = (
                f"{icon} **{report['incident_id']}** | "
                f"`{report['issue']['type']}` | "
                f"Line {report['issue']['line_number']}"
            )
            with st.expander(label, expanded=(sev in ("CRITICAL", "ERROR"))):
                left, right = st.columns(2)
                with left:
                    st.markdown(f"**Incident ID:** `{report['incident_id']}`")
                    st.markdown(f"**Severity:** `{sev}`")
                    st.markdown(f"**Issue Type:** `{report['issue']['type']}`")
                    st.markdown(f"**Timestamp:** {report['issue']['timestamp']}")
                with right:
                    st.markdown(f"**Status:** `{report['status']}`")
                    st.markdown(f"**Reasoning:** {report['reasoning_method']}")
                    st.markdown(f"**Action:** `{report['action_taken']}`")

                st.markdown("**Raw Log Entry:**")
                st.code(report["issue"]["raw_log"], language=None)

                st.markdown("**Root-Cause Analysis:**")
                st.info(f"🧠 {report['root_cause']}")

                # Show Foundry multi-step reasoning if available
                steps = report.get("reasoning_steps")
                if steps:
                    with st.expander("🔬 Foundry Multi-Step Reasoning", expanded=False):
                        st.markdown(f"**Step 1 — Context:** {steps.get('step1_context', '')}")
                        st.markdown(f"**Step 2 — Root Cause:** {steps.get('step2_root_cause', '')}")
                        opts = steps.get('step3_options', [])
                        if opts:
                            st.markdown("**Step 3 — Options:**")
                            for opt in opts:
                                st.markdown(f"- {opt}")
                        st.markdown(f"**Step 4 — Recommendation:** {steps.get('step4_recommendation', '')}")
                        st.markdown(f"**Confidence:** `{report.get('confidence', 'N/A')}`")

    elif not st.session_state.get("ran"):
        st.info("Click **Run Agent Analysis** to start the pipeline.")


# ============================================================
# TAB 3 — ACTIONS
# ============================================================
with tab_actions:
    st.subheader("Remediation Actions Taken")

    if st.session_state.get("ran") and st.session_state.get("reports"):
        reports = st.session_state["reports"]

        rows = []
        for r in reports:
            rows.append({
                "Incident":    r["incident_id"],
                "Severity":    r["severity"],
                "Issue Type":  r["issue"]["type"],
                "Action":      r["action_taken"],
                "Result":      (r["action_result"] or "")[:90]
                               + ("…" if len(r.get("action_result") or "") > 90 else ""),
                "Status":      r["status"],
            })

        df = pd.DataFrame(rows)

        # Colour the Severity column
        def _colour_severity(val: str) -> str:
            palette = {
                "CRITICAL": "background-color:#ffcccc",
                "ERROR":    "background-color:#ffe0cc",
                "WARNING":  "background-color:#fffacc",
                "INFO":     "background-color:#ccffcc",
            }
            return palette.get(val, "")

        styled = df.style.map(_colour_severity, subset=["Severity"])
        st.dataframe(styled, use_container_width=True, hide_index=True)

        # Action distribution chart
        st.divider()
        st.markdown("#### Action Distribution")
        action_counts: Dict[str, int] = {}
        for r in rows:
            a = r["Action"]
            action_counts[a] = action_counts.get(a, 0) + 1

        chart_df = (
            pd.DataFrame(
                list(action_counts.items()),
                columns=["Action", "Count"],
            ).set_index("Action")
        )
        st.bar_chart(chart_df)

    else:
        st.info("Run the agent analysis first to see remediation actions.")


# ============================================================
# TAB 4 — REPORTS
# ============================================================
with tab_reports:
    st.subheader("Incident Report Export")

    if st.session_state.get("ran") and st.session_state.get("reports"):
        reports = st.session_state["reports"]
        summary = st.session_state["summary"]

        # Executive Summary
        st.markdown("#### Executive Summary")
        st.json(summary)

        st.divider()

        # Download button
        full_report_payload = {
            "summary":     summary,
            "incidents":   reports,
            "exported_at": datetime.now().isoformat(),
        }
        report_json_str = json.dumps(full_report_payload, indent=2, default=str)

        st.download_button(
            label="📥 Download Full Report (JSON)",
            data=report_json_str,
            file_name=f"incident_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
        )

        st.divider()
        st.markdown("#### Individual Incident Reports")

        for i, report in enumerate(reports, start=1):
            with st.expander(f"Incident {i}: {report['incident_id']}"):
                st.json(report)

    else:
        st.info("Run the agent analysis first to generate exportable reports.")


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.divider()
st.markdown(
    "<div style='text-align:center;color:#666;font-size:0.82em;'>"
    "AI DevOps Autonomous Incident Response Agent v1.0.0 &nbsp;|&nbsp; "
    "Observe → Analyze → Reason → Decide → Act → Report"
    "</div>",
    unsafe_allow_html=True,
)
