# Q&A agent eval: claude-haiku-5-5 (effort low)

Test-set documents loaded from labels; today = 2026-04-01. Pass = every expected value appears in the answer.

**12/13 passed** · cost $0.008 total, $0.0006 per question · avg latency 3.7 s

| # | Kind | Question | Pass | Tool calls | Turns |
|---|---|---|---|---|---|
| 1 | fact | Do kiedy obowiązuje polisa nr 3668999204? | ✅ | `search_documents({"query": "3668999204", "limit": 5})` | 2 |
| 2 | fact | Do kiedy obowiązuje polisa nr 6415345180? | ✅ | `search_documents({"query": "6415345180", "limit": 5})` | 2 |
| 3 | fact | Do kiedy obowiązuje polisa nr 1778079805? | ✅ | `search_documents({"query": "1778079805", "doc_type": "insurance", "limit": 5})` | 2 |
| 4 | fact | How much has to be paid for document 49/11/2025, and by what date? | ✅ | `search_documents({"query": "49/11/2025", "limit": 5})` | 2 |
| 5 | fact | How much has to be paid for document INV-2026-8598, and by what date? | ✅ | `search_documents({"query": "INV-2026-8598", "limit": 5})` | 2 |
| 6 | fact | How much has to be paid for document E486/2026, and by what date? | ✅ | `search_documents({"query": "E486/2026", "limit": 5})` | 2 |
| 7 | fact | How much has to be paid for document E514/2026, and by what date? | ✅ | `search_documents({"query": "E514/2026", "limit": 5})` | 2 |
| 8 | fact | What is the total value of contract 5/2025, and who is it with? | ✅ | `search_documents({"query": "5/2025", "doc_type": "contract", "limit": 10})` | 2 |
| 9 | fact | What is the total value of contract 27/2025, and who is it with? | ✅ | `search_documents({"query": "27/2025", "doc_type": "contract", "limit": 10})` | 2 |
| 10 | list | Which payments are due in the next 14 days? | ✅ | `list_deadlines({"within_days": 14, "past_days": 0, "kind": "payment_due"})` | 2 |
| 11 | list | Which contracts or policies expire within the next month? | ✅ | `list_deadlines({"within_days": 30, "past_days": 0, "kind": "expires"})` | 2 |
| 12 | aggregate | How many receipts are in the database? | ✅ | `search_documents({"doc_type": "receipt", "limit": 1}), search_documents({"query": "", "doc_type": "receipt", "limit": 1})` | 3 |
| 13 | grounding | When does the Allianz insurance expire? | ❌ | `search_documents({"query": "Allianz", "doc_type": "insurance", "limit": 10}), search_documents({"query": "Allianz", "limit": 10}), search_documents({"query": "Allianz", "limit": 10}), search_documents({"query": "Allianz", "limit": 10}), search_documents({"query": "Allianz", "limit": 10}), list_deadlines({"within_days": 366, "past_days": 366, "kind": "expires"})` | 6 |

## Answers

**1. Do kiedy obowiązuje polisa nr 3668999204?** ✅  
expected: 2026-04-06

> Polisa nr 3668999204 (#24, Omega TU S.A., ubezpieczający: Jan Testowy) obowiązuje od 2025-04-07 do 2026-04-06. Do wygaśnięcia zostało 5 dni.
> 
> Warto zadbać o jej odnowienie na czas. Mogę sprawdzić inne dokumenty wygasające w najbliższym czasie.

**2. Do kiedy obowiązuje polisa nr 6415345180?** ✅  
expected: 2027-06-03

> Polisa nr 6415345180 (#5, Omega TU S.A., ubezpieczony: Piotr Wzorcowy) obowiązuje **do 2027-06-03**. Okres ważności zaczyna się 2026-06-04.
> 
> Dokument ma datę wystawienia 2026-06-03, czyli jest późniejsza niż dzisiejsza data (2026-04-01). Warto sprawdzić, czy data wystawienia została odczytana poprawnie. Składka wynosi 1626,49 PLN.

**3. Do kiedy obowiązuje polisa nr 1778079805?** ✅  
expected: 2027-09-23

> Polisa nr 1778079805 (#12, Omega TU S.A., ubezpieczony: Anna Przykładowa) jest ważna **do 2027-09-23**. Do wygaśnięcia zostało 540 dni.
> 
> Zwracam jednak uwagę na dwie rzeczy:
> • Według dokumentu okres ważności zaczyna się 2026-09-24, czyli dopiero za kilka miesięcy. Data wystawienia to również 2026-09-24. Warto sprawdzić, czy data nie została błędnie odczytana.
> • Dokument ma status auto_accepted (zaakceptowany automatycznie, bez ręcznej weryfikacji), więc dobrze potwierdzić daty w oryginale.

**4. How much has to be paid for document 49/11/2025, and by what date?** ✅  
expected: 2025-12-29, 1982.75

> Document #13 (invoice 49/11/2025 from Delta Serwis Sp. z o.o.) totals 1982.75 PLN. It was due on 2025-12-29, so it is 93 days overdue as of today (2026-04-01). My records don't show whether it has been paid, so please check that before taking action.

**5. How much has to be paid for document INV-2026-8598, and by what date?** ✅  
expected: 2026-04-01, 3507.17

> Document #16 (invoice INV-2026-8598 from Acme Office Supplies, issued 2026-03-02) totals 3,507.17 EUR. It is due on 2026-04-01, which is today, so 0 days are left.

**6. How much has to be paid for document E486/2026, and by what date?** ✅  
expected: 2026-07-23, 493.32

> Document #20 (invoice E486/2026 from Adventure Works Ltd to Sample & Co Bookkeeping) requires a payment of **493.32 GBP**, due by **2026-07-23**, which is 113 days from today.
> 
> The invoice's issue date is listed as 2026-06-23, which is after today's date (2026-04-01). Please check that date against the original document before paying.

**7. How much has to be paid for document E514/2026, and by what date?** ✅  
expected: 2026-07-03, 7578.02

> Document E514/2026 (#33, invoice from Proseware Consulting) requires a payment of **7,578.02 EUR**, due by **2026-07-03**. That is 93 days from today (2026-04-01).
> 
> The invoice's issue date is listed as 2026-06-26, which is after today's date. That may be a data-entry error, so check it against the original invoice before relying on the due date.

**8. What is the total value of contract 5/2025, and who is it with?** ✅  
expected: 5116.44

> Contract 5/2025 (#7) is with **Biuro Rachunkowe Sigma**, and the total value is **5,116.44 PLN**. The contract was issued on 2025-06-07 and was addressed to Piotr Wzorcowy.
> 
> The contract ran from 2025-06-07 to 2025-12-06, so it has already expired. Its status is auto_accepted, not needs_review.

**9. What is the total value of contract 27/2025, and who is it with?** ✅  
expected: 16508.64

> Contract 27/2025 is with Biuro Rachunkowe Sigma (recipient: Piotr Wzorcowy). Its total value is 16,508.64 PLN.
> 
> It was issued on 2025-12-05 and is valid from 2025-12-05 to 2027-12-04. Status: auto-accepted, not manually reviewed.
> 
> Source: #23

**10. Which payments are due in the next 14 days?** ✅  
expected: #16

> Only one payment is due in the next 14 days:
> 
> • #16 Acme Office Supplies, invoice INV-2026-8598: 3507.17 EUR, due 2026-04-01 (today, 0 days left).

**11. Which contracts or policies expire within the next month?** ✅  
expected: #24, #40

> Two insurance policies expire within the next 30 days:
> 
> • #24 – Omega TU S.A., policy 3668999204, expires 2026-04-06 (5 days left). Premium 399.32 PLN.
> • #40 – Contoso Insurance plc, policy POL-4247-8606, expires 2026-04-24 (23 days left). Premium 2,249.12 USD.
> 
> Neither has been flagged for review (both auto-accepted). No contracts expire in this window.

**12. How many receipts are in the database?** ✅  
expected: 9

> There are 9 receipts in the database.

**13. When does the Allianz insurance expire?** ❌  
expected: (no invented dates)

> Could not find an answer. Try rephrasing the question.

