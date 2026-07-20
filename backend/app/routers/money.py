from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from ..config import MAX_TRANSACTION_LIMIT
from ..services import money
from ..services.import_parse import ColumnMapping
from ..services.import_sessions import save_upload

router = APIRouter(prefix="/api/money", tags=["money"])


class CategoryUpdate(BaseModel):
    category: str
    remember: bool = False
    match_text: str | None = None


class RecurringUpdate(BaseModel):
    decision: str | None = None
    use_it: str | None = None
    worth_it: str | None = None
    name: str | None = None


@router.get("/categories")
def get_categories() -> dict[str, Any]:
    return {"categories": CATEGORIES}


@router.get("/stats")
def stats() -> dict[str, Any]:
    return money.money_stats()


@router.get("/completeness")
def completeness() -> dict[str, Any]:
    return money.completeness()


@router.get("/summary")
def summary() -> dict[str, Any]:
    return {"by_category": money.category_summary()}


@router.get("/cashflow")
def cashflow(months: int = 12) -> dict[str, Any]:
    months = max(1, min(months, 36))
    return {"months": money.cashflow(months)}


@router.get("/breakdown")
def breakdown(kind: str = "spent") -> dict[str, Any]:
    if kind not in {"spent", "income"}:
        raise HTTPException(400, "kind must be spent or income")
    return {"kind": kind, "categories": money.breakdown(kind)}


@router.post("/preview")
async def preview(file: UploadFile = File(...)) -> dict[str, Any]:
    data = await file.read()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 20 MB)")
    session_id, safe_name = save_upload(file.filename or "upload.csv", data)
    from ..services.import_sessions import get_session_path

    result = money.preview_file(get_session_path(session_id))
    result["import_session_id"] = session_id
    result["filename"] = safe_name
    return result


@router.post("/import")
async def import_transactions(
    import_session_id: str = Form(...),
    filename: str = Form("import.csv"),
    mapping_json: str = Form(...),
    delete_upload: str = Form("true"),
) -> dict[str, Any]:
    try:
        raw = json.loads(mapping_json)
        mapping = ColumnMapping(**raw)
    except Exception as exc:
        raise HTTPException(400, f"Invalid mapping: {exc}") from exc
    remove_file = delete_upload.lower() in ("true", "1", "yes")
    try:
        return money.commit_import_session(
            import_session_id,
            mapping,
            filename,
            delete_upload=remove_file,
        )
    except KeyError:
        raise HTTPException(400, "Import session not found — preview again") from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/transactions")
def transactions(
    needs_review: bool | None = None,
    income_review: bool | None = None,
    category: str | None = None,
    limit: int = 500,
    offset: int = 0,
) -> dict[str, Any]:
    limit = max(1, min(limit, MAX_TRANSACTION_LIMIT))
    offset = max(0, offset)
    items = money.list_transactions(
        needs_review=needs_review,
        income_review=income_review,
        category=category,
        limit=limit,
        offset=offset,
    )
    return {"transactions": items}


@router.patch("/transactions/{tx_id}")
def patch_transaction(tx_id: int, body: CategoryUpdate) -> dict[str, Any]:
    try:
        return money.update_transaction_category(
            tx_id,
            body.category,
            remember=body.remember,
            match_text=body.match_text,
        )
    except KeyError:
        raise HTTPException(404, "Transaction not found") from None


@router.get("/recurring")
def recurring() -> dict[str, Any]:
    return {"groups": money.list_recurring()}


@router.patch("/recurring/{group_id}")
def patch_recurring(group_id: int, body: RecurringUpdate) -> dict[str, Any]:
    try:
        return money.update_recurring(
            group_id,
            decision=body.decision,
            use_it=body.use_it,
            worth_it=body.worth_it,
            name=body.name,
        )
    except KeyError:
        raise HTTPException(404, "Not found") from None


@router.get("/rules")
def rules() -> dict[str, Any]:
    return {"rules": money.list_rules()}


@router.delete("/rules/{rule_id}")
def remove_rule(rule_id: int) -> dict[str, str]:
    money.delete_rule(rule_id)
    return {"status": "ok"}
