"""Built-in capital allocation model implementations."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal

from simulor.core.protocols import AllocationModel


class WeightBasedAllocationModel(AllocationModel):
    """Fixed-weight capital allocation.

    Allocates capital to strategies based on predefined weights.
    Weights are normalized to sum to 1.0.

    Example:
        >>> allocation = WeightBasedAllocationModel({'momentum': Decimal('0.6'), 'mean_rev': Decimal('0.4')})
        >>> allocation.allocate({'momentum', 'mean_rev'}, Decimal('100000'))
        {'momentum': Decimal('60000'), 'mean_rev': Decimal('40000')}
    """

    def __init__(self, weights: Mapping[str, Decimal] | None = None):
        """Initialize weight-based allocation.

        Args:
            weights: Dictionary mapping strategy names to weights.
                    If None, uses equal weights for all strategies.
        """
        # Defensive copy of provided mapping and normalize values to Decimal.
        if weights is None:
            self.weights: dict[str, Decimal] = {}
        else:
            converted: dict[str, Decimal] = {}
            for name, w in weights.items():
                try:
                    dec = w if isinstance(w, Decimal) else Decimal(str(w))
                except Exception as exc:  # explicit conversion error
                    raise TypeError(f"Weight for '{name}' is not Decimal-convertible: {w!r}") from exc
                if dec < 0:
                    raise ValueError(f"Weight for '{name}' must be non-negative")
                converted[str(name)] = dec
            self.weights = converted

    def allocate(self, strategy_names: Iterable[str], total_capital: Decimal) -> dict[str, Decimal]:
        """Allocate capital based on fixed weights.

        Normalizes only weights corresponding to the requested strategies. If the
        sum of requested weights is zero, falls back to equal-weight allocation.
        """
        # Preserve order and uniqueness while allowing any iterable input
        strategy_list = list(dict.fromkeys(strategy_names))
        if not strategy_list:
            return {}

        # If weights were provided, consider only the requested strategies
        if self.weights:
            weights_for_requested = {name: self.weights.get(name, Decimal("0")) for name in strategy_list}
            total_weight = sum(weights_for_requested.values())
            if total_weight > 0:
                normalized_weights = {name: weight / total_weight for name, weight in weights_for_requested.items()}
            else:
                # Fallback to equal weights when requested weights sum to zero
                eq = Decimal("1") / Decimal(len(strategy_list))
                normalized_weights = dict.fromkeys(strategy_list, eq)
        else:
            eq = Decimal("1") / Decimal(len(strategy_list))
            normalized_weights = dict.fromkeys(strategy_list, eq)

        # Allocate capital
        allocation: dict[str, Decimal] = {}
        for name in strategy_list:
            weight = normalized_weights.get(name, Decimal("0"))
            allocation[name] = total_capital * weight

        return allocation
