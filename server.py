# server.py
from mcp.server.fastmcp import FastMCP
from pykrx import stock
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import ta
import json
import yfinance as yf


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

    # 참조용 컬럼명 통일
    df['_close'] = df[close]
    df['_open'] = df[open_]
    df['_volume'] = df[volume]

    return df


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


SCREENING_STRATEGIES = [
    _check_golden_cross,
    _check_pullback,
    _check_momentum,
    _check_volume_breakout,
]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 새 도구: 한국 주식 스크리닝
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@mcp.tool()
def screen_kr_stocks(market: str = "ALL", min_trade_value: int = 100_000_000) -> str:
    """한국 주식(코스피/코스닥)에서 단기 상승 확률이 높은 종목을 기술적 지표로 필터링합니다.
    4가지 전략(골든크로스+거래량, 눌림목 매수, 모멘텀 돌파, 거래량 폭발)을 복합 적용합니다.

    Args:
        market: 시장 선택 ('KOSPI', 'KOSDAQ', 'ALL'). 기본 'ALL'
        min_trade_value: 최소 거래대금 필터 (원). 기본 1억원. 유동성 낮은 종목 제외용
    """
    today_str = datetime.today().strftime("%Y%m%d")
    start_str = (datetime.today() - timedelta(days=200)).strftime("%Y%m%d")

    if market.upper() == "ALL":
        tickers = stock.get_market_ticker_list(today_str, market="KOSPI") + \
                  stock.get_market_ticker_list(today_str, market="KOSDAQ")
    else:
        tickers = stock.get_market_ticker_list(today_str, market=market.upper())

    results = []

    for ticker in tickers:
        try:
            df = stock.get_market_ohlcv(start_str, today_str, ticker)
            if len(df) < 60:
                continue

            # 거래대금 필터
            latest_trade_value = df['종가'].iloc[-1] * df['거래량'].iloc[-1]
            if latest_trade_value < min_trade_value:
                continue

            df = _calc_screening_indicators(
                df, close='종가', high='고가', low='저가', open_='시가', volume='거래량'
            )

            name = stock.get_market_ticker_name(ticker)

            for strat_func in SCREENING_STRATEGIES:
                passed, info = strat_func(df)
                if passed:
                    latest = df.iloc[-1]
                    prev = df.iloc[-2]
                    vol_ratio = round(latest['거래량'] / latest['Vol_MA5'], 1) if latest['Vol_MA5'] > 0 else 0

                    results.append({
                        "종목코드": ticker,
                        "종목명": name,
                        "전략": info['전략'],
                        "점수": info['점수'],
                        "현재가": int(latest['종가']),
                        "등락률": f"{round((latest['종가'] - prev['종가']) / prev['종가'] * 100, 2):+}%",
                        "RSI": round(latest['RSI'], 1) if pd.notna(latest['RSI']) else None,
                        "거래량비": f"{vol_ratio}x",
                        "조건상세": info['조건'],
                    })
        except Exception:
            continue

    # 복수 전략 충족 종목 표시
    from collections import Counter
    ticker_counts = Counter(r['종목코드'] for r in results)
    multi_hits = {t for t, c in ticker_counts.items() if c > 1}

    for r in results:
        r['복수전략'] = r['종목코드'] in multi_hits

    # 복수전략 우선 → 점수 높은 순 정렬
    results.sort(key=lambda x: (x['복수전략'], x['점수']), reverse=True)

    output = {
        "스크리닝일": today_str,
        "대상시장": market.upper(),
        "스캔종목수": len(tickers),
        "필터링결과수": len(results),
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

# 미국 주요 종목 유니버스
US_UNIVERSE = [
    # 대형 기술주
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'AVGO',
    'ORCL', 'CRM', 'AMD', 'ADBE', 'INTC', 'CSCO', 'QCOM', 'TXN',
    'AMAT', 'MU', 'LRCX', 'KLAC', 'MRVL', 'SNPS', 'CDNS', 'PANW',
    'CRWD', 'ABNB', 'DASH', 'COIN', 'SQ', 'SHOP', 'SNOW', 'DDOG',
    'NET', 'ZS', 'MNDY', 'PLTR', 'RBLX', 'U', 'ROKU', 'TTD',
    # 헬스케어 / 바이오
    'UNH', 'JNJ', 'LLY', 'ABBV', 'MRK', 'PFE', 'TMO', 'ABT',
    'AMGN', 'GILD', 'ISRG', 'VRTX', 'REGN', 'MRNA', 'BIIB',
    # 금융
    'BRK-B', 'JPM', 'V', 'MA', 'BAC', 'GS', 'MS', 'AXP',
    # 소비재 / 산업
    'WMT', 'HD', 'COST', 'NKE', 'SBUX', 'MCD', 'DIS', 'NFLX',
    'BA', 'CAT', 'UPS', 'HON', 'GE', 'RTX', 'LMT',
    # 에너지 / 소재
    'XOM', 'CVX', 'COP', 'SLB', 'LIN', 'APD',
    # ETF
    'SPY', 'QQQ', 'IWM', 'ARKK', 'SOXX', 'XLF', 'XLE',
]


@mcp.tool()
def screen_us_stocks(symbols: list[str] | None = None) -> str:
    """미국 주식에서 단기 상승 확률이 높은 종목을 기술적 지표로 필터링합니다.
    4가지 전략(골든크로스+거래량, 눌림목 매수, 모멘텀 돌파, 거래량 폭발)을 복합 적용합니다.

    Args:
        symbols: 스크리닝할 티커 목록 (예: ['AAPL','TSLA','NVDA']). None이면 주요 90종목 기본 유니버스 사용
    """
    target_symbols = symbols if symbols else US_UNIVERSE

    end = datetime.now()
    start = end - timedelta(days=200)
    results = []

    for symbol in target_symbols:
        try:
            df = yf.download(symbol, start=start, end=end, progress=False)
            if len(df) < 60:
                continue

            # MultiIndex 처리
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            df = _calc_screening_indicators(
                df, close='Close', high='High', low='Low', open_='Open', volume='Volume'
            )

            for strat_func in SCREENING_STRATEGIES:
                passed, info = strat_func(df)
                if passed:
                    latest = df.iloc[-1]
                    prev = df.iloc[-2]
                    vol_ratio = round(latest['_volume'] / latest['Vol_MA5'], 1) if latest['Vol_MA5'] > 0 else 0

                    results.append({
                        "심볼": symbol,
                        "전략": info['전략'],
                        "점수": info['점수'],
                        "현재가": round(latest['_close'], 2),
                        "등락률": f"{round((latest['_close'] - prev['_close']) / prev['_close'] * 100, 2):+}%",
                        "RSI": round(latest['RSI'], 1) if pd.notna(latest['RSI']) else None,
                        "거래량비": f"{vol_ratio}x",
                        "조건상세": info['조건'],
                    })
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
        "스캔종목수": len(target_symbols),
        "필터링결과수": len(results),
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
    """특정 종목이 4가지 단기 전략 중 어떤 조건에 해당하는지 상세 진단합니다.

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
        "충족전략수": len(passed_strategies),
        "충족전략": passed_strategies,
        "전략별진단": diagnoses,
    }

    return json.dumps(result, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run()