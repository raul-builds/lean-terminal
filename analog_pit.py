#!/usr/bin/env python3
"""analog_pit.py — HOP ON event study on the shared loader + point-in-time universe.
Fixes analog.py's look-ahead: it hard-coded TODAY's retired set and applied it to
ALL history. Here a ticker-day is eligible only while the ticker was actually live."""

import random
import sys

import numpy as np
import pandas as pd

from lean_data import CASH_TICKERS, Universe, load_canonical_tape

H = (1, 3, 5, 10, 20)
SEED = 20260913


def frame(tape, uni, pit=True):
    rows = []
    for tk, s in tape.series.items():
        if tk in CASH_TICKERS:
            continue
        for d, c in s:
            if pit and tk not in uni.eligible_on(d):
                continue
            rows.append((d, tk, c))
    return pd.DataFrame(rows, columns=["d", "TICKER", "c"]).sort_values(["TICKER", "d"])


def event_study(df):
    on = []
    for tk, g in df.groupby("TICKER"):
        g = g.reset_index(drop=True)
        if len(g) < 120:
            continue
        e8 = g.c.ewm(span=8, adjust=False).mean()
        e20 = g.c.ewm(span=20, adjust=False).mean()
        ab = e8 > e20
        up = ab & (~ab.shift(1).astype("boolean")).fillna(False)
        for i in np.where(up)[0]:
            if i < 50 or i >= len(g) - max(H):
                continue
            on.append({"tk": tk, **{f"r{h}": g.c[i + h] / g.c[i] - 1 for h in H}})
    return pd.DataFrame(on)


def baseline(df):
    out = {}
    for h in H:
        v = []
        for _, g in df.groupby("TICKER"):
            c = g.c.values
            if len(c) > h:
                v.extend(c[h:] / c[:-h] - 1)
        out[h] = np.array(v)
    return out


def cluster_ci(ev, col, reps=2000, seed=SEED):
    by = {}
    for tk, g in ev.groupby("tk"):
        by[tk] = list(g[col].values)
    tks = sorted(by)
    rng = random.Random(seed)
    out = []
    for _ in range(reps):
        s = []
        for _ in range(len(tks)):
            s.extend(by[tks[rng.randrange(len(tks))]])
        out.append(float(np.mean([x > 0 for x in s]) * 100))
    out.sort()
    return out[50], out[1950]


if __name__ == "__main__":
    tape = load_canonical_tape(sys.argv[1])
    uni = Universe.from_tape(tape)
    for label, pit in (("HARD-CODED STALE (legacy, look-ahead)", False), ("POINT-IN-TIME", True)):
        df = frame(tape, uni, pit)
        ev = event_study(df)
        bl = baseline(df)
        print(f"\n=== {label} ===  rows {len(df):,}  tickers {df.TICKER.nunique()}  events {len(ev)}")
        print(
            f"{'hz':>4} {'n':>5} {'mean':>8} {'median':>8} {'win%':>7} {'base win%':>10} {'gap pp':>8} {'win% 95% CI':>18}"
        )
        for h in H:
            r = ev[f"r{h}"].values
            b = bl[h]
            w = (r > 0).mean() * 100
            bw = (b > 0).mean() * 100
            ci = cluster_ci(ev, f"r{h}") if pit else (float("nan"),) * 2
            cis = f"[{ci[0]:5.1f},{ci[1]:5.1f}]" if pit else "         --      "
            print(
                f"+{h:>2}d {len(r):5d} {r.mean():+7.2%} {np.median(r):+7.2%} {w:6.1f}% {bw:9.1f}% {w - bw:+7.1f} {cis:>18}"
            )
