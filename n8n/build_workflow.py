#!/usr/bin/env python3
"""Build n8n/docflow_telegram.json from n8n/code/*.js.

The JSON is the importable artefact (n8n UI: Import from file, or `n8n import:workflow`).
The Code-node sources live in n8n/code/ so they can be reviewed and diffed as JavaScript.
If you edit the workflow in the n8n UI, export it back over the JSON.

    python n8n/build_workflow.py

Flow:
  Webhook /webhook/telegram ─► IF secret header ok ─► Parse update ─► Switch(kind)
    file        ─► getFile ─► download ─► POST /extract ─► Format result ─────────┐
    review      ─► POST /documents/{id}/review (approve|reject) ─► Format review ─┤
    fix_prompt  ─► Fix prompt (force_reply) ──────────────────────────────────────┤
    correction  ─► POST /documents/{id}/review (correct) ─► Format review ────────┤
    help        ─► Help ──────────────────────────────────────────────────────────┴─► Telegram API
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
ROUTES = ["file", "review", "fix_prompt", "correction", "help", "ignore"]

nodes, connections = [], {}


def node(name, type_, version, params, pos, **extra):
    nodes.append({"id": f"docflow-{len(nodes) + 1:02d}", "name": name, "type": type_, "typeVersion": version,
                  "position": pos, "parameters": params, **extra})
    return name


def code(name, file, pos, common=True):
    src = (CODE / file).read_text(encoding="utf-8")
    return node(name, "n8n-nodes-base.code", 2, {"jsCode": (COMMON + "\n" + src) if common else src}, pos)


def http(name, pos, **params):
    return node(name, "n8n-nodes-base.httpRequest", 4.2, {"options": {}, **params}, pos)


def link(src, dst, out=0):
    outs = connections.setdefault(src, {"main": []})["main"]
    while len(outs) <= out:
        outs.append([])
    outs[out].append({"node": dst, "type": "main", "index": 0})


# ---- nodes -----------------------------------------------------------------------
webhook = node("Telegram webhook", "n8n-nodes-base.webhook", 2,
               {"httpMethod": "POST", "path": "telegram", "responseMode": "onReceived", "options": {}},
               [0, 300], webhookId="7d1c2b3a-docf-4f10-9a11-telegram0001")
secret = node("Secret ok?", "n8n-nodes-base.if", 2.2, {
    "conditions": {
        "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
        "conditions": [{"id": "secret", "operator": {"type": "string", "operation": "equals"},
                        "leftValue": "={{ $json.headers['x-telegram-bot-api-secret-token'] }}",
                        "rightValue": "={{ $env.TELEGRAM_WEBHOOK_SECRET }}"}],
        "combinator": "and"},
    "options": {}}, [220, 300])
parse = code("Parse update", "parse_update.js", [440, 300], common=False)
route = node("Route", "n8n-nodes-base.switch", 3.2, {
    "mode": "expression", "numberOutputs": len(ROUTES),
    "output": "={{ " + json.dumps({k: i for i, k in enumerate(ROUTES)}) + "[$json.kind] ?? " + str(len(ROUTES) - 1) + " }}",
    "options": {}}, [660, 300])

get_file = http("Telegram getFile", [900, 0], url=TG + "/getFile", sendQuery=True,
                queryParameters={"parameters": [{"name": "file_id", "value": "={{ $json.file_id }}"}]})
download = http("Download file", [1120, 0],
                url="={{ $env.TELEGRAM_API_BASE }}/file/bot{{ $env.TELEGRAM_BOT_TOKEN }}/{{ $json.result.file_path }}",
                options={"response": {"response": {"responseFormat": "file", "outputPropertyName": "data"}}})
extract = http("POST /extract", [1340, 0], method="POST", url=API + "/extract",
               sendHeaders=True, headerParameters=KEY_HEADER, sendBody=True, contentType="multipart-form-data",
               bodyParameters={"parameters": [
                   {"parameterType": "formBinaryData", "name": "file", "inputDataFieldName": "data"},
                   {"name": "source", "value": "telegram"},
                   {"name": "source_ref",
                    "value": "={{ $('Parse update').first().json.chat_id }}:{{ $('Parse update').first().json.message_id }}"}]},
               options={"timeout": 180000, **FULL_NEVER_ERROR})
fmt_result = code("Format result", "format_result.js", [1560, 0])

review_body = ("={{ JSON.stringify({action: $json.action, fields: $json.fields || {}, "
               "reviewer: $json.reviewer}) }}")
review = http("POST review", [900, 200], method="POST",
              url=API + "/documents/{{ $json.doc_id }}/review", sendHeaders=True, headerParameters=KEY_HEADER,
              sendBody=True, specifyBody="json", jsonBody=review_body, options=FULL_NEVER_ERROR)
correct = http("POST correction", [900, 500], method="POST",
               url=API + "/documents/{{ $json.doc_id }}/review", sendHeaders=True, headerParameters=KEY_HEADER,
               sendBody=True, specifyBody="json", jsonBody=review_body, options=FULL_NEVER_ERROR)
fmt_review = code("Format review", "format_review.js", [1560, 300])
fix = code("Fix prompt", "fix_prompt.js", [1560, 400])
help_ = code("Help", "help.js", [1560, 600])
telegram = http("Telegram API", [1800, 300], method="POST", url=TG + "/{{ $json.method }}",
                sendBody=True, specifyBody="json", jsonBody="={{ JSON.stringify($json.payload) }}",
                options=FULL_NEVER_ERROR)

# ---- wiring ----------------------------------------------------------------------
link(webhook, secret)
link(secret, parse, 0)             # false branch (index 1) left empty: unauthenticated calls are dropped
link(parse, route)
link(route, get_file, ROUTES.index("file"))
link(route, review, ROUTES.index("review"))
link(route, fix, ROUTES.index("fix_prompt"))
link(route, correct, ROUTES.index("correction"))
link(route, help_, ROUTES.index("help"))
link(get_file, download)
link(download, extract)
link(extract, fmt_result)
link(review, fmt_review)
link(correct, fmt_review)
for n in (fmt_result, fmt_review, fix, help_):
    link(n, telegram)

workflow = {
    "id": "DocflowTgIntake1",
    "name": "DocFlow: Telegram intake and review",
    "nodes": nodes,
    "connections": connections,
    "active": False,
    "settings": {"executionOrder": "v1", "saveDataSuccessExecution": "all", "saveManualExecutions": True,
                 "timezone": "Europe/Kyiv"},
    "pinData": {},
    "tags": [],
}

out = HERE / "docflow_telegram.json"
out.write_text(json.dumps(workflow, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"{out.relative_to(HERE.parent)}: {len(nodes)} nodes")
