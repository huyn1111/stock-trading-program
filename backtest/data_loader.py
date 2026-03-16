"""
한국투자증권 API로 일별 OHLCV 과거 데이터를 가져옴.
- 최초 1회만 KIS API 호출 → cache/{ticker}_{start}_{end}.parquet 저장
- 이후 실행부터는 parquet 캐시에서 즉시 로드 (CSV 대비 빠르고 용량 小)
"""

import os
import time
from datetime import datetime, timedelta

import pandas as pd
import requests
from config import BASE_URL, APP_KEY, APP_SECRET

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "cache")


def _cache_path(ticker: str, start: str, end: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, f"{ticker}_{start}_{end}.parquet")


def _prev_day(date_str: str) -> str:
    d = datetime.strptime(date_str, "%Y%m%d") - timedelta(days=1)
    return d.strftime("%Y%m%d")


def _fetch_once(token: str, ticker: str, start: str, end: str) -> list[dict]:
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
    res  = requests.get(url, headers=headers, params=params)
    data = res.json()

    if "output2" not in data:
        raise Exception(f"데이터 조회 실패: {data.get('msg1', data)}")

    rows = []
    for row in data["output2"]:
        if not row.get("stck_bsop_date"):
            continue
        rows.append({
            "date":   row["stck_bsop_date"],
            "open":   int(row["stck_oprc"]),
            "high":   int(row["stck_hgpr"]),
            "low":    int(row["stck_lwpr"]),
            "close":  int(row["stck_clpr"]),
            "volume": int(row["acml_vol"])
        })
    return rows  # 최신순


def _fetch_all(token: str, ticker: str, start: str, end: str) -> list[dict]:
    """페이지네이션으로 전체 기간 수집"""
    all_rows: list[dict] = []
    cur_end = end

    while True:
        batch = _fetch_once(token, ticker, start, cur_end)
        if not batch:
            break

        all_rows.extend(batch)
        oldest = min(row["date"] for row in batch)

        if oldest <= start or len(batch) < 100:
            break

        cur_end = _prev_day(oldest)
        if cur_end < start:
            break

    # 중복 제거 + 정렬 + 범위 필터
    seen, unique = set(), []
    for row in all_rows:
        if row["date"] not in seen:
            seen.add(row["date"])
            unique.append(row)

    unique.sort(key=lambda x: x["date"])
    return [r for r in unique if start <= r["date"] <= end]


def load_ohlcv(token: str, ticker: str, start: str, end: str) -> list[dict]:
    """
    일별 OHLCV 전체 기간 반환 (오래된 날짜 순).
    캐시(parquet)가 있으면 즉시 로드, 없으면 KIS API 호출 후 저장.

    Args:
        token:  인증 토큰 (캐시 히트 시 미사용)
        ticker: 종목코드
        start:  시작일 "YYYYMMDD"
        end:    종료일 "YYYYMMDD"
    """
    path = _cache_path(ticker, start, end)

    if os.path.exists(path):
        df = pd.read_parquet(path)
        return df.to_dict(orient="records")

    # 캐시 없음 → API 호출
    rows = _fetch_all(token, ticker, start, end)
    if rows:
        pd.DataFrame(rows).to_parquet(path, index=False)
    return rows
