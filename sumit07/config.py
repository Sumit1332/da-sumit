"""Runtime configuration for Sumit07 (loaded from environment / .env).

Two providers are supported and auto-detected from the API key:

  * Google Gemini - free tier, no card needed. Keys start with ``AIza``.
  * OpenAI        - pay-as-you-go. Keys start with ``sk-``.

Gemini is reached through its OpenAI-compatible endpoint, so the rest of the
codebase keeps talking plain ``client.chat.completions.create(...)``.
"""

from __future__ import annotations

import datetime
import os
import re

from dotenv import load_dotenv

load_dotenv()

# --- Provider settings ------------------------------------------------------
# Leave PROVIDER unset to auto-detect from the key.
# Set PROVIDER="gemini" or PROVIDER="openai" to force one.
PROVIDER = os.getenv("PROVIDER", "").strip().lower()

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

# Gemini chat models that are free of charge on a new project (Nov 2026).
GEMINI_FALLBACK_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3-flash-preview",
    "gemma-4-31b-it",
]

# OpenAI chat models. (gpt-4-turbo / gpt-4 / gpt-3.5-turbo / o1 / o3-mini /
# o4-mini were shut down on 23 Oct 2026; the GPT-4o family follows 14 Jan 2027.)
FALLBACK_MODELS = [
    "gpt-6-luna",
    "gpt-6.1-terra",
    "gpt-6.1-sol",
    "gpt-6-astra",
    "gpt-5.6-luna",
    "gpt-4o-mini",
]

# Chosen at runtime from the live model list; empty means "let the app decide".
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "").strip()

MAX_AGENT_STEPS = int(os.getenv("MAX_AGENT_STEPS", "12"))
SCOPE_GUARD = os.getenv("SCOPE_GUARD", "true").strip().lower() in ("1", "true", "yes", "on")

# --- Paths ------------------------------------------------------------------
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "outputs")
DATA_DIR = os.getenv("DATA_DIR", "data")

_NON_CHAT_HINTS = (
    "embedding",
    "tts",
    "whisper",
    "transcribe",
    "dall-e",
    "image",
    "imagen",
    "audio",
    "realtime",
    "moderation",
    "sora",
    "veo",
    "search",
    "diarize",
    "computer-use",
    "deep-research",
    "codex",
    "ocr",
    "nano-banana",
    "robotics",
    "omni",
)
_DATED_SNAPSHOT = re.compile(r"-\d{4}-\d{2}-\d{2}$")


def detect_provider(key: str | None = None) -> str:
    """Return "gemini" or "openai" for the given (or configured) key."""
    if PROVIDER in ("gemini", "google", "google-gemini"):
        return "gemini"
    if PROVIDER == "openai":
        return "openai"

    candidate = (key or get_api_key() or "").strip()
    if candidate.startswith("AIza") or candidate.startswith("AQ."):
        return "gemini"
    if candidate.startswith("sk-"):
        return "openai"
    if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
        return "gemini"
    return "openai"


def get_api_key(explicit: str | None = None) -> str | None:
    """Return the API key: explicit first, then the configured provider's key."""
    if explicit:
        return explicit.strip() or None
    if PROVIDER in ("gemini", "google", "google-gemini"):
        return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or None
    if PROVIDER == "openai":
        return os.getenv("OPENAI_API_KEY") or None
    return (
        os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or None
    )


def fallback_models(model: str | None = None) -> list[str]:
    """Candidate models to try when the selected one is unavailable."""
    name = (model or "").strip().lower()
    if name.startswith("gemini") or name.startswith("gemma"):
        return GEMINI_FALLBACK_MODELS
    if not name:
        return GEMINI_FALLBACK_MODELS if detect_provider() == "gemini" else FALLBACK_MODELS
    return FALLBACK_MODELS


def preferred_models(key: str | None = None) -> list[str]:
    """Sensible static list for the provider of the given key."""
    return GEMINI_FALLBACK_MODELS if detect_provider(key) == "gemini" else FALLBACK_MODELS


# Kept for backwards compatibility with older callers/tests.
AVAILABLE_MODELS = FALLBACK_MODELS


def get_client(api_key: str | None = None):
    """Create an OpenAI-compatible client for the detected provider."""
    from openai import OpenAI

    key = get_api_key(api_key)
    if not key:
        raise RuntimeError(
            "No API key found. Add GEMINI_API_KEY (free) or OPENAI_API_KEY to "
            "Streamlit secrets, your .env file, or the sidebar."
        )
    if detect_provider(key) == "gemini":
        return OpenAI(api_key=key, base_url=GEMINI_BASE_URL)
    return OpenAI(api_key=key)


def list_chat_models(api_key: str | None = None) -> list[str]:
    """Return the chat models this key can actually use, live from the provider."""
    client = get_client(api_key)
    today = datetime.date.today().isoformat()
    found: list[str] = []
    for model in client.models.list():
        model_id = (getattr(model, "id", "") or "").strip()
        if model_id.startswith("models/"):
            model_id = model_id[len("models/") :]
        if not model_id or _DATED_SNAPSHOT.search(model_id):
            continue
        if any(hint in model_id for hint in _NON_CHAT_HINTS):
            continue
        shutdown = getattr(model, "shutdown_date", None)
        if shutdown and str(shutdown)[:10] <= today:
            continue
        found.append(model_id)

    preferred = [m for m in preferred_models(api_key) if m in found]
    rest = sorted(m for m in found if m not in preferred)
    return preferred + rest
