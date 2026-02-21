import streamlit as st
import requests
import pandas as pd
import numpy as np
from scipy.stats import linregress
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# ==========================================
# ⚙️ 1. 웹페이지 기본 설정 및 파라미터
# ==========================================
st.set_page_config(page_title="All-Weather Beast 알리미", page_icon="🦁", layout="centered")

WINDOW = 60
MA_FILTER = 120

TARGETS = [
    {'name': 'KODEX 은선물(H)',   'tk': '144600.KS', 'ent': 1.7, 'ext': 0.3},
    {'name': 'TIGER 200 중공업',  'tk': '139230.KS', 'ent': 2.7, 'ext': -0.5},
    {'name': 'KODEX 보험',        'tk': '140700.KS', 'ent': 2.3, 'ext': 1.5},
    {'name': 'TIGER 헬스케어',    'tk': '143860.KS', 'ent': 2.1, 'ext': 0.7}
]
PARKING_NDX = {'name': 'TIGER 미국나스닥100', 'tk': '133690.KS'}

# 캐싱을 통해 웹 새로고침 시 반복적인 야후 데이터 요청 방지
@st.cache_data(ttl=3600) 
def get_data(ticker):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1y"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=5).json()
        closes = resp['chart']['result'][0]['indicators']['quote'][0]['close']
        df = pd.DataFrame({'Close': closes}, index=pd.to_datetime(resp['chart']['result'][0]['timestamp'], unit='s'))
        return df['Close'].dropna()
    except: 
        return pd.Series(dtype=float)

# ==========================================
# 🚀 2. 웹 UI 구성 및 데이터 분석
# ==========================================
st.title("🦁 All-Weather Beast 실전 알리미")
st.write(f"**기준일:** {datetime.now().strftime('%Y-%m-%d')} | **실행 시간:** 내일 아침 09:05")
st.markdown("---")

# 분석 진행 상태 표시
with st.spinner("야후 파이낸스에서 최신 데이터를 불러와 시그널을 분석 중입니다..."):
    results = []
    buy_list = []
    sell_list = []

    # 야수 종목 분석
    for t in TARGETS:
        series = get_data(t['tk'])
        if len(series) < MA_FILTER:
            continue

        curr_price = series.iloc[-1]
        ma120 = series.rolling(window=MA_FILTER).mean().iloc[-1]
        is_trend_up = curr_price >= ma120
        trend_icon = "🟢 상승" if is_trend_up else "🔴 하락"

        y = series.values[-WINDOW:]
        x = np.arange(WINDOW)
        res = linregress(x, y)
        D = np.std(y - (res.slope*x + res.intercept))
        current_sigma = 0 if D == 0 else (curr_price - (res.slope * (WINDOW-1) + res.intercept)) / D

        action = ""
        # 로직 판별
        if is_trend_up and res.slope > 0 and current_sigma <= -t['ent']:
            action = "🔥 신규 매수 (과매도 진입)"
            buy_list.append(t['name'])
        elif not is_trend_up:
            action = "🚨 전량 매도 (120일선 이탈 손절)"
            sell_list.append(t['name'])
        elif current_sigma >= t['ext']:
            action = "💰 전량 매도 (목표가 익절)"
            sell_list.append(t['name'])
        else:
            action = "👌 보유 또는 대기"

        results.append({
            "종목명": t['name'],
            "현재가": f"{curr_price:,.0f}",
            "120일선": f"{ma120:,.0f}",
            "추세": trend_icon,
            "Sigma": f"{current_sigma:.2f}",
            "상태/액션": action
        })

    # 파킹 자산 분석
    ndx_series = get_data(PARKING_NDX['tk'])
    ndx_price = ndx_series.iloc[-1]
    ndx_ma120 = ndx_series.rolling(window=MA_FILTER).mean().iloc[-1]
    ndx_trend = "🟢 상승 (나스닥 파킹)" if ndx_price >= ndx_ma120 else "🔴 하락 (완전 현금 파킹)"

# ==========================================
# 📊 3. 화면 출력 (테이블 및 액션 플랜)
# ==========================================
st.subheader("📊 야수 종목 시그널 현황")
# 데이터프레임으로 변환하여 웹에 예쁜 표로 출력
df_results = pd.DataFrame(results)
st.dataframe(df_results, use_container_width=True, hide_index=True)

st.subheader("🛡️ 파킹 자산 상태")
st.info(f"**{PARKING_NDX['name']}** | 현재가: {ndx_price:,.0f} | 120일선: {ndx_ma120:,.0f} | **상태: {ndx_trend}**")

st.markdown("---")
st.subheader("📝 내일 아침 09:05 실행 가이드")

if buy_list or sell_list:
    if sell_list:
        st.error(f"1️⃣ 보유 중인 **{', '.join(sell_list)}** 종목이 있다면 전량 매도(청산) 하세요.")
    if buy_list:
        st.success(f"2️⃣ 매도 대금 및 파킹 자금을 모아 **{', '.join(buy_list)}** 종목을 1/N로 나누어 매수하세요.")
    
    parking_action = ndx_trend.split('(')[1].replace(')','')
    st.warning(f"3️⃣ 매수 후 남는 현금이 있다면, 현재 장세에 따라 **[{parking_action}]** 하세요.")
else:
    parking_action = ndx_trend.split('(')[1].replace(')','')
    st.success(f"▶️ 포트폴리오 비중 변화 없음. 남는 현금은 **[{parking_action}]** 상태를 유지하세요.")

st.caption("※ 매매 체결은 장 시작 직후 호가 스프레드가 안정화되는 오전 9시 5분경에 진행하는 것을 권장합니다.")
