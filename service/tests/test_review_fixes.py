"""Regression tests for the security and code review fixes (no Claude calls).

Issue numbers in the section comments refer to the review notes."""
from datetime import date
from io import BytesIO
from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient

from docflow.agent import Agent
from docflow.config import REPO, Settings
from docflow.extraction import MAX_IMAGE_BYTES, ExtractionError, Extractor, fit_image
from docflow.main import create_app
from docflow.schemas import Fields

from test_api import INSURANCE, INVOICE, RECEIPT, FakeExtractor, label, upload


def make(tmp_path, **kw):
    fake = FakeExtractor()
    settings = Settings(database_url=f"sqlite:///{(tmp_path / 't.db').as_posix()}", storage_dir=tmp_path / "f", **kw)
    app = create_app(settings, extractor=fake)
    return app, TestClient(app, headers={"X-API-Key": kw.get("api_key") or ""}), fake


@pytest.fixture
def two_chats(tmp_path):
    """INVOICE from chat 42, INSURANCE from chat 77, RECEIPT uploaded over the API (no chat)."""
    app, client, fake = make(tmp_path, api_key="k")
    ids = {}
    for name, form in ((INVOICE, {"source": "telegram", "source_ref": "42:1"}),
                       (INSURANCE, {"source": "telegram", "source_ref": "77:1"}),
                       (RECEIPT, {"source": "api"})):
        fake.register(name)
        ids[name] = upload(client, name, **form).json()["document"]["id"]
    return app, client, fake, ids


# ---- #3 fail closed ------------------------------------------------------------------
def test_no_api_key_means_503_not_open(tmp_path):
    _, client, _ = make(tmp_path, api_key="")
    assert client.get("/documents/search").status_code == 503
    assert client.get("/health").status_code == 200


def test_dev_mode_allows_running_without_key(tmp_path):
    _, client, _ = make(tmp_path, api_key="", dev_mode=True)
    assert client.get("/documents/search").status_code == 200


# ---- #2 chat isolation -----------------------------------------------------------------
def test_review_from_another_chat_is_not_found(two_chats):
    _, client, _, ids = two_chats
    other = client.post(f"/documents/{ids[INSURANCE]}/review", json={"action": "reject", "chat_id": "42"})
    assert other.status_code == 404
    api_doc = client.post(f"/documents/{ids[RECEIPT]}/review", json={"action": "reject", "chat_id": "42"})
    assert api_doc.status_code == 404
    own = client.post(f"/documents/{ids[INVOICE]}/review", json={"action": "approve", "chat_id": "42"})
    assert own.status_code == 200 and own.json()["status"] == "approved"


def test_chat_id_must_be_numeric(two_chats):
    _, client, _, ids = two_chats
    r = client.post(f"/documents/{ids[INVOICE]}/review", json={"action": "approve", "chat_id": "42%"})
    assert r.status_code == 422


def test_agent_tools_see_only_the_chats_documents(two_chats):
    app, _, _, ids = two_chats
    agent = Agent(app.state.sessionmaker, "claude-haiku-5-5", client=object())
    args = {"query": None, "doc_type": None, "date_from": None, "date_to": None, "limit": None}
    everything = agent.run_tool("search_documents", args, date.today())
    mine = agent.run_tool("search_documents", args, date.today(), chat="42")
    assert everything["count"] == 3
    assert mine["count"] == 1 and mine["documents"][0]["id"] == ids[INVOICE]
    ins = label(INSURANCE)
    dl = {"within_days": 366, "past_days": 0, "kind": "any"}
    today = date.fromisoformat(ins["valid_from"])
    assert any(d["document_id"] == ids[INSURANCE] for d in agent.run_tool("list_deadlines", dl, today))
    assert not any(d["document_id"] == ids[INSURANCE] for d in agent.run_tool("list_deadlines", dl, today, "42"))


def test_ask_passes_chat_to_the_agent(two_chats):
    app, client, _, _ = two_chats
    seen = {}

    class SpyAgent:
        def ask(self, question, today=None, chat=None):
            seen["chat"] = chat
            return NS(answer="ok", model="m", served_by="m", tool_calls=[], turns=1,
                      usage={"input_tokens": 0, "output_tokens": 0}, cost_usd=0.0, latency_s=0.0, error=None)

    app.state.agent = SpyAgent()
    assert client.post("/ask", json={"question": "?", "chat_id": "77"}).status_code == 200
    assert seen["chat"] == "77"


def test_search_escapes_like_wildcards(two_chats):
    _, client, _, _ = two_chats
    assert client.get("/documents/search", params={"q": "%"}).json() == []
    # unescaped, "_" would match the "." in "..._pl.pdf"
    assert client.get("/documents/search", params={"q": "pl_pdf"}).json() == []
    assert len(client.get("/documents/search", params={"q": "_pl."}).json()) >= 1


# ---- #4 / #5 review state and reprocess ---------------------------------------------------
def test_rejected_is_final(two_chats):
    _, client, _, ids = two_chats
    did = ids[INVOICE]
    assert client.post(f"/documents/{did}/review", json={"action": "reject"}).json()["status"] == "rejected"
    assert client.post(f"/documents/{did}/review", json={"action": "approve"}).status_code == 409
    r = client.post(f"/documents/{did}/review", json={"action": "correct", "fields": {"total_amount": 1}})
    assert r.status_code == 409


def test_reprocess_keeps_reviewer_corrections(two_chats):
    _, client, fake, ids = two_chats
    did = ids[INVOICE]
    r = client.post(f"/documents/{did}/review", json={"action": "correct", "fields": {"total_amount": "1.234,56"}})
    assert r.json()["status"] == "corrected" and r.json()["fields"]["total_amount"] == 1234.56
    calls = fake.calls
    assert client.post(f"/documents/{did}/reprocess").status_code == 409
    assert fake.calls == calls
    doc = client.get(f"/documents/{did}").json()
    assert doc["status"] == "corrected" and doc["fields"]["total_amount"] == 1234.56
    forced = client.post(f"/documents/{did}/reprocess", params={"force": True})
    assert forced.status_code == 200 and forced.json()["status"] == "auto_accepted"


def test_oversized_upload_is_rejected(tmp_path):
    _, client, _ = make(tmp_path, api_key="k", max_file_mb=1)
    big = b"%PDF-1.4\n" + b"0" * (1024 * 1024 + 10)
    r = client.post("/extract", files={"file": ("big.pdf", big, "application/pdf")})
    assert r.status_code == 413


# ---- #22 / #23 parsing ---------------------------------------------------------------------
@pytest.mark.parametrize("raw,expected", [
    ("№ FV/2025/03/1", "FV/2025/03/1"), ("nr FV/1", "FV/1"), ("No. 7", "7"), ("Nr123", "123"), ("#12", "12"),
    ("No:15", "15"), ("NOV/2026/1", "NOV/2026/1"), ("Nordic-15", "Nordic-15"), ("Nomenclature-1", "Nomenclature-1")])
def test_number_label(raw, expected):
    assert Fields(doc_type="invoice", document_number=raw).document_number == expected


@pytest.mark.parametrize("raw,expected", [
    ("1.234,56", 1234.56), ("1,234.56", 1234.56), ("1 234,56", 1234.56), ("1.234.567", 1234567.0),
    ("1,234,567", 1234567.0), ("15,5", 15.5), ("12.5", 12.5)])
def test_amount_formats(raw, expected):
    assert Fields(doc_type="receipt", total_amount=raw).total_amount == expected


# ---- #13 / #15 extraction ------------------------------------------------------------------
class Scripted:
    def __init__(self, *responses):
        self.responses, self.requests = list(responses), []
        self.messages = NS(create=self.create)
        self.beta = NS(messages=NS(create=self.create))

    def create(self, **kw):
        self.requests.append([dict(m) for m in kw["messages"]])
        return self.responses.pop(0)


def reply(*content, stop="tool_use"):
    return NS(content=list(content), stop_reason=stop, model="claude-haiku-5-5", stop_details=None,
              usage=NS(input_tokens=100, output_tokens=10))


def extractor(client):
    return Extractor("claude-haiku-5-5", "extract_v2", REPO / "prompts", REPO / "schema.json", client=client)


def test_retry_tells_the_model_what_was_wrong():
    good = {**label(INVOICE), "confidence": 0.9}
    bad = {**good, "issue_date": "10.01.2025"}
    client = Scripted(reply(NS(type="tool_use", name="record_document", input=bad, id="t1")),
                      reply(NS(type="tool_use", name="record_document", input=good, id="t2")))
    res = extractor(client).extract(b"%PDF-1.4 x", "application/pdf")
    assert res.attempts == 2 and res.fields["issue_date"] == good["issue_date"]
    second = client.requests[1]
    assert len(second) == 3 and second[2]["content"][0]["is_error"] is True
    assert second[2]["content"][0]["tool_use_id"] == "t1" and "issue_date" in second[2]["content"][0]["content"]


def test_max_tokens_is_not_retried():
    client = Scripted(reply(NS(type="text", text="..."), stop="max_tokens"))
    with pytest.raises(ExtractionError) as e:
        extractor(client).extract(b"%PDF-1.4 x", "application/pdf")
    assert e.value.attempts == 1 and len(client.requests) == 1


def test_large_image_is_shrunk_below_the_api_limit():
    from PIL import Image
    import os
    im = Image.frombytes("RGB", (5000, 3000), os.urandom(5000 * 3000 * 3))
    buf = BytesIO()
    im.save(buf, "PNG")
    data, media = fit_image(buf.getvalue(), "image/png")
    assert media == "image/jpeg" and len(data) <= MAX_IMAGE_BYTES
    assert max(Image.open(BytesIO(data)).size) <= 4096
    small = BytesIO()
    Image.new("RGB", (100, 100)).save(small, "PNG")
    assert fit_image(small.getvalue(), "image/png") == (small.getvalue(), "image/png")
