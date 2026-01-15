# Data

The data module is responsible for acquiring, processing, and serving market data to the backtesting engine. It ensures data integrity, handles multiple formats, and provides a unified interface for various asset classes.

## Table of Contents

- [Core Data Features](#core-data-features)
  - [Multi-Resolution Support](#multi-resolution-support)
  - [Multi-Asset Support](#multi-asset-support)
  - [Corporate Actions](#corporate-actions)
  - [Market Hours Modeling](#market-hours-modeling)
  - [Data Loading & Multi-Source Integration](#data-loading--multi-source-integration)
- [Data Quality & Validation](#data-quality--validation)
  - [Data Cleaning & Validation](#data-cleaning--validation)
  - [Survivorship Bias Handling](#survivorship-bias-handling)
  - [Look-Ahead Bias Prevention](#look-ahead-bias-prevention)
- [Advanced Market Data](#advanced-market-data)
  - [Level 1 Market Data (Primary Support)](#level-1-market-data-primary-support)
  - [Level 2 Market Data (Future Extension)](#level-2-market-data-future-extension)
  - [Level 3 Market Data (Future Extension - Advanced HFT Only)](#level-3-market-data-future-extension---advanced-hft-only)
  - [Market Data Levels Summary](#market-data-levels-summary)
  - [Alternative Data](#alternative-data)
  - [Fundamental Data](#fundamental-data)
  - [Options Market Data](#options-market-data)
- [Technical Infrastructure](#technical-infrastructure)
  - [Data Caching & Persistence](#data-caching--persistence)
  - [Real-Time Data Feeds](#real-time-data-feeds)
  - [Data Version Control](#data-version-control)
  - [Compression & Storage Optimization](#compression--storage-optimization)
- [Risk & Compliance Data](#risk--compliance-data)
  - [Benchmark Data](#benchmark-data)
  - [Risk-Free Rates](#risk-free-rates)
  - [Currency Exchange Rates](#currency-exchange-rates)
  - [Regulatory Calendar](#regulatory-calendar)

---

## Core Data Features

### Multi-Resolution Support

Simulor supports multiple time resolutions through two fundamental data structures:

#### Tick-Level Data (Raw Events - No Aggregation)

- **TradeTick**: Individual executed trades as they occur
- **QuoteTick**: Best bid/offer (BBO) updates at Level 1

#### Bar-Level Data (Time-Aggregated OHLC)

- **TradeBar**: Aggregated OHLC from TradeTicks over a time window
- **QuoteBar**: Aggregated bid/ask OHLC from QuoteTicks over a time window
- Supported resolutions: **Minute** (1-min), **Hourly** (1-hour), **Daily** (EOD)

Each resolution type supports only its base interval (1-minute, 1-hour, daily). Custom intervals (5-minute, 15-minute, 4-hour) are **not supported** for simplicity. Users requiring multiple timeframes should subscribe to multiple resolutions or perform their own aggregation externally.

**Design Decision**: We separate tick-level (TradeTick/QuoteTick) from bar-level (TradeBar/QuoteBar) data structures. At tick resolution, you receive individual market events. At minute/hourly/daily resolutions, you receive pre-aggregated bars.

**Rationale**: Different strategies operate at different frequencies. HFT/market making requires tick data, day trading uses minute bars, swing trading uses hourly/daily data. Limiting to base resolutions reduces complexity and maintains a clean, predictable data interface. Second bars are omitted as they are rarely used in practice.

📖 Detailed Explanation: [Ticks vs Bars](../concepts/ticks_vs_bars.md)

---

### Multi-Asset Support

Unified data interface across various asset classes:

- **Equities**: Stocks, ETFs, ADRs
- **Options**: Calls, puts, American/European style
- **Futures**: Commodities, indices, interest rates
- **Forex**: Spot FX pairs, crosses
- **Cryptocurrency**: Spot and perpetual futures
- **CFDs**: Contract for Difference instruments
- **Fixed Income**: Bonds, treasuries (future extension)

**Rationale**: Modern portfolios are multi-asset. The framework should handle different instrument characteristics (e.g., options expiry, futures roll dates).

### Corporate Actions

Accurate handling of corporate events affecting price and position calculations:

- **Stock splits**: Forward and reverse splits with automatic price/quantity adjustments
- **Dividends**: Cash and stock dividends, ex-dividend date tracking
- **Mergers & Acquisitions**: Stock conversions, cash-stock combinations
- **Spin-offs**: New entity creation and position allocation
- **Rights issues**: Subscription rights and dilution effects
- **Special distributions**: One-time payments, return of capital

**Rationale**: Ignoring corporate actions leads to significant backtest inaccuracies. A $100 stock that splits 10:1 should be $10, not appear as a 90% loss.

### Market Hours Modeling

Realistic simulation of trading sessions and calendar effects:

- **Regular trading hours**: Exchange-specific opening/closing times
- **Extended hours**: Pre-market and after-hours sessions
- **Market holidays**: Exchange holiday calendars (NYSE, NASDAQ, LSE, etc.)
- **Early closes**: Half-day trading sessions
- **Multiple timezones**: Convert and synchronize data across global markets
- **Auction periods**: Opening/closing auctions, circuit breakers
- **Settlement calendars**: Track business days for T+1/T+2/T+3 settlement calculations

**Rationale**: Orders placed outside market hours behave differently. Holiday effects and timezone alignment are critical for multi-market strategies. Settlement calendars ensure accurate cash availability modeling.

### Data Loading & Multi-Source Integration

Flexible data ingestion from various sources and formats:

- **File formats**: CSV, Parquet, HDF5, Feather
- **Databases**: PostgreSQL, MySQL, SQLite, TimescaleDB
- **Cloud storage**: S3, Google Cloud Storage, Azure Blob
- **APIs**: REST and WebSocket data vendors
- **Multi-vendor aggregation**: Combine and normalize data from multiple providers
- **Custom loaders**: Plugin architecture for proprietary data sources

**Rationale**: Users have data in different formats. Multi-vendor support allows filling gaps and cross-validation.

## Data Quality & Validation

### Data Cleaning & Validation

Automated detection and handling of data quality issues:

- **Missing data detection**: Identify gaps in time series
- **Outlier detection**: Statistical methods to flag anomalous prices
- **Bad tick filtering**: Remove erroneous trades (e.g., stub quotes)
- **Data consistency checks**: Validate OHLC relationships (High ≥ Close ≥ Low)
- **Volume validation**: Detect zero or negative volume anomalies
- **Configurable handling**: Fill, interpolate, or flag missing data

**Rationale**: Real-world data is messy. Bad data leads to unrealistic backtest results and false signals.

### Survivorship Bias Handling

Include complete universe of securities including delisted/bankrupt instruments:

- **Delisting tracking**: Maintain data for securities removed from exchanges
- **Bankruptcy records**: Include companies that went bankrupt
- **Complete historical universe**: Point-in-time composition of indices/ETFs
- **Ticker changes**: Track symbol changes over time

**Rationale**: Only using currently-traded securities inflates returns. Survivorship bias is one of the most common backtest errors.

### Look-Ahead Bias Prevention

Ensure data reflects information available only at that point in time:

- **Point-in-time data**: No future information leakage
- **As-of timestamps**: Data versioning with revision tracking
- **Restated data handling**: Flag and manage financial restatements
- **Split-adjusted data**: Ensure adjustments don't use future information
- **Timestamp validation**: Verify data alignment across sources

**Rationale**: Using revised or future data creates unrealistic results. Strategies must use only information available at execution time.

## Advanced Market Data

### Level 1 Market Data (Primary Support)

**Simulor's Foundation**: Level 1 market data is the **primary focus** and fully supported from day one.

**What is Level 1?**
Level 1 represents the **top-of-book** market data consisting of:

- **QuoteTick (BBO)**: Best bid price/size and best ask price/size
- **TradeTick (Last Sale)**: Last executed trade price, size, and direction

**Why Level 1 is Sufficient**:

- ✅ Covers 95%+ of retail and institutional trading strategies
- ✅ Day trading, swing trading, trend following strategies
- ✅ Realistic fill simulation with spread costs
- ✅ Basic slippage and transaction cost modeling
- ✅ Available from nearly all data providers
- ✅ Manageable data volumes (MBs per day)

📖 Detailed Explanation: [Level 1 Data Structure](../concepts/level1_data_structure.md)

---

### Level 2 Market Data (Future Extension)

**Status**: L2 matching model is **implemented** in the execution layer, but Level 2 market data feeds may not be included in the initial framework release.

**What is Level 2?**
Level 2 shows **aggregated order book depth** beyond the best bid/offer (typically 5-20 price levels on each side).

**Level 2 Use Cases**:

- ✅ Market making with depth analysis
- ✅ Order book imbalance strategies
- ✅ Large order execution simulation (market impact)
- ✅ Realistic slippage for large trades
- ✅ Liquidity analysis beyond top-of-book

**Design Decision**: Level 2 **matching engine is implemented** but requires L2 data which may not be available initially. The execution layer (`L2MatchingModel`) is ready to use when L2 data becomes available.

**Data Availability**: Check with your data provider for Level 2 market data availability. Common sources include exchange direct feeds, institutional data vendors, and specialized tick data providers.

📖 Detailed Explanation: [Level 2 Order Book](../concepts/level2_order_book.md)

---

### Level 3 Market Data (Future Extension - Advanced HFT Only)

**Status**: Planned for potential future implementation if specialized HFT strategies are needed.

**What is Level 3?**
Level 3 shows **individual order IDs** in the book (market-by-order) with order lifecycle tracking.

**Level 3 Use Cases**:

- ✅ True HFT market making with queue position
- ✅ FIFO queue modeling for order priority
- ✅ Latency arbitrage strategies
- ✅ Exchange microstructure research

**Level 3 Challenges**:

- ❌ Extremely high data volume (GBs per day per symbol)
- ❌ Requires specialized storage and infrastructure
- ❌ Very expensive data feeds
- ❌ Only available for specific exchanges

**Design Decision**: Level 3 is **future consideration only**. The complexity and data requirements are only justified for specialized HFT strategies.

📖 Detailed Explanation: [Level 3 Market-By-Order](../concepts/level3_market_by_order.md)

---

### Market Data Levels Summary

| Level       | Data Type              | Structure          | Can Aggregate to Bar?   | Simulor Support       |
| ----------- | ---------------------- | ------------------ | ----------------------- | --------------------- |
| **Level 1** | QuoteTick (BBO)        | Scalar (2 prices)  | Yes → QuoteBar          | **Primary Support**   |
| **Level 1** | TradeTick (Trades)     | Scalar (1 price)   | Yes → TradeBar          | **Primary Support**   |
| **Level 2** | Order Book Depth       | Multi-dimensional  | No (store snapshots)    | **Future Extension**  |
| **Level 3** | Market-By-Order        | Order event stream | No (process events)     | **Potential Future**  |

**Recommendation for Users**:

- Start with **Level 1** data (QuoteTick/TradeTick → QuoteBar/TradeBar)
- This covers 95%+ of strategies
- Only consider Level 2 if you need depth-based analysis
- Only consider Level 3 if you're building true HFT with queue modeling

---

### Alternative Data

Non-traditional data sources for alpha generation:

- **News sentiment**: Real-time news feeds with NLP sentiment scores
- **Social media**: Twitter/Reddit sentiment and volume
- **Economic indicators**: GDP, employment, inflation data
- **Web traffic**: Site visits, app downloads
- **Satellite imagery**: Retail parking lots, shipping activity
- **Custom signals**: User-defined alternative data integration

**Rationale**: Modern quant strategies increasingly rely on alternative data. Framework should support integration.

### Fundamental Data

Company financials and derived metrics:

- **Financial statements**: Income statement, balance sheet, cash flow
- **Financial ratios**: P/E, P/B, ROE, debt ratios
- **Earnings data**: EPS, revenue, guidance
- **Analyst estimates**: Consensus forecasts and revisions
- **Ownership data**: Institutional holdings, insider transactions
- **Point-in-time availability**: Ensure fundamentals reflect reporting dates

**Rationale**: Value and fundamental strategies require financial data. Must respect reporting lag.

### Options Market Data

Comprehensive options data for derivatives strategies:

- **Options chains**: Complete strike/expiry grid
- **Greeks**: Delta, gamma, theta, vega, rho
- **Implied volatility**: Strike-level IV and surfaces
- **Open interest**: Track liquidity and positioning
- **Early exercise handling**: American option exercise simulation
- **Volatility surfaces**: 3D IV surfaces over strike and time

**Rationale**: Options strategies require rich derivatives data. Greeks and IV are essential for risk management.

## Technical Infrastructure

### Data Caching & Persistence

Efficient data storage and retrieval:

- **In-memory caching**: Fast access to frequently used data
- **Disk caching**: Persistent cache for large datasets
- **Lazy loading**: Load data on-demand to minimize memory
- **Incremental updates**: Update only new/changed data
- **Cache invalidation**: Smart cache refresh strategies
- **Compression**: Reduce storage footprint

**Rationale**: Backtests load same data repeatedly. Caching dramatically improves performance.

### Real-Time Data Feeds

Live market data integration for paper trading and live execution:

- **WebSocket connections**: Real-time streaming data
- **REST API polling**: Periodic data updates
- **Tick-by-tick ingestion**: Process live market ticks
- **Backtest-to-live consistency**: Same interface for historical and live data
- **Connection management**: Automatic reconnection and error handling

**Rationale**: Seamless transition from backtest to paper trading to live trading requires unified data interface.

### Data Version Control

Track data changes and maintain reproducibility:

- **Version tracking**: Log data updates and revisions
- **Audit trail**: Record data source and timestamp
- **Snapshot capability**: Save data state for exact backtest reproduction
- **Rollback support**: Revert to previous data versions
- **Change detection**: Identify what data changed between versions

**Rationale**: Data vendors correct errors. Reproducible backtests require knowing exact data version used.

### Compression & Storage Optimization

Handle large datasets efficiently:

- **Columnar storage**: Parquet/Arrow for analytical queries
- **Time-series databases**: Optimized for temporal data
- **Data partitioning**: By date, symbol, or asset class
- **Sampling strategies**: Downsample for faster iteration
- **Storage backends**: Local, network, and cloud storage support

**Rationale**: Years of tick data for thousands of symbols can be terabytes. Efficient storage is critical.

## Risk & Compliance Data

### Benchmark Data

Reference indices for performance comparison:

- **Index compositions**: Historical constituent lists
- **Index weights**: Market-cap or equal-weighted
- **Total return indices**: Include dividend reinvestment
- **Custom benchmarks**: User-defined comparison portfolios
- **Rebalancing dates**: Track index reconstitution

**Rationale**: Strategies are evaluated against benchmarks. Accurate benchmark data is essential for alpha calculation.

### Risk-Free Rates

Reference rates for risk metrics:

- **Treasury yields**: Government bond yields across maturities
- **Interbank rates**: LIBOR (historical), SOFR, EURIBOR
- **Central bank rates**: Fed funds, ECB rates
- **Term structure**: Full yield curve data
- **Historical rates**: Long history for Sharpe ratio calculations

**Rationale**: Sharpe ratio, beta, and many risk metrics require risk-free rate. Must match backtest period and currency.

### Currency Exchange Rates

Multi-currency portfolio support:

- **FX spot rates**: Real-time and historical exchange rates
- **Cross rates**: All major and minor currency pairs
- **FX forwards**: Forward rates for hedging simulation
- **Base currency conversion**: Normalize all returns to single currency
- **Intraday FX**: Align FX rates with trade timestamps

**Rationale**: Global portfolios require currency conversion. FX movements affect returns and must be tracked.

### Regulatory Calendar

Important dates affecting trading and corporate events:

- **Earnings dates**: Scheduled and actual earnings announcements
- **Ex-dividend dates**: Dividend payment timeline
- **Options expiry**: Monthly/weekly expiration dates
- **Futures roll dates**: Contract expiration and rollover
- **Lock-up expirations**: IPO/secondary offering restrictions
- **Conference schedules**: Fed meetings, ECB announcements

**Rationale**: Many strategies avoid/target specific dates. Earnings and expiry dates create volatility and liquidity patterns.
