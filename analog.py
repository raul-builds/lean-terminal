#!/usr/bin/env python3
"""
analog.py - D071 analog matcher + D194 HOP ON validation
Built L120 (2026-08-11).

Two studies, one file:
  A) HOP ON EVENT STUDY - what actually happens after the 8/20 cross fires
  B) ANALOG MATCHER - find historical shape matches, show what followed
"""
import sys
import numpy as np
import pandas as pd

STALE = {'CGC','HYFM','MSOS','TLRY','AMD','SPCX'}
CASH  = {'SGOV'}

def load(p):
    df = pd.read_csv(p, dtype=str)
    df['d'] = pd.to_datetime(df.DATE, format='mixed', errors='coerce')
    df['c'] = pd.to_numeric(df.CLOSE, errors='coerce')
    df = df.dropna(subset=['d','c']).sort_values(['TICKER','d'])
    return df[~df.TICKER.isin(STALE | CASH)]

def emas(s):
    return (s.ewm(span=8,adjust=False).mean(),
            s.ewm(span=20,adjust=False).mean(),
            s.ewm(span=50,adjust=False).mean())

# ---------------- A) HOP ON / HOP OFF EVENT STUDY ----------------
def event_study(df, horizons=(1,3,5,10,20)):
    on, off = [], []
    for tk, g in df.groupby('TICKER'):
        g = g.reset_index(drop=True)
        if len(g) < 120: continue
        e8, e20, _ = emas(g.c)
        above = e8 > e20
        cross_up   = above & (~above.shift(1).astype("boolean")).fillna(False)
        cross_down = (~above) & above.shift(1).astype("boolean").fillna(False)
        for i in np.where(cross_up)[0]:
            if i < 50 or i >= len(g)-max(horizons): continue
            base = g.c.iloc[i]
            on.append({'ticker':tk,'date':g.d.iloc[i],'px':base,
                       **{f'r{h}':(g.c.iloc[i+h]/base-1)*100 for h in horizons}})
        for i in np.where(cross_down)[0]:
            if i < 50 or i >= len(g)-max(horizons): continue
            base = g.c.iloc[i]
            off.append({'ticker':tk,'date':g.d.iloc[i],'px':base,
                        **{f'r{h}':(g.c.iloc[i+h]/base-1)*100 for h in horizons}})
    return pd.DataFrame(on), pd.DataFrame(off)

def baseline(df, horizons=(1,3,5,10,20)):
    out = {h:[] for h in horizons}
    for tk, g in df.groupby('TICKER'):
        g = g.reset_index(drop=True)
        if len(g) < 120: continue
        for h in horizons:
            r = (g.c.shift(-h)/g.c - 1)*100
            out[h].extend(r.dropna().tolist())
    return {h: np.array(v) for h,v in out.items()}

# ---------------- B) ANALOG MATCHER ----------------
def zshape(w):
    w = np.asarray(w, float)
    r = np.diff(np.log(w))
    s = r.std()
    return r/s if s > 0 else r

def analogs(df, ticker, window=20, fwd=10, top=25):
    tgt = df[df.TICKER==ticker].sort_values('d').reset_index(drop=True)
    if len(tgt) < window+5: return None, None
    q = zshape(tgt.c.tail(window).values)
    hits = []
    for tk, g in df.groupby('TICKER'):
        g = g.reset_index(drop=True)
        c = g.c.values
        for i in range(window, len(c)-fwd):
            seg = c[i-window:i]
            # skip overlap with the query itself
            if tk == ticker and i > len(c)-window-fwd-5: continue
            cand = zshape(seg)
            if len(cand) != len(q): continue
            d = np.sqrt(((cand-q)**2).sum())
            hits.append((d, tk, g.d.iloc[i-1], (c[i+fwd-1]/c[i-1]-1)*100))
    hits.sort(key=lambda x: x[0])
    best = hits[:top]
    fwds = np.array([h[3] for h in best])
    return best, fwds

def pct(a, q): return np.percentile(a, q)

def show(name, arr, base=None):
    if len(arr)==0:
        print(f'  {name}: no observations'); return
    win = (arr>0).mean()*100
    line = (f'  {name:>6s}  n={len(arr):5d}  mean {arr.mean():+6.2f}%  '
            f'median {np.median(arr):+6.2f}%  win {win:5.1f}%  '
            f'p10 {pct(arr,10):+7.2f}  p90 {pct(arr,90):+7.2f}')
    if base is not None and len(base)>0:
        line += f'   vs base {base.mean():+.2f}% / {(base>0).mean()*100:.1f}%'
    print(line)

if __name__ == '__main__':
    path = sys.argv[1]
    df = load(path)
    print('='*104)
    print(f'ANALOG + EVENT STUDY   rows={len(df):,}  tickers={df.TICKER.nunique()}  '
          f'{df.d.min().date()} to {df.d.max().date()}')
    print(f'excluded: stale {sorted(STALE)}  cash {sorted(CASH)}')
    print('='*104)

    H=(1,3,5,10,20)
    on, off = event_study(df, H)
    base = baseline(df, H)

    print(f'\n--- A) HOP ON  (8 EMA crosses ABOVE 20 EMA)   {len(on)} events ---')
    for h in H: show(f'+{h}d', on[f'r{h}'].values, base[h])
    print(f'\n--- HOP OFF  (8 EMA crosses BELOW 20 EMA)   {len(off)} events ---')
    for h in H: show(f'+{h}d', off[f'r{h}'].values, base[h])
