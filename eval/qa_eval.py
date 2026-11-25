#!/usr/bin/env python3
"""Evaluate the Q&A agent (service/docflow/agent.py) on questions generated from the test-set labels.

    python eval/qa_eval.py                              # DOCFLOW_AGENT_MODEL or claude-haiku-5-5
    python eval/qa_eval.py --model claude-haiku-5-5

The 50 test documents are loaded from their ground-truth labels into a temporary SQLite database
(no extraction calls), so the agent's answers are checked against known values:
  * exact facts: amount / expiry / due date of a document picked by its number (pl / en questions; English for uk documents)
  * lists: payments due in the next 14 days, contracts expiring in a month (every expected #id cited)
  * aggregates: number of receipts
  * grounding: a question about a company that is not in the database (no invented dates)
A question passes when every expected string appears in the answer.
Writes eval/results/qa_<model>.md.
"""
import argparse
import json
import random
import re
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "service"))

from docflow.agent import Agent  # noqa: E402
from docflow.config import Settings  # noqa: E402
from docflow.db import Document, make_sessionmaker  # noqa: E402
from docflow.queries import deadlines  # noqa: E402

TODAY = None  # chosen in pick_today(): a day with non-empty 14-day payment and 31-day expiry windows


def load_db(labels_dir: Path, url: str):
    sm = make_sessionmaker(url)
    labels = []
    with sm() as db:
        for i, f in enumerate(sorted(labels_dir.glob("*.json")), 1):
            lab = json.loads(f.read_text(encoding="utf-8"))
            lab["id"] = i
            labels.append(lab)
            fields = {k: lab[k] for k in Document.FIELD_NAMES}
            for k in ("issue_date", "due_date", "valid_from", "valid_until"):
                fields[k] = date.fromisoformat(fields[k]) if fields[k] else None
            db.add(Document(id=i, sha256=f"{i:064d}", filename=lab["_meta"]["file"], media_type="application/pdf",
                            size_bytes=1, storage_path="-", source="eval", status="auto_accepted", confidence=0.95,
                            issues=[], **fields))
        db.commit()
    return sm, labels


def amount_variants(x: float) -> list[str]:
    """10805.08 -> ['10805.08', '10805,08'] compared after removing spaces / thousands separators."""
    s = f"{x:.2f}"
    return [s, s.replace(".", ",")]


def norm(text: str) -> str:
    # "10 805,08" / "10,805.08" -> "10805,08" / "10805.08"; keeps dates intact
    t = re.sub(r"(?<=\d)[\s  ](?=\d{3}\b)", "", text)
    return re.sub(r"(?<=\d),(?=\d{3}\b)", "", t)


def pick_today(sm) -> date:
    """Latest day in the data range where both list questions have expected documents (as many as possible)."""
    best, day = (0, None), date(2025, 3, 1)
    with sm() as db:
        while day <= date(2026, 11, 30):
            n_due = len(deadlines(db, day, within_days=14, kind="payment_due"))
            n_exp = len(deadlines(db, day, within_days=31, kind="expires"))
            score = min(n_due, 4) + min(n_exp, 4)
            if n_due >= 1 and n_exp >= 1 and score >= best[0]:
                best = (score, day)
            day += timedelta(days=1)
    return best[1]


def questions(labels, sm):
    rng = random.Random(7)
    by = lambda t: [l for l in labels if l["doc_type"] == t and l["document_number"]]  # noqa: E731
    qs = []
    for lab in rng.sample(by("insurance"), 3):
        q = {"uk": f"When does insurance policy {lab['document_number']} expire?",
             "pl": f"Do kiedy obowiązuje polisa nr {lab['document_number']}?",
             "en": f"When does insurance policy {lab['document_number']} expire?"}[lab["language"]]
        qs.append({"q": q, "kind": "fact", "expect": [lab["valid_until"]]})
    for lab in rng.sample(by("invoice") + by("utility_bill"), 4):
        qs.append({"q": f"How much has to be paid for document {lab['document_number']}, and by what date?",
                   "kind": "fact", "expect": [lab["due_date"]], "amount": lab["total_amount"]})
    for lab in rng.sample(by("contract"), 2):
        qs.append({"q": f"What is the total value of contract {lab['document_number']}, and who is it with?",
                   "kind": "fact", "expect": [], "amount": lab["total_amount"], "any_of": [lab["counterparty"]]})
    with sm() as db:
        due = deadlines(db, TODAY, within_days=14, kind="payment_due")
        exp = deadlines(db, TODAY, within_days=31, kind="expires")
    qs.append({"q": "Which payments are due in the next 14 days?", "kind": "list",
               "expect": [f"#{d['document_id']}" for d in due], "n": len(due)})
    qs.append({"q": "Which contracts or policies expire within the next month?", "kind": "list",
               "expect": [f"#{d['document_id']}" for d in exp], "n": len(exp)})
    n_receipts = sum(l["doc_type"] == "receipt" for l in labels)
    qs.append({"q": "How many receipts are in the database?", "kind": "aggregate", "expect": [str(n_receipts)]})
    qs.append({"q": "When does the Allianz insurance expire?", "kind": "grounding", "expect": [],
               "forbid": sorted({l["valid_until"] for l in labels if l["valid_until"]})})
    return qs


def score(item, answer):
    a = norm(answer)
    ok = all(e in a for e in item["expect"])
    if "amount" in item:
        ok &= any(v in a for v in amount_variants(item["amount"]))
    if "any_of" in item:
        ok &= any(x.lower() in a.lower() for x in item["any_of"])
    if "forbid" in item:
        ok &= not any(x in a for x in item["forbid"])
    if item["kind"] == "aggregate":  # the first number stated must be the right one (no "8... no, 9")
        first = re.search(r"\d+", a)
        ok &= bool(first) and first.group() == item["expect"][0]
    return ok


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=Settings().agent_model)
    ap.add_argument("--effort", default=Settings().agent_effort or None)
    ap.add_argument("--labels", default=str(HERE / "dataset_test" / "labels"))
    a = ap.parse_args()

    global TODAY
    tmp = tempfile.mkdtemp()
    sm, labels = load_db(Path(a.labels), f"sqlite:///{Path(tmp, 'qa.db').as_posix()}")
    TODAY = pick_today(sm)
    print(f"today = {TODAY}")
    agent = Agent(sm, a.model, effort=a.effort)
    rows, cost, lat = [], 0.0, 0.0
    for item in questions(labels, sm):
        r = agent.ask(item["q"], TODAY)
        ok = score(item, r.answer) and not r.error
        cost += r.cost_usd
        lat += r.latency_s
        tools = ", ".join(f"{t['name']}({json.dumps({k: v for k, v in t['input'].items() if v is not None}, ensure_ascii=False)})"
                          for t in r.tool_calls)
        rows.append((ok, item, r, tools))
        print(f"{'PASS' if ok else 'FAIL'} [{item['kind']}] {item['q']}\n     tools: {tools}\n     "
              f"answer: {r.answer[:300].replace(chr(10), ' | ')}\n")

    n_ok = sum(r[0] for r in rows)
    L = [f"# Q&A agent eval: {a.model} (effort {a.effort or 'default'})", "",
         f"Test-set documents loaded from labels; today = {TODAY}. Pass = every expected value appears in the answer.", "",
         f"**{n_ok}/{len(rows)} passed** · cost ${cost:.3f} total, ${cost / len(rows):.4f} per question · "
         f"avg latency {lat / len(rows):.1f} s", "",
         "| # | Kind | Question | Pass | Tool calls | Turns |", "|---|---|---|---|---|---|"]
    for i, (ok, item, r, tools) in enumerate(rows, 1):
        L.append(f"| {i} | {item['kind']} | {item['q']} | {'✅' if ok else '❌'} | `{tools}` | {r.turns} |")
    L += ["", "## Answers", ""]
    for i, (ok, item, r, _) in enumerate(rows, 1):
        exp = ", ".join(item["expect"] + ([f"{item['amount']:.2f}"] if "amount" in item else []))
        L += [f"**{i}. {item['q']}** {'✅' if ok else '❌'}  ", f"expected: {exp or '(no invented dates)'}", "",
              "> " + r.answer.replace("\n", "\n> "), ""]
    out = HERE / "results" / f"qa_{a.model}.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"{n_ok}/{len(rows)} passed, ${cost:.3f}, avg {lat / len(rows):.1f}s -> {out}")


if __name__ == "__main__":
    main()
