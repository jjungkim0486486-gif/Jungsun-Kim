"""
AI scorer - GPT-4o-mini judges each candidate product

Fixes vs original design:
- client.responses.create -> client.chat.completions.create  (responses API does not exist)
- model='gpt-5-mini'      -> model='gpt-4o-mini'            (gpt-5-mini does not exist)
- input=prompt            -> messages=[{role,content}]       (correct Chat API format)
- Added JSON extraction fallback in case model adds prose around JSON
- Added retry decorator for API rate-limit / network errors
"""
import json
import re
from openai import OpenAI
from app.utils.logger import get_logger
from app.utils.retry import with_retry

log = get_logger(__name__)
client = OpenAI()  # Reads OPENAI_API_KEY from env automatically

SCORING_PROMPT = """
You are a TikTok dropshipping product expert. Evaluate whether the candidate below
is a real, sellable physical product that is going viral on TikTok.

Candidate:
  title:    {title}
  caption:  {caption}
  views:    {views}
  likes:    {likes}
  comments: {comments}
  keyword:  {keyword}
  source:   {source_type}

Scoring rules (0-100 each):
  product_score   - Is this a clear, tangible physical product? (100=obvious, 0=not a product)
  viral_score     - How viral/trending is the video signal? (views, likes, engagement velocity)
  margin_fit_score - Likely dropshippable with 40%+ margin? Consider price range $15-$80.
  risk_score      - Risk of returns, brand issues, safety concerns, copyright. HIGHER = more risk.

Return ONLY valid JSON, no other text:
{{
  "is_product": true,
  "product_score": 0,
  "viral_score": 0,
  "margin_fit_score": 0,
  "risk_score": 0,
  "product_name": "",
  "reason": ""
}}
"""


@with_retry(max_attempts=3, base_delay=2.0)
def score_candidate(candidate: dict) -> dict:
    """Score a single candidate using GPT-4o-mini.

    Returns:
        {
            is_product, product_score, viral_score,
            margin_fit_score, risk_score, product_name, reason
        }
    """
    prompt = SCORING_PROMPT.format(
        title=candidate.get("title", "")[:200],
        caption=candidate.get("caption", "")[:500],
        views=candidate.get("source_views", 0),
        likes=candidate.get("source_likes", 0),
        comments=candidate.get("source_comments", 0),
        keyword=candidate.get("source_keyword", ""),
        source_type=candidate.get("source_platform_type", "tiktok_search"),
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,   # Low temperature = consistent scoring
        max_tokens=300,
    )

    raw_text = response.choices[0].message.content or ""
    return _parse_json_response(raw_text)


def _parse_json_response(text: str) -> dict:
    """Extract JSON from model response. Handles prose wrapping around JSON."""
    # Try direct parse first
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # Extract first JSON block if model added extra text
    match = re.search(r'\{[\s\S]+\}', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    log.warning(f"Could not parse AI response as JSON: {text[:200]}")
    # Safe fallback: treat as non-product
    return {
        "is_product": False,
        "product_score": 0,
        "viral_score": 0,
        "margin_fit_score": 0,
        "risk_score": 100,
        "product_name": "",
        "reason": "parse_failed",
    }
