# Extraction eval report

Predictions: `eval/predictions_test/claude-sonnet-5-5/extract_v1`

## Field accuracy by set

| Field | clean | light | medium | heavy |
|---|---|---|---|---|
| doc_type | 100% | 100% | 100% | 100% |
| language | 100% | 100% | 100% | 100% |
| counterparty | 100% | 100% | 100% | 94% |
| recipient | 98% | 96% | 96% | 88% |
| document_number | 94% | 94% | 94% | 84% |
| issue_date | 100% | 100% | 100% | 72% |
| currency | 100% | 100% | 100% | 98% |
| total_amount | 100% | 100% | 100% | 86% |
| due_date | 100% | 100% | 100% | 92% |
| valid_from | 100% | 100% | 100% | 100% |
| valid_until | 100% | 100% | 100% | 98% |
| **doc exact match** | **92%** | **90%** | **90%** | **54%** |
| failed calls / invalid JSON | 0 | 0 | 0 | 0 |

## Doc exact match by document type

| Type | clean | light | medium | heavy |
|---|---|---|---|---|
| contract | 100% (n=9) | 100% (n=9) | 100% (n=9) | 67% (n=9) |
| insurance | 100% (n=9) | 100% (n=9) | 89% (n=9) | 67% (n=9) |
| invoice | 100% (n=9) | 100% (n=9) | 100% (n=9) | 67% (n=9) |
| other | 80% (n=5) | 60% (n=5) | 60% (n=5) | 40% (n=5) |
| receipt | 67% (n=9) | 67% (n=9) | 78% (n=9) | 22% (n=9) |
| utility_bill | 100% (n=9) | 100% (n=9) | 100% (n=9) | 56% (n=9) |

## Doc exact match by trap (tag)

See eval/dataset/README.md for tag meanings.

| Tag | clean | light | medium | heavy |
|---|---|---|---|---|
| account_number | 100% (n=9) | 100% (n=9) | 100% (n=9) | 56% (n=9) |
| billing_period | 100% (n=9) | 100% (n=9) | 100% (n=9) | 56% (n=9) |
| card | 83% (n=6) | 83% (n=6) | 100% (n=6) | 0% (n=6) |
| cash_change | 33% (n=3) | 33% (n=3) | 33% (n=3) | 67% (n=3) |
| currency_symbol | 92% (n=24) | 88% (n=24) | 88% (n=24) | 54% (n=24) |
| fiscal_ids | 67% (n=9) | 67% (n=9) | 78% (n=9) | 22% (n=9) |
| iban | 100% (n=18) | 100% (n=18) | 100% (n=18) | 61% (n=18) |
| installments | 100% (n=3) | 100% (n=3) | 100% (n=3) | 67% (n=3) |
| issue_before_start | 100% (n=6) | 100% (n=6) | 83% (n=6) | 50% (n=6) |
| monthly_vs_total | 100% (n=9) | 100% (n=9) | 100% (n=9) | 67% (n=9) |
| narrative | 100% (n=9) | 100% (n=9) | 100% (n=9) | 67% (n=9) |
| no_number | 40% (n=5) | 40% (n=5) | 60% (n=5) | 60% (n=5) |
| no_recipient | 67% (n=9) | 67% (n=9) | 78% (n=9) | 22% (n=9) |
| other_certificate | 50% (n=2) | 0% (n=2) | 0% (n=2) | 0% (n=2) |
| other_letter | 100% (n=2) | 100% (n=2) | 100% (n=2) | 50% (n=2) |
| other_minutes | 100% (n=1) | 100% (n=1) | 100% (n=1) | 100% (n=1) |
| paid_no_due | 100% (n=1) | 100% (n=1) | 100% (n=1) | 100% (n=1) |
| previous_balance | 100% (n=4) | 100% (n=4) | 100% (n=4) | 75% (n=4) |
| stamp | 94% (n=16) | 94% (n=16) | 94% (n=16) | 50% (n=16) |
| start_after_signing | 100% (n=3) | 100% (n=3) | 100% (n=3) | 67% (n=3) |
| sum_insured | 100% (n=9) | 100% (n=9) | 89% (n=9) | 67% (n=9) |
| supply_date | 100% (n=6) | 100% (n=6) | 100% (n=6) | 50% (n=6) |
| textual_date | 100% (n=13) | 100% (n=13) | 92% (n=13) | 69% (n=13) |
| vat_breakdown | 100% (n=9) | 100% (n=9) | 100% (n=9) | 67% (n=9) |
| vat_included | 67% (n=9) | 67% (n=9) | 78% (n=9) | 22% (n=9) |

## Confidence threshold (auto-accept vs manual review)

Docs with confidence >= threshold are auto-accepted; the rest go to human review.

| Set | Threshold | Auto-accepted | Accuracy of accepted | Sent to review |
|---|---|---|---|---|
| clean | 0.5 | 100% | 92% | 0% |
| clean | 0.6 | 100% | 92% | 0% |
| clean | 0.7 | 100% | 92% | 0% |
| clean | 0.8 | 100% | 92% | 0% |
| clean | 0.9 | 92% | 98% | 8% |
| light | 0.5 | 100% | 90% | 0% |
| light | 0.6 | 100% | 90% | 0% |
| light | 0.7 | 100% | 90% | 0% |
| light | 0.8 | 100% | 90% | 0% |
| light | 0.9 | 90% | 98% | 10% |
| medium | 0.5 | 100% | 90% | 0% |
| medium | 0.6 | 100% | 90% | 0% |
| medium | 0.7 | 100% | 90% | 0% |
| medium | 0.8 | 100% | 90% | 0% |
| medium | 0.9 | 76% | 100% | 24% |
| heavy | 0.5 | 84% | 64% | 16% |
| heavy | 0.6 | 70% | 74% | 30% |
| heavy | 0.7 | 46% | 74% | 54% |
| heavy | 0.8 | 18% | 89% | 82% |
| heavy | 0.9 | 0% | - | 100% |

## Cost and latency

| Set | Avg in tok | Avg out tok | Avg latency, s | 
|---|---|---|---|
| clean | 3606 | 347 | 3.1 |
| light | 3271 | 347 | 3.1 |
| medium | 3278 | 350 | 3.3 |
| heavy | 3279 | 394 | 3.6 |

## Most common errors

- `issue_date` on `heavy`: 14 errors
- `document_number` on `heavy`: 8 errors
- `total_amount` on `heavy`: 7 errors
- `recipient` on `heavy`: 6 errors
- `due_date` on `heavy`: 4 errors
- `document_number` on `clean`: 3 errors
- `document_number` on `light`: 3 errors
- `document_number` on `medium`: 3 errors
- `counterparty` on `heavy`: 3 errors
- `recipient` on `light`: 2 errors
