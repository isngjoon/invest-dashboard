# 제갈공명 — AI 투자 대시보드

30분마다 자동으로 포트폴리오 시세, 공시, 뉴스를 수집하고
Claude AI가 맥락을 해석해서 대시보드 + 텔레그램으로 알려주는 시스템.

## 구조

```
scripts/          # Python 백엔드
  config.py       # 포트폴리오 설정 (종목 변경 시 여기 수정)
  main.py         # 메인 파이프라인
  dart_collector.py
  price_collector.py
  news_collector.py
  ai_analyzer.py  # 제갈공명 AI 분석 엔진
  telegram_bot.py
frontend/         # React 대시보드 (GitHub Pages)
.github/workflows/
  pipeline.yml    # 30분마다 데이터 수집
  deploy-pages.yml # 대시보드 배포
```

## 세팅 가이드

### 1. GitHub repo 생성 + 코드 push

```bash
cd invest-dashboard
git init
git add .
git commit -m "초기 세팅"
gh repo create invest-dashboard --private --push
```

### 2. GitHub Secrets 설정

GitHub repo → Settings → Secrets and variables → Actions → New repository secret:

| Secret Name | Value |
|-------------|-------|
| `DART_API_KEY` | DART OpenAPI 키 |
| `TELEGRAM_BOT_TOKEN` | 텔레그램 봇 토큰 |
| `TELEGRAM_CHAT_ID` | 텔레그램 채팅 ID |
| `ANTHROPIC_API_KEY` | Claude API 키 |

### 3. GitHub Pages 활성화

Settings → Pages → Source: GitHub Actions

### 4. 수동 테스트

Actions → "Investment Dashboard Pipeline" → Run workflow → mode: full

## 종목 변경

`scripts/config.py`에서 PORTFOLIO 수정 후 커밋.

## 비용

- GitHub Actions: 무료 (월 2,000분)
- GitHub Pages: 무료
- DART API: 무료
- Claude API: ~$5-10/월 (분석 빈도에 따라)
