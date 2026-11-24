#!/usr/bin/env python3
"""Run Claude extraction over the dataset (clean PDFs + scan levels).

    pip install -r requirements.txt
    cp .env.example .env                      # ANTHROPIC_API_KEY, DOCFLOW_MODEL
    python eval/extract.py --sets clean --limit 3            # smoke test
    python eval/extract.py --sets clean light medium heavy --workers 4
    python eval/extract.py --prompt extract_v2 --model claude-haiku-5-5

    python eval/extract.py --mock             # no API: fake predictions to test eval.py

Output: eval/predictions/<model>/<prompt>/<set>/<name>.json
  {"extraction": {...}|null, "usage": {...}, "latency_s": float, "attempts": int,
   "stop_reason": str, "served_by": str, "error": str|null, "prompt": str}

The Claude call itself lives in service/docflow/extraction.py (shared with the
FastAPI service), so eval numbers describe the production code path.
"""
import argparse, json, os, random, sys, threading, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "service"))

from docflow.config import Settings  # noqa: E402  (also loads <repo>/.env)
from docflow.extraction import Extractor, load_schema  # noqa: E402

SCHEMA = load_schema(ROOT / "schema.json")


def pdf_dir(src: Path, s: str) -> Path:
    return src / "pdf" if s == "clean" else src / "scans" / s


def validate(extraction):
    import jsonschema
    jsonschema.validate(extraction, SCHEMA)


def mock_extraction(label, rng, set_name):
    """Fake model: noisier on worse scans. Only for testing the eval pipeline."""
    err = {"clean": 0.03, "light": 0.06, "medium": 0.15, "heavy": 0.30}[set_name]
    e = {k: label[k] for k in SCHEMA["required"] if k != "confidence"}
    for k in list(e):
        if rng.random() < err and e[k] is not None:
            if k == "total_amount": e[k] = round(e[k] * rng.choice([0.1, 10, 1.01]), 2)
            elif k.endswith("date") or k.startswith("valid"): e[k] = "2025-01-01"
            elif k == "doc_type": e[k] = "other"
            else: e[k] = str(e[k])[:-1]
    e["confidence"] = round(max(0.2, min(0.99, rng.gauss(0.92 - 2 * err, 0.08))), 2)
    return e


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(HERE / "dataset"))
    ap.add_argument("--sets", nargs="+", default=["clean", "light", "medium", "heavy"])
    ap.add_argument("--prompt", default="extract_v1")
    ap.add_argument("--model", default=os.environ.get("DOCFLOW_MODEL"), help="default: DOCFLOW_MODEL")
    ap.add_argument("--effort", choices=["low", "medium", "high", "xhigh", "max"], help="default: model default")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", nargs="+", help="document stems to run, e.g. 004_invoice_pl")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--force", action="store_true", help="re-run documents that already have a successful prediction")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--out", default=str(HERE / "predictions"))
    a = ap.parse_args()

    src = Path(a.src)
    rng = random.Random(0)
    if a.mock:
        model, extractor = "mock", None
    else:
        model = a.model or Settings().model
        extractor = Extractor(model, a.prompt, ROOT / "prompts", ROOT / "schema.json", effort=a.effort)
    run_name = model + (f"@{a.effort}" if a.effort else "")
    lock = threading.Lock()
    totals = {"in": 0, "out": 0, "err": 0}

    def work(s, p, out):
        label = json.loads((src / "labels" / f"{p.stem}.json").read_text(encoding="utf-8"))
        rec = {"extraction": None, "usage": {}, "latency_s": 0.0, "error": None, "prompt": a.prompt}
        try:
            if a.mock:
                rec["extraction"] = mock_extraction(label, rng, s)
                rec["usage"] = {"input_tokens": 1500, "output_tokens": 150}
                validate(rec["extraction"])
            else:
                r = extractor.extract(p.read_bytes(), "application/pdf")
                rec.update(extraction=r.fields, usage=r.usage, latency_s=r.latency_s, attempts=r.attempts,
                           stop_reason=r.stop_reason, served_by=r.served_by)
        except Exception as e:
            rec["error"] = f"{type(e).__name__}: {e}"[:400]
        (out / f"{p.stem}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        with lock:
            totals["in"] += rec["usage"].get("input_tokens", 0)
            totals["out"] += rec["usage"].get("output_tokens", 0)
            totals["err"] += bool(rec["error"])
        return p.stem, rec["error"]

    for s in a.sets:
        out = Path(a.out) / run_name / a.prompt / s
        out.mkdir(parents=True, exist_ok=True)
        pdfs = sorted(pdf_dir(src, s).glob("*.pdf"))
        if a.only:
            pdfs = [p for p in pdfs if p.stem in a.only]
        if a.limit:
            pdfs = pdfs[:a.limit]
        if not a.force:
            def done(p):
                f = out / f"{p.stem}.json"
                return f.exists() and not json.loads(f.read_text(encoding="utf-8")).get("error")
            pdfs = [p for p in pdfs if not done(p)]
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=1 if a.mock else a.workers) as ex:
            for fut in as_completed([ex.submit(work, s, p, out) for p in pdfs]):
                stem, err = fut.result()
                if err:
                    print(f"  ! {s}/{stem}: {err}")
        print(f"{s}: {len(pdfs)} done in {time.time() - t0:.0f}s -> {out}")
    print(f"tokens: in={totals['in']} out={totals['out']} | errors: {totals['err']}")


if __name__ == "__main__":
    main()
