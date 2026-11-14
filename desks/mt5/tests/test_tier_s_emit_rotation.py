"""Tier S emission rotation: each hour's donation is NEW cells, not last hour's prefix again.

The emitters used to cap a deterministic list (`_emit_orthogonal` stopped building at 150;
qd_niches took two families by three symbols; theory compositions four symbols), so the same
(family, symbol) cells were re-sent every hour and the compiler, which already held them, minted
nothing -- the reason tier_s showed 0 cells. Now every emitter hands `_emit` its full grid, and
`rotate` puts never-donated cells first, withholds cells donated in the last REEMIT_AFTER_DAYS,
and re-sends older cells (oldest first) only when the fresh ones do not fill the cap.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(ROOT), str(DESK / "research"), str(DESK)):
    if p not in sys.path:
        sys.path.insert(0, p)

import tier_s as ts  # noqa: E402

NOW = datetime(2026, 11, 14, 1, 0, tzinfo=UTC)


def _rows(n: int, fam: str = "trend_ma_cross") -> list[dict]:
    return [{"kind": "hypothesis", "family": fam, "symbols": [f"SYM{i:04d}"],
             "text": f"probe {i}"} for i in range(n)]


def test_cell_key_is_identity_not_prose():
    a = {"family": "f", "symbols": ["EURUSD"], "params": {"session": "asia"}, "text": "x",
         "steering": {"mechanism": 0.3}}
    b = {**a, "text": "different words", "steering": {"mechanism": 0.9}}
    c = {**a, "params": {"session": "london"}}
    assert ts.cell_key(a) == ts.cell_key(b) != ts.cell_key(c)


def test_rotate_fresh_first_recent_withheld_stale_fills_oldest_first():
    rows = _rows(6)
    keys = [ts.cell_key(r) for r in rows]
    seen = {keys[0]: (NOW - timedelta(days=1)).isoformat(),          # recent: withheld
            keys[1]: (NOW - timedelta(days=40)).isoformat(),         # stale, oldest
            keys[2]: (NOW - timedelta(days=20)).isoformat()}         # stale
    got, c = ts.rotate("k", [dict(r) for r in rows], seen, now=NOW, cap=5)
    order = [r["symbols"][0] for r in got]
    assert order == ["SYM0003", "SYM0004", "SYM0005", "SYM0001", "SYM0002"]
    assert c == {"candidates": 6, "fresh_available": 3, "fresh_emitted": 3, "reemitted": 2,
                 "withheld_recent": 1, "stale_available": 2}
    # the rank orders fresh cells; the emitter's own order breaks ties
    got, _ = ts.rotate("k", [dict(r) for r in rows], {}, now=NOW, cap=3,
                       rank=lambda r: -int(r["symbols"][0][3:]))
    assert [r["symbols"][0] for r in got] == ["SYM0005", "SYM0004", "SYM0003"]


def test_interleave_spans_every_group():
    out = ts._interleave([[1, 2, 3], [10], [20, 21]])
    assert out == [1, 10, 20, 2, 21, 3]


def test_successive_hours_donate_new_cells_until_the_grid_is_spent(tmp_path, monkeypatch):
    monkeypatch.setattr(ts, "STATE", tmp_path / "state")
    monkeypatch.setattr(ts, "INTEL", tmp_path / "intel")
    monkeypatch.setattr(ts, "_explored", lambda r: 0)
    grid = _rows(400)
    donated: list[set[str]] = []
    for h in range(4):
        monkeypatch.setattr(ts, "NOW", NOW + timedelta(hours=h))
        res = ts._emit("orthogonal", [dict(r) for r in grid])
        stamp = (NOW + timedelta(hours=h)).strftime("%Y%m%dT%H")
        f = tmp_path / "intel" / f"orthogonal_{stamp}.json"
        doc = json.loads(f.read_text()) if f.exists() else {"rows": []}
        donated.append({r["symbols"][0] for r in doc["rows"]})
        assert all("_cell" not in r for r in doc["rows"])
        if h < 2:
            assert res["emitted"] == 150 and res["rotation"]["fresh_emitted"] == 150
    assert not (donated[0] & donated[1])
    # hour 2 takes the last 100 fresh cells; nothing is re-sent inside the 14-day window
    assert len(donated[2]) == 100 and not (donated[2] & (donated[0] | donated[1]))
    assert donated[3] == set()
    mem = json.loads((tmp_path / "state" / "emitted_cells.json").read_text())
    assert len(mem["orthogonal"]) == 400
    # after the re-emit window the oldest donations come round again
    monkeypatch.setattr(ts, "NOW", NOW + timedelta(days=ts.REEMIT_AFTER_DAYS, hours=1))
    res = ts._emit("orthogonal", [dict(r) for r in grid])
    assert res["rotation"]["reemitted"] == 150 and res["rotation"]["fresh_emitted"] == 0


def test_emitters_hand_over_the_full_grid():
    src = (DESK / "research" / "tier_s.py").read_text("utf-8")
    body = src.split("def _emit_orthogonal", 1)[1].split("\ndef ", 1)[0]
    assert "len(rows) >= MAX_EMIT_PER_KIND" not in body
    assert "fams[:2]" not in src and "pool[:3]" not in src
    assert ".most_common(4)" not in src.split("theory_compositions", 1)[0][-6000:]


def test_orthogonal_grid_widens_past_family_x_symbol(tmp_path, monkeypatch):
    """Base cells first, then session variants, then registered param_grid variants, then
    session x param -- so a spent family x symbol base never leaves the emitter silent."""
    monkeypatch.setattr(ts, "STATE", tmp_path / "state")
    monkeypatch.setattr(ts, "INTEL", tmp_path / "intel")
    monkeypatch.setattr(ts, "_explored", lambda r: 0)
    monkeypatch.setattr(ts, "_family_vocab", lambda: ["fam_a", "fam_b"])
    monkeypatch.setattr(ts, "_param_variants",
                        lambda f: [{"k": 1}, {"k": 3}] if f == "fam_a" else [])
    uni = tmp_path / "uni"
    uni.mkdir()
    for s in ("EURUSD", "GBPUSD"):
        (uni / f"{s}_H1.parquet").write_text("x")
    monkeypatch.setattr(ts, "UNIVERSE", uni)
    monkeypatch.setattr(ts, "_may_hypothesise", lambda s: True)
    monkeypatch.setattr(ts, "MAX_EMIT_PER_KIND", 4)
    seen_params: list[list] = []
    cells: list[str] = []
    for h in range(12):
        monkeypatch.setattr(ts, "NOW", NOW + timedelta(hours=h))
        res = ts._emit_orthogonal({}, [])
        stamp = (NOW + timedelta(hours=h)).strftime("%Y%m%dT%H")
        f = tmp_path / "intel" / f"orthogonal_{stamp}.json"
        rows = json.loads(f.read_text())["rows"] if f.exists() else []
        seen_params.append([r.get("params") for r in rows])
        cells.extend(ts.cell_key(r) for r in rows)
        if h == 0:
            # 4 base + 12 session + 4 param + 12 session x param
            assert res["rotation"]["candidates"] == 32
    assert all(p is None for p in seen_params[0])                    # base first
    assert all(p and set(p) == {"session"} for p in seen_params[1])  # then sessions
    flat = [p for hour in seen_params for p in hour]
    # 3 sessions + 2 knob values + 6 session x knob = 11 distinct parameterisations, each on
    # both symbols (28 widened cells) -- and no cell is donated twice
    assert len(flat) == 32 and len({json.dumps(p, sort_keys=True) for p in flat if p}) == 11
    assert len(cells) == len(set(cells)) == 32
    assert seen_params[8] == []                                       # all 32 donated, 4/hour


def test_param_variants_are_one_knob_off_the_defaults(monkeypatch):
    from mt5desk import families
    monkeypatch.setitem(families.FAMILY_REGISTRY, "toy_fam",
                        {"defaults": {"a": 1, "b": 2}, "param_grid": {"a": [1, 5], "b": [2, 7]}})
    assert ts._param_variants("toy_fam") == [{"a": 5, "b": 2}, {"a": 1, "b": 7}]
    assert ts._param_variants("not_registered") == []
