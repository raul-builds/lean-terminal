# Lean Terminal — research engine

Canonical data layer, walk-forward validation, and event study for Lens v1.0.

## Reproduce the current result in one command

```bash
pip install -e ".[dev]"
python d250r.py tests/fixtures/tape_fixture.csv
```

Expected (golden, pinned in `tests/test_lean_data.py`):

```
POINT-IN-TIME   windows 248 | v1vsBH 83W/3T/162L W1 33.5% | v2vsv1 150W/10T/88L median +2.5%
block bootstrap    median +2.53%   95% CI [+0.41%, +4.22%]
cluster bootstrap  median +2.52%   95% CI [+0.36%, +4.23%]
```

## Layout

| File | Role |
|---|---|
| `lean_data.py` | The only research loader. Calendar, dedupe, V-spike, point-in-time universe. |
| `prep.py` | Raw Apps Script export (JS dates) → canonical ISO tape. Values untouched. |
| `d250r.py` | Walk-forward: next-close fill, costs, cash, block + cluster bootstrap. |
| `analog_pit.py` | HOP ON event study on the same loader and universe. |
| `battery_v2.py` | 32-test data-integrity battery. Roster-aware T19 via `RETIRED=A,B,C`. |
| `tests/` | 16 unit + golden tests. Every bug this project paid for has one. |

## Current claim

A pre-registered regime gate reduced the performance penalty of an always-on SMA20
defensive filter by a median **+2.5% per quarter (95% CI +0.4% to +4.2%)** after
one-session fills, 5 bps costs and 4% cash yield, across 248 overlapping 63-session
windows on 48 tickers, 2025-04 to 2026-09.

Its incremental economic value beyond removing a harmful overlay is **not established**.

## Known limits

- Universe is `derived_from_tape`, not an asset master. Tickers never written are invisible.
  Survivorship risk is reduced, not eliminated.
- `next_open` fills untested — the tape carries no open prices. `next_close` is the
  conservative bound.
- No trial-count ledger.
- GOOGLEFINANCE is the sole data source. No second vendor, no corporate-action metadata.
