"""
개인정보 마스킹 함수
- 전화번호, 주민번호, 이메일 마스킹
- 규칙 기반 패턴 매칭
"""

import re


def mask_personal_data(text: str) -> str:
    """
    입력 텍스트에서 개인정보를 마스킹
    
    마스킹 대상:
    - 주민등록번호 (123456-1234567 형식) - 먼저 처리
    - 전화번호 (010-1234-5678 형식)
    - 이메일
    """
    masked = text
    
    # 1. 주민등록번호 마스킹 먼저 (123456-1234567)
    masked = re.sub(
        r'(\d{6})[-]?(\d{7})',
        r'[주민번호]',
        masked
    )
    
    # 2. 전화번호 마스킹 (010-1234-5678 또는 01012345678 등)
    masked = re.sub(
        r'0\d{1,2}[-.]?\d{3,4}[-.]?\d{4}',
        '[전화번호]',
        masked
    )
    
    # 3. 이메일 마스킹
    masked = re.sub(
        r'[\w\.-]+@[\w\.-]+\.\w+',
        '[이메일]',
        masked
    )
    
    return masked


def mask_personal_data_simple(text: str) -> str:
    """간단한 마스킹"""
    return mask_personal_data(text)


if __name__ == "__main__":
    # 테스트
    samples = [
        "안녕하세요. 전화번호는 010-1234-5678입니다.",
        "주민번호: 971234-1234567",
        "이메일: kim@example.com",
    ]
    
    for sample in samples:
        print(f"원본: {sample}")
        print(f"마스킹: {mask_personal_data(sample)}")
        print()
