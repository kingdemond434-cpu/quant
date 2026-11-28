"""DATA-46: each source declares the window its state can move a price over, its decay, its
release session and its release clock; the compiler demotes (never drops) charts outside the
window, mints session-transfer cells that read the state only once it is public, and the judge's
docket ranks the compiler's priority inside each family's own slots."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import cell_modifiers as cm  # noqa: E402
from mt5desk.family_call import SESSIONS  # noqa: E402

from libs.mining import release_clock as rc  # noqa: E402
from libs.mining import source_horizon as sh  # noqa: E402
from libs.tiers import prejudge_screen as pj  # noqa: E402
from research import judge_coverage as jc  # noqa: E402
from research import merge_hypotheses as mh  # noqa: E402
from research import miner_candidate_compiler as mcc  # noqa: E402


def _w(*a: int) -> datetime:
    return rc.wall(*a)


def _cand(source: str) -> dict:
    return {"symbol": "EURUSD", "family": "trend_ma_cross", "params": {"fast": 10},
            "source": f"miner:{source}", "mechanism_status": "NAMED"}


def test_every_declared_seat_is_a_real_window_with_a_release_clock() -> None:
    doc = json.loads(sh.TABLE.read_text("utf-8"))
    for seat, d in doc["seats"].items():
        if d.get("kind") == "strategy":
            continue
        assert 0 < d["min_h"] < d["max_h"], seat
        assert 0 < d["decay_half_life_h"] <= d["max_h"], seat
        assert d.get("release_session") in (None, *sh.SESSION_ORDER), seat
        rel = d["release"]
        assert rel["kind"] in rc.KINDS and rel["tz"], seat
        if rel["kind"] == "weekly":
            assert 0 <= rel["weekday"] <= 6 and len(rel["local"]) == 5, seat


def test_the_release_clock_sessions_are_the_desks_sessions() -> None:
    assert {n: (lo, hi) for n, lo, hi in rc.SESSION_WINDOWS} == {
        k: v for k, v in SESSIONS.items() if v is not None}


def test_chart_fit_reads_the_window_and_undeclared_is_never_inside() -> None:
    weekly = {"min_h": 24, "max_h": 720}
    assert sh.chart_fit("M5", weekly) == "OUTSIDE"        # 24h spans 288 M5 bars
    assert sh.chart_fit("M30", weekly) == "INSIDE"
    assert sh.chart_fit("D1", weekly) == "INSIDE"
    fast = {"min_h": 0.05, "max_h": 8}
    assert sh.chart_fit("D1", fast) == "OUTSIDE" and sh.chart_fit("H4", fast) == "INSIDE"
    assert sh.chart_fit("H1", None) == "UNDECLARED"
    assert sh.declared("mql5_signals") is None             # a strategy carries its own horizon
    assert sh.declared("no_such_seat") is None


def test_a_row_overrides_its_seat() -> None:
    d = sh.declared("cot", {"max_h": 48, "release_session": "asia"})
    assert d is not None and d["max_h"] == 48 and d["release_session"] == "asia"
    assert d["min_h"] == 24                                 # untouched keys stay the seat's


def test_release_instants_convert_through_new_york_daylight_saving() -> None:
    # COT: Friday 15:30 New York is 22:30 broker in summer AND winter (broker = NY + 7h).
    summer = rc.release_instants("cot", _w(2026, 7, 1), _w(2026, 7, 8))
    winter = rc.release_instants("cot", _w(2026, 1, 5), _w(2026, 1, 12))
    assert summer[-1] == _w(2026, 7, 3, 22, 30)
    assert winter[-1] == _w(2026, 1, 9, 22, 30)
    # A non-New-York zone moves on the broker clock with BOTH daylight-saving calendars.
    jul = rc.broker_wall(rc.to_utc(_w(2026, 7, 15, 10, 0), "Asia/Shanghai"))
    jan = rc.broker_wall(rc.to_utc(_w(2026, 1, 15, 10, 0), "Asia/Shanghai"))
    assert (jul.hour, jan.hour) == (5, 4)


def test_the_us_rule_fallback_matches_the_timezone_database(monkeypatch) -> None:
    probes = [_w(2026, 3, 8, 6, 59), _w(2026, 3, 8, 7, 1),
              _w(2026, 11, 1, 5, 59), _w(2026, 11, 1, 6, 1),
              _w(2026, 7, 1, 12), _w(2026, 1, 1, 12)]
    want = [rc.broker_wall(p) for p in probes]
    monkeypatch.setattr(rc, "_zone", lambda tz: None)
    assert [rc.broker_wall(p) for p in probes] == want


def test_only_scheduled_seats_mint_and_the_lags_respect_the_release() -> None:
    # COT lands at 22:30 broker, after New York closes: no own-session window exists, so the
    # first transfer is Monday Asia. AAII (Thursday 23:59 NY = Friday 06:59 broker) lands in Asia.
    assert rc.mintable_lags("cot") == (1, 2, 3)
    assert rc.mintable_lags("aaii") == (0, 1, 2, 3)
    assert rc.mintable_lags("china") == () and rc.mintable_lags("broker_swaps") == ()
    assert rc.refusal("china:1") and rc.refusal("cot:9") and rc.refusal("nonsense")
    assert rc.refusal("cot:1") is None


def test_the_gate_reads_the_state_only_once_public_and_while_it_lasts() -> None:
    # Release Fri 2026-07-03 22:30 broker. Lag 1 = Monday Asia (00:00-08:00).
    times = [_w(2026, 7, 3, 21, 0),     # Friday NY, before the release: not yet public
             _w(2026, 7, 6, 3, 0),      # Monday Asia: the first session after it
             _w(2026, 7, 6, 9, 0),      # Monday London: lag 2, not lag 1
             _w(2026, 7, 13, 3, 0)]     # next Monday Asia: next release's lag-1 window
    assert rc.gate(times, "cot:1") == [False, True, False, True]
    assert rc.gate(times, "cot:2") == [False, False, True, False]
    # Decay: age beyond log2(1/DECAY_FLOOR) half-lives keeps nothing (cot HL 168h -> 336h).
    assert rc.max_age_h("cot") == 336.0 and rc.decay_weight("cot", 168) == 0.5


def test_cell_modifiers_apply_the_gate_even_for_a_kwargs_family() -> None:
    def fam(df, **kw):
        return []
    kwargs, mods = cm.split(fam, {"fast": 3, "release_gate": "cot:1"})
    assert kwargs == {"fast": 3} and mods == {"release_gate": "cot:1"}
    assert cm.refusal(mods) is None and cm.refusal({"release_gate": "china:1"})
    sig = [SimpleNamespace(time=_w(2026, 7, 3, 21, 0), side=1),
           SimpleNamespace(time=_w(2026, 7, 6, 3, 0), side=1)]
    kept = cm.apply(sig, None, mods)                        # type: ignore[arg-type]
    assert [s.time for s in kept] == [_w(2026, 7, 6, 3, 0)]


def _universe(tmp_path, monkeypatch) -> None:
    uni = tmp_path / "universe"
    uni.mkdir()
    for tf in ("M5", "M30", "H1"):
        (uni / f"EURUSD_{tf}.parquet").write_bytes(b"")
    monkeypatch.setattr(mcc, "UNIVERSE", uni)


def test_the_compiler_demotes_outside_cells_and_mints_transfer_cells(tmp_path,
                                                                    monkeypatch) -> None:
    _universe(tmp_path, monkeypatch)
    plain = mcc.expand_axes([_cand("reddit")])
    cot = mcc.expand_axes([_cand("cot")])
    sessions = [v for v in cot if "release_gate" not in v["params"]]
    transfer = [v for v in cot if "release_gate" in v["params"]]
    assert len(sessions) == len(plain)                      # nothing removed
    assert len(transfer) == 3 * 3                           # 3 charts x lags (1, 2, 3)
    m5 = [v for v in sessions if v["axis"]["chart"] == "M5"]
    m30 = [v for v in sessions if v["axis"]["chart"] == "M30"]
    assert all(v["source_horizon"]["fit"] == "OUTSIDE" and v["priority"] == 2 for v in m5)
    assert all(v["source_horizon"]["fit"] == "INSIDE" and v["priority"] == 0 for v in m30)
    assert all("session_transfer" not in v for v in sessions)   # a label is not a test
    ids = {json.dumps(v["params"], sort_keys=True) for v in cot}
    assert len(ids) == len(cot)                             # each transfer cell its own identity
    again = mcc.expand_axes([_cand("cot")])
    assert [v.get("genome_id") for v in again] == [v.get("genome_id") for v in cot]
    assert {v["session_transfer"]["lag_sessions"] for v in transfer} == {1, 2, 3}
    assert all(v["source_horizon"]["fit"] == "UNDECLARED" for v in plain)
    t = sh.tally(cot)
    assert t["fit"] == {"OUTSIDE": 4 + 3, "INSIDE": 8 + 6}
    assert t["transfer_cells"] == {"cot:1": 3, "cot:2": 3, "cot:3": 3}
    assert t["releases"]["cot"]["broker_summer"] == "Fri 22:30"


def test_a_cell_two_seats_produce_gets_one_label_whatever_the_order() -> None:
    def cell(src: str) -> dict:
        c = {**_cand(src), "axis": {"chart": "M5", "session": "all"}, "priority": 0}
        c["priority"] += sh.annotate(c, "M5")
        return c
    a, b = cell("cot"), cell("microstructure")              # cot: M5 OUTSIDE, micro: INSIDE
    assert a["priority"] == 2 and b["priority"] == 0
    for c in (a, b):
        sh.resolve(c, ["miner:microstructure", "miner:cot"])
    assert a["priority"] == b["priority"] == 0
    assert a["source_horizon"] == b["source_horizon"]
    assert a["source_horizon"]["seat"] == "microstructure"


def _rows() -> list[dict]:
    out = []
    for fam in ("f1", "f2"):
        for i, pr in enumerate((2, 0, 1, 0)):
            out.append({"family": fam, "symbol": "EURUSD", "params": {"i": i},
                        "axis": {"chart": "M5", "session": "all"}, "priority": pr})
    out.append({"family": "f1", "symbol": "EURUSD", "params": {"i": 9}, "priority": 99})
    return out


def test_the_docket_ranks_priority_inside_family_slots_and_removes_nothing() -> None:
    """THE PROBE: same rows, same per-family slot positions, priority 0 first inside them."""
    rows = jc.coverage_order(_rows(), {"f1": 1, "f2": 1})
    flat = jc.coverage_order(_rows(), {"f1": 1, "f2": 1}, use_priority=False)
    assert [r["family"] for r in rows] == [r["family"] for r in flat]   # interleave unchanged
    assert len(rows) == len(_rows())
    f1 = [jc.docket_priority(r) for r in rows if r["family"] == "f1"]
    assert f1 == sorted(f1)
    # a foreign `priority` (no compiler `axis`) is never read as the compiler's rank
    assert jc.docket_priority({"priority": 99}) == 0
    # the slot-preserving helper, the merge fallback copy and the prejudge screen all keep it
    base = _rows()
    for got in (jc.priority_within_family(base), mh._priority_within_family(base)):
        assert [r["family"] for r in got] == [r["family"] for r in base]
        assert [jc.docket_priority(r) for r in got if r["family"] == "f2"] == [0, 0, 1, 2]
    ranked = jc.priority_within_family(base)
    demoted, _ = pj.demote_flagged(ranked, {})
    assert demoted == ranked
    # a stronger tier (never-judged) stays above the priority
    tiered = jc.priority_within_family(base, tier=lambda r: 0 if r["params"]["i"] == 0 else 1)
    assert next(r["params"]["i"] for r in tiered if r["family"] == "f2") == 0


def test_the_compile_leg_names_the_compiler_as_its_code() -> None:
    from desks.mt5.ops import components
    spec = next(s for s in components.hourly_leg_specs()
                if s.component_id == "leg:compile_candidates")
    assert "desks/mt5/research/miner_candidate_compiler.py" in spec.code_paths
