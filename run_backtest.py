"""
백테스트 실행 진입점.

사용 예시:
    python run_backtest.py                          # train/test 분리 (기본)
    python run_backtest.py --ticker 005930          # 삼성전자만
    python run_backtest.py --k 0.3 0.5 0.7         # k값 지정
    python run_backtest.py --start 20240101 --end 20251231  # 단일 기간
"""

import argparse
from api import get_token
from backtest.data_loader import load_ohlcv
from backtest.engine import run
from backtest.report import print_comparison, print_train_test_comparison
from strategies.volatility_breakout import VolatilityBreakoutStrategy

TICKERS = {
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "079550": "LIG넥스원",
    "034020": "두산에너빌리티",
    "086520": "에코프로",
    "277810": "레인보우로보틱스",
}


def parse_args():
    parser = argparse.ArgumentParser(description="백테스트 실행")
    parser.add_argument("--ticker",      nargs="+", default=list(TICKERS.keys()), help="종목코드")
    parser.add_argument("--k",           nargs="+", type=float,
                        default=[round(x * 0.1, 1) for x in range(1, 10)],
                        help="변동성 돌파 k값 (기본: 0.1~0.9)")
    parser.add_argument("--cash",        type=int, default=10_000_000, help="초기 자금")
    # 단일 기간 모드
    parser.add_argument("--start",       default=None, help="단일 기간 시작일 YYYYMMDD")
    parser.add_argument("--end",         default=None, help="단일 기간 종료일 YYYYMMDD")
    # train/test 분리 모드 (기본)
    parser.add_argument("--train-start", default="20220101", help="Train 시작일")
    parser.add_argument("--train-end",   default="20231231", help="Train 종료일")
    parser.add_argument("--test-start",  default="20240101", help="Test 시작일")
    parser.add_argument("--test-end",    default="20251231", help="Test 종료일")
    return parser.parse_args()


def _run_period(token, tickers, k_list, start, end, cash, label):
    """지정 기간 백테스트 실행 후 결과 리스트 반환"""
    results = []
    for ticker in tickers:
        name = TICKERS.get(ticker, ticker)
        print(f"  [{label}] {name} 데이터 로드 중... ({start}~{end})")
        try:
            data = load_ohlcv(token, ticker, start, end)
            print(f"    → {len(data)}일치")
        except Exception as e:
            print(f"    → 실패: {e}")
            continue

        for k in k_list:
            strategy = VolatilityBreakoutStrategy(k=k)
            result   = run(strategy, data, initial_cash=cash)
            results.append({"strategy": strategy.name, "ticker": name, "result": result})

    return results


def main():
    args  = parse_args()
    token = get_token()

    # 단일 기간 모드
    if args.start and args.end:
        print(f"\n단일 기간 백테스트: {args.start} ~ {args.end}\n")
        results = _run_period(token, args.ticker, args.k, args.start, args.end, args.cash, "단일")
        print_comparison(results)
        return

    # Train / Test 분리 모드 (기본)
    print(f"\nTrain 기간 백테스트: {args.train_start} ~ {args.train_end}")
    train_results = _run_period(token, args.ticker, args.k, args.train_start, args.train_end, args.cash, "TRAIN")

    print(f"\nTest 기간 백테스트: {args.test_start} ~ {args.test_end}")
    test_results  = _run_period(token, args.ticker, args.k, args.test_start,  args.test_end,  args.cash, "TEST")

    print_train_test_comparison(train_results, test_results)


if __name__ == "__main__":
    main()
