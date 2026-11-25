"""Read queries shared by the REST endpoints and the Q&A agent's tools."""
from datetime import date, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .db import Document

VERIFIED = ("auto_accepted", "approved", "corrected")
VISIBLE = VERIFIED + ("needs_review",)   # what the agent and reminders may see (not rejected / failed)


def _like(q: str) -> str:
    """Substring pattern with LIKE wildcards in the user's text escaped (`50%` is not "50 + anything")."""
    return "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def chat_scope(stmt, chat: str | None):
    """Only documents sent from this Telegram chat (source_ref = "<chat_id>:<message_id>")."""
    if chat is None:
        return stmt
    return stmt.where(Document.source == "telegram", Document.source_ref.like(f"{chat}:%"))


def doc_chat(doc: Document) -> str | None:
    if doc.source != "telegram" or not doc.source_ref:
        return None
    return doc.source_ref.split(":", 1)[0]


def _filters(stmt, q, doc_type, status, date_from, date_to, statuses, chat=None):
    stmt = chat_scope(stmt, chat)
    if q and q.strip():
        like = _like(q.strip())
        stmt = stmt.where(or_(*(c.ilike(like, escape="\\") for c in (
            Document.counterparty, Document.recipient, Document.document_number, Document.filename))))
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
                     limit: int = 50, offset: int = 0, chat: str | None = None) -> list[Document]:
    stmt = _filters(select(Document), q, doc_type, status, date_from, date_to, statuses, chat)
    stmt = stmt.order_by(Document.issue_date.desc().nulls_last(), Document.id.desc()).limit(limit).offset(offset)
    return list(db.scalars(stmt).all())


def count_documents(db: Session, q: str | None = None, doc_type: str | None = None, status: str | None = None,
                    date_from: date | None = None, date_to: date | None = None, statuses=None,
                    chat: str | None = None) -> int:
    return db.scalar(_filters(select(func.count(Document.id)), q, doc_type, status, date_from, date_to, statuses,
                              chat))


def deadlines(db: Session, today: date, within_days: int = 30, past_days: int = 0, include_unverified: bool = True,
              kind: str | None = None, days_left: set[int] | None = None, chat: str | None = None) -> list[dict]:
    """Payment deadlines (due_date) and expiries (valid_until) in [today - past_days, today + within_days].
    `days_left` keeps only items exactly that many days ahead (reminder offsets, e.g. {7, 3, 1, 0})."""
    start, until = today - timedelta(days=past_days), today + timedelta(days=within_days)
    statuses = list(VERIFIED) + (["needs_review"] if include_unverified else [])
    out = []
    for col, k in ((Document.due_date, "payment_due"), (Document.valid_until, "expires")):
        if kind and kind != k:
            continue
        stmt = chat_scope(select(Document), chat).where(Document.status.in_(statuses), col >= start, col <= until)
        for d in db.scalars(stmt):
            when = getattr(d, col.key)
            left = (when - today).days
            if days_left is not None and left not in days_left:
                continue
            out.append({"document_id": d.id, "kind": k, "date": when, "days_left": left, "doc_type": d.doc_type,
                        "counterparty": d.counterparty, "document_number": d.document_number,
                        "total_amount": d.total_amount, "currency": d.currency, "status": d.status,
                        "source": d.source, "source_ref": d.source_ref})
    return sorted(out, key=lambda x: (x["date"], x["document_id"]))
