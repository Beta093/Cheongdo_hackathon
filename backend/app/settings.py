from dataclasses import dataclass, field
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    knowledge_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "knowledge")
    session_ttl: int = 7200
    proposal_ttl: int = 1800
    session_rate: int = 60
    ip_rate: int = 240
    rate_window: int = 60
    model_timeout: float = 40.0
    max_model_concurrency: int = 2
    max_sessions: int = 1000
    max_body_bytes: int = 16384
