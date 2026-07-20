import pytest


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    data = tmp_path / "data"
    uploads = data / "uploads"
    db = data / "sir_doge.db"
    token = data / "api-token"

    monkeypatch.setenv("SIR_DOGE_DATA_DIR", str(data))
    monkeypatch.setenv("SIR_DOGE_DEV", "1")

    import app.config as config
    import app.services.auth as auth

    monkeypatch.setattr(config, "USER_DATA_DIR", data)
    monkeypatch.setattr(config, "DATA_DIR", data)
    monkeypatch.setattr(config, "UPLOADS_DIR", uploads)
    monkeypatch.setattr(config, "DB_PATH", db)
    monkeypatch.setattr(auth, "TOKEN_FILE", token)
    monkeypatch.setattr(auth, "USER_DATA_DIR", data)

    import app.db as dbmod
    import app.services.import_sessions as sessions

    monkeypatch.setattr(dbmod, "DB_PATH", db)
    monkeypatch.setattr(sessions, "UPLOADS_DIR", uploads)

    from app.config import ensure_dirs
    from app.db import init_db

    ensure_dirs()
    init_db()
    yield
