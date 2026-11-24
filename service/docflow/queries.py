"""Read queries shared by the REST endpoints and the Q&A agent's tools."""
from datetime import date, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .db import Document

VERIFIED = ("auto_accepted", "approved", "corrected")
VISIBLE = VERIFIED + ("needs_review",)   # what the agent and reminders may see (not rejected / failed)


def _filters(stmt, q, doc_type, status, date_from, date_to, statuses):
    if q and q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Document.counterparty.ilike(like), Document.recipient.ilike(like),
                              Document.document_number.ilike(like), Document.filename.ilike(like)))
    if doc_type:
        stmt = stmt.where(Document.doc_type == doc_type)
    if status:
        stmt = stmt.where(Document.status == status)
    elif statuses:
        stmt = stmt.where(Document.status.in_(statuses))
    if date_from:
        stmt = stmt.where(Document.issue_date >= date_from)
    if date_to:
        stmt = stmt.where(Document.issue_date <= date_to)
    return stmt


def search_documents(db: Session, q: str | None = None, doc_type: str | None = None, status: str | None = None,
                     date_from: date | None = None, date_to: date | None = None, statuses=None,
                     limit: int = 50, offset: int = 0) -> list[Document]:
    stmt = _filters(select(Document), q, doc_type, status, date_from, date_to, statuses)
    stmt = stmt.order_by(Document.issue_date.desc().nulls_last(), Document.id.desc()).limit(limit).offset(offset)
    return list(db.scalars(stmt).all())


def count_documents(db: Session, q: str | None = None, doc_type: str | None = None, status: str | None = None,
                    date_from: date | None = None, date_to: date | None = None, statuses=None) -> int:
    return db.scalar(_filters(select(func.count(Document.id)), q, doc_type, status, date_from, date_to, statuses))


def deadlines(db: Session, today: date, within_days: int = 30, past_days: int = 0, include_unverified: bool = True,
              kind: str | None = None, days_left: set[int] | None = None) -> list[dict]:
    """Payment deadlines (due_date) and expiries (valid_until) in [today - past_days, today + within_days].
    `days_left` keeps only items exactly that many days ahead (reminder offsets, e.g. {7, 3, 1, 0})."""
    start, until = today - timedelta(days=past_days), today + timedelta(days=within_days)
    statuses = list(VERIFIED) + (["needs_review"] if include_unverified else [])
    out = []
    for col, k in ((Document.due_date, "payment_due"), (Document.valid_until, "expires")):
        if kind and kind != k:
            continue
        for d in db.scalars(select(Document).where(Document.status.in_(statuses), col >= start, col <= until)):
            when = getattr(d, col.key)
            left = (when - today).days
            if days_left is not None and left not in days_left:
                continue
            out.append({"document_id": d.id, "kind": k, "date": when, "days_left": left, "doc_type": d.doc_type,
                        "counterparty": d.counterparty, "document_number": d.document_number,
                        "total_amount": d.total_amount, "currency": d.currency, "status": d.status,
                        "source": d.source, "source_ref": d.source_ref})
    return sorted(out, key=lambda x: (x["date"], x["document_id"]))
