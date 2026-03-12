"""
백테스트 실행 진입점.

사용 예시:
    python run_backtest.py                          # 기본 (6종목, k=0.5, 2024~2025)
    python run_backtest.py --ticker 005930          # 삼성전자만
    python run_backtest.py --start 20240101 --end 20241231
    python run_backtest.py --k 0.3 0.5 0.7         # k값 비교
"""

import argparse
from api import get_token
from backtest.data_loader import load_ohlcv
from backtest.engine import run
from backtest.report import print_comparison
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
    parser.add_argument("--ticker",  nargs="+", default=list(TICKERS.keys()), help="종목코드")
    parser.add_argument("--start",   default="20240101", help="시작일 YYYYMMDD")
    parser.add_argument("--end",     default="20251231", help="종료일 YYYYMMDD")
    parser.add_argument("--k",       nargs="+", type=float,
                        default=[round(x * 0.1, 1) for x in range(1, 10)],
                        help="변동성 돌파 k값 (기본: 0.1~0.9)")
    parser.add_argument("--cash",    type=int,  default=10_000_000, help="초기 자금")
    return parser.parse_args()


def main():
    args = parse_args()
    token = get_token()

    comparison = []

    for ticker in args.ticker:
        name = TICKERS.get(ticker, ticker)
        print(f"\n[데이터 로드] {name} ({ticker}) {args.start} ~ {args.end}")

        try:
            data = load_ohlcv(token, ticker, args.start, args.end)
            print(f"  → {len(data)}일치 데이터 로드 완료")
        except Exception as e:
            print(f"  → 실패: {e}")
            continue

        for k in args.k:
            strategy = VolatilityBreakoutStrategy(k=k)
            result   = run(strategy, data, initial_cash=args.cash)

            comparison.append({
                "strategy": strategy.name,
                "ticker":   name,
                "result":   result
            })

    if len(comparison) > 1:
        print("\n\n[전략 비교 요약]")
        print_comparison(comparison)


if __name__ == "__main__":
    main()
