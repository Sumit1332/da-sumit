"""Runtime configuration for Sumit07 (loaded from environment / .env)."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

# --- Model settings ---------------------------------------------------------
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
MAX_AGENT_STEPS = int(os.getenv("MAX_AGENT_STEPS", "12"))
SCOPE_GUARD = os.getenv("SCOPE_GUARD", "true").strip().lower() in ("1", "true", "yes", "on")

# --- Paths ------------------------------------------------------------------
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "outputs")
DATA_DIR = os.getenv("DATA_DIR", "data")

# --- Models offered in the UI ----------------------------------------------
AVAILABLE_MODELS = [
    "gpt-4o-mini",
    "gpt-4o",
    "gpt-4.1-mini",
    "gpt-4.1",
    "gpt-4-turbo",
]


def get_api_key(explicit: str | None = None) -> str | None:
    """Return an API key, preferring an explicitly supplied one."""
    return explicit or os.getenv("OPENAI_API_KEY") or None


def get_client(api_key: str | None = None):
    """Create an OpenAI client, raising a friendly error when no key is set."""
    from openai import OpenAI

    key = get_api_key(api_key)
    if not key:
        raise RuntimeError(
            "No OpenAI API key found. Set OPENAI_API_KEY in your .env file "
            "or paste a key into the sidebar."
        )
    return OpenAI(api_key=key)
