# Lean Terminal — working brief

Read this before touching anything. It is the operator's system, not a greenfield project.

---

## What this is

A solo-built systematic swing-trading system. Google Sheets is the data backbone, an Apps Script pipeline runs daily, a single-file HTML terminal renders it, and a Python harness validates it. Real money, small book (~$8.8K).

It is also — explicitly — a **quant dev portfolio piece** aimed at a junior fintech engineering role. Software architecture and honest validation matter as much as trading results. Public repo: `github.com/raul-builds/lean-terminal`.

**The system has no demonstrated trading edge.** Its entry signal was tested and found to carry no information (see FINDINGS below). Its measured value is that it enforced abstention through a five-month period when its own signals would have lost money. Do not treat it as a money-maker; treat it as an instrument being made trustworthy.

---

## Files in this folder

| file | what it is |
|---|---|
| `lean_terminal_v651.html` | **The terminal.** 8,532 lines, single file, HTML+JS+CSS. This is the live one. |
| `start_lean_terminal.command` | Launcher. Serves the folder on `localhost:8000`, opens v651. Hardened Aug 2026: binds `127.0.0.1`, guards the `cd`, traps on exit. |
| `Code.gs` | Apps Script pipeline. Runs 5:37am PT daily. |
| `battery.py` | 32-test data integrity suite. `python3 battery.py PRICE_HISTORY.csv [HOLDINGS.csv]` |
| `analog.py` | Event-study harness. Forward returns conditioned on any signal vs baseline. |
| `walkforward.py` | Rolling-window validation engine, 1-day action lag. |
| ~140 older `lean_terminal_v*.html` | Version history. **The launcher is the only thing that marks which is current.** Do not assume the highest number is live. |

**The terminal contains its own embedded backlog** — a 15-item "Loading Deck" panel on the DNA Lab tab, never reconciled against the dock (D205). Do not treat it as authoritative.

**The folder is flat and has ~244 entries.** Organizing it is an open task (D222). Do not reorganize without being asked — the launcher and several scripts reference paths.

---

## Vocabulary

Internal terms, used constantly, non-standard:

- **bus** — EMA-based trend filter. "On the bus" = price above the 8 EMA. HOP ON / HOP OFF = 8/20 crossover. TREND SHIFT = 20/50 golden cross. BAIL = 20/50 death cross.
- **lens** — two different things: (1) **Lens v1.0**, the ratified operating rule (QQQ close vs SMA200, 1-day action lag); (2) the **five-layer lens panel** (stock / family / market / calendar / anomaly) that renders a go-count verdict.
- **stack** — where price sits relative to the 8/20/50 EMAs, plus the order of those EMAs. Six states: full bull, bullish, weak, mixed, fading, full bear.
- **DNA** — per-ticker factor profile.
- **fatigue** — momentum exhaustion score, 0–100.
- **rhythm** — position in the cycle, as a percentage.
- **noise** — signal entropy, 0–100. Runs 79–99 in practice. **Several thresholds were calibrated for a different scale and are unreachable.**
- **bench** — three unrelated uses, they collide in any grep. (1) **BENCH pill** — the feature. Days since the last new non-cash entry. `computeBenchDays()` ~:7159, `updateBenchPill()` ~:7176. Skips SGOV and anything tagged cash/safety — "parking isn't a deployment." Measures idle *capital*, not holding period; closed trades don't reset it, only a live non-cash position does. Hardcoded yellow, no threshold logic. Operator has been on the bench since L14 and that is deliberate. (2) **Benchmark** — unrelated panel, portfolio vs SPY/SGOV with alpha, `renderBenchmark()` ~:7184. Dominates any search for "bench." (3) **bench stocks** — ETF component jargon in the Loading Deck: rank 1–3 in a parent ETF is a "team captain," rank 20+ is a "bench" stock.
- **LEAN / AGG** — risk posture modes. LEAN base position $75, AGG $125.
- **Wario** — the Alpaca paper account.
- **dock** — the issue tracker, a tab in the sheet. Rows are `D###`. Currently past D220.
- **BEHAVIOR_LOG** — session log, rows are `L###`. L0 = 2026-04-10, incremented by calendar day with no skips. Sub-rows use suffixes (L124-a, L124-b).
- **pills** — status indicators: READY, RISK, PLAN, ACTION.

---

## Standing rules

**Done at pixel, not at paste.** Nothing is closed until it has been seen working on screen. A dock row saying GREEN when the fix did not ship is the exact failure mode the dock exists to prevent.

**Dock freely, fix only what makes the terminal lie to you.** The board grows faster than it closes. Docking something and doing something are different acts. Most rows should stay docked.

**Never tune a rule to win a known window.** The correct response to a losing test is more tickers and more windows, not parameter adjustment. Two models have been killed this way rather than tuned (D175, D177).

**Disclose errors immediately.** Three analysis bugs were caught mid-run and published rather than quietly fixed. That record is a career asset. If you find a mistake in your own work, say so before reporting the result.

**Tag, don't delete.** Corrections amend in place with a correction stamp. Wrong intermediate diagnoses stay in the record.

**Validate before concluding.** "No evidence of edge" and "evidence of no edge" are different claims. Sample size is checked before a result is believed.

---

## Established findings — do not re-litigate

- **HOP ON (8/20 EMA crossover) has no forward edge.** 136 events, underperforms a random day at every horizon, win rate 46.3% at +10d vs 55.2% baseline, p=0.22–0.85. Demoted to descriptive label.
- **Market-regime filtering shows no edge at any timescale.** Tested QQQ vs 8 EMA, SMA50, SMA100, SMA200. The dramatic SMA200 result was rejected: only 29 below-average days, all in two V-shaped clusters.
- **A deliberately simple rival lost to buy-and-hold SMH.** Recorded, not tuned.
- **The score column is hand-typed.** No scoring formula exists. Tested against forward returns: rank correlation +0.152, p=0.61, n=14 — the sample cannot answer the question. Needs ~2,000 score-outcome pairs.
- **Effective bets ≈ 4.67 across ~10 positions.** QQQ↔VOO 0.93, QQQ↔SMH 0.91. The book is one AI/semis bet held several ways.

---

## Known live defects

- **Lens layers 1 and 5** gate on `noise <= 40` against live noise of 79–99. Structurally unreachable. Max go-count is 2 of 5 (3 in the full lens).
- **Full-lens layer 4** is hardcoded `'neutral'` and tested against `'clear'`. Never fires.
- **Two lens implementations exist** — `_ml_l1` (mini, baseball card, ~line 6217) and `l1Score` (full, LENS tab, ~line 6609) — with different thresholds and different label vocabularies. Consolidating them is D207.
- **Two stack classifiers exist** — `calcEMAStack()` (6 states, used by cards) and `searchTickerMath()` (4 states, different names). Line ~4832 tests a string the first classifier never produces — dead branch.
- **MARKOV_CURRENT** renders "no probability data" board-wide.
- **Six tickers are stale or dead** in PRICE_HISTORY: AMD and SPCX stopped 2026-06-30; CGC, HYFM, MSOS, TLRY stopped 2026-04-17 (a universe swap, not a feed failure).
- **BENCH pill has no threshold logic** — hardcoded yellow, no escalation between 10 and 60 days. Same class as the score column: reads like a judgment, is a raw number.
- **RADAR catalogues 134 tickers; PRICE_HISTORY carries 32.** Roughly 102 tickers cannot be scored. This gates most radar and diversification work.

---

## Working style

- **Terse.** Short answers. No preamble. Street-speak first, then specs.
- **Confidence scores** on recommendations (e.g. "confidence: 82").
- **Stoplight** where useful: 🟢 do, 🟡 consider, 🔴 skip.
- **Honest pushback over agreement.** The operator's pushback has historically been correct — treat it as signal.
- **Three upgrades maximum** at once.
- Deliver **complete corrected files**, not line-level edit instructions, when working outside this folder.

---

## Token discipline

`lean_terminal_v651.html` is 574KB — roughly 150K tokens if read whole. **Do not read it whole.**

- Grep for the string, then read a line range around the hit.
- Name the file and narrow the scope in every request.
- `/clear` between unrelated tasks.

Same applies to the CSVs. `PRICE_HISTORY` is 8,827 rows.

---

## What you cannot do

- **No Google Sheets access.** No connector, no API auth. You can edit `Code.gs`; the operator pastes it into the Apps Script editor and runs it.
- **No memory across sessions.** This file is the entire briefing.
- **No dock or log access.** The operator maintains those in the sheet. Give paste-ready TSV when a row is needed — tab-separated, no headers, no instruction lines mixed into cell content.

---

## Current context

- Session numbering: **L0 = 2026-04-10.** Today's L-number = calendar days since.
- Dock is past **D220**.
- Real-estate closing **2026-08-27** — the operator's attention is legitimately split.
- CS50 (CS50x + CS50P) deadline **2026-12-31**, currently stalled.
- Open priority order: D216 (label the score column MANUAL) → D206 (provenance tags) → D207 (single lens function) → D208 (LENS_HISTORY logging) → D218 (ticker coverage).
