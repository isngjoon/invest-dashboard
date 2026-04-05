"""
Telegram bot - 투자 알림 전송
"""
import os
import json
import requests

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


def send_message(text: str, parse_mode: str = "HTML") -> bool:
    """텔레그램 메시지 전송"""
    if not BOT_TOKEN or not CHAT_ID:
        print("[TG] Missing bot token or chat ID")
        return False

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }

    r = requests.post(url, json=payload)
    if r.status_code != 200:
        print(f"[TG] Send failed: {r.status_code} {r.text}")
        return False
    return True


def format_morning_briefing(briefing: dict) -> str:
    """모닝 브리핑을 텔레그램 메시지로 포맷"""
    if not briefing:
        return ""

    lines = [
        f"<b>☀️ 모닝 브리핑</b>",
        f"",
        f"{briefing.get('greeting', '')}",
        f"",
        f"<b>📊 시장</b>",
        f"{briefing.get('market_summary', '')}",
        f"",
        f"<b>💼 포트폴리오</b>",
        f"{briefing.get('portfolio_status', '')}",
    ]

    events = briefing.get("key_events", [])
    if events:
        lines.append("")
        lines.append("<b>📌 주목</b>")
        for e in events:
            lines.append(f"• {e}")

    one_thing = briefing.get("one_thing", "")
    if one_thing:
        lines.append("")
        lines.append(f"<b>💡 오늘 한 줄:</b> {one_thing}")

    return "\n".join(lines)


def format_disclosure_alert(disclosure: dict) -> str:
    """공시 알림을 텔레그램 메시지로 포맷"""
    ai = disclosure.get("ai_analysis", {}) or {}

    urgency_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
        ai.get("urgency", "low"), "⚪"
    )

    lines = [
        f"{urgency_emoji} <b>공시 알림</b>",
        f"",
        f"<b>{disclosure.get('corp_name', '')}</b> ({disclosure.get('ticker', '')})",
        f"📄 {disclosure.get('title', '')}",
        f"📅 {disclosure.get('date', '')}",
    ]

    # 대량보유 세부 데이터가 있으면 표시
    shareholders = disclosure.get("major_shareholders", [])
    if shareholders:
        lines.append("")
        lines.append("<b>👤 대량보유 변동</b>")
        for sh in shareholders[:3]:
            change = sh.get("shares_change", "")
            direction = ""
            if change:
                try:
                    num = int(str(change).replace(",", ""))
                    direction = "📈증가" if num > 0 else "📉감소" if num < 0 else ""
                except ValueError:
                    pass
            lines.append(
                f"  {sh.get('reporter', '?')}: "
                f"{sh.get('shares_held', '?')}주 "
                f"({sh.get('ratio_pct', '?')}%) "
                f"{direction} {change}주"
            )

    if ai:
        lines.append("")
        lines.append(f"<b>🔍 {ai.get('headline', '')}</b>")
        lines.append("")
        lines.append(f"<b>📋 상황</b>")
        lines.append(ai.get("situation", ai.get("analysis", "")))
        lines.append("")
        lines.append(f"<b>💡 시사점</b>")
        lines.append(ai.get("implication", ""))
        lines.append("")
        lines.append(f"<b>💼 내 포트 영향</b>")
        lines.append(ai.get("impact", ai.get("portfolio_impact", "")))
        if ai.get("action_note"):
            lines.append("")
            lines.append(f"📝 {ai['action_note']}")

    url = disclosure.get("url", "")
    if url:
        lines.append("")
        lines.append(f"<a href='{url}'>공시 원문 보기</a>")

    return "\n".join(lines)


def format_news_alert(ticker: str, name: str, article: dict) -> str:
    """뉴스 알림을 텔레그램 메시지로 포맷"""
    ai = article.get("ai_analysis", {}) or {}

    urgency_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
        ai.get("urgency", "low"), "⚪"
    )

    lines = [
        f"{urgency_emoji} <b>뉴스 알림</b>",
        f"",
        f"<b>{name}</b> ({ticker})",
        f"📰 {article.get('title', '')}",
        f"📡 {article.get('source', '')} | {article.get('date', '')}",
    ]

    if ai:
        lines.append("")
        lines.append(f"<b>🔍 {ai.get('headline', '')}</b>")
        lines.append("")
        lines.append(f"<b>📋 상황</b>")
        lines.append(ai.get("situation", ai.get("analysis", "")))
        lines.append("")
        lines.append(f"<b>💡 시사점</b>")
        lines.append(ai.get("implication", ""))
        lines.append("")
        lines.append(f"<b>💼 내 포트 영향</b>")
        lines.append(ai.get("impact", ai.get("portfolio_impact", "")))
        if ai.get("action_note"):
            lines.append("")
            lines.append(f"📝 {ai['action_note']}")

    return "\n".join(lines)


def format_price_alert(stock: dict, alert_type: str = "surge") -> str:
    """급등락 알림"""
    emoji = "📈" if stock.get("change_pct", 0) > 0 else "📉"
    return (
        f"{emoji} <b>급{'등' if stock.get('change_pct', 0) > 0 else '락'} 알림</b>\n"
        f"\n"
        f"<b>{stock.get('ticker', '')}</b>\n"
        f"현재가: {stock.get('price', 0):,} ({stock.get('change_pct', 0):+.1f}%)\n"
        f"평가손익: {stock.get('pnl_pct', 0):+.1f}%"
    )


def send_portfolio_summary(prices: dict) -> bool:
    """포트폴리오 요약 전송"""
    total_krw = 0
    total_cost = 0
    lines = ["<b>📊 포트폴리오 현황</b>", ""]

    # KR
    lines.append("<b>🇰🇷 한국</b>")
    for s in prices.get("kr", []):
        if "error" in s:
            continue
        val = s.get("current_value", 0)
        pnl = s.get("pnl_pct", 0)
        total_krw += val
        total_cost += s.get("cost_basis", 0)
        lines.append(f"  {s['ticker']} ₩{s['price']:,.0f} ({pnl:+.1f}%)")

    # US
    lines.append("")
    lines.append("<b>🇺🇸 미국</b>")
    for s in prices.get("us", []):
        if "error" in s:
            continue
        val_krw = s.get("current_value_krw", 0)
        pnl = s.get("pnl_pct", 0)
        total_krw += val_krw
        total_cost += round(s.get("cost_basis_usd", 0) * prices.get("usdkrw", 1400))
        lines.append(f"  {s['ticker']} ${s['price']:.2f} ({pnl:+.1f}%)")

    # Crypto
    lines.append("")
    lines.append("<b>🪙 크립토</b>")
    for c in prices.get("crypto", []):
        if c.get("price_krw"):
            val = c.get("current_value_krw", 0)
            pnl = c.get("pnl_pct", 0)
            total_krw += val
            total_cost += c.get("cost_basis_krw", 0)
            lines.append(f"  {c['ticker']} ₩{c['price_krw']:,.0f} ({pnl:+.1f}%)")

    total_pnl = total_krw - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost else 0

    lines.append("")
    lines.append(f"<b>총 평가: ₩{total_krw:,.0f}</b>")
    lines.append(f"<b>총 손익: ₩{total_pnl:,.0f} ({total_pnl_pct:+.1f}%)</b>")

    return send_message("\n".join(lines))
