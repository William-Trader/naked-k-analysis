# Walk-forward reality check (365 days)

This is the honest part most trading repos skip: we ran the deterministic
engine forward over a full year and report the result even though it is
not profitable.

## Setup

- Symbols: BTCUSDT, ETHUSDT
- Interval: 4h, 2190 bars (~365 days)
- Entry: close of each bar where the engine is non-neutral
- Exit: close of the next 4h bar (horizon = 1 bar)
- No parameter fitting; the same `stance()` used live

## Results (v2 engine, 1-bar horizon)

| Symbol | Trades | Hit rate | Avg / trade | Cumulative | Max DD | Sharpe / trade |
|---|---|---|---|---|---|---|
| BTCUSDT | 446 | 49.3% | +0.006% | +1.13% | -15.72% | 0.007 |
| ETHUSDT | 392 | 48.2% | +0.010% | +0.60% | -19.16% | 0.008 |

BTC by side: long 166 (46.4%, +0.031%), short 280 (51.1%, -0.008%).
ETH by side: long 155 (49.7%, +0.018%), short 237 (47.3%, +0.006%).

## Rule-family scan (train / validation split)

We scanned 9 rule families × 4 horizons (4/8/12/24h) × 2 symbols = 72
combinations. Split: first 70% train, last 30% validation.

Only **one** combination was positive in both segments:
BTC `base` at the 12h horizon (train +0.121%/trade, validation
+0.036%/trade, hit 52.6% / 50.0%). The same rule is negative at 4h and
24h, and no ETH rule survived both segments. With 72 tests, one nominal
pass is what chance looks like.

## Conclusion

**No robust edge was found.** We therefore do not ship a "profitable
strategy" claim. What ships instead:

1. a transparent, dependency-free feature + stance engine;
2. the full negative result (this file);
3. an outcome-scoring loop so future iterations are judged on real prices;
4. a conservative neutral stance when no edge is present.

If a future rule survives walk-forward on both symbols, it belongs here
with the same level of evidence.
