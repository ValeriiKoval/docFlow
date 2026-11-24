# n8n workflow: Telegram intake and review

[docflow_telegram.json](docflow_telegram.json) is the importable workflow, **DocFlow: Telegram intake and review** (14 nodes):

```
Telegram ─► Webhook /webhook/telegram ─► Secret ok? ─► Parse update ─► Route
   file        ─► getFile ─► download ─► POST /extract ─► Format result ─────────────┐
   review      ─► POST /documents/{id}/review (approve | reject) ─► Format review ─┤
   fix_prompt  ─► Fix prompt (asks for "field=value", force_reply) ───────────────┤
   correction  ─► POST /documents/{id}/review (correct) ─► Format review ─────────┤
   help        ─► Help ───────────────────────────────────────────────────────────┴─► Telegram API
```

What the bot does:
- **Auto-accepted** (confidence ≥ 0.6, no rule violations): ✅ plus a summary of the fields.
- **Needs review**: ⚠️ plus the reasons and three buttons: **✅ Approve**, **✏️ Correct**, **🗑 Reject**.
  - ✏️ asks the reviewer to reply with lines such as `total_amount=1516.40`. The reply is saved as a correction, and the service validates it again.
  - ✅ and 🗑 save the decision with the reviewer's username and remove the buttons.
- **Duplicates**: the bot answers from the database, with no new Claude call.
- **Failed extraction** (API or schema error): ❌, with buttons to enter the fields manually or reject the document.

## Design choices

- **Webhook node + Bot API over HTTP**, instead of n8n's Telegram nodes. Everything is configured through environment variables, so the workflow imports and runs with no credentials set up in the UI. It is also testable against a mock Bot API (`TELEGRAM_API_BASE`).
- **Webhook secret:** Telegram sends `X-Telegram-Bot-Api-Secret-Token`. Calls without the right value are dropped at the second node.
- **No business logic in n8n:** validation, dedup, storage and the review state machine live in the service. n8n only routes events and formats messages, so the same API can serve email or Drive intake later.
- **Code-node sources** are in [code/](code/) as plain JavaScript. [build_workflow.py](build_workflow.py) assembles the JSON. If you edit the workflow in the n8n UI, export it back over the JSON.

## Run

`docker compose up -d` from the repo root starts Postgres, the API and n8n. A one-shot `n8n-import` container imports and publishes this workflow on every start, so the JSON in git is what runs.

### With a real bot

1. Create a bot with @BotFather and put the token in `.env` as `TELEGRAM_BOT_TOKEN`. `TELEGRAM_WEBHOOK_SECRET` and `SERVICE_API_KEY` are random strings; any long values will do.
2. Telegram needs a public HTTPS URL. Locally, start a Cloudflare quick tunnel (no account needed):
   ```
   docker compose --profile tunnel up -d
   python n8n/set_webhook.py          # finds the tunnel URL in the logs, calls setWebhook
   ```
   On a server, use `python n8n/set_webhook.py --url https://your-n8n-host` instead.
3. Send the bot a PDF or a photo of a document.

`python n8n/set_webhook.py --info` shows the webhook status and the last delivery error.

### Offline test (no bot, no tunnel)

```
python n8n/mock_telegram.py --root eval/dataset_test        # mock Bot API on :8081
TELEGRAM_API_BASE=http://host.docker.internal:8081 TELEGRAM_BOT_TOKEN=123:mock docker compose up -d
python n8n/test_workflow.py
```

The test posts fake Telegram updates to the webhook and checks the bot's replies:
- a wrong secret is ignored;
- `/start` returns help;
- a clean PDF is auto-accepted;
- a poor scan goes to review with buttons;
- ✏️ followed by a reply saves a correction;
- ✅ approves the document and removes the buttons.

The test uses the real API service and Claude: about 2 calls, ~$0.03.

The n8n UI is at http://localhost:5678. On first visit it asks you to create a local owner account.
