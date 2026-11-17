"""Runtime configuration for Sumit07 (loaded from environment / .env)."""

from __future__ import annotations

import datetime
import os
import re

from dotenv import load_dotenv

load_dotenv()

# --- Model settings ---------------------------------------------------------
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-6-luna")
MAX_AGENT_STEPS = int(os.getenv("MAX_AGENT_STEPS", "12"))
SCOPE_GUARD = os.getenv("SCOPE_GUARD", "true").strip().lower() in ("1", "true", "yes", "on")

# --- Paths ------------------------------------------------------------------
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "outputs")
DATA_DIR = os.getenv("DATA_DIR", "data")

# Tried in order when the configured model has been retired by OpenAI.
# (gpt-4-turbo / gpt-4 / gpt-3.5-turbo / o1 / o3-mini / o4-mini were shut down
#  on 23 Oct 2026; the GPT-4o family follows on 14 Jan 2027.)
FALLBACK_MODELS = [
    "gpt-6-luna",
    "gpt-6.1-terra",
    "gpt-6.1-sol",
    "gpt-6-astra",
    "gpt-5.6-luna",
    "gpt-4o-mini",
    "gpt-4o",
    "gpt-4.1-mini",
    "gpt-4.1",
]

# Only used when the live model list cannot be fetched (no key / offline UI).
AVAILABLE_MODELS = FALLBACK_MODELS

_NON_CHAT_HINTS = (
    "embedding",
    "tts",
    "whisper",
    "transcribe",
    "dall-e",
    "image",
    "audio",
    "realtime",
    "moderation",
    "sora",
    "search",
    "diarize",
    "computer-use",
    "deep-research",
    "codex",
    "ocr",
)
_DATED_SNAPSHOT = re.compile(r"-\d{4}-\d{2}-\d{2}$")


def list_chat_models(api_key: str | None = None) -> list[str]:
    """Return the chat models this key can actually use.

    Queried live from OpenAI so retired models never show up in the UI.
    """
    client = get_client(api_key)
    today = datetime.date.today().isoformat()
    found: list[str] = []
    for model in client.models.list():
        model_id = getattr(model, "id", "") or ""
        if not model_id or _DATED_SNAPSHOT.search(model_id):
            continue
        if any(hint in model_id for hint in _NON_CHAT_HINTS):
            continue
        shutdown = getattr(model, "shutdown_date", None)
        if shutdown and str(shutdown)[:10] <= today:
            continue
        found.append(model_id)

    preferred = [m for m in FALLBACK_MODELS if m in found]
    rest = sorted(m for m in found if m not in preferred)
    return preferred + rest


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
