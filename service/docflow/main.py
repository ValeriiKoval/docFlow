"""DocFlow AI service.

    pip install -r service/requirements.txt
    python -m uvicorn docflow.main:app --app-dir service --port 8000
    open http://localhost:8000/docs

Pipeline for POST /extract:
    upload -> sniff type, size/page limits -> sha256 dedup -> store original
    -> Claude extraction (strict tool schema) -> pydantic normalisation -> business checks
    -> status: auto_accepted (confidence >= threshold and no issues) | needs_review | failed
    -> every Claude call is logged in `runs` (tokens, cost, latency, error)

POST /ask: Q&A agent (docflow/agent.py) over the stored documents, logged in `agent_runs`.
"""
import secrets
from datetime import date, datetime, timedelta, timezone

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .agent import Agent
from .db import AgentRun, Document, Run, make_sessionmaker
from .extraction import ExtractionError, Extractor
from .files import InputError, inspect, store
from .queries import deadlines as query_deadlines, search_documents
from .schemas import (AskIn, AskOut, Deadline, DocumentOut, ExtractResponse, Fields, ReviewIn, Status,
                      business_checks)


def create_app(settings: Settings | None = None, extractor: Extractor | None = None,
               agent: Agent | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="DocFlow AI", version="0.5.0",
                  description="Intake of business documents: Claude extraction, validation, review, deadlines, Q&A.")
    app.state.settings = settings
    app.state.sessionmaker = make_sessionmaker(settings.database_url)
    app.state.extractor = extractor  # created lazily, so the app starts without an API key
    app.state.agent = agent

    def get_db():
        with app.state.sessionmaker() as db:
            yield db

    def get_extractor() -> Extractor:
        if app.state.extractor is None:
            app.state.extractor = Extractor(settings.model, settings.prompt_version, settings.prompts_dir,
                                            settings.schema_path)
        return app.state.extractor

    def get_agent() -> Agent:
        if app.state.agent is None:
            app.state.agent = Agent(app.state.sessionmaker, settings.agent_model, effort=settings.agent_effort or None)
        return app.state.agent

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
        return search_documents(db, q, doc_type, status, date_from, date_to, limit=limit, offset=offset)

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
                  past_days: int = Query(0, ge=0, le=366, description="Also include up to N days back (overdue)"),
                  today: date | None = Query(None, description="Defaults to the server date; set for demos"),
                  include_unverified: bool = Query(True, description="Include documents still awaiting review"),
                  days_left: str | None = Query(None, description="Comma-separated reminder offsets, e.g. 7,3,1,0"),
                  db: Session = Depends(get_db)):
        """Payment deadlines (due_date) and expiries (valid_until), soonest first."""
        try:
            offsets = {int(x) for x in days_left.split(",") if x.strip()} if days_left else None
        except ValueError:
            raise HTTPException(422, "days_left must be comma-separated integers")
        return query_deadlines(db, today or date.today(), within_days, past_days, include_unverified,
                               days_left=offsets)

    @app.post("/ask", response_model=AskOut, dependencies=[Depends(auth)])
    def ask(body: AskIn, db: Session = Depends(get_db), agent: Agent = Depends(get_agent)):
        """Q&A over stored documents: Claude with tools search_documents and list_deadlines."""
        r = agent.ask(body.question, body.today)
        db.add(AgentRun(question=body.question, answer=r.answer, chat_ref=body.chat_ref, model=r.model,
                        served_by=r.served_by, tool_calls=r.tool_calls, turns=r.turns,
                        input_tokens=r.usage["input_tokens"], output_tokens=r.usage["output_tokens"],
                        cost_usd=r.cost_usd, latency_s=round(r.latency_s, 3), error=r.error))
        db.commit()
        return AskOut(answer=r.answer, tool_calls=r.tool_calls, turns=r.turns, usage=r.usage,
                      cost_usd=r.cost_usd, latency_s=round(r.latency_s, 2), error=r.error)

    @app.get("/stats", dependencies=[Depends(auth)])
    def stats(db: Session = Depends(get_db)):
        """Totals for monitoring: documents by status / type, Claude usage and cost."""
        by_status = dict(db.execute(select(Document.status, func.count()).group_by(Document.status)).all())
        by_type = dict(db.execute(select(Document.doc_type, func.count()).group_by(Document.doc_type)).all())
        n, tin, tout, cost, lat, errs = db.execute(select(
            func.count(Run.id), func.coalesce(func.sum(Run.input_tokens), 0),
            func.coalesce(func.sum(Run.output_tokens), 0), func.coalesce(func.sum(Run.cost_usd), 0.0),
            func.avg(Run.latency_s), func.count(Run.error))).one()
        an, acost, alat, aerr = db.execute(select(
            func.count(AgentRun.id), func.coalesce(func.sum(AgentRun.cost_usd), 0.0), func.avg(AgentRun.latency_s),
            func.count(AgentRun.error))).one()
        return {"documents": {"by_status": by_status, "by_type": {k or "unknown": v for k, v in by_type.items()}},
                "runs": {"count": n, "errors": errs, "input_tokens": tin, "output_tokens": tout,
                         "cost_usd": round(cost, 4), "avg_latency_s": round(lat or 0.0, 2)},
                "agent": {"count": an, "errors": aerr, "cost_usd": round(acost, 4),
                          "avg_latency_s": round(alat or 0.0, 2)}}

    return app


app = create_app()
