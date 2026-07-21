"""Config / auth-mode helpers."""

from app.config import is_dev_open


def test_is_dev_open_when_dev_set(monkeypatch):
    monkeypatch.delenv("SIR_DOGE_PROD", raising=False)
    monkeypatch.setenv("SIR_DOGE_DEV", "1")
    assert is_dev_open() is True


def test_is_dev_open_prod_wins_over_dev(monkeypatch):
    monkeypatch.setenv("SIR_DOGE_DEV", "1")
    monkeypatch.setenv("SIR_DOGE_PROD", "1")
    assert is_dev_open() is False


def test_is_dev_open_false_when_neither(monkeypatch):
    monkeypatch.delenv("SIR_DOGE_DEV", raising=False)
    monkeypatch.delenv("SIR_DOGE_PROD", raising=False)
    assert is_dev_open() is False
