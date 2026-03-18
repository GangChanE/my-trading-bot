import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

# =====================================================================
# ⚙️ 1. 최종 확정 파라미터 (13야수 하이브리드 V3)
# =====================================================================
PORTFOLIO_CONFIG = {
    # --- 🛡️ 수비수 (이웃 1위 방어형) ---
    "305540.KS": {"name": "TIGER 2차전지테마", "buy": -3.5, "sell": 0.8, "stop": -0.8},
    "139230.KS": {"name": "TIGER 200중공업", "buy": -2.4, "sell": 1.0, "stop": -0.2},
    "091180.KS": {"name": "KODEX 자동차", "buy": -3.0, "sell": 1.8, "stop": -5.0},
    "371160.KS": {"name": "TIGER 차이나항셍테크", "buy": -2.5, "sell": 0.7, "stop": -0.8},
    
    # --- ⚔️ 공격수 (스윗 1위 타격형) ---
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
# 📡 2. 실시간 데이터 스캐너 (가장 최근 종가 기준)
# =====================================================================
@st.cache_data(ttl=3600) # 1시간 주기로 캐시 갱신
def get_daily_signals():
    tickers = list(PORTFOLIO_CONFIG.keys())
    # 60일 이동평균을 구하기 위해 넉넉히 최근 150일치 데이터만 로드
    df = yf.download(tickers, period="150d", progress=False)['Close']
    df.fillna(method='ffill', inplace=True)
    
    last_date = df.index[-1].strftime("%Y년 %m월 %d일")
    
    LR_WINDOW = 60
    weights = np.arange(1, LR_WINDOW + 1) - (LR_WINDOW + 1) / 2
    sum_w2 = np.sum(weights**2)
    
    results = []
    
    for ticker in tickers:
        prices = df[ticker].values
        if len(prices) < LR_WINDOW:
            continue
            
        # 오늘(최근) 기준 지표 계산
        ma = pd.Series(prices).rolling(LR_WINDOW).mean().values[-1]
        slope = pd.Series(prices).rolling(LR_WINDOW).apply(lambda y: np.sum(weights * y) / sum_w2, raw=True).values[-1]
        lr_current = ma + slope * ((LR_WINDOW - 1) / 2)
        std = pd.Series(prices).rolling(LR_WINDOW).std().values[-1]
        
        cur_price = prices[-1]
        cur_sigma = (cur_price - lr_current) / std if std != 0 else 0
        cur_slope_pct = (slope / ma) * 100 if ma != 0 else 0
        
        # 파라미터 매칭
        params = PORTFOLIO_CONFIG[ticker]
        name = params['name']
        buy_sig = params['buy']
        sell_sig = params['sell']
        stop_slp = params['stop']
        
        # 🔥 내일 아침 트레이딩 액션 판독기 🔥
        if cur_slope_pct < stop_slp:
            signal = "🔴 전량 매도 (추세 이탈/손절)"
        elif cur_sigma >= sell_sig:
            signal = "🔵 전량 익절 (목표 도달)"
        elif cur_sigma <= buy_sig:
            signal = "🔥 신규 매수 (진입 타점)"
        else:
            signal = "⏳ 관망 (대기)"
            
        results.append({
            "종목명": name,
            "오늘 종가": f"{cur_price:,.0f} 원",
            "내일 아침 액션": signal,
            "현재 시그마": round(cur_sigma, 2),
            "(진입/청산 기준)": f"({buy_sig} / {sell_sig})",
            "현재 기울기(%)": round(cur_slope_pct, 2),
            "(손절 기준)": f"({stop_slp}%)"
        })
        
    df_result = pd.DataFrame(results)
    return df_result, last_date

# =====================================================================
# 🖥️ 3. 스트림릿 대시보드 UI
# =====================================================================
st.set_page_config(page_title="13야수 트레이딩 레이더", layout="wide")

st.title("🦁 13야수 실전 트레이딩 레이더")
st.markdown("매일 저녁 장 마감 후 확인하고, **다음 날 아침 시초가**에 기계처럼 대응하세요.")

with st.spinner('오늘 장마감 데이터를 분석 중입니다...'):
    df_signals, last_date = get_daily_signals()

if df_signals is not None and not df_signals.empty:
    st.success(f"✅ 데이터 업데이트 완료 (기준일: {last_date} 종가)")
    
    # 신규 매수나 매도 시그널이 뜬 종목만 위로 정렬 (관망은 아래로)
    def sort_signal(val):
        if "매수" in val: return 1
        elif "매도" in val or "익절" in val: return 2
        else: return 3
        
    df_signals['sort_key'] = df_signals['내일 아침 액션'].apply(sort_signal)
    df_signals = df_signals.sort_values('sort_key').drop('sort_key', axis=1).reset_index(drop=True)
    
    # 판다스 데이터프레임 스타일링 (시그널에 따라 색상 강조)
    def color_signal(val):
        if "매수" in str(val):
            return 'color: #ff4b4b; font-weight: bold;'
        elif "매도" in str(val) or "익절" in str(val):
            return 'color: #0068c9; font-weight: bold;'
        elif "관망" in str(val):
            return 'color: gray;'
        return ''
    
    styled_df = df_signals.style.map(color_signal, subset=['내일 아침 액션'])
    
    # 표 출력
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
    
    st.info("💡 **매매 가이드** \n"
            "1. **신규 매수**가 뜬 종목이 있다면, (현재 계좌 현금 ÷ 뜬 종목 수) 만큼 다음 날 시초가에 매수합니다.\n"
            "2. 보유 중인 종목에 **매도/익절**이 떴다면 다음 날 시초가에 미련 없이 전량 던집니다.\n"
            "3. **관망**은 아무것도 하지 않고 구경만 합니다.")
else:
    st.error("데이터를 불러오지 못했습니다. 야후 파이낸스 서버 상태를 확인해 주세요.")
