# Lean Terminal

A solo-built systematic swing-trading system: a Google Sheets data plant, an Apps Script pipeline, a single-file HTML terminal, and a Python validation harness — governed by one rule that only evidence can change.

**[→ 2008 crash stress test](https://raul-builds.github.io/lean-terminal/STRESS_2008.html)** — a −60% semiconductor crash capped at −18% max drawdown, cross-validated across four independent data sources.

**[→ What didn't work](FINDINGS.md)** — the signals this system tested and rejected.

---

## Why this exists

I'm a self-taught systematic trader building toward fintech engineering. This repo is the system I actually trade with real money — and more importantly, the *process* around it: automated data collection, versioned decision logs, and a validation harness that has already overruled my own ideas several times.

The most valuable results here are the negative ones.

## Architecture

```
GOOGLEFINANCE  ──►  Apps Script pipeline (5:37am PT daily)
                     · NYSE holiday/weekend guard
                     · ticker registry filter (lifecycle statuses)
                     · writes PRICE_HISTORY (32 tickers, 2.1 yrs)
                     · exports dated CSVs to Drive (audit trail)
                           │
        ┌──────────────────┴──────────────────┐
        ▼                                     ▼
  Lean Terminal (renderer)             Python harness (judge)
  single-file HTML/JS, ~8,500 lines    walk-forward engine
  baseball-card UI per ticker          63-day rolling windows
  EMA ladders · regime light           1-day action lag, no lookahead
  behavioral logging                   baseline: buy-and-hold
```

Data (Sheets) and rendering (terminal) are fully decoupled. The terminal can be rebuilt without touching a single data row.

## Lens v1.0 — the operating rule (ratified 2026-07-07)

One regime light, checked each morning:

```
if QQQ_close > SMA200(QQQ):        # market healthy
    hold all positions             # trend filter asleep
else:                              # market sick
    for each ticker:
        in  if close > SMA20(ticker)
        out (park in SGOV) otherwise
# signals act with a 1-day lag — no lookahead
```

**Amendment policy:** the rule can only be changed by the quarterly walk-forward re-test. Not by a hot streak, a drawdown, or a social-media strategy reel. This clause is the whole point.

## The validation study

**Method.** 63-trading-day rolling windows, stepped 21 days, across 24 tickers and 2.1 years of daily closes (275 windows). Strategy returns computed with a 1-day action lag. Baseline: buy-and-hold of the same ticker over the same window. Nothing was tuned to the sample.

### Result 1 — the always-on trend filter fails

A plain `close > SMA20` rule beat buy-and-hold in only **27.3%** of windows. Split by market direction, the story flips:

| window type | rule wins |
|---|---|
| rising markets | 12.2% |
| falling markets | **70.6%** |

The filter is a **parachute, not an engine** — a tax in bulls, insurance in bears. On a relentless trender (NVDA) it lost in **all 21 windows**: you cannot whipsaw-trade a strong trend.

### Result 2 — the harness caught corrupted data

The first run produced an impossible result: a long-only filter losing −99% while buy-and-hold gained +93%.

Root cause: **489 phantom weekend rows** — Saturday "prices" at roughly half the real value, injected during a historical backfill — creating fake 45% crashes that never happened. Plus Good Friday ghost rows and 1,659 duplicate `(ticker, date)` keys.

All were purged (10,651 → 8,501 rows), the purge tool is now permanent pipeline code, and every number here comes from the clean re-run.

*Finding the corruption was worth more than any backtest result.*

### Result 3 — the regime gate wins

Lens v1.0 (hold in bull, filter in bear) vs the always-on filter, head-to-head across the same windows: **122 wins, 56 losses, median +4.0% per quarter.**

Regime-era equity (Apr 2025 – Jul 2026):

| ticker | buy & hold | always-on filter | **Lens v1.0** |
|---|---|---|---|
| NVDA | +93% | +47% | **+79%** |
| SMH  | +214% | +87% | **+171%** |
| QQQ  | +63% | +22% | **+57%** |

Max drawdowns were equal or shallower under the lens in every case.

### Honest limitations

The regime era was 91% bull with only 3 regime flips — the bear-mode branch is undertested live. Its credentials come from the full-history down-window stats above and from the [2008 replay](https://raul-builds.github.io/lean-terminal/STRESS_2008.html).

Day-scale Markov analysis of the same data shows direction is near coin-flip (only volatility clusters), which is why the system doesn't attempt daily prediction.

The quarterly re-walk is the only body allowed to amend the rule.

## Reproducibility

Every figure in this README regenerates from the harness in this repo:

```
python3 walkforward.py
```

No number here is hand-typed. If the data changes, the README is wrong until it is re-run — which is the point.

## The behavioral layer

Every session is logged (BEHAVIOR_LOG, dating to day 0). Sample entry:

> *L17 — "Stack, bus, rhythm all green. I almost convinced myself to override the lens. Stopped. Recognized I was building a case for what I wanted to do rather than reading what the system said. Bench day."*

The system's first empirical vindication of that discipline: across 21 walk-forward windows, holding NVDA beat trading it **every single time**. The 40+ day "bench" wasn't hesitation; it was the optimal policy.

A separate fabrication log tracks viral "strategy" posts tested and debunked (curve-fit Sharpe ratios, impossible returns) — the immune system against feed-driven rule changes.

## Governance

- **DOCK:** 215+ tracked work items with statuses, colors, dependency gates, and revisit triggers — the project's issue tracker, in-sheet.
- **Founding rules** (day-one constitution): position caps, daily loss stop, 15% drawdown circuit-breaker reverting the system to its conservative mode.
- **Audit trail:** dated CSVs auto-exported to Drive every trading morning.

## Stack

Google Apps Script · Google Sheets · vanilla HTML/JS/CSS (no framework, single file) · Python 3 (stdlib + matplotlib) for the harness.

---

*Built in Reno, NV, with an AI pair-programmer. The charts in `/docs` are generated by the harness in this repo.*
