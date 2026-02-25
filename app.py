import streamlit as st
import requests
import pandas as pd
import numpy as np
from scipy.stats import linregress
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# ==========================================
# ⚙️ 1. [End Game] 5대 야수 & 계절성 파킹
# ==========================================
st.set_page_config(page_title="All-Weather Beast V5.0", page_icon="🦁", layout="wide")

WINDOW = 60
MA_FILTER = 120

# 🦁 5대 야수
TARGETS = [
    {'name': 'KODEX 은선물(H)',   'tk': '144600.KS', 'ent': 1.7, 'ext': 0.3},
    {'name': 'TIGER 200 중공업',  'tk': '139230.KS', 'ent': 2.7, 'ext': -0.5},
    {'name': 'KODEX 보험',        'tk': '140700.KS', 'ent': 2.3, 'ext': 1.5},
    {'name': 'TIGER 헬스케어',    'tk': '143860.KS', 'ent': 2.1, 'ext': 0.7},
    {'name': 'HANARO Fn K-POP',   'tk': '395290.KS', 'ent': 1.6, 'ext': 1.3}
]

# 🏎️ 메인 파킹 (1순위)
MAIN_PARKING = {'name': 'KODEX 미국빅테크10(H)', 'tk': '314250.KS'}

# 🍂❄️ 계절성 파킹 (2순위: Risk Off 대피소)
SEASONAL_WINTER = {'name': 'KODEX 코스닥150',   'tk': '229200.KS'} # 11~4월 (1배수)
SEASONAL_SUMMER = {'name': 'KOSEF 미국달러선물', 'tk': '138230.KS'} # 5~10월 (1배수)

@st.cache_data(ttl=3600) 
def get_data(ticker):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1y"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=5).json()
        closes = resp['chart']['result'][0]['indicators']['quote'][0]['close']
        df = pd.DataFrame({'Close': closes}, index=pd.to_datetime(resp['chart']['result'][0]['timestamp'], unit='s'))
        return df['Close'].dropna()
    except: 
        return pd.Series(dtype=float)

# ==========================================
# 🚀 2. 데이터 분석 및 시그널 판별
# ==========================================
st.title("🦁 All-Weather Beast V5.0")
st.caption("Strategy: 5 Beasts + BigTech + Seasonal Cash Parking")
st.write(f"**기준일:** {datetime.now().strftime('%Y-%m-%d')} | **실행:** 장 마감 후 확인 -> 익일 시가 매매")
st.markdown("---")

with st.spinner("야수, 빅테크, 그리고 계절을 분석 중입니다..."):
    results = []
    buy_list = []
    sell_list = []
    
    # --- A. 야수 종목 분석 ---
    for t in TARGETS:
        series = get_data(t['tk'])
        if len(series) < MA_FILTER: continue

        curr_price = series.iloc[-1]
        ma120 = series.rolling(window=MA_FILTER).mean().iloc[-1]
        is_trend_up = curr_price >= ma120
        trend_icon = "🟢 상승" if is_trend_up else "🔴 하락"

        y = series.values[-WINDOW:]
        x = np.arange(WINDOW)
        res = linregress(x, y)
        
        L = res.slope * (WINDOW-1) + res.intercept
        D = np.std(y - (res.slope*x + res.intercept))
        current_sigma = 0 if D == 0 else (curr_price - L) / D

        # 목표가 계산
        buy_target_price = L + (-t['ent'] * D)
        sell_target_price = L + (t['ext'] * D)

        action = ""
        # 로직
        if is_trend_up and res.slope > 0 and current_sigma <= -t['ent']:
            action = "🔥 신규 매수"
            buy_list.append(t['name'])
        elif not is_trend_up:
            action = "🚨 손절 (120일선 이탈)"
            sell_list.append(t['name'])
        elif current_sigma >= t['ext']:
            action = "💰 익절 (목표가 도달)"
            sell_list.append(t['name'])
        else:
            action = "👌 보유/대기"

        results.append({
            "종목명": t['name'],
            "현재가": f"{curr_price:,.0f}",
            "추세": trend_icon,
            "Sigma": f"{current_sigma:.2f}",
            "진입 목표": f"-{t['ent']} ({buy_target_price:,.0f})",
            "청산 목표": f"{t['ext']} ({sell_target_price:,.0f})",
            "판단": action
        })

    # --- B. 파킹 시스템 (2단계) ---
    # 1단계: 메인 파킹 (빅테크)
    park_series = get_data(MAIN_PARKING['tk'])
    park_price = park_series.iloc[-1]
    park_ma120 = park_series.rolling(window=MA_FILTER).mean().iloc[-1]
    
    today_month = datetime.now().month
    
    # 2단계: 계절성 파킹 (빅테크 탈락 시)
    if today_month in [11, 12, 1, 2, 3, 4]:
        season_name = "❄️ 겨울 (Winter)"
        season_asset = SEASONAL_WINTER
    else:
        season_name = "☀️ 여름 (Summer)"
        season_asset = SEASONAL_SUMMER
        
    # 파킹 로직 판단
    if park_price >= park_ma120:
        # 빅테크가 상승세면 무조건 빅테크
        final_park_name = MAIN_PARKING['name']
        final_park_status = "🟢 빅테크 보유 (Risk On)"
        final_park_action = f"**{MAIN_PARKING['name']}** 매수/보유"
    else:
        # 빅테크 하락세면 -> 계절성 자산으로 피신
        final_park_name = f"{season_asset['name']} ({season_name})"
        final_park_status = "🛡️ 계절성 파킹 (Risk Off)"
        final_park_action = f"빅테크 전량 매도 후 **{season_asset['name']}** 매수/보유"

# ==========================================
# 📊 3. 웹 UI 출력
# ==========================================
st.subheader("📊 5대 야수 시그널")
df_results = pd.DataFrame(results)

def highlight_action(val):
    if '매수' in val: return 'background-color: #d4edda; color: #155724; font-weight: bold;'
    elif '손절' in val or '익절' in val: return 'background-color: #f8d7da; color: #721c24; font-weight: bold;'
    return ''

st.dataframe(df_results.style.applymap(highlight_action, subset=['판단']), use_container_width=True, hide_index=True)

st.markdown("---")
col1, col2 = st.columns(2)

with col1:
    st.subheader("🏎️ 메인 엔진 (Big Tech)")
    st.metric(label=MAIN_PARKING['name'], value=f"{park_price:,.0f} 원", delta=f"120일선 대비 {park_price-park_ma120:,.0f}")
    st.caption(f"120일선: {park_ma120:,.0f} | 상태: {'상승장' if park_price >= park_ma120 else '하락장'}")

with col2:
    st.subheader("🛡️ 비상 대피소 (Season)")
    st.info(f"현재 계절: **{season_name}**")
    st.write(f"대피 자산: **{season_asset['name']}** ({season_asset['tk']})")

st.markdown("---")
st.subheader("📝 내일 아침 행동 강령")

if buy_list or sell_list:
    if sell_list:
        st.error(f"1️⃣ 보유 중인 **{', '.join(sell_list)}** 종목을 전량 매도(청산/손절) 하세요.")
    if buy_list:
        st.success(f"2️⃣ 확보된 현금(매도금+파킹금)을 모아 **{', '.join(buy_list)}** 종목을 1/N로 나누어 매수하세요.")
    
    st.warning(f"3️⃣ 매수 후 남는 현금이 있다면, {final_park_action} 하세요.")
else:
    st.success(f"▶️ 포트폴리오 변경 없음. 남는 현금은 {final_park_action} 상태를 유지하세요.")

st.markdown("---")
st.caption("All-Weather Beast V5.0 | Created by Mr. Joo & The Quant Master")
