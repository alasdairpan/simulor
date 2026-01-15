# Level 2 Order Book

## Components

- **Multiple price levels**: Typically 5-20 levels deep on each side
- **Aggregated quantities**: Total volume at each price level (not individual orders)
- **Order book snapshots**: Full depth at a point in time
- **Book updates**: Add/remove/modify events at each level

## Data Structure

```python
# Level 2 Order Book Snapshot
OrderBookSnapshot(
    timestamp=09:30:01.523,
    bids=[
        (150.24, 500),     # (price, total_size)
        (150.23, 1200),
        (150.22, 800),
        (150.21, 600),
        (150.20, 1500),
        # ... up to 10-20 levels
    ],
    asks=[
        (150.26, 300),
        (150.27, 900),
        (150.28, 700),
        (150.29, 400),
        (150.30, 1100),
        # ... up to 10-20 levels
    ]
)
```

## Why Level 2 is Different from Level 1

- Level 1 = **Scalar values** (single best price per side) → Can aggregate into bars
- Level 2 = **Distribution** (multiple price levels) → Cannot aggregate into OHLC bars
- Level 2 stays as **snapshots** or derives **scalar features** for analysis

## Level 2 Derived Features

```python
# Extract scalar metrics from L2 for analysis
l2_features = {
    'spread': asks[0][0] - bids[0][0],
    'bid_depth_5': sum(size for _, size in bids[:5]),
    'ask_depth_5': sum(size for _, size in asks[:5]),
    'imbalance': bid_depth_5 / ask_depth_5,
    'mid_price': (bids[0][0] + asks[0][0]) / 2,
    'weighted_mid': (bids[0][0]*asks[0][1] + asks[0][0]*bids[0][1]) / (bids[0][1] + asks[0][1])
}
```

## Important Note

- **NASDAQ TotalView** is Level 2 (aggregated depth), NOT Level 3
- Many vendors market "Level 2" as premium data
- Level 2 shows aggregated size at each price, not individual orders
