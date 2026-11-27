"""Exit-policy live parity (Audit HOLD MF1 on #628, 2026-11-24).

The live gateway executes the stop, the target, the ttl and the trail (`trail_k`) only. A
`session_exit_overlay` survivor certified on a bank_frac partial, a reversal exit or a
liquidity exit would go live as a ratchet-only lookalike, so `live_policy` refuses those
policies live capital BY NAME, with the reason, and the trials stay research. Fenced here:
  * every engine-only policy is refused, and the reason names the policy and the missing mechanic;
  * ratchet, time_4 and time_8 still enrol, through `refuse`, `admit` and the promoter's own
    `_apply_live_policy` (the door `save_sleeves` runs on every write);
  * the mechanics table covers every registered policy, and an unknown policy fails closed;
  * the E8 book and the missed-growth ledger see the same refusal.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import live_policy as LP  # noqa: E402
from mt5desk.families import SESSION_EXIT_POLICIES  # noqa: E402

ENGINE_ONLY = ("partial_1r", "partial_2r", "regime", "reversal", "liquidity")
LIVE_OK = ("ratchet", "time_4", "time_8")
#: An open policy (gold is in the live universe by default, so nothing but the exit can refuse).
POL = LP.Policy()


def _row(policy: str | None, name: str = "") -> dict:
    params = {"timeframe": "H1"}
    if policy is not None:
        params["exit_policy"] = policy
    return {"name": name or f"external.XAUUSD.session_exit_overlay.{policy}",
            "symbol": "XAUUSD", "family": "session_exit_overlay", "selector": "asia",
            "exec": "family_market", "params": params, "status": "LIVE", "risk_frac": 0.004}


@pytest.mark.parametrize("policy", ENGINE_ONLY)
def test_an_engine_only_exit_is_refused_live_with_its_reason(policy: str) -> None:
    why = LP.refuse(_row(policy), POL)
    assert why is not None
    assert why.startswith(LP.EXIT_PARITY_TAG)
    assert repr(policy) in why
    missing = sorted(LP.EXIT_POLICY_MECHANICS[policy] - LP.LIVE_EXIT_MECHANICS)
    assert missing and all(m in why for m in missing)
    assert "lookalike" in why
    keep, refused = LP.admit([_row(policy)], POL)
    assert keep == [] and refused[0][1] == why


def test_every_engine_only_policy_is_refused_by_name() -> None:
    for policy in ENGINE_ONLY:
        assert LP.exit_parity_refusal({"params": {"exit_policy": policy}})


@pytest.mark.parametrize("policy", LIVE_OK)
def test_stop_target_ttl_trail_policies_still_enrol(policy: str) -> None:
    assert LP.exit_parity_refusal(_row(policy)) is None
    assert LP.refuse(_row(policy), POL) is None
    keep, refused = LP.admit([_row(policy)], POL)
    assert refused == [] and keep[0]["name"] == _row(policy)["name"]


def test_live_ok_policies_need_only_live_mechanics() -> None:
    for policy in LIVE_OK:
        assert LP.EXIT_POLICY_MECHANICS[policy] <= LP.LIVE_EXIT_MECHANICS
    assert frozenset({"stop", "target", "ttl", "trail_k"}) == LP.LIVE_EXIT_MECHANICS


def test_the_table_covers_every_registered_policy_and_splits_them_as_audited() -> None:
    assert set(SESSION_EXIT_POLICIES) == set(LP.EXIT_POLICY_MECHANICS)
    refused = {p for p in SESSION_EXIT_POLICIES if LP.exit_parity_refusal(_row(p))}
    assert refused == set(ENGINE_ONLY)
    assert set(SESSION_EXIT_POLICIES) - refused == set(LIVE_OK)


def test_an_unknown_exit_policy_fails_closed_and_a_row_without_one_is_untouched() -> None:
    why = LP.refuse(_row("scale_out_thirds"), POL)
    assert why and why.startswith(LP.EXIT_PARITY_TAG) and "UNMEASURED" in why
    assert LP.exit_parity_refusal(_row(None)) is None
    assert LP.refuse(_row(None), POL) is None


def test_the_policy_is_found_wherever_a_certificate_spec_nests_it() -> None:
    survivor = {"shadow_spec": {"symbol": "XAUUSD", "family": "session_exit_overlay",
                                "params": {"exit_policy": "Partial_1R"}}}
    assert LP.exit_policy_of(survivor) == "partial_1r"
    assert LP.exit_parity_refusal(survivor)
    e8_row = {"key": "k", "symbol": "XAUUSD", "family": "session_exit_overlay",
              "params": {"params": {"exit_policy": "reversal"}}}
    assert LP.exit_parity_refusal(e8_row)


def test_the_promoter_door_retires_an_engine_only_row_and_keeps_a_ratchet(monkeypatch) -> None:
    promoter = pytest.importorskip("promoter")
    monkeypatch.setattr(LP, "policy", lambda path=None: POL)
    rows = [_row("partial_2r"), _row("time_8")]
    assert promoter._apply_live_policy(rows) == 1
    assert rows[0]["status"] == "RETIRED" and rows[0]["risk_frac"] == 0.0
    assert rows[0]["retired_by"] == "live_policy"
    assert rows[0]["retire_reason"].startswith(LP.EXIT_PARITY_TAG)
    assert rows[1]["status"] == "LIVE" and rows[1]["risk_frac"] == 0.004


def test_the_missed_growth_line_is_two_sided_and_unmeasured(tmp_path, monkeypatch) -> None:
    from research import missed_growth as MG
    surv = tmp_path / "UNIVERSAL_SURVIVORS.json"
    surv.write_text(json.dumps({"survivors": {
        "external.XAUUSD.session_exit_overlay.p=a": {
            "shadow_spec": {"symbol": "XAUUSD", "family": "session_exit_overlay",
                            "exit_policy": "liquidity"},
            "gates": {"expected_value": {"ev": 0.12}}},
        "external.XAUUSD.session_exit_overlay.p=b": {
            "shadow_spec": {"symbol": "XAUUSD", "family": "session_exit_overlay",
                            "exit_policy": "ratchet"}}}}), "utf-8")
    sleeves = tmp_path / "sleeves.json"
    sleeves.write_text(json.dumps({"sleeves": []}), "utf-8")
    monkeypatch.setattr(MG, "SURVIVORS", surv)
    monkeypatch.setattr(MG, "SLEEVES", sleeves)
    line = MG.exit_parity_line({})
    assert line["verdict"] == MG.UNMEASURED and line["n"] == 1
    assert list(line["held"]) == ["external.XAUUSD.session_exit_overlay.p=a"]
    assert line["cost"]["value_logw_per_day"] is None
    assert line["saving"]["verdict"] == MG.UNMEASURED
    priced = MG.exit_parity_line({"admission": {"candidates": {
        "external.XAUUSD.session_exit_overlay.p=a": {"delta_elogw_per_day": 0.0002}}}})
    assert priced["cost"]["value_logw_per_day"] == pytest.approx(-0.0002)
    surv.write_text(json.dumps({"survivors": {}}), "utf-8")
    assert MG.exit_parity_line({})["verdict"] == MG.NOT_BINDING
    surv.unlink()
    assert MG.exit_parity_line({})["verdict"] == MG.UNMEASURED


def test_the_e8_book_names_the_refusal(monkeypatch, tmp_path) -> None:
    e8 = pytest.importorskip("prop.e8_book")
    import types
    book = tmp_path / "CERT_BOOK_LIVE.json"
    book.write_text(json.dumps({"excluded": {}}), "utf-8")
    monkeypatch.setattr(e8, "CERT_BOOK", book)
    fake_ai = types.SimpleNamespace(
        REPLICATED="REPLICATED",
        IntegrityGate=types.SimpleNamespace(load=lambda: types.SimpleNamespace(
            alarm={}, replication=lambda k, f: ("REPLICATED", ""))))
    monkeypatch.setitem(sys.modules, "admission_integrity", fake_ai)
    monkeypatch.setitem(sys.modules, "kelly_survival",
                        types.SimpleNamespace(terms_fenced_cells=lambda: (set(), "test")))
    import mt5desk.kelly_sizing as ks
    monkeypatch.setattr(ks, "load_cert_book", lambda path, lane: {
        "XAUUSD_session_exit_overlay_asia": 0.0015})
    rows = [dict(_row(p), key=f"k.{p}") for p in ("reversal", "time_4")]
    accepted, blocked = e8.live_admissible(rows)
    assert [r["key"] for r in accepted] == ["k.time_4"]
    assert blocked[0]["certificate"] == "k.reversal"
    assert blocked[0]["why"].startswith(LP.EXIT_PARITY_TAG)
