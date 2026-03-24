# TikTok Product Radar - V1

Overnight TikTok signal collection -> GPT scoring -> Airtable approval queue.

## What V1 does

| Time | Action |
|------|--------|
| 01:00 UTC | Collect TikTok search + Creative Center signals, score with GPT-4o-mini, save to Airtable |
| 08:00 UTC | Print morning digest (top candidates waiting for your approval) |
| Morning | You open Airtable, filter `approval_status = waiting_approval`, approve or reject |

## V1 success criteria

- Raw items collected >= 30
- AI-passed candidates >= 5  
- Airtable records saved >= 3

## Setup

```bash
cd tiktok-agent
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
# Fill in OPENAI_API_KEY, AIRTABLE_TOKEN, AIRTABLE_BASE_ID
```

## Run manually

```bash
python -m app.jobs.nightly_scan   # full overnight scan
python -m app.jobs.morning_digest  # view today's candidates
```

## Run tests

```bash
python -m pytest tests/ -v
```

## GitHub Actions (automatic schedule)

1. Go to **Settings -> Secrets and variables -> Actions**
2. Add three secrets:
   - `OPENAI_API_KEY`
   - `AIRTABLE_TOKEN`
   - `AIRTABLE_BASE_ID`
3. Workflows run automatically:
   - `nightly_scan.yml` at 01:00 UTC
   - `morning_digest.yml` at 08:00 UTC

## Airtable table: `trend_candidates`

| Column | Type | Description |
|--------|------|-------------|
| product_key | Single line | Unique slug (dedupe key) |
| title | Single line | Video title |
| source_platform | Single line | TikTok |
| source_keyword | Single line | Search keyword used |
| source_url | URL | TikTok video URL |
| source_views | Number | View count |
| source_likes | Number | Like count |
| source_comments | Number | Comment count |
| source_caption | Long text | Full raw caption |
| ai_is_product | Checkbox | GPT confirmed product |
| ai_product_score | Number | 0-100 |
| ai_viral_score | Number | 0-100 |
| ai_margin_fit_score | Number | 0-100 |
| ai_risk_score | Number | 0-100 (higher = more risk) |
| overall_score | Number | Weighted final score |
| approval_status | Single select | new / waiting_approval / approved / rejected |
| approval_note | Long text | Your notes |
| created_at | Date | First seen |
| updated_at | Date | Last score update |

## Score formula

```
overall_score = product_score * 0.35
              + viral_score   * 0.35
              + margin_fit    * 0.20
              - risk_score    * 0.10
```

## V1.5 roadmap (after V1 is proven)

- approved products -> CJ Dropshipping search -> cost/shipping match
- Shopify auto-upload
- Order automation

## Key bug fixes vs original design

| Bug | Fix |
|-----|-----|
| `client.responses.create` | `client.chat.completions.create` |
| `model='gpt-5-mini'` | `model='gpt-4o-mini'` |
| `input=prompt` | `messages=[{role, content}]` |
| No duplicate check | `upsert_record()` checks before insert |
| No Creative Center | `creative_center.py` implemented |
| No morning digest | `morning_digest.py` implemented |
| headless + no delay = instant block | Human delays + UA rotation + retry |
