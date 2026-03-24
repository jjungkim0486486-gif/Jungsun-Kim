"""상품 키 정규화 - 중복 비교 기준 문자열 생성"""
import re


def make_product_key(title: str) -> str:
    """제목에서 URL-safe 슬러그 생성 (최대 6단어).

    예: 'Amazing LED Desk Lamp 2024 USB' → 'amazing-led-desk-lamp-2024-usb'
    """
    text = (title or "").lower()
    # 특수문자 제거, 공백 정규화
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    words = text.split()[:6]
    return "-".join(words) if words else "unknown"
