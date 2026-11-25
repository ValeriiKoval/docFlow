"""Settings from environment variables (and <repo>/.env when present)."""
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

try:
    from dotenv import load_dotenv
    load_dotenv(REPO / ".env")
except ImportError:
    pass


def _env(name, default):
    return field(default_factory=lambda: os.getenv(name, default))


@dataclass(frozen=True)
class Settings:
    model: str = _env("DOCFLOW_MODEL", "claude-sonnet-5-5")
    prompt_version: str = _env("DOCFLOW_PROMPT", "extract_v2")
    # chosen in eval/RESULTS.md: 81.5% auto-accepted, 1/200 wrong documents passed
    confidence_threshold: float = field(default_factory=lambda: float(os.getenv("CONFIDENCE_THRESHOLD", "0.6")))
    database_url: str = _env("DATABASE_URL", f"sqlite:///{(REPO / 'data' / 'docflow.db').as_posix()}")
    storage_dir: Path = field(default_factory=lambda: Path(os.getenv("STORAGE_DIR", str(REPO / "data" / "files"))))
    prompts_dir: Path = field(default_factory=lambda: Path(os.getenv("PROMPTS_DIR", str(REPO / "prompts"))))
    schema_path: Path = field(default_factory=lambda: Path(os.getenv("SCHEMA_PATH", str(REPO / "schema.json"))))
    api_key: str = _env("SERVICE_API_KEY", "")  # required unless dev_mode
    # DOCFLOW_DEV=1: allow running without SERVICE_API_KEY (local experiments only). Without it, an empty
    # key makes every protected endpoint answer 503 instead of silently serving unauthenticated requests.
    dev_mode: bool = field(default_factory=lambda: os.getenv("DOCFLOW_DEV", "").lower() in ("1", "true", "yes"))
    max_file_mb: int = field(default_factory=lambda: int(os.getenv("MAX_FILE_MB", "20")))
    max_pages: int = field(default_factory=lambda: int(os.getenv("MAX_PAGES", "20")))
    # Haiku: 12/13 on the QA eval (Sonnet 13/13) at ~1/15 of the cost: eval/RESULTS.md
    agent_model: str = _env("DOCFLOW_AGENT_MODEL", "claude-haiku-5-5")
    agent_effort: str = _env("DOCFLOW_AGENT_EFFORT", "low")    # short chat answers; "" = model default


@lru_cache
def get_settings() -> Settings:
    return Settings()
