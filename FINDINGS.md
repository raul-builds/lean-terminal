# Findings

What this system tested and rejected. Negative results are kept because they cost the most to produce and are the least likely to be published elsewhere.

Every result below is reproducible from the tools in this repo against `PRICE_HISTORY`.

---

## 1. The 8/20 EMA crossover has no forward edge

**The signal.** When a ticker's 8-day EMA crosses above its 20-day EMA, the terminal fires *HOP ON* — its primary entry trigger.

**The test.** All 8/20 crossings across 7,547 ticker-days, 25 tickers, excluding stale feeds and cash instruments. Forward returns measured at 1, 3, 5, 10 and 20 days, compared against the return of a randomly selected day in the same universe.

**Result — 136 events:**

| horizon | after HOP ON | random day | difference |
|---|---|---|---|
| +1d | +0.02% | +0.14% | −0.11pp |
| +3d | +0.29% | +0.39% | −0.10pp |
| +5d | +0.02% | +0.66% | −0.64pp |
| +10d | +0.31% | +1.33% | −1.02pp |
| +20d | +2.15% | +2.92% | −0.77pp |

Win rate at 10 days: **46.3%**, against a **55.2%** baseline.

**Interpretation.** The signal underperforms a random entry at every horizon. Welch t-tests return p = 0.22 to 0.85, so none of the gaps are statistically significant. The correct reading is that the crossover **carries no information** — not that it is inverted.

A live instance during testing: CRWV ran +19.5% and +7.2% on consecutive days while the signal printed "confused," fired HOP ON the day *after* the top, and closed −5.1% the following session. Across all 8 CRWV events the mean 10-day return is −3.8%.

**Action taken.** HOP ON demoted from entry trigger to descriptive label.

*Reproduce:* `python3 analog.py PRICE_HISTORY.csv`

---

## 2. Market-regime filtering shows no edge at any timescale

**The rule.** Gate entries on broad-market health — enter only when the index is above a moving average.

**The test.** QQQ against its 8-day EMA, and its 50-, 100- and 200-day simple moving averages. Forward returns of all other tickers split by the regime verdict on each day.

**Result.** Every timescale favours entries taken while the index was *below* its average. The effect strengthens as the filter slows.

The 8 EMA result was flat (+0.04pp at 10 days across 7,292 observations). The SMA200 result appeared dramatic — +2.37% vs +17.07% at 20 days — and was rejected. See below.

**Why the dramatic result was not used.** QQQ closed below its SMA200 on **29 days out of 324**, all inside two clusters (April–May 2025 and March–April 2026). Both were V-shaped declines that recovered quickly. The measurement is of two bounces, not a property of markets.

A sample containing only the kind of decline that recovers will always conclude that declines recover.

**Honest conclusion.** There is no evidence that regime filtering helped over this period at any timescale. There is also not enough bear-market data here to conclude that it never helps — which matters, because that is the environment the filter exists for.

**Action taken.** Regime layer demoted from a veto to a context label. Not because it is disproven, but because it is unproven, and an unproven gate should not hold a veto.

---

## 3. A deliberately simple rival beat the system

A five-rule momentum model, built as a control, returned +129% with a Sharpe of 2.15 and a −15% maximum drawdown over 14.6 months.

It lost to buying and holding SMH (+173%, Sharpe 2.35).

Removing a single ticker from the rival halved its CAGR — the returns were a concentration bet, not a strategy.

**Action taken.** Recorded rather than tuned. The response to a losing test is more tickers and more windows, never parameter adjustment.

---

## 4. Three analysis bugs caught before publication

Documented because the catch matters more than the absence.

**26× event-count inflation.** The first crossover study reported 3,592 events. NVDA alone showed 295 crossings in 523 sessions — implausible on inspection. A pandas boolean-shift error was converting missing values into false crossings. True count: 136.

**Warmup misclassified as regime.** Comparing a price against a not-yet-defined moving average returns `false` rather than null, so the first 200 sessions of every SMA200 test were scored as "market below average." Every result was inflated until this was corrected.

**A rounding artifact reported as a wiring bug.** All four position sizes rendered identically at $50 and were docked as an input failure. The formula was correct: raw values of $59.80, $54.56, $44.00 and $41.80 were being rounded to the nearest $25. A display-resolution problem, not a computation one.

---

## Tools

| file | purpose |
|---|---|
| `battery.py` | 32-test data integrity suite — staleness, scale corruption, duplicates, frozen feeds, position sanity |
| `analog.py` | event-study harness — forward returns conditioned on any signal, against baseline |
| `walkforward.py` | rolling-window validation engine, 1-day action lag |

`battery.py` includes a test that reports SKIP rather than a result: Benford's law is not applicable to equity closes, because prices do not span the orders of magnitude the law requires. Running it anyway produces a large chi-square statistic that means nothing. The gate is deliberate.

---

## What this system is for

It does not have a demonstrated trading edge. Its measurable value so far is that it enforced abstention through a five-month period in which its own entry signals would have lost money.

That is a narrower claim than the one this project started with, and it is the one the evidence supports.
