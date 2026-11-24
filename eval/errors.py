#!/usr/bin/env python3
"""List every wrong field of a prediction run, for error analysis.

    python eval/errors.py --pred eval/predictions/claude-sonnet-5-5/extract_v1
    python eval/errors.py --pred ... --set clean --field total_amount
    python eval/errors.py --pred ... --csv eval/results/errors_v1.csv

Prints: set, document, field, expected, predicted, confidence, trap tags.
"""
import argparse, csv, json, sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval import FIELDS, SET_ORDER, HERE, match  # noqa: E402


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred", required=True)
    ap.add_argument("--labels", default=str(HERE / "dataset" / "labels"))
    ap.add_argument("--set", dest="sets", nargs="+")
    ap.add_argument("--field", dest="fields", nargs="+")
    ap.add_argument("--csv")
    a = ap.parse_args()

    root, labels = Path(a.pred), Path(a.labels)
    rows = []
    for s in a.sets or [s for s in SET_ORDER if (root / s).is_dir()]:
        for pf in sorted((root / s).glob("*.json")):
            rec = json.loads(pf.read_text(encoding="utf-8"))
            gt = json.loads((labels / pf.name).read_text(encoding="utf-8"))
            ex = rec.get("extraction") or {}
            tags = " ".join(gt["_meta"].get("tags", []))
            if rec.get("error"):
                rows.append([s, pf.stem, "<call>", "", rec["error"], "", tags])
                continue
            for f in a.fields or FIELDS:
                if not match(f, gt[f], ex.get(f)):
                    rows.append([s, pf.stem, f, gt[f], ex.get(f), ex.get("confidence"), tags])

    for r in rows:
        print(" | ".join("" if v is None and i == 3 else str(v) for i, v in enumerate(r)))
    print(f"\n{len(rows)} wrong fields. By field:", dict(Counter(r[2] for r in rows).most_common()))
    if a.csv:
        with open(a.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["set", "doc", "field", "expected", "predicted", "confidence", "tags"])
            w.writerows(rows)


if __name__ == "__main__":
    main()
