"""
토큰 기반 단계 강제 (청도 팀 구현 참고)
- 마스킹 단계 필수 완료
- 토큰 서명으로 조작 방지
- 1시간 만료 정책
"""

import hmac
import hashlib
from datetime import datetime


class TokenGate:
    """토큰 기반 단계 강제 게이트"""
    
    def __init__(self, secret: str = "default-secret"):
        self.secret = secret.encode()
    
    def text_hash(self, text: str) -> str:
        """텍스트의 MD5 해시 (체크섬)"""
        return hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()
    
    def sign_token(self, step: str, text_hash: str) -> str:
        """토큰 생성
        
        형식: {step}:{text_hash}:{timestamp}:{signature}
        예: mask:abc123:1699190400:xyz789
        """
        timestamp = str(int(datetime.now().timestamp()))
        data = f"{step}:{text_hash}:{timestamp}"
        signature = hmac.new(self.secret, data.encode(), hashlib.sha256).hexdigest()
        return f"{data}:{signature}"
    
    def verify_token(self, token: str, expected_step: str, expected_hash: str) -> bool:
        """토큰 검증
        
        Args:
            token: 검증할 토큰
            expected_step: 예상 단계 (예: "mask")
            expected_hash: 예상 해시값
        
        Returns:
            True if 토큰이 유효하고, 만료되지 않았고, 해시가 일치하면
        """
        try:
            # 토큰 파싱
            parts = token.rsplit(":", 1)  # 마지막 ':'로 분리 (signature)
            if len(parts) != 2:
                return False
            
            data_part, signature = parts
            
            # 서명 검증
            expected_signature = hmac.new(
                self.secret, 
                data_part.encode(), 
                hashlib.sha256
            ).hexdigest()
            
            if not hmac.compare_digest(signature, expected_signature):
                return False
            
            # 데이터 파싱: "step:hash:timestamp"
            data_parts = data_part.split(":")
            if len(data_parts) != 3:
                return False
            
            step, text_hash, timestamp_str = data_parts
            
            # 단계 검증
            if step != expected_step:
                return False
            
            # 해시 검증
            if text_hash != expected_hash:
                return False
            
            # 만료 검증 (1시간 = 3600초)
            try:
                timestamp = int(timestamp_str)
                current_time = int(datetime.now().timestamp())
                if current_time - timestamp > 3600:
                    return False
            except ValueError:
                return False
            
            return True
        
        except Exception:
            return False
    
    def create_mask_token(self, masked_text: str) -> str:
        """마스킹 토큰 생성"""
        return self.sign_token("mask", self.text_hash(masked_text))
    
    def verify_mask_token(self, token: str, masked_text: str) -> bool:
        """마스킹 토큰 검증"""
        return self.verify_token(token, "mask", self.text_hash(masked_text))
    
    def create_chat_token(self, masked_text: str, farm_id: str) -> str:
        """채팅 토큰 생성"""
        combined = f"{masked_text}:{farm_id}"
        return self.sign_token("chat", self.text_hash(combined))
    
    def verify_chat_token(self, token: str, masked_text: str, farm_id: str) -> bool:
        """채팅 토큰 검증"""
        combined = f"{masked_text}:{farm_id}"
        return self.verify_token(token, "chat", self.text_hash(combined))


# 전역 인스턴스 (나중에 main.py에서 초기화)
gate: TokenGate = None


def initialize_gate(secret: str = None) -> TokenGate:
    """토큰 게이트 초기화"""
    global gate
    import os
    gate = TokenGate(secret or os.getenv("SIGNING_KEY", "default-secret"))
    return gate
