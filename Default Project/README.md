# DA Sumit — Autonomous AI Data Analyst

**DA Sumit** is an agentic AI data analyst (powered by the **Sumit07** agent).
Upload a **CSV or Excel** file, then chat with it in plain English. It inspects,
cleans, analyses, charts, builds dashboards and extracts actionable insights
from your data.

It is **scoped to data analysis only**: it has no browsing, no general coding,
no unrelated chat. Its entire capability set is the 14 data-analyst tools listed
below, so it literally cannot do anything else.

```
Upload CSV/Excel  →  Ask in plain English  →  Sumit07 plans + uses tools  →  Answer + charts + dashboard
```

---

## Quick start (Windows)

**Easiest:** double-click **`start.bat`**. It runs setup the first time, starts
the server in the **background**, waits until it is ready, then opens your
browser at <http://127.0.0.1:8501>.

- You can safely **close the black window** — the app keeps running.
- To stop it, double-click **`stop.bat`**.

**Or from PowerShell:**

```powershell
# 1. One-time setup (installs Python if needed, creates .venv, installs deps)
.\setup.ps1

# 2. Add your OpenAI key
notepad .env        # set OPENAI_API_KEY=sk-...

# 3. Run it
.\run.ps1
```

> **"running scripts is disabled on this system"?** Windows is blocking the
> `.ps1` files. Use `start.bat` instead, or run:
> `powershell -ExecutionPolicy Bypass -File .\run.ps1`

> If `setup.ps1` had to install Python, close the window, open a **new**
> PowerShell, and run it again.

### Manual setup (any OS)

```bash
python -m venv .venv
# Windows:  .\.venv\Scripts\Activate.ps1
# macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # then edit .env and add OPENAI_API_KEY
streamlit run app.py
```

---

## How to use it

1. **Upload** one or more CSV/Excel files in the sidebar.
2. Pick the **active dataset** (if you loaded several).
3. **Chat** in the Chat tab. Examples:

| Goal | What to type |
|------|--------------|
| Cleaning | "Remove duplicate rows and fill missing numeric values with the median" |
| Null handling | "Drop columns that are more than 50% empty" |
| Analysis | "What is total revenue by region and category?" |
| Trends | "Show monthly revenue as a line chart" |
| Insights | "Give me 5 actionable insights and the biggest risks in this data" |
| Dashboard | "Build a dashboard of revenue by region, sales trend, and the correlation heatmap" |
| Export | "Export the cleaned dataset as Excel" |

4. Open the **Charts & Dashboard** tab to review charts and download a
   standalone `dashboard.html` report.
5. Open the **Datasets** tab to preview data and download any dataset as CSV.

---

## What Sumit07 can do (its only tools)

| Tool | Purpose |
|------|---------|
| `list_datasets` | Show loaded datasets |
| `inspect_dataset` | Shape, dtypes, nulls, uniques, head |
| `profile_dataset` | Statistical profile + correlations + missingness |
| `clean_dataset` | Drop duplicates/nulls, fill missing, fix dtypes, strip text, rename/drop columns, replace values, clip outliers |
| `reset_dataset` | Undo all cleaning (restore original) |
| `query_dataset` | Filter rows with a pandas expression |
| `aggregate` | Group-by + metrics (mean/sum/count/…/nunique) |
| `value_counts` | Frequency distributions |
| `correlation` | Correlation matrix + strongest pairs |
| `detect_outliers` | IQR / z-score outlier detection |
| `visualize` | bar, line, scatter, histogram, box, violin, pie, countplot, heatmap, area |
| `generate_insights` | Compact analytical digest for insight writing |
| `build_dashboard` | Assemble charts + insights into an HTML dashboard |
| `export_dataset` | Write CSV/XLSX to `outputs/` |

**Scope enforcement** happens in two layers:
1. A strict system prompt that defines Sumit07 as a data analyst and nothing else.
2. A fast "scope guard" classifier that refuses off-topic requests before they
   reach the agent (disable with `SCOPE_GUARD=false` in `.env`).

---

## Project structure

```
.
├── app.py                 # Streamlit UI (upload, chat, charts, dashboard)
├── launch.py              # waits for the server, then opens the browser
├── start.bat / setup.bat  # one-click launchers (no PowerShell policy issues)
├── sumit07/
│   ├── __init__.py
│   ├── config.py          # env config (model, paths, flags)
│   ├── prompts.py         # system prompt + scope guard + refusal
│   ├── store.py           # DatasetStore & ChartStore (session state)
│   ├── tools.py           # the 14 data-analyst tools (schemas + impls)
│   ├── agent.py           # Sumit07Agent tool-calling loop
│   └── report.py          # HTML dashboard builder
├── .streamlit/config.toml # disables the first-run prompt, pins the port
├── data/sample_sales.csv  # demo data (has nulls + duplicates on purpose)
├── requirements.txt
├── run.ps1 / setup.ps1
└── .env.example
```

---

## Configuration (`.env`)

| Variable | Default | Meaning |
|----------|---------|---------|
| `OPENAI_API_KEY` | – | Your OpenAI key (**required**) |
| `OPENAI_MODEL` | `gpt-4o-mini` | Model to use (gpt-4o gives better analysis) |
| `MAX_AGENT_STEPS` | `12` | Max tool-calling rounds per request |
| `SCOPE_GUARD` | `true` | Refuse non-data-analysis requests |
| `OUTPUT_DIR` | `outputs` | Where dashboards/exports are written |

---

## Try it with the sample data

1. Upload `data/sample_sales.csv`.
2. Ask: **"Inspect the data and tell me about data quality."**
3. Ask: **"Clean it — remove duplicates, fix missing values, then show total revenue by region as a bar chart."**
4. Ask: **"Give me actionable insights and build a dashboard."**

---

## Troubleshooting

**"This site can't be reached" / "localhost refused to connect"**
- Double-click **`start.bat`** and wait ~8 seconds. It starts the server in the
  background and opens <http://127.0.0.1:8501>.
- Use **`127.0.0.1`** (not `localhost`) — on some Windows setups `localhost`
  resolves to IPv6 while the server listens on IPv4.
- The server runs in the background, so closing the black window is safe.
  If the page still won't load, check `outputs\server.log`.

**"running scripts is disabled on this system"**
- Windows is blocking `.ps1` files. Use **`start.bat`** / **`setup.bat`**, or run
  `powershell -ExecutionPolicy Bypass -File .\run.ps1`.

**Blank page or stuck spinner**
- Refresh the tab (Ctrl+F5). If it persists, stop the app (Ctrl+C in the black
  window) and run `start.bat` again.

**Port 8501 already in use**
- Another copy is already running — just open <http://localhost:8501>. To use a
  different port, edit `port` in `.streamlit/config.toml`.

**"No OpenAI API key found"**
- Open `.env` and set `OPENAI_API_KEY=sk-...`, or paste the key into the sidebar.

---

## Notes & limitations

- Only a compact statistical digest of your data is sent to the model — not the
  full file — but avoid uploading sensitive data unless you accept that.
- Large files work but very wide datasets (>200 columns) may be trimmed in
  summaries.
- Charts are rendered with matplotlib/seaborn and saved as PNG inside the
  dashboard HTML (fully self-contained, no internet needed to view).
