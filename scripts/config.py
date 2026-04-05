"""
Portfolio configuration - 승준's holdings
Update this file when portfolio changes
"""

PORTFOLIO = {
    "kr": [
        {
            "name": "비츠로셀",
            "ticker": "082920",
            "market": "kosdaq",
            "shares": 572,
            "avg_price": 34950,
            "dart_code": None,  # will be fetched
            "tags": ["4월매도예정", "지인추천"],
            "conviction": "low",
        },
        {
            "name": "그레이트리치과기유한공사",
            "ticker": "900290",
            "market": "kosdaq",
            "shares": 670,
            "avg_price": 6468,
            "dart_code": None,
            "tags": ["텔레그램"],
            "conviction": "low",
        },
    ],
    "us": [
        {
            "name": "Palantir",
            "ticker": "PLTR",
            "shares": 42.766171,
            "avg_price_usd": 87.12,
            "tags": ["확신", "온톨로지", "닥터나우경험"],
            "conviction": "high",
        },
        {
            "name": "Hims & Hers",
            "ticker": "HIMS",
            "shares": 42,
            "avg_price_usd": 46.61,
            "tags": ["확신", "닥터나우피어"],
            "conviction": "high",
        },
    ],
    "crypto": [
        {"name": "도지코인", "ticker": "DOGE", "amount": 6899.18619436, "avg_price_krw": 543.6},
        {"name": "스텔라루멘", "ticker": "XLM", "amount": 2581.45187870, "avg_price_krw": 606.8},
        {"name": "스택스", "ticker": "STX", "amount": 1015.52921644, "avg_price_krw": 3292.7},
        {"name": "이더리움클래식", "ticker": "ETC", "amount": 21.38210586, "avg_price_krw": 52140},
        {"name": "크레딧코인", "ticker": "CTC", "amount": 926.43591074, "avg_price_krw": 1927},
        {"name": "피스네트워크", "ticker": "PYTH", "amount": 371.04639175, "avg_price_krw": 1358},
    ],
}

# DART watchlist - additional tickers to monitor for relevant disclosures
DART_WATCHLIST = [t["ticker"] for t in PORTFOLIO["kr"]]

# SEC watchlist
SEC_WATCHLIST = [t["ticker"] for t in PORTFOLIO["us"]]

# Exchange rate default (updated at runtime)
DEFAULT_USD_KRW = 1400
