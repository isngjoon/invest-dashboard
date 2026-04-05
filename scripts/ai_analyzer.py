"""
제갈공명 분석 엔진
Claude API로 공시/뉴스를 투자 맥락에서 해석

톤 스펙:
- 메르 스타일: 뉴스 이면의 맥락과 연결고리, 글로벌 흐름 해석
- 농구천재 스타일: 원칙과 근거 중심, 깊은 사고
- 호재/악재 이분법 금지 → 구조적 해석
"""
import os
import json
import requests
from datetime import datetime

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

SYSTEM_PROMPT = """너는 "제갈공명"이라는 투자 분석 AI야.

# 분석 대상 포트폴리오
- KR: 비츠로셀(082920, 572주, 평단 ₩34,950, 4월 매도예정), 그레이트리치(900290, 670주, 평단 ₩6,468)
- US: PLTR(42.77주, 평단 $87.12, 확신종목-온톨로지), HIMS(42주, 평단 $46.61, 확신종목-닥터나우경험)
- Crypto: DOGE, XLM, STX, ETC, CTC, PYTH (무지성 매수)
- 현금: 0원
- 투자자 프로필: 의대 본과2, 경력 ~1.5년, 공격적(수익률 극대화), 2029년부터 의사 소득 예정

# 분석 톤 (반드시 지킬 것)
1. "호재/악재" 이분법 절대 금지. 모든 이벤트는 구조적으로 해석.
2. 뉴스 자체가 아닌 뉴스 이면의 맥락을 해석. "왜 이게 나왔는지" → "이 흐름은 어디로 가는지" → "니 포트에 어떤 의미인지"
3. 근거 기반 판단. 추측은 추측이라 명시.
4. 반말, 직설적. 의대생이 이해할 수 있게.
5. 매크로 연결: 개별 이벤트도 가능하면 매크로(금리, 환율, 정책) 맥락과 연결.

# 출력 형식
반드시 아래 JSON 형식으로만 응답:
{
  "headline": "한 줄 핵심 (20자 이내)",
  "analysis": "맥락 해석 (3-5문장, 번호 매기기)",
  "portfolio_impact": "니 포트에 미치는 영향 (2-3문장)",
  "action_note": "참고할 점 (1문장, 없으면 null)",
  "urgency": "high | medium | low"
}
"""


def analyze_item(item_type: str, content: str) -> dict | None:
    """공시 또는 뉴스 항목을 제갈공명 톤으로 분석"""
    if not ANTHROPIC_API_KEY:
        return None

    user_msg = f"[{item_type}] {content}"

    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 500,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": user_msg}],
            },
            timeout=30,
        )

        if r.status_code != 200:
            print(f"[AI] API error: {r.status_code}")
            return None

        data = r.json()
        text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")

        # Parse JSON from response
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]

        return json.loads(text)

    except Exception as e:
        print(f"[AI] Error: {e}")
        return None


def analyze_disclosures(disclosures: list[dict], max_items: int = 5) -> list[dict]:
    """공시 목록을 분석"""
    analyzed = []
    for d in disclosures[:max_items]:
        content = f"종목: {d.get('corp_name', '')} ({d.get('ticker', '')})\n"
        content += f"공시: {d.get('title', '')}\n"
        content += f"일자: {d.get('date', '')}"

        analysis = analyze_item("공시", content)
        analyzed.append({
            **d,
            "ai_analysis": analysis,
        })

    return analyzed


def analyze_news(news: dict, max_per_ticker: int = 2) -> dict:
    """뉴스를 분석"""
    analyzed = {}
    for ticker, data in news.items():
        articles = data.get("articles", [])
        analyzed_articles = []
        for article in articles[:max_per_ticker]:
            content = f"종목: {data.get('name', '')} ({ticker})\n"
            content += f"제목: {article.get('title', '')}\n"
            content += f"출처: {article.get('source', '')}\n"
            content += f"일자: {article.get('date', '')}"

            analysis = analyze_item("뉴스", content)
            analyzed_articles.append({
                **article,
                "ai_analysis": analysis,
            })

        analyzed[ticker] = {
            "name": data.get("name", ""),
            "articles": analyzed_articles,
        }

    return analyzed


def generate_morning_briefing(prices: dict, disclosures: list, news: dict) -> dict | None:
    """데일리 모닝 브리핑 생성"""
    if not ANTHROPIC_API_KEY:
        return None

    summary = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "prices": {},
        "key_disclosures": [],
        "key_news": [],
    }

    # Price summary
    for stock in prices.get("kr", []):
        if "error" not in stock:
            summary["prices"][stock["ticker"]] = {
                "price": stock["price"],
                "change": stock.get("change_pct", 0),
                "pnl_pct": stock.get("pnl_pct", 0),
            }
    for stock in prices.get("us", []):
        if "error" not in stock:
            summary["prices"][stock["ticker"]] = {
                "price": stock["price"],
                "change": stock.get("change_pct", 0),
                "pnl_pct": stock.get("pnl_pct", 0),
            }

    # Top disclosures
    for d in disclosures[:3]:
        summary["key_disclosures"].append(f"{d.get('corp_name','')}: {d.get('title','')}")

    # Top news per ticker
    for ticker, data in news.items():
        for a in data.get("articles", [])[:1]:
            summary["key_news"].append(f"[{ticker}] {a.get('title','')}")

    content = json.dumps(summary, ensure_ascii=False)

    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 800,
                "system": SYSTEM_PROMPT + """

추가 지시: 모닝 브리핑을 생성해. 아래 JSON 형식으로:
{
  "greeting": "한 줄 인사 (반말)",
  "market_summary": "시장 요약 (2-3문장)",
  "portfolio_status": "포트 상태 (2-3문장, 수익률 포함)",
  "key_events": ["오늘 주목할 이벤트 1", "이벤트 2"],
  "one_thing": "오늘 딱 한 가지 기억할 것"
}""",
                "messages": [{"role": "user", "content": f"[모닝브리핑] {content}"}],
            },
            timeout=30,
        )

        if r.status_code != 200:
            return None

        data = r.json()
        text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")

        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]

        return json.loads(text)

    except Exception as e:
        print(f"[AI] Briefing error: {e}")
        return None
