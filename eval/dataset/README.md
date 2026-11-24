# Eval dataset (v2)

Synthetic business documents with ground-truth labels for testing extraction.
**All data is fabricated:** companies, people, addresses, tax IDs and IBANs are fictional, and every page carries a footer saying so.

Regenerate:

```
python eval/generate_dataset.py --seed 42          # pdf/, labels/, manifest.csv
python eval/make_scans.py --seed 42                # scans/{light,medium,heavy}/ (not in git)
```

## Composition

- 50 documents: 9 each of `invoice`, `contract`, `insurance`, `receipt`, `utility_bill`, plus 5 `other` (certificates, notice letters, meeting minutes).
- Languages rotate uk / pl / en inside each type.
- 4 layouts: `classic`, `boxed` (letterhead with a box of dates and numbers), `narrative` (contract-style text), `receipt` (narrow till slip).
- About a quarter of the documents carry a "COPY / KOPIA / КОПІЯ" stamp (`noisy`). The stamp is always placed below the content, so it never covers a labeled value.
- `scans/` holds the same 50 PDFs rasterised and degraded at 3 levels. Scans share labels with the clean PDF of the same name.

## Labeling conventions

| Field | Rule |
|---|---|
| `counterparty` | Issuing party: seller, provider, insurer, utility, shop, or the organisation issuing an `other` document. |
| `recipient` | Addressed party: buyer, client, policyholder, customer, or addressee. For a certificate, the person it certifies. `null` for receipts and meeting minutes. |
| `document_number` | Number as printed, without the label (`№`, `nr`, `No.`, `Ref.`). Other numbers are never the document number: account number, tax ID, IBAN, fiscal / terminal ID. `null` if the document has no number. |
| `issue_date` | Issue / signing / bill date. Not the supply date and not the start of validity. |
| `currency` | ISO code of `total_amount`. `null` when `total_amount` is `null`. |
| `total_amount` | **invoice:** gross (incl. VAT). **utility_bill:** "amount due" (charges plus previous balance, minus overpayment). **receipt:** total paid, not cash tendered or change. **insurance:** the **premium**, not the sum insured. **contract:** the total contract value, not the monthly fee. **other:** `null`. |
| `due_date` | Only for `invoice` and `utility_bill`. `null` if an invoice is already paid. Always `null` for insurance, even when the premium is paid in instalments with dates. |
| `valid_from` / `valid_until` | Only for `insurance` and `contract`: the period of cover or effect, inclusive. |

> Note: prompt v1 and the old `schema.json` description of `total_amount` ("to pay / insured / contract value") are ambiguous for insurance: premium or sum insured? The v1 baseline was run with that wording, and the model chose the sum insured on all 9 policies. Prompt v2 and the current schema description state the convention above. Prompt v1 also did not cover the certificate recipient or fiscal numbers on receipts. v2 states both.

## Traps (`_meta.tags`)

Each label lists the traps present in its document, for per-trap error analysis in `eval.py`:

| Tag | What makes it hard |
|---|---|
| `vat_breakdown` | net, VAT and gross amounts all printed |
| `supply_date` | supply / sale date next to the issue date |
| `paid_no_due` | paid invoice: no due date, so expect `null` |
| `account_number`, `billing_period` | utility bill: account number and billing month next to the bill number and date |
| `previous_balance`, `overpayment` | amount due differs from the period's charges |
| `sum_insured` | sum insured (large) next to the premium |
| `installments` | instalment dates that are not `due_date` |
| `issue_before_start` | policy issue date ≠ start of cover |
| `monthly_vs_total` | monthly fee next to the total contract value |
| `start_after_signing` | contract signed before it takes effect |
| `no_number` | document has no number, so expect `null` |
| `no_recipient` | receipt: recipient is `null` |
| `vat_included`, `cash_change`, `card`, `fiscal_ids` | receipt: VAT line, cash tendered and change, card digits, fiscal and terminal IDs |
| `iban` | long bank number on the page |
| `textual_date` | dates such as "21 lipca 2026 r." or "14 вересня 2025 р." |
| `currency_symbol` | `zł`, `грн`, `€`, `£`, `$` instead of an ISO code |
| `foreign_currency` | uk / pl document in USD / EUR |
| `narrative` | values embedded in running text |
| `stamp` | COPY stamp on the page |
| `other_*` | non-target document type |
