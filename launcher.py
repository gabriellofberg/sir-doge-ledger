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


def _parse_port(raw: str, *, name: str) -> int:
    try:
        port = int(raw)
    except ValueError as exc:
        raise SystemExit(f"Invalid {name}={raw!r}") from exc
    if not (1 <= port <= 65535):
        raise SystemExit(f"{name} out of range: {port}")
    return port


def _find_free_port(start: int = 8000) -> int:
    env_port = os.environ.get("SIR_DOGE_PORT")
    if env_port:
        return _parse_port(env_port, name="SIR_DOGE_PORT")
    for port in range(start, start + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start


def _project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _open_browser_later(port: int, *, prod: bool, frontend_port: int) -> None:
    time.sleep(1.5)
    url = f"http://127.0.0.1:{port if prod else frontend_port}/"
    webbrowser.open(url)


def main() -> int:
    frozen = getattr(sys, "frozen", False)
    root = _project_root()
    if not frozen:
        os.chdir(root)

    port = _find_free_port()
    frontend_port = _parse_port(
        os.environ.get("FRONTEND_PORT", "5173"), name="FRONTEND_PORT"
    )
    os.environ["SIR_DOGE_PORT"] = str(port)

    if frozen:
        os.environ["SIR_DOGE_PROD"] = "1"
        os.environ.pop("SIR_DOGE_DEV", None)
        # Ensure app.* is importable (Analysis uses pathex=backend)
        if hasattr(sys, "_MEIPASS"):
            meipass = str(sys._MEIPASS)
            if meipass not in sys.path:
                sys.path.insert(0, meipass)
            backend_in_bundle = Path(meipass) / "backend"
            if backend_in_bundle.is_dir() and str(backend_in_bundle) not in sys.path:
                sys.path.insert(0, str(backend_in_bundle))
    else:
        if os.environ.get("SIR_DOGE_PROD", "").lower() in ("1", "true", "yes"):
            # Explicit prod: never leave open auth via a leftover SIR_DOGE_DEV.
            os.environ.pop("SIR_DOGE_DEV", None)
        else:
            os.environ.setdefault("SIR_DOGE_DEV", "1")
        os.environ["PYTHONPATH"] = str(root / "backend") + os.pathsep + os.environ.get(
            "PYTHONPATH", ""
        )

    prod = frozen or os.environ.get("SIR_DOGE_PROD", "").lower() in ("1", "true", "yes")

    print("=" * 54)
    print(" SirDoge Ledger")
    print("=" * 54)
    if prod:
        print(f" Open http://127.0.0.1:{port}/")
        print(" Password auth enabled (prod)")
    else:
        print(f" Frontend http://127.0.0.1:{frontend_port}/")
        if os.environ.get("SIR_DOGE_DEV") == "1":
            print(" Dev mode: no password (SIR_DOGE_DEV=1)")
    print("=" * 54)

    threading.Thread(
        target=_open_browser_later,
        args=(port,),
        kwargs={"prod": prod, "frontend_port": frontend_port},
        daemon=True,
    ).start()

    if frozen:
        import uvicorn

        uvicorn.run("app.main:app", host="127.0.0.1", port=port, log_level="info")
        return 0

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
