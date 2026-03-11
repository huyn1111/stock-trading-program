import time

from api import get_token
from data import get_price, get_prev_close
from strategy import check_signal
from trade import buy_stock, sell_stock
from account import is_holding

ticker = "005930"  # 삼성전자

token = get_token()

base_price = get_prev_close(token, ticker)

holding = is_holding(token, ticker)  # 시작 시 실제 보유 여부 자동 확인

print("기준가격:", base_price)

while True:

    price = get_price(token, ticker)

    if price is None:
        print("가격 조회 실패")
        time.sleep(10)
        continue

    signal = check_signal(base_price, price, holding)

    print("현재가:", price, "신호:", signal)

    if signal == "BUY" and not holding:
        buy_stock(token, ticker)
        holding = True

    elif signal in ["SELL", "STOP_LOSS"] and holding:
        sell_stock(token, ticker)
        holding = False

    time.sleep(10)
