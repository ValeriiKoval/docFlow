"""DocFlow AI service.

    pip install -r service/requirements.txt
    python -m uvicorn docflow.main:app --app-dir service --port 8000
    open http://localhost:8000/docs

Pipeline for POST /extract:
    upload -> sniff type, size/page limits -> sha256 dedup -> store original
    -> Claude extraction (strict tool schema) -> pydantic normalisation -> business checks
    -> status: auto_accepted (confidence >= threshold and no issues) | needs_review | failed
    -> every Claude call is logged in `runs` (tokens, cost, latency, error)
"""
import secrets
from datetime import date, datetime, timedelta, timezone

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .db import Document, Run, make_sessionmaker
from .extraction import ExtractionError, Extractor
from .files import InputError, inspect, store
from .schemas import (Deadline, DocumentOut, ExtractResponse, Fields, ReviewIn, Status, business_checks)

VERIFIED = ("auto_accepted", "approved", "corrected")


def create_app(settings: Settings | None = None, extractor: Extractor | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="DocFlow AI", version="0.3.0",
                  description="Intake of business documents: Claude extraction, validation, review, deadlines.")
    app.state.settings = settings
    app.state.sessionmaker = make_sessionmaker(settings.database_url)
    app.state.extractor = extractor  # created lazily, so the app starts without an API key

    def get_db():
        with app.state.sessionmaker() as db:
            yield db

    def get_extractor() -> Extractor:
        if app.state.extractor is None:
            app.state.extractor = Extractor(settings.model, settings.prompt_version, settings.prompts_dir,
                                            settings.schema_path)
        return app.state.extractor

    def auth(x_api_key: str | None = Header(default=None)):
        if settings.api_key and not secrets.compare_digest(x_api_key or "", settings.api_key):
            raise HTTPException(401, "invalid or missing X-API-Key")

    def get_doc(db: Session, doc_id: int) -> Document:
        doc = db.get(Document, doc_id)
        if doc is None:
            raise HTTPException(404, "document not found")
        return doc

    def apply_fields(doc: Document, f: Fields, confidence: float | None):
        for k in Document.FIELD_NAMES:
            setattr(doc, k, getattr(f, k))
        issues = business_checks(f)
        doc.issues = issues
        doc.confidence = confidence
        return issues

    def run_extraction(db: Session, doc: Document, data: bytes, extractor: Extractor):
        run = Run(document=doc, model=extractor.model, prompt_version=extractor.prompt_version)
        db.add(run)
        try:
            res = extractor.extract(data, doc.media_type)
        except ExtractionError as e:
            run.input_tokens, run.output_tokens = e.usage["input_tokens"], e.usage["output_tokens"]
            run.attempts, run.error = e.attempts, str(e)
            doc.status, doc.error = "failed", str(e)
        except Exception as e:  # API errors after SDK retries (auth, 4xx, persistent 5xx)
            run.error = f"{type(e).__name__}: {e}"[:1000]
            doc.status, doc.error = "failed", run.error
        else:
            run.input_tokens, run.output_tokens = res.usage["input_tokens"], res.usage["output_tokens"]
            run.cost_usd, run.latency_s = res.cost_usd, round(res.latency_s, 3)
            run.attempts, run.stop_reason, run.served_by = res.attempts, res.stop_reason, res.served_by
            doc.raw_extraction = res.fields
            try:
                f = Fields.model_validate(res.fields)
            except ValidationError as e:
                doc.status, doc.error = "failed", f"invalid fields: {e.errors()[0]['msg']}"
                run.error = doc.error
            else:
                conf = res.fields.get("confidence")
                issues = apply_fields(doc, f, conf)
                low = conf is None or conf < settings.confidence_threshold
                if low:
                    doc.issues = issues + [f"low confidence {conf} < {settings.confidence_threshold}"]
                doc.status = "needs_review" if (issues or low) else "auto_accepted"
                doc.error = None
        db.commit()

    @app.get("/health")
    def health():
        return {"status": "ok", "model": settings.model, "prompt": settings.prompt_version,
                "confidence_threshold": settings.confidence_threshold}

    @app.post("/extract", response_model=ExtractResponse, dependencies=[Depends(auth)])
    def extract(file: UploadFile = File(...), source: str | None = Form(None), source_ref: str | None = Form(None),
                db: Session = Depends(get_db), extractor: Extractor = Depends(get_extractor)):
        """Upload a PDF or image. Duplicates (same bytes) return the existing record without a new Claude call;
        a duplicate of a failed document is re-processed."""
        data = file.file.read()
        try:
            info = inspect(data, settings.max_file_mb, settings.max_pages)
        except InputError as e:
            raise HTTPException(e.status_code, str(e))
        doc = db.scalar(select(Document).where(Document.sha256 == info.sha256))
        if doc and doc.status != "failed":
            return {"duplicate": True, "document": doc}
        if doc is None:
            path = store(settings.storage_dir, info.sha256, info.media_type, data)
            doc = Document(sha256=info.sha256, filename=file.filename, media_type=info.media_type,
                           size_bytes=info.size_bytes, pages=info.pages, has_text_layer=info.has_text_layer,
                           storage_path=str(path), source=source, source_ref=source_ref, status="failed")
            db.add(doc)
            db.flush()
        run_extraction(db, doc, data, extractor)
        return {"duplicate": False, "document": doc}

    @app.get("/documents/search", response_model=list[DocumentOut], dependencies=[Depends(auth)])
    def search(q: str | None = Query(None, description="Substring of counterparty, recipient or number"),
               doc_type: str | None = None, status: Status | None = None,
               date_from: date | None = Query(None, description="issue_date >="),
               date_to: date | None = Query(None, description="issue_date <="),
               limit: int = Query(50, le=200), offset: int = 0, db: Session = Depends(get_db)):
        stmt = select(Document)
        if q:
            like = f"%{q.strip()}%"
            stmt = stmt.where(or_(Document.counterparty.ilike(like), Document.recipient.ilike(like),
                                  Document.document_number.ilike(like), Document.filename.ilike(like)))
        if doc_type:
            stmt = stmt.where(Document.doc_type == doc_type)
        if status:
            stmt = stmt.where(Document.status == status)
        if date_from:
            stmt = stmt.where(Document.issue_date >= date_from)
        if date_to:
            stmt = stmt.where(Document.issue_date <= date_to)
        stmt = stmt.order_by(Document.issue_date.desc().nulls_last(), Document.id.desc()).limit(limit).offset(offset)
        return db.scalars(stmt).all()

    @app.get("/documents/{doc_id}", response_model=DocumentOut, dependencies=[Depends(auth)])
    def get_document(doc_id: int, db: Session = Depends(get_db)):
        return get_doc(db, doc_id)

    @app.get("/documents/{doc_id}/file", dependencies=[Depends(auth)])
    def get_file(doc_id: int, db: Session = Depends(get_db)):
        doc = get_doc(db, doc_id)
        return FileResponse(doc.storage_path, media_type=doc.media_type, filename=doc.filename)

    @app.post("/documents/{doc_id}/review", response_model=DocumentOut, dependencies=[Depends(auth)])
    def review(doc_id: int, body: ReviewIn, db: Session = Depends(get_db)):
        """Human-in-the-loop decision (Telegram buttons ✅ / ✏️ in stage 4)."""
        doc = get_doc(db, doc_id)
        if body.action == "approve":
            if doc.doc_type is None:
                raise HTTPException(409, "nothing to approve: extraction failed, use action=correct")
            doc.status = "approved"
        elif body.action == "reject":
            doc.status = "rejected"
        else:
            unknown = set(body.fields) - set(Document.FIELD_NAMES)
            if unknown:
                raise HTTPException(422, f"unknown fields: {sorted(unknown)}")
            merged = {**(doc.fields or {}), **body.fields}
            try:
                f = Fields.model_validate(merged)
            except ValidationError as e:
                raise HTTPException(422, e.errors()[0]["msg"])
            apply_fields(doc, f, doc.confidence)
            doc.status, doc.error = "corrected", None
        doc.reviewed_at, doc.reviewed_by = datetime.now(timezone.utc), body.reviewer
        db.commit()
        return doc

    @app.post("/documents/{doc_id}/reprocess", response_model=DocumentOut, dependencies=[Depends(auth)])
    def reprocess(doc_id: int, db: Session = Depends(get_db), extractor: Extractor = Depends(get_extractor)):
        """Run extraction again (after a failure, or with a new prompt / model)."""
        doc = get_doc(db, doc_id)
        with open(doc.storage_path, "rb") as fh:
            run_extraction(db, doc, fh.read(), extractor)
        return doc

    @app.get("/deadlines", response_model=list[Deadline], dependencies=[Depends(auth)])
    def deadlines(within_days: int = Query(30, ge=0, le=366),
                  today: date | None = Query(None, description="Defaults to the server date; set for demos"),
                  include_unverified: bool = Query(True, description="Include documents still awaiting review"),
                  db: Session = Depends(get_db)):
        """Upcoming payment deadlines (due_date) and expiries (valid_until), soonest first."""
        today = today or date.today()
        until = today + timedelta(days=within_days)
        statuses = list(VERIFIED) + (["needs_review"] if include_unverified else [])
        out = []
        for col, kind in ((Document.due_date, "payment_due"), (Document.valid_until, "expires")):
            rows = db.scalars(select(Document).where(Document.status.in_(statuses), col >= today, col <= until))
            for d in rows:
                when = getattr(d, col.key)
                out.append(Deadline(document_id=d.id, kind=kind, date=when, days_left=(when - today).days,
                                    doc_type=d.doc_type, counterparty=d.counterparty,
                                    document_number=d.document_number, total_amount=d.total_amount,
                                    currency=d.currency, status=d.status))
        return sorted(out, key=lambda x: (x.date, x.document_id))

    @app.get("/stats", dependencies=[Depends(auth)])
    def stats(db: Session = Depends(get_db)):
        """Totals for monitoring: documents by status / type, Claude usage and cost."""
        by_status = dict(db.execute(select(Document.status, func.count()).group_by(Document.status)).all())
        by_type = dict(db.execute(select(Document.doc_type, func.count()).group_by(Document.doc_type)).all())
        n, tin, tout, cost, lat, errs = db.execute(select(
            func.count(Run.id), func.coalesce(func.sum(Run.input_tokens), 0),
            func.coalesce(func.sum(Run.output_tokens), 0), func.coalesce(func.sum(Run.cost_usd), 0.0),
            func.avg(Run.latency_s), func.count(Run.error))).one()
        return {"documents": {"by_status": by_status, "by_type": {k or "unknown": v for k, v in by_type.items()}},
                "runs": {"count": n, "errors": errs, "input_tokens": tin, "output_tokens": tout,
                         "cost_usd": round(cost, 4), "avg_latency_s": round(lat or 0.0, 2)}}

    return app


app = create_app()
