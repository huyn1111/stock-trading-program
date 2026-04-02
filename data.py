# 03. 주식 데이터 가져오기(현재가 조회 / 전날 종가 조회 / 최근 OHLCV 조회)

import time
from datetime import date, timedelta
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


def get_prev_avg(token, ticker):
    """전날 시가/고가/저가/종가 평균 반환"""

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
            prev = data["output"][1]
            avg = (int(prev["stck_oprc"]) + int(prev["stck_hgpr"]) +
                   int(prev["stck_lwpr"]) + int(prev["stck_clpr"])) / 4
            return avg

        print(f"전날 가격 조회 실패, 재시도 중... ({attempt + 1}/3): {data.get('msg1', data)}")
        time.sleep(1)

    return None


def get_recent_ohlcv(token: str, ticker: str, n: int = 30) -> list[dict]:
    """최근 n 영업일 OHLCV 반환 (오래된 날짜 순). RSI 계산용."""
    today = date.today().strftime("%Y%m%d")
    start = (date.today() - timedelta(days=90)).strftime("%Y%m%d")

    url = f"{BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
    headers = {
        "authorization": f"Bearer {token}",
        "appKey": APP_KEY,
        "appSecret": APP_SECRET,
        "tr_id": "FHKST03010100"
    }
    params = {
        "fid_cond_mrkt_div_code": "J",
        "fid_input_iscd": ticker,
        "fid_input_date_1": start,
        "fid_input_date_2": today,
        "fid_period_div_code": "D",
        "fid_org_adj_prc": "0"
    }

    res  = requests.get(url, headers=headers, params=params)
    data = res.json()

    if "output2" not in data:
        print(f"OHLCV 조회 실패: {data.get('msg1', data)}")
        return []

    rows = []
    for row in data["output2"]:
        if not row.get("stck_bsop_date"):
            continue
        rows.append({
            "date":  row["stck_bsop_date"],
            "open":  int(row["stck_oprc"]),
            "high":  int(row["stck_hgpr"]),
            "low":   int(row["stck_lwpr"]),
            "close": int(row["stck_clpr"]),
        })

    rows.sort(key=lambda x: x["date"])
    # 장 중에 오늘 데이터가 포함될 수 있으므로 어제까지만 사용
    rows = [r for r in rows if r["date"] < today]
    return rows[-n:]


def get_today_open(token: str, ticker: str) -> int | None:
    """당일 시가 반환. VB 목표가 계산용."""
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

    res  = requests.get(url, headers=headers, params=params)
    data = res.json()

    if "output" not in data:
        return None
    return int(data["output"]["stck_oprc"])
