"""
바이럴 가능성 스코어러
TikTok + 소셜 미디어 바이럴 잠재력 평가
"""

from config import config, TIKTOK_CATEGORY_SCORES


class ViralScorer:
    """
    바이럴 가능성 종합 평가 (0~100점)

    평가 항목:
    1. TikTok 해시태그 조회수 (25점)
    2. UGC 영상 수 및 참여율 (20점)
    3. 카테고리 TikTok 적합도 (15점)
    4. 상품 "wow factor" (시각적 임팩트) (20점)
    5. 문제-해결형 상품 여부 (20점)
    """

    WOW_KEYWORDS = [
        "viral", "satisfying", "amazing", "incredible", "magic",
        "instant", "before after", "transformation", "glow", "hack",
        "dupe", "game changer", "asmr", "oddly", "aesthetic",
    ]

    PROBLEM_SOLVING_KEYWORDS = [
        "remov", "clean", "fix", "repair", "relief", "ease",
        "boost", "improve", "protect", "prevent", "treat",
        "plump", "lift", "slim", "tone", "whiten", "brighten",
    ]

    def score(self, product: dict, trend_data: dict) -> dict:
        """
        상품 바이럴 점수 산출
        Args:
            product: 상품 기본 데이터
            trend_data: TrendAnalyzer.analyze() 결과
        Returns:
            viral scoring result dict
        """
        tiktok_signal = trend_data.get("tiktok_signal", {})
        category = product.get("category", "general")
        title = product.get("title", "")

        # 1. TikTok 해시태그 점수 (25점)
        hashtag_score = self._score_hashtags(tiktok_signal)

        # 2. UGC 참여 점수 (20점)
        ugc_score = self._score_ugc(tiktok_signal)

        # 3. 카테고리 적합도 (15점)
        category_score = self._score_category(category)

        # 4. Wow Factor (20점)
        wow_score = self._score_wow_factor(title, product)

        # 5. 문제 해결형 (20점)
        problem_score = self._score_problem_solving(title)

        total = hashtag_score + ugc_score + category_score + wow_score + problem_score

        return {
            "viral_score": round(min(100, total), 1),
            "breakdown": {
                "hashtag_score": round(hashtag_score, 1),
                "ugc_score": round(ugc_score, 1),
                "category_score": round(category_score, 1),
                "wow_score": round(wow_score, 1),
                "problem_score": round(problem_score, 1),
            },
            "viral_grade": _get_grade(total),
            "tiktok_fit": TIKTOK_CATEGORY_SCORES.get(category, 70),
            "recommended_hooks": self._get_content_hooks(title, category),
        }

    def _score_hashtags(self, tiktok_signal: dict) -> float:
        """TikTok 해시태그 조회수 기반 점수 (0~25)"""
        views_m = tiktok_signal.get("hashtag_views_m", 0)
        cfg = config.viral
        threshold_m = cfg.min_tiktok_hashtag_views / 1_000_000

        if views_m <= 0:
            return 0
        if views_m >= threshold_m * 50:  # 5천만 이상
            return 25
        ratio = views_m / threshold_m
        return min(25, ratio * 5)

    def _score_ugc(self, tiktok_signal: dict) -> float:
        """UGC 영상 수 + 참여율 점수 (0~20)"""
        video_count = tiktok_signal.get("video_count", 0)
        eng_rate = tiktok_signal.get("engagement_rate_pct", 0) / 100

        # 영상 수 점수 (0~12)
        video_score = min(12, (video_count / 1000) * 1.2)

        # 참여율 점수 (0~8): 5% = 8점
        eng_score = min(8, (eng_rate / config.viral.min_video_engagement_rate) * 8)

        return video_score + eng_score

    def _score_category(self, category: str) -> float:
        """카테고리 TikTok 적합도 (0~15)"""
        tiktok_fit = TIKTOK_CATEGORY_SCORES.get(category, 70)
        return (tiktok_fit / 100) * 15

    def _score_wow_factor(self, title: str, product: dict) -> float:
        """시각적 임팩트 및 Wow Factor (0~20)"""
        title_lower = title.lower()
        score = 0

        # Wow 키워드 보너스
        matched = sum(1 for kw in self.WOW_KEYWORDS if kw in title_lower)
        score += min(12, matched * 4)

        # 영상 참여율이 높으면 시각적으로 좋은 상품 (추가 점수)
        engagement = product.get("engagement_rate", 0)
        if engagement >= 0.08:
            score += 5
        elif engagement >= 0.05:
            score += 3

        # 트렌드 속도 기반 (바이럴 중이면 보너스)
        velocity = product.get("trend_velocity", 0)
        if velocity >= 4.0:
            score += 3
        elif velocity >= 2.5:
            score += 1

        return min(20, score)

    def _score_problem_solving(self, title: str) -> float:
        """문제 해결형 상품 점수 (0~20) - TikTok에서 잘 팔림"""
        title_lower = title.lower()
        matched = sum(1 for kw in self.PROBLEM_SOLVING_KEYWORDS if kw in title_lower)
        return min(20, matched * 7)

    def _get_content_hooks(self, title: str, category: str) -> list[str]:
        """TikTok 콘텐츠 훅 추천"""
        hooks = {
            "beauty": [
                f"POV: This {title.split()[0]} changed my skin...",
                f"Skincare girlies, you NEED to see this 😱",
                f"I tried this for 7 days and...",
            ],
            "gadgets": [
                f"You've been doing it wrong 😳 This {title.split()[0]}...",
                f"The gadget I didn't know I needed...",
                f"Amazon sent me this and I'm obsessed 📦",
            ],
            "fitness": [
                f"This {title.split()[0]} is going VIRAL for a reason...",
                f"POV: Your home gym just got an upgrade 💪",
                f"The workout hack everyone's talking about...",
            ],
            "home": [
                f"This home hack will save you HOURS ⏰",
                f"I cleaned my entire house with THIS...",
                f"Amazon find that broke the internet 🔥",
            ],
            "pet": [
                f"My dog's reaction to this is EVERYTHING 🐶",
                f"Pet parents, you NEED this...",
                f"This went viral for a reason 🐾",
            ],
        }
        return hooks.get(category, [
            f"This product changed everything...",
            f"You need to see this 😱",
            f"TikTok made me buy it and I'm not mad 🔥",
        ])


def _get_grade(score: float) -> str:
    """점수를 등급으로 변환"""
    if score >= 85:
        return "S"   # 슈퍼 바이럴
    if score >= 70:
        return "A"   # 강한 바이럴 가능성
    if score >= 55:
        return "B"   # 보통 바이럴 가능성
    if score >= 40:
        return "C"   # 낮은 바이럴 가능성
    return "D"       # 바이럴 부적합
