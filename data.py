# 03. 주식 데이터 가져오기(현재가 조회)

import requests
from config import BASE_URL, APP_KEY, APP_SECRET

def get_price(token, ticker):

    url = f"{BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"

    headers = {
        "authorization": f"Bearer {token}",
        "appKey": APP_KEY,
        "appSecret": APP_SECRET,
        "tr_id": "FHKST01010100"
    }

    params = {
        "fid_cond_mrkt_div_code": "J",
        "fid_input_iscd": ticker
    }

    res = requests.get(url, headers=headers, params=params)

    return int(res.json()["output"]["stck_prpr"])