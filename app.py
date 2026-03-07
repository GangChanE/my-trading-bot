import streamlit as st
import numpy as np
import pandas as pd
import yfinance as yf
from scipy.stats import linregress
import time

# ---------------------------------------------------------
# ⚙️ 페이지 설정
# ---------------------------------------------------------
st.set_page_config(
    page_title="5 Beasts V17.0 (Dynamic Scaling)",
    page_icon="🐅",
    layout="wide"
)

# ---------------------------------------------------------
# ⚙️ 1. 전략 파라미터 (V17.0 궁극의 5야수)
# ---------------------------------------------------------
BEASTS = {
    '139230.KS': {'name': 'TIGER 200 중공업',       'ent': 3.0, 'ext': -0.3, 'drop': 0.7, 'r_ent': 0.02, 'r_ext': 0.01, 'theme': '경기민감'},
    '261220.KS': {'name': 'KODEX WTI원유선물(H)',   'ent': 3.3, 'ext': 3.6,  'drop': 0.5, 'r_ent': 0.01, 'r_ext': 0.02, 'theme': '원자재'},
    '371460.KS': {'name': 'TIGER 차이나전기차',     'ent': 2.6, 'ext': -0.9, 'drop': 0.9, 'r_ent': 0.01, 'r_ext': 0.03, 'theme': '해외/섹터'},
    '305720.KS': {'name': 'KODEX 2차전지산업',      'ent': 3.5, 'ext': 2.5,  'drop': 2.2, 'r_ent': 0.01, 'r_ext': 0.02, 'theme': '국내/섹터'},
    '314250.KS': {'name': 'KODEX 미국빅테크10(H)',  'ent': 3.1, 'ext': 3.3,  'drop': 1.1, 'r_ent': 0.01, 'r_ext': 0.01, 'theme': '글로벌성장'}
}

# ---------------------------------------------------------
# ⚙️ 사이드바 (사용자 보유 종목 및 상태 설정)
# ---------------------------------------------------------
with st.sidebar:
    st.header("💼 내 포트폴리오 (상태 설정)")
    st.markdown("현재 실제 계좌에 보유 중인 야수와 그 **투입 비율(상태)**을 정확히 선택해 주세요.")
    
    user_portfolio = {}
    for tk, info in BEASTS.items():
        st.markdown(f"**{info['name']}**")
        status = st.radio(
            f"상태 선택 ({info['name']})",
            options=["미보유 (0%)", "1차 진입 완료 (50%)", "2차 추매 완료 (100%)", "1차 익절 완료 (50% 남음)"],
            key=tk,
            label_visibility="collapsed"
        )
        if status != "미보유 (0%)":
            user_portfolio[tk] = status
    
    st.markdown("---")
    st.info("💡 **V17.0 트레일링 룰**\n* **1차 진입(50%)**: 시그마 과매도 도달 시\n* **2차 추매(100%)**: 1차 후 저점 대비 반등 시\n* **1차 익절(50%)**: 시그마 과매수 도달 시\n* **2차 익절(0%)**: 1차 후 고점 대비 하락 시\n* **손절(0%)**: 기준 기울기 이탈 시")

# ---------------------------------------------------------
# ⚙️ 2. 데이터 분석 및 시뮬레이션 엔진
# ---------------------------------------------------------
@st.cache_data(ttl=900) # 15분 캐시
def analyze_5_beasts(portfolio):
    tickers = list(BEASTS.keys())
    
    try:
        # 데이터는 트레일링(고점/저점) 파악을 위해 넉넉히 1년 치를 가져옴
        data_close = yf.download(tickers, period="1y", progress=False)['Close'].ffill()
        data_high = yf.download(tickers, period="1y", progress=False)['High'].ffill()
        data_low = yf.download(tickers, period="1y", progress=False)['Low'].ffill()
        
        # Series 처리 방어 (종목이 1개일 경우)
        if isinstance(data_close, pd.Series):
            data_close = data_close.to_frame()
            data_high = data_high.to_frame()
            data_low = data_low.to_frame()
            
    except Exception as e:
        st.error(f"데이터 다운로드 에러: {e}")
        return pd.DataFrame(), []
        
    if data_close.empty: 
        return pd.DataFrame(), []

    report = []
    missing_beasts = [] 
    
    for tk in tickers:
        if tk not in data_close.columns: 
            missing_beasts.append(BEASTS[tk]['name'])
            continue
            
        closes = data_close[tk].dropna().values
        highs = data_high[tk].dropna().values
        lows = data_low[tk].dropna().values
        
        if len(closes) < 30: 
            missing_beasts.append(BEASTS[tk]['name'])
            continue
        
        p = BEASTS[tk]
        win = 20
        x = np.arange(win)
        
        # 오늘자(마지막 거래일) 지표 계산
        y_last = closes[-win:]
        s, inter, _, _, _ = linregress(x, y_last)
        L = s*(win-1) + inter 
        std = np.std(y_last - (s*x + inter))
        
        today_price = closes[-1]
        today_slope = (s / today_price) * 100 if today_price > 0 else 0
        today_sigma = (today_price - L) / std if std > 0 else 0
        
        # 🌟 V17 동적 스케일링 액션 판별 🌟
        action = "WAIT (대기)"
        target_info = f"진입대기 (Sig -{p['ent']:.1f})"
        
        if tk in portfolio:
            status = portfolio[tk]
            
            # 1. 1차 진입 완료 상태 (50% 보유) -> 2차 추매(트레일링) OR 손절 대기
            if status == "1차 진입 완료 (50%)":
                # 간이 트레일링 계산: 사용자가 샀다고 가정한 최근 10일 중 최저점 찾기
                recent_low = np.min(lows[-10:]) 
                bounce_rate = (today_price - recent_low) / recent_low
                
                # 손절은 기준 기울기(최근 10일 평균 기울기로 임시 대체) 이탈 시
                recent_slopes = []
                for i in range(len(closes)-10, len(closes)):
                    sy, _inter, _, _, _ = linregress(x, closes[i-win:i])
                    recent_slopes.append((sy/closes[i])*100)
                avg_ent_slope = np.mean(recent_slopes)
                
                if today_slope < (avg_ent_slope - p['drop']):
                    action = "🛑 SELL ALL (손절)"
                    target_info = "기울기 이탈"
                elif bounce_rate >= p['r_ent']:
                    action = "🔥 BUY 50% (2차 추매)"
                    target_info = f"저점대비 +{bounce_rate*100:.1f}% 반등 (목표 {p['r_ent']*100}%)"
                else:
                    action = "HOLD 50% (관망)"
                    target_info = f"반등 대기 (현재 +{bounce_rate*100:.1f}%)"

            # 2. 2차 진입 완료 상태 (100% 보유) -> 1차 익절 OR 손절 대기
            elif status == "2차 추매 완료 (100%)":
                # 손절 기울기 계산 (임시)
                recent_slopes = []
                for i in range(len(closes)-20, len(closes)):
                    sy, _inter, _, _, _ = linregress(x, closes[i-win:i])
                    recent_slopes.append((sy/closes[i])*100)
                avg_ent_slope = np.mean(recent_slopes)
                
                if today_slope < (avg_ent_slope - p['drop']):
                    action = "🛑 SELL ALL (손절)"
                    target_info = "기울기 이탈"
                elif today_sigma >= p['ext']:
                    action = "💰 SELL 50% (1차 익절)"
                    target_info = f"과매수 도달 (Sig {today_sigma:.2f})"
                else:
                    action = "HOLD 100% (관망)"
                    target_info = f"익절 대기 (목표 Sig {p['ext']:.1f})"

            # 3. 1차 익절 완료 상태 (50% 보유) -> 2차 익절(트레일링) OR 손절 대기
            elif status == "1차 익절 완료 (50% 남음)":
                # 최근 10일 중 최고점 찾기
                recent_high = np.max(highs[-10:])
                drop_rate = (recent_high - today_price) / recent_high
                
                if drop_rate >= p['r_ext']:
                    action = "📉 SELL ALL (트레일링 익절)"
                    target_info = f"고점대비 -{drop_rate*100:.1f}% 하락 (목표 {p['r_ext']*100}%)"
                else:
                    action = "HOLD 50% (관망)"
                    target_info = f"하락 대기 (현재 -{drop_rate*100:.1f}%)"
                    
        else:
            # 미보유 상태 -> 1차 진입 대기
            if today_sigma <= -p['ent']:
                action = "🛒 BUY 50% (1차 진입)"
                target_info = f"과매도 도달 (Sig {today_sigma:.2f})"
            else:
                action = "WAIT (대기)"
                target_info = f"진입대기 (목표 Sig -{p['ent']:.1f})"
                
        report.append({
            'Theme': p['theme'],
            'Asset': p['name'],
            'Action': action,
            'Price': float(today_price),
            'Cur Sigma': float(today_sigma),
            'Cur Slope': float(today_slope),
            'Target/Status Info': target_info
        })

    return pd.DataFrame(report), missing_beasts

# ---------------------------------------------------------
# ⚙️ 3. 웹 UI 렌더링
# ---------------------------------------------------------
st.title("🐅 The Quantum Oracle V17.0 (5 Beasts Dynamic)")
st.caption(f"Last Update: {time.strftime('%Y-%m-%d %H:%M:%S')} | Logic: Dynamic Scaling & Trailing Stop")
st.markdown("---")

with st.spinner("야수들의 현재 사냥 상태를 분석 중입니다..."):
    df_res, missing_beasts = analyze_5_beasts(user_portfolio) 

if missing_beasts:
    st.warning(f"⚠️ 야후 파이낸스 서버 오류로 데이터 누락: **{', '.join(missing_beasts)}**")

if not df_res.empty:
    st.subheader("📊 5야수 실시간 시그널 대시보드")
    
    def text_color_action(val):
        if 'BUY' in val: return 'color: #155724; background-color: #d4edda; font-weight: bold;'
        if 'SELL' in val: return 'color: #721c24; background-color: #f8d7da; font-weight: bold;'
        if 'HOLD' in val: return 'color: #004085; background-color: #cce5ff; font-weight: bold;'
        if 'WAIT' in val: return 'color: #856404; background-color: #fff3cd;'
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
        hide_index=True
    )
    
    st.markdown("---")
    st.subheader("📝 내일 아침 행동 강령 (Action Plan)")
    
    action_items = df_res[df_res['Action'].str.contains('BUY|SELL')]
    
    if not action_items.empty:
        for _, row in action_items.iterrows():
            if 'SELL ALL' in row['Action']:
                st.error(f"🚨 **[전량 매도]** {row['Asset']} : {row['Target/Status Info']} -> 내일 시가에 남은 물량 100% 매도")
            elif 'SELL 50%' in row['Action']:
                st.warning(f"💰 **[절반 익절]** {row['Asset']} : {row['Target/Status Info']} -> 내일 시가에 보유 물량의 50% 매도 (1차 익절)")
            elif 'BUY 100%' in row['Action'] or 'BUY 50% (2차' in row['Action']:
                st.success(f"🔥 **[불타기 추매]** {row['Asset']} : {row['Target/Status Info']} -> 내일 시가에 남은 현금 비중 100% 채우기")
            elif 'BUY 50%' in row['Action']:
                st.info(f"🛒 **[1차 진입]** {row['Asset']} : {row['Target/Status Info']} -> 내일 시가에 할당 비중의 50%만 매수")
    else:
        # 아무 행동도 안 할 때
        if user_portfolio:
            st.success("▶️ **[HOLD]** 현재 야수가 사냥 중입니다. 섣불리 움직이지 말고 관망하십시오.")
        else:
            st.success("🏦 **[100% CASH PARKING]** 폭락장이 올 때까지 KOFR(현금) 이자를 받으며 편안하게 관망하십시오.")

