import json
import os
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from api import get_token
from data import get_price, get_recent_ohlcv, get_today_open
from strategy import (RSI_STRATEGIES, VB_STRATEGIES,
                      load_strategies_from_file,
                      check_rsi_signal, check_vb_signal)
from trade import buy_stock, sell_stock
from account import get_holdings

# ── 최적 전략 종목 로드 ───────────────────────────────────────────────────────
_BEST_PATH = os.path.join("results", "best_strategies.json")

if os.path.exists(_BEST_PATH):
    with open(_BEST_PATH, encoding="utf-8") as _f:
        _cfg = json.load(_f)
    TICKERS = {t: info["name"] for t, info in _cfg["tickers"].items()}
    RSI_STRATEGIES, VB_STRATEGIES = load_strategies_from_file(_BEST_PATH)
    print(f"전략 설정 로드: {_BEST_PATH}")
    print(f"  생성일: {_cfg.get('generated_at')}  |  테스트 기간: {_cfg.get('test_period')}")
    print(f"  RSI {len(RSI_STRATEGIES)}종목 / VB {len(VB_STRATEGIES)}종목  (총 {len(TICKERS)}종목)")
else:
    TICKERS = {
        "005930": "삼성전자", "000660": "SK하이닉스",
        "079550": "LIG넥스원", "034020": "두산에너빌리티",
        "086520": "에코프로",  "277810": "레인보우로보틱스",
    }
    print("기본 전략 설정 사용 (6종목)")

RSI_TICKERS = {t: n for t, n in TICKERS.items() if t in RSI_STRATEGIES}
VB_TICKERS  = {t: n for t, n in TICKERS.items() if t in VB_STRATEGIES}

# ── 폴백 전략 종목 로드 (백테스트 탈락 종목) ─────────────────────────────────
_ALL_PATH = os.path.join("results", "all_tickers.json")
if os.path.exists(_ALL_PATH):
    with open(_ALL_PATH, encoding="utf-8") as _f:
        _all = json.load(_f)
    _all_dict = {**_all.get("KOSPI", {}), **_all.get("KOSDAQ", {})}
    FALLBACK_TICKERS = {t: n for t, n in _all_dict.items() if t not in TICKERS}
else:
    FALLBACK_TICKERS = {}

print(f"  폴백 전략 대상: {len(FALLBACK_TICKERS)}종목 (5%/7%/10% 하락매수, 20% 손절)")

# ── 보유 현황 조회 (전체 종목) ────────────────────────────────────────────────
ALL_TICKERS = {**TICKERS, **FALLBACK_TICKERS}
token    = get_token()
holdings = get_holdings(token, list(ALL_TICKERS.keys()))

# ── 보유 현황 출력 함수 ───────────────────────────────────────────────────────
def print_holdings(label="보유 현황"):
    held = [(t, n) for t, n in ALL_TICKERS.items() if holdings[t]["qty"] > 0]
    print(f"\n── {label} ──")
    if not held:
        print("  보유 종목 없음")
        return
    for ticker, name in held:
        h     = holdings[ticker]
        price = get_price(token, ticker)
        if price and h["avg_price"] > 0:
            pnl = f"{(price - h['avg_price']) / h['avg_price'] * 100:+.2f}%"
        else:
            pnl = "0%"
        strat = ""
        if ticker in RSI_STRATEGIES:
            strat = f" [{RSI_STRATEGIES[ticker].name}]"
        elif ticker in VB_STRATEGIES:
            strat = f" [{VB_STRATEGIES[ticker].name}]"
        else:
            strat = " [폴백]"
        print(f"  [{name}]{strat} {h['qty']}주 (매입평균가: {h['avg_price']:,}원 / 현재 수익률: {pnl})")

print_holdings("초기 보유 현황")

# ── 터미널 명령 리스너 ────────────────────────────────────────────────────────
def _cmd_listener():
    for line in sys.stdin:
        if line.strip() == "자산현황":
            print_holdings("자산 현황")

threading.Thread(target=_cmd_listener, daemon=True).start()

# ── 공통 상태 변수 ────────────────────────────────────────────────────────────
market_open_done_date = None
vb_cache:      dict[str, dict] = {}
vb_cache_date: dict[str, str]  = {}

TRADE_COOLDOWN = 300
last_trade_time: dict[str, float] = {}
_trade_lock = threading.Lock()

def _can_trade(ticker: str) -> bool:
    return time.time() - last_trade_time.get(ticker, 0) >= TRADE_COOLDOWN

def _mark_traded(ticker: str):
    last_trade_time[ticker] = time.time()

# ── 폴백 전략 상태 ────────────────────────────────────────────────────────────
# 전날 종가 캐시: {ticker: prev_close}
fb_prev_close: dict[str, float] = {}
# 당일 매수 레벨 실행 여부: {ticker: set()} — 완료된 레벨 저장
fb_buy_done: dict[str, set] = {}
# 폴백 모니터링 순서 (로테이션)
_fb_list = list(FALLBACK_TICKERS.keys())
_fb_idx  = 0
FALLBACK_BATCH = 50  # 10초 사이클당 체크할 폴백 종목 수

def _reset_fallback_daily():
    """장 시작 시 당일 매수 레벨 초기화."""
    fb_buy_done.clear()

def _fetch_fb_prev_close(ticker: str):
    """폴백 종목의 전날 종가를 API로 조회."""
    try:
        rows = get_recent_ohlcv(token, ticker)
        if rows:
            fb_prev_close[ticker] = rows[-1]["close"]
    except Exception:
        pass

def _process_rsi(ticker: str, name: str):
    """RSI 신호 판단 + 매매 (스레드용)."""
    try:
        ohlcv   = get_recent_ohlcv(token, ticker)
        holding = holdings[ticker]["qty"] > 0
        signal  = check_rsi_signal(ticker, ohlcv, holding)

        with _trade_lock:
            if not _can_trade(ticker):
                return
            if signal == "BUY":
                print(f"  [BUY]  [{name}] RSI 매수")
                buy_stock(token, ticker, qty=1)
                holdings[ticker]["qty"] += 1
                _mark_traded(ticker)
            elif signal == "SELL":
                print(f"  [SELL] [{name}] RSI 매도")
                sell_stock(token, ticker, qty=holdings[ticker]["qty"])
                holdings[ticker]["qty"]       = 0
                holdings[ticker]["avg_price"] = 0
                _mark_traded(ticker)
    except Exception as e:
        print(f"  [{name}] RSI 처리 오류: {e}")

def _process_fallback(ticker: str, name: str):
    """폴백 종목 매수/매도 판단 + 실행."""
    prev_close = fb_prev_close.get(ticker)
    if not prev_close:
        return

    try:
        price = get_price(token, ticker)
        if not price:
            return

        h   = holdings[ticker]
        qty = h["qty"]
        avg = h["avg_price"]

        # ── 보유 중: 매도 판단 (수익률 기준) ──────────────────────────────
        if qty > 0 and avg > 0:
            pnl_pct = (price - avg) / avg * 100
            with _trade_lock:
                if not _can_trade(ticker):
                    return
                if pnl_pct <= -20:
                    print(f"  [SELL] [{name}] 폴백 손절 {pnl_pct:+.1f}% ({qty}주 전량)")
                    sell_stock(token, ticker, qty=qty)
                    holdings[ticker]["qty"]       = 0
                    holdings[ticker]["avg_price"] = 0
                    _mark_traded(ticker)
                elif pnl_pct >= 10:
                    print(f"  [SELL] [{name}] 폴백 익절(10%) {pnl_pct:+.1f}% ({qty}주 전량)")
                    sell_stock(token, ticker, qty=qty)
                    holdings[ticker]["qty"]       = 0
                    holdings[ticker]["avg_price"] = 0
                    _mark_traded(ticker)
                elif pnl_pct >= 5:
                    half = max(1, qty // 2)
                    print(f"  [SELL] [{name}] 폴백 익절(5%) {pnl_pct:+.1f}% ({half}주 절반매도)")
                    sell_stock(token, ticker, qty=half)
                    holdings[ticker]["qty"] -= half
                    if holdings[ticker]["qty"] == 0:
                        holdings[ticker]["avg_price"] = 0
                    _mark_traded(ticker)
            return

        # ── 미보유: 매수 판단 (전날 종가 대비 하락률) ─────────────────────
        drop_pct = (prev_close - price) / prev_close * 100
        done     = fb_buy_done.get(ticker, set())

        with _trade_lock:
            if 10 not in done and drop_pct >= 10:
                print(f"  [BUY]  [{name}] 폴백 매수 -10% ({drop_pct:.1f}%, 3주)")
                buy_stock(token, ticker, qty=3)
                holdings[ticker]["qty"]       = (holdings[ticker]["qty"] or 0) + 3
                holdings[ticker]["avg_price"] = price
                fb_buy_done.setdefault(ticker, set()).add(10)
                fb_buy_done[ticker].add(7)
                fb_buy_done[ticker].add(5)
                _mark_traded(ticker)
            elif 7 not in done and drop_pct >= 7:
                print(f"  [BUY]  [{name}] 폴백 매수 -7% ({drop_pct:.1f}%, 2주)")
                buy_stock(token, ticker, qty=2)
                holdings[ticker]["qty"]       = (holdings[ticker]["qty"] or 0) + 2
                holdings[ticker]["avg_price"] = price
                fb_buy_done.setdefault(ticker, set()).add(7)
                fb_buy_done[ticker].add(5)
                _mark_traded(ticker)
            elif 5 not in done and drop_pct >= 5:
                print(f"  [BUY]  [{name}] 폴백 매수 -5% ({drop_pct:.1f}%, 1주)")
                buy_stock(token, ticker, qty=1)
                holdings[ticker]["qty"]       = (holdings[ticker]["qty"] or 0) + 1
                holdings[ticker]["avg_price"] = price
                fb_buy_done.setdefault(ticker, set()).add(5)
                _mark_traded(ticker)
    except Exception as e:
        print(f"  [{name}] 폴백 처리 오류: {e}")


# ── 메인 루프 ────────────────────────────────────────────────────────────────
RSI_WORKERS = 10

while True:
    now     = datetime.now()
    today   = now.strftime("%Y%m%d")
    weekday = now.weekday()

    is_trading_day  = weekday < 5
    is_trading_hour = is_trading_day and 9 <= now.hour < 15

    # ── 장 시작 처리 (당일 첫 1회) ──────────────────────────────────────────
    if is_trading_hour and market_open_done_date != today:

        print(f"\n[{now.strftime('%H:%M')}] ══ 장 시작 — "
              f"RSI {len(RSI_TICKERS)}종목 / VB {len(VB_TICKERS)}종목 / "
              f"폴백 {len(FALLBACK_TICKERS)}종목 ══")

        # ① RSI: 병렬 처리
        with ThreadPoolExecutor(max_workers=RSI_WORKERS) as pool:
            futures = {pool.submit(_process_rsi, t, n): (t, n)
                       for t, n in RSI_TICKERS.items()}
            for f in as_completed(futures):
                pass

        # ② VB: 시초가 매도 + 목표가 계산
        for ticker, name in VB_TICKERS.items():
            try:
                if holdings[ticker]["qty"] > 0 and _can_trade(ticker):
                    print(f"  [SELL] [{name}] VB 시초가 매도")
                    sell_stock(token, ticker, qty=holdings[ticker]["qty"])
                    holdings[ticker]["qty"]       = 0
                    holdings[ticker]["avg_price"] = 0
                    _mark_traded(ticker)
                    time.sleep(0.3)

                ohlcv      = get_recent_ohlcv(token, ticker)
                today_open = get_today_open(token, ticker)
                if ohlcv and today_open:
                    prev   = ohlcv[-1]
                    k      = VB_STRATEGIES[ticker].k
                    target = today_open + (prev["high"] - prev["low"]) * k
                    vb_cache[ticker]      = {
                        "target":    target,
                        "open":      today_open,
                        "prev_high": prev["high"],
                        "prev_low":  prev["low"],
                    }
                    vb_cache_date[ticker] = today
                    print(f"  [{name}] VB 목표가: {target:,.0f}원  "
                          f"(k={k}, 시가: {today_open:,})")
            except Exception as e:
                print(f"  [{name}] VB 초기화 오류: {e}")

        # ③ 폴백: 전날 종가 병렬 수집 + 당일 레벨 초기화
        _reset_fallback_daily()
        print(f"  폴백 {len(FALLBACK_TICKERS)}종목 전날 종가 수집 중...")
        with ThreadPoolExecutor(max_workers=RSI_WORKERS) as pool:
            futures = [pool.submit(_fetch_fb_prev_close, t) for t in FALLBACK_TICKERS]
            for f in as_completed(futures):
                pass
        print(f"  폴백 종가 수집 완료: {len(fb_prev_close)}종목")

        market_open_done_date = today
        print(f"[{now.strftime('%H:%M')}] ══ 장 시작 처리 완료 ══\n")

    # ── VB 장 중 모니터링 ────────────────────────────────────────────────────
    if is_trading_hour:
        for ticker, name in VB_TICKERS.items():
            if vb_cache_date.get(ticker) != today:
                continue
            if holdings[ticker]["qty"] > 0 or not _can_trade(ticker):
                continue
            try:
                price = get_price(token, ticker)
                if price is None:
                    continue
                cache  = vb_cache[ticker]
                signal = check_vb_signal(
                    ticker,
                    today_open    = cache["open"],
                    prev_high     = cache["prev_high"],
                    prev_low      = cache["prev_low"],
                    current_price = price,
                    holding       = False,
                )
                if signal == "BUY":
                    print(f"[{now.strftime('%H:%M')}] [BUY]  [{name}] VB 매수 (목표가 {cache['target']:,.0f}원 돌파)")
                    buy_stock(token, ticker, qty=1)
                    holdings[ticker]["qty"]       = 1
                    holdings[ticker]["avg_price"] = price
                    _mark_traded(ticker)
            except Exception as e:
                print(f"  [{name}] VB 모니터링 오류: {e}")
            time.sleep(0.3)

        # ── 폴백 종목 로테이션 체크 ─────────────────────────────────────────
        if _fb_list and fb_prev_close:
            # 보유 중인 폴백 종목은 매 사이클 항상 체크
            held_fb = [t for t in _fb_list if holdings[t]["qty"] > 0]
            for ticker in held_fb:
                _process_fallback(ticker, FALLBACK_TICKERS[ticker])

            # 미보유 종목은 FALLBACK_BATCH 단위로 순환
            batch = _fb_list[_fb_idx: _fb_idx + FALLBACK_BATCH]
            for ticker in batch:
                if holdings[ticker]["qty"] == 0:
                    _process_fallback(ticker, FALLBACK_TICKERS[ticker])
            _fb_idx = (_fb_idx + FALLBACK_BATCH) % len(_fb_list)

    time.sleep(10)
