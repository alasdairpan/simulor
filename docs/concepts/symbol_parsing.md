# Industry-Standard Symbol Parsing

## Overview

The CSVDataProvider now automatically parses industry-standard symbol formats to extract instrument metadata, eliminating the need for separate columns for expiration dates, strike prices, and other derivative-specific data.

## Supported Formats

### 1. **Stocks** (Default)

- Format: `AAPL`, `MSFT`, `TSLA`
- No special parsing needed

### 2. **Cryptocurrency**

- Format: `BTC-USD`, `ETH-USDT`
- Pattern: Base currency + hyphen + quote currency

### 3. **Forex**

- Format: `EUR/USD`, `GBP/JPY`
- Pattern: Base currency + slash + quote currency

### 4. **CME Futures**

- Format: `ESZ24`, `CLF25`, `NQH26`
- Pattern: Root symbol (1-3 letters) + month code + 2-digit year
- Month codes:
  - F = January, G = February, H = March, J = April
  - K = May, M = June, N = July, Q = August
  - U = September, V = October, X = November, Z = December
- Example: `ESZ24` = E-mini S&P 500 December 2024 contract
- Expiry: Automatically set to 3rd Friday of expiry month

### 5. **OCC Options**

- Format: `AAPL240119C00150000`, `SPY240315P00450000`
- Pattern: Root symbol + YYMMDD + C/P + 8-digit strike (price × 1000)
- Example: `AAPL240119C00150000` = AAPL Call option, Jan 19, 2024, $150 strike
- Components:
  - Root: `AAPL`
  - Expiry: `240119` (Jan 19, 2024)
  - Type: `C` (Call) or `P` (Put)
  - Strike: `00150000` ($150.00)

## Usage Examples

### Basic Usage (CSV with symbols only)

```python
from simulor.data import CSVDataProvider

# CSV contains: timestamp,symbol,open,high,low,close,volume
provider = CSVDataProvider("options.csv")

# Symbols are automatically parsed:
# - AAPL240119C00150000 → AAPL call option, strike $150, expiry Jan 19, 2024
# - ESZ24 → ES futures, expiry December 20, 2024
# - BTC-USD → Bitcoin cryptocurrency
# - EUR/USD → Euro/Dollar forex pair

for data in provider.load():
    print(f"{data.instrument.symbol} ({data.instrument.asset_type.value})")
    if data.instrument.expiry:
        print(f"  Expiry: {data.instrument.expiry}")
    if data.instrument.strike:
        print(f"  Strike: ${data.instrument.strike}")
```

### With Optional Instrument Type Column

```python
# CSV contains: timestamp,symbol,instrument_type,open,high,low,close,volume
provider = CSVDataProvider("mixed.csv", instrument_type_column="instrument_type")

# The instrument_type column is optional:
# - If present and valid: overrides symbol inference
# - If missing or invalid: falls back to symbol parsing
# - Metadata is always extracted from symbol format
```

### Sample CSV Files

**Futures example (`futures.csv`):**

```csv
timestamp,symbol,open,high,low,close,volume
2024-01-02,ESH24,4800.0,4850.0,4790.0,4825.0,100000
2024-01-02,ESM24,4805.0,4855.0,4795.0,4830.0,90000
2024-01-02,NQZ24,16500.0,16600.0,16450.0,16550.0,50000
```

**Options example (`options.csv`):**

```csv
timestamp,symbol,open,high,low,close,volume
2024-01-02,AAPL240119C00150000,5.0,5.5,4.8,5.2,1000
2024-01-02,AAPL240119P00145000,3.0,3.2,2.8,3.1,800
2024-01-02,SPY240315C00450000,10.0,11.0,9.5,10.5,5000
```

**Mixed assets example (`mixed.csv`):**

```csv
timestamp,symbol,open,high,low,close,volume
2024-01-02,AAPL,180.0,182.0,179.0,181.0,1000000
2024-01-02,BTC-USD,45000.0,46000.0,44000.0,45500.0,100.5
2024-01-02,EUR/USD,1.0950,1.0980,1.0940,1.0970,50000000
2024-01-02,ESZ24,4800.0,4850.0,4790.0,4825.0,100000
2024-01-02,AAPL240119C00150000,5.0,5.5,4.8,5.2,1000
```

## Known Limitations

### Year Ambiguity

- **CME Futures**: 2-digit years use a 50-year sliding window
  - In 2025: "24" = 2024, "75" = 2075, "76" = 2076
  - Years less than (current_year % 100) are interpreted as next century if difference > 50
- **OCC Options**: 6-digit date format (YYMMDD) assumes 21st century (2000-2099)
  - Will need format update before year 2100

### Symbol Parsing Precedence

To avoid ambiguity, symbols are checked in this order:

1. **OCC Options** (most specific: 21+ chars with YYMMDD pattern)
2. **CME Futures** (specific: 4-5 chars with month code + 2 digits)
3. **Cryptocurrency** (contains hyphen: `BTC-USD`)
4. **Forex** (contains slash: `EUR/USD`)
5. **Stock** (fallback: any other format)

### Validation Rules

- **Strike prices**: Must be between $0.01 and $1,000,000
- **Expiry dates**: Must be within 10 years forward from current date
- **Month codes**: Must be valid CME codes (F,G,H,J,K,M,N,Q,U,V,X,Z)
- **Dates**: Must represent valid calendar dates

### CME Expiry Assumptions

- **Standard contracts**: Expire on 3rd Friday of contract month
- **Non-standard contracts**: May have different expiry schedules (not currently supported)
- **Early termination**: Settlement dates may differ from expiry dates

### Future Format Extensions

The following formats are not yet implemented but can be added as needed:

#### OPRA 21-Character Options

- Format: `AAPL  240119C00150000` (6-char padded root + space + standard OCC format)
- **Solution**: Add regex pattern matching 21-char format before OCC check
- **Priority**: Medium - less common than OCC format

#### Weekly/Quarterly Options

- Weeklys: Same OCC format but non-monthly expiration dates
- Quarterlys: End-of-quarter expirations
- **Solution**: Already supported by OCC date parsing (YYMMDD handles any date)
- **Status**: Works automatically, just document it

#### European Derivatives (EUREX)

- Format varies: `ODAX`, `OGBL`, etc. with specific month/year codes
- **Solution**: Add EUREX-specific parser with regional month code mappings
- **Priority**: Low - requires European market data

#### Asian Derivatives

##### SGX (Singapore Exchange)

- Format: `NKH25`, `CNZ24` (same as CME: root + month code + 2-digit year)
- Examples: `NK` = Nikkei 225, `CN` = USD/CNH
- **Solution**: Already compatible with existing CME parser, just add SGX root symbols to registry

##### HKEX (Hong Kong Exchange)

- Format: `HSIZ4` or `HSIZ24` (supports both 1-digit and 2-digit years)
- **Solution**: Extend CME parser regex to accept optional single digit: `^(\w{1,3})([FGHJKMNQUVXZ])(\d{1,2})$`

##### JPX (Japan Exchange)

- Format: `NK24M` (reversed: root + year + month code)
- Month code comes AFTER year (opposite of Western convention)
- **Solution**: Add JPX-specific parser before CME check:

  ```python
  # Pattern: root + 2-digit year + month code
  if re.match(r'^\w{1,3}\d{2}[FGHJKMNQUVXZ]$', symbol):
      root = symbol[:-3]
      year = symbol[-3:-1]
      month_code = symbol[-1]
      # Parse using same month code mapping as CME
  ```

- **Precedence**: Check JPX format after OCC options, before standard CME

**Implementation Priority**: Low - most Asian exchanges now support ISO/Western formats, and `instrument_type_column` can override when needed

#### Fixed Income Instruments

- Bonds: `US10Y`, `T 4.5 02/15/25` (CUSIP-based)
- **Solution**: Add bond-specific parser with maturity date extraction
- **Priority**: Medium - useful for multi-asset strategies

#### Custom Expiration Schedules

- Non-standard expiry dates (e.g., last trading day vs. 3rd Friday)
- **Solution**: Add optional `expiry_override` column in CSV or config file mapping
- **Priority**: High - affects accuracy for certain contracts

## Fallback Behavior

1. **Symbol parsing fails**: Falls back to stock with warning
2. **Invalid instrument_type column**: Uses symbol parsing instead
3. **Missing required metadata**: Falls back to stock with warning
4. **Invalid OCC/CME format**: Treats as regular stock symbol
5. **Out-of-range values**: Logs warning and falls back to stock

## Benefits

1. **Clean CSV files**: No need for multiple columns (expiry, strike, option_type)
2. **Industry standards**: Uses familiar symbol formats from exchanges
3. **Flexible**: Optional instrument_type column for explicit control
4. **Backward compatible**: Existing stock data works without changes
5. **Error handling**: Clear warnings when data is incomplete
