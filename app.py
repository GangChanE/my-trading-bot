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
    page_title="6 Beasts V7.1 (Method A)",
    page_icon="🐅",
    layout="wide"
)

# ---------------------------------------------------------
# ⚙️ 1. 전략 파라미터 (6대 정규 야수)
# ---------------------------------------------------------
BEASTS = {
    '144600.KS': {'name': 'KODEX 은선물(H)',         'drop': 4.9, 'ent': 2.2, 'ext': 3.8, 'theme': '원자재'},
    '139230.KS': {'name': 'TIGER 200 중공업',        'drop': 0.8, 'ent': 3.1, 'ext': -0.2,'theme': '경기민감'},
    '140700.KS': {'name': 'KODEX 보험',              'drop': 0.9, 'ent': 3.6, 'ext': 1.8, 'theme': '가치/금리'},
    '143860.KS': {'name': 'TIGER 헬스케어',          'drop': 0.7, 'ent': 3.8, 'ext': 0.6, 'theme': '바이오'},
    '395290.KS': {'name': 'HANARO Fn K-POP',         'drop': 0.8, 'ent': 3.5, 'ext': 0.0, 'theme': '엔터'},
    '314250.KS': {'name': 'KODEX 미국빅테크10(H)',   'drop': 1.7, 'ent': 2.2, 'ext': 3.5, 'theme': '글로벌성장'}
}

# ---------------------------------------------------------
# ⚙️ 사이드바 (사용자 보유 종목 강제 설정)
# ---------------------------------------------------------
with st.sidebar:
    st.header("💼 내 포트폴리오 (선진입 설정)")
    st.markdown("장중에 선진입했거나 이미 보유 중인 종목을 선택하세요. 시스템이 알아서 **[BUY/WAIT]** 시그널을 지우고 **[HOLD/SELL]** 모드로 강제 전환합니다.")
    
    owned_beasts = st.multiselect(
        "현재 보유 중인 야수 선택:",
        options=[b['name'] for b in BEASTS.values()],
        default=[]
    )

# ---------------------------------------------------------
# ⚙️ 2. 데이터 분석 및 시뮬레이션 엔진
# ---------------------------------------------------------
@st.cache_data(ttl=900) # 15분 캐시
def analyze_6_beasts(owned_list):
    tickers = list(BEASTS.keys())
    
    try:
        data = yf.download(tickers, period="1y", progress=False)
        if isinstance(data.columns, pd.MultiIndex):
            if 'Close' in data.columns.get_level_values(0): 
                data = data['Close']
            else: 
                data.columns = data.columns.get_level_values(0)
                
        data = data.ffill().bfill()
        
    except Exception as e:
        st.error(f"데이터 다운로드 에러: {e}")
        return pd.DataFrame(), []
        
    if data.empty: 
        return pd.DataFrame(), []

    report = []
    missing_beasts = [] 
    
    for tk in tickers:
        if tk not in data.columns: 
            missing_beasts.append(BEASTS[tk]['name'])
            continue
            
        series = data[tk].dropna()
        closes = series.values
        
        if len(closes) < 30: 
            missing_beasts.append(BEASTS[tk]['name'])
            continue
        
        p = BEASTS[tk]
        win = 20
        x = np.arange(win)
        
        hold = False
        ent_slope = 0.0
        
        # 1) 시스템상 과거 히스토리 추적
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

        # 2) 오늘자 지표 계산
        y_last = closes[-win:]
        s, inter, _, _, _ = linregress(x, y_last)
        L = s*(win-1) + inter 
        std = np.std(y_last - (s*x + inter))
        
        today_price = closes[-1]
        today_slope = (s / today_price) * 100 if today_price > 0 else 0
        today_sigma = (today_price - L) / std if std > 0 else 0
        
        target_buy_price = L + (-p['ent'] * std)
        target_sell_price = L + (p['ext'] * std)
        
        # 🌟 핵심 로직: 사용자가 '보유중'이라고 체크한 경우 강제 덮어쓰기
        is_user_owned = p['name'] in owned_list
        
        if is_user_owned and not hold:
            hold = True
            # 시스템은 미보유인데 사용자가 샀으므로, '오늘' 진입한 것으로 간주하여 기준 슬로프 셋팅
            ent_slope = today_slope 

        # 4) 액션 판별
        action = "HOLD"
        display_ent_slope = "-"
        display_stop_slope = "-"
        
        if hold:
            cut_slope = ent_slope - p['drop']
            display_ent_slope = f"{ent_slope:.2f}%"
            display_stop_slope = f"{cut_slope:.2f}%"
            
            if today_sigma >= p['ext']: action = "SELL (익절)"
            elif today_slope < cut_slope: action = "SELL (손절)"
            else: 
                action = "HOLD (보유)"
                if is_user_owned: action = "HOLD (보유중)" # 사용자가 체크한 종목임을 명시
        else:
            if today_sigma <= -p['ent']:
                action = "BUY (진입)"
                display_ent_slope = f"{today_slope:.2f}% (New)"
                display_stop_slope = f"{today_slope - p['drop']:.2f}% (Est)"
            else:
                action = "WAIT (대기)"
                
        report.append({
            'Theme': p['theme'],
            'Asset': p['name'],
            'Ticker': tk,
            'Action': action,
            'Price': float(today_price),
            'Cur Sigma': float(today_sigma),
            'Cur Slope': float(today_slope),
            'Buy Target': f"-{p['ent']} (₩{target_buy_price:,.0f})",
            'Sell Target': f"{p['ext']} (₩{target_sell_price:,.0f})",
            'Entry Slope': display_ent_slope,
            'Stop Slope': display_stop_slope
        })

    return pd.DataFrame(report), missing_beasts

# ---------------------------------------------------------
# ⚙️ 3. 웹 UI 렌더링
# ---------------------------------------------------------
st.title("🐅 6 Beasts V7.1 (선진입 대응 패치)")
st.caption(f"Last Update: {time.strftime('%Y-%m-%d %H:%M:%S')} | Logic: 20d 3-Var (User Override)")
st.markdown("---")

with st.spinner("6대 야수들의 궤적을 분석 중입니다..."):
    df_res, missing_beasts = analyze_6_beasts(owned_beasts) # 사용자가 체크한 리스트 전달

if missing_beasts:
    st.warning(f"⚠️ 야후 파이낸스 일시적 서버 오류로 다음 종목의 데이터가 누락되었습니다: **{', '.join(missing_beasts)}**")

if not df_res.empty:
    st.subheader("📊 6대 야수 시그널 대시보드")
    
    def text_color_action(val):
        if 'BUY' in val: return 'color: #155724; background-color: #d4edda; font-weight: bold;'
        if 'SELL' in val: return 'color: #721c24; background-color: #f8d7da; font-weight: bold;'
        if 'HOLD' in val: return 'color: #004085; background-color: #cce5ff; font-weight: bold;'
        return 'color: #383d41; background-color: #e2e3e5;'

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
        column_order=['Theme', 'Asset', 'Action', 'Price', 'Cur Sigma', 'Cur Slope', 'Buy Target', 'Sell Target', 'Entry Slope', 'Stop Slope']
    )
    
    st.markdown("---")
    st.subheader("📝 내일 시가 행동 강령")
    
    buy_list = df_res[df_res['Action'].str.contains('BUY')]['Asset'].tolist()
    sell_list = df_res[df_res['Action'].str.contains('SELL')]['Asset'].tolist()
    
    if buy_list or sell_list:
        if sell_list:
            st.error(f"🚨 **[SELL]** 보유 중인 **{', '.join(sell_list)}** 종목을 내일 시가에 전량 매도하세요.")
        
        if buy_list:
            st.success(f"🔥 **[BUY & REBALANCE]** 내일 시가에 **{', '.join(buy_list)}** 종목을 매수합니다.")
        elif sell_list and not buy_list:
            st.warning(f"🏦 **[CASH PARKING]** 매도 후 신규 매수 신호가 없습니다. **'100% 현금'** 상태로 파킹하십시오.")
    else:
        st.success("▶️ **[HOLD]** 포트폴리오 변경 사항 없음. 현재 상태를 그대로 홀딩하십시오.")
