import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# =====================================================================
# ⚙️ 1. 최종 확정 파라미터 (13야수 하이브리드 V3)
# =====================================================================
PORTFOLIO_CONFIG = {
    "305540.KS": {"name": "TIGER 2차전지테마", "buy": -3.5, "sell": 0.8, "stop": -0.8},
    "139230.KS": {"name": "TIGER 200중공업", "buy": -2.4, "sell": 1.0, "stop": -0.2},
    "091180.KS": {"name": "KODEX 자동차", "buy": -3.0, "sell": 1.8, "stop": -5.0},
    "371160.KS": {"name": "TIGER 차이나항셍테크", "buy": -2.5, "sell": 0.7, "stop": -0.8},
    "091160.KS": {"name": "KODEX 반도체", "buy": -3.1, "sell": 2.3, "stop": -5.0},
    "118990.KS": {"name": "KODEX 게임산업", "buy": -2.2, "sell": 1.0, "stop": -1.0},
    "157490.KS": {"name": "TIGER 소프트웨어", "buy": -3.4, "sell": 2.3, "stop": -0.6},
    "261070.KS": {"name": "TIGER 코스닥150바이오", "buy": -3.4, "sell": 2.5, "stop": -2.6},
    "245360.KS": {"name": "TIGER 차이나HSCEI", "buy": -3.7, "sell": 0.6, "stop": -0.6},
    "130680.KS": {"name": "KODEX WTI원유선물(H)", "buy": -3.3, "sell": 1.4, "stop": -0.6},
    "144600.KS": {"name": "KODEX 은선물(H)", "buy": -4.1, "sell": 2.0, "stop": -2.8},
    "117680.KS": {"name": "KODEX 철강", "buy": -3.1, "sell": 1.3, "stop": -2.6},
    "138920.KS": {"name": "KODEX 구리선물(H)", "buy": -3.2, "sell": 0.9, "stop": -2.6}
}

# =====================================================================
# 🚀 2. 데이터 로더 (캐싱으로 웹 속도 최적화)
# =====================================================================
@st.cache_data(ttl=86400) # 하루 한 번만 야후 파이낸스에서 다운로드
def load_and_preprocess_data():
    tickers = list(PORTFOLIO_CONFIG.keys())
    df_all = yf.download(tickers, start="2018-01-01", end="today", progress=False)['Close']
    df_all.fillna(method='ffill', inplace=True)
    
    LR_WINDOW = 60
    sigma_data, slope_data = {}, {}
    weights = np.arange(1, LR_WINDOW + 1) - (LR_WINDOW + 1) / 2
    sum_w2 = np.sum(weights**2)

    for ticker in tickers:
        prices = df_all[ticker].values
        ma = pd.Series(prices).rolling(LR_WINDOW).mean().values
        slope = pd.Series(prices).rolling(LR_WINDOW).apply(lambda y: np.sum(weights * y) / sum_w2, raw=True).values
        lr_current = ma + slope * ((LR_WINDOW - 1) / 2)
        std = pd.Series(prices).rolling(LR_WINDOW).std().values
        
        sigma_data[ticker] = (prices - lr_current) / std
        slope_data[ticker] = (slope / ma) * 100
        
    return df_all, sigma_data, slope_data

# =====================================================================
# ⚖️ 3. 포트폴리오 백테스트 엔진
# =====================================================================
@st.cache_data
def run_hybrid_portfolio(df_all, sigma_data, slope_data, start_capital=20000000):
    SLIPPAGE = 0.0015
    TAX_RATE = 0.154
    LR_WINDOW = 60
    dates = df_all.index
    tickers = list(PORTFOLIO_CONFIG.keys())
    
    cash = start_capital
    daily_equity = []
    port = {t: {"shares": 0, "avg_price": 0} for t in tickers}
    
    for i in range(LR_WINDOW, len(dates)):
        # [1] 매도 처리 (손익절)
        for ticker, p_info in port.items():
            if p_info["shares"] == 0: continue
            price = df_all[ticker].values[i]
            if np.isnan(price): continue
            
            sig, slp = sigma_data[ticker][i], slope_data[ticker][i]
            params = PORTFOLIO_CONFIG[ticker]
            
            if slp < params['stop'] or sig >= params['sell']:
                gross = p_info["shares"] * price * (1 - SLIPPAGE)
                profit = gross - (p_info["shares"] * p_info["avg_price"])
                if profit > 0: gross -= profit * TAX_RATE
                cash += gross
                p_info["shares"], p_info["avg_price"] = 0, 0
                
        # [2] 매수 대상 색출 (신규 시그널이 뜰 때만 리밸런싱)
        new_signals = []
        held_tickers = []
        for ticker, p_info in port.items():
            price = df_all[ticker].values[i]
            if np.isnan(price): continue
            sig, slp = sigma_data[ticker][i], slope_data[ticker][i]
            params = PORTFOLIO_CONFIG[ticker]
            
            if p_info["shares"] > 0: 
                held_tickers.append(ticker)
            elif p_info["shares"] == 0 and slp >= params['stop'] and sig <= params['buy']:
                new_signals.append(ticker)

        # [3] 1/N 동적 자금 할당
        if len(new_signals) > 0:
            rebalance_pool = held_tickers + new_signals
            current_held_value = sum(port[t]["shares"] * df_all[t].values[i] for t in held_tickers)
            total_equity = cash + current_held_value
            target_value_per_asset = total_equity / len(rebalance_pool)
            
            # 비중 초과 매도
            for ticker in rebalance_pool:
                if port[ticker]["shares"] > 0:
                    price = df_all[ticker].values[i]
                    current_val = port[ticker]["shares"] * price
                    if current_val > target_value_per_asset:
                        excess_val = current_val - target_value_per_asset
                        shares_to_sell = excess_val / price
                        gross = shares_to_sell * price * (1 - SLIPPAGE)
                        profit = gross - (shares_to_sell * port[ticker]["avg_price"])
                        if profit > 0: gross -= profit * TAX_RATE
                        cash += gross
                        port[ticker]["shares"] -= shares_to_sell
            
            # 비중 부족 매수
            for ticker in rebalance_pool:
                price = df_all[ticker].values[i]
                current_val = port[ticker]["shares"] * price
                if current_val < target_value_per_asset:
                    deficit_val = target_value_per_asset - current_val
                    actual_invest = min(deficit_val, cash * 0.99) 
                    if actual_invest > 10000:
                        shares_to_buy = (actual_invest * (1 - SLIPPAGE)) / price
                        old_val = port[ticker]["shares"] * port[ticker]["avg_price"]
                        new_val = shares_to_buy * price
                        port[ticker]["shares"] += shares_to_buy
                        port[ticker]["avg_price"] = (old_val + new_val) / port[ticker]["shares"]
                        cash -= actual_invest

        # [4] 일일 자산 기록
        day_equity = cash + sum(port[t]["shares"] * (df_all[t].values[i] if not np.isnan(df_all[t].values[i]) else 0) for t in port)
        daily_equity.append(day_equity)
        
    return dates[LR_WINDOW:], daily_equity

# =====================================================================
# 🖥️ 4. 스트림릿 화면(UI) 렌더링 부
# =====================================================================
st.set_page_config(page_title="13야수 퀀트 포트폴리오", layout="wide")

st.title("🦁 13야수 하이브리드 포트폴리오 대시보드")
st.markdown("회원님의 오리지널 로직 (트레일링 방어 + 1/N 자동 리밸런싱 + 현실 세금/수수료 반영)")

with st.spinner('데이터를 불러오고 백테스트를 수행 중입니다... (최초 1회 약 5~10초 소요)'):
    df_all, sigmas, slopes = load_and_preprocess_data()
    dates, equity_curve = run_hybrid_portfolio(df_all, sigmas, slopes)

# --- 결과 계산 ---
START_CAPITAL = 20000000
final_capital = equity_curve[-1]
cagr = ((final_capital / START_CAPITAL) ** (252 / len(equity_curve)) - 1) * 100
peak = np.maximum.accumulate(equity_curve)
mdd = ((np.array(equity_curve) - peak) / peak).min() * 100

# --- 화면 상단 요약 대시보드 ---
col1, col2, col3 = st.columns(3)
col1.metric("▶ 총 운용 자산", f"{final_capital:,.0f} 원", f"수익금: {final_capital - START_CAPITAL:,.0f} 원")
col2.metric("🚀 연 복리 (CAGR)", f"{cagr:.2f} %")
col3.metric("📉 최대 낙폭 (MDD)", f"{mdd:.2f} %", delta_color="inverse")

st.divider()

# --- 자산 우상향 차트 ---
st.subheader("📈 포트폴리오 자산 성장 곡선")
chart_data = pd.DataFrame({'총 자산(원)': equity_curve}, index=dates)
st.line_chart(chart_data, use_container_width=True)

st.success("데이터 로딩 및 시뮬레이션 완료!")
