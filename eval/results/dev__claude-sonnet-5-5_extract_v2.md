# Extraction eval report

Predictions: `eval/predictions/claude-sonnet-5-5/extract_v2`

## Field accuracy by set

| Field | clean | light | medium | heavy |
|---|---|---|---|---|
| doc_type | 100% | 100% | 100% | 100% |
| language | 100% | 100% | 100% | 100% |
| counterparty | 100% | 100% | 100% | 96% |
| recipient | 100% | 100% | 100% | 96% |
| document_number | 100% | 100% | 100% | 92% |
| issue_date | 100% | 100% | 100% | 74% |
| currency | 100% | 100% | 100% | 100% |
| total_amount | 100% | 100% | 100% | 88% |
| due_date | 100% | 100% | 100% | 90% |
| valid_from | 100% | 100% | 100% | 96% |
| valid_until | 100% | 100% | 100% | 98% |
| **doc exact match** | **100%** | **100%** | **100%** | **54%** |
| failed calls / invalid JSON | 0 | 0 | 0 | 0 |

## Doc exact match by document type

| Type | clean | light | medium | heavy |
|---|---|---|---|---|
| contract | 100% (n=9) | 100% (n=9) | 100% (n=9) | 67% (n=9) |
| insurance | 100% (n=9) | 100% (n=9) | 100% (n=9) | 56% (n=9) |
| invoice | 100% (n=9) | 100% (n=9) | 100% (n=9) | 33% (n=9) |
| other | 100% (n=5) | 100% (n=5) | 100% (n=5) | 100% (n=5) |
| receipt | 100% (n=9) | 100% (n=9) | 100% (n=9) | 22% (n=9) |
| utility_bill | 100% (n=9) | 100% (n=9) | 100% (n=9) | 67% (n=9) |

## Doc exact match by trap (tag)

See eval/dataset/README.md for tag meanings.

| Tag | clean | light | medium | heavy |
|---|---|---|---|---|
| account_number | 100% (n=9) | 100% (n=9) | 100% (n=9) | 67% (n=9) |
| billing_period | 100% (n=9) | 100% (n=9) | 100% (n=9) | 67% (n=9) |
| card | 100% (n=5) | 100% (n=5) | 100% (n=5) | 20% (n=5) |
| cash_change | 100% (n=4) | 100% (n=4) | 100% (n=4) | 25% (n=4) |
| currency_symbol | 100% (n=20) | 100% (n=20) | 100% (n=20) | 55% (n=20) |
| fiscal_ids | 100% (n=9) | 100% (n=9) | 100% (n=9) | 22% (n=9) |
| iban | 100% (n=18) | 100% (n=18) | 100% (n=18) | 50% (n=18) |
| installments | 100% (n=2) | 100% (n=2) | 100% (n=2) | 50% (n=2) |
| issue_before_start | 100% (n=6) | 100% (n=6) | 100% (n=6) | 67% (n=6) |
| monthly_vs_total | 100% (n=9) | 100% (n=9) | 100% (n=9) | 67% (n=9) |
| narrative | 100% (n=9) | 100% (n=9) | 100% (n=9) | 67% (n=9) |
| no_number | 100% (n=6) | 100% (n=6) | 100% (n=6) | 83% (n=6) |
| no_recipient | 100% (n=9) | 100% (n=9) | 100% (n=9) | 22% (n=9) |
| other_certificate | 100% (n=2) | 100% (n=2) | 100% (n=2) | 100% (n=2) |
| other_letter | 100% (n=2) | 100% (n=2) | 100% (n=2) | 100% (n=2) |
| other_minutes | 100% (n=1) | 100% (n=1) | 100% (n=1) | 100% (n=1) |
| overpayment | 100% (n=1) | 100% (n=1) | 100% (n=1) | 100% (n=1) |
| paid_no_due | 100% (n=1) | 100% (n=1) | 100% (n=1) | 0% (n=1) |
| previous_balance | 100% (n=3) | 100% (n=3) | 100% (n=3) | 67% (n=3) |
| stamp | 100% (n=18) | 100% (n=18) | 100% (n=18) | 72% (n=18) |
| start_after_signing | 100% (n=4) | 100% (n=4) | 100% (n=4) | 75% (n=4) |
| sum_insured | 100% (n=9) | 100% (n=9) | 100% (n=9) | 56% (n=9) |
| supply_date | 100% (n=5) | 100% (n=5) | 100% (n=5) | 40% (n=5) |
| textual_date | 100% (n=9) | 100% (n=9) | 100% (n=9) | 67% (n=9) |
| vat_breakdown | 100% (n=9) | 100% (n=9) | 100% (n=9) | 33% (n=9) |
| vat_included | 100% (n=9) | 100% (n=9) | 100% (n=9) | 22% (n=9) |

## Confidence threshold (auto-accept vs manual review)

Docs with confidence >= threshold are auto-accepted; the rest go to human review.

| Set | Threshold | Auto-accepted | Accuracy of accepted | Sent to review |
|---|---|---|---|---|
| clean | 0.5 | 100% | 100% | 0% |
| clean | 0.6 | 100% | 100% | 0% |
| clean | 0.7 | 100% | 100% | 0% |
| clean | 0.8 | 100% | 100% | 0% |
| clean | 0.9 | 100% | 100% | 0% |
| light | 0.5 | 100% | 100% | 0% |
| light | 0.6 | 100% | 100% | 0% |
| light | 0.7 | 100% | 100% | 0% |
| light | 0.8 | 100% | 100% | 0% |
| light | 0.9 | 100% | 100% | 0% |
| medium | 0.5 | 100% | 100% | 0% |
| medium | 0.6 | 100% | 100% | 0% |
| medium | 0.7 | 100% | 100% | 0% |
| medium | 0.8 | 98% | 100% | 2% |
| medium | 0.9 | 46% | 100% | 54% |
| heavy | 0.5 | 38% | 89% | 62% |
| heavy | 0.6 | 22% | 100% | 78% |
| heavy | 0.7 | 8% | 100% | 92% |
| heavy | 0.8 | 0% | - | 100% |
| heavy | 0.9 | 0% | - | 100% |

## Cost and latency

| Set | Avg in tok | Avg out tok | Avg latency, s | 
|---|---|---|---|
| clean | 4273 | 348 | 3.1 |
| light | 3935 | 351 | 3.1 |
| medium | 3939 | 370 | 3.5 |
| heavy | 3943 | 435 | 4.0 |

## Most common errors

- `issue_date` on `heavy`: 13 errors
- `total_amount` on `heavy`: 6 errors
- `due_date` on `heavy`: 5 errors
- `document_number` on `heavy`: 4 errors
- `recipient` on `heavy`: 2 errors
- `valid_from` on `heavy`: 2 errors
- `counterparty` on `heavy`: 2 errors
- `valid_until` on `heavy`: 1 errors
