from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from ..config import DATA_DIR, USER_DATA_DIR
from ..services import auth, settings as settings_svc
from ..services.demo import reset_demo_db

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsPatch(BaseModel):
    language: str | None = None
    theme: str | None = None
    default_months: int | None = None
    delete_upload_after_import: bool | None = None
    default_date_format: str | None = None
    monthly_income: float | None = None
    foodora_grocery_threshold: float | None = None


@router.get("")
def get_settings() -> dict[str, Any]:
    return {
        **settings_svc.get_all_settings(),
        "data_dir": str(USER_DATA_DIR),
        "auth_status": auth.auth_status(),
    }


@router.patch("")
def patch_settings(body: SettingsPatch) -> dict[str, Any]:
    patch = body.model_dump(exclude_none=True)
    return settings_svc.set_many(patch)


@router.post("/demo/reset")
def reset_demo() -> dict[str, str]:
    reset_demo_db()
    return {"status": "ok"}


@router.get("/data-dir")
def data_dir_info() -> dict[str, str]:
    return {"path": str(DATA_DIR.resolve())}
