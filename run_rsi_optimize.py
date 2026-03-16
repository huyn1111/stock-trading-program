"""
RSI 파라미터 최적화 (그리드 서치).

p=7 고정, oversold 30~40, overbought 60~70 범위에서 전수 탐색.
→ 11 × 11 = 121개 조합

사용 예시:
    python run_rsi_optimize.py                          # train/test 분리 (기본)
    python run_rsi_optimize.py --start 20220101 --end 20251231
    python run_rsi_optimize.py --ticker 005930 000660   # 특정 종목만
    python run_rsi_optimize.py --top 10                 # 상위 10개 출력 (기본 5)
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

PERIOD    = 7
OS_RANGE  = range(30, 41)   # oversold  30~40
OB_RANGE  = range(60, 71)   # overbought 60~70
W = 95


def parse_args():
    parser = argparse.ArgumentParser(description="RSI 파라미터 최적화")
    parser.add_argument("--ticker",      nargs="+", default=list(TICKERS.keys()))
    parser.add_argument("--cash",        type=int,  default=10_000_000)
    parser.add_argument("--top",         type=int,  default=5, help="종목별 상위 N개 출력")
    parser.add_argument("--start",       default=None)
    parser.add_argument("--end",         default=None)
    parser.add_argument("--train-start", default="20220101")
    parser.add_argument("--train-end",   default="20231231")
    parser.add_argument("--test-start",  default="20240101")
    parser.add_argument("--test-end",    default="20251231")
    return parser.parse_args()


def _search(data_map, cash, label):
    """
    data_map: {ticker_name: ohlcv_list}
    121개 조합 × 종목 수 만큼 백테스트 실행.
    반환: {ticker_name: [{strategy, result}, ...]} (total_return 내림차순 정렬)
    """
    total_combos = len(OS_RANGE) * len(OB_RANGE)
    print(f"\n  [{label}] {total_combos}개 조합 탐색 중...")

    all_results: dict[str, list] = {}

    for ticker_name, data in data_map.items():
        ticker_results = []
        for os_ in OS_RANGE:
            for ob in OB_RANGE:
                strategy = RSIStrategy(period=PERIOD, oversold=os_, overbought=ob)
                result   = run(strategy, data, initial_cash=cash)
                ticker_results.append({
                    "oversold":   os_,
                    "overbought": ob,
                    "strategy":   strategy.name,
                    "result":     result,
                })

        # total_return 기준 내림차순 정렬
        ticker_results.sort(key=lambda x: x["result"]["total_return"], reverse=True)
        all_results[ticker_name] = ticker_results
        print(f"    {ticker_name} 완료 — 최적: oversold={ticker_results[0]['oversold']}, overbought={ticker_results[0]['overbought']} ({ticker_results[0]['result']['total_return']:+.2f}%)")

    return all_results


def _print_top(label, all_results, top_n):
    print(f"\n\n{'='*W}")
    print(f"  [RSI 최적화 결과 Top {top_n}]  {label}  (p={PERIOD}, oversold 30~40 / overbought 60~70)")
    print(f"{'='*W}")

    for ticker_name, items in all_results.items():
        print(f"\n  ■ {ticker_name}")
        print(f"  {'-'*(W-2)}")
        print(
            f"  {'전략':<24}"
            f"{'총수익률':>10}"
            f"{'주간평균':>10}"
            f"{'MDD':>9}"
            f"{'승률':>7}"
            f"{'매매횟수':>7}"
        )
        print(f"  {'-'*(W-2)}")

        for item in items[:top_n]:
            r = item["result"]
            mark = " ★" if item == items[0] else "  "
            print(
                f"  {item['strategy']:<24}"
                f"{r['total_return']:>+9.2f}%"
                f"{r['weekly_return']:>+9.3f}%"
                f"{r['mdd']:>8.2f}%"
                f"{r['win_rate']:>6.1f}%"
                f"{r['trade_count']:>6}회"
                f"{mark}"
            )

        print(f"  {'-'*(W-2)}")

    print(f"\n{'='*W}")


def _print_train_test_best(train_results, test_results, top_n):
    """Train 최적 파라미터가 Test에서도 유효한지 검증."""
    W2 = 110
    print(f"\n\n{'='*W2}")
    print(f"  [Train 최적 파라미터 → Test 검증]  (p={PERIOD})")
    print(f"{'='*W2}")
    print(
        f"  {'종목':<14}"
        f"  {'Train 최적':<24}{'총수익률':>10}{'MDD':>8}"
        f"  │"
        f"  {'Test 동일 파라미터':<24}{'총수익률':>10}{'MDD':>8}"
        f"  일치여부"
    )
    print(f"  {'-'*(W2-2)}")

    for ticker_name in train_results:
        train_items = train_results[ticker_name]
        test_items  = test_results.get(ticker_name, [])

        best_train = train_items[0] if train_items else None
        best_test  = test_items[0]  if test_items  else None

        if not best_train:
            continue

        # Test 결과에서 Train 최적과 동일한 파라미터 찾기
        same_param_test = next(
            (x for x in test_items
             if x["oversold"] == best_train["oversold"] and x["overbought"] == best_train["overbought"]),
            None
        )

        tr = best_train["result"]
        tr_str = f"{tr['total_return']:>+9.2f}%  {tr['mdd']:>6.2f}%"

        if same_param_test:
            te = same_param_test["result"]
            te_str  = f"{te['total_return']:>+9.2f}%  {te['mdd']:>6.2f}%"
            # Test에서도 상위권인지 확인 (top_n 이내)
            test_rank = next((i+1 for i, x in enumerate(test_items) if x["oversold"] == best_train["oversold"] and x["overbought"] == best_train["overbought"]), None)
            rank_str = f"Test {test_rank}위/{len(test_items)}" if test_rank else "?"
            consistent = "✓" if test_rank and test_rank <= top_n else "△"
        else:
            te_str   = "데이터 없음"
            rank_str = "-"
            consistent = "?"

        print(
            f"  {ticker_name:<14}"
            f"  {best_train['strategy']:<24}{tr_str}"
            f"  │"
            f"  {best_train['strategy']:<24}{te_str}"
            f"  {consistent} ({rank_str})"
        )

    print(f"  {'-'*(W2-2)}")
    print(f"  ✓ = Test에서도 상위 {top_n}위 이내  /  △ = Test에서 상위권 밖")
    print(f"{'='*W2}")


def main():
    args  = parse_args()
    token = get_token()

    def load_data(tickers, start, end, label):
        data_map = {}
        for ticker in tickers:
            name = TICKERS.get(ticker, ticker)
            print(f"  [{label}] {name} 로드 중... ({start}~{end})")
            try:
                data = load_ohlcv(token, ticker, start, end)
                data_map[name] = data
                print(f"    → {len(data)}일치")
            except Exception as e:
                print(f"    → 실패: {e}")
        return data_map

    # 단일 기간 모드
    if args.start and args.end:
        print(f"\n단일 기간 RSI 최적화: {args.start} ~ {args.end}")
        data_map = load_data(args.ticker, args.start, args.end, "단일")
        results  = _search(data_map, args.cash, "단일")
        _print_top(f"{args.start} ~ {args.end}", results, args.top)
        return

    # Train / Test 분리 모드
    print(f"\nTrain 데이터 로드: {args.train_start} ~ {args.train_end}")
    train_data = load_data(args.ticker, args.train_start, args.train_end, "TRAIN")
    train_results = _search(train_data, args.cash, "TRAIN")
    _print_top(f"Train ({args.train_start}~{args.train_end})", train_results, args.top)

    print(f"\nTest 데이터 로드: {args.test_start} ~ {args.test_end}")
    test_data = load_data(args.ticker, args.test_start, args.test_end, "TEST")
    test_results = _search(test_data, args.cash, "TEST")
    _print_top(f"Test ({args.test_start}~{args.test_end})", test_results, args.top)

    _print_train_test_best(train_results, test_results, args.top)


if __name__ == "__main__":
    main()
