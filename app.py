import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

# =====================================================================
# ⚙️ 1. 최종 확정 파라미터 (철강 방어형 + 12야수 스윗스팟)
# =====================================================================
PORTFOLIO_CONFIG = {
    # 🛡️ 수비수 (이웃 1위 방어형)
    "117680.KS": {"name": "KODEX 철강", "buy": -3.1, "sell": 1.1, "stop": -2.2},
    
    # ⚔️ 공격수 (스윗 1위 타격형)
    "091160.KS": {"name": "KODEX 반도체", "buy": -3.1, "sell": 2.3, "stop": -4.0},
    "305540.KS": {"name": "TIGER 2차전지테마", "buy": -3.3, "sell": 2.1, "stop": -2.4},
    "139230.KS": {"name": "TIGER 200중공업", "buy": -2.4, "sell": -0.7, "stop": -0.4},
    "091180.KS": {"name": "KODEX 자동차", "buy": -3.0, "sell": 1.9, "stop": -4.0},
    "118990.KS": {"name": "KODEX 게임산업", "buy": -2.0, "sell": 1.9, "stop": -0.4},
    "371160.KS": {"name": "TIGER 차이나항셍테크", "buy": -2.5, "sell": -1.0, "stop": -2.0},
    "157490.KS": {"name": "TIGER 소프트웨어", "buy": -3.4, "sell": 2.3, "stop": -2.2},
    "261070.KS": {"name": "TIGER 코스닥150바이오", "buy": -3.4, "sell": 2.1, "stop": -0.4},
    "245360.KS": {"name": "TIGER 차이나HSCEI", "buy": -3.7, "sell": -0.6, "stop": -0.4},
    "130680.KS": {"name": "KODEX WTI원유선물(H)", "buy": -3.3, "sell": 1.4, "stop": -0.6},
    "144600.KS": {"name": "KODEX 은선물(H)", "buy": -4.1, "sell": 2.0, "stop": -2.2},
    "138920.KS": {"name": "KODEX 구리선물(H)", "buy": -3.2, "sell": 0.9, "stop": -2.0}
}

# =====================================================================
# 📡 2. 실시간 데이터 스캐너 (최근 종가 기준 지표 산출)
# =====================================================================
@st.cache_data(ttl=3600) 
def get_daily_signals():
    tickers = list(PORTFOLIO_CONFIG.keys())
    df = yf.download(tickers, period="150d", progress=False)['Close']
    
    if df is None or df.empty:
        return None, None
        
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
            
        ma = pd.Series(prices).rolling(LR_WINDOW).mean().values[-1]
        slope = pd.Series(prices).rolling(LR_WINDOW).apply(lambda y: np.sum(weights * y) / sum_w2, raw=True).values[-1]
        lr_current = ma + slope * ((LR_WINDOW - 1) / 2)
        std = pd.Series(prices).rolling(LR_WINDOW).std().values[-1]
        
        cur_price = prices[-1]
        cur_sigma = (cur_price - lr_current) / std if std != 0 else 0
        cur_slope_pct = (slope / ma) * 100 if ma != 0 else 0
        
        params = PORTFOLIO_CONFIG[ticker]
        name = params['name']
        buy_sig = params['buy']
        sell_sig = params['sell']
        stop_drop = params['stop']
        
        # 🚨 액션 판별 (손절은 '진입 기울기'를 알아야 하므로 대시보드에서는 익절/매수만 지시)
        if cur_sigma >= sell_sig:
            signal = "🔵 전량 익절 (목표 도달)"
        elif cur_sigma <= buy_sig:
            signal = "🔥 신규 매수 (진입 타점)"
        else:
            signal = "⏳ 보유 / 관망"
            
        results.append({
            "종목명": name,
            "오늘 종가": f"{cur_price:,.0f} 원",
            "내일 아침 액션": signal,
            "현재 시그마": round(cur_sigma, 2),
            "(진입/청산 기준)": f"({buy_sig} / {sell_sig})",
            "현재 기울기(%)": round(cur_slope_pct, 2),
            "손절 기준": f"진입시점 대비 {stop_drop}% 하락"
        })
        
    df_result = pd.DataFrame(results)
    return df_result, last_date

# =====================================================================
# 🖥️ 3. 스트림릿 대시보드 UI
# =====================================================================
st.set_page_config(page_title="13야수 트레이딩 레이더", layout="wide")

st.title("🦁 13야수 실전 트레이딩 레이더 (CAGR 34.3% 엔진)")
st.markdown("매일 저녁 장 마감 후 시그널을 확인하고, **섀넌의 악마(매일 1/N 리밸런싱)**를 실천하세요.")

with st.spinner('오늘 장마감 데이터를 분석 중입니다...'):
    df_signals, last_date = get_daily_signals()

if df_signals is not None and not df_signals.empty:
    st.success(f"✅ 데이터 업데이트 완료 (기준일: {last_date} 종가)")
    
    # 정렬: 매수/익절 액션이 위로 오도록
    def sort_signal(val):
        if "매수" in val: return 1
        elif "익절" in val: return 2
        else: return 3
        
    df_signals['sort_key'] = df_signals['내일 아침 액션'].apply(sort_signal)
    df_signals = df_signals.sort_values('sort_key').drop('sort_key', axis=1).reset_index(drop=True)
    
    # 색상 스타일링
    def color_signal(val):
        if "매수" in str(val): return 'color: #ff4b4b; font-weight: bold;'
        elif "익절" in str(val): return 'color: #0068c9; font-weight: bold;'
        elif "관망" in str(val): return 'color: gray;'
        return ''
    
    # 출력
    styled_df = df_signals.style.map(color_signal, subset=['내일 아침 액션'])
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
    
    st.divider()
    
    # 실전 매뉴얼
    st.subheader("💡 실전 매매 매뉴얼 (필독)")
    st.info("""
    **1. 매일 아침 1/N 리밸런싱 (섀넌의 악마 작동법)**
    - 매일 시초가에 **(총 계좌 평가금액) ÷ (보유 중인 종목 수 + 신규 매수 뜬 종목 수)** 로 1/N 타겟 금액을 계산합니다.
    - 비중이 넘치는 종목은 팔아서 현금을 만들고, 부족한 종목이나 신규 진입 종목은 그 현금으로 매수하여 비중을 맞춥니다.

    **2. 익절과 손절 규칙**
    - **익절:** 레이더에 `🔵 전량 익절`이 뜨면 다음 날 시초가에 전량 매도합니다.
    - **손절 (중요!):** 웹사이트는 회원님의 '진입 시점'을 알 수 없습니다. 따라서 매수하신 날의 **'현재 기울기(%)'를 반드시 엑셀이나 메모장에 기록**해 두십시오. 매일 대시보드의 '현재 기울기'를 확인하시고, **(현재 기울기) < (기록해둔 진입 기울기 + 손절 기준)** 이 되면 레이더 지시와 상관없이 즉시 전량 손절합니다!
    """)
else:
    st.error("데이터를 불러오지 못했습니다. 잠시 후 새로고침 해주세요.")
