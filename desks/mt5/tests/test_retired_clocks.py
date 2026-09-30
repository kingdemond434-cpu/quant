"""RETIRED CLOCKS LEAVE THE LIVE STORE, and a banned family never gets one.

The two defects these pin were measured together on the trading box vmi3571445 on 2026-09-23,
when `reports/CERTIFICATE_TRUTH.json` carried 42 divergences of which 35 were fatal:

  * 23 BANNED_CLOCK + 12 UNBACKED_CLOCK, every one a `shadow_state.json` row whose own status said
    `RETIRED_NO_CERTIFICATE` -- a word `certificate_truth.TERMINAL` did not hold, so rows the desk
    had ALREADY retired were re-judged as running clocks, for ever, by an exact-match set;
  * the same 23 were `discovered`-family clocks, of a family the principal banned permanently,
    which no door had ever refused to CREATE.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK / "research"), str(_DESK), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import certificate_truth as CT  # noqa: E402
import family_policy as fp  # noqa: E402
import retired_clocks as RC  # noqa: E402
import sleeve_registry as SR  # noqa: E402
from gate_policy import ATTESTATION, GATES  # noqa: E402


def _w(p: Path, doc: object) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=1), encoding="utf-8")


def _clock(status: str, **extra: object) -> dict:
    row = {"n": 4, "cum_r": -2.21, "max_dd_r": -2.11, "days_active": 3, "status": status,
           "first_entry": "2026-09-18 03:00:00+00:00", "last_entry": "2026-09-18 15:00:00+00:00",
           "forward_start": "2026-09-17T22:55:29+00:00", "sleeve_id": "ff2eae3d7198"}
    row.update(extra)
    return row


# --------------------------------------------------------------- 1. the one retirement word
def test_a_retirement_is_recognised_by_its_prefix_and_never_by_an_exact_spelling():
    """THE DEFECT ITSELF. `clock_certificate.retire_unbacked` writes `RETIRED_NO_CERTIFICATE`;
    `certificate_truth.TERMINAL` was an exact-match set that did not hold it. Every organ that
    invents a retirement word must be understood by every reader on the day it ships."""
    for status in ("RETIRED", "RETIRED_NO_CERTIFICATE", "RETIRED_ORPHAN", "RETIRED_GATE_FAIL",
                   "RETIRED_UNRECONSTRUCTIBLE", "retired_something_invented_tomorrow", "VOID",
                   "VOIDED_BY_ACCOUNT"):
        assert RC.is_retired(status), status
        assert RC.is_terminal(status), status
        assert CT._terminal(status), status
    # Terminal but NOT a retirement: these are standing states their writer still reads, so the
    # row stays exactly where it is.
    for status in ("REFUSED_BY_UNIVERSE_POLICY", "QUARANTINED_FORWARD_CLOCK_BREACH", "PROMOTED"):
        assert RC.is_terminal(status) and not RC.is_retired(status), status
        assert CT._terminal(status), status
    # A live clock is neither, and an absent status is UNMEASURED -- never a retirement.
    for status in ("ACTIVE", "BLOCKED_NO_BARS", "", None):
        assert not RC.is_retired(status) and not RC.is_terminal(status), status


# --------------------------------------------------------------- 2. the evacuation
def test_a_retired_clock_leaves_the_live_store_for_an_append_only_ledger(tmp_path: Path):
    base = tmp_path / "desk"
    _w(base / "reports" / "shadow" / "shadow_state.json", {
        "updated_at": "2026-09-23T19:00:00+00:00",
        "GBPJPY.engulfing_reversal.continuous@H4#session=asia": _clock(
            "RETIRED_NO_CERTIFICATE", status_why="no canonical certificate backs this clock",
            status_at="2026-09-23T19:50:00+00:00", retired_by="research/clock_certificate.py"),
        "AUDCAD.discovered.asia#band=x": _clock("RETIRED_ORPHAN", retire_reason="banned family"),
        "CADJPY.asia": _clock("ACTIVE"),
        "AFG.london_am": _clock("REFUSED_BY_UNIVERSE_POLICY"),
    })
    _w(base / "reports" / "shadow" / "scalp_shadow_state.json",
       {"sleeves": {"xau_m5_anti_breakout_overlap": _clock("RETIRED"),
                    "xau_m15_anti_momentum": _clock("ACTIVE")}})

    acts = RC.evacuate(base, now="2026-09-23T20:30:00+00:00")
    assert acts["moved"] == 3
    assert acts["by_store"] == {"shadow_state": 2, "scalp_shadow_state": 1}

    live = json.loads((base / "reports" / "shadow" / "shadow_state.json").read_text("utf-8"))
    assert set(live) >= {"CADJPY.asia", "AFG.london_am"}
    assert "GBPJPY.engulfing_reversal.continuous@H4#session=asia" not in live
    assert "AUDCAD.discovered.asia#band=x" not in live
    scalp = json.loads((base / "reports" / "shadow" / "scalp_shadow_state.json").read_text("utf-8"))
    assert set(scalp["sleeves"]) == {"xau_m15_anti_momentum"}

    # THE TOMBSTONE: a key that was retired is not the same answer as one that never existed.
    stone = live[RC.TOMBSTONE]["GBPJPY.engulfing_reversal.continuous@H4#session=asia"]
    assert stone["status"] == "RETIRED_NO_CERTIFICATE" and stone["accrued_days"] == 3

    # THE HISTORY: whole rows, the identity, the reason, and the evidence the retirement lost.
    rows = [json.loads(x) for x in
            (base / RC.LEDGER).read_text("utf-8").splitlines()]
    assert len(rows) == 3
    by_key = {r["key"]: r for r in rows}
    gbp = by_key["GBPJPY.engulfing_reversal.continuous@H4#session=asia"]
    assert gbp["symbol"] == "GBPJPY" and gbp["family"] == "engulfing_reversal"
    assert gbp["selector"] == "continuous"
    assert gbp["reason"] == "no canonical certificate backs this clock"
    assert gbp["retired_at"] == "2026-09-23T19:50:00+00:00"
    assert gbp["retired_by"] == "research/clock_certificate.py"
    assert gbp["accrued_days"] == 3 and gbp["accrued_trades"] == 4
    assert gbp["accrued"]["cum_r"] == -2.21           # the cost is recorded, not merely stated
    assert gbp["row"]["status"] == "RETIRED_NO_CERTIFICATE"   # nothing is destroyed


def test_the_evacuation_is_idempotent_and_never_touches_the_canonical_registry(tmp_path: Path):
    base = tmp_path / "desk"
    _w(base / "reports" / "shadow" / "shadow_state.json", {"A.carry.asia": _clock("RETIRED")})
    reg = {"sleeves": {"A.carry.asia": {"status": "RETIRED", "identity": {"family": "carry"},
                                        "forward_start": "2026-09-01T00:00:00+00:00"}}}
    _w(base / "data" / "sleeve_registry.json", reg)

    assert RC.evacuate(base)["moved"] == 1
    second = RC.evacuate(base)
    assert second["moved"] == 0 and second["by_store"] == {}
    assert len((base / RC.LEDGER).read_text("utf-8").splitlines()) == 1

    # THE REGISTRY KEEPS ITS RETIRED ROWS. `freeze()` is idempotent by the row's PRESENCE, so
    # deleting one re-mints it LIVE with a new forward_start -- the silent clock re-base that
    # destroyed the whole forward book three times in 32 hours on 2026-08-27.
    assert json.loads((base / "data" / "sleeve_registry.json").read_text("utf-8")) == reg


def test_an_unreadable_clock_store_is_unmeasured_and_never_an_empty_evacuation(tmp_path: Path):
    base = tmp_path / "desk"
    p = base / "reports" / "shadow" / "shadow_state.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{not json", encoding="utf-8")
    acts = RC.evacuate(base)
    assert acts["moved"] == 0 and acts["unreadable"] == ["reports/shadow/shadow_state.json"]
    assert not (base / RC.LEDGER).exists()


def test_the_history_is_queryable_by_key_symbol_family_and_store(tmp_path: Path):
    base = tmp_path / "desk"
    _w(base / "reports" / "shadow" / "shadow_state.json",
       {"GBPJPY.engulfing_reversal.continuous": _clock("RETIRED_NO_CERTIFICATE"),
        "XTIUSD.trend_ma_cross.continuous": _clock("RETIRED_ORPHAN")})
    RC.evacuate(base)
    assert {r["key"] for r in RC.query(base)} == {"GBPJPY.engulfing_reversal.continuous",
                                                  "XTIUSD.trend_ma_cross.continuous"}
    assert [r["symbol"] for r in RC.query(base, "gbpjpy")] == ["GBPJPY"]
    assert [r["symbol"] for r in RC.query(base, family="trend_ma_cross")] == ["XTIUSD"]
    assert RC.query(base, store="scalp_shadow_state") == []
    assert RC.query(base, "no-such-thing") == []
    assert RC.main(["--query", "gbpjpy", "--base", str(base)]) == 0


# -------------------------------------------- 3. the audit stops re-judging a closed decision
def test_a_clock_the_desk_already_retired_is_no_longer_a_divergence(tmp_path: Path):
    """THE 35 FATAL ROWS. Same store, same rows, same evidence -- the only thing that decided
    whether the fence read 35 fatal or 0 was which hourly leg had last written a status string."""
    base = tmp_path / "desk"
    gates = {g: {"passed": True, "message": "t"} for g in GATES}
    _w(base / "reports" / "UNIVERSAL_SURVIVORS.json", {
        "n": 1, "gate_policy": dict(ATTESTATION), "survivors": {
            "external.CADJPY.session_range_breakout": {
                "hunt": "external", "sym": "CADJPY", "days": 500, "gates": gates,
                "shadow_spec": {"symbol": "CADJPY", "family": "session_range_breakout",
                                "selector": "asia"}}}})
    _w(base / "reports" / "shadow" / "shadow_state.json", {
        "GBPJPY.engulfing_reversal.continuous": _clock("RETIRED_NO_CERTIFICATE"),
        "AUDCAD.discovered.asia#band=x": _clock("RETIRED_NO_CERTIFICATE"),
        "EURUSD.carry.asia": _clock("ACTIVE"),
    })
    paths = CT.Paths.at(base)
    doc = CT.audit(paths)
    kinds = doc["by_kind"]
    # The retired rows make no live claim; the one genuinely running unbacked clock still does.
    assert kinds.get("UNBACKED_CLOCK") == 1
    assert kinds.get("BANNED_CLOCK") is None
    keys = {d["key"] for d in doc["divergences"]}
    assert keys == {"EURUSD.carry.asia"}
    assert doc["stores"]["shadow_state"]["live_rows"] == 1


def test_repair_evacuates_the_retired_rows_on_the_clock_without_any_apply_flag(tmp_path: Path):
    base = tmp_path / "desk"
    _w(base / "reports" / "shadow" / "shadow_state.json",
       {"GBPJPY.engulfing_reversal.continuous": _clock("RETIRED_NO_CERTIFICATE")})
    acts = CT.repair(CT.Paths.at(base))
    assert acts["retired_evacuation"]["moved"] == 1
    assert "GBPJPY.engulfing_reversal.continuous" not in json.loads(
        (base / "reports" / "shadow" / "shadow_state.json").read_text("utf-8"))
    assert (base / RC.LEDGER).exists()


# ------------------------------------------------------------------- 4. the banned write door
def test_a_banned_family_can_never_create_a_clock_row(tmp_path: Path, monkeypatch):
    """AT THE DOOR, NOT IN A SWEEP. Between two sweeps the row exists and every downstream organ
    reads it; at the door "never created" is a fact."""
    monkeypatch.setattr(SR, "REGISTRY", tmp_path / "sleeve_registry.json")
    ident = SR.identity(family="discovered", symbol="AUDCAD", selector="asia", behaviour="b")
    with pytest.raises(fp.BannedFamilyRefused) as exc:
        SR.freeze("AUDCAD.discovered.asia", ident)
    assert exc.value.what == "clock" and exc.value.family == "discovered"
    assert "permanently banned" in str(exc.value)
    assert not (tmp_path / "sleeve_registry.json").exists()     # no row, no file, no residue

    ok = SR.identity(family="session_range_breakout", symbol="CADJPY", selector="asia",
                     behaviour="b")
    SR.freeze("CADJPY.asia", ok)
    rows = json.loads((tmp_path / "sleeve_registry.json").read_text("utf-8"))["sleeves"]
    assert rows["CADJPY.asia"]["status"] == "LIVE"


def test_no_later_organ_can_re_admit_the_permanently_banned_family(tmp_path: Path, monkeypatch):
    """The ban is not data that a writer, a merge or a missing file can undo."""
    empty = tmp_path / "banned_families.json"
    empty.write_text(json.dumps({"banned": {}}), "utf-8")
    monkeypatch.setattr(fp, "BANNED_FAMILIES_FILE", empty)
    assert fp.family_banned("discovered")
    with pytest.raises(fp.BannedFamilyRefused):
        fp.refuse_if_banned("DISCOVERED", what="candidate", key="x")
    monkeypatch.setattr(fp, "BANNED_FAMILIES_FILE", tmp_path / "gone.json")
    assert fp.family_banned("discovered")
    # The three write doors name the three things a banned family may never own again.
    for what in ("clock", "certificate", "candidate"):
        with pytest.raises(fp.BannedFamilyRefused):
            fp.refuse_if_banned("discovered", what=what, key="k")
    # And it refuses nothing else: an unbanned family passes the door untouched.
    assert fp.refuse_if_banned("carry", what="clock", key="k") is None
    assert fp.refuse_if_banned("", what="clock", key="k") is None
    # The audit's own constant and the policy's permanent list are the same decision.
    assert CT.DISCOVERED in fp.PERMANENT


def test_the_shadow_enrolment_loop_refuses_to_create_a_banned_clock(monkeypatch):
    """`shadow_forward`'s state row is born at `state.get(key, {...})`; the door is before it."""
    import shadow_forward as SF
    src = Path(SF.__file__).read_text(encoding="utf-8")
    door = src.index("THE BANNED FAMILY DOOR")
    born = src.index('st = state.get(key, {"n": 0')
    assert door < born, "the ban must be refused BEFORE the state row is created"
    assert "REFUSED_BANNED_FAMILY" in src
