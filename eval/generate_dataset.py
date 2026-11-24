#!/usr/bin/env python3
"""DocFlow AI: synthetic dataset generator.

Produces PDFs of 5 document types plus ground-truth JSON labels (same schema
as the LLM extraction output) and a manifest.csv for evaluation.

Usage:
    pip install -r requirements.txt
    python eval/generate_dataset.py --n 40 --seed 42          # -> eval/dataset

Fonts: needs a TTF with Cyrillic + Polish glyphs. Auto-detected (DejaVu on
Linux, Arial on Windows/macOS); override with DOCFLOW_FONT / DOCFLOW_FONT_BOLD.

All data is fabricated. No real people, companies or IDs.
"""
import argparse
import csv
import hashlib
import json
import os
import random
from datetime import date, timedelta
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

HERE = Path(__file__).resolve().parent

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
    pdfmetrics.registerFont(TTFont("DJ", reg))
    pdfmetrics.registerFont(TTFont("DJB", bold))

# ---- fake reference data (edit freely) -------------------------------------
COMPANIES = {
    "uk": ["ТОВ «Дніпро-Сервіс»", "ФОП Мельник О. І.", "ТОВ «Карпатська Енергія»", "ТОВ «ЛінкНет»"],
    "pl": ["Alfa-Energia Sp. z o.o.", "Beta Ubezpieczenia S.A.", "Gamma Telekom Sp. z o.o.", "Delta Serwis Sp. z o.o."],
    "en": ["Northwind Utilities Ltd", "Contoso Insurance plc", "Fabrikam Services LLC", "Acme Office Supplies"],
}
PEOPLE = ["Jan Testowy", "Anna Przykładowa", "Олег Тестовий", "Марія Прикладна", "John Sample"]
CURRENCIES = {"uk": "UAH", "pl": "PLN", "en": "EUR"}

LABELS = {
    "invoice": {"uk": "Рахунок-фактура", "pl": "Faktura VAT", "en": "Invoice"},
    "contract": {"uk": "Договір", "pl": "Umowa", "en": "Service Agreement"},
    "insurance": {"uk": "Страховий поліс", "pl": "Polisa ubezpieczeniowa", "en": "Insurance Policy"},
    "receipt": {"uk": "Квитанція", "pl": "Paragon", "en": "Receipt"},
    "utility_bill": {"uk": "Рахунок за комунальні послуги", "pl": "Rachunek za media", "en": "Utility Bill"},
}
DOC_TYPES = list(LABELS)


def rnd_date(rng, start=date(2025, 1, 1), end=date(2026, 12, 31)):
    return start + timedelta(days=rng.randint(0, (end - start).days))


def make_label(rng, doc_type, lang):
    """Ground truth. Keep keys in sync with the extraction JSON schema."""
    issue = rnd_date(rng)
    label = {
        "doc_type": doc_type,
        "language": lang,
        "counterparty": rng.choice(COMPANIES[lang]),
        "recipient": rng.choice(PEOPLE),
        "document_number": f"{rng.choice('ABCDEF')}{rng.randint(100, 999)}/{issue.year}",
        "issue_date": issue.isoformat(),
        "currency": CURRENCIES[lang],
        "total_amount": None,
        "due_date": None,
        "valid_from": None,
        "valid_until": None,
    }
    if doc_type in ("invoice", "utility_bill"):
        label["total_amount"] = round(rng.uniform(40, 4000), 2)
        label["due_date"] = (issue + timedelta(days=rng.choice([7, 14, 30]))).isoformat()
    elif doc_type == "receipt":
        label["total_amount"] = round(rng.uniform(5, 600), 2)
    elif doc_type == "insurance":
        label["total_amount"] = round(rng.uniform(300, 3500), 2)
        label["valid_from"] = issue.isoformat()
        label["valid_until"] = (issue + timedelta(days=364)).isoformat()
    elif doc_type == "contract":
        label["valid_from"] = issue.isoformat()
        label["valid_until"] = (issue + timedelta(days=365 * rng.choice([1, 2]))).isoformat()
        label["total_amount"] = round(rng.uniform(500, 20000), 2)
    return label


def fmt_date(d, style):
    y, m, dd = d.split("-")
    return {"iso": d, "eu": f"{dd}.{m}.{y}", "slash": f"{dd}/{m}/{y}"}[style]


def fmt_amount(a, cur, style):
    s = f"{a:,.2f}"
    if style == "eu":  # 1 234,56
        s = s.replace(",", " ").replace(".", ",")
    return f"{s} {cur}"


def render_pdf(path, label, rng, noisy):
    c = canvas.Canvas(str(path), pagesize=A4)
    w, h = A4
    ds = rng.choice(["iso", "eu", "slash"])
    As = rng.choice(["eu", "us"])
    lang = label["language"]
    title = LABELS[label["doc_type"]][lang]
    y = h - 60
    c.setFont("DJB", 18)
    c.drawString(50, y, f"{title} № {label['document_number']}")
    y -= 40
    c.setFont("DJ", 11)

    def line(text, bold=False):
        nonlocal y
        c.setFont("DJB" if bold else "DJ", 11)
        c.drawString(50, y, text)
        y -= 20

    line(f"{label['counterparty']}", bold=True)
    line(f"→ {label['recipient']}")
    line(f"Date: {fmt_date(label['issue_date'], ds)}")
    if label["due_date"]:
        line(f"Due: {fmt_date(label['due_date'], ds)}")
    if label["valid_from"]:
        line(f"Valid: {fmt_date(label['valid_from'], ds)} – {fmt_date(label['valid_until'], ds)}")
    y -= 10
    # filler line items to make layout realistic
    for i in range(rng.randint(2, 5)):
        line(f"Item {i + 1}: sample position            {rng.randint(1, 9)} x {rng.randint(5, 300)}.00")
    y -= 10
    if label["total_amount"] is not None:
        line(f"TOTAL: {fmt_amount(label['total_amount'], label['currency'], As)}", bold=True)
    if noisy:  # simple degradation: stamp + skew via rotated text
        c.saveState()
        c.translate(300, 300)
        c.rotate(25)
        c.setFont("DJB", 40)
        c.setFillGray(0.85)
        c.drawString(-120, 0, "SAMPLE / ПРИКЛАД")
        c.restoreState()
    c.showPage()
    c.save()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=str(HERE / "dataset"))
    ap.add_argument("--noisy-share", type=float, default=0.25)
    a = ap.parse_args()

    register_fonts()
    rng = random.Random(a.seed)
    out = Path(a.out)
    (out / "pdf").mkdir(parents=True, exist_ok=True)
    (out / "labels").mkdir(exist_ok=True)

    rows = []
    for i in range(a.n):
        doc_type = DOC_TYPES[i % len(DOC_TYPES)]  # balanced classes
        lang = rng.choice(list(COMPANIES))
        label = make_label(rng, doc_type, lang)
        noisy = rng.random() < a.noisy_share
        name = f"{i:03d}_{doc_type}_{lang}"
        pdf_path = out / "pdf" / f"{name}.pdf"
        render_pdf(pdf_path, label, rng, noisy)
        label["_meta"] = {"file": pdf_path.name, "noisy": noisy,
                          "sha256": hashlib.sha256(pdf_path.read_bytes()).hexdigest()}
        (out / "labels" / f"{name}.json").write_text(
            json.dumps(label, ensure_ascii=False, indent=2), encoding="utf-8")
        rows.append({"file": pdf_path.name, "doc_type": doc_type, "language": lang, "noisy": noisy})

    with open(out / "manifest.csv", "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=rows[0].keys())
        wr.writeheader()
        wr.writerows(rows)
    print(f"Generated {a.n} documents in {out}/")


if __name__ == "__main__":
    main()
