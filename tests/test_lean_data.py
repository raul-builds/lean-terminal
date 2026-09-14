"""Golden + unit tests for the Lean Terminal research engine. (#14, L156)
Every bug this project paid for in a session gets a test here so it cannot return."""
import datetime as dt, subprocess, sys, os, csv, tempfile
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lean_data import load_canonical_tape, Universe, is_session, NYSE_HOLIDAYS
import d250r

_HERE = os.path.dirname(os.path.abspath(__file__))
TAPE = os.environ.get("LEAN_TAPE", os.path.join(_HERE, "fixtures", "tape_fixture.csv"))
pytestmark = pytest.mark.skipif(not os.path.exists(TAPE), reason="canonical tape not present")

def _tape(): return load_canonical_tape(TAPE)

# ---- calendar (D016) -------------------------------------------------------
def test_weekend_is_not_a_session():
    assert not is_session(dt.date(2026, 9, 12))   # Saturday
    assert not is_session(dt.date(2026, 9, 13))   # Sunday
def test_labor_day_2026_is_not_a_session():
    assert not is_session(dt.date(2026, 9, 7))
def test_ordinary_weekday_is_a_session():
    assert is_session(dt.date(2026, 9, 10))
def test_holiday_table_covers_the_tape_era():
    assert any(h.startswith("2024") for h in NYSE_HOLIDAYS), "T15 gap: pre-2026 holidays missing"

# ---- loader (D242 / D288) --------------------------------------------------
def test_no_weekend_rows_survive_load():
    t = _tape()
    assert all(d.weekday() < 5 for s in t.series.values() for d, _ in s)
def test_no_duplicate_ticker_date():
    t = _tape()
    for tk, s in t.series.items():
        assert len({d for d, _ in s}) == len(s), f"dupe (date,ticker) in {tk}"
def test_series_sorted_ascending():
    t = _tape()
    for tk, s in t.series.items():
        assert [d for d, _ in s] == sorted(d for d, _ in s), f"{tk} unsorted"
def test_js_dates_are_rejected_not_silently_dropped():
    """D288: a raw JS-date export must not load as an empty-but-plausible tape."""
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
        w = csv.writer(f); w.writerow(["DATE","TICKER","CLOSE"])
        w.writerow(["Thu Dec 11 2025 16:00:00 GMT-0800 (Pacific Standard Time)","NVDA","100"])
        p = f.name
    t = load_canonical_tape(p); os.unlink(p)
    assert len(t) == 0 and t.stats["unparsed"] == 1

# ---- point-in-time universe (D146 / D293) ----------------------------------
def test_retired_tickers_are_eligible_before_retirement():
    u = Universe.from_tape(_tape())
    assert "AMD" in u.eligible_on("2026-01-15"), "look-ahead: AMD excluded from its own live era"
def test_retired_tickers_are_ineligible_after():
    u = Universe.from_tape(_tape())
    assert "AMD" not in u.eligible_on("2026-09-10")
    assert "AMD" in u.retired_as_of("2026-09-10")
def test_cash_is_not_in_the_universe():
    assert "SGOV" not in Universe.from_tape(_tape()).spans

# ---- fill clock (Astra finding #1, L156) -----------------------------------
def test_next_close_fill_lags_one_more_bar_than_legacy():
    """The whole point of D250-R. If this passes trivially the lag was lost."""
    ret = [0.0, 0.10, 0.10, 0.10]
    legacy = d250r.equity(ret[1:], [1, 1, 1], cost=False, cash=False)
    lagged = d250r.equity(ret[1:], [0, 1, 1], cost=False, cash=False)
    assert lagged < legacy
def test_costs_reduce_equity_on_every_transition():
    ret = [0.0]*6
    flat = d250r.equity(ret, [0,1,0,1,0,1], cost=False, cash=False)
    paid = d250r.equity(ret, [0,1,0,1,0,1], cost=True,  cash=False)
    assert paid < flat
def test_cash_pays_only_when_flat():
    ret = [0.0]*10
    assert d250r.equity(ret, [0]*10, cost=False, cash=True) > 0
    assert d250r.equity(ret, [1]*10, cost=False, cash=True) == pytest.approx(0.0, abs=1e-12)

# ---- determinism (doctrine) ------------------------------------------------
def test_bootstrap_is_seeded_and_reproducible():
    e = [0.01*i % 0.07 for i in range(200)]
    assert d250r.block_boot(e, reps=200) == d250r.block_boot(e, reps=200)

# ---- golden: the ratified D250-R numbers must not drift ---------------------
def test_golden_d250r_headline():
    t = _tape(); u = Universe.from_tape(t); g, r0 = d250r.regime_fn(t)
    res = d250r.windows(t, u, g, r0, pit=True)
    w, tie, l, med, _ = d250r.score(res, "v2", "v1")
    assert len(res) == 248
    assert (w, tie, l) == (150, 10, 88)
    assert med == pytest.approx(0.0253, abs=5e-4)
