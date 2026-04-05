"""
DART OpenAPI - 공시 수집
https://opendart.fss.or.kr
"""
import os
import json
import requests
from datetime import datetime, timedelta

DART_API_KEY = os.environ.get("DART_API_KEY", "")
BASE_URL = "https://opendart.fss.or.kr/api"


def get_corp_code(ticker: str) -> str | None:
    """DART 고유번호 조회 (종목코드 → corp_code)"""
    import zipfile
    import io
    import xml.etree.ElementTree as ET

    cache_path = "data/corp_codes.json"
    if os.path.exists(cache_path):
        with open(cache_path) as f:
            codes = json.load(f)
            if ticker in codes:
                return codes[ticker]

    url = f"{BASE_URL}/corpCode.xml"
    r = requests.get(url, params={"crtfc_key": DART_API_KEY})
    if r.status_code != 200:
        print(f"[DART] corpCode fetch failed: {r.status_code}")
        return None

    z = zipfile.ZipFile(io.BytesIO(r.content))
    xml_data = z.read(z.namelist()[0])
    root = ET.fromstring(xml_data)

    codes = {}
    for item in root.findall("list"):
        stock_code = item.findtext("stock_code", "").strip()
        corp_code = item.findtext("corp_code", "").strip()
        if stock_code:
            codes[stock_code] = corp_code

    os.makedirs("data", exist_ok=True)
    with open(cache_path, "w") as f:
        json.dump(codes, f)

    return codes.get(ticker)


def fetch_disclosures(corp_code: str, days: int = 7) -> list[dict]:
    """최근 N일간 공시 목록 조회"""
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

    url = f"{BASE_URL}/list.json"
    params = {
        "crtfc_key": DART_API_KEY,
        "corp_code": corp_code,
        "bgn_de": start,
        "end_de": end,
        "page_count": 20,
    }
    r = requests.get(url, params=params)
    if r.status_code != 200:
        return []

    data = r.json()
    if data.get("status") != "000":
        return []

    results = []
    for item in data.get("list", []):
        results.append({
            "title": item.get("report_nm", ""),
            "date": item.get("rcept_dt", ""),
            "corp_name": item.get("corp_name", ""),
            "rcept_no": item.get("rcept_no", ""),
            "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={item.get('rcept_no', '')}",
            "type": item.get("corp_cls", ""),
        })

    return results


def fetch_financials(corp_code: str, year: str, report_code: str = "11011") -> dict:
    """재무제표 주요 항목 조회
    report_code: 11011=사업보고서, 11012=반기, 11013=1분기, 11014=3분기
    """
    url = f"{BASE_URL}/fnlttSinglAcntAll.json"
    params = {
        "crtfc_key": DART_API_KEY,
        "corp_code": corp_code,
        "bsns_year": year,
        "reprt_code": report_code,
        "fs_div": "OFS",  # 개별
    }
    r = requests.get(url, params=params)
    if r.status_code != 200:
        return {}

    data = r.json()
    if data.get("status") != "000":
        return {}

    financials = {}
    for item in data.get("list", []):
        key = item.get("account_nm", "")
        val = item.get("thstrm_amount", "")
        if key and val:
            financials[key] = val

    return financials


def fetch_major_shareholders(corp_code: str) -> list:
    """대량보유 상황보고 데이터 조회 - 누가 얼마나 매수/매도했는지"""
    url = f"{BASE_URL}/majorstock.json"
    params = {
        "crtfc_key": DART_API_KEY,
        "corp_code": corp_code,
    }
    r = requests.get(url, params=params)
    if r.status_code != 200:
        return []

    data = r.json()
    if data.get("status") != "000":
        return []

    results = []
    for item in data.get("list", []):
        results.append({
            "reporter": item.get("repror", ""),
            "shares_held": item.get("stkqy", ""),
            "shares_change": item.get("stkqy_irds", ""),
            "ratio_pct": item.get("stkrt", ""),
            "ratio_change_pct": item.get("stkrt_irds", ""),
            "reason": item.get("report_resn", ""),
            "date": item.get("rcept_dt", ""),
        })

    return results


def enrich_disclosure_with_details(disclosure: dict, corp_code: str) -> dict:
    """공시 유형에 따라 세부 데이터를 추가"""
    title = disclosure.get("title", "")

    # 대량보유상황보고서인 경우 대량보유 데이터 추가
    if "대량보유" in title:
        shareholders = fetch_major_shareholders(corp_code)
        if shareholders:
            disclosure["major_shareholders"] = shareholders

    return disclosure


def collect_all_disclosures(tickers: list[str], days: int = 7) -> list[dict]:
    """전체 관심종목 공시 수집"""
    all_disclosures = []
    for ticker in tickers:
        corp_code = get_corp_code(ticker)
        if not corp_code:
            print(f"[DART] corp_code not found for {ticker}")
            continue
        disclosures = fetch_disclosures(corp_code, days)
        for d in disclosures:
            d["ticker"] = ticker
            enrich_disclosure_with_details(d, corp_code)
        all_disclosures.extend(disclosures)

    all_disclosures.sort(key=lambda x: x["date"], reverse=True)
    return all_disclosures


if __name__ == "__main__":
    from config import DART_WATCHLIST
    results = collect_all_disclosures(DART_WATCHLIST)
    print(json.dumps(results, ensure_ascii=False, indent=2))
