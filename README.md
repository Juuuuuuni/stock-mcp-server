# 📈 Stock MCP Server

한국/미국 주식의 기술적 분석과 전략 기반 스크리닝을 제공하는 **Model Context Protocol (MCP) 서버**입니다.
Claude Desktop, Claude Code 등 MCP 호환 클라이언트에서 자연어로 차트 분석·종목 스크리닝을 할 수 있습니다.

## ✨ Features

- 🇰🇷 **한국 주식 분석** — `pykrx` 기반 KOSPI/KOSDAQ 전 종목 OHLCV + 기술적 지표
- 🇺🇸 **미국 주식 분석** — `yfinance` 기반 NYSE/NASDAQ 종목 + 시가총액/PER/52주 고저가
- 🔍 **종목 검색** — 종목명으로 종목코드 찾기 (한국 종목)
- 📊 **10가지 Momentum 전략 + 7가지 Breakout 전략** — 골든크로스부터 VCP까지
- 🎯 **두 가지 스크리닝 철학** — 🐎 달리는 말 잡아타기 vs 🌱 곧 달릴 말 찾기
- 🔎 **다단 사전필터** — 거래량 급증·Trend Template·RS·52주 밴드 등

## 🛠️ Tools

| Tool | 설명 | 입력 예시 |
|------|------|-----------|
| `get_stock_analysis` | 한국 종목 기술적 분석 | `ticker="005930"` (삼성전자) |
| `get_us_stock_analysis` | 미국 종목 기술적 분석 | `symbol="NVDA"` |
| `search_stock` | 종목명 → 종목코드 검색 | `keyword="알체라"` |
| `screen_kr_momentum` | 🐎 한국 **달리는 말 잡아타기** (Stage 2 추세) | `market="ALL"` |
| `screen_us_momentum` | 🐎 미국 **달리는 말 잡아타기** | `symbols=None` (Yahoo 자동 시드) |
| `screen_kr_breakout` | 🌱 한국 **곧 달릴 말 찾기** (VCP·매집·Stage 1 말기) | `market="ALL"` |
| `screen_us_breakout` | 🌱 미국 **곧 달릴 말 찾기** | `symbols=None` |
| `diagnose_stock` | 특정 종목 전략 진단 | `ticker="005930", market="KR"` |

## 🎯 Screening: 두 가지 철학

### 🐎 Momentum — 달리는 말 잡아타기

이미 상승 추세에 진입한 종목의 **추세 지속(Stage 2 continuation)** 을 포착합니다.
O'Neil의 CANSLIM, Minervini의 Trend Template 이론 기반.

**파이프라인**
```
시드 (네이버 거래량/상승률/급등  |  Yahoo most_actives/day_gainers/small_cap_gainers)
  ↓
① min_trade_value         — 유동성
② 당일 과열 제외 +10% 이상  — 추격매수 방지
③ 20일 내 거래량 급증 ≥ 3x  — 자금 유입 시그널
④ Minervini Trend Template — Stage 2 6조건 (ON)
⑤ 52주 고점 근접            — OFF (Trend Template과 중복)
⑥ RS vs 지수               — OFF (opt-in, 강한 종목만 보고 싶을 때)
  ↓
10가지 Momentum 전략 적용
```

**적용 전략 (10)**
- 기존 4: 골든크로스+거래량, 눌림목 매수, 모멘텀 돌파, 거래량 폭발
- 신규 6: RSI 다이버전스, MACD 다이버전스, 스토캐스틱, BB 스퀴즈, 일목균형표 돌파, 3선 정배열

### 🌱 Breakout — 곧 달릴 말 찾기

아직 크게 움직이지 않은 **매집 단계 / 돌파 직전** 종목을 포착합니다.
Mark Minervini의 VCP 패턴, Wyckoff 매집 이론 기반.

**파이프라인**
```
시드 (Momentum과 동일 — 매집도 거래량에 반영됨)
  ↓
① min_trade_value
② 당일 과열 제외 +10% 이상
③ 누적 상승 한도: 최근 30일 +30% 이상 제외   ← Breakout 전용
④ 52주 밴드: 고점 × 0.85 이하 AND 저점 × 1.20 이상 ← 전용 (중간권만)
⑤ 20일 내 거래량 급증 ≥ 2x                    (momentum의 3x보다 완화)
  ↓
Breakout 7전략 적용  (Trend Template / 52w 근접 / RS 모두 off)
```

**적용 전략 (7)**
- 재사용 4: 눌림목 매수, 거래량 폭발, MACD 다이버전스, BB 스퀴즈
- 신규 3: **VCP 변동성 수축**, **조용한 매집**, **Stage 1 말기 전환**

## 🧪 두 모드 비교

| | 🐎 Momentum | 🌱 Breakout |
|---|---|---|
| **철학** | 추세 지속 | 매집 → 돌파 초기 |
| **누적 상승률** | 제한 없음 | **30일 +30% 이상 제외** |
| **52주 위치** | 고점 근접 권장 | **고점 85% 이하 + 저점 120% 이상 밴드** |
| **Trend Template** | ON (MA 정배열 요구) | OFF |
| **거래량 급증** | 3.0x | **2.0x** (매집은 덜 폭발적) |
| **전략 개수** | 10개 | 7개 (신규 3 포함) |
| **적합한 타이밍** | 시장 강세기, 추세 추종 | 조정기 후 재진입, 바닥 반전 |

### 실전 결과 비교 예시

동일 시장(KOSPI) 기준:
- **Momentum**: 퍼스텍(6전략 충족) — 이미 달리고 있는 종목
- **Breakout**: 대원전선 30일 **-20.32%**, 52주고점 72% 지점에서 눌림목+VCP — 매집 전형

## 📊 신규 Breakout 전략 설명

### VCP (Volatility Contraction Pattern)
최근 15일을 5일씩 3구간으로 나눠 각 구간의 고저 범위(%)가 **순차 축소**되는지 판정.
코일링 스프링 형태 → 돌파 임박. (Mark Minervini)

### 조용한 매집 (Silent Accumulation)
최근 20일 거래량 평균이 이전 20일 대비 **증가**하고 급증일도 있지만,
같은 20일 가격 변동폭은 **±8% 이내** → 시장에 드러나지 않은 세력 매집.

### Stage 1 말기 전환
바닥 박스권(Stage 1)에서 완만한 상승(Stage 2 초입)으로 넘어가는 구간.
- MA60 기울기 1개월 전 대비 상승
- MA20 > MA60 (단기 상향 전환)
- 종가 > MA60 (지지 확보)
- BB폭 ≤ 20일 평균 (아직 변동성 미확장)

## 🔎 사전필터 파라미터 치트시트

### Momentum 스크리너 공통
| 파라미터 | 기본 | 용도 |
|---------|------|------|
| `exclude_if_up_pct` | 10.0 | 오늘 +10% 이상 제외. `None`이면 미적용 |
| `spike_threshold` | 3.0 | 거래량 급증 배율 |
| `enable_trend_template` | True | Minervini Trend Template |
| `enable_rs_filter` | False | RS 필터 (강한 종목만 보고 싶을 때 on) |
| `min_rs_outperformance` | 0.0 | 벤치마크 초과수익(pp) 임계값 |

### Breakout 스크리너 공통
| 파라미터 | 기본 | 용도 |
|---------|------|------|
| `max_cumulative_return_pct` | 30.0 | 최근 N일 누적 상승률 상한(%) |
| `cumulative_return_days` | 30 | 누적 계산 구간 |
| `high_ceiling` | 0.85 | 52주 고점 × 이 값 이하만 통과 |
| `low_floor` | 1.20 | 52주 저점 × 이 값 이상만 통과 |
| `spike_threshold` | 2.0 | 거래량 급증 (매집은 완화된 배율) |

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

### 개별 종목 분석
```
👤 삼성전자 최근 분석해줘
🤖 [get_stock_analysis("005930")] → 현재가 / RSI / MACD / 추세 해석

👤 NVDA 한 달 차트 분석
🤖 [get_us_stock_analysis("NVDA", days=30)]

👤 알체라 종목코드가 뭐야?
🤖 [search_stock("알체라")] → 347860
```

### 스크리닝 (달리는 말)
```
👤 지금 코스피에서 뜨는 종목 찾아줘
🤖 [screen_kr_momentum(market="KOSPI")]
   → Stage 2 추세 + 거래량 급증 종목. 퍼스텍(6전략), 대우건설(3전략) …

👤 미국 주식에서 강세 종목만 (RS 10pp 이상)
🤖 [screen_us_momentum(enable_rs_filter=True, min_rs_outperformance=10.0)]
```

### 스크리닝 (곧 달릴 말)
```
👤 코스닥에서 매집 단계 종목 스크리닝
🤖 [screen_kr_breakout(market="KOSDAQ")]
   → 누적 상승 30% 미만 + 52주 중간권 + VCP/매집 패턴

👤 아직 안 오른 바닥 종목만 (최근 30일 +10% 이내)
🤖 [screen_kr_breakout(max_cumulative_return_pct=10.0)]
```

### 개별 종목 전략 진단
```
👤 알체라 지금 어떤 단계야?
🤖 [diagnose_stock(ticker="347860", market="KR")]
   → 10전략 중 어느 조건 통과했는지 상세 진단
```

## 📋 출력 예시

### Momentum 스크리닝 결과 (요약)
```json
{
  "스크리닝일": "20260413",
  "대상시장": "KOSPI",
  "시드후보수": 80,
  "필터링_단계별_통과": {
    "당일과열제외": 64,
    "거래량급증": 31,
    "Trend_Template": 8,
    "52주고점근접": 0,
    "RS": 0
  },
  "필터링결과수": 26,
  "결과": [
    {
      "종목코드": "010820",
      "종목명": "퍼스텍",
      "전략": "모멘텀 돌파",
      "점수": "5/5",
      "현재가": 2340,
      "등락률": "+4.23%",
      "RSI": 68.4,
      "거래량비": "2.1x",
      "20일내_최대거래량배율": "8.7x",
      "복수전략": true
    }
  ]
}
```

### Breakout 스크리닝 결과 (요약)
```json
{
  "스크리닝일": "20260413",
  "모드": "Breakout (곧 달릴 말)",
  "대상시장": "KOSPI",
  "시드후보수": 80,
  "필터링_단계별_통과": {
    "당일과열제외": 64,
    "누적상승한도": 55,
    "52주밴드": 22,
    "거래량급증": 12
  },
  "필터링결과수": 28,
  "결과": [
    {
      "종목코드": "006340",
      "종목명": "대원전선",
      "전략": "눌림목 매수",
      "점수": "5/5",
      "현재가": 1245,
      "30일누적": "-20.32%",
      "52주고점대비": "72.2%",
      "52주저점대비": "128.4%",
      "복수전략": true
    }
  ]
}
```

## 🧩 Tech Stack

- **[FastMCP](https://github.com/modelcontextprotocol/python-sdk)** — MCP 서버 프레임워크
- **[pykrx](https://github.com/sharebook-kr/pykrx)** — 한국거래소 데이터
- **[yfinance](https://github.com/ranaroussi/yfinance)** — Yahoo Finance 데이터
- **[ta](https://github.com/bukosabino/ta)** — 기술적 분석 지표
- **BeautifulSoup + lxml** — 네이버 금융 / Yahoo 스크리너 HTML 파싱
- **pandas** — 데이터 처리

## 📚 References

- William J. O'Neil — *How to Make Money in Stocks* (CANSLIM)
- Mark Minervini — *Trade Like a Stock Market Wizard* (Trend Template, VCP)
- Richard Wyckoff — 가격-거래량 매집/분산 이론
- Stan Weinstein — *Secrets for Profiting in Bull and Bear Markets* (Stage Analysis)

## 📄 License

MIT
