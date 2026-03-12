from abc import ABC, abstractmethod


class BaseStrategy(ABC):
    """
    모든 전략이 상속받는 추상 기본 클래스.
    새 전략 추가 시 name과 generate_signal만 구현하면 됨.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """전략 이름"""
        pass

    @abstractmethod
    def generate_signal(self, today: dict, prev: dict) -> str:
        """
        하루치 데이터를 받아 매매 신호를 반환.

        Args:
            today: 오늘 OHLCV {"open", "high", "low", "close", "volume", "date"}
            prev:  전날 OHLCV (동일 구조)

        Returns:
            "BUY" | "SELL" | "HOLD"
        """
        pass
