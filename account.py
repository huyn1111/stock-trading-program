# 04. 가상 계좌 관리

import requests
from config import BASE_URL, APP_KEY, APP_SECRET, ACCOUNT, ACCOUNT_CODE


def get_balance(token):

    url = f"{BASE_URL}/uapi/domestic-stock/v1/trading/inquire-balance"

    headers = {
        "authorization": f"Bearer {token}",
        "appKey": APP_KEY,
        "appSecret": APP_SECRET,
        "tr_id": "VTTC8434R"
    }

    params = {
        "CANO": ACCOUNT,
        "ACNT_PRDT_CD": ACCOUNT_CODE,
        "AFHR_FLPR_YN": "N",
        "OFL_YN": "",
        "INQR_DVSN": "02",
        "UNPR_DVSN": "01",
        "FUND_STTL_ICLD_YN": "N",
        "FNCG_AMT_AUTO_RDPT_YN": "N",
        "PRCS_DVSN": "01",
        "CTX_AREA_FK100": "",
        "CTX_AREA_NK100": ""
    }

    res = requests.get(url, headers=headers, params=params)

    return res.json()


def get_holdings(token, tickers):
    """잔고를 한 번만 조회해서 여러 종목의 보유 수량/매입평균가를 딕셔너리로 반환"""

    data = get_balance(token)
    stocks = data.get("output1", [])

    holdings = {ticker: {"qty": 0, "avg_price": 0} for ticker in tickers}

    for stock in stocks:
        code = stock.get("pdno")
        qty = int(stock.get("hldg_qty", 0))
        avg_price = int(float(stock.get("pchs_avg_pric", 0)))
        if code in holdings and qty > 0:
            holdings[code] = {"qty": qty, "avg_price": avg_price}
            print(f"보유 확인: {code} {qty}주 (매입평균가: {avg_price:,}원)")

    for ticker in tickers:
        if holdings[ticker]["qty"] == 0:
            print(f"미보유 확인: {ticker}")

    return holdings
