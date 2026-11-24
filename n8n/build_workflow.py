#!/usr/bin/env python3
"""Build the importable n8n workflows from n8n/code/*.js.

    python n8n/build_workflow.py      # -> n8n/docflow_telegram.json, n8n/docflow_reminders.json

The JSON files are the artefacts (n8n UI: Import from file, or `n8n import:workflow`; docker compose
imports and publishes them on start). Code-node sources live in n8n/code/ so they can be reviewed
and diffed as JavaScript. If you edit a workflow in the n8n UI, export it back over its JSON.

1. DocFlow: Telegram intake and review
   Webhook /webhook/telegram ─► Secret ok? ─► Parse update ─► Chat allowed? ─┬► Route(kind)
                                                                            └► Access denied
     file        ─► getFile ─► download ─► POST /extract ─► Format result ─────────┐
     review      ─► POST /documents/{id}/review (approve|reject) ─► Format review ─┤
     fix_prompt  ─► Fix prompt (force_reply) ──────────────────────────────────────┤
     correction  ─► POST /documents/{id}/review (correct) ─► Format review ────────┤
     question    ─► Typing ; POST /ask (Q&A agent) ─► Format answer ───────────────┤
     help        ─► Help ──────────────────────────────────────────────────────────┴─► Telegram API

2. DocFlow: deadline reminders
   Every day 09:00 ─┐
   Webhook /webhook/reminders/run (X-API-Key) ─► Key ok? ─┴─► GET /deadlines?days_left=7,3,1,0
     ─► Format reminders (one message per chat) ─► Telegram API
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODE = HERE / "code"
COMMON = (CODE / "common.js").read_text(encoding="utf-8")

API = "={{ $env.DOCFLOW_API_URL }}"
TG = "={{ $env.TELEGRAM_API_BASE }}/bot{{ $env.TELEGRAM_BOT_TOKEN }}"
KEY_HEADER = {"parameters": [{"name": "X-API-Key", "value": "={{ $env.SERVICE_API_KEY }}"}]}
FULL_NEVER_ERROR = {"response": {"response": {"fullResponse": True, "neverError": True}}}


class Workflow:
    def __init__(self, wid, name):
        self.wid, self.name, self.nodes, self.connections = wid, name, [], {}

    def node(self, name, type_, version, params, pos, **extra):
        self.nodes.append({"id": f"{self.wid}-{len(self.nodes) + 1:02d}", "name": name, "type": type_,
                           "typeVersion": version, "position": pos, "parameters": params, **extra})
        return name

    def code(self, name, file, pos, common=True):
        src = (CODE / file).read_text(encoding="utf-8")
        return self.node(name, "n8n-nodes-base.code", 2, {"jsCode": (COMMON + "\n" + src) if common else src}, pos)

    def http(self, name, pos, **params):
        return self.node(name, "n8n-nodes-base.httpRequest", 4.2, {"options": {}, **params}, pos)

    def if_(self, name, left, right_or_expr, pos, operation="equals"):
        cond = {"id": name, "leftValue": left, "operator": {"type": "string", "operation": operation}}
        if operation == "equals":
            cond["rightValue"] = right_or_expr
        else:  # boolean expression in leftValue
            cond["operator"] = {"type": "boolean", "operation": "true", "singleValue": True}
        return self.node(name, "n8n-nodes-base.if", 2.2, {
            "conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose",
                                       "version": 2},
                           "conditions": [cond], "combinator": "and"},
            "options": {}}, pos)

    def link(self, src, dst, out=0):
        outs = self.connections.setdefault(src, {"main": []})["main"]
        while len(outs) <= out:
            outs.append([])
        outs[out].append({"node": dst, "type": "main", "index": 0})

    def save(self, filename):
        wf = {"id": self.wid, "name": self.name, "nodes": self.nodes, "connections": self.connections,
              "active": False, "pinData": {}, "tags": [],
              "settings": {"executionOrder": "v1", "saveDataSuccessExecution": "all", "saveManualExecutions": True,
                           "timezone": "Europe/Kyiv"}}
        out = HERE / filename
        out.write_text(json.dumps(wf, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{out.relative_to(HERE.parent)}: {len(self.nodes)} nodes")


# ---- 1. Telegram intake, review and Q&A ------------------------------------------
ROUTES = ["file", "review", "fix_prompt", "correction", "question", "help", "ignore"]
w = Workflow("DocflowTgIntake1", "DocFlow: Telegram intake, review and Q&A")
webhook = w.node("Telegram webhook", "n8n-nodes-base.webhook", 2,
                 {"httpMethod": "POST", "path": "telegram", "responseMode": "onReceived", "options": {}},
                 [0, 300], webhookId="7d1c2b3a-d0cf-4f10-9a11-7e1e6a000001")
secret = w.if_("Secret ok?", "={{ $json.headers['x-telegram-bot-api-secret-token'] }}",
               "={{ $env.TELEGRAM_WEBHOOK_SECRET }}", [220, 300])
parse = w.code("Parse update", "parse_update.js", [440, 300], common=False)
allowed = w.if_("Chat allowed?",
                "={{ !$env.TELEGRAM_ALLOWED_CHAT_IDS || $env.TELEGRAM_ALLOWED_CHAT_IDS.split(',')"
                ".map(s => s.trim()).includes(String($json.chat_id)) }}", None, [660, 300], operation="true")
denied = w.code("Access denied", "access_denied.js", [1560, 800])
route = w.node("Route", "n8n-nodes-base.switch", 3.2, {
    "mode": "expression", "numberOutputs": len(ROUTES),
    "output": "={{ " + json.dumps({k: i for i, k in enumerate(ROUTES)}) + "[$json.kind] ?? " + str(len(ROUTES) - 1) + " }}",
    "options": {}}, [880, 300])

get_file = w.http("Telegram getFile", [1120, 0], url=TG + "/getFile", sendQuery=True,
                  queryParameters={"parameters": [{"name": "file_id", "value": "={{ $json.file_id }}"}]})
download = w.http("Download file", [1340, 0],
                  url="={{ $env.TELEGRAM_API_BASE }}/file/bot{{ $env.TELEGRAM_BOT_TOKEN }}/{{ $json.result.file_path }}",
                  options={"response": {"response": {"responseFormat": "file", "outputPropertyName": "data"}}})
extract = w.http("POST /extract", [1560, 0], method="POST", url=API + "/extract",
                 sendHeaders=True, headerParameters=KEY_HEADER, sendBody=True, contentType="multipart-form-data",
                 bodyParameters={"parameters": [
                     {"parameterType": "formBinaryData", "name": "file", "inputDataFieldName": "data"},
                     {"name": "source", "value": "telegram"},
                     {"name": "source_ref",
                      "value": "={{ $('Parse update').first().json.chat_id }}:{{ $('Parse update').first().json.message_id }}"}]},
                 options={"timeout": 180000, **FULL_NEVER_ERROR})
fmt_result = w.code("Format result", "format_result.js", [1780, 0])

review_body = "={{ JSON.stringify({action: $json.action, fields: $json.fields || {}, reviewer: $json.reviewer}) }}"
review = w.http("POST review", [1120, 200], method="POST", url=API + "/documents/{{ $json.doc_id }}/review",
                sendHeaders=True, headerParameters=KEY_HEADER, sendBody=True, specifyBody="json",
                jsonBody=review_body, options=FULL_NEVER_ERROR)
correct = w.http("POST correction", [1120, 400], method="POST", url=API + "/documents/{{ $json.doc_id }}/review",
                 sendHeaders=True, headerParameters=KEY_HEADER, sendBody=True, specifyBody="json",
                 jsonBody=review_body, options=FULL_NEVER_ERROR)
fmt_review = w.code("Format review", "format_review.js", [1780, 300])
fix = w.code("Fix prompt", "fix_prompt.js", [1780, 450])

typing = w.code("Typing", "typing.js", [1120, 550], common=False)
ask = w.http("POST /ask", [1340, 650], method="POST", url=API + "/ask", sendHeaders=True,
             headerParameters=KEY_HEADER, sendBody=True, specifyBody="json",
             jsonBody="={{ JSON.stringify({question: $json.question, chat_ref: String($json.chat_id)}) }}",
             options={"timeout": 120000, **FULL_NEVER_ERROR})
fmt_answer = w.code("Format answer", "format_answer.js", [1780, 650], common=False)
help_ = w.code("Help", "help.js", [1780, 750])
telegram = w.http("Telegram API", [2020, 300], method="POST", url=TG + "/{{ $json.method }}",
                  sendBody=True, specifyBody="json", jsonBody="={{ JSON.stringify($json.payload) }}",
                  options=FULL_NEVER_ERROR)

w.link(webhook, secret)
w.link(secret, parse, 0)           # false branch left empty: unauthenticated calls are dropped
w.link(parse, allowed)
w.link(allowed, route, 0)
w.link(allowed, denied, 1)
for name, target in [("file", get_file), ("review", review), ("fix_prompt", fix), ("correction", correct),
                     ("question", typing), ("question", ask), ("help", help_)]:
    w.link(route, target, ROUTES.index(name))
w.link(get_file, download)
w.link(download, extract)
w.link(extract, fmt_result)
w.link(review, fmt_review)
w.link(correct, fmt_review)
w.link(ask, fmt_answer)
for n in (fmt_result, fmt_review, fix, typing, fmt_answer, help_, denied):
    w.link(n, telegram)
w.save("docflow_telegram.json")

# ---- 2. Daily deadline reminders ---------------------------------------------------
r = Workflow("DocflowReminder1", "DocFlow: deadline reminders")
cron = r.node("Every day 09:00", "n8n-nodes-base.scheduleTrigger", 1.2,
              {"rule": {"interval": [{"field": "cronExpression", "expression": "0 9 * * *"}]}}, [0, 200])
manual = r.node("Run now (webhook)", "n8n-nodes-base.webhook", 2,
                {"httpMethod": "POST", "path": "reminders/run", "responseMode": "onReceived", "options": {}},
                [0, 420], webhookId="7d1c2b3a-d0cf-4f10-9a11-7e1e6a000002")
key_ok = r.if_("Key ok?", "={{ $json.headers['x-api-key'] }}", "={{ $env.SERVICE_API_KEY }}", [220, 420])
fetch = r.http("GET /deadlines", [460, 300], url=API + "/deadlines", sendHeaders=True, headerParameters=KEY_HEADER,
               sendQuery=True, queryParameters={"parameters": [
                   {"name": "within_days", "value": "7"},
                   {"name": "days_left", "value": "={{ $env.REMINDER_DAYS || '7,3,1,0' }}"},
                   # manual runs may pass {"today": "YYYY-MM-DD"} for demos; the schedule uses Kyiv time
                   {"name": "today", "value": "={{ $json.body?.today ?? $now.setZone('Europe/Kyiv').toISODate() }}"}]})
fmt = r.code("Format reminders", "format_reminders.js", [700, 300])
send = r.http("Telegram API", [940, 300], method="POST", url=TG + "/{{ $json.method }}",
              sendBody=True, specifyBody="json", jsonBody="={{ JSON.stringify($json.payload) }}",
              options=FULL_NEVER_ERROR)
r.link(cron, fetch)
r.link(manual, key_ok)
r.link(key_ok, fetch, 0)
r.link(fetch, fmt)
r.link(fmt, send)
r.save("docflow_reminders.json")
