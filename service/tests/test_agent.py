"""Agent loop and reminder offsets, with a scripted fake Claude client (no API calls)."""
from datetime import date, timedelta
from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient

from docflow.agent import TOOLS, Agent
from docflow.config import Settings
from docflow.main import create_app

from test_api import INSURANCE, INVOICE, RECEIPT, FakeExtractor, label, upload


def tool_use(name, args, id_="tu1"):
    return NS(type="tool_use", name=name, input=args, id=id_)


def text(t):
    return NS(type="text", text=t)


def response(*content, stop="end_turn"):
    return NS(content=list(content), stop_reason=stop, model="claude-sonnet-5-5",
              usage=NS(input_tokens=1000, output_tokens=100))


class ScriptedClient:
    """Plays back responses; records every request so tests can inspect what the agent sent."""

    def __init__(self, *responses):
        self.responses, self.requests = list(responses), []
        self.beta = NS(messages=NS(create=self.create))
        self.messages = NS(create=self.create)

    def create(self, **kw):
        self.requests.append({**kw, "messages": list(kw["messages"])})  # snapshot: the agent keeps appending
        return self.responses.pop(0)


@pytest.fixture
def stack(tmp_path):
    fake = FakeExtractor()
    settings = Settings(database_url=f"sqlite:///{(tmp_path / 't.db').as_posix()}", storage_dir=tmp_path / "f",
                        api_key="k")
    app = create_app(settings, extractor=fake)
    client = TestClient(app, headers={"X-API-Key": "k"})
    for n in (INVOICE, INSURANCE, RECEIPT):
        fake.register(n)
        upload(client, n, source="telegram", source_ref=f"42:{n[:3]}")
    return app, client


def test_tools_are_strict_and_fully_required():
    for t in TOOLS:
        s = t["input_schema"]
        assert t["strict"] and s["additionalProperties"] is False
        assert set(s["required"]) == set(s["properties"])


def test_agent_uses_tool_and_answers(stack):
    app, client = stack
    ins = label(INSURANCE)
    scripted = ScriptedClient(
        response(tool_use("list_deadlines", {"within_days": 366, "past_days": 0, "kind": "expires"}), stop="tool_use"),
        response(text(f"Policy #2 is valid until {ins['valid_until']}.")),
    )
    app.state.agent = Agent(app.state.sessionmaker, "claude-sonnet-5-5", client=scripted)
    r = client.post("/ask", json={"question": "When does the insurance expire?", "today": ins["valid_from"],
                                  "chat_ref": "42"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert ins["valid_until"] in body["answer"] and body["turns"] == 2
    assert body["tool_calls"] == [{"name": "list_deadlines",
                                   "input": {"within_days": 366, "past_days": 0, "kind": "expires"}, "results": 1}]
    # the tool result sent back to Claude contains the policy's expiry date
    tool_result = scripted.requests[1]["messages"][-1]["content"][0]
    assert tool_result["type"] == "tool_result" and ins["valid_until"] in tool_result["content"]
    assert ins["valid_from"] in scripted.requests[0]["system"]      # today is in the system prompt
    stats = client.get("/stats").json()["agent"]
    assert stats["count"] == 1 and stats["cost_usd"] > 0


def test_agent_search_excludes_rejected(stack):
    app, client = stack
    inv = label(INVOICE)
    client.post("/documents/1/review", json={"action": "reject"})
    agent = Agent(app.state.sessionmaker, "claude-sonnet-5-5", client=ScriptedClient())
    found = agent.run_tool("search_documents", {"query": inv["counterparty"][:5], "doc_type": None, "date_from": None,
                                                "date_to": None, "limit": None}, date.today())
    assert found == {"count": 0, "documents": []}


def test_agent_recovers_from_bad_tool_args(stack):
    app, client = stack
    scripted = ScriptedClient(
        response(tool_use("search_documents", {"query": None, "doc_type": None, "date_from": "not-a-date",
                                               "date_to": None, "limit": 5}), stop="tool_use"),
        response(text("No documents found.")),
    )
    app.state.agent = Agent(app.state.sessionmaker, "claude-sonnet-5-5", client=scripted)
    body = client.post("/ask", json={"question": "Documents from last year?"}).json()
    assert "error" in body["tool_calls"][0]
    assert scripted.requests[1]["messages"][-1]["content"][0]["is_error"] is True
    assert body["answer"] == "No documents found."


def test_agent_api_failure_returns_friendly_answer(stack):
    app, client = stack

    class Broken:
        def create(self, **kw):
            raise RuntimeError("overloaded")
    broken = NS(messages=Broken(), beta=NS(messages=Broken()))
    app.state.agent = Agent(app.state.sessionmaker, "claude-sonnet-5-5", client=broken)
    body = client.post("/ask", json={"question": "What should I pay?"}).json()
    assert "unavailable" in body["answer"] and "overloaded" in body["error"]


def test_reminder_offsets(stack):
    _, client = stack
    inv = label(INVOICE)
    due = date.fromisoformat(inv["due_date"])
    seven_before = (due - timedelta(days=7)).isoformat()
    r = client.get("/deadlines", params={"today": seven_before, "within_days": 7, "days_left": "7,3,1,0"}).json()
    assert [x["kind"] for x in r] == ["payment_due"] and r[0]["days_left"] == 7
    assert r[0]["source"] == "telegram" and r[0]["source_ref"].startswith("42:")
    r = client.get("/deadlines", params={"today": (due - timedelta(days=5)).isoformat(), "within_days": 7,
                                         "days_left": "7,3,1,0"}).json()
    assert r == []
    overdue = client.get("/deadlines", params={"today": (due + timedelta(days=2)).isoformat(), "within_days": 0,
                                               "past_days": 5}).json()
    assert overdue and overdue[0]["days_left"] == -2
    assert client.get("/deadlines", params={"days_left": "a,b"}).status_code == 422
