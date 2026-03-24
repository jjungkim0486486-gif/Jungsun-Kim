"""
Central config - loaded from environment variables (.env or GitHub Secrets)
"""
import os
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@dataclass
class Settings:
    # --- OpenAI ---
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))

    # --- Airtable ---
    airtable_token: str = field(default_factory=lambda: os.getenv("AIRTABLE_TOKEN", ""))
    airtable_base_id: str = field(default_factory=lambda: os.getenv("AIRTABLE_BASE_ID", ""))

    # --- Scan settings ---
    max_items_per_keyword: int = 20
    min_overall_score: float = 65.0

    # --- TikTok search keywords (V1 starter set) ---
    keywords: list[str] = field(default_factory=lambda: [
        "tiktok made me buy it",
        "viral product",
        "amazon finds",
        "kitchen gadget",
        "home finds",
        "beauty find",
        "car gadget",
        "summer gadget",
        "travel gadget",
        "cleaning hack",
    ])


settings = Settings()
