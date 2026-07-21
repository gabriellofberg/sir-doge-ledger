from __future__ import annotations

import json

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel

from ..config import MAX_UPLOAD_BYTES
from ..services import data_management

router = APIRouter(prefix="/api/data", tags=["data"])

_MAX_BACKUP_BYTES = MAX_UPLOAD_BYTES


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


@router.post("/import/backup")
async def import_backup(file: UploadFile = File(...)) -> dict:
    raw = await file.read()
    if len(raw) > _MAX_BACKUP_BYTES:
        raise HTTPException(413, "Backup file too large")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(400, "Invalid JSON backup file") from exc
    try:
        return data_management.import_backup_json(payload)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/wipe")
def wipe_all_data(body: WipeRequest) -> dict:
    if body.confirm != "DELETE":
        raise HTTPException(400, 'Type DELETE in confirm to wipe all data')
    return {"status": "ok", "removed": data_management.wipe_all_data()}
