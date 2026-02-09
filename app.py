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
    # 1. KODEX 레버리지 (상
