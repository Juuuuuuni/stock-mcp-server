# 📈 Stock MCP Server

한국/미국 주식의 기술적 분석을 제공하는 **Model Context Protocol (MCP) 서버**입니다.
Claude Desktop, Claude Code 등 MCP 호환 클라이언트에서 자연어로 차트를 분석할 수 있습니다.

## ✨ Features

- 🇰🇷 **한국 주식 분석** — `pykrx` 기반 KOSPI/KOSDAQ 전 종목 OHLCV + 기술적 지표
- 🇺🇸 **미국 주식 분석** — `yfinance` 기반 NYSE/NASDAQ 종목 + 시가총액/PER/52주 고저가
- 🔍 **종목 검색** — 종목명으로 종목코드 찾기 (한국 종목)
- 📊 **기술적 지표** — SMA(5/20/60), RSI(14), MACD, Bollinger Bands, 일목균형표(Ichimoku)
- 📅 **기간 조정** — 기본 120일, 필요에 따라 커스터마이즈 가능

## 🛠️ Tools

| Tool | 설명 | 입력 예시 |
|------|------|-----------|
| `get_stock_analysis` | 한국 종목 기술적 분석 | `ticker="005930"` (삼성전자) |
| `search_stock` | 종목명 → 종목코드 검색 | `keyword="알체라"` |
| `get_us_stock_analysis` | 미국 종목 기술적 분석 | `symbol="NVDA"` |

## 📦 Installation

### Prerequisites
- Python 3.13+
- [uv](https://github.com/astral-sh/uv) (권장)

### Setup
```bash
git clone https://github.com/Juuuuuuni/stock-mcp-server.git
cd stock-mcp-server
uv sync
```

## 🚀 Usage

### Claude Desktop 연동

`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)
또는 `%APPDATA%\Claude\claude_desktop_config.json` (Windows)에 다음을 추가:

```json
{
  "mcpServers": {
    "stock-analyzer": {
      "command": "uv",
      "args": [
        "--directory",
        "/절대/경로/stock-mcp-server",
        "run",
        "python",
        "server.py"
      ]
    }
  }
}
```

### 직접 실행
```bash
uv run python server.py
```

## 💬 대화 예시

```
👤 삼성전자 최근 분석해줘
🤖 [get_stock_analysis("005930")] 실행 후 현재가 / RSI / MACD / 추세 해석

👤 NVDA 한 달 차트 분석
🤖 [get_us_stock_analysis("NVDA", days=30)] 실행

👤 알체라 종목코드가 뭐야?
🤖 [search_stock("알체라")] → 347860
```

## 📋 출력 예시 (IREN)

```json
{
  "종목명": "IREN LIMITED",
  "심볼": "IREN",
  "현재가": 39.32,
  "등락률": 6.1,
  "기술적지표": {
    "SMA5": 36.82,
    "SMA20": 38.54,
    "SMA60": 43.86,
    "RSI_14": 51.38,
    "MACD": -1.53,
    "볼린저_상단": 45.84,
    "볼린저_하단": 31.23
  },
  "시가총액": 13044770816,
  "52주_최고": 76.87,
  "52주_최저": 5.24
}
```

## 🧩 Tech Stack

- **[FastMCP](https://github.com/modelcontextprotocol/python-sdk)** — MCP 서버 프레임워크
- **[pykrx](https://github.com/sharebook-kr/pykrx)** — 한국거래소 데이터
- **[yfinance](https://github.com/ranaroussi/yfinance)** — Yahoo Finance 데이터
- **[ta](https://github.com/bukosabino/ta)** — 기술적 분석 지표
- **pandas** — 데이터 처리

## 📄 License

MIT
