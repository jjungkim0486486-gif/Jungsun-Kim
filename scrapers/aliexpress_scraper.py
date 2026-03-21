"""
AliExpress 상품 스크래퍼
- 인기 상품, 신상품, 빠른 배송 상품 수집
- AliExpress Affiliate API + 공개 데이터 활용
"""

import time
import random
import hashlib
import hmac
import json
import requests
from datetime import datetime
from typing import Optional
from urllib.parse import urlencode

from config import config, BLACKLIST_KEYWORDS


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "application/json, text/plain, */*",
}

# 빠른 배송 카테고리 ID (AliExpress)
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


def _make_api_signature(params: dict, secret: str) -> str:
    """AliExpress API HMAC-MD5 서명 생성"""
    sorted_params = "".join(f"{k}{v}" for k, v in sorted(params.items()))
    return hmac.new(
        secret.encode(), sorted_params.encode(), hashlib.md5
    ).hexdigest().upper()


def fetch_aliexpress_hot_products(
    category: str = "beauty",
    page: int = 1,
    page_size: int = 40,
    min_rating: float = 4.0,
    max_ship_days: int = 7,
) -> list[dict]:
    """
    AliExpress 인기 상품 수집
    API 키가 있으면 공식 API, 없으면 공개 엔드포인트 사용
    """
    if config.aliexpress_app_key:
        return _fetch_via_api(category, page, page_size, min_rating, max_ship_days)
    return _fetch_via_public(category, page, page_size, min_rating, max_ship_days)


def _fetch_via_api(
    category: str, page: int, page_size: int,
    min_rating: float, max_ship_days: int
) -> list[dict]:
    """AliExpress Affiliate API v2 호출"""
    base_url = "https://api-sg.aliexpress.com/sync"
    cat_id = FAST_SHIP_CATEGORIES.get(category, "66")

    params = {
        "method": "aliexpress.affiliate.hotproduct.query",
        "app_key": config.aliexpress_app_key,
        "sign_method": "hmac",
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "format": "json",
        "v": "2.0",
        "category_ids": cat_id,
        "page_no": str(page),
        "page_size": str(page_size),
        "sort": "LAST_VOLUME_DESC",
        "ship_to_country": "US",
        "delivery_days": str(max_ship_days),
        "min_comm_rate": "0",
        "fields": "product_id,product_title,product_main_image_url,"
                  "target_original_price,target_sale_price,evaluate_rate,"
                  "lastest_volume,logistics_desc,store_id,store_info",
    }
    params["sign"] = _make_api_signature(params, config.aliexpress_app_secret)

    try:
        resp = requests.get(base_url, params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        raw_products = (
            data.get("aliexpress_affiliate_hotproduct_query_response", {})
            .get("resp_result", {})
            .get("result", {})
            .get("products", {})
            .get("product", [])
        )
        return [_normalize_api_product(p, category) for p in raw_products
                if _passes_basic_filter(p.get("product_title", ""), float(p.get("evaluate_rate", 0)))]
    except Exception as e:
        print(f"[AliExpress API Error] {e}")
        return []


def _fetch_via_public(
    category: str, page: int, page_size: int,
    min_rating: float, max_ship_days: int
) -> list[dict]:
    """
    공개 AliExpress 데이터 수집 (API 키 없을 때)
    실제 운영 시에는 API 키 발급 권장
    """
    # 실제 스크래핑 대신 시뮬레이션 데이터 반환 (데모/테스트용)
    # 실제 구현 시: Playwright/Selenium 또는 AliExpress Affiliate API 사용
    sample_products = _generate_sample_products(category, page_size)
    return [p for p in sample_products
            if p["rating"] >= min_rating
            and p["shipping_days"] <= max_ship_days
            and _passes_basic_filter(p["title"], p["rating"])]


def _normalize_api_product(raw: dict, category: str) -> dict:
    """API 응답 -> 표준 상품 딕셔너리 변환"""
    try:
        cost = float(raw.get("target_sale_price", "0").replace("US $", "").strip())
        original = float(raw.get("target_original_price", "0").replace("US $", "").strip())
        rating = float(raw.get("evaluate_rate", "0").replace("%", "")) / 20  # 100% -> 5점
        sales = int(raw.get("lastest_volume", 0))
    except (ValueError, AttributeError):
        cost, original, rating, sales = 0.0, 0.0, 0.0, 0

    return {
        "product_id": f"ae_{raw.get('product_id', '')}",
        "source": "aliexpress",
        "title": raw.get("product_title", ""),
        "category": category,
        "price_usd": cost,
        "cost_usd": cost,
        "original_price_usd": original,
        "rating": rating,
        "review_count": sales,
        "image_url": raw.get("product_main_image_url", ""),
        "product_url": f"https://www.aliexpress.com/item/{raw.get('product_id')}.html",
        "supplier": "AliExpress",
        "shipping_days": _parse_delivery_days(raw.get("logistics_desc", "")),
        "sales_30d": sales,
        "raw_data": raw,
    }


def _parse_delivery_days(logistics_desc: str) -> int:
    """배송 설명에서 배송일 파싱"""
    if not logistics_desc:
        return 14
    desc_lower = logistics_desc.lower()
    if "3-5" in desc_lower or "3 to 5" in desc_lower:
        return 5
    if "5-7" in desc_lower or "5 to 7" in desc_lower:
        return 7
    if "7-10" in desc_lower or "7 to 10" in desc_lower:
        return 10
    if "express" in desc_lower or "fast" in desc_lower:
        return 5
    if "epacket" in desc_lower:
        return 7
    return 14


def _passes_basic_filter(title: str, rating: float) -> bool:
    """블랙리스트 및 기본 조건 필터"""
    if not title:
        return False
    title_lower = title.lower()
    for kw in BLACKLIST_KEYWORDS:
        if kw in title_lower:
            return False
    return True


def _generate_sample_products(category: str, count: int) -> list[dict]:
    """
    샘플 상품 생성 (API 키 없을 때 데모용)
    실제 운영 시 API 키 발급 후 _fetch_via_api 사용
    """
    templates = {
        "beauty": [
            ("Viral Gua Sha Facial Lifting Tool Rose Quartz", 12.5, 4.7, 1250, "gua sha facial massage"),
            ("LED Face Mask Light Therapy Skin Rejuvenation", 18.9, 4.5, 890, "led face mask beauty"),
            ("Microneedling Derma Roller 0.5mm Collagen Boost", 8.5, 4.6, 2100, "derma roller skincare"),
            ("Electric Facial Cleansing Brush Silicone", 15.2, 4.4, 675, "facial cleansing brush"),
            ("Ice Roller Face Eye Puffiness Relief", 6.8, 4.8, 3200, "ice roller face"),
        ],
        "gadgets": [
            ("Mini Portable Projector 1080P Home Theater", 45.0, 4.3, 320, "mini projector home"),
            ("Wireless Charger 3-in-1 MagSafe Compatible", 22.5, 4.5, 780, "wireless charger magsafe"),
            ("Smart LED Strip Lights RGB 10m App Control", 16.8, 4.6, 1450, "led strip lights smart"),
            ("Portable Air Purifier USB Desktop Mini", 19.9, 4.4, 560, "air purifier desktop"),
            ("Phone Camera Lens Kit Wide Macro 3-in-1", 12.0, 4.5, 890, "phone camera lens"),
        ],
        "fitness": [
            ("Booty Bands Resistance Set Hip Workout", 8.5, 4.7, 2800, "resistance bands booty"),
            ("Ab Roller Wheel Core Strength Trainer", 11.2, 4.6, 1650, "ab roller wheel"),
            ("Massage Gun Deep Tissue Muscle Recovery", 38.5, 4.4, 430, "massage gun muscle"),
            ("Jump Rope Speed Skipping Fitness", 7.5, 4.8, 4200, "jump rope fitness"),
            ("Yoga Block Set Non-Slip Cork Support", 14.5, 4.5, 920, "yoga block set"),
        ],
        "home": [
            ("Magnetic Knife Strip Wall Mount Organizer", 9.8, 4.7, 1800, "magnetic knife strip"),
            ("Vacuum Sealer Bags Food Storage Space Saver", 13.5, 4.5, 950, "vacuum sealer bags"),
            ("LED Sunset Lamp Rainbow Projection Night", 16.0, 4.6, 2200, "sunset lamp projection"),
            ("Silicone Stretch Lids Universal Bowl Cover", 8.2, 4.8, 5600, "silicone stretch lids"),
            ("Shower Head High Pressure Filtered Rainfall", 22.0, 4.5, 780, "shower head filtered"),
        ],
        "pet": [
            ("Self-Cleaning Slicker Brush Dog Cat Grooming", 12.5, 4.8, 3400, "self cleaning pet brush"),
            ("Interactive Laser Toy Cat Exercise Auto", 9.8, 4.6, 2100, "interactive cat toy laser"),
            ("Slow Feeder Bowl Anti-Bloat Dog Puzzle", 8.5, 4.7, 1900, "slow feeder bowl dog"),
            ("Pet Camera Treat Dispenser WiFi App", 42.0, 4.3, 280, "pet camera treat dispenser"),
            ("Portable Dog Water Bottle Leak Proof Travel", 11.0, 4.7, 2600, "dog water bottle travel"),
        ],
    }

    products_data = templates.get(category, templates["gadgets"])
    result = []

    for i, (title, cost, rating, sales, keyword) in enumerate(products_data * (count // len(products_data) + 1)):
        if len(result) >= count:
            break
        # 약간의 무작위 변동 추가
        cost_variation = cost * (1 + random.uniform(-0.1, 0.1))
        result.append({
            "product_id": f"ae_demo_{category}_{i:04d}",
            "source": "aliexpress_demo",
            "title": title,
            "category": category,
            "price_usd": round(cost_variation, 2),
            "cost_usd": round(cost_variation, 2),
            "rating": min(5.0, rating + random.uniform(-0.1, 0.1)),
            "review_count": sales + random.randint(-50, 200),
            "image_url": f"https://ae-pic-a1.aliexpress-media.com/kf/demo_{i}.jpg",
            "product_url": f"https://www.aliexpress.com/item/demo_{category}_{i}.html",
            "supplier": random.choice(["CJ Dropshipping", "AliExpress", "Zendrop"]),
            "shipping_days": random.choice([3, 4, 5, 5, 5, 6, 7]),
            "sales_30d": sales + random.randint(0, 500),
            "search_keyword": keyword,
        })

    return result


def fetch_cj_dropshipping_products(
    category: str = "beauty",
    max_ship_days: int = 7,
) -> list[dict]:
    """
    CJ Dropshipping 상품 수집 (빠른 배송 전문)
    실제 구현: CJ Dropshipping Open API 사용
    """
    # CJ는 미국 창고 있어 3-5일 배송 가능
    # 실제 API: https://developers.cjdropshipping.com/
    products = _generate_sample_products(category, 20)
    for p in products:
        p["source"] = "cj_dropshipping"
        p["supplier"] = "CJ Dropshipping"
        p["shipping_days"] = random.choice([3, 4, 5, 5])
        p["product_id"] = p["product_id"].replace("ae_", "cj_")
    return products
