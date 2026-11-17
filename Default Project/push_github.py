"""Create a GitHub repo and upload the deploy/ folder using the GitHub REST API.

Requires a GitHub token with `repo` scope in the GITHUB_TOKEN environment
variable (or in a file passed as the first argument).

No git installation needed.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.github.com"
BASE = Path(__file__).resolve().parent
DEPLOY = BASE / "deploy"
REPO = os.getenv("GITHUB_REPO", "da-sumit").strip() or "da-sumit"


def get_token() -> str:
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if not token and len(sys.argv) > 1:
        token = Path(sys.argv[1]).read_text(encoding="utf-8").strip()
    return token


TOKEN = get_token()
if not TOKEN:
    print("ERROR: no GitHub token provided.")
    sys.exit(2)


def call(method: str, path: str, payload: dict | None = None) -> dict:
    body = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(API + path, data=body, method=method)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "da-sumit-deploy")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from None


def main() -> int:
    if not DEPLOY.is_dir():
        print(f"ERROR: deploy folder not found at {DEPLOY}")
        return 2

    user = call("GET", "/user")
    login = user["login"]
    print(f"Authenticated as: {login}")

    created = False
    try:
        call("POST", "/user/repos", {"name": REPO, "private": True, "auto_init": True})
        print(f"Created private repo: {login}/{REPO}")
        created = True
        time.sleep(2)
    except RuntimeError as exc:
        if "HTTP 422" in str(exc):
            print(f"Repo {login}/{REPO} already exists - reusing it.")
        else:
            raise

    repo_info = call("GET", f"/repos/{login}/{REPO}")
    branch = repo_info.get("default_branch", "main")
    print(f"Using branch: {branch}")

    uploaded = 0
    failed = 0
    for path in sorted(DEPLOY.rglob("*")):
        if path.is_dir() or "__pycache__" in path.parts:
            continue
        rel = path.relative_to(DEPLOY).as_posix()
        content_b64 = base64.b64encode(path.read_bytes()).decode()

        payload = {
            "message": f"Add {rel}",
            "content": content_b64,
            "branch": branch,
        }

        # If the file already exists we need its SHA to update it.
        try:
            existing = call("GET", f"/repos/{login}/{REPO}/contents/{rel}?ref={branch}")
            if isinstance(existing, dict) and existing.get("sha"):
                payload["sha"] = existing["sha"]
        except RuntimeError:
            pass

        try:
            call("PUT", f"/repos/{login}/{REPO}/contents/{rel}", payload)
            print(f"  uploaded {rel}")
            uploaded += 1
        except RuntimeError as exc:
            print(f"  FAILED {rel}: {exc}")
            failed += 1

    print()
    print(f"Uploaded {uploaded} files, {failed} failed.")
    print(f"Repository: https://github.com/{login}/{REPO}")
    print(f"Branch:     {branch}")
    if failed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
