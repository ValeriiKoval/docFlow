#!/usr/bin/env python3
"""Evaluate extraction predictions against ground-truth labels.

    python eval/eval.py --pred eval/predictions/<model>          # -> eval/results/<model>.md
    python eval/eval.py --pred eval/predictions/<model> --price-in 3 --price-out 15   # USD per 1M tokens, optional

Reports: field accuracy per set (clean/light/medium/heavy), doc-level exact match,
per-doc-type accuracy, confidence threshold sweep (coverage vs accuracy), cost.
"""
import argparse, json, re
from collections import defaultdict
from pathlib import Path

FIELDS = ["doc_type", "language", "counterparty", "recipient", "document_number",
          "issue_date", "currency", "total_amount", "due_date", "valid_from", "valid_until"]
SET_ORDER = ["clean", "light", "medium", "heavy"]
HERE = Path(__file__).resolve().parent


def norm_str(x):
    return None if x is None else re.sub(r"[\W_]+", "", str(x).casefold())


def match(field, gt, pr):
    if gt is None or pr is None:
        return gt is None and pr is None
    if field == "total_amount":
        try: return abs(float(gt) - float(pr)) <= 0.01
        except (TypeError, ValueError): return False
    if field in ("counterparty", "recipient", "document_number"):
        return norm_str(gt) == norm_str(pr)
    return str(gt).strip() == str(pr).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred", required=True)
    ap.add_argument("--labels", default=str(HERE / "dataset" / "labels"))
    ap.add_argument("--report", help="default: eval/results/<model>.md")
    ap.add_argument("--price-in", type=float)
    ap.add_argument("--price-out", type=float)
    ap.add_argument("--thresholds", type=float, nargs="+", default=[0.5, 0.6, 0.7, 0.8, 0.9])
    a = ap.parse_args()

    pred_root, lab_root = Path(a.pred), Path(a.labels)
    sets = [s for s in SET_ORDER if (pred_root / s).is_dir()]
    rows = defaultdict(list)  # set -> list of per-doc results
    for s in sets:
        for pf in sorted((pred_root / s).glob("*.json")):
            rec = json.loads(pf.read_text(encoding="utf-8"))
            gt = json.loads((lab_root / pf.name).read_text(encoding="utf-8"))
            ex = rec.get("extraction")
            res = {"name": pf.stem, "doc_type": gt["doc_type"], "error": rec.get("error"),
                   "usage": rec.get("usage") or {}, "latency": rec.get("latency_s", 0.0),
                   "conf": (ex or {}).get("confidence", 0.0)}
            res["fields"] = {f: (match(f, gt[f], ex.get(f)) if ex else False) for f in FIELDS}
            res["exact"] = all(res["fields"].values())
            rows[s].append(res)

    L = ["# Extraction eval report", "", f"Predictions: `{a.pred}`", ""]

    L += ["## Field accuracy by set", "", "| Field | " + " | ".join(sets) + " |", "|---|" + "---|" * len(sets)]
    for f in FIELDS:
        L.append(f"| {f} | " + " | ".join(f"{100*sum(r['fields'][f] for r in rows[s])/len(rows[s]):.0f}%" for s in sets) + " |")
    L.append("| **doc exact match** | " + " | ".join(f"**{100*sum(r['exact'] for r in rows[s])/len(rows[s]):.0f}%**" for s in sets) + " |")
    L.append("| failed calls / invalid JSON | " + " | ".join(str(sum(1 for r in rows[s] if r["error"])) for s in sets) + " |")
    L.append("")

    L += ["## Doc exact match by document type", "", "| Type | " + " | ".join(sets) + " |", "|---|" + "---|" * len(sets)]
    for t in sorted({r["doc_type"] for s in sets for r in rows[s]}):
        cells = []
        for s in sets:
            sub = [r for r in rows[s] if r["doc_type"] == t]
            cells.append(f"{100*sum(r['exact'] for r in sub)/len(sub):.0f}% (n={len(sub)})" if sub else "-")
        L.append(f"| {t} | " + " | ".join(cells) + " |")
    L.append("")

    L += ["## Confidence threshold (auto-accept vs manual review)", "",
          "Docs with confidence >= threshold are auto-accepted; the rest go to human review.", "",
          "| Set | Threshold | Auto-accepted | Accuracy of accepted | Sent to review |", "|---|---|---|---|---|"]
    for s in sets:
        for th in a.thresholds:
            acc = [r for r in rows[s] if r["conf"] >= th and not r["error"]]
            n = len(rows[s])
            ok = f"{100*sum(r['exact'] for r in acc)/len(acc):.0f}%" if acc else "-"
            L.append(f"| {s} | {th} | {100*len(acc)/n:.0f}% | {ok} | {100*(n-len(acc))/n:.0f}% |")
    L.append("")

    L += ["## Cost and latency", "", "| Set | Avg in tok | Avg out tok | Avg latency, s | " + ("Cost / doc, USD |" if a.price_in is not None else ""),
          "|---|---|---|---|" + ("---|" if a.price_in is not None else "")]
    for s in sets:
        n = len(rows[s]); ti = sum(r["usage"].get("input_tokens", 0) for r in rows[s]) / n
        to = sum(r["usage"].get("output_tokens", 0) for r in rows[s]) / n
        lat = sum(r["latency"] for r in rows[s]) / n
        line = f"| {s} | {ti:.0f} | {to:.0f} | {lat:.1f} |"
        if a.price_in is not None:
            line += f" {(ti*a.price_in + to*(a.price_out or 0))/1e6:.4f} |"
        L.append(line)
    L.append("")

    L += ["## Most common errors", ""]
    errs = defaultdict(int)
    for s in sets:
        for r in rows[s]:
            for f, ok in r["fields"].items():
                if not ok: errs[(f, s)] += 1
    for (f, s), n in sorted(errs.items(), key=lambda kv: -kv[1])[:10]:
        L.append(f"- `{f}` on `{s}`: {n} errors")

    report = Path(a.report or HERE / "results" / f"{pred_root.name}.md")
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
