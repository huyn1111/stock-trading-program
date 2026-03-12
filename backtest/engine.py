"""
백테스트 엔진.
전략과 OHLCV 데이터를 받아 매매 시뮬레이션을 수행.
"""

from strategies.base import BaseStrategy

BUY_FEE  = 0.00015   # 매수 수수료 0.015%
SELL_FEE = 0.0023    # 매도 수수료 + 세금 0.23%


def run(strategy: BaseStrategy, data: list[dict], initial_cash: int = 10_000_000) -> dict:
    """
    백테스트 실행.

    매매 규칙:
    - BUY  신호: 목표가(당일 시가 + 변동폭*k)에 매수 → 다음날 시가에 매도
    - 1회에 보유 현금의 100% 투입 (1종목 집중)

    Returns:
        {
          "trades":        매매 내역 리스트,
          "final_value":   최종 평가금액,
          "total_return":  수익률(%),
          "win_rate":      승률(%),
          "mdd":           최대낙폭(%),
        }
    """

    cash = initial_cash
    holding = False
    buy_price = 0
    buy_qty = 0

    trades = []
    portfolio_values = [initial_cash]

    for i in range(1, len(data)):
        today = data[i]
        prev  = data[i - 1]

        signal = strategy.generate_signal(today, prev)

        if signal == "BUY" and not holding:
            target = today["open"] + (prev["high"] - prev["low"])

            # 목표가가 당일 범위 안에 있을 때만 체결
            buy_price = max(target, today["open"])
            buy_qty = int(cash / (buy_price * (1 + BUY_FEE)))

            if buy_qty > 0:
                cost = buy_price * buy_qty * (1 + BUY_FEE)
                cash -= cost
                holding = True
                trades.append({
                    "date": today["date"],
                    "action": "BUY",
                    "price": buy_price,
                    "qty": buy_qty
                })

        elif holding:
            # 다음날 시가에 매도
            if i + 1 < len(data):
                sell_price = data[i + 1]["open"]
            else:
                sell_price = today["close"]

            revenue = sell_price * buy_qty * (1 - SELL_FEE)
            profit  = revenue - (buy_price * buy_qty)
            cash += revenue
            holding = False

            trades.append({
                "date":   data[i + 1]["date"] if i + 1 < len(data) else today["date"],
                "action": "SELL",
                "price":  sell_price,
                "qty":    buy_qty,
                "profit": round(profit)
            })

        # 당일 포트폴리오 평가금액
        if holding:
            portfolio_values.append(cash + today["close"] * buy_qty)
        else:
            portfolio_values.append(cash)

    # 보유 중 강제 청산
    if holding:
        sell_price = data[-1]["close"]
        revenue = sell_price * buy_qty * (1 - SELL_FEE)
        profit  = revenue - (buy_price * buy_qty)
        cash += revenue
        trades.append({
            "date":   data[-1]["date"],
            "action": "SELL",
            "price":  sell_price,
            "qty":    buy_qty,
            "profit": round(profit)
        })

    final_value  = cash
    total_return = (final_value - initial_cash) / initial_cash * 100

    sell_trades = [t for t in trades if t["action"] == "SELL"]
    win_count   = sum(1 for t in sell_trades if t.get("profit", 0) > 0)
    win_rate    = win_count / len(sell_trades) * 100 if sell_trades else 0

    mdd = _calc_mdd(portfolio_values)

    # 주간평균수익률: (1 + 총수익률)^(1/총주수) - 1
    weeks = len(data) / 5
    weekly_return = ((1 + total_return / 100) ** (1 / weeks) - 1) * 100 if weeks > 0 else 0

    return {
        "trades":         trades,
        "final_value":    round(final_value),
        "total_return":   round(total_return, 2),
        "weekly_return":  round(weekly_return, 3),
        "win_rate":       round(win_rate, 1),
        "mdd":            round(mdd, 2),
        "trade_count":    len(sell_trades)
    }


def _calc_mdd(values: list[float]) -> float:
    """최대낙폭(MDD) 계산"""
    peak = values[0]
    mdd  = 0.0
    for v in values:
        if v > peak:
            peak = v
        dd = (peak - v) / peak * 100
        if dd > mdd:
            mdd = dd
    return mdd
