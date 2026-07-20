#!/usr/bin/env python3
"""SirDoge Ledger launcher — starts uvicorn and opens browser with auth token."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path


def _find_free_port(start: int = 8000) -> int:
    env_port = os.environ.get("SIR_DOGE_PORT")
    if env_port:
        return int(env_port)
    for port in range(start, start + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start


def _project_root() -> Path:
    return Path(__file__).resolve().parent


def _open_browser_later(port: int, token: str, frontend_port: int) -> None:
    time.sleep(1.5)
    # Dev: Vite frontend; prod: single port
    if os.environ.get("SIR_DOGE_PROD") == "1":
        webbrowser.open(f"http://127.0.0.1:{port}/?token={token}")
    else:
        webbrowser.open(f"http://127.0.0.1:{frontend_port}/?token={token}")


def main() -> int:
    root = _project_root()
    os.chdir(root)
    port = _find_free_port()
    frontend_port = int(os.environ.get("FRONTEND_PORT", "5173"))
    os.environ["SIR_DOGE_PORT"] = str(port)
    os.environ["PYTHONPATH"] = str(root / "backend") + os.pathsep + os.environ.get("PYTHONPATH", "")

    from app.services import auth

    token = auth.ensure_token()
    print("=" * 54)
    print(" SirDoge Ledger")
    print("=" * 54)
    print(f" Open: http://127.0.0.1:{frontend_port}/?token={token}")
    print(" Data stays on this machine only.")
    print("=" * 54)

    threading.Thread(
        target=_open_browser_later, args=(port, token, frontend_port), daemon=True
    ).start()

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--app-dir",
            "backend",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=str(root),
    )
    try:
        return proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
