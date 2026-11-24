# Extraction quality: results (stage 2)

Date: 2026-11-24. Models: `claude-sonnet-5-5`, `claude-haiku-5-5` (default effort, adaptive thinking on).

## Method

- **Data:** two synthetic sets of 50 single-page documents (5 target types plus `other`; uk / pl / en; 4 layouts; with traps). See [dataset/README.md](dataset/README.md).
  - **dev** (`dataset/`, seed 42): used to find errors and write prompt v2.
  - **test** (`dataset_test/`, seed 2026): held out. Only the final prompts were run on it. No PDF overlaps between the two sets.
- **Scan levels:** each document is also rasterised and degraded at 3 levels (`light`, `medium`, `heavy`: rotation, blur, noise, JPEG artefacts, shadow), so 200 extractions per set.
- **Call:** the PDF goes in a `document` block. Output comes back via a strict `record_document` tool, `tool_choice: auto`. The result is validated against [schema.json](../schema.json) with jsonschema. The model is re-asked if no valid call comes back; in practice this was never needed (0 failed calls in 1,200).
- **Metric:** a field counts as correct on exact match after normalisation (amounts ±0.01; names and numbers compared case- and punctuation-insensitively). A document counts as correct only if all 11 fields are correct.

## Headline (held-out test set)

| Run | clean | light | medium | heavy | Cost / 1000 docs |
|---|---|---|---|---|---|
| Sonnet 5.5, prompt v1 | 92% | 90% | 90% | 54% | $10.3 |
| **Sonnet 5.5, prompt v2** | **100%** | **100%** | **98%** | **60%** | **$11.8** |
| Haiku 5.5, prompt v2 | 100% | 98% | 100% | 28% | $0.7 |

Document exact match. Mean field accuracy with Sonnet v2: 100 / 100 / 100 / 93%. Average latency is 3.3 s per document (Sonnet).

The dev set gives the same picture: Sonnet v1 74 / 78 / 80 / 46% → v2 100 / 100 / 100 / 54%. Full tables:
- dev: [results/summary_dev.md](results/summary_dev.md)
- test: [results/summary_test.md](results/summary_test.md)
- per-run reports with breakdowns by field, document type and trap: `results/dev__*.md`, `results/test__*.md`

## Typical errors and fixes (v1 → v2)

| Error (v1, dev set) | Cause | Fix in v2 |
|---|---|---|
| Insurance `total_amount` = sum insured instead of premium (9 of 9 policies) | v1 prompt and schema described the field as "to pay / insured / contract value" | `total_amount` defined per document type; insurance = premium, explicitly not the sum insured; schema description aligned |
| Receipt `document_number` = fiscal number (FN, BDE) when the receipt has no number of its own | v1 did not say which numbers are not document numbers | List of non-document numbers (fiscal, terminal, account, tax ID, IBAN); "no own number → null" |
| Certificate `recipient` = null | Convention was underspecified ("addressed to") | Recipient includes the person a certificate is issued for (convention also clarified in the dataset README) |
| Confidence ≥ 0.8 on wrong documents | Vague confidence instruction | Confidence = probability that **every** field is right, judged by the weakest field, with explicit bands |

The remaining v2 error on clean / light / medium (test set): a document number printed with Cyrillic letters (`AN-7004608` in transliteration) was returned with the look-alike Latin letters. Heavy-scan errors are mostly misread digits (dates, amounts, numbers) on heavily blurred images.

## Confidence threshold and human review

Sonnet v2's confidence separates right from wrong on heavy scans:

| Set | Correct docs | Mean confidence | Wrong docs | Mean confidence |
|---|---|---|---|---|
| dev | 27 | 0.53 | 23 | 0.40 |
| test | 30 | 0.56 | 20 | 0.36 |

Threshold sweep, Sonnet v2, test set. Each cell: auto-accepted / accuracy of the accepted / wrong documents that slipped through.

| Threshold | clean | light | medium | heavy |
|---|---|---|---|---|
| 0.5 | 100% / 100% / 0 | 100% / 100% / 0 | 100% / 98% / 1 | 56% / 86% / 4 |
| **0.6** | **100% / 100% / 0** | **100% / 100% / 0** | **100% / 98% / 1** | **26% / 100% / 0** |
| 0.7 | 100% / 100% / 0 | 100% / 100% / 0 | 100% / 98% / 1 | 12% / 100% / 0 |
| 0.8 | 100% / 100% / 0 | 100% / 100% / 0 | 100% / 98% / 1 | 4% / 100% / 0 |

**Chosen threshold: 0.6** (Sonnet v2). Across all 200 test extractions:
- 81.5% are auto-accepted;
- 18.5% go to human review (almost all heavy scans);
- 1 wrong document (0.5%) passed, the Cyrillic/Latin case above.

The pipeline (stage 4) uses `CONFIDENCE_THRESHOLD=0.6`.

## Model choice

- **Sonnet 5.5** is the default. It is the only model that stays usable on poor scans, and its confidence is well calibrated.
- **Haiku 5.5** matches Sonnet on clean and lightly degraded documents at ~1/17 of the cost. It is much weaker on heavy scans (28%), and its confidence is less reliable there. Possible later optimisation: route born-digital PDFs (with a text layer) to Haiku and scans to Sonnet.

## Cost of this evaluation

1,203 API calls (1,200 plus a 3-document smoke test), about **$9** in total. Sonnet runs cost ~$2.1–2.4 per 200 documents, Haiku ~$0.14.

## Q&A agent (stage 5)

[qa_eval.py](qa_eval.py) loads the 50 test documents from their labels into a temporary database and asks 13 generated questions:
- 9 exact facts in pl / en: policy expiry, amount and due date by document number, contract value and party;
- 2 lists: payments due in 14 days, policies and contracts expiring within a month;
- 1 count;
- 1 question about a company that is not in the database, which must not get an invented date.

"Today" is set to a day when both lists are non-empty.

| Agent model | Passed | Cost / answer | Avg latency |
|---|---|---|---|
| Sonnet 5.5 (effort low) | 13/13 | $0.009 | 4.0 s |
| Haiku 5.5 (effort low) | 12/13 | $0.0006 | 3.7 s |

Answers and tool calls are in [results/qa_claude-sonnet-5-5.md](results/qa_claude-sonnet-5-5.md) and [results/qa_claude-haiku-5-5.md](results/qa_claude-haiku-5-5.md).

The first version of the eval exposed two problems, both fixed:
- **Empty lists:** the list questions had no expected documents, so they passed trivially. The eval now picks a day with non-empty windows.
- **Counting:** the agent counted receipts by hand and answered "8… actually 9". `search_documents` now returns the total `count`, and the eval requires the first number stated to be correct.

Haiku misses one question: for the company that is not in the database it kept searching until the turn limit and returned the fallback "could not find an answer". It invented no date, but it also gave no clear "not found". It answers every fact, list and count question correctly at 1/15 of the cost, so **the agent runs on Haiku 5.5 by default** (`DOCFLOW_AGENT_MODEL`). Haiku's weak spot is heavy scans, but the agent only reads data that is already extracted. Extraction stays on Sonnet 5.5. With 13 questions the eval is small: switch back to Sonnet with one env var if real questions turn out harder.

## Limitations

- Synthetic, single-page, machine-generated documents. Real scans (photos, handwriting, multi-page contracts) will be harder.
- 50 documents per set. One document is 2 percentage points, so small differences are noise.
- Prompt v2 was written after inspecting dev-set errors. The held-out test set guards against overfitting, but it comes from the same generator, so it shares the generator's templates.
