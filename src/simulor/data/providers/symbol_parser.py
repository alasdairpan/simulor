"""Symbol parsing utilities for extracting instrument metadata from symbol formats.

Supports industry-standard symbol formats:
- OCC Options: AAPL240119C00150000
- CME Futures: ESZ24, CLF25
- Forex: EUR/USD
- Crypto: BTC-USD
- Stocks: AAPL (default)
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from simulor.types import AssetType, OptionType

__all__ = ["parse_symbol"]


def parse_symbol(symbol: str) -> tuple[AssetType, dict[str, Any]]:
    """Parse symbol and extract asset type and metadata using industry standards.

    Supports:
    - OCC format for options: AAPL240119C00150000 (symbol + YYMMDD + C/P + strike*1000)
    - CME futures codes: ESZ24 (root + month code + year)
    - Forex pairs: EUR/USD
    - Crypto pairs: BTC-USD

    Args:
        symbol: Symbol string to parse

    Returns:
        Tuple of (AssetType, metadata_dict) where metadata contains:
        - For options: underlying, expiry, strike, option_type
        - For futures: underlying, expiry
        - For other types: empty dict

    Examples:
        >>> parse_symbol("AAPL240119C00150000")
        (AssetType.OPTION, {"underlying": "AAPL", "expiry": ..., "strike": 150.0, ...})
        >>> parse_symbol("ESZ24")
        (AssetType.FUTURE, {"underlying": "ES", "expiry": ...})
        >>> parse_symbol("BTC-USD")
        (AssetType.CRYPTO, {})
    """
    symbol = symbol.strip()
    metadata: dict[str, Any] = {}

    # OCC Options format: AAPL240119C00150000
    # Pattern: Root (1-6 chars) + YYMMDD (6 digits) + C/P + Strike (8 digits, price * 1000)
    if len(symbol) >= 15:
        # Try to extract OCC format
        try:
            # Find the position where digits start (expiry date)
            digit_start = next(i for i, c in enumerate(symbol) if c.isdigit())
            if digit_start > 0 and len(symbol) >= digit_start + 15:
                root = symbol[:digit_start]
                expiry_str = symbol[digit_start : digit_start + 6]
                option_type_char = symbol[digit_start + 6]
                strike_str = symbol[digit_start + 7 : digit_start + 15]

                if option_type_char in ("C", "P") and strike_str.isdigit():
                    # Parse expiry: YYMMDD
                    try:
                        expiry = datetime.strptime(expiry_str, "%y%m%d")
                    except ValueError:
                        # Invalid date (e.g., month > 12, day > 31)
                        pass
                    else:
                        # Validate expiry is within reasonable range
                        # Allow past dates for backtesting, but reject dates > 10 years forward
                        now = datetime.now()
                        max_future = now + timedelta(days=3650)  # 10 years forward
                        if expiry > max_future:
                            pass  # Too far in future, fall through to next parser
                        else:
                            # Parse strike: 8 digits represent price * 1000
                            strike = Decimal(strike_str) / 1000

                            # Validate strike price bounds ($0.01 to $1,000,000)
                            if not (Decimal("0.01") <= strike <= Decimal("1000000")):
                                pass  # Invalid strike, fall through
                            else:
                                # Parse option type
                                option_type = OptionType.CALL if option_type_char == "C" else OptionType.PUT

                                metadata["underlying"] = root
                                metadata["expiry"] = expiry
                                metadata["strike"] = strike
                                metadata["option_type"] = option_type
                                return AssetType.OPTION, metadata
        except (ValueError, StopIteration):
            pass

    # CME Futures format: ESZ24, CLF25, NQH26
    # Pattern: 1-3 letter root + month code (F,G,H,J,K,M,N,Q,U,V,X,Z) + 2-digit year
    # Length: 4-6 chars (1-letter root: 4 chars, 2-letter: 5 chars, 3-letter: 6 chars)
    if 4 <= len(symbol) <= 6:
        month_codes = "FGHJKMNQUVXZ"
        # Check if last 3 chars match pattern: [FGHJKMNQUVXZ][0-9]{2}
        if symbol[-3] in month_codes and symbol[-2:].isdigit() and symbol[:-3].isalpha() and symbol[:-3].isupper():
            root = symbol[:-3]
            month_code = symbol[-3]
            year_suffix = symbol[-2:]

            # Map month code to month number
            month_map = {
                "F": 1,
                "G": 2,
                "H": 3,
                "J": 4,
                "K": 5,
                "M": 6,
                "N": 7,
                "Q": 8,
                "U": 9,
                "V": 10,
                "X": 11,
                "Z": 12,
            }
            month = month_map[month_code]

            # Convert 2-digit year to 4-digit using 50-year sliding window
            # In 2025: "24" = 2024, "75" = 2075, "76" = 2076
            year_int = int(year_suffix)
            current_year = datetime.now().year
            current_century = (current_year // 100) * 100
            current_2digit = current_year % 100

            # If year is more than 50 years behind current year, assume next century
            year = current_century + 100 + year_int if year_int < current_2digit - 50 else current_century + year_int

            # Use 3rd Friday of expiry month as standard futures expiry
            # (This is typical for equity index futures)
            # Find first day of month
            first_day = datetime(year, month, 1)
            # Find first Friday (weekday 4 is Friday)
            days_until_friday = (4 - first_day.weekday()) % 7
            first_friday = first_day + timedelta(days=days_until_friday)
            # Third Friday is 14 days later
            third_friday = first_friday + timedelta(days=14)

            metadata["underlying"] = root
            metadata["expiry"] = third_friday
            return AssetType.FUTURE, metadata

    # Forex: Contains forward slash (e.g., "EUR/USD", "GBP/JPY")
    # Check before crypto to maintain correct precedence
    if "/" in symbol:
        return AssetType.FOREX, metadata

    # Crypto: Contains hyphen (e.g., "BTC-USD", "ETH-USDT")
    # More specific check: base currency should be uppercase and short
    if "-" in symbol:
        parts = symbol.split("-")
        if len(parts) == 2 and parts[0].isupper() and len(parts[0]) <= 5:  # BTC, ETH, etc.
            return AssetType.CRYPTO, metadata

    # Default to stock
    return AssetType.STOCK, metadata
