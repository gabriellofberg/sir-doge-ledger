#!/usr/bin/env python3
"""SirDoge Ledger launcher."""

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


def _open_browser_later(port: int, frontend_port: int) -> None:
    time.sleep(1.5)
    url = f"http://127.0.0.1:{frontend_port if os.environ.get('SIR_DOGE_PROD') != '1' else port}/"
    webbrowser.open(url)


def main() -> int:
    root = _project_root()
    os.chdir(root)
    port = _find_free_port()
    frontend_port = int(os.environ.get("FRONTEND_PORT", "5173"))
    os.environ["SIR_DOGE_PORT"] = str(port)
    os.environ.setdefault("SIR_DOGE_DEV", "1")
    os.environ["PYTHONPATH"] = str(root / "backend") + os.pathsep + os.environ.get("PYTHONPATH", "")

    print("=" * 54)
    print(" SirDoge Ledger")
    print("=" * 54)
    print(f" Frontend http://127.0.0.1:{frontend_port}/")
    if os.environ.get("SIR_DOGE_DEV") == "1":
        print(" Dev mode: no password (SIR_DOGE_DEV=1)")
    print("=" * 54)

    threading.Thread(target=_open_browser_later, args=(port, frontend_port), daemon=True).start()

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
