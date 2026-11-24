#!/usr/bin/env python3
"""Run Claude extraction over the dataset (clean PDFs + scan levels).

    pip install -r requirements.txt
    cp .env.example .env                      # ANTHROPIC_API_KEY, DOCFLOW_MODEL
    python eval/extract.py --sets clean light medium heavy --limit 40

    python eval/extract.py --mock             # no API: fake predictions to test eval.py

Output: eval/predictions/<model>/<set>/<name>.json
  {"extraction": {...}|null, "usage": {...}, "latency_s": float, "error": str|null, "prompt": "extract_v1"}
"""
import argparse, base64, json, os, random, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

try:  # optional: pick up ANTHROPIC_API_KEY / DOCFLOW_MODEL from <repo>/.env
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

SCHEMA = json.loads((ROOT / "schema.json").read_text(encoding="utf-8"))


def pdf_dir(src: Path, s: str) -> Path:
    return src / "pdf" if s == "clean" else src / "scans" / s


def call_claude(client, model, system, pdf_path, max_retries=3):
    data = base64.standard_b64encode(pdf_path.read_bytes()).decode()
    tool = {"name": "record_document", "description": "Record extracted document fields.",
            "input_schema": SCHEMA}
    last = None
    for attempt in range(max_retries):
        try:
            t0 = time.time()
            r = client.messages.create(
                model=model, max_tokens=1024, system=system,
                tools=[tool], tool_choice={"type": "tool", "name": "record_document"},
                messages=[{"role": "user", "content": [
                    {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": data}},
                    {"type": "text", "text": "Extract the fields from this document."}]}])
            block = next(b for b in r.content if b.type == "tool_use")
            return block.input, {"input_tokens": r.usage.input_tokens, "output_tokens": r.usage.output_tokens}, time.time() - t0
        except Exception as e:  # network, 429, 5xx, schema
            last = e
            time.sleep(2 ** attempt)
    raise last


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
    ap.add_argument("--model", default=os.environ.get("DOCFLOW_MODEL"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--out", default=str(HERE / "predictions"))
    a = ap.parse_args()

    src = Path(a.src)
    system = (ROOT / "prompts" / f"{a.prompt}.md").read_text(encoding="utf-8")
    rng = random.Random(0)
    if a.mock:
        model = "mock"; client = None
    else:
        if not a.model: raise SystemExit("Set --model or DOCFLOW_MODEL")
        import anthropic
        model = a.model; client = anthropic.Anthropic()

    for s in a.sets:
        out = Path(a.out) / model / s
        out.mkdir(parents=True, exist_ok=True)
        pdfs = sorted(pdf_dir(src, s).glob("*.pdf"))
        if a.limit: pdfs = pdfs[:a.limit]
        for p in pdfs:
            label = json.loads((src / "labels" / f"{p.stem}.json").read_text(encoding="utf-8"))
            rec = {"extraction": None, "usage": {}, "latency_s": 0.0, "error": None, "prompt": a.prompt}
            try:
                if a.mock:
                    rec["extraction"] = mock_extraction(label, rng, s)
                    rec["usage"] = {"input_tokens": 1500, "output_tokens": 150}
                else:
                    rec["extraction"], rec["usage"], rec["latency_s"] = call_claude(client, model, system, p)
                validate(rec["extraction"])
            except Exception as e:
                rec["error"] = f"{type(e).__name__}: {e}"[:300]
            (out / f"{p.stem}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{s}: {len(pdfs)} done -> {out}")


if __name__ == "__main__":
    main()
