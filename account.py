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
    "cash": 10000000
    "stocks": {}
