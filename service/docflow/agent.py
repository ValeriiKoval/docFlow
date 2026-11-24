"""Q&A agent: Claude answers questions about stored documents using two read-only tools.

    "When does the insurance expire?"  ->  list_deadlines(kind="expires", ...) -> "Policy #12 ... valid until 2027-08-08"

A plain Messages API tool-use loop (no framework): the tools are SQL queries in this service,
answers are short and single-turn, so the loop lives here next to the data.
Tools are strict (schema-valid arguments); results are compact JSON; every answer is logged
in `agent_runs` with the tool calls, tokens and cost.
"""
import json
import time
from dataclasses import dataclass, field
from datetime import date

from .extraction import FALLBACK_BETA, cost_usd
from .queries import VISIBLE, count_documents, deadlines, search_documents

DOC_TYPES = ["invoice", "contract", "insurance", "receipt", "utility_bill", "other"]
NULLABLE = lambda t, **kw: {"anyOf": [{"type": t, **kw}, {"type": "null"}]}  # noqa: E731

TOOLS = [
    {
        "name": "search_documents",
        "description": (
            "Find stored documents. Filters combine with AND; pass null to skip one. `query` is a case-insensitive "
            "substring of counterparty, recipient or document number (e.g. a company name). Dates filter by "
            "issue_date. Returns {count: total number of matches, documents: newest first (at most `limit`, "
            "default 20, max 50) with all extracted fields}. Use `count` for \"how many\" questions."),
        "strict": True,
        "input_schema": {
            "type": "object", "additionalProperties": False,
            "properties": {
                "query": NULLABLE("string"),
                "doc_type": {"anyOf": [{"type": "string", "enum": DOC_TYPES}, {"type": "null"}]},
                "date_from": NULLABLE("string", format="date"),
                "date_to": NULLABLE("string", format="date"),
                "limit": NULLABLE("integer"),
            },
            "required": ["query", "doc_type", "date_from", "date_to", "limit"],
        },
    },
    {
        "name": "list_deadlines",
        "description": (
            "Upcoming payment deadlines (kind=payment_due, from due_date of invoices and utility bills) and "
            "expiries (kind=expires, from valid_until of insurance policies and contracts), soonest first. "
            "Window: from today - past_days to today + within_days. Use past_days > 0 for overdue payments "
            "or recently expired documents."),
        "strict": True,
        "input_schema": {
            "type": "object", "additionalProperties": False,
            "properties": {
                "within_days": {"type": "integer", "description": "0-366"},
                "past_days": {"type": "integer", "description": "0-366"},
                "kind": {"type": "string", "enum": ["payment_due", "expires", "any"]},
            },
            "required": ["within_days", "past_days", "kind"],
        },
    },
]

SYSTEM = """You are DocFlow, an assistant for a small office's incoming documents (invoices, contracts, insurance policies, receipts, utility bills). Today is {today}.

- Answer only from the tools' results. Never invent documents, amounts, dates or companies. If nothing matches, say so and suggest what to check.
- Call tools as needed; prefer one well-filtered call. For "when does X expire / what to pay soon" use list_deadlines; for "find / how much / which documents" use search_documents.
- Cite each document you mention as #id. Give amounts with currency and dates as YYYY-MM-DD; for deadlines also say how many days are left.
- Documents with status needs_review were not yet checked by a person: mention that when you rely on them.
- Reply in the language of the question (English by default). Telegram chat: short plain text, no Markdown, no tables; a few lines or a short list with "•"."""


def _compact(d) -> dict:
    return {"id": d.id, "status": d.status, "doc_type": d.doc_type, "counterparty": d.counterparty,
            "recipient": d.recipient, "document_number": d.document_number, "issue_date": d.issue_date,
            "total_amount": d.total_amount, "currency": d.currency, "due_date": d.due_date,
            "valid_from": d.valid_from, "valid_until": d.valid_until}


def _date(v):
    return date.fromisoformat(v) if v else None


@dataclass
class AgentResult:
    answer: str
    model: str
    served_by: str = ""
    tool_calls: list = field(default_factory=list)
    turns: int = 0
    usage: dict = field(default_factory=lambda: {"input_tokens": 0, "output_tokens": 0})
    latency_s: float = 0.0
    error: str | None = None

    @property
    def cost_usd(self) -> float:
        return cost_usd(self.served_by or self.model, self.usage["input_tokens"], self.usage["output_tokens"])


class Agent:
    def __init__(self, sessionmaker, model: str, client=None, effort: str | None = "low", max_turns: int = 6):
        self.sessionmaker, self.model, self.effort, self.max_turns = sessionmaker, model, effort, max_turns
        if client is None:
            import anthropic
            client = anthropic.Anthropic(max_retries=4)
        self.client = client

    def run_tool(self, name: str, args: dict, today: date):
        with self.sessionmaker() as db:
            if name == "search_documents":
                limit = max(1, min(int(args.get("limit") or 20), 50))
                f = dict(q=args.get("query"), doc_type=args.get("doc_type"), date_from=_date(args.get("date_from")),
                         date_to=_date(args.get("date_to")), statuses=VISIBLE)
                docs = search_documents(db, limit=limit, **f)
                return {"count": count_documents(db, **f), "documents": [_compact(d) for d in docs]}
            if name == "list_deadlines":
                kind = args.get("kind")
                return deadlines(db, today, within_days=max(0, min(int(args.get("within_days", 30)), 366)),
                                 past_days=max(0, min(int(args.get("past_days", 0)), 366)),
                                 kind=None if kind in (None, "any") else kind)
        raise ValueError(f"unknown tool {name}")

    def ask(self, question: str, today: date | None = None) -> AgentResult:
        today = today or date.today()
        res, t0 = AgentResult(answer="", model=self.model), time.time()
        kwargs = dict(model=self.model, max_tokens=4000, system=SYSTEM.format(today=today.isoformat()), tools=TOOLS)
        if self.effort:
            kwargs["output_config"] = {"effort": self.effort}
        use_fallback = not self.model.startswith("claude-haiku")
        messages = [{"role": "user", "content": question}]
        try:
            for turn in range(1, self.max_turns + 1):
                if use_fallback:
                    r = self.client.beta.messages.create(betas=[FALLBACK_BETA], fallbacks="default",
                                                         messages=messages, **kwargs)
                else:
                    r = self.client.messages.create(messages=messages, **kwargs)
                res.turns, res.served_by = turn, r.model
                res.usage["input_tokens"] += r.usage.input_tokens
                res.usage["output_tokens"] += r.usage.output_tokens
                if r.stop_reason == "refusal":
                    res.answer = "I cannot answer this question."
                    res.error = "refusal"
                    break
                # keep the full content (incl. thinking blocks) so the next turn continues the same reasoning
                messages.append({"role": "assistant", "content": r.content})
                uses = [b for b in r.content if b.type == "tool_use"]
                if not uses:
                    res.answer = "".join(b.text for b in r.content if b.type == "text").strip()
                    break
                results = []
                for u in uses:
                    try:
                        out = self.run_tool(u.name, u.input, today)
                        n = len(out["documents"]) if isinstance(out, dict) else len(out)
                        res.tool_calls.append({"name": u.name, "input": u.input, "results": n})
                        results.append({"type": "tool_result", "tool_use_id": u.id,
                                        "content": json.dumps(out, ensure_ascii=False, default=str)})
                    except Exception as e:  # bad arguments: let the model recover
                        res.tool_calls.append({"name": u.name, "input": u.input, "error": str(e)})
                        results.append({"type": "tool_result", "tool_use_id": u.id, "is_error": True,
                                        "content": f"{type(e).__name__}: {e}"})
                messages.append({"role": "user", "content": results})
            else:
                res.error = f"no final answer after {self.max_turns} turns"
                res.answer = "Could not find an answer. Try rephrasing the question."
        except Exception as e:  # API failure after SDK retries
            res.error = f"{type(e).__name__}: {e}"[:1000]
            res.answer = "The service is temporarily unavailable, please try again later."
        res.latency_s = time.time() - t0
        return res
