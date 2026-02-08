import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import datetime

# --- [미스터 주's 트레이딩 시스템 설정] ---
st.set_page_config(page_title="미스터 주 트레이딩 시스템", layout="wide")

# 종목 코드 설정
TICKER_KOSPI = '122630'  # KODEX 레버리지
TICKER_KOSDAQ = '233740' # KODEX 코스닥150레버리지

# 데이터 조회 기간 (1년치)
today = datetime.date.today()
start_date = today - datetime.timedelta(days=365)

# [함수] 데이터 수집 및 지표 계산
def get_market_status(ticker):
    try:
        # 데이터 가져오기
        df = fdr.DataReader(ticker, start_date)
        
        # 60일 이동평균선 계산
        df['MA60'] = df['Close'].rolling(window=60).mean()
        
        # 60일 이격도 계산 ((종가 / 60이평) * 100)
        df['Disparity'] = (df['Close'] / df['MA60']) * 100
        
        # 상승 추세 여부 (어제 60이평 < 오늘 60이평)
        df['Trend_Up'] = df['MA60'] > df['MA60'].shift(1)
        
        return df.iloc[-1] # 오늘자 데이터 반환
    except Exception as e:
        return None

# --- [앱 화면 구성] ---
st.title(f"📊 미스터 주: 트레이딩 시그널 ({today.strftime('%Y-%m-%d')})")
st.markdown("---")

# 사이드바: 보유 상태 체크
st.sidebar.header("내 계좌 보유 현황")
has_kospi = st.sidebar.checkbox('KODEX 레버리지 보유 중', value=False)
has_kosdaq = st.sidebar.checkbox('코스닥150 레버리지 보유 중', value=False)

# 버튼 클릭 시 분석 시작
if st.button('🚀 오늘의 매매 신호 분석 (Click)'):

    # =========================================================
    # 1. KODEX 레버리지 (상승장 & 하락장 혼합 전략)
    # =========================================================
    k_data = get_market_status(TICKER_KOSPI)
    
    if k_data is not None:
        k_disp = round(k_data['Disparity'], 2) # 이격도
        k_trend = k_data['Trend_Up']           # 추세(True/False)
        k_close = format(int(k_data['Close']), ",")
        
        st.subheader(f"1. KODEX 레버리지 (현재가: {k_close}원)")
        
        # 지표 표시
        col1, col2 = st.columns(2)
        col1.metric("현재 이격도(60일)", f"{k_disp}%", delta="진입기준: 104↑ / 95↓")
        col2.metric("60일선 추세", "상승중 📈" if k_trend else "하락/횡보 📉")

        # [논리 판별]
        if has_kospi:
            # === 보유 중일 때 (매도 조건 체크) ===
            st.markdown("#### 🛑 매도(청산) 신호 점검")
            
            # 1. 상승장 전략 청산 (이격도 100 미만)
            if k_disp < 100:
                st.error(f"🚨 [상승장 전략 매도] 이격도가 100 미만({k_disp})입니다. 추세가 끝났습니다.")
            
            # 2. 하락장 전략 청산 (익절 98 이상 OR 손절 85 미만)
            elif k_disp >= 98:
                st.warning(f"💰 [하락장 전략 익절] 이격도 98 이상({k_disp}) 도달! 수익 실현하세요.")
            elif k_disp < 85:
                st.error(f"🩸 [하락장 전략 손절] 이격도 85 미만({k_disp}) 붕괴! 즉시 손절하세요.")
            
            # 홀딩 메시지
            else:
                st.success("✅ [보유 지속] 매도 신호가 없습니다. 계속 보유하세요.")
                st.caption("💡 본인이 진입한 전략(상승/하락)에 맞는 신호를 따르세요.")

        else:
            # === 미보유 중일 때 (매수 조건 체크) ===
            st.markdown("#### ⚡ 매수(진입) 신호 점검")
            
            # 조건 1: 상승장 진입 (이격도 104 이상 AND 추세 상승)
            buy_bull = (k_disp >= 104) and k_trend
            # 조건 2: 하락장 진입 (이격도 95 미만)
            buy_bear = k_disp < 95
            
            if buy_bull:
                st.success("🔥 [강력 매수] 상승장 진입 조건 만족! (이격도 104↑ & 60일선 상승)")
            elif buy
