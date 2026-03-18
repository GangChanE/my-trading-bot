import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

# =====================================================================
# ⚙️ 1. 개편된 14야수 최종 파라미터 (게임산업 OUT, 골드/달러 IN)
# =====================================================================
PORTFOLIO_CONFIG = {
    "132030.KS": {"name": "KODEX 골드선물(H)", "buy": -2.6, "sell": 2.0, "stop": -0.4},
    "261240.KS": {"name": "KODEX 미국달러선물", "buy": -2.4, "sell": -1.0, "stop": -0.4},
    "091180.KS": {"name": "KODEX 자동차", "buy": -3.0, "sell": 1.8, "stop": -0.8},
    "117680.KS": {"name": "KODEX 철강", "buy": -3.1, "sell": 1.3, "stop": -0.8},
    "091160.KS": {"name": "KODEX 반도체", "buy": -3.1, "sell": 2.3, "stop": -0.8},
    "305540.KS": {"name": "TIGER 2차전지테마", "buy": -3.5, "sell": 1.7, "stop": -1.0},
    "139230.KS": {"name": "TIGER 200중공업", "buy": -2.4, "sell": -0.6, "stop": -0.4},
    "371160.KS": {"name": "TIGER 차이나항셍테크", "buy": -2.5, "sell": -1.0, "stop": -0.4},
    "157490.KS": {"name": "TIGER 소프트웨어", "buy": -3.4, "sell": 2.3, "stop": -0.6},
    "261070.KS": {"name": "TIGER 코스닥150바이오", "buy": -3.4, "sell": 2.1, "stop": -0.4},
    "245360.KS": {"name": "TIGER 차이나HSCEI", "buy": -4.3, "sell": -0.6, "stop": -0.4},
    "261220.KS": {"name": "KODEX WTI원유선물(H)", "buy": -3.4, "sell": 2.6, "stop": -0.4},
    "144600.KS": {"name": "KODEX 은선물(H)", "buy": -4.1, "sell": 2.2, "stop": -0.6},
    "138910.KS": {"name": "KODEX 구리선물(H)", "buy": -3.4, "sell": 2.0, "stop": -0.8}
}

def snap_to_tick(price):
    return int(round(price / 5.0) * 5)

# =====================================================================
# 📡 2. 실시간 상태 시뮬레이터 (T일 종가 시그널 -> T+1일 시가 체결)
# =====================================================================
@st.cache_data(ttl=3600) 
def get_daily_signals():
    tickers = list(PORTFOLIO_CONFIG.keys())
    
    df_raw = yf.download(tickers, start="2018-01-01", progress=False)
    
    if df_raw is None or df_raw.empty:
        return None, None
        
    df_close = df_raw['Close'].fillna(method='ffill')
    df_open = df_raw['Open'].fillna(method='ffill')
    
    dates = df_close.index
    last_date = dates[-1].strftime("%Y년 %m월 %d일")
    
    LR_WINDOW = 60
    weights = np.arange(1, LR_WINDOW + 1) - (LR_WINDOW + 1) / 2
    sum_w2 = np.sum(weights**2)
    
    results = []
    
    for ticker in tickers:
        prices_close = df_close[ticker].values
        prices_open = df_open[ticker].values
        
        if len(prices_close) < LR_WINDOW + 1: continue
            
        ma_arr = pd.Series(prices_close).rolling(LR_WINDOW).mean().values
        slp_arr = pd.Series(prices_close).rolling(LR_WINDOW).apply(lambda y: np.sum(weights * y) / sum_w2, raw=True).values
        lr_cur_arr = ma_arr + slp_arr * ((LR_WINDOW - 1) / 2)
        std_arr = pd.Series(prices_close).rolling(LR_WINDOW).std().values
        
        sig_arr = np.divide(prices_close - lr_cur_arr, std_arr, out=np.zeros_like(prices_close), where=std_arr!=0)
        slope_pct_arr = np.divide(slp_arr, ma_arr, out=np.zeros_like(slp_arr), where=ma_arr!=0) * 100
        
        params = PORTFOLIO_CONFIG[ticker]
        buy_sig, sell_sig, stop_drop = params['buy'], params['sell'], params['stop']
        
        state = 0 
        entry_slope = 0
        last_buy_dt, last_buy_px = "-", 0
        last_sell_dt, last_sell_px = "-", 0
        
        for i in range(LR_WINDOW, len(prices_close)):
            prev_i = i - 1
            s_prev, l_prev = sig_arr[prev_i], slope_pct_arr[prev_i]
            
            exec_price = prices_open[i] 
            d_str = dates[i].strftime("%y/%m/%d")
            
            if state == 1:
                if l_prev < (entry_slope + stop_drop) or s_prev >= sell_sig:
                    state = 0
                    last_sell_dt, last_sell_px = d_str, exec_price 
                    entry_slope = 0
            else:
                if s_prev <= buy_sig:
                    state = 1
                    last_buy_dt, last_buy_px = d_str, exec_price 
                    entry_slope = l_prev
                    
        cur_price_close = prices_close[-1] 
        cur_sig = sig_arr[-1] 
        cur_slp = slope_pct_arr[-1] 
        
        stop_target_str = "-"
        
        if state == 1:
            stop_target = entry_slope + stop_drop
            stop_target_str = f"{stop_target:.2f} %" 
            sigma_display = f"{cur_sig:.2f} (매도: {sell_sig})"
            
            if cur_slp < stop_target:
                action = "🔴 전량 손절"
            elif cur_sig >= sell_sig:
                action = "🔵 전량 익절"
            else:
                action = "⏳ 보유 중"
        else:
            sigma_display = f"{cur_sig:.2f} (매수: {buy_sig})"
            
            if cur_sig <= buy_sig:
                action = "🔥 신규 매수"
            else:
                action = "⏳ 대기 중"
                
        results.append({
            "종목명": params['name'],
            "액션 (내일 시초가)": action,
            "오늘 종가": f"{snap_to_tick(cur_price_close):,.0f} 원",
            "현재 시그마": sigma_display,
            "현재 기울기": f"{cur_slp:.2f} %",
            "손절 기준선": stop_target_str,
            "최근 매수기록": f"{last_buy_dt} ({snap_to_tick(last_buy_px):,.0f}원)" if last_buy_px > 0 else "-",
            "최근 매도기록": f"{last_sell_dt} ({snap_to_tick(last_sell_px):,.0f}원)" if last_sell_px > 0 else "-"
        })
        
    return pd.DataFrame(results), last_date

# =====================================================================
# 🖥️ 3. 스트림릿 대시보드 UI
# =====================================================================
st.set_page_config(page_title="14야수 트레이딩 레이더", layout="wide")

st.title("🦁 14야수 실전 트레이딩 레이더")

st.markdown("과거 타점을 추적하여 **내일 아침 시초가(Open)에 던질 시그널**을 띄워줍니다.  \n*(백테스트 기간: 2021.03.17 ~ 현재 | 연 복리 14.07% | MDD -23.75%)*")

with st.spinner('전체 매매 히스토리를 추적하며 오늘 장마감 데이터를 분석 중입니다...'):
    df_signals, last_date = get_daily_signals()

if df_signals is not None and not df_signals.empty:
    st.success(f"✅ 데이터 업데이트 완료 (기준일: {last_date} 종가)")
    
    def sort_signal(val):
        if "매수" in val: return 1
        elif "손절" in val: return 2
        elif "익절" in val: return 3
        elif "보유" in val: return 4
        else: return 5
        
    df_signals['sort_key'] = df_signals['액션 (내일 시초가)'].apply(sort_signal)
    df_signals = df_signals.sort_values(['sort_key', '종목명']).drop('sort_key', axis=1).reset_index(drop=True)
    
    def color_signal(val):
        if "매수" in str(val): return 'color: #ff4b4b; font-weight: bold; background-color: #ffe6e6;'
        elif "손절" in str(val): return 'color: #ffffff; font-weight: bold; background-color: #ff4b4b;'
        elif "익절" in str(val): return 'color: #ffffff; font-weight: bold; background-color: #0068c9;'
        elif "보유" in str(val): return 'color: #008000; font-weight: bold;'
        elif "대기" in str(val): return 'color: #808080;'
        return ''
    
    styled_df = df_signals.style.map(color_signal, subset=['액션 (내일 시초가)'])
    
    # 🔥 표 높이를 600픽셀로 늘려서 14개 종목이 한 번에 보이게 설정!
    st.dataframe(styled_df, use_container_width=True, hide_index=True, height=600)
    
    st.divider()
    
    st.subheader("💡 섀넌의 악마 (1/N 강제 리밸런싱) 실천 가이드")
    st.info("""
    **1. 매일 아침 단 5분만 투자하세요.**
    - 위 표에서 `🔥 신규 매수`, `🔵 전량 익절`, `🔴 전량 손절`이 뜬 종목이 있는지 확인합니다. 
    - 만약 행동해야 할 종목이 있다면, MTS(증권사 앱)를 켜서 장 시작(9시)과 동시에 **'시장가' 또는 '시초가'**로 주문을 넣습니다.

    **2. 1/N 리밸런싱 예산 맞추기**
    - **타겟 금액 = (총 계좌 평가금액) ÷ (보유 중인 종목 수 + 신규 매수할 종목 수)**
    - 익절/손절 종목은 시초가에 전량 던져 현금을 확보합니다.
    - 기존 보유 종목 중 수익이 나서 비중이 커진 것은 타겟 금액만큼 덜어내고(매도), 부족해진 종목과 신규 진입 종목은 타겟 금액만큼 채워 넣습니다(매수).
    """)
else:
    st.error("데이터를 불러오지 못했습니다. 잠시 후 새로고침 해주세요.")
