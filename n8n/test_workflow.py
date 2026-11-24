#!/usr/bin/env python3
"""End-to-end test of the n8n workflow against the mock Telegram API (real API service + Claude).

    python n8n/mock_telegram.py --root eval/dataset_test &
    TELEGRAM_API_BASE=http://host.docker.internal:8081 TELEGRAM_BOT_TOKEN=123:mock docker compose up -d
    python n8n/test_workflow.py

Sends fake Telegram updates to http://localhost:5678/webhook/telegram and checks what the bot "sent".
Makes ~2 Claude calls (~$0.03) unless the documents are already in the database (duplicates).
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
ENV = dotenv_values(ROOT / ".env")
WEBHOOK = "http://localhost:5678/webhook/telegram"
MOCK = "http://localhost:8081/_sent"
CHAT = {"id": 555, "type": "private"}
USER = {"id": 777, "is_bot": False, "first_name": "Test", "username": "reviewer_test"}

DS = ROOT / "eval/dataset_test"   # file_id = path relative to the mock's --root
CLEAN = next(p for p in sorted((DS / "pdf").glob("*invoice*"))).relative_to(DS).as_posix()
# a heavy scan the eval scored below the 0.6 threshold, so it lands in review
HEAVY = "scans/heavy/" + next(
    p.stem + ".pdf" for p in sorted((ROOT / "eval/predictions_test/claude-sonnet-5-5/extract_v2/heavy").glob("*.json"))
    if (json.loads(p.read_text(encoding="utf-8"))["extraction"] or {}).get("confidence", 1) < 0.5)
UPD = iter(range(1, 10**6))


def http(method, url, body=None, headers=None):
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
        return json.loads(raw) if raw else None


def post_update(update, secret=None):
    update = {"update_id": next(UPD), **update}
    hdr = {"X-Telegram-Bot-Api-Secret-Token": secret if secret is not None else ENV["TELEGRAM_WEBHOOK_SECRET"]}
    return http("POST", WEBHOOK, update, hdr)


def wait_sent(n, timeout=90):
    t0 = time.time()
    while time.time() - t0 < timeout:
        sent = http("GET", MOCK)
        if len(sent) >= n:
            time.sleep(1)  # let trailing calls land
            return http("GET", MOCK)
        time.sleep(1)
    return http("GET", MOCK)


def msg(mid, **kw):
    return {"message": {"message_id": mid, "date": int(time.time()), "chat": CHAT, "from": USER, **kw}}


def check(cond, what):
    print(("  ok   " if cond else "  FAIL ") + what)
    if not cond:
        check.failed += 1


check.failed = 0


def step(title, update, expect_calls, secret=None):
    print(f"\n# {title}")
    http("DELETE", MOCK)
    post_update(update, secret)
    sent = wait_sent(expect_calls)
    for s in sent:
        text = s["payload"].get("text", "")
        print(f"  -> {s['method']}: {text[:160].replace(chr(10), ' | ')}")
    return sent


def texts(sent):
    return "\n".join(s["payload"].get("text", "") for s in sent)


def doc_id_from(sent):
    import re
    for s in sent:
        m = re.search(r"#(\d+)", s["payload"].get("text", ""))
        if m:
            return int(m.group(1))


def main():
    sent = step("wrong secret is ignored", msg(1, text="hi"), 1, secret="wrong")
    check(sent == [], "no reply to an unauthenticated webhook call")

    sent = step("/start -> help", msg(2, text="/start"), 1)
    check(len(sent) == 1 and "Send a PDF" in sent[0]["payload"]["text"], "help text")

    sent = step(f"clean PDF {CLEAN}", msg(3, document={"file_id": CLEAN, "file_name": CLEAN}), 1)
    t = sent[0]["payload"]["text"] if sent else ""
    check(("✅" in t and "automatically" in t) or "already in the database" in t, "auto-accepted (or duplicate) reply")
    check(sent and sent[0]["payload"].get("reply_to_message_id") == 3, "replies to the original message")

    sent = step(f"heavy scan {HEAVY}", msg(4, document={"file_id": HEAVY, "file_name": HEAVY}), 1)
    t = sent[0]["payload"]["text"] if sent else ""
    did = doc_id_from(sent)
    kb = sent[0]["payload"].get("reply_markup", {}).get("inline_keyboard") if sent else None
    if "already in the database" in t:
        print("  (document already in DB from an earlier run; review buttons only on first upload)")
    else:
        check("⚠️" in t and kb is not None, "needs_review reply with buttons")

    sent = step("✏️ pressed", {"callback_query": {"id": "cb1", "from": USER, "data": f"fix:{did}",
                                                 "message": {"message_id": 900, "chat": CHAT}}}, 2)
    methods = [s["method"] for s in sent]
    check("answerCallbackQuery" in methods and any(s["payload"].get("reply_markup", {}).get("force_reply")
                                                   for s in sent), "asks for corrections with force_reply")

    sent = step("reply with corrections", msg(5, text="total_amount=1234.50\ndocument_number=TEST-1",
                                              reply_to_message={"message_id": 901, "chat": CHAT,
                                                                "text": f"✏️ Correcting document #{did}."}), 1)
    text = texts(sent)
    check("corrected" in text and "1234.50" in text, "correction saved and echoed")

    # n8n sends the items of one node in parallel, so the order of calls is not fixed
    sent = step("✅ pressed", {"callback_query": {"id": "cb2", "from": USER, "data": f"approve:{did}",
                                                 "message": {"message_id": 902, "chat": CHAT}}}, 3)
    methods = {s["method"] for s in sent}
    check({"answerCallbackQuery", "editMessageReplyMarkup"} <= methods, "callback answered, buttons removed")
    text = texts(sent)
    check("approved" in text and "reviewer_test" in text, "approval confirmed with reviewer name")

    print(f"\n{'ALL OK' if not check.failed else f'{check.failed} FAILED'}")
    sys.exit(1 if check.failed else 0)


if __name__ == "__main__":
    main()
