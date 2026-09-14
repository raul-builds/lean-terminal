#!/usr/bin/env python3
"""
battery.py — Lean Terminal integrity battery
=============================================
32-test diagnostic suite for PRICE_HISTORY (and optionally HOLDINGS).

Built L115 (2026-08-03) as a PERMANENT tool. Prior runs (L90, L94, L98)
were ad-hoc code-exec and were never saved — which is why D164 / D171 / D176
all said "wire into next battery run" and never got wired. Now they are
tests T26, T27-T28, and T18-T20 below.

USAGE
    python3 battery.py PRICE_HISTORY.csv [HOLDINGS.csv]

EXIT CODES
    0 = all tests pass or warn
    1 = one or more FAIL

Every test returns PASS / WARN / FAIL / SKIP with a one-line reason.
Nothing here mutates data. Read-only by construction.
"""

import sys
from collections import Counter

import numpy as np
import pandas as pd

# ---------------------------------------------------------------- config
CASH_TICKERS = {"SGOV"}  # per walkforward.py — never rule-traded
STALE_DAYS = 5  # D176: >5 trading days behind = stale
DEAD_DAYS = 30  # no update in 30 trading days = dead feed
MAX_WEIGHT = 0.50  # D164: any position >50% of book = red flag
FROZEN_RUN = 5  # same close N sessions running = frozen feed
EXTREME_MOVE = 0.50  # >50% single-day move = suspect
SCALE_RATIO = 20  # close >20x ticker median = scale corruption

RESULTS = []


def record(tid, name, status, detail):
    RESULTS.append((tid, name, status, detail))


# ---------------------------------------------------------------- helpers
def load(path):
    df = pd.read_csv(path, dtype=str)
    df.columns = [c.strip() for c in df.columns]
    return df


def trading_calendar(dates):
    """Sheet-wide set of observed dates = proxy trading calendar."""
    return sorted(set(dates.dropna()))


def days_behind(cal, d):
    """How many trading sessions behind the sheet max a given date is."""
    if pd.isna(d):
        return len(cal)
    try:
        return len(cal) - 1 - cal.index(d)
    except ValueError:
        after = [x for x in cal if x > d]
        return len(after)


# ---------------------------------------------------------------- tests
def run(price_path, holdings_path=None, retired=None):
    """retired: set of tickers intentionally removed from the universe (roster-aware T19)."""
    retired = set(t.strip().upper() for t in (retired or []) if t.strip())
    # ---- T01 file loads
    try:
        df = load(price_path)
        record("T01", "File loads", "PASS", f"{len(df):,} rows / {len(df.columns)} cols")
    except Exception as e:
        record("T01", "File loads", "FAIL", str(e))
        return

    # ---- T02 required columns
    need = {"DATE", "TICKER", "CLOSE"}
    missing = need - set(df.columns)
    record(
        "T02",
        "Required columns",
        "PASS" if not missing else "FAIL",
        "DATE/TICKER/CLOSE present" if not missing else f"missing {missing}",
    )
    if missing:
        return

    # ---- T03 non-empty
    record("T03", "Non-empty", "PASS" if len(df) > 0 else "FAIL", f"{len(df):,} rows")

    # ---- T04 date parses
    d = pd.to_datetime(df["DATE"], format="mixed", errors="coerce")
    bad = int(d.isna().sum())
    record(
        "T04",
        "DATE parses",
        "PASS" if bad == 0 else "FAIL",
        "100% parseable" if bad == 0 else f"{bad} unparseable",
    )
    df["DT"] = d

    # ---- T05 single date format  (D151)
    s = df["DATE"].astype(str)
    iso = int(s.str.match(r"^\d{4}-\d{2}-\d{2}$").sum())
    us = int(s.str.match(r"^\d{1,2}/\d{1,2}/\d{4}$").sum())
    other = len(s) - iso - us
    if iso and us:
        record(
            "T05", "Single date format", "FAIL", f"D151 LIVE — {iso} ISO + {us} M/D/YYYY mixed in one column"
        )
    elif other:
        record("T05", "Single date format", "FAIL", f"{other} rows in a third format")
    else:
        record("T05", "Single date format", "PASS", "uniform")

    # ---- T06 CLOSE numeric
    c = pd.to_numeric(df["CLOSE"], errors="coerce")
    nn = int(c.isna().sum())
    record(
        "T06",
        "CLOSE numeric",
        "PASS" if nn == 0 else "FAIL",
        "all numeric" if nn == 0 else f"{nn} non-numeric/blank",
    )
    df["CLOSEN"] = c

    # ---- T07 CLOSE positive
    nonpos = int((c <= 0).sum())
    record(
        "T07",
        "CLOSE > 0",
        "PASS" if nonpos == 0 else "FAIL",
        "all positive" if nonpos == 0 else f"{nonpos} rows <= 0",
    )

    # ---- T08 ticker hygiene
    t = df["TICKER"].astype(str)
    dirty = int((t != t.str.strip().str.upper()).sum())
    record(
        "T08",
        "TICKER hygiene",
        "PASS" if dirty == 0 else "FAIL",
        f"{t.nunique()} tickers, clean" if dirty == 0 else f"{dirty} rows with whitespace/case issues",
    )

    # ---- T09 duplicate (DATE,TICKER)
    dup = int(df.duplicated(subset=["DT", "TICKER"]).sum())
    record(
        "T09",
        "No duplicate DATE+TICKER",
        "PASS" if dup == 0 else "FAIL",
        "unique" if dup == 0 else f"{dup} duplicate pairs",
    )

    # ---- T10 exact duplicate rows
    dupe_all = int(df.duplicated().sum())
    record(
        "T10",
        "No exact duplicate rows",
        "PASS" if dupe_all == 0 else "FAIL",
        "none" if dupe_all == 0 else f"{dupe_all} identical rows",
    )

    # ---- T11 no weekend rows
    wk = int(df["DT"].dt.dayofweek.isin([5, 6]).sum())
    record(
        "T11", "No weekend rows", "PASS" if wk == 0 else "FAIL", "clean" if wk == 0 else f"{wk} Sat/Sun rows"
    )

    # ---- T12 no future dates
    today = pd.Timestamp.today().normalize()
    fut = int((df["DT"] > today).sum())
    record(
        "T12",
        "No future dates",
        "PASS" if fut == 0 else "FAIL",
        "clean" if fut == 0 else f"{fut} rows dated after today",
    )

    cal = trading_calendar(df["DT"])
    sheet_max = max(cal)
    sheet_min = min(cal)

    # ---- T13 coverage span
    span = (sheet_max - sheet_min).days / 365.25
    record(
        "T13",
        "Coverage span",
        "PASS" if span >= 1.0 else "WARN",
        f"{sheet_min.date()} to {sheet_max.date()} ({span:.2f} yr, {len(cal)} sessions)",
    )

    # ---- T14 sheet freshness
    behind = np.busday_count(sheet_max.date(), today.date())
    record(
        "T14",
        "Sheet freshness",
        "PASS" if behind <= 1 else ("WARN" if behind <= 3 else "FAIL"),
        f"latest row {sheet_max.date()}, {behind} business days behind today",
    )

    # ---- T15 sheet-wide date gaps  (D150 class)
    exp = pd.bdate_range(sheet_min, sheet_max)
    gaps = sorted(set(exp) - set(cal))
    record(
        "T15",
        "Sheet-wide session gaps",
        "PASS" if len(gaps) == 0 else "WARN",
        "none"
        if not gaps
        else f"{len(gaps)} missing weekdays (incl. holidays) e.g. "
        + ", ".join(str(g.date()) for g in gaps[:4]),
    )

    # ---- T16 rows per ticker
    per = df.groupby("TICKER")["DT"].count()
    thin = per[per < len(cal) * 0.25]
    record(
        "T16",
        "Rows per ticker",
        "PASS" if thin.empty else "WARN",
        f"median {int(per.median())} rows/ticker"
        if thin.empty
        else f"{len(thin)} thin tickers: " + ", ".join(f"{k}({v})" for k, v in thin.items()),
    )

    # ---- T17 ticker count
    record("T17", "Ticker universe", "PASS", f"{df['TICKER'].nunique()} tickers")

    # ================================================== D176 STALENESS
    last = df.groupby("TICKER")["DT"].max()
    lag = {tk: days_behind(cal, dt) for tk, dt in last.items()}

    stale = {k: v for k, v in lag.items() if STALE_DAYS < v < DEAD_DAYS}
    dead = {k: v for k, v in lag.items() if v >= DEAD_DAYS}
    fresh = {k: v for k, v in lag.items() if v <= STALE_DAYS}

    record(
        "T18",
        "D176 per-ticker staleness",
        "PASS" if not stale else "FAIL",
        f"all {len(fresh)} current"
        if not stale
        else f"{len(stale)} stale >{STALE_DAYS}d: "
        + ", ".join(f"{k} {v}d" for k, v in sorted(stale.items(), key=lambda x: -x[1])),
    )

    dead_real = {k: v for k, v in dead.items() if k not in retired}
    dead_ret = {k: v for k, v in dead.items() if k in retired}
    def fmt(d):
        items = sorted(d.items(), key=lambda x: -x[1])
        return ", ".join(f"{k} {v}d ({last[k].date()})" for k, v in items)

    msg = []
    if dead_real:
        msg.append(f"{len(dead_real)} DEAD (on roster, no writes >={DEAD_DAYS}d): " + fmt(dead_real))
    if dead_ret:
        msg.append(f"{len(dead_ret)} RETIRED (off roster, expected): " + fmt(dead_ret))
    record(
        "T19",
        "D176 dead feeds (roster-aware)",
        "FAIL" if dead_real else ("WARN" if dead_ret else "PASS"),
        " | ".join(msg) if msg else "none",
    )

    record("T20", "D176 current tickers", "PASS", f"{len(fresh)}/{len(lag)} within {STALE_DAYS} sessions")

    # ================================================== VALUE SANITY
    df = df.sort_values(["TICKER", "DT"])

    # ---- T21 extreme single-day moves
    df["RET"] = df.groupby("TICKER")["CLOSEN"].pct_change()
    ext = df[df["RET"].abs() > EXTREME_MOVE]
    record(
        "T21",
        "Extreme daily moves",
        "PASS" if ext.empty else "WARN",
        f"none >{EXTREME_MOVE:.0%}"
        if ext.empty
        else f"{len(ext)} moves >{EXTREME_MOVE:.0%}: "
        + ", ".join(f"{r.TICKER} {r.DT.date()} {r.RET:+.0%}" for r in ext.head(5).itertuples()),
    )

    # ---- T22 scale corruption  (the CRH / D158 class)
    med = df.groupby("TICKER")["CLOSEN"].transform("median")
    scale = df[(df["CLOSEN"] > med * SCALE_RATIO) | (df["CLOSEN"] < med / SCALE_RATIO)]
    record(
        "T22",
        "Scale corruption",
        "PASS" if scale.empty else "FAIL",
        f"no close >{SCALE_RATIO}x off ticker median"
        if scale.empty
        else f"{len(scale)} rows: "
        + ", ".join(f"{r.TICKER} {r.DT.date()} ${r.CLOSEN:,.2f}" for r in scale.head(5).itertuples()),
    )

    # ---- T23 frozen feeds
    frozen = []
    for tk, g in df.groupby("TICKER"):
        v = g["CLOSEN"].values
        run_len, best = 1, 1
        for i in range(1, len(v)):
            run_len = run_len + 1 if v[i] == v[i - 1] else 1
            best = max(best, run_len)
        if best >= FROZEN_RUN and tk not in CASH_TICKERS:
            frozen.append((tk, best))
    record(
        "T23",
        "Frozen price feeds",
        "PASS" if not frozen else "WARN",
        f"none (>={FROZEN_RUN} identical closes)"
        if not frozen
        else ", ".join(f"{k} {v} sessions flat" for k, v in frozen[:6]),
    )

    # ---- T24 null closes by ticker
    nullc = df[df["CLOSEN"].isna()].groupby("TICKER").size()
    record(
        "T24",
        "Null closes by ticker",
        "PASS" if nullc.empty else "FAIL",
        "none" if nullc.empty else ", ".join(f"{k} {v}" for k, v in nullc.items()),
    )

    # ---- T25 MOVE_% consistency
    if "MOVE_%" in df.columns:
        m = pd.to_numeric(df["MOVE_%"], errors="coerce")
        both = df["RET"].notna() & m.notna()
        if both.sum() > 0:
            scale_guess = 100 if m[both].abs().median() > 1 else 1
            diff = (m[both] / scale_guess - df.loc[both, "RET"]).abs()
            badm = int((diff > 0.005).sum())
            record(
                "T25",
                "MOVE_% consistency",
                "PASS" if badm == 0 else "WARN",
                f"{both.sum():,} checked, agree"
                if badm == 0
                else f"{badm}/{both.sum():,} disagree with computed return",
            )
        else:
            record("T25", "MOVE_% consistency", "SKIP", "column empty")
    else:
        record("T25", "MOVE_% consistency", "SKIP", "column absent")

    # ================================================== D171 BENFORD
    def benford(series, label, tid, group=None):
        # APPLICABILITY GATE. Benford's law requires data spanning several
        # orders of magnitude. A stock price does not: a ticker that lives
        # between $94 and $235 will produce first digits of 1 and 2 almost
        # exclusively, and SGOV at $100.xx produces a literal 100% "1".
        # Running Benford on that returns a huge chi2 that means nothing.
        # Gate first, report SKIP with the reason, never cry fraud.
        if group is not None:
            spread = (group.max() / group.min()).replace([np.inf, -np.inf], np.nan).dropna()
            orders = np.log10(spread)
            if orders.median() < 1.0:
                record(
                    tid,
                    f"D171 Benford ({label})",
                    "SKIP",
                    f"NOT APPLICABLE — median ticker spans {orders.median():.2f} "
                    f"orders of magnitude, {int((orders >= 1).sum())}/{len(orders)} span >=1. "
                    "Benford needs multi-order data (volume, market cap, dollar flows).",
                )
                return

        digits = (
            series.dropna().astype(float).abs().astype(str).str.replace(r"[^1-9]", "", regex=True).str[:1]
        )
        digits = digits[digits != ""]
        if len(digits) < 500:
            record(tid, f"D171 Benford ({label})", "SKIP", f"only {len(digits)} values")
            return
        obs = Counter(digits)
        n = len(digits)
        exp = {str(k): n * np.log10(1 + 1 / k) for k in range(1, 10)}
        chi = sum((obs.get(k, 0) - exp[k]) ** 2 / exp[k] for k in exp)
        # chi-square, 8 dof: 15.51 = p.05, 20.09 = p.01, 26.12 = p.001
        if chi < 15.51:
            st, note = "PASS", "conforms"
        elif chi < 26.12:
            st, note = "WARN", "mild deviation"
        else:
            st, note = "FAIL", "strong deviation — suspect synthetic/duplicated"
        top = ", ".join(
            f"{k}:{obs.get(k, 0) * 100 / n:.1f}%(exp {exp[k] * 100 / n:.1f}%)" for k in ["1", "2", "3"]
        )
        record(tid, f"D171 Benford ({label})", st, f"chi2={chi:.1f} dof=8 — {note} | {top}")

    benford(df["CLOSEN"], "CLOSE", "T26", group=df.groupby("TICKER")["CLOSEN"])

    # ---- T27 last-digit uniformity
    # Judge on EFFECT SIZE, not raw chi-square. At n~9,000 a chi-square test
    # flags deviations far too small to matter, and mild clustering on 0 and 5
    # is a real market artifact (round-number preference), not corruption.
    cents = (df["CLOSEN"].dropna() * 100).round().astype(int) % 10
    if len(cents) >= 500:
        obs = Counter(cents)
        n = len(cents)
        pct = {k: obs.get(k, 0) * 100 / n for k in range(10)}
        dev = max(abs(v - 10.0) for v in pct.values())
        worst = max(pct, key=lambda k: abs(pct[k] - 10.0))
        if dev < 3.0:
            st, note = "PASS", "uniform within tolerance"
        elif dev < 6.0:
            st, note = "WARN", "mild clustering — check rounding"
        else:
            st, note = "FAIL", "strong clustering — suspect fabricated/rounded"
        record(
            "T27",
            "Last-digit uniformity",
            st,
            f"max deviation {dev:.1f}pp (digit {worst} at {pct[worst]:.1f}%) — {note}",
        )
    else:
        record("T27", "Last-digit uniformity", "SKIP", "insufficient rows")

    # ================================================== D164 POSITION SANITY
    if holdings_path:
        try:
            h = load(holdings_path)
            h.columns = [c.strip().upper() for c in h.columns]
            valcol = next((c for c in h.columns if "VALUE" in c), None)
            tcol = next((c for c in h.columns if "TICKER" in c or "SYMBOL" in c), None)
            shcol = next((c for c in h.columns if "SHARE" in c), None)

            if valcol and tcol:
                hv = pd.to_numeric(
                    h[valcol].astype(str).str.replace(r"[$,]", "", regex=True), errors="coerce"
                )
                total = hv.sum()
                w = hv / total if total else hv * 0
                over = h.loc[w > MAX_WEIGHT, tcol].tolist()
                record(
                    "T28",
                    "D164 position weight",
                    "PASS" if not over else "FAIL",
                    f"book ${total:,.0f}, max weight {w.max():.1%}"
                    if not over
                    else f"{over} exceed {MAX_WEIGHT:.0%} of ${total:,.0f} book",
                )

                bigger = h.loc[hv > total, tcol].tolist()
                record(
                    "T29",
                    "D164 value vs book total",
                    "PASS" if not bigger else "FAIL",
                    "no position exceeds book total" if not bigger else f"{bigger} larger than entire book",
                )
            else:
                record("T28", "D164 position weight", "SKIP", "no VALUE/TICKER column")
                record("T29", "D164 value vs book total", "SKIP", "no VALUE/TICKER column")

            # cross-check shares x price
            if shcol and tcol:
                lastpx = df.groupby("TICKER")["CLOSEN"].last()
                sh = pd.to_numeric(h[shcol].astype(str).str.replace(",", ""), errors="coerce")
                impl = [
                    (h.loc[i, tcol], sh[i] * lastpx.get(h.loc[i, tcol], np.nan))
                    for i in h.index
                    if pd.notna(sh.get(i))
                ]
                bad = [(t, v) for t, v in impl if pd.notna(v) and v > total * 1.5]
                record(
                    "T30",
                    "D164 shares x price sanity",
                    "PASS" if not bad else "FAIL",
                    "implied values consistent"
                    if not bad
                    else ", ".join(f"{t} implies ${v:,.0f}" for t, v in bad[:4]),
                )
            else:
                record("T30", "D164 shares x price sanity", "SKIP", "no SHARES column")
        except Exception as e:
            for tid in ("T28", "T29", "T30"):
                record(tid, "D164 position sanity", "SKIP", f"holdings load failed: {e}")
    else:
        for tid, nm in (
            ("T28", "D164 position weight"),
            ("T29", "D164 value vs book total"),
            ("T30", "D164 shares x price sanity"),
        ):
            record(tid, nm, "SKIP", "no HOLDINGS file supplied")

    # ---- T31 cash sleeve isolation
    present = CASH_TICKERS & set(df["TICKER"].unique())
    record(
        "T31",
        "Cash sleeve tagged",
        "PASS" if present else "WARN",
        f"{sorted(present)} present and flagged non-tradeable"
        if present
        else "no cash ticker found in PRICE_HISTORY",
    )

    # ---- T32 encoding / stray whitespace
    stray = sum(
        int(df[c].astype(str).str.contains(r"^\s|\s$", regex=True, na=False).sum())
        for c in ["DATE", "TICKER", "CLOSE"]
    )
    record(
        "T32",
        "No stray whitespace",
        "PASS" if stray == 0 else "WARN",
        "clean" if stray == 0 else f"{stray} padded cells",
    )


# ---------------------------------------------------------------- report
def report():
    order = {"FAIL": 0, "WARN": 1, "SKIP": 2, "PASS": 3}
    counts = Counter(r[2] for r in RESULTS)
    width = max(len(r[1]) for r in RESULTS) + 2

    print("=" * 100)
    print("LEAN TERMINAL INTEGRITY BATTERY".center(100))
    print("=" * 100)
    for tid, name, status, detail in RESULTS:
        mark = {"PASS": "PASS", "WARN": "WARN", "FAIL": "FAIL", "SKIP": "SKIP"}[status]
        print(f"{tid}  [{mark}]  {name:<{width}} {detail}")
    print("-" * 100)
    print(
        f"  {counts['PASS']} PASS   {counts['WARN']} WARN   "
        f"{counts['FAIL']} FAIL   {counts['SKIP']} SKIP   "
        f"({len(RESULTS)} tests)"
    )
    print("=" * 100)

    if counts["FAIL"]:
        print("\nFAILURES")
        for tid, name, status, detail in sorted(RESULTS, key=lambda r: order[r[2]]):
            if status == "FAIL":
                print(f"  {tid}  {name}: {detail}")
    if counts["WARN"]:
        print("\nWARNINGS")
        for tid, name, status, detail in RESULTS:
            if status == "WARN":
                print(f"  {tid}  {name}: {detail}")
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    hold = None
    ret = None
    for a in sys.argv[2:]:
        if a.upper().startswith("RETIRED="):
            ret = a.split("=", 1)[1].split(",")
        else:
            hold = a
    run(sys.argv[1], hold, ret)
    sys.exit(report())
