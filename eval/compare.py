#!/usr/bin/env python3
"""Side-by-side summary of several prediction runs (prompt / model comparison).

    python eval/compare.py eval/predictions/claude-sonnet-5-5/extract_v1 \
                           eval/predictions/claude-sonnet-5-5/extract_v2 \
                           eval/predictions/claude-haiku-5-5/extract_v2 --threshold 0.8

Writes eval/results/summary.md. Prices (USD per 1M tokens) come from PRICES below;
check them against the current pricing page before quoting.
"""
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval import FIELDS, SET_ORDER, HERE, match  # noqa: E402

PRICES = {"claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50), "claude-opus-5-5": (4.0, 20.0)}


def load(run: Path, labels: Path):
    out = {}
    for s in SET_ORDER:
        if not (run / s).is_dir():
            continue
        rows = []
        for pf in sorted((run / s).glob("*.json")):
            rec = json.loads(pf.read_text(encoding="utf-8"))
            gt = json.loads((labels / pf.name).read_text(encoding="utf-8"))
            ex = rec.get("extraction")
            fields = {f: bool(ex) and match(f, gt[f], ex.get(f)) for f in FIELDS}
            rows.append({"exact": all(fields.values()), "fields": fields, "err": bool(rec.get("error")),
                         "conf": (ex or {}).get("confidence", 0.0), "usage": rec.get("usage") or {},
                         "lat": rec.get("latency_s", 0.0)})
        out[s] = rows
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--labels", default=str(HERE / "dataset" / "labels"))
    ap.add_argument("--threshold", type=float, default=0.8)
    ap.add_argument("--sweep", type=float, nargs="+", default=[0.5, 0.6, 0.7, 0.8, 0.9])
    ap.add_argument("--out", default=str(HERE / "results" / "summary.md"))
    a = ap.parse_args()

    labels = Path(a.labels)
    data = {f"{Path(r).parent.name} / {Path(r).name}": (Path(r).parent.name, load(Path(r), labels)) for r in a.runs}
    sets = [s for s in SET_ORDER if all(s in d for _, d in data.values())]
    pct = lambda xs: f"{100 * sum(xs) / len(xs):.0f}%" if xs else "-"  # noqa: E731

    L = ["# Run comparison", "", f"n = {len(next(iter(data.values()))[1][sets[0]])} documents per set.", "",
         "## Document exact match (all 11 fields correct)", "",
         "| Run | " + " | ".join(sets) + " |", "|---|" + "---|" * len(sets)]
    for name, (_, d) in data.items():
        L.append(f"| {name} | " + " | ".join(pct([r["exact"] for r in d[s]]) for s in sets) + " |")
    L += ["", "## Field accuracy (mean over 11 fields)", "",
          "| Run | " + " | ".join(sets) + " |", "|---|" + "---|" * len(sets)]
    for name, (_, d) in data.items():
        L.append(f"| {name} | " + " | ".join(pct([v for r in d[s] for v in r["fields"].values()]) for s in sets) + " |")
    L += ["", f"## Human-in-the-loop at confidence >= {a.threshold}", "",
          "Auto-accepted share / exact-match accuracy of the auto-accepted documents.", "",
          "| Run | " + " | ".join(sets) + " |", "|---|" + "---|" * len(sets)]
    for name, (_, d) in data.items():
        cells = []
        for s in sets:
            acc = [r for r in d[s] if r["conf"] >= a.threshold and not r["err"]]
            cells.append(f"{pct([True] * len(acc) + [False] * (len(d[s]) - len(acc)))} / {pct([r['exact'] for r in acc])}")
        L.append(f"| {name} | " + " | ".join(cells) + " |")
    L += ["", "## Threshold sweep", "",
          "Per run: auto-accepted share / exact-match accuracy of accepted / wrong documents that slipped through "
          "(out of all documents in the set).", ""]
    for name, (_, d) in data.items():
        L += [f"**{name}**", "", "| Threshold | " + " | ".join(sets) + " |", "|---|" + "---|" * len(sets)]
        for th in a.sweep:
            cells = []
            for s in sets:
                acc = [r for r in d[s] if r["conf"] >= th and not r["err"]]
                bad = sum(not r["exact"] for r in acc)
                cells.append(f"{100 * len(acc) / len(d[s]):.0f}% / {pct([r['exact'] for r in acc])} / {bad}")
            L.append(f"| {th} | " + " | ".join(cells) + " |")
        L.append("")

    L += ["", "## Cost and latency (all sets)", "",
          "| Run | Avg in tok | Avg out tok | Cost / doc, USD | Cost / 1000 docs, USD | Avg latency, s | Failed calls |",
          "|---|---|---|---|---|---|---|"]
    for name, (model, d) in data.items():
        rows = [r for s in sets for r in d[s]]
        ti = sum(r["usage"].get("input_tokens", 0) for r in rows) / len(rows)
        to = sum(r["usage"].get("output_tokens", 0) for r in rows) / len(rows)
        pin, pout = PRICES.get(model.split("@")[0], (0, 0))
        c = (ti * pin + to * pout) / 1e6
        L.append(f"| {name} | {ti:.0f} | {to:.0f} | {c:.4f} | {c * 1000:.2f} | "
                 f"{sum(r['lat'] for r in rows) / len(rows):.1f} | {sum(r['err'] for r in rows)} |")

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
