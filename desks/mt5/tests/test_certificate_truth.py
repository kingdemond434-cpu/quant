"""ONE CERTIFICATE TRUTH on a temporary desk: the audit names every divergence by store, key and
kind against the one lane; --apply moves banned-family certificates and clocks to history, retires
every unbacked clock with the lane's reason, never touches the live book or a row it cannot parse,
and is idempotent; the fence exits 2 on residue and 0 once the lane is the only truth."""
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
from gate_policy import ATTESTATION, GATES  # noqa: E402

sys.path.insert(0, str(_ROOT / "scripts"))
import check_certificate_truth as FENCE  # noqa: E402


def _gates(fail: tuple[str, ...] = ()) -> dict:
    return {g: {"passed": g not in fail, "message": "test"} for g in GATES}


def _w(p: Path, doc: object) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=1), encoding="utf-8")


def _r(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def _cert(sym: str, fam: str, sel: str, fail: tuple[str, ...] = ()) -> dict:
    return {"hunt": "external", "cell": f"{sym}.{fam}", "sym": sym, "days": 500,
            "gates": _gates(fail), "gated_at": "2026-09-01T00:00:00+00:00",
            "shadow_spec": {"symbol": sym, "family": fam, "selector": sel, "is_universe": True}}


@pytest.fixture
def desk(tmp_path: Path) -> Path:
    base = tmp_path / "desk"
    canon = {"n": 3, "gate_policy": dict(ATTESTATION), "survivors": {
        "external.CADJPY.session_range_breakout": _cert("CADJPY", "session_range_breakout", "asia"),
        "external.EURCHF.discovered.p=1": _cert("EURCHF", "discovered", "asia"),
        "external.AUDCAD.carry.p=2": _cert("AUDCAD", "carry", "continuous", fail=("cpcv",)),
    }}
    _w(base / "reports" / "UNIVERSAL_SURVIVORS.json", canon)
    _w(base / "data" / "UNIVERSAL_SURVIVORS.canon.json", canon)
    _w(base / "reports" / "POWER_CURE_CANDIDATES.json", {
        "gate_policy": dict(ATTESTATION), "n": 2, "candidates": {
            "external.USDSGD.overnight_gap_decay.p=3": {
                "validity_pass": True, "failed_power_gates": ["deflated_sharpe"],
                "shadow_spec": {"symbol": "USDSGD", "family": "overnight_gap_decay",
                                "selector": "continuous", "is_universe": True}},
            "external.EURCHF.discovered.p=9": {
                "validity_pass": True, "failed_power_gates": ["cpcv"],
                "shadow_spec": {"symbol": "EURCHF", "family": "discovered",
                                "selector": "asia", "is_universe": True}}}})
    _w(base / "reports" / "QQUANT_GATES.json", {
        "gate_policy": dict(ATTESTATION), "verdicts": [
            {"id": "AUDNZD dav_range_filter_adx SHORT afternoon NORMAL_DAY",
             "stages": _gates(fail=("walk_forward",))},
            {"id": "NZDUSD breakout LONG asia TREND_DAY", "stages": _gates(fail=("pbo",))}]})
    _w(base / "reports" / "SURVIVORS_LEDGER.json", {"n": 3, "claims": {
        "external.CADJPY.session_range_breakout": {"status": "UNIVERSAL", "shadow_spec": {
            "symbol": "CADJPY", "family": "session_range_breakout", "selector": "asia"}},
        "external.GBPJPY.session_range_breakout": {"status": "UNIVERSAL", "shadow_spec": {
            "symbol": "GBPJPY", "family": "session_range_breakout", "selector": "asia"}},
        "external.EURCHF.discovered.p=1": {"status": "UNIVERSAL", "shadow_spec": {
            "symbol": "EURCHF", "family": "discovered", "selector": "asia"}}}})

    def ident(sym: str, fam: str, sel: str) -> dict:
        return {"identity": {"family": fam, "symbol": sym, "direction": "LONG",
                             "timeframe": "H1", "selector": sel, "params": {},
                             "sleeve_id": f"id-{sym}-{fam}"}, "status": "LIVE", "status_why": ""}
    _w(base / "data" / "sleeve_registry.json", {"sleeves": {
        "CADJPY.asia": ident("CADJPY", "session_range_breakout", "asia"),
        "EURCHF.discovered.asia#band=[0.9, 1.0]_feature=ru_24": ident(
            "EURCHF", "discovered", "asia"),
        "USDSGD.overnight_gap_decay.continuous": ident(
            "USDSGD", "overnight_gap_decay", "continuous"),
        "CHFNOK.carry.asia#input_symbol=CHFNOK": ident("CHFNOK", "carry", "asia"),
        "XAUUSD.london_am": ident("XAUUSD", "session_range_breakout", "london_am"),
        "OLD.asia": {**ident("OLD", "session_range_breakout", "asia"), "status": "RETIRED"},
    }})
    _w(base / "reports" / "shadow" / "shadow_state.json", {
        "CADJPY.asia": {"status": "ACTIVE", "n": 3},
        "EURCHF.discovered.asia#band=[0.9, 1.0]_feature=ru_24": {"status": "ACTIVE", "n": 9},
        "AUDNZD.dav_range_filter_adx.afternoon.SHORT": {"status": "ACTIVE", "n": 2},
        "NZDCAD.carry.continuous#x=1": {"status": "ACTIVE", "n": 1},
        "GBPJPY.asia": {"status": "RETIRED_ORPHAN", "n": 4},
        "USDJPY.asia": {"status": "REFUSED_BY_UNIVERSE_POLICY", "n": 0}})
    _w(base / "reports" / "shadow" / "scalp_shadow_state.json", {
        "sleeves": {"xau_m5_anti_breakout_overlap": {"status": "ACTIVE", "n": 40}},
        "AUDCAD.discovered.asia#p=1": {"status": "ACTIVE", "n": 5}})
    _w(base / "data" / "sleeves.json", {"sleeves": [
        {"name": "xau_asia_gold", "symbol": "XAUUSD", "family": "session_range_breakout",
         "selector": "asia", "status": "LIVE", "risk_frac": 0.01, "certificate": "forward_clock",
         "principal_override": {"by": "principal"}},
        {"name": "audcad_discovered_asia_p", "symbol": "AUDCAD", "family": "discovered",
         "selector": "asia", "status": "LIVE", "risk_frac": 0.005,
         "certificate": {"source": "UNIVERSAL_SURVIVORS",
                         "cell": "external.AUDCAD.discovered.p=7"}},
        {"name": "cadjpy_srb_asia", "symbol": "CADJPY", "family": "session_range_breakout",
         "selector": "asia", "status": "STANDBY", "risk_frac": 0.0,
         "certificate": {"source": "UNIVERSAL_SURVIVORS",
                         "cell": "external.CADJPY.session_range_breakout"}},
        {"name": "gbpjpy_srb_asia", "symbol": "GBPJPY", "family": "session_range_breakout",
         "selector": "asia", "status": "LIVE", "risk_frac": 0.004,
         "certificate": {"source": "UNIVERSAL_SURVIVORS",
                         "cell": "external.GBPJPY.session_range_breakout"}},
        {"name": "old_discovered", "symbol": "EURCHF", "family": "discovered",
         "status": "RETIRED", "risk_frac": 0.0}]})
    _w(base / "data" / "forward_reconcile.json", {"certified_clocks": 5, "enrolled": 6})
    _w(base / "data" / "banned_families.json", {"banned": {"discovered": {
        "since": "2026-09-16", "by": "principal", "why": "test"}}})
    return base


def _kinds(doc: dict) -> dict[str, int]:
    return dict(doc["by_kind"])


def test_parse_clock_key_reads_every_shape_the_engine_writes():
    assert CT.parse_clock_key("CADJPY.asia") == {
        "symbol": "CADJPY", "family": "session_range_breakout", "selector": "asia",
        "side": "LONG", "timeframe": "H1"}
    k = CT.parse_clock_key("EURCHF.discovered.asia#band=[0.9, 1.0]_feature=ru_24.SHORT")
    assert k == {"symbol": "EURCHF", "family": "discovered", "selector": "asia",
                 "side": "SHORT", "timeframe": "H1"}
    assert CT.parse_clock_key("XAUUSD.asia@M5#rr=1.5")["timeframe"] == "M5"
    q = CT.parse_clock_key(
        "qquant.hunt16.json.AUDNZD dav_range_filter_adx SHORT afternoon NORMAL_DAY")
    assert (q["symbol"], q["family"], q["selector"], q["side"]) == (
        "AUDNZD", "dav_range_filter_adx", "afternoon", "SHORT")
    ext = CT.parse_clock_key("external.AUDCAD.discovered.p=7c99")
    assert (ext["symbol"], ext["family"], ext["selector"]) == ("AUDCAD", "discovered", None)
    assert CT.parse_clock_key("xau_m5_anti_breakout_overlap") is None
    assert CT.parse_clock_key("") is None


def test_audit_names_every_divergence_by_store_key_and_kind(desk: Path):
    paths = CT.Paths.at(desk)
    doc = CT.audit(paths, now="2026-09-22T12:00:00+00:00")
    lane = doc["canon"]
    assert lane["status"] == "EXACT" and lane["n"] == 1
    assert lane["rows_not_ten_gate"] == 1            # the carry cell that failed cpcv
    assert lane["cure_n"] == 2                        # USDSGD ogd + the AUDNZD qquant verdict
    assert lane["certificate_keys"] == ["external.CADJPY.session_range_breakout"]
    assert _kinds(doc) == {
        "BANNED_CERTIFICATE": 2,          # canon + seal
        "BANNED_CURE_CANDIDATE": 1,
        "BANNED_CLAIM": 1, "CLAIM_NOT_IN_CANON": 1,
        "BANNED_CLOCK": 3,                # registry, shadow, scalp lane
        "UNBACKED_CLOCK": 2,              # CHFNOK carry, NZDCAD carry
        "LIVE_BOOK_UNBACKED_CLOCK": 1,    # XAUUSD.london_am: the gold book's symbol
        "UNPARSED_CLOCK": 1,              # the scalp row with a name-shaped key
        "BANNED_SLEEVE": 1,
        "SLEEVE_CERTIFICATE_NOT_IN_CANON": 1,
    }
    reg = doc["stores"]["sleeve_registry"]
    assert (reg["live_rows"], reg["backed"], reg["cure_backed"], reg["unbacked"],
            reg["banned"], reg["protected"]) == (5, 1, 1, 2, 1, 1)
    sh = doc["stores"]["shadow_state"]
    assert (sh["live_rows"], sh["backed"], sh["cure_backed"], sh["unbacked"], sh["banned"]) == (
        4, 1, 1, 1, 1)
    assert doc["stores"]["sleeves"]["protected_symbols"] == ["XAUUSD"]
    assert doc["stores"]["sleeves"]["live_book"] == 1
    prot = [d for d in doc["divergences"] if d["kind"] == "LIVE_BOOK_UNBACKED_CLOCK"]
    assert prot[0]["key"] == "XAUUSD.london_am" and prot[0]["protected"] is True
    assert doc["ok"] is False and doc["n_fatal"] == 11
    assert doc["migration"]["planned"]["unbacked_clocks_to_retire"] == 2
    assert doc["migration"]["planned"]["unbacked_clocks_protected"] == 1
    # the unparsed lane row and the live-book row are published, never fatal
    assert "UNPARSED_CLOCK" not in CT.FATAL_KINDS
    assert "LIVE_BOOK_UNBACKED_CLOCK" not in CT.FATAL_KINDS


def test_main_writes_the_report_and_an_event_and_never_applies_without_the_flag(desk: Path):
    rc = CT.main(["--once", "--budget-s", "120", "--base", str(desk)])
    assert rc == 0
    paths = CT.Paths.at(desk)
    doc = _r(paths.out)
    assert doc["n_divergences"] > 0 and "applied" not in doc and doc["budget_s"] == 120.0
    rows = [json.loads(x) for x in paths.events.read_text("utf-8").splitlines() if x.strip()]
    assert rows[-1]["leg"] == "certificate_truth" and rows[-1]["applied"] is False
    # nothing moved: the canon still holds the banned certificate, the registry row is LIVE
    assert "external.EURCHF.discovered.p=1" in _r(paths.canon)["survivors"]
    reg = _r(paths.registry)["sleeves"]
    assert reg["CHFNOK.carry.asia#input_symbol=CHFNOK"]["status"] == "LIVE"
    assert not paths.history.exists()


def test_apply_migrates_banned_rows_to_history_and_retires_unbacked_clocks(desk: Path):
    paths = CT.Paths.at(desk)
    out = CT.apply(paths, now="2026-09-22T12:00:00+00:00")
    assert out["moved"] == 11 and out["lane_status"] == "EXACT"
    assert out["by_store"] == {"UNIVERSAL_SURVIVORS": 1, "UNIVERSAL_SURVIVORS.canon": 1,
                               "POWER_CURE_CANDIDATES": 1, "SURVIVORS_LEDGER": 2,
                               "sleeve_registry": 2, "shadow_state": 2,
                               "scalp_shadow_state": 1, "sleeves": 1}
    # the canon and its seal: the banned certificate is gone, the other rows stand, n is honest
    for p in (paths.canon, paths.seal):
        d = _r(p)
        assert "external.EURCHF.discovered.p=1" not in d["survivors"]
        assert set(d["survivors"]) == {"external.CADJPY.session_range_breakout",
                                       "external.AUDCAD.carry.p=2"}
        assert d["n"] == 2 and d["certificate_truth"]["retired_to_history"] == 1
    assert "external.EURCHF.discovered.p=9" not in _r(paths.cure)["candidates"]
    # the ledger keeps the claims as history with the reason on them
    claims = _r(paths.ledger)["claims"]
    assert claims["external.EURCHF.discovered.p=1"]["status"] == "RETIRED"
    assert claims["external.EURCHF.discovered.p=1"]["retire_reason"] == CT.BAN_REASON
    assert claims["external.GBPJPY.session_range_breakout"]["retire_reason"] == CT.HISTORY_REASON
    assert claims["external.CADJPY.session_range_breakout"]["status"] == "UNIVERSAL"
    # the registry: banned and unbacked retired with their reasons; backed, cure and the live
    # book's symbol untouched
    reg = _r(paths.registry)["sleeves"]
    banned = reg["EURCHF.discovered.asia#band=[0.9, 1.0]_feature=ru_24"]
    assert banned["status"] == "RETIRED" and banned["status_why"] == CT.BAN_REASON
    assert reg["CHFNOK.carry.asia#input_symbol=CHFNOK"]["status_why"] == CT.UNBACKED_REASON
    assert reg["CHFNOK.carry.asia#input_symbol=CHFNOK"]["retired_by"] == "certificate_truth"
    for key in ("CADJPY.asia", "USDSGD.overnight_gap_decay.continuous", "XAUUSD.london_am"):
        assert reg[key]["status"] == "LIVE", key
    # the shadow state: same rule, the engine's own vocabulary, promotion authority withdrawn
    sh = _r(paths.shadow)
    assert sh["EURCHF.discovered.asia#band=[0.9, 1.0]_feature=ru_24"]["status"] == "RETIRED"
    assert sh["NZDCAD.carry.continuous#x=1"]["retire_reason"] == CT.UNBACKED_REASON
    assert sh["NZDCAD.carry.continuous#x=1"]["promotion_authority"] is False
    assert sh["CADJPY.asia"]["status"] == "ACTIVE"
    assert sh["AUDNZD.dav_range_filter_adx.afternoon.SHORT"]["status"] == "ACTIVE"
    assert sh["GBPJPY.asia"]["status"] == "RETIRED_ORPHAN"        # terminal rows untouched
    # a lane owns its rows: only the banned one leaves, the unparsed one is untouched
    scalp = _r(paths.lanes[1])
    assert scalp["AUDCAD.discovered.asia#p=1"]["status"] == "RETIRED"
    assert scalp["sleeves"]["xau_m5_anti_breakout_overlap"]["status"] == "ACTIVE"
    # the live book: the banned row in the promoter's vocabulary; every other row untouched
    sl = {s["name"]: s for s in _r(paths.sleeves)["sleeves"]}
    assert sl["audcad_discovered_asia_p"]["status"] == "RETIRED"
    assert sl["audcad_discovered_asia_p"]["risk_frac"] == 0.0
    assert sl["audcad_discovered_asia_p"]["risk_frac_source"] == "none"
    assert sl["audcad_discovered_asia_p"]["retire_reason"] == CT.BAN_REASON
    assert sl["xau_asia_gold"]["status"] == "LIVE" and sl["gbpjpy_srb_asia"]["status"] == "LIVE"
    # history holds one row per move, each with store, key, reason and the statuses
    hist = [json.loads(x) for x in paths.history.read_text("utf-8").splitlines() if x.strip()]
    assert len(hist) == 11
    assert {h["store"] for h in hist} == set(out["by_store"])
    assert all(h["to_status"] == "RETIRED" and h["reason"] for h in hist)
    # after: only the published, non-fatal rows remain
    assert out["after"]["ok"] is True
    assert out["after"]["by_kind"] == {"LIVE_BOOK_UNBACKED_CLOCK": 1, "UNPARSED_CLOCK": 1,
                                       "SLEEVE_CERTIFICATE_NOT_IN_CANON": 1}


def test_apply_is_idempotent(desk: Path):
    paths = CT.Paths.at(desk)
    first = CT.apply(paths)
    second = CT.apply(paths)
    assert first["moved"] == 11 and second["moved"] == 0 and second["by_store"] == {}
    hist = paths.history.read_text("utf-8").splitlines()
    assert len([x for x in hist if x.strip()]) == 11


def test_an_unmeasured_canon_retires_only_banned_rows(desk: Path):
    paths = CT.Paths.at(desk)
    for p in (paths.canon, paths.seal):
        d = _r(p)
        d["gate_policy"] = {"version": "something-else"}
        _w(p, d)
    doc = CT.audit(paths)
    assert doc["canon"]["status"] == "UNMEASURED" and doc["canon"]["n"] == 0
    kinds = _kinds(doc)
    assert kinds["CANON_UNMEASURED_WITH_LIVE_CLOCKS"] == 1
    assert "UNBACKED_CLOCK" not in kinds and "CLAIM_NOT_IN_CANON" not in kinds
    assert kinds["BANNED_CERTIFICATE"] == 2 and kinds["BANNED_CLOCK"] == 3
    out = CT.apply(paths, doc)
    reg = _r(paths.registry)["sleeves"]
    assert reg["CHFNOK.carry.asia#input_symbol=CHFNOK"]["status"] == "LIVE"     # not evidence
    assert reg["EURCHF.discovered.asia#band=[0.9, 1.0]_feature=ru_24"]["status"] == "RETIRED"
    assert out["skipped"]["unbacked_on_unmeasured_canon"] == 0
    assert "external.EURCHF.discovered.p=1" not in _r(paths.canon)["survivors"]


def test_an_empty_canon_is_a_verdict_and_the_reconciler_is_caught_lying(desk: Path):
    paths = CT.Paths.at(desk)
    for p in (paths.canon, paths.seal):
        d = _r(p)
        d["survivors"].pop("external.CADJPY.session_range_breakout")
        _w(p, d)
    doc = CT.audit(paths)
    assert doc["canon"]["status"] == "EMPTY"
    kinds = _kinds(doc)
    assert kinds["RECONCILE_CERTIFIED_CLOCKS_ON_EMPTY_CANON"] == 1
    assert kinds["UNBACKED_CLOCK"] == 4            # CADJPY's clock is unbacked now, on both stores
    out = CT.apply(paths, doc)
    reg = _r(paths.registry)["sleeves"]
    assert reg["CADJPY.asia"]["status"] == "RETIRED"
    assert reg["USDSGD.overnight_gap_decay.continuous"]["status"] == "LIVE"
    assert out["moved"] == 14


def test_the_fence_fails_on_residue_and_passes_once_the_lane_is_the_truth(desk: Path, capsys):
    assert FENCE.main(["--base", str(desk)]) == 2
    out = capsys.readouterr().out
    assert "FATAL BANNED_CERTIFICATE" in out and "--once --apply" in out
    CT.apply(CT.Paths.at(desk))
    assert FENCE.main(["--base", str(desk)]) == 0
    assert (desk / "reports" / "CERTIFICATE_TRUTH.json").exists()


def test_the_fence_reads_no_desk_state_as_unmeasured_unless_state_is_required(tmp_path: Path):
    empty = tmp_path / "nothing"
    empty.mkdir()
    assert FENCE.main(["--base", str(empty)]) == 0
    assert FENCE.main(["--base", str(empty), "--require-state"]) == 2


def test_the_leg_the_layer_the_gate_and_the_lesson_are_wired():
    src = (_DESK / "research" / "hourly_cycle.py").read_text(encoding="utf-8")
    call = src[src.index('_costed("certificate_truth"'):][:400]
    assert '"research/certificate_truth.py", "--once", "--budget-s", "120"' in call
    assert "--apply" not in call                       # the migration never rides the clock
    assert '"certificate_truth"), "validate")' in src   # the validate department
    assert '"certificate_truth": ctt' in src
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["certificate_truth"] == "meta"
    gate = (_ROOT / "scripts" / "run_law_gate.py").read_text(encoding="utf-8")
    assert '("check_certificate_truth.py", ())' in gate
    assert '("check_certificate_truth.py", ("--require-state",))' in gate
    lessons = (_ROOT / "docs" / "desk_lessons.jsonl").read_text(encoding="utf-8")
    assert "certificate_truth" in lessons and "discovery" in lessons.lower()
