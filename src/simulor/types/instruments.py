"""Instrument type definitions.

This module defines Instrument and related types with NO imports from simulor packages.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from simulor.types.common import AssetType, OptionType

__all__ = ["Instrument"]


@dataclass(frozen=True)
class Instrument:
    """Financial instrument identifier.

    Represents any tradeable financial instrument with support for stocks,
    futures, options, crypto, forex, and bonds.

    Attributes:
        symbol: Base symbol identifier (e.g., "AAPL", "BTC", "ES")
        asset_type: Type of financial asset
        exchange: Exchange or venue (e.g., "NASDAQ", "CME", "BINANCE")
        currency: Quote currency (default: "USD")
        expiry: Expiration date for derivatives (futures, options)
        strike: Strike price for options
        option_type: CALL or PUT for options
        contract_size: Contract multiplier for futures/options
        tick_size: Minimum price increment
    """

    symbol: str
    asset_type: AssetType
    exchange: str | None = None
    currency: str = "USD"
    tick_size: Decimal | None = None

    # Derivative-specific fields
    expiry: datetime | None = None
    strike: Decimal | None = None
    option_type: OptionType | None = None

    # Contract specifications
    contract_size: Decimal | None = None

    def __hash__(self) -> int:
        """Compute hash based on symbol only."""
        return hash(self.symbol)

    def __eq__(self, other: object) -> bool:
        """Compare instruments based on symbol only."""
        if not isinstance(other, Instrument):
            return NotImplemented
        return self.symbol == other.symbol

    def __post_init__(self) -> None:
        """Validate instrument data."""
        if not self.symbol or not self.symbol.strip():
            raise ValueError("Symbol cannot be empty")

        if self.asset_type != AssetType.STOCK:
            raise NotImplementedError(f"Asset type {self.asset_type.value} is not yet supported.")

        # Validate non-derivative fields
        if self.asset_type not in (AssetType.OPTION, AssetType.FUTURE) and self.strike is not None:
            raise ValueError(f"Strike price only valid for options, not {self.asset_type.value}")
        if self.asset_type not in (AssetType.OPTION, AssetType.FUTURE) and self.option_type is not None:
            raise ValueError(f"Option type only valid for options, not {self.asset_type.value}")

    @property
    def is_derivative(self) -> bool:
        """Check if this is a derivative instrument."""
        return self.asset_type in (AssetType.OPTION, AssetType.FUTURE)

    @property
    def display_name(self) -> str:
        """Generate human-readable display name."""
        parts = [self.symbol]

        if self.asset_type == AssetType.OPTION:
            expiry_str = self.expiry.strftime("%y%m%d") if self.expiry else "?"
            opt_type = "C" if self.option_type == OptionType.CALL else "P"
            parts.append(f"{expiry_str}{opt_type}{self.strike}")
        elif self.asset_type == AssetType.FUTURE and self.expiry:
            parts.append(self.expiry.strftime("%b%y"))

        if self.exchange:
            parts.append(f"@{self.exchange}")

        return "_".join(parts)

    @classmethod
    def stock(
        cls,
        symbol: str,
        exchange: str | None = None,
        currency: str = "USD",
        tick_size: Decimal | None = None,
    ) -> Instrument:
        """Create a stock instrument."""
        return cls(
            symbol=symbol,
            asset_type=AssetType.STOCK,
            exchange=exchange,
            currency=currency,
            tick_size=tick_size,
        )
