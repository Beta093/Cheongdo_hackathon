"""
감잡아 AI 에이전트 (Copilot SDK + Microsoft Agent Framework)
- GitHub Copilot SDK로 LLM 모델 제공
- Microsoft Agent Framework로 도구 호출 오케스트레이션
- 도구: search_knowledge, get_weather, get_farm_context, propose_calendar_event
"""

import json
import os
import asyncio
from typing import Any, Optional
from datetime import datetime

from copilot import CopilotClient
from agent_framework_github_copilot import GitHubCopilotAgent


class FarmAdvisorAgent:
    """
    청도반시 초보 농부 도우미 에이전트 (SDK 통합 버전)
    - Copilot SDK를 통해 LLM 호출
    - Agent Framework를 통해 도구 실행 오케스트레이션
    """
    
    def __init__(self):
        self.name = "감잡아 AI"
        self.version = "1.0.0"
        self.copilot_client: Optional[CopilotClient] = None
        self.agent: Optional[GitHubCopilotAgent] = None
        self._initialize_sdk()
    
    def _initialize_sdk(self):
        """Copilot SDK + Agent Framework 초기화"""
        github_token = os.getenv("GITHUB_TOKEN")
        
        try:
            # Copilot Client 생성
            if github_token:
                self.copilot_client = CopilotClient(github_token)
            
            # Agent Framework 에이전트 생성
            instructions = """
당신은 청도반시를 재배하는 초보 농부를 돕는 AI 어시스턴트입니다.
역할:
1. 검증된 재배 정보만 제공 (출처 필수)
2. 농부의 오늘 할 일을 제안
3. 토양 센서 데이터 없이는 측정값을 만들지 않기
4. 불확실한 진단은 전문가 확인 권장

사용 가능한 도구를 활용해 정보를 검색하고 답변하세요.
"""
            
            # 도구 함수들
            tools = [
                self._tool_search_knowledge,
                self._tool_get_weather,
                self._tool_get_farm_context,
                self._tool_propose_calendar_event,
            ]
            
            self.agent = GitHubCopilotAgent(
                instructions=instructions,
                tools=tools,
                default_options={"model": "gpt-4", "timeout": 30}
            )
            
            print(f"✅ {self.name} v{self.version} 초기화 완료 (SDK 모드)")
            
        except Exception as e:
            print(f"⚠️ SDK 초기화 시 오류: {e}")
            print("   폴백 모드(rule-based)로 실행합니다.")
            self.agent = None

    def _tool_search_knowledge(self, query: str, farm_type: str = "청도반시") -> dict:
        """도구 1: 지식 검색"""
        print(f"🔍 도구 호출: search_knowledge(query='{query}')")
        
        mock_results = {
            "5월 적과": {
                "title": "5월 중순~6월 초 적과 (열매 솎기)",
                "description": "과실 크기 2cm 정도일 때 솎아 과실당 잎 50장 비율 유지",
                "sources": [
                    {
                        "source_id": "agro-center-2024-persimmon-01",
                        "source_title": "청도 농업기술센터 단감 재배 관리법",
                        "source_url": "https://example.com/청도기술센터",
                        "retrieved_at": "2026-11-05T00:00:00Z"
                    }
                ],
                "confidence": 0.95
            },
            "장마철 관리": {
                "title": "장마철(6~7월) 과원 관리",
                "description": "배수 불량 방지, 병해충 증가 시 전문가 상담 권장",
                "sources": [
                    {
                        "source_id": "rural-dev-2024-persimmon-02",
                        "source_title": "농촌진흥청 과실 재배 지침",
                        "source_url": "https://example.com/농진청",
                        "retrieved_at": "2026-11-05T00:00:00Z"
                    }
                ],
                "confidence": 0.90
            }
        }
        
        result = mock_results.get(query, {
            "title": f"'{query}'에 대한 결과 없음",
            "description": "확인이 필요합니다. 청도 농업기술센터에 문의해주세요.",
            "sources": [],
            "confidence": 0.0
        })
        
        return {
            "success": True,
            "query": query,
            "result": result,
            "timestamp": datetime.now().isoformat()
        }

    def _tool_get_weather(self, farm_id: str) -> dict:
        """도구 2: 날씨 조회"""
        print(f"🌤️ 도구 호출: get_weather(farm_id='{farm_id}')")
        
        return {
            "success": True,
            "farm_id": farm_id,
            "weather": {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "condition": "맑음",
                "temperature": 22,
                "humidity": 65,
                "wind_speed": 3.5
            },
            "timestamp": datetime.now().isoformat()
        }

    def _tool_get_farm_context(self, farm_id: str) -> dict:
        """도구 3: 과원 정보 조회"""
        print(f"🌳 도구 호출: get_farm_context(farm_id='{farm_id}')")
        
        farm_data = {
            "demo": {
                "id": "demo",
                "name": "청도 데모 과원",
                "location": "경주시 청도",
                "variety": "청도반시",
                "planted_year": 2021,
                "tree_age_years": 5,
                "area_pyeong": 100,
                "area_m2": 330,
                "last_observation": "2026-11-05",
                "current_growth_stage": "열매 비대기",
            }
        }
        
        farm = farm_data.get(farm_id, farm_data["demo"])
        
        return {
            "success": True,
            "farm_id": farm_id,
            "farm": farm,
            "timestamp": datetime.now().isoformat()
        }

    def _tool_propose_calendar_event(self, farm_id: str, task: str, 
                                     recommended_date: str, reason: str) -> dict:
        """도구 4: 일정 제안 생성"""
        print(f"📅 도구 호출: propose_calendar_event(task='{task}')")
        
        proposal_id = f"prop_{farm_id}_{int(datetime.now().timestamp())}"
        
        return {
            "success": True,
            "proposal": {
                "id": proposal_id,
                "farm_id": farm_id,
                "task": task,
                "recommended_date": recommended_date,
                "reason": reason,
                "status": "pending",
                "created_at": datetime.now().isoformat()
            },
            "timestamp": datetime.now().isoformat()
        }

    async def run_with_user_input(self, user_message: str, farm_id: str = "demo") -> str:
        """
        사용자 메시지 처리 (Copilot SDK + Agent Framework 모드)
        - Agent Framework가 LLM을 호출하고 도구 실행을 오케스트레이션
        """
        print(f"\n💬 사용자: {user_message}")
        print(f"📍 과원: {farm_id}\n")
        
        try:
            if not self.agent:
                # SDK 실패 시 폴백
                return self._run_with_fallback(user_message, farm_id)
            
            # Agent Framework 실행
            response = await self.agent.run(user_message)
            print(f"🤖 에이전트 응답:\n{response}\n")
            return response
        
        except Exception as e:
            print(f"⚠️ SDK 실행 오류: {e}")
            return self._run_with_fallback(user_message, farm_id)
    
    def _run_with_fallback(self, user_message: str, farm_id: str) -> str:
        """폴백: 규칙 기반 라우팅"""
        response = ""
        
        if "날씨" in user_message or "기상" in user_message:
            weather = self._tool_get_weather(farm_id)
            response = f"🌤️ 오늘 날씨: {weather['weather']['condition']}, 기온 {weather['weather']['temperature']}°C"
        
        elif "할일" in user_message or "오늘" in user_message:
            farm = self._tool_get_farm_context(farm_id)
            knowledge = self._tool_search_knowledge("5월 적과")
            if farm["success"]:
                response = f"🌳 {farm['farm']['name']}에서 추천 작업:\n"
                response += f"  - {knowledge['result']['title']}\n"
                response += f"  - {knowledge['result']['description']}"
        
        elif "일정" in user_message or "제안" in user_message:
            proposal = self._tool_propose_calendar_event(
                farm_id=farm_id,
                task="적과 (열매 솎기)",
                recommended_date="2026-11-15",
                reason="5월 중순이 적과 시기입니다"
            )
            response = f"✅ 일정 제안 생성 완료 (ID: {proposal['proposal']['id']})"
        
        else:
            response = "🤔 죄송합니다. '오늘 할 일', '날씨' 또는 '일정'에 대해 물어봐주세요."
        
        return response


# 스파이크 테스트
if __name__ == "__main__":
    agent = FarmAdvisorAgent()
    
    test_messages = [
        "오늘 할 일이 뭐야?",
        "날씨는 어때?",
        "일정을 제안해줘"
    ]
    
    print("=" * 60)
    print("🚀 감잡아 에이전트 테스트 (SDK 버전)")
    print("=" * 60)
    
    for msg in test_messages:
        asyncio.run(agent.run_with_user_input(msg, farm_id="demo"))
    
    print("=" * 60)
