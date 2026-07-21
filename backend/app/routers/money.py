from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from ..config import MAX_TRANSACTION_LIMIT, SAMPLE_DATA_DIR
from ..services import (
    budgets as budget_svc,
    categories as cat_svc,
    insights as insights_svc,
    money,
    recommendations as reco_svc,
)
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
    cancel_by: str | None = None


class ManualTransaction(BaseModel):
    tx_date: str
    amount: float
    description: str
    category: str = "Other"
    notes: str | None = None
    tags: list[str] = []


class TransactionPatch(BaseModel):
    category: str | None = None
    remember: bool = False
    match_text: str | None = None
    notes: str | None = None
    tags: list[str] | None = None


class BulkCategoryUpdate(BaseModel):
    transaction_ids: list[int]
    category: str
    remember: bool = False
    match_text: str | None = None


class BankProfileIn(BaseModel):
    name: str
    mapping_json: dict[str, Any]


class BudgetIn(BaseModel):
    category: str
    monthly_limit: float | None
    enabled: bool = True


class SavingsGoalIn(BaseModel):
    id: int | None = None
    name: str
    target_amount: float
    current_amount: float = 0


class CategoryCreate(BaseModel):
    name: str


class CategoryRename(BaseModel):
    name: str


class CategoryMerge(BaseModel):
    target_slug: str


@router.get("/categories")
def get_categories() -> dict[str, Any]:
    return {"categories": cat_svc.list_categories()}


@router.post("/categories")
def create_category(body: CategoryCreate) -> dict[str, Any]:
    try:
        return cat_svc.create_category(body.name)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.patch("/categories/{slug}")
def rename_category(slug: str, body: CategoryRename) -> dict[str, Any]:
    try:
        return cat_svc.rename_category(slug, body.name)
    except KeyError as exc:
        raise HTTPException(404, "category not found") from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.delete("/categories/{slug}")
def delete_category(slug: str) -> dict[str, Any]:
    try:
        return cat_svc.delete_category(slug)
    except KeyError as exc:
        raise HTTPException(404, "category not found") from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/categories/{slug}/delete-preview")
def category_delete_preview(slug: str) -> dict[str, Any]:
    try:
        return cat_svc.delete_preview(slug)
    except KeyError as exc:
        raise HTTPException(404, "category not found") from exc


@router.post("/categories/{slug}/merge")
def merge_category(slug: str, body: CategoryMerge) -> dict[str, Any]:
    try:
        return cat_svc.merge_categories(slug, body.target_slug)
    except KeyError as exc:
        raise HTTPException(404, "category not found") from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


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
def breakdown(
    kind: str = "spent",
    month: str | None = None,
    months: int | None = None,
) -> dict[str, Any]:
    if kind not in {"spent", "income"}:
        raise HTTPException(400, "kind must be spent or income")
    if month is not None and (len(month) != 7 or month[4] != "-"):
        raise HTTPException(400, "month must be YYYY-MM")
    if months is not None:
        months = max(1, min(months, 36))
    return {
        "kind": kind,
        "month": month,
        "months": months,
        "categories": money.breakdown(kind, month=month, months=months),
    }


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
    search: str | None = None,
    tag: str | None = None,
    month: str | None = None,
    sort: str = "date_desc",
    limit: int = 500,
    offset: int = 0,
) -> dict[str, Any]:
    limit = max(1, min(limit, MAX_TRANSACTION_LIMIT))
    offset = max(0, offset)
    items = money.list_transactions(
        needs_review=needs_review,
        income_review=income_review,
        category=category,
        search=search,
        tag=tag,
        month=month,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    return {"transactions": items}


@router.post("/transactions")
def create_transaction(body: ManualTransaction) -> dict[str, Any]:
    return money.create_manual_transaction(
        body.tx_date, body.amount, body.description, body.category, body.notes, body.tags
    )


@router.patch("/transactions/{tx_id}")
def patch_transaction(tx_id: int, body: TransactionPatch) -> dict[str, Any]:
    try:
        if body.category is not None:
            return money.update_transaction_category(
                tx_id,
                body.category,
                remember=body.remember,
                match_text=body.match_text,
                notes=body.notes,
                tags=body.tags,
            )
        return money.update_transaction_meta(tx_id, notes=body.notes, tags=body.tags)
    except KeyError:
        raise HTTPException(404, "Transaction not found") from None


@router.post("/transactions/bulk-category")
def bulk_category(body: BulkCategoryUpdate) -> dict[str, Any]:
    return {
        "updated": money.bulk_update_category(
            body.transaction_ids,
            body.category,
            body.remember,
            match_text=body.match_text,
        )
    }


@router.get("/imports")
def import_history() -> dict[str, Any]:
    return {"imports": money.list_imports()}


@router.post("/import/sample")
def import_sample() -> dict[str, Any]:
    sample = SAMPLE_DATA_DIR / "sample_transactions.csv"
    if not sample.is_file():
        raise HTTPException(404, "Sample file missing")
    data = sample.read_bytes()
    session_id, safe_name = save_upload("sample_transactions.csv", data)
    mapping = ColumnMapping(
        date="Bokföringsdag",
        amount="Belopp",
        description="Text",
        amount_decimal=",",
        delimiter=";",
    )
    return money.commit_import_session(session_id, mapping, safe_name)


@router.get("/bank-profiles")
def bank_profiles() -> dict[str, Any]:
    return {"profiles": money.list_bank_profiles()}


@router.post("/bank-profiles")
def save_bank_profile(body: BankProfileIn) -> dict[str, Any]:
    return money.save_bank_profile(body.name, body.mapping_json)


@router.delete("/bank-profiles/{profile_id}")
def delete_bank_profile(profile_id: int) -> dict[str, str]:
    money.delete_bank_profile(profile_id)
    return {"status": "ok"}


@router.get("/alerts")
def alerts() -> dict[str, Any]:
    return {
        "budget": budget_svc.budget_alerts(),
        "price": money.price_alerts(),
        "recommendations": reco_svc.recommendations(),
    }


@router.get("/insights")
def insights(months: int = 12) -> dict[str, Any]:
    return {"insights": insights_svc.generate_insights(months)}


@router.patch("/recurring/price-events/{event_id}/acknowledge")
def acknowledge_price_event(event_id: int) -> dict[str, str]:
    money.acknowledge_price_event(event_id)
    return {"status": "ok"}


@router.get("/budgets")
def get_budgets() -> dict[str, Any]:
    return {"budgets": budget_svc.list_budgets(), "savings_goals": budget_svc.list_savings_goals()}


@router.put("/budgets")
def put_budget(body: BudgetIn) -> dict[str, Any]:
    return budget_svc.upsert_budget(body.category, body.monthly_limit, enabled=body.enabled)


@router.post("/savings-goals")
def put_savings(body: SavingsGoalIn) -> dict[str, Any]:
    return budget_svc.upsert_savings_goal(body.id, body.name, body.target_amount, body.current_amount)


@router.get("/year-comparison")
def year_comparison() -> dict[str, Any]:
    return {"years": money.year_comparison()}


@router.get("/recurring/alerts")
def recurring_alerts() -> dict[str, Any]:
    return {"alerts": money.price_alerts(), "yearly_total": money.recurring_yearly_total()}


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
            cancel_by=body.cancel_by,
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


@router.patch("/rules/{rule_id}")
def patch_rule(rule_id: int, body: dict[str, Any]) -> dict[str, Any]:
    try:
        return money.update_rule(
            rule_id,
            category=body.get("category"),
            enabled=body.get("enabled"),
            match_text=body.get("match_text"),
        )
    except KeyError:
        raise HTTPException(404, "Not found") from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
