import streamlit as st
import numpy as np
import pandas as pd
import yfinance as yf
from scipy.stats import linregress
from datetime import datetime
import time

# ---------------------------------------------------------
# ⚙️ 페이지 설정
# ---------------------------------------------------------
st.set_page_config(
    page_title="Korean Beast V6.0 (3-Var)",
    page_icon="🐅",
    layout="wide"
)

# ---------------------------------------------------------
# ⚙️ 1. 전략 파라미터 (신형 3변수 엔진)
# ---------------------------------------------------------
BEASTS = {
    '144600.KS': {'name': 'KODEX 은선물(H)',   'drop': 4.9, 'ent': 2.2, 'ext': 3.8},
    '139230.KS': {'name': 'TIGER 200 중공업',  'drop': 0.8, 'ent': 3.1, 'ext': -0.2},
    '140700.KS': {'name': 'KODEX 보험',        'drop': 0.9, 'ent': 3.6, 'ext': 1.8},
    '143860.KS': {'name': 'TIGER 헬스케어',    'drop': 0.7, 'ent': 3.8, 'ext': 0.6},
    '395290.KS': {'name': 'HANARO Fn K-POP',   'drop': 0.8, 'ent': 3.5, 'ext': 0.0}
}

PARKING = {
    'MAIN':   {'tk': '314250.KS', 'name': 'KODEX 미국빅테크10(H)'},
    'WINTER': {'tk': '229200.KS', 'name': 'KODEX 코스닥150'},
    'SUMMER': {'tk': '138230.KS', 'name': 'KOSEF 미국달러선물'}
}

# ---------------------------------------------------------
# ⚙️ 2. 데이터 분석 및 시뮬레이션 엔진
# ---------------------------------------------------------
@st.cache_data(ttl=900) # 15분 캐시
def analyze_korean_beasts():
    beast_tks = list(BEASTS.keys())
    parking_tks = [v['tk'] for v in PARKING.values()]
    all_tks = list(set(beast_tks + parking_tks))
    
    # 120일 이평선 계산을 위해 넉넉히 1년치 다운로드
    try:
        data = yf.download(all_tks, period="1y", progress=False)
        if isinstance(data.columns, pd.MultiIndex):
            if 'Close' in data.columns.get_level_values(0): data = data['Close']
            else: data.columns = data.columns.get_level_values(0)
    except Exception as e:
        st.error(f"데이터 다운로드 에러: {e}")
        return pd.DataFrame(), None
        
    if data.empty: return pd.DataFrame(), None

    report = []
    
    # --- [A] 5대 야수 분석 (3변수 로직) ---
    for tk in beast_tks:
        if tk not in data.columns: continue
        series = data[tk].dropna()
        closes = series.values
        if len(closes) < 30: continue
        
        p = BEASTS[tk]
        win = 20
        x = np.arange(win)
        
        hold = False
        ent_slope = 0.0
        
        # 현재 보유 상태 및 진입 슬로프 추적을 위한 히스토리 시뮬레이션
        for i in range(win, len(closes)-1):
            y = closes[i-win:i]
            s, inter, _, _, _ = linregress(x, y)
            std = np.std(y - (s*x + inter))
            
            c_sig = 999.0
            c_slp = -999.0
            if std > 0: c_sig = (closes[i] - (s*(win-1)+inter)) / std
            if closes[i] > 0: c_slp = (s / closes[i]) * 100
            
            if not hold:
                if c_sig <= -p['ent']:
                    hold = True; ent_slope = c_slp
            else:
                if c_sig >= p['ext'] or c_slp < (ent_slope - p['drop']):
                    hold = False

        # 오늘자 지표 계산
        y_last = closes[-win:]
        s, inter, _, _, _ = linregress(x, y_last)
        L = s*(win-1) + inter 
        std = np.std(y_last - (s*x + inter))
        
        today_price = closes[-1]
        today_slope = (s / today_price) * 100 if today_price > 0 else 0
        today_sigma = (today_price - L) / std if std > 0 else 0
        
        # 목표가 역산
        target_buy_price = L + (-p['ent'] * std)
        target_sell_price = L + (p['ext'] * std)
        
        action = "HOLD"
        status = "HOLDING" if hold else "WAITING"
        
        display_ent_slope = "-"
        display_stop_slope = "-"
        
        if hold:
            cut_slope = ent_slope - p['drop']
            display_ent_slope = f"{ent_slope:.2f}%"
            display_stop_slope = f"{cut_slope:.2f}%"
            
            if today_sigma >= p['ext']: action = "SELL (익절)"
            elif today_slope < cut_slope: action = "SELL (손절)"
            else: action = "HOLD (보유)"
        else:
            if today_sigma <= -p['ent']:
                action = "BUY (진입)"
                display_ent_slope = f"{today_slope:.2f}% (New)"
                display_stop_slope = f"{today_slope - p['drop']:.2f}% (Est)"
            else:
                action = "WAIT (대기)"
                
        report.append({
            'Asset': BEASTS[tk]['name'],
            'Ticker': tk,
            'Action': action,
            'Price': today_price,
            'Cur Sigma': today_sigma,
            'Cur Slope': today_slope,
            'Buy Target': f"-{p['ent']} (₩{target_buy_price:,.0f})",
            'Sell Target': f"{p['ext']} (₩{target_sell_price:,.0f})",
            'Entry Slope': display_ent_slope,
            'Stop Slope': display_stop_slope
        })

    # --- [B] 파킹 자산 분석 (기존 로직 유지) ---
    park_info = {}
    main_tk = PARKING['MAIN']['tk']
    
    if main_tk in data.columns:
        park_series = data[main_tk].dropna()
        if len(park_series) >= 120:
            p_price = park_series.iloc[-1]
            p_ma120 = park_series.rolling(window=120).mean().iloc[-1]
            
            is_bull = p_price >= p_ma120
            month = datetime.now().month
            
            if is_bull:
                park_info['Target'] = PARKING['MAIN']['name']
                park_info['Status'] = f"🟢 Risk On (BigTech >= MA120)"
            else:
                if month in [11, 12, 1, 2, 3, 4]:
                    park_info['Target'] = f"{PARKING['WINTER']['name']} (❄️ 겨울)"
                    park_info['Status'] = f"🛡️ Risk Off (BigTech < MA120)"
                else:
                    park_info['Target'] = f"{PARKING['SUMMER']['name']} (☀️ 여름)"
                    park_info['Status'] = f"🛡️ Risk Off (BigTech < MA120)"
                    
            park_info['BigTech Price'] = p_price
            park_info['BigTech MA120'] = p_ma120

    return pd.DataFrame(report), park_info

# ---------------------------------------------------------
# ⚙️ 3. 웹 UI 출력
# ---------------------------------------------------------
st.title("🐅 Korean Beast V6.0 (3-Var Edition)")
st.caption(f"Last Update: {time.strftime('%Y-%m-%d %H:%M:%S')} | Logic: 20d Sigma & Slope Stop + Method A")
st.markdown("---")

with st.spinner("야수들의 기울기와 파킹 구역을 스캔 중입니다..."):
    df_res, park_info = analyze_korean_beasts()

if not df_res.empty:
    # --- 상단: 야수 신호 ---
    st.subheader("📊 5대 야수 시그널 (Action Board)")
    
    def text_color_action(val):
        if 'BUY' in val: return 'color: #155724; background-color: #d4edda; font-weight: bold;'
        if 'SELL' in val: return 'color: #721c24; background-color: #f8d7da; font-weight: bold;'
        if 'HOLD' in val: return 'color: #004085; background-color: #cce5ff; font-weight: bold;'
        return 'color: #383d41; background-color: #e2e3e5;'

    # 데이터프레임 렌더링
    st.dataframe(
        df_res.style
        .map(text_color_action, subset=['Action'])
        .format({
            'Price': '₩{:,.0f}',
            'Cur Sigma': '{:.2f}',
            'Cur Slope': '{:.2f}%'
        })
        .set_properties(**{'text-align': 'center'})
        .set_table_styles([{'selector': 'th', 'props': [('text-align', 'center')]}])
        , 
        use_container_width=True,
        hide_index=True,
        column_order=['Asset', 'Action', 'Price', 'Cur Sigma', 'Cur Slope', 'Buy Target', 'Sell Target', 'Entry Slope', 'Stop Slope']
    )
    
    # --- 중단: 파킹 상태 ---
    st.markdown("---")
    st.subheader("🏎️ 파킹 구역 (Parking Zone)")
    if park_info:
        c1, c2 = st.columns(2)
        delta = park_info['BigTech Price'] - park_info['BigTech MA120']
        with c1:
            st.metric(
                label="미국빅테크10 (현재가 vs 120일선)", 
                value=f"₩{park_info['BigTech Price']:,.0f}", 
                delta=f"{delta:,.0f}"
            )
        with c2:
            st.info(f"**현재 시장 상태:** {park_info['Status']}\n\n**대피 자산:** {park_info['Target']}")
    else:
        st.warning("파킹 자산 데이터를 불러오는 데 실패했습니다.")

    # --- 하단: 내일 아침 행동 강령 (Method A) ---
    st.markdown("---")
    st.subheader("📝 내일 시가 행동 강령 (Method A)")
    
    buy_list = df_res[df_res['Action'].str.contains('BUY')]['Asset'].tolist()
    sell_list = df_res[df_res['Action'].str.contains('SELL')]['Asset'].tolist()
    
    if buy_list or sell_list:
        if sell_list:
            st.error(f"🚨 **[SELL]** 보유 중인 **{', '.join(sell_list)}** 종목을 전량 매도(청산/손절) 하세요.")
        if buy_list:
            st.success(f"🔥 **[BUY & REBALANCE]** 확보된 현금(기존 매도금+파킹금 전량)을 모아 **{', '.join(buy_list)}** 포함 보유할 야수들을 1/N로 리밸런싱 하세요.")
            
        target_park = park_info['Target'] if park_info else "파킹 자산"
        st.warning(f"🏦 **[PARKING]** 야수 매수 후 남는 자투리 현금, 또는 매수 신호가 없을 시 매도 대금은 **{target_park}** 에 파킹하세요.")
    else:
        st.success("▶️ **포트폴리오 변경 없음.** 현재 보유 종목(야수 및 파킹)을 그대로 홀딩하십시오.")

    with st.expander("📖 **전략 가이드 (Click)**"):
        st.markdown("""
        * **Cur Sigma:** 현재 가격의 과열/침체 정도입니다. ((-)면 저평가)
        * **Cur Slope:** 최근 20일간의 상승 각도입니다.
        * **Stop Slope (손절선):** 야수 진입 당시의 기울기보다 이 수치 미만으로 각도가 꺾이면 **손절(SELL)** 처리됩니다.
        * **Method A 룰:** 신규 진입(BUY)이 뜰 때만 파킹금을 빼서 리밸런싱합니다. 매도(SELL)만 뜬 날은 판 돈을 모두 **안전 구역(파킹)**으로 옮깁니다.
        """)
else:
    st.error("데이터 로드 실패. 잠시 후 다시 시도해주세요.")
