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


def _friendly_key_error(exc: Exception) -> str:
    """Turn an OpenAI auth failure into something a human can act on."""
    text = str(exc)
    lowered = text.lower()
    if "401" in text or "invalid_api_key" in lowered or "incorrect api key" in lowered:
        return (
            "**This key is rejected by OpenAI (401).**\n\n"
            "The key is wrong, truncated, or was deleted. Fix it:\n\n"
            "1. Open https://platform.openai.com/api-keys\n"
            "2. Click **Create new secret key** (name it `DA Sumit`)\n"
            "3. Click the **📋 copy icon** — the full key starts with `sk-proj-` "
            "or `sk-` and is ~50–160 characters\n"
            "4. Paste it here. Never copy the short `sk-proj-…abcd` text shown in "
            "the key table — that is a truncated preview.\n\n"
            "A ChatGPT Plus subscription does **not** include API access."
        )
    if "api key not valid" in lowered or "api_key_invalid" in lowered or "invalid api key" in lowered:
        return (
            "**Google rejected that API key (400).**\n\n"
            "Fix it:\n"
            "1. Open https://aistudio.google.com/apikey\n"
            "2. Click **Create API key** and copy the whole value — it starts "
            "with `AIza`\n"
            "3. Streamlit → **Settings → Secrets** → set:\n\n"
            "```toml\nGEMINI_API_KEY = \"AIza...\"\n```\n\n"
            "Gemini's free tier needs no credit card."
        )
    if "404" in text or "model_not_found" in lowered or "has been deprecated" in lowered:
        return (
            "**That model has been retired by OpenAI (404).**\n\n"
            "OpenAI shut down the GPT-4 era models (`gpt-4-turbo`, `gpt-4`, "
            "`gpt-3.5-turbo`, `o1`, `o3-mini`, `o4-mini`) on 23 Oct 2026, and the "
            "GPT-4o family follows on 14 Jan 2027.\n\n"
            "Click **🔄 Refresh models** in the sidebar and pick a current model "
            "(e.g. `gpt-6-luna`, `gpt-6.1-terra`). Sumit07 also retries "
            "automatically, so a stale choice will not stop a request."
        )
    if "400" in text or "invalid_argument" in lowered or "bad request" in lowered:
        detail = text.strip()
        if len(detail) > 700:
            detail = detail[:700] + "…"
        return (
            "**The provider rejected the request (400).**\n\n"
            f"```\n{detail}\n```\n\n"
            "Most common cause: the selected model cannot use tools. Set "
            "**Model → `gemini-3.8-flash`** (or `gemini-3.6-flash`) and retry. "
            "Lite models have limited function-calling support."
        )
    if "429" in text or "insufficient_quota" in lowered or "quota" in lowered or "credits" in lowered:
        return (
            "**No credits / quota exhausted (429).**\n\n"
            "**If you're on Google Gemini (free tier):** you've hit the free "
            "request limit for this model. Wait a few minutes, or pick a lighter "
            "model in the sidebar (e.g. `gemini-3.5-flash-lite`). Free limits reset "
            "daily.\n\n"
            "**If you're on OpenAI:** the account balance is $0. The API is "
            "pay-as-you-go and is **not** included with ChatGPT Plus:\n"
            "1. https://platform.openai.com/settings/organization/billing/overview\n"
            "2. **Add payment details** → buy the minimum prepaid amount (~$5)\n"
            "3. Resend your request — no restart needed\n\n"
            "Tip: switch to Gemini's free tier by setting `GEMINI_API_KEY` in "
            "Streamlit secrets."
        )
    if "rate" in lowered and "limit" in lowered:
        return "**Rate limited by OpenAI.** Wait ~30 seconds and try again."
    if "connect" in lowered or "timeout" in lowered or "network" in lowered:
        return "**Network problem reaching OpenAI.** Check your internet connection and retry."
    return f"Key test failed: {text}"


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
    if "key_ok" not in ss:
        ss.key_ok = None
    if "key_error" not in ss:
        ss.key_error = ""
    if "model_options" not in ss:
        ss.model_options = []
    if "models_loaded" not in ss:
        ss.models_loaded = False
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
    env_key = (
        _secret("GEMINI_API_KEY")
        or _secret("GOOGLE_API_KEY")
        or _secret("OPENAI_API_KEY")
        or config.get_api_key()
    )
    typed_key = st.text_input(
        "API key",
        value=st.session_state.api_key,
        type="password",
        help=(
            "Google Gemini keys start with AIza (free tier) · OpenAI keys start "
            "with sk-. Leave blank to use the key from Streamlit secrets or .env."
        ),
    )
    st.session_state.api_key = (typed_key or "").strip()
    effective_key = (st.session_state.api_key or env_key or "").strip()

    if effective_key:
        if st.button("🔌 Test key", use_container_width=True):
            try:
                config.get_client(effective_key).models.list()
                st.session_state.key_ok = True
                st.session_state.key_error = ""
            except Exception as exc:  # noqa: BLE001
                st.session_state.key_ok = False
                st.session_state.key_error = _friendly_key_error(exc)
        if st.session_state.key_ok:
            st.success("Key verified — ready to go", icon="✅")
        elif st.session_state.key_error:
            st.error(st.session_state.key_error)
        else:
            st.info("Key saved. Click **Test key** to verify it.", icon="🔑")
    else:
        st.warning("Add an OpenAI API key to start.", icon="⚠️")

    # Pull the live model list so retired models (gpt-4-turbo et al.) never
    # appear in the dropdown.
    if effective_key and not st.session_state.models_loaded:
        try:
            with st.spinner("Loading available models…"):
                found = config.list_chat_models(effective_key)
        except Exception:  # noqa: BLE001 - fall back to the static list
            found = []
        if found:
            st.session_state.model_options = found
            st.session_state.models_loaded = True

    models = st.session_state.model_options or config.preferred_models(effective_key)
    if st.session_state.model not in models:
        st.session_state.model = models[0]
    st.session_state.model = st.selectbox(
        "Model", models, index=models.index(st.session_state.model)
    )
    if st.button("🔄 Refresh models", use_container_width=True):
        st.session_state.models_loaded = False
        st.session_state.model_options = []
        st.rerun()

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
                        content = str(event.get("content", ""))
                        lowered = content.lower()
                        if any(hit in lowered for hit in ("401", "invalid_api_key", "404", "model_not_found", "has been deprecated", "429", "quota", "credits", "400", "invalid_argument", "bad request", "api key not valid")):
                            content = _friendly_key_error(Exception(content))
                        final_text = f"⚠️ {content}"
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
