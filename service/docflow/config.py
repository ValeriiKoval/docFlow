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
    api_key: str = _env("SERVICE_API_KEY", "")  # empty = no auth (local dev only)
    max_file_mb: int = field(default_factory=lambda: int(os.getenv("MAX_FILE_MB", "20")))
    max_pages: int = field(default_factory=lambda: int(os.getenv("MAX_PAGES", "20")))


@lru_cache
def get_settings() -> Settings:
    return Settings()
