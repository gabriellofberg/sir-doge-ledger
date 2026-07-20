from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from ..services import life

router = APIRouter(prefix="/api/life", tags=["life"])


class LifeItemIn(BaseModel):
    title: str
    kind: str = "reminder"
    due_date: str | None = None
    amount: float | None = None
    notes: str | None = None


class LifeItemPatch(BaseModel):
    title: str | None = None
    kind: str | None = None
    due_date: str | None = None
    amount: float | None = None
    notes: str | None = None


@router.get("/items")
def list_items(sort: str = "due") -> dict[str, Any]:
    return {"items": life.list_items(sort=sort)}


@router.get("/export.ics")
def export_ics() -> Response:
    from fastapi.responses import PlainTextResponse

    body = life.export_ics()
    return PlainTextResponse(
        content=body,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="sir-doge-life.ics"'},
    )


@router.post("/items")
def create_item(body: LifeItemIn) -> dict[str, Any]:
    return life.create_item(
        title=body.title,
        kind=body.kind,
        due_date=body.due_date,
        amount=body.amount,
        notes=body.notes,
    )


@router.patch("/items/{item_id}")
def patch_item(item_id: int, body: LifeItemPatch) -> dict[str, Any]:
    try:
        return life.update_item(item_id, **body.model_dump(exclude_unset=True))
    except KeyError:
        raise HTTPException(404, "Not found") from None


@router.delete("/items/{item_id}")
def remove_item(item_id: int) -> dict[str, str]:
    life.delete_item(item_id)
    return {"status": "ok"}
