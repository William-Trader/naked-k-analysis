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

## Extended check: 730 days x 5 symbols

Same engine, no parameter fitting, 2 years of 4h bars (4380 bars each):

| Symbol | Trades | Hit rate | Avg / trade | Cumulative | Max DD |
|---|---|---|---|---|---|
| BTCUSDT | 810 | 49.6% | -0.010% | **-10.82%** | -26.85% |
| ETHUSDT | 775 | 48.8% | -0.078% | **-49.67%** | -58.67% |
| SOLUSDT | 831 | 47.4% | -0.135% | **-70.82%** | -73.11% |
| BNBUSDT | 906 | 49.0% | -0.022% | **-22.44%** | -32.85% |
| XRPUSDT | 1059 | 48.6% | -0.059% | **-53.86%** | -74.10% |

All five symbols are net negative **before fees and funding**. This rules out
"BTC/ETH was just an unlucky regime" as the explanation: the rule family
itself has no edge on this sample.

## What this means for the roadmap

We will not tune thresholds until the backtest turns green — with 5 symbols,
2 years and 72 rule variants already tested, that would be curve-fitting.
The honest next step is a different hypothesis, not a different threshold:

1. **cross-sectional momentum** across the top-N USDT universe (relative
   strength, monthly rebalance) rather than single-symbol 4h timing;
2. **regime-conditioned** rules (only trade when the higher-timeframe trend
   and volatility regime agree);
3. **longer history** and **funding/basis** data, which are not in the
   current 4h OHLCV set.

Any candidate must survive the same walk-forward protocol and be reported
here with the same honesty.

