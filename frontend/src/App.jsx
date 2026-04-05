import { useState, useEffect } from "react";

const REFRESH_INTERVAL = 60000; // 1min

function formatKRW(n) {
  if (!n) return "₩0";
  if (Math.abs(n) >= 1e8) return `₩${(n / 1e8).toFixed(1)}억`;
  if (Math.abs(n) >= 1e4) return `₩${(n / 1e4).toFixed(0)}만`;
  return `₩${n.toLocaleString()}`;
}

function PnlBadge({ pct }) {
  if (pct === undefined || pct === null) return null;
  const color = pct >= 0 ? "#dc2626" : "#2563eb";
  return (
    <span style={{ color, fontWeight: 500 }}>{pct >= 0 ? "+" : ""}{pct.toFixed(1)}%</span>
  );
}

function StockRow({ ticker, price, change, pnl, currency = "₩", conviction }) {
  return (
    <div style={{
      display: "flex", justifyContent: "space-between", alignItems: "center",
      padding: "10px 0", borderBottom: "1px solid var(--border)"
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ fontWeight: 500 }}>{ticker}</span>
        {conviction === "high" && (
          <span style={{
            fontSize: 11, background: "#fef3c7", color: "#92400e",
            padding: "1px 6px", borderRadius: 4
          }}>확신</span>
        )}
      </div>
      <div style={{ textAlign: "right" }}>
        <div>{currency === "$" ? `$${price}` : `₩${price?.toLocaleString()}`}</div>
        <div style={{ fontSize: 13 }}>
          <span style={{ color: change >= 0 ? "#dc2626" : "#2563eb", marginRight: 8 }}>
            {change >= 0 ? "▲" : "▼"}{Math.abs(change)}%
          </span>
          <PnlBadge pct={pnl} />
        </div>
      </div>
    </div>
  );
}

function DisclosureCard({ d }) {
  const ai = d.ai_analysis || {};
  const urgencyColor = { high: "#dc2626", medium: "#d97706", low: "#059669" };
  return (
    <div style={{
      background: "var(--card)", border: "1px solid var(--border)",
      borderRadius: 10, padding: 14, marginBottom: 10,
      borderLeft: `3px solid ${urgencyColor[ai.urgency] || "#9ca3af"}`
    }}>
      <div style={{ fontSize: 13, color: "var(--muted)", marginBottom: 4 }}>
        {d.corp_name} · {d.date}
      </div>
      <div style={{ fontWeight: 500, marginBottom: 6 }}>{d.title}</div>
      {ai.headline && (
        <div style={{ fontSize: 14, fontWeight: 500, color: "#7c3aed", marginBottom: 4 }}>
          🔍 {ai.headline}
        </div>
      )}
      {ai.analysis && (
        <div style={{ fontSize: 13, color: "var(--muted)", marginBottom: 4 }}>{ai.analysis}</div>
      )}
      {ai.portfolio_impact && (
        <div style={{ fontSize: 13, background: "var(--surface)", padding: "6px 8px", borderRadius: 6 }}>
          💼 {ai.portfolio_impact}
        </div>
      )}
      {d.url && (
        <a href={d.url} target="_blank" rel="noreferrer"
          style={{ fontSize: 12, color: "#6366f1", marginTop: 6, display: "inline-block" }}>
          공시 원문 →
        </a>
      )}
    </div>
  );
}

function NewsCard({ ticker, name, article }) {
  const ai = article.ai_analysis || {};
  return (
    <div style={{
      background: "var(--card)", border: "1px solid var(--border)",
      borderRadius: 10, padding: 14, marginBottom: 10
    }}>
      <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 4 }}>
        {name} ({ticker}) · {article.source}
      </div>
      <div style={{ fontWeight: 500, marginBottom: 6, fontSize: 14 }}>{article.title}</div>
      {ai.headline && (
        <div style={{ fontSize: 13, color: "#7c3aed", marginBottom: 4 }}>🔍 {ai.headline}</div>
      )}
      {ai.analysis && (
        <div style={{ fontSize: 13, color: "var(--muted)" }}>{ai.analysis}</div>
      )}
    </div>
  );
}

function MacroBar({ macro }) {
  if (!macro) return null;
  const items = [
    { key: "kospi", label: "KOSPI" },
    { key: "kosdaq", label: "KOSDAQ" },
    { key: "sp500", label: "S&P500" },
    { key: "usdkrw", label: "USD/KRW" },
    { key: "vix", label: "VIX" },
    { key: "us10y", label: "US 10Y" },
  ];
  return (
    <div style={{
      display: "flex", gap: 12, overflowX: "auto", padding: "8px 0",
      marginBottom: 16, flexWrap: "wrap"
    }}>
      {items.map(({ key, label }) => {
        const d = macro[key];
        if (!d) return null;
        return (
          <div key={key} style={{
            background: "var(--surface)", borderRadius: 8, padding: "8px 12px",
            minWidth: 90, textAlign: "center"
          }}>
            <div style={{ fontSize: 11, color: "var(--muted)" }}>{label}</div>
            <div style={{ fontWeight: 500, fontSize: 14 }}>{d.value?.toLocaleString()}</div>
            {d.change_pct !== 0 && (
              <div style={{ fontSize: 12, color: d.change_pct >= 0 ? "#dc2626" : "#2563eb" }}>
                {d.change_pct >= 0 ? "+" : ""}{d.change_pct}%
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

export default function App() {
  const [data, setData] = useState(null);
  const [tab, setTab] = useState("portfolio");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const r = await fetch("data.json?" + Date.now());
        const d = await r.json();
        setData(d);
      } catch (e) {
        console.error("Failed to load data:", e);
      }
      setLoading(false);
    };
    load();
    const interval = setInterval(load, REFRESH_INTERVAL);
    return () => clearInterval(interval);
  }, []);

  if (loading) return <div style={{ padding: 20, textAlign: "center" }}>Loading...</div>;
  if (!data) return <div style={{ padding: 20, textAlign: "center" }}>데이터를 불러올 수 없습니다</div>;

  const prices = data.prices || {};
  const kr = prices.kr || [];
  const us = prices.us || [];
  const crypto = prices.crypto || [];

  // Calculate totals
  let totalValue = 0, totalCost = 0;
  kr.forEach(s => { if (!s.error) { totalValue += s.current_value || 0; totalCost += s.cost_basis || 0; } });
  us.forEach(s => { if (!s.error) { totalValue += s.current_value_krw || 0; totalCost += (s.cost_basis_usd || 0) * (prices.usdkrw || 1400); } });
  crypto.forEach(c => { if (c.price_krw) { totalValue += c.current_value_krw || 0; totalCost += c.cost_basis_krw || 0; } });
  const totalPnl = totalValue - totalCost;
  const totalPnlPct = totalCost ? (totalPnl / totalCost * 100) : 0;

  const tabs = [
    { id: "portfolio", label: "포트폴리오" },
    { id: "disclosures", label: "공시" },
    { id: "news", label: "뉴스" },
  ];

  const portfolio = data.portfolio || {};
  const krConfig = portfolio.kr || [];
  const usConfig = portfolio.us || [];

  return (
    <div style={{
      "--bg": "#ffffff", "--card": "#ffffff", "--surface": "#f5f5f4",
      "--text": "#1c1917", "--muted": "#78716c", "--border": "#e7e5e4",
      maxWidth: 480, margin: "0 auto", padding: "12px 16px",
      fontFamily: "system-ui, -apple-system, sans-serif",
      color: "var(--text)", background: "var(--bg)",
    }}>
      {/* Header */}
      <div style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 20, fontWeight: 600 }}>제갈공명</div>
        <div style={{ fontSize: 12, color: "var(--muted)" }}>
          {data.updated_at ? new Date(data.updated_at).toLocaleString("ko-KR") : ""} 기준
        </div>
      </div>

      {/* Total */}
      <div style={{
        background: "var(--surface)", borderRadius: 12, padding: 16, marginBottom: 16
      }}>
        <div style={{ fontSize: 13, color: "var(--muted)" }}>총 평가금액</div>
        <div style={{ fontSize: 28, fontWeight: 600 }}>{formatKRW(totalValue)}</div>
        <div style={{ fontSize: 15, marginTop: 4 }}>
          <PnlBadge pct={totalPnlPct} />
          <span style={{ color: "var(--muted)", marginLeft: 8, fontSize: 13 }}>
            {formatKRW(totalPnl)}
          </span>
        </div>
      </div>

      {/* Macro */}
      <MacroBar macro={prices.macro} />

      {/* Tabs */}
      <div style={{ display: "flex", gap: 0, marginBottom: 16, borderBottom: "1px solid var(--border)" }}>
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} style={{
            flex: 1, padding: "10px 0", border: "none", background: "none",
            cursor: "pointer", fontSize: 14, fontWeight: tab === t.id ? 600 : 400,
            color: tab === t.id ? "var(--text)" : "var(--muted)",
            borderBottom: tab === t.id ? "2px solid var(--text)" : "2px solid transparent",
          }}>{t.label}</button>
        ))}
      </div>

      {/* Portfolio Tab */}
      {tab === "portfolio" && (
        <div>
          <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 8, color: "var(--muted)" }}>한국 주식</div>
          {kr.map((s, i) => (
            <StockRow key={s.ticker} ticker={s.ticker} price={s.price}
              change={s.change_pct} pnl={s.pnl_pct}
              conviction={krConfig[i]?.conviction} />
          ))}

          <div style={{ fontSize: 14, fontWeight: 500, marginTop: 16, marginBottom: 8, color: "var(--muted)" }}>미국 주식</div>
          {us.map((s, i) => (
            <StockRow key={s.ticker} ticker={s.ticker} price={s.price}
              change={s.change_pct} pnl={s.pnl_pct} currency="$"
              conviction={usConfig[i]?.conviction} />
          ))}

          <div style={{ fontSize: 14, fontWeight: 500, marginTop: 16, marginBottom: 8, color: "var(--muted)" }}>크립토</div>
          {crypto.map(c => (
            <StockRow key={c.ticker} ticker={c.ticker} price={c.price_krw}
              change={c.change_24h_pct} pnl={c.pnl_pct} />
          ))}
        </div>
      )}

      {/* Disclosures Tab */}
      {tab === "disclosures" && (
        <div>
          {(data.disclosures || []).length === 0 ? (
            <div style={{ textAlign: "center", padding: 40, color: "var(--muted)" }}>
              최근 공시 없음
            </div>
          ) : (
            (data.disclosures || []).map((d, i) => <DisclosureCard key={i} d={d} />)
          )}
        </div>
      )}

      {/* News Tab */}
      {tab === "news" && (
        <div>
          {Object.entries(data.news || {}).map(([ticker, nd]) => (
            (nd.articles || []).map((a, i) => (
              <NewsCard key={`${ticker}-${i}`} ticker={ticker} name={nd.name} article={a} />
            ))
          ))}
        </div>
      )}

      {/* Footer */}
      <div style={{ textAlign: "center", padding: "24px 0 12px", fontSize: 12, color: "var(--muted)" }}>
        Powered by Claude AI · 30분마다 자동 업데이트
      </div>
    </div>
  );
}
