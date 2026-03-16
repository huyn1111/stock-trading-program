"""
모멘텀 전략 백테스트 엔진.

- 지정 종목들의 20일 수익률을 계산해 랭킹
- 상위 top_n 종목 동일비중 매수
- 20일마다 리밸런싱: 탈락 종목 매도 → 신규 진입 종목 매수
- 데이터: 기존 KIS API (load_ohlcv)
"""

from backtest.data_loader import load_ohlcv

BUY_FEE  = 0.00015
SELL_FEE = 0.0023


def run(
    token:          str,
    tickers:        dict,          # {"종목코드": "종목명", ...}
    start:          str,
    end:            str,
    top_n:          int = 20,
    rebalance_days: int = 20,      # 리밸런싱 주기 (영업일)
    lookback_days:  int = 20,      # 모멘텀 계산 lookback (영업일)
    initial_cash:   int = 10_000_000,
    verbose:        bool = True,
) -> dict:
    """
    모멘텀 전략 백테스트 실행.

    Args:
        token:           KIS API 토큰
        tickers:         {"종목코드": "종목명"} 딕셔너리
        start/end:       백테스트 기간 "YYYYMMDD"
        top_n:           보유 종목 수
        rebalance_days:  리밸런싱 주기 (영업일)
        lookback_days:   모멘텀 계산 기준 과거 영업일 수
        initial_cash:    초기 자금
        verbose:         진행 상황 출력 여부

    Returns:
        trades, final_value, total_return, win_rate, mdd, trade_count, rebalance_count
    """

    # ── 전 종목 OHLCV 로드 ──────────────────────────────────────────────────
    if verbose:
        print(f"  데이터 로드 중...")
    data: dict[str, list[dict]] = {}
    for ticker, name in tickers.items():
        try:
            rows = load_ohlcv(token, ticker, start, end)
            data[ticker] = rows
            if verbose:
                print(f"    {name}: {len(rows)}일치")
        except Exception as e:
            if verbose:
                print(f"    {name}: 실패 ({e})")

    if not data:
        raise ValueError("로드된 데이터가 없습니다.")

    # ── 거래일 목록 (가장 많은 데이터를 가진 종목 기준) ─────────────────────
    base_ticker = max(data, key=lambda t: len(data[t]))
    all_dates   = [row["date"] for row in data[base_ticker]]

    # 종목별 종가를 날짜 → 가격 딕셔너리로 변환
    prices: dict[str, dict[str, float]] = {
        ticker: {row["date"]: float(row["close"]) for row in rows}
        for ticker, rows in data.items()
    }

    min_start = max(rebalance_days, lookback_days)
    if len(all_dates) < min_start + 1:
        raise ValueError("백테스트 기간이 너무 짧습니다.")

    # lookback 확보 후 rebalance_days 간격으로 리밸런싱
    rebalance_indices = list(range(min_start, len(all_dates), rebalance_days))
    if verbose:
        print(f"\n  총 {len(all_dates)}거래일 / lookback={lookback_days}일 / 리밸런싱 {len(rebalance_indices)}회 예정\n")

    cash      = float(initial_cash)
    portfolio: dict[str, dict] = {}   # {ticker: {"qty": int, "buy_price": float}}
    trades:    list[dict]      = []
    portfolio_values           = [float(initial_cash)]

    for idx, date_idx in enumerate(rebalance_indices):
        today_date = all_dates[date_idx]
        prev_date  = all_dates[date_idx - lookback_days]

        # ── 20일 수익률 계산 ──
        momentum: dict[str, float] = {}
        for ticker in data:
            p_now  = prices[ticker].get(today_date)
            p_prev = prices[ticker].get(prev_date)
            if p_now and p_prev and p_prev > 0:
                momentum[ticker] = (p_now - p_prev) / p_prev

        if not momentum:
            continue

        # 수익률 내림차순 정렬 → 상위 top_n
        ranked  = sorted(momentum, key=lambda t: momentum[t], reverse=True)
        target  = set(ranked[:top_n])
        current = set(portfolio.keys())

        sell_list = current - target
        buy_list  = target - current

        if verbose:
            print(f"  [{idx+1}/{len(rebalance_indices)}] {today_date}  "
                  f"매도 {len(sell_list)}종목 / 매수 {len(buy_list)}종목")
            print(f"    랭킹: " + " > ".join(
                f"{tickers.get(t, t)}({momentum[t]*100:+.1f}%)" for t in ranked
            ))

        # ── 매도 ──
        for ticker in sell_list:
            pos        = portfolio[ticker]
            sell_price = prices[ticker].get(today_date, pos["buy_price"])
            revenue    = sell_price * pos["qty"] * (1 - SELL_FEE)
            profit     = revenue - pos["buy_price"] * pos["qty"]
            cash      += revenue
            trades.append({
                "date":   today_date,
                "action": "SELL",
                "ticker": tickers.get(ticker, ticker),
                "price":  sell_price,
                "qty":    pos["qty"],
                "profit": round(profit),
            })
            del portfolio[ticker]

        # ── 매수 (동일비중) ──
        if buy_list:
            budget_per = cash / len(buy_list)
            for ticker in buy_list:
                buy_price = prices[ticker].get(today_date, 0)
                if buy_price <= 0:
                    continue
                qty = int(budget_per / (buy_price * (1 + BUY_FEE)))
                if qty <= 0:
                    continue
                cash -= buy_price * qty * (1 + BUY_FEE)
                portfolio[ticker] = {"qty": qty, "buy_price": buy_price}
                trades.append({
                    "date":   today_date,
                    "action": "BUY",
                    "ticker": tickers.get(ticker, ticker),
                    "price":  buy_price,
                    "qty":    qty,
                })

        # 포트폴리오 평가금액
        port_value = cash + sum(
            prices[t].get(today_date, pos["buy_price"]) * pos["qty"]
            for t, pos in portfolio.items()
        )
        portfolio_values.append(port_value)
        if verbose:
            print(f"    보유: {', '.join(tickers.get(t, t) for t in portfolio)} "
                  f"| 평가금액: {port_value:,.0f}원")

    # ── 기간 종료 강제 청산 ──────────────────────────────────────────────────
    if portfolio:
        last_date = all_dates[-1]
        for ticker, pos in portfolio.items():
            sell_price = prices[ticker].get(last_date, pos["buy_price"])
            revenue    = sell_price * pos["qty"] * (1 - SELL_FEE)
            profit     = revenue - pos["buy_price"] * pos["qty"]
            cash      += revenue
            trades.append({
                "date":   last_date,
                "action": "SELL",
                "ticker": tickers.get(ticker, ticker),
                "price":  sell_price,
                "qty":    pos["qty"],
                "profit": round(profit),
            })
        portfolio.clear()

    final_value  = cash
    total_return = (final_value - initial_cash) / initial_cash * 100

    sell_trades = [t for t in trades if t["action"] == "SELL"]
    win_count   = sum(1 for t in sell_trades if t.get("profit", 0) > 0)
    win_rate    = win_count / len(sell_trades) * 100 if sell_trades else 0
    mdd         = _calc_mdd(portfolio_values)

    return {
        "trades":          trades,
        "final_value":     round(final_value),
        "total_return":    round(total_return, 2),
        "win_rate":        round(win_rate, 1),
        "mdd":             round(mdd, 2),
        "trade_count":     len(sell_trades),
        "rebalance_count": len(rebalance_indices),
    }


def _calc_mdd(values: list[float]) -> float:
    peak = values[0]
    mdd  = 0.0
    for v in values:
        if v > peak:
            peak = v
        dd = (peak - v) / peak * 100
        if dd > mdd:
            mdd = dd
    return mdd
