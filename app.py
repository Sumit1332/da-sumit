"""Sumit07 - Streamlit app entry point.

Upload a CSV/Excel file, then chat with Sumit07 to clean, analyse, visualise,
dashboard and extract insights from it.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from sumit07 import AGENT_NAME, APP_NAME, APP_TAGLINE, config
from sumit07.agent import Sumit07Agent
from sumit07.report import build_dashboard_html
from sumit07.store import ChartStore, DatasetStore
from sumit07.tools import DataAnalystTools

st.set_page_config(
    page_title=f"{APP_NAME} · {APP_TAGLINE}",
    page_icon="📊",
    layout="wide",
)

AVATAR = "📊"


def _secret(name: str, default: str = "") -> str:
    """Read a secret from Streamlit secrets or the environment."""
    try:
        value = st.secrets.get(name, default)
    except Exception:  # noqa: BLE001 - no secrets file locally
        value = default
    return value or os.getenv(name, default) or default


# --------------------------------------------------------------------------- #
# Session state
# --------------------------------------------------------------------------- #
def init_state() -> None:
    ss = st.session_state
    if "datasets" not in ss:
        ss.datasets = DatasetStore()
    if "charts" not in ss:
        ss.charts = ChartStore()
    if "messages" not in ss:
        ss.messages = []
    if "loaded_files" not in ss:
        ss.loaded_files = set()
    if "api_key" not in ss:
        ss.api_key = ""
    if "model" not in ss:
        ss.model = config.DEFAULT_MODEL
    if "dashboard_html" not in ss:
        ss.dashboard_html = None
    if "authed" not in ss:
        ss.authed = False


def _short_args(args: dict) -> str:
    try:
        text = json.dumps(args, default=str)
    except Exception:  # noqa: BLE001
        text = str(args)
    return text if len(text) <= 160 else text[:157] + "…"


init_state()
store: DatasetStore = st.session_state.datasets


# --------------------------------------------------------------------------- #
# Optional password gate (strongly recommended for public deployments)
# Set APP_PASSWORD in Streamlit secrets to enable it.
# --------------------------------------------------------------------------- #
APP_PASSWORD = _secret("APP_PASSWORD")
if APP_PASSWORD and not st.session_state.get("authed"):
    st.title(f"🔒 {APP_NAME}")
    st.caption(f"{APP_TAGLINE} — password protected")
    entered = st.text_input("Password", type="password")
    if st.button("Enter", type="primary"):
        if entered == APP_PASSWORD:
            st.session_state.authed = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    st.stop()


# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.title(f"📊 {APP_NAME}")
    st.caption(APP_TAGLINE)

    st.subheader("🔑 Model access")
    env_key = _secret("OPENAI_API_KEY") or config.get_api_key()
    typed_key = st.text_input(
        "OpenAI API key",
        value=st.session_state.api_key,
        type="password",
        help="Leave blank to use OPENAI_API_KEY from your .env file.",
    )
    st.session_state.api_key = typed_key
    effective_key = typed_key or env_key
    if effective_key:
        st.success("API key ready", icon="✅")
        if st.button("🔌 Test key", use_container_width=True):
            try:
                config.get_client(effective_key).models.list()
                st.success("Key works — you're ready to go!")
            except Exception as exc:  # noqa: BLE001
                st.error(f"Key test failed: {exc}")
    else:
        st.warning("Add an OpenAI API key to start.", icon="⚠️")

    models = config.AVAILABLE_MODELS
    default_index = models.index(st.session_state.model) if st.session_state.model in models else 0
    st.session_state.model = st.selectbox("Model", models, index=default_index)

    st.divider()
    st.subheader("📁 Upload data")
    uploaded = st.file_uploader(
        "CSV or Excel files",
        type=["csv", "xlsx", "xls"],
        accept_multiple_files=True,
        help="Everything stays on this machine; only summaries are sent to the model.",
    )
    if uploaded:
        for file in uploaded:
            fid = f"{file.name}:{file.size}"
            if fid in st.session_state.loaded_files:
                continue
            try:
                if file.name.lower().endswith(".csv"):
                    df = pd.read_csv(file)
                else:
                    df = pd.read_excel(file)
                name = store.add(Path(file.name).stem, df)
                store.set_active(name)
                st.session_state.loaded_files.add(fid)
                st.success(f"Loaded '{name}' ({df.shape[0]}×{df.shape[1]})")
            except Exception as exc:  # noqa: BLE001
                st.error(f"Could not read {file.name}: {exc}")

    if store.names():
        st.divider()
        st.subheader("🗂 Datasets")
        names = store.names()
        active_index = names.index(store.active) if store.active in names else 0
        chosen = st.selectbox("Active dataset", names, index=active_index)
        store.set_active(chosen)
        if st.button("♻️ Reset active dataset to original", use_container_width=True):
            store.reset(chosen)
            st.success(f"Restored '{chosen}' to its original state.")

    st.divider()
    if st.button("🧹 Clear conversation & charts", use_container_width=True):
        st.session_state.messages = []
        st.session_state.charts.clear()
        st.session_state.dashboard_html = None
        st.rerun()

    with st.expander(f"ℹ️ What can {APP_NAME} do?"):
        st.markdown(
            "- Inspect & profile any dataset\n"
            "- Clean: nulls, duplicates, dtypes, outliers, text\n"
            "- Filter, group and aggregate\n"
            "- Correlations & outlier detection\n"
            "- Charts: bar, line, scatter, histogram, box, pie, heatmap…\n"
            "- Build HTML dashboards\n"
            "- Actionable insights & exports"
        )


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
st.title(f"{APP_NAME} — {APP_TAGLINE}")
st.caption(f"Upload a CSV/Excel file, then tell {AGENT_NAME} what you need.")

tab_chat, tab_data, tab_charts = st.tabs(["💬 Chat", "📋 Datasets", "📈 Charts & Dashboard"])


# ---- Chat ------------------------------------------------------------------
with tab_chat:
    if not store.names():
        st.info("👈 Upload a CSV or Excel file from the sidebar to get started.", icon="📁")

    for message in st.session_state.messages:
        with st.chat_message(message["role"], avatar=AVATAR if message["role"] == "assistant" else None):
            st.markdown(message.get("content") or "_(no response)_")
            for chart in message.get("charts", []):
                st.image(chart["png"], caption=chart["title"], use_container_width=True)

    prompt = st.chat_input("Ask Sumit07… e.g. 'Clean the data, then show revenue by region as a bar chart'")

    if prompt:
        if not effective_key:
            st.error("Please provide an OpenAI API key in the sidebar.")
        else:
            history = [
                {"role": m["role"], "content": m.get("content", "")}
                for m in st.session_state.messages
                if m.get("content")
            ]
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            tools = DataAnalystTools(store, st.session_state.charts)
            try:
                client = config.get_client(effective_key)
                agent = Sumit07Agent(tools, client=client, model=st.session_state.model)
            except Exception as exc:  # noqa: BLE001
                st.error(str(exc))
                st.stop()

            start_index = len(st.session_state.charts.charts)
            final_text = ""
            with st.chat_message("assistant", avatar=AVATAR):
                status = st.status(f"{AGENT_NAME} is working…", expanded=True)
                for event in agent.run(prompt, history):
                    if event["type"] == "tool_call":
                        status.write(f"🔧 `{event['name']}`  {_short_args(event.get('args', {}))}")
                    elif event["type"] == "tool_result":
                        content = event.get("content", "")
                        flag = "⚠️" if '"error"' in content else "✅"
                        status.write(f"{flag} `{event['name']}` completed")
                    elif event["type"] == "final":
                        final_text = event["content"]
                    elif event["type"] == "error":
                        final_text = f"⚠️ {event['content']}"
                status.update(label=f"{AGENT_NAME} finished", state="complete", expanded=False)

                st.markdown(final_text or "_(no response)_")
                new_charts = st.session_state.charts.charts[start_index:]
                for chart in new_charts:
                    st.image(chart.png, caption=chart.title, use_container_width=True)

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": final_text or "_(no response)_",
                    "charts": [{"title": c.title, "png": c.png} for c in new_charts],
                }
            )


# ---- Datasets --------------------------------------------------------------
with tab_data:
    if not store.names():
        st.info("No datasets loaded yet.")
    for name in store.names():
        _, df = store.resolve(name)
        with st.expander(f"**{name}**  —  {df.shape[0]} rows × {df.shape[1]} columns", expanded=(name == store.active)):
            c1, c2, c3 = st.columns(3)
            c1.metric("Rows", f"{df.shape[0]:,}")
            c2.metric("Columns", f"{df.shape[1]:,}")
            c3.metric("Missing cells", f"{int(df.isna().sum().sum()):,}")

            st.markdown("**Columns**")
            info = pd.DataFrame(
                {
                    "dtype": df.dtypes.astype(str),
                    "non-null": df.notna().sum(),
                    "nulls": df.isna().sum(),
                    "null %": (df.isna().mean() * 100).round(2),
                    "unique": df.nunique(dropna=True),
                }
            )
            st.dataframe(info, use_container_width=True)

            st.markdown("**Preview**")
            st.dataframe(df.head(50), use_container_width=True)

            st.download_button(
                f"⬇️ Download '{name}' as CSV",
                df.to_csv(index=False).encode("utf-8"),
                file_name=f"{name}.csv",
                mime="text/csv",
                key=f"dl_{name}",
            )


# ---- Charts & dashboard ----------------------------------------------------
with tab_charts:
    charts = st.session_state.charts.charts
    if not charts:
        st.info("No charts yet — ask Sumit07 to visualise something in the Chat tab.")
    else:
        st.subheader(f"Charts ({len(charts)})")
        for i, chart in enumerate(charts):
            st.image(chart.png, caption=f"[{i}] {chart.title}", use_container_width=True)

        st.divider()
        st.subheader("🧾 Build a dashboard")
        dash_title = st.text_input("Dashboard title", f"{APP_NAME} Dashboard")
        insights_text = st.text_area(
            "Optional insights to embed",
            placeholder="Paste or write the key insights to show at the top of the dashboard.",
            height=120,
        )
        if st.button("Build dashboard", type="primary"):
            st.session_state.dashboard_html = build_dashboard_html(dash_title, charts, insights_text)

        if st.session_state.dashboard_html:
            st.download_button(
                "⬇️ Download dashboard.html",
                st.session_state.dashboard_html.encode("utf-8"),
                file_name="sumit07_dashboard.html",
                mime="text/html",
            )
            st.success("Dashboard built. Download it above, or open it from the outputs/ folder.")

    outputs_dir = config.OUTPUT_DIR
    if os.path.isdir(outputs_dir) and os.listdir(outputs_dir):
        with st.expander("📂 Generated files (outputs/)"):
            for fname in sorted(os.listdir(outputs_dir)):
                st.write(f"• `{os.path.join(outputs_dir, fname)}`")
