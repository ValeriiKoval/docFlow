"""SQLAlchemy models. SQLite by default, Postgres via DATABASE_URL (stage 4)."""
from datetime import date, datetime, timezone

from sqlalchemy import (JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, create_engine,
                        event)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


def utcnow():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    filename: Mapped[str | None] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(50))
    size_bytes: Mapped[int] = mapped_column(Integer)
    pages: Mapped[int | None] = mapped_column(Integer)
    has_text_layer: Mapped[bool | None] = mapped_column(Boolean)
    storage_path: Mapped[str] = mapped_column(String(500))
    source: Mapped[str | None] = mapped_column(String(50))          # telegram / email / drive / api
    source_ref: Mapped[str | None] = mapped_column(String(255))     # e.g. telegram chat_id:message_id

    status: Mapped[str] = mapped_column(String(20), index=True)
    confidence: Mapped[float | None] = mapped_column(Float)
    issues: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(Text)
    raw_extraction: Mapped[dict | None] = mapped_column(JSON)      # model output as returned

    # normalised fields (flattened for search / deadlines)
    doc_type: Mapped[str | None] = mapped_column(String(20), index=True)
    language: Mapped[str | None] = mapped_column(String(5))
    counterparty: Mapped[str | None] = mapped_column(String(255))
    recipient: Mapped[str | None] = mapped_column(String(255))
    document_number: Mapped[str | None] = mapped_column(String(100))
    issue_date: Mapped[date | None] = mapped_column(Date, index=True)
    currency: Mapped[str | None] = mapped_column(String(3))
    total_amount: Mapped[float | None] = mapped_column(Float)
    due_date: Mapped[date | None] = mapped_column(Date, index=True)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(Date, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[str | None] = mapped_column(String(100))

    runs: Mapped[list["Run"]] = relationship(back_populates="document", order_by="Run.id")

    FIELD_NAMES = ("doc_type", "language", "counterparty", "recipient", "document_number", "issue_date",
                   "currency", "total_amount", "due_date", "valid_from", "valid_until")

    @property
    def fields(self):
        if self.doc_type is None:
            return None
        return {k: getattr(self, k) for k in self.FIELD_NAMES}


class Run(Base):
    """One extraction attempt: tokens, cost, latency, outcome."""
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    model: Mapped[str] = mapped_column(String(50))
    served_by: Mapped[str | None] = mapped_column(String(50))
    prompt_version: Mapped[str] = mapped_column(String(50))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    latency_s: Mapped[float] = mapped_column(Float, default=0.0)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    stop_reason: Mapped[str | None] = mapped_column(String(30))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    document: Mapped[Document] = relationship(back_populates="runs")


class AgentRun(Base):
    """One Q&A agent answer: question, tools used, tokens, cost, latency."""
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str | None] = mapped_column(Text)
    chat_ref: Mapped[str | None] = mapped_column(String(255))
    model: Mapped[str] = mapped_column(String(50))
    served_by: Mapped[str | None] = mapped_column(String(50))
    tool_calls: Mapped[list] = mapped_column(JSON, default=list)
    turns: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    latency_s: Mapped[float] = mapped_column(Float, default=0.0)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


def make_sessionmaker(database_url: str):
    kwargs = {}
    if database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        path = database_url.removeprefix("sqlite:///")
        if path and path != ":memory:":
            from pathlib import Path
            Path(path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(database_url, **kwargs)
    if database_url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _):
            dbapi_conn.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)
