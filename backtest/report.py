"""
백테스트 결과 출력 및 전략 비교.
"""


def print_result(strategy_name: str, ticker: str, result: dict):
    """단일 전략 결과 출력"""

    print(f"\n{'='*50}")
    print(f"  전략: {strategy_name}  |  종목: {ticker}")
    print(f"{'='*50}")
    print(f"  최종 평가금액 : {result['final_value']:>15,}원")
    print(f"  총 수익률     : {result['total_return']:>+14.2f}%")
    print(f"  승률          : {result['win_rate']:>14.1f}%")
    print(f"  최대낙폭(MDD) : {result['mdd']:>14.2f}%")
    print(f"  총 매매 횟수  : {len([t for t in result['trades'] if t['action']=='SELL']):>14}회")
    print(f"{'='*50}")

    print("\n  [매매 내역]")
    for t in result["trades"]:
        if t["action"] == "BUY":
            print(f"  {t['date']}  매수  {t['price']:>8,}원  {t['qty']}주")
        else:
            sign = "+" if t.get("profit", 0) >= 0 else ""
            print(f"  {t['date']}  매도  {t['price']:>8,}원  {t['qty']}주  ({sign}{t.get('profit', 0):,}원)")


def print_comparison(results: list[dict]):
    """
    여러 전략 비교 출력.
    results: [{"strategy": 전략명, "ticker": 종목, "result": run() 반환값}, ...]
    """

    print(f"\n{'='*65}")
    print(f"  {'전략':<20} {'종목':<10} {'수익률':>8} {'승률':>7} {'MDD':>8} {'횟수':>5}")
    print(f"{'-'*65}")

    for item in sorted(results, key=lambda x: x["result"]["total_return"], reverse=True):
        r = item["result"]
        print(
            f"  {item['strategy']:<20} {item['ticker']:<10} "
            f"{r['total_return']:>+7.2f}% {r['win_rate']:>6.1f}% "
            f"{r['mdd']:>7.2f}% {len([t for t in r['trades'] if t['action']=='SELL']):>5}회"
        )

    print(f"{'='*65}")
