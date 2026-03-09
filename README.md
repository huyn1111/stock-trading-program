# 자동매매 시스템

한국투자증권 Open API를 활용한 삼성전자 모의투자 자동매매 프로그램

---

## 파일 구조

```
auto-trading-system/
├── main.py        # 메인 실행 파일 (매매 루프)
├── config.py      # 환경설정 (API 키, 계좌번호 로드)
├── api.py         # 한국투자증권 API 토큰 발급
├── data.py        # 현재가 / 전날 종가 조회
├── strategy.py    # 매매 전략 (신호 판단)
├── trade.py       # 매수 / 매도 주문 실행
├── account.py     # 모의 계좌 잔고 조회
├── .env           # API 키 및 계좌번호 (Git 제외)
└── .env.example   # .env 작성 양식 예시
```

---

## 매매 전략

전날 종가를 기준가격으로 설정하여 아래 조건에 따라 자동 매매합니다.

| 조건 | 신호 | 동작 |
|------|------|------|
| 현재가 ≤ 기준가 × 0.90 (−10%) | BUY | 매수 |
| 현재가 ≥ 기준가 × 1.10 (+10%) | SELL | 매도 |
| 현재가 ≤ 기준가 × 0.85 (−15%) | STOP_LOSS | 손절 매도 |
| 그 외 | HOLD | 대기 |

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

---

## 주의사항

- 현재 **모의투자** 환경에서만 동작합니다.
- `.env` 파일은 절대 Git에 올리지 않습니다. (`.gitignore` 처리됨)
- 실계좌 전환 시 `config.py`의 `BASE_URL` 및 `trade.py`의 `tr_id` 변경 필요합니다.
