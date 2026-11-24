#!/usr/bin/env python3
"""DocFlow AI: synthetic dataset generator (v2).

Produces single-page PDFs of 5 business document types plus "other", in
Ukrainian, Polish and English, with ground-truth JSON labels (same keys as the
extraction schema) and a manifest.csv.

v2 makes the task realistic rather than trivial:
  * field labels in the document's own language, 4 layouts (classic, boxed,
    narrative, receipt), numeric and textual dates, currency codes or symbols;
  * distractors: net/VAT/gross, supply date, previous balance, sum insured vs
    premium, monthly fee vs contract value, cash tendered and change, account
    and fiscal numbers, IBANs, signing date != start of validity;
  * fields that are genuinely absent (paid invoice without due date, contract
    or receipt without a number, receipt without recipient) -> null.

Labeling conventions: eval/dataset/README.md.  Each label's _meta.tags lists
the traps present in that document, for per-trap error analysis.

Usage:
    pip install -r requirements.txt
    python eval/generate_dataset.py                 # 9 per type + 5 other = 50 docs
    python eval/generate_dataset.py --per-type 2 --other 1 --out /tmp/ds

Fonts: needs a TTF with Cyrillic + Polish glyphs. Auto-detected (DejaVu on
Linux, Arial on Windows/macOS); override with DOCFLOW_FONT / DOCFLOW_FONT_BOLD.

All data is fabricated. No real people, companies, IDs or accounts.
"""
import argparse
import calendar
import csv
import hashlib
import json
import math
import os
import random
from datetime import date, timedelta
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

HERE = Path(__file__).resolve().parent
W, H = A4
LM, RM = 50, W - 50  # left / right margin

FONT_CANDIDATES = [  # (regular, bold)
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("C:/Windows/Fonts/DejaVuSans.ttf", "C:/Windows/Fonts/DejaVuSans-Bold.ttf"),
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
]


def find_fonts():
    env = (os.environ.get("DOCFLOW_FONT"), os.environ.get("DOCFLOW_FONT_BOLD"))
    if env[0]:
        return env[0], env[1] or env[0]
    for reg, bold in FONT_CANDIDATES:
        if Path(reg).is_file() and Path(bold).is_file():
            return reg, bold
    raise SystemExit("No suitable TTF font found. Set DOCFLOW_FONT and DOCFLOW_FONT_BOLD.")


def register_fonts():
    reg, bold = find_fonts()
    pdfmetrics.registerFont(TTFont("F", reg))
    pdfmetrics.registerFont(TTFont("FB", bold))


# ---- fake reference data (edit freely) -------------------------------------
LANGS = ("uk", "pl", "en")
DOC_TYPES = ("invoice", "contract", "insurance", "receipt", "utility_bill")

VENDORS = {
    "uk": ["ТОВ «Дніпро-Сервіс»", "ТОВ «ЛінкНет»", "ФОП Мельник О. І.", "ТОВ «Офіс-Постач Тест»"],
    "pl": ["Gamma Telekom Sp. z o.o.", "Delta Serwis Sp. z o.o.", "Biuro Rachunkowe Sigma", "Kappa IT s.c."],
    "en": ["Fabrikam Services LLC", "Adventure Works Ltd", "Proseware Consulting", "Acme Office Supplies"],
}
INSURERS = {
    "uk": ["ПрАТ «СК Тестова Гарантія»", "ТДВ «Страхова компанія Приклад»"],
    "pl": ["Beta Ubezpieczenia S.A.", "Omega TU S.A."],
    "en": ["Contoso Insurance plc", "Litware Assurance Ltd"],
}
UTILITIES = {
    "uk": ["ТОВ «Карпатська Енергія»", "КП «Міськводоканал-Тест»"],
    "pl": ["Alfa-Energia Sp. z o.o.", "Wodociągi Przykładowe Sp. z o.o."],
    "en": ["Northwind Utilities Ltd", "Tailspin Water plc"],
}
SHOPS = {
    "uk": ["ТОВ «Продмаркет Тест»", "ФОП Петренко Т. С.", "Магазин «Канцтовари-Приклад»"],
    "pl": ["Sklep Przykład Sp. z o.o.", "Kiosk Gamma", "Market Testowy s.c."],
    "en": ["Wingtip Grocers", "Acme Office Supplies", "Blue Yonder Café"],
}
PEOPLE = {
    "uk": ["Олег Тестовий", "Марія Прикладна", "Ірина Зразкова"],
    "pl": ["Jan Testowy", "Anna Przykładowa", "Piotr Wzorcowy"],
    "en": ["John Sample", "Jane Example", "Alex Specimen"],
}
CLIENT_FIRMS = {
    "uk": ["ФОП Тестовий О. В.", "ТОВ «Бухгалтерія Плюс»"],
    "pl": ["Biuro Testowe Sp. z o.o.", "Kancelaria Przykład"],
    "en": ["Example Accounting Ltd", "Sample & Co Bookkeeping"],
}
ADDRESSES = {
    "uk": ["вул. Тестова, 12, м. Київ, 01001", "просп. Прикладний, 5, оф. 3, м. Львів, 79000",
           "вул. Зразкова, 41, м. Дніпро, 49000"],
    "pl": ["ul. Przykładowa 5, 00-001 Warszawa", "ul. Testowa 17/4, 30-002 Kraków", "al. Wzorcowa 8, 50-003 Wrocław"],
    "en": ["12 Sample Street, London EC1A 1AA", "3 Example Road, Manchester M1 2AB", "Unit 7, Test Park, Leeds LS1 4CD"],
}
CITY = {"uk": ["м. Київ", "м. Львів", "м. Дніпро"], "pl": ["Warszawa", "Kraków", "Wrocław"],
        "en": ["London", "Manchester", "Leeds"]}

MONTHS_GEN = {
    "uk": ["січня", "лютого", "березня", "квітня", "травня", "червня", "липня", "серпня", "вересня",
           "жовтня", "листопада", "грудня"],
    "pl": ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia", "września",
           "października", "listopada", "grudnia"],
    "en": list(calendar.month_name)[1:],
}
MONTHS_NOM = {
    "uk": ["січень", "лютий", "березень", "квітень", "травень", "червень", "липень", "серпень", "вересень",
           "жовтень", "листопад", "грудень"],
    "pl": ["styczeń", "luty", "marzec", "kwiecień", "maj", "czerwiec", "lipiec", "sierpień", "wrzesień",
           "październik", "listopad", "grudzień"],
    "en": list(calendar.month_name)[1:],
}
# currency symbol as printed: (lang, ISO) -> (symbol, before_number)
SYMBOL = {("uk", "UAH"): ("грн", False), ("uk", "USD"): ("дол. США", False),
          ("pl", "PLN"): ("zł", False), ("pl", "EUR"): ("€", False),
          ("en", "EUR"): ("€", True), ("en", "GBP"): ("£", True), ("en", "USD"): ("$", True)}
VAT_RATE = {"uk": 20, "pl": 23, "en": 20}


def tr(lang, uk, pl, en):
    return {"uk": uk, "pl": pl, "en": en}[lang]


def rnd_date(rng, start=date(2025, 1, 1), end=date(2026, 12, 31)):
    return start + timedelta(days=rng.randint(0, (end - start).days))


def add_months(d, n):
    m = d.month - 1 + n
    y, m = d.year + m // 12, m % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


class Fmt:
    """Per-document formatting choices (date style, currency style)."""

    def __init__(self, rng, lang, cur, date_styles=("dot", "slash", "iso", "text"), cur_styles=("code", "symbol")):
        self.lang, self.cur = lang, cur
        self.ds = rng.choice(date_styles)
        self.cs = rng.choice(cur_styles)

    def d(self, x: date) -> str:
        if self.ds == "iso":
            return x.isoformat()
        if self.ds == "dot":
            return x.strftime("%d.%m.%Y")
        if self.ds == "slash":
            return x.strftime("%d/%m/%Y")
        m = MONTHS_GEN[self.lang][x.month - 1]
        return tr(self.lang, f"{x.day} {m} {x.year} р.", f"{x.day} {m} {x.year} r.", f"{x.day} {m} {x.year}")

    def n(self, x: float) -> str:
        s = f"{x:,.2f}"
        return s if self.lang == "en" else s.replace(",", " ").replace(".", ",")

    def sym(self) -> str:
        return self.cur if self.cs == "code" else SYMBOL[(self.lang, self.cur)][0]

    def m(self, x: float) -> str:
        if self.cs == "code":
            return f"{self.n(x)} {self.cur}"
        s, before = SYMBOL[(self.lang, self.cur)]
        return f"{s}{self.n(x)}" if before else f"{self.n(x)} {s}"

    def tags(self):
        t = []
        if self.ds == "text":
            t.append("textual_date")
        if self.cs == "symbol":
            t.append("currency_symbol")
        return t


def pick_currency(rng, lang, local_only=False):
    if lang == "en":
        return rng.choice(["GBP", "EUR"]) if local_only else rng.choices(["EUR", "GBP", "USD"], [5, 3.5, 1.5])[0]
    local, foreign = {"uk": ("UAH", "USD"), "pl": ("PLN", "EUR")}[lang]
    return local if local_only or rng.random() < 0.85 else foreign


def tax_id(rng, lang):
    if lang == "uk":
        return f"Код ЄДРПОУ {rng.randint(10**7, 10**8 - 1)}"
    if lang == "pl":
        return f"NIP {rng.randint(100, 999)}-{rng.randint(100, 999)}-{rng.randint(10, 99)}-{rng.randint(10, 99)}"
    return f"VAT No GB {rng.randint(100, 999)} {rng.randint(1000, 9999)} {rng.randint(10, 99)}"


def iban(rng, lang):
    cc, n = {"uk": ("UA", 27), "pl": ("PL", 26), "en": ("GB", 20)}[lang]
    raw = cc + f"{rng.randint(10, 99)}" + "".join(str(rng.randint(0, 9)) for _ in range(n - 2))
    return " ".join(raw[i:i + 4] for i in range(0, len(raw), 4))


def party(rng, lang, name, firm=None):
    """Address block. Firms get a tax id, private persons do not."""
    firm = firm if firm is not None else name not in PEOPLE[lang]
    lines = [name, rng.choice(ADDRESSES[lang])]
    return lines + [tax_id(rng, lang)] if firm else lines


def recipient_name(rng, lang, firm_share=0.5):
    return rng.choice(CLIENT_FIRMS[lang] if rng.random() < firm_share else PEOPLE[lang])


def make_items(rng, names, k_min, k_max, price_range, qty_max=5):
    rows = []
    for name in rng.sample(names, rng.randint(k_min, min(k_max, len(names)))):
        q = rng.randint(1, qty_max)
        p = round(rng.uniform(*price_range), 2)
        rows.append((name, q, p, round(q * p, 2)))
    return rows


def base_label(doc_type, lang):
    return {"doc_type": doc_type, "language": lang, "counterparty": None, "recipient": None,
            "document_number": None, "issue_date": None, "currency": None, "total_amount": None,
            "due_date": None, "valid_from": None, "valid_until": None}


def empty_spec(layout):
    return {"layout": layout, "title": "", "letterhead": [], "meta": [], "parties": [], "table": None,
            "totals": [], "paragraphs": [], "notes": [], "signatures": [], "stamp": None}


# ---- document builders: each returns (label, spec, tags) -------------------
ITEMS_INVOICE = {
    "uk": ["Консультаційні послуги", "Папір офісний A4, пачка", "Картридж для принтера",
           "Обслуговування ПЗ (місяць)", "Доставка", "Налаштування мережі"],
    "pl": ["Usługi księgowe", "Papier biurowy A4, ryza", "Toner do drukarki", "Abonament serwisowy (miesiąc)",
           "Dostawa", "Konfiguracja sieci"],
    "en": ["Consulting services", "A4 office paper, ream", "Printer toner", "Software support (month)",
           "Delivery", "Network setup"],
}


def build_invoice(rng, lang):
    cur = pick_currency(rng, lang)
    f = Fmt(rng, lang, cur)
    issue = rnd_date(rng)
    seller, buyer = rng.choice(VENDORS[lang]), recipient_name(rng, lang, 0.7)
    y = issue.year
    num = rng.choice({
        "uk": [f"РФ-{rng.randint(1, 9999):06d}", f"{rng.randint(1, 999)}/{y}"],
        "pl": [f"FV/{y}/{issue.month:02d}/{rng.randint(1, 300)}", f"{rng.randint(1, 300)}/{issue.month:02d}/{y}"],
        "en": [f"INV-{y}-{rng.randint(1, 9999):04d}", f"{rng.choice('ABCDEF')}{rng.randint(100, 999)}/{y}"],
    }[lang])
    items = make_items(rng, ITEMS_INVOICE[lang], 1, 5, (15, 900))
    net = round(sum(r[3] for r in items), 2)
    rate = VAT_RATE[lang]
    vat = round(net * rate / 100, 2)
    gross = round(net + vat, 2)
    paid = rng.random() < 0.2
    due = None if paid else issue + timedelta(days=rng.choice([7, 14, 21, 30]))
    sale = issue - timedelta(days=rng.randint(1, 6)) if rng.random() < 0.5 else None

    title = rng.choice(tr(lang, ["Рахунок-фактура", "Рахунок на оплату"], ["Faktura VAT", "Faktura"],
                          ["Invoice", "Tax invoice"]))
    s = empty_spec(rng.choice(["classic", "boxed"]))
    s["title"] = f"{title} {tr(lang, '№', 'nr', 'No.')} {num}"
    s["letterhead"] = party(rng, lang, seller, True)
    s["meta"].append((tr(lang, "Дата складання", "Data wystawienia", "Invoice date"), f.d(issue)))
    if sale:
        s["meta"].append((tr(lang, "Дата постачання", "Data sprzedaży", "Supply date"), f.d(sale)))
    if due:
        s["meta"].append((tr(lang, "Сплатити до", "Termin płatności", "Payment due"), f.d(due)))
    else:
        s["meta"].append((tr(lang, "Оплата", "Forma płatności", "Payment"),
                          tr(lang, "оплачено карткою", "zapłacono kartą", "paid by card")))
    s["parties"] = [(tr(lang, "Постачальник", "Sprzedawca", "Seller"), s["letterhead"]),
                    (tr(lang, "Покупець", "Nabywca", "Bill to"), party(rng, lang, buyer))]
    s["table"] = {
        "head": ["#", tr(lang, "Найменування", "Nazwa towaru / usługi", "Description"), tr(lang, "К-сть", "Ilość", "Qty"),
                 tr(lang, "Ціна без ПДВ", "Cena netto", "Unit price"),
                 tr(lang, f"Сума, {f.sym()}", f"Wartość netto ({f.sym()})", f"Amount ({f.sym()})")],
        "rows": [[str(i + 1), n, str(q), f.n(p), f.n(a)] for i, (n, q, p, a) in enumerate(items)],
        "cols": [(LM, "l"), (LM + 20, "l"), (345, "r"), (440, "r"), (RM, "r")],
    }
    s["totals"] = [(tr(lang, "Разом без ПДВ", "Razem netto", "Subtotal"), f.m(net), False),
                   (tr(lang, f"ПДВ {rate}%", f"VAT {rate}%", f"VAT {rate}%"), f.m(vat), False),
                   (tr(lang, "Всього до сплати", "Do zapłaty", "Total due") if due else
                    tr(lang, "Всього з ПДВ", "Razem brutto", "Total incl. VAT"), f.m(gross), True)]
    s["notes"] = [f"IBAN: {iban(rng, lang)}"]
    s["stamp"] = tr(lang, "ОПЛАЧЕНО", "ZAPŁACONO", "PAID") if paid else None

    lab = base_label("invoice", lang)
    lab.update(counterparty=seller, recipient=buyer, document_number=num, issue_date=issue.isoformat(),
               currency=cur, total_amount=gross, due_date=due.isoformat() if due else None)
    tags = ["vat_breakdown", "iban"] + f.tags() + (["paid_no_due"] if paid else []) + (["supply_date"] if sale else [])
    if cur not in ("UAH", "PLN") and lang != "en":
        tags.append("foreign_currency")
    return lab, s, tags


UTILITY_LINES = {  # (name, unit, qty range, tariff range)
    "uk": [("Електроенергія", "кВт·год", (80, 450), (4.3, 4.3)), ("Водопостачання", "м³", (3, 15), (30, 45)),
           ("Опалення", "Гкал", (0.5, 2.5), (1600, 1700)), ("Вивіз ТПВ", "особа", (1, 4), (40, 60))],
    "pl": [("Energia elektryczna", "kWh", (80, 450), (0.8, 1.1)), ("Woda i ścieki", "m³", (3, 15), (14, 19)),
           ("Ogrzewanie", "GJ", (1, 6), (90, 130)), ("Wywóz odpadów", "osoba", (1, 4), (30, 40))],
    "en": [("Electricity", "kWh", (80, 450), (0.22, 0.30)), ("Water & sewerage", "m³", (3, 15), (3.5, 4.5)),
           ("Gas", "kWh", (200, 1200), (0.06, 0.09)), ("Standing charge", "day", (28, 31), (0.45, 0.6))],
}


def build_utility(rng, lang):
    cur = pick_currency(rng, lang, local_only=True)
    f = Fmt(rng, lang, cur)
    issue = rnd_date(rng)
    period = add_months(issue.replace(day=1), -1)
    due = issue + timedelta(days=rng.choice([10, 14, 20, 25]))
    issuer, client = rng.choice(UTILITIES[lang]), rng.choice(PEOPLE[lang])
    num = rng.choice([f"{issue.year}-{issue.month:02d}-{rng.randint(100000, 999999)}",
                      f"{rng.randint(10**8, 10**9 - 1)}"])
    account = f"{rng.randint(10**9, 10**10 - 1)}"
    rows = []
    for name, unit, qr, tr_ in rng.sample(UTILITY_LINES[lang], rng.randint(2, 4)):
        q = rng.randint(*qr) if unit in ("особа", "osoba", "day") else round(rng.uniform(*qr), 1 if qr[1] < 20 else 0)
        t = round(rng.uniform(*tr_), 2)
        rows.append((name, q, unit, t, round(q * t, 2)))
    accrued = round(sum(r[4] for r in rows), 2)
    roll = rng.random()
    balance = 0.0 if roll < 0.5 else (round(rng.uniform(20, accrued * 0.8), 2) if roll < 0.8
                                      else -round(rng.uniform(5, accrued * 0.4), 2))
    total = round(accrued + balance, 2)

    s = empty_spec(rng.choice(["classic", "boxed"]))
    s["title"] = f"{tr(lang, 'Рахунок за комунальні послуги', 'Rachunek za media', 'Utility bill')} {tr(lang, '№', 'nr', 'No.')} {num}"
    s["letterhead"] = party(rng, lang, issuer, True)
    per = f"{MONTHS_NOM[lang][period.month - 1]} {period.year}"
    s["meta"] = [(tr(lang, "Дата рахунку", "Data wystawienia", "Bill date"), f.d(issue)),
                 (tr(lang, "Особовий рахунок", "Numer klienta", "Account number"), account),
                 (tr(lang, "Період", "Okres rozliczeniowy", "Billing period"), per),
                 (tr(lang, "Сплатити до", "Termin płatności", "Pay by"), f.d(due))]
    s["parties"] = [(tr(lang, "Постачальник", "Sprzedawca", "Supplier"), s["letterhead"]),
                    (tr(lang, "Споживач", "Odbiorca", "Customer"), party(rng, lang, client, False))]
    s["table"] = {
        "head": [tr(lang, "Послуга", "Usługa", "Service"), tr(lang, "Обсяг", "Zużycie", "Usage"),
                 tr(lang, "Тариф", "Cena jedn.", "Rate"), tr(lang, f"Сума, {f.sym()}", f"Kwota ({f.sym()})", f"Amount ({f.sym()})")],
        "rows": [[n, f"{q:g} {u}" if lang == "en" else f"{q:g} {u}".replace(".", ","),
                  f"{t:.2f}" if lang == "en" else f"{t:.2f}".replace(".", ","), f.n(a)]
                 for n, q, u, t, a in rows],
        "cols": [(LM, "l"), (330, "r"), (430, "r"), (RM, "r")],
    }
    s["totals"] = [(tr(lang, "Нараховано за період", "Naliczono za okres", "Charges this period"), f.m(accrued), False)]
    if balance > 0:
        s["totals"].append((tr(lang, "Борг на початок періоду", "Zaległość z poprz. okresu", "Previous balance"),
                            f.m(balance), False))
    elif balance < 0:
        s["totals"].append((tr(lang, "Переплата", "Nadpłata", "Credit carried forward"), "-" + f.m(-balance), False))
    s["totals"].append((tr(lang, "До сплати", "Do zapłaty", "Amount due"), f.m(total), True))
    s["notes"] = [f"IBAN: {iban(rng, lang)}",
                  tr(lang, f"У призначенні платежу вкажіть особовий рахунок {account}.",
                     f"W tytule przelewu podaj numer klienta {account}.",
                     f"Quote account number {account} with your payment.")]

    lab = base_label("utility_bill", lang)
    lab.update(counterparty=issuer, recipient=client, document_number=num, issue_date=issue.isoformat(),
               currency=cur, total_amount=total, due_date=due.isoformat())
    tags = ["account_number", "billing_period", "iban"] + f.tags()
    tags += ["previous_balance"] if balance > 0 else (["overpayment"] if balance < 0 else [])
    return lab, s, tags


def build_insurance(rng, lang):
    cur = pick_currency(rng, lang)
    f = Fmt(rng, lang, cur)
    issue = rnd_date(rng)
    start = issue + timedelta(days=rng.choice([0, 0, 1, 3, 7, 14]))
    end = add_months(start, 12) - timedelta(days=1)
    insurer, holder = rng.choice(INSURERS[lang]), rng.choice(PEOPLE[lang])
    num = rng.choice({"uk": [f"АН-{rng.randint(10**6, 10**7 - 1)}", f"{rng.randint(100, 999)}.{issue.year}.{rng.randint(1000, 9999)}"],
                      "pl": [f"PL-AC {rng.randint(10**6, 10**7 - 1)}", f"{rng.randint(10**9, 10**10 - 1)}"],
                      "en": [f"POL-{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}", f"HC{rng.randint(10**6, 10**7 - 1)}"]}[lang])
    premium = round(rng.uniform(300, 3500), 2)
    insured = round(premium * rng.uniform(25, 80), -3)
    obj = rng.choice(tr(lang,
                        ["квартира за адресою " + rng.choice(ADDRESSES["uk"]), "легковий автомобіль (тестовий номер ТТ0000ТТ)",
                         "майно офісу"],
                        ["mieszkanie, " + rng.choice(ADDRESSES["pl"]), "samochód osobowy (nr rej. TEST000)", "wyposażenie biura"],
                        ["home contents at " + rng.choice(ADDRESSES["en"]), "private car (reg. TE57 ABC)", "office equipment"]))
    installments = rng.random() < 0.35

    s = empty_spec(rng.choice(["boxed", "narrative"]))
    s["title"] = f"{tr(lang, 'Страховий поліс', 'Polisa ubezpieczeniowa', 'Insurance policy')} {tr(lang, '№', 'nr', 'No.')} {num}"
    s["letterhead"] = party(rng, lang, insurer, True)
    s["meta"] = [(tr(lang, "Дата видачі", "Data wystawienia", "Date of issue"), f.d(issue)),
                 (tr(lang, "Місце видачі", "Miejsce wystawienia", "Place of issue"), rng.choice(CITY[lang]))]
    s["parties"] = [(tr(lang, "Страховик", "Ubezpieczyciel", "Insurer"), s["letterhead"]),
                    (tr(lang, "Страхувальник", "Ubezpieczający", "Policyholder"), party(rng, lang, holder, False))]
    s["paragraphs"] = [
        tr(lang, f"Об'єкт страхування: {obj}.", f"Przedmiot ubezpieczenia: {obj}.", f"Insured object: {obj}."),
        tr(lang, f"Строк дії договору страхування: з {f.d(start)} до {f.d(end)} включно.",
           f"Okres ubezpieczenia: od {f.d(start)} do {f.d(end)} włącznie.",
           f"Period of cover: from {f.d(start)} to {f.d(end)} inclusive."),
        tr(lang, f"Страхова сума: {f.m(insured)}. Страхова премія: {f.m(premium)}.",
           f"Suma ubezpieczenia: {f.m(insured)}. Składka: {f.m(premium)}.",
           f"Sum insured: {f.m(insured)}. Premium: {f.m(premium)}."),
    ]
    if installments:
        p1 = round(premium / 2, 2)
        p2 = round(premium - p1, 2)
        d2 = add_months(start, 6)
        s["paragraphs"].append(tr(lang,
            f"Премія сплачується двома частинами: {f.m(p1)} до {f.d(start)} та {f.m(p2)} до {f.d(d2)}.",
            f"Składka płatna w dwóch ratach: {f.m(p1)} do {f.d(start)} oraz {f.m(p2)} do {f.d(d2)}.",
            f"Premium payable in two instalments: {f.m(p1)} by {f.d(start)} and {f.m(p2)} by {f.d(d2)}."))
    if s["layout"] == "boxed":
        s["totals"] = [(tr(lang, "Страхова сума", "Suma ubezpieczenia", "Sum insured"), f.m(insured), False),
                       (tr(lang, "Страхова премія", "Składka", "Premium"), f.m(premium), True)]
    s["signatures"] = [s["parties"][0][0], s["parties"][1][0]]

    lab = base_label("insurance", lang)
    lab.update(counterparty=insurer, recipient=holder, document_number=num, issue_date=issue.isoformat(),
               currency=cur, total_amount=premium, valid_from=start.isoformat(), valid_until=end.isoformat())
    tags = ["sum_insured"] + f.tags() + (["installments"] if installments else []) + \
           (["issue_before_start"] if start != issue else [])
    return lab, s, tags


SERVICES = {
    "uk": ["бухгалтерського обслуговування", "технічної підтримки комп'ютерної мережі", "прибирання офісних приміщень",
           "доступу до мережі Інтернет"],
    "pl": ["obsługi księgowej", "wsparcia technicznego sieci komputerowej", "sprzątania biura", "dostępu do Internetu"],
    "en": ["bookkeeping services", "IT network support", "office cleaning", "internet access"],
}


def build_contract(rng, lang):
    cur = pick_currency(rng, lang)
    f = Fmt(rng, lang, cur, date_styles=("dot", "text", "text", "slash"))
    signed = rnd_date(rng)
    start = signed if rng.random() < 0.5 else add_months(signed.replace(day=1), 1)
    months = rng.choice([6, 12, 12, 24])
    end = add_months(start, months) - timedelta(days=1)
    provider, client = rng.choice(VENDORS[lang]), recipient_name(rng, lang, 0.6)
    num = None if rng.random() < 0.25 else rng.choice([f"{rng.randint(1, 99)}/{signed.year}",
                                                       f"{rng.choice(['DU', 'SRV', 'K'])}-{signed.year}-{rng.randint(1, 999):03d}"])
    fee = round(rng.uniform(150, 2500), 2)
    total = round(fee * months, 2)
    service = rng.choice(SERVICES[lang])
    city = rng.choice(CITY[lang])

    s = empty_spec("narrative")
    base = tr(lang, "Договір про надання послуг", "Umowa o świadczenie usług", "Service agreement")
    s["title"] = f"{base} {tr(lang, '№', 'nr', 'No.')} {num}" if num else base
    s["meta"] = [(city, f.d(signed))]
    prov, cli = tr(lang, "Виконавець", "Wykonawca", "the Provider"), tr(lang, "Замовник", "Zamawiający", "the Client")
    s["paragraphs"] = [
        tr(lang, f"{provider} (далі — {prov}) та {client} (далі — {cli}) уклали цей договір про таке.",
           f"{provider} (dalej: {prov}) oraz {client} (dalej: {cli}) zawierają umowę następującej treści.",
           f"This agreement is made between {provider} ({prov}) and {client} ({cli})."),
        tr(lang, f"1. {prov} надає {cli}у послуги {service}.",
           f"1. {prov} świadczy na rzecz {cli}ego usługi {service}.",
           f"1. The Provider shall provide {service} to the Client."),
    ]
    price = [tr(lang, f"Вартість послуг становить {f.m(fee)} на місяць.",
                f"Wynagrodzenie wynosi {f.m(fee)} miesięcznie.",
                f"The fee is {f.m(fee)} per month."),
             tr(lang, f"Загальна вартість договору — {f.m(total)}.",
                f"Łączna wartość umowy wynosi {f.m(total)}.",
                f"The total contract value is {f.m(total)}.")]
    if rng.random() < 0.5:
        price.reverse()
    s["paragraphs"].append("2. " + " ".join(price))
    s["paragraphs"] += [
        tr(lang, f"3. Договір набирає чинності {f.d(start)} і діє до {f.d(end)} включно.",
           f"3. Umowa obowiązuje od {f.d(start)} do {f.d(end)} włącznie.",
           f"3. This agreement is effective from {f.d(start)} until {f.d(end)} inclusive."),
        tr(lang, "4. Оплата здійснюється щомісяця до 10 числа на підставі рахунку.",
           "4. Płatność następuje co miesiąc do 10. dnia miesiąca na podstawie faktury.",
           "4. Payment is due monthly by the 10th day of the month against an invoice."),
        tr(lang, "5. Договір складено у двох примірниках, по одному для кожної зі сторін.",
           "5. Umowę sporządzono w dwóch egzemplarzach, po jednym dla każdej ze stron.",
           "5. This agreement is executed in two counterparts, one for each party."),
    ]
    s["signatures"] = [prov.replace("the ", "").capitalize(), cli.replace("the ", "").capitalize()]
    s["parties"] = [(s["signatures"][0], party(rng, lang, provider, True)),
                    (s["signatures"][1], party(rng, lang, client))]

    lab = base_label("contract", lang)
    lab.update(counterparty=provider, recipient=client, document_number=num, issue_date=signed.isoformat(),
               currency=cur, total_amount=total, valid_from=start.isoformat(), valid_until=end.isoformat())
    tags = ["monthly_vs_total", "narrative"] + f.tags() + (["no_number"] if not num else []) + \
           (["start_after_signing"] if start != signed else [])
    return lab, s, tags


ITEMS_RECEIPT = {
    "uk": ["Кава мелена 250 г", "Хліб пшеничний", "Ручка кулькова", "Батарейки AA 4 шт.", "Вода 1,5 л",
           "Папір A4 500 арк.", "Молоко 2,5% 0,9 л"],
    "pl": ["Kawa mielona 250 g", "Chleb pszenny", "Długopis", "Baterie AA 4 szt.", "Woda 1,5 l",
           "Papier A4 500 ark.", "Mleko 2% 1 l"],
    "en": ["Ground coffee 250 g", "White bread", "Ballpoint pen", "AA batteries 4 pk", "Still water 1.5 l",
           "A4 paper 500 sh", "Semi-skimmed milk 1 l"],
}


def build_receipt(rng, lang):
    cur = pick_currency(rng, lang, local_only=True)
    f = Fmt(rng, lang, cur, date_styles=("dot", "slash", "iso"))
    issue = rnd_date(rng)
    shop = rng.choice(SHOPS[lang])
    hi = {"UAH": 250, "PLN": 40, "EUR": 12, "GBP": 10}[cur]
    items = make_items(rng, ITEMS_RECEIPT[lang], 2, 6, (hi * 0.08, hi), qty_max=3)
    total = round(sum(r[3] for r in items), 2)
    num = None if rng.random() < 0.3 else str(rng.randint(100, 99999))
    cash = rng.random() < 0.5
    rate = VAT_RATE[lang]

    s = empty_spec("receipt")
    s["letterhead"] = party(rng, lang, shop, True)
    s["title"] = tr(lang, "ФІСКАЛЬНИЙ ЧЕК", "PARAGON FISKALNY", "RECEIPT")
    time_ = f"{rng.randint(8, 21):02d}:{rng.randint(0, 59):02d}"
    if num:
        s["meta"].append((tr(lang, "Чек №", "Nr paragonu", "Receipt #"), num))
    s["meta"] += [(tr(lang, "Дата", "Data", "Date"), f"{f.d(issue)} {time_}"),
                  (tr(lang, "Каса", "Kasa", "Till"), str(rng.randint(1, 6)))]
    s["table"] = {"rows": [[n, f"{q} x {f.n(p)}", f.n(a)] for n, q, p, a in items]}
    vat = round(total * rate / (100 + rate), 2)
    s["totals"] = [(tr(lang, f"у т.ч. ПДВ {rate}%", f"PTU A {rate}%", f"incl. VAT {rate}%"), f.n(vat), False),
                   (tr(lang, "СУМА", "SUMA", "TOTAL"), f.m(total), True)]
    if cash:
        step = {"UAH": 100, "PLN": 50, "EUR": 10, "GBP": 10}[cur]
        given = float(math.ceil((total + 0.01) / step) * step)
        s["totals"] += [(tr(lang, "Готівка", "Gotówka", "Cash"), f.n(given), False),
                        (tr(lang, "Решта", "Reszta", "Change"), f.n(round(given - total, 2)), False)]
    else:
        s["totals"].append((tr(lang, "Картка", "Karta", "Card"), f"**** {rng.randint(1000, 9999)}", False))
    s["notes"] = [tr(lang, f"ФН {rng.randint(10**9, 10**10 - 1)}", f"Nr unikatowy BDE {rng.randint(10**7, 10**8 - 1)}",
                     f"Terminal ID {rng.randint(10**5, 10**6 - 1)}"),
                  tr(lang, "Дякуємо за покупку!", "Dziękujemy za zakupy!", "Thank you for shopping with us!")]

    lab = base_label("receipt", lang)
    lab.update(counterparty=shop, document_number=num, issue_date=issue.isoformat(), currency=cur, total_amount=total)
    tags = ["no_recipient", "vat_included", "fiscal_ids"] + f.tags() + (["cash_change"] if cash else ["card"]) + \
           (["no_number"] if not num else [])
    return lab, s, tags


def build_other(rng, lang, kind):
    """Non-target documents: certificate, notice letter, meeting minutes. No amounts or validity."""
    f = Fmt(rng, lang, None, date_styles=("dot", "text"))
    issue = rnd_date(rng)
    org = rng.choice(VENDORS[lang])
    person = rng.choice(PEOPLE[lang])
    s = empty_spec("narrative")
    s["letterhead"] = party(rng, lang, org, True)
    s["meta"] = [(rng.choice(CITY[lang]), f.d(issue))]
    lab = base_label("other", lang)
    lab.update(counterparty=org, issue_date=issue.isoformat())
    if kind == "certificate":
        num = f"{rng.randint(1, 300)}"
        s["title"] = f"{tr(lang, 'Довідка', 'Zaświadczenie', 'Certificate of employment')} {tr(lang, '№', 'nr', 'No.')} {num}"
        s["paragraphs"] = [tr(lang,
            f"Цим підтверджується, що {person} дійсно працює в {org} на посаді офіс-менеджера з {f.d(add_months(issue, -30))}.",
            f"Zaświadcza się, że {person} jest zatrudniona/y w {org} na stanowisku specjalisty ds. biura od {f.d(add_months(issue, -30))}.",
            f"This is to certify that {person} has been employed by {org} as an office manager since {f.d(add_months(issue, -30))}."),
            tr(lang, "Довідка видана для подання за місцем вимоги.", "Zaświadczenie wydaje się na prośbę pracownika.",
               "This certificate is issued at the employee's request.")]
        lab.update(recipient=person, document_number=num)
    elif kind == "letter":
        num = f"{rng.randint(1, 999)}/{issue.year}"
        client = rng.choice(CLIENT_FIRMS[lang])
        new_addr = rng.choice(ADDRESSES[lang])
        s["title"] = f"{tr(lang, 'Лист-повідомлення', 'Zawiadomienie', 'Notice')} {tr(lang, 'вих. №', 'znak:', 'Ref.')} {num}"
        s["parties"] = [(tr(lang, "Кому", "Adresat", "To"), party(rng, lang, client, True))]
        s["paragraphs"] = [tr(lang,
            f"Повідомляємо, що з {f.d(issue + timedelta(days=30))} наш офіс переїжджає за адресою: {new_addr}.",
            f"Uprzejmie informujemy, że od {f.d(issue + timedelta(days=30))} nasze biuro mieści się pod adresem: {new_addr}.",
            f"Please note that from {f.d(issue + timedelta(days=30))} our office moves to {new_addr}."),
            tr(lang, "Реквізити для оплати не змінюються.", "Dane do płatności pozostają bez zmian.",
               "Our payment details remain unchanged.")]
        lab.update(recipient=client, document_number=num)
    else:  # minutes
        s["title"] = tr(lang, "Протокол робочої наради", "Protokół z zebrania", "Meeting minutes")
        s["paragraphs"] = [tr(lang, f"Присутні: {person}, {rng.choice(PEOPLE['uk'])}.", f"Obecni: {person}, {rng.choice(PEOPLE['pl'])}.",
                              f"Present: {person}, {rng.choice(PEOPLE['en'])}."),
                           tr(lang, "1. Обговорили графік закриття звітного періоду.", "1. Omówiono harmonogram zamknięcia okresu.",
                              "1. Discussed the month-end closing schedule."),
                           tr(lang, "2. Вирішили перейти на електронний документообіг.", "2. Postanowiono wdrożyć obieg dokumentów online.",
                              "2. Agreed to move to electronic document flow.")]
    s["signatures"] = [tr(lang, "Директор", "Dyrektor", "Director")]
    return lab, s, ["other_" + kind] + f.tags()


BUILDERS = {"invoice": build_invoice, "contract": build_contract, "insurance": build_insurance,
            "receipt": build_receipt, "utility_bill": build_utility}


# ---- rendering --------------------------------------------------------------
class Page:
    def __init__(self, c):
        self.c, self.y = c, H - 55

    def text(self, x, s, size=10, bold=False, align="l", gray=0.0):
        c = self.c
        c.setFont("FB" if bold else "F", size)
        c.setFillGray(gray)
        {"l": c.drawString, "r": c.drawRightString, "c": c.drawCentredString}[align](x, self.y, s)
        c.setFillGray(0)

    def nl(self, dy=15):
        self.y -= dy

    def wrap(self, x, s, width, size=10, lead=None, bold=False):
        s = s.replace(" р..", " р.").replace(" r..", " r.")
        for ln in simpleSplit(s, "FB" if bold else "F", size, width):
            self.text(x, ln, size, bold)
            self.nl(lead or size * 1.45)

    def hline(self, x0=LM, x1=RM, gray=0.6):
        self.c.setStrokeGray(gray)
        self.c.line(x0, self.y, x1, self.y)
        self.c.setStrokeGray(0)


def draw_parties(pg, parties):
    if not parties:
        return
    top, low = pg.y, pg.y
    for i, (head, lines) in enumerate(parties[:2]):
        pg.y = top
        x = LM + i * 265
        pg.text(x, head, 8.5, True, gray=0.4)
        pg.nl(13)
        for j, ln in enumerate(lines):
            pg.text(x, ln, 10 if j == 0 else 9, bold=j == 0)
            pg.nl(13)
        low = min(low, pg.y)
    pg.y = low - 10


def draw_table(pg, t):
    cols = t["cols"]
    pg.hline()
    pg.nl(13)
    for (x, al), h in zip(cols, t["head"]):
        pg.text(x, h, 8.5, True, align=al)
    pg.nl(6)
    pg.hline()
    pg.nl(14)
    for row in t["rows"]:
        for (x, al), v in zip(cols, row):
            pg.text(x, v, 9.5, align=al)
        pg.nl(16)
    pg.y += 8
    pg.hline()
    pg.nl(20)


def draw_totals(pg, totals, x_label=430, x_val=RM):
    for label, val, bold in totals:
        pg.text(x_label, label, 11 if bold else 9.5, bold, align="r")
        pg.text(x_val, val, 11 if bold else 9.5, bold, align="r")
        pg.nl(18 if bold else 15)


def draw_signatures(pg, sigs, rng):
    pg.nl(25)
    for i, who in enumerate(sigs[:2]):
        x = LM + i * 265
        pg.text(x, who, 9, True)
        pg.c.setStrokeGray(0.3)
        pg.c.line(x, pg.y - 28, x + 170, pg.y - 28)
        # scribble
        sx, sy = x + rng.randint(10, 60), pg.y - 24
        p = pg.c.beginPath()
        p.moveTo(sx, sy)
        for _ in range(3):
            p.curveTo(sx + rng.randint(5, 25), sy + rng.randint(5, 18), sx + rng.randint(25, 45), sy - rng.randint(4, 12),
                      sx + rng.randint(45, 70), sy + rng.randint(-3, 6))
            sx += rng.randint(40, 60)
        pg.c.setLineWidth(0.9)
        pg.c.setStrokeColorRGB(0.1, 0.15, 0.45)
        pg.c.drawPath(p, stroke=1, fill=0)
        pg.c.setLineWidth(1)
        pg.c.setStrokeGray(0)
    pg.nl(45)


def render_standard(pg, s, boxed):
    if boxed:
        top = pg.y
        for j, ln in enumerate(s["letterhead"]):
            pg.text(LM, ln, 12 if j == 0 else 9, bold=j == 0)
            pg.nl(16 if j == 0 else 12)
        low = pg.y
        pg.y = top
        box_h = 16 * len(s["meta"]) + 10
        pg.c.setStrokeGray(0.5)
        pg.c.rect(330, top - box_h + 12, RM - 330, box_h)
        pg.c.setStrokeGray(0)
        for label, val in s["meta"]:
            pg.text(338, f"{label}:", 8.5, gray=0.35)
            pg.text(RM - 8, val, 9, True, align="r")
            pg.nl(16)
        pg.y = min(low, pg.y) - 22
        pg.text(W / 2, s["title"], 15, True, align="c")
        pg.nl(30)
        parties = s["parties"][1:] if s["parties"] and s["parties"][0][1] == s["letterhead"] else s["parties"]
        draw_parties(pg, parties)
    else:
        pg.text(LM, s["title"], 16, True)
        pg.nl(28)
        for label, val in s["meta"]:
            pg.text(LM, f"{label}: {val}", 10)
            pg.nl(15)
        pg.nl(10)
        draw_parties(pg, s["parties"])
    if s["table"]:
        draw_table(pg, s["table"])
    for p in s["paragraphs"]:
        pg.wrap(LM, p, RM - LM, 10)
        pg.nl(4)
    if s["totals"]:
        pg.nl(4)
        draw_totals(pg, s["totals"])


def render_narrative(pg, s, rng):
    if s["letterhead"]:
        for j, ln in enumerate(s["letterhead"]):
            pg.text(LM, ln, 11 if j == 0 else 8.5, bold=j == 0, gray=0 if j == 0 else 0.3)
            pg.nl(14 if j == 0 else 11)
        pg.nl(4)
        pg.hline()
        pg.nl(26)
    pg.text(W / 2, s["title"], 14, True, align="c")
    pg.nl(26)
    place, when = s["meta"][0]
    pg.text(LM, place, 10)
    pg.text(RM, when, 10, align="r")
    pg.nl(26)
    if s["parties"] and not s["signatures"][1:]:  # letter: addressee block
        for j, ln in enumerate(s["parties"][0][1]):
            pg.text(330, ln, 10 if j == 0 else 9, bold=j == 0)
            pg.nl(13)
        pg.nl(14)
    for p in s["paragraphs"]:
        pg.wrap(LM, p, RM - LM, 10.5)
        pg.nl(6)
    if s["totals"]:
        draw_totals(pg, s["totals"])
    if len(s["signatures"]) > 1 and s["parties"]:
        pg.nl(10)
        draw_parties(pg, s["parties"])
    draw_signatures(pg, s["signatures"], rng)


def render_receipt(pg, s):
    x0, x1, xc = W / 2 - 110, W / 2 + 110, W / 2
    for j, ln in enumerate(s["letterhead"]):
        pg.text(xc, ln, 10 if j == 0 else 8, bold=j == 0, align="c")
        pg.nl(13 if j == 0 else 11)
    pg.nl(4)
    pg.text(xc, s["title"], 10, True, align="c")
    pg.nl(14)
    for label, val in s["meta"]:
        pg.text(x0, label, 8.5)
        pg.text(x1, val, 8.5, align="r")
        pg.nl(12)
    pg.y += 3
    pg.hline(x0, x1, 0.4)
    pg.nl(13)
    for name, qty, amt in s["table"]["rows"]:
        pg.text(x0, name, 9)
        pg.nl(11)
        pg.text(x0 + 12, qty, 8.5, gray=0.3)
        pg.text(x1, amt, 9, align="r")
        pg.nl(14)
    pg.y += 3
    pg.hline(x0, x1, 0.4)
    pg.nl(14)
    for label, val, bold in s["totals"]:
        pg.text(x0, label, 12 if bold else 8.5, bold)
        pg.text(x1, val, 12 if bold else 8.5, bold, align="r")
        pg.nl(17 if bold else 12)
    pg.nl(6)
    for n in s["notes"]:
        pg.text(xc, n, 7.5, align="c", gray=0.3)
        pg.nl(11)


def draw_stamp(c, rng, text, x, y):
    c.saveState()
    c.translate(x, y)
    c.rotate(rng.uniform(-25, 25))
    c.setStrokeColorRGB(0.55, 0.15, 0.15)
    c.setFillColorRGB(0.55, 0.15, 0.15)
    c.setLineWidth(2)
    w = pdfmetrics.stringWidth(text, "FB", 20) + 24
    c.roundRect(-w / 2, -16, w, 36, 6, stroke=1, fill=0)
    c.setFont("FB", 20)
    c.drawCentredString(0, -6, text)
    c.restoreState()


def render_pdf(path, spec, lang, rng, noisy):
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setTitle(spec["title"])
    pg = Page(c)
    if spec["layout"] == "receipt":
        render_receipt(pg, spec)
    elif spec["layout"] == "narrative":
        render_narrative(pg, spec, rng)
    else:
        render_standard(pg, spec, spec["layout"] == "boxed")
        if spec["signatures"]:
            draw_signatures(pg, spec["signatures"], rng)
    if spec["layout"] != "receipt":
        for n in spec["notes"]:
            pg.text(LM, n, 8, gray=0.35)
            pg.nl(12)
    stamp = spec["stamp"] or (tr(lang, "КОПІЯ", "KOPIA", "COPY") if noisy else None)
    if stamp:
        draw_stamp(c, rng, stamp, rng.uniform(330, 470), max(pg.y - rng.uniform(20, 60), 110))
    c.setFont("F", 6.5)
    c.setFillGray(0.5)
    c.drawCentredString(W / 2, 25, tr(lang, "Синтетичний тестовий документ DocFlow AI. Усі дані вигадані.",
                                      "Syntetyczny dokument testowy DocFlow AI. Wszystkie dane są fikcyjne.",
                                      "Synthetic test document (DocFlow AI). All data is fictitious."))
    c.showPage()
    c.save()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-type", type=int, default=9, help="documents per target type (languages rotate)")
    ap.add_argument("--other", type=int, default=5, help="non-target documents (doc_type=other)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=str(HERE / "dataset"))
    ap.add_argument("--noisy-share", type=float, default=0.25, help="share of docs with a COPY stamp")
    a = ap.parse_args()

    register_fonts()
    rng = random.Random(a.seed)
    out = Path(a.out)
    for sub in ("pdf", "labels"):
        (out / sub).mkdir(parents=True, exist_ok=True)
        for old in (out / sub).glob("*.*"):
            old.unlink()

    plan = [(t, LANGS[k % 3]) for t in DOC_TYPES for k in range(a.per_type)]
    kinds = ["certificate", "letter", "minutes"]
    plan += [("other", LANGS[k % 3], kinds[k % 3]) for k in range(a.other)]
    rng.shuffle(plan)

    rows = []
    for i, item in enumerate(plan):
        doc_type, lang = item[0], item[1]
        label, spec, tags = build_other(rng, lang, item[2]) if doc_type == "other" else BUILDERS[doc_type](rng, lang)
        noisy = rng.random() < a.noisy_share
        if noisy:
            tags.append("stamp")
        name = f"{i:03d}_{doc_type}_{lang}"
        pdf_path = out / "pdf" / f"{name}.pdf"
        render_pdf(pdf_path, spec, lang, rng, noisy)
        label["_meta"] = {"file": pdf_path.name, "layout": spec["layout"], "noisy": noisy, "tags": tags,
                          "sha256": hashlib.sha256(pdf_path.read_bytes()).hexdigest()}
        (out / "labels" / f"{name}.json").write_text(json.dumps(label, ensure_ascii=False, indent=2), encoding="utf-8")
        rows.append({"file": pdf_path.name, "doc_type": doc_type, "language": lang, "layout": spec["layout"],
                     "noisy": noisy, "tags": " ".join(tags)})

    with open(out / "manifest.csv", "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=rows[0].keys())
        wr.writeheader()
        wr.writerows(rows)
    print(f"Generated {len(rows)} documents in {out}")


if __name__ == "__main__":
    main()
