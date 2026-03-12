"""
백테스트 결과 출력 및 전략 비교.
"""

W = 70  # 표 전체 너비


def print_result(strategy_name: str, ticker: str, result: dict):
    """단일 전략 결과 출력"""

    print(f"\n{'='*52}")
    print(f"  전략: {strategy_name}  |  종목: {ticker}")
    print(f"{'='*52}")
    print(f"  최종 평가금액   : {result['final_value']:>15,}원")
    print(f"  총 수익률       : {result['total_return']:>+14.2f}%")
    print(f"  주간 평균수익률 : {result['weekly_return']:>+14.3f}%")
    print(f"  승률            : {result['win_rate']:>14.1f}%")
    print(f"  최대낙폭(MDD)   : {result['mdd']:>14.2f}%")
    print(f"  총 매매 횟수    : {result['trade_count']:>13}회")
    print(f"{'='*52}")

    print("\n  [매매 내역]")
    for t in result["trades"]:
        if t["action"] == "BUY":
            print(f"  {t['date']}  매수  {t['price']:>8,}원  {t['qty']}주")
        else:
            sign = "+" if t.get("profit", 0) >= 0 else ""
            print(f"  {t['date']}  매도  {t['price']:>8,}원  {t['qty']}주  ({sign}{t.get('profit', 0):,}원)")


def _header_line():
    return (
        f"  {'k값':<8}"
        f"{'주간평균수익률':>13}"
        f"{'총수익률':>10}"
        f"{'MDD':>9}"
        f"{'승률':>7}"
        f"{'매매횟수':>8}"
    )


def print_comparison(results: list[dict]):
    """
    종목별로 그룹핑하여 k값 비교 표 출력.
    results: [{"strategy": 전략명, "ticker": 종목명, "result": run() 반환값}, ...]
    """

    # 종목별로 그룹핑
    grouped: dict[str, list] = {}
    for item in results:
        grouped.setdefault(item["ticker"], []).append(item)

    print(f"\n\n{'='*W}")
    print(f"  [백테스트 결과 비교]  (변동성 돌파 전략, k값별)")
    print(f"{'='*W}")

    for ticker_name, items in grouped.items():
        print(f"\n  ■ {ticker_name}")
        print(f"  {'-'*(W-2)}")
        print(_header_line())
        print(f"  {'-'*(W-2)}")

        for item in sorted(items, key=lambda x: float(x["strategy"].split("=")[1].rstrip(")"))):
            r   = item["result"]
            k   = item["strategy"].split("=")[1].rstrip(")")
            best_mark = " ★" if r["total_return"] == max(i["result"]["total_return"] for i in items) else ""
            print(
                f"  k={k:<6}"
                f"{r['weekly_return']:>+12.3f}%"
                f"{r['total_return']:>+9.2f}%"
                f"{r['mdd']:>8.2f}%"
                f"{r['win_rate']:>6.1f}%"
                f"{r['trade_count']:>7}회"
                f"{best_mark}"
            )

        print(f"  {'-'*(W-2)}")

    print(f"\n{'='*W}")
