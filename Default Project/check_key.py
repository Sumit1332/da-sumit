"""Verify the OPENAI_API_KEY in .env against OpenAI, without printing the key."""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

load_dotenv()

raw = os.getenv("OPENAI_API_KEY", "")
key = raw.strip()

if not key:
    print("NO KEY: OPENAI_API_KEY in .env is empty.")
    print("Open .env and set:  OPENAI_API_KEY=sk-proj-...your-key...")
    sys.exit(2)

masked = (key[:7] + "..." + key[-4:]) if len(key) > 14 else "(too short)"
print(f"Key detected: {masked}")
print(f"Length:       {len(key)} characters")

problems = []
if not key.startswith("sk-"):
    problems.append("does not start with 'sk-'")
if any(ch.isspace() for ch in key):
    problems.append("contains whitespace/line-break")
if raw != key:
    problems.append("has leading/trailing spaces")
if '"' in key or "'" in key:
    problems.append("contains quote characters")
if len(key) < 40:
    problems.append("looks too short (likely truncated)")

if problems:
    print("FORMAT PROBLEMS:")
    for p in problems:
        print(f"  - {p}")
else:
    print("Format:       looks OK")

print("Testing with OpenAI...")
try:
    from openai import OpenAI

    client = OpenAI(api_key=key)
    models = client.models.list()
    sample = ", ".join(m.id for m in list(models)[:5])
    print()
    print("SUCCESS: the key is valid.")
    print(f"Sample models: {sample}")
except Exception as exc:  # noqa: BLE001
    print()
    print("FAILED:", exc)
    sys.exit(1)
