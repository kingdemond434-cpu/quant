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
import shadow_forward as sf  # noqa: E402

from research import canon_publication as cp  # noqa: E402

CERT = "external.EURZAR.carry.p=8339edce23032d21"
SPEC_BOOK = ["overnight_gap_decay", "session_range_breakout"]


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
    gate = _gate(tmp_path, {CERT: {"verdict": "REPLICATED"},
                            "external.U": {"verdict": "UNMEASURED", "why": ["no bars"]},
                            "external.M": {"verdict": "MISMATCH"}})
    assert gate.live_refusal(CERT) is None
    for cert in ("external.U", "external.M", "external.never"):
        assert str(gate.live_refusal(cert)).startswith(ai.REFUSED_UNREPLICATED), cert


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


def test_a_reconcile_restore_is_refused_when_unreplicated(roster, monkeypatch) -> None:
    monkeypatch.setattr(promoter, "capital_verdict", lambda *a, **k: {
        "status": "LIVE", "risk_frac": 0.03, "streak": 2, "why": "funded"})
    monkeypatch.setattr(promoter, "note_door", lambda *a, **k: None)
    row = {**_principal_row("STANDBY"), "demote_reason": "the optimiser gives it 0% heat"}
    on_disk = dict(row)
    rows = [row]
    promoter.reconcile_capital(rows, {"fresh": True, "at": "2026-10-14T00:00:00+00:00",
                                      "admission_at": "2026-10-14T01:00:00+00:00"})
    assert rows[0]["status"] == "LIVE"                       # the restore happened in memory
    got = roster([on_disk], rows)["eurzar_carry_asia_p_8339edce23032d21"]
    assert got["status"] == "STANDBY"                          # and never reached the file
    assert got["demote_reason"].startswith(ai.REFUSED_UNREPLICATED)


def test_a_replicated_certificate_goes_live(roster, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ai, "REPLICATION_VERDICTS",
                        _book(tmp_path, {CERT: {"verdict": "REPLICATED"}}))
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


def test_the_healer_still_restores_a_replicated_silent_demotion(healer) -> None:
    got = healer([{**_principal_row("STANDBY"), "risk_frac": 0.0}],
                 {CERT: {"verdict": "REPLICATED"}})
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
                        _book(tmp_path, {CERT: {"verdict": "MISMATCH", "why": ["fills"]}}))
    got = roster([], [_principal_row()])["eurzar_carry_asia_p_8339edce23032d21"]
    assert got["status"] == "STANDBY" and "voids any waiver" in got["demote_reason"]


def test_the_healer_honours_the_waiver_and_its_mismatch_void(healer, tmp_path) -> None:
    (tmp_path / "waiver.json").write_text(
        json.dumps({"certificates": {CERT: "zuck 2026-10-13 22:21Z book"}}), "utf-8")
    row = {**_principal_row("STANDBY"), "risk_frac": 0.0}
    assert healer([dict(row)], {})["eurzar_carry_asia_p_8339edce23032d21"] == "LIVE"
    assert healer([dict(row)], {CERT: {"verdict": "MISMATCH"}})[
        "eurzar_carry_asia_p_8339edce23032d21"] == "STANDBY"
