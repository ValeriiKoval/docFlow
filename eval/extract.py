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

API notes (current models):
  * forced tool_choice returns 400 on Sonnet 5.5 / Opus 5.5, so we use tool_choice=auto
    + strict tool schema, tell the model in the prompt to call the tool, and re-ask if
    it does not;
  * strict schemas do not support pattern/minimum/maximum, so the schema sent to the
    API is a relaxed copy (ISO dates via format=date); the full schema.json is still
    enforced locally with jsonschema;
  * adaptive thinking is on by default, so output_tokens include thinking tokens;
  * Sonnet / Opus requests enable server-side refusal fallback ("default" routing);
    `served_by` records which model actually answered.
"""
import argparse, base64, copy, json, os, random, threading, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

try:  # optional: pick up ANTHROPIC_API_KEY / DOCFLOW_MODEL from <repo>/.env
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

SCHEMA = json.loads((ROOT / "schema.json").read_text(encoding="utf-8"))
TOOL_NAME = "record_document"
FALLBACK_BETA = "server-side-fallback-2026-07-01"


def api_schema(schema: dict) -> dict:
    """Strict-mode compatible copy: drop unsupported constraints, nullable types via anyOf."""
    s = copy.deepcopy(schema)
    s.pop("$schema", None)
    s.pop("title", None)
    for name, p in s["properties"].items():
        is_date = "pattern" in p and "\\d{4}" in p["pattern"]
        for k in ("pattern", "minimum", "maximum"):
            p.pop(k, None)
        if is_date:
            p["format"] = "date"
        t = p.get("type")
        if isinstance(t, list):  # ["string", "null"] -> anyOf
            desc = p.pop("description", None)
            base = {k: v for k, v in p.items() if k != "type"}
            s["properties"][name] = {"anyOf": [{"type": t[0], **base}, {"type": "null"}]}
            if desc:
                s["properties"][name]["description"] = desc
    return s


TOOL = {"name": TOOL_NAME, "description": "Record the fields extracted from the document.",
        "strict": True, "input_schema": api_schema(SCHEMA)}


def pdf_dir(src: Path, s: str) -> Path:
    return src / "pdf" if s == "clean" else src / "scans" / s


def validate(extraction):
    import jsonschema
    jsonschema.validate(extraction, SCHEMA)


def call_claude(client, model, system, pdf_path, effort=None, max_attempts=3):
    """One document -> (extraction, usage, latency, meta). Re-asks when no valid tool call comes back.
    Network errors, 429 and 5xx are retried by the SDK itself (max_retries on the client)."""
    import anthropic
    data = base64.standard_b64encode(pdf_path.read_bytes()).decode()
    kwargs = dict(model=model, max_tokens=16000, system=system, tools=[TOOL], tool_choice={"type": "auto"},
                  messages=[{"role": "user", "content": [
                      {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": data}},
                      {"type": "text", "text": f"Extract the fields from this document and call {TOOL_NAME}."}]}])
    if effort:
        kwargs["output_config"] = {"effort": effort}
    use_fallback = not model.startswith("claude-haiku")
    usage = {"input_tokens": 0, "output_tokens": 0}
    last_err, t0 = None, time.time()
    for attempt in range(1, max_attempts + 1):
        if use_fallback:
            r = client.beta.messages.create(betas=[FALLBACK_BETA], fallbacks="default", **kwargs)
        else:
            r = client.messages.create(**kwargs)
        usage["input_tokens"] += r.usage.input_tokens
        usage["output_tokens"] += r.usage.output_tokens
        meta = {"attempts": attempt, "stop_reason": r.stop_reason, "served_by": r.model}
        if r.stop_reason == "refusal":
            raise RuntimeError(f"refusal: {getattr(r.stop_details, 'category', None)}")
        block = next((b for b in r.content if b.type == "tool_use" and b.name == TOOL_NAME), None)
        if block is None:
            last_err = f"no {TOOL_NAME} call (stop_reason={r.stop_reason})"
            continue
        try:
            validate(block.input)
        except Exception as e:  # jsonschema.ValidationError
            last_err = f"schema: {str(e).splitlines()[0]}"
            continue
        return block.input, usage, time.time() - t0, meta
    raise RuntimeError(f"{last_err} after {max_attempts} attempts")


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
    ap.add_argument("--effort", choices=["low", "medium", "high", "xhigh", "max"], help="default: model default")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", nargs="+", help="document stems to run, e.g. 004_invoice_pl")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--force", action="store_true", help="re-run documents that already have a successful prediction")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--out", default=str(HERE / "predictions"))
    a = ap.parse_args()

    src = Path(a.src)
    system = (ROOT / "prompts" / f"{a.prompt}.md").read_text(encoding="utf-8")
    rng = random.Random(0)
    if a.mock:
        model, client = "mock", None
    else:
        if not a.model:
            raise SystemExit("Set --model or DOCFLOW_MODEL")
        import anthropic
        model, client = a.model, anthropic.Anthropic(max_retries=4)
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
                rec["extraction"], rec["usage"], rec["latency_s"], meta = call_claude(client, model, system, p, a.effort)
                rec.update(meta)
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
