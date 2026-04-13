# server.py
from mcp.server.fastmcp import FastMCP
from pykrx import stock
from datetime import datetime, timedelta
import pandas as pd
import ta
import json
import yfinance as yf


mcp = FastMCP("Stock Analyzer")


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


if __name__ == "__main__":
    mcp.run()