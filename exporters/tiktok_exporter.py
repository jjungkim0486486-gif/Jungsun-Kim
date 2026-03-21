"""
TikTok 콘텐츠 & Shop 익스포터
- TikTok Shop 상품 등록
- 바이럴 콘텐츠 스크립트 자동 생성
- 해시태그 전략 생성
- 광고 훅 텍스트 생성
"""

import json
import os
import csv
from datetime import datetime
from typing import Optional
import requests

from config import config
from scrapers.tiktok_scraper import get_viral_keywords_for_product


class TikTokExporter:
    """
    TikTok Shop 상품 등록 + 콘텐츠 전략 생성

    기능:
    1. TikTok Shop API 상품 등록
    2. 바이럴 영상 스크립트 생성
    3. 해시태그 전략 (라이징 + 메가 태그 조합)
    4. 광고 훅 (처음 3초 멘트) 5개 생성
    5. 콘텐츠 캘린더 생성
    """

    def __init__(self):
        self.access_token = config.tiktok_access_token

    def export_product(self, product: dict, score_data: dict) -> dict:
        """단일 상품 TikTok 전략 패키지 생성"""
        content_package = self._build_content_package(product, score_data)

        result = {
            "platform": "tiktok",
            "product_id": product.get("product_id", ""),
            "content_package": content_package,
            "shop_listing": None,
            "exported_at": datetime.utcnow().isoformat(),
        }

        # TikTok Shop API 등록 (토큰 있을 때)
        if self.access_token:
            shop_result = self._upload_to_tiktok_shop(product, score_data)
            result["shop_listing"] = shop_result

        # JSON 저장
        self._save_content_package(product, result)
        return result

    def export_batch(
        self,
        products: list[dict],
        export_dir: str = "data/exports",
    ) -> str:
        """
        여러 상품 콘텐츠 패키지 일괄 생성
        Returns: JSON 파일 경로
        """
        os.makedirs(export_dir, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        json_path = os.path.join(export_dir, f"tiktok_content_{timestamp}.json")

        all_packages = []
        for item in products:
            product = item.get("product", {})
            score_data = item.get("scores", {})
            package = self._build_content_package(product, score_data)
            all_packages.append({
                "product_id": product.get("product_id"),
                "title": product.get("title"),
                "total_score": score_data.get("total_score"),
                "content": package,
            })

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(all_packages, f, ensure_ascii=False, indent=2)

        return json_path

    def _build_content_package(self, product: dict, score_data: dict) -> dict:
        """TikTok 콘텐츠 전략 패키지 생성"""
        title = product.get("title", "")
        category = product.get("category", "general")
        pricing = score_data.get("commercial", {}).get("pricing", {})
        sell_price = pricing.get("sell_price", 0)
        is_spike = score_data.get("is_24h_spike", False)
        viral_grade = score_data.get("viral_grade", "B")

        return {
            "video_hooks": _generate_video_hooks(title, category, is_spike),
            "video_scripts": _generate_video_scripts(title, category, sell_price, product),
            "hashtag_strategy": _generate_hashtag_strategy(product, score_data),
            "caption_templates": _generate_captions(title, category, sell_price),
            "content_calendar": _generate_content_calendar(title, category),
            "ad_creative_brief": _generate_ad_brief(product, score_data),
            "viral_grade": viral_grade,
            "recommended_posting_time": _get_optimal_posting_time(),
        }

    def _upload_to_tiktok_shop(self, product: dict, score_data: dict) -> dict:
        """TikTok Shop API 상품 등록"""
        # TikTok Shop Open API
        # https://partner.tiktokshop.com/docv2/page/6509571688812c0241b4a2a2
        url = "https://open-api.tiktokglobalshop.com/product/202309/products"
        headers = {
            "x-tts-access-token": self.access_token,
            "Content-Type": "application/json",
        }
        pricing = score_data.get("commercial", {}).get("pricing", {})

        payload = {
            "title": product.get("title", "")[:255],
            "description": _generate_tiktok_description(product, score_data),
            "category_id": _get_tiktok_category_id(product.get("category", "")),
            "main_images": [{"url": product.get("image_url", "")}] if product.get("image_url") else [],
            "skus": [{
                "seller_sku": product.get("product_id", ""),
                "original_price": str(pricing.get("sell_price", 0)),
                "available_stock": 999,
            }],
            "package_weight": {"value": "200", "unit": "GRAM"},
            "package_dimensions": {
                "length": "10", "width": "10", "height": "5", "unit": "CENTIMETER"
            },
        }

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            return {
                "status": "success",
                "product_id": data.get("data", {}).get("product_id"),
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _save_content_package(self, product: dict, result: dict) -> None:
        """콘텐츠 패키지를 로컬 JSON 파일로 저장"""
        os.makedirs("data/exports/tiktok", exist_ok=True)
        product_id = product.get("product_id", "unknown")
        path = f"data/exports/tiktok/{product_id}_content.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)


def _generate_video_hooks(
    title: str, category: str, is_spike: bool
) -> list[str]:
    """
    TikTok 영상 처음 3초 훅 멘트 5개 생성
    처음 3초가 시청 여부를 결정
    """
    product_noun = title.split()[0].capitalize()
    hooks = [
        f"Wait— this {product_noun} actually works 😭",
        f"I cannot believe I lived without this {product_noun}...",
        f"POV: You just discovered the best {category} hack on TikTok",
        f"This {product_noun} has 10,000+ 5-star reviews and I finally tried it",
        f"Stop scrolling. You NEED to see this {product_noun} 🔥",
    ]
    if is_spike:
        hooks.insert(0, f"Everyone is buying this {product_noun} right now and here's why 👇")
    return hooks[:5]


def _generate_video_scripts(
    title: str, category: str, price: float, product: dict
) -> list[dict]:
    """TikTok 영상 스크립트 템플릿 생성"""
    rating = product.get("rating", 4.5)
    reviews = product.get("review_count", 0)
    shipping_days = product.get("shipping_days", 7)
    product_noun = title.split()[0].capitalize()

    return [
        {
            "type": "unboxing",
            "duration": "30-60s",
            "script": f"""
[Hook - 0~3s] "Okay I need to talk about this {product_noun} I just got..."
[Unboxing - 3~15s] Show package, open slowly, react to product
[Demo - 15~40s] Use the product, show before/after or key feature
[Review - 40~55s] "Honestly? {rating}/5 stars. {reviews:,} people can't be wrong."
[CTA - 55~60s] "Link in bio! Only ${price:.0f} and ships in {shipping_days} days 🔗"
""".strip(),
        },
        {
            "type": "problem_solution",
            "duration": "15-30s",
            "script": f"""
[Problem - 0~5s] Show the problem this product solves dramatically
[Solution - 5~20s] "{product_noun} literally fixes this in seconds"
[Proof - 20~28s] Show results / rating screenshot
[CTA - 28~30s] "Get it for ${price:.0f} — link in bio ✨"
""".strip(),
        },
        {
            "type": "comparison",
            "duration": "30-45s",
            "script": f"""
[Before - 0~10s] "Me before this {product_noun}: [show struggle]"
[After - 10~25s] "Me after: [show amazing result]"
[Stats - 25~40s] "{reviews:,} reviews, {rating}/5 stars, ${price:.0f}"
[CTA - 40~45s] "Shop link in bio! Fast shipping 📦"
""".strip(),
        },
    ]


def _generate_hashtag_strategy(product: dict, score_data: dict) -> dict:
    """
    해시태그 전략 생성
    - 메가 태그 (1B+ 조회수): 도달 범위 극대화
    - 미드 태그 (100M+): 타겟 오디언스
    - 니치 태그 (10M-): 전환율 높음
    """
    category = product.get("category", "general")
    viral_hashtags = score_data.get("tiktok_signal", {}).get("hashtags", [])

    mega_tags = ["#fyp", "#foryou", "#foryoupage", "#tiktok"]
    mid_tags = {
        "beauty": ["#BeautyTok", "#SkincareTok", "#GlowUp", "#MakeupTok"],
        "gadgets": ["#TechTok", "#GadgetTok", "#SmartHome", "#CoolFinds"],
        "fitness": ["#FitTok", "#GymTok", "#WorkoutTok", "#FitnessMotivation"],
        "home": ["#HomeTok", "#CleaningTok", "#OrganizationTok", "#HomeHacks"],
        "pet": ["#PetTok", "#DogTok", "#CatTok", "#PetLife"],
    }.get(category, ["#TikTokMadeMeBuyIt", "#AmazonFinds"])

    niche_tags = [
        "#TikTokMadeMeBuyIt",
        "#AmazonFinds",
        f"#{category.capitalize()}Finds",
        "#ShopTikTok",
        "#TikTokShop",
    ]

    all_tags = mega_tags[:2] + mid_tags[:3] + niche_tags[:3]
    if viral_hashtags:
        all_tags = viral_hashtags[:2] + all_tags

    return {
        "mega_tags": mega_tags,
        "mid_tags": mid_tags,
        "niche_tags": niche_tags,
        "recommended_combo": list(dict.fromkeys(all_tags))[:10],
        "tip": "처음 3개는 니치 태그, 마지막 2개는 #fyp #foryou 사용 권장",
    }


def _generate_captions(title: str, category: str, price: float) -> list[str]:
    """TikTok 캡션 템플릿 (5개)"""
    return [
        f"POV: TikTok made me buy this and I'm obsessed 😍 Only ${price:.0f}! Link in bio 🔗",
        f"This {title.split()[0]} is going viral for a reason... 🔥 Shop now - link in bio",
        f"Under ${price + 5:.0f} and it actually works?? Found in bio 👇",
        f"My honest review after 7 days... I'm not going back 💅 Link in bio",
        f"You need this in your {category} routine ASAP 🤩 ${price:.0f} - link in bio",
    ]


def _generate_content_calendar(title: str, category: str) -> list[dict]:
    """7일 콘텐츠 캘린더"""
    product_noun = title.split()[0].capitalize()
    return [
        {"day": 1, "content_type": "Unboxing + First Impression", "best_time": "7PM-9PM"},
        {"day": 2, "content_type": "Tutorial / How-to Use", "best_time": "12PM-2PM"},
        {"day": 3, "content_type": "Before & After", "best_time": "7PM-9PM"},
        {"day": 4, "content_type": "Day in my life featuring product", "best_time": "6PM-8PM"},
        {"day": 5, "content_type": "Reply to comments / Q&A", "best_time": "7PM-9PM"},
        {"day": 6, "content_type": "Duet/Stitch viral video", "best_time": "12PM-3PM"},
        {"day": 7, "content_type": "Results after 1 week", "best_time": "7PM-9PM"},
    ]


def _generate_ad_brief(product: dict, score_data: dict) -> dict:
    """TikTok 광고 크리에이티브 브리프"""
    pricing = score_data.get("commercial", {}).get("pricing", {})
    return {
        "objective": "Conversion (Purchase)",
        "target_audience": {
            "age": "18-34",
            "gender": "All (skew Female for beauty/home)",
            "interests": [product.get("category", ""), "Online Shopping", "TikTok Shop"],
        },
        "budget_daily_usd": 30,
        "bid_type": "Cost Cap",
        "target_cpa_usd": round(pricing.get("sell_price", 0) * 0.25, 2),
        "creative_format": "In-Feed Video",
        "video_length": "15-30s",
        "landing_page": "Product Page",
        "cta": "Shop Now",
    }


def _generate_tiktok_description(product: dict, score_data: dict) -> str:
    """TikTok Shop 상품 설명"""
    title = product.get("title", "")
    rating = product.get("rating", 4.5)
    shipping = product.get("shipping_days", 7)
    return (
        f"✨ {title}\n\n"
        f"⭐ {rating}/5 rated | Fast {shipping}-day shipping\n"
        f"🔥 Trending on TikTok — join 10,000+ satisfied customers!\n\n"
        f"✅ Premium quality\n"
        f"✅ Easy returns\n"
        f"✅ Ships fast\n\n"
        f"Order now and see the difference! 🛍️"
    )


def _get_tiktok_category_id(category: str) -> str:
    """TikTok Shop 카테고리 ID 매핑"""
    mapping = {
        "beauty": "601251",
        "gadgets": "601009",
        "fitness": "601144",
        "home": "601100",
        "pet": "601170",
        "kitchen": "601101",
        "fashion": "601002",
    }
    return mapping.get(category, "601009")


def _get_optimal_posting_time() -> dict:
    """최적 TikTok 포스팅 시간"""
    return {
        "weekday": "Tuesday - Thursday",
        "time_slots": ["7AM-9AM", "12PM-2PM", "7PM-9PM"],
        "timezone": "EST (US)",
        "tip": "첫 포스팅은 팔로워가 가장 활발한 저녁 7-9시 권장",
    }
