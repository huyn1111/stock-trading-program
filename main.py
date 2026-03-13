import time
from datetime import datetime

from api import get_token
from data import get_price, get_prev_avg
from strategy import check_signal
from trade import buy_stock, sell_stock
from account import get_holdings

TICKERS = {
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "079550": "LIG넥스원",
    "034020": "두산에너빌리티",
    "086520": "에코프로",
    "277810": "레인보우로보틱스",
}

token = get_token()

# 종목별 기준가격 초기화
base_prices = {}
for ticker, name in TICKERS.items():
    base_prices[ticker] = get_prev_avg(token, ticker)
    time.sleep(0.5)  # API 호출 간격

# 잔고 한 번만 조회해서 전체 보유여부 확인
holdings = get_holdings(token, list(TICKERS.keys()))

for ticker, name in TICKERS.items():
    print(f"[{name}] 기준가격: {base_prices[ticker]}, 보유: {holdings[ticker]}")

last_print_time = 0  # 마지막 현재가 출력 시각

while True:

    now = time.time()
    if now - last_print_time >= 600:  # 10분마다 현재가 출력
        time.sleep(1)  # 메인 루프 마지막 호출과 간격 확보
        now_str = datetime.now().strftime("%H:%M")
        for ticker, name in TICKERS.items():
            price = get_price(token, ticker)
            if price:
                print(f"[{now_str}] {name}: {price:,}원")
            time.sleep(1)
        last_print_time = now

    hold_names = []

    for ticker, name in TICKERS.items():

        price = get_price(token, ticker)

        if price is None:
            print(f"[{name}] 가격 조회 실패")
            time.sleep(1)
            continue

        signal = check_signal(base_prices[ticker], price, holdings[ticker])

        if signal == "BUY" and not holdings[ticker]:
            print(f"[{name}] 현재가: {price}, 신호: {signal}")
            buy_stock(token, ticker)
            holdings[ticker] = True

        elif signal in ["SELL", "STOP_LOSS"] and holdings[ticker]:
            print(f"[{name}] 현재가: {price}, 신호: {signal}")
            sell_stock(token, ticker)
            holdings[ticker] = False

        else:
            hold_names.append(name)

        time.sleep(1)  # 종목 간 API 호출 간격

    if hold_names:
        print(f"[{', '.join(hold_names)}] : HOLD")

    time.sleep(10)
