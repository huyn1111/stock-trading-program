"""
전체 한국 주식 유니버스 백테스트 — 종목별 최적 전략 탐색 및 저장

전략: VB(k=0.5) / VB(k=0.9) / RSI(7,35/65) / RSI(7,40/60)

실행 후 results/best_strategies.json 에 최적 전략이 저장되며,
main.py 가 이 파일을 자동으로 읽어 해당 전략으로 자동매매를 실행합니다.

사용:
    python run_universe_backtest.py                    # 내장 100종목 (기본)
    python run_universe_backtest.py --market KOSPI     # KOSPI 전종목 (pykrx 필요)
    python run_universe_backtest.py --market ALL       # KOSPI+KOSDAQ 전종목
    python run_universe_backtest.py --top-n 200        # 시총 상위 200개 (pykrx 필요)
    python run_universe_backtest.py --max-pos 10       # 자동매매 최대 보유 종목 수
    python run_universe_backtest.py --output results/my_best.json

전체 종목 사용 시 pykrx 필요:
    pip install pykrx
"""

import argparse
import json
import os
import time
from datetime import datetime, timedelta

from api import get_token
from backtest.data_loader import load_ohlcv
from backtest.engine import run as vb_run
from backtest.rsi_engine import run as rsi_run
from strategies.volatility_breakout import VolatilityBreakoutStrategy
from strategies.rsi import RSIStrategy


# ── 비교할 전략 목록 ─────────────────────────────────────────────────────────
STRATEGIES = {
    # 변동성 돌파 (k값 4단계)
    "VB_k0.3":    {"type": "VB",  "k": 0.3},
    "VB_k0.5":    {"type": "VB",  "k": 0.5},
    "VB_k0.7":    {"type": "VB",  "k": 0.7},
    "VB_k0.9":    {"type": "VB",  "k": 0.9},
    # RSI 7일 (4가지 임계값)
    "RSI7_30/70": {"type": "RSI", "period": 7,  "oversold": 30, "overbought": 70},
    "RSI7_35/65": {"type": "RSI", "period": 7,  "oversold": 35, "overbought": 65},
    "RSI7_40/60": {"type": "RSI", "period": 7,  "oversold": 40, "overbought": 60},
    "RSI7_45/55": {"type": "RSI", "period": 7,  "oversold": 45, "overbought": 55},
    # RSI 14일 (2가지 임계값)
    "RSI14_30/70": {"type": "RSI", "period": 14, "oversold": 30, "overbought": 70},
    "RSI14_35/65": {"type": "RSI", "period": 14, "oversold": 35, "overbought": 65},
}

# ── 기본 유니버스 (pykrx 미설치 시 fallback) ─────────────────────────────────
FALLBACK_TICKERS = {
    "005930": "삼성전자",    "000660": "SK하이닉스",  "009150": "삼성전기",
    "066570": "LG전자",      "000990": "DB하이텍",    "108320": "LX세미콘",
    "042700": "한미반도체",  "240810": "원익IPS",     "058470": "리노공업",   "095610": "테스",
    "373220": "LG에너지솔루션", "006400": "삼성SDI",  "051910": "LG화학",
    "003670": "포스코퓨처엠", "086520": "에코프로",   "247540": "에코프로비엠",
    "066970": "엘앤에프",    "278280": "천보",        "005070": "코스모신소재", "121600": "나노신소재",
    "005380": "현대차",      "000270": "기아",        "012330": "현대모비스",  "011210": "현대위아",
    "204320": "HL만도",      "018880": "한온시스템",  "005850": "에스엘",
    "307950": "현대오토에버","086280": "현대글로비스", "010690": "화신",
    "012450": "한화에어로스페이스", "079550": "LIG넥스원", "047810": "한국항공우주",
    "064350": "현대로템",    "277810": "레인보우로보틱스", "454910": "두산로보틱스",
    "034020": "두산에너빌리티", "272210": "한화시스템", "003570": "SNT다이내믹스", "010820": "퍼스텍",
    "035420": "NAVER",       "035720": "카카오",      "293490": "카카오게임즈",
    "377300": "카카오페이",  "323410": "카카오뱅크",  "067160": "SOOP",
    "192080": "더블유게임즈","078340": "컴투스",      "063080": "컴투스홀딩스", "112040": "위메이드",
    "207940": "삼성바이오로직스", "068270": "셀트리온", "091990": "셀트리온헬스케어",
    "068760": "셀트리온제약","326030": "SK바이오팜",  "302440": "SK바이오사이언스",
    "128940": "한미약품",    "000100": "유한양행",    "196170": "알테오젠",    "028300": "HLB",
    "005490": "POSCO홀딩스", "047050": "포스코인터내셔널", "004020": "현대제철",
    "010130": "고려아연",    "103140": "풍산",        "001230": "동국제강",
    "058650": "세아베스틸지주", "010060": "OCI",     "011170": "롯데케미칼",  "011780": "금호석유",
    "105560": "KB금융",      "055550": "신한지주",    "086790": "하나금융지주",
    "316140": "우리금융지주","024110": "기업은행",    "016360": "삼성증권",
    "006800": "미래에셋증권","071050": "한국금융지주","138040": "메리츠금융지주", "039490": "키움증권",
    "090430": "아모레퍼시픽","051900": "LG생활건강",  "008770": "호텔신라",
    "001040": "CJ",          "097950": "CJ제일제당",  "139480": "이마트",
    "023530": "롯데쇼핑",    "282330": "BGF리테일",   "007070": "GS리테일",    "004370": "농심",
    "003490": "대한항공",    "011200": "HMM",         "030200": "KT",          "017670": "SK텔레콤",
    "003550": "LG",          "034730": "SK",          "000880": "한화",        "078930": "GS",
    "000150": "두산",        "006260": "LS",
}

RESULTS_DIR = "results"


# ── CLI 인자 ─────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="전체 유니버스 백테스트")
    p.add_argument("--market",      default=None,   help="KOSPI | KOSDAQ | ALL (pykrx 필요)")
    p.add_argument("--top-n",       type=int, default=0, help="시총 상위 N개 필터 (pykrx 필요)")
    p.add_argument("--cash",        type=int, default=10_000_000)
    p.add_argument("--max-pos",     type=int, default=10, help="자동매매 최대 보유 종목 수")
    p.add_argument("--min-trades",  type=int, default=3,  help="유효 전략 최소 매매 횟수")
    p.add_argument("--train-start", default="20220101")
    p.add_argument("--train-end",   default="20231231")
    p.add_argument("--test-start",  default="20240101")
    p.add_argument("--test-end",    default="20251231")
    p.add_argument("--output",      default=os.path.join(RESULTS_DIR, "best_strategies.json"))
    p.add_argument("--cache-only",  action="store_true",
                   help="캐시 파일만 사용 (API 토큰 불필요). 미캐시 종목은 건너뜀.")
    return p.parse_args()


# ── 유니버스 로드 ─────────────────────────────────────────────────────────────

def _last_trading_day() -> str:
    d = datetime.today()
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime("%Y%m%d")


def get_universe(market: str | None, top_n: int) -> dict[str, str]:
    """
    종목 유니버스 반환.
    우선순위: results/all_tickers.json → 내장 100종목
    --market 옵션: KOSPI | KOSDAQ | ALL 필터 적용
    """
    all_tickers_path = os.path.join(RESULTS_DIR, "all_tickers.json")

    # results/all_tickers.json 있으면 우선 사용 (download_all_data.py 실행 후 생성)
    if os.path.exists(all_tickers_path):
        with open(all_tickers_path, encoding="utf-8") as f:
            data = json.load(f)

        if market == "KOSPI":
            tickers = data.get("KOSPI", {})
        elif market == "KOSDAQ":
            tickers = data.get("KOSDAQ", {})
        else:  # ALL 또는 None
            tickers = {**data.get("KOSPI", {}), **data.get("KOSDAQ", {})}

        if top_n > 0:
            tickers = dict(list(tickers.items())[:top_n])

        print(f"  유니버스: {all_tickers_path}  ({len(tickers)}종목"
              + (f", {market}" if market else "") + ")")
        return tickers

    # 파일 없으면 내장 100종목
    print(f"  유니버스: 내장 {len(FALLBACK_TICKERS)}종목 (기본값)")
    print("  전체 종목 사용하려면: python download_all_data.py  실행 후 재시도")
    if market:
        print(f"  (--market {market} 옵션은 all_tickers.json 없으면 무시됩니다)")
    return FALLBACK_TICKERS


# ── 데이터 다운로드 ───────────────────────────────────────────────────────────

def download_data(token: str, tickers: dict, start: str, end: str, label: str) -> dict[str, list]:
    """전 종목 OHLCV 다운로드 (캐시 우선). 최소 20거래일 미만 종목 제외."""
    total = len(tickers)
    print(f"\n  [{label}] 데이터 로드 중 ({start}~{end}, {total}종목)...")
    data_map = {}
    for i, (ticker, name) in enumerate(tickers.items(), 1):
        try:
            rows = load_ohlcv(token, ticker, start, end)
            if len(rows) >= 20:
                data_map[ticker] = rows
        except Exception:
            pass
        if i % 50 == 0 or i == total:
            print(f"    {i}/{total} ... (유효 {len(data_map)}개)")
        time.sleep(0.05)
    print(f"    완료: {len(data_map)}/{total}종목")
    return data_map


# ── 백테스트 실행 ─────────────────────────────────────────────────────────────

def _make_strategy(sname: str):
    cfg = STRATEGIES[sname]
    if cfg["type"] == "VB":
        return VolatilityBreakoutStrategy(k=cfg["k"])
    return RSIStrategy(period=cfg["period"], oversold=cfg["oversold"], overbought=cfg["overbought"])


def run_all_strategies(data_map: dict, cash: int, label: str) -> dict[str, dict[str, dict]]:
    """
    Returns: {ticker: {strategy_name: result_dict}}
    """
    total = len(data_map)
    print(f"\n  [{label}] {total}종목 × {len(STRATEGIES)}전략 백테스트 중...")
    results: dict[str, dict[str, dict]] = {}
    for i, (ticker, rows) in enumerate(data_map.items(), 1):
        results[ticker] = {}
        for sname, cfg in STRATEGIES.items():
            try:
                s = _make_strategy(sname)
                r = vb_run(s, rows, initial_cash=cash) if cfg["type"] == "VB" \
                    else rsi_run(s, rows, initial_cash=cash)
                results[ticker][sname] = r
            except Exception:
                results[ticker][sname] = {}
        if i % 50 == 0 or i == total:
            print(f"    {i}/{total} 완료...")
    print("    완료")
    return results


# ── 최적 전략 선정 ────────────────────────────────────────────────────────────

def _score(r: dict, min_trades: int) -> float:
    """리스크 조정 점수. 조건 미달 시 -inf."""
    if not r or r.get("trade_count", 0) < min_trades:
        return float("-inf")
    return r["total_return"] / (1 + r.get("mdd", 100) / 100)


def select_best(
    train_results: dict,
    test_results: dict,
    tickers: dict,
    min_trades: int,
) -> list[dict]:
    """
    종목별 최적 전략 선정.

    선정 기준:
      1. Train 수익률 > 0  AND  Test 수익률 > 0
      2. Test 매매 횟수 >= min_trades
      3. 점수 = (train_score + test_score) / 2  (리스크 조정)
    """
    selected = []

    for ticker, train_strats in train_results.items():
        test_strats = test_results.get(ticker, {})
        best_sname, best_score = None, float("-inf")

        for sname in STRATEGIES:
            tr = train_strats.get(sname, {})
            te = test_strats.get(sname, {})
            if not tr or not te:
                continue
            if tr.get("total_return", -999) <= 0 or te.get("total_return", -999) <= 0:
                continue
            if te.get("trade_count", 0) < min_trades:
                continue

            combined = (_score(tr, min_trades) + _score(te, min_trades)) / 2
            if combined > best_score:
                best_score  = combined
                best_sname  = sname

        if best_sname is None:
            continue

        cfg = STRATEGIES[best_sname]
        tr  = train_strats[best_sname]
        te  = test_strats[best_sname]

        selected.append({
            "ticker":        ticker,
            "name":          tickers.get(ticker, ticker),
            "strategy":      best_sname,
            "strategy_type": cfg["type"],
            "params":        {k: v for k, v in cfg.items() if k != "type"},
            "train_return":  round(tr["total_return"], 2),
            "train_mdd":     round(tr.get("mdd", 0), 2),
            "test_return":   round(te["total_return"], 2),
            "test_mdd":      round(te.get("mdd", 0), 2),
            "test_win_rate": round(te.get("win_rate", 0), 1),
            "test_trades":   te.get("trade_count", 0),
            "score":         round(best_score, 4),
        })

    selected.sort(key=lambda x: x["score"], reverse=True)
    return selected


# ── 리포트 출력 ───────────────────────────────────────────────────────────────

def print_report(selected: list[dict]):
    W = 120
    strat_count: dict[str, int] = {}

    print(f"\n\n{'='*W}")
    print(f"  [유니버스 백테스트 결과]  전략 통과 종목 전체 {len(selected)}개 → 자동매매 적용")
    print(f"{'='*W}")
    print(
        f"  {'종목':<14} {'전략':<13}"
        f"  {'TRAIN 수익률':>12} {'MDD':>8}"
        f"  │"
        f"  {'TEST 수익률':>12} {'MDD':>8} {'승률':>7} {'매매':>5}"
        f"  {'점수':>8}"
    )
    print(f"  {'-'*(W-2)}")

    for item in selected:
        print(
            f"  {item['name']:<14} {item['strategy']:<13}"
            f"  {item['train_return']:>+11.2f}% {item['train_mdd']:>7.2f}%"
            f"  │"
            f"  {item['test_return']:>+11.2f}% {item['test_mdd']:>7.2f}%"
            f" {item['test_win_rate']:>6.1f}%"
            f" {item['test_trades']:>4}회"
            f"  {item['score']:>8.4f}"
        )
        strat_count[item["strategy"]] = strat_count.get(item["strategy"], 0) + 1

    print(f"\n  전략별 선정 종목 수:")
    for s, cnt in sorted(strat_count.items(), key=lambda x: x[1], reverse=True):
        print(f"    {s:<14}: {cnt}개")
    print(f"{'='*W}")


def save_results(selected: list[dict], max_pos: int, output_path: str, args):
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    payload = {
        "generated_at":  datetime.now().strftime("%Y-%m-%d %H:%M"),
        "train_period":  f"{args.train_start}~{args.train_end}",
        "test_period":   f"{args.test_start}~{args.test_end}",
        "max_positions": max_pos,
        "tickers": {}
    }

    for item in selected[:max_pos]:
        payload["tickers"][item["ticker"]] = {
            "name":          item["name"],
            "strategy":      item["strategy"],
            "strategy_type": item["strategy_type"],
            "params":        item["params"],
            "test_return":   item["test_return"],
            "test_mdd":      item["test_mdd"],
            "test_win_rate": item["test_win_rate"],
        }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"\n  저장: {output_path}  ({len(payload['tickers'])}종목)")
    print("  → python main.py 실행 시 이 설정이 자동으로 적용됩니다.")


# ── 메인 ─────────────────────────────────────────────────────────────────────

def main():
    args = parse_args()

    if args.cache_only:
        token = "CACHE_ONLY"
        print("  [cache-only 모드] API 토큰 없이 캐시 파일만 사용합니다.")
    else:
        token = get_token()

    print(f"\n{'='*60}")
    print(f"  유니버스 백테스트")
    print(f"  Train : {args.train_start} ~ {args.train_end}")
    print(f"  Test  : {args.test_start} ~ {args.test_end}")
    print(f"  전략  : {', '.join(STRATEGIES.keys())}")
    print(f"{'='*60}")

    tickers    = get_universe(args.market, args.top_n)
    train_data = download_data(token, tickers, args.train_start, args.train_end, "TRAIN")
    test_data  = download_data(token, tickers, args.test_start,  args.test_end,  "TEST")

    train_results = run_all_strategies(train_data, args.cash, "TRAIN")
    test_results  = run_all_strategies(test_data,  args.cash, "TEST")

    selected = select_best(train_results, test_results, tickers, args.min_trades)
    print_report(selected)
    save_results(selected, args.max_pos, args.output, args)


if __name__ == "__main__":
    main()
