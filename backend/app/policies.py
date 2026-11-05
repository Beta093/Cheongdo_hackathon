"""
책임 있는 AI 정책 필터
- 농약 제품명·용량 차단
- 지어낸 측정값 차단
- 출처 검증
- 프롬프트 인젝션 방어
"""

import re
from typing import Optional, Dict, Any, List
from enum import Enum


class PolicyViolation(Enum):
    """정책 위반 유형"""
    PESTICIDE_PRESCRIPTION = "농약 제품명·용량 처방"
    FABRICATED_MEASUREMENT = "지어낸 측정값"
    MISSING_SOURCES = "근거 없는 주장"
    PROMPT_INJECTION = "프롬프트 인젝션 시도"
    UNKNOWN = "기타 위반"


class PolicyChecker:
    """에이전트 출력에 대한 정책 검사"""
    
    def __init__(self):
        # 농약 제품명 패턴 (예: "캡탄", "황산구리", "살충제 10배", "해충약 10배", "살충제 희석 5배" 등)
        self.pesticide_patterns = [
            r'(캡탄|황산구리|살충제|살균제|농약)',  # 제품명
            r'\d+\s*배\s*(희석|희석액|배수)?',  # "10배 희석"
        ]
        
        # 지어낸 측정값 패턴 (토양 수분, 온도 같은 센서 값)
        self.fabricated_measurement_patterns = [
            r'토양\s*수분\s*(\d+)',
            r'토양\s*습도\s*(\d+)',
            r'지온\s*(\d+)',
            r'기온\s*(\d+)',
            r'(산도|ph)\s*(\d+\.?\d*)',
        ]
        
        # 프롬프트 인젝션 키워드
        self.injection_keywords = [
            r'이전\s*지시',
            r'지시를\s*무시',
            r'규칙을\s*변경',
            r'제약을\s*제거',
            r'시스템\s*프롬프트',
        ]
    
    def check_response(self, response: str, sources: List[Dict] = None) -> Dict[str, Any]:
        """
        에이전트 응답 검사
        
        Returns:
            {
                "is_safe": bool,
                "violations": [PolicyViolation, ...],
                "sanitized": str (필요시 수정된 응답),
                "message": str (사용자 알림)
            }
        """
        violations = []
        sanitized = response
        
        # 1. 농약 처방 검사
        for pattern in self.pesticide_patterns:
            if re.search(pattern, response, re.IGNORECASE):
                violations.append(PolicyViolation.PESTICIDE_PRESCRIPTION)
                # 농약 부분을 "전문가 상담" 안내로 대체
                sanitized = re.sub(
                    pattern,
                    "방제 방법은 청도 농업기술센터에 문의해주세요",
                    sanitized,
                    flags=re.IGNORECASE
                )
        
        # 2. 측정되지 않은 값 검사 (센서 없으면 지어낸 값)
        for pattern in self.fabricated_measurement_patterns:
            if re.search(pattern, response, re.IGNORECASE):
                violations.append(PolicyViolation.FABRICATED_MEASUREMENT)
                sanitized = re.sub(
                    pattern,
                    "⚠️ 현장 확인 필요",
                    sanitized,
                    flags=re.IGNORECASE
                )
        
        # 3. 근거 없는 주장 검사 (sources가 없으면 위험)
        if sources is not None and len(sources) == 0:
            # 제안 항목에 출처 없으면 위반
            if "제안" in response or "추천" in response or "해야" in response:
                violations.append(PolicyViolation.MISSING_SOURCES)
        
        # 4. 프롬프트 인젝션 검사
        for keyword in self.injection_keywords:
            if re.search(keyword, response, re.IGNORECASE):
                violations.append(PolicyViolation.PROMPT_INJECTION)
        
        return {
            "is_safe": len(violations) == 0,
            "violations": violations,
            "sanitized": sanitized,
            "message": self._get_violation_message(violations)
        }
    
    def check_sources(self, sources: List[Dict], valid_source_ids: set) -> Dict[str, Any]:
        """
        제안의 출처가 실제 검색 결과에 있는지 검증
        (지어낸 출처 ID 거부)
        """
        invalid_sources = []
        for source in sources:
            source_id = source.get("source_id", "")
            if source_id not in valid_source_ids:
                invalid_sources.append(source_id)
        
        return {
            "is_valid": len(invalid_sources) == 0,
            "invalid_source_ids": invalid_sources,
            "message": f"❌ 검증되지 않은 출처: {invalid_sources}" if invalid_sources else "✅ 모든 출처 검증됨"
        }
    
    def sanitize_proposal(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        """
        제안 항목을 정책으로 검증·수정
        
        Return: {
            "is_valid": bool,
            "proposal": modified proposal,
            "issues": [str, ...]
        }
        """
        issues = []
        
        # 1. 필수 필드 확인
        if not proposal.get("reason"):
            issues.append("reason 필드 누락")
        if not proposal.get("sources"):
            issues.append("sources 배열 필수 (최소 1개)")
            proposal["sources"] = []
        
        # 2. reason 정책 검사
        reason_check = self.check_response(proposal.get("reason", ""))
        if not reason_check["is_safe"]:
            issues.append(f"reason이 정책 위반: {reason_check['message']}")
            proposal["reason"] = reason_check["sanitized"]
        
        # 3. AI 생성 라벨
        if "ai_generated" not in proposal:
            proposal["ai_generated"] = True
        
        return {
            "is_valid": len(issues) == 0,
            "proposal": proposal,
            "issues": issues
        }
    
    def _get_violation_message(self, violations: List[PolicyViolation]) -> str:
        """위반 항목을 사용자 메시지로 변환"""
        if not violations:
            return "✅ 정책 검사 통과"
        
        messages = {
            PolicyViolation.PESTICIDE_PRESCRIPTION: "농약 처방은 전문가 상담이 필요합니다",
            PolicyViolation.FABRICATED_MEASUREMENT: "측정되지 않은 값은 현장 확인이 필요합니다",
            PolicyViolation.MISSING_SOURCES: "근거가 없는 주장은 제안할 수 없습니다",
            PolicyViolation.PROMPT_INJECTION: "외부 지시는 무시됩니다",
        }
        
        return " | ".join(messages.get(v, "알 수 없는 위반") for v in violations)


# 테스트
if __name__ == "__main__":
    checker = PolicyChecker()
    
    # 테스트 케이스 1: 농약 처방 차단
    test1 = "캡탄 10배 희석해서 살포하세요."
    result1 = checker.check_response(test1)
    print(f"🧪 Test 1 (농약):")
    print(f"  입력: {test1}")
    print(f"  안전: {result1['is_safe']}")
    print(f"  수정본: {result1['sanitized']}\n")
    
    # 테스트 케이스 2: 지어낸 값 차단
    test2 = "지금 토양 수분이 65%이므로 물을 줘야 합니다."
    result2 = checker.check_response(test2)
    print(f"🧪 Test 2 (측정값):")
    print(f"  입력: {test2}")
    print(f"  안전: {result2['is_safe']}")
    print(f"  수정본: {result2['sanitized']}\n")
    
    # 테스트 케이스 3: 정상 응답
    test3 = "5월 중순에 적과를 추천합니다. 이유는 과실이 2cm 정도일 때 솎아야 하기 때문입니다."
    result3 = checker.check_response(test3)
    print(f"🧪 Test 3 (정상):")
    print(f"  입력: {test3}")
    print(f"  안전: {result3['is_safe']}")
    print(f"  메시지: {result3['message']}\n")
    
    # 테스트 케이스 4: 출처 검증
    sources = [{"source_id": "fake-source-999"}]
    valid_ids = {"agro-center-2024-persimmon-01", "rural-dev-2024-persimmon-02"}
    result4 = checker.check_sources(sources, valid_ids)
    print(f"🧪 Test 4 (출처):")
    print(f"  유효한 출처: {result4['is_valid']}")
    print(f"  잘못된 ID: {result4['invalid_source_ids']}\n")
    
    # 테스트 케이스 5: 제안 항목 검증
    proposal = {
        "title": "적과 시기",
        "reason": "캡탄을 5배 희석해서 살포하면 됩니다.",
        "sources": []
    }
    result5 = checker.sanitize_proposal(proposal)
    print(f"🧪 Test 5 (제안):")
    print(f"  유효: {result5['is_valid']}")
    print(f"  이슈: {result5['issues']}")
    print(f"  수정본 reason: {result5['proposal'].get('reason')}\n")
