#!/usr/bin/env python3
"""Build the importable n8n workflows from n8n/code/*.js.

    python n8n/build_workflow.py                  # -> n8n/docflow_telegram.json, n8n/docflow_reminders.json
    python n8n/build_workflow.py --check          # exit 1 if the JSON is out of date with code/*.js
    python n8n/build_workflow.py --pull           # take Code-node JS edited in the running n8n back into code/
    python n8n/build_workflow.py --extract FILE   # same, from a workflow file downloaded from the n8n UI

The JSON files are the artefacts (n8n UI: Import from file, or `n8n import:workflow`; docker compose
imports and publishes them on start). Code-node sources live in n8n/code/ so they can be reviewed
and diffed as JavaScript; edit them there, not in the JSON. If you changed Code nodes in the n8n UI,
run --pull (or --extract on a downloaded file); both rebuild the JSON afterwards. Changes to anything
other than Code nodes (wiring, HTTP parameters) go into this file by hand. The pre-commit hook in
.githooks/ runs --check (enable once: git config core.hooksPath .githooks).

1. DocFlow: Telegram intake and review
   Webhook /webhook/telegram ─► Secret ok? ─► Parse update ─► Chat allowed? ─┬► Route(kind)
                                                                            └► Access denied
     file        ─► getFile ─► download ─► POST /extract ─► Format result ─────────┐
                    (getFile / download error ─► File error) ──────────────────────┤
     review      ─► POST /documents/{id}/review (approve|reject) ─► Format review ─┤
     fix_prompt  ─► Fix prompt (force_reply) ──────────────────────────────────────┤
     correction  ─► POST /documents/{id}/review (correct) ─► Format review ────────┤
     question    ─► Typing ; POST /ask (Q&A agent) ─► Format answer ───────────────┤
     help        ─► Help ──────────────────────────────────────────────────────────┴─► Telegram API

2. DocFlow: deadline reminders
   Every day 09:00 ─┐
   Webhook /webhook/reminders/run (REMINDERS_WEBHOOK_KEY) ─► Key ok? ─┴─► GET /deadlines?days_left=7,3,1,0
     ─► Format reminders (one message per chat) ─► Telegram API
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODE = HERE / "code"
COMMON = (CODE / "common.js").read_text(encoding="utf-8")

API = "={{ $env.DOCFLOW_API_URL }}"
TG = "={{ $env.TELEGRAM_API_BASE }}/bot{{ $env.TELEGRAM_BOT_TOKEN }}"
KEY_HEADER = {"parameters": [{"name": "X-API-Key", "value": "={{ $env.SERVICE_API_KEY }}"}]}
FULL_NEVER_ERROR = {"response": {"response": {"fullResponse": True, "neverError": True}}}


class Workflow:
    def __init__(self, filename, wid, name):
        self.filename, self.wid, self.name, self.nodes, self.connections = filename, wid, name, [], {}
        self.sources = {}  # Code node name -> (file in code/, common.js prepended?)

    def node(self, name, type_, version, params, pos, **extra):
        self.nodes.append({"id": f"{self.wid}-{len(self.nodes) + 1:02d}", "name": name, "type": type_,
                           "typeVersion": version, "position": pos, "parameters": params, **extra})
        return name

    def code(self, name, file, pos, common=True):
        src = (CODE / file).read_text(encoding="utf-8")
        self.sources[name] = (file, common)
        return self.node(name, "n8n-nodes-base.code", 2, {"jsCode": (COMMON + "\n" + src) if common else src}, pos)

    def http(self, name, pos, node_extra=None, **params):
        return self.node(name, "n8n-nodes-base.httpRequest", 4.2, {"options": {}, **params}, pos, **(node_extra or {}))

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

    def render(self):
        wf = {"id": self.wid, "name": self.name, "nodes": self.nodes, "connections": self.connections,
              "active": False, "pinData": {}, "tags": [],
              # successful runs are not stored: they carry document files and extracted personal data
              "settings": {"executionOrder": "v1", "saveDataSuccessExecution": "none", "saveDataErrorExecution": "all",
                           "saveManualExecutions": True, "timezone": "Europe/Kyiv"}}
        return json.dumps(wf, ensure_ascii=False, indent=2) + "\n"


def build():
    """Construct both workflows from code/*.js; returns [Workflow, ...] without writing anything."""
    # ---- 1. Telegram intake, review and Q&A ------------------------------------------
    ROUTES = ["file", "review", "fix_prompt", "correction", "question", "help", "ignore"]
    w = Workflow("docflow_telegram.json", "DocflowTgIntake1", "DocFlow: Telegram intake, review and Q&A")
    webhook = w.node("Telegram webhook", "n8n-nodes-base.webhook", 2,
                     {"httpMethod": "POST", "path": "telegram", "responseMode": "onReceived", "options": {}},
                     [0, 300], webhookId="7d1c2b3a-d0cf-4f10-9a11-7e1e6a000001")
    # an empty secret never matches: the workflow fails closed if TELEGRAM_WEBHOOK_SECRET is missing
    secret = w.if_("Secret ok?", "={{ !!$env.TELEGRAM_WEBHOOK_SECRET && $json.headers['x-telegram-bot-api-secret-token']"
                   " === $env.TELEGRAM_WEBHOOK_SECRET }}", None, [220, 300], operation="true")
    parse = w.code("Parse update", "parse_update.js", [440, 300], common=False)
    # empty allowlist = nobody (fail closed)
    allowed = w.if_("Chat allowed?",
                    "={{ ($env.TELEGRAM_ALLOWED_CHAT_IDS || '').split(',').map(s => s.trim()).filter(Boolean)"
                    ".includes(String($json.chat_id)) }}", None, [660, 300], operation="true")
    denied = w.code("Access denied", "access_denied.js", [1560, 800])
    route = w.node("Route", "n8n-nodes-base.switch", 3.2, {
        "mode": "expression", "numberOutputs": len(ROUTES),
        "output": "={{ " + json.dumps({k: i for i, k in enumerate(ROUTES)}) + "[$json.kind] ?? " + str(len(ROUTES) - 1) + " }}",
        "options": {}}, [880, 300])

    # errors (file > 20 MB for the Bot API, network) go to the second output -> "File error" reply
    on_error = {"onError": "continueErrorOutput"}
    get_file = w.http("Telegram getFile", [1120, 0], node_extra=on_error, url=TG + "/getFile", sendQuery=True,
                      queryParameters={"parameters": [{"name": "file_id", "value": "={{ $json.file_id }}"}]})
    download = w.http("Download file", [1340, 0], node_extra=on_error,
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
    file_error = w.code("File error", "file_error.js", [1780, -150])

    # chat_id: the service only lets a chat review documents that were sent from that chat
    review_body = ("={{ JSON.stringify({action: $json.action, fields: $json.fields || {}, reviewer: $json.reviewer, "
                   "chat_id: String($json.chat_id)}) }}")
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
                 jsonBody="={{ JSON.stringify({question: $json.question, chat_ref: String($json.chat_id), "
                          "chat_id: String($json.chat_id)}) }}",
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
    w.link(get_file, file_error, 1)
    w.link(download, extract)
    w.link(download, file_error, 1)
    w.link(extract, fmt_result)
    w.link(review, fmt_review)
    w.link(correct, fmt_review)
    w.link(ask, fmt_answer)
    for n in (fmt_result, file_error, fmt_review, fix, typing, fmt_answer, help_, denied):
        w.link(n, telegram)

    # ---- 2. Daily deadline reminders ---------------------------------------------------
    r = Workflow("docflow_reminders.json", "DocflowReminder1", "DocFlow: deadline reminders")
    cron = r.node("Every day 09:00", "n8n-nodes-base.scheduleTrigger", 1.2,
                  {"rule": {"interval": [{"field": "cronExpression", "expression": "0 9 * * *"}]}}, [0, 200])
    manual = r.node("Run now (webhook)", "n8n-nodes-base.webhook", 2,
                    {"httpMethod": "POST", "path": "reminders/run", "responseMode": "onReceived", "options": {}},
                    [0, 420], webhookId="7d1c2b3a-d0cf-4f10-9a11-7e1e6a000002")
    # own key, not SERVICE_API_KEY: whoever may trigger reminders must not get full API access.
    # Empty REMINDERS_WEBHOOK_KEY disables the manual webhook.
    key_ok = r.if_("Key ok?", "={{ !!$env.REMINDERS_WEBHOOK_KEY && $json.headers['x-api-key'] === "
                   "$env.REMINDERS_WEBHOOK_KEY }}", None, [220, 420], operation="true")
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
    return [w, r]


def write(workflows):
    for wf in workflows:
        (HERE / wf.filename).write_text(wf.render(), encoding="utf-8", newline="\n")
        print(f"n8n/{wf.filename}: {len(wf.nodes)} nodes")


def check(workflows):
    """Compare the committed JSON with a fresh build; report which nodes differ."""
    stale = 0
    for wf in workflows:
        path = HERE / wf.filename
        current = path.read_text(encoding="utf-8") if path.exists() else ""
        if current == wf.render():
            print(f"n8n/{wf.filename}: up to date")
            continue
        stale += 1
        try:
            old = {n["name"]: n for n in json.loads(current)["nodes"]}
        except (ValueError, KeyError):
            old = {}
        changed = [n["name"] for n in wf.nodes if old.get(n["name"]) != n] + [k for k in old if k not in
                                                                              {n["name"] for n in wf.nodes}]
        print(f"n8n/{wf.filename}: OUT OF DATE" + (f" (nodes: {', '.join(changed)})" if changed else ""))
    if stale:
        print("Run: python n8n/build_workflow.py  (or --extract FILE if the change was made in the n8n UI)")
    return 1 if stale else 0


def extract(workflows, files):
    """Write the jsCode of Code nodes from n8n export files back to code/*.js."""
    return extract_data(workflows, [(f, json.loads(Path(f).read_text(encoding="utf-8"))) for f in files])


def pull(workflows):
    """Export the workflows from the running n8n container (docker compose) and extract their Code nodes."""
    exports = []
    for wf in workflows:
        tmp = f"/tmp/docflow_pull_{wf.wid}.json"
        cmd = ["docker", "compose", "exec", "-T", "n8n", "sh", "-c",
               f"n8n export:workflow --id={wf.wid} --output={tmp} >/dev/null && cat {tmp} && rm -f {tmp}"]
        try:
            res = subprocess.run(cmd, cwd=HERE.parent, capture_output=True, text=True, encoding="utf-8")
        except FileNotFoundError:
            print("docker not found; install Docker or download the workflow from the UI and use --extract")
            return 1
        if res.returncode != 0:
            print(f"export of {wf.wid} failed (is `docker compose up -d` running?):\n{res.stderr.strip()}")
            return 1
        try:
            exports.append((f"n8n:{wf.wid}", json.loads(res.stdout)))
        except ValueError:
            print(f"export of {wf.wid}: not JSON:\n{res.stdout[:500]}")
            return 1
    return extract_data(workflows, exports)


def extract_data(workflows, exports):
    """exports: [(label, parsed n8n export)]; common.js prefix is stripped from the nodes that have it."""
    by_name = {wf.name: wf for wf in workflows}
    errors = 0
    for f, data in exports:
        for exported in data if isinstance(data, list) else [data]:  # n8n CLI exports are a list
            wf = by_name.get(exported.get("name"))
            if wf is None:
                print(f"{f}: unknown workflow {exported.get('name')!r}, expected one of {sorted(by_name)}")
                errors += 1
                continue
            nodes = {n["name"]: n for n in exported.get("nodes", [])}
            for node_name, (file, common) in wf.sources.items():
                if node_name not in nodes:
                    print(f"{f}: node {node_name!r} not found (renamed?), code/{file} left as is")
                    errors += 1
                    continue
                code = nodes[node_name]["parameters"].get("jsCode", "")
                if common:
                    prefix = COMMON + "\n"
                    if not code.startswith(prefix):
                        print(f"{f}: {node_name!r} has edited shared helpers; move that change to "
                              f"code/common.js by hand, code/{file} left as is")
                        errors += 1
                        continue
                    code = code[len(prefix):]
                target = CODE / file
                if target.read_text(encoding="utf-8") != code:
                    target.write_text(code, encoding="utf-8", newline="\n")
                    print(f"code/{file}: updated from {node_name!r}")
            extra = [n for n, v in nodes.items() if v.get("type") == "n8n-nodes-base.code" and n not in wf.sources]
            if extra:
                print(f"{f}: new Code nodes {extra} must be added to build_workflow.py by hand")
                errors += 1
    return 1 if errors else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="verify the JSON matches code/*.js; write nothing")
    mode.add_argument("--extract", nargs="+", metavar="FILE", help="n8n workflow export(s) to pull Code-node JS from")
    mode.add_argument("--pull", action="store_true",
                      help="like --extract, but export the workflows from the running n8n (docker compose)")
    args = ap.parse_args()
    if args.check:
        sys.exit(check(build()))
    if args.extract or args.pull:
        status = extract(build(), args.extract) if args.extract else pull(build())
        write(build())  # rebuild from the updated sources
        sys.exit(status)
    write(build())
