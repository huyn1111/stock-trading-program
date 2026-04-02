# 자동매매 시스템

한국투자증권 Open API를 활용한 멀티전략 모의투자 자동매매 프로그램

---

## 파일 구조

```
auto-trading-system/
├── main.py                   # 메인 실행 파일 (매매 루프)
├── config.py                 # 환경설정 (dotenv 기반 API 키/계좌번호 로드)
├── api.py                    # 한국투자증권 API 토큰 발급
├── data.py                   # 현재가 / OHLCV / 시초가 조회
├── strategy.py               # 전략 인스턴스 정의 및 신호 생성
├── trade.py                  # 매수 / 매도 주문 실행 (KIS API)
├── account.py                # 잔고 조회 (보유 수량 / 매입평균가)
├── strategies/               # 전략 클래스 모음
│   ├── base.py               # BaseStrategy 추상 클래스
│   ├── rsi.py                # RSIStrategy
│   └── volatility_breakout.py# VolatilityBreakoutStrategy
├── backtest/                 # 백테스트 엔진 모음
│   ├── engine.py             # RSI/VB 백테스트 공통 엔진
│   ├── rsi_engine.py         # RSI 전용 엔진
│   ├── momentum_engine.py    # 모멘텀 전략 엔진
│   ├── data_loader.py        # OHLCV 데이터 로더 (캐시 포함)
│   └── report.py             # 결과 리포트 출력
├── results/
│   ├── best_strategies.json  # 백테스트 최적 전략 결과
│   └── all_tickers.json      # KOSPI/KOSDAQ 전 종목 목록
├── run_backtest.py           # RSI/VB 백테스트 실행
├── run_rsi_backtest.py       # RSI 전용 백테스트 실행
├── run_rsi_optimize.py       # RSI 파라미터 최적화
├── run_momentum_backtest.py  # 모멘텀 백테스트 실행
├── run_universe_backtest.py  # 전 종목 유니버스 백테스트
├── download_all_data.py      # 전 종목 OHLCV 다운로드
├── .env                      # API 키 및 계좌번호 (Git 제외)
└── .env.example              # .env 작성 양식 예시
```

---

## 매매 전략 (백테스트 최적 결과 기반)

### 1. RSI 전략 (5종목)

RSI 크로스오버 신호 기반. 일봉 데이터로 판단, 장 시작 시 1회 실행.

| 종목 | 파라미터 | Test 수익률 |
|------|----------|------------|
| 삼성전자 (005930) | RSI(7, OS=34, OB=65) | +47% |
| SK하이닉스 (000660) | RSI(7, OS=31, OB=70) | +106% |
| LIG넥스원 (079550) | RSI(7, OS=38, OB=63) | +151% |
| 두산에너빌리티 (034020) | RSI(7, OS=33, OB=68) | +162% |
| 레인보우로보틱스 (277810) | RSI(7, OS=39, OB=70) | +214% |

### 2. 변동성 돌파 전략 (1종목)

당일 시가 + (전날 고가 − 전날 저가) × k 를 목표가로 설정. 장 중 모니터링.

| 종목 | 파라미터 | Test 수익률 |
|------|----------|------------|
| 에코프로 (086520) | k=0.9 | +334% |

### 3. 폴백 전략 (전 종목 적용)

백테스트 미선정 종목에 대해 전날 종가 대비 하락률로 분할 매수, 수익률 기준 매도.

| 조건 | 동작 |
|------|------|
| 전날 종가 대비 −5% | 1주 매수 |
| 전날 종가 대비 −7% | 2주 추가 매수 |
| 전날 종가 대비 −10% | 3주 추가 매수 |
| 수익률 +5% | 절반 매도 |
| 수익률 +10% | 전량 매도 |
| 수익률 −20% | 손절 전량 매도 |

---

## 실행 방법

### 1. 패키지 설치

```bash
pip install requests python-dotenv
```

### 2. `.env` 파일 생성

`.env.example`을 참고하여 `.env` 파일을 작성합니다.

```
APP_KEY=모의투자_앱키
APP_SECRET=모의투자_시크릿키
ACCOUNT=계좌번호_8자리
ACCOUNT_CODE=01
```

> KIS Developers(https://apiportal.koreainvestment.com)에서 **모의투자 전용** 앱을 등록하여 발급받아야 합니다.

### 3. 실행

```bash
python main.py
```

터미널에서 `자산현황` 입력 시 현재 보유 종목과 수익률을 출력합니다.

---

## 백테스트 실행

```bash
# RSI/VB 전략 백테스트
python run_backtest.py

# RSI 파라미터 최적화
python run_rsi_optimize.py

# 모멘텀 전략 백테스트
python run_momentum_backtest.py

# 전 종목 유니버스 백테스트 (최적 전략 선정)
python run_universe_backtest.py
```

---

## 주의사항

- 현재 **모의투자** 환경에서만 동작합니다.
- `.env` 파일은 절대 Git에 올리지 않습니다. (`.gitignore` 처리됨)
- 실계좌 전환 시 `config.py`의 `BASE_URL` 및 `trade.py`의 `tr_id` 변경 필요합니다.
- `results/best_strategies.json`이 있으면 백테스트 최적 전략을 자동 로드합니다.
