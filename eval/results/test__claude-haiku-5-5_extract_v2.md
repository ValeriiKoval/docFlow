# Extraction eval report

Predictions: `eval/predictions_test/claude-haiku-5-5/extract_v2`

## Field accuracy by set

| Field | clean | light | medium | heavy |
|---|---|---|---|---|
| doc_type | 100% | 100% | 100% | 100% |
| language | 100% | 100% | 100% | 100% |
| counterparty | 100% | 100% | 100% | 80% |
| recipient | 100% | 100% | 100% | 90% |
| document_number | 100% | 98% | 100% | 86% |
| issue_date | 100% | 100% | 100% | 56% |
| currency | 100% | 100% | 100% | 92% |
| total_amount | 100% | 100% | 100% | 66% |
| due_date | 100% | 100% | 100% | 90% |
| valid_from | 100% | 100% | 100% | 100% |
| valid_until | 100% | 100% | 100% | 94% |
| **doc exact match** | **100%** | **98%** | **100%** | **28%** |
| failed calls / invalid JSON | 0 | 0 | 0 | 0 |

## Doc exact match by document type

| Type | clean | light | medium | heavy |
|---|---|---|---|---|
| contract | 100% (n=9) | 89% (n=9) | 100% (n=9) | 11% (n=9) |
| insurance | 100% (n=9) | 100% (n=9) | 100% (n=9) | 33% (n=9) |
| invoice | 100% (n=9) | 100% (n=9) | 100% (n=9) | 33% (n=9) |
| other | 100% (n=5) | 100% (n=5) | 100% (n=5) | 60% (n=5) |
| receipt | 100% (n=9) | 100% (n=9) | 100% (n=9) | 0% (n=9) |
| utility_bill | 100% (n=9) | 100% (n=9) | 100% (n=9) | 44% (n=9) |

## Doc exact match by trap (tag)

See eval/dataset/README.md for tag meanings.

| Tag | clean | light | medium | heavy |
|---|---|---|---|---|
| account_number | 100% (n=9) | 100% (n=9) | 100% (n=9) | 44% (n=9) |
| billing_period | 100% (n=9) | 100% (n=9) | 100% (n=9) | 44% (n=9) |
| card | 100% (n=6) | 100% (n=6) | 100% (n=6) | 0% (n=6) |
| cash_change | 100% (n=3) | 100% (n=3) | 100% (n=3) | 0% (n=3) |
| currency_symbol | 100% (n=24) | 96% (n=24) | 100% (n=24) | 29% (n=24) |
| fiscal_ids | 100% (n=9) | 100% (n=9) | 100% (n=9) | 0% (n=9) |
| iban | 100% (n=18) | 100% (n=18) | 100% (n=18) | 39% (n=18) |
| installments | 100% (n=3) | 100% (n=3) | 100% (n=3) | 67% (n=3) |
| issue_before_start | 100% (n=6) | 100% (n=6) | 100% (n=6) | 33% (n=6) |
| monthly_vs_total | 100% (n=9) | 89% (n=9) | 100% (n=9) | 11% (n=9) |
| narrative | 100% (n=9) | 89% (n=9) | 100% (n=9) | 11% (n=9) |
| no_number | 100% (n=5) | 100% (n=5) | 100% (n=5) | 0% (n=5) |
| no_recipient | 100% (n=9) | 100% (n=9) | 100% (n=9) | 0% (n=9) |
| other_certificate | 100% (n=2) | 100% (n=2) | 100% (n=2) | 50% (n=2) |
| other_letter | 100% (n=2) | 100% (n=2) | 100% (n=2) | 50% (n=2) |
| other_minutes | 100% (n=1) | 100% (n=1) | 100% (n=1) | 100% (n=1) |
| paid_no_due | 100% (n=1) | 100% (n=1) | 100% (n=1) | 100% (n=1) |
| previous_balance | 100% (n=4) | 100% (n=4) | 100% (n=4) | 50% (n=4) |
| stamp | 100% (n=16) | 100% (n=16) | 100% (n=16) | 19% (n=16) |
| start_after_signing | 100% (n=3) | 100% (n=3) | 100% (n=3) | 33% (n=3) |
| sum_insured | 100% (n=9) | 100% (n=9) | 100% (n=9) | 33% (n=9) |
| supply_date | 100% (n=6) | 100% (n=6) | 100% (n=6) | 33% (n=6) |
| textual_date | 100% (n=13) | 100% (n=13) | 100% (n=13) | 38% (n=13) |
| vat_breakdown | 100% (n=9) | 100% (n=9) | 100% (n=9) | 33% (n=9) |
| vat_included | 100% (n=9) | 100% (n=9) | 100% (n=9) | 0% (n=9) |

## Confidence threshold (auto-accept vs manual review)

Docs with confidence >= threshold are auto-accepted; the rest go to human review.

| Set | Threshold | Auto-accepted | Accuracy of accepted | Sent to review |
|---|---|---|---|---|
| clean | 0.5 | 100% | 100% | 0% |
| clean | 0.6 | 100% | 100% | 0% |
| clean | 0.7 | 98% | 100% | 2% |
| clean | 0.8 | 98% | 100% | 2% |
| clean | 0.9 | 94% | 100% | 6% |
| light | 0.5 | 100% | 98% | 0% |
| light | 0.6 | 100% | 98% | 0% |
| light | 0.7 | 100% | 98% | 0% |
| light | 0.8 | 100% | 98% | 0% |
| light | 0.9 | 90% | 98% | 10% |
| medium | 0.5 | 100% | 100% | 0% |
| medium | 0.6 | 100% | 100% | 0% |
| medium | 0.7 | 100% | 100% | 0% |
| medium | 0.8 | 98% | 100% | 2% |
| medium | 0.9 | 10% | 100% | 90% |
| heavy | 0.5 | 28% | 64% | 72% |
| heavy | 0.6 | 8% | 75% | 92% |
| heavy | 0.7 | 6% | 67% | 94% |
| heavy | 0.8 | 2% | 100% | 98% |
| heavy | 0.9 | 0% | - | 100% |

## Cost and latency

| Set | Avg in tok | Avg out tok | Avg latency, s | 
|---|---|---|---|
| clean | 4270 | 430 | 3.2 |
| light | 3935 | 448 | 3.3 |
| medium | 3942 | 518 | 4.0 |
| heavy | 3943 | 886 | 6.2 |

## Most common errors

- `issue_date` on `heavy`: 22 errors
- `total_amount` on `heavy`: 17 errors
- `counterparty` on `heavy`: 10 errors
- `document_number` on `heavy`: 7 errors
- `recipient` on `heavy`: 5 errors
- `due_date` on `heavy`: 5 errors
- `currency` on `heavy`: 4 errors
- `valid_until` on `heavy`: 3 errors
- `document_number` on `light`: 1 errors
