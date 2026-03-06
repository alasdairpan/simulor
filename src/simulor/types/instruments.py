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

    @property
    def multiplier(self) -> Decimal:
        """Contract multiplier used for notional and PnL calculations."""
        return self.contract_size or Decimal("1")

    def __hash__(self) -> int:
        """Compute hash using stable instrument identity fields."""
        return hash(self._identity_key())

    def __eq__(self, other: object) -> bool:
        """Compare instruments using stable instrument identity fields."""
        if not isinstance(other, Instrument):
            return NotImplemented
        return self._identity_key() == other._identity_key()

    def _identity_key(self) -> tuple[object, ...]:
        """Return the tuple used for equality and hashing."""
        if self.asset_type == AssetType.OPTION:
            return (
                self.asset_type,
                self.symbol,
                self.exchange,
                self.currency,
                self.expiry,
                self.strike,
                self.option_type,
            )
        return (self.asset_type, self.symbol)

    def __post_init__(self) -> None:
        """Validate instrument data."""
        if not self.symbol or not self.symbol.strip():
            raise ValueError("Symbol cannot be empty")

        # Keep current implementation scope explicit while enabling options.
        if self.asset_type not in (AssetType.STOCK, AssetType.OPTION):
            raise NotImplementedError(f"Asset type {self.asset_type.value} is not yet supported.")

        if self.asset_type == AssetType.OPTION:
            if self.expiry is None:
                raise ValueError("Option expiry is required")
            if self.strike is None or self.strike <= 0:
                raise ValueError("Option strike must be positive")
            if self.option_type is None:
                raise ValueError("Option type is required")
            if self.contract_size is None:
                object.__setattr__(self, "contract_size", Decimal("100"))
            elif self.contract_size <= 0:
                raise ValueError("Contract size must be positive")
        else:
            # STOCK validation: derivative fields are invalid.
            if self.expiry is not None:
                raise ValueError("Expiry is only valid for options")
            if self.strike is not None:
                raise ValueError("Strike price is only valid for options")
            if self.option_type is not None:
                raise ValueError("Option type is only valid for options")

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

    @classmethod
    def option(
        cls,
        underlying: str,
        expiry: datetime,
        strike: Decimal,
        option_type: OptionType,
        exchange: str | None = None,
        currency: str = "USD",
        tick_size: Decimal | None = None,
        contract_size: Decimal | None = Decimal("100"),
        symbol: str | None = None,
    ) -> Instrument:
        """Create an option instrument.

        By default a canonical OCC-style symbol is generated when `symbol`
        is not explicitly provided.
        """
        option_symbol = symbol or cls._to_occ_symbol(underlying=underlying, expiry=expiry, strike=strike, option_type=option_type)
        return cls(
            symbol=option_symbol,
            asset_type=AssetType.OPTION,
            exchange=exchange,
            currency=currency,
            tick_size=tick_size,
            expiry=expiry,
            strike=strike,
            option_type=option_type,
            contract_size=contract_size,
        )

    @staticmethod
    def _to_occ_symbol(underlying: str, expiry: datetime, strike: Decimal, option_type: OptionType) -> str:
        """Build OCC option symbol from components.

        Format: ROOT + YYMMDD + C/P + strike*1000 (8 digits).
        """
        cp = "C" if option_type == OptionType.CALL else "P"
        strike_millis = int((strike * Decimal("1000")).to_integral_value())
        return f"{underlying}{expiry.strftime('%y%m%d')}{cp}{strike_millis:08d}"
