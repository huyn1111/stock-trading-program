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
from llm_check import llm_check as _llm_check_fn

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

# ── API rate limit 제어 ───────────────────────────────────────────────────────
# KIS 가상계좌 실제 한도 ~10건/초 → 동시 2건 + 0.3s 대기 = 최대 ~6건/초
_api_sem = threading.Semaphore(2)

def _api(fn, *args, retries: int = 3, **kwargs):
    """모든 API 호출을 이 함수로 감싸 rate limit 준수 + 자동 재시도."""
    for attempt in range(retries):
        with _api_sem:
            result = fn(*args, **kwargs)
            time.sleep(0.3)
        if result is not None and result != []:
            return result
        if attempt < retries - 1:
            time.sleep(1.0 * (attempt + 1))  # 1s, 2s 대기 후 재시도
    return result

# ── LLM 필터 (당일 종목당 1회 캐시) ─────────────────────────────────────────
_llm_cache_date: dict[str, str] = {}
_llm_cache_result: dict[str, bool] = {}

def _llm_check(ticker: str, name: str) -> bool:
    """뉴스 조회 → LLM 리스크 평가. True = 매수 허용, False = 매수 차단. 당일 1회만 호출."""
    today = datetime.now().strftime("%Y%m%d")
    if _llm_cache_date.get(ticker) == today:
        return _llm_cache_result[ticker]
    try:
        allowed = _llm_check_fn(ticker, name)
        _llm_cache_date[ticker]   = today
        _llm_cache_result[ticker] = allowed
        if not allowed:
            print(f"  [BLOCK] [{name}] LLM 매수 차단", flush=True)
        return allowed
    except Exception as e:
        print(f"  [{name}] LLM 필터 오류: {e} — 매수 허용", flush=True)
        return True

# ── 보유 현황 출력 함수 ───────────────────────────────────────────────────────
def print_holdings(label="보유 현황"):
    held = [(t, n) for t, n in ALL_TICKERS.items() if holdings[t]["qty"] > 0]
    print(f"\n── {label} ──")
    if not held:
        print("  보유 종목 없음")
        return
    for ticker, name in held:
        h     = holdings[ticker]
        price = _api(get_price, token, ticker)
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
HELP_TEXT = """자산현황 : 내 현재 보유 주식을 나타냅니다.
도움말   : 사용 가능한 명령어 목록을 표시합니다.
"""

def _cmd_listener():
    for line in sys.stdin:
        cmd = line.strip()
        if not cmd:
            continue
        if cmd == "자산현황":
            print_holdings("자산 현황")
            sys.stdout.flush()
        elif cmd == "도움말":
            print(HELP_TEXT, flush=True)
        else:
            print(f"  알 수 없는 명령어: '{cmd}'  (도움말 입력 시 명령어 목록 확인)", flush=True)

threading.Thread(target=_cmd_listener, daemon=True).start()

# ── 공통 상태 변수 ────────────────────────────────────────────────────────────
market_open_done_date = None
vb_cache:      dict[str, dict] = {}
vb_cache_date: dict[str, str]  = {}

TRADE_COOLDOWN = 300
last_trade_time: dict[str, float] = {}
_trade_lock = threading.Lock()

def _can_trade(ticker: str) -> bool:
    """매수 쿨다운 체크 (5분). 매도는 쿨다운 없음."""
    return time.time() - last_trade_time.get(ticker, 0) >= TRADE_COOLDOWN

def _mark_traded(ticker: str):
    last_trade_time[ticker] = time.time()

# ── RSI 장 중 실시간 상태 ────────────────────────────────────────────────────
rsi_ohlcv_cache: dict[str, list] = {}   # {ticker: ohlcv_rows} — 장 시작 시 캐시
_rsi_intra_list = list(RSI_TICKERS.keys())
_rsi_intra_idx  = 0
RSI_INTRA_BATCH = 30  # 10초 사이클당 체크 종목 수 (전체 순환 ~5분)

# ── 폴백 전략 상태 ────────────────────────────────────────────────────────────
# 전날 종가 캐시: {ticker: prev_close}
fb_prev_close: dict[str, float] = {}
# 당일 매수 레벨 실행 여부: {ticker: set()} — 완료된 레벨 저장
fb_buy_done: dict[str, set] = {}
# 폴백 모니터링 순서 (로테이션)
_fb_list = list(FALLBACK_TICKERS.keys())
_fb_idx  = 0
FALLBACK_BATCH = 50  # 10초 사이클당 체크할 폴백 종목 수

# ── 모멘텀 전략 상태 ──────────────────────────────────────────────────────────
MOMENTUM_TOP_N     = 10   # 보유 종목 수
MOMENTUM_LOOKBACK  = 20   # 수익률 계산 기준 영업일
MOMENTUM_REBALANCE = 40   # 리밸런싱 주기 (영업일)
MOMENTUM_STOPLOSS  = -15  # 손절 기준 수익률 (%)

momentum_portfolio: set[str] = set()         # 현재 보유 중인 모멘텀 종목
momentum_trading_days = MOMENTUM_REBALANCE   # 첫 실행 시 즉시 리밸런싱

def _reset_fallback_daily():
    """장 시작 시 당일 매수 레벨 초기화."""
    fb_buy_done.clear()

def _fetch_fb_prev_close(ticker: str):
    """폴백 종목의 전날 종가를 API로 조회."""
    try:
        rows = _api(get_recent_ohlcv, token, ticker)
        if rows:
            fb_prev_close[ticker] = rows[-1]["close"]
    except Exception:
        pass

def _process_rsi(ticker: str, name: str):
    """RSI 신호 판단 + 매매 (장 시작 1회, 스레드용). OHLCV도 캐시."""
    try:
        ohlcv = _api(get_recent_ohlcv, token, ticker)
        if ohlcv:
            rsi_ohlcv_cache[ticker] = ohlcv  # 장 중 실시간 체크용 캐시

        holding = holdings[ticker]["qty"] > 0
        signal  = check_rsi_signal(ticker, ohlcv, holding)

        with _trade_lock:
            if not _can_trade(ticker):
                return
            if signal == "BUY":
                cur = ohlcv[-1]["close"] if ohlcv else 0
                if not _llm_check(ticker, name):
                    return
                print(f"  [BUY]  [{name}] RSI 매수")
                buy_stock(token, ticker, qty=1, price=cur)
                holdings[ticker]["qty"] += 1
                _mark_traded(ticker)
            elif signal == "SELL":
                cur = ohlcv[-1]["close"] if ohlcv else 0
                print(f"  [SELL] [{name}] RSI 매도")
                sell_stock(token, ticker, qty=holdings[ticker]["qty"], price=cur)
                holdings[ticker]["qty"]       = 0
                holdings[ticker]["avg_price"] = 0
                _mark_traded(ticker)
    except Exception as e:
        print(f"  [{name}] RSI 처리 오류: {e}")


def _process_rsi_intraday(ticker: str, name: str):
    """장 중 현재가로 RSI 재계산 → 크로스오버 발생 시 매매."""
    base = rsi_ohlcv_cache.get(ticker)
    if not base:
        return
    try:
        price = _api(get_price, token, ticker)
        if not price:
            return

        # 현재가를 오늘 캔들로 추가해 실시간 RSI 계산
        today     = datetime.now().strftime("%Y%m%d")
        live_ohlcv = base + [{"date": today, "open": price, "high": price,
                               "low": price, "close": price}]
        holding = holdings[ticker]["qty"] > 0
        signal  = check_rsi_signal(ticker, live_ohlcv, holding)

        with _trade_lock:
            if not _can_trade(ticker):
                return
            if signal == "BUY":
                if not _llm_check(ticker, name):
                    return
                print(f"[{datetime.now().strftime('%H:%M')}] [BUY]  [{name}] RSI 장중 매수")
                buy_stock(token, ticker, qty=1, price=price)
                holdings[ticker]["qty"] += 1
                _mark_traded(ticker)
            elif signal == "SELL":
                print(f"[{datetime.now().strftime('%H:%M')}] [SELL] [{name}] RSI 장중 매도")
                sell_stock(token, ticker, qty=holdings[ticker]["qty"], price=price)
                holdings[ticker]["qty"]       = 0
                holdings[ticker]["avg_price"] = 0
                _mark_traded(ticker)
    except Exception as e:
        print(f"  [{name}] RSI 장중 처리 오류: {e}")

def _calc_momentum_returns(universe: dict) -> dict[str, float]:
    """유니버스 종목들의 lookback 기간 수익률 병렬 계산."""
    returns: dict[str, float] = {}

    def _fetch(ticker: str):
        rows = _api(get_recent_ohlcv, token, ticker, n=MOMENTUM_LOOKBACK + 5)
        if len(rows) >= MOMENTUM_LOOKBACK + 1:
            p_now  = rows[-1]["close"]
            p_prev = rows[-(MOMENTUM_LOOKBACK + 1)]["close"]
            if p_prev > 0:
                returns[ticker] = (p_now - p_prev) / p_prev

    with ThreadPoolExecutor(max_workers=RSI_WORKERS) as pool:
        futures = [pool.submit(_fetch, t) for t in universe]
        for f in as_completed(futures):
            pass
    return returns


def _run_momentum_rebalance():
    """모멘텀 리밸런싱: top-N 선정 → 탈락 종목 매도 → 신규 종목 매수."""
    global momentum_trading_days

    universe = FALLBACK_TICKERS
    if not universe:
        print("  [모멘텀] 유니버스 없음, 건너뜀")
        return

    print(f"\n  [모멘텀] 리밸런싱 시작 ({len(universe)}종목 수익률 계산 중...)")
    returns = _calc_momentum_returns(universe)

    if len(returns) < MOMENTUM_TOP_N:
        print(f"  [모멘텀] 데이터 부족 ({len(returns)}종목), 건너뜀")
        return

    ranked     = sorted(returns, key=lambda t: returns[t], reverse=True)
    target     = set(ranked[:MOMENTUM_TOP_N])
    current    = set(momentum_portfolio)
    sell_list  = current - target
    buy_list   = target - current

    top_str = ", ".join(
        f"{universe.get(t, t)}({returns[t]*100:+.1f}%)" for t in ranked[:MOMENTUM_TOP_N]
    )
    print(f"  [모멘텀] 상위 {MOMENTUM_TOP_N}: {top_str}")
    print(f"  [모멘텀] 매도 {len(sell_list)}종목 / 매수 {len(buy_list)}종목")

    # 탈락 종목 매도
    for ticker in sell_list:
        h    = holdings[ticker]
        qty  = h["qty"]
        name = universe.get(ticker, ticker)
        if qty > 0:
            with _trade_lock:
                if _can_trade(ticker):
                    cur = _api(get_price, token, ticker) or 0
                    print(f"  [SELL] [{name}] 모멘텀 리밸런싱 매도 ({qty}주)")
                    sell_stock(token, ticker, qty=qty, price=cur)
                    holdings[ticker]["qty"]       = 0
                    holdings[ticker]["avg_price"] = 0
                    _mark_traded(ticker)
        momentum_portfolio.discard(ticker)

    # 신규 종목 매수 (1주씩 동일비중)
    for ticker in buy_list:
        name  = universe.get(ticker, ticker)
        price = _api(get_price, token, ticker)
        if not price:
            continue
        with _trade_lock:
            if _can_trade(ticker) and holdings[ticker]["qty"] == 0:
                if not _llm_check(ticker, name):
                    continue
                print(f"  [BUY]  [{name}] 모멘텀 매수 1주")
                buy_stock(token, ticker, qty=1, price=price)
                holdings[ticker]["qty"]       = 1
                holdings[ticker]["avg_price"] = price
                _mark_traded(ticker)
                momentum_portfolio.add(ticker)

    momentum_trading_days = 0
    held_names = ", ".join(universe.get(t, t) for t in momentum_portfolio)
    print(f"  [모멘텀] 리밸런싱 완료. 보유: {held_names or '없음'}")


def _process_fallback(ticker: str, name: str):
    """폴백 종목 매수/매도 판단 + 실행."""
    prev_close = fb_prev_close.get(ticker)
    if not prev_close:
        return

    try:
        price = _api(get_price, token, ticker)
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
                    sell_stock(token, ticker, qty=qty, price=price)
                    holdings[ticker]["qty"]       = 0
                    holdings[ticker]["avg_price"] = 0
                elif pnl_pct >= 10:
                    print(f"  [SELL] [{name}] 폴백 익절(10%) {pnl_pct:+.1f}% ({qty}주 전량)")
                    sell_stock(token, ticker, qty=qty, price=price)
                    holdings[ticker]["qty"]       = 0
                    holdings[ticker]["avg_price"] = 0
                elif pnl_pct >= 5:
                    half = max(1, qty // 2)
                    print(f"  [SELL] [{name}] 폴백 익절(5%) {pnl_pct:+.1f}% ({half}주 절반매도)")
                    sell_stock(token, ticker, qty=half, price=price)
                    holdings[ticker]["qty"] -= half
                    if holdings[ticker]["qty"] == 0:
                        holdings[ticker]["avg_price"] = 0
            return

        # ── 미보유: 매수 판단 (전날 종가 대비 하락률) ─────────────────────
        drop_pct = (prev_close - price) / prev_close * 100
        done     = fb_buy_done.get(ticker, set())

        with _trade_lock:
            if 10 not in done and drop_pct >= 10:
                if not _llm_check(ticker, name):
                    return
                print(f"  [BUY]  [{name}] 폴백 매수 -10% ({drop_pct:.1f}%, 3주)")
                buy_stock(token, ticker, qty=3, price=price)
                holdings[ticker]["qty"]       = (holdings[ticker]["qty"] or 0) + 3
                holdings[ticker]["avg_price"] = price
                fb_buy_done.setdefault(ticker, set()).add(10)
                fb_buy_done[ticker].add(7)
                fb_buy_done[ticker].add(5)
                _mark_traded(ticker)
            elif 7 not in done and drop_pct >= 7:
                if not _llm_check(ticker, name):
                    return
                print(f"  [BUY]  [{name}] 폴백 매수 -7% ({drop_pct:.1f}%, 2주)")
                buy_stock(token, ticker, qty=2, price=price)
                holdings[ticker]["qty"]       = (holdings[ticker]["qty"] or 0) + 2
                holdings[ticker]["avg_price"] = price
                fb_buy_done.setdefault(ticker, set()).add(7)
                fb_buy_done[ticker].add(5)
                _mark_traded(ticker)
            elif 5 not in done and drop_pct >= 5:
                if not _llm_check(ticker, name):
                    return
                print(f"  [BUY]  [{name}] 폴백 매수 -5% ({drop_pct:.1f}%, 1주)")
                buy_stock(token, ticker, qty=1, price=price)
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
                    open_price = _api(get_today_open, token, ticker) or 0
                    print(f"  [SELL] [{name}] VB 시초가 매도")
                    sell_stock(token, ticker, qty=holdings[ticker]["qty"], price=open_price)
                    holdings[ticker]["qty"]       = 0
                    holdings[ticker]["avg_price"] = 0
                    _mark_traded(ticker)
                    time.sleep(0.3)

                ohlcv      = _api(get_recent_ohlcv, token, ticker)
                today_open = _api(get_today_open, token, ticker)
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

        # ④ 모멘텀: 거래일 카운트 + 40일마다 리밸런싱
        momentum_trading_days += 1
        print(f"  모멘텀 거래일 카운트: {momentum_trading_days}/{MOMENTUM_REBALANCE}")
        if momentum_trading_days >= MOMENTUM_REBALANCE:
            _run_momentum_rebalance()

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
                price = _api(get_price, token, ticker)
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
                    if not _llm_check(ticker, name):
                        continue
                    print(f"[{now.strftime('%H:%M')}] [BUY]  [{name}] VB 매수 (목표가 {cache['target']:,.0f}원 돌파)")
                    buy_stock(token, ticker, qty=1, price=price)
                    holdings[ticker]["qty"]       = 1
                    holdings[ticker]["avg_price"] = price
                    _mark_traded(ticker)
            except Exception as e:
                print(f"  [{name}] VB 모니터링 오류: {e}")
            time.sleep(0.3)

        # ── 모멘텀 종목 손절 체크 ───────────────────────────────────────────
        for ticker in list(momentum_portfolio):
            h = holdings[ticker]
            if h["qty"] > 0 and h["avg_price"] > 0:
                price = _api(get_price, token, ticker)
                if price:
                    pnl = (price - h["avg_price"]) / h["avg_price"] * 100
                    if pnl <= MOMENTUM_STOPLOSS:
                        name = FALLBACK_TICKERS.get(ticker, ticker)
                        with _trade_lock:
                            if _can_trade(ticker):
                                print(f"  [SELL] [{name}] 모멘텀 손절 {pnl:+.1f}% ({h['qty']}주)")
                                sell_stock(token, ticker, qty=h["qty"], price=price)
                                holdings[ticker]["qty"]       = 0
                                holdings[ticker]["avg_price"] = 0
                                momentum_portfolio.discard(ticker)
                                _mark_traded(ticker)

        # ── RSI 장 중 실시간 체크 (배치 순환) ──────────────────────────────
        if _rsi_intra_list and rsi_ohlcv_cache:
            batch = _rsi_intra_list[_rsi_intra_idx: _rsi_intra_idx + RSI_INTRA_BATCH]
            for ticker in batch:
                _process_rsi_intraday(ticker, RSI_TICKERS[ticker])
            _rsi_intra_idx = (_rsi_intra_idx + RSI_INTRA_BATCH) % len(_rsi_intra_list)

        # ── 폴백 종목 로테이션 체크 ─────────────────────────────────────────
        if _fb_list and fb_prev_close:
            # 보유 중인 폴백 종목은 매 사이클 항상 체크 (모멘텀 종목 제외)
            held_fb = [t for t in _fb_list
                       if holdings[t]["qty"] > 0 and t not in momentum_portfolio]
            for ticker in held_fb:
                _process_fallback(ticker, FALLBACK_TICKERS[ticker])

            # 미보유 종목은 FALLBACK_BATCH 단위로 순환 (모멘텀 종목 제외)
            batch = _fb_list[_fb_idx: _fb_idx + FALLBACK_BATCH]
            for ticker in batch:
                if holdings[ticker]["qty"] == 0 and ticker not in momentum_portfolio:
                    _process_fallback(ticker, FALLBACK_TICKERS[ticker])
            _fb_idx = (_fb_idx + FALLBACK_BATCH) % len(_fb_list)

    time.sleep(10)
