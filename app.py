import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import datetime

# --- [미스터 주's 듀얼 모멘텀 시스템] ---

st.set_page_config(page_title="미스터 주 트레이딩 시스템", layout="wide")

# 종목 코드
ticker_kospi = '122630'  # KODEX 레버리지
ticker_kosdaq = '233740' # KODEX 코스닥150레버리지

# 날짜 설정 (데이터 확보)
today = datetime.date.today()
start_date = today - datetime.timedelta(days=365)

# [함수] 데이터 계산 로직
def get_market_data(ticker):
    try:
        df = fdr.DataReader(ticker, start_date)
        # 60일 이동평균선
        df['MA60'] = df['Close'].rolling(window=60).mean()
        # 60일 이격도
        df['Disparity'] = (df['Close'] / df['MA60']) * 100
        # 상승추세 여부 (어제 MA60 < 오늘 MA60)
        df['Trend_Up'] = df['MA60'] > df['MA60'].shift(1)
        return df.iloc[-1]
    except Exception as e:
        return None

# --- [앱 화면 시작] ---
st.title(f"📊 미스터 주: 듀얼 전략 시스템 ({today})")
st.info("상승장(추세)과 하락장(역추세)을 분리하여 대응합니다.")

# 사이드바 입력
st.sidebar.header("내 포트폴리오 상태")
has_kospi = st.sidebar.checkbox('KODEX 레버리지 보유 중', value=False)
has_kosdaq = st.sidebar.checkbox('코스닥150 레버리지 보유 중', value=False)

if st.button('🚀 전략 분석 실행'):
    
    # ---------------------------------------------------------
    # 1. KODEX 레버리지 (상승장 & 하락장 겸용)
    # ---------------------------------------------------------
    k_data = get_market_data(ticker_kospi)
    
    if k_data is not None:
        k_disp = round(k_data['Disparity'], 2)
        k_trend = k_data['Trend_Up']
        k_close = format(int(k_data['Close']), ",")
        
        st.markdown("---")
        st.subheader(f"1. KODEX 레버리지 (현재가: {k_close}원)")
        
        col1, col2 = st.columns(2)
        col1.metric("현재 이격도(60일)", f"{k_disp}%", delta="기준: 104↑(추세) / 95↓(역추세)")
        col2.metric("60일선 추세", "상승중 🔼" if k_trend else "하락/횡보 🔽")
        
        # [KOSPI 매매 로직]
        if has_kospi:
            st.markdown("##### 🛑 보유 중 대응 (매도 체크)")
            # 1. 상승장 전략으로 진입했던 경우 (청산: 100 미만)
            if k_disp < 100:
                st.error(f"🚨 [상승장 전략 매도] 이격도가 100 미만({k_disp})입니다. 추세가 끝났습니다.")
            else:
                st.success(f"✅ [상승장 전략 홀딩] 이격도 100 이상 유지 중. 수익을 즐기세요.")
            
            # 2. 하락장 전략으로 진입했던 경우 (익절: 98 이상 / 손절: 85 미만)
            if k_disp >= 98:
                st.warning(f"💰 [하락장 전략 익절] 이격도 98 도달! 반등 수익 실현하세요.")
            elif k_disp < 85:
                st.error(f"🩸 [하락장 전략 손절] 이격도 85 붕괴. 즉시 손절하여 방어하세요.")
            else:
                st.info(f"⏳ [하락장 전략 홀딩] 반등(98) 대기 중. (손절라인 85)")
                
        else:
            st.markdown("##### ⚡ 미보유 중 대응 (진입 체크)")
            # 매수 조건 1: 상승장 (이격도 104 이상 & 추세 상승)
            buy_signal_bull = k_disp >= 104 and k_trend
            # 매수 조건 2: 하락장 (이격도 95 미만)
            buy_signal_bear = k_disp < 95
            
            if buy_signal_bull:
                st.primary_button("🔥 [강력 매수] 상승장 진입 조건 만족! (이격도 104↑ & 추세상승)")
            elif buy_signal_bear:
                st.primary_button("✨ [저점 매수] 하락장 과매도 진입! (이격도 95↓)")
            else:
                st.markdown("💤 **[관망]** 진입 조건에 맞지 않습니다.")
                st.caption("- 상승장 진입: 이격도 104 이상 & 60일선 상승")
                st.caption("- 하락장 진입: 이격도 95 미만")

    # ---------------------------------------------------------
    # 2. 코스닥150 레버리지 (하락장 전용)
    # ---------------------------------------------------------
    q_data = get_market_data(ticker_kosdaq)
    
    if q_data is not None:
        q_disp = round(q_data['Disparity'], 2)
        q_close = format(int(q_data['Close']), ",")
        
        st.markdown("---")
        st.subheader(f"2. 코스닥150 레버리지 (현재가: {q_close}원)")
        
        col3, col4 = st.columns(2)
        col3.metric("현재 이격도(60일)", f"{q_disp}%", delta="기준: 90 미만 진입")
        
        # [KOSDAQ 매매 로직]
        if has_kosdaq:
            st.markdown("##### 🛑 보유 중 대응 (매도 체크)")
            # 익절: 97 이상
            if q_disp >= 97:
                st.warning(f"💰 [익절 신호] 이격도 97 도달! 욕심 버리고 수익 실현하세요.")
            # 손절: 80 미만
            elif q_disp < 80:
                st.error(f"🩸 [손절 신호] 이격도 80 붕괴. 더 큰 하락을 피해야 합니다.")
            else:
                st.success(f"✅ [홀딩] 목표가(97) 대기 중. (손절라인 80)")
                
        else:
            st.markdown("##### ⚡ 미보유 중 대응 (진입 체크)")
            # 매수 조건: 이격도 90 미만
            if q_disp < 90:
                st.primary_button("✨ [저점 매수] 코스닥 과매도 구간! (이격도 90↓)")
            else:
                st.markdown("💤 **[관망]** 아직 충분히 싸지 않습니다.")
                st.caption("- 진입 기준: 이격도 90 미만")