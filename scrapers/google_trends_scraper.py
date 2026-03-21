"""
Google Trends 스크래퍼
- 상품 키워드의 24시간 급등 감지
- 3일 연속 트렌드 데이터 수집
- pytrends 활용
"""

import time
import random
from datetime import datetime, timedelta
from typing import Optional

try:
    from pytrends.request import TrendReq
    PYTRENDS_AVAILABLE = True
except ImportError:
    PYTRENDS_AVAILABLE = False

from config import config

# 인메모리 캐시: (keyword, timeframe, geo) → data
_trends_cache: dict[tuple, list[dict]] = {}


def fetch_keyword_interest(
    keywords: list[str],
    timeframe: str = "now 1-d",
    geo: str = "US",
) -> dict[str, list[dict]]:
    """
    Google Trends 키워드 관심도 수집
    timeframe: 'now 1-d' (24h), 'now 7-d' (7일), 'today 3-m' (3개월)
    """
    if not PYTRENDS_AVAILABLE:
        return _simulate_keyword_interest(keywords, timeframe)

    # 캐시 히트 확인
    results = {}
    uncached = []
    for kw in keywords:
        key = (kw, timeframe, geo)
        if key in _trends_cache:
            results[kw] = _trends_cache[key]
        else:
            uncached.append(kw)

    if not uncached:
        return results

    try:
        pytrends = TrendReq(hl="en-US", tz=360, timeout=(10, 25))
        # pytrends는 한 번에 최대 5개 키워드
        for i in range(0, len(uncached), 5):
            batch = uncached[i:i + 5]
            batch_data = _fetch_batch_with_retry(pytrends, batch, timeframe, geo)
            for kw, data in batch_data.items():
                _trends_cache[(kw, timeframe, geo)] = data
                results[kw] = data
            if i + 5 < len(uncached):
                time.sleep(5.0)  # 배치 간 충분한 대기
        return results
    except Exception as e:
        print(f"[Google Trends Error] {e}")
        sim = _simulate_keyword_interest(uncached, timeframe)
        results.update(sim)
        return results


def _fetch_batch_with_retry(
    pytrends,
    batch: list[str],
    timeframe: str,
    geo: str,
    max_retries: int = 4,
) -> dict[str, list[dict]]:
    """429 에러 시 지수 백오프로 재시도"""
    delay = 10  # 초기 대기(초)
    for attempt in range(max_retries):
        try:
            pytrends.build_payload(batch, timeframe=timeframe, geo=geo)
            df = pytrends.interest_over_time()
            if df is None or df.empty:
                return {}
            return {
                kw: [
                    {"timestamp": str(ts), "value": int(val)}
                    for ts, val in df[kw].items()
                ]
                for kw in batch if kw in df.columns
            }
        except Exception as e:
            err_str = str(e)
            if "429" in err_str and attempt < max_retries - 1:
                print(f"[Google Trends 429] {delay}초 대기 후 재시도 ({attempt + 1}/{max_retries})")
                time.sleep(delay)
                delay *= 2
            else:
                print(f"[Google Trends Error] {e}")
                return _simulate_keyword_interest(batch, timeframe)
    return _simulate_keyword_interest(batch, timeframe)


def detect_24h_spike(
    keyword: str,
    spike_threshold: float = 2.0,
    geo: str = "US",
) -> dict:
    """
    24시간 급등 감지
    spike_ratio > threshold이면 급등으로 판단
    7d 데이터 한 번만 요청해서 24h + 기준선 모두 추출 (캐시 재활용)
    """
    # 7d 데이터 하나로 24h 최근 구간과 기준선 모두 추출
    data_7d = fetch_keyword_interest([keyword], timeframe="now 7-d", geo=geo)

    if keyword not in data_7d:
        return {"keyword": keyword, "is_spike": False, "spike_ratio": 0}

    all_values = data_7d[keyword]
    # 7d = 약 168포인트, 마지막 ~24포인트가 최근 24h
    recent_cutoff = max(1, len(all_values) - 24)
    recent_values = [d["value"] for d in all_values[recent_cutoff:]]
    baseline_values = [d["value"] for d in all_values[:recent_cutoff - 24]]  # 최근 48h 제외

    if not recent_values or not baseline_values:
        return {"keyword": keyword, "is_spike": False, "spike_ratio": 0}

    recent_avg = sum(recent_values) / len(recent_values)
    baseline_avg = sum(baseline_values) / len(baseline_values) if baseline_values else 1

    spike_ratio = recent_avg / max(baseline_avg, 1)
    is_spike = spike_ratio >= spike_threshold and recent_avg >= config.spike.volume_threshold

    return {
        "keyword": keyword,
        "is_spike": is_spike,
        "spike_ratio": round(spike_ratio, 2),
        "recent_avg": round(recent_avg, 1),
        "baseline_avg": round(baseline_avg, 1),
        "peak_value": max(recent_values) if recent_values else 0,
        "checked_at": datetime.utcnow().isoformat(),
    }


def get_3day_trend_consistency(
    keyword: str,
    min_daily_value: int = 40,
    geo: str = "US",
) -> dict:
    """
    3일 연속 트렌드 일관성 분석
    매일 일정 수준 이상 유지되어야 진짜 트렌드
    """
    data = fetch_keyword_interest([keyword], timeframe="now 7-d", geo=geo)

    if keyword not in data:
        return {"keyword": keyword, "is_consistent": False, "days_above_threshold": 0}

    values = [d["value"] for d in data[keyword]]

    # 일별 최대값 계산 (24개 포인트 = 7일 * 시간당 약 3.4개)
    daily_max = []
    chunk_size = len(values) // 7 if len(values) >= 7 else 1
    for i in range(7):
        chunk = values[i * chunk_size: (i + 1) * chunk_size]
        daily_max.append(max(chunk) if chunk else 0)

    # 최근 3일 분석
    recent_3_days = daily_max[-3:] if len(daily_max) >= 3 else daily_max
    days_above = sum(1 for v in recent_3_days if v >= min_daily_value)
    is_consistent = days_above >= config.repeat.repeat_days

    consistency_score = days_above / max(len(recent_3_days), 1)

    return {
        "keyword": keyword,
        "is_consistent": is_consistent,
        "days_above_threshold": days_above,
        "consistency_score": round(consistency_score, 2),
        "daily_values": daily_max,
        "recent_3_days": recent_3_days,
        "avg_7d": round(sum(values) / len(values), 1) if values else 0,
        "checked_at": datetime.utcnow().isoformat(),
    }


def get_related_queries(keyword: str, geo: str = "US") -> list[str]:
    """연관 검색어 수집 (상품 확장용)"""
    if not PYTRENDS_AVAILABLE:
        return []

    try:
        pytrends = TrendReq(hl="en-US", tz=360, timeout=(10, 25))
        pytrends.build_payload([keyword], timeframe="now 7-d", geo=geo)
        related = pytrends.related_queries()
        rising = related.get(keyword, {}).get("rising", None)
        if rising is not None and not rising.empty:
            return rising["query"].head(10).tolist()
    except Exception:
        pass
    return []


def _simulate_keyword_interest(
    keywords: list[str],
    timeframe: str,
) -> dict[str, list[dict]]:
    """
    pytrends 없을 때 시뮬레이션 데이터
    실제 운영 시 pytrends 설치 필수
    """
    results = {}
    points = 72 if "1-d" in timeframe else 168  # 24h=72포인트, 7d=168포인트

    now = datetime.utcnow()
    for kw in keywords:
        base = random.randint(30, 80)
        series = []

        for i in range(points):
            ts = now - timedelta(hours=points - i)
            # 최근 24시간에 스파이크 시뮬레이션
            if i > points * 0.85 and random.random() > 0.6:
                value = min(100, int(base * random.uniform(1.5, 4.0)))
            else:
                value = max(0, int(base + random.gauss(0, 10)))

            series.append({
                "timestamp": ts.isoformat(),
                "value": value,
            })
        results[kw] = series

    return results
