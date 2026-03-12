"""
백테스트 결과 출력 및 전략 비교.
"""

W = 90  # 표 전체 너비


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


def _row(k, r, best_k):
    mark = " ★" if k == best_k else "  "
    return (
        f"  k={k:<5}"
        f"{r['weekly_return']:>+12.3f}%"
        f"{r['total_return']:>+9.2f}%"
        f"{r['mdd']:>8.2f}%"
        f"{r['win_rate']:>6.1f}%"
        f"{r['trade_count']:>6}회"
        f"{mark}"
    )


def _sub_header(label: str):
    return (
        f"  {'k값':<7}"
        f"  {'주간평균수익률':>11}"
        f"{'총수익률':>10}"
        f"{'MDD':>9}"
        f"{'승률':>7}"
        f"{'매매횟수':>7}"
        f"  ({label})"
    )


def print_comparison(results: list[dict]):
    """종목별 k값 비교 표 출력 (train/test 구분 없이)"""

    grouped: dict[str, list] = {}
    for item in results:
        grouped.setdefault(item["ticker"], []).append(item)

    print(f"\n\n{'='*W}")
    print(f"  [백테스트 결과 비교]  (변동성 돌파 전략, k값별)")
    print(f"{'='*W}")

    for ticker_name, items in grouped.items():
        sorted_items = sorted(items, key=lambda x: float(x["strategy"].split("=")[1].rstrip(")")))
        best_k = max(items, key=lambda x: x["result"]["total_return"])["strategy"].split("=")[1].rstrip(")")

        print(f"\n  ■ {ticker_name}")
        print(f"  {'-'*(W-2)}")
        print(_sub_header("단일 기간"))
        print(f"  {'-'*(W-2)}")

        for item in sorted_items:
            k = item["strategy"].split("=")[1].rstrip(")")
            print(_row(k, item["result"], best_k))

        print(f"  {'-'*(W-2)}")

    print(f"\n{'='*W}")


def print_train_test_comparison(train_results: list[dict], test_results: list[dict]):
    """
    Train(2022~2023) / Test(2024~2025) 나란히 비교 표 출력.
    k=0.9가 train에서 최적이었는지, test에서도 유효한지 확인용.
    """

    # {ticker: {k: result}} 형태로 인덱싱
    def index(results):
        d: dict[str, dict] = {}
        for item in results:
            k = item["strategy"].split("=")[1].rstrip(")")
            d.setdefault(item["ticker"], {})[k] = item["result"]
        return d

    train_idx = index(train_results)
    test_idx  = index(test_results)

    tickers = list(train_idx.keys())
    k_list  = sorted(train_idx[tickers[0]].keys(), key=float)

    W2 = 100
    print(f"\n\n{'='*W2}")
    print(f"  [Train vs Test 비교]  Train: 2022~2023  /  Test: 2024~2025")
    print(f"{'='*W2}")

    for ticker_name in tickers:
        tr = train_idx.get(ticker_name, {})
        te = test_idx.get(ticker_name, {})

        best_train_k = max(tr, key=lambda k: tr[k]["total_return"]) if tr else None
        best_test_k  = max(te, key=lambda k: te[k]["total_return"]) if te else None

        print(f"\n  ■ {ticker_name}")
        print(f"  {'-'*(W2-2)}")
        print(
            f"  {'k값':<7}"
            f"{'[TRAIN] 주간평균':>14}{'총수익률':>10}{'MDD':>8}{'승률':>6}"
            f"  │"
            f"{'[TEST] 주간평균':>14}{'총수익률':>10}{'MDD':>8}{'승률':>6}"
        )
        print(f"  {'-'*(W2-2)}")

        for k in k_list:
            r_tr = tr.get(k)
            r_te = te.get(k)

            train_mark = "★" if k == best_train_k else " "
            test_mark  = "★" if k == best_test_k  else " "

            tr_str = (
                f"{r_tr['weekly_return']:>+13.3f}%"
                f"{r_tr['total_return']:>+9.2f}%"
                f"{r_tr['mdd']:>7.2f}%"
                f"{r_tr['win_rate']:>5.1f}%"
                f" {train_mark}"
            ) if r_tr else f"{'데이터 없음':>40}"

            te_str = (
                f"{r_te['weekly_return']:>+13.3f}%"
                f"{r_te['total_return']:>+9.2f}%"
                f"{r_te['mdd']:>7.2f}%"
                f"{r_te['win_rate']:>5.1f}%"
                f" {test_mark}"
            ) if r_te else f"{'데이터 없음':>40}"

            print(f"  k={k:<5} {tr_str}  │ {te_str}")

        print(f"  {'-'*(W2-2)}")
        if best_train_k and best_test_k:
            consistent = "✓ 일치" if best_train_k == best_test_k else f"✗ 불일치 (train★k={best_train_k} / test★k={best_test_k})"
            print(f"  → 최적 k 일치 여부: {consistent}")

    print(f"\n{'='*W2}")
