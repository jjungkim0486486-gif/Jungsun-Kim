"""
Product Radar - 메인 엔진
24h급등 + 3d반복 포착 상품 레이더 시스템

실행 방법:
    python main.py                  # 1회 스캔 실행
    python main.py --schedule       # 자동 스케줄 실행 (6시간마다)
    python main.py --category beauty  # 특정 카테고리만 스캔
    python main.py --top 10         # 상위 10개만 출력
    python main.py --export         # 결과 즉시 익스포트
"""

import argparse
import sys
import time
from datetime import datetime

from config import config, FAST_SHIP_CATEGORIES
from storage.database import init_db, upsert_product, insert_radar_score, get_top_products
from scrapers.aliexpress_scraper import fetch_aliexpress_hot_products, fetch_cj_dropshipping_products
from scrapers.tiktok_scraper import fetch_tiktok_trending_products
from analyzers.trend_analyzer import TrendAnalyzer
from analyzers.viral_scorer import ViralScorer
from filters.product_filter import ProductQualityFilter, ShippingFilter
from filters.commercial_optimizer import CommercialOptimizer
from exporters.shopify_exporter import ShopifyExporter
from exporters.tiktok_exporter import TikTokExporter
from dashboard import Dashboard


def run_radar_scan(
    categories: list[str] | None = None,
    export: bool = False,
    top_n: int = 20,
) -> list[dict]:
    """
    레이더 풀 스캔 실행

    단계:
    1. 다중 소스에서 상품 수집
    2. 품질 + 배송 필터 적용
    3. 24h 급등 + 3d 반복 분석
    4. 바이럴 점수 + 수익성 평가
    5. 종합 점수로 정렬
    6. 익스포트 (옵션)
    """
    scan_start = datetime.utcnow()
    dashboard = Dashboard()

    # 스캔 대상 카테고리
    target_categories = categories or list(FAST_SHIP_CATEGORIES.keys())

    dashboard.print_header(f"Product Radar Scan | {scan_start.strftime('%Y-%m-%d %H:%M UTC')}")
    dashboard.print_info(f"스캔 카테고리: {', '.join(target_categories)}")

    # 분석 도구 초기화
    trend_analyzer = TrendAnalyzer()
    viral_scorer = ViralScorer()
    quality_filter = ProductQualityFilter()
    shipping_filter = ShippingFilter()
    commercial_optimizer = CommercialOptimizer()

    all_products = []
    filtered_out = 0

    # 1단계: 다중 소스 상품 수집
    dashboard.print_step(1, "상품 수집 중...")
    for category in target_categories:
        # AliExpress 인기 상품
        ae_products = fetch_aliexpress_hot_products(
            category=category,
            page_size=20,
            min_rating=config.quality.min_rating,
            max_ship_days=config.shipping.max_delivery_days,
        )
        # CJ Dropshipping (빠른 배송 특화)
        cj_products = fetch_cj_dropshipping_products(
            category=category,
            max_ship_days=config.shipping.max_delivery_days,
        )
        # TikTok 트렌딩 상품
        tiktok_products = fetch_tiktok_trending_products(category=category)

        # TikTok 트렌드 데이터를 AE/CJ 상품에 매칭
        enriched = _enrich_with_tiktok_data(ae_products + cj_products, tiktok_products)
        all_products.extend(enriched)

    dashboard.print_info(f"총 {len(all_products)}개 상품 수집 완료")

    # 2단계: 품질 + 배송 필터
    dashboard.print_step(2, "품질 & 배송 필터 적용 중...")
    passed_products = []
    for product in all_products:
        # 중복 제거
        if any(p["product_id"] == product["product_id"] for p in passed_products):
            continue

        q_pass, q_reason = quality_filter.filter(product)
        s_pass, s_reason = shipping_filter.filter(product)

        if not q_pass or not s_pass:
            filtered_out += 1
            continue

        passed_products.append(product)

    dashboard.print_info(f"필터 통과: {len(passed_products)}개 | 제외: {filtered_out}개")

    # 3단계: 수익성 필터
    dashboard.print_step(3, "수익성 분석 중...")
    profitable_products = []
    for product in passed_products:
        c_pass, c_reason = commercial_optimizer.filter(product)
        if c_pass:
            profitable_products.append(product)

    dashboard.print_info(f"수익성 통과: {len(profitable_products)}개")

    # 4단계: 트렌드 + 바이럴 + 종합 점수 산출
    dashboard.print_step(4, "트렌드 분석 & 점수 산출 중...")
    scored_products = []

    for i, product in enumerate(profitable_products):
        # DB에 상품 저장
        _save_product_to_db(product)

        # 분석 실행
        trend_data = trend_analyzer.analyze(product)
        viral_data = viral_scorer.score(product, trend_data)
        quality_data = quality_filter.score(product)
        shipping_data = shipping_filter.score(product)
        commercial_data = commercial_optimizer.optimize(product)

        # 종합 점수 산출 (가중 합산)
        total_score = _calculate_total_score(
            viral_score=viral_data["viral_score"],
            trend_score=trend_data["trend_score"],
            profit_score=commercial_data["profit_score"],
            quality_score=quality_data["quality_score"],
            shipping_score=shipping_data["shipping_score"],
        )

        scores = {
            "total_score": total_score,
            "viral_score": viral_data["viral_score"],
            "trend_score": trend_data["trend_score"],
            "profit_score": commercial_data["profit_score"],
            "quality_score": quality_data["quality_score"],
            "shipping_score": shipping_data["shipping_score"],
            "viral_grade": viral_data["viral_grade"],
            "is_24h_spike": trend_data["is_24h_spike"],
            "is_3d_repeat": trend_data["is_3d_repeat"],
            "spike_ratio": trend_data["spike_ratio"],
            "repeat_days": trend_data["repeat_days"],
            "commercial": commercial_data,
            "pricing": commercial_data.get("pricing", {}),
            "meta": {
                "trend_detail": trend_data,
                "viral_detail": viral_data,
                "quality_detail": quality_data,
                "shipping_detail": shipping_data,
            },
        }

        # DB에 점수 저장
        insert_radar_score(product["product_id"], scores)

        scored_products.append({
            "product": product,
            "scores": scores,
        })

        # 진행 상황 표시
        if (i + 1) % 10 == 0:
            dashboard.print_info(f"  {i + 1}/{len(profitable_products)} 완료...")

    # 5단계: 점수 기준 정렬
    dashboard.print_step(5, "결과 정렬 중...")
    scored_products.sort(key=lambda x: x["scores"]["total_score"], reverse=True)

    # 최소 점수 필터
    top_products = [
        p for p in scored_products
        if p["scores"]["total_score"] >= config.min_total_score
    ][:top_n]

    scan_duration = (datetime.utcnow() - scan_start).total_seconds()
    dashboard.print_info(f"스캔 완료: {len(top_products)}개 레이더 포착 | {scan_duration:.1f}초 소요")

    # 6단계: 결과 출력
    dashboard.print_results(top_products)

    # 7단계: 익스포트
    if export and top_products:
        dashboard.print_step(6, "익스포트 중...")
        _export_results(top_products, dashboard)

    return top_products


def _enrich_with_tiktok_data(
    products: list[dict],
    tiktok_products: list[dict],
) -> list[dict]:
    """AE/CJ 상품에 TikTok 트렌드 데이터 결합"""
    tiktok_by_category = {}
    for tp in tiktok_products:
        cat = tp.get("category", "general")
        if cat not in tiktok_by_category:
            tiktok_by_category[cat] = []
        tiktok_by_category[cat].append(tp)

    enriched = []
    for product in products:
        category = product.get("category", "general")
        tiktok_list = tiktok_by_category.get(category, [])

        # 카테고리 내 TikTok 트렌드 평균값 적용
        if tiktok_list:
            import random
            # 실제 구현: 제목 유사도 매칭으로 개별 연결
            # 데모: 카테고리 평균 사용
            sample_tt = random.choice(tiktok_list)
            product.setdefault("tiktok_hashtag_views", sample_tt.get("tiktok_hashtag_views", 0))
            product.setdefault("tiktok_video_count", sample_tt.get("tiktok_video_count", 0))
            product.setdefault("engagement_rate", sample_tt.get("engagement_rate", 0.05))
            product.setdefault("trend_velocity", sample_tt.get("trend_velocity", 1.0))
            product.setdefault("is_trending_up", sample_tt.get("is_trending_up", False))
            product.setdefault("spike_24h", sample_tt.get("spike_24h", 0))

        enriched.append(product)

    return enriched


def _save_product_to_db(product: dict) -> None:
    """상품을 DB에 저장"""
    upsert_product({
        "product_id": product.get("product_id", ""),
        "source": product.get("source", ""),
        "title": product.get("title", ""),
        "category": product.get("category", ""),
        "price_usd": product.get("price_usd", 0),
        "cost_usd": product.get("cost_usd", 0),
        "rating": product.get("rating", 0),
        "review_count": product.get("review_count", 0),
        "image_url": product.get("image_url", ""),
        "product_url": product.get("product_url", ""),
        "supplier": product.get("supplier", ""),
        "shipping_days": product.get("shipping_days", 14),
    })


def _calculate_total_score(
    viral_score: float,
    trend_score: float,
    profit_score: float,
    quality_score: float,
    shipping_score: float,
) -> float:
    """가중 합산으로 종합 점수 산출 (0~100)"""
    total = (
        viral_score * (config.weight_viral / 100)
        + trend_score * (config.weight_trend / 100)
        + profit_score * (config.weight_profit / 100)
        + quality_score * (config.weight_quality / 100)
        + shipping_score * (config.weight_shipping / 100)
    )
    return round(min(100, total), 1)


def _export_results(top_products: list[dict], dashboard: "Dashboard") -> None:
    """상위 상품 Shopify + TikTok 익스포트"""
    shopify_exporter = ShopifyExporter()
    tiktok_exporter = TikTokExporter()

    # Shopify CSV
    shopify_path = shopify_exporter.export_batch(top_products)
    dashboard.print_info(f"Shopify CSV: {shopify_path}")

    # TikTok 콘텐츠 패키지
    tiktok_path = tiktok_exporter.export_batch(top_products)
    dashboard.print_info(f"TikTok 콘텐츠: {tiktok_path}")


def run_scheduler():
    """자동 스케줄 실행 (6시간마다)"""
    dashboard = Dashboard()
    interval_hours = config.scan_interval_hours
    dashboard.print_header(f"Product Radar 스케줄러 시작 | {interval_hours}시간마다 자동 스캔")

    while True:
        try:
            run_radar_scan(export=True)
        except KeyboardInterrupt:
            dashboard.print_info("스케줄러 중단됨")
            break
        except Exception as e:
            dashboard.print_error(f"스캔 오류: {e}")

        next_run = datetime.utcnow().replace(microsecond=0)
        dashboard.print_info(f"다음 스캔: {interval_hours}시간 후")
        time.sleep(interval_hours * 3600)


def main():
    parser = argparse.ArgumentParser(
        description="Product Radar - 24h급등 + 3d반복 포착 상품 레이더"
    )
    parser.add_argument(
        "--schedule", action="store_true",
        help="자동 스케줄 모드 (6시간마다 스캔)"
    )
    parser.add_argument(
        "--category", nargs="+",
        choices=list(FAST_SHIP_CATEGORIES.keys()),
        help="스캔할 카테고리 (기본: 전체)"
    )
    parser.add_argument(
        "--top", type=int, default=20,
        help="상위 N개 상품 출력 (기본: 20)"
    )
    parser.add_argument(
        "--export", action="store_true",
        help="결과를 Shopify CSV + TikTok JSON으로 익스포트"
    )
    parser.add_argument(
        "--min-score", type=float, default=None,
        help="최소 레이더 점수 (기본: 65.0)"
    )

    args = parser.parse_args()

    # DB 초기화
    init_db()

    if args.min_score is not None:
        config.min_total_score = args.min_score

    if args.schedule:
        run_scheduler()
    else:
        results = run_radar_scan(
            categories=args.category,
            export=args.export,
            top_n=args.top,
        )
        if not results:
            print("\n포착된 상품이 없습니다. 임계값을 낮추거나 카테고리를 변경해 보세요.")
            sys.exit(1)


if __name__ == "__main__":
    main()
