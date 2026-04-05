"""
Price collector - Yahoo Finance (KR+US stocks) + CoinGecko (crypto)
"""
import json
import requests
from datetime import datetime


def fetch_stock_price(ticker: str, market: str = "us", sub_market: str = "") -> dict:
    """Yahoo Finance에서 주가 조회
    market: "us" or "kr"
    sub_market: "kospi" or "kosdaq" (kr only)
    """
    if market == "kr":
        if sub_market == "kosdaq":
            symbol = f"{ticker}.KQ"
        elif sub_market == "kospi":
            symbol = f"{ticker}.KS"
        else:
            # 둘 다 시도, .KQ 먼저 (코스닥이 더 많으므로)
            symbol = f"{ticker}.KQ"
    else:
        symbol = ticker

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    headers = {"User-Agent": "Mozilla/5.0"}
    params = {"range": "5d", "interval": "1d"}

    r = requests.get(url, headers=headers, params=params)
    if r.status_code != 200:
        # fallback: 코스닥 실패 시 코스피 시도 (또는 반대)
        if market == "kr":
            alt = f"{ticker}.KS" if sub_market == "kosdaq" else f"{ticker}.KQ"
            r = requests.get(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{alt}",
                headers=headers, params=params,
            )
            if r.status_code == 200:
                symbol = alt
            else:
                return {"ticker": ticker, "error": f"HTTP {r.status_code}"}
        else:
            return {"ticker": ticker, "error": f"HTTP {r.status_code}"}

    data = r.json()
    result = data.get("chart", {}).get("result", [])
    if not result:
        return {"ticker": ticker, "error": "no data"}

    meta = result[0].get("meta", {})
    price = meta.get("regularMarketPrice", 0)
    prev_close = meta.get("previousClose", 0)
    currency = meta.get("currency", "USD")

    change_pct = ((price - prev_close) / prev_close * 100) if prev_close else 0

    return {
        "ticker": ticker,
        "symbol": symbol,
        "price": round(price, 2),
        "prev_close": round(prev_close, 2),
        "change_pct": round(change_pct, 2),
        "currency": currency,
        "updated_at": datetime.now().isoformat(),
    }


def fetch_exchange_rate() -> float:
    """USD/KRW 환율 조회"""
    r = requests.get(
        "https://query1.finance.yahoo.com/v8/finance/chart/USDKRW=X",
        headers={"User-Agent": "Mozilla/5.0"},
        params={"range": "1d", "interval": "1d"},
    )
    if r.status_code == 200:
        data = r.json()
        result = data.get("chart", {}).get("result", [])
        if result:
            return result[0].get("meta", {}).get("regularMarketPrice", 1400)
    return 1400


def fetch_crypto_prices(tickers: list[str]) -> list[dict]:
    """CoinGecko에서 크립토 가격 조회 (KRW)"""
    # ticker → coingecko id mapping
    cg_map = {
        "DOGE": "dogecoin",
        "XLM": "stellar",
        "STX": "blockstack",
        "ETC": "ethereum-classic",
        "CTC": "creditcoin-2",
        "PYTH": "pyth-network",
    }

    ids = [cg_map.get(t, t.lower()) for t in tickers]
    ids_str = ",".join(ids)

    url = f"https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": ids_str,
        "vs_currencies": "krw",
        "include_24hr_change": "true",
    }

    r = requests.get(url, params=params)
    if r.status_code != 200:
        return [{"ticker": t, "error": f"HTTP {r.status_code}"} for t in tickers]

    data = r.json()
    results = []
    for ticker in tickers:
        cg_id = cg_map.get(ticker, ticker.lower())
        info = data.get(cg_id, {})
        results.append({
            "ticker": ticker,
            "price_krw": info.get("krw", 0),
            "change_24h_pct": round(info.get("krw_24h_change", 0), 2),
            "updated_at": datetime.now().isoformat(),
        })

    return results


def fetch_macro_indicators() -> dict:
    """주요 매크로 지표 조회"""
    indicators = {}
    symbols = {
        "us10y": "^TNX",       # US 10Y Treasury
        "vix": "^VIX",         # VIX
        "sp500": "^GSPC",      # S&P 500
        "kospi": "^KS11",      # KOSPI
        "kosdaq": "^KQ11",     # KOSDAQ
    }

    for name, symbol in symbols.items():
        r = requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
            headers={"User-Agent": "Mozilla/5.0"},
            params={"range": "5d", "interval": "1d"},
        )
        if r.status_code == 200:
            data = r.json()
            result = data.get("chart", {}).get("result", [])
            if result:
                meta = result[0].get("meta", {})
                price = meta.get("regularMarketPrice", 0)
                prev = meta.get("previousClose", 0)
                chg = ((price - prev) / prev * 100) if prev else 0
                indicators[name] = {
                    "value": round(price, 2),
                    "change_pct": round(chg, 2),
                }

    # USD/KRW
    usdkrw = fetch_exchange_rate()
    indicators["usdkrw"] = {"value": round(usdkrw, 2), "change_pct": 0}

    return indicators


def collect_all_prices(portfolio: dict) -> dict:
    """포트폴리오 전체 시세 수집"""
    usdkrw = fetch_exchange_rate()

    kr_prices = []
    for stock in portfolio["kr"]:
        p = fetch_stock_price(stock["ticker"], market="kr", sub_market=stock.get("market", ""))
        p["shares"] = stock["shares"]
        p["avg_price"] = stock["avg_price"]
        if "error" not in p:
            p["current_value"] = p["price"] * stock["shares"]
            p["cost_basis"] = stock["avg_price"] * stock["shares"]
            p["pnl"] = p["current_value"] - p["cost_basis"]
            p["pnl_pct"] = round(p["pnl"] / p["cost_basis"] * 100, 2)
        kr_prices.append(p)

    us_prices = []
    for stock in portfolio["us"]:
        p = fetch_stock_price(stock["ticker"], market="us")
        p["shares"] = stock["shares"]
        p["avg_price_usd"] = stock["avg_price_usd"]
        if "error" not in p:
            p["current_value_usd"] = round(p["price"] * stock["shares"], 2)
            p["current_value_krw"] = round(p["current_value_usd"] * usdkrw)
            p["cost_basis_usd"] = round(stock["avg_price_usd"] * stock["shares"], 2)
            p["pnl_usd"] = round(p["current_value_usd"] - p["cost_basis_usd"], 2)
            p["pnl_pct"] = round(p["pnl_usd"] / p["cost_basis_usd"] * 100, 2)
        us_prices.append(p)

    crypto_tickers = [c["ticker"] for c in portfolio["crypto"]]
    crypto_prices = fetch_crypto_prices(crypto_tickers)
    for i, cp in enumerate(crypto_prices):
        holding = portfolio["crypto"][i]
        cp["amount"] = holding["amount"]
        cp["avg_price_krw"] = holding["avg_price_krw"]
        if cp.get("price_krw"):
            cp["current_value_krw"] = round(cp["price_krw"] * holding["amount"])
            cp["cost_basis_krw"] = round(holding["avg_price_krw"] * holding["amount"])
            cp["pnl_krw"] = cp["current_value_krw"] - cp["cost_basis_krw"]
            cp["pnl_pct"] = round(cp["pnl_krw"] / cp["cost_basis_krw"] * 100, 2)

    macro = fetch_macro_indicators()

    return {
        "kr": kr_prices,
        "us": us_prices,
        "crypto": crypto_prices,
        "macro": macro,
        "usdkrw": usdkrw,
        "updated_at": datetime.now().isoformat(),
    }


if __name__ == "__main__":
    from config import PORTFOLIO
    result = collect_all_prices(PORTFOLIO)
    print(json.dumps(result, ensure_ascii=False, indent=2))
