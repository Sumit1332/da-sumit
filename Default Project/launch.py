"""DA Sumit launcher.

Starts the Streamlit server, waits until it is actually responding, and only
then opens the browser.

Environment options:
  DA_SUMIT_PORT        port to use (default 8501)
  DA_SUMIT_NO_BROWSER  set to 1 to skip opening a browser (background mode)
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser

HOST = "127.0.0.1"
PORT = int(os.getenv("DA_SUMIT_PORT", "8501"))
URL = f"http://{HOST}:{PORT}"
HEALTH = f"{URL}/_stcore/health"
OPEN_BROWSER = os.getenv("DA_SUMIT_NO_BROWSER", "").strip() not in ("1", "true", "yes")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(BASE_DIR, "outputs", "server.log")


def port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def wait_for_server(timeout_seconds: int = 90) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(HEALTH, timeout=2) as response:
                if response.read().strip() == b"ok":
                    return True
        except Exception:  # noqa: BLE001 - server not up yet
            pass
        time.sleep(0.5)
    return False


def log(message: str) -> None:
    try:
        print(message, flush=True)
    except Exception:  # noqa: BLE001 - stdout can be None under pythonw
        pass


def open_browser() -> None:
    if OPEN_BROWSER:
        try:
            webbrowser.open(URL)
        except Exception:  # noqa: BLE001
            pass


def main() -> int:
    os.chdir(BASE_DIR)
    try:
        sys.stdout.reconfigure(line_buffering=True)  # show messages immediately
    except Exception:  # noqa: BLE001
        pass

    log("=" * 46)
    log("   DA Sumit - Autonomous AI Data Analyst")
    log("=" * 46)

    if port_in_use(HOST, PORT):
        log(f"Port {PORT} is already in use - DA Sumit is already running.")
        log(f"Opening {URL}")
        open_browser()
        return 0

    log("Starting the server, please wait...")

    # Send the server's output to outputs/server.log so it is never lost, and
    # prevent any console window from popping up in background mode.
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    log_file = open(LOG_PATH, "w", encoding="utf-8")
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0

    proc = subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run", "app.py",
            "--server.port", str(PORT),
            "--server.address", HOST,
            "--server.headless", "true",
            "--browser.gatherUsageStats", "false",
        ],
        stdout=log_file,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
    )

    if wait_for_server():
        log("")
        log(f"  DA Sumit is ready:  {URL}")
        log("")
        log("  You can close this window - the app keeps running in the background.")
        log("  To stop it, run stop.bat.")
        log("")
        open_browser()
    else:
        log("")
        log("  The server did not respond in time. See outputs\\server.log for details.")

    try:
        return proc.wait()
    except KeyboardInterrupt:
        log("\nStopping DA Sumit...")
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
