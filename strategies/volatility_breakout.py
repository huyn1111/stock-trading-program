from .base import BaseStrategy


class VolatilityBreakoutStrategy(BaseStrategy):
    """
    래리 윌리엄스 변동성 돌파 전략.

    목표가 = 당일 시가 + (전날 고가 - 전날 저가) * k
    당일 고가가 목표가 이상이면 BUY → 다음날 시가에 SELL
    k값이 클수록 보수적 (기본값 0.5)
    """

    def __init__(self, k: float = 0.5):
        self.k = k

    @property
    def name(self) -> str:
        return f"변동성돌파(k={self.k})"

    def generate_signal(self, today: dict, prev: dict) -> str:
        target = today["open"] + (prev["high"] - prev["low"]) * self.k

        if today["high"] >= target:
            return "BUY"

        return "HOLD"
