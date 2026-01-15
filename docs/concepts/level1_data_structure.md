# Level 1 Data Structure

## Components

**QuoteTick (BBO - Best Bid/Offer)**:

- Best bid price and size (where you can SELL)
- Best ask price and size (where you can BUY)
- Timestamp of quote update

**TradeTick (Last Sale)**:

- Last executed trade price
- Trade size (volume)
- Trade direction (if available)
- Timestamp of trade execution

## Data Structure

```python
# Level 1 QuoteTick
QuoteTick(
    timestamp=datetime(2024, 1, 15, 9, 30, 1, 523000),
    instrument=Instrument.from_symbol("AAPL"),
    resolution=Resolution.TICK,
    bid_price=Decimal("150.24"),  # Top of bid side
    bid_size=Decimal("500"),      # Volume at best bid
    ask_price=Decimal("150.26"),  # Top of ask side
    ask_size=Decimal("300")       # Volume at best ask
)

# Level 1 TradeTick
TradeTick(
    timestamp=datetime(2024, 1, 15, 9, 30, 1, 524000),
    instrument=Instrument.from_symbol("AAPL"),
    resolution=Resolution.TICK,
    price=Decimal("150.25"),  # Execution price
    size=Decimal("100")       # Trade volume
)
```

## What Level 1 Provides

- Bar aggregation: TradeTick → TradeBar, QuoteTick → QuoteBar
- Spread calculation: ask - bid
- Transaction cost estimation: slippage based on spread and volume
- Market state: knowing current tradeable prices
