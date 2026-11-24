# Q&A agent eval: claude-sonnet-5-5 (effort low)

Test-set documents loaded from labels; today = 2026-04-01. Pass = every expected value appears in the answer.

**13/13 passed** · cost $0.116 total, $0.0089 per question · avg latency 4.0 s

| # | Kind | Question | Pass | Tool calls | Turns |
|---|---|---|---|---|---|
| 1 | fact | Do kiedy obowiązuje polisa nr 3668999204? | ✅ | `search_documents({"query": "3668999204"})` | 2 |
| 2 | fact | Do kiedy obowiązuje polisa nr 6415345180? | ✅ | `search_documents({"query": "6415345180"})` | 2 |
| 3 | fact | Do kiedy obowiązuje polisa nr 1778079805? | ✅ | `search_documents({"query": "1778079805"})` | 2 |
| 4 | fact | How much has to be paid for document 49/11/2025, and by what date? | ✅ | `search_documents({"query": "49/11/2025", "limit": 10})` | 2 |
| 5 | fact | How much has to be paid for document INV-2026-8598, and by what date? | ✅ | `search_documents({"query": "INV-2026-8598", "limit": 5})` | 2 |
| 6 | fact | How much has to be paid for document E486/2026, and by what date? | ✅ | `search_documents({"query": "E486/2026", "limit": 10})` | 2 |
| 7 | fact | How much has to be paid for document E514/2026, and by what date? | ✅ | `search_documents({"query": "E514/2026", "limit": 10})` | 2 |
| 8 | fact | What is the total value of contract 5/2025, and who is it with? | ✅ | `search_documents({"query": "5/2025", "doc_type": "contract", "limit": 20})` | 2 |
| 9 | fact | What is the total value of contract 27/2025, and who is it with? | ✅ | `search_documents({"query": "27/2025", "doc_type": "contract", "limit": 20})` | 2 |
| 10 | list | Which payments are due in the next 14 days? | ✅ | `list_deadlines({"within_days": 14, "past_days": 0, "kind": "payment_due"})` | 2 |
| 11 | list | Which contracts or policies expire within the next month? | ✅ | `list_deadlines({"within_days": 31, "past_days": 0, "kind": "expires"})` | 2 |
| 12 | aggregate | How many receipts are in the database? | ✅ | `search_documents({"doc_type": "receipt", "limit": 1})` | 2 |
| 13 | grounding | When does the Allianz insurance expire? | ✅ | `search_documents({"query": "Allianz", "doc_type": "insurance", "limit": 20}), search_documents({"query": "Allianz", "limit": 20})` | 3 |

## Answers

**1. Do kiedy obowiązuje polisa nr 3668999204?** ✅  
expected: 2026-04-06

> Polisa nr 3668999204 (#24, Omega TU S.A.) obowiązuje od 2025-04-07 do 2026-04-06. Do końca ważności zostało 5 dni.
> 
> Składka wynosi 399,32 PLN. Dokument ma status auto_accepted. Warto więc odnowić polisę w najbliższych dniach.

**2. Do kiedy obowiązuje polisa nr 6415345180?** ✅  
expected: 2027-06-03

> Polisa nr 6415345180 (#5, Omega TU S.A., ubezpieczony: Piotr Wzorcowy) obowiązuje od 2026-06-04 do 2027-06-03.
> 
> Do końca ochrony zostało 428 dni (licząc od dziś, 2026-04-01). Polisa jeszcze nie weszła w życie. Zacznie obowiązywać za 64 dni.
> 
> Składka wynosi 1626,49 PLN. Data wystawienia dokumentu to 2026-06-03, czyli jest późniejsza niż dzisiejsza data. Warto sprawdzić, czy ta data została odczytana poprawnie.

**3. Do kiedy obowiązuje polisa nr 1778079805?** ✅  
expected: 2027-09-23

> Polisa nr 1778079805 (#12, Omega TU S.A.) obowiązuje od 2026-09-24 do 2027-09-23. Do końca okresu ochrony zostało 540 dni, licząc od dziś (2026-04-01). Polisa jeszcze się nie zaczęła. Rozpocznie się za 176 dni.
> 
> Składka wynosi 2317,73 EUR. Ubezpieczoną osobą jest Anna Przykładowa. Dokument ma status auto_accepted.

**4. How much has to be paid for document 49/11/2025, and by what date?** ✅  
expected: 2025-12-29, 1982.75

> Dokument 49/11/2025 to faktura #13 od Delta Serwis Sp. z o.o. Dokument ma status auto_accepted.
> 
> • Kwota do zapłaty: 1982,75 PLN
> • Termin płatności: 2025-12-29
> 
> Termin minął 93 dni temu (dziś jest 2026-04-01). W danych nie ma informacji, czy faktura została opłacona. Sprawdź to, zanim wykonasz przelew.

**5. How much has to be paid for document INV-2026-8598, and by what date?** ✅  
expected: 2026-04-01, 3507.17

> Invoice INV-2026-8598 (#16) from Acme Office Supplies is for 3,507.17 EUR. It is due on 2026-04-01, which is today, so 0 days are left.
> 
> The invoice was issued on 2026-03-02 and is addressed to John Sample. Its status is auto_accepted.

**6. How much has to be paid for document E486/2026, and by what date?** ✅  
expected: 2026-07-23, 493.32

> Document #20 is an invoice from Adventure Works Ltd to Sample & Co Bookkeeping.
> 
> • Amount to pay: 493.32 GBP
> • Due date: 2026-07-23, which is 113 days from today (2026-04-01)
> 
> The invoice's issue date is 2026-06-23, which is after today's date. You may want to check that date. The document's status is auto_accepted.

**7. How much has to be paid for document E514/2026, and by what date?** ✅  
expected: 2026-07-03, 7578.02

> Document #33 is an invoice from Proseware Consulting to Sample & Co Bookkeeping. The number is E514/2026.
> 
> • Amount to pay: 7,578.02 EUR
> • Due date: 2026-07-03, which is 93 days from today (2026-04-01)
> 
> The issue date on the invoice is 2026-06-26, which is after today's date. You may want to check that date. The document's status is auto_accepted.

**8. What is the total value of contract 5/2025, and who is it with?** ✅  
expected: 5116.44

> Contract 5/2025 (#7) is with Biuro Rachunkowe Sigma. Its total value is 5,116.44 PLN.
> 
> The contract was issued on 2025-06-07 to Piotr Wzorcowy. It was valid from 2025-06-07 until 2025-12-06, so it has already expired.

**9. What is the total value of contract 27/2025, and who is it with?** ✅  
expected: 16508.64

> Contract 27/2025 (#23) is with Biuro Rachunkowe Sigma. Its total value is 16,508.64 PLN.
> 
> The contract was issued on 2025-12-05 and is valid until 2027-12-04. The recipient is Piotr Wzorcowy.

**10. Which payments are due in the next 14 days?** ✅  
expected: #16

> There is one payment due in the next 14 days:
> 
> • #16 is invoice INV-2026-8598 from Acme Office Supplies. The amount is 3507.17 EUR. It is due 2026-04-01, which is today (0 days left). Its status is auto_accepted.

**11. Which contracts or policies expire within the next month?** ✅  
expected: #24, #40

> Two documents expire within the next month:
> 
> • #24: insurance policy with Omega TU S.A., no. 3668999204. It expires on 2026-04-06, which is 5 days from now. The amount is 399.32 PLN.
> • #40: insurance policy with Contoso Insurance plc, no. POL-4247-8606. It expires on 2026-04-24, which is 23 days from now. The amount is 2,249.12 USD.
> 
> No contracts expire in this period. Both policies were auto-accepted.

**12. How many receipts are in the database?** ✅  
expected: 9

> There are 9 receipts in the database.

**13. When does the Allianz insurance expire?** ✅  
expected: (no invented dates)

> I couldn't find any Allianz documents. I searched insurance documents and then all document types, and both searches returned nothing.
> 
> Here's what you could check:
> • The insurer may be stored under a different name, such as a subsidiary or a broker.
> • The policy may not have been uploaded yet.
> 
> If you tell me another name or the policy number, I'll search again.

