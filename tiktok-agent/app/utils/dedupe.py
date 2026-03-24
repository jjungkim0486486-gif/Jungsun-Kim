"""후보 중복 제거 - product_key 기준"""
from typing import Any


def dedupe_candidates(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """product_key 기준으로 중복을 제거한다.
    동일 키가 여러 개라면 overall_score가 가장 높은 것만 남긴다.
    """
    best: dict[str, dict] = {}
    for item in items:
        key = item.get("product_key") or ""
        if not key:
            continue
        existing = best.get(key)
        if existing is None or item.get("overall_score", 0) > existing.get("overall_score", 0):
            best[key] = item
    return list(best.values())
