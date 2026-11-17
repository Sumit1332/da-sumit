"""The data-analyst toolset for Sumit07.

Every capability Sumit07 has is defined here. Because these are the ONLY tools
exposed to the model, the agent is physically limited to data-analyst work.

`DataAnalystTools` binds to a :class:`DatasetStore` and :class:`ChartStore`
(both kept in the Streamlit session) and exposes:
  - ``schemas()``  -> OpenAI tool schemas
  - ``dispatch(name, args)`` -> JSON string result
"""

from __future__ import annotations

import io
import json
import math
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import matplotlib

matplotlib.use("Agg")  # headless rendering

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import seaborn as sns  # noqa: E402

from . import config  # noqa: E402
from .report import build_dashboard_html  # noqa: E402
from .store import Chart, ChartStore, DatasetStore  # noqa: E402

sns.set_theme(style="whitegrid", palette="deep")
plt.rcParams["figure.autolayout"] = True


# --------------------------------------------------------------------------- #
# Serialization helpers
# --------------------------------------------------------------------------- #
def _scalar(value: Any) -> Any:
    """Convert a single pandas/numpy value into something JSON-safe."""
    if value is None:
        return None
    if isinstance(value, (str, bool)):
        return value
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        f = float(value)
        return None if math.isnan(f) or math.isinf(f) else f
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return str(value)


def _records(df: pd.DataFrame, limit: int = 50) -> List[Dict[str, Any]]:
    """Return at most ``limit`` rows as JSON-safe records."""
    head = df.head(limit)
    try:
        return json.loads(head.to_json(orient="records", date_format="iso"))
    except Exception:
        return json.loads(head.astype(str).to_json(orient="records"))


def _dumps(obj: Any) -> str:
    return json.dumps(obj, default=_scalar, ensure_ascii=False)


def _corr_pairs(corr: pd.DataFrame, top: int = 10) -> List[Dict[str, Any]]:
    cols = list(corr.columns)
    pairs: List[Dict[str, Any]] = []
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            v = corr.iloc[i, j]
            if pd.isna(v):
                continue
            pairs.append({"a": str(cols[i]), "b": str(cols[j]), "corr": round(float(v), 3)})
    pairs.sort(key=lambda p: abs(p["corr"]), reverse=True)
    return pairs[:top]


def _fig_to_png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


# --------------------------------------------------------------------------- #
# Tool schemas
# --------------------------------------------------------------------------- #
TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_datasets",
            "description": "List all datasets currently loaded in the session, with row/column counts and which one is active.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "inspect_dataset",
            "description": "Quick structural overview of a dataset: shape, per-column dtype, null counts/percentages, unique counts, sample values, duplicate row count and the first rows.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dataset": {"type": "string", "description": "Dataset name. Omit to use the active dataset."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "profile_dataset",
            "description": "Deep statistical profile: numeric describe(), categorical summaries, missingness table, duplicate count and the strongest correlations. Use this to understand data before deeper analysis.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dataset": {"type": "string", "description": "Dataset name. Omit for the active dataset."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "clean_dataset",
            "description": (
                "Apply an ordered list of cleaning operations to a dataset. Supports: "
                "drop_duplicates, drop_null_rows, drop_null_columns, fill_missing "
                "(strategies: mean/median/mode/ffill/bfill/constant/zero), strip_whitespace, "
                "lowercase, fix_dtypes (via mapping {col: dtype}), rename_columns (mapping "
                "{old: new}), drop_columns, replace_values, clip_outliers. Returns before/after "
                "metrics and a log of actions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "operations": {
                        "type": "array",
                        "description": "Ordered cleaning operations.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "op": {
                                    "type": "string",
                                    "enum": [
                                        "drop_duplicates",
                                        "drop_null_rows",
                                        "drop_null_columns",
                                        "fill_missing",
                                        "strip_whitespace",
                                        "lowercase",
                                        "fix_dtypes",
                                        "rename_columns",
                                        "drop_columns",
                                        "replace_values",
                                        "clip_outliers",
                                    ],
                                },
                                "columns": {"type": "array", "items": {"type": "string"}, "description": "Columns to target (default: all applicable)."},
                                "strategy": {"type": "string", "enum": ["mean", "median", "mode", "ffill", "bfill", "constant", "zero"]},
                                "value": {"description": "Value used by fill_missing with strategy=constant."},
                                "mapping": {"type": "object", "description": "Mapping for fix_dtypes ({col: dtype}) or replace_values ({col: {from: to}})."},
                                "method": {"type": "string", "enum": ["iqr", "zscore"], "description": "Method for clip_outliers."},
                                "threshold": {"type": "number", "description": "For drop_null_columns: max allowed null fraction (e.g. 0.5)."},
                            },
                            "required": ["op"],
                        },
                    },
                    "dataset": {"type": "string", "description": "Dataset to clean. Omit for the active dataset."},
                    "new_name": {"type": "string", "description": "If set, save the cleaned result as a new dataset instead of modifying in place."},
                    "in_place": {"type": "boolean", "description": "Modify the active dataset in place (default true)."},
                },
                "required": ["operations"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reset_dataset",
            "description": "Restore a dataset to its original, unmodified state (undo all cleaning).",
            "parameters": {
                "type": "object",
                "properties": {"dataset": {"type": "string", "description": "Dataset to reset. Omit for the active dataset."}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_dataset",
            "description": "Filter rows with a pandas query expression, e.g. \"region == 'North' and revenue > 1000\". Optionally save the result as a new dataset.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "pandas query string."},
                    "dataset": {"type": "string"},
                    "limit": {"type": "integer", "description": "Max rows to return (default 50)."},
                    "save_as": {"type": "string", "description": "Optional name to save the filtered result as a new dataset."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "aggregate",
            "description": "Group by one or more columns and compute metrics (mean/sum/count/min/max/median/std/nunique). Use this for totals, averages and breakdowns.",
            "parameters": {
                "type": "object",
                "properties": {
                    "group_by": {"type": "array", "items": {"type": "string"}, "description": "Column(s) to group by."},
                    "metrics": {
                        "type": "array",
                        "description": "Metrics to compute. If omitted, returns row counts per group.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "column": {"type": "string"},
                                "agg": {"type": "string", "enum": ["mean", "sum", "count", "min", "max", "median", "std", "nunique"]},
                            },
                            "required": ["column", "agg"],
                        },
                    },
                    "dataset": {"type": "string"},
                    "sort_by": {"type": "string", "description": "Column to sort the result by."},
                    "ascending": {"type": "boolean", "description": "Sort ascending (default false = descending)."},
                    "top_n": {"type": "integer", "description": "Return only the top N rows."},
                    "save_as": {"type": "string", "description": "Optional name to save the result as a new dataset."},
                },
                "required": ["group_by"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "value_counts",
            "description": "Frequency distribution of a categorical column (counts or normalized shares).",
            "parameters": {
                "type": "object",
                "properties": {
                    "column": {"type": "string"},
                    "dataset": {"type": "string"},
                    "top_n": {"type": "integer", "description": "Return the top N values (default 20)."},
                    "normalize": {"type": "boolean", "description": "Return proportions instead of counts."},
                },
                "required": ["column"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "correlation",
            "description": "Compute a correlation matrix for numeric columns and list the strongest relationships.",
            "parameters": {
                "type": "object",
                "properties": {
                    "columns": {"type": "array", "items": {"type": "string"}, "description": "Numeric columns to include (default: all numeric)."},
                    "dataset": {"type": "string"},
                    "method": {"type": "string", "enum": ["pearson", "spearman", "kendall"]},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "detect_outliers",
            "description": "Detect outliers in numeric columns using the IQR or z-score method.",
            "parameters": {
                "type": "object",
                "properties": {
                    "columns": {"type": "array", "items": {"type": "string"}},
                    "dataset": {"type": "string"},
                    "method": {"type": "string", "enum": ["iqr", "zscore"]},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "visualize",
            "description": "Create a chart and add it to the session dashboard. Chart types: bar, line, scatter, histogram, box, violin, pie, countplot, heatmap, area.",
            "parameters": {
                "type": "object",
                "properties": {
                    "chart_type": {"type": "string", "enum": ["bar", "line", "scatter", "histogram", "box", "violin", "pie", "countplot", "heatmap", "area"]},
                    "x": {"type": "string", "description": "Column for the x-axis / category."},
                    "y": {"type": "string", "description": "Numeric column for the y-axis (bar/line/scatter/box/area)."},
                    "hue": {"type": "string", "description": "Optional column to colour/segment by."},
                    "dataset": {"type": "string"},
                    "title": {"type": "string", "description": "Chart title."},
                    "agg": {"type": "string", "enum": ["mean", "sum", "count", "median", "min", "max"], "description": "Aggregation for bar charts with a y column (default sum)."},
                    "top_n": {"type": "integer", "description": "Limit to the top N categories (default 15)."},
                    "bins": {"type": "integer", "description": "Number of bins for histograms (default 30)."},
                },
                "required": ["chart_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_insights",
            "description": "Return a compact analytical digest (shape, missingness, numeric summary, top correlations, categorical breakdowns, outliers) that you use to write actionable insights.",
            "parameters": {
                "type": "object",
                "properties": {"dataset": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "build_dashboard",
            "description": "Assemble all (or selected) generated charts, plus an insights summary, into a standalone HTML dashboard file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Dashboard title."},
                    "insights": {"type": "string", "description": "Concise insights text to embed at the top of the dashboard."},
                    "chart_indices": {"type": "array", "items": {"type": "integer"}, "description": "Indices of charts to include (default: all)."},
                    "dataset": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "export_dataset",
            "description": "Export a dataset (e.g. a cleaned one) to CSV or Excel in the outputs/ folder.",
            "parameters": {
                "type": "object",
                "properties": {
                    "format": {"type": "string", "enum": ["csv", "xlsx"]},
                    "dataset": {"type": "string"},
                    "filename": {"type": "string", "description": "Optional output filename without extension."},
                },
            },
        },
    },
]


# --------------------------------------------------------------------------- #
# Tool implementations
# --------------------------------------------------------------------------- #
class DataAnalystTools:
    """Bound tool implementations operating on the session stores."""

    def __init__(
        self,
        datasets: DatasetStore,
        charts: ChartStore,
        output_dir: Optional[str] = None,
    ) -> None:
        self.datasets = datasets
        self.charts = charts
        self.output_dir = output_dir or config.OUTPUT_DIR
        os.makedirs(self.output_dir, exist_ok=True)

        self._tools = {
            "list_datasets": self.list_datasets,
            "inspect_dataset": self.inspect_dataset,
            "profile_dataset": self.profile_dataset,
            "clean_dataset": self.clean_dataset,
            "reset_dataset": self.reset_dataset,
            "query_dataset": self.query_dataset,
            "aggregate": self.aggregate,
            "value_counts": self.value_counts,
            "correlation": self.correlation,
            "detect_outliers": self.detect_outliers,
            "visualize": self.visualize,
            "generate_insights": self.generate_insights,
            "build_dashboard": self.build_dashboard,
            "export_dataset": self.export_dataset,
        }

    # -- plumbing ------------------------------------------------------------
    def schemas(self) -> List[Dict[str, Any]]:
        return TOOL_SCHEMAS

    def dispatch(self, name: str, args: Dict[str, Any]) -> str:
        fn = self._tools.get(name)
        if fn is None:
            return _dumps({"error": f"Unknown tool '{name}'."})
        try:
            return _dumps(fn(**(args or {})))
        except TypeError as exc:
            return _dumps({"error": f"Invalid arguments for '{name}': {exc}"})
        except Exception as exc:  # noqa: BLE001 - surface any error to the model
            return _dumps({"error": f"{type(exc).__name__}: {exc}"})

    # -- 1. inventory --------------------------------------------------------
    def list_datasets(self) -> Dict[str, Any]:
        return {
            "active": self.datasets.active,
            "datasets": self.datasets.describe_all(),
            "charts_created": len(self.charts.charts),
        }

    def inspect_dataset(self, dataset: Optional[str] = None) -> Dict[str, Any]:
        name, df = self.datasets.resolve(dataset)
        columns = []
        for col in df.columns:
            s = df[col]
            columns.append(
                {
                    "column": str(col),
                    "dtype": str(s.dtype),
                    "non_null": int(s.notna().sum()),
                    "nulls": int(s.isna().sum()),
                    "null_pct": round(float(s.isna().mean() * 100), 2),
                    "unique": int(s.nunique(dropna=True)),
                    "sample": [_scalar(v) for v in s.dropna().head(3).tolist()],
                }
            )
        return {
            "dataset": name,
            "rows": int(df.shape[0]),
            "columns": int(df.shape[1]),
            "duplicate_rows": int(df.duplicated().sum()),
            "memory_mb": round(df.memory_usage(deep=True).sum() / 1e6, 3),
            "column_details": columns,
            "head": _records(df, 5),
        }

    def profile_dataset(self, dataset: Optional[str] = None) -> Dict[str, Any]:
        name, df = self.datasets.resolve(dataset)
        result: Dict[str, Any] = {
            "dataset": name,
            "rows": int(df.shape[0]),
            "columns": int(df.shape[1]),
            "duplicate_rows": int(df.duplicated().sum()),
        }

        numeric = df.select_dtypes(include=np.number)
        if not numeric.empty:
            desc = numeric.describe().T.reset_index().rename(columns={"index": "column"})
            result["numeric_summary"] = _records(desc, 50)
            corr = numeric.corr(numeric_only=True)
            result["top_correlations"] = _corr_pairs(corr)

        categorical = df.select_dtypes(exclude=np.number)
        if not categorical.empty:
            cat = []
            for col in categorical.columns[:25]:
                s = df[col]
                top = s.value_counts(dropna=True)
                cat.append(
                    {
                        "column": str(col),
                        "unique": int(s.nunique(dropna=True)),
                        "top_value": _scalar(top.index[0]) if not top.empty else None,
                        "top_freq": int(top.iloc[0]) if not top.empty else 0,
                    }
                )
            result["categorical_summary"] = cat

        missing = [
            {
                "column": str(col),
                "nulls": int(df[col].isna().sum()),
                "pct": round(float(df[col].isna().mean() * 100), 2),
            }
            for col in df.columns
            if df[col].isna().any()
        ]
        result["missing"] = missing
        return result

    # -- 2. cleaning ---------------------------------------------------------
    def clean_dataset(
        self,
        operations: List[Dict[str, Any]],
        dataset: Optional[str] = None,
        new_name: Optional[str] = None,
        in_place: bool = True,
    ) -> Dict[str, Any]:
        name, original = self.datasets.resolve(dataset)
        df = original.copy()
        before = {
            "rows": int(df.shape[0]),
            "columns": int(df.shape[1]),
            "nulls": int(df.isna().sum().sum()),
            "duplicates": int(df.duplicated().sum()),
        }
        log: List[str] = []

        for raw in operations or []:
            op = str(raw.get("op", "")).strip().lower()
            cols = raw.get("columns")

            if op == "drop_duplicates":
                subset = [c for c in cols if c in df.columns] if cols else None
                dropped = int(df.duplicated(subset=subset).sum())
                df = df.drop_duplicates(subset=subset).reset_index(drop=True)
                log.append(f"Dropped {dropped} duplicate row(s)" + (f" on {subset}" if subset else ""))

            elif op in ("drop_null_rows", "dropna_rows"):
                subset = [c for c in cols if c in df.columns] if cols else None
                dropped = int(df.isna().any(axis=1).sum()) if subset is None else int(df[subset].isna().any(axis=1).sum())
                df = df.dropna(subset=subset).reset_index(drop=True)
                log.append(f"Dropped {dropped} row(s) with missing values")

            elif op in ("drop_null_columns", "dropna_columns"):
                if cols:
                    df = df.drop(columns=[c for c in cols if c in df.columns], errors="ignore")
                    log.append(f"Dropped column(s): {cols}")
                else:
                    thresh = raw.get("threshold")
                    if thresh is not None:
                        df = df.dropna(axis=1, thresh=int(math.ceil((1 - float(thresh)) * len(df))))
                    else:
                        df = df.dropna(axis=1, how="any")
                    log.append("Dropped columns with missing values")

            elif op in ("fill_missing", "fillna", "impute"):
                strategy = str(raw.get("strategy") or "mean").lower()
                value = raw.get("value")
                targets = [c for c in (cols or df.columns.tolist()) if c in df.columns]
                for col in targets:
                    if not df[col].isna().any():
                        continue
                    if strategy in ("mean", "median") and pd.api.types.is_numeric_dtype(df[col]):
                        df[col] = df[col].fillna(df[col].mean() if strategy == "mean" else df[col].median())
                    elif strategy == "mode":
                        mode = df[col].mode(dropna=True)
                        if not mode.empty:
                            df[col] = df[col].fillna(mode.iloc[0])
                    elif strategy in ("ffill", "pad"):
                        df[col] = df[col].ffill()
                    elif strategy in ("bfill", "backfill"):
                        df[col] = df[col].bfill()
                    elif strategy == "zero":
                        df[col] = df[col].fillna(0)
                    else:  # constant
                        df[col] = df[col].fillna(value)
                log.append(f"Filled missing values with strategy '{strategy}'")

            elif op in ("strip_whitespace", "strip"):
                targets = [c for c in (cols or df.columns.tolist()) if c in df.columns]
                for col in targets:
                    if df[col].dtype == object:
                        df[col] = df[col].apply(lambda v: v.strip() if isinstance(v, str) else v)
                log.append("Stripped leading/trailing whitespace")

            elif op == "lowercase":
                targets = [c for c in (cols or df.columns.tolist()) if c in df.columns]
                for col in targets:
                    if df[col].dtype == object:
                        df[col] = df[col].apply(lambda v: v.lower() if isinstance(v, str) else v)
                log.append("Lowercased text values")

            elif op == "fix_dtypes":
                mapping = raw.get("mapping") or {}
                for col, dtype in mapping.items():
                    if col not in df.columns:
                        continue
                    dtype = str(dtype).lower()
                    try:
                        if dtype in ("int", "int64", "integer"):
                            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
                        elif dtype in ("float", "float64", "double"):
                            df[col] = pd.to_numeric(df[col], errors="coerce")
                        elif dtype in ("str", "string", "text", "object"):
                            df[col] = df[col].astype(str)
                        elif dtype in ("datetime", "date", "timestamp"):
                            df[col] = pd.to_datetime(df[col], errors="coerce")
                        elif dtype in ("bool", "boolean"):
                            df[col] = df[col].astype("boolean")
                        elif dtype == "category":
                            df[col] = df[col].astype("category")
                    except Exception as exc:  # noqa: BLE001
                        log.append(f"Could not convert '{col}' to {dtype}: {exc}")
                log.append(f"Converted dtypes: {mapping}")

            elif op == "rename_columns":
                mapping = raw.get("mapping") or {}
                df = df.rename(columns={k: v for k, v in mapping.items() if k in df.columns})
                log.append(f"Renamed columns: {mapping}")

            elif op == "drop_columns":
                df = df.drop(columns=[c for c in (cols or []) if c in df.columns], errors="ignore")
                log.append(f"Dropped column(s): {cols}")

            elif op == "replace_values":
                mapping = raw.get("mapping") or {}
                for col, spec in mapping.items():
                    if col not in df.columns:
                        continue
                    if isinstance(spec, dict):
                        df[col] = df[col].replace(spec)
                    else:
                        df[col] = df[col].replace(spec)
                log.append("Replaced values")

            elif op == "clip_outliers":
                method = str(raw.get("method") or "iqr").lower()
                targets = [c for c in (cols or df.select_dtypes(include=np.number).columns.tolist()) if c in df.columns]
                for col in targets:
                    if not pd.api.types.is_numeric_dtype(df[col]):
                        continue
                    s = df[col]
                    if method == "zscore":
                        std = s.std(ddof=0)
                        if std and not math.isnan(std):
                            df[col] = s.clip(s.mean() - 3 * std, s.mean() + 3 * std)
                    else:
                        q1, q3 = s.quantile(0.25), s.quantile(0.75)
                        iqr = q3 - q1
                        df[col] = s.clip(q1 - 1.5 * iqr, q3 + 1.5 * iqr)
                log.append(f"Clipped outliers using '{method}' bounds")

            else:
                log.append(f"Skipped unknown operation '{op}'")

        after = {
            "rows": int(df.shape[0]),
            "columns": int(df.shape[1]),
            "nulls": int(df.isna().sum().sum()),
            "duplicates": int(df.duplicated().sum()),
        }

        if in_place and not new_name:
            self.datasets.set(name, df)
            target = name
        else:
            target = self.datasets.add(new_name or f"{name}_clean", df, original=df.copy())
            self.datasets.set_active(target)

        return {"dataset": target, "before": before, "after": after, "actions": log}

    def reset_dataset(self, dataset: Optional[str] = None) -> Dict[str, Any]:
        key = self.datasets.reset(dataset)
        _, df = self.datasets.resolve(key)
        return {"dataset": key, "restored_rows": int(df.shape[0]), "restored_columns": int(df.shape[1])}

    # -- 3. querying & aggregation ------------------------------------------
    def query_dataset(
        self,
        query: str,
        dataset: Optional[str] = None,
        limit: int = 50,
        save_as: Optional[str] = None,
    ) -> Dict[str, Any]:
        name, df = self.datasets.resolve(dataset)
        try:
            result = df.query(query, engine="python")
        except Exception as exc:  # noqa: BLE001
            raise ValueError(
                f"Could not evaluate query '{query}'. Use column names directly, "
                f"e.g. \"region == 'North' and revenue > 1000\". Error: {exc}"
            )
        out: Dict[str, Any] = {
            "dataset": name,
            "matched_rows": int(result.shape[0]),
            "total_rows": int(df.shape[0]),
            "result": _records(result, int(limit or 50)),
        }
        if save_as:
            key = self.datasets.add(save_as, result.reset_index(drop=True))
            out["saved_as"] = key
        return out

    def aggregate(
        self,
        group_by: List[str],
        metrics: Optional[List[Dict[str, str]]] = None,
        dataset: Optional[str] = None,
        sort_by: Optional[str] = None,
        ascending: bool = False,
        top_n: Optional[int] = None,
        save_as: Optional[str] = None,
    ) -> Dict[str, Any]:
        name, df = self.datasets.resolve(dataset)
        if isinstance(group_by, str):
            group_by = [group_by]
        missing = [c for c in group_by if c not in df.columns]
        if missing:
            raise ValueError(f"Group-by column(s) not found: {missing}. Available: {list(df.columns)}")

        if metrics:
            aggs = {}
            for m in metrics:
                col = m.get("column")
                fn = str(m.get("agg") or "mean").lower()
                if not col or col not in df.columns:
                    continue
                aggs[f"{col}_{fn}"] = pd.NamedAgg(column=col, aggfunc=fn)
            if not aggs:
                raise ValueError("No valid metrics provided. Check the column names.")
            result = df.groupby(group_by, dropna=False).agg(**aggs).reset_index()
        else:
            result = df.groupby(group_by, dropna=False).size().reset_index(name="count")

        if sort_by and sort_by in result.columns:
            result = result.sort_values(sort_by, ascending=bool(ascending))
        elif metrics:
            first_metric = next((c for c in result.columns if c not in group_by), None)
            if first_metric:
                result = result.sort_values(first_metric, ascending=False)

        if top_n:
            result = result.head(int(top_n))

        out: Dict[str, Any] = {
            "dataset": name,
            "group_by": group_by,
            "groups": int(result.shape[0]),
            "result": _records(result, 100),
        }
        if save_as:
            out["saved_as"] = self.datasets.add(save_as, result)
        return out

    def value_counts(
        self,
        column: str,
        dataset: Optional[str] = None,
        top_n: int = 20,
        normalize: bool = False,
    ) -> Dict[str, Any]:
        name, df = self.datasets.resolve(dataset)
        if column not in df.columns:
            raise ValueError(f"Column '{column}' not found. Available: {list(df.columns)}")
        counts = df[column].value_counts(normalize=bool(normalize), dropna=False)
        return {
            "dataset": name,
            "column": column,
            "normalized": bool(normalize),
            "counts": [
                {"value": _scalar(k), "count": _scalar(round(float(v), 4) if normalize else int(v))}
                for k, v in counts.head(int(top_n or 20)).items()
            ],
        }

    def correlation(
        self,
        columns: Optional[List[str]] = None,
        dataset: Optional[str] = None,
        method: str = "pearson",
    ) -> Dict[str, Any]:
        name, df = self.datasets.resolve(dataset)
        numeric = df.select_dtypes(include=np.number)
        if columns:
            numeric = numeric[[c for c in columns if c in numeric.columns]]
        if numeric.shape[1] < 2:
            raise ValueError("Need at least two numeric columns to compute correlations.")
        corr = numeric.corr(method=method, numeric_only=True).round(3)
        return {
            "dataset": name,
            "method": method,
            "columns": [str(c) for c in corr.columns],
            "matrix": _records(corr.reset_index().rename(columns={"index": "column"})),
            "strongest": _corr_pairs(corr),
        }

    def detect_outliers(
        self,
        columns: Optional[List[str]] = None,
        dataset: Optional[str] = None,
        method: str = "iqr",
    ) -> Dict[str, Any]:
        name, df = self.datasets.resolve(dataset)
        numeric = df.select_dtypes(include=np.number)
        targets = columns or numeric.columns.tolist()
        results = []
        for col in targets:
            if col not in df.columns or not pd.api.types.is_numeric_dtype(df[col]):
                continue
            s = df[col].dropna()
            if s.empty:
                continue
            if method == "zscore":
                std = s.std(ddof=0)
                mask = (np.abs((s - s.mean()) / std) > 3) if std else pd.Series(False, index=s.index)
            else:
                q1, q3 = s.quantile(0.25), s.quantile(0.75)
                iqr = q3 - q1
                mask = (s < q1 - 1.5 * iqr) | (s > q3 + 1.5 * iqr)
            results.append(
                {"column": str(col), "outliers": int(mask.sum()), "pct": round(float(mask.mean() * 100), 2)}
            )
        results.sort(key=lambda r: r["outliers"], reverse=True)
        return {"dataset": name, "method": method, "results": results}

    # -- 4. visualization ----------------------------------------------------
    def visualize(
        self,
        chart_type: str,
        x: Optional[str] = None,
        y: Optional[str] = None,
        hue: Optional[str] = None,
        dataset: Optional[str] = None,
        title: Optional[str] = None,
        agg: str = "sum",
        top_n: int = 15,
        bins: int = 30,
    ) -> Dict[str, Any]:
        name, df = self.datasets.resolve(dataset)
        ct = str(chart_type or "").lower()

        def require(col: Optional[str], role: str) -> str:
            if not col or col not in df.columns:
                raise ValueError(f"Column for {role} ('{col}') not found. Available: {list(df.columns)}")
            return col

        fig, ax = plt.subplots(figsize=(9, 5))
        chart_title = title

        if ct in ("bar", "bar_chart"):
            x = require(x, "x-axis")
            if y:
                y = require(y, "y-axis")
                grouped = (
                    df.groupby(x, dropna=False)[y]
                    .agg(agg or "sum")
                    .reset_index()
                    .sort_values(y, ascending=False)
                    .head(int(top_n))
                )
                sns.barplot(data=grouped, x=x, y=y, hue=hue, ax=ax)
                chart_title = chart_title or f"{agg.title()} of {y} by {x}"
            else:
                vc = df[x].value_counts().head(int(top_n))
                sns.barplot(x=vc.index.astype(str), y=vc.values, ax=ax)
                ax.set_xlabel(x)
                ax.set_ylabel("count")
                chart_title = chart_title or f"Count of {x}"
            if len(ax.get_xticklabels()) > 8:
                ax.tick_params(axis="x", rotation=45)

        elif ct == "line":
            x = require(x, "x-axis")
            y = require(y, "y-axis")
            d = df.sort_values(x)
            sns.lineplot(data=d, x=x, y=y, hue=hue, ax=ax)
            chart_title = chart_title or f"{y} over {x}"

        elif ct == "area":
            x = require(x, "x-axis")
            y = require(y, "y-axis")
            d = df.sort_values(x)
            ax.fill_between(d[x], d[y], alpha=0.35)
            ax.plot(d[x], d[y])
            chart_title = chart_title or f"{y} over {x}"

        elif ct == "scatter":
            x = require(x, "x-axis")
            y = require(y, "y-axis")
            sns.scatterplot(data=df, x=x, y=y, hue=hue, ax=ax)
            chart_title = chart_title or f"{y} vs {x}"

        elif ct in ("histogram", "hist"):
            x = require(x, "x-axis")
            sns.histplot(df[x].dropna(), bins=int(bins or 30), kde=True, ax=ax)
            chart_title = chart_title or f"Distribution of {x}"

        elif ct == "box":
            y = require(y, "y-axis")
            sns.boxplot(data=df, x=x if x in df.columns else None, y=y, ax=ax)
            chart_title = chart_title or f"Box plot of {y}" + (f" by {x}" if x else "")

        elif ct == "violin":
            y = require(y, "y-axis")
            sns.violinplot(data=df, x=x if x in df.columns else None, y=y, ax=ax)
            chart_title = chart_title or f"Violin plot of {y}" + (f" by {x}" if x else "")

        elif ct in ("countplot", "count"):
            x = require(x, "x-axis")
            vc = df[x].value_counts().head(int(top_n))
            sns.barplot(x=vc.index.astype(str), y=vc.values, ax=ax)
            ax.set_ylabel("count")
            chart_title = chart_title or f"Count of {x}"
            if len(ax.get_xticklabels()) > 8:
                ax.tick_params(axis="x", rotation=45)

        elif ct == "pie":
            x = require(x, "x-axis")
            vc = df[x].value_counts().head(int(top_n))
            ax.pie(vc.values, labels=vc.index.astype(str), autopct="%1.1f%%", startangle=90)
            ax.axis("equal")
            chart_title = chart_title or f"Share by {x}"

        elif ct in ("heatmap", "correlation"):
            numeric = df.select_dtypes(include=np.number)
            if numeric.shape[1] < 2:
                raise ValueError("Need at least two numeric columns for a heatmap.")
            sns.heatmap(numeric.corr(), annot=True, fmt=".2f", cmap="coolwarm", ax=ax)
            chart_title = chart_title or "Correlation heatmap"

        else:
            raise ValueError(
                f"Unsupported chart_type '{chart_type}'. Use one of: bar, line, scatter, "
                "histogram, box, violin, pie, countplot, heatmap, area."
            )

        ax.set_title(chart_title or ct.title())
        png = _fig_to_png(fig)
        idx = self.charts.add(
            Chart(title=chart_title or ct.title(), kind=ct, png=png, meta={"dataset": name})
        )
        return {"chart_index": idx, "title": chart_title or ct.title(), "chart_type": ct, "dataset": name}

    # -- 5. insights & reporting --------------------------------------------
    def generate_insights(self, dataset: Optional[str] = None) -> Dict[str, Any]:
        name, df = self.datasets.resolve(dataset)
        numeric = df.select_dtypes(include=np.number)
        digest: Dict[str, Any] = {
            "dataset": name,
            "rows": int(df.shape[0]),
            "columns": int(df.shape[1]),
            "duplicate_rows": int(df.duplicated().sum()),
            "total_missing": int(df.isna().sum().sum()),
        }
        if not numeric.empty:
            desc = numeric.describe().T.reset_index().rename(columns={"index": "column"})
            digest["numeric_summary"] = _records(desc, 50)
            if numeric.shape[1] >= 2:
                digest["top_correlations"] = _corr_pairs(numeric.corr())
            outliers = self.detect_outliers(dataset=name).get("results", [])
            digest["outlier_columns"] = [o for o in outliers if o["outliers"] > 0][:5]
        cat = df.select_dtypes(exclude=np.number)
        if not cat.empty:
            digest["categorical_summary"] = [
                {
                    "column": str(col),
                    "unique": int(df[col].nunique(dropna=True)),
                    "top_value": _scalar(df[col].value_counts(dropna=True).index[0])
                    if df[col].notna().any()
                    else None,
                }
                for col in cat.columns[:20]
            ]
        digest["missing_columns"] = [
            {"column": str(c), "nulls": int(df[c].isna().sum()), "pct": round(float(df[c].isna().mean() * 100), 2)}
            for c in df.columns
            if df[c].isna().any()
        ]
        return digest

    def build_dashboard(
        self,
        title: str = "Sumit07 Dashboard",
        insights: Optional[str] = None,
        chart_indices: Optional[List[int]] = None,
        dataset: Optional[str] = None,
    ) -> Dict[str, Any]:
        charts = self.charts.charts
        if chart_indices:
            charts = [charts[i] for i in chart_indices if 0 <= i < len(charts)]
        if not charts and not insights:
            raise ValueError("Nothing to include: create at least one chart first.")

        html = build_dashboard_html(title or "Sumit07 Dashboard", charts, insights)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(self.output_dir, f"dashboard_{stamp}.html")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(html)

        return {
            "dashboard_path": os.path.abspath(path),
            "charts_included": len(charts),
            "title": title,
        }

    def export_dataset(
        self,
        format: str = "csv",
        dataset: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> Dict[str, Any]:
        name, df = self.datasets.resolve(dataset)
        fmt = str(format or "csv").lower()
        base = filename or f"{name}_export"
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if fmt in ("xlsx", "excel"):
            path = os.path.join(self.output_dir, f"{base}_{stamp}.xlsx")
            df.to_excel(path, index=False)
        else:
            path = os.path.join(self.output_dir, f"{base}_{stamp}.csv")
            df.to_csv(path, index=False)
        return {
            "exported_path": os.path.abspath(path),
            "dataset": name,
            "rows": int(df.shape[0]),
            "columns": int(df.shape[1]),
        }
