"""도구 권한 관리 - 허용된 도구만 실행 가능하도록 제한"""

from enum import Enum
from typing import Set, Optional
from datetime import datetime


class ToolPermission(Enum):
    """허용된 도구 목록"""
    # 정보 조회
    GET_WEATHER = "get_weather_info"
    GET_SOIL_CONDITION = "get_soil_condition"
    GET_DISEASE_DATA = "get_disease_data"
    GET_PEST_INFO = "get_pest_info"
    
    # 추천 도구
    RECOMMEND_FERTILIZER = "recommend_fertilizer"
    RECOMMEND_IRRIGATION = "recommend_irrigation"
    RECOMMEND_PESTICIDE = "recommend_pesticide"
    RECOMMEND_HARVEST_TIME = "recommend_harvest_time"
    
    # 기타
    CALCULATE_YIELD = "calculate_yield"


class ToolPermissionManager:
    """도구 권한 검증 및 로깅"""
    
    def __init__(self):
        self.whitelist: Set[str] = {perm.value for perm in ToolPermission}
        self.denied_attempts: list = []
    
    def is_allowed(self, tool_name: str) -> bool:
        """도구 사용 가능 여부 확인"""
        return tool_name in self.whitelist
    
    def check_tool(self, tool_name: str, farm_id: str, user_input: str) -> Optional[str]:
        """
        도구 사용 가능 여부 확인 및 로깅
        
        Args:
            tool_name: 요청된 도구명
            farm_id: 농장 ID
            user_input: 사용자 입력
            
        Returns:
            None (허용) 또는 에러 메시지 (거부)
        """
        if self.is_allowed(tool_name):
            return None  # ✅ 허용
        
        # ❌ 거부: 로깅
        self.denied_attempts.append({
            "timestamp": datetime.now().isoformat(),
            "farm_id": farm_id,
            "tool_name": tool_name,
            "user_input": user_input[:100],  # 첫 100글자만
        })
        
        return f"❌ 이 도구는 사용할 수 없습니다: {tool_name}. 허용된 도구: {', '.join(sorted(self.whitelist))}"
    
    def get_allowed_tools(self) -> list:
        """허용된 모든 도구 반환"""
        return sorted(list(self.whitelist))
    
    def get_denied_attempts(self, limit: int = 10) -> list:
        """거부된 시도 로그 반환 (최근 limit개)"""
        return self.denied_attempts[-limit:]


# 전역 매니저 인스턴스
permission_manager = ToolPermissionManager()
