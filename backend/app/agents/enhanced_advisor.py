"""
감잡아 AI 에이전트 - 향상된 버전
- 지식 기반 응답 (한국 농업 지침)
- 컨텍스트 메모리 (대화 이력)
- 도구 기반 추론 (검색, 진단, 계획)
- 신뢰도 추적
"""

import json
import os
import asyncio
from typing import Any, Optional, List, Dict
from datetime import datetime, timedelta
from enum import Enum


class TaskPriority(Enum):
    """작업 우선순위"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SeasonalStage(Enum):
    """생육 단계"""
    DORMANCY = "dormancy"  # 휴면기 (11월-2월)
    SPROUTING = "sprouting"  # 발아기 (3월)
    GROWTH = "growth"  # 생장기 (4-6월)
    FLOWERING = "flowering"  # 개화기 (5-6월)
    THINNING = "thinning"  # 적과기 (5-7월)
    DEVELOPMENT = "development"  # 과실 비대기 (7-9월)
    RIPENING = "ripening"  # 숙성기 (9-11월)


class KnowledgeBase:
    """청도반시 재배 지식베이스"""
    
    # 월별 주요 작업
    MONTHLY_TASKS = {
        1: {  # 1월: 겨울 관리
            "high": [
                {
                    "task": "동해 방지",
                    "reason": "최저 기온이 -10°C 이하일 때 백색 페인트 칠하기",
                    "description": "주간 동측 미백 처리로 낮과 밤의 온도 차이 감소",
                    "sources": ["청도농기원_동해방지_2024"]
                },
                {
                    "task": "강전정 (강한 전정)",
                    "reason": "겨울은 나무 정형의 최적 시기",
                    "description": "구거지를 제거하고 통풍을 좋게 하기",
                    "sources": ["농진청_과수전정지침_2024"]
                }
            ],
            "medium": [
                {
                    "task": "비료 계획 수립",
                    "reason": "이듬해 재배 계획 준비",
                    "description": "토양 검사 결과에 기반해 시비량 결정",
                    "sources": ["청도농기원_시비지침_2024"]
                }
            ],
            "low": [
                {
                    "task": "농기구 점검 및 정비",
                    "reason": "봄철 작업 준비",
                    "description": "전기톱, 가지자르기, 분무기 등 점검",
                    "sources": ["안전관리지침"]
                }
            ]
        },
        
        2: {  # 2월: 후기 겨울
            "high": [
                {
                    "task": "전정 완료",
                    "reason": "3월 발아 전에 전정 마무리",
                    "description": "수형 정리 및 불필요한 가지 제거",
                    "sources": ["청도농기원_전정지침_2024"]
                }
            ],
            "medium": [
                {
                    "task": "기초 비료 준비",
                    "reason": "발아 전 토양 준비",
                    "description": "퇴비 1-2톤/10a 시용 준비",
                    "sources": ["농진청_시비지침_2024"]
                }
            ]
        },
        
        3: {  # 3월: 발아기
            "high": [
                {
                    "task": "발아 촉진 작업",
                    "reason": "고르고 빠른 발아를 위해",
                    "description": "노지에 물 주기 (주 1-2회, 토양 함수량 70% 유지)",
                    "sources": ["청도농기원_관수지침_2024"]
                },
                {
                    "task": "봄철 해충 방제",
                    "reason": "발아 후 곤충 증가",
                    "description": "진딧물, 잎말이나방 예방 약제 살포",
                    "sources": ["농진청_병해충예찰_2024"]
                }
            ],
            "medium": [
                {
                    "task": "추비 살포",
                    "reason": "발아 후 양분 공급",
                    "description": "요소 3-5kg/10a (엽면 살포 권장)",
                    "sources": ["청도농기원_시비지침_2024"]
                }
            ]
        },
        
        4: {  # 4월: 개화 준비
            "high": [
                {
                    "task": "개화 전 병해충 방제",
                    "reason": "개화 중 약제 살포 불가",
                    "description": "흰가루병, 깍지벌레 등 선제적 방제",
                    "sources": ["농진청_병해충예찰_2024"]
                }
            ],
            "medium": [
                {
                    "task": "관수 관리",
                    "reason": "개화기 적정 토양 수분 필수",
                    "description": "토양 함수량 70-80% 유지, 개화 중 과다 관수 피하기",
                    "sources": ["청도농기원_관수지침_2024"]
                }
            ]
        },
        
        5: {  # 5월: 개화 및 적과기
            "high": [
                {
                    "task": "인공 수분 (개화기)",
                    "reason": "화분 부족으로 인한 결실 저하 방지",
                    "description": "개화 초기~최성기에 이른 아침 인공 수분 실시",
                    "sources": ["청도농기원_개화관리_2024"]
                },
                {
                    "task": "적과 (열매 솎기)",
                    "reason": "과실 크기 2cm 정도일 때 솎아 품질 향상",
                    "description": "과실당 잎 50장 비율 유지 (3-4개 남기기)",
                    "sources": ["청도농기원_적과지침_2024"]
                }
            ],
            "medium": [
                {
                    "task": "질소 비료 제한",
                    "reason": "지나친 잎 성장 억제",
                    "description": "개화기부터 질소 비료 줄이기",
                    "sources": ["농진청_시비지침_2024"]
                },
                {
                    "task": "병해충 방제",
                    "reason": "따뜻한 날씨로 해충 증가",
                    "description": "나방류, 진딧물 주기적 점검",
                    "sources": ["농진청_병해충예찰_2024"]
                }
            ]
        },
        
        6: {  # 6월: 장마철
            "high": [
                {
                    "task": "배수 관리",
                    "reason": "장마로 인한 뿌리 부패 방지",
                    "description": "배수 불량 지역 확인 및 배수로 정리",
                    "sources": ["청도농기원_장마관리_2024"]
                },
                {
                    "task": "여름 전정 (순 적심)",
                    "reason": "과실 비대 촉진",
                    "description": "기부 10-15엽까지 적심하여 양분 집중",
                    "sources": ["청도농기원_전정지침_2024"]
                }
            ],
            "medium": [
                {
                    "task": "병해충 방제",
                    "reason": "고온 다습으로 병해 급증",
                    "description": "탄저병, 흰가루병, 곰팡이병 예방",
                    "sources": ["농진청_병해충예찰_2024"]
                }
            ]
        },
        
        7: {  # 7월: 여름철
            "high": [
                {
                    "task": "가뭄 관수",
                    "reason": "여름 고온으로 수분 부족",
                    "description": "아침 또는 저녁에 충분히 관수, 토양 함수량 70% 유상",
                    "sources": ["청도농기원_관수지침_2024"]
                }
            ],
            "medium": [
                {
                    "task": "병해충 모니터링",
                    "reason": "고온 다습한 환경",
                    "description": "주 2-3회 과원 순회 점검",
                    "sources": ["농진청_병해충예찰_2024"]
                }
            ]
        },
        
        8: {  # 8월: 과실 비대기
            "high": [
                {
                    "task": "과실 비대 관수",
                    "reason": "과실 크기 중요한 시기",
                    "description": "토양 함수량 60-70% 유지, 급수 불균등 피하기",
                    "sources": ["청도농기원_관수지침_2024"]
                }
            ],
            "medium": [
                {
                    "task": "포장 작업",
                    "reason": "과실 광합성 향상",
                    "description": "흰 부직포나 은박 반사재 깔기 (선택사항)",
                    "sources": ["청도농기원_품질향상_2024"]
                }
            ]
        },
        
        9: {  # 9월: 숙성 개시
            "high": [
                {
                    "task": "착색 관리",
                    "reason": "착색 시기 시작",
                    "description": "과다 관수 피하고 (토양 함수량 50-60%), 일조 확보",
                    "sources": ["청도농기원_착색관리_2024"]
                }
            ],
            "medium": [
                {
                    "task": "병해충 최종 방제",
                    "reason": "수확 전 해충 방지",
                    "description": "나방류, 깍지벌레 최종 방제",
                    "sources": ["농진청_병해충예찰_2024"]
                }
            ]
        },
        
        10: {  # 10월: 숙성 진행
            "high": [
                {
                    "task": "수확 준비",
                    "reason": "수확 1개월 전 준비",
                    "description": "수확용 용기, 포장재, 노동력 준비",
                    "sources": ["청도농기원_수확준비_2024"]
                }
            ],
            "medium": [
                {
                    "task": "수확 기준 확인",
                    "reason": "최적 성숙도 판정",
                    "description": "감도계 사용 또는 색상 확인 (9-10브릭스)",
                    "sources": ["청도농기원_수확지침_2024"]
                }
            ]
        },
        
        11: {  # 11월: 수확
            "high": [
                {
                    "task": "본격 수확",
                    "reason": "주 수확 시기",
                    "description": "아침 이슬 마른 후 수확, 흠 없는 것 우선",
                    "sources": ["청도농기원_수확지침_2024"]
                }
            ],
            "medium": [
                {
                    "task": "수확 후 관리",
                    "reason": "품질 유지",
                    "description": "냉동 저장소 준비, 급속 냉각",
                    "sources": ["청도농기원_저장지침_2024"]
                }
            ]
        },
        
        12: {  # 12월: 동계 준비
            "high": [
                {
                    "task": "수확 완료 및 정리",
                    "reason": "내년을 위한 준비",
                    "description": "낙엽 정리, 부산물 처리",
                    "sources": ["청도농기원_동계준비_2024"]
                }
            ],
            "medium": [
                {
                    "task": "겨울 준비",
                    "reason": "동해 방지",
                    "description": "흙 북돋기, 짚 덮기 (지역에 따라)",
                    "sources": ["청도농기원_동해방지_2024"]
                }
            ]
        }
    }
    
    # 질병 진단 정보
    DISEASE_DIAGNOSIS = {
        "탄저병": {
            "symptoms": "잎, 열매에 갈색 반점, 검은색 테두리",
            "cause": "고온 다습",
            "treatment": "베노밀, 카르벤다짐 등 살균제 살포",
            "prevention": "배수 개선, 환기 좋게",
            "sources": ["농진청_병해충지침_2024"]
        },
        "흰가루병": {
            "symptoms": "잎, 신초에 흰색 가루 같은 병반",
            "cause": "낮은 습도와 온난",
            "treatment": "황, 트리플루미졸 등 살포",
            "prevention": "통풍 개선, 질소 과다 피하기",
            "sources": ["농진청_병해충지침_2024"]
        },
        "깍지벌레": {
            "symptoms": "가지, 줄기에 갈색 딱지 같은 곤충",
            "cause": "월동 후 4월부터 증가",
            "treatment": "유제 살포 (유황 10배)",
            "prevention": "발아 전 석회유황합제 살포",
            "sources": ["농진청_병해충지침_2024"]
        }
    }


class EnhancedFarmAdvisor:
    """향상된 감잡아 AI - 기능 중심"""
    
    def __init__(self):
        self.name = "감잡아 AI"
        self.version = "2.0.0"
        self.kb = KnowledgeBase()
        self.conversation_history: List[Dict] = []
        self.farm_memory: Dict = {}
        
        print(f"✅ {self.name} v{self.version} 초기화 완료 (기능 강화 모드)")
    
    def get_current_season(self) -> tuple:
        """현재 계절 및 생육 단계 판단"""
        today = datetime.now()
        month = today.month
        
        month_map = {
            (1, 2): (SeasonalStage.DORMANCY, "휴면기"),
            (3,): (SeasonalStage.SPROUTING, "발아기"),
            (4,): (SeasonalStage.GROWTH, "생장기"),
            (5, 6): (SeasonalStage.FLOWERING, "개화기"),
            (5, 6, 7): (SeasonalStage.THINNING, "적과기"),
            (7, 8, 9): (SeasonalStage.DEVELOPMENT, "과실 비대기"),
            (9, 10, 11): (SeasonalStage.RIPENING, "숙성기"),
        }
        
        for months, (stage, label) in month_map.items():
            if month in months:
                return stage, label
        
        return SeasonalStage.DORMANCY, "휴면기"
    
    def get_today_tasks(self, farm_id: str = "demo") -> Dict:
        """오늘의 추천 작업"""
        today = datetime.now()
        month = today.month
        
        tasks_by_priority = self.kb.MONTHLY_TASKS.get(month, {})
        
        result = {
            "farm_id": farm_id,
            "date": today.strftime("%Y-%m-%d"),
            "season": self.get_current_season()[1],
            "tasks": []
        }
        
        # 우선순위별 작업 정렬
        for priority in [TaskPriority.HIGH, TaskPriority.MEDIUM, TaskPriority.LOW]:
            tasks = tasks_by_priority.get(priority.value, [])
            for task in tasks:
                result["tasks"].append({
                    "id": f"{month}_{task['task']}",
                    "priority": priority.value,
                    "title": task["task"],
                    "reason": task["reason"],
                    "description": task["description"],
                    "sources": task["sources"],
                    "recommended_time": "오전 10시" if priority == TaskPriority.HIGH else "오후"
                })
        
        return result
    
    def diagnose_disease(self, symptoms: str) -> Dict:
        """증상 기반 질병 진단"""
        results = []
        
        for disease, info in self.kb.DISEASE_DIAGNOSIS.items():
            # 간단한 키워드 매칭
            if any(kw in symptoms for kw in disease.split()):
                results.append({
                    "disease": disease,
                    "confidence": 0.85,
                    "symptoms": info["symptoms"],
                    "cause": info["cause"],
                    "treatment": info["treatment"],
                    "prevention": info["prevention"],
                    "sources": info["sources"]
                })
        
        if not results:
            results.append({
                "disease": "진단 불가",
                "confidence": 0.0,
                "recommendation": "전문가(청도농기원 010-XXXX-XXXX) 상담 권장",
                "sources": []
            })
        
        return {
            "query": symptoms,
            "results": results,
            "timestamp": datetime.now().isoformat()
        }
    
    def propose_plan(self, farm_id: str, duration_days: int = 30) -> Dict:
        """맞춤형 영농 계획 수립"""
        today = datetime.now()
        tasks = self.get_today_tasks(farm_id)
        
        plan = {
            "farm_id": farm_id,
            "start_date": today.strftime("%Y-%m-%d"),
            "end_date": (today + timedelta(days=duration_days)).strftime("%Y-%m-%d"),
            "season": self.get_current_season()[1],
            "total_tasks": len(tasks["tasks"]),
            "tasks_by_priority": {
                "high": [t for t in tasks["tasks"] if t["priority"] == "high"],
                "medium": [t for t in tasks["tasks"] if t["priority"] == "medium"],
                "low": [t for t in tasks["tasks"] if t["priority"] == "low"],
            },
            "success_factors": [
                "정기적 병해충 모니터링 (주 2-3회)",
                "토양 수분 관리 (함수량 60-80% 유지)",
                "시기별 전정 및 관리 철저히",
                "농기원 상담 적극 활용"
            ],
            "timestamp": datetime.now().isoformat()
        }
        
        return plan
    
    async def run_with_user_input(self, user_message: str, farm_id: str = "demo") -> str:
        """사용자 입력 처리 (컨텍스트 기반)"""
        
        # 대화 이력 저장
        self.conversation_history.append({
            "role": "user",
            "content": user_message,
            "timestamp": datetime.now().isoformat()
        })
        
        print(f"\n💬 사용자: {user_message}")
        print(f"📍 과원: {farm_id}\n")
        
        response = ""
        
        # 의도 감지 및 응답
        if any(kw in user_message for kw in ["오늘", "할일", "작업", "뭐"]):
            tasks = self.get_today_tasks(farm_id)
            response = self._format_tasks_response(tasks)
        
        elif any(kw in user_message for kw in ["진단", "병", "증상", "문제", "왜"]):
            diagnosis = self.diagnose_disease(user_message)
            response = self._format_diagnosis_response(diagnosis)
        
        elif any(kw in user_message for kw in ["계획", "준비", "목표", "앞으로"]):
            plan = self.propose_plan(farm_id)
            response = self._format_plan_response(plan)
        
        elif any(kw in user_message for kw in ["날씨", "기상", "온도", "습도"]):
            response = self._get_weather_advice()
        
        else:
            # 기본 응답
            response = self._get_general_advice(user_message, farm_id)
        
        # 응답 저장
        self.conversation_history.append({
            "role": "assistant",
            "content": response,
            "timestamp": datetime.now().isoformat()
        })
        
        print(f"🤖 에이전트 응답:\n{response}\n")
        return response
    
    def _format_tasks_response(self, tasks: Dict) -> str:
        """작업 리스트 포맷팅"""
        lines = [f"📅 {tasks['date']} ({tasks['season']})의 추천 작업:\n"]
        
        for task in tasks["tasks"]:
            priority_emoji = "🔴" if task["priority"] == "high" else "🟠" if task["priority"] == "medium" else "🟢"
            lines.append(f"{priority_emoji} [{task['priority'].upper()}] {task['title']}")
            lines.append(f"   이유: {task['reason']}")
            lines.append(f"   설명: {task['description']}")
            lines.append("")
        
        lines.append("출처: 청도농기원, 농촌진흥청")
        return "\n".join(lines)
    
    def _format_diagnosis_response(self, diagnosis: Dict) -> str:
        """진단 결과 포맷팅"""
        if not diagnosis["results"] or diagnosis["results"][0].get("disease") == "진단 불가":
            return "🤔 증상만으로는 정확한 진단이 어렵습니다.\n청도농기원 전문가 상담(☎)을 권장합니다."
        
        lines = ["🔍 진단 결과:\n"]
        for result in diagnosis["results"]:
            lines.append(f"질병: {result['disease']} (신뢰도: {result['confidence']*100:.0f}%)")
            lines.append(f"증상: {result['symptoms']}")
            lines.append(f"원인: {result['cause']}")
            lines.append(f"치료: {result['treatment']}")
            lines.append(f"예방: {result['prevention']}")
            lines.append("")
        
        lines.append("⚠️ 정확한 진단을 위해 사진 제출 또는 현장 방문 진단을 권장합니다.")
        return "\n".join(lines)
    
    def _format_plan_response(self, plan: Dict) -> str:
        """계획 포맷팅"""
        lines = [f"📋 {plan['start_date']} ~ {plan['end_date']} 영농 계획\n"]
        lines.append(f"현재 시기: {plan['season']}")
        lines.append(f"총 작업 수: {plan['total_tasks']}개\n")
        
        lines.append("🔴 긴급 작업:")
        for task in plan["tasks_by_priority"]["high"]:
            lines.append(f"  • {task['title']}")
        
        lines.append("\n🟠 중요 작업:")
        for task in plan["tasks_by_priority"]["medium"][:3]:
            lines.append(f"  • {task['title']}")
        
        lines.append("\n✅ 성공 포인트:")
        for factor in plan["success_factors"]:
            lines.append(f"  • {factor}")
        
        return "\n".join(lines)
    
    def _get_weather_advice(self) -> str:
        """날씨 관련 조언"""
        month = datetime.now().month
        
        weather_tips = {
            (1, 2): "❄️ 겨울 동해 방지가 중요합니다. 부직포나 페인트로 보호하세요.",
            (3,): "🌱 발아기입니다. 적절한 수분 관리(주 1-2회)를 시작하세요.",
            (4,): "🌸 개화 준비 시기입니다. 개화 전 병해충 방제를 완료하세요.",
            (5, 6): "☔ 장마 시기가 다가옵니다. 배수 관리를 점검하세요.",
            (7, 8): "☀️ 고온기입니다. 충분한 관수(토양 함수량 70%)를 유지하세요.",
            (9, 10): "🍂 착색 시기입니다. 과다 관수를 피하세요.",
            (11,): "🍊 수확 시기입니다. 품질 좋은 것부터 수확하세요.",
        }
        
        for months, tip in weather_tips.items():
            if month in months:
                return tip
        
        return "🤔 계절 변화에 맞춰 관리 계획을 세우세요."
    
    def _get_general_advice(self, message: str, farm_id: str) -> str:
        """일반 조언"""
        return (
            "🌾 감잡아 AI입니다!\n\n"
            "다음과 같은 질문이 가능합니다:\n"
            "• '오늘 할 일' - 추천 작업 보기\n"
            "• '증상 설명' - 병해충 진단\n"
            "• '계획 세우기' - 영농 계획 수립\n"
            "• '날씨' - 계절 조언\n\n"
            "더 자세한 상담이 필요하면 청도농기원에 문의하세요."
        )
