import streamlit as st
import requests
import pandas as pd
import numpy as np
from scipy.stats import linregress
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# ==========================================
# ⚙️ 1. [Final] 5대 야수 & 미국빅테크10 설정
# ==========================================
st.set_page_config(page_title="All-Weather Beast", page_icon="🦁", layout="wide")

WINDOW = 60
MA_FILTER = 120

# 🦁 5대 야수 (K-POP 포함 확정)
TARGETS = [
    {'name': 'KODEX 은선물(H)',   'tk': '144600.KS', 'ent': 1.7, 'ext': 0.3},
    {'name': 'TIGER 200 중공업',  'tk': '139230.KS', 'ent': 2.7, 'ext': -0.5},
    {'name': 'KODEX 보험',        'tk': '140700.KS', 'ent': 2.3, 'ext': 1.5},
    {'name': 'TIGER 헬스케어',    'tk': '143860.KS', 'ent': 2.1, 'ext': 0.7},
    {'name': 'HANARO Fn K-POP',   'tk': '395290.KS', 'ent': 1.6, 'ext': 1.3}
]

PARKING_ASSET = {'name': 'KODEX 미국빅테크10(H)', 'tk': '314250.KS'}

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
# 🚀 2. 데이터 분석 및 목표가 계산
# ==========================================
st.title("🦁 All-Weather Beast V4.0")
st.caption("Strategy: 5 Beasts + BigTech10 Parking | Market Open Exit")
st.write(f"**기준일:** {datetime.now().strftime('%Y-%m-%d')} | **실행:** 매일 장 마감 후 확인 -> 다음날 아침 09:00 매매")
st.markdown("---")

with st.spinner("야수들의 목표가를 정밀 계산 중입니다..."):
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
        
        # 추세선(L)과 표준편차(D)
        L = res.slope * (WINDOW-1) + res.intercept
        D = np.std(y - (res.slope*x + res.intercept))
        
        current_sigma = 0 if D == 0 else (curr_price - L) / D

        # 🎯 목표가 계산 (Price = L + Sigma * D)
        # 1. 진입 목표가 (Buy Target)
        buy_target_price = L + (-t['ent'] * D)
        # 2. 청산 목표가 (Sell Target)
        sell_target_price = L + (t['ext'] * D)

        action = ""
        # [매수] 120일선 위 & 기울기 양수 & 과매도 진입
        if is_trend_up and res.slope > 0 and current_sigma <= -t['ent']:
            action = "🔥 신규 매수"
            buy_list.append(t['name'])
        # [손절] 120일선 이탈 시 즉시 손절
        elif not is_trend_up:
            action = "🚨 손절 (120일선 이탈)"
            sell_list.append(t['name'])
        # [익절] 목표 시그마 도달
        elif current_sigma >= t['ext']:
            action = "💰 익절 (목표가 도달)"
            sell_list.append(t['name'])
        else:
            action = "👌 보유/대기"

        results.append({
            "종목명": t['name'],
            "현재가": f"{curr_price:,.0f}",
            "추세(120일)": trend_icon,
            "현재 Sigma": f"{current_sigma:.2f}",
            "진입 목표 (Sigma)": f"-{t['ent']} ({buy_target_price:,.0f})",
            "청산 목표 (Sigma)": f"{t['ext']} ({sell_target_price:,.0f})",
            "판단": action
        })

    # --- 2. 슈퍼 파킹 자산 (미국빅테크10) 분석 ---
    park_series = get_data(PARKING_ASSET['tk'])
    if not park_series.empty:
        park_price = park_series.iloc[-1]
        park_ma120 = park_series.rolling(window=MA_FILTER).mean().iloc[-1]
        
        if park_price >= park_ma120:
            park_status = "🟢 상승 (빅테크 매수/보유)"
            park_action = "미국빅테크10 전량 매수/보유"
        else:
            park_status = "🔴 하락 (전량 현금 보유)"
            park_action = "전량 현금 보유 (Risk Off)"
    else:
        park_price = 0; park_ma120 = 0
        park_status = "데이터 오류"; park_action = "확인 필요"

# ==========================================
# 📊 3. 웹 UI 출력
# ==========================================
st.subheader("📊 5대 야수 시그널 & 목표가")
df_results = pd.DataFrame(results)

# 스타일링 함수
def color_trend(val):
    color = 'red' if '하락' in val else 'green'
    return f'color: {color}'

def highlight_action(val):
    if '매수' in val: return 'background-color: #d4edda; color: #155724; font-weight: bold;'
    elif '손절' in val or '익절' in val: return 'background-color: #f8d7da; color: #721c24; font-weight: bold;'
    return ''

st.dataframe(
    df_results.style
    .applymap(color_trend, subset=['추세(120일)'])
    .applymap(highlight_action, subset=['판단']),
    use_container_width=True, hide_index=True
)

st.subheader(f"🏎️ 슈퍼 파킹 자산 ({PARKING_ASSET['name']})")
col1, col2, col3 = st.columns(3)
col1.metric("현재가", f"{park_price:,.0f} 원")
col2.metric("120일 이동평균", f"{park_ma120:,.0f} 원")
col3.metric("상태", park_status.split(' ')[0], park_status.split(' ')[1])

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
st.caption("All-Weather Beast V4.0 | Created by Mr. Joo & The Quant Master")
