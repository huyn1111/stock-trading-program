"""
RSI(7, 35/65) vs RSI(7, 40/60) 백테스트 비교.

사용 예시:
    python run_rsi_backtest.py                          # train/test 분리 (기본)
    python run_rsi_backtest.py --ticker 005930          # 삼성전자만
    python run_rsi_backtest.py --start 20240101 --end 20251231  # 단일 기간
"""

import argparse
from api import get_token
from backtest.data_loader import load_ohlcv
from backtest.rsi_engine import run
from strategies.rsi import RSIStrategy

TICKERS = {
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "079550": "LIG넥스원",
    "034020": "두산에너빌리티",
    "086520": "에코프로",
    "277810": "레인보우로보틱스",
}

STRATEGIES = [
    RSIStrategy(period=7, oversold=35, overbought=65),
    RSIStrategy(period=7, oversold=40, overbought=60),
]

W = 110


def parse_args():
    parser = argparse.ArgumentParser(description="RSI 전략 백테스트")
    parser.add_argument("--ticker",      nargs="+", default=list(TICKERS.keys()))
    parser.add_argument("--cash",        type=int,  default=10_000_000)
    parser.add_argument("--start",       default=None)
    parser.add_argument("--end",         default=None)
    parser.add_argument("--train-start", default="20220101")
    parser.add_argument("--train-end",   default="20231231")
    parser.add_argument("--test-start",  default="20240101")
    parser.add_argument("--test-end",    default="20251231")
    return parser.parse_args()


def _run_period(token, tickers, start, end, cash, label):
    results: dict[str, dict] = {}

    for ticker in tickers:
        name = TICKERS.get(ticker, ticker)
        print(f"  [{label}] {name} 데이터 로드 중... ({start}~{end})")
        try:
            data = load_ohlcv(token, ticker, start, end)
            print(f"    → {len(data)}일치")
        except Exception as e:
            print(f"    → 실패: {e}")
            continue

        results[name] = {}
        for strategy in STRATEGIES:
            results[name][strategy.name] = run(strategy, data, initial_cash=cash)

    return results


def _print_single(label, results):
    print(f"\n\n{'='*W}")
    print(f"  [RSI 백테스트 결과]  {label}")
    print(f"{'='*W}")
    print(
        f"  {'종목':<14}  {'전략':<22}"
        f"{'총수익률':>10}{'주간평균':>10}{'MDD':>9}{'승률':>7}{'매매횟수':>7}"
    )
    print(f"  {'-'*(W-2)}")

    for ticker_name, strat_results in results.items():
        best = max(strat_results, key=lambda k: strat_results[k]["total_return"])
        for sname, r in strat_results.items():
            mark = " ★" if sname == best else "  "
            print(
                f"  {ticker_name:<14}  {sname:<22}"
                f"{r['total_return']:>+9.2f}%"
                f"{r['weekly_return']:>+9.3f}%"
                f"{r['mdd']:>8.2f}%"
                f"{r['win_rate']:>6.1f}%"
                f"{r['trade_count']:>6}회"
                f"{mark}"
            )
        print(f"  {'-'*(W-2)}")

    print(f"{'='*W}")


def _print_train_test(train_results, test_results):
    W2 = 130
    print(f"\n\n{'='*W2}")
    print(f"  [RSI 전략 Train vs Test 비교]  Train: 2022~2023  /  Test: 2024~2025")
    print(f"{'='*W2}")
    print(
        f"  {'종목':<14}  {'전략':<22}"
        f"  {'[TRAIN] 총수익률':>13}{'주간평균':>10}{'MDD':>8}{'승률':>6}{'매매':>5}"
        f"  │"
        f"  {'[TEST] 총수익률':>13}{'주간평균':>10}{'MDD':>8}{'승률':>6}{'매매':>5}"
    )
    print(f"  {'-'*(W2-2)}")

    for ticker_name in train_results:
        tr = train_results[ticker_name]
        te = test_results.get(ticker_name, {})
        best_train = max(tr, key=lambda k: tr[k]["total_return"]) if tr else None
        best_test  = max(te, key=lambda k: te[k]["total_return"]) if te else None

        for sname in tr:
            r_tr = tr.get(sname)
            r_te = te.get(sname)
            train_mark = "★" if sname == best_train else " "
            test_mark  = "★" if sname == best_test  else " "

            tr_str = (
                f"  {r_tr['total_return']:>+12.2f}%"
                f"{r_tr['weekly_return']:>+9.3f}%"
                f"{r_tr['mdd']:>7.2f}%"
                f"{r_tr['win_rate']:>5.1f}%"
                f"{r_tr['trade_count']:>4}회 {train_mark}"
            ) if r_tr else f"  {'데이터 없음':>46}"

            te_str = (
                f"  {r_te['total_return']:>+12.2f}%"
                f"{r_te['weekly_return']:>+9.3f}%"
                f"{r_te['mdd']:>7.2f}%"
                f"{r_te['win_rate']:>5.1f}%"
                f"{r_te['trade_count']:>4}회 {test_mark}"
            ) if r_te else f"  {'데이터 없음':>46}"

            print(f"  {ticker_name:<14}  {sname:<22}{tr_str}  │{te_str}")

        print(f"  {'-'*(W2-2)}")

    print(f"{'='*W2}")


def main():
    args  = parse_args()
    token = get_token()

    if args.start and args.end:
        print(f"\n단일 기간 RSI 백테스트: {args.start} ~ {args.end}\n")
        results = _run_period(token, args.ticker, args.start, args.end, args.cash, "단일")
        _print_single(f"{args.start} ~ {args.end}", results)
        return

    print(f"\nTrain 기간 RSI 백테스트: {args.train_start} ~ {args.train_end}")
    train_results = _run_period(token, args.ticker, args.train_start, args.train_end, args.cash, "TRAIN")

    print(f"\nTest 기간 RSI 백테스트: {args.test_start} ~ {args.test_end}")
    test_results  = _run_period(token, args.ticker, args.test_start, args.test_end, args.cash, "TEST")

    _print_train_test(train_results, test_results)


if __name__ == "__main__":
    main()
