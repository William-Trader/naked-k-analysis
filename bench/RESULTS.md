# Benchmark: 201 real briefings vs real prices

This benchmark is the reason the v2 rules exist. It is reproducible from
the session log and Binance public data.

## Sample

- 201 briefings produced by the bot between **2026-09-13 and 2026-10-20**
- BTCUSDT / ETHUSDT 4h candles from `data-api.binance.vision`
- Entry = close of the 4h candle containing the briefing timestamp
- Exit = close at +4h / +8h / +12h / +24h / +48h

## BTC directional results

| Horizon | Base up-rate | Long hit | Short hit | Directional hit |
|---|---|---|---|---|
| +4h | 54.2% | 56% | **66%** | **61%** |
| +8h | 54.2% | 48% | 43% | 45% |
| +12h | 52.7% | 41% | 69% | 56% |
| +24h | 55.2% | 37% | 43% | **40%** |
| +48h | 49.8% | 44% | 43% | 44% |

## What the numbers say

1. **Only the 4h bearish continuation had a measurable edge (~66%).**
2. **24h directional calls were anti-predictive (40%)** — so v2 forbids them.
3. **69% of briefings were neutral** and 71% of structure calls were "mixed" —
   the old prompt rewarded hedging.
4. **Shorting range lows lost at 24h** (62% of those shorts were followed by a
   bounce) — so v2 hard-disables shorts when `pos20 < 0.30`.
5. 200/201 briefings contained fabricated 45%/30%/25% probabilities; v2 uses
   calibrated confidence priors instead.

## Raw

- `results.json` — the aggregated table used by the README.
