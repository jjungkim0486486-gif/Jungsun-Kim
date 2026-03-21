"""
Product Radar - Configuration
24h급등 + 3d반복 포착 상품 레이더 시스템
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SpikeConfig:
    """24시간 급등 감지 설정"""
    min_spike_ratio: float = 2.0       # 기준 대비 2배 이상 급등
    spike_window_hours: int = 24       # 감지 윈도우 (시간)
    min_baseline_days: int = 3         # 기준값 산출 기간 (일)
    volume_threshold: int = 100        # 최소 검색/판매량 기준값


@dataclass
class RepeatConfig:
    """3일 반복 포착 설정"""
    repeat_days: int = 3               # 반복 감지 기간 (일)
    min_daily_score: float = 60.0      # 일일 최소 트렌드 점수
    consistency_threshold: float = 0.7 # 일관성 임계값 (0~1)


@dataclass
class QualityConfig:
    """상품 품질 필터 설정"""
    min_rating: float = 4.0            # 최소 평점
    min_reviews: int = 50              # 최소 리뷰 수
    max_defect_rate: float = 0.03      # 최대 불량률 (3%)
    min_supplier_score: float = 4.5    # 최소 공급업체 점수
    preferred_suppliers: list = field(default_factory=lambda: [
        "AliExpress", "CJ Dropshipping", "Spocket", "Zendrop"
    ])


@dataclass
class ShippingConfig:
    """배송 설정"""
    max_delivery_days: int = 7         # 최대 배송일
    preferred_warehouses: list = field(default_factory=lambda: [
        "US", "CN-ePacket", "EU"
    ])
    max_shipping_cost_usd: float = 5.0 # 최대 배송비 ($)
    require_tracking: bool = True      # 추적번호 필수


@dataclass
class ProfitConfig:
    """수익성 설정"""
    min_margin_pct: float = 40.0       # 최소 마진율 (%)
    min_selling_price_usd: float = 15.0  # 최소 판매가 ($)
    max_selling_price_usd: float = 80.0  # 최대 판매가 ($)
    target_roas: float = 3.0           # 목표 ROAS
    max_cost_per_order_usd: float = 25.0 # 최대 원가 ($)


@dataclass
class ViralConfig:
    """바이럴 가능성 설정"""
    min_tiktok_hashtag_views: int = 1_000_000  # 최소 틱톡 해시태그 조회수
    min_video_engagement_rate: float = 0.05    # 최소 영상 참여율 (5%)
    min_ugc_count: int = 10                    # 최소 UGC 영상 수
    trending_keywords_boost: float = 1.5       # 트렌딩 키워드 가중치


@dataclass
class RadarConfig:
    """전체 레이더 설정"""
    # 스코어 가중치 (합계 = 100)
    weight_viral: float = 30.0
    weight_trend: float = 25.0
    weight_profit: float = 20.0
    weight_quality: float = 15.0
    weight_shipping: float = 10.0

    # 최소 종합 점수 (100점 만점)
    min_total_score: float = 65.0

    # 결과 설정
    top_products_count: int = 20       # 최상위 상품 수

    # 스캔 간격
    scan_interval_hours: int = 6       # 스캔 주기 (시간)

    # API Keys (환경변수에서 로드)
    aliexpress_app_key: str = field(default_factory=lambda: os.getenv("ALIEXPRESS_APP_KEY", ""))
    aliexpress_app_secret: str = field(default_factory=lambda: os.getenv("ALIEXPRESS_APP_SECRET", ""))
    tiktok_access_token: str = field(default_factory=lambda: os.getenv("TIKTOK_ACCESS_TOKEN", ""))
    shopify_store_url: str = field(default_factory=lambda: os.getenv("SHOPIFY_STORE_URL", ""))
    shopify_access_token: str = field(default_factory=lambda: os.getenv("SHOPIFY_ACCESS_TOKEN", ""))

    spike: SpikeConfig = field(default_factory=SpikeConfig)
    repeat: RepeatConfig = field(default_factory=RepeatConfig)
    quality: QualityConfig = field(default_factory=QualityConfig)
    shipping: ShippingConfig = field(default_factory=ShippingConfig)
    profit: ProfitConfig = field(default_factory=ProfitConfig)
    viral: ViralConfig = field(default_factory=ViralConfig)


# 카테고리별 틱톡 바이럴 적합도 (높을수록 틱톡에서 잘 팜)
TIKTOK_CATEGORY_SCORES = {
    "beauty": 95,
    "skincare": 92,
    "gadgets": 90,
    "fitness": 88,
    "fashion": 87,
    "home_decor": 82,
    "kitchen": 80,
    "pet": 85,
    "baby": 78,
    "accessories": 83,
    "electronics": 75,
    "sports": 80,
    "toys": 77,
    "health": 86,
    "lifestyle": 84,
}

# 상품 블랙리스트 키워드 (판매 금지 또는 위험 카테고리)
BLACKLIST_KEYWORDS = [
    "weapon", "gun", "knife", "drug", "medical device", "prescription",
    "counterfeit", "replica", "fake", "adult", "tobacco", "alcohol",
    "copyright", "trademark",
]

# 빠른 배송 가능 플랫폼 목록
FAST_SHIPPING_PLATFORMS = {
    "CJ Dropshipping": 5,
    "Zendrop": 5,
    "Spocket US": 3,
    "Spocket EU": 5,
    "AliExpress US Warehouse": 4,
    "AliExpress ePacket": 7,
    "DSers": 6,
    "AutoDS": 5,
}

# 글로벌 설정 인스턴스
config = RadarConfig()

# 빠른 배송 가능 카테고리 (AliExpress 카테고리 ID 매핑)
FAST_SHIP_CATEGORIES = {
    "beauty": "66",
    "gadgets": "44",
    "home": "13",
    "fashion": "200000343",
    "fitness": "200001087",
    "pet": "200001077",
    "kitchen": "200000220",
    "baby": "200000345",
}
