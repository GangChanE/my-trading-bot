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
# 📡 2. 실시간 상태 시뮬레이터 (진입 기울기 기억 & 히스토리 추적)
# =====================================================================
@st.cache_data(ttl=3600) 
def get_daily_signals():
    tickers = list(PORTFOLIO_CONFIG.keys())
    # 최근 매수/매도 기록을 찾기 위해 넉넉히 2년 치 데이터 로드
    df = yf.download(tickers, period="2y", progress=False)['Close']
    
    if df is None or df.empty:
        return None, None
        
    df.fillna(method='ffill', inplace=True)
    dates = df.index
    last_date = dates[-1].strftime("%Y년 %m월 %d일")
    
    LR_WINDOW = 60
    weights = np.arange(1, LR_WINDOW + 1) - (LR_WINDOW + 1) / 2
    sum_w2 = np.sum(weights**2)
    
    results = []
    
    for ticker in tickers:
        prices = df[ticker].values
        if len(prices) < LR_WINDOW + 1: continue
            
        # 벡터화된 연산으로 전 기간 지표 한 번에 계산
        ma_arr = pd.Series(prices).rolling(LR_WINDOW).mean().values
        slp_arr = pd.Series(prices).rolling(LR_WINDOW).apply(lambda y: np.sum(weights * y) / sum_w2, raw=True).values
        lr_cur_arr = ma_arr + slp_arr * ((LR_WINDOW - 1) / 2)
        std_arr = pd.Series(prices).rolling(LR_WINDOW).std().values
        
        # 0 나누기 방지
        sig_arr = np.divide(prices - lr_cur_arr, std_arr, out=np.zeros_like(prices), where=std_arr!=0)
        slope_pct_arr = np.divide(slp_arr, ma_arr, out=np.zeros_like(slp_arr), where=ma_arr!=0) * 100
        
        params = PORTFOLIO_CONFIG[ticker]
        buy_sig, sell_sig, stop_drop = params['buy'], params['sell'], params['stop']
        
        # 🔥 상태 시뮬레이션 (어제까지의 매매 상태를 앱이 스스로 추적)
        state = 0 # 0: 대기 중, 1: 보유 중
        entry_slope = 0
        last_buy_dt, last_buy_px = "-", 0
        last_sell_dt, last_sell_px = "-", 0
        
        for i in range(LR_WINDOW, len(prices) - 1):
            s, l, p = sig_arr[i], slope_pct_arr[i], prices[i]
            d_str = dates[i].strftime("%y/%m/%d")
            
            if state == 1:
                # 익절 또는 손절(진입 기울기 대비 하락)
                if l < (entry_slope + stop_drop) or s >= sell_sig:
                    state = 0
                    last_sell_dt, last_sell_px = d_str, p
                    entry_slope = 0
            else:
                # 신규 진입 (기울기 기억)
                if s <= buy_sig:
                    state = 1
                    last_buy_dt, last_buy_px = d_str, p
                    entry_slope = l
                    
        # 🔥 오늘 종가 기준 '내일 액션' 판독
        cur_price = prices[-1]
        cur_sig = sig_arr[-1]
        cur_slp = slope_pct_arr[-1]
        
        stop_target_str = "-"
        
        if state == 1:
            stop_target = entry_slope + stop_drop
            stop_target_str = f"하락 이탈선: {stop_target:.2f}%"
            if cur_slp < stop_target:
                action = "🔴 전량 손절"
            elif cur_sig >= sell_sig:
                action = "🔵 전량 익절"
            else:
                action = "⏳ 보유 중"
        else:
            if cur_sig <= buy_sig:
                action = "🔥 신규 매수"
            else:
                action = "⏳ 대기 중"
                
        # 출력 결과 정리 (소수점 2자리 문자열 포매팅)
        results.append({
            "종목명": params['name'],
            "액션 (내일 시초가)": action,
            "현재가": f"{cur_price:,.0f} 원",
            "현재 시그마": f"{cur_sig:.2f}",
            "현재 기울기": f"{cur_slp:.2f}%",
            "손절 기준선": stop_target_str,
            "최근 매수기록": f"{last_buy_dt} ({last_buy_px:,.0f}원)" if last_buy_px > 0 else "-",
            "최근 매도기록": f"{last_sell_dt} ({last_sell_px:,.0f}원)" if last_sell_px > 0 else "-"
        })
        
    return pd.DataFrame(results), last_date

# =====================================================================
# 🖥️ 3. 스트림릿 대시보드 UI
# =====================================================================
st.set_page_config(page_title="13야수 트레이딩 레이더", layout="wide")

st.title("🦁 13야수 실전 트레이딩 레이더")
st.markdown("앱이 회원님의 과거 타점(기울기)을 스스로 기억하여 **정확한 손절/익절 시그널**을 띄워줍니다.")

with st.spinner('히스토리를 추적하며 오늘 장마감 데이터를 분석 중입니다...'):
    df_signals, last_date = get_daily_signals()

if df_signals is not None and not df_signals.empty:
    st.success(f"✅ 데이터 업데이트 완료 (기준일: {last_date} 종가)")
    
    # 🚨 정렬: 당장 행동해야 할 종목(매수/손절/익절)이 맨 위로 오도록
    def sort_signal(val):
        if "매수" in val: return 1
        elif "손절" in val: return 2
        elif "익절" in val: return 3
        else: return 4
        
    df_signals['sort_key'] = df_signals['액션 (내일 시초가)'].apply(sort_signal)
    df_signals = df_signals.sort_values(['sort_key', '종목명']).drop('sort_key', axis=1).reset_index(drop=True)
    
    # 🎨 색상 강조 스타일링
    def color_signal(val):
        if "매수" in str(val): return 'color: #ff4b4b; font-weight: bold; background-color: #ffe6e6;'
        elif "손절" in str(val): return 'color: #ffffff; font-weight: bold; background-color: #ff4b4b;'
        elif "익절" in str(val): return 'color: #ffffff; font-weight: bold; background-color: #0068c9;'
        elif "보유" in str(val): return 'color: #008000; font-weight: bold;'
        elif "대기" in str(val): return 'color: #808080;'
        return ''
    
    styled_df = df_signals.style.map(color_signal, subset=['액션 (내일 시초가)'])
    
    # 표 출력
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
    
    st.divider()
    
    st.subheader("💡 섀넌의 악마 (1/N 강제 리밸런싱) 실천 가이드")
    st.info("""
    **1. 매일 아침 단 5분만 투자하세요.**
    - 위 표에서 `🔥 신규 매수`, `🔵 전량 익절`, `🔴 전량 손절`이 뜬 종목이 있는지 확인합니다. 
    - 만약 행동해야 할 종목이 있다면, MTS(증권사 앱)를 켜서 아래 2번을 수행합니다.

    **2. 1/N 리밸런싱 예산 맞추기**
    - **타겟 금액 = (총 계좌 평가금액) ÷ (보유 중인 종목 수 + 신규 매수할 종목 수)** - 익절/손절 종목은 시초가에 전량 던져 현금을 확보합니다.
    - 기존 보유 종목 중 수익이 나서 비중이 커진 것은 타겟 금액만큼 덜어내고(매도), 부족해진 종목과 신규 진입 종목은 타겟 금액만큼 채워 넣습니다(매수).
    """)
else:
    st.error("데이터를 불러오지 못했습니다. 잠시 후 새로고침 해주세요.")
