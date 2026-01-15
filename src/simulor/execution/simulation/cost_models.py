"""Transaction cost model implementations.

Implements:
- FixedCommission: Fixed commission per trade
- PercentageFee: Percentage-based fees
- PerShareCommission: Per-share commission
- CostModel: Composite cost model combining multiple fee types
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal

__all__ = [
    "CostComponent",
    "FixedCommission",
    "PercentageFee",
    "PerShareCommission",
    "CostModel",
]


class CostComponent(ABC):
    """Base class for transaction cost components.

    Cost components calculate fees, commissions, or other transaction
    costs based on trade details.
    """

    @abstractmethod
    def calculate_cost(self, quantity: Decimal, price: Decimal) -> Decimal:
        """Calculate cost for a trade.

        Args:
            quantity: Trade quantity
            price: Execution price per unit

        Returns:
            Total cost in currency units
        """
        ...


class FixedCommission(CostComponent):
    """Fixed commission per trade.

    Charges a flat fee regardless of trade size. Common for discount
    brokers and certain institutional arrangements.

    Example:
        commission = FixedCommission(amount=Decimal("1.00"))
        cost = commission.calculate_cost(quantity=100, price=Decimal("50"))
        # Returns: 1.00 (flat fee)
    """

    def __init__(self, amount: Decimal, minimum: Decimal = Decimal("0")) -> None:
        """Initialize fixed commission model.

        Args:
            amount: Fixed commission amount per trade
            minimum: Minimum commission (default: 0)
        """
        if amount < 0:
            raise ValueError("Commission amount must be non-negative")
        if minimum < 0:
            raise ValueError("Minimum commission must be non-negative")

        self.amount = Decimal(amount)
        self.minimum = Decimal(minimum)

    def calculate_cost(self, quantity: Decimal, price: Decimal) -> Decimal:  # noqa: ARG002
        """Calculate fixed commission.

        Args:
            quantity: Trade quantity (unused for fixed commission)
            price: Execution price (unused for fixed commission)

        Returns:
            Fixed commission amount
        """
        return max(self.amount, self.minimum)


class PercentageFee(CostComponent):
    """Percentage-based fee on trade value.

    Charges a percentage of the total trade value. Common for FX,
    crypto exchanges, and some stock brokers.

    Example:
        fee = PercentageFee(rate=Decimal("0.001"))  # 0.1% = 10 bps
        cost = fee.calculate_cost(quantity=100, price=Decimal("50"))
        # Returns: 5.00 (0.1% of 5000)
    """

    def __init__(self, rate: Decimal, minimum: Decimal = Decimal("0")) -> None:
        """Initialize percentage fee model.

        Args:
            rate: Fee rate as decimal (e.g., 0.001 = 0.1% = 10 bps)
            minimum: Minimum fee amount (default: 0)
        """
        if rate < 0:
            raise ValueError("Fee rate must be non-negative")
        if rate > 1:
            raise ValueError("Fee rate must be <= 1.0 (100%)")
        if minimum < 0:
            raise ValueError("Minimum fee must be non-negative")

        self.rate = Decimal(rate)
        self.minimum = Decimal(minimum)

    def calculate_cost(self, quantity: Decimal, price: Decimal) -> Decimal:
        """Calculate percentage-based fee.

        Args:
            quantity: Trade quantity
            price: Execution price per unit

        Returns:
            Fee amount (rate * quantity * price), or minimum if higher
        """
        trade_value = abs(quantity) * price
        fee = trade_value * self.rate
        return max(fee, self.minimum)


class PerShareCommission(CostComponent):
    """Per-share commission model.

    Charges a fixed rate per share traded. Common for US equity brokers
    (e.g., $0.005 per share).

    Example:
        commission = PerShareCommission(rate=Decimal("0.005"), minimum=Decimal("1.00"))
        cost = commission.calculate_cost(quantity=100, price=Decimal("50"))
        # Returns: 1.00 (max of 0.50 calculated vs 1.00 minimum)
    """

    def __init__(self, rate: Decimal, minimum: Decimal = Decimal("0")) -> None:
        """Initialize per-share commission model.

        Args:
            rate: Commission per share
            minimum: Minimum commission per trade (default: 0)
        """
        if rate < 0:
            raise ValueError("Commission rate must be non-negative")
        if minimum < 0:
            raise ValueError("Minimum commission must be non-negative")

        self.rate = Decimal(rate)
        self.minimum = Decimal(minimum)

    def calculate_cost(self, quantity: Decimal, price: Decimal) -> Decimal:  # noqa: ARG002
        """Calculate per-share commission.

        Args:
            quantity: Trade quantity
            price: Execution price (unused)

        Returns:
            Commission (rate * quantity), or minimum if higher
        """
        commission = abs(quantity) * self.rate
        return max(commission, self.minimum)


class CostModel:
    """Composite cost model combining multiple fee types.

    Aggregates multiple cost components (commissions, fees, etc.) to
    calculate total transaction costs for a trade.

    Example:
        cost_model = CostModel(
            components=[
                PerShareCommission(rate=Decimal("0.005"), minimum=Decimal("1.00")),
                PercentageFee(rate=Decimal("0.0001"))  # 1 bps regulatory fee
            ]
        )
        total = cost_model.calculate_total_cost(quantity=100, price=Decimal("50"))
        # Returns: 1.50 (1.00 commission + 0.50 regulatory fee)
    """

    def __init__(self, components: list[CostComponent] | None = None) -> None:
        """Initialize composite cost model.

        Args:
            components: List of cost components to apply (default: empty)
        """
        self.components = components or []

    def add_component(self, component: CostComponent) -> None:
        """Add a cost component to the model.

        Args:
            component: Cost component to add
        """
        self.components.append(component)

    def calculate_total_cost(self, quantity: Decimal, price: Decimal) -> Decimal:
        """Calculate total transaction cost.

        Sums costs from all components.

        Args:
            quantity: Trade quantity
            price: Execution price per unit

        Returns:
            Total transaction cost
        """
        return sum([comp.calculate_cost(quantity=quantity, price=price) for comp in self.components], Decimal("0"))
