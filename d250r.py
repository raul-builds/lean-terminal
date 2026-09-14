#!/usr/bin/env python3
"""
d250r.py — D250-R: Lens v1.0 re-run through the corrected research engine. (L156)
Shared loader + point-in-time universe + next-close fill + costs + cash + bootstrap CI.
Lens rules UNCHANGED. Deterministic: seeded RNG, no other randomness.
USAGE  python3 d250r.py TAPE.csv
"""

import random
import statistics as st
import sys

from lean_data import CASH_TICKERS, TRANSFORM_VERSION, Universe, load_canonical_tape

SMA_FAST, SMA_REGIME, WIN, STEP = 20, 200, 63, 21
COST_BPS, CASH_ANN, SEED = 5.0, 0.04, 20260913
CASH_D = (1 + CASH_ANN) ** (1 / 252) - 1
B_REPS, BLOCK = 2000, 8  # moving-block bootstrap


def regime_fn(tape):
    q = tape.series["QQQ"]
    px = [p for _, p in q]
    reg = {}
    for i in range(SMA_REGIME, len(px)):
        reg[q[i][0]] = "BULL" if px[i - 1] > sum(px[i - SMA_REGIME : i]) / SMA_REGIME else "BEAR"
    days = sorted(reg)

    def get(d):
        if d in reg:
            return reg[d]
        pri = [x for x in days if x <= d]
        return reg[pri[-1]] if pri else None

    return get, days[0]


def equity(ret, pos, cost=True, cash=True):
    e, prev, c = 1.0, pos[0], (COST_BPS / 1e4 if cost else 0.0)
    for r, p in zip(ret, pos):
        if p != prev:
            e *= 1 - c
            prev = p
        e *= (1 + r * p) if p else (1 + (CASH_D if cash else 0.0))
    return e - 1


def windows(tape, uni, getreg, r0, pit=True, fill="NEXT_CLOSE"):
    out = []
    for tk, s in tape.series.items():
        if tk in CASH_TICKERS:
            continue
        s = [(d, p) for d, p in s if d >= r0]
        if len(s) < WIN + 10:
            continue
        full = [p for _, p in tape.series[tk]]
        fd = [d for d, _ in tape.series[tk]]
        i0 = fd.index(s[0][0])
        dates = [d for d, _ in s]
        px = [p for _, p in s]
        ret = [0.0] + [px[i] / px[i - 1] - 1 for i in range(1, len(px))]
        p1, p2 = [0] * len(px), [0] * len(px)
        for i in range(1, len(px)):
            gi = i0 + i
            sma = sum(full[gi - SMA_FAST : gi]) / SMA_FAST if gi >= SMA_FAST else None
            f = 1 if (sma and px[i - 1] > sma) else 0
            p1[i] = f
            p2[i] = 1 if getreg(dates[i]) == "BULL" else f
        if fill == "NEXT_CLOSE":
            p1 = [0] + p1[:-1]
            p2 = [0] + p2[:-1]
        i = 1
        while i + WIN <= len(px):
            sl = slice(i, i + WIN)
            # POINT-IN-TIME GATE: ticker must be eligible on the window's first session
            if (not pit) or (tk in uni.eligible_on(dates[i])):
                out.append(
                    {
                        "tk": tk,
                        "start": dates[i],
                        "bh": equity(ret[sl], [1] * WIN, cost=False, cash=False),
                        "v1": equity(ret[sl], p1[sl]),
                        "v2": equity(ret[sl], p2[sl]),
                    }
                )
            i += STEP
    return out


def score(res, key, base):
    e = [w[key] - w[base] for w in res]
    wn = sum(1 for x in e if x > 0.001)
    tie = sum(1 for x in e if abs(x) <= 0.001)
    return wn, tie, len(e) - wn - tie, st.median(e), e


def block_boot(edges, reps=B_REPS, block=BLOCK, seed=SEED):
    """Moving-block bootstrap on the time-ordered edge series. Preserves local
    dependence from 42/63 window overlap that an iid bootstrap would destroy."""
    rng = random.Random(seed)
    n = len(edges)
    meds = []
    nblocks = -(-n // block)
    for _ in range(reps):
        samp = []
        for _ in range(nblocks):
            s = rng.randrange(0, max(1, n - block + 1))
            samp.extend(edges[s : s + block])
        meds.append(st.median(samp[:n]))
    meds.sort()
    return meds[int(0.025 * reps)], meds[int(0.5 * reps)], meds[int(0.975 * reps)]


def cluster_boot(res, reps=B_REPS, seed=SEED + 1):
    """Resample whole TICKERS. NVDA and SMH are one semiconductor bet; a
    per-window bootstrap treats them as two. This is the honest cluster."""
    by = {}
    for w in res:
        by.setdefault(w["tk"], []).append(w["v2"] - w["v1"])
    tks = sorted(by)
    rng = random.Random(seed)
    meds = []
    for _ in range(reps):
        samp = []
        for _ in range(len(tks)):
            samp.extend(by[tks[rng.randrange(len(tks))]])
        meds.append(st.median(samp))
    meds.sort()
    return meds[int(0.025 * reps)], meds[int(0.5 * reps)], meds[int(0.975 * reps)]


if __name__ == "__main__":
    tape = load_canonical_tape(sys.argv[1])
    uni = Universe.from_tape(tape)
    getreg, r0 = regime_fn(tape)
    print(f"lean_data {TRANSFORM_VERSION} | {tape.stats}")
    print(f"universe {len(uni.spans)} tickers, provenance={uni.provenance} | regime era {r0} on\n")

    for label, pit in (("CURRENT-ROSTER (no PIT)", False), ("POINT-IN-TIME", True)):
        res = windows(tape, uni, getreg, r0, pit=pit)
        w1 = score(res, "v1", "bh")
        w2 = score(res, "v2", "bh")
        h = score(res, "v2", "v1")
        print(
            f"{label:24s} windows {len(res):4d} | v1vsBH {w1[0]:3d}W/{w1[1]:2d}T/{w1[2]:3d}L "
            f"W1 {w1[0] / len(res) * 100:4.1f}% | v2vsv1 {h[0]:3d}W/{h[1]:2d}T/{h[2]:3d}L median {h[3]:+.1%}"
        )
        if pit:
            res.sort(key=lambda w: w["start"])
            edges = [w["v2"] - w["v1"] for w in res]
            lo, md, hi = block_boot(edges)
            clo, cmd, chi = cluster_boot(res)
            print(f"\n  BLOCK BOOTSTRAP (time, block={BLOCK}, {B_REPS} reps, seed {SEED})")
            print(f"    median edge {h[3]:+.2%}   95% CI [{lo:+.2%}, {hi:+.2%}]   excludes zero: {lo > 0}")
            print(f"  CLUSTER BOOTSTRAP (resample tickers, {B_REPS} reps)")
            print(f"    median edge {cmd:+.2%}   95% CI [{clo:+.2%}, {chi:+.2%}]   excludes zero: {clo > 0}")
