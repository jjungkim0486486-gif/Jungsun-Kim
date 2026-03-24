"""
Airtable client for trend_candidates table

Fixes vs original design:
- Added duplicate check: search by product_key before creating
- Upsert logic: update existing record instead of creating duplicate
- Proper error logging with status codes
- Retry on network errors
"""
import os
import requests
from datetime import datetime, timezone
from app.utils.logger import get_logger
from app.utils.retry import with_retry

log = get_logger(__name__)

BASE_ID = os.getenv("AIRTABLE_BASE_ID", "")
TABLE_NAME = "trend_candidates"
TOKEN = os.getenv("AIRTABLE_TOKEN", "")
BASE_URL = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_NAME}"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
    }


@with_retry(max_attempts=3, base_delay=2.0, exceptions=(requests.RequestException,))
def find_record_by_product_key(product_key: str) -> str | None:
    """Return Airtable record ID if product_key already exists, else None."""
    resp = requests.get(
        BASE_URL,
        headers=_headers(),
        params={
            "filterByFormula": f"{{product_key}} = '{product_key}'",
            "maxRecords": 1,
            "fields[]": "product_key",
        },
        timeout=15,
    )
    resp.raise_for_status()
    records = resp.json().get("records", [])
    return records[0]["id"] if records else None


@with_retry(max_attempts=3, base_delay=2.0, exceptions=(requests.RequestException,))
def create_record(item: dict) -> bool:
    """Insert a new record with approval_status = waiting_approval.

    Returns:
        True on success, False on failure.
    """
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "fields": {
            "product_key":        item["product_key"],
            "title":              item["title"],
            "source_platform":    item.get("source_platform", "TikTok"),
            "source_keyword":     item.get("source_keyword", ""),
            "source_url":         item.get("source_url", ""),
            "source_views":       item.get("source_views", 0),
            "source_likes":       item.get("source_likes", 0),
            "source_comments":    item.get("source_comments", 0),
            "source_caption":     item.get("caption", "")[:2000],
            "ai_is_product":      item.get("ai_is_product", False),
            "ai_product_score":   item.get("ai_product_score", 0),
            "ai_viral_score":     item.get("ai_viral_score", 0),
            "ai_margin_fit_score": item.get("ai_margin_fit_score", 0),
            "ai_risk_score":      item.get("ai_risk_score", 0),
            "overall_score":      item.get("overall_score", 0),
            "approval_status":    "waiting_approval",
            "created_at":         now,
            "updated_at":         now,
        }
    }
    resp = requests.post(BASE_URL, headers=_headers(), json=payload, timeout=30)
    if resp.status_code not in (200, 201):
        log.error(f"Airtable create failed [{resp.status_code}]: {resp.text[:200]}")
        return False
    log.info(f"Created record: {item['product_key']}")
    return True


@with_retry(max_attempts=3, base_delay=2.0, exceptions=(requests.RequestException,))
def update_record(record_id: str, item: dict) -> bool:
    """Update an existing record's scores (keeps approval_status as-is)."""
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "fields": {
            "source_views":        item.get("source_views", 0),
            "source_likes":        item.get("source_likes", 0),
            "source_comments":     item.get("source_comments", 0),
            "ai_product_score":    item.get("ai_product_score", 0),
            "ai_viral_score":      item.get("ai_viral_score", 0),
            "ai_margin_fit_score": item.get("ai_margin_fit_score", 0),
            "ai_risk_score":       item.get("ai_risk_score", 0),
            "overall_score":       item.get("overall_score", 0),
            "updated_at":          now,
        }
    }
    resp = requests.patch(
        f"{BASE_URL}/{record_id}",
        headers=_headers(),
        json=payload,
        timeout=30,
    )
    if resp.status_code != 200:
        log.error(f"Airtable update failed [{resp.status_code}]: {resp.text[:200]}")
        return False
    log.info(f"Updated existing record: {record_id}")
    return True


def upsert_record(item: dict) -> bool:
    """Create if product_key is new, update scores if it already exists.

    This prevents duplicate rows from accumulating night after night.
    """
    product_key = item.get("product_key", "")
    if not product_key:
        log.warning("upsert_record called with empty product_key, skipping")
        return False

    existing_id = find_record_by_product_key(product_key)
    if existing_id:
        log.debug(f"product_key '{product_key}' already exists -> update")
        return update_record(existing_id, item)
    return create_record(item)


@with_retry(max_attempts=3, base_delay=2.0, exceptions=(requests.RequestException,))
def fetch_waiting_approval(min_score: float = 65.0) -> list[dict]:
    """Fetch records with approval_status = waiting_approval, sorted by overall_score desc.

    Used by morning_digest to build the review summary.
    """
    resp = requests.get(
        BASE_URL,
        headers=_headers(),
        params={
            "filterByFormula": "AND({approval_status}='waiting_approval', {overall_score}>="
                               + str(min_score) + ")",
            "sort[0][field]": "overall_score",
            "sort[0][direction]": "desc",
            "maxRecords": 50,
        },
        timeout=15,
    )
    resp.raise_for_status()
    records = resp.json().get("records", [])
    return [r["fields"] for r in records]
