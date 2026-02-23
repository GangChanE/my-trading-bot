import streamlit as st
import requests
import pandas as pd
import numpy as np
from scipy.stats import linregress
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# ==========================================
# ⚙️ 1. [Final Masterpiece] 5대 야수 & FANG+ 파킹 설정
# ==========================================
st.set_page_config(page_title="All-Weather Beast : Masterpiece", page_icon="🦁", layout="centered")

WINDOW = 60
MA_FILTER = 120

# 🦁 최강의 5대 야수 라인업 (최종 최적화 파라미터 적용)
TARGETS = [
    # 1. 인플레이션 방어 (원자재)
    {'name': 'KODEX 은선물(H)',   'tk': '144600.KS', 'ent': 1.7, 'ext': 0.3},
    # 2. 경기 민감 & 조선 (가치주)
    {'name': 'TIGER 200 중공업',  'tk': '139230.KS', 'ent': 2.7, 'ext': -0.5},
    # 3. 금리 인상 수혜 (금융)
    {'name': 'KODEX 보험',        'tk': '140700.KS', 'ent': 2.3, 'ext': 1.5},
    # 4. 개별 성장 & 바이오 (성장주)
    {'name': 'TIGER 헬스케어',    'tk': '143860.KS', 'ent': 2.1, 'ext': 0.7},
    # 5. 필수 소비재 & 수출 (스나이퍼 모드: 진입 -3.4)
    {'name': 'HANARO Fn K-푸드',  'tk': '426030.KS', 'ent': 3.4, 'ext': 1.9}
]

# 🏎️ 슈퍼 파킹 자산 (FANG플러스: 나스닥 상위 호환)
PARKING_ASSET = {'name': 'KODEX 미국FANG플러스(H)', 'tk': '314250.KS'}

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
# 🚀 2. 데이터 분석 및 시그널 판별
# ==========================================
st.title("🦁 All-Weather Beast")
st.caption("The Masterpiece : 5 Beasts & FANG+ Strategy")
st.write(f"**기준일:** {datetime.now().strftime('%Y-%m-%d')} | **실행:** 내일 아침 09:05")
st.markdown("---")

with st.spinner("야수들과 FANG+의 동태를 정밀 분석 중입니다..."):
    results = []
    buy_list = []
    sell_list = []
    
    # --- 1. 야수 종목 분석 ---
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
        # [매수] 120일선 위 & 기울기 양수 & 과매도 진입
        if is_trend_up and res.slope > 0 and current_sigma <= -t['ent']:
            action = "🔥 신규 매수 (진입)"
            buy_list.append(t['name'])
        # [손절] 120일선 이탈 시 즉시 손절
        elif not is_trend_up:
            action = "🚨 전량 매도 (손절: 120일선 이탈)"
            sell_list.append(t['name'])
        # [익절] 목표 시그마 도달
        elif current_sigma >= t['ext']:
            action = "💰 전량 매도 (익절: 목표가 도달)"
            sell_list.append(t['name'])
        else:
            action = "👌 보유 또는 대기"

        results.append({
            "종목명": t['name'],
            "현재가": f"{curr_price:,.0f}",
            "120일선": f"{ma120:,.0f}",
            "추세": trend_icon,
            "Sigma": f"{current_sigma:.2f}",
            "판단": action
        })

    # --- 2. 슈퍼 파킹 자산 (FANG+) 분석 ---
    park_series = get_data(PARKING_ASSET['tk'])
    park_price = park_series.iloc[-1]
    park_ma120 = park_series.rolling(window=MA_FILTER).mean().iloc[-1]
    
    # 파킹 로직: 120일선 위면 매수, 아니면 현금
    if park_price >= park_ma120:
        park_status = "🟢 상승 (FANG+ 매수/보유)"
        park_action = "FANG플러스 전량 매수/보유"
    else:
        park_status = "🔴 하락 (전량 현금 보유)"
        park_action = "전량 현금 보유 (Risk Off)"

# ==========================================
# 📊 3. 웹 UI 출력
# ==========================================
st.subheader("📊 5대 야수 시그널")
df_results = pd.DataFrame(results)

# 스타일링
def color_trend(val):
    color = 'red' if '하락' in val else 'green'
    return f'color: {color}'

st.dataframe(df_results.style.applymap(color_trend, subset=['추세']), use_container_width=True, hide_index=True)

st.subheader("🏎️ 슈퍼 파킹 자산 (FANG+)")
st.info(f"**{PARKING_ASSET['name']}** | 현재가: {park_price:,.0f} | 120일선: {park_ma120:,.0f} | **상태: {park_status}**")

st.markdown("---")
st.subheader("📝 내일 아침 행동 강령")

if buy_list or sell_list:
    if sell_list:
        st.error(f"1️⃣ 보유 중인 **{', '.join(sell_list)}** 종목을 전량 매도(청산/손절) 하세요.")
    if buy_list:
        st.success(f"2️⃣ 확보된 현금(매도금+파킹금)을 모아 **{', '.join(buy_list)}** 종목을 1/N로 나누어 매수하세요.")
    
    st.warning(f"3️⃣ 매수 후 남는 현금이 있다면, **[{park_action}]** 상태로 운용하세요.")
else:
    st.success(f"▶️ 포트폴리오 변경 없음. 남는 현금은 **[{park_action}]** 상태를 유지하세요.")

st.markdown("---")
st.caption("Final Strategy V2.0 | 5 Beasts + FANG Parking | 120-Day Stop Loss Enabled")
