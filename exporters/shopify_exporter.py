"""
Shopify 상품 익스포터
- Shopify Admin API를 통한 상품 자동 등록
- CSV 익스포트 (수동 업로드용)
- 상품 설명, 태그, SEO 최적화 자동 생성
"""

import csv
import json
import os
import requests
from datetime import datetime
from typing import Optional

from config import config


class ShopifyExporter:
    """
    Shopify 상품 등록 및 관리

    기능:
    1. Shopify Admin API 직접 등록 (API 키 있을 때)
    2. CSV 파일 생성 (수동 업로드용)
    3. 상품 설명 자동 생성
    4. SEO 메타태그 최적화
    """

    def __init__(self):
        self.store_url = config.shopify_store_url
        self.access_token = config.shopify_access_token
        self.api_version = "2024-01"
        self.base_url = f"https://{self.store_url}/admin/api/{self.api_version}"

    def export_product(self, product: dict, score_data: dict) -> dict:
        """
        단일 상품 Shopify 등록/익스포트
        API 키 있으면 직접 등록, 없으면 CSV에 추가
        """
        shopify_product = self._build_shopify_product(product, score_data)

        if self.access_token and self.store_url:
            return self._upload_via_api(shopify_product, product["product_id"])
        return self._export_to_csv(shopify_product, product["product_id"])

    def export_batch(
        self,
        products: list[dict],
        export_dir: str = "data/exports",
    ) -> str:
        """
        여러 상품을 CSV로 일괄 익스포트
        Returns: CSV 파일 경로
        """
        os.makedirs(export_dir, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        csv_path = os.path.join(export_dir, f"shopify_products_{timestamp}.csv")

        # Shopify CSV 컬럼
        fieldnames = [
            "Handle", "Title", "Body (HTML)", "Vendor", "Type",
            "Tags", "Published", "Option1 Name", "Option1 Value",
            "Variant SKU", "Variant Grams", "Variant Inventory Tracker",
            "Variant Inventory Qty", "Variant Inventory Policy",
            "Variant Fulfillment Service", "Variant Price",
            "Variant Compare At Price", "Variant Requires Shipping",
            "Variant Taxable", "Variant Barcode", "Image Src",
            "Image Position", "Image Alt Text", "SEO Title", "SEO Description",
            "Google Shopping / Google Product Category", "Metafield: custom.badge [single_line_text_field]",
        ]

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for item in products:
                product = item.get("product", {})
                score_data = item.get("scores", {})
                row = self._build_csv_row(product, score_data)
                writer.writerow(row)

        return csv_path

    def _build_shopify_product(self, product: dict, score_data: dict) -> dict:
        """Shopify 상품 데이터 구조 생성"""
        pricing = score_data.get("commercial", {}).get("pricing", {})
        sell_price = pricing.get("sell_price", product.get("price_usd", 0) * 3)
        compare_price = pricing.get("compare_price", sell_price * 1.5)

        title = product.get("title", "")
        category = product.get("category", "general")
        description = _generate_product_description(product, score_data)
        tags = _generate_tags(product, score_data)
        handle = _slugify(title)

        return {
            "product": {
                "title": title,
                "body_html": description,
                "vendor": product.get("supplier", ""),
                "product_type": category.capitalize(),
                "tags": ", ".join(tags),
                "status": "draft",  # 검토 후 active로 변경
                "images": [{"src": product.get("image_url", "")}] if product.get("image_url") else [],
                "variants": [{
                    "price": str(sell_price),
                    "compare_at_price": str(compare_price),
                    "sku": product.get("product_id", ""),
                    "inventory_quantity": 999,
                    "inventory_management": "shopify",
                    "fulfillment_service": "manual",
                    "requires_shipping": True,
                    "taxable": True,
                    "weight": 200,
                    "weight_unit": "g",
                }],
                "metafields": [
                    {
                        "namespace": "custom",
                        "key": "radar_score",
                        "value": str(score_data.get("total_score", 0)),
                        "type": "number_decimal",
                    },
                    {
                        "namespace": "custom",
                        "key": "is_viral",
                        "value": "true" if score_data.get("is_24h_spike") else "false",
                        "type": "boolean",
                    },
                ],
                "seo": {
                    "title": _generate_seo_title(title),
                    "description": _generate_seo_description(product, score_data),
                },
            }
        }

    def _build_csv_row(self, product: dict, score_data: dict) -> dict:
        """Shopify CSV 행 생성"""
        pricing = score_data.get("commercial", {}).get("pricing", {})
        sell_price = pricing.get("sell_price", product.get("price_usd", 0) * 3)
        compare_price = pricing.get("compare_price", sell_price * 1.5)

        title = product.get("title", "")
        category = product.get("category", "general")
        tags = _generate_tags(product, score_data)
        description = _generate_product_description(product, score_data)
        seo_title = _generate_seo_title(title)
        seo_desc = _generate_seo_description(product, score_data)

        viral_badge = ""
        if score_data.get("is_24h_spike"):
            viral_badge = "🔥 Trending Now"
        elif score_data.get("is_3d_repeat"):
            viral_badge = "⭐ Best Seller"

        return {
            "Handle": _slugify(title),
            "Title": title,
            "Body (HTML)": description,
            "Vendor": product.get("supplier", ""),
            "Type": category.capitalize(),
            "Tags": ", ".join(tags),
            "Published": "TRUE",
            "Option1 Name": "Title",
            "Option1 Value": "Default Title",
            "Variant SKU": product.get("product_id", ""),
            "Variant Grams": "200",
            "Variant Inventory Tracker": "shopify",
            "Variant Inventory Qty": "999",
            "Variant Inventory Policy": "deny",
            "Variant Fulfillment Service": "manual",
            "Variant Price": str(sell_price),
            "Variant Compare At Price": str(compare_price),
            "Variant Requires Shipping": "TRUE",
            "Variant Taxable": "TRUE",
            "Variant Barcode": "",
            "Image Src": product.get("image_url", ""),
            "Image Position": "1",
            "Image Alt Text": title[:125],
            "SEO Title": seo_title,
            "SEO Description": seo_desc,
            "Google Shopping / Google Product Category": _get_google_category(category),
            "Metafield: custom.badge [single_line_text_field]": viral_badge,
        }

    def _upload_via_api(self, shopify_product: dict, product_id: str) -> dict:
        """Shopify Admin API로 상품 등록"""
        headers = {
            "X-Shopify-Access-Token": self.access_token,
            "Content-Type": "application/json",
        }
        try:
            resp = requests.post(
                f"{self.base_url}/products.json",
                headers=headers,
                json=shopify_product,
                timeout=30,
            )
            resp.raise_for_status()
            result = resp.json()
            shopify_id = result.get("product", {}).get("id", "")
            return {
                "status": "success",
                "platform": "shopify",
                "external_id": str(shopify_id),
                "product_url": f"https://{self.store_url}/products/{_slugify(shopify_product['product']['title'])}",
                "admin_url": f"https://{self.store_url}/admin/products/{shopify_id}",
            }
        except Exception as e:
            return {"status": "error", "platform": "shopify", "error": str(e)}

    def _export_to_csv(self, shopify_product: dict, product_id: str) -> dict:
        """로컬 CSV 파일에 상품 추가"""
        csv_path = "data/exports/shopify_pending.csv"
        os.makedirs("data/exports", exist_ok=True)

        product_data = shopify_product["product"]
        variant = product_data["variants"][0]
        row = {
            "Handle": _slugify(product_data["title"]),
            "Title": product_data["title"],
            "Body (HTML)": product_data["body_html"],
            "Vendor": product_data["vendor"],
            "Type": product_data["product_type"],
            "Tags": product_data["tags"],
            "Variant Price": variant["price"],
            "Variant Compare At Price": variant["compare_at_price"],
            "Variant SKU": variant["sku"],
        }

        file_exists = os.path.exists(csv_path)
        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(row.keys()))
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)

        return {
            "status": "csv_exported",
            "platform": "shopify",
            "csv_path": csv_path,
            "product_id": product_id,
        }


def _generate_product_description(product: dict, score_data: dict) -> str:
    """상품 설명 HTML 자동 생성"""
    title = product.get("title", "")
    rating = product.get("rating", 0)
    review_count = product.get("review_count", 0)
    shipping_days = product.get("shipping_days", 7)
    viral_score = score_data.get("viral_score", 0)
    is_spike = score_data.get("is_24h_spike", False)

    trending_badge = ""
    if is_spike:
        trending_badge = '<div class="badge">🔥 Trending on TikTok!</div>'

    stars = "⭐" * int(rating) if rating >= 4 else ""

    return f"""
<div class="product-description">
    {trending_badge}
    <h2>Why Everyone's Talking About {title.split()[0]} {title.split()[1] if len(title.split()) > 1 else ''}</h2>

    <div class="highlights">
        <ul>
            <li>✅ <strong>Viral on TikTok</strong> — Join thousands of happy customers</li>
            <li>✅ <strong>Fast Shipping</strong> — Delivered in {shipping_days} days or less</li>
            <li>✅ <strong>Top Rated</strong> — {stars} {rating:.1f}/5 from {review_count:,}+ reviews</li>
            <li>✅ <strong>30-Day Money Back Guarantee</strong></li>
        </ul>
    </div>

    <h3>Product Features</h3>
    <ul>
        <li>Premium quality materials</li>
        <li>Easy to use — no experience needed</li>
        <li>Perfect gift idea</li>
        <li>Used by influencers worldwide</li>
    </ul>

    <div class="shipping-info">
        <h3>📦 Shipping Information</h3>
        <p>We process all orders within 24 hours. Standard delivery: <strong>{shipping_days} days</strong>.</p>
    </div>
</div>
""".strip()


def _generate_tags(product: dict, score_data: dict) -> list[str]:
    """상품 태그 생성 (SEO + 검색 최적화)"""
    category = product.get("category", "general")
    tags = [category, "dropshipping", "free-shipping", "trending"]

    if score_data.get("is_24h_spike"):
        tags.extend(["viral", "trending-now", "tiktok-viral"])
    if score_data.get("is_3d_repeat"):
        tags.extend(["bestseller", "popular"])

    # 카테고리별 태그
    category_tags = {
        "beauty": ["beauty", "skincare", "makeup", "self-care"],
        "gadgets": ["gadgets", "tech", "smart-home", "innovative"],
        "fitness": ["fitness", "workout", "gym", "health"],
        "home": ["home-decor", "organization", "cleaning", "kitchen"],
        "pet": ["pet-supplies", "dog", "cat", "pet-care"],
    }
    tags.extend(category_tags.get(category, []))

    # 제목에서 키워드 추출
    title_words = [w.lower() for w in product.get("title", "").split()
                   if len(w) > 4 and w.isalpha()]
    tags.extend(title_words[:3])

    return list(dict.fromkeys(tags))[:20]  # 중복 제거, 최대 20개


def _generate_seo_title(title: str) -> str:
    """SEO 최적화 타이틀 생성"""
    seo_title = f"{title} | Free Shipping | Best Price"
    return seo_title[:70]  # Google 권장 70자 이하


def _generate_seo_description(product: dict, score_data: dict) -> str:
    """SEO 메타 설명 생성"""
    title = product.get("title", "")
    shipping = product.get("shipping_days", 7)
    rating = product.get("rating", 0)
    pricing = score_data.get("commercial", {}).get("pricing", {})
    price = pricing.get("sell_price", 0)

    desc = (
        f"Buy {title} at the best price. "
        f"⭐{rating:.1f}/5 rating. "
        f"Fast {shipping}-day shipping. "
        f"From ${price:.2f}. Free returns."
    )
    return desc[:155]  # Google 권장 155자 이하


def _get_google_category(category: str) -> str:
    """Google Shopping 카테고리 매핑"""
    mapping = {
        "beauty": "Health & Beauty > Beauty > Skin Care",
        "gadgets": "Electronics > Consumer Electronics",
        "fitness": "Sporting Goods > Exercise & Fitness",
        "home": "Home & Garden > Household Supplies",
        "pet": "Animals & Pet Supplies > Pet Supplies",
        "kitchen": "Home & Garden > Kitchen & Dining",
        "fashion": "Apparel & Accessories",
    }
    return mapping.get(category, "Home & Garden")


def _slugify(text: str) -> str:
    """URL 슬러그 생성"""
    import re
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    text = text.strip("-")
    return text[:60]
