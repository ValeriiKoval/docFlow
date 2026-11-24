"""Pydantic models: normalisation of extracted fields and business-rule checks."""
import re
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

DocType = Literal["invoice", "contract", "insurance", "receipt", "utility_bill", "other"]
Language = Literal["uk", "pl", "en", "other"]
Status = Literal["auto_accepted", "needs_review", "approved", "corrected", "rejected", "failed"]

PAYABLE = {"invoice", "utility_bill"}
WITH_VALIDITY = {"insurance", "contract"}
WITH_TOTAL = {"invoice", "utility_bill", "receipt"}
KNOWN_CURRENCIES = {"UAH", "PLN", "EUR", "USD", "GBP", "CHF", "CZK"}


class Fields(BaseModel):
    """Extracted document fields after normalisation (the schema.json keys minus confidence)."""
    model_config = ConfigDict(extra="ignore")

    doc_type: DocType
    language: Language = "other"
    counterparty: str | None = None
    recipient: str | None = None
    document_number: str | None = None
    issue_date: date | None = None
    currency: str | None = None
    total_amount: float | None = None
    due_date: date | None = None
    valid_from: date | None = None
    valid_until: date | None = None

    @field_validator("counterparty", "recipient", "document_number", mode="before")
    @classmethod
    def _clean_text(cls, v):
        if v is None:
            return None
        v = re.sub(r"\s+", " ", str(v)).strip()
        return v or None

    @field_validator("document_number", mode="after")
    @classmethod
    def _strip_number_label(cls, v):
        # "№ 15/2025", "nr FV/1", "No. 7" -> bare number
        return re.sub(r"^(№|nr\.?|no\.?|#)\s*", "", v, flags=re.I) if v else v

    @field_validator("currency", mode="before")
    @classmethod
    def _currency(cls, v):
        if v is None or str(v).strip() == "":
            return None
        v = str(v).strip().upper()
        if not re.fullmatch(r"[A-Z]{3}", v):
            raise ValueError(f"not an ISO 4217 code: {v!r}")
        return v

    @field_validator("total_amount", mode="before")
    @classmethod
    def _amount(cls, v):
        if v is None or v == "":
            return None
        if isinstance(v, str):  # tolerate "1 234,56" from manual corrections
            s = v.replace(" ", "").replace(" ", "")
            s = s.replace(",", ".") if s.count(",") == 1 and "." not in s else s.replace(",", "")
            v = float(s)
        return round(float(v), 2)


def business_checks(f: Fields) -> list[str]:
    """Rules a correct extraction must satisfy. Any issue sends the document to human review."""
    issues = []
    if f.due_date and f.doc_type not in PAYABLE:
        issues.append(f"due_date set on a {f.doc_type}")
    if (f.valid_from or f.valid_until) and f.doc_type not in WITH_VALIDITY:
        issues.append(f"validity period set on a {f.doc_type}")
    if f.valid_from and f.valid_until and f.valid_until < f.valid_from:
        issues.append("valid_until is before valid_from")
    if f.due_date and f.issue_date and f.due_date < f.issue_date:
        issues.append("due_date is before issue_date")
    if f.doc_type in WITH_TOTAL and f.total_amount is None:
        issues.append(f"{f.doc_type} without total_amount")
    if f.total_amount is not None and f.total_amount < 0:
        issues.append("negative total_amount")
    if f.total_amount is not None and not f.currency:
        issues.append("total_amount without currency")
    if f.currency and f.currency not in KNOWN_CURRENCIES:
        issues.append(f"unexpected currency {f.currency}")
    if f.doc_type != "other" and not f.issue_date:
        issues.append("missing issue_date")
    if f.doc_type in WITH_VALIDITY and not (f.valid_from and f.valid_until):
        issues.append(f"{f.doc_type} without full validity period")
    return issues


# ---- API models --------------------------------------------------------------
class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sha256: str
    filename: str | None
    media_type: str
    pages: int | None
    has_text_layer: bool | None
    source: str | None
    source_ref: str | None
    status: Status
    confidence: float | None
    fields: Fields | None
    issues: list[str] = []
    error: str | None = None
    created_at: datetime
    reviewed_at: datetime | None = None
    reviewed_by: str | None = None


class ExtractResponse(BaseModel):
    duplicate: bool
    document: DocumentOut


class ReviewIn(BaseModel):
    action: Literal["approve", "correct", "reject"]
    fields: dict = Field(default_factory=dict, description="Partial field corrections (action=correct)")
    reviewer: str | None = None


class Deadline(BaseModel):
    document_id: int
    kind: Literal["payment_due", "expires"]
    date: date
    days_left: int
    doc_type: DocType
    counterparty: str | None
    document_number: str | None
    total_amount: float | None
    currency: str | None
    status: Status
    source: str | None = None
    source_ref: str | None = None


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    chat_ref: str | None = Field(None, description="Where the question came from, e.g. telegram chat id")
    today: date | None = Field(None, description="Defaults to the server date; set for demos and evals")


class AskOut(BaseModel):
    answer: str
    tool_calls: list[dict]
    turns: int
    usage: dict
    cost_usd: float
    latency_s: float
    error: str | None = None
