"""Settlement and cash management.

T+0 Settlement (Instant)
============================================

For v0.1.0, Simulor implements instant settlement (T+0) for simplicity and
rapid iteration. This means:

- Trades settle immediately
- Cash is instantly available for new trades
- No settlement queue or pending cash states
- Position updates happen synchronously with fills

This simplified model is appropriate for:
- Strategy development and prototyping
- Daily/swing strategies where settlement timing doesn't matter
- Parameter optimization runs requiring fast execution
- Most retail trading scenarios

Realistic Settlement
==============================

Future versions will implement realistic settlement modeling:

T+2 Settlement (US Equities):
- Trade Date (T+0): Order fills, position created
- T+1: Settlement pending
- T+2: Cash settles, available for trading

Cash States:
- Settled Cash: Available for immediate use
- Unsettled Cash: Proceeds from recent sales awaiting settlement
- Reserved Cash: Set aside for pending limit orders

Account Types:
- Cash Account: Can only trade with settled cash
- Margin Account: Can trade on unsettled proceeds within limits
- Pattern Day Trading rules and restrictions

Violations Tracking:
- Good Faith Violations (cash accounts)
- Free Riding Violations
- Pattern Day Trading violations

Settlement Queue:
- Chronological queue of pending cash movements
- Holiday and weekend handling
- Point-in-time buying power calculations

Configuration:
- Per-symbol settlement periods (stocks, options, futures, forex, crypto)
- Account type selection
- Violation detection and warnings
- Historical accuracy (T+3 before Sept 2017)

Performance Impact:
- Minimal overhead (~1-2% slowdown)
- Can be disabled for strategies that don't require it
- Fast-forward mode available for rapid iteration

"""

from __future__ import annotations
