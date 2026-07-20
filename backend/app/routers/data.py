from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel

from ..services import data_management

router = APIRouter(prefix="/api/data", tags=["data"])


class WipeRequest(BaseModel):
    confirm: str


@router.get("/export/transactions.csv")
def export_transactions_csv() -> PlainTextResponse:
    body = data_management.export_transactions_csv()
    return PlainTextResponse(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="sir-doge-transactions.csv"'},
    )


@router.get("/export/backup.json")
def export_backup_json() -> Response:
    payload = data_management.export_backup_json()
    return Response(
        content=json.dumps(payload, indent=2, ensure_ascii=False),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="sir-doge-backup.json"'},
    )


@router.post("/wipe")
def wipe_all_data(body: WipeRequest) -> dict:
    if body.confirm != "DELETE":
        raise HTTPException(400, 'Type DELETE in confirm to wipe all data')
    return {"status": "ok", "removed": data_management.wipe_all_data()}
