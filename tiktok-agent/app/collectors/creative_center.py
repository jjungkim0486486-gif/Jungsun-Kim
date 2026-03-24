"""
TikTok Creative Center trending ads collector

Creative Center provides official TikTok trending data without login.
URL: https://ads.tiktok.com/business/creativecenter/inspiration/topads/pc/en

Advantages over search scraping:
- Much lower block probability (official page)
- Already-proven products running live ads
- Includes category, industry, CTR signals
"""
import random
import time
from playwright.sync_api import sync_playwright, Page, TimeoutError as PWTimeout
from app.utils.logger import get_logger
from app.utils.retry import with_retry
from app.collectors.tiktok_search import USER_AGENTS

log = get_logger(__name__)

CREATIVE_CENTER_URL = (
    "https://ads.tiktok.com/business/creativecenter/inspiration/topads/pc/en"
)


def collect_creative_center_trends(max_items: int = 30) -> list[dict]:
    """Collect trending product videos from TikTok Creative Center Top Ads.

    Returns:
        list of {keyword, raw_text, url, source}
    """
    results: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1440, "height": 900},
            locale="en-US",
        )
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = context.new_page()
        results = _scrape_top_ads(page, max_items)
        browser.close()

    log.info(f"Creative Center collected: {len(results)} items")
    return results


@with_retry(max_attempts=3, base_delay=5.0)
def _scrape_top_ads(page: Page, max_items: int) -> list[dict]:
    try:
        page.goto(CREATIVE_CENTER_URL, wait_until="domcontentloaded", timeout=60_000)
    except PWTimeout:
        log.warning("Creative Center page load timeout")
        return []

    time.sleep(random.uniform(4, 7))

    # Scroll to load more ads
    for _ in range(4):
        page.evaluate("window.scrollBy(0, window.innerHeight * 2)")
        time.sleep(random.uniform(1.5, 2.5))

    results = []
    card_selectors = [
        '[class*="card-container"]',
        '[class*="TopAd"]',
        '[class*="creative-card"]',
        '[data-testid="card"]',
    ]

    cards = None
    for sel in card_selectors:
        cards = page.locator(sel)
        if cards.count() > 0:
            log.debug(f"Creative Center selector matched: {sel} ({cards.count()} items)")
            break

    if cards is None or cards.count() == 0:
        # Fallback: collect full page text
        log.warning("Creative Center card selector failed -> page text fallback")
        raw = page.inner_text("body")[:5000]
        return [{
            "keyword": "creative_center_trending",
            "raw_text": raw,
            "url": CREATIVE_CENTER_URL,
            "source": "creative_center",
        }]

    count = min(cards.count(), max_items)
    for i in range(count):
        try:
            card = cards.nth(i)
            raw_text = card.inner_text(timeout=3_000)
            if not raw_text.strip():
                continue

            link_el = card.locator("a").first
            link = link_el.get_attribute("href") if link_el.count() > 0 else CREATIVE_CENTER_URL

            results.append({
                "keyword": "creative_center_trending",
                "raw_text": raw_text,
                "url": link,
                "source": "creative_center",
            })
        except Exception as e:
            log.debug(f"Creative Center card[{i}] failed: {e}")
            continue

    return results
