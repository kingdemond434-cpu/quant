"""A LIVE sleeve whose traded spec is not its certified spec is RETIRED by the Tier S live door.

Ships WITH patch `tier_s_promoter_live_door_retirement.patch` (promoter.py is sealed); skips until
the reader lands. The chain end to end: `research_live_identity.judge` names the MISMATCH,
`promotion_authority.review_live` lists it with the reason the door publishes to
`data/tier_s/live_door.json`, and `promoter.retire_tier_s_live` reads that file and retires the
row. Measured 2026-09-30: seven LIVE sleeves carried a code-hash MISMATCH, and before
IDENTITY_MISMATCH joined TIER_S_RETIRING_VERDICTS all seven were HELD, not retired.
"""
from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research"), str(DESK / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import promoter  # noqa: E402

from libs.tiers import promotion_authority as pa  # noqa: E402
from libs.tiers import research_live_identity as rli  # noqa: E402

CELL = "external.CHFNOK.carry.p=0123456789abcdef"
PARAMS = {"lookback": 20, "side": 1}


def _world() -> dict[str, Any]:
    survivors = {CELL: {"cell": "CHFNOK.carry.p=0123456789abcdef", "sym": "CHFNOK",
                        "shadow_spec": {"symbol": "CHFNOK", "selector": "asia",
                                        "family": "carry", "params": dict(PARAMS)}}}
    registry = {"CHFNOK.carry.asia#x": {"status": "LIVE", "identity": {
        "family": "carry", "symbol": "CHFNOK", "selector": "asia",
        "params": dict(PARAMS), "code_hash": "certified", "behaviour_hash": "beh-certified"}}}
    return {"survivors": survivors, "registry": registry,
            "docket_index": {"CHFNOK.carry.p=0123456789abcdef": dict(PARAMS)},
            "docket_by_sym_family": {},
            # THE CODE THE GATEWAY RUNS TODAY: both hashes moved since certification.
            "code_of": lambda fam: ("traded", "beh-traded")}


def _row(name: str) -> dict[str, Any]:
    return {"name": name, "symbol": "CHFNOK", "family": "carry", "selector": "asia",
            "status": "LIVE", "exec": "family_market", "risk_frac": 0.01,
            "certificate": {"source": "UNIVERSAL_SURVIVORS", "cell": CELL}}


@pytest.fixture()
def door(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
    if getattr(promoter, "retire_tier_s_live", None) is None:
        pytest.skip("promoter has no live_door reader yet (tier_s_promoter_live_door_retirement"
                    ".patch not applied; promoter.py is sealed)")
    monkeypatch.setattr(promoter, "SLEEVES_FILE", tmp_path / "sleeves.json")
    src, out = promoter.tier_s_live_door_paths()
    src.parent.mkdir(parents=True)
    queued: list[list[str]] = []
    monkeypatch.setattr(promoter, "_queue_close", lambda names: queued.append(list(names)))
    monkeypatch.setattr(promoter, "_record_tier_s_block", lambda *a, **k: None)
    monkeypatch.setattr(promoter, "plog", lambda msg: None)
    # The door's other six verdicts find nothing; only the identity join speaks.
    monkeypatch.setattr(pa, "IDENTITY", tmp_path / "RESEARCH_LIVE_IDENTITY.json")
    monkeypatch.setattr(pa, "ROOT", tmp_path)
    monkeypatch.setattr(pa, "block", lambda name: None)
    promoter._DOOR_EVENTS.clear()
    yield {"src": src, "out": out, "queued": queued, "tmp": tmp_path}
    promoter._DOOR_EVENTS.clear()


def test_identity_mismatch_is_a_retiring_verdict() -> None:
    if getattr(promoter, "TIER_S_RETIRING_VERDICTS", None) is None:
        pytest.skip("tier_s_promoter_live_door_retirement.patch not applied")
    assert "IDENTITY_MISMATCH" in promoter.TIER_S_RETIRING_VERDICTS


def test_a_code_hash_mismatch_published_by_the_door_retires_the_live_row(
        door: dict[str, Any]) -> None:
    rows = [_row("chfnok_carry_asia"), _row("cadchf_overnight_gap_decay_asia")]
    ident = rli.judge(rows, **_world())
    assert ident["mismatched"] == [r["name"] for r in rows]
    assert all("code" in d["fields"] for d in ident["defects"])
    (door["tmp"] / "RESEARCH_LIVE_IDENTITY.json").write_text(
        json.dumps({"generated_utc": datetime.now(UTC).isoformat(), **ident}), "utf-8")
    # What the `door` organ publishes: review_live over the live book, verbatim.
    live = pa.review_live([r["name"] for r in rows])
    assert set(live) == {r["name"] for r in rows}
    assert all(v.split(":", 1)[0] == "IDENTITY_MISMATCH" for v in live.values())
    door["src"].write_text(json.dumps({"generated_utc": datetime.now(UTC).isoformat(),
                                       "rows": live}), "utf-8")
    sleeves = [dict(r) for r in rows] + [{"name": "untouched", "status": "LIVE",
                                          "risk_frac": 0.02}]
    assert promoter.retire_tier_s_live(sleeves) is True
    by = {s["name"]: s for s in sleeves}
    for r in rows:
        assert by[r["name"]]["status"] == "RETIRED" and by[r["name"]]["risk_frac"] == 0.0
        assert "IDENTITY_MISMATCH" in by[r["name"]]["retire_reason"]
    assert by["untouched"]["status"] == "LIVE" and by["untouched"]["risk_frac"] == 0.02
    assert door["queued"] == [[r["name"] for r in rows]]
    out = json.loads(door["out"].read_text("utf-8"))
    assert out["status"] == "MEASURED" and out["n_retired"] == 2 and out["held"] == {}


def test_a_bare_identity_mismatch_reason_still_retires(door: dict[str, Any]) -> None:
    """`mismatch_reasons` falls back to the bare code when a row carries no `why`."""
    door["src"].write_text(json.dumps({"generated_utc": datetime.now(UTC).isoformat(),
                                       "rows": {"x": "IDENTITY_MISMATCH"}}), "utf-8")
    sleeves = [{"name": "x", "status": "LIVE", "risk_frac": 0.01}]
    assert promoter.retire_tier_s_live(sleeves) is True
    assert sleeves[0]["status"] == "RETIRED"
