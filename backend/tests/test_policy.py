import pytest

from backend.app.policy import PolicyError, check_text, validate_sources
from backend.app.schemas import Source


@pytest.mark.parametrize("text", [
    "농약 제품 A를 쓰세요", "살충제 추천", "가상의약 수화제를 사용", "1000배 희석",
    "1,000 배액", "물에 20mL 넣으세요", "10 g/20 L", "토양 수분은 30%입니다",
    "현재 기온은 12도입니다", "농\u200b약 사용", "1000배로 희석",
])
def test_unsafe_output_is_blocked(text):
    with pytest.raises(PolicyError):
        check_text(text)


def test_safe_uncertainty():
    check_text("측정된 토양 수분과 날씨 정보가 없습니다. 현장 확인이 필요합니다.")


def test_sources_are_request_scoped_and_reviewed():
    source = Source(id="checked", source_title="test", source_url="https://example.org",
                    retrieved_at="2026-11-05", reviewed=True)
    assert validate_sources(["checked"], {"checked": source}) == [source]
    for ids, found in [(["invented"], {"checked": source}), (["checked"], {}), ([], {})]:
        with pytest.raises(PolicyError):
            validate_sources(ids, found)
    with pytest.raises(PolicyError):
        validate_sources(["checked"], {"checked": source.model_copy(update={"reviewed": False})})
