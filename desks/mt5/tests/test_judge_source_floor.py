"""The alt-data source floor: a minimum share of every prefix of the judge's build list per source
family while it is judged below the desk-wide ratio; a permutation, never a cap."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import judge_source_floor as jsf  # noqa: E402

TABLE = {"cot": {"min_share": 0.10, "members": ("cot_a", "cot_b")},
         "tape": {"min_share": 0.10, "members": ("tape_a",)}}


def _rows(spec: list[tuple[str, int]]) -> list[dict]:
    out = []
    for fam, n in spec:
        out.extend({"family": fam, "i": i} for i in range(n))
    return out


def _state(mined, judged, never_fires=None):
    return jsf.source_state(mined, judged, never_fires=never_fires or {}, table=TABLE)


def test_activates_below_the_desk_ratio_and_deactivates_at_parity():
    mined = {"carry": 1000, "cot_a": 100, "cot_b": 100, "tape_a": 100}
    st = _state(mined, {"carry": 500, "cot_a": 5, "cot_b": 5, "tape_a": 50})
    desk = st["desk_judged_mined_ratio"]
    assert st["groups"]["cot"]["active"] is True          # 0.05 < desk
    assert st["groups"]["cot"]["judged_mined_ratio"] < desk
    # tape: 50/100 = 0.5 >= desk ratio (565/1300 = 0.43) -> parity reached, inactive
    assert st["groups"]["tape"]["active"] is False
    # cot brought to parity: inactive
    st2 = _state(mined, {"carry": 500, "cot_a": 100, "cot_b": 100, "tape_a": 50})
    assert st2["groups"]["cot"]["active"] is False


def test_every_prefix_holds_the_floor_share_while_rows_last():
    rows = _rows([("carry", 900), ("cot_a", 30), ("cot_b", 30)])
    st = _state({"carry": 1000, "cot_a": 100, "cot_b": 100}, {"carry": 900})
    out, census = jsf.floor_interleave(rows, st)
    n_src = 0
    for n, r in enumerate(out, start=1):
        n_src += r["family"].startswith("cot")
        if n_src < 60:                                    # source still has rows
            assert n_src >= math.floor(0.10 * n), n
    assert census["cot"]["rows"] == 60


def test_unused_slots_are_given_back_and_total_unchanged():
    rows = _rows([("carry", 200), ("cot_a", 3)])
    st = _state({"carry": 1000, "cot_a": 100}, {"carry": 900})
    out, _ = jsf.floor_interleave(rows, st)
    assert len(out) == len(rows)
    assert sorted(map(id, out)) == sorted(map(id, rows))  # a permutation: nothing added/removed
    # cot ran out after 3 rows; everything after the first 30 is carry, in carry's own order
    carry = [r["i"] for r in out if r["family"] == "carry"]
    assert carry == list(range(200))
    assert sum(r["family"] == "cot_a" for r in out[:30]) == 3


def test_others_lose_at_most_the_floor_slots_and_keep_their_order():
    rows = _rows([("carry", 500), ("trend", 500), ("cot_a", 500)])
    st = _state({"carry": 1000, "trend": 1000, "cot_a": 1000}, {"carry": 900, "trend": 900})
    out, _ = jsf.floor_interleave(rows, st)
    rest_before = [r for r in rows if r["family"] != "cot_a"]
    rest_after = [r for r in out if r["family"] != "cot_a"]
    assert rest_after == rest_before
    head = out[:100]
    assert sum(r["family"] == "cot_a" for r in head) == 10   # exactly the floor, no more


def test_inactive_or_absent_sources_change_nothing():
    rows = _rows([("carry", 50), ("cot_a", 50)])
    st = _state({"carry": 100, "cot_a": 100}, {"carry": 10, "cot_a": 90})
    out, _ = jsf.floor_interleave(rows, st)
    assert out == rows


def test_blocked_member_gets_no_floor_slots():
    rows = _rows([("carry", 100), ("tape_a", 50)])
    st = _state({"carry": 1000, "tape_a": 1000}, {"carry": 900},
                never_fires={"tape_a": 400})
    g = st["groups"]["tape"]
    assert g["active"] is True and g["eligible_members"] == []
    assert "never_fires" in g["blocked_members"]["tape_a"]
    out, _ = jsf.floor_interleave(rows, st)
    assert out == rows
    pub = jsf.publish(st, slots_per_pass=250.0)
    assert pub["groups"]["tape"]["slots_granted"] == 0
    # one ruled verdict re-admits it
    st2 = _state({"carry": 1000, "tape_a": 1000}, {"carry": 900, "tape_a": 1},
                 never_fires={"tape_a": 400})
    assert st2["groups"]["tape"]["eligible_members"] == ["tape_a"]


def test_deterministic_and_published(tmp_path):
    rows = _rows([("carry", 300), ("cot_b", 40), ("cot_a", 40), ("tape_a", 40)])
    st = _state({"carry": 1000, "cot_a": 100, "cot_b": 100, "tape_a": 100}, {"carry": 900})
    a, _ = jsf.floor_interleave([dict(r) for r in rows], st)
    b, _ = jsf.floor_interleave([dict(r) for r in rows], st)
    assert a == b
    pub = jsf.publish(st, slots_per_pass=250.0)
    for src in ("cot", "tape"):
        g = pub["groups"][src]
        assert g["floor_share"] == 0.10 and g["active"] is True
        assert g["slots_granted"] == 25
        assert "judged_mined_ratio" in g
    assert pub["enforced"] is False and "SEAL" in pub["enforcement_status"]
    rep = tmp_path / "JUDGE_COVERAGE.json"
    rep.write_text(json.dumps({"source_floor": pub}), "utf-8")
    assert jsf.floor_from_report([dict(r) for r in rows], rep) == a
    # an unreadable decision never reorders
    bad = tmp_path / "missing.json"
    assert jsf.floor_from_report(rows, bad) is rows


def test_default_table_names_the_three_alt_sources():
    t = jsf.SOURCE_FAMILY_FLOOR
    assert set(t) == {"cot", "tick_tape", "event_analyst"}
    assert "orderflow_imbalance" in t["tick_tape"]["members"]
    assert "cot_net_fade" in t["cot"]["members"]
    assert "event_reaction" in t["event_analyst"]["members"]


def test_member_without_backlog_is_not_granted_slots():
    st = jsf.source_state({"carry": 1000, "tape_a": 100}, {"carry": 900, "tape_a": 3},
                          backlog={"carry": 50, "tape_a": 0}, table=TABLE)
    g = st["groups"]["tape"]
    assert g["active"] is True and g["eligible_members"] == []
    assert g["no_backlog_members"] == ["tape_a"]
    assert jsf.publish(st, slots_per_pass=250.0)["groups"]["tape"]["slots_granted"] == 0


def test_floor_survives_the_h2_reorder_when_applied_last():
    """Audit (2026-11-25, seal r1 HOLD): `reorder_keep` restores every kept cell's pre-allocation
    position, so a floor applied INSIDE the trim is erased. Applied LAST, after the reorder, every
    prefix holds each active source's share and the result is still a permutation of keep."""
    from research.judge_efficiency import reorder_keep

    before = _rows([("carry", 60), ("cot_a", 6), ("momo", 60), ("tape_a", 6), ("cot_b", 6)])
    keep = [r for r in before if r["family"] != "momo" or r["i"] < 40]   # a family trim
    block = {"source_floor": {"groups": {"cot": {"active": True, "min_share": 0.10,
                                "eligible_members": ["cot_a", "cot_b"]}}}}
    # Floor inside the trim, then the H2 reorder: the floor's permutation is gone.
    erased = reorder_keep(before, jsf.floor_from_report(list(keep), block))
    assert [id(r) for r in erased] == [id(r) for r in reorder_keep(before, keep)]
    assert jsf.floor_from_report(list(keep), block) != keep          # the floor did reorder
    # Floor last: every prefix holds its share while the source has rows left.
    out = jsf.floor_from_report(reorder_keep(before, keep), block)
    assert sorted(map(id, out)) == sorted(map(id, keep)) and len(out) == len(keep)
    members = {"cot": {"cot_a", "cot_b"}}
    total = {src: sum(1 for r in keep if r["family"] in fams) for src, fams in members.items()}
    for n in range(1, len(out) + 1):
        for src, fams in members.items():
            got = sum(1 for r in out[:n] if r["family"] in fams)
            assert got >= min(total[src], math.ceil(0.10 * n - 1e-12)), (src, n, got)


def test_sealed_sources_apply_the_floor_after_the_reorder():
    """Once the sealed judge and its warmer restatement call the floor, they call it AFTER
    `reorder_keep` (and, in the judge, after the re-mint front), never inside the trim."""
    gauntlet = ROOT / "desks" / "mt5" / "scripts" / "external_gauntlet.py"
    docket = DESK / "research" / "judge_docket_order.py"
    cases = ((gauntlet, "def main(", ("reorder_keep(_pre_alloc", "_remint_front +")),
             (docket, "def sealed_keep(", ("reorder_keep(ordered",)))
    for path, fn, anchors in cases:
        src = path.read_text("utf-8")
        if "floor_from_report" not in src:
            continue                      # seal not landed yet: nothing to order
        assert "floor_from_report" not in src[src.index("def allocate"):src.index(fn)], path
        body = src[src.index(fn):]
        call = body.index("floor_from_report(")
        for a in anchors:
            assert body.index(a) < call, (path, a)
