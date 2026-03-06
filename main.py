import time

from api import get_token
from data import get_price
from strategy import check_signal
from trade import buy_stock, sell_stock

ticker = "005930"  # 삼성전자

token = get_token()

base_price = get_price(token, ticker)

holding = False

print("기준가격:", base_price)

while True:

    price = get_price(token, ticker)

    signal = check_signal(base_price, price, holding)

    print("현재가:", price, "신호:", signal)

    if signal == "BUY":

        buy_stock(ticker)

        holding = True

    elif signal == "SELL":

        sell_stock(ticker)

        holding = False

    elif signal == "STOP_LOSS":

        sell_stock(ticker)

        holding = False

    time.sleep(10)