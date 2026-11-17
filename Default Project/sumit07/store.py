"""In-memory stores for datasets and generated charts.

These objects live in Streamlit's session_state, so they survive script
re-runs. They hold the user's data and every chart the agent has produced.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


@dataclass
class Chart:
    """A rendered chart stored as PNG bytes plus metadata."""

    title: str
    kind: str
    png: bytes
    meta: Dict[str, Any] = field(default_factory=dict)


class DatasetStore:
    """Holds loaded datasets, their pristine originals, and the active one."""

    def __init__(self) -> None:
        self._data: Dict[str, pd.DataFrame] = {}
        self._originals: Dict[str, pd.DataFrame] = {}
        self.active: Optional[str] = None

    # -- creation ------------------------------------------------------------
    def add(self, name: str, df: pd.DataFrame, original: Optional[pd.DataFrame] = None) -> str:
        """Add a dataset, returning the (possibly de-duplicated) key."""
        key = self._unique_key(str(name) or "dataset")
        self._data[key] = df
        self._originals[key] = (original if original is not None else df.copy())
        if self.active is None:
            self.active = key
        return key

    def _unique_key(self, name: str) -> str:
        if name not in self._data:
            return name
        i = 2
        while f"{name}_{i}" in self._data:
            i += 1
        return f"{name}_{i}"

    # -- access --------------------------------------------------------------
    def names(self) -> List[str]:
        return list(self._data)

    def has(self, name: Optional[str]) -> bool:
        return name is not None and name in self._data

    def resolve(self, name: Optional[str] = None) -> Tuple[str, pd.DataFrame]:
        """Return (key, dataframe) for a name, falling back to the active one."""
        key = name or self.active
        if key is None:
            raise ValueError(
                "No dataset is loaded yet. Upload a CSV or Excel file first."
            )
        if key not in self._data:
            # Case-insensitive fallback.
            for candidate in self._data:
                if candidate.lower() == str(key).lower():
                    key = candidate
                    break
            else:
                raise ValueError(
                    f"Dataset '{key}' not found. Available: {list(self._data)}"
                )
        return key, self._data[key]

    # -- mutation ------------------------------------------------------------
    def set(self, name: str, df: pd.DataFrame) -> None:
        self._data[name] = df

    def set_active(self, name: str) -> None:
        key, _ = self.resolve(name)
        self.active = key

    def reset(self, name: Optional[str] = None) -> str:
        """Restore a dataset from its pristine original copy."""
        key, _ = self.resolve(name)
        self._data[key] = self._originals[key].copy()
        return key

    def remove(self, name: str) -> None:
        self._data.pop(name, None)
        self._originals.pop(name, None)
        if self.active == name:
            self.active = next(iter(self._data), None)

    def describe_all(self) -> List[Dict[str, Any]]:
        out = []
        for key, df in self._data.items():
            out.append(
                {
                    "name": key,
                    "rows": int(df.shape[0]),
                    "columns": int(df.shape[1]),
                    "active": key == self.active,
                }
            )
        return out


class ChartStore:
    """Ordered collection of charts produced during the session."""

    def __init__(self) -> None:
        self.charts: List[Chart] = []

    def add(self, chart: Chart) -> int:
        self.charts.append(chart)
        return len(self.charts) - 1

    def clear(self) -> None:
        self.charts = []

    def __len__(self) -> int:  # pragma: no cover - convenience
        return len(self.charts)
