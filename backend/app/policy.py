import os
import re
import unicodedata
from urllib.parse import urlsplit

from backend.app.schemas import Source


class PolicyError(ValueError):
    pass


UNCERTAIN = "검토된 근거가 부족합니다. 작업 시기와 방법은 청도군 농업기술센터에 확인해 주세요."
BLOCKED = "응답이 안전성 또는 출처 검사를 통과하지 못했습니다. 질문을 바꿔 다시 시도해 주세요."

# Intentionally conservative P0 filter; not a comprehensive pesticide-name classifier.
PATTERNS = [
    r"농약|살충제|살균제|제초제|약제|수화제|유제|입제|액상수화제",
    r"\d[\d,.]*배(?:로|액|희석)?",
    r"\d[\d,.]*(?:mg|kg|ml|cc|g|l|그램|밀리리터|리터)(?:\b|[가-힣/])",
    r"(?:토양수분|수분함량|토양온도|기온|강수량|습도|풍속).{0,30}\d",
    r"(?:gh[pousr]_|github_pat_)[a-z0-9_]+",
]


def check_text(text: str) -> None:
    for key in ("COPILOT_GITHUB_TOKEN", "WEATHER_API_KEY", "COSMOS_KEY",
                "APPLICATIONINSIGHTS_CONNECTION_STRING"):
        token = os.environ.get(key, "")
        if token and token in text:
            raise PolicyError("secret_in_output")
    normalized = unicodedata.normalize("NFKC", text).lower()
    normalized = "".join(char for char in normalized
                         if not char.isspace() and unicodedata.category(char) != "Cf")
    if any(re.search(pattern, normalized) for pattern in PATTERNS):
        raise PolicyError("unsafe_output")


def validate_sources(ids: list[str], found: dict[str, Source]) -> list[Source]:
    if not ids:
        raise PolicyError("missing_sources")
    sources = []
    for source_id in dict.fromkeys(ids):
        source = found.get(source_id)
        if source is None or not source.reviewed:
            raise PolicyError("unverified_source")
        parsed = urlsplit(source.source_url)
        if parsed.scheme != "https" or not parsed.netloc or "확인 필요" in source.source_url:
            raise PolicyError("invalid_source_url")
        check_text(source.source_title)
        sources.append(source)
    return sources
