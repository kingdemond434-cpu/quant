"""The execution-entry families: registered, classified into `execution_entry`, causal, mintable.

`execution_entry` was a declared alpha cluster that no registered family classified into, so the
breadth law could raise no debt against it and `empty_cluster_forcer` filed it UNREACHABLE. These
tests pin the four things that make the cluster reachable rather than merely named:

  REGISTERED   both names resolve through the gauntlet's own two lookups and read BUILDABLE
  CLASSIFIED   `alpha_clusters.classify_family` places each in execution_entry by exact key, and
               `axis_registry` gives each a named mechanism (an UNKNOWN one raises no debt)
  CAUSAL       a decision uses only the spread of bars that had CLOSED, and a session threshold
               never includes the bar it judges
  MINTABLE     a seat row naming the family, or prose naming its phrase, compiles to a cell the
               sealed gauntlet builds on real bars with the family defaults
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK / "scripts"), str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import family_execution_entry as fee  # noqa: E402
from mt5desk.engine import Signal  # noqa: E402

NAMES = fee.FAMILY_NAMES
UNIVERSE = _DESK / "data" / "universe"


def _bars(n: int = 3000, seed: int = 7, wide_hour: int = 0) -> pd.DataFrame:
    """An hourly random walk whose spread is wide on the rollover/open bar and normal after it,
    the shape measured on the committed store (EURUSD 16 against 12 points at server hour 0)."""
    rng = np.random.default_rng(seed)
    close = 1.10 + np.cumsum(rng.normal(0, 0.0012, n))
    open_ = np.concatenate([[1.10], close[:-1]])
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 0.0008, n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 0.0008, n))
    idx = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    spread = rng.integers(10, 14, n).astype(float)
    spread[idx.hour == wide_hour] += 20.0
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close,
                         "tick_volume": rng.integers(50, 500, n), "spread": spread}, index=idx)


def _key(sigs: list[Signal]) -> list[tuple]:
    return sorted((pd.Timestamp(s.time).value, s.side, round(s.stop, 8), round(s.target, 8),
                   s.tag) for s in sigs)


# ------------------------------------------------------------------------------- registered ---
def test_both_families_are_in_the_registry_the_gauntlet_reads_and_read_buildable() -> None:
    from mt5desk import families, families_orthogonal as fo
    from research.gauntlet_buildability import BUILDABLE, family_verdict
    for name in NAMES:
        assert fo.ORTHOGONAL_FAMILIES[name] is fee.FAMILIES[name]
        assert families.get_family_func(name) is fee.FAMILIES[name]
        assert fo.FAMILY_INPUTS[name][0] == "price only"
        assert "H4" not in fo.FAMILY_TIMEFRAMES[name][0] and "H1" in fo.FAMILY_TIMEFRAMES[name][0]
        verdict, why = family_verdict(name)
        assert verdict == BUILDABLE, why


def test_no_argument_is_required_so_family_defaults_build_a_cell() -> None:
    import inspect
    for name in NAMES:
        sig = inspect.signature(fee.FAMILIES[name])
        required = [p for p in sig.parameters.values()
                    if p.default is inspect.Parameter.empty and p.name != "df"]
        assert required == [], f"{name} requires {required}: a default mint could not build it"


# ------------------------------------------------------------------------------- classified ---
def test_each_family_classifies_into_execution_entry_by_exact_key() -> None:
    from libs.research import alpha_clusters as ac
    for name in NAMES:
        assert ac.FAMILY_CLUSTER[name] == fee.TARGET_CLUSTER == "execution_entry"
        assert ac.classify_family(name) == "execution_entry"
        assert ac.classify_sleeve(f"EURUSD_{name}_asia") == "execution_entry"
    declared = {k for k, v in ac.FAMILY_CLUSTER.items()
                if v == "execution_entry" and k.startswith("entry_alpha_")}
    assert declared == set(NAMES), "the cluster map and the module disagree on the family set"


def test_each_family_has_a_named_mechanism_so_the_breadth_law_can_raise_a_debt() -> None:
    import research.axis_registry as ar
    for name in NAMES:
        mech, info, style = ar.classify_family(name)
        assert mech == "execution_microstructure" and info == "microstructure", name
        assert style == "market"
        assert ar.MECHANISM_ACTOR[mech] != ar.UNKNOWN
    assert set(NAMES) <= ar.registered_families()


def test_the_empty_cluster_forcer_now_finds_a_donatable_family_for_execution_entry() -> None:
    from research.empty_cluster_forcer import _families_by_cluster, _testable
    donatable, registered = _families_by_cluster()
    assert set(NAMES) <= set(donatable.get("execution_entry") or [])
    assert set(NAMES) <= set(registered.get("execution_entry") or [])
    ok, bad = _testable(list(NAMES))
    assert set(ok) == set(NAMES) and not bad


# ----------------------------------------------------------------------------------- causal ---
@pytest.mark.parametrize("name", NAMES)
def test_signals_do_not_change_when_the_future_changes(name: str) -> None:
    """Corrupt prices AND spreads after the split: every signal at or before it must stand."""
    clean = _bars()
    split = 2000
    dirty = clean.copy()
    rng = np.random.default_rng(99)
    m = len(clean) - split
    for col in ("open", "high", "low", "close"):
        dirty.iloc[split:, dirty.columns.get_loc(col)] = (
            clean[col].to_numpy()[split:] + rng.normal(0, 0.01, m))
    dirty.iloc[split:, dirty.columns.get_loc("spread")] = rng.integers(1, 90, m).astype(float)
    cutoff = clean.index[split - 1]
    fn = fee.FAMILIES[name]
    a = [s for s in fn(clean, base_family="failed_breakout") if s.time <= cutoff]
    b = [s for s in fn(dirty, base_family="failed_breakout") if s.time <= cutoff]
    assert a, f"{name} emitted nothing on the fixture; the invariant would pass vacuously"
    assert _key(a) == _key(b)


def test_the_spread_of_the_fill_bar_never_decides_its_own_entry() -> None:
    """The defect to avoid: admitting an entry on the spread of the bar it FILLS in, which has
    not closed when the order is sent. Widening only the fill bar of a decision must leave that
    decision, and every one before it, exactly as it was."""
    d = _bars()
    fn = fee.family_entry_alpha_spread_session_median
    base = fn(d, base_family="failed_breakout")
    assert len(base) > 20
    for s in base[:: max(1, len(base) // 20)]:
        j = d.index.get_loc(s.time)
        if j + 1 >= len(d):
            continue
        poked = d.copy()
        poked.iloc[j + 1, poked.columns.get_loc("spread")] = 500.0
        before = [g for g in base if g.time <= s.time]
        after = [g for g in fn(poked, base_family="failed_breakout") if g.time <= s.time]
        assert _key(before) == _key(after), f"the fill bar after {s.time} moved a decision"


def test_a_session_threshold_never_includes_the_bar_it_judges() -> None:
    d = _bars(800)
    sp = d["spread"].copy()
    labels = fee.session_labels(pd.DatetimeIndex(d.index))
    t0 = fee.session_threshold(sp, labels, window=40, spread_q=0.5)
    i = 700
    sp.iloc[i] = 10_000.0
    t1 = fee.session_threshold(sp, labels, window=40, spread_q=0.5)
    assert t0.iloc[i] == t1.iloc[i]


def test_session_labels_follow_the_one_shared_window_table() -> None:
    from mt5desk.family_call import SESSIONS
    idx = pd.date_range("2024-01-01", periods=24, freq="1h", tz="UTC")
    lab = dict(zip(idx.hour, fee.session_labels(idx), strict=True))
    assert lab[SESSIONS["asia"][0]] == "asia" and lab[SESSIONS["london"][0]] == "london"
    assert lab[SESSIONS["ny"][0]] == "ny"          # the overlap belongs to the newer session
    assert lab[23] == "off"
    assert fee.session_opens() == tuple(sorted(w[0] for w in SESSIONS.values() if w))


# ---------------------------------------------------------------------------- the operators ---
def test_a_wide_spread_decision_waits_for_the_normal_bar_and_keeps_its_geometry() -> None:
    # asia_momentum decides at server hour 7; the fixture widens that bar's spread. (The default
    # base, overnight_gap_decay, needs real gaps a random walk does not print.)
    d = _bars(wide_hour=7)
    fn = fee.family_entry_alpha_spread_session_median
    base = {s.time: s for s in fee.base_signals(fee._h1(d), "asia_momentum", None)}
    out = fn(d, base_family="asia_momentum")
    moved = [s for s in out if s.tag.startswith("entry_alpha_spread_session_median<")]
    assert moved, "the wide-spread decisions should be held to a later bar"
    assert all(s.time.hour != 7 for s in out)      # the wide bar never admits an entry
    for s in moved:
        src = max(t for t in base if t < s.time)
        ref_old, ref_new = float(d["close"][src]), float(d["close"][s.time])
        assert abs(ref_new - s.stop) == pytest.approx(abs(ref_old - base[src].stop))
        assert abs(s.target - ref_new) == pytest.approx(abs(base[src].target - ref_old))
        assert s.side == base[src].side and s.trigger is None


def test_post_open_moves_only_open_window_fills_and_lands_past_the_window() -> None:
    d = _bars(wide_hour=7)                         # asia_momentum fills at 08:00, the open
    out = fee.family_entry_alpha_post_open_normalised(d, base_family="asia_momentum",
                                                      open_minutes=120)
    assert out
    for s in out:
        fill_hour = (s.time + pd.Timedelta(hours=1)).hour
        since = min((fill_hour - o) % 24 for o in fee.session_opens())
        assert since >= 2, f"{s.time} fills inside an open window"


def test_refusals_return_nothing_rather_than_a_price_only_fallback() -> None:
    d = _bars()
    for name, fn in fee.FAMILIES.items():
        assert fn(d.drop(columns=["spread"])) == [], name
        assert fn(d, base_family="discovered") == [], name           # banned / unwrappable
        assert fn(d, base_family="carry") == [], name                # needs an injected input
        assert fn(d, base_family=name) == [], name                   # no operator over itself
        assert fn(d, base_family="no_such_family") == [], name
        assert fn(d, spread_q=1.5) == [], name
        assert fn(d.iloc[:100]) == [], name


def test_a_stop_entry_base_has_no_market_entry_to_move() -> None:
    d = _bars()
    sigs = fee.base_signals(fee._h1(d), "session_range_breakout", None)
    assert all(s.trigger is None for s in sigs)


# --------------------------------------------------------------------------------- mintable ---
UNI = {"EURUSD", "GBPUSD", "USDJPY", "XAUUSD"}


@pytest.mark.parametrize("name", NAMES)
def test_a_seat_row_naming_the_family_compiles_with_family_defaults(name: str) -> None:
    from research import miner_candidate_compiler as mcc
    row = {"source": "deepseek", "kind": "hypothesis", "title": "entry timing", "mechanism": "",
           "testable_claim": "", "symbols": ["EURUSD"], "family": name, "mechanism_tags": [],
           "url": "deepseek://x"}
    cands, disp = mcc.compile_row("deepseek", row, UNI)
    assert disp == "STRUCTURED_HYPOTHESIS"
    (c,) = cands
    assert (c["symbol"], c["family"], c["params"]) == ("EURUSD", name, {})


def test_prose_naming_the_mechanism_compiles_to_the_family() -> None:
    from research import miner_candidate_compiler as mcc
    fams = {f for f, _ in mcc.text_families(
        "on eurusd, wait for the spread to normalise after the rollover before entering.")}
    assert "entry_alpha_post_open_normalised" in fams


@pytest.mark.parametrize("name", NAMES)
def test_the_sealed_gauntlet_builds_a_default_cell_with_signals_on_real_bars(name: str) -> None:
    if not (UNIVERSE / "EURUSD_H1.parquet").exists():
        pytest.skip("EURUSD_H1 bars not on this checkout")
    eg = pytest.importorskip("external_gauntlet")
    import json
    meta = json.loads((UNIVERSE / "universe.json").read_text(encoding="utf-8"))
    cell = eg.build_cell("EURUSD", name, {}, meta)
    assert cell is not None, getattr(eg, "LAST_BUILD_FAILURE", None)
    assert len(cell["sigs"]) >= 60, f"{name}: {len(cell['sigs'])} signals at family defaults"
