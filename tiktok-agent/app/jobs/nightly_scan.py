"""
Nightly scan job - runs at 01:00 UTC

Pipeline:
  [1] Load keywords
  [2] Collect TikTok search + Creative Center signals
  [3] Parse candidates
  [4] Filter by product_signal
  [5] AI score (GPT-4o-mini)
  [6] Calculate overall_score
  [7] Dedupe by product_key
  [8] Upsert to Airtable (skip if score < threshold)

Success criteria (V1 pass gate):
  - raw collected >= 30
  - AI-passed candidates >= 5
  - Airtable saved >= 3
"""
import sys
from app.collectors.tiktok_search import collect_tiktok_search_results
from app.collectors.creative_center import collect_creative_center_trends
from app.extractors.candidate_parser import parse_candidate
from app.scorers.ai_scorer import score_candidate
from app.utils.normalizer import make_product_key
from app.utils.dedupe import dedupe_candidates
from app.db.airtable_client import upsert_record
from app.utils.logger import get_logger
from app.config import settings

log = get_logger(__name__)

# --- Score weights ---
W_PRODUCT = 0.35
W_VIRAL   = 0.35
W_MARGIN  = 0.20
W_RISK    = 0.10   # subtracted


def calculate_overall_score(ai: dict) -> float:
    """Weighted overall score (0-100). Risk is penalised."""
    score = (
        ai["product_score"] * W_PRODUCT
        + ai["viral_score"]  * W_VIRAL
        + ai["margin_fit_score"] * W_MARGIN
        - ai["risk_score"]   * W_RISK
    )
    return round(max(0, min(100, score)), 1)


def main() -> None:
    log.info("=== Nightly scan START ===")

    # --- Step 1: Collect ---
    log.info("[1/4] Collecting TikTok signals...")
    search_items = collect_tiktok_search_results(
        settings.keywords,
        max_items_per_keyword=settings.max_items_per_keyword,
    )
    cc_items = collect_creative_center_trends(max_items=30)
    raw_items = search_items + cc_items
    log.info(f"Raw collected: {len(raw_items)} (search={len(search_items)}, cc={len(cc_items)})")

    # V1 failure gate #1
    if len(raw_items) == 0:
        log.error("FAIL: 0 raw items collected. Check TikTok scraper / network.")
        sys.exit(1)

    # --- Step 2: Parse ---
    log.info("[2/4] Parsing candidates...")
    parsed = []
    for item in raw_items:
        candidate = parse_candidate(item)
        # Pre-filter: must have at least weak product signal
        if not candidate["product_signal"]:
            continue
        parsed.append(candidate)
    log.info(f"Parsed with product signal: {len(parsed)}")

    # --- Step 3: AI score ---
    log.info("[3/4] AI scoring with GPT-4o-mini...")
    scored = []
    for candidate in parsed:
        try:
            ai = score_candidate(candidate)
        except Exception as e:
            log.warning(f"Score failed for '{candidate['title'][:50]}': {e}")
            continue

        if not ai.get("is_product", False):
            continue

        overall = calculate_overall_score(ai)
        candidate.update({
            "product_key":       make_product_key(candidate["title"]),
            "ai_is_product":     ai["is_product"],
            "ai_product_score":  ai["product_score"],
            "ai_viral_score":    ai["viral_score"],
            "ai_margin_fit_score": ai["margin_fit_score"],
            "ai_risk_score":     ai["risk_score"],
            "ai_product_name":   ai.get("product_name", ""),
            "ai_reason":         ai.get("reason", ""),
            "overall_score":     overall,
        })
        scored.append(candidate)

    log.info(f"AI-passed candidates: {len(scored)}")

    # V1 failure gate #2
    if len(scored) < 5:
        log.warning(f"WARNING: Only {len(scored)} AI-passed candidates (target >= 5).")

    # --- Step 4: Dedupe + Save ---
    log.info("[4/4] Deduplicating and saving to Airtable...")
    final = dedupe_candidates(scored)
    log.info(f"After dedup: {len(final)} candidates")

    saved = 0
    skipped = 0
    for item in final:
        if item["overall_score"] < settings.min_overall_score:
            skipped += 1
            continue
        ok = upsert_record(item)
        if ok:
            saved += 1

    log.info(f"Airtable saved/updated: {saved} | skipped (score too low): {skipped}")

    # --- V1 pass/fail verdict ---
    log.info("--- V1 SUCCESS CRITERIA ---")
    raw_ok  = len(raw_items) >= 30
    cand_ok = len(scored)   >= 5
    save_ok = saved         >= 3
    log.info(f"  Raw >= 30:          {'PASS' if raw_ok  else 'FAIL'} ({len(raw_items)})")
    log.info(f"  AI candidates >= 5: {'PASS' if cand_ok else 'FAIL'} ({len(scored)})")
    log.info(f"  Saved >= 3:         {'PASS' if save_ok else 'FAIL'} ({saved})")
    log.info("=== Nightly scan END ===")

    if not save_ok:
        sys.exit(1)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    main()
