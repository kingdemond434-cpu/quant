"""A family sleeve must be called with the parameters its certificate was earned on.

NO FOREX SLEEVE HAD EVER SENT AN ORDER, AND THIS IS WHY (measured 2026-09-14). All 53
`family_market` rows were LIVE, the lane was armed (`GENERIC_EXEC_ENABLED` present since
2026-09-11), the heat cap admitted 62 sleeves at 20.2%, and `order_intents.jsonl` held 59 intents
of which NOT ONE was on a non-gold symbol.

`_family_call_params` read `s["params"]`. Not one of the 53 registry rows has that key:

    audcad_discovered_asia_p_7c996ac8456c8919
      certified: {"feature": "ext_resid_EURGBP_z", "band": [0.9, 1.0], "horizon": 1, "side": -1}
      called:    {}
      signals over 400 bars: 0

`family_discovered` with no feature and no band returns an empty signal list forever. That lands
on stage `no_signal`, which the executor is DELIBERATELY silent about -- "the ordinary quiet
outcome" -- so 53 sleeves produced nothing every hour for days and the gateway log carried exactly
one FAMILY-EXEC line in its entire history. Silence that is indistinguishable from "no trade
today" is the defect class this desk keeps paying for.

After the fix, over the first eight sleeves: 7 recovered their params, 1 is genuinely empty, 0
refused, and 351 signals were produced where there had been 0.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

pytest.importorskip("pandas")
fi = pytest.importorskip("research.frontier_identity")
gw = pytest.importorskip("mt5desk.gateway")


@pytest.fixture()
def docket(tmp_path, monkeypatch):
    def _install(rows):
        d = tmp_path / "data" / "hypotheses"
        d.mkdir(parents=True, exist_ok=True)
        (d / "external_survivors.json").write_text(json.dumps(rows), encoding="utf-8")
        monkeypatch.setattr(gw, "BASE", tmp_path)
        monkeypatch.setattr(gw, "_DOCKET_CACHE", None)
    return _install


def _sleeve(cell: str) -> dict:
    return {"name": "x", "symbol": "AUDCAD", "family": "discovered",
            "certificate": {"cell": cell}}


def test_certified_params_are_recovered_from_the_docket(docket):
    params = {"feature": "ext_resid_EURGBP_z", "band": [0.9, 1.0], "horizon": 1, "side": -1}
    row = {"symbol": "AUDCAD", "family": "discovered", "params": params}
    cid = fi.cell_id({**row, "sym": "AUDCAD"})
    docket([row])
    got, why = gw._params_from_certificate(_sleeve(f"external.{cid}"))
    assert got == params, f"the certified parameters must be recovered ({why})"


def test_a_genuinely_empty_parameterisation_is_accepted(docket):
    """`p=44136fa355b3678a` really is the digest of {}. Empty is not the same as missing."""
    row = {"symbol": "AUDCHF", "family": "overnight_gap_decay", "params": {}}
    cid = fi.cell_id({**row, "sym": "AUDCHF"})
    docket([row])
    got, why = gw._params_from_certificate(
        {"name": "y", "symbol": "AUDCHF", "family": "overnight_gap_decay",
         "certificate": {"cell": f"external.{cid}"}})
    assert got == {}, why


def test_a_cell_absent_from_the_docket_FAILS_CLOSED(docket):
    """The original defect was calling a parameterised family with {}. Never re-introduce it."""
    docket([{"symbol": "OTHER", "family": "discovered", "params": {"feature": "x"}}])
    got, why = gw._params_from_certificate(_sleeve("external.AUDCAD.discovered.p=deadbeefdeadbeef"))
    assert got is None, "an unjoinable cell must refuse, not trade unparameterised"
    assert "cannot be reconstructed" in why


def test_a_sleeve_with_no_certificate_cell_refuses(docket):
    docket([])
    got, why = gw._params_from_certificate({"name": "z", "symbol": "AUDCAD",
                                            "family": "discovered"})
    assert got is None
    assert "names no cell" in why


def test_an_absent_docket_refuses_rather_than_defaulting(tmp_path, monkeypatch):
    monkeypatch.setattr(gw, "BASE", tmp_path)
    monkeypatch.setattr(gw, "_DOCKET_CACHE", None)
    got, why = gw._params_from_certificate(_sleeve("external.AUDCAD.discovered.p=abc123abc123abcd"))
    assert got is None
    assert "no docket" in why


def test_the_roster_carries_the_certificate_to_the_executor():
    """The runtime sleeve dict is BUILT, not passed through -- so anything unnamed is invisible.

    `roster()` constructs a fresh dict for every `family_market` row. It named nine keys and
    `certificate` was not among them, so the cell id the parameters are recovered and verified
    against never reached `_family_call_params`. Every downstream fix is inert without this line:
    measured 2026-09-14, the first pass after recovery landed still logged "certificate names no
    cell" for all 53 sleeves, because the registry row had one and the runtime dict did not.
    """
    from mt5desk.decision_core import roster

    row = {"name": "audcad_discovered_asia_p_7c996ac8456c8919", "symbol": "AUDCAD",
           "family": "discovered", "selector": "asia", "exec": "family_market",
           "status": "LIVE", "risk_frac": 0.002,
           "certificate": {"cell": "external.AUDCAD.discovered.p=7c996ac8456c8919"}}
    sleeves, _ = roster({}, [row])
    fam = [s for s in sleeves if s.get("exec") == "family_market"]
    assert len(fam) == 1
    cert = fam[0].get("certificate")
    assert isinstance(cert, dict), "the certificate must reach the executor"
    assert cert.get("cell") == "external.AUDCAD.discovered.p=7c996ac8456c8919"
