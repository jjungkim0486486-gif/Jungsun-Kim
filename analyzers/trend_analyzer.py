"""
트렌드 분석기 - 핵심 엔진
24h 급등 + 3d 반복 포착 알고리즘
"""

from datetime import datetime, timedelta
from typing import Optional
import statistics

from config import config, SpikeConfig, RepeatConfig
from storage.database import (
    get_recent_snapshots,
    get_daily_scores,
    insert_snapshot,
)
from scrapers.google_trends_scraper import (
    detect_24h_spike,
    get_3day_trend_consistency,
)
from scrapers.tiktok_scraper import fetch_hashtag_trend


class TrendAnalyzer:
    """
    24h급등 + 3d반복 포착 분석기

    알고리즘:
    1. 24h Spike Detection
       - 최근 24h 평균 vs 이전 기준선(3~7일 평균) 비교
       - spike_ratio >= 2.0 → 급등 확정
       - TikTok 영상 수 급증 + Google Trends 급등 → 복합 시그널

    2. 3d Repeat Detection
       - 3일 연속으로 트렌드 점수가 임계값 이상
       - 단순 일시적 스파이크 vs 지속적 트렌드 구분
       - 3일 모두 >= min_daily_score → 진성 트렌드

    3. 복합 점수 산출
       - spike_ratio * consistency * recency_bonus
    """

    def __init__(
        self,
        spike_config: Optional[SpikeConfig] = None,
        repeat_config: Optional[RepeatConfig] = None,
    ):
        self.spike_cfg = spike_config or config.spike
        self.repeat_cfg = repeat_config or config.repeat

    def analyze(self, product: dict) -> dict:
        """
        상품 트렌드 전체 분석
        Returns: trend analysis result dict
        """
        product_id = product["product_id"]
        keyword = product.get("search_keyword") or _extract_keyword(product["title"])
        category = product.get("category", "general")

        # 1. Google Trends 24h 급등 감지
        spike_result = self._detect_spike(keyword, product)

        # 2. 3일 반복 포착
        repeat_result = self._detect_repeat(keyword, product_id)

        # 3. TikTok 트렌드 신호
        tiktok_signal = self._analyze_tiktok_signal(product)

        # 4. 최종 트렌드 점수
        trend_score = self._calculate_trend_score(
            spike_result, repeat_result, tiktok_signal
        )

        # 스냅샷 저장
        insert_snapshot(product_id, {
            "search_volume": int(spike_result.get("recent_avg", 0)),
            "sales_count": product.get("sales_30d", 0),
            "tiktok_views": product.get("tiktok_hashtag_views", 0),
            "tiktok_videos": product.get("tiktok_video_count", 0),
            "viral_score": tiktok_signal.get("viral_score", 0),
            "trend_score": trend_score,
        })

        return {
            "product_id": product_id,
            "keyword": keyword,
            "trend_score": round(trend_score, 1),
            "is_24h_spike": spike_result["is_spike"],
            "spike_ratio": spike_result.get("spike_ratio", 0),
            "is_3d_repeat": repeat_result["is_consistent"],
            "repeat_days": repeat_result.get("days_above_threshold", 0),
            "consistency_score": repeat_result.get("consistency_score", 0),
            "tiktok_signal": tiktok_signal,
            "spike_detail": spike_result,
            "repeat_detail": repeat_result,
            "analyzed_at": datetime.utcnow().isoformat(),
        }

    def _detect_spike(self, keyword: str, product: dict) -> dict:
        """24시간 급등 감지"""
        # Google Trends 스파이크
        google_spike = detect_24h_spike(
            keyword,
            spike_threshold=self.spike_cfg.min_spike_ratio,
        )

        # TikTok 기반 스파이크 보강
        tiktok_spike = _detect_tiktok_spike(product)

        # 복합 판단: Google OR TikTok 중 하나라도 급등 시 급등 확정
        is_spike = google_spike["is_spike"] or tiktok_spike["is_spike"]
        spike_ratio = max(
            google_spike.get("spike_ratio", 0),
            tiktok_spike.get("spike_ratio", 0),
        )

        return {
            "is_spike": is_spike,
            "spike_ratio": round(spike_ratio, 2),
            "source": "combined",
            "google_spike": google_spike,
            "tiktok_spike": tiktok_spike,
            "recent_avg": google_spike.get("recent_avg", 0),
            "baseline_avg": google_spike.get("baseline_avg", 0),
        }

    def _detect_repeat(self, keyword: str, product_id: str) -> dict:
        """3일 반복 트렌드 감지"""
        # Google Trends 3일 일관성
        google_repeat = get_3day_trend_consistency(
            keyword,
            min_daily_value=int(self.repeat_cfg.min_daily_score),
        )

        # DB 이력에서 3일 점수 확인
        db_history = get_daily_scores(product_id, days=3)
        db_days_above = sum(
            1 for d in db_history
            if d.get("avg_score", 0) >= self.repeat_cfg.min_daily_score
        )

        # 복합 판단
        days_above = max(google_repeat.get("days_above_threshold", 0), db_days_above)
        is_consistent = days_above >= self.repeat_cfg.repeat_days
        consistency_score = days_above / self.repeat_cfg.repeat_days

        return {
            "is_consistent": is_consistent,
            "days_above_threshold": days_above,
            "consistency_score": min(1.0, consistency_score),
            "google_data": google_repeat,
            "db_history_days": len(db_history),
        }

    def _analyze_tiktok_signal(self, product: dict) -> dict:
        """TikTok 바이럴 시그널 분석"""
        hashtag_views = product.get("tiktok_hashtag_views", 0)
        video_count = product.get("tiktok_video_count", 0)
        engagement = product.get("engagement_rate", 0)
        trend_velocity = product.get("trend_velocity", 0)

        # 해시태그 조회수 점수 (0~40)
        view_score = min(40, (hashtag_views / 1_000_000) * 2)

        # 영상 수 점수 (0~20)
        video_score = min(20, (video_count / 10_000) * 20)

        # 참여율 점수 (0~20) - 5% 이상이면 만점
        eng_score = min(20, (engagement / 0.05) * 20)

        # 트렌드 속도 점수 (0~20)
        velocity_score = min(20, trend_velocity * 4)

        viral_score = view_score + video_score + eng_score + velocity_score

        return {
            "viral_score": round(viral_score, 1),
            "view_score": round(view_score, 1),
            "video_score": round(video_score, 1),
            "engagement_score": round(eng_score, 1),
            "velocity_score": round(velocity_score, 1),
            "hashtag_views_m": round(hashtag_views / 1_000_000, 1),
            "video_count": video_count,
            "engagement_rate_pct": round(engagement * 100, 1),
        }

    def _calculate_trend_score(
        self,
        spike: dict,
        repeat: dict,
        tiktok: dict,
    ) -> float:
        """
        최종 트렌드 점수 산출 (0~100)

        구성:
        - 24h 스파이크 (30점): 급등 여부 + 급등 강도
        - 3d 반복성 (30점): 일관성 * 반복 일수
        - TikTok 바이럴 (40점): viral_score 정규화
        """
        # 24h 스파이크 점수
        if spike["is_spike"]:
            spike_score = min(30, 15 + spike["spike_ratio"] * 5)
        else:
            spike_score = min(15, spike["spike_ratio"] * 5)

        # 3d 반복성 점수
        repeat_score = min(30, repeat["consistency_score"] * 30)
        if repeat["is_consistent"]:
            repeat_score = max(repeat_score, 25)  # 3일 반복 확정 시 최소 25점

        # TikTok 바이럴 점수 (viral_score는 이미 0~100 범위)
        tiktok_score = tiktok["viral_score"] * 0.4  # 40점 만점으로 변환

        total = spike_score + repeat_score + tiktok_score
        return min(100, total)


def _extract_keyword(title: str) -> str:
    """상품 제목에서 핵심 검색 키워드 추출"""
    # 불용어 제거
    stop_words = {
        "the", "a", "an", "and", "or", "for", "with", "in", "of",
        "to", "is", "set", "pack", "piece", "pcs", "lot",
    }
    words = title.lower().split()
    keywords = [w for w in words if w not in stop_words and len(w) > 2]
    # 앞 3-4개 단어가 핵심 키워드
    return " ".join(keywords[:4])


def _detect_tiktok_spike(product: dict) -> dict:
    """TikTok 기반 24h 스파이크 감지"""
    spike_24h = product.get("spike_24h", 0)
    is_trending_up = product.get("is_trending_up", False)
    trend_velocity = product.get("trend_velocity", 0)

    # spike_24h > 0 이고 trending_up이면 스파이크
    is_spike = (spike_24h >= config.spike.min_spike_ratio) or (
        is_trending_up and trend_velocity >= 3.0
    )

    spike_ratio = max(spike_24h, trend_velocity / 2) if is_spike else spike_24h

    return {
        "is_spike": is_spike,
        "spike_ratio": round(spike_ratio, 2),
        "trend_velocity": trend_velocity,
        "is_trending_up": is_trending_up,
    }
