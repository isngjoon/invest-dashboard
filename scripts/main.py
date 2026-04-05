"""
Main pipeline orchestrator
- Collects data (prices, disclosures, news)
- Runs AI analysis
- Sends Telegram alerts
- Saves data.json for dashboard
"""
import os
import sys
import json
import hashlib
from datetime import datetime

# Add scripts dir to path
sys.path.insert(0, os.path.dirname(__file__))

from config import PORTFOLIO
from price_collector import collect_all_prices
from config import DART_WATCHLIST
from dart_collector import collect_all_disclosures
from news_collector import collect_all_news
from ai_analyzer import analyze_disclosures, analyze_news, generate_morning_briefing
from telegram_bot import (
    send_message, send_portfolio_summary,
    format_disclosure_alert, format_news_alert,
    format_price_alert, format_morning_briefing,
)


DATA_DIR = os.environ.get("DATA_DIR", "data")
SENT_CACHE = os.path.join(DATA_DIR, "sent_cache.json")


def load_sent_cache() -> set:
    """이미 전송된 항목 캐시 로드"""
    if os.path.exists(SENT_CACHE):
        with open(SENT_CACHE) as f:
            return set(json.load(f))
    return set()


def save_sent_cache(cache: set):
    """전송 캐시 저장"""
    with open(SENT_CACHE, "w") as f:
        json.dump(list(cache)[-500:], f)  # 최근 500개만 유지


def item_hash(item: dict) -> str:
    """항목 고유 해시"""
    key = json.dumps(item, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(key.encode()).hexdigest()[:12]


def run_pipeline(mode: str = "full"):
    """
    mode:
    - "full": 전체 실행 (데이터수집 + AI분석 + 알림 + 대시보드)
    - "data_only": 데이터수집 + 대시보드만 (AI 비용 절약)
    - "briefing": 모닝 브리핑만
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    sent_cache = load_sent_cache()

    print(f"[{datetime.now().isoformat()}] Pipeline start (mode={mode})")

    # === Step 1: Collect prices ===
    print("[1/5] Collecting prices...")
    prices = collect_all_prices(PORTFOLIO)
    print(f"  KR: {len(prices.get('kr', []))} stocks")
    print(f"  US: {len(prices.get('us', []))} stocks")
    print(f"  Crypto: {len(prices.get('crypto', []))} tokens")

    # === Step 2: Collect disclosures ===
    print("[2/5] Collecting DART disclosures...")
    disclosures = collect_all_disclosures(DART_WATCHLIST, days=3)
    print(f"  Found {len(disclosures)} disclosures")

    # === Step 3: Collect news ===
    print("[3/5] Collecting news...")
    news = collect_all_news(PORTFOLIO)
    total_articles = sum(len(v.get("articles", [])) for v in news.values())
    print(f"  Found {total_articles} articles")

    # === Step 4: AI Analysis (if not data_only) ===
    analyzed_disclosures = disclosures
    analyzed_news = news

    if mode in ("full", "briefing"):
        print("[4/5] Running AI analysis...")

        if mode == "briefing":
            briefing = generate_morning_briefing(prices, disclosures, news)
            if briefing:
                msg = format_morning_briefing(briefing)
                if msg:
                    send_message(msg)
                    print("  Morning briefing sent!")
            # Save briefing to data
            with open(os.path.join(DATA_DIR, "briefing.json"), "w") as f:
                json.dump(briefing, f, ensure_ascii=False, indent=2)

        if mode == "full":
            # Analyze new disclosures only
            new_disclosures = [
                d for d in disclosures if item_hash(d) not in sent_cache
            ]
            if new_disclosures:
                analyzed_disclosures = analyze_disclosures(new_disclosures, max_items=3)
                print(f"  Analyzed {len(analyzed_disclosures)} disclosures")

            # Analyze new important news
            analyzed_news = analyze_news(news, max_per_ticker=1)
            print(f"  Analyzed news for {len(analyzed_news)} tickers")
    else:
        print("[4/5] Skipping AI analysis (data_only mode)")

    # === Step 5: Send Telegram alerts ===
    print("[5/5] Sending alerts...")

    # Price surge alerts (±5%)
    for market in ["kr", "us"]:
        for stock in prices.get(market, []):
            if "error" in stock:
                continue
            if abs(stock.get("change_pct", 0)) >= 5:
                h = f"price_{stock['ticker']}_{datetime.now().strftime('%Y%m%d')}"
                if h not in sent_cache:
                    msg = format_price_alert(stock)
                    send_message(msg)
                    sent_cache.add(h)
                    print(f"  Sent price alert: {stock['ticker']}")

    # Disclosure alerts
    if mode == "full":
        for d in analyzed_disclosures:
            h = item_hash({"rcept_no": d.get("rcept_no", "")})
            if h not in sent_cache:
                msg = format_disclosure_alert(d)
                send_message(msg)
                sent_cache.add(h)
                print(f"  Sent disclosure: {d.get('title', '')[:30]}")

        # News alerts (high urgency only)
        for ticker, data in analyzed_news.items():
            for article in data.get("articles", []):
                ai = article.get("ai_analysis", {}) or {}
                if ai.get("urgency") == "high":
                    h = item_hash({"title": article.get("title", "")})
                    if h not in sent_cache:
                        msg = format_news_alert(ticker, data.get("name", ""), article)
                        send_message(msg)
                        sent_cache.add(h)
                        print(f"  Sent news: {article.get('title', '')[:30]}")

    save_sent_cache(sent_cache)

    # === Save dashboard data ===
    dashboard_data = {
        "prices": prices,
        "disclosures": analyzed_disclosures[:20],
        "news": {
            k: {
                "name": v.get("name", ""),
                "articles": v.get("articles", [])[:3],
            }
            for k, v in analyzed_news.items()
        },
        "portfolio": {
            "kr": PORTFOLIO["kr"],
            "us": PORTFOLIO["us"],
            "crypto": PORTFOLIO["crypto"],
        },
        "updated_at": datetime.now().isoformat(),
    }

    with open(os.path.join(DATA_DIR, "dashboard.json"), "w") as f:
        json.dump(dashboard_data, f, ensure_ascii=False, indent=2)

    print(f"[DONE] Dashboard data saved to {DATA_DIR}/dashboard.json")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"
    run_pipeline(mode)
