# n8n workflows

Two importable workflows, built from [code/](code/) by [build_workflow.py](build_workflow.py):

**[docflow_telegram.json](docflow_telegram.json): DocFlow: Telegram intake, review and Q&A** (20 nodes)

```
Telegram ─► Webhook /webhook/telegram ─► Secret ok? ─► Parse update ─► Chat allowed? ─┬─► Route
                                                                                     └─► Access denied
   file        ─► getFile ─► download ─► POST /extract ─► Format result ─────────────┐
   review      ─► POST /documents/{id}/review (approve | reject) ─► Format review ─┤
   fix_prompt  ─► Fix prompt (asks for "field=value", force_reply) ───────────────┤
   correction  ─► POST /documents/{id}/review (correct) ─► Format review ─────────┤
   question    ─► Typing ; POST /ask (Q&A agent) ─► Format answer ────────────────┤
   help        ─► Help ───────────────────────────────────────────────────────────┴─► Telegram API
```

**[docflow_reminders.json](docflow_reminders.json): DocFlow: deadline reminders** (6 nodes)

```
Every day 09:00 (Kyiv) ──────────────────────────────┐
Webhook /webhook/reminders/run ─► X-API-Key ok? ────┴─► GET /deadlines?within_days=7&days_left=7,3,1,0
   ─► Format reminders (one message per Telegram chat the documents came from) ─► Telegram API
```

## What the bot does

- **📎 Documents** (PDF or photo):
  - auto-accepted (confidence ≥ 0.6, no rule violations): ✅ plus a summary of the fields;
  - needs review: ⚠️ plus the reasons and three buttons: **✅ Approve**, **✏️ Correct**, **🗑 Reject**;
    - ✏️ asks the reviewer to reply with lines such as `total_amount=1516.40`; the service validates the correction again;
    - ✅ and 🗑 save the decision with the reviewer's username and remove the buttons;
  - duplicates are answered from the database, with no new Claude call;
  - a failed extraction gets ❌, with buttons to enter the fields manually or reject the document.
- **💬 Questions** in plain text ("When does the insurance expire?", "How much do we owe Kappa IT?") go to the Q&A agent (`POST /ask`). While it works, the bot shows "typing…". `/deadlines` asks for the next 30 days plus overdue payments.
- **⏰ Reminders:** every morning at 09:00, for payments due and policies or contracts expiring in 7, 3 or 1 days, or today. Each reminder goes to the chat the document was sent from. Documents not yet reviewed are marked ⚠️.
- **⛔ Access:** only chats in `TELEGRAM_ALLOWED_CHAT_IDS` are served. Any other chat gets its chat id and no data.

## Design choices

- **Webhook node + Bot API over HTTP**, instead of n8n's Telegram nodes. All settings come from environment variables, so the workflows import and run with no credentials set up in the UI. They are also testable against a mock Bot API (`TELEGRAM_API_BASE`).
- **Security:**
  - Telegram sends the `X-Telegram-Bot-Api-Secret-Token` header; calls without the right value are dropped at the second node. An empty `TELEGRAM_WEBHOOK_SECRET` never matches;
  - only chats on the allowlist are served; an empty allowlist serves nobody;
  - each chat sees, reviews and asks about only the documents sent from it (`chat_id` is passed to the service, which enforces it). Corrections are accepted only as a reply to the bot's own ✏️ prompt;
  - the manual reminders webhook requires its own `REMINDERS_WEBHOOK_KEY` (not the service key); empty = disabled;
  - ports 8000 and 5678 are bound to `127.0.0.1`. The tunnel goes through an nginx edge ([edge.nginx.conf](edge.nginx.conf)) that lets through only `POST /webhook/telegram`, so the n8n UI is never public;
  - successful executions are not stored (they carry files and personal data); error executions are pruned after 7 days.
- **No business logic in n8n:** validation, dedup, storage, the review state machine, deadline queries and the agent live in the service. n8n only routes events, schedules jobs and formats messages.
- **Workflows as code:** Code-node sources are plain JavaScript in [code/](code/), and [build_workflow.py](build_workflow.py) assembles the JSON from them. The shared helpers in `common.js` are prepended to the nodes that format messages. Edit the `.js` files, never `jsCode` in the JSON:
  ```
  python n8n/build_workflow.py                    # rebuild both JSON files from code/
  python n8n/build_workflow.py --check            # exit 1 if the JSON is stale (names the nodes)
  python n8n/build_workflow.py --pull             # after editing Code nodes in the n8n UI: export both workflows
                                                  # from the running container, write their JS to code/*.js, rebuild
  python n8n/build_workflow.py --extract my.json  # the same, from a workflow file downloaded from the UI
  ```
  `--pull` needs the stack running (`docker compose up -d`). Save the workflow in the UI first. `--pull` and `--extract` stop with an error on changes they can't map back safely: a renamed or new Code node, or edited shared helpers. Those go into `build_workflow.py` or `common.js` by hand. The same applies to changes outside Code nodes (wiring, HTTP parameters). Review `git diff n8n/code` before committing.
- **Pre-commit hook:** [.githooks/pre-commit](../.githooks/pre-commit) runs `--check` when a commit touches `n8n/`, so stale JSON can't be committed. Enable it once per clone:
  ```
  git config core.hooksPath .githooks
  ```

## Run

`docker compose up -d` from the repo root starts Postgres, the API and n8n. A one-shot `n8n-import` container imports and publishes both workflows on every start, so the JSON in git is what runs.

### With a real bot

1. Create a bot with @BotFather and put the token in `.env` as `TELEGRAM_BOT_TOKEN`.
   - `TELEGRAM_WEBHOOK_SECRET`, `SERVICE_API_KEY` and `REMINDERS_WEBHOOK_KEY` are random strings (`A-Z a-z 0-9 _ -`).
   - `TELEGRAM_ALLOWED_CHAT_IDS` is your chat id. If you don't know it, the bot tells you when access is denied.
2. Telegram needs a public HTTPS URL. Locally, start a Cloudflare quick tunnel (no account needed), then register the webhook:
   ```
   docker compose --profile tunnel up -d
   python n8n/set_webhook.py          # finds the tunnel URL in the logs, calls setWebhook
   ```
   The quick-tunnel URL changes every time the tunnel restarts; run `set_webhook.py` again after that. On a server, use `python n8n/set_webhook.py --url https://your-n8n-host` instead, and publish only `/webhook/telegram` there too (see [edge.nginx.conf](edge.nginx.conf)).
3. Send the bot a PDF or a photo of a document, or ask it a question.

`python n8n/set_webhook.py --info` shows the webhook status and the last delivery error.

To send reminders now, as of a given day (for demos):

```
curl -X POST localhost:5678/webhook/reminders/run -H "X-API-Key: $REMINDERS_WEBHOOK_KEY" -H "Content-Type: application/json" -d '{"today": "2026-04-01"}'
```

### Offline test (no bot, no tunnel)

```
python n8n/mock_telegram.py --root eval/dataset_test        # mock Bot API on :8081
TELEGRAM_API_BASE=http://host.docker.internal:8081 TELEGRAM_BOT_TOKEN=123:mock TELEGRAM_ALLOWED_CHAT_IDS=555 docker compose up -d
python n8n/test_workflow.py
```

The test posts fake Telegram updates to the webhooks and checks what the bot sends:
- a wrong secret is ignored;
- `/start` returns help;
- a clean PDF is auto-accepted; a poor scan goes to review with buttons;
- ✏️ followed by a reply saves a correction; ✅ approves the document and removes the buttons;
- a question gets a typing indicator and an answer with the right amount and due date; `/deadlines` gets an answer;
- a chat that is not on the allowlist is refused;
- reminders reach the right chat, and the reminders webhook rejects a wrong key.

It uses the real API service and Claude, ~$0.05 per run.

The n8n UI is at http://localhost:5678. On first visit it asks you to create a local owner account.
