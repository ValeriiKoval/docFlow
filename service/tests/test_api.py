"""API tests with a fake extractor (no Claude calls).

    python -m pytest service/tests -q
"""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from docflow.config import REPO, Settings
from docflow.extraction import ExtractionError, ExtractionResult
from docflow.main import create_app

DATASET = REPO / "eval" / "dataset"


def pdf(name):
    return (DATASET / "pdf" / f"{name}.pdf").read_bytes()


def label(name):
    lab = json.loads((DATASET / "labels" / f"{name}.json").read_text(encoding="utf-8"))
    lab.pop("_meta")
    return lab


class FakeExtractor:
    """Returns ground truth for the uploaded dataset PDF, optionally altered."""
    model, prompt_version = "fake-model", "test"

    def __init__(self):
        self.calls = 0
        self.override = {}      # fields merged into the answer
        self.fail = None        # exception to raise
        self.by_sha = {}

    def register(self, name):
        import hashlib
        self.by_sha[hashlib.sha256(pdf(name)).hexdigest()] = name

    def extract(self, data, media_type):
        import hashlib
        self.calls += 1
        if self.fail:
            raise self.fail
        fields = {**label(self.by_sha[hashlib.sha256(data).hexdigest()]), "confidence": 0.95, **self.override}
        return ExtractionResult(fields=fields, model=self.model, prompt_version=self.prompt_version,
                                usage={"input_tokens": 4000, "output_tokens": 400}, latency_s=0.01,
                                stop_reason="tool_use", served_by="claude-sonnet-5-5")


@pytest.fixture
def ctx(tmp_path):
    fake = FakeExtractor()
    settings = Settings(database_url=f"sqlite:///{(tmp_path / 't.db').as_posix()}", storage_dir=tmp_path / "files",
                        api_key="secret", confidence_threshold=0.6)
    client = TestClient(create_app(settings, extractor=fake), headers={"X-API-Key": "secret"})
    return client, fake


def upload(client, name, **form):
    return client.post("/extract", files={"file": (f"{name}.pdf", pdf(name), "application/pdf")}, data=form)


INVOICE = "004_invoice_pl"
INSURANCE = "000_insurance_pl"
RECEIPT = "008_receipt_en"


def test_auth_required(ctx):
    client, _ = ctx
    r = client.post("/extract", headers={"X-API-Key": "wrong"},
                    files={"file": ("a.pdf", pdf(INVOICE), "application/pdf")})
    assert r.status_code == 401


def test_extract_auto_accepted_and_stored(ctx, tmp_path):
    client, fake = ctx
    fake.register(INVOICE)
    r = upload(client, INVOICE, source="telegram", source_ref="42:7")
    assert r.status_code == 200, r.text
    body = r.json()
    doc = body["document"]
    assert body["duplicate"] is False
    assert doc["status"] == "auto_accepted"
    assert doc["fields"]["total_amount"] == label(INVOICE)["total_amount"]
    assert doc["has_text_layer"] is True and doc["pages"] == 1
    assert doc["source_ref"] == "42:7"
    assert list((tmp_path / "files").rglob("*.pdf")), "original not stored"
    assert client.get(f"/documents/{doc['id']}/file").content == pdf(INVOICE)


def test_duplicate_does_not_call_claude_again(ctx):
    client, fake = ctx
    fake.register(INVOICE)
    first = upload(client, INVOICE).json()["document"]["id"]
    r = upload(client, INVOICE).json()
    assert r["duplicate"] is True and r["document"]["id"] == first
    assert fake.calls == 1


def test_low_confidence_goes_to_review(ctx):
    client, fake = ctx
    fake.register(INVOICE)
    fake.override = {"confidence": 0.45}
    doc = upload(client, INVOICE).json()["document"]
    assert doc["status"] == "needs_review"
    assert any("low confidence" in i for i in doc["issues"])


def test_business_rule_violation_goes_to_review_even_if_confident(ctx):
    client, fake = ctx
    fake.register(INSURANCE)
    fake.override = {"valid_until": "2020-01-01", "confidence": 0.99}
    doc = upload(client, INSURANCE).json()["document"]
    assert doc["status"] == "needs_review"
    assert "valid_until is before valid_from" in doc["issues"]


def test_failed_extraction_is_recorded_and_retried_on_reupload(ctx):
    client, fake = ctx
    fake.register(RECEIPT)
    fake.fail = ExtractionError("no record_document call after 3 attempts",
                                {"input_tokens": 9000, "output_tokens": 30}, 3)
    doc = upload(client, RECEIPT).json()["document"]
    assert doc["status"] == "failed" and "no record_document" in doc["error"]
    fake.fail = None
    r = upload(client, RECEIPT).json()
    assert r["duplicate"] is False and r["document"]["status"] == "auto_accepted"
    stats = client.get("/stats").json()
    assert stats["runs"]["count"] == 2 and stats["runs"]["errors"] == 1


def test_unsupported_and_corrupt_files(ctx):
    client, _ = ctx
    r = client.post("/extract", files={"file": ("x.txt", b"hello world", "text/plain")})
    assert r.status_code == 415
    r = client.post("/extract", files={"file": ("x.pdf", b"%PDF-1.4 garbage", "application/pdf")})
    assert r.status_code == 422


def test_review_correct_and_approve(ctx):
    client, fake = ctx
    fake.register(INSURANCE)
    fake.override = {"total_amount": 76000.0, "confidence": 0.5}   # the v1 sum-insured mistake
    doc = upload(client, INSURANCE).json()["document"]
    assert doc["status"] == "needs_review"
    r = client.post(f"/documents/{doc['id']}/review",
                    json={"action": "correct", "fields": {"total_amount": "1 516,40"}, "reviewer": "anna"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "corrected" and r.json()["fields"]["total_amount"] == 1516.4
    assert r.json()["reviewed_by"] == "anna"
    bad = client.post(f"/documents/{doc['id']}/review", json={"action": "correct", "fields": {"amount": 1}})
    assert bad.status_code == 422


def test_search_and_deadlines(ctx):
    client, fake = ctx
    for n in (INVOICE, INSURANCE, RECEIPT):
        fake.register(n)
        upload(client, n)
    inv, ins = label(INVOICE), label(INSURANCE)

    found = client.get("/documents/search", params={"q": inv["counterparty"][:6]}).json()
    assert [d["fields"]["document_number"] for d in found] == [inv["document_number"]]
    assert len(client.get("/documents/search", params={"doc_type": "receipt"}).json()) == 1

    dl = client.get("/deadlines", params={"today": inv["issue_date"], "within_days": 60}).json()
    assert {"kind": "payment_due", "date": inv["due_date"]}.items() <= dl[0].items()
    dl = client.get("/deadlines", params={"today": ins["valid_from"], "within_days": 366}).json()
    assert any(d["kind"] == "expires" and d["date"] == ins["valid_until"] for d in dl)
