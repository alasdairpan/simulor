from abc import abstractmethod
from datetime import timedelta

__all__ = ["LatencyModel", "ConstantLatencyModel"]


class LatencyModel:
    """Base class for latency models."""

    @abstractmethod
    def sample(self) -> timedelta:
        """Sample a latency value"""
        ...


class ConstantLatencyModel(LatencyModel):
    """Latency model with a constant latency value.

    Args:
        latency: Constant latency in seconds
    """

    def __init__(self, latency: float) -> None:
        self.latency = latency

    def sample(self) -> timedelta:
        """Return the constant latency value."""
        return timedelta(seconds=self.latency)
