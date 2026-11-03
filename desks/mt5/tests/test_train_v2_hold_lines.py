"""Audit HOLD on 06cab1824 (gd-landing-train-v2): the missed-growth lines the cuts owe.

* MF1 -- the third-party FRED cut drops the VIX risk leg from three capital readers (macro_view's
  0.6-1.4 two-sided modifier, macro_state `risk`, leg_factors `d_vix`). The lost lean is billed:
  delta E[log W] UNMEASURED, the licensed substitute (US500_RV21 from own bars) named and NOT wired.
* SF -- run_cot_screen falls back to curl only on a pure transport error; bar_clock_probe bills its
  UNMEASURED futures (cross-venue) block; a fetcher's own `fetch_stats` carries its access holds.
"""
from __future__ import annotations

import io
import sys
import urllib.error
from pathlib import Path
from typing import Any, ClassVar

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK / "research"), str(DESK), str(ROOT), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import missed_growth as mg  # noqa: E402
import run_cot_screen as cot  # noqa: E402
from mt5desk import macro_view as mv  # noqa: E402

from libs.data import polite_fetch as pf  # noqa: E402
from libs.data import terms_fence as tf  # noqa: E402
from research import bar_clock_probe as bp  # noqa: E402


# ------------------------------------------------------------------------------ MF1 ----
def test_the_lost_vix_lean_is_billed_unmeasured_with_its_unwired_substitute() -> None:
    assert tf.fred_series_source("VIXCLS")                 # the cut is in force
    line = mv.risk_leg_missed_growth()
    assert line is not None
    assert line["delta_elogw"] == "UNMEASURED" and line["verdict"] == "UNMEASURED"
    assert line["modifier"] == "macro_view" and line["band"] == [mv.MULT_MIN, mv.MULT_MAX]
    assert "US500_RV21" in line["licensed_substitute"] and line["substitute_wired"] is False
    for word in ("risk-on", "haven", "XAU/XAG", "dollar-only", "macro_state", "d_vix"):
        assert word in line["effect"]
    import macro_desk
    assert macro_desk.RV_PROXY in line["licensed_substitute"]   # the name the tree publishes


def test_the_view_publishes_the_line_and_the_lean_is_not_rewired() -> None:
    v = mv.view()
    if v.get("status") == "UNMEASURED" and not v.get("lean"):
        assert v["missed_growth"] and v["missed_growth"][0]["source"] == "macro_view:VIXCLS"
        return
    assert "VIXCLS" not in v["ranks"] and "US500_RV21" not in v["ranks"]
    assert v["missed_growth"][0]["source"] == "macro_view:VIXCLS"
    for c in mv.RISK_ON + mv.HAVENS:
        assert c not in v["lean"]                          # absent, never re-leaned on the proxy


def test_missed_growth_carries_the_vix_lean_line_without_an_artifact() -> None:
    out = mg.vix_risk_lean_cut_line()
    assert out["verdict"] == mg.UNMEASURED and out["n_cut"] == 1
    assert out["lines"][0]["kind"] == "capital_modifier_cut"
    # billed ONCE: macro_view's own artifact is not also gathered under fred_copyrighted_cut
    assert all(organ != "macro_view" for organ, _p in mg.FRED_COPYRIGHTED_CUT_ARTIFACTS)


def test_missed_growth_run_publishes_the_vix_lean_cut(monkeypatch: pytest.MonkeyPatch,
                                                      tmp_path: Path) -> None:
    monkeypatch.setattr(mg, "LEDGER", tmp_path / "mg.jsonl")
    doc = mg.run(write=False)
    gl = doc["published_gate_lines"]
    got = gl["vix_risk_lean_cut"]
    assert got["verdict"] == mg.UNMEASURED and got["lines"]
    every = [x for v in gl.values() if isinstance(v, dict) for x in (v.get("lines") or [])
             if isinstance(x, dict)]
    assert sum(1 for x in every if x.get("source") == "macro_view:VIXCLS") == 1


# ------------------------------------------------------------------------- run_cot_screen --
@pytest.mark.parametrize("exc, curl", [
    (pf.PoliteRefused("https://x.example/a", "", "URLError: timed out"), True),
    (urllib.error.URLError("reset"), True),
    (TimeoutError("t"), True),
    (pf.PoliteRefused("https://x.example/a", "ROBOTS_DISALLOWED", "robots"), False),
    (pf.PoliteRefused("https://x.example/a", "METHOD_BLOCKED", "held"), False),
    (pf.PoliteRefused("https://x.example/a", "", "body longer than 9 bytes"), False),
    (tf.TermsFenced("yahoo", "https://x.example/a"), False),
    (ValueError("bug"), False),
])
def test_cot_curl_fallback_only_on_pure_transport(exc: BaseException, curl: bool,
                                                  monkeypatch: pytest.MonkeyPatch,
                                                  tmp_path: Path) -> None:
    ran: list[Any] = []

    def boom(*a: Any, **k: Any) -> Any:
        raise exc

    def fake_run(cmd: list[str], **k: Any) -> None:
        ran.append(cmd)
        Path(cmd[cmd.index("-o") + 1]).write_bytes(b"zip")
    monkeypatch.setattr(cot, "polite_urlopen", boom)
    monkeypatch.setattr(cot.subprocess, "run", fake_run)
    dest = tmp_path / "f.zip"
    if curl:
        assert cot._fetch("https://x.example/a", dest) == b"zip" and ran
    else:
        with pytest.raises(type(exc)):
            cot._fetch("https://x.example/a", dest)
        assert not ran


def test_a_held_site_refusal_carries_a_verdict(tmp_path: Path) -> None:
    acc = pf.HostAccess(tmp_path / "acc.json")
    acc.block("https://held.example/x", 403)

    def never(*a: Any, **k: Any) -> Any:
        raise AssertionError("a held site was contacted")
    with pytest.raises(pf.PoliteRefused) as ei:
        pf.polite_urlopen("https://held.example/data.zip", access=acc, opener=never)
    assert ei.value.verdict
    assert not cot.transport_only(ei.value)


# ---------------------------------------------------------------------------- bar clock --
def test_unmeasured_futures_block_is_billed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(bp, "release_opinion", lambda _r: {"per_season": {}})
    doc = bp.build(tmp_path, tape_clock=tmp_path / "no_tape")
    assert doc["second_opinions"]["cross_venue"]["status"] == bp.UNMEASURED
    (line,) = doc["missed_growth"]
    assert line["delta_elogw"] == "UNMEASURED" and line["substitute_wired"] is False
    assert line["source"] == "bar_clock_probe:cross_venue" and line["policy_row"] == "yahoo"
    assert bp.futures_missed_growth({"status": bp.MEASURED, "per_season": {}}) == []
    assert ("bar_clock_probe", mg.BASE / "reports" / "BAR_CLOCK.json") in mg.YAHOO_CUT_ARTIFACTS


# --------------------------------------------------------------- access holds per fetcher --
class _R403:
    def __call__(self, req: Any, timeout: float = 0, context: Any = None) -> Any:
        if req.full_url.endswith("/robots.txt"):
            return _Body(b"User-agent: *\nDisallow:\n")
        raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", None, io.BytesIO(b""))


class _Body(io.BytesIO):
    status = 200
    headers: ClassVar[dict[str, str]] = {}
    url = ""


def test_a_fetchers_stats_carry_its_access_hold_lines(tmp_path: Path) -> None:
    leg = "test_train_v2_hold_leg"
    pf.reset_stats(leg)
    acc = pf.HostAccess(tmp_path / "acc.json")
    r = pf.get("https://refuser.example/a", leg=leg, access=acc, opener=_R403(), retries=0,
               gate=None)
    assert r.status == 403 and r.verdict
    row = pf.stats(leg)
    assert row["n_access_holds"] == 1
    assert row["access_holds"][0]["kind"] == "access_hold"
    # a later refusal BY the hold (nothing sent) carries the same line
    pf.reset_stats(leg)
    r2 = pf.get("https://refuser.example/b", leg=leg, access=acc, opener=_R403(), retries=0,
                gate=None)
    assert r2.verdict and pf.stats(leg)["n_access_holds"] == 1
    pf.reset_stats(leg)


class _Keyed403:
    def __call__(self, req: Any, timeout: float = 0, context: Any = None) -> Any:
        if req.full_url.split("?")[0].endswith("/robots.txt"):
            return _Body(b"User-agent: *\nDisallow:\n")
        raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", None, io.BytesIO(b""))


def test_post_and_keyed_seams_carry_their_access_holds(tmp_path: Path,
                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pf, "GATE", None)
    acc = pf.HostAccess(tmp_path / "acc.json")
    leg = "test_train_v2_post_leg"
    pf.reset_stats(leg)
    with pytest.raises(pf.FetchRefused):
        pf.post("https://poster.example/q", b"{}", leg=leg, access=acc, opener=_Keyed403())
    assert pf.stats(leg)["n_access_holds"] == 1
    pf.reset_stats(leg)
    leg2 = "test_train_v2_keyed_leg"
    pf.reset_stats(leg2)
    with pytest.raises(urllib.error.HTTPError):
        pf.polite_urlopen("https://keyed.example/x?api_key=SECRET", leg=leg2, access=acc,
                          opener=_Keyed403())
    assert pf.stats(leg2)["n_access_holds"] == 1
    with pytest.raises(pf.PoliteRefused):      # now refused BY the hold, nothing sent
        pf.polite_urlopen("https://keyed.example/y?api_key=SECRET", leg=leg2, access=acc,
                          opener=_Keyed403())
    assert pf.stats(leg2)["n_access_holds"] == 1
    pf.reset_stats(leg2)
