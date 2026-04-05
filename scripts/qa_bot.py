"""
제갈공명 Q&A 봇 - 대화형 투자 분석
Telegram long-polling으로 사용자 질문에 Claude로 답변

실행:
  ANTHROPIC_API_KEY=... TELEGRAM_BOT_TOKEN=... python scripts/qa_bot.py
"""
import os
import sys
import json
import logging
import requests as http_requests
from datetime import datetime
from collections import defaultdict

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# Add scripts dir to path
sys.path.insert(0, os.path.dirname(__file__))
from config import PORTFOLIO

# SYSTEM_PROMPT를 직접 import하면 ai_analyzer.py의 3.10+ 문법 때문에 에러남
# 파일에서 직접 읽어서 파싱
def _load_system_prompt() -> str:
    path = os.path.join(os.path.dirname(__file__), "ai_analyzer.py")
    with open(path) as f:
        src = f.read()
    # SYSTEM_PROMPT = """...""" 블록 추출
    start = src.index('SYSTEM_PROMPT = """') + len('SYSTEM_PROMPT = """')
    end = src.index('"""', start)
    return src[start:end]

_SYSTEM_PROMPT = _load_system_prompt()

logging.basicConfig(
    format="%(asctime)s [QA] %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

# 대화 히스토리 (chat_id별, 최근 5쌍 유지)
conversation_history = defaultdict(list)  # chat_id -> list of {q, a}
MAX_HISTORY = 5


def load_dashboard_context() -> str:
    """dashboard.json에서 최신 데이터를 읽어 컨텍스트 문자열 생성"""
    path = os.path.join(DATA_DIR, "dashboard.json")
    if not os.path.exists(path):
        return "(대시보드 데이터 없음 - 파이프라인 미실행)"

    with open(path) as f:
        data = json.load(f)

    updated = data.get("updated_at", "?")
    lines = [f"[데이터 기준: {updated}]", ""]

    # 가격 요약
    lines.append("## 현재 가격")
    for market in ["kr", "us"]:
        for s in data.get("prices", {}).get(market, []):
            if "error" in s:
                continue
            pnl = s.get("pnl_pct", 0)
            change = s.get("change_pct", 0)
            lines.append(
                f"- {s['ticker']}: {s.get('price', '?'):,} "
                f"(오늘 {change:+.1f}%, 평가손익 {pnl:+.1f}%)"
            )

    for c in data.get("prices", {}).get("crypto", []):
        if c.get("price_krw"):
            pnl = c.get("pnl_pct", 0)
            lines.append(f"- {c['ticker']}: ₩{c['price_krw']:,.0f} (평가손익 {pnl:+.1f}%)")

    # 매크로
    macro = data.get("prices", {}).get("macro", {})
    if macro:
        lines.append("")
        lines.append("## 매크로")
        for k, v in macro.items():
            lines.append(f"- {k}: {v}")

    # 최근 공시
    disclosures = data.get("disclosures", [])
    if disclosures:
        lines.append("")
        lines.append("## 최근 공시")
        for d in disclosures[:5]:
            ai = d.get("ai_analysis") or {}
            headline = ai.get("headline", "")
            title = d.get("title", "")
            corp = d.get("corp_name", "")
            lines.append(f"- [{corp}] {title}" + (f" → {headline}" if headline else ""))

    # 최근 뉴스
    news = data.get("news", {})
    if news:
        lines.append("")
        lines.append("## 최근 뉴스")
        for ticker, nd in news.items():
            for a in nd.get("articles", [])[:2]:
                ai = a.get("ai_analysis") or {}
                headline = ai.get("headline", "")
                lines.append(
                    f"- [{ticker}] {a.get('title', '')}"
                    + (f" → {headline}" if headline else "")
                )

    return "\n".join(lines)


def build_qa_system_prompt() -> str:
    """Q&A용 시스템 프롬프트 구성"""
    base = _SYSTEM_PROMPT.split("# 출력 형식")[0].strip()

    return base + """

# Q&A 모드
지금은 대화형 Q&A 모드야. JSON이 아니라 자연스러운 한국어로 답해.
- 반말, 직설적, 핵심만
- 구조적 해석 유지 (호재/악재 이분법 금지)
- 포트폴리오 맥락을 항상 고려해서 답변
- 모르면 모른다고 솔직하게
- 답변은 간결하게 (3-8문장)

""" + load_dashboard_context()


def ask_claude(chat_id: str, question: str) -> str:
    """Claude API에 질문하고 답변 받기"""
    if not ANTHROPIC_API_KEY:
        return "ANTHROPIC_API_KEY가 설정되지 않았어."

    history = conversation_history[chat_id]

    messages = []
    for h in history:
        messages.append({"role": "user", "content": h["q"]})
        messages.append({"role": "assistant", "content": h["a"]})
    messages.append({"role": "user", "content": question})

    try:
        r = http_requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1000,
                "system": build_qa_system_prompt(),
                "messages": messages,
            },
            timeout=30,
        )

        if r.status_code != 200:
            logger.error(f"Claude API error: {r.status_code} {r.text[:200]}")
            return f"API 에러 ({r.status_code}). 잠시 후 다시 시도해봐."

        data = r.json()
        answer = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                answer += block.get("text", "")

        # 히스토리 저장
        history.append({"q": question, "a": answer})
        if len(history) > MAX_HISTORY:
            history.pop(0)

        return answer.strip()

    except Exception as e:
        logger.error(f"Claude error: {e}")
        return "분석 중 에러가 났어. 잠시 후 다시 해봐."


def is_authorized(chat_id: int) -> bool:
    """허가된 chat_id인지 확인"""
    if not CHAT_ID:
        return True
    return str(chat_id) == CHAT_ID


# === Handlers ===

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return

    await update.message.reply_text(
        "제갈공명 Q&A 봇이야.\n\n"
        "아무 질문이나 던져봐. 니 포트폴리오 맥락에서 답해줄게.\n\n"
        "명령어:\n"
        "/status - 포트폴리오 현황\n"
        "/briefing - 최신 브리핑\n"
        "/clear - 대화 초기화"
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return

    answer = ask_claude(
        str(update.effective_chat.id),
        "내 포트폴리오 현재 상황을 간결하게 정리해줘. 종목별 수익률과 전체 평가를 포함해서."
    )
    await update.message.reply_text(answer)


async def cmd_briefing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return

    path = os.path.join(DATA_DIR, "briefing.json")
    if os.path.exists(path):
        with open(path) as f:
            briefing = json.load(f)

        lines = [
            f"☀️ 모닝 브리핑",
            "",
            briefing.get("greeting", ""),
            "",
            f"📊 시장: {briefing.get('market_summary', '')}",
            "",
            f"💼 포트: {briefing.get('portfolio_status', '')}",
        ]
        events = briefing.get("key_events", [])
        if events:
            lines.append("")
            for e in events:
                lines.append(f"📌 {e}")
        one = briefing.get("one_thing", "")
        if one:
            lines.append(f"\n💡 {one}")

        await update.message.reply_text("\n".join(lines))
    else:
        answer = ask_claude(
            str(update.effective_chat.id),
            "오늘 브리핑 해줘. 시장 상황, 내 포트 상태, 주목할 점."
        )
        await update.message.reply_text(answer)


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return

    chat_id = str(update.effective_chat.id)
    conversation_history[chat_id].clear()
    await update.message.reply_text("대화 히스토리 초기화했어.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return

    question = update.message.text.strip()
    if not question:
        return

    logger.info(f"Q: {question[:50]}")

    # "생각 중" 표시
    await update.message.chat.send_action("typing")

    answer = ask_claude(str(update.effective_chat.id), question)
    logger.info(f"A: {answer[:50]}")

    # 텔레그램 메시지 길이 제한 (4096자)
    if len(answer) > 4000:
        answer = answer[:4000] + "\n\n(답변이 길어서 잘렸어)"

    await update.message.reply_text(answer)


def main():
    if not BOT_TOKEN:
        print("TELEGRAM_BOT_TOKEN 환경변수를 설정해줘.")
        sys.exit(1)

    if not ANTHROPIC_API_KEY:
        print("ANTHROPIC_API_KEY 환경변수를 설정해줘.")
        sys.exit(1)

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("briefing", cmd_briefing))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("제갈공명 Q&A 봇 시작!")
    logger.info(f"Authorized chat: {CHAT_ID or 'ALL'}")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
