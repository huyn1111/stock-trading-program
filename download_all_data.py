"""
전체 KOSPI + KOSDAQ 종목 OHLCV 데이터 다운로드 (캐시 저장)

- 이미 캐시된 종목은 건너뜀 → 중단 후 재실행해도 안전
- 다운로드 완료 후 run_universe_backtest.py 실행 가능

사용:
    python download_all_data.py           # 전체 다운로드
    python download_all_data.py --kospi   # KOSPI만
    python download_all_data.py --kosdaq  # KOSDAQ만
"""

import argparse
import json
import os
import sys
import time
import requests
import re
import pandas as pd
from io import StringIO
from datetime import datetime

from api import get_token
from backtest.data_loader import load_ohlcv

# 다운로드할 기간 (train / test)
PERIODS = [
    ("20220101", "20231231"),  # Train
    ("20240101", "20251231"),  # Test
]

CACHE_DIR   = "cache"
RESULTS_DIR = "results"


def fetch_all_tickers() -> dict[str, dict]:
    """KRX에서 전체 상장 종목 조회. results/all_tickers.json 캐시 사용."""
    path = os.path.join(RESULTS_DIR, "all_tickers.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        print(f"종목 목록 로드: {path}")
        return data

    print("KRX에서 전체 종목 조회 중...")
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://kind.krx.co.kr/"}
    url     = "https://kind.krx.co.kr/corpgeneral/corpList.do"

    def fetch(market_type, label):
        r = requests.get(url,
            params={"method": "download", "searchType": "13", "marketType": market_type},
            headers=headers, timeout=15)
        html = r.content.decode("euc-kr", errors="replace")
        df   = pd.read_html(StringIO(html), header=0)[0]
        result = {}
        for name, code in zip(df.iloc[:, 0].astype(str), df.iloc[:, 2].astype(str).str.zfill(6)):
            if re.match(r"^\d{6}$", code):
                result[code] = name
        print(f"  {label}: {len(result)}개")
        return result

    kospi  = fetch("stockMkt",  "KOSPI")
    kosdaq = fetch("kosdaqMkt", "KOSDAQ")

    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"KOSPI": kospi, "KOSDAQ": kosdaq}, f, ensure_ascii=False)
    print(f"  저장: {path}")
    return {"KOSPI": kospi, "KOSDAQ": kosdaq}


def count_cached(tickers: dict, start: str, end: str) -> int:
    return sum(
        1 for t in tickers
        if os.path.exists(os.path.join(CACHE_DIR, f"{t}_{start}_{end}.parquet"))
    )


def download(token: str, tickers: dict, start: str, end: str, label: str):
    """tickers 전체 OHLCV 다운로드. 캐시 있으면 건너뜀."""
    total   = len(tickers)
    already = count_cached(tickers, start, end)
    need    = total - already

    print(f"\n  [{label}]  {start}~{end}")
    print(f"  전체 {total}개 / 캐시됨 {already}개 / 신규 {need}개")

    if need == 0:
        print("  → 모두 캐시됨, 건너뜀")
        return

    done = 0
    fail = 0
    t0   = time.time()

    for i, (ticker, name) in enumerate(tickers.items(), 1):
        cache_path = os.path.join(CACHE_DIR, f"{ticker}_{start}_{end}.parquet")
        if os.path.exists(cache_path):
            continue

        try:
            rows = load_ohlcv(token, ticker, start, end)
            done += 1
        except Exception:
            fail += 1

        # 진행률 표시 (50종목마다)
        remaining = need - done - fail
        if (done + fail) % 50 == 0 and (done + fail) > 0:
            elapsed  = time.time() - t0
            per_call = elapsed / (done + fail)
            eta_sec  = remaining * per_call
            eta_min  = int(eta_sec // 60)
            eta_s    = int(eta_sec % 60)
            pct      = (done + fail) / need * 100
            print(f"    {done+fail}/{need} ({pct:.0f}%)  성공 {done} / 실패 {fail}"
                  f"  남은 시간 약 {eta_min}분 {eta_s}초")

        time.sleep(0.55)  # API 호출 간격

    elapsed = time.time() - t0
    print(f"  완료: 성공 {done}개 / 실패(상폐 등) {fail}개  ({elapsed/60:.1f}분 소요)")


def main():
    parser = argparse.ArgumentParser(description="전체 종목 데이터 다운로드")
    parser.add_argument("--kospi",  action="store_true", help="KOSPI만")
    parser.add_argument("--kosdaq", action="store_true", help="KOSDAQ만")
    args = parser.parse_args()

    data  = fetch_all_tickers()
    kospi  = data.get("KOSPI",  {})
    kosdaq = data.get("KOSDAQ", {})

    if args.kospi and not args.kosdaq:
        tickers = kospi
        label   = "KOSPI"
    elif args.kosdaq and not args.kospi:
        tickers = kosdaq
        label   = "KOSDAQ"
    else:
        tickers = {**kospi, **kosdaq}
        label   = "KOSPI+KOSDAQ"

    print(f"\n{'='*60}")
    print(f"  전체 종목 데이터 다운로드")
    print(f"  대상: {label}  {len(tickers)}개 종목")
    print(f"  기간: {' / '.join(f'{s}~{e}' for s,e in PERIODS)}")
    print(f"{'='*60}")

    total_need = sum(len(tickers) - count_cached(tickers, s, e) for s, e in PERIODS)
    est_min    = total_need * 0.6 / 60
    print(f"\n  신규 다운로드 필요: 약 {total_need}건  (예상 {est_min:.0f}분)")
    if total_need > 100:
        print("  Ctrl+C 로 중단해도 캐시가 유지되어 재실행 시 이어서 진행됩니다.")

    token = get_token()

    for start, end in PERIODS:
        download(token, tickers, start, end, label)

    print(f"\n{'='*60}")
    print("  다운로드 완료!")
    print("  다음 단계: python run_universe_backtest.py --market ALL")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
