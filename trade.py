# 06. 실제 매수/매도 주문 실행

import requests
from config import BASE_URL, APP_KEY, APP_SECRET, ACCOUNT, ACCOUNT_CODE


def _order(token, ticker, is_buy, qty=1):

    url = f"{BASE_URL}/uapi/domestic-stock/v1/trading/order-cash"

    headers = {
        "authorization": f"Bearer {token}",
        "appKey": APP_KEY,
        "appSecret": APP_SECRET,
        "tr_id": "VTTC0802U" if is_buy else "VTTC0801U"  # 모의: 매수/매도
    }

    body = {
        "CANO": ACCOUNT,
        "ACNT_PRDT_CD": ACCOUNT_CODE,
        "PDNO": ticker,
        "ORD_DVSN": "01",       # 시장가
        "ORD_QTY": str(qty),
        "ORD_UNPR": "0"         # 시장가일 때 0
    }

    res = requests.post(url, headers=headers, json=body)
    result = res.json()

    if result.get("rt_cd") == "0":
        action = "매수" if is_buy else "매도"
        print(f"{action} 주문 성공 | {ticker} {qty}주 | 주문번호: {result['output']['ODNO']}")
    else:
        print(f"주문 실패: {result.get('msg1')}")

    return result


def buy_stock(token, ticker, qty=1):
    return _order(token, ticker, is_buy=True, qty=qty)


def sell_stock(token, ticker, qty=1):
    return _order(token, ticker, is_buy=False, qty=qty)
