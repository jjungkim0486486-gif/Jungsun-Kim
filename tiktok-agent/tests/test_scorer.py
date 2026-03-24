"""Unit tests for ai_scorer JSON parsing (no OpenAI calls)"""
from app.scorers.ai_scorer import _parse_json_response


def test_parse_clean_json():
    raw = '{"is_product": true, "product_score": 80, "viral_score": 70, "margin_fit_score": 60, "risk_score": 20, "product_name": "LED Desk Lamp", "reason": "clear product"}'
    result = _parse_json_response(raw)
    assert result["is_product"] is True
    assert result["product_score"] == 80


def test_parse_json_with_prose():
    # Model sometimes wraps JSON in text
    raw = 'Here is the evaluation:\n{"is_product": false, "product_score": 10, "viral_score": 50, "margin_fit_score": 30, "risk_score": 80, "product_name": "", "reason": "not a product"}\nHope this helps.'
    result = _parse_json_response(raw)
    assert result["is_product"] is False
    assert result["risk_score"] == 80


def test_parse_invalid_returns_safe_default():
    raw = "Sorry, I cannot evaluate this."
    result = _parse_json_response(raw)
    assert result["is_product"] is False
    assert result["risk_score"] == 100
