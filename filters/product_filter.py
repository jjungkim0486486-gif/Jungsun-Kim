"""
상품 품질 + 배송 필터
- 상품 품질: 평점, 리뷰 수, 불량률
- 배송: 7일 이내 도착 가능 여부
- 블랙리스트 키워드 필터
"""

from config import config, BLACKLIST_KEYWORDS, FAST_SHIPPING_PLATFORMS


class ProductQualityFilter:
    """
    상품 품질 필터 및 점수 산출 (0~100)

    평가 기준:
    - 평점: 4.0+ (엄격: 4.5+)
    - 리뷰 수: 50개 이상
    - 공급업체 신뢰도
    - 불량률/반품률
    """

    def filter(self, product: dict) -> tuple[bool, str]:
        """
        상품이 품질 기준을 통과하는지 검사
        Returns: (통과 여부, 실패 이유)
        """
        cfg = config.quality

        # 블랙리스트 키워드 검사
        title_lower = product.get("title", "").lower()
        for kw in BLACKLIST_KEYWORDS:
            if kw in title_lower:
                return False, f"블랙리스트 키워드: '{kw}'"

        # 평점 검사
        rating = product.get("rating", 0)
        if rating < cfg.min_rating:
            return False, f"평점 미달: {rating:.1f} < {cfg.min_rating}"

        # 리뷰 수 검사
        review_count = product.get("review_count", 0)
        if review_count < cfg.min_reviews:
            return False, f"리뷰 부족: {review_count} < {cfg.min_reviews}개"

        return True, ""

    def score(self, product: dict) -> dict:
        """
        상품 품질 점수 산출 (0~100)

        구성:
        - 평점 점수 (35점)
        - 리뷰 수 점수 (30점)
        - 공급업체 신뢰도 (20점)
        - 상품 일관성 (15점)
        """
        rating = product.get("rating", 0)
        review_count = product.get("review_count", 0)
        supplier = product.get("supplier", "")

        # 평점 점수 (35점): 4.0=20점, 4.5=30점, 5.0=35점
        if rating >= 5.0:
            rating_score = 35
        elif rating >= 4.5:
            rating_score = 30 + (rating - 4.5) * 10
        elif rating >= 4.0:
            rating_score = 20 + (rating - 4.0) * 20
        else:
            rating_score = rating * 5

        # 리뷰 수 점수 (30점): 로그 스케일
        import math
        if review_count >= 5000:
            review_score = 30
        elif review_count >= 100:
            review_score = min(30, math.log10(review_count) * 12)
        else:
            review_score = min(15, review_count / 10)

        # 공급업체 신뢰도 (20점)
        supplier_score = _get_supplier_trust_score(supplier)

        # 상품 일관성 점수 (15점): 제목 길이, 이미지 존재 여부
        consistency_score = 0
        if product.get("image_url"):
            consistency_score += 8
        if 10 < len(product.get("title", "")) < 100:
            consistency_score += 7

        total = rating_score + review_score + supplier_score + consistency_score

        return {
            "quality_score": round(min(100, total), 1),
            "breakdown": {
                "rating_score": round(rating_score, 1),
                "review_score": round(review_score, 1),
                "supplier_score": round(supplier_score, 1),
                "consistency_score": round(consistency_score, 1),
            },
            "rating": rating,
            "review_count": review_count,
            "supplier": supplier,
            "quality_grade": _get_grade(total),
        }


class ShippingFilter:
    """
    배송 필터 - 7일 이내 배송 가능 여부 판단
    """

    def filter(self, product: dict) -> tuple[bool, str]:
        """
        배송 조건 통과 여부 검사
        """
        cfg = config.shipping
        shipping_days = product.get("shipping_days", 999)

        if shipping_days > cfg.max_delivery_days:
            return False, f"배송 초과: {shipping_days}일 > {cfg.max_delivery_days}일"

        # 알 수 없는 배송일 (None 또는 0)
        if not shipping_days or shipping_days <= 0:
            return False, "배송일 정보 없음"

        return True, ""

    def score(self, product: dict) -> dict:
        """
        배송 점수 산출 (0~100)

        구성:
        - 배송 속도 (60점): 7일=60점, 5일=80점, 3일=100점
        - 추적 가능 여부 (20점)
        - 배송비 (20점)
        """
        shipping_days = product.get("shipping_days", 14)
        supplier = product.get("supplier", "")

        # 배송 속도 점수
        if shipping_days <= 3:
            speed_score = 60
        elif shipping_days <= 5:
            speed_score = 50
        elif shipping_days <= 7:
            speed_score = 40
        elif shipping_days <= 10:
            speed_score = 25
        else:
            speed_score = 10

        # 추적 가능 여부 (플랫폼 기반)
        tracking_score = 20 if _supports_tracking(supplier) else 10

        # 배송비 점수 (가정: 빠른 배송 플랫폼은 합리적인 배송비)
        shipping_cost_score = 20 if supplier in FAST_SHIPPING_PLATFORMS else 10

        total = speed_score + tracking_score + shipping_cost_score

        return {
            "shipping_score": round(min(100, total), 1),
            "breakdown": {
                "speed_score": round(speed_score, 1),
                "tracking_score": round(tracking_score, 1),
                "cost_score": round(shipping_cost_score, 1),
            },
            "shipping_days": shipping_days,
            "supplier": supplier,
            "has_tracking": _supports_tracking(supplier),
            "estimated_delivery": f"{shipping_days}일 이내",
        }


def _get_supplier_trust_score(supplier: str) -> float:
    """공급업체 신뢰도 점수 (0~20)"""
    trust_scores = {
        "CJ Dropshipping": 19,
        "Zendrop": 18,
        "Spocket": 18,
        "Spocket US": 19,
        "AutoDS": 17,
        "DSers": 16,
        "AliExpress": 14,
        "aliexpress": 14,
        "AliExpress US Warehouse": 17,
    }
    # 부분 일치 검색
    supplier_lower = supplier.lower()
    for key, score in trust_scores.items():
        if key.lower() in supplier_lower:
            return score
    return 12  # 알 수 없는 공급업체 기본값


def _supports_tracking(supplier: str) -> bool:
    """추적번호 지원 여부"""
    tracked_suppliers = {
        "cj dropshipping", "zendrop", "spocket",
        "autods", "dsers", "aliexpress",
    }
    return any(s in supplier.lower() for s in tracked_suppliers)


def _get_grade(score: float) -> str:
    if score >= 85:
        return "A+"
    if score >= 70:
        return "A"
    if score >= 55:
        return "B"
    if score >= 40:
        return "C"
    return "D"
