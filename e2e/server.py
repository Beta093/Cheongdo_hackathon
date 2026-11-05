"""Offline, synthetic test server; never use this corpus in the production app."""
import os
from pathlib import Path

# Force external integrations off before importing the application module.
os.environ["GAMJABA_MODEL"] = "fake"
os.environ["GAMJABA_STORE"] = "memory"
for name in ("WEATHER_API_KEY", "APPLICATIONINSIGHTS_CONNECTION_STRING"):
    os.environ.pop(name, None)

from backend.agents.fake import FakeModel  # noqa: E402
from backend.app.main import create_app  # noqa: E402
from backend.app.settings import Settings  # noqa: E402

app = create_app(Settings(knowledge_dir=Path(__file__).parent / "fixtures"), FakeModel())
