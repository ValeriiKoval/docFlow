# DocFlow AI service

FastAPI service that takes a business document (PDF or photo), extracts its fields with Claude, validates them, stores the result, and decides whether a human must review it.

```
upload ─► type sniffing, size/page limits ─► sha256 dedup ─► store original (content-addressed)
       ─► Claude (strict tool schema, prompt v2) ─► pydantic normalisation ─► business checks
       ─► auto_accepted  (confidence ≥ 0.6 and no issues)
          needs_review   (low confidence or a rule violated) ─► /review: approve / correct / reject
          failed         (API or schema error; re-upload or /reprocess retries)
       ─► every Claude call logged in `runs`: tokens, cost, latency, attempts, error
```

The Claude call (`docflow/extraction.py`) is the same code the offline eval uses (`eval/extract.py`), so [eval/RESULTS.md](../eval/RESULTS.md) measures what runs here.

## Run

```
pip install -r service/requirements.txt
cp .env.example .env                   # ANTHROPIC_API_KEY, SERVICE_API_KEY
python -m uvicorn docflow.main:app --app-dir service --port 8000
```

Interactive docs: http://localhost:8000/docs. Tests: `python -m pytest -q` from the repo root. They use a fake extractor, so they make no API calls.

## Endpoints

When `SERVICE_API_KEY` is set, every endpoint except `/health` requires the header `X-API-Key`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness, model, prompt, threshold |
| POST | `/extract` | Multipart `file` (+ optional `source`, `source_ref`). Returns `{duplicate, document}`. A duplicate returns the stored result without a new Claude call. |
| GET | `/documents/{id}` | Document with normalised fields, status, issues |
| GET | `/documents/{id}/file` | The stored original |
| GET | `/documents/search` | `q` (counterparty / recipient / number / filename), `doc_type`, `status`, `date_from`, `date_to` |
| POST | `/documents/{id}/review` | `{"action": "approve" \| "correct" \| "reject", "fields": {...}, "reviewer": "..."}` |
| POST | `/documents/{id}/reprocess` | Re-run extraction (after a failure or a prompt change) |
| GET | `/deadlines` | Payment deadlines and expiries within `within_days` (`today` can be set for demos) |
| GET | `/stats` | Documents by status and type; Claude calls, tokens, cost, average latency |

Example (`/extract`, utility bill scan):

```json
{
  "duplicate": false,
  "document": {
    "id": 3, "status": "needs_review", "confidence": 0.5,
    "issues": ["low confidence 0.5 < 0.6"],
    "fields": {"doc_type": "utility_bill", "language": "pl", "counterparty": "Wodociągi Przykładowe Sp. z o.o.",
               "recipient": "Piotr Wzorcowy", "document_number": "2026-03-681381", "issue_date": "2026-03-09",
               "currency": "PLN", "total_amount": 1014.63, "due_date": "2026-03-19",
               "valid_from": null, "valid_until": null},
    "has_text_layer": false, "pages": 1, "source": "api"
  }
}
```

## Validation

- **Input:** the file type is detected from its magic bytes, not from the declared content type. Accepted: PDF, JPEG, PNG, WEBP, GIF. Limits: `MAX_FILE_MB`, `MAX_PAGES`. Unreadable PDFs are rejected with 422.
- **Model output:** checked against the full `schema.json` (jsonschema). The model is re-asked up to 3 times when it returns no valid tool call.
- **Normalisation:** whitespace in names; the `№` / `nr` / `No.` label is stripped from numbers; currency is upper-cased and must be an ISO code; amounts like `"1 234,56"` from manual corrections are accepted; dates must be real dates.
- **Business checks** (any failure sends the document to review, even at high confidence):
  - due date only on invoices and bills, and not before the issue date;
  - validity period only on policies and contracts, and `valid_until` not before `valid_from`;
  - invoices, bills and receipts must have a total;
  - a total needs a currency, and the currency must be one we expect;
  - every target type needs an issue date.

## Configuration

See [.env.example](../.env.example): `DOCFLOW_MODEL`, `DOCFLOW_PROMPT`, `CONFIDENCE_THRESHOLD`, `SERVICE_API_KEY`, `DATABASE_URL` (SQLite by default; Postgres in docker-compose, stage 4), `STORAGE_DIR`, `MAX_FILE_MB`, `MAX_PAGES`.
