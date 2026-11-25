"""FUNNEL.json `labs`: the five research labs, each with breadth / depth / conversion, floors that
only rise, the newest output time and a status that reads STALE after two hours of silence."""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import funnel as fn  # noqa: E402
from research import funnel_labs as fl  # noqa: E402

LAB_KEYS = {"mathlab", "physics_lab", "expression_factory", "world_lab", "coevolution"}
STATUSES = {"OK", "BELOW_FLOOR", "STALE", "UNMEASURED"}
FORMULA = {"expr": ["zscore", ["delta", "close", 5], 24], "norm": 240, "entry_z": 1.5,
           "side_mode": "follow", "hold_bars": 8, "atr_n": 20, "stop_atr": 2.0, "rr": 1.5}


def _w(p: Path, doc: Any, age_s: float = 0.0) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc), "utf-8")
    if age_s:
        t = time.time() - age_s
        os.utime(p, (t, t))


def _donation(tmp: Path, seat: str, rows: list[dict[str, Any]], age_s: float = 0.0) -> None:
    _w(tmp / "data" / "intelligence" / seat / "discoveries_20261125_1200.json",
       {"discoveries": rows}, age_s)


def _row(tradition: str, family: str = "formula", params: dict | None = None) -> dict[str, Any]:
    return {"source": "mathlab", "symbol": "EURUSD", "family": family,
            "params": FORMULA if params is None else params,
            "evidence": {"tradition": tradition}}


def _build(tmp: Path) -> dict[str, Any]:
    return fn.build(fn.Paths.at(tmp), now=datetime.now(UTC), budget_s=60,
                    is_exotic=lambda s: False, trades_of=lambda n: [])


def _check_shape(labs: dict[str, Any]) -> None:
    assert set(labs) == LAB_KEYS
    for row in labs.values():
        for m in ("breadth", "depth", "conversion"):
            for k in (m, f"{m}_floor"):
                v = row[k]
                assert v == fn.UNMEASURED or (isinstance(v, int | float)
                                              and not isinstance(v, bool)), (k, v)
        assert row["status"] in STATUSES
        assert "last_output_utc" in row


def test_the_block_has_exactly_the_five_labs_and_reads_unmeasured_on_an_empty_desk(
        tmp_path: Path) -> None:
    labs = _build(tmp_path)["labs"]
    _check_shape(labs)
    assert all(r["status"] == fn.UNMEASURED and r["last_output_utc"] is None
               for r in labs.values())


def test_a_fresh_lab_measures_breadth_depth_conversion_and_names_its_refusals(
        tmp_path: Path) -> None:
    _w(tmp_path / "reports" / "MATH_LAB.json", {"at": "now"})
    _donation(tmp_path, "mathlab", [_row("spectral"), _row("spectral"), _row("topology"),
                                    _row("wavelets", family="no_such_family")])
    labs = _build(tmp_path)["labs"]
    _check_shape(labs)
    m = labs["mathlab"]
    assert m["donated"] == 4 and m["depth"] == 3 and m["breadth"] == 2
    assert m["conversion"] == 0.75
    assert sum(m["refused"].values()) == 1                 # a named refusal, never a drop
    assert m["status"] == "OK"
    assert labs["physics_lab"]["status"] == fn.UNMEASURED


def test_a_silent_lab_reads_stale_after_two_hours(tmp_path: Path) -> None:
    _w(tmp_path / "reports" / "MATH_LAB.json", {"at": "then"}, age_s=3 * 3600)
    _donation(tmp_path, "mathlab", [_row("spectral")], age_s=3 * 3600)
    m = _build(tmp_path)["labs"]["mathlab"]
    assert m["status"] == "STALE"
    then = datetime.fromisoformat(m["last_output_utc"])
    assert datetime.now(UTC) - then > timedelta(hours=2)


def test_lab_floors_ratchet_up_only_and_a_shortfall_reads_below_floor(tmp_path: Path) -> None:
    p = fn.Paths.at(tmp_path)
    _w(tmp_path / "reports" / "MATH_LAB.json", {"at": "now"})
    _donation(tmp_path, "mathlab", [_row(t) for t in ("a", "b", "c", "d")])
    fn.write(_build(tmp_path), p)
    floors = json.loads(p.floors.read_text("utf-8"))["labs"]["mathlab"]
    assert floors["depth_floor"] == 3 and floors["breadth_floor"] == 3   # 0.9 x 4, floored
    assert floors["conversion_floor"] == 0.9
    # a thinner pass: the floor stands, the lab reads BELOW_FLOOR
    _donation(tmp_path, "mathlab", [_row("a"), _row("a", family="no_such_family")])
    doc = _build(tmp_path)
    m = doc["labs"]["mathlab"]
    assert m["status"] == "BELOW_FLOOR" and m["depth_status"] == "VIOLATED"
    fn.write(doc, p)
    again = json.loads(p.floors.read_text("utf-8"))["labs"]["mathlab"]
    assert again["depth_floor"] == 3 and again["conversion_floor"] == 0.9   # never lowered
    assert fl.merge_up({"mathlab": {"depth_floor": 9}},
                       {"mathlab": {"depth_floor": 1}})["mathlab"]["depth_floor"] == 9


def test_coevolution_counts_its_enqueued_survivors_and_names_why_they_are_not_cells(
        tmp_path: Path) -> None:
    _w(tmp_path / "reports" / "COEVOLUTION.json", {
        "survivors": [{"symbol": "EURUSD", "island": "i1", "model": "logit",
                       "features": ["ret"]}],
        "registry": [{"symbol": "EURUSD", "island": "i1", "enqueued": True}]})
    c = _build(tmp_path)["labs"]["coevolution"]
    assert c["donated"] == 1
    assert c["depth"] + sum(c["refused"].values()) == 1
