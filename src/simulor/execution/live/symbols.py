"""Symbol conversion utilities for Longbridge broker.

This module provides stateless helpers for converting between Simulor's
Instrument type and Longbridge's symbol format (e.g. ``700.HK``).
"""

from __future__ import annotations

from simulor.types import Instrument

_REGION_CURRENCY: dict[str, str] = {
    "HK": "HKD",
    "US": "USD",
    "SH": "CNY",
    "SZ": "CNY",
    "SG": "SGD",
}

__all__ = ["instrument_to_longbridge_symbol", "longbridge_symbol_to_instrument"]


def instrument_to_longbridge_symbol(instrument: Instrument) -> str:
    """Convert a Simulor Instrument to a Longbridge symbol (e.g. ``700.HK``).

    Raises:
        ValueError: if the instrument has no exchange or the exchange is not supported.
    """
    exchange_map = {
        "HKEX": "HK",
        "HK": "HK",
        "NYSE": "US",
        "NASDAQ": "US",
        "US": "US",
        "SSE": "SH",
        "SH": "SH",
        "SZSE": "SZ",
        "SZ": "SZ",
        "SGX": "SG",
        "SG": "SG",
    }
    if not instrument.exchange:
        raise ValueError(f"Instrument {instrument.symbol!r} has no exchange set.")
    region = exchange_map.get(instrument.exchange)
    if region is None:
        raise ValueError(f"Unsupported exchange for Longbridge: {instrument.exchange!r}")
    return f"{instrument.symbol}.{region}"


def longbridge_symbol_to_instrument(symbol: str, currency: str | None = None) -> Instrument:
    """Convert a Longbridge symbol (e.g. ``700.HK``) to a Simulor Instrument.

    Args:
        symbol: Longbridge symbol in ``TICKER.REGION`` format.
        currency: ISO currency code. When omitted, the correct default for the
            region is used (e.g. ``'HKD'`` for ``HK``, ``'USD'`` for ``US``).

    Raises:
        ValueError: if the symbol format is invalid or the region is not supported.
    """
    parts = symbol.split(".", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid Longbridge symbol format: {symbol!r}. Expected 'TICKER.REGION'.")
    ticker, region = parts
    exchange_map = {
        "HK": "HKEX",
        "US": "NASDAQ",
        "SH": "SSE",
        "SZ": "SZSE",
        "SG": "SGX",
    }
    exchange = exchange_map.get(region)
    if exchange is None:
        raise ValueError(f"Unsupported Longbridge region: {region!r} in symbol {symbol!r}")
    resolved_currency = currency if currency is not None else _REGION_CURRENCY.get(region)
    if resolved_currency is None:
        raise ValueError(f"Unsupported Longbridge region: {region!r} in symbol {symbol!r}")
    return Instrument.stock(
        symbol=ticker,
        exchange=exchange,
        currency=resolved_currency,
    )
