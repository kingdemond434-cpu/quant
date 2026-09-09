"""Every sleeve row names its certificate and registry identity; every door leaves a ledger row.

AUDIT E9/E1 (2026-09-08): promoter.py wrote `{name, symbol, lot, risk_frac, ..., certificate_drift}`
and NO certificate id, so the hop from a funded sleeve to the certificate that justified it was a
name-shaped inference. AUDIT P10/A15: data/alpha_state_ledger.jsonl held two rows nine
milliseconds apart for one alpha -- the state machine had never been driven by the organ that
actually opens and closes doors.

What is pinned here, and each is a way the fix could have quietly become a regression:

  * the row carries `certificate` (the clock key, the convention forward_reconcile.py:308 already
    reads) and `sleeve_id` from data/sleeve_registry.json -- None, never "", when absent;
  * every door (PROMOTED, RESTORED, DEMOTED, RETIRED) appends a timestamped OBSERVATION row; the
    ledger takes only legal rung steps and is NEVER forced: a promotion to LIVE is refused by the
    machine, quoted verbatim, and the ledger file stays loadable;
  * RETIRED is the one door the ledger always takes, with the promoter's own reason on it;
  * the ledger paths follow SLEEVES_FILE to tmp_path, so no test writes the repository's data/;
  * NOTHING ABOUT THE DOORS CHANGED: the same fixtures produce the same statuses as before.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import promoter  # noqa: E402
from mt5desk import provenance  # noqa: E402

from libs.research.alpha_state import AlphaStateLedger  # noqa: E402

_ACC = {"login": 5551234, "server": "FusionMarkets-Live", "kind": provenance.LIVE}
_GOOD = {"status": "PROMOTION CANDIDATE", "exp_r": 0.276, "n": 40, "max_dd_r": -8.0, "days": 21}


@pytest.fixture
def desk(tmp_path, monkeypatch):
    """The lifecycle fixture, plus a registry: every path the promoter reads or writes on
    tmp_path, the allocator admitting whatever the shadow file names."""
    shadow_dir = tmp_path / "reports" / "shadow"
    shadow_dir.mkdir(parents=True)
    (tmp_path / "data").mkdir()
    (tmp_path / "logs").mkdir()
    monkeypatch.setattr(promoter, "SHADOW_DIR", shadow_dir)
    monkeypatch.setattr(promoter, "SLEEVES_FILE", tmp_path / "data" / "sleeves.json")
    monkeypatch.setattr(promoter, "LEDGER", tmp_path / "data" / "live_ledger.jsonl")
    monkeypatch.setattr(promoter, "LOG", tmp_path / "logs" / "promoter.log")
    monkeypatch.setattr(promoter, "GOLD_RETIRED_FILE", tmp_path / "data" / "GOLD_RETIRED.json")
    monkeypatch.setattr(promoter, "GOLD_RETIRED_VOIDED_FILE",
                        tmp_path / "data" / "GOLD_RETIRED_VOIDED.json")
    monkeypatch.setattr(promoter, "RECERT_AUDIT", tmp_path / "reports" / "recert.json")
    monkeypatch.setattr(promoter, "SLEEVE_REGISTRY", tmp_path / "data" / "sleeve_registry.json")
    monkeypatch.setattr(promoter.provenance, "current_account", lambda _acc: _ACC)
    monkeypatch.setattr(promoter, "clock_identities", dict)

    def _authority_from_shadow(base=None):
        try:
            blob = json.loads((shadow_dir / "shadow_state.json").read_text(encoding="utf-8"))
        except OSError:
            return set()
        out = set()
        for key, row in blob.items():
            if not isinstance(row, dict):
                continue
            parts = key.split(".")
            if len(parts) < 2:
                continue
            cond = parts[2] if len(parts) > 2 else None
            out.add((parts[0], parts[1], cond, "session_range_breakout", False))
        return out
    monkeypatch.setattr(promoter, "authorized_specs", _authority_from_shadow)

    alloc = tmp_path / "reports" / "pf_allocation.json"
    monkeypatch.setattr(promoter, "ALLOCATION", alloc)
    pinned: dict = {}

    def _write_allocation(keys, *, admit=True, heat=0.03, at=None) -> None:
        stamp = (at or datetime.now(tz=UTC)).isoformat()
        alloc.write_text(json.dumps({
            "generated_utc": stamp, "heat": {"total": 0.20}, "book": {}, "book_zeroed": {},
            "admission": {
                "status": "MEASURED", "measured_utc": stamp, "universe": {},
                "candidates": {k: {"symbol": "", "family": "", "selector": "",
                                   "delta_elogw_per_day": 0.0004 if admit else -0.0002,
                                   "heat_earned": heat if admit else 0.0, "admit": bool(admit),
                                   "why": "fixture: admitted" if admit else "fixture: refused"}
                               for k in keys}},
        }), encoding="utf-8")

    class Desk:
        root = tmp_path

        def allocation(self, keys, *, admit=True, heat=0.03, at=None) -> None:
            pinned["on"] = True
            _write_allocation(keys, admit=admit, heat=heat, at=at)

        def shadow(self, blob: dict) -> None:
            (shadow_dir / "shadow_state.json").write_text(json.dumps(blob), encoding="utf-8")
            if not pinned:
                _write_allocation(list(blob))

        def registry(self, rows: dict) -> None:
            (tmp_path / "data" / "sleeve_registry.json").write_text(
                json.dumps({"sleeves": rows}), encoding="utf-8")

        def ledger(self, rows: list[dict]) -> None:
            (tmp_path / "data" / "live_ledger.jsonl").write_text(
                "\n".join(json.dumps({**provenance.stamp(_ACC), **r}) for r in rows),
                encoding="utf-8")

        def sleeves(self) -> list[dict]:
            p = tmp_path / "data" / "sleeves.json"
            return json.loads(p.read_text(encoding="utf-8"))["sleeves"] if p.exists() else []

        def observations(self) -> list[dict]:
            p = tmp_path / "data" / "alpha_state_observations.jsonl"
            if not p.exists():
                return []
            return [json.loads(x) for x in p.read_text("utf-8").splitlines() if x.strip()]

        def ledger_path(self) -> Path:
            return tmp_path / "data" / "alpha_state_ledger.jsonl"

    return Desk()


def _losing(name: str, n: int = 12) -> list[dict]:
    losses = (-1.0, -0.62, -1.0, -0.95, -0.41, -1.0, -0.88, -1.0, -0.73, -1.0, -0.55, -1.0)
    return [{"sleeve": name, "r_multiple": losses[i % len(losses)]} for i in range(n)]


# ------------------------------------------------------------------- the certificate on the row
def test_a_promoted_row_carries_its_certificate_key_and_registry_sleeve_id(desk) -> None:
    desk.registry({"CADJPY.asia.FAILED_BREAK": {
        "identity": {"sleeve_id": "fc7a4bed7e8868331829", "code_hash": "38d9ca40fbd659c6"},
        "forward_start": "2026-08-27T07:58:09+00:00", "status": "LIVE"}})
    desk.shadow({"CADJPY.asia.FAILED_BREAK": dict(_GOOD)})
    promoter.main()
    (s,) = desk.sleeves()
    assert s["status"] == "LIVE"                       # the door itself is unchanged
    assert s["certificate"] == "CADJPY.asia.FAILED_BREAK" == s["name"]
    assert s["sleeve_id"] == "fc7a4bed7e8868331829"


def test_an_unregistered_sleeve_carries_none_never_an_empty_id(desk) -> None:
    desk.shadow({"USDJPY.asia": dict(_GOOD)})
    promoter.main()                                    # no registry file at all
    (s,) = desk.sleeves()
    assert s["certificate"] == "USDJPY.asia" and s["sleeve_id"] is None
    desk.registry({"EURJPY.asia": {"identity": {}}})   # a registry that lacks the id
    assert promoter.registry_sleeve_id("EURJPY.asia") is None
    assert promoter.registry_sleeve_id("USDJPY.asia") is None


def test_the_generic_and_scalp_lanes_carry_identity_too(desk, monkeypatch) -> None:
    key = "EURZAR.overnight_gap_decay.asia"
    desk.registry({key: {"identity": {"sleeve_id": "1903a4cc90212b4c29d5"}},
                   "xau_m5_test": {"identity": {"sleeve_id": "aa11bb22cc33dd44ee55"}}})
    spec = {"symbol": "EURZAR", "selector": "asia", "family": "overnight_gap_decay",
            "condition": None, "side": "LONG"}
    monkeypatch.setattr(promoter, "load_cert_specs", lambda: {key: spec})
    desk.allocation([key, "xau_m5_test"])
    view = promoter.allocation_view()
    sleeves: list[dict] = []
    assert promoter.promote_generic(sleeves, {key: {"status": "PROMOTION_CANDIDATE",
                                                    "exp_r": 0.2, "n": 55}},
                                    set(), set(), regrade={}, view=view)
    (g,) = sleeves
    assert g["certificate"] == key and g["sleeve_id"] == "1903a4cc90212b4c29d5"
    scalp = {"sleeves": {"xau_m5_test": {
        "status": "PROMOTION_CANDIDATE", "promotion_authority": True, "matured": True,
        "timeframe": "M5", "expectancy_r": 0.3, "n": 60, "days": 20,
        "choice": {"family": "gold_scalp", "session": "ny", "stop_atr": 1.0,
                   "target_atr": 2.0, "max_hold": 12}}}}
    assert promoter.promote_scalp(sleeves, scalp, set(), set(), view=view)
    sc = sleeves[-1]
    assert sc["certificate"] == "forward_clock"           # the lane's own convention, kept
    assert sc["sleeve_id"] == "aa11bb22cc33dd44ee55"
    # A LANE FUNCTION CALLED ON ITS OWN WRITES NOTHING: doors are buffered for `main` to flush,
    # because seven test files call these lanes directly with every ledger path left real.
    assert desk.observations() == []
    promoter.flush_door_events()
    doors = [o["door"] for o in desk.observations()]
    assert doors == ["PROMOTED", "PROMOTED"]
    assert promoter._DOOR_EVENTS == []


# ------------------------------------------------------------------- the alpha-state ledger
def test_a_promotion_is_observed_not_forced_onto_the_ledger(desk) -> None:
    """DISCOVERED -> LIVE is nine rungs; the machine refuses it and the refusal is the record."""
    desk.registry({"CADJPY.asia": {"identity": {"sleeve_id": "abc"},
                                   "forward_start": "2026-08-27T07:58:09+00:00"}})
    desk.shadow({"CADJPY.asia": dict(_GOOD)})
    promoter.main()
    (o,) = desk.observations()
    assert o["alpha_id"] == "CADJPY.asia" and o["door"] == "PROMOTED"
    assert o["from"] is None and o["to"] == "LIVE" and o["rung_attempted"] == "LIVE"
    assert o["outcome"] == "OBSERVATION"
    assert "REFUSED DISCOVERED -> LIVE" in o["why"]
    assert o["ledger_state_before"] == "DISCOVERED" == o["ledger_state_after"]
    assert o["evidence"]["certificate"] == "CADJPY.asia"
    assert o["evidence"]["forward_observations"] == "40"
    assert o["evidence"]["forward_result"] == "0.2760R"
    assert o["evidence"]["shadow_started_at"] == "2026-08-27T07:58:09+00:00"
    assert o["evidence"]["heat_earned"] == "0.03"
    datetime.fromisoformat(o["at"])                     # a real per-door timestamp
    assert not desk.ledger_path().exists(), "a refused step must not touch the ledger"


def test_a_standby_promotion_claims_capital_eligible_and_is_observed(desk) -> None:
    desk.allocation(["CADJPY.asia"], admit=False)
    desk.shadow({"CADJPY.asia": dict(_GOOD)})
    promoter.main()
    (s,) = desk.sleeves()
    assert s["status"] == "STANDBY"
    (o,) = desk.observations()
    assert o["to"] == "STANDBY" and o["rung_attempted"] == "CAPITAL_ELIGIBLE"
    assert o["outcome"] == "OBSERVATION" and "REFUSED" in o["why"]


def test_demotion_and_restoration_are_observed_with_no_rung_and_the_live_rung(desk) -> None:
    desk.shadow({"CADJPY.asia": dict(_GOOD)})
    promoter.main()
    desk.allocation(["CADJPY.asia"], admit=False)
    promoter.main()                                     # LIVE -> STANDBY on one reading
    assert desk.sleeves()[0]["status"] == "STANDBY"
    # two consecutive admitting readings on two DIFFERENT scans restore it
    desk.allocation(["CADJPY.asia"], admit=True, at=datetime(2026, 9, 8, 1, tzinfo=UTC))
    promoter.main()
    desk.allocation(["CADJPY.asia"], admit=True, at=datetime(2026, 9, 8, 2, tzinfo=UTC))
    promoter.main()
    assert desk.sleeves()[0]["status"] == "LIVE"
    obs = desk.observations()
    assert [o["door"] for o in obs] == ["PROMOTED", "DEMOTED", "RESTORED"]
    demoted = obs[1]
    assert demoted["from"] == "LIVE" and demoted["to"] == "STANDBY"
    assert demoted["rung_attempted"] is None and demoted["outcome"] == "OBSERVATION"
    assert "not a rung" in demoted["why"] and demoted["reason"]
    restored = obs[2]
    assert restored["from"] == "STANDBY" and restored["rung_attempted"] == "LIVE"
    assert restored["evidence"]["admit_streak"] == str(promoter.PROMOTE_ADMIT_STREAK)
    assert not desk.ledger_path().exists()


def test_a_retirement_is_ledgered_with_the_promoters_own_reason(desk) -> None:
    desk.shadow({"USDJPY.asia": dict(_GOOD)})
    promoter.main()
    desk.ledger(_losing("USDJPY.asia"))
    promoter.main()
    (s,) = desk.sleeves()
    assert s["status"] == "RETIRED"
    obs = desk.observations()
    assert [o["door"] for o in obs] == ["PROMOTED", "RETIRED"]
    r = obs[1]
    assert r["outcome"] == "LEDGERED" and r["from"] == "LIVE"
    assert r["ledger_state_before"] == "DISCOVERED" and r["ledger_state_after"] == "RETIRED"
    assert r["reason"].startswith("roll20 exp") and r["evidence"]["forward_observations"] == "12"
    # the ledger file is real, loadable, and carries the reason, not the generic note
    led = AlphaStateLedger(desk.ledger_path())
    rec = led.get("USDJPY.asia")
    assert rec.state == "RETIRED" and rec.note.startswith("roll20 exp")
    assert rec.history[-1][0] == "RETIRED" and rec.history[-1][1] == r["at"]
    # and re-running never re-retires or re-writes: the row is RETIRED and skipped
    promoter.main()
    assert len(desk.observations()) == 2


def test_the_ledger_paths_follow_the_roster_to_tmp_path(desk) -> None:
    ledger, obs = promoter._alpha_state_paths()
    assert ledger == desk.root / "data" / "alpha_state_ledger.jsonl"
    assert obs == desk.root / "data" / "alpha_state_observations.jsonl"
    assert promoter.ALPHA_STATE_LEDGER == _ROOT / "data" / "alpha_state_ledger.jsonl"


def test_an_explicit_ledger_path_wins_over_the_derived_one(desk, monkeypatch) -> None:
    monkeypatch.setattr(promoter, "ALPHA_STATE_LEDGER", desk.root / "elsewhere.jsonl")
    ledger, obs = promoter._alpha_state_paths()
    assert ledger == desk.root / "elsewhere.jsonl"
    assert obs == desk.root / "data" / "alpha_state_observations.jsonl"


def test_an_unreadable_ledger_never_aborts_the_pass(desk) -> None:
    desk.ledger_path().write_text('{"alpha_id": "forged", "state": "LIVE", "evidence": {}, '
                                  '"history": [["LIVE", "2026-01-01T00:00:00Z"]], "note": ""}\n',
                                  "utf-8")
    desk.shadow({"CADJPY.asia": dict(_GOOD)})
    promoter.main()
    (s,) = desk.sleeves()
    assert s["status"] == "LIVE"                       # the promotion happened regardless
    (o,) = desk.observations()
    assert o["outcome"] == "OBSERVATION" and "unreadable" in o["why"]


def test_the_door_rung_map_names_every_door_and_forces_nothing() -> None:
    assert promoter._RUNG_BY_DOOR == {
        ("PROMOTED", "LIVE"): "LIVE", ("PROMOTED", "STANDBY"): "CAPITAL_ELIGIBLE",
        ("RESTORED", "LIVE"): "LIVE", ("DEMOTED", "STANDBY"): None,
        ("RETIRED", "RETIRED"): "RETIRED"}
    src = (_DESK / "research" / "promoter.py").read_text("utf-8")
    body = src[src.index("def record_door_transition"):src.index("def account_in_hand")]
    assert body.count("ledger.advance(") == 1 and body.count("ledger.retreat(") == 1, (
        "one attempt per door; a walk up the rungs would be the machine forced from below")
    # the thresholds and the streak this wave may not move
    assert (promoter.RETIRE_MIN_N, promoter.RETIRE_MAX_DD, promoter.RETIRE_MIN_EXP,
            promoter.PROMOTE_ADMIT_STREAK, promoter.ADMISSION_MAX_AGE_H) == (10, -25.0, 0.05, 2,
                                                                             26.0)
