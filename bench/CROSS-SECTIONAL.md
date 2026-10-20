# Cross-sectional momentum study (negative)

Hypothesis: instead of timing one symbol on 4h bars, rank the top-N USDT
universe by past return and hold the strongest K names.

## Setup

- Universe: top 25 USDT pairs by 24h quote volume; 19 had enough history
- Data: 730 days of daily closes (Binance public API)
- Rebalance every 7 / 14 / 30 days
- Lookback 30 / 60 / 90 days; hold top 3 / 5 / 10, equal weight
- Split: first 70% train, last 30% validation
- Benchmark: BTC buy-and-hold

## Results (sorted by validation Sharpe)

| Lookback | Top K | Rebalance | Train total | Train Sharpe | Validation total | Validation Sharpe | BTC |
|---|---|---|---|---|---|---|---|
| 30d | 3 | 30d | -53.3% | -0.39 | +12.8% | 2.15 | -26.3% |
| 30d | 5 | 30d | -54.8% | -0.47 | -7.0% | 1.72 | -26.3% |
| 90d | 5 | 7d | -23.7% | -0.13 | +51.2% | 1.55 | -11.4% |
| 30d | 3 | 7d | -48.2% | -0.33 | +32.4% | 1.41 | -26.3% |
| 30d | 3 | 14d | -28.0% | -0.09 | +42.9% | 1.39 | -26.3% |
| 60d | 10 | 30d | -54.3% | -0.78 | -18.8% | 1.38 | -23.1% |
| 90d | 10 | 30d | -42.5% | -0.63 | +4.6% | 1.36 | -11.4% |
| 90d | 10 | 7d | -39.0% | -0.45 | +2.8% | 1.35 | -11.4% |
| 30d | 10 | 30d | -52.3% | -0.60 | -4.8% | 1.25 | -26.3% |
| 60d | 5 | 14d | -60.6% | -0.80 | -19.5% | 1.23 | -23.1% |
| 60d | 10 | 7d | -54.4% | -0.66 | -17.2% | 1.22 | -23.1% |
| 90d | 3 | 7d | -13.9% | 0.05 | +46.0% | 1.18 | -11.4% |

## Conclusion

**No combination was positive in the training segment.** Every one lost
money over the first ~1.4 years and most made money in the last ~7
months. That is regime dependence, not an edge: the validation window
happened to favour high-beta alts.

We therefore do not promote cross-sectional momentum as implemented. The
next honest test is a **rolling walk-forward** (multiple folds, not one
70/30 split) combined with a **regime filter** (BTC trend / market
breadth), and only then a decision. Until a configuration survives
several folds on more than one symbol universe, it stays a research note.

## Caveats

- 19 symbols, 2 years, daily closes; survivorship bias is possible
  because the universe is today's top-25.
- No fees, funding or slippage; with costs the numbers are worse.
- One 70/30 split is not a walk-forward; it is a first screen.
