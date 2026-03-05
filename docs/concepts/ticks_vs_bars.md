# Ticks vs Bars

## TradeTick (Raw Trade Event)

A single executed transaction in the market:

```python
TradeTick(
    timestamp=datetime(2024, 1, 15, 9, 30, 1, 523000),
    instrument=Instrument.stock("AAPL"),
    resolution=Resolution.TICK,
    price=Decimal("150.25"),    # Trade execution price
    size=Decimal("100")         # Number of shares/contracts
)
```

**What it represents**: One completed trade that already happened on the exchange. This is Level 1 trade data.

**When to use**: High-frequency strategies, tick-by-tick analysis, building custom aggregations.

---

## QuoteTick (Raw Quote Update - Level 1)

A single best bid/offer (BBO) update:

```python
QuoteTick(
    timestamp=datetime(2024, 1, 15, 9, 30, 1, 524000),
    instrument=Instrument.stock("AAPL"),
    resolution=Resolution.TICK,
    bid_price=Decimal("150.24"),    # Best bid price
    bid_size=Decimal("500"),        # Size at best bid
    ask_price=Decimal("150.26"),    # Best ask price
    ask_size=Decimal("300")         # Size at best ask
)
```

**What it represents**: The top of the order book at a specific moment. Every time the best bid or ask changes, you get a new QuoteTick. This is Level 1 quote data.

**When to use**: Spread analysis, realistic fill simulation, market-making strategies, understanding bid-ask dynamics.

**Key Difference from TradeTick**:

- TradeTick = trades that **already executed** (past events)
- QuoteTick = orders **waiting to execute** (current market state)
- QuoteTick shows where YOU can trade NOW (you buy at ask, sell at bid)

---

## TradeBar (Aggregated Trade Data)

OHLC aggregated from TradeTicks over a time window:

```python
TradeBar(
    timestamp=datetime(2024, 1, 15, 9, 30, 0),  # Bar start time
    instrument=Instrument.stock("AAPL"),
    resolution=Resolution.MINUTE,
    open=Decimal("150.25"),     # First trade price in period
    high=Decimal("150.32"),     # Highest trade price in period
    low=Decimal("150.20"),      # Lowest trade price in period
    close=Decimal("150.28"),    # Last trade price in period
    volume=Decimal("15000")     # Total shares traded in period
)
```

**What it represents**: Summary of all trades that occurred during a specific time window (1 minute, 1 hour, 1 day).

**When to use**: Most trading strategies (day trading, swing trading, trend following). Shows actual execution prices and trading volume.

**Important**:

- **Minute TradeBar**: Aggregates all TradeTicks from 09:30:00 to 09:30:59
- **Hourly TradeBar**: Aggregates all TradeTicks from 09:00:00 to 09:59:59
- **Daily TradeBar**: Aggregates all TradeTicks from market open to close

---

## QuoteBar (Aggregated Quote Data)

Bid/Ask OHLC aggregated from QuoteTicks over a time window:

```python
QuoteBar(
    timestamp=datetime(2024, 1, 15, 9, 30, 0),  # Bar start time
    instrument=Instrument.stock("AAPL"),
    resolution=Resolution.MINUTE,
    # Bid side (where you can SELL)
    bid_open=Decimal("150.24"),     # First BBO bid in period
    bid_high=Decimal("150.29"),     # Highest BBO bid in period
    bid_low=Decimal("150.22"),      # Lowest BBO bid in period
    bid_close=Decimal("150.27"),    # Last BBO bid in period
    # Ask side (where you can BUY)
    ask_open=Decimal("150.26"),     # First BBO ask in period
    ask_high=Decimal("150.31"),     # Highest BBO ask in period
    ask_low=Decimal("150.24"),      # Lowest BBO ask in period
    ask_close=Decimal("150.29")     # Last BBO ask in period
)
```

**What it represents**: Summary of how the bid-ask spread evolved during a specific time window. Shows where market participants were willing to buy/sell.

**When to use**: Realistic backtesting with spread costs, spread-based strategies, understanding liquidity conditions.

**Important**:

- **Minute QuoteBar**: Aggregates all QuoteTicks from 09:30:00 to 09:30:59
- **Hourly QuoteBar**: Aggregates all QuoteTicks from 09:00:00 to 09:59:59
- **Daily QuoteBar**: Aggregates all QuoteTicks from market open to close

---

## Data Type Relationships & Transformations

### The Data Pipeline

```text
RAW MARKET EVENTS (Tick Resolution - No Aggregation)
┌─────────────────┐              ┌─────────────────┐
│ TradeTick       │              │ QuoteTick       │
│   (Level 1)     │              │   (Level 1 BBO) │
├─────────────────┤              ├─────────────────┤
│ 09:30:01.001    │              │ 09:30:01.002    │
│ price=150.25    │              │ bid=150.24      │
│ size=100        │              │ ask=150.26      │
│                 │              │                 │
│ 09:30:01.105    │              │ 09:30:01.110    │
│ price=150.26    │              │ bid=150.25      │
│ size=200        │              │ ask=150.27      │
│                 │              │                 │
│ 09:30:01.234    │              │ 09:30:01.245    │
│ price=150.24    │              │ bid=150.24      │
│ size=150        │              │ ask=150.28      │
│                 │              │                 │
│ ... (1000+      │              │ ... (500+       │
│ trades/min)     │              │ quotes/min)     │
└────────┬────────┘              └────────┬────────┘
         │                                │
         │ AGGREGATE over time window     │ AGGREGATE over time window
         │ (1-min, 1-hour, 1-day)        │ (1-min, 1-hour, 1-day)
         ↓                                ↓
┌─────────────────┐              ┌─────────────────┐
│ TradeBar        │              │ QuoteBar        │
│   (1-minute)    │              │   (1-minute)    │
├─────────────────┤              ├─────────────────┤
│ timestamp:      │              │ timestamp:      │
│   09:30:00      │              │   09:30:00      │
│                 │              │                 │
│ open=150.25     │              │ bid_open=150.24 │
│ high=150.32     │              │ bid_high=150.29 │
│ low=150.20      │              │ bid_low=150.22  │
│ close=150.28    │              │ bid_close=150.27│
│ volume=15000    │              │                 │
│                 │              │ ask_open=150.26 │
│                 │              │ ask_high=150.31 │
│                 │              │ ask_low=150.24  │
│                 │              │ ask_close=150.29│
└─────────────────┘              └─────────────────┘
```

### Aggregation Rules

**TradeTick → TradeBar:**

1. Collect all TradeTick objects in time window [start, end)
2. **Open** = price of first TradeTick in window
3. **High** = maximum price of all TradeTicks in window
4. **Low** = minimum price of all TradeTicks in window
5. **Close** = price of last TradeTick in window
6. **Volume** = sum of all sizes in window

**QuoteTick → QuoteBar:**

1. Collect all QuoteTick objects in time window [start, end)
2. For **bid side**:
   - bid_open = bid_price of first QuoteTick
   - bid_high = maximum bid_price seen
   - bid_low = minimum bid_price seen
   - bid_close = bid_price of last QuoteTick
3. For **ask side**:
   - ask_open = ask_price of first QuoteTick
   - ask_high = maximum ask_price seen
   - ask_low = minimum ask_price seen
   - ask_close = ask_price of last QuoteTick
4. Optional: bid_volume/ask_volume = sum of sizes

---

## Why Both TradeBars AND QuoteBars?

### Problem 1: Different Markets Have Different Data

| Asset Class  | Trade Data Available?         | Quote Data Available?     |
| ------------ | ----------------------------- | ------------------------- |
| **Equities** | Yes (exchange trades)         | Yes (Level 1 BBO)         |
| **Forex**    | No (OTC, no central exchange) | Yes (market maker quotes) |
| **Futures**  | Yes (exchange trades)         | Yes (Level 1 BBO)         |
| **Crypto**   | Yes (exchange trades)         | Varies by exchange        |

**Implication**:

- For **Forex**, only QuoteBars exist at all resolutions (no TradeBars possible)
- For **Equities**, both TradeBars and QuoteBars available at all resolutions
- Framework must support both types to handle all asset classes

### Problem 2: Realistic Backtesting Requires Both

**Scenario**: You're backtesting an equity day-trading strategy using minute bars.

**With TradeBar Only (Unrealistic):**

```python
# At 09:30, you get minute TradeBar
trade_bar = TradeBar(..., close=Decimal("150.28"), volume=Decimal("15000"), ...)

# Your strategy generates BUY signal
# Question: What price do you assume you bought at?

# Wrong: Assume you bought at bar.close = $150.28
fill_price = trade_bar.close

# Problem: The "close" is the last TRADE price in that minute
# It could have been a seller hitting someone's bid!
# When YOU try to buy, you must hit the ASK, which might be $150.32
# You're giving yourself 4 cents of free profit per share!
```

**With TradeBar + QuoteBar (Realistic):**

```python
# At 09:30, you get BOTH bars for that minute
trade_bar = TradeBar(..., close=Decimal("150.28"), volume=Decimal("15000"), ...)
quote_bar = QuoteBar(..., bid_close=Decimal("150.27"), ask_close=Decimal("150.29"), ...)

# Your strategy generates BUY signal
# Question: What price do you actually fill at?

# Right: You buy at the ask (where market makers SELL to you)
fill_price = quote_bar.ask_close  # $150.29

# You pay the spread: $150.29 - $150.28 = $0.01 per share
# On 1000 shares: $10 transaction cost
# Over 100 trades: $1000 difference in backtest P&L!

# Plus: Check liquidity
if trade_bar.volume < 10000:
    skip()  # Not enough volume, might not fill your 500 share order
```

### Problem 3: Different Strategies Need Different Data

#### Example A: Trend Following (Long-term)

```python
# Uses Daily TradeBars only
def on_data(self, event: MarketEvent):
    for instrument in event.instruments():
        trade_bar = event.get_min_res_trade_bar(instrument)
        if trade_bar and trade_bar.resolution == Resolution.DAILY:
            if trade_bar.close > self.sma_200:
                self.buy_signal()
```

- **Needs**: TradeBar for price trends and volume
- **Doesn't need**: QuoteBar (spread irrelevant for long-term holds)

#### Example B: Market Making (High-frequency)

```python
# Uses Minute QuoteBars only
def on_data(self, event: MarketEvent):
    for instrument in event.instruments():
        quote_bar = event.get_min_res_quote_bar(instrument)
        if quote_bar:
            spread = quote_bar.ask_close - quote_bar.bid_close
            if spread > Decimal("0.10"):  # Wide spread = opportunity
                self.place_limit_order(quote_bar.bid_close + Decimal("0.05"))
```

- **Needs**: QuoteBar for spread analysis
- **Doesn't need**: TradeBar (cares about quotes, not trade flow)

#### Example C: Realistic Day Trading

```python
# Uses BOTH Minute TradeBars and QuoteBars
def on_data(self, event: MarketEvent):
    if self.signal_to_buy:
        for instrument in event.instruments():
            trade_bar = event.get_min_res_trade_bar(instrument)
            # Check liquidity from TradeBar
            if trade_bar and trade_bar.volume < self.avg_volume * Decimal("0.5"):
                return  # Too illiquid

            # Fill at realistic price from QuoteBar
            quote_bar = event.get_min_res_quote_bar(instrument)
            if quote_bar:
                fill_price = quote_bar.ask_close
                spread_cost = quote_bar.ask_close - quote_bar.bid_close
```

- **Needs**: Both types for realistic simulation

---

## Summary: When to Use Each Data Type

| Data Type     | Resolution        | Use Case                         | Example                                    |
| ------------- | ----------------- | -------------------------------- | ------------------------------------------ |
| **TradeTick** | Tick              | HFT, custom tick aggregation     | Real-time market making                    |
| **QuoteTick** | Tick              | HFT, spread strategies           | Liquidity provision                        |
| **TradeBar**  | Minute/Hour/Daily | Price trends, volume analysis    | Most strategies (EMA crossover, breakouts) |
| **QuoteBar**  | Minute/Hour/Daily | Realistic fills, spread analysis | Day trading with realistic costs           |
| **Both Bars** | Minute/Hour/Daily | Complete backtesting             | Any strategy needing realistic simulation  |

**Key Principle**:

- TradeTick/QuoteTick = **raw events** (what actually happened in market)
- TradeBar/QuoteBar = **aggregated summaries** (what happened over a time window)
- TradeBar = **where trades executed** (actual prices)
- QuoteBar = **where market quotes were** (available prices for YOU to trade at)
