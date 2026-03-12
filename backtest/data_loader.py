"""
한국투자증권 API로 일별 OHLCV 과거 데이터를 가져옴.
"""

import time
import requests
from config import BASE_URL, APP_KEY, APP_SECRET


def load_ohlcv(token: str, ticker: str, start: str, end: str) -> list[dict]:
    """
    일별 OHLCV 데이터 반환 (오래된 날짜 순 정렬).

    Args:
        token:  인증 토큰
        ticker: 종목코드 (예: "005930")
        start:  시작일 "YYYYMMDD"
        end:    종료일 "YYYYMMDD"

    Returns:
        [{"date", "open", "high", "low", "close", "volume"}, ...]
    """

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
        "fid_input_date_2": end,
        "fid_period_div_code": "D",
        "fid_org_adj_prc": "0"
    }

    time.sleep(0.5)
    res = requests.get(url, headers=headers, params=params)
    data = res.json()

    if "output2" not in data:
        raise Exception(f"데이터 조회 실패: {data.get('msg1', data)}")

    result = []
    for row in data["output2"]:
        if not row.get("stck_bsop_date"):
            continue
        result.append({
            "date":   row["stck_bsop_date"],
            "open":   int(row["stck_oprc"]),
            "high":   int(row["stck_hgpr"]),
            "low":    int(row["stck_lwpr"]),
            "close":  int(row["stck_clpr"]),
            "volume": int(row["acml_vol"])
        })

    # API는 최신순 반환 → 오래된 순으로 정렬
    result.sort(key=lambda x: x["date"])
    return result
