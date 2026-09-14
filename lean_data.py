#!/usr/bin/env python3
"""
lean_data — the ONLY research loader for Lean Terminal.  (#12, L156)

Replaces the three divergent cleaners that existed before:
  walkforward.py  weekend/holiday purge + V-spike + dedupe, hard-coded HOLIDAYS
  analog.py       no calendar, no dedupe, hard-coded current STALE set
  battery.py      diagnoses staleness, excludes nothing

One loader, one calendar, one universe contract.

    from lean_data import load_canonical_tape, Universe
    tape = load_canonical_tape("TAPE.csv")
    uni  = Universe.from_tape(tape)
    elig = uni.eligible_on("2025-03-14")

POINT-IN-TIME UNIVERSE — read this before trusting it.
There is no authoritative asset master in this project. Universe.from_tape()
DERIVES membership from observed presence in the tape: a ticker is eligible
between its first and last written session. That is enough to kill the
look-ahead in analog.py's hard-coded STALE set (which applied TODAY's
retirements to the WHOLE history), but it is NOT survivorship-free: tickers
that were never written at all are invisible. Provenance is stamped
`derived_from_tape` so no study can mistake it for an asset master.
"""

from __future__ import annotations

import csv
import datetime as dt
from dataclasses import dataclass, field

TRANSFORM_VERSION = "lean_data/1.0.0"

# Exchange calendar, versioned with the data rather than scattered per script.
NYSE_HOLIDAYS = {
    "2024-01-01",
    "2024-01-15",
    "2024-02-19",
    "2024-03-29",
    "2024-05-27",
    "2024-06-19",
    "2024-07-04",
    "2024-09-02",
    "2024-11-28",
    "2024-12-25",
    "2025-01-01",
    "2025-01-20",
    "2025-02-17",
    "2025-04-18",
    "2025-05-26",
    "2025-06-19",
    "2025-07-04",
    "2025-09-01",
    "2025-11-27",
    "2025-12-25",
    "2026-01-01",
    "2026-01-19",
    "2026-02-16",
    "2026-04-03",
    "2026-05-25",
    "2026-06-19",
    "2026-07-03",
    "2026-09-07",
    "2026-11-26",
    "2026-12-25",
}
CASH_TICKERS = {"SGOV"}
V_SPIKE = 0.35  # single-bar move that fully reverses next bar


def is_session(d: dt.date) -> bool:
    return d.weekday() < 5 and d.isoformat() not in NYSE_HOLIDAYS


@dataclass
class Tape:
    series: dict  # ticker -> [(date, close), ...] sorted
    stats: dict = field(default_factory=dict)
    transform_version: str = TRANSFORM_VERSION

    def tickers(self):
        return sorted(self.series)

    def __len__(self):
        return sum(len(v) for v in self.series.values())


def load_canonical_tape(path, drop_cash=False) -> Tape:
    """date,ticker,close -> cleaned Tape. Calendar + dedupe + V-spike, once."""
    rows = list(csv.reader(open(path)))
    hdr = [h.strip().upper() for h in rows[0]]
    di, ti, ci = hdr.index("DATE"), hdr.index("TICKER"), hdr.index("CLOSE")
    keep, n_weekend, n_holiday, n_bad = {}, 0, 0, 0
    for r in rows[1:]:
        try:
            d = dt.date.fromisoformat(r[di][:10])
            c = float(r[ci])
        except (ValueError, IndexError):
            n_bad += 1
            continue
        if d.weekday() >= 5:
            n_weekend += 1
            continue
        if d.isoformat() in NYSE_HOLIDAYS:
            n_holiday += 1
            continue
        tk = r[ti].strip().upper()
        if drop_cash and tk in CASH_TICKERS:
            continue
        keep[(tk, d)] = c  # dedupe: last write wins
    series, n_spike = {}, 0
    for (tk, d), c in sorted(keep.items()):
        series.setdefault(tk, []).append((d, c))
    for tk, s in series.items():
        out = [s[0]]
        for i in range(1, len(s) - 1):
            a, b, nx = s[i - 1][1], s[i][1], s[i + 1][1]
            if (
                a
                and abs(b / a - 1) > V_SPIKE
                and abs(nx / b - 1) > V_SPIKE
                and (b / a - 1) * (nx / b - 1) < 0
            ):
                n_spike += 1
                continue
            out.append(s[i])
        if len(s) > 1:
            out.append(s[-1])
        series[tk] = out
    return Tape(
        series,
        {
            "rows_kept": sum(len(v) for v in series.values()),
            "weekend": n_weekend,
            "holiday": n_holiday,
            "unparsed": n_bad,
            "v_spikes": n_spike,
            "tickers": len(series),
        },
    )


@dataclass
class Universe:
    """Point-in-time membership. See module docstring for its real limits."""

    spans: dict  # ticker -> (active_from, active_to)
    provenance: str = "derived_from_tape"

    @classmethod
    def from_tape(cls, tape: Tape, cash=CASH_TICKERS):
        return cls({tk: (s[0][0], s[-1][0]) for tk, s in tape.series.items() if tk not in cash})

    def eligible_on(self, day) -> set:
        if isinstance(day, str):
            day = dt.date.fromisoformat(day[:10])
        return {tk for tk, (a, b) in self.spans.items() if a <= day <= b}

    def retired_as_of(self, day) -> set:
        if isinstance(day, str):
            day = dt.date.fromisoformat(day[:10])
        return {tk for tk, (_, b) in self.spans.items() if b < day}
