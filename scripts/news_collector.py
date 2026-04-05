"""
News collector - Google News RSS for stock-related news
"""
import json
import re
import requests
from datetime import datetime
from urllib.parse import quote


def fetch_news_for_ticker(query: str, max_results: int = 5) -> list[dict]:
    """Google News RSS로 종목 관련 뉴스 수집"""
    encoded = quote(query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=ko&gl=KR&ceid=KR:ko"

    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    if r.status_code != 200:
        return []

    # Simple XML parsing without lxml
    items = re.findall(r"<item>(.*?)</item>", r.text, re.DOTALL)
    results = []
    for item in items[:max_results]:
        title = re.search(r"<title>(.*?)</title>", item)
        link = re.search(r"<link/>(.*?)(?:<|\s)", item)
        if not link:
            link = re.search(r"<link>(.*?)</link>", item)
        pub_date = re.search(r"<pubDate>(.*?)</pubDate>", item)
        source = re.search(r"<source.*?>(.*?)</source>", item)

        results.append({
            "title": title.group(1).strip() if title else "",
            "url": link.group(1).strip() if link else "",
            "date": pub_date.group(1).strip() if pub_date else "",
            "source": source.group(1).strip() if source else "",
        })

    return results


def collect_all_news(portfolio: dict) -> dict:
    """포트폴리오 전체 종목 뉴스 수집"""
    news = {}

    # KR stocks
    for stock in portfolio["kr"]:
        query = f"{stock['name']} 주가"
        articles = fetch_news_for_ticker(query, max_results=5)
        news[stock["ticker"]] = {
            "name": stock["name"],
            "articles": articles,
        }

    # US stocks
    for stock in portfolio["us"]:
        query = f"{stock['name']} stock"
        articles = fetch_news_for_ticker(query, max_results=5)
        news[stock["ticker"]] = {
            "name": stock["name"],
            "articles": articles,
        }

    # Macro news
    macro_articles = fetch_news_for_ticker("미국 금리 연준 경제", max_results=5)
    news["macro"] = {
        "name": "매크로",
        "articles": macro_articles,
    }

    return news


if __name__ == "__main__":
    from config import PORTFOLIO
    result = collect_all_news(PORTFOLIO)
    print(json.dumps(result, ensure_ascii=False, indent=2))
