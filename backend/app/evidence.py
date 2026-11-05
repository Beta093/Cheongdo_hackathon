"""근거/인용 시스템 - AI 응답의 신뢰도 향상"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel


class Evidence(BaseModel):
    """근거 정보"""
    source: str                    # "사용자 입력" | "날씨 데이터" | "토양 분석" 등
    quote: str                     # 원문 인용
    reasoning: str                 # 왜 이 결론에 도달했는지
    confidence: int                # 신뢰도 0-100


class CitedRecommendation(BaseModel):
    """근거가 포함된 추천"""
    recommendation: str            # 주요 추천사항
    evidence_list: List[Evidence]  # 근거 목록
    action_priority: str           # "높음" | "중간" | "낮음"
    estimated_impact: Optional[str] = None  # "수확량 +15%" 등


class EvidenceCollector:
    """근거 수집 및 관리"""
    
    def __init__(self, user_input: str, farm_id: str):
        self.user_input = user_input
        self.farm_id = farm_id
        self.evidence_list: List[Evidence] = []
        self.timestamp = datetime.now().isoformat()
    
    def add_evidence(
        self,
        source: str,
        quote: str,
        reasoning: str,
        confidence: int = 85
    ) -> None:
        """근거 추가"""
        if not (0 <= confidence <= 100):
            raise ValueError("신뢰도는 0-100 사이여야 합니다")
        
        evidence = Evidence(
            source=source,
            quote=quote,
            reasoning=reasoning,
            confidence=confidence
        )
        self.evidence_list.append(evidence)
    
    def add_from_user_input(self, reasoning: str, confidence: int = 90) -> None:
        """사용자 입력을 근거로 추가"""
        self.add_evidence(
            source="사용자 입력",
            quote=self.user_input[:200],  # 처음 200자
            reasoning=reasoning,
            confidence=confidence
        )
    
    def create_cited_recommendation(
        self,
        recommendation: str,
        priority: str = "중간",
        impact: Optional[str] = None
    ) -> CitedRecommendation:
        """근거가 포함된 추천 생성"""
        
        if not self.evidence_list:
            raise ValueError("최소 1개 이상의 근거가 필요합니다")
        
        return CitedRecommendation(
            recommendation=recommendation,
            evidence_list=self.evidence_list,
            action_priority=priority,
            estimated_impact=impact
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "farm_id": self.farm_id,
            "timestamp": self.timestamp,
            "evidence_count": len(self.evidence_list),
            "evidence": [e.dict() for e in self.evidence_list]
        }


class EvidenceFormatter:
    """근거를 사람이 읽기 쉬운 형식으로 포맷팅"""
    
    @staticmethod
    def format_for_display(cited_rec: CitedRecommendation) -> str:
        """사용자 UI용 포맷팅"""
        output = f"📌 {cited_rec.recommendation}\n"
        output += f"⚡ 우선순위: {cited_rec.action_priority}\n"
        
        if cited_rec.estimated_impact:
            output += f"📈 예상 효과: {cited_rec.estimated_impact}\n"
        
        output += f"\n🔗 근거:\n"
        for i, evidence in enumerate(cited_rec.evidence_list, 1):
            output += f"\n{i}. 출처: {evidence.source}\n"
            output += f"   인용: \"{evidence.quote}\"\n"
            output += f"   이유: {evidence.reasoning}\n"
            output += f"   신뢰도: {evidence.confidence}%\n"
        
        return output
    
    @staticmethod
    def format_for_api(cited_rec: CitedRecommendation) -> Dict[str, Any]:
        """API 응답용 포맷팅"""
        return {
            "recommendation": cited_rec.recommendation,
            "priority": cited_rec.action_priority,
            "impact": cited_rec.estimated_impact,
            "evidence": [
                {
                    "source": e.source,
                    "quote": e.quote,
                    "reasoning": e.reasoning,
                    "confidence": e.confidence
                }
                for e in cited_rec.evidence_list
            ],
            "evidence_count": len(cited_rec.evidence_list),
            "confidence_avg": sum(e.confidence for e in cited_rec.evidence_list) // len(cited_rec.evidence_list)
        }


# 사용 예시
if __name__ == "__main__":
    # 예시 시나리오
    print("=" * 70)
    print("근거 시스템 데모")
    print("=" * 70)
    
    user_input = "흙이 건조하고 인(P) 수치가 낮아 보여요"
    
    # 1. 근거 수집
    collector = EvidenceCollector(user_input, farm_id="farm_001")
    
    # 2. 근거 추가
    collector.add_from_user_input(
        reasoning="토양 건조도가 높으므로 수분 공급 필요",
        confidence=95
    )
    
    collector.add_evidence(
        source="토양 분석 데이터",
        quote="인(P) 함량: 120 mg/kg (기준: 150-200)",
        reasoning="인 부족으로 뿌리 발달 저해 가능",
        confidence=88
    )
    
    collector.add_evidence(
        source="날씨 데이터",
        quote="최근 7일 강수량: 0mm, 평균 온도: 28°C",
        reasoning="고온 + 무강우 = 토양 건조 심화",
        confidence=92
    )
    
    # 3. 추천 생성
    recommendation = collector.create_cited_recommendation(
        recommendation="비료(인 성분) 시비 + 관수",
        priority="높음",
        impact="수확량 +10-15%, 뿌리 강화"
    )
    
    # 4. 표시
    print("\n📱 사용자 UI 출력:")
    print("-" * 70)
    print(EvidenceFormatter.format_for_display(recommendation))
    
    print("\n📡 API 응답:")
    print("-" * 70)
    import json
    print(json.dumps(EvidenceFormatter.format_for_api(recommendation), 
                     indent=2, ensure_ascii=False))
