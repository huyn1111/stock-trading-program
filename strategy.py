"""
종목별 매매 전략 파라미터 및 신호 생성.

백테스트(Train 2022~2023 / Test 2023~2025) 최적 결과 기반:
  - 삼성전자        (005930): RSI(p=7, OS=34, OB=65)   Test +47%
  - SK하이닉스      (000660): RSI(p=7, OS=31, OB=70)   Test +106%
  - LIG넥스원       (079550): RSI(p=7, OS=38, OB=63)   Test +151%
  - 두산에너빌리티  (034020): RSI(p=7, OS=33, OB=68)   Test +162%
  - 에코프로        (086520): 변동성 돌파 k=0.9        Test +334%
  - 레인보우로보틱스(277810): RSI(p=7, OS=39, OB=70)   Test +214%
"""

from strategies.rsi import RSIStrategy
from strategies.volatility_breakout import VolatilityBreakoutStrategy

# RSI 전략 종목별 인스턴스
RSI_STRATEGIES: dict[str, RSIStrategy] = {
    "005930": RSIStrategy(period=7, oversold=34, overbought=65),  # 삼성전자
    "000660": RSIStrategy(period=7, oversold=31, overbought=70),  # SK하이닉스
    "079550": RSIStrategy(period=7, oversold=38, overbought=63),  # LIG넥스원
    "034020": RSIStrategy(period=7, oversold=33, overbought=68),  # 두산에너빌리티
    "277810": RSIStrategy(period=7, oversold=39, overbought=70),  # 레인보우로보틱스
}

# 변동성 돌파 전략 종목별 인스턴스
VB_STRATEGIES: dict[str, VolatilityBreakoutStrategy] = {
    "086520": VolatilityBreakoutStrategy(k=0.9),  # 에코프로
}


def check_rsi_signal(ticker: str, ohlcv: list[dict], holding: bool) -> str:
    """
    일봉 OHLCV 기반 RSI 크로스오버 신호.

    Args:
        ticker: 종목코드
        ohlcv:  최근 N일 OHLCV (오래된 날짜 순), 마지막 항목 = 전날 종가
        holding: 현재 보유 여부

    Returns:
        "BUY" | "SELL" | "HOLD"
    """
    strategy = RSI_STRATEGIES.get(ticker)
    if strategy is None or len(ohlcv) < strategy.period + 2:
        return "HOLD"
    signal = strategy.generate_signal(ohlcv, len(ohlcv) - 1)
    if signal == "BUY" and holding:
        return "HOLD"
    if signal == "SELL" and not holding:
        return "HOLD"
    return signal


def load_strategies_from_file(path: str) -> tuple[dict, dict]:
    """
    results/best_strategies.json 로드 → (RSI_STRATEGIES, VB_STRATEGIES) 반환.
    파일이 없거나 파싱 실패 시 하드코딩된 기본값 반환.
    """
    import json, os
    if not os.path.exists(path):
        return RSI_STRATEGIES, VB_STRATEGIES

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[strategy] 전략 파일 로드 실패: {e} → 기본값 사용")
        return RSI_STRATEGIES, VB_STRATEGIES

    rsi_strats: dict[str, RSIStrategy] = {}
    vb_strats:  dict[str, VolatilityBreakoutStrategy] = {}

    for ticker, info in data.get("tickers", {}).items():
        stype  = info.get("strategy_type")
        params = info.get("params", {})
        try:
            if stype == "RSI":
                rsi_strats[ticker] = RSIStrategy(
                    period=params["period"],
                    oversold=params["oversold"],
                    overbought=params["overbought"],
                )
            elif stype == "VB":
                vb_strats[ticker] = VolatilityBreakoutStrategy(k=params["k"])
        except Exception as e:
            print(f"[strategy] {ticker} 전략 생성 실패: {e}")

    return rsi_strats, vb_strats


def check_vb_signal(
    ticker: str,
    today_open: int,
    prev_high: int,
    prev_low: int,
    current_price: int,
    holding: bool,
) -> str:
    """
    변동성 돌파 신호. 장 중 현재가가 목표가 이상이면 BUY.
    목표가 = 당일 시가 + (전날 고가 - 전날 저가) * k

    Returns:
        "BUY" | "HOLD"
    """
    strategy = VB_STRATEGIES.get(ticker)
    if strategy is None or holding:
        return "HOLD"
    today_dict = {"open": today_open, "high": current_price}
    prev_dict  = {"high": prev_high,  "low": prev_low}
    return strategy.generate_signal(today_dict, prev_dict)
