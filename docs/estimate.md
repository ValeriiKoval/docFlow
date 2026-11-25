# Effort estimate: DocFlow AI for a client

How I would estimate this project for a small office or accounting firm that wants incoming documents processed automatically. The hours are for one engineer. They assume that the reusable parts of this repository (schema, prompts, service, n8n workflows, eval harness) are adapted, not written from scratch.

## Scope

**In scope:**
- **Intake:** one channel, a Telegram bot (an email inbox is an option below).
- **Documents:** up to 6 types, up to 3 languages, single- or multi-page PDFs and photos.
- **Fields:** up to ~12 per document, with confidence, business rules and human review in Telegram.
- **Register:** Postgres with a REST API, deadline reminders and a Q&A bot over it.
- **Proof of quality:** a measured accuracy report on the client's own labelled sample.
- **Deployment:** on one VPS or the client's server with docker-compose, plus handover documentation.

**Out of scope:**
- Payments and posting to accounting.
- Line items and VAT breakdown.
- Handwriting.
- Integrations beyond those listed in the options.

## Stages

| # | Stage | Hours | Result the client can check |
|---|---|---|---|
| 1 | **Discovery.** Document types and fields, how they are used today, 30–50 real sample documents, success criteria (e.g. "≥ 95% of clean documents need no human") | 2–3 | Field list, review rules, agreed metric |
| 2 | **Test set.** Label the client's sample (with the client's bookkeeper for edge cases) and add synthetic documents for rare cases. Set up the eval harness | 4–6 | Labelled set, baseline accuracy report |
| 3 | **Extraction.** Adapt the schema and prompt, then 2–3 iterations on the errors found. Choose the model and the confidence threshold on held-out documents | 4–6 | Accuracy per field and per document type; auto-accept vs review share; cost per document |
| 4 | **Service.** Validation and business rules for this client, dedup, storage, review API, deadline queries, tests | 6–8 | API docs, passing tests |
| 5 | **n8n.** Telegram intake, review buttons, reminders, access control. Deployment with HTTPS and backups | 5–7 | Working bot on the client's server |
| 6 | **Q&A agent.** Tools over the register and an eval on 15–20 of the client's real questions | 3–4 | Answers with document references; eval report |
| 7 | **Handover.** README and run book, a 30-minute demo, two weeks of pilot support (fixes from real use) | 3–4 | Documentation; pilot report with real accuracy |
| | **Total** | **27–38** | |

**Why a range:** the main uncertainty is the documents themselves. Clean born-digital PDFs land at the low end. Phone photos, multi-page contracts or unusual layouts land at the high end, because they need more prompt iterations and more review rules.

**What makes it fit the low end:**
- the client provides a sample with correct values early (stage 2 is the bottleneck);
- one person on the client side decides on edge cases;
- the bot and server stay as in this repository.

## Options

| Option | Hours |
|---|---|
| Email intake (IMAP trigger in n8n, attachments → `/extract`) | 2–3 |
| Google Drive or OneDrive watched folder | 2–3 |
| Push approved records to Airtable, HubSpot or Google Sheets | 3–5 |
| Push to an accounting system or ERP via its API (depends on the API) | 6–12 |
| Invoice line items and VAT breakdown | 5–8 |
| Web review screen instead of Telegram buttons | 6–10 |
| Routing: born-digital PDFs to Haiku, scans to Sonnet (lower cost) | 1–2 |

## Running costs (monthly)

| Item | 300 docs / month | 1,000 docs / month | Note |
|---|---|---|---|
| Claude: extraction, Sonnet 5.5 | ~$4 | ~$12 | $0.012 per document, measured |
| Claude: Q&A, Haiku 5.5 | < $1 | < $1 | $0.0006 per answer, measured |
| VPS (2 vCPU, 4 GB) for Postgres, API and n8n | ~$5–10 | ~$5–10 | Or the client's existing server |
| **Total** | **~$10–15** | **~$20–25** | |

Human time: about 1 in 5 documents needs a review click when many documents are poor scans; close to none for born-digital PDFs.

## Risks and how they are handled

| Risk | Mitigation |
|---|---|
| Real documents are harder than the sample | The pilot (stage 7) measures accuracy on real traffic. The confidence threshold and business rules send uncertain documents to a human, not into the register. |
| Personal data leaves the office | Original files stay on the client's server. The Anthropic API is used only for extraction (no training on API data by default). The bot only serves allow-listed chats. |
| A wrong value is accepted automatically | Threshold chosen so that no wrong document passed on the held-out set at that scan level. Every record keeps a link to the original file and a review history. |
| Model or API changes | Model and prompt are environment settings. The eval harness re-checks a new model on the same test set before switching. |

## How this repository compares

This repository was built as a portfolio case: about 15 hours over stages 0–6, on synthetic data, with no client communication. The client estimate above is about twice that. The difference is discovery, labelling real documents, deployment on the client's side, and the pilot.
