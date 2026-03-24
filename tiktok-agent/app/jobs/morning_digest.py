"""
Morning digest job - runs at 08:00 UTC

Fetches waiting_approval candidates from Airtable and prints a
human-readable summary so you can quickly approve / reject.

No automation here: the output is read-only. You approve in Airtable.
"""
from app.db.airtable_client import fetch_waiting_approval
from app.utils.logger import get_logger
from app.config import settings
from datetime import datetime, timezone

log = get_logger(__name__)

SEPARATOR = "=" * 60


def main() -> None:
    log.info("=== Morning digest START ===")
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    candidates = fetch_waiting_approval(min_score=settings.min_overall_score)

    print(f"\n{SEPARATOR}")
    print(f"  TIKTOK PRODUCT RADAR - Morning Digest")
    print(f"  {now_utc}")
    print(SEPARATOR)

    if not candidates:
        print("  No candidates waiting for approval today.")
        print(f"  (min_score filter: {settings.min_overall_score})")
        print(SEPARATOR)
        return

    print(f"  {len(candidates)} candidates waiting for your review")
    print(f"  Sorted by overall_score DESC | min_score={settings.min_overall_score}")
    print(SEPARATOR)

    for i, c in enumerate(candidates, 1):
        score     = c.get("overall_score", 0)
        title     = c.get("title", "(no title)")[:70]
        keyword   = c.get("source_keyword", "")
        views     = _fmt_num(c.get("source_views", 0))
        likes     = _fmt_num(c.get("source_likes", 0))
        p_score   = c.get("ai_product_score", 0)
        v_score   = c.get("ai_viral_score", 0)
        m_score   = c.get("ai_margin_fit_score", 0)
        r_score   = c.get("ai_risk_score", 0)
        url       = c.get("source_url", "")

        grade = _grade(score)
        print(f"\n  [{i:02d}] {grade} {score:.1f}/100  |  {title}")
        print(f"       keyword: {keyword}")
        print(f"       views: {views}  likes: {likes}")
        print(f"       scores -> product:{p_score} viral:{v_score} margin:{m_score} risk:{r_score}")
        if url:
            print(f"       url: {url}")

    print(f"\n{SEPARATOR}")
    print("  ACTION: Go to Airtable -> filter approval_status = waiting_approval")
    print("          Sort by overall_score DESC -> Approve or Reject each row")
    print(SEPARATOR + "\n")
    log.info(f"Digest complete: {len(candidates)} candidates shown")


def _fmt_num(n: int) -> str:
    """Format large numbers: 1500000 -> '1.5M'"""
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


def _grade(score: float) -> str:
    """Emoji grade badge based on score."""
    if score >= 85:
        return "[A+]"
    if score >= 75:
        return "[A ]"
    if score >= 65:
        return "[B ]"
    return "[C ]"


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    main()
