# Extraction eval report

Predictions: `eval/predictions_test/claude-sonnet-5-5/extract_v2`

## Field accuracy by set

| Field | clean | light | medium | heavy |
|---|---|---|---|---|
| doc_type | 100% | 100% | 100% | 100% |
| language | 100% | 100% | 100% | 100% |
| counterparty | 100% | 100% | 100% | 94% |
| recipient | 100% | 100% | 100% | 92% |
| document_number | 100% | 100% | 98% | 86% |
| issue_date | 100% | 100% | 100% | 76% |
| currency | 100% | 100% | 100% | 98% |
| total_amount | 100% | 100% | 100% | 84% |
| due_date | 100% | 100% | 100% | 96% |
| valid_from | 100% | 100% | 100% | 96% |
| valid_until | 100% | 100% | 100% | 100% |
| **doc exact match** | **100%** | **100%** | **98%** | **60%** |
| failed calls / invalid JSON | 0 | 0 | 0 | 0 |

## Doc exact match by document type

| Type | clean | light | medium | heavy |
|---|---|---|---|---|
| contract | 100% (n=9) | 100% (n=9) | 100% (n=9) | 56% (n=9) |
| insurance | 100% (n=9) | 100% (n=9) | 89% (n=9) | 78% (n=9) |
| invoice | 100% (n=9) | 100% (n=9) | 100% (n=9) | 67% (n=9) |
| other | 100% (n=5) | 100% (n=5) | 100% (n=5) | 80% (n=5) |
| receipt | 100% (n=9) | 100% (n=9) | 100% (n=9) | 22% (n=9) |
| utility_bill | 100% (n=9) | 100% (n=9) | 100% (n=9) | 67% (n=9) |

## Doc exact match by trap (tag)

See eval/dataset/README.md for tag meanings.

| Tag | clean | light | medium | heavy |
|---|---|---|---|---|
| account_number | 100% (n=9) | 100% (n=9) | 100% (n=9) | 67% (n=9) |
| billing_period | 100% (n=9) | 100% (n=9) | 100% (n=9) | 67% (n=9) |
| card | 100% (n=6) | 100% (n=6) | 100% (n=6) | 0% (n=6) |
| cash_change | 100% (n=3) | 100% (n=3) | 100% (n=3) | 67% (n=3) |
| currency_symbol | 100% (n=24) | 100% (n=24) | 96% (n=24) | 54% (n=24) |
| fiscal_ids | 100% (n=9) | 100% (n=9) | 100% (n=9) | 22% (n=9) |
| iban | 100% (n=18) | 100% (n=18) | 100% (n=18) | 67% (n=18) |
| installments | 100% (n=3) | 100% (n=3) | 100% (n=3) | 100% (n=3) |
| issue_before_start | 100% (n=6) | 100% (n=6) | 83% (n=6) | 67% (n=6) |
| monthly_vs_total | 100% (n=9) | 100% (n=9) | 100% (n=9) | 56% (n=9) |
| narrative | 100% (n=9) | 100% (n=9) | 100% (n=9) | 56% (n=9) |
| no_number | 100% (n=5) | 100% (n=5) | 100% (n=5) | 60% (n=5) |
| no_recipient | 100% (n=9) | 100% (n=9) | 100% (n=9) | 22% (n=9) |
| other_certificate | 100% (n=2) | 100% (n=2) | 100% (n=2) | 100% (n=2) |
| other_letter | 100% (n=2) | 100% (n=2) | 100% (n=2) | 50% (n=2) |
| other_minutes | 100% (n=1) | 100% (n=1) | 100% (n=1) | 100% (n=1) |
| paid_no_due | 100% (n=1) | 100% (n=1) | 100% (n=1) | 100% (n=1) |
| previous_balance | 100% (n=4) | 100% (n=4) | 100% (n=4) | 75% (n=4) |
| stamp | 100% (n=16) | 100% (n=16) | 100% (n=16) | 44% (n=16) |
| start_after_signing | 100% (n=3) | 100% (n=3) | 100% (n=3) | 67% (n=3) |
| sum_insured | 100% (n=9) | 100% (n=9) | 89% (n=9) | 78% (n=9) |
| supply_date | 100% (n=6) | 100% (n=6) | 100% (n=6) | 50% (n=6) |
| textual_date | 100% (n=13) | 100% (n=13) | 92% (n=13) | 62% (n=13) |
| vat_breakdown | 100% (n=9) | 100% (n=9) | 100% (n=9) | 67% (n=9) |
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
| medium | 0.5 | 100% | 98% | 0% |
| medium | 0.6 | 100% | 98% | 0% |
| medium | 0.7 | 100% | 98% | 0% |
| medium | 0.8 | 100% | 98% | 0% |
| medium | 0.9 | 54% | 100% | 46% |
| heavy | 0.5 | 56% | 86% | 44% |
| heavy | 0.6 | 26% | 100% | 74% |
| heavy | 0.7 | 12% | 100% | 88% |
| heavy | 0.8 | 4% | 100% | 96% |
| heavy | 0.9 | 0% | - | 100% |

## Cost and latency

| Set | Avg in tok | Avg out tok | Avg latency, s | 
|---|---|---|---|
| clean | 4270 | 347 | 2.9 |
| light | 3935 | 352 | 3.2 |
| medium | 3942 | 364 | 3.3 |
| heavy | 3943 | 449 | 3.8 |

## Most common errors

- `issue_date` on `heavy`: 12 errors
- `total_amount` on `heavy`: 8 errors
- `document_number` on `heavy`: 7 errors
- `recipient` on `heavy`: 4 errors
- `counterparty` on `heavy`: 3 errors
- `valid_from` on `heavy`: 2 errors
- `due_date` on `heavy`: 2 errors
- `document_number` on `medium`: 1 errors
- `currency` on `heavy`: 1 errors
