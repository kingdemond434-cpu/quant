"""Every registered family reaches the docket (2026-10-29): the 15 never-mined families.

JUDGE_COVERAGE 2026-10-27 published fifteen live families with zero docket rows. Three causes,
each pinned here: the buildability table and the default sweep never read the hunt16 population
(`dav_*`); the learned families' self-loaded `peers` was filed as an unsupplied input; and
`mass_screen_lead` / the analyst families were reachable only through screens that never passed.
The fence (`scripts/check_judge_coverage.py`) fails on any live family that still holds none.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK), str(DESK / "research"), str(ROOT), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import breadth_sweep as bs  # noqa: E402
from research import gauntlet_buildability as gb  # noqa: E402

LEARNED = ("gnn_propagation", "attention_ts", "rocket_ts", "ae_latent", "sig_path")


def test_buildability_resolves_every_live_family_the_gauntlet_resolves() -> None:
    from mt5desk import families
    for fam in families.live_family_names():
        if getattr(families, f"family_{fam}", None) is None:
            from mt5desk import families_orthogonal as fo
            if fam not in fo.ORTHOGONAL_FAMILIES:
                continue
        verdict, why = gb.family_verdict(fam)
        assert verdict != gb.NO_IMPLEMENTATION, (fam, why)


def test_hunt16_families_are_buildable_and_swept_at_defaults() -> None:
    from mt5desk.executables import hunt16_families
    ok, _blocked = bs.default_families()
    for fam in hunt16_families():
        assert gb.family_verdict(fam)[0] == gb.BUILDABLE, fam
        assert fam in ok, fam


def test_learned_families_need_a_named_panel_not_an_unsupplied_input() -> None:
    for fam in LEARNED:
        assert gb.family_verdict(fam)[0] == gb.BUILDABLE, fam
        assert gb.cell_verdict(fam, {})[0] == gb.MISSING_PARAMS, fam
        verdict, _ = gb.cell_verdict(fam, {"symbol": "EURUSD", "peer_symbols": ["GBPUSD"]})
        assert verdict == gb.BUILDABLE, fam


def test_learned_targets_name_the_panel_and_the_first_declared_configuration() -> None:
    from research import learned_miners as LM
    panel = list(LM.PANEL)
    for fam in LEARNED:
        rows = bs._targets(fam, bs.READY[fam], panel)
        assert rows, fam
        spec = next(m for m in LM.MINERS.values() if m["family"] == fam)
        for sym, p in rows:
            assert p["symbol"] == sym and sym not in p["peer_symbols"]
            assert set(p["peer_symbols"]) | {sym} <= set(panel)
            for k, v in spec["grid"][0].items():
                assert p[k] == v
    # A panel below the model's minimum names nothing rather than a degenerate panel.
    assert bs._targets("gnn_propagation", bs.READY["gnn_propagation"],
                       panel[: LM.MIN_PANEL - 1]) == []


def test_lead_targets_cover_the_core_against_every_leader_both_ways() -> None:
    from research.mass_screen import LEADERS
    rows = bs._targets("mass_screen_lead", bs.READY["mass_screen_lead"], list(bs.CORE))
    assert rows
    for sym, p in rows:
        assert sym in bs.CORE and p["leader"] in LEADERS and p["leader"] != sym
        assert gb.cell_verdict("mass_screen_lead", p)[0] == gb.BUILDABLE
    dirs = {(p["op"], p["direction"]) for _s, p in rows}
    assert dirs == {("gt", 1), ("gt", -1), ("lt", 1), ("lt", -1)}


def test_analyst_targets_come_only_from_the_store(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("QUANT_ALPHA_CAPTURE_STORE", str(tmp_path / "absent.jsonl"))
    for fam in ("analyst_revision_drift", "analyst_cross_market_lead"):
        assert bs._targets(fam, bs.READY[fam], list(bs.CORE)) == []


def test_unmined_families_go_first_under_the_cap(tmp_path, monkeypatch) -> None:
    docket = tmp_path / "external_survivors.json"
    docket.write_text(json.dumps([{"symbol": "EURUSD", "family": "held", "params": {"a": 0}}]))
    monkeypatch.setattr(bs, "DOCKET", docket)
    import research.merge_hypotheses as mh
    monkeypatch.setattr(mh, "_write_docket_atomically",
                        lambda path, rows: Path(path).write_text(json.dumps(rows)))
    import libs.data.pit as pit
    monkeypatch.setattr(pit, "stamp_or_refuse", lambda rows, _src: (rows, []))
    new = ([{"symbol": "EURUSD", "family": "held", "params": {"a": i}} for i in range(1, 5)]
           + [{"symbol": "EURUSD", "family": "fresh", "params": {"b": 1}}])
    added, _total = bs._apply_locked(new, max_new=2)
    rows = json.loads(docket.read_text())
    assert added == 2
    assert [r["family"] for r in rows[1:]] == ["fresh", "held"]


def _report(path: Path, unmined: list[str]) -> Path:
    path.write_text(json.dumps({
        "at": "2026-10-29T12:00:00+00:00",
        "families": {"carry": {"mined": 5, "queued": 1, "unjudged": 1, "judged_window": 1}},
        "totals": {"families_unmined": len(unmined)},
        "unmined_live_families": unmined}))
    return path


def test_the_fence_fails_on_any_unmined_live_family(tmp_path, monkeypatch) -> None:
    import check_judge_coverage as cjc
    monkeypatch.delenv(cjc.SOURCE_VIEW_ENV, raising=False)
    from datetime import UTC, datetime
    now = datetime(2026, 10, 29, 12, 30, tzinfo=UTC)
    doc = cjc.judge(_report(tmp_path / "r.json", ["dav_t3_trend", "sig_path"]), now=now,
                    liveness=False)
    row = next(c for c in doc["checks"] if c["metric"] == "families_unmined")
    assert doc["verdict"] == "FAIL" and row["state"] == "FAIL"
    assert "dav_t3_trend" in row["why"] and "sig_path" in row["why"]
    ok = cjc.judge(_report(tmp_path / "g.json", []), now=now, liveness=False)
    assert next(c for c in ok["checks"] if c["metric"] == "families_unmined")["state"] == "OK"
