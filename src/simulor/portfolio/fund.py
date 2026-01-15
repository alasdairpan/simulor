"""Fund module for managing multiple strategies with capital allocation."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulor.core.protocols import AllocationModel
    from simulor.strategy.strategy import Strategy


class Fund:
    """Global fund that manages multiple strategies with capital allocation.

    The Fund:
    - Holds a collection of strategies
    - Manages total capital allocation across strategies
    - Applies allocation model to distribute capital
    - Each strategy gets its own Portfolio (account) with allocated capital

    Example:
        >>> from simulor.allocation import WeightBasedAllocationModel
        >>> fund = Fund(
        ...     strategies=[strategy1, strategy2],
        ...     capital=Decimal('100000'),
        ...     allocation=WeightBasedAllocationModel()
        ... )
    """

    def __init__(
        self,
        strategies: list[Strategy],
        capital: Decimal,
        allocation: AllocationModel | None = None,
    ):
        """Initialize the fund with strategies and capital.

        This constructor validates the input capital and strategies, ensures strategy names
        are unique, and calculates the initial capital allocation for each strategy using
        the provided (or default) allocation model.

        Args:
            strategies: A list of `Strategy` objects to be managed by the fund.
                Must contain at least one strategy.
            capital: The initial total capital available to the fund.
                Must be a positive decimal number.
            allocation: An optional `AllocationModel` to determine how capital is
                distributed among strategies. If None, `WeightBasedAllocationModel`
                (equal weighting) is used by default.

        Raises:
            ValueError: If `strategies` list is empty.
            ValueError: If `capital` is not positive.
            ValueError: If strategy names are not unique.
            ValueError: If the allocation model allocates more than the available capital.
        """

        self._strategies = strategies
        self._capital = capital

        # Basic validation
        if not self._strategies:
            raise ValueError("At least one strategy must be provided")
        if self._capital <= Decimal("0"):
            raise ValueError("Total capital must be positive")

        from simulor.allocation.models import WeightBasedAllocationModel

        self._allocation_model = allocation or WeightBasedAllocationModel()

        # Validate unique strategy names to prevent collisions in the broker/portfolio
        strategy_names = {s.name for s in self._strategies}
        if len(strategy_names) != len(self._strategies):
            raise ValueError("Strategy names must be unique")

        # Calculate and store capital allocation per strategy
        # The allocation model returns a dict of {strategy_name: allocated_amount}
        self._allocations = self._allocation_model.allocate(strategy_names, self._capital)

        # Validate that the model didn't over-allocate
        total_allocated = sum(self._allocations.values())
        if total_allocated > self._capital:
            raise ValueError("Total allocated capital exceeds available capital")

    def get_allocation(self, strategy_name: str) -> Decimal:
        """Get the allocated capital amount for a specific strategy.

        Args:
            strategy_name: The unique name of the strategy.

        Returns:
            The amount of capital allocated to the strategy as a Decimal.
            Returns 0 if the strategy is not found (though this should ideally not happen
            if the strategy is part of the fund).
        """
        return self._allocations.get(strategy_name, Decimal("0"))

    @property
    def strategies(self) -> list[Strategy]:
        """Get the list of managed strategies."""
        return self._strategies

    @property
    def capital(self) -> Decimal:
        """Get the total capital of the fund."""
        return self._capital
