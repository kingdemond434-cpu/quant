"""The clock door and the capital door, split (coordinator ruling C, 2026-10-14).

Measured that day: 127 certificates held with no forward clock, 102 of them in families the
replication lane has no written rule for -- UNMEASURED by construction, so held forever. A paper
clock deploys no capital, so those clocks now start (tagged UNMEASURED_NO_SPEC) and REPLICATED is
required where money moves: every row newly written LIVE to sleeves.json, by any path.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK.parents[1]), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import admission_integrity as ai  # noqa: E402
import promoter  # noqa: E402
import replication_civilization as rc  # noqa: E402
import shadow_forward as sf  # noqa: E402

from research import canon_publication as cp  # noqa: E402

CERT = "external.EURZAR.carry.p=8339edce23032d21"
SPEC_BOOK = ["overnight_gap_decay", "session_range_breakout"]
#: The main lane's enrolment, as `promoter.clock_identities` returns it (set per test).
CLOCKS: dict[str, dict] = {}
MAIN_KEY = "USDJPY.asia#rr=2.5"
MAIN_CANON = "external.USDJPY@H1.session_range_breakout.p=0123456789abcdef"
REP = {"verdict": "REPLICATED", "sharpe_metric_version": rc.SHARPE_METRIC_VERSION}


def _book(tmp: Path, rows: dict[str, dict], spec_book: list[str] | None = SPEC_BOOK) -> Path:
    p = tmp / "verdicts.json"
    doc: dict = {"certificates": rows}
    if spec_book is not None:
        doc["spec_book"] = spec_book
    p.write_text(json.dumps(doc), "utf-8")
    return p


def _gate(tmp: Path, rows: dict[str, dict], spec_book: list[str] | None = SPEC_BOOK
          ) -> ai.IntegrityGate:
    return ai.IntegrityGate.load(placebo=tmp / "absent.json", verdicts=_book(tmp, rows, spec_book))


def _hold(gate: ai.IntegrityGate, cert: str, family: str) -> str | None:
    return gate.hold(cert, symbol="EURZAR", family=family, selector="asia", side="LONG",
                     params={})


# ------------------------------------------------------------------ the clock door
def test_a_family_with_no_written_rule_starts_its_paper_clock(tmp_path: Path) -> None:
    assert _hold(_gate(tmp_path, {}), CERT, "carry") is None


def test_a_family_with_a_written_rule_still_waits_for_replicated(tmp_path: Path) -> None:
    assert str(_hold(_gate(tmp_path, {}), CERT, "overnight_gap_decay")).startswith(
        ai.HELD_UNREPLICATED)


def test_a_recorded_no_spec_verdict_releases_when_no_book_was_published(tmp_path: Path) -> None:
    gate = _gate(tmp_path, {CERT: {"verdict": "UNMEASURED", "fp": "x", "why": [
        "no written specification in the spec book for family 'carry'"]}}, spec_book=None)
    assert _hold(gate, CERT, "carry") is None
    assert _hold(_gate(tmp_path, {}, spec_book=None), CERT, "carry") is not None


def test_the_placebo_alarm_still_holds_a_no_spec_clock(tmp_path: Path) -> None:
    gate = _gate(tmp_path, {})
    gate.alarm = {"blocks": True, "why": "planted trap admitted"}
    assert str(_hold(gate, CERT, "carry")).startswith(ai.HELD_PLACEBO)


def test_the_released_clock_is_tagged_unmeasured_no_spec(tmp_path: Path) -> None:
    sf.REPLICATION_TAG.clear()
    run = {"certificate": CERT, "symbol": "EURZAR", "family": "carry", "selector": "asia",
           "side": "LONG", "params": {}}
    assert sf._held(run, "K", _gate(tmp_path, {}), set(), "") is None
    assert sf.REPLICATION_TAG == {"K": ai.NO_SPEC}


# ------------------------------------------------------------------ the capital door
def test_live_needs_replicated_and_fails_closed_otherwise(tmp_path: Path) -> None:
    gate = _gate(tmp_path, {CERT: dict(REP),
                            "external.U": {"verdict": "UNMEASURED", "why": ["no bars"]},
                            "external.M": {"verdict": "MISMATCH"}})
    assert gate.live_refusal(CERT) is None
    for cert in ("external.U", "external.M", "external.never"):
        assert str(gate.live_refusal(cert)).startswith(ai.REFUSED_UNREPLICATED), cert


EVENTS: list[tuple[str, dict]] = []


@pytest.fixture()
def roster(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    path = tmp_path / "sleeves.json"
    monkeypatch.setattr(promoter, "SLEEVES_FILE", path)
    monkeypatch.setattr(promoter, "REPLICATION_WAIVER", tmp_path / "waiver.json")
    monkeypatch.setattr(promoter, "cost_basis_of", lambda row, universe=None: ("h", "test"))
    monkeypatch.setattr(promoter, "artifact_of", lambda row: {"ok": True, "problems": []})
    monkeypatch.setattr(promoter, "_apply_live_policy", lambda rows: 0)
    monkeypatch.setattr(promoter, "plog", lambda *a, **k: None)
    monkeypatch.setattr(ai, "REPLICATION_VERDICTS", _book(tmp_path, {}))
    # The main lane's clock key -> canon map is the enrolment's; tests that need one set it.
    monkeypatch.setattr(promoter, "clock_identities", lambda: dict(CLOCKS))
    CLOCKS.clear()
    EVENTS.clear()
    monkeypatch.setattr(promoter, "note_door", lambda name, **k: EVENTS.append((name, k)))

    def save(prior: list[dict], rows: list[dict]) -> dict[str, dict]:
        path.write_text(json.dumps({"sleeves": prior}), "utf-8")
        promoter.save_sleeves(rows)
        return {r["name"]: r for r in json.loads(path.read_text("utf-8"))["sleeves"]}
    return save


def _principal_row(status: str = "LIVE") -> dict:
    """The shape `apply_principal_promotions` writes: principal_certificate on a LIVE row."""
    return {"name": "eurzar_carry_asia_p_8339edce23032d21", "symbol": "EURZAR", "family": "carry",
            "status": status, "risk_frac": 0.03, "principal_override": True,
            "principal_certificate": CERT,
            "certificate": {"source": "UNIVERSAL_SURVIVORS", "cell": CERT}}


def test_the_principal_book_path_is_refused_when_unreplicated(roster) -> None:
    got = roster([], [_principal_row()])["eurzar_carry_asia_p_8339edce23032d21"]
    assert (got["status"], got["risk_frac"]) == ("STANDBY", 0.0)
    assert got["demote_reason"].startswith(ai.REFUSED_UNREPLICATED)


def _reconcile(monkeypatch, rows: list[dict]) -> None:
    monkeypatch.setattr(promoter, "capital_verdict", lambda *a, **k: {
        "status": "LIVE", "risk_frac": 0.03, "streak": 2, "why": "funded"})
    promoter.reconcile_capital(rows, {"fresh": True, "at": "2026-10-14T00:00:00+00:00",
                                      "admission_at": "2026-10-14T01:00:00+00:00"})


def test_a_reconcile_restore_is_refused_when_unreplicated(roster, monkeypatch) -> None:
    row = {**_principal_row("STANDBY"), "demote_reason": "the optimiser gives it 0% heat"}
    on_disk = dict(row)
    rows = [row]
    for _ in range(3):                                # three passes, as the audit probe ran
        _reconcile(monkeypatch, rows)
        got = roster([on_disk], rows)["eurzar_carry_asia_p_8339edce23032d21"]
    assert rows[0]["status"] == "STANDBY" and got["status"] == "STANDBY"
    assert rows[0]["replication_refusal"].startswith(ai.REFUSED_UNREPLICATED)
    assert not [e for e in EVENTS if e[1].get("door") == "RESTORED"]   # no false RESTORED


def test_a_reconcile_restore_of_a_replicated_certificate_is_written(roster, tmp_path,
                                                                   monkeypatch) -> None:
    monkeypatch.setattr(ai, "REPLICATION_VERDICTS",
                        _book(tmp_path, {CERT: dict(REP)}))
    rows = [{**_principal_row("STANDBY"), "replication_refusal": "old"}]
    _reconcile(monkeypatch, rows)
    assert rows[0]["status"] == "LIVE" and "replication_refusal" not in rows[0]
    assert [e[1]["door"] for e in EVENTS] == ["RESTORED"]


# The main shadow lane writes `certificate` as its CLOCK KEY and the generic (qquant) lane as its
# survivor key; the replication lane keys verdicts by canon id, so the main lane's clock key is
# resolved through the enrolment (audit of door v3, probe P7). The scalp lane writes its markers.
def _lane_row(cert: object, name: str = "EURZAR.carry.asia@M15", **extra: object) -> dict:
    return {"name": name, "symbol": "EURZAR", "family": "carry", "status": "LIVE",
            "risk_frac": 0.03, "certificate": cert, "sleeve_id": "sid", **extra}


@pytest.mark.parametrize("lane", ["main", "generic"])
def test_a_string_certificate_lane_is_refused_when_unreplicated(roster, lane) -> None:
    key = MAIN_KEY if lane == "main" else "qquant.AUDSGD.macro_conditional.asia"
    if lane == "main":
        CLOCKS[MAIN_KEY] = {"certificate": MAIN_CANON}
    got = roster([], [_lane_row(key, key)])[key]
    assert (got["status"], got["risk_frac"]) == ("STANDBY", 0.0)
    assert got["demote_reason"].startswith(ai.REFUSED_UNREPLICATED)
    assert [e[1]["door"] for e in EVENTS] == ["REPLICATION_REFUSED"]   # the ledger is corrected


def test_a_main_lane_clock_whose_canon_certificate_replicated_goes_live(
        roster, tmp_path, monkeypatch) -> None:
    """The book is keyed by CANON id, as replication_civilization writes it -- never by the clock
    key -- and the clock's own enrolling certificate is what the door looks up."""
    CLOCKS[MAIN_KEY] = {"certificate": MAIN_CANON}
    monkeypatch.setattr(ai, "REPLICATION_VERDICTS", _book(tmp_path, {MAIN_CANON: dict(REP)}))
    got = roster([], [_lane_row(MAIN_KEY, MAIN_KEY)])[MAIN_KEY]
    assert got["status"] == "LIVE" and got["canon_certificate"] == MAIN_CANON


def test_a_promoted_main_row_carrying_its_canon_certificate_needs_no_lookup(
        roster, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ai, "REPLICATION_VERDICTS", _book(tmp_path, {MAIN_CANON: dict(REP)}))
    row = _lane_row(MAIN_KEY, MAIN_KEY, canon_certificate=MAIN_CANON)
    assert roster([], [row])[MAIN_KEY]["status"] == "LIVE"


def test_a_generic_survivor_key_that_replicated_goes_live(roster, tmp_path, monkeypatch) -> None:
    key = "qquant.AUDSGD.macro_conditional.asia"
    monkeypatch.setattr(ai, "REPLICATION_VERDICTS", _book(tmp_path, {key: dict(REP)}))
    assert roster([], [_lane_row(key, key)])[key]["status"] == "LIVE"


def test_a_matured_no_spec_paper_clock_cannot_go_live(roster, tmp_path, monkeypatch) -> None:
    key = "CHFNOK.carry.asia#input_symbol=CHFNOK"
    canon = "external.CHFNOK@H1.carry.p=fedcba9876543210"
    CLOCKS[key] = {"certificate": canon}
    monkeypatch.setattr(ai, "REPLICATION_VERDICTS", _book(tmp_path, {canon: {
        "verdict": "UNMEASURED", "why": [f"{ai.NO_SPEC_MARK} for family 'carry'"]}}))
    assert roster([], [_lane_row(key, key)])[key]["status"] == "STANDBY"


def _scalp(name: str = "xau_m5_anti_breakout_overlap", cert: str = "forward_clock") -> dict:
    return _lane_row(cert, name, exec="scalp_market", symbol="XAUUSD")


def _policy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, doc: object) -> None:
    from mt5desk import live_policy
    p = tmp_path / "live_sleeve_policy.json"
    if doc is None:
        p.unlink(missing_ok=True)
    else:
        p.write_text(doc if isinstance(doc, str) else json.dumps(doc), "utf-8")
    monkeypatch.setattr(live_policy, "POLICY_FILE", p)


def test_the_scalp_lane_passes_only_while_its_live_ban_stands(roster, tmp_path,
                                                              monkeypatch) -> None:
    name = "xau_m5_anti_breakout_overlap"
    for cert in ("forward_clock", f"ten_gate:scalp.{name}"):
        _policy(tmp_path, monkeypatch, {"banned_execs": ["scalp_market"]})
        assert roster([], [_scalp(name, cert)])[name]["status"] == "LIVE"
        _policy(tmp_path, monkeypatch, None)            # no file: the coded ban stands
        assert roster([], [_scalp(name, cert)])[name]["status"] == "LIVE"
        _policy(tmp_path, monkeypatch, {"banned_execs": []})      # ban lifted: door applies
        got = roster([], [_scalp(name, cert)])[name]
        assert got["status"] == "STANDBY" and "no longer bans" in got["demote_reason"]
        _policy(tmp_path, monkeypatch, "{not json")     # unreadable: door applies
        assert roster([], [_scalp(name, cert)])[name]["status"] == "STANDBY"


def test_the_scalp_exemption_is_scoped_to_the_lanes_exact_form(roster, tmp_path,
                                                              monkeypatch) -> None:
    _policy(tmp_path, monkeypatch, {"banned_execs": ["scalp_market"]})
    # another lane's row cannot borrow a scalp marker ...
    for row in (_lane_row("forward_clock", "x"), _lane_row("ten_gate:scalp.x", "x")):
        assert roster([], [row])["x"]["status"] == "STANDBY"
    # ... nor a scalp row another sleeve's ten-gate name, nor a prefix lookalike
    for cert in ("ten_gate:scalp.other", "ten_gate:scalp.xau_m5_anti_breakout_overlap_v2"):
        got = roster([], [_scalp("xau_m5_anti_breakout_overlap", cert)])
        assert got["xau_m5_anti_breakout_overlap"]["status"] == "STANDBY"


def test_the_healer_and_the_promoter_read_the_certificate_the_same_way(tmp_path, monkeypatch
                                                                       ) -> None:
    spec = importlib.util.spec_from_file_location(
        "heal_silent_demotions_p", DESK / "scripts" / "heal_silent_demotions.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _policy(tmp_path, monkeypatch, {"banned_execs": ["scalp_market"]})
    gate = _gate(tmp_path, {})
    for row in (_principal_row(), _lane_row(MAIN_KEY, MAIN_KEY, canon_certificate=MAIN_CANON),
                _lane_row("forward_clock"), _scalp(), _lane_row({"cell": CERT}),
                {"name": "gold_asia_v4"}):
        assert bool(mod._replication_refusal(row, gate, set())) == bool(
            promoter._row_check(gate, "", set())(dict(row))), row


def test_a_replicated_certificate_goes_live(roster, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ai, "REPLICATION_VERDICTS",
                        _book(tmp_path, {CERT: dict(REP)}))
    assert roster([], [_principal_row()])["eurzar_carry_asia_p_8339edce23032d21"][
        "status"] == "LIVE"


def test_a_row_already_live_on_disk_is_never_demoted_by_the_door(roster) -> None:
    got = roster([_principal_row()], [_principal_row()])
    assert got["eurzar_carry_asia_p_8339edce23032d21"]["status"] == "LIVE"


def test_a_row_with_no_canon_certificate_is_not_asked(roster) -> None:
    got = roster([], [{"name": "gold_asia_v4", "symbol": "XAUUSD", "family": "gold",
                       "status": "LIVE", "risk_frac": 0.08}])
    assert got["gold_asia_v4"]["status"] == "LIVE"


def test_an_unreadable_verdict_book_refuses(roster, tmp_path, monkeypatch) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", "utf-8")
    monkeypatch.setattr(ai, "REPLICATION_VERDICTS", bad)
    got = roster([], [_principal_row()])["eurzar_carry_asia_p_8339edce23032d21"]
    assert got["status"] == "STANDBY"


def test_only_a_waiver_carrying_its_order_opens_the_door(roster, tmp_path) -> None:
    waiver = tmp_path / "waiver.json"
    waiver.write_text(json.dumps({"certificates": {CERT: ""}}), "utf-8")
    assert roster([], [_principal_row()])["eurzar_carry_asia_p_8339edce23032d21"][
        "status"] == "STANDBY"
    waiver.write_text(json.dumps({"certificates": {CERT: "zuck 2026-10-13 22:21Z book"}}),
                      "utf-8")
    assert roster([], [_principal_row()])["eurzar_carry_asia_p_8339edce23032d21"][
        "status"] == "LIVE"


# ------------------------------------------------------------------ the healer's restore path
@pytest.fixture()
def healer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    spec = importlib.util.spec_from_file_location(
        "heal_silent_demotions_r", DESK / "scripts" / "heal_silent_demotions.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sleeves = tmp_path / "sleeves.json"
    monkeypatch.setattr(mod, "SLEEVES", sleeves)
    monkeypatch.setattr(mod, "REPLICATION_WAIVER", tmp_path / "waiver.json")

    def run(rows: list[dict], book: dict[str, dict]) -> dict[str, str]:
        monkeypatch.setattr(ai, "REPLICATION_VERDICTS", _book(tmp_path, book))
        sleeves.write_text(json.dumps({"sleeves": rows}), encoding="utf-8")
        mod.heal(apply=True)
        return {r["name"]: r["status"] for r in
                json.loads(sleeves.read_text(encoding="utf-8"))["sleeves"]}
    return run


def test_the_healer_never_restores_an_unreplicated_certificate(healer) -> None:
    got = healer([{**_principal_row("STANDBY"), "risk_frac": 0.0}], {})
    assert got["eurzar_carry_asia_p_8339edce23032d21"] == "STANDBY"


def test_the_healer_refuses_a_string_certificate_and_does_not_make_it_sticky(healer) -> None:
    row = {**_lane_row(MAIN_KEY, MAIN_KEY, canon_certificate=MAIN_CANON), "status": "STANDBY",
           "risk_frac": 0.0}
    assert healer([dict(row)], {})[MAIN_KEY] == "STANDBY"
    assert healer([dict(row)], {MAIN_CANON: dict(REP)})[MAIN_KEY] == "LIVE"
    # an unstamped clock key finds no verdict here and is left for the promoter's restore
    bare = {**_lane_row(MAIN_KEY, MAIN_KEY), "status": "STANDBY", "risk_frac": 0.0}
    assert healer([dict(bare)], {MAIN_CANON: dict(REP)})[MAIN_KEY] == "STANDBY"


def test_the_healer_still_restores_a_replicated_silent_demotion(healer) -> None:
    got = healer([{**_principal_row("STANDBY"), "risk_frac": 0.0}],
                 {CERT: dict(REP)})
    assert got["eurzar_carry_asia_p_8339edce23032d21"] == "LIVE"


# ------------------------------------------------------------------ the canon dedupe
def test_aliases_in_the_seal_collapse_even_when_the_judge_did_not_republish(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seal = tmp_path / "canon.json"
    seal.write_text(json.dumps({"n": 2, "swept_at": "2026-10-12T00:00:00+00:00",
                                "survivors": {"external.B": {"shadow_spec": {}},
                                              "external.A": {"shadow_spec": {}}}}), "utf-8")
    monkeypatch.setattr(cp, "_clock_identity", lambda row: "CHFNOK.carry.asia")
    rec = cp.publish(tmp_path / "no_report.json", seal)
    doc = json.loads(seal.read_text("utf-8"))
    assert rec["status"] == "NO_REPORT" and rec["identity_aliases_collapsed"] == 1
    assert set(doc["survivors"]) == {"external.A"}
    assert doc["certificate_aliases"]["external.B"]["canonical_certificate"] == "external.A"
    assert doc["swept_at"] == "2026-10-12T00:00:00+00:00"      # no evidence was gathered


# ------------------------------------------------------------------ the committed waiver
def test_the_committed_waiver_holds_exactly_the_principals_three_book_sleeves() -> None:
    doc = json.loads((DESK / "data" / "REPLICATION_WAIVER.json").read_text("utf-8"))
    certs = doc["certificates"]
    assert set(certs) == {"external.USDNOK@M5.carry.p=ff35bb7c8427d66f",
                          "external.EURILS.formula.p=673857a649d3c271",
                          "external.EURZAR@M15.carry.p=8339edce23032d21"}
    assert all("cmsg_012XFUfE12Rvggnu86fDb8prHz6dDBptWXNU76e4gkCAJY" in v for v in certs.values())
    assert not any("gap_decay" in k for k in certs)       # zuck's stop is not waived


def test_a_mismatch_voids_the_waiver(roster, tmp_path, monkeypatch) -> None:
    (tmp_path / "waiver.json").write_text(
        json.dumps({"certificates": {CERT: "zuck 2026-10-13 22:21Z book"}}), "utf-8")
    monkeypatch.setattr(ai, "REPLICATION_VERDICTS",
                        _book(tmp_path, {CERT: {"verdict": "MISMATCH",
                                                "why": ["summed P&L disagrees in SIGN"]}}))
    got = roster([], [_principal_row()])["eurzar_carry_asia_p_8339edce23032d21"]
    assert got["status"] == "STANDBY" and "voids the waiver" in got["demote_reason"]


def test_the_healer_honours_the_waiver_and_its_mismatch_void(healer, tmp_path) -> None:
    (tmp_path / "waiver.json").write_text(
        json.dumps({"certificates": {CERT: "zuck 2026-10-13 22:21Z book"}}), "utf-8")
    row = {**_principal_row("STANDBY"), "risk_frac": 0.0}
    assert healer([dict(row)], {})["eurzar_carry_asia_p_8339edce23032d21"] == "LIVE"
    assert healer([dict(row)], {CERT: {"verdict": "MISMATCH"}})[
        "eurzar_carry_asia_p_8339edce23032d21"] == "STANDBY"


def test_a_waiver_survives_a_size_only_mismatch_and_falls_to_a_sign_one(tmp_path: Path) -> None:
    size = ["forward fills off by more than half: 4 vs 10"]
    gate = _gate(tmp_path, {CERT: {"verdict": "MISMATCH", "why": size}})
    assert gate.live_refusal(CERT, waived=True) is None
    assert gate.live_refusal(CERT) is not None
    for why in (["Sharpe SIGN disagrees: recorded +1.2, rebuilt -0.3"],
                ["the rebuild produced NO fill against 12 ledger trades"], []):
        assert "SIGN mismatch voids" in str(
            _gate(tmp_path, {CERT: {"verdict": "MISMATCH", "why": why}}).live_refusal(
                CERT, waived=True))


def test_a_replicated_verdict_under_an_old_metric_or_another_spec_is_refused(
        tmp_path: Path) -> None:
    old = _gate(tmp_path, {CERT: {"verdict": "REPLICATED", "sharpe_metric_version": "v1"}})
    assert "Sharpe metric v1" in str(old.live_refusal(CERT))
    assert "unstamped" in str(_gate(tmp_path, {CERT: {"verdict": "REPLICATED"}}).live_refusal(CERT))
    gate = _gate(tmp_path, {CERT: {**REP, "fp": "a"}})
    assert gate.live_refusal(CERT, fingerprint="a") is None
    assert ai.STALE_SPEC in str(gate.live_refusal(CERT, fingerprint="b"))


def test_an_unimportable_metric_version_refuses_replicated(tmp_path, monkeypatch) -> None:
    ai._current_metric_version.cache_clear()
    monkeypatch.setattr(ai, "_current_metric_version", lambda: "")
    assert "UNMEASURED" in str(_gate(tmp_path, {CERT: dict(REP)}).live_refusal(CERT))
