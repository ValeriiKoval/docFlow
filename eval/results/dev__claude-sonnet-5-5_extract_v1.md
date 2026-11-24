# Extraction eval report

Predictions: `eval/predictions/claude-sonnet-5-5/extract_v1`

## Field accuracy by set

| Field | clean | light | medium | heavy |
|---|---|---|---|---|
| doc_type | 100% | 100% | 100% | 100% |
| language | 100% | 100% | 100% | 100% |
| counterparty | 100% | 100% | 100% | 98% |
| recipient | 96% | 96% | 96% | 88% |
| document_number | 96% | 96% | 96% | 92% |
| issue_date | 100% | 100% | 100% | 74% |
| currency | 100% | 100% | 100% | 100% |
| total_amount | 82% | 86% | 88% | 76% |
| due_date | 100% | 100% | 100% | 92% |
| valid_from | 100% | 100% | 100% | 96% |
| valid_until | 100% | 100% | 100% | 96% |
| **doc exact match** | **74%** | **78%** | **80%** | **46%** |
| failed calls / invalid JSON | 0 | 0 | 0 | 0 |

## Doc exact match by document type

| Type | clean | light | medium | heavy |
|---|---|---|---|---|
| contract | 100% (n=9) | 100% (n=9) | 100% (n=9) | 78% (n=9) |
| insurance | 0% (n=9) | 22% (n=9) | 33% (n=9) | 11% (n=9) |
| invoice | 100% (n=9) | 100% (n=9) | 100% (n=9) | 33% (n=9) |
| other | 60% (n=5) | 60% (n=5) | 60% (n=5) | 60% (n=5) |
| receipt | 78% (n=9) | 78% (n=9) | 78% (n=9) | 22% (n=9) |
| utility_bill | 100% (n=9) | 100% (n=9) | 100% (n=9) | 78% (n=9) |

## Doc exact match by trap (tag)

See eval/dataset/README.md for tag meanings.

| Tag | clean | light | medium | heavy |
|---|---|---|---|---|
| account_number | 100% (n=9) | 100% (n=9) | 100% (n=9) | 78% (n=9) |
| billing_period | 100% (n=9) | 100% (n=9) | 100% (n=9) | 78% (n=9) |
| card | 80% (n=5) | 80% (n=5) | 80% (n=5) | 20% (n=5) |
| cash_change | 75% (n=4) | 75% (n=4) | 75% (n=4) | 25% (n=4) |
| currency_symbol | 75% (n=20) | 85% (n=20) | 80% (n=20) | 45% (n=20) |
| fiscal_ids | 78% (n=9) | 78% (n=9) | 78% (n=9) | 22% (n=9) |
| iban | 100% (n=18) | 100% (n=18) | 100% (n=18) | 56% (n=18) |
| installments | 0% (n=2) | 0% (n=2) | 0% (n=2) | 0% (n=2) |
| issue_before_start | 0% (n=6) | 0% (n=6) | 17% (n=6) | 0% (n=6) |
| monthly_vs_total | 100% (n=9) | 100% (n=9) | 100% (n=9) | 78% (n=9) |
| narrative | 100% (n=9) | 100% (n=9) | 100% (n=9) | 78% (n=9) |
| no_number | 67% (n=6) | 67% (n=6) | 67% (n=6) | 83% (n=6) |
| no_recipient | 78% (n=9) | 78% (n=9) | 78% (n=9) | 22% (n=9) |
| other_certificate | 0% (n=2) | 0% (n=2) | 0% (n=2) | 0% (n=2) |
| other_letter | 100% (n=2) | 100% (n=2) | 100% (n=2) | 100% (n=2) |
| other_minutes | 100% (n=1) | 100% (n=1) | 100% (n=1) | 100% (n=1) |
| overpayment | 100% (n=1) | 100% (n=1) | 100% (n=1) | 100% (n=1) |
| paid_no_due | 100% (n=1) | 100% (n=1) | 100% (n=1) | 0% (n=1) |
| previous_balance | 100% (n=3) | 100% (n=3) | 100% (n=3) | 100% (n=3) |
| stamp | 94% (n=18) | 94% (n=18) | 94% (n=18) | 67% (n=18) |
| start_after_signing | 100% (n=4) | 100% (n=4) | 100% (n=4) | 75% (n=4) |
| sum_insured | 0% (n=9) | 22% (n=9) | 33% (n=9) | 11% (n=9) |
| supply_date | 100% (n=5) | 100% (n=5) | 100% (n=5) | 40% (n=5) |
| textual_date | 78% (n=9) | 78% (n=9) | 78% (n=9) | 67% (n=9) |
| vat_breakdown | 100% (n=9) | 100% (n=9) | 100% (n=9) | 33% (n=9) |
| vat_included | 78% (n=9) | 78% (n=9) | 78% (n=9) | 22% (n=9) |

## Confidence threshold (auto-accept vs manual review)

Docs with confidence >= threshold are auto-accepted; the rest go to human review.

| Set | Threshold | Auto-accepted | Accuracy of accepted | Sent to review |
|---|---|---|---|---|
| clean | 0.5 | 100% | 74% | 0% |
| clean | 0.6 | 100% | 74% | 0% |
| clean | 0.7 | 100% | 74% | 0% |
| clean | 0.8 | 88% | 84% | 12% |
| clean | 0.9 | 82% | 90% | 18% |
| light | 0.5 | 100% | 78% | 0% |
| light | 0.6 | 100% | 78% | 0% |
| light | 0.7 | 100% | 78% | 0% |
| light | 0.8 | 92% | 80% | 8% |
| light | 0.9 | 80% | 92% | 20% |
| medium | 0.5 | 100% | 80% | 0% |
| medium | 0.6 | 100% | 80% | 0% |
| medium | 0.7 | 100% | 80% | 0% |
| medium | 0.8 | 86% | 86% | 14% |
| medium | 0.9 | 68% | 94% | 32% |
| heavy | 0.5 | 94% | 49% | 6% |
| heavy | 0.6 | 68% | 59% | 32% |
| heavy | 0.7 | 32% | 81% | 68% |
| heavy | 0.8 | 10% | 100% | 90% |
| heavy | 0.9 | 0% | - | 100% |

## Cost and latency

| Set | Avg in tok | Avg out tok | Avg latency, s | Cost / doc, USD |
|---|---|---|---|---|
| clean | 3584 | 385 | 3.6 | 0.0110 |
| light | 3246 | 377 | 3.4 | 0.0103 |
| medium | 3250 | 390 | 3.5 | 0.0104 |
| heavy | 3254 | 445 | 3.9 | 0.0110 |

## Most common errors

- `issue_date` on `heavy`: 13 errors
- `total_amount` on `heavy`: 12 errors
- `total_amount` on `clean`: 9 errors
- `total_amount` on `light`: 7 errors
- `total_amount` on `medium`: 6 errors
- `recipient` on `heavy`: 6 errors
- `document_number` on `heavy`: 4 errors
- `due_date` on `heavy`: 4 errors
- `recipient` on `clean`: 2 errors
- `document_number` on `clean`: 2 errors
