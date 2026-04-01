import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import numpy as np
from datetime import datetime
import traceback # 🚨 에러 원문 추적용 모듈 추가

# =====================================================================
# ⚙️ 1. 개편된 14야수 최종 파라미터 
# =====================================================================
PORTFOLIO_CONFIG = {
    "132030": {"name": "KODEX 골드선물(H)", "buy": -2.6, "sell": 2.0, "stop": -0.4},
    "261240": {"name": "KODEX 미국달러선물", "buy": -2.4, "sell": -1.0, "stop": -0.4},
    "091180": {"name": "KODEX 자동차", "buy": -3.0, "sell": 1.8, "stop": -0.8},
    "117680": {"name": "KODEX 철강", "buy": -3.1, "sell": 1.3, "stop": -0.8},
    "091160": {"name": "KODEX 반도체", "buy": -3.1, "sell": 2.3, "stop": -0.8},
    "305540": {"name": "TIGER 2차전지테마", "buy": -3.5, "sell": 1.7, "stop": -1.0},
    "139230": {"name": "TIGER 200중공업", "buy": -2.4, "sell": -0.6, "stop": -0.4},
    "371160": {"name": "TIGER 차이나항셍테크", "buy": -2.5, "sell": -1.0, "stop": -0.4},
    "157490": {"name": "TIGER 소프트웨어", "buy": -3.4, "sell": 2.3, "stop": -0.6},
    "261070": {"name": "TIGER 코스닥150바이오", "buy": -3.4, "sell": 2.1, "stop": -0.4},
    "245360": {"name": "TIGER 차이나HSCEI", "buy": -4.3, "sell": -0.6, "stop": -0.4},
    "261220": {"name": "KODEX WTI원유선물(H)", "buy": -3.4, "sell": 2.6, "stop": -0.4},
    "144600": {"name": "KODEX 은선물(H)", "buy": -4.1, "sell": 2.2, "stop": -0.6},
    "138910": {"name": "KODEX 구리선물(H)", "buy": -3.4, "sell": 2.0, "stop": -0.8}
}

def snap_to_tick(price):
    return int(round(price / 5.0) * 5)

# =====================================================================
# 📡 2. 실시간 상태 시뮬레이터 (에러 추적기 탑재)
# =====================================================================
@st.cache_data(ttl=3600) 
def get_daily_signals():
    tickers = list(PORTFOLIO_CONFIG.keys())
    results = []
    last_date_str = "업데이트 중"
    
    LR_WINDOW = 60
    weights = np.arange(1, LR_WINDOW + 1) - (LR_WINDOW + 1) / 2
    sum_w2 = np.sum(weights**2)
    
    for ticker in tickers:
        params = PORTFOLIO_CONFIG[ticker]
        
        try:
            df = fdr.DataReader(ticker, start="2018-01-01")
            
            if df.empty or len(df) < LR_WINDOW + 1:
                results.append({
                    "종목명": params['name'],
                    "액션 (내일 시초가)": f"⚠️ 데이터 60개 미만 (현재 {len(df)}개)",
                    "오늘 종가": "-", "현재 시그마": "-", "현재 기울기": "-", 
                    "손절 기준선": "-", "최근 매수기록": "-", "최근 매도기록": "-"
                })
                continue
            
            df['Close'] = df['Close'].fillna(method='ffill')
            df['Open'] = df['Open'].fillna(method='ffill')
            
            prices_close = df['Close'].values
            prices_open = df['Open'].values
            dates = df.index
            
            last_date_str = dates[-1].strftime("%Y년 %m월 %d일")
            
            ma_arr = pd.Series(prices_close).rolling(LR_WINDOW).mean().values
            slp_arr = pd.Series(prices_close).rolling(LR_WINDOW).apply(lambda y: np.sum(weights * y) / sum_w2, raw=True).values
            lr_cur_arr = ma_arr + slp_arr * ((LR_WINDOW - 1) / 2)
            std_arr = pd.Series(prices_close).rolling(LR_WINDOW).std().values
            
            sig_arr = np.divide(prices_close - lr_cur_arr, std_arr, out=np.zeros_like(prices_close), where=std_arr!=0)
            slope_pct_arr = np.divide(slp_arr, ma_arr, out=np.zeros_like(slp_arr), where=ma_arr!=0) * 100
            
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
            
        except Exception as e:
            # 🚨 [핵심 변경점] 뭉뚱그린 에러 메시지 대신 실제 에러 원문을 표에 때려 박습니다.
            error_msg = str(e)
            results.append({
                "종목명": params['name'],
                "액션 (내일 시초가)": f"❌ 에러: {error_msg}",
                "오늘 종가": "-", "현재 시그마": "-", "현재 기울기": "-", 
                "손절 기준선": "-", "최근 매수기록": "-", "최근 매도기록": "-"
            })
            continue
            
    return pd.DataFrame(results), last_date_str

# =====================================================================
# 🖥️ 3. 스트림릿 대시보드 UI
# =====================================================================
st.set_page_config(page_title="14야수 트레이딩 레이더", layout="wide")

st.title("🦁 14야수 실전 트레이딩 레이더 (디버그 모드)")

st.markdown("과거 타점을 추적하여 **내일 아침 시초가(Open)에 던질 시그널**을 띄워줍니다.")

with st.spinner('전체 매매 히스토리를 추적하며 장마감 데이터를 분석 중입니다...'):
    df_signals, last_date = get_daily_signals()

if df_signals is not None and not df_signals.empty:
    st.success(f"✅ 분석 완료 (가장 최근 정상 데이터 기준: {last_date})")
    
    # 에러 원문이 길 수 있으므로 표 설정을 약간 조정
    st.dataframe(df_signals, use_container_width=True, hide_index=True, height=600)
    
else:
    st.error("전체 시스템이 멈췄습니다. 데이터를 아예 가져오지 못했습니다.")
