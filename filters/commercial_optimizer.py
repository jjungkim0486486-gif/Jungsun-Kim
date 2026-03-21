"""
상품화 최적화 필터 & 수익성 분석
- 마진 계산
- 경쟁 강도 분석
- 틱톡/쇼피파이 최적 판매가 산출
- 최종 상품화 적합 여부 결정
"""

import math
from config import config


class CommercialOptimizer:
    """
    수익성 + 상품화 적합도 평가 (0~100점)

    평가 항목:
    1. 마진율 (30점): 최소 40% 마진 목표
    2. 가격 경쟁력 (20점): 시장 가격 대비 경쟁력
    3. ROAS 예측 (20점): 광고비 대비 수익
    4. 시장 포화도 (15점): 경쟁 상품 수
    5. 반복 구매 가능성 (15점): 소모품 여부
    """

    def optimize(self, product: dict) -> dict:
        """
        상품 수익성 분석 및 최적 가격 산출
        """
        cost = product.get("cost_usd", 0)
        if cost <= 0:
            return self._empty_result("원가 정보 없음")

        # 최적 판매가 산출
        pricing = self._calculate_optimal_pricing(cost, product)

        # 마진율 점수
        margin_score = self._score_margin(pricing["margin_pct"])

        # 가격 경쟁력 점수
        price_score = self._score_price_competitiveness(pricing["sell_price"])

        # ROAS 예측 점수
        roas_score = self._score_roas(pricing["estimated_roas"])

        # 시장 포화도 점수
        saturation_score = self._score_saturation(product)

        # 반복 구매 점수
        repeat_score = self._score_repeat_purchase(product)

        total = margin_score + price_score + roas_score + saturation_score + repeat_score

        return {
            "profit_score": round(min(100, total), 1),
            "breakdown": {
                "margin_score": round(margin_score, 1),
                "price_score": round(price_score, 1),
                "roas_score": round(roas_score, 1),
                "saturation_score": round(saturation_score, 1),
                "repeat_score": round(repeat_score, 1),
            },
            "pricing": pricing,
            "is_profitable": pricing["margin_pct"] >= config.profit.min_margin_pct,
            "recommendation": self._get_recommendation(pricing, total),
            "shopify_price": pricing["sell_price"],
            "compare_at_price": pricing["compare_price"],
        }

    def filter(self, product: dict) -> tuple[bool, str]:
        """수익성 기준 통과 여부"""
        cost = product.get("cost_usd", 0)
        if cost <= 0:
            return False, "원가 정보 없음"

        pricing = self._calculate_optimal_pricing(cost, product)

        if pricing["margin_pct"] < config.profit.min_margin_pct:
            return False, f"마진 미달: {pricing['margin_pct']:.0f}% < {config.profit.min_margin_pct:.0f}%"

        sell_price = pricing["sell_price"]
        if sell_price < config.profit.min_selling_price_usd:
            return False, f"판매가 너무 낮음: ${sell_price:.2f}"
        if sell_price > config.profit.max_selling_price_usd:
            return False, f"판매가 너무 높음: ${sell_price:.2f}"

        return True, ""

    def _calculate_optimal_pricing(self, cost: float, product: dict) -> dict:
        """최적 판매가 산출"""
        cfg = config.profit
        category = product.get("category", "general")

        # 카테고리별 일반 마크업 배수
        markup_multipliers = {
            "beauty": 4.0,
            "gadgets": 3.0,
            "fitness": 3.5,
            "home": 3.5,
            "pet": 4.0,
            "kitchen": 3.5,
            "fashion": 3.5,
            "accessories": 4.5,
            "electronics": 2.5,
        }
        multiplier = markup_multipliers.get(category, 3.5)

        # 기본 판매가
        base_price = cost * multiplier

        # 가격 범위 조정
        sell_price = max(cfg.min_selling_price_usd, min(cfg.max_selling_price_usd, base_price))

        # 심리적 가격 ($X.99)
        sell_price = _round_to_psychological_price(sell_price)

        # 배송비 포함 마진 계산
        shipping_cost = 3.5  # 평균 배송비 가정
        platform_fee = sell_price * 0.03  # 쇼피파이 3%
        payment_fee = sell_price * 0.029 + 0.30  # 결제 수수료
        ad_cost = sell_price * 0.20  # 광고비 (ROAS 5 기준 20%)
        total_cost = cost + shipping_cost + platform_fee + payment_fee

        net_profit = sell_price - total_cost
        margin_pct = (net_profit / sell_price) * 100 if sell_price > 0 else 0

        # ROAS 예측 (광고비 제외 마진 / 광고비 기준)
        estimated_roas = (sell_price - total_cost) / (sell_price * 0.20) if sell_price > 0 else 0

        # 비교 가격 (할인 표시용: 판매가의 1.4~1.6배)
        compare_price = _round_to_psychological_price(sell_price * 1.5)

        return {
            "cost_usd": round(cost, 2),
            "sell_price": round(sell_price, 2),
            "compare_price": round(compare_price, 2),
            "net_profit": round(net_profit, 2),
            "margin_pct": round(margin_pct, 1),
            "markup_multiplier": multiplier,
            "estimated_roas": round(estimated_roas, 2),
            "shipping_cost": shipping_cost,
            "ad_cost_estimate": round(ad_cost, 2),
            "total_cost_breakdown": {
                "product_cost": cost,
                "shipping": shipping_cost,
                "platform_fee": round(platform_fee, 2),
                "payment_fee": round(payment_fee, 2),
            },
        }

    def _score_margin(self, margin_pct: float) -> float:
        """마진율 점수 (0~30)"""
        if margin_pct >= 60:
            return 30
        if margin_pct >= 50:
            return 26
        if margin_pct >= 40:
            return 20
        if margin_pct >= 30:
            return 12
        return max(0, margin_pct * 0.4)

    def _score_price_competitiveness(self, sell_price: float) -> float:
        """가격 경쟁력 점수 (0~20) - TikTok 충동구매 적정 가격"""
        # 틱톡 충동구매 최적 가격대: $15-$35
        cfg = config.profit
        if 15 <= sell_price <= 35:
            return 20
        if 35 < sell_price <= 50:
            return 15
        if 10 <= sell_price < 15:
            return 12
        if 50 < sell_price <= 70:
            return 10
        return 5

    def _score_roas(self, roas: float) -> float:
        """ROAS 예측 점수 (0~20)"""
        if roas >= 4.0:
            return 20
        if roas >= 3.0:
            return 16
        if roas >= 2.0:
            return 10
        return max(0, roas * 5)

    def _score_saturation(self, product: dict) -> float:
        """시장 포화도 점수 (0~15) - 경쟁 적을수록 높음"""
        # 리뷰 수가 적당히 많으면서 너무 많지 않은 것이 블루오션
        review_count = product.get("review_count", 0)
        if 100 <= review_count <= 2000:
            return 15  # 블루오션 가능성
        if 2000 < review_count <= 10000:
            return 10  # 경쟁 있음
        if review_count > 10000:
            return 5   # 레드오션
        return 8       # 너무 새로운 상품

    def _score_repeat_purchase(self, product: dict) -> float:
        """반복 구매 가능성 점수 (0~15)"""
        title_lower = product.get("title", "").lower()
        consumable_keywords = [
            "serum", "cream", "mask", "patch", "brush", "pad",
            "strip", "capsule", "filter", "roller", "refill",
            "sheet", "sachet", "gel", "oil", "toner",
        ]
        matched = sum(1 for kw in consumable_keywords if kw in title_lower)
        return min(15, matched * 5)

    def _get_recommendation(self, pricing: dict, score: float) -> str:
        """상품화 추천 의견"""
        margin = pricing["margin_pct"]
        sell_price = pricing["sell_price"]
        roas = pricing["estimated_roas"]

        if score >= 80 and margin >= 50:
            return f"★ 강력 추천 | 마진 {margin:.0f}% | 예상 ROAS {roas:.1f}x | ${sell_price:.2f} 판매"
        if score >= 65 and margin >= 40:
            return f"✓ 추천 | 마진 {margin:.0f}% | 예상 ROAS {roas:.1f}x | ${sell_price:.2f} 판매"
        if score >= 50:
            return f"△ 조건부 추천 | 마진 {margin:.0f}% | 가격 최적화 필요"
        return f"✗ 비추천 | 마진 {margin:.0f}% 부족 또는 경쟁 과다"

    def _empty_result(self, reason: str) -> dict:
        return {
            "profit_score": 0,
            "breakdown": {},
            "pricing": {},
            "is_profitable": False,
            "recommendation": f"분석 불가: {reason}",
        }


def _round_to_psychological_price(price: float) -> float:
    """심리적 가격으로 반올림 ($X.99 형태)"""
    if price <= 9.99:
        return round(price, 0) - 0.01
    if price <= 19.99:
        return round(price / 5) * 5 - 0.01
    if price <= 49.99:
        # $24.99, $29.99, $34.99 등
        return round(price / 5) * 5 - 0.01
    return round(price / 10) * 10 - 0.01
