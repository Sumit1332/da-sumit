"""Verify the API key in .env against the provider it belongs to.

Prints only the first 7 and last 4 characters of the key.
    python check_key.py
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sumit07 import config  # noqa: E402

raw = (
    os.getenv("GEMINI_API_KEY")
    or os.getenv("GOOGLE_API_KEY")
    or os.getenv("OPENAI_API_KEY")
    or ""
)
key = raw.strip()

if not key:
    print("NO KEY: none of GEMINI_API_KEY / GOOGLE_API_KEY / OPENAI_API_KEY is set in .env")
    print()
    print("Free Google Gemini key (no credit card): https://aistudio.google.com/apikey")
    print('Then add this line to .env:  GEMINI_API_KEY=AIza...your-key...')
    sys.exit(2)

masked = (key[:7] + "..." + key[-4:]) if len(key) > 14 else "(too short)"
provider = config.detect_provider(key)
print(f"Provider:     {provider}")
print(f"Key detected: {masked}")
print(f"Length:       {len(key)} characters")

problems = []
if provider == "gemini":
    if not key.startswith("AIza"):
        problems.append("Gemini keys normally start with 'AIza'")
elif provider == "openai":
    if not key.startswith("sk-"):
        problems.append("OpenAI keys normally start with 'sk-'")
if any(ch.isspace() for ch in key):
    problems.append("contains whitespace/line-break")
if raw != key:
    problems.append("has leading/trailing spaces")
if '"' in key or "'" in key:
    problems.append("contains quote characters")
if len(key) < 30:
    problems.append("looks too short (likely truncated)")

if problems:
    print("FORMAT PROBLEMS:")
    for problem in problems:
        print(f"  - {problem}")
else:
    print("Format:       looks OK")

print(f"\nTesting with {provider}...")
try:
    client = config.get_client(key)
    models = list(client.models.list())
    names = [getattr(m, "id", "?") for m in models][:6]
    print()
    print("SUCCESS: the key is valid.")
    print(f"Models visible: {', '.join(names)}")
except Exception as exc:  # noqa: BLE001
    print()
    print("FAILED:", exc)
    if provider == "openai":
        print("  - 401 Incorrect API key -> create a new key at https://platform.openai.com/api-keys")
        print("  - 429 insufficient_quota -> add credit (pay-as-you-go)")
    else:
        print("  - 400 API key not valid -> re-create at https://aistudio.google.com/apikey")
        print("  - 429 -> free-tier rate limit hit; wait a few minutes")
    sys.exit(1)
