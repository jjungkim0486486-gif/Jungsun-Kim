"""
Candidate parser - extract structured data from raw TikTok card text
"""
import re
from app.utils.logger import get_logger

log = get_logger(__name__)

# Keywords that signal a shoppable product video
PRODUCT_HINTS = [
    "buy", "shop", "amazon", "find", "gadget", "tool", "must have",
    "need this", "made me buy", "product", "cleaning", "kitchen",
    "portable", "under $", "link in bio", "order", "get yours",
    "obsessed", "game changer", "life hack", "where to buy",
]


def parse_candidate(item: dict) -> dict:
    """Parse raw card text into structured candidate dict.

    Args:
        item: {keyword, raw_text, url, source}

    Returns:
        Structured candidate dict with extracted metrics.
    """
    raw = item.get("raw_text", "")
    lines = [x.strip() for x in raw.split("\n") if x.strip()]

    title = lines[0] if lines else ""
    stats_text = " ".join(lines[:8]).lower()

    views = _extract_metric(stats_text, "view")
    likes = _extract_metric(stats_text, "like")
    comments = _extract_metric(stats_text, "comment")
    shares = _extract_metric(stats_text, "share")

    product_signal = any(h in stats_text for h in PRODUCT_HINTS)
    signal_count = sum(1 for h in PRODUCT_HINTS if h in stats_text)

    return {
        "title": title,
        "caption": raw[:1000],
        "source_keyword": item.get("keyword", ""),
        "source_url": item.get("url", ""),
        "source_platform": "TikTok",
        "source_platform_type": item.get("source", "tiktok_search"),
        "source_views": views,
        "source_likes": likes,
        "source_comments": comments,
        "source_shares": shares,
        # Engagement rate proxy (likes / views)
        "engagement_rate": round(likes / max(views, 1), 4),
        "product_signal": product_signal,
        "product_signal_strength": signal_count,  # 0~N: stronger = more hints matched
    }


def _extract_metric(text: str, kind: str) -> int:
    """Extract numeric metric (views/likes/comments/shares) from text.

    Handles formats: '1.2M views', '45K likes', '300 comments'
    """
    pattern = r'(\d+(?:[.,]\d+)?)\s*([km]?)\s*' + re.escape(kind)
    m = re.search(pattern, text)
    if not m:
        return 0
    num_str = m.group(1).replace(",", ".")
    try:
        num = float(num_str)
    except ValueError:
        return 0
    unit = m.group(2).lower()
    if unit == "k":
        num *= 1_000
    elif unit == "m":
        num *= 1_000_000
    return int(num)
