import os
import stat
import sys
from pathlib import Path

APP_NAME = "SirDoge Ledger"
APP_VERSION = "1.0.0"

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_IMPORT_ROWS = 50_000
MAX_TRANSACTION_LIMIT = 1000


def _resolve_install_root() -> Path:
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            return Path(sys._MEIPASS)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def _resolve_user_data_dir() -> Path:
    if env := os.environ.get("SIR_DOGE_DATA_DIR"):
        return Path(env).expanduser().resolve()
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            return Path(local) / "sir-doge-ledger"
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "sir-doge-ledger"
    return Path.home() / ".local" / "share" / "sir-doge-ledger"


def _chmod_private(path: Path, *, is_dir: bool = False) -> None:
    try:
        mode = stat.S_IRUSR | stat.S_IWUSR | (stat.S_IXUSR if is_dir else 0)
        path.chmod(mode)
    except OSError:
        pass


INSTALL_ROOT = _resolve_install_root()
PROJECT_ROOT = INSTALL_ROOT
USER_DATA_DIR = _resolve_user_data_dir()
DATA_DIR = USER_DATA_DIR
UPLOADS_DIR = USER_DATA_DIR / "uploads"
DB_PATH = USER_DATA_DIR / "sir_doge.db"
FRONTEND_DIST = INSTALL_ROOT / "frontend" / "dist"
SAMPLE_DATA_DIR = INSTALL_ROOT / "sample_data"
DEFAULT_PORT = int(os.environ.get("SIR_DOGE_PORT", "8000"))


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").lower() in ("1", "true", "yes")


def is_dev_open() -> bool:
    # Prod always wins if both flags are set (defense in depth).
    if _env_truthy("SIR_DOGE_PROD"):
        return False
    return _env_truthy("SIR_DOGE_DEV")


def demo_db_path() -> Path:
    return USER_DATA_DIR / "demo.db"


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    _chmod_private(DATA_DIR, is_dir=True)
    _chmod_private(UPLOADS_DIR, is_dir=True)
    if DB_PATH.exists():
        _chmod_private(DB_PATH)


def secure_db_file() -> None:
    if DB_PATH.exists():
        _chmod_private(DB_PATH)
