# 🎯 Product Radar — 24h급등 + 3d반복 포착 상품 레이더

쇼피파이 + 틱톡 드롭쉬핑을 위한 **바이럴 상품 자동 탐지 시스템**

## 핵심 기능

| 기능 | 설명 |
|------|------|
| ⚡ **24h 급등 감지** | Google Trends + TikTok 영상 수 급증 복합 시그널 |
| 🔁 **3d 반복 포착** | 3일 연속 트렌드 점수 유지 → 진성 트렌드 확정 |
| 🛡️ **품질 필터** | 평점 4.0+, 리뷰 50+, 불량률 3% 이하 |
| 🚀 **7일 배송 필터** | CJ Dropshipping, Spocket, AliExpress ePacket |
| 💰 **수익성 분석** | 마진 40%+, 최적 판매가 자동 산출, ROAS 예측 |
| 📊 **바이럴 스코어** | TikTok 조회수·참여율·WoW Factor 종합 평가 |
| 🛒 **Shopify 익스포트** | CSV 또는 API 직접 등록 (SEO 최적화 포함) |
| 🎬 **TikTok 콘텐츠** | 영상 훅·스크립트·해시태그 전략 자동 생성 |

---

## 빠른 시작

### 1. 설치

```bash
# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정
cp .env.example .env
# .env 파일에 API 키 입력
```

### 2. 실행

```bash
# 전체 카테고리 1회 스캔 (API 키 없어도 데모 모드로 동작)
python main.py

# 특정 카테고리만 스캔
python main.py --category beauty gadgets

# 결과를 Shopify CSV + TikTok JSON으로 익스포트
python main.py --export

# 6시간마다 자동 스캔
python main.py --schedule

# 상위 10개, 임계값 70점 이상만
python main.py --top 10 --min-score 70
```

---

## 점수 시스템 (100점 만점)

```
종합 점수 = 바이럴(30%) + 트렌드(25%) + 수익성(20%) + 품질(15%) + 배송(10%)
```

### 바이럴 점수 (0~100)
- TikTok 해시태그 조회수 (25점)
- UGC 영상 수 + 참여율 (20점)
- 카테고리 TikTok 적합도 (15점)
- Wow Factor / 시각적 임팩트 (20점)
- 문제 해결형 상품 여부 (20점)

### 트렌드 점수 (0~100)
- **24h 급등**: 기준값 대비 2배 이상 급등 시 확정
- **3d 반복**: 3일 연속 임계값 이상 유지
- Google Trends + TikTok 복합 시그널

### 수익성 점수 (0~100)
- 마진율 40% 이상 필수
- TikTok 충동구매 최적 가격대: $15~$35
- 예상 ROAS 3.0x 이상

---

## 출력 파일

| 파일 | 내용 |
|------|------|
| `data/exports/shopify_products_YYYYMMDD_HHmmss.csv` | Shopify 상품 업로드용 CSV |
| `data/exports/tiktok_content_YYYYMMDD_HHmmss.json` | TikTok 콘텐츠 전략 패키지 |
| `data/radar.db` | SQLite 상품 이력 DB |

### TikTok 콘텐츠 패키지 예시
```json
{
  "video_hooks": ["Wait— this Lip Oil actually works 😭", ...],
  "video_scripts": [{"type": "unboxing", "script": "..."}, ...],
  "hashtag_strategy": {
    "recommended_combo": ["#fyp", "#BeautyTok", "#TikTokMadeMeBuyIt", ...]
  },
  "caption_templates": ["POV: TikTok made me buy this..."],
  "content_calendar": [{"day": 1, "content_type": "Unboxing", "best_time": "7PM-9PM"}, ...]
}
```

---

## API 키 발급 가이드

### AliExpress Affiliate API
1. [AliExpress Portals](https://portals.aliexpress.com/) 접속
2. Developer Center → Create App
3. App Key와 App Secret 복사

### TikTok for Business API
1. [TikTok Developers](https://developers.tiktok.com/) 접속
2. App 생성 → Creative Content API 신청
3. Access Token 복사

### Shopify Admin API
1. Shopify Admin → Settings → Apps → Develop Apps
2. Create App → Configure Admin API scopes
3. `write_products, read_products` 권한 체크
4. Access Token 복사

---

## 아키텍처

```
product_radar/
├── main.py                      # 메인 엔진 & CLI
├── config.py                    # 전체 설정
├── dashboard.py                 # 터미널 대시보드
│
├── scrapers/
│   ├── aliexpress_scraper.py    # AliExpress & CJ Dropshipping
│   ├── tiktok_scraper.py        # TikTok Creative Center
│   └── google_trends_scraper.py # Google Trends (pytrends)
│
├── analyzers/
│   ├── trend_analyzer.py        # 24h급등 + 3d반복 핵심 알고리즘
│   └── viral_scorer.py          # 바이럴 가능성 평가
│
├── filters/
│   ├── product_filter.py        # 품질 + 배송 필터
│   └── commercial_optimizer.py  # 수익성 분석 + 가격 최적화
│
├── exporters/
│   ├── shopify_exporter.py      # Shopify CSV/API 익스포트
│   └── tiktok_exporter.py       # TikTok 콘텐츠 패키지
│
└── storage/
    └── database.py              # SQLite 이력 관리
```

---

## 권장 운영 방식

1. **API 키 발급** → `.env` 파일 설정
2. **`--schedule` 모드**로 6시간마다 자동 스캔
3. **Shopify CSV** 다운로드 → 대량 업로드
4. **TikTok JSON**에서 콘텐츠 스크립트 복사 → 영상 촬영
5. 7일 후 판매 데이터 기반으로 **`config.py` 가중치 조정**

> **데모 모드**: API 키 없이도 실제적인 시뮬레이션 데이터로 전체 파이프라인 테스트 가능
