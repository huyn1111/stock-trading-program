import time

from api import get_token
from data import get_price, get_prev_close
from strategy import check_signal
from trade import buy_stock, sell_stock
from account import is_holding

TICKERS = {
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "079550": "LIG넥스원",
}

token = get_token()

# 종목별 기준가격, 보유여부 초기화
base_prices = {}
holdings = {}

for ticker, name in TICKERS.items():
    base_prices[ticker] = get_prev_close(token, ticker)
    holdings[ticker] = is_holding(token, ticker)
    print(f"[{name}] 기준가격: {base_prices[ticker]}, 보유: {holdings[ticker]}")

while True:

    for ticker, name in TICKERS.items():

        price = get_price(token, ticker)

        if price is None:
            print(f"[{name}] 가격 조회 실패")
            continue

        signal = check_signal(base_prices[ticker], price, holdings[ticker])

        print(f"[{name}] 현재가: {price}, 신호: {signal}")

        if signal == "BUY" and not holdings[ticker]:
            buy_stock(token, ticker)
            holdings[ticker] = True

        elif signal in ["SELL", "STOP_LOSS"] and holdings[ticker]:
            sell_stock(token, ticker)
            holdings[ticker] = False

        time.sleep(1)  # 종목 간 API 호출 간격

    time.sleep(10)
