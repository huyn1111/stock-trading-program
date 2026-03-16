"""
RSI(Relative Strength Index) 전략.

- RSI가 oversold 미만에서 oversold 이상으로 올라올 때 → BUY
- RSI가 overbought 초과에서 overbought 이하로 내려올 때 → SELL
"""


class RSIStrategy:
    """RSI 전략 (기존 BaseStrategy와 다른 인터페이스 사용 — 히스토리 윈도우 필요)"""

    def __init__(self, period: int = 14, oversold: float = 30, overbought: float = 70):
        self.period     = period
        self.oversold   = oversold
        self.overbought = overbought

    @property
    def name(self) -> str:
        return f"RSI(p={self.period},{self.oversold}/{self.overbought})"

    @staticmethod
    def calc_rsi(closes: list[float], period: int) -> float | None:
        """Wilder 평활 방식 RSI 계산. 데이터가 부족하면 None 반환."""
        if len(closes) < period + 1:
            return None

        changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        gains   = [max(c, 0) for c in changes]
        losses  = [abs(min(c, 0)) for c in changes]

        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period

        for i in range(period, len(changes)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def generate_signal(self, data: list[dict], index: int) -> str:
        """
        data[index]까지의 종가로 RSI를 계산해 매매 신호 반환.

        Returns:
            "BUY" | "SELL" | "HOLD"
        """
        if index < self.period + 2:
            return "HOLD"

        closes_prev = [d["close"] for d in data[:index]]
        closes_curr = [d["close"] for d in data[:index + 1]]

        rsi_prev = self.calc_rsi(closes_prev, self.period)
        rsi_curr = self.calc_rsi(closes_curr, self.period)

        if rsi_prev is None or rsi_curr is None:
            return "HOLD"

        if rsi_prev < self.oversold and rsi_curr >= self.oversold:
            return "BUY"

        if rsi_prev > self.overbought and rsi_curr <= self.overbought:
            return "SELL"

        return "HOLD"
