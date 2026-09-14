#!/usr/bin/env python3
"""
prep.py — canonical tape builder for Lean Terminal  (D289)
Converts the Apps Script PRICE_HISTORY export (JS Date.toString(), raw CLOSE values)
into an ISO-dated CSV with values untouched. Writes a trailing newline (D288).

USAGE  python3 prep.py RAW_EXPORT.csv OUT.csv
"""
import sys, re, csv, hashlib

MON = {'Jan':1,'Feb':2,'Mar':3,'Apr':4,'May':5,'Jun':6,
       'Jul':7,'Aug':8,'Sep':9,'Oct':10,'Nov':11,'Dec':12}
JS = re.compile(r'^[A-Za-z]{3} ([A-Za-z]{3}) (\d{2}) (\d{4})')

def to_iso(s):
    s = (s or '').strip()
    if re.match(r'^\d{4}-\d{2}-\d{2}$', s):        # already ISO, pass through
        return s
    m = JS.match(s)
    if not m:
        return None
    return f"{m.group(3)}-{MON[m.group(1)]:02d}-{int(m.group(2)):02d}"

def main(src, dst):
    with open(src, newline='') as f:
        rows = list(csv.reader(f))
    hdr, body = rows[0], rows[1:]
    di = hdr.index('DATE')
    bad = []
    for i, r in enumerate(body):
        iso = to_iso(r[di])
        if iso is None:
            bad.append(i + 2)
        else:
            r[di] = iso
    if bad:
        sys.exit(f"ABORT: {len(bad)} unparsed DATE rows, first at line {bad[0]}")
    with open(dst, 'w', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(hdr); w.writerows(body)          # csv module ends final line -> trailing newline
    raw = open(dst,'rb').read()
    nl = raw.endswith(bytes([10]))
    sha = hashlib.sha256(raw).hexdigest()[:16]
    print('rows %d | bytes %d | trailing_newline %s | sha256 %s' % (len(body), len(raw), nl, sha))

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
