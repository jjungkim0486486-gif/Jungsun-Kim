"""
TikTok public search collector

Notes:
- TikTok blocks repeated headless access quickly
- human-like delays + user-agent rotation for defense
- Recommend clean VPS IP (home IP has high failure rate)
"""
import random
import time
from playwright.sync_api import sync_playwright, Page, TimeoutError as PWTimeout
from app.utils.logger import get_logger
from app.utils.retry import with_retry

log = get_logger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]


def collect_tiktok_search_results(
    keywords: list[str],
    max_items_per_keyword: int = 20,
) -> list[dict]:
    """Collect TikTok search results for the given keywords.

    Returns:
        list of {keyword, raw_text, url, source}
    """
    results: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1280, "height": 900},
            locale="en-US",
        )
        # Remove automation signal
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = context.new_page()

        for keyword in keywords:
            keyword_results = _collect_keyword(page, keyword, max_items_per_keyword)
            results.extend(keyword_results)
            log.info(f"[{keyword}] collected {len(keyword_results)} items")
            # Human-like delay between keywords
            time.sleep(random.uniform(4, 8))

        browser.close()

    log.info(f"Total collected: {len(results)} items")
    return results


@with_retry(max_attempts=3, base_delay=5.0, exceptions=(Exception,))
def _collect_keyword(page: Page, keyword: str, max_items: int) -> list[dict]:
    """Collect results for a single keyword. Auto-retries up to 3 times on failure."""
    encoded = keyword.replace(" ", "%20")
    url = f"https://www.tiktok.com/search?q={encoded}&type=video"

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60_000)
    except PWTimeout:
        log.warning(f"Page load timeout: {keyword}")
        return []

    # Wait for content to load
    time.sleep(random.uniform(3, 6))

    # Scroll down to load more content
    for _ in range(3):
        page.evaluate("window.scrollBy(0, window.innerHeight * 2)")
        time.sleep(random.uniform(1.5, 3))

    results = []
    selectors = [
        '[data-e2e="search_top-item"]',
        '[data-e2e="search_video-item"]',
        '.tiktok-x6y88p-DivItemContainerV2',
    ]

    cards = None
    for selector in selectors:
        cards = page.locator(selector)
        if cards.count() > 0:
            break

    if cards is None or cards.count() == 0:
        log.warning(f"No cards found for keyword: {keyword}")
        return []

    count = min(cards.count(), max_items)
    for i in range(count):
        try:
            card = cards.nth(i)
            raw_text = card.inner_text(timeout=3_000)
            link_el = card.locator("a[href*='/video/']").first
            link = link_el.get_attribute("href") if link_el.count() > 0 else None

            if not raw_text.strip():
                continue

            results.append({
                "keyword": keyword,
                "raw_text": raw_text,
                "url": link,
                "source": "tiktok_search",
            })
        except Exception as e:
            log.debug(f"card[{i}] failed: {e}")
            continue

    return results
