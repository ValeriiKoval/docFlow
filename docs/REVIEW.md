# DocFlow review: architecture, security, code

Date: 2026-11-25. Scope: `service/`, `n8n/`, `docker-compose.yml`, `prompts/`, `eval/RESULTS.md`.

Status: `[x]` fixed, `[~]` partly fixed, `[ ]` open.

## What was done (2026-11-25)

| # | Change | Where |
|---|---|---|
| 1 | Tunnel → nginx edge that passes only `POST /webhook/telegram`; ports 8000 / 5678 bound to `127.0.0.1` | `docker-compose.yml`, `n8n/edge.nginx.conf` |
| 3 | API without `SERVICE_API_KEY` → 503 (except with `DOCFLOW_DEV=1`); compose requires `TELEGRAM_WEBHOOK_SECRET` and `TELEGRAM_ALLOWED_CHAT_IDS`; in n8n an empty secret / allowlist means "deny" | `config.py`, `main.py`, `build_workflow.py` |
| 2, 12 | `chat_id` in `/ask` and `/review`: the agent's tools and review see only the documents of their own chat; corrections are accepted only as a reply to the bot's ✏️ prompt; the agent is told not to follow instructions found in document text | `queries.py`, `agent.py`, `main.py`, `parse_update.js` |
| 4, 5 | `/reprocess` does not touch human-reviewed documents without `force=true`; `rejected` is a final state | `main.py` |
| 7 | Concurrent upload of the same file → duplicate instead of 500 | `main.py` |
| 13 | A retry passes the schema error text back to the model (`tool_result`, `is_error`); `max_tokens` is not retried | `extraction.py` |
| 15 | Images over ~3.6 MB / 4096 px are re-encoded to JPEG | `extraction.py` (`fit_image`), `pillow` in `service/requirements.txt` |
| 16, 17 | A getFile / download error → message to the user; long reminders are split into messages of up to 3800 characters | `build_workflow.py`, `file_error.js`, `format_reminders.js` |
| 19 | Successful n8n executions are not saved; execution data is pruned after 7 days | `build_workflow.py`, `docker-compose.yml` |
| 20 | Separate `REMINDERS_WEBHOOK_KEY` for triggering reminders manually | `build_workflow.py`, `.env.example` |
| 22, 23, 24 | Numbers like `NOV/…` are no longer cut; `1.234,56` → 1234.56; `%` / `_` are escaped in search; uploads are read no further than the limit | `schemas.py`, `queries.py`, `main.py` |

Tests: `service/tests/test_review_fixes.py` (29 new checks, 53 in total).

**Open (needs a separate decision):** 6 — asynchronous processing (queue / worker); 8 — semantic deduplication; 9 — `Numeric` + Alembic; 10 — threshold sweep on a dev set; 11 — anti-injection instruction in the extraction prompt (needs a new eval run), cross-check against the PDF text layer; 14 — rate limit and budget; 18 — log of sent reminders; 21 — reviewer allowlist in group chats; audit of field changes (5).

**Limitations of the current changes:** documents uploaded through the API (not from Telegram) are not visible from any chat. Isolation relies on `source_ref`: chats that should see shared documents no longer see them. `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` is still set: the workflows read settings through `$env`; the risk is reduced because the UI is no longer public.

## 🔴 Critical

- [x] **1. The tunnel exposes all of n8n, not just the webhook.** `cloudflared --url http://n8n:5678` puts the UI, `/rest` and `/webhook/reminders/run` on the internet. If the owner account has not been created yet, anyone with the tunnel URL can create it. Together with `N8N_BLOCK_ENV_ACCESS_IN_NODE=false`, a Code node can read `TELEGRAM_BOT_TOKEN` and `SERVICE_API_KEY`.
  *Fix:* tunnel → reverse proxy that passes only `POST /webhook/telegram`; the UI and API are reachable only from `127.0.0.1`.
- [x] **2. No data isolation between chats (IDOR).** The agent searches all documents (`chat_ref` is only logged). A correction takes `doc_id` from `#N` in any message that was replied to; `approve:ID` / `reject:ID` are not bound to a chat. Any allowed chat can read and change other chats' documents.
  *Fix:* a `chat_id` parameter in `/ask` and `/review`; the service checks that the document came from this chat (`source=telegram`, `source_ref=<chat>:<msg>`) and filters the agent's tools.
- [x] **3. Protection turns off when settings are empty.** Empty `SERVICE_API_KEY` → API without authorisation (port 8000 on `0.0.0.0`). Empty `TELEGRAM_ALLOWED_CHAT_IDS` → the bot is open to everyone. Empty `TELEGRAM_WEBHOOK_SECRET` → the secret check is effectively off.
  *Fix:* the service does not start without a key (except with an explicit `DOCFLOW_DEV=1`); compose requires the secret and the allowlist; an empty allowlist means "nobody"; ports on `127.0.0.1`.

## 🟠 High: architecture and data

- [x] **4. `/reprocess` overwrites a human review.** Fields and the `approved` / `corrected` status are overwritten by the model's result, and on an error the document becomes `failed`.
  *Fix:* 409 for human-reviewed documents unless `force=true` is passed.
- [~] **5. No state machine for review.** A `rejected` document can be approved, a document can be rejected twice, and so on. Field changes are not audited.
  *Fix:* allowed transitions; `approve` only from `auto_accepted` / `needs_review` / `corrected`.
- [ ] **6. A transaction stays open for the whole Claude call** (up to 3 attempts × 16k tokens × SDK retries). On Postgres this holds a pool connection for minutes; ~15 concurrent files block every endpoint.
  *Fix (architectural, not done):* asynchronous processing — `status=processing`, a worker / queue, commit before the model call.
- [x] **7. Race on concurrent upload of the same file** → `IntegrityError` → 500.
  *Fix:* catch `IntegrityError`, roll back and return the existing record as a duplicate.
- [ ] **8. Deduplication by bytes only.** A second photo / scan of the same invoice → a new document → a double payment reminder.
  *Fix (not done):* a semantic check on `counterparty + document_number + total_amount` → `needs_review` with a link to the possible duplicate.
- [ ] **9. Money stored as `Float`, no migrations** (`create_all`).
  *Fix (not done):* `Numeric(14,2)` + Alembic.

## 🟠 High: AI/ML

- [ ] **10. The confidence threshold was tuned on the test set** (`eval/RESULTS.md`, "Threshold sweep… test set"). The test set is no longer independent; the data is synthetic from one generator, 50 documents.
  *Fix (not done):* sweep the threshold on a dev set and use the test set only for the final numbers; in production, monitor the share of corrections among `auto_accepted`.
- [~] **11. The model's self-assessment is the only barrier to auto-acceptance, and it is open to prompt injection** from document text.
  *Fix:* the prompt states explicitly that document text is data, not instructions (`[x]` below). Not done: cross-checking amount / number against the PDF text layer, mandatory review for new counterparties / large amounts.
- [x] **12. Indirect prompt injection into the agent** through document fields in tool results. The tools only read, so the damage is limited, but together with item 2 it is a leak channel.
  *Fix:* isolation from item 2 + an instruction in the system prompt.
- [x] **13. A retry sends the same request without the validation error text.**
  *Fix:* return a `tool_result` with `is_error` and the error text to the model.
- [ ] **14. No rate limit / budget** on `/ask` and `/extract`.
  *Fix (not done):* a per-chat request limit and a daily budget based on `runs` / `agent_runs`.
- [x] **15. File limits do not match the API.** The service accepts images up to 20 MB; the Anthropic API accepts base64 images up to ~5 MB.
  *Fix:* re-encode / downscale images over the limit before the call.

## 🟡 Medium: n8n

- [x] **16. `Telegram getFile` / `Download file` without error handling.** A file over 20 MB or a network failure → the execution fails and the user gets no reply.
- [~] **17. Telegram send errors are ignored; reminders are not limited to 4096 characters** → a long reminder is silently lost.
- [ ] **18. Reminders are not idempotent** (a second run → duplicates; a missed day is not caught up).
  *Fix (not done):* a `notifications_sent` table.
- [x] **19. `saveDataSuccessExecution: "all"`** stores the files and personal data of every execution with no retention limit.
- [x] **20. One `SERVICE_API_KEY` for n8n→API and for the public reminders webhook;** the comparison is not constant-time.
  *Fix:* a separate `REMINDERS_WEBHOOK_KEY`.
- [ ] **21. In group chats any member can approve / change documents.**
  *Fix (not done):* an allowlist of reviewer users.

## 🟢 Code bugs

- [x] **22. `_strip_number_label` cuts real numbers:** `NOV/2026/1` → `V/2026/1`, `Nordic-15` → `rdic-15`.
- [x] **23. `_amount` breaks the European format:** `1.234,56` → 1.23.
- [~] **24. Minor issues:** `ilike` does not escape `%` / `_`; the file is read into memory in full before the size check; `/docs` without authorisation; `cloudflared:latest` without a pinned version.
