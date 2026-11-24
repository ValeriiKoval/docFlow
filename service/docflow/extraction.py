"""Claude extraction: one document (PDF or image) -> fields dict.

Shared by the FastAPI service and the offline eval (eval/extract.py), so the
numbers in eval/RESULTS.md describe exactly the code that runs in production.

API notes (current models):
  * forced tool_choice returns 400 on Sonnet 5.5 / Opus 5.5, so we use tool_choice=auto
    + a strict tool schema, tell the model to call the tool, and re-ask if it does not;
  * strict schemas do not support pattern/minimum/maximum, so the schema sent to the
    API is a relaxed copy (ISO dates via format=date); the full schema.json is still
    enforced locally with jsonschema;
  * adaptive thinking is on by default, so output_tokens include thinking tokens;
  * Sonnet / Opus requests enable server-side refusal fallback ("default" routing);
    `served_by` records which model actually answered.
"""
import base64
import copy
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

TOOL_NAME = "record_document"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}

# USD per 1M tokens (input, output). Check against the pricing page before quoting.
PRICES = {"claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50), "claude-opus-5-5": (4.0, 20.0)}


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    pin, pout = PRICES.get(model, (0.0, 0.0))
    return round((input_tokens * pin + output_tokens * pout) / 1e6, 6)


def load_schema(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


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


class ExtractionError(RuntimeError):
    def __init__(self, message, usage=None, attempts=0):
        super().__init__(message)
        self.usage = usage or {"input_tokens": 0, "output_tokens": 0}
        self.attempts = attempts


@dataclass
class ExtractionResult:
    fields: dict
    model: str
    prompt_version: str
    usage: dict = field(default_factory=dict)
    latency_s: float = 0.0
    attempts: int = 1
    stop_reason: str = ""
    served_by: str = ""

    @property
    def cost_usd(self) -> float:
        return cost_usd(self.served_by or self.model, self.usage.get("input_tokens", 0),
                        self.usage.get("output_tokens", 0))


class Extractor:
    def __init__(self, model: str, prompt_version: str, prompts_dir: Path, schema_path: Path,
                 client=None, effort: str | None = None, max_attempts: int = 3):
        self.model, self.prompt_version, self.effort, self.max_attempts = model, prompt_version, effort, max_attempts
        self.system = (Path(prompts_dir) / f"{prompt_version}.md").read_text(encoding="utf-8")
        self.schema = load_schema(schema_path)
        self.tool = {"name": TOOL_NAME, "description": "Record the fields extracted from the document.",
                     "strict": True, "input_schema": api_schema(self.schema)}
        if client is None:
            import anthropic
            client = anthropic.Anthropic(max_retries=4)  # SDK retries network errors, 429, 5xx
        self.client = client

    def _content_block(self, data: bytes, media_type: str) -> dict:
        b64 = base64.standard_b64encode(data).decode()
        if media_type == "application/pdf":
            return {"type": "document", "source": {"type": "base64", "media_type": media_type, "data": b64}}
        if media_type in IMAGE_TYPES:
            return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}}
        raise ValueError(f"unsupported media type {media_type}")

    def validate(self, fields: dict):
        import jsonschema
        jsonschema.validate(fields, self.schema)

    def extract(self, data: bytes, media_type: str) -> ExtractionResult:
        kwargs = dict(model=self.model, max_tokens=16000, system=self.system, tools=[self.tool],
                      tool_choice={"type": "auto"},
                      messages=[{"role": "user", "content": [
                          self._content_block(data, media_type),
                          {"type": "text", "text": f"Extract the fields from this document and call {TOOL_NAME}."}]}])
        if self.effort:
            kwargs["output_config"] = {"effort": self.effort}
        use_fallback = not self.model.startswith("claude-haiku")  # Haiku has no server-side fallback
        usage = {"input_tokens": 0, "output_tokens": 0}
        last_err, t0 = None, time.time()
        for attempt in range(1, self.max_attempts + 1):
            if use_fallback:
                r = self.client.beta.messages.create(betas=[FALLBACK_BETA], fallbacks="default", **kwargs)
            else:
                r = self.client.messages.create(**kwargs)
            usage["input_tokens"] += r.usage.input_tokens
            usage["output_tokens"] += r.usage.output_tokens
            if r.stop_reason == "refusal":
                raise ExtractionError(f"refusal: {getattr(r.stop_details, 'category', None)}", usage, attempt)
            block = next((b for b in r.content if b.type == "tool_use" and b.name == TOOL_NAME), None)
            if block is None:
                last_err = f"no {TOOL_NAME} call (stop_reason={r.stop_reason})"
                continue
            try:
                self.validate(block.input)
            except Exception as e:  # jsonschema.ValidationError
                last_err = f"schema: {str(e).splitlines()[0]}"
                continue
            return ExtractionResult(fields=dict(block.input), model=self.model, prompt_version=self.prompt_version,
                                    usage=usage, latency_s=time.time() - t0, attempts=attempt,
                                    stop_reason=r.stop_reason, served_by=r.model)
        raise ExtractionError(f"{last_err} after {self.max_attempts} attempts", usage, self.max_attempts)
