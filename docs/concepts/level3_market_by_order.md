# Level 3 Market-By-Order

## Components

- **Individual order IDs**: Each order tracked separately
- **Order lifecycle**: Exact add/modify/cancel/fill events for each order
- **Queue position**: Precise FIFO position in price-time priority
- **Exchange routing**: Which venue each order is on
- **Order timestamps**: Nanosecond precision on order events

## Data Structure

```python
# Level 3 Order Event
OrderEvent(
    timestamp=09:30:01.523456789,
    event_type='add',              # add, modify, cancel, fill
    order_id=1234567890,           # Unique order identifier
    side='bid',
    price=150.24,
    size=100,
    exchange='NASDAQ',
    queue_position=15              # Position in FIFO queue
)
```

## Why Level 3 is Fundamentally Different

- Level 1 = Top of book (2 prices)
- Level 2 = Aggregated depth (20-40 prices)
- Level 3 = Individual orders (thousands of order IDs, constant updates)

## True Level 3 Feeds

- NASDAQ TotalView-ITCH (order-level messages)
- IEX DEEP
- NYSE OpenBook Ultra
- Some futures exchanges (CME MDP 3.0)
