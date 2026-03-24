"""Unit tests for candidate_parser (no network required)"""
from app.extractors.candidate_parser import parse_candidate, _extract_metric


def test_extract_metric_views():
    assert _extract_metric("1.2m views 45k likes", "view") == 1_200_000


def test_extract_metric_likes():
    assert _extract_metric("1.2m views 45k likes", "like") == 45_000


def test_extract_metric_zero():
    assert _extract_metric("nothing here", "view") == 0


def test_parse_candidate_product_signal():
    item = {
        "keyword": "viral product",
        "raw_text": "Amazing kitchen gadget\n1.2M views\n45K likes\nbuy this now",
        "url": "https://www.tiktok.com/video/123",
        "source": "tiktok_search",
    }
    result = parse_candidate(item)
    assert result["product_signal"] is True
    assert result["source_views"] == 1_200_000
    assert result["source_likes"] == 45_000
    assert result["title"] == "Amazing kitchen gadget"


def test_parse_candidate_no_signal():
    item = {
        "keyword": "dance trend",
        "raw_text": "cool dance moves\n500 views",
        "url": None,
        "source": "tiktok_search",
    }
    result = parse_candidate(item)
    assert result["product_signal"] is False
