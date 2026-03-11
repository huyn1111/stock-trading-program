# 03. 주식 데이터 가져오기(현재가 조회 / 전날 종가 조회)

import time
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
    data = res.json()

    if "output" not in data:
        print(f"현재가 조회 실패: {data.get('msg1', data)}")
        return None

    return int(data["output"]["stck_prpr"])


def get_prev_close(token, ticker):
    """전날 종가 반환"""

    url = f"{BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-daily-price"

    headers = {
        "authorization": f"Bearer {token}",
        "appKey": APP_KEY,
        "appSecret": APP_SECRET,
        "tr_id": "FHKST01010400"
    }

    params = {
        "fid_cond_mrkt_div_code": "J",
        "fid_input_iscd": ticker,
        "fid_org_adj_prc": "0",       # 수정주가 반영
        "fid_period_div_code": "D"    # 일별
    }

    for attempt in range(3):
        res = requests.get(url, headers=headers, params=params)
        data = res.json()

        if "output" in data:
            return int(data["output"][1]["stck_clpr"])

        print(f"전날 종가 조회 실패, 재시도 중... ({attempt + 1}/3): {data.get('msg1', data)}")
        time.sleep(1)

    return None
