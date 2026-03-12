"""
백테스트 결과 출력 및 전략 비교.
"""


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


def print_comparison(results: list[dict]):
    """
    여러 전략/종목 비교 결과를 표로 출력.
    results: [{"strategy": 전략명, "ticker": 종목명, "result": run() 반환값}, ...]
    """

    col = {
        "종목":         12,
        "전략":         16,
        "주간평균수익률": 13,
        "총수익률":      10,
        "MDD":          9,
        "승률":         7,
        "매매횟수":      7,
    }

    header = (
        f"  {'종목':<{col['종목']}}"
        f"{'전략':<{col['전략']}}"
        f"{'주간평균수익률':>{col['주간평균수익률']}}"
        f"{'총수익률':>{col['총수익률']}}"
        f"{'MDD':>{col['MDD']}}"
        f"{'승률':>{col['승률']}}"
        f"{'매매횟수':>{col['매매횟수']}}"
    )
    divider = "=" * len(header)

    print(f"\n\n{divider}")
    print(f"  [백테스트 결과 비교]")
    print(divider)
    print(header)
    print("-" * len(header))

    for item in sorted(results, key=lambda x: x["result"]["total_return"], reverse=True):
        r = item["result"]
        print(
            f"  {item['ticker']:<{col['종목']}}"
            f"{item['strategy']:<{col['전략']}}"
            f"{r['weekly_return']:>+{col['주간평균수익률']}.3f}%"
            f"{r['total_return']:>+{col['총수익률']}.2f}%"
            f"{r['mdd']:>{col['MDD']}.2f}%"
            f"{r['win_rate']:>{col['승률']}.1f}%"
            f"{r['trade_count']:>{col['매매횟수']}}회"
        )

    print(divider)
