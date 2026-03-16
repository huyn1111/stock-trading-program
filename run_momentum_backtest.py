"""
모멘텀 전략 백테스트 실행 진입점.

전략:
  - 6개 종목의 20일 수익률 랭킹
  - 상위 3종목 동일비중 매수
  - 20일마다 리밸런싱

사용 예시:
    python run_momentum_backtest.py                         # train/test 분리 (기본)
    python run_momentum_backtest.py --start 20240101 --end 20251231
"""

import argparse
from api import get_token
from backtest.momentum_engine import run

TICKERS = {
    # ── 반도체 / IT ─────────────────────────────────────────────────────────
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "009150": "삼성전기",
    "066570": "LG전자",
    "000990": "DB하이텍",
    "108320": "LX세미콘",
    "042700": "한미반도체",
    "240810": "원익IPS",
    "058470": "리노공업",
    "095610": "테스",
    # ── 2차전지 ──────────────────────────────────────────────────────────────
    "373220": "LG에너지솔루션",
    "006400": "삼성SDI",
    "051910": "LG화학",
    "003670": "포스코퓨처엠",
    "086520": "에코프로",
    "247540": "에코프로비엠",
    "066970": "엘앤에프",
    "278280": "천보",
    "005070": "코스모신소재",
    "121600": "나노신소재",
    # ── 자동차 / 부품 ────────────────────────────────────────────────────────
    "005380": "현대차",
    "000270": "기아",
    "012330": "현대모비스",
    "011210": "현대위아",
    "204320": "HL만도",
    "018880": "한온시스템",
    "005850": "에스엘",
    "307950": "현대오토에버",
    "086280": "현대글로비스",
    "010690": "화신",
    # ── 방산 / 로봇 ──────────────────────────────────────────────────────────
    "012450": "한화에어로스페이스",
    "079550": "LIG넥스원",
    "047810": "한국항공우주",
    "064350": "현대로템",
    "277810": "레인보우로보틱스",
    "454910": "두산로보틱스",
    "034020": "두산에너빌리티",
    "272210": "한화시스템",
    "003570": "SNT다이내믹스",
    "010820": "퍼스텍",
    # ── 인터넷 / 플랫폼 ──────────────────────────────────────────────────────
    "035420": "NAVER",
    "035720": "카카오",
    "293490": "카카오게임즈",
    "377300": "카카오페이",
    "323410": "카카오뱅크",
    "067160": "SOOP",
    "192080": "더블유게임즈",
    "078340": "컴투스",
    "063080": "컴투스홀딩스",
    "112040": "위메이드",
    # ── 바이오 ───────────────────────────────────────────────────────────────
    "207940": "삼성바이오로직스",
    "068270": "셀트리온",
    "091990": "셀트리온헬스케어",
    "068760": "셀트리온제약",
    "326030": "SK바이오팜",
    "302440": "SK바이오사이언스",
    "128940": "한미약품",
    "000100": "유한양행",
    "196170": "알테오젠",
    "028300": "HLB",
    # ── 철강 / 소재 ──────────────────────────────────────────────────────────
    "005490": "POSCO홀딩스",
    "047050": "포스코인터내셔널",
    "004020": "현대제철",
    "010130": "고려아연",
    "103140": "풍산",
    "001230": "동국제강",
    "058650": "세아베스틸지주",
    "010060": "OCI",
    "011170": "롯데케미칼",
    "011780": "금호석유",
    # ── 금융 ────────────────────────────────────────────────────────────────
    "105560": "KB금융",
    "055550": "신한지주",
    "086790": "하나금융지주",
    "316140": "우리금융지주",
    "024110": "기업은행",
    "016360": "삼성증권",
    "006800": "미래에셋증권",
    "071050": "한국금융지주",
    "138040": "메리츠금융지주",
    "039490": "키움증권",
    # ── 소비재 / 유통 ────────────────────────────────────────────────────────
    "090430": "아모레퍼시픽",
    "051900": "LG생활건강",
    "008770": "호텔신라",
    "001040": "CJ",
    "097950": "CJ제일제당",
    "139480": "이마트",
    "023530": "롯데쇼핑",
    "282330": "BGF리테일",
    "007070": "GS리테일",
    "004370": "농심",
    # ── 기타 대형주 ──────────────────────────────────────────────────────────
    "003490": "대한항공",
    "011200": "HMM",
    "030200": "KT",
    "017670": "SK텔레콤",
    "003550": "LG",
    "034730": "SK",
    "000880": "한화",
    "078930": "GS",
    "000150": "두산",
    "006260": "LS",
}

LOOKBACKS  = [20]               # lookback 고정 (영업일)
REBALANCES = [40]               # 리밸런싱 주기 고정
TOP_N      = 10                  # 보유 종목 수 고정
W2 = 120


def parse_args():
    parser = argparse.ArgumentParser(description="모멘텀 전략 백테스트")
    parser.add_argument("--cash",        type=int, default=10_000_000, help="초기 자금")
    parser.add_argument("--start",       default=None,       help="단일 기간 시작일 YYYYMMDD")
    parser.add_argument("--end",         default=None,       help="단일 기간 종료일 YYYYMMDD")
    parser.add_argument("--train-start", default="20190101")
    parser.add_argument("--train-end",   default="20221231")
    parser.add_argument("--test-start",  default="20230101")
    parser.add_argument("--test-end",    default="20251231")
    return parser.parse_args()


def _row(lb, rb, r, best_key):
    mark = " ★" if (lb, rb) == best_key else "  "
    return (
        f"  lookback={lb:<4} rebal={rb:<4}"
        f"{r['total_return']:>+10.2f}%"
        f"{r['mdd']:>8.2f}%"
        f"{r['win_rate']:>6.1f}%"
        f"{r['trade_count']:>7}회"
        f"{r['rebalance_count']:>7}회"
        f"{r['final_value']:>14,}원"
        f"{mark}"
    )


def _print_comparison(label, results_map):
    """results_map: {(lookback, rebalance): result_dict}"""
    best_key = max(results_map, key=lambda k: results_map[k]["total_return"])
    print(f"\n\n{'='*W2}")
    print(f"  [Lookback × Rebalance 비교]  {label}  (top_n={TOP_N} 고정)")
    print(f"{'='*W2}")
    print(
        f"  {'lookback / rebal':<20}"
        f"{'총수익률':>11}"
        f"{'MDD':>9}"
        f"{'승률':>7}"
        f"{'매도횟수':>8}"
        f"{'리밸런싱':>8}"
        f"{'최종금액':>15}"
    )
    print(f"  {'-'*(W2-2)}")
    for lb in LOOKBACKS:
        for rb in REBALANCES:
            key = (lb, rb)
            if key in results_map:
                print(_row(lb, rb, results_map[key], best_key))
        print(f"  {'·'*(W2-2)}")
    print(f"  ★ 최적 조합: lookback={best_key[0]}일  rebalance={best_key[1]}일")
    print(f"{'='*W2}")


def _print_train_test_comparison(train_map, test_map):
    best_train = max(train_map, key=lambda k: train_map[k]["total_return"])
    best_test  = max(test_map,  key=lambda k: test_map[k]["total_return"])

    print(f"\n\n{'='*W2}")
    print(f"  [Train vs Test 비교]  Train: 2019~2022  /  Test: 2023~2025  (top_n={TOP_N})")
    print(f"{'='*W2}")
    print(
        f"  {'lookback / rebal':<20}"
        f"  {'[TRAIN] 총수익률':>13}{'MDD':>8}{'승률':>6}"
        f"  │"
        f"  {'[TEST] 총수익률':>13}{'MDD':>8}{'승률':>6}"
    )
    print(f"  {'-'*(W2-2)}")
    for lb in LOOKBACKS:
        for rb in REBALANCES:
            key = (lb, rb)
            tr = train_map.get(key)
            te = test_map.get(key)
            tm = "★" if key == best_train else " "
            em = "★" if key == best_test  else " "
            tr_str = f"  {tr['total_return']:>+12.2f}%{tr['mdd']:>7.2f}%{tr['win_rate']:>5.1f}% {tm}" if tr else f"  {'없음':>28}"
            te_str = f"  {te['total_return']:>+12.2f}%{te['mdd']:>7.2f}%{te['win_rate']:>5.1f}% {em}" if te else f"  {'없음':>28}"
            print(f"  lb={lb:<4} rb={rb:<4}         {tr_str}  │{te_str}")
        print(f"  {'·'*(W2-2)}")
    match = "✓ 일치" if best_train == best_test else f"✗ 불일치 (train★lb={best_train[0]}/rb={best_train[1]} / test★lb={best_test[0]}/rb={best_test[1]})"
    print(f"  → 최적 조합 일치 여부: {match}")
    print(f"{'='*W2}")


def _run_all(token, start, end, cash, label):
    """LOOKBACKS × REBALANCES 전체 조합 실행. 데이터는 첫 번째 조합에서만 로드(캐시 활용)."""
    results = {}
    first = True
    for lb in LOOKBACKS:
        for rb in REBALANCES:
            key = (lb, rb)
            print(f"\n  [lookback={lb}, rebalance={rb}] {label} 실행 중...")
            try:
                results[key] = run(
                    token, TICKERS, start, end,
                    top_n=TOP_N,
                    rebalance_days=rb,
                    lookback_days=lb,
                    initial_cash=cash,
                    verbose=first,
                )
                first = False
                r = results[key]
                print(f"    → 수익률: {r['total_return']:+.2f}%  MDD: {r['mdd']:.2f}%  승률: {r['win_rate']:.1f}%")
            except Exception as e:
                print(f"    → 실패: {e}")
                first = False
    return results


def main():
    args  = parse_args()
    token = get_token()

    if args.start and args.end:
        print(f"\n모멘텀 전략 비교: {args.start} ~ {args.end}\n")
        results = _run_all(token, args.start, args.end, args.cash, "단일")
        _print_comparison(f"{args.start} ~ {args.end}", results)
        return

    print(f"\n모멘텀 전략 Lookback × Rebalance 비교  (top_n={TOP_N})")
    print(f"  lookback: {LOOKBACKS}  /  rebalance: {REBALANCES}\n")

    print(f"▶ Train: {args.train_start} ~ {args.train_end}")
    train_map = _run_all(token, args.train_start, args.train_end, args.cash, "TRAIN")
    _print_comparison(f"Train ({args.train_start}~{args.train_end})", train_map)

    print(f"\n▶ Test: {args.test_start} ~ {args.test_end}")
    test_map = _run_all(token, args.test_start, args.test_end, args.cash, "TEST")
    _print_comparison(f"Test ({args.test_start}~{args.test_end})", test_map)

    _print_train_test_comparison(train_map, test_map)


if __name__ == "__main__":
    main()
