# server.py
from mcp.server.fastmcp import FastMCP
from pykrx import stock
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import ta
import json
import yfinance as yf
import requests
from bs4 import BeautifulSoup


mcp = FastMCP("Stock Analyzer")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 기존 도구들
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@mcp.tool()
def get_stock_analysis(ticker: str, days: int = 120) -> str:
    """종목코드를 입력하면 OHLCV + 기술적 지표를 분석합니다.

    Args:
        ticker: 종목코드 (예: '347860' for 알체라, '005930' for 삼성전자)
        days: 조회 기간 (일수, 기본 120일)
    """
    end = datetime.today().strftime("%Y%m%d")
    start = (datetime.today() - timedelta(days=days)).strftime("%Y%m%d")

    # OHLCV 데이터 수집
    df = stock.get_market_ohlcv(start, end, ticker)
    if df.empty:
        return f"종목코드 {ticker}에 대한 데이터를 찾을 수 없습니다."
    if len(df) < 2:
        return f"종목코드 {ticker}의 데이터가 부족합니다 (거래일 {len(df)}일). 분석 기간을 늘려주세요."

    # 종목명 가져오기
    name = stock.get_market_ticker_name(ticker)

    # 기술적 지표 계산
    df['SMA5'] = df['종가'].rolling(5).mean()
    df['SMA20'] = df['종가'].rolling(20).mean()
    df['SMA60'] = df['종가'].rolling(60).mean()
    df['RSI'] = ta.momentum.RSIIndicator(df['종가'], window=14).rsi()

    macd_ind = ta.trend.MACD(df['종가'])
    df['MACD'] = macd_ind.macd()
    df['MACD_signal'] = macd_ind.macd_signal()
    df['MACD_hist'] = macd_ind.macd_diff()

    bb = ta.volatility.BollingerBands(df['종가'])
    df['BB_upper'] = bb.bollinger_hband()
    df['BB_lower'] = bb.bollinger_lband()

    ichimoku = ta.trend.IchimokuIndicator(df['고가'], df['저가'], window1=9, window2=26, window3=52)
    df['Ichimoku_conversion'] = ichimoku.ichimoku_conversion_line()
    df['Ichimoku_base'] = ichimoku.ichimoku_base_line()
    df['Ichimoku_span_a'] = ichimoku.ichimoku_a()
    df['Ichimoku_span_b'] = ichimoku.ichimoku_b()
    df['Ichimoku_lagging'] = df['종가'].shift(-26)

    # 최근 데이터 요약
    latest = df.iloc[-1]
    prev = df.iloc[-2]

    result = {
        "종목명": name,
        "종목코드": ticker,
        "분석일": end,
        "현재가": int(latest['종가']),
        "전일대비": int(latest['종가'] - prev['종가']),
        "등락률": round((latest['종가'] - prev['종가']) / prev['종가'] * 100, 2),
        "거래량": int(latest['거래량']),
        "최근5일_평균거래량": int(df['거래량'].tail(5).mean()),
        "기술적지표": {
            "SMA5": round(latest['SMA5'], 0) if pd.notna(latest['SMA5']) else None,
            "SMA20": round(latest['SMA20'], 0) if pd.notna(latest['SMA20']) else None,
            "SMA60": round(latest['SMA60'], 0) if pd.notna(latest['SMA60']) else None,
            "RSI_14": round(latest['RSI'], 2) if pd.notna(latest['RSI']) else None,
            "MACD": round(latest['MACD'], 2) if pd.notna(latest['MACD']) else None,
            "MACD_signal": round(latest['MACD_signal'], 2) if pd.notna(latest['MACD_signal']) else None,
            "MACD_histogram": round(latest['MACD_hist'], 2) if pd.notna(latest['MACD_hist']) else None,
            "볼린저_상단": round(latest['BB_upper'], 0) if pd.notna(latest['BB_upper']) else None,
            "볼린저_하단": round(latest['BB_lower'], 0) if pd.notna(latest['BB_lower']) else None,
            "일목_전환선": round(latest['Ichimoku_conversion'], 0) if pd.notna(latest['Ichimoku_conversion']) else None,
            "일목_기준선": round(latest['Ichimoku_base'], 0) if pd.notna(latest['Ichimoku_base']) else None,
            "일목_선행스팬A": round(latest['Ichimoku_span_a'], 0) if pd.notna(latest['Ichimoku_span_a']) else None,
            "일목_선행스팬B": round(latest['Ichimoku_span_b'], 0) if pd.notna(latest['Ichimoku_span_b']) else None,
            "일목_후행스팬": round(latest['Ichimoku_lagging'], 0) if pd.notna(latest['Ichimoku_lagging']) else None,
        },
        "기간내_최고가": int(df['고가'].max()),
        "기간내_최저가": int(df['저가'].min()),
        "최근10일_OHLCV": []
    }

    for _, row in df.tail(10).iterrows():
        result["최근10일_OHLCV"].append({
            "날짜": str(row.name.date()),
            "시가": int(row['시가']),
            "고가": int(row['고가']),
            "저가": int(row['저가']),
            "종가": int(row['종가']),
            "거래량": int(row['거래량'])
        })

    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def search_stock(keyword: str) -> str:
    """종목명으로 종목코드를 검색합니다.

    Args:
        keyword: 검색할 종목명 (예: '삼성전자', '알체라')
    """
    today = datetime.today().strftime("%Y%m%d")
    tickers = stock.get_market_ticker_list(today, market="ALL")

    results = []
    for t in tickers:
        name = stock.get_market_ticker_name(t)
        if keyword.lower() in name.lower():
            results.append({"종목코드": t, "종목명": name})

    if not results:
        return f"'{keyword}'에 해당하는 종목을 찾을 수 없습니다."

    return json.dumps(results[:10], ensure_ascii=False, indent=2)


@mcp.tool()
def get_us_stock_analysis(symbol: str, days: int = 120) -> str:
    """미국 주식 종목을 분석합니다.

    Args:
        symbol: 티커 심볼 (예: 'AAPL', 'TSLA', 'NVDA', 'GOOGL')
        days: 조회 기간 (일수, 기본 120일)
    """
    tk = yf.Ticker(symbol)
    df = tk.history(period=f"{days}d")

    if df.empty:
        return f"'{symbol}'에 대한 데이터를 찾을 수 없습니다."
    if len(df) < 2:
        return f"'{symbol}'의 데이터가 부족합니다 (거래일 {len(df)}일). 분석 기간을 늘려주세요."

    info = tk.info
    name = info.get("shortName", symbol)

    # 기술적 지표 계산
    df['SMA5'] = df['Close'].rolling(5).mean()
    df['SMA20'] = df['Close'].rolling(20).mean()
    df['SMA60'] = df['Close'].rolling(60).mean()
    df['RSI'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()

    macd_ind = ta.trend.MACD(df['Close'])
    df['MACD'] = macd_ind.macd()
    df['MACD_signal'] = macd_ind.macd_signal()
    df['MACD_hist'] = macd_ind.macd_diff()

    bb = ta.volatility.BollingerBands(df['Close'])
    df['BB_upper'] = bb.bollinger_hband()
    df['BB_lower'] = bb.bollinger_lband()

    ichimoku = ta.trend.IchimokuIndicator(df['High'], df['Low'], window1=9, window2=26, window3=52)
    df['Ichimoku_conversion'] = ichimoku.ichimoku_conversion_line()
    df['Ichimoku_base'] = ichimoku.ichimoku_base_line()
    df['Ichimoku_span_a'] = ichimoku.ichimoku_a()
    df['Ichimoku_span_b'] = ichimoku.ichimoku_b()
    df['Ichimoku_lagging'] = df['Close'].shift(-26)

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    result = {
        "종목명": name,
        "심볼": symbol,
        "현재가": round(latest['Close'], 2),
        "전일대비": round(latest['Close'] - prev['Close'], 2),
        "등락률": round((latest['Close'] - prev['Close']) / prev['Close'] * 100, 2),
        "거래량": int(latest['Volume']),
        "기술적지표": {
            "SMA5": round(latest['SMA5'], 2) if pd.notna(latest['SMA5']) else None,
            "SMA20": round(latest['SMA20'], 2) if pd.notna(latest['SMA20']) else None,
            "SMA60": round(latest['SMA60'], 2) if pd.notna(latest['SMA60']) else None,
            "RSI_14": round(latest['RSI'], 2) if pd.notna(latest['RSI']) else None,
            "MACD": round(latest['MACD'], 2) if pd.notna(latest['MACD']) else None,
            "MACD_signal": round(latest['MACD_signal'], 2) if pd.notna(latest['MACD_signal']) else None,
            "MACD_histogram": round(latest['MACD_hist'], 2) if pd.notna(latest['MACD_hist']) else None,
            "볼린저_상단": round(latest['BB_upper'], 2) if pd.notna(latest['BB_upper']) else None,
            "볼린저_하단": round(latest['BB_lower'], 2) if pd.notna(latest['BB_lower']) else None,
            "일목_전환선": round(latest['Ichimoku_conversion'], 2) if pd.notna(latest['Ichimoku_conversion']) else None,
            "일목_기준선": round(latest['Ichimoku_base'], 2) if pd.notna(latest['Ichimoku_base']) else None,
            "일목_선행스팬A": round(latest['Ichimoku_span_a'], 2) if pd.notna(latest['Ichimoku_span_a']) else None,
            "일목_선행스팬B": round(latest['Ichimoku_span_b'], 2) if pd.notna(latest['Ichimoku_span_b']) else None,
            "일목_후행스팬": round(latest['Ichimoku_lagging'], 2) if pd.notna(latest['Ichimoku_lagging']) else None,
        },
        "기간내_최고가": round(df['High'].max(), 2),
        "기간내_최저가": round(df['Low'].min(), 2),
        "시가총액": info.get("marketCap"),
        "52주_최고": info.get("fiftyTwoWeekHigh"),
        "52주_최저": info.get("fiftyTwoWeekLow"),
        "PER": info.get("trailingPE"),
        "최근10일_OHLCV": []
    }

    for _, row in df.tail(10).iterrows():
        result["최근10일_OHLCV"].append({
            "날짜": str(row.name.date()),
            "시가": round(row['Open'], 2),
            "고가": round(row['High'], 2),
            "저가": round(row['Low'], 2),
            "종가": round(row['Close'], 2),
            "거래량": int(row['Volume'])
        })

    return json.dumps(result, ensure_ascii=False, indent=2)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 스크리닝 공통 함수
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _calc_screening_indicators(df: pd.DataFrame, close='Close', high='High',
                                low='Low', open_='Open', volume='Volume') -> pd.DataFrame:
    """스크리닝용 기술적 지표를 일괄 계산합니다."""
    df = df.copy()

    df['MA5'] = df[close].rolling(5).mean()
    df['MA20'] = df[close].rolling(20).mean()
    df['MA60'] = df[close].rolling(60).mean()

    # RSI
    delta = df[close].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    df['RSI'] = 100 - (100 / (1 + rs))

    # MACD
    ema12 = df[close].ewm(span=12).mean()
    ema26 = df[close].ewm(span=26).mean()
    df['MACD'] = ema12 - ema26
    df['MACD_signal'] = df['MACD'].ewm(span=9).mean()
    df['MACD_hist'] = df['MACD'] - df['MACD_signal']

    # 볼린저 밴드
    df['BB_mid'] = df[close].rolling(20).mean()
    df['BB_std'] = df[close].rolling(20).std()
    df['BB_upper'] = df['BB_mid'] + 2 * df['BB_std']
    df['BB_lower'] = df['BB_mid'] - 2 * df['BB_std']

    # 볼린저 밴드 폭 (%)  ← 신규: BB 스퀴즈 전략용
    df['BB_width'] = ((df['BB_upper'] - df['BB_lower']) / df['BB_mid'] * 100)
    df['BB_width_MA20'] = df['BB_width'].rolling(20).mean()

    # 거래량 이동평균
    df['Vol_MA5'] = df[volume].rolling(5).mean()
    df['Vol_MA20'] = df[volume].rolling(20).mean()

    # 20일 최고가
    df['High_20d'] = df[high].rolling(20).max()

    # 5일 변동폭 (%)
    df['Range_5d'] = (
        (df[high].rolling(5).max() - df[low].rolling(5).min())
        / df[close].rolling(5).mean() * 100
    )

    # ── 신규 지표: 스토캐스틱 (%K, %D) ──
    stoch_k_period = 14
    stoch_d_period = 3
    lowest_low = df[low].rolling(stoch_k_period).min()
    highest_high = df[high].rolling(stoch_k_period).max()
    denom = highest_high - lowest_low
    df['Stoch_K'] = ((df[close] - lowest_low) / denom.replace(0, np.nan)) * 100
    df['Stoch_D'] = df['Stoch_K'].rolling(stoch_d_period).mean()

    # ── 신규 지표: 일목균형표 ──
    hi9 = df[high].rolling(9).max()
    lo9 = df[low].rolling(9).min()
    df['Ichi_tenkan'] = (hi9 + lo9) / 2  # 전환선

    hi26 = df[high].rolling(26).max()
    lo26 = df[low].rolling(26).min()
    df['Ichi_kijun'] = (hi26 + lo26) / 2  # 기준선

    df['Ichi_spanA'] = ((df['Ichi_tenkan'] + df['Ichi_kijun']) / 2).shift(26)  # 선행스팬A
    hi52 = df[high].rolling(52).max()
    lo52 = df[low].rolling(52).min()
    df['Ichi_spanB'] = ((hi52 + lo52) / 2).shift(26)  # 선행스팬B

    # 참조용 컬럼명 통일
    df['_close'] = df[close]
    df['_open'] = df[open_]
    df['_high'] = df[high]
    df['_low'] = df[low]
    df['_volume'] = df[volume]

    return df


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 기존 4개 전략
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _check_golden_cross(df: pd.DataFrame) -> tuple:
    """골든크로스 + 거래량 돌파"""
    if len(df) < 2:
        return False, {}
    today = df.iloc[-1]
    yesterday = df.iloc[-2]

    conds = {
        'MA5>MA20 크로스': bool(today['MA5'] > today['MA20'] and yesterday['MA5'] <= yesterday['MA20']),
        '거래량>5일평균×2': bool(today['_volume'] > today['Vol_MA5'] * 2),
        'RSI 40~70': bool(pd.notna(today['RSI']) and 40 <= today['RSI'] <= 70),
        '종가>MA20': bool(today['_close'] > today['MA20']),
    }
    score = sum(conds.values())
    return score >= 3, {'전략': '골든크로스+거래량', '점수': f'{score}/4', '조건': conds}


def _check_pullback(df: pd.DataFrame) -> tuple:
    """눌림목 매수 (조정 후 반등)"""
    if len(df) < 2:
        return False, {}
    today = df.iloc[-1]
    yesterday = df.iloc[-2]

    ma20_dist = abs(today['_close'] - today['MA20']) / today['MA20'] * 100 if today['MA20'] > 0 else 999

    conds = {
        'MA20>MA60 상승추세': bool(pd.notna(today['MA60']) and today['MA20'] > today['MA60']),
        '종가 MA20±3%': bool(ma20_dist <= 3),
        'RSI 35~50': bool(pd.notna(today['RSI']) and 35 <= today['RSI'] <= 50),
        '양봉(종가>시가)': bool(today['_close'] > today['_open']),
        'MACD히스토그램 개선': bool(pd.notna(today['MACD_hist']) and pd.notna(yesterday['MACD_hist'])
                              and today['MACD_hist'] > yesterday['MACD_hist']),
    }
    score = sum(conds.values())
    return score >= 4, {'전략': '눌림목 매수', '점수': f'{score}/5', '조건': conds}


def _check_momentum(df: pd.DataFrame) -> tuple:
    """모멘텀 돌파 (신고가 근접)"""
    if len(df) < 2:
        return False, {}
    today = df.iloc[-1]

    conds = {
        '종가>BB중심선': bool(pd.notna(today['BB_mid']) and today['_close'] > today['BB_mid']),
        '20일고가 95%이상': bool(pd.notna(today['High_20d']) and today['_close'] >= today['High_20d'] * 0.95),
        'RSI 55~75': bool(pd.notna(today['RSI']) and 55 <= today['RSI'] <= 75),
        'MACD>Signal': bool(pd.notna(today['MACD']) and pd.notna(today['MACD_signal'])
                           and today['MACD'] > today['MACD_signal']),
        '거래량>5일평균×1.5': bool(today['_volume'] > today['Vol_MA5'] * 1.5),
    }
    score = sum(conds.values())
    return score >= 4, {'전략': '모멘텀 돌파', '점수': f'{score}/5', '조건': conds}


def _check_volume_breakout(df: pd.DataFrame) -> tuple:
    """거래량 폭발 초기 포착"""
    if len(df) < 2:
        return False, {}
    today = df.iloc[-1]

    conds = {
        '거래량>20일평균×3': bool(pd.notna(today['Vol_MA20']) and today['_volume'] > today['Vol_MA20'] * 3),
        '양봉(종가>시가)': bool(today['_close'] > today['_open']),
        '5일변동폭<5%(횡보)': bool(pd.notna(today['Range_5d']) and today['Range_5d'] < 5),
        '종가≥BB상단×0.98': bool(pd.notna(today['BB_upper']) and today['_close'] >= today['BB_upper'] * 0.98),
        'RSI 50~80': bool(pd.notna(today['RSI']) and 50 <= today['RSI'] <= 80),
    }
    score = sum(conds.values())
    return score >= 3, {'전략': '거래량 폭발', '점수': f'{score}/5', '조건': conds}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 신규 6개 전략
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _check_rsi_divergence(df: pd.DataFrame) -> tuple:
    """RSI 다이버전스 — 주가와 RSI의 방향 괴리를 포착합니다.

    ■ 매수(강세) 다이버전스: 주가는 저점을 낮추는데 RSI는 저점을 높임 → 하락 피로, 반등 기대
    ■ 매도(약세) 다이버전스: 주가는 고점을 높이는데 RSI는 고점을 낮춤 → 상승 피로, 조정 주의
    최근 20일 내 두 개의 피벗(고점/저점)을 비교해 판단합니다.
    """
    if len(df) < 20:
        return False, {}

    window = df.iloc[-20:]
    closes = window['_close'].values
    rsi_vals = window['RSI'].values

    if np.any(np.isnan(rsi_vals)):
        return False, {}

    # 간단한 피벗 탐색: 전반부([-20:-10])와 후반부([-10:]) 비교
    first_half_close = closes[:10]
    second_half_close = closes[10:]
    first_half_rsi = rsi_vals[:10]
    second_half_rsi = rsi_vals[10:]

    today = df.iloc[-1]

    # ── 매수(강세) 다이버전스 ──
    fh_low_idx = np.argmin(first_half_close)
    sh_low_idx = np.argmin(second_half_close)
    price_lower_low = second_half_close[sh_low_idx] < first_half_close[fh_low_idx]
    rsi_higher_low = second_half_rsi[sh_low_idx] > first_half_rsi[fh_low_idx]

    bullish = price_lower_low and rsi_higher_low

    # ── 매도(약세) 다이버전스 ──
    fh_high_idx = np.argmax(first_half_close)
    sh_high_idx = np.argmax(second_half_close)
    price_higher_high = second_half_close[sh_high_idx] > first_half_close[fh_high_idx]
    rsi_lower_high = second_half_rsi[sh_high_idx] < first_half_rsi[fh_high_idx]

    bearish = price_higher_high and rsi_lower_high

    conds = {
        '주가 저점↓ + RSI 저점↑ (강세)': bool(bullish),
        '주가 고점↑ + RSI 고점↓ (약세)': bool(bearish),
        'RSI 과매수(>70) 영역': bool(today['RSI'] > 70),
        'RSI 과매도(<30) 영역': bool(today['RSI'] < 30),
    }
    score = sum(conds.values())
    detected = bullish or bearish
    return detected, {'전략': 'RSI 다이버전스', '점수': f'{score}/4', '조건': conds}


def _check_macd_divergence(df: pd.DataFrame) -> tuple:
    """MACD 다이버전스 — 주가와 MACD의 방향 괴리를 포착합니다.

    ■ 매수(강세) 다이버전스: 주가 저점 하락 + MACD 저점 상승 → 반등 신호
    ■ 매도(약세) 다이버전스: 주가 고점 상승 + MACD 고점 하락 → 조정 신호
    ■ 제로라인 상향 돌파: MACD가 0선을 아래→위로 돌파 → 추세 전환 확인
    """
    if len(df) < 20:
        return False, {}

    window = df.iloc[-20:]
    closes = window['_close'].values
    macd_vals = window['MACD'].values

    if np.any(np.isnan(macd_vals)):
        return False, {}

    today = df.iloc[-1]
    yesterday = df.iloc[-2]

    first_half_close = closes[:10]
    second_half_close = closes[10:]
    first_half_macd = macd_vals[:10]
    second_half_macd = macd_vals[10:]

    # 강세 다이버전스
    fh_low_idx = np.argmin(first_half_close)
    sh_low_idx = np.argmin(second_half_close)
    bullish = (second_half_close[sh_low_idx] < first_half_close[fh_low_idx]
               and second_half_macd[sh_low_idx] > first_half_macd[fh_low_idx])

    # 약세 다이버전스
    fh_high_idx = np.argmax(first_half_close)
    sh_high_idx = np.argmax(second_half_close)
    bearish = (second_half_close[sh_high_idx] > first_half_close[fh_high_idx]
               and second_half_macd[sh_high_idx] < first_half_macd[fh_high_idx])

    # 제로라인 상향 돌파
    zero_cross_up = bool(
        pd.notna(today['MACD']) and pd.notna(yesterday['MACD'])
        and yesterday['MACD'] <= 0 and today['MACD'] > 0
    )

    conds = {
        '주가 저점↓ + MACD 저점↑ (강세)': bool(bullish),
        '주가 고점↑ + MACD 고점↓ (약세)': bool(bearish),
        'MACD 제로라인 상향돌파': zero_cross_up,
        'MACD>Signal': bool(pd.notna(today['MACD']) and pd.notna(today['MACD_signal'])
                            and today['MACD'] > today['MACD_signal']),
    }
    score = sum(conds.values())
    detected = bullish or bearish or zero_cross_up
    return detected, {'전략': 'MACD 다이버전스', '점수': f'{score}/4', '조건': conds}


def _check_stochastic(df: pd.DataFrame) -> tuple:
    """스토캐스틱 과매수/과매도 — %K, %D 교차로 단기 반전을 포착합니다.

    ■ 매수 신호: %K와 %D가 모두 20 이하(과매도)에서 %K가 %D를 상향 돌파
    ■ 매도 신호: %K와 %D가 모두 80 이상(과매수)에서 %K가 %D를 하향 돌파
    """
    if len(df) < 2:
        return False, {}

    today = df.iloc[-1]
    yesterday = df.iloc[-2]

    k = today.get('Stoch_K')
    d = today.get('Stoch_D')
    k_prev = yesterday.get('Stoch_K')
    d_prev = yesterday.get('Stoch_D')

    if any(pd.isna(v) for v in [k, d, k_prev, d_prev]):
        return False, {}

    # 매수: 과매도 구간에서 골든크로스
    buy_signal = bool(k_prev <= d_prev and k > d and d < 20)
    # 매도: 과매수 구간에서 데드크로스
    sell_signal = bool(k_prev >= d_prev and k < d and d > 80)

    conds = {
        '과매도 골든크로스(%K↑%D, D<20)': buy_signal,
        '과매수 데드크로스(%K↓%D, D>80)': sell_signal,
        '%K 과매도(<20)': bool(k < 20),
        '%K 과매수(>80)': bool(k > 80),
        '%K값': round(float(k), 1),
        '%D값': round(float(d), 1),
    }
    score = sum(1 for key in ['과매도 골든크로스(%K↑%D, D<20)',
                               '과매수 데드크로스(%K↓%D, D>80)',
                               '%K 과매도(<20)', '%K 과매수(>80)']
                if conds[key])
    detected = buy_signal or sell_signal
    return detected, {'전략': '스토캐스틱', '점수': f'{score}/4', '조건': conds}


def _check_bb_squeeze(df: pd.DataFrame) -> tuple:
    """볼린저 밴드 스퀴즈 — 변동성 수축 후 확장을 포착합니다.

    밴드 폭이 최근 20일 평균 대비 크게 축소된 뒤 다시 확장되기 시작하면
    큰 방향성 움직임이 임박했음을 의미합니다.
    종가 방향(상단 돌파/하단 이탈)으로 진입 방향을 판단합니다.
    """
    if len(df) < 5:
        return False, {}

    today = df.iloc[-1]
    yesterday = df.iloc[-2]

    bw = today.get('BB_width')
    bw_ma = today.get('BB_width_MA20')
    bw_prev = yesterday.get('BB_width')

    if any(pd.isna(v) for v in [bw, bw_ma, bw_prev]):
        return False, {}

    # 스퀴즈: 현재 밴드폭이 20일 평균의 50% 이하
    is_squeezed = bw < bw_ma * 0.5
    # 확장 시작: 전일보다 밴드폭이 넓어지기 시작
    expanding = bw > bw_prev
    # 돌파 방향
    breakout_up = bool(pd.notna(today['BB_upper']) and today['_close'] > today['BB_upper'])
    breakout_down = bool(pd.notna(today['BB_lower']) and today['_close'] < today['BB_lower'])

    conds = {
        '밴드폭 < 20일평균×0.5 (스퀴즈)': bool(is_squeezed),
        '밴드폭 확장 시작': bool(expanding),
        '종가 > BB상단 (상방돌파)': breakout_up,
        '종가 < BB하단 (하방이탈)': breakout_down,
        '현재 밴드폭(%)': round(float(bw), 1),
    }
    score = sum(1 for key in ['밴드폭 < 20일평균×0.5 (스퀴즈)',
                               '밴드폭 확장 시작',
                               '종가 > BB상단 (상방돌파)',
                               '종가 < BB하단 (하방이탈)']
                if conds[key])
    detected = (is_squeezed and expanding) or breakout_up or breakout_down
    return detected, {'전략': 'BB 스퀴즈', '점수': f'{score}/4', '조건': conds}


def _check_ichimoku_breakout(df: pd.DataFrame) -> tuple:
    """일목균형표 구름대 돌파 — 추세 전환 및 강도를 종합 판단합니다.

    ■ 전환선 > 기준선: 단기 상승 모멘텀
    ■ 종가 > 구름대 상단: 강한 상승 추세 확인
    ■ 구름대 상향 돌파 (전일 구름 내 → 당일 구름 위): 매수 신호
    """
    if len(df) < 2:
        return False, {}

    today = df.iloc[-1]
    yesterday = df.iloc[-2]

    tenkan = today.get('Ichi_tenkan')
    kijun = today.get('Ichi_kijun')
    spanA = today.get('Ichi_spanA')
    spanB = today.get('Ichi_spanB')

    if any(pd.isna(v) for v in [tenkan, kijun, spanA, spanB]):
        return False, {}

    cloud_top = max(spanA, spanB)
    cloud_bottom = min(spanA, spanB)

    prev_spanA = yesterday.get('Ichi_spanA')
    prev_spanB = yesterday.get('Ichi_spanB')
    if pd.notna(prev_spanA) and pd.notna(prev_spanB):
        prev_cloud_top = max(prev_spanA, prev_spanB)
        cloud_breakout = bool(yesterday['_close'] <= prev_cloud_top and today['_close'] > cloud_top)
    else:
        cloud_breakout = False

    conds = {
        '전환선 > 기준선': bool(tenkan > kijun),
        '종가 > 구름대 상단': bool(today['_close'] > cloud_top),
        '구름대 상향 돌파': cloud_breakout,
        '구름 두께 양수(spanA>spanB, 상승 구름)': bool(spanA > spanB),
    }
    score = sum(conds.values())
    detected = score >= 3 or cloud_breakout
    return detected, {'전략': '일목균형표 돌파', '점수': f'{score}/4', '조건': conds}


def _check_three_line_alignment(df: pd.DataFrame) -> tuple:
    """3선 정배열/역배열 — 이동평균선 정렬 상태로 추세 강도를 판단합니다.

    ■ 정배열 (MA5 > MA20 > MA60): 강한 상승 추세 → 매수 유리
    ■ 역배열 (MA5 < MA20 < MA60): 강한 하락 추세 → 매수 불리
    ■ 정배열 전환: 직전일 비정배열 → 당일 정배열 전환 시 초기 매수 신호
    """
    if len(df) < 2:
        return False, {}

    today = df.iloc[-1]
    yesterday = df.iloc[-2]

    ma5 = today.get('MA5')
    ma20 = today.get('MA20')
    ma60 = today.get('MA60')

    if any(pd.isna(v) for v in [ma5, ma20, ma60]):
        return False, {}

    bullish_align = bool(ma5 > ma20 > ma60)
    bearish_align = bool(ma5 < ma20 < ma60)

    # 정배열 전환 감지 (어제는 아닌데 오늘 정배열)
    prev_ma5 = yesterday.get('MA5')
    prev_ma20 = yesterday.get('MA20')
    prev_ma60 = yesterday.get('MA60')
    if all(pd.notna(v) for v in [prev_ma5, prev_ma20, prev_ma60]):
        was_not_bullish = not (prev_ma5 > prev_ma20 > prev_ma60)
        just_aligned = bullish_align and was_not_bullish
    else:
        just_aligned = False

    # MA5-MA20 간격이 벌어지는 중 (가속)
    ma5_ma20_gap = (ma5 - ma20) / ma20 * 100 if ma20 > 0 else 0
    accelerating = bool(ma5_ma20_gap > 1)  # 1% 이상 벌어짐

    conds = {
        'MA5>MA20>MA60 정배열': bullish_align,
        'MA5<MA20<MA60 역배열': bearish_align,
        '정배열 전환(신규)': bool(just_aligned),
        'MA5-MA20 가속(1%↑)': accelerating,
    }
    score = sum(1 for key in ['MA5>MA20>MA60 정배열', '정배열 전환(신규)', 'MA5-MA20 가속(1%↑)']
                if conds[key])
    detected = bullish_align or just_aligned
    return detected, {'전략': '3선 정배열', '점수': f'{score}/3', '조건': conds}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 전략 레지스트리 (기존 4 + 신규 6 = 10개)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


SCREENING_STRATEGIES = [
    # 기존 4개
    _check_golden_cross,
    _check_pullback,
    _check_momentum,
    _check_volume_breakout,
    # 신규 6개
    _check_rsi_divergence,
    _check_macd_divergence,
    _check_stochastic,
    _check_bb_squeeze,
    _check_ichimoku_breakout,
    _check_three_line_alignment,
]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 새 도구: 한국 주식 스크리닝
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _fetch_naver_sise_list(path: str, sosok: str, max_pages: int) -> list[dict]:
    """네이버 금융 시세 테이블 페이지에서 종목 리스트를 수집하는 범용 헬퍼.

    Args:
        path: 페이지 경로 (예: 'sise_quant.naver', 'sise_rise.naver', 'sise_low_up.naver')
        sosok: '0'=KOSPI, '1'=KOSDAQ
        max_pages: 조회할 페이지 수

    Returns:
        [{"code": "005930", "name": "삼성전자"}, ...]  (이미 dedup됨)
    """
    items = []
    seen = set()
    for page in range(1, max_pages + 1):
        url = f"https://finance.naver.com/sise/{path}?sosok={sosok}&page={page}"
        try:
            r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
            r.encoding = 'euc-kr'
        except requests.RequestException:
            break
        soup = BeautifulSoup(r.text, 'lxml')
        for tr in soup.select('table.type_2 tr'):
            a = tr.select_one('a.tltle')
            if not a:
                continue
            href = a.get('href', '')
            if 'code=' not in href:
                continue
            code = href.split('code=')[-1]
            if code in seen:
                continue
            seen.add(code)
            items.append({"code": code, "name": a.text.strip()})
    return items


def _get_kr_candidates(market: str, limit: int) -> list[dict]:
    """한국 주식 스크리닝용 넓은 시드 후보군을 수집합니다.

    거래량 상위 + 상승률 상위 + 급등 리스트의 합집합. 20일 내 거래량 급증 필터
    후처리를 전제로 하므로 시드를 넉넉히 확보합니다.
    """
    sosok_list = ["0", "1"] if market.upper() == "ALL" else \
                 (["0"] if market.upper() == "KOSPI" else ["1"])
    # 각 소스별 상위 N 수집 — 페이지당 ~40종목
    sources = [
        ("sise_quant.naver", 2),   # 거래량 상위
        ("sise_rise.naver", 2),    # 상승률 상위
        ("sise_low_up.naver", 2),  # 급등
    ]
    merged = []
    seen = set()
    for sosok in sosok_list:
        for path, pages in sources:
            for item in _fetch_naver_sise_list(path, sosok, pages):
                if item['code'] in seen:
                    continue
                seen.add(item['code'])
                merged.append(item)
    return merged[:limit]


def _fetch_yahoo_screener(scr_id: str, count: int = 50) -> list[str]:
    """Yahoo Finance 내부 스크리너 API를 호출해 심볼 목록을 가져옵니다.

    Args:
        scr_id: 'most_actives' | 'day_gainers' | 'day_losers' | 'small_cap_gainers' 등
        count: 가져올 종목 수 (최대 250)

    Returns:
        ["NVDA", "PLTR", ...]
    """
    url = (f"https://query2.finance.yahoo.com/v1/finance/screener/predefined/saved"
           f"?scrIds={scr_id}&count={count}")
    try:
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        data = r.json()
    except (requests.RequestException, ValueError):
        return []
    quotes = data.get('finance', {}).get('result', [{}])[0].get('quotes', [])
    return [q.get('symbol') for q in quotes if q.get('symbol')]


def _get_us_candidates(limit: int) -> list[str]:
    """미국 주식 스크리닝용 넓은 시드 후보군을 수집합니다.

    Yahoo most_actives + day_gainers + small_cap_gainers 의 합집합.
    """
    sources = ["most_actives", "day_gainers", "small_cap_gainers"]
    merged = []
    seen = set()
    for scr_id in sources:
        for sym in _fetch_yahoo_screener(scr_id, count=50):
            if sym in seen:
                continue
            seen.add(sym)
            merged.append(sym)
    return merged[:limit]


def _had_volume_spike(df: pd.DataFrame, volume_col: str,
                      lookback: int = 20, baseline: int = 40,
                      threshold: float = 3.0) -> tuple[bool, float]:
    """최근 N 거래일 안에 거래량 폭발이 있었는지 판정.

    판정식:
        max(volume[최근 lookback일]) / mean(volume[그 이전 baseline일]) >= threshold

    Args:
        df: OHLCV 데이터프레임 (날짜 오름차순)
        volume_col: 거래량 컬럼명 ('거래량' / 'Volume')
        lookback: 폭발 이력을 찾을 최근 거래일 수
        baseline: 비교 기준이 되는 과거 평균 구간 길이
        threshold: 몇 배 이상을 "급증"으로 볼지

    Returns:
        (급증이력있음, 최대배율)
    """
    if len(df) < lookback + baseline:
        return False, 0.0
    recent = df[volume_col].iloc[-lookback:]
    prior = df[volume_col].iloc[-(lookback + baseline):-lookback]
    prior_mean = prior.mean()
    if pd.isna(prior_mean) or prior_mean <= 0:
        return False, 0.0
    ratio = float(recent.max() / prior_mean)
    return ratio >= threshold, round(ratio, 2)


def _check_trend_template(df: pd.DataFrame, close_col: str, high_col: str,
                          low_col: str, lookback_52w: int = 252) -> tuple[bool, dict]:
    """Minervini Trend Template — Stage 2 상승추세 판정.

    6가지 조건을 모두 충족해야 통과:
      1) 종가 > MA50
      2) MA50 > MA150
      3) MA150 > MA200
      4) MA200이 1개월 전보다 상승
      5) 현재가 ≥ 52주 저점 × 1.30 (저점에서 30% 이상 오름)
      6) 현재가 ≥ 52주 고점 × 0.75 (고점의 25% 범위 내)
    """
    if len(df) < 200:
        return False, {"사유": f"데이터부족({len(df)}일, 200일 필요)"}

    close = df[close_col]
    latest = close.iloc[-1]
    ma50 = close.rolling(50).mean().iloc[-1]
    ma150 = close.rolling(150).mean().iloc[-1]
    ma200_series = close.rolling(200).mean()
    ma200 = ma200_series.iloc[-1]
    ma200_1m = ma200_series.iloc[-21] if len(df) >= 221 else None

    window = df.iloc[-lookback_52w:] if len(df) >= lookback_52w else df
    high_52w = window[high_col].max()
    low_52w = window[low_col].min()

    conds = {
        "종가 > MA50": bool(pd.notna(ma50) and latest > ma50),
        "MA50 > MA150": bool(pd.notna(ma50) and pd.notna(ma150) and ma50 > ma150),
        "MA150 > MA200": bool(pd.notna(ma150) and pd.notna(ma200) and ma150 > ma200),
        "MA200 1개월전 대비 상승": bool(ma200_1m is not None and pd.notna(ma200) and ma200 > ma200_1m),
        "52주저점 +30% 이상": bool(low_52w > 0 and latest >= low_52w * 1.30),
        "52주고점 -25% 이내": bool(high_52w > 0 and latest >= high_52w * 0.75),
    }
    return all(conds.values()), conds


def _check_near_52w_high(df: pd.DataFrame, close_col: str, high_col: str,
                         threshold: float = 0.75,
                         lookback_52w: int = 252) -> tuple[bool, float]:
    """52주 고점 근접 필터.

    현재가 ≥ 52주 고점 × threshold 인지 판정.
    Returns: (통과여부, 52주고점대비 현재가 비율 0~1)
    """
    if df.empty:
        return False, 0.0
    window = df.iloc[-lookback_52w:] if len(df) >= lookback_52w else df
    high_52w = window[high_col].max()
    if pd.isna(high_52w) or high_52w <= 0:
        return False, 0.0
    ratio = float(df[close_col].iloc[-1] / high_52w)
    return ratio >= threshold, round(ratio, 3)


def _compute_rs_delta(df: pd.DataFrame, close_col: str,
                      benchmark_return_pct: float,
                      period_days: int = 63) -> float | None:
    """종목의 N일 수익률과 벤치마크 수익률 차이(퍼센트 포인트).

    Args:
        period_days: 수익률 계산 구간 (기본 63일 ≈ 3개월)

    Returns:
        `종목_수익률 - 벤치마크_수익률` (pp). 데이터 부족시 None.
    """
    if len(df) < period_days + 1:
        return None
    close_now = df[close_col].iloc[-1]
    close_then = df[close_col].iloc[-period_days - 1]
    if pd.isna(close_now) or pd.isna(close_then) or close_then <= 0:
        return None
    stock_return = (close_now / close_then - 1) * 100
    return round(stock_return - benchmark_return_pct, 2)


def _apply_strategies(df: pd.DataFrame, ticker: str, name: str,
                      close_col: str, volume_col: str) -> list[dict]:
    """종목 하나에 전체 전략을 적용해 통과한 결과만 반환합니다."""
    hits = []
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    vol_ma5 = latest['Vol_MA5']
    vol_ratio = round(latest[volume_col] / vol_ma5, 1) if vol_ma5 > 0 else 0
    change_pct = round((latest[close_col] - prev[close_col]) / prev[close_col] * 100, 2)

    for strat_func in SCREENING_STRATEGIES:
        passed, info = strat_func(df)
        if not passed:
            continue
        hits.append({
            "종목코드": ticker,
            "종목명": name,
            "전략": info['전략'],
            "점수": info['점수'],
            "현재가": int(latest[close_col]),
            "등락률": f"{change_pct:+}%",
            "RSI": round(latest['RSI'], 1) if pd.notna(latest['RSI']) else None,
            "거래량비": f"{vol_ratio}x",
            "조건상세": info['조건'],
        })
    return hits


@mcp.tool()
def screen_kr_stocks(market: str = "ALL", top_n: int = 150,
                     min_trade_value: int = 500_000_000,
                     lookback_days: int = 20,
                     spike_threshold: float = 3.0,
                     baseline_days: int = 40,
                     enable_trend_template: bool = True,
                     enable_near_52w_high: bool = True,
                     high_proximity: float = 0.75,
                     enable_rs_filter: bool = False,
                     rs_period_days: int = 63,
                     min_rs_outperformance: float = 0.0) -> str:
    """한국 주식에서 '최근 N일 내 거래량 급증 + 추세 정합' 종목을 필터링합니다.

    [시드] 네이버 거래량상위 + 상승률상위 + 급등 합집합
    [사전필터] 순차 적용:
      · 거래대금: `min_trade_value` 이상
      · 거래량 급증: `max(최근 lookback일) / 이전 baseline일 평균` ≥ `spike_threshold`
      · Minervini Trend Template (옵션): Stage 2 상승추세 6조건
      · 52주 고점 근접 (옵션): 현재가 ≥ 52주고점 × `high_proximity`
      · RS vs KODEX 200 (옵션): 3개월 초과수익률 ≥ `min_rs_outperformance` (pp)
    [전략] 10가지 기술적 전략 적용

    Args:
        market: 'KOSPI' | 'KOSDAQ' | 'ALL'
        top_n: 시드 후보 상한
        min_trade_value: 최소 거래대금 필터(원)
        lookback_days: 거래량 급증 룩백 (기본 20)
        spike_threshold: 급증 배율 (기본 3.0)
        baseline_days: 비교 기준 기간 (기본 40)
        enable_trend_template: Minervini Trend Template 사용 여부
        enable_near_52w_high: 52주 고점 근접 필터 사용 여부
        high_proximity: 52주 고점 대비 허용 비율 (0.75 = 고점의 75% 이상)
        enable_rs_filter: KODEX 200 대비 RS 필터 사용 여부
        rs_period_days: RS 수익률 계산 기간 (기본 63 ≈ 3개월)
        min_rs_outperformance: 벤치마크 초과수익 하한 (pp)
    """
    today_str = datetime.today().strftime("%Y%m%d")
    start_str = (datetime.today() - timedelta(days=365)).strftime("%Y%m%d")

    # 0) RS 필터 활성화 시 벤치마크(KODEX 200) 수익률 1회 계산
    benchmark_ret = None
    if enable_rs_filter:
        bench_df = stock.get_market_ohlcv(start_str, today_str, '069500')
        if len(bench_df) >= rs_period_days + 1:
            benchmark_ret = (bench_df['종가'].iloc[-1]
                             / bench_df['종가'].iloc[-rs_period_days - 1] - 1) * 100

    # 1) 넓은 시드 후보 수집
    candidates = _get_kr_candidates(market, top_n)

    # 2) 후보별 사전필터 파이프라인
    results = []
    funnel = {"거래량급증": 0, "Trend_Template": 0, "52주고점근접": 0, "RS": 0}
    for cand in candidates:
        ticker = cand['code']
        name = cand['name']
        try:
            df = stock.get_market_ohlcv(start_str, today_str, ticker)
            if len(df) < lookback_days + baseline_days:
                continue

            latest_trade_value = df['종가'].iloc[-1] * df['거래량'].iloc[-1]
            if latest_trade_value < min_trade_value:
                continue

            had_spike, spike_ratio = _had_volume_spike(
                df, '거래량', lookback_days, baseline_days, spike_threshold
            )
            if not had_spike:
                continue
            funnel["거래량급증"] += 1

            if enable_trend_template:
                passed_tt, _tt_conds = _check_trend_template(df, '종가', '고가', '저가')
                if not passed_tt:
                    continue
                funnel["Trend_Template"] += 1

            if enable_near_52w_high:
                passed_hi, high_ratio = _check_near_52w_high(df, '종가', '고가', high_proximity)
                if not passed_hi:
                    continue
                funnel["52주고점근접"] += 1
            else:
                high_ratio = None

            rs_delta = None
            if enable_rs_filter and benchmark_ret is not None:
                rs_delta = _compute_rs_delta(df, '종가', benchmark_ret, rs_period_days)
                if rs_delta is None or rs_delta < min_rs_outperformance:
                    continue
                funnel["RS"] += 1

            df = _calc_screening_indicators(
                df, close='종가', high='고가', low='저가', open_='시가', volume='거래량'
            )
            hits = _apply_strategies(df, ticker, name, '종가', '거래량')
            for h in hits:
                h['20일내_최대거래량배율'] = f"{spike_ratio}x"
                if high_ratio is not None:
                    h['52주고점대비'] = f"{round(high_ratio * 100, 1)}%"
                if rs_delta is not None:
                    h['RS초과수익(pp)'] = rs_delta
            results.extend(hits)
        except Exception:
            continue

    # 복수 전략 충족 종목 표시
    from collections import Counter
    ticker_counts = Counter(r['종목코드'] for r in results)
    multi_hits = {t for t, c in ticker_counts.items() if c > 1}

    for r in results:
        r['복수전략'] = r['종목코드'] in multi_hits

    results.sort(key=lambda x: (x['복수전략'], x['점수']), reverse=True)

    output = {
        "스크리닝일": today_str,
        "대상시장": market.upper(),
        "시드후보수": len(candidates),
        "필터링_단계별_통과": funnel,
        "필터링결과수": len(results),
        "거래량급증_조건": f"최근 {lookback_days}일 중 이전 {baseline_days}일 평균 대비 {spike_threshold}x 이상",
        "활성화_사전필터": {
            "Trend_Template": enable_trend_template,
            "52주고점근접": f"{enable_near_52w_high} (고점×{high_proximity})",
            "RS_vs_KODEX200": f"{enable_rs_filter} (초과 ≥{min_rs_outperformance}pp)",
        },
        "적용전략수": len(SCREENING_STRATEGIES),
        "적용전략": [
            "골든크로스+거래량", "눌림목 매수", "모멘텀 돌파", "거래량 폭발",
            "RSI 다이버전스", "MACD 다이버전스", "스토캐스틱",
            "BB 스퀴즈", "일목균형표 돌파", "3선 정배열",
        ],
        "복수전략_충족종목": [
            {"종목코드": t, "종목명": next(r['종목명'] for r in results if r['종목코드'] == t),
             "해당전략": [r['전략'] for r in results if r['종목코드'] == t]}
            for t in multi_hits
        ],
        "결과": results,
    }

    return json.dumps(output, ensure_ascii=False, indent=2)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 새 도구: 미국 주식 스크리닝
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@mcp.tool()
def screen_us_stocks(symbols: list[str] | None = None,
                     top_n: int = 100,
                     lookback_days: int = 20,
                     spike_threshold: float = 3.0,
                     baseline_days: int = 40,
                     enable_trend_template: bool = True,
                     enable_near_52w_high: bool = True,
                     high_proximity: float = 0.75,
                     enable_rs_filter: bool = False,
                     rs_period_days: int = 63,
                     min_rs_outperformance: float = 0.0) -> str:
    """미국 주식에서 '최근 N일 내 거래량 급증 + 추세 정합' 종목을 필터링합니다.

    [시드] symbols 미지정 시 Yahoo `most_actives` + `day_gainers` + `small_cap_gainers`
    [사전필터] 순차 적용:
      · 거래량 급증: `max(최근 lookback일) / 이전 baseline일 평균` ≥ `spike_threshold`
      · Minervini Trend Template (옵션): Stage 2 상승추세 6조건
      · 52주 고점 근접 (옵션): 현재가 ≥ 52주고점 × `high_proximity`
      · RS vs SPY (옵션): 3개월 초과수익률 ≥ `min_rs_outperformance` (pp)
    [전략] 10가지 기술적 전략 적용

    Args:
        symbols: 스크리닝할 티커 목록. None이면 Yahoo 스크리너에서 시드 수집
        top_n: 시드 후보 상한
        lookback_days: 거래량 급증 룩백
        spike_threshold: 급증 배율
        baseline_days: 비교 기준 기간
        enable_trend_template: Minervini Trend Template 사용 여부
        enable_near_52w_high: 52주 고점 근접 필터 사용 여부
        high_proximity: 52주 고점 대비 허용 비율 (0.75 = 고점의 75% 이상)
        enable_rs_filter: SPY 대비 RS 필터 사용 여부
        rs_period_days: RS 수익률 계산 기간 (기본 63 ≈ 3개월)
        min_rs_outperformance: 벤치마크 초과수익 하한 (pp)
    """
    # 1) 시드 후보 결정
    target_symbols = symbols if symbols else _get_us_candidates(top_n)

    end = datetime.now()
    start = end - timedelta(days=365)
    results = []
    funnel = {"거래량급증": 0, "Trend_Template": 0, "52주고점근접": 0, "RS": 0}

    # 2) RS 필터용 벤치마크(SPY) 1회 다운로드
    benchmark_ret = None
    if enable_rs_filter:
        spy = yf.download('SPY', start=start, end=end, progress=False, auto_adjust=True)
        if isinstance(spy.columns, pd.MultiIndex):
            spy.columns = spy.columns.get_level_values(0)
        if len(spy) >= rs_period_days + 1:
            benchmark_ret = (spy['Close'].iloc[-1]
                             / spy['Close'].iloc[-rs_period_days - 1] - 1) * 100

    # 3) 배치 다운로드 (개별 호출 대비 수~수십 배 빠름)
    if not target_symbols:
        batch = pd.DataFrame()
    elif len(target_symbols) == 1:
        single = yf.download(target_symbols[0], start=start, end=end,
                             progress=False, auto_adjust=True)
        if isinstance(single.columns, pd.MultiIndex):
            single.columns = single.columns.get_level_values(0)
        batch = {target_symbols[0]: single}
    else:
        batch = yf.download(target_symbols, start=start, end=end,
                            progress=False, group_by='ticker',
                            threads=True, auto_adjust=True)

    for symbol in target_symbols:
        try:
            if isinstance(batch, dict):
                df = batch[symbol]
            else:
                df = batch[symbol].dropna(how='all')
            if df.empty or len(df) < lookback_days + baseline_days:
                continue

            had_spike, spike_ratio = _had_volume_spike(
                df, 'Volume', lookback_days, baseline_days, spike_threshold
            )
            if not had_spike:
                continue
            funnel["거래량급증"] += 1

            if enable_trend_template:
                passed_tt, _tt = _check_trend_template(df, 'Close', 'High', 'Low')
                if not passed_tt:
                    continue
                funnel["Trend_Template"] += 1

            if enable_near_52w_high:
                passed_hi, high_ratio = _check_near_52w_high(df, 'Close', 'High', high_proximity)
                if not passed_hi:
                    continue
                funnel["52주고점근접"] += 1
            else:
                high_ratio = None

            rs_delta = None
            if enable_rs_filter and benchmark_ret is not None:
                rs_delta = _compute_rs_delta(df, 'Close', benchmark_ret, rs_period_days)
                if rs_delta is None or rs_delta < min_rs_outperformance:
                    continue
                funnel["RS"] += 1

            df = _calc_screening_indicators(
                df, close='Close', high='High', low='Low', open_='Open', volume='Volume'
            )

            for strat_func in SCREENING_STRATEGIES:
                passed, info = strat_func(df)
                if not passed:
                    continue
                latest = df.iloc[-1]
                prev = df.iloc[-2]
                vol_ratio = round(latest['_volume'] / latest['Vol_MA5'], 1) if latest['Vol_MA5'] > 0 else 0
                result_entry = {
                    "심볼": symbol,
                    "전략": info['전략'],
                    "점수": info['점수'],
                    "현재가": round(float(latest['_close']), 2),
                    "등락률": f"{round((latest['_close'] - prev['_close']) / prev['_close'] * 100, 2):+}%",
                    "RSI": round(float(latest['RSI']), 1) if pd.notna(latest['RSI']) else None,
                    "거래량비": f"{vol_ratio}x",
                    "20일내_최대거래량배율": f"{spike_ratio}x",
                    "조건상세": info['조건'],
                }
                if high_ratio is not None:
                    result_entry['52주고점대비'] = f"{round(high_ratio * 100, 1)}%"
                if rs_delta is not None:
                    result_entry['RS초과수익(pp)'] = rs_delta
                results.append(result_entry)
        except Exception:
            continue

    # 복수 전략 충족 종목 표시
    from collections import Counter
    ticker_counts = Counter(r['심볼'] for r in results)
    multi_hits = {t for t, c in ticker_counts.items() if c > 1}

    for r in results:
        r['복수전략'] = r['심볼'] in multi_hits

    results.sort(key=lambda x: (x['복수전략'], x['점수']), reverse=True)

    output = {
        "스크리닝일": datetime.today().strftime("%Y%m%d"),
        "시드종목수": len(target_symbols),
        "필터링_단계별_통과": funnel,
        "필터링결과수": len(results),
        "거래량급증_조건": f"최근 {lookback_days}일 중 이전 {baseline_days}일 평균 대비 {spike_threshold}x 이상",
        "활성화_사전필터": {
            "Trend_Template": enable_trend_template,
            "52주고점근접": f"{enable_near_52w_high} (고점×{high_proximity})",
            "RS_vs_SPY": f"{enable_rs_filter} (초과 ≥{min_rs_outperformance}pp)",
        },
        "적용전략수": len(SCREENING_STRATEGIES),
        "적용전략": [
            "골든크로스+거래량", "눌림목 매수", "모멘텀 돌파", "거래량 폭발",
            "RSI 다이버전스", "MACD 다이버전스", "스토캐스틱",
            "BB 스퀴즈", "일목균형표 돌파", "3선 정배열",
        ],
        "복수전략_충족종목": [
            {"심볼": t,
             "해당전략": [r['전략'] for r in results if r['심볼'] == t]}
            for t in multi_hits
        ],
        "결과": results,
    }

    return json.dumps(output, ensure_ascii=False, indent=2)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 새 도구: 개별 종목 전략 진단
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@mcp.tool()
def diagnose_stock(ticker: str, market: str = "KR") -> str:
    """특정 종목이 10가지 단기 전략 중 어떤 조건에 해당하는지 상세 진단합니다.

    ■ 기존 전략: 골든크로스+거래량, 눌림목 매수, 모멘텀 돌파, 거래량 폭발
    ■ 신규 전략: RSI 다이버전스, MACD 다이버전스, 스토캐스틱 과매수/과매도,
                BB 스퀴즈, 일목균형표 구름대 돌파, 3선 정배열/역배열

    Args:
        ticker: 종목코드 (한국) 또는 티커심볼 (미국). 예: '005930', 'AAPL'
        market: 'KR' 또는 'US'. 기본 'KR'
    """
    if market.upper() == "KR":
        end_str = datetime.today().strftime("%Y%m%d")
        start_str = (datetime.today() - timedelta(days=200)).strftime("%Y%m%d")
        df = stock.get_market_ohlcv(start_str, end_str, ticker)
        if df.empty:
            return f"종목코드 {ticker}에 대한 데이터를 찾을 수 없습니다."
        name = stock.get_market_ticker_name(ticker)
        df = _calc_screening_indicators(
            df, close='종가', high='고가', low='저가', open_='시가', volume='거래량'
        )
    else:
        tk = yf.Ticker(ticker)
        df = tk.history(period="200d")
        if df.empty:
            return f"'{ticker}'에 대한 데이터를 찾을 수 없습니다."
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        info = tk.info
        name = info.get("shortName", ticker)
        df = _calc_screening_indicators(
            df, close='Close', high='High', low='Low', open_='Open', volume='Volume'
        )

    if len(df) < 60:
        return f"데이터가 부족합니다 (거래일 {len(df)}일). 최소 60일 필요."

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    diagnoses = []
    for strat_func in SCREENING_STRATEGIES:
        passed, info = strat_func(df)
        diagnoses.append({
            "전략": info.get('전략', '알수없음'),
            "충족": passed,
            "점수": info.get('점수', '0/0'),
            "조건상세": info.get('조건', {}),
        })

    passed_strategies = [d['전략'] for d in diagnoses if d['충족']]
    vol_ratio = round(latest['_volume'] / latest['Vol_MA5'], 1) if latest['Vol_MA5'] > 0 else 0

    result = {
        "종목": name,
        "코드": ticker,
        "시장": market.upper(),
        "현재가": round(float(latest['_close']), 2),
        "등락률": f"{round((latest['_close'] - prev['_close']) / prev['_close'] * 100, 2):+}%",
        "RSI": round(float(latest['RSI']), 1) if pd.notna(latest['RSI']) else None,
        "거래량비": f"{vol_ratio}x",
        "충족전략수": f"{len(passed_strategies)}/{len(SCREENING_STRATEGIES)}",
        "충족전략": passed_strategies,
        "전략별진단": diagnoses,
    }

    return json.dumps(result, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run()