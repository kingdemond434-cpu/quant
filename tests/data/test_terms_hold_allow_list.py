"""The terms gate is an allow-list that fails closed (audit #211, 2026-10-07)."""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

from libs.data import terms_hold as th

QUOTED = {"status": "CLEARED", "by": "terms review", "terms_url": "https://example.test/terms",
          "terms_quote": "you may use the data for any purpose"}


@pytest.fixture
def none(tmp_path: Path) -> Path:
    return tmp_path / "absent.json"


@pytest.mark.parametrize("sid", ["mt5:bars", "desk:sensor_ledger", "forced_flow_calendar"])
def test_evidenced_sources_are_admitted(sid: str, none: Path) -> None:
    assert th.gauntlet_terms(sid, none)[0] is True


@pytest.mark.parametrize("sid", ["fred:DFII10", "fred:T10YIE", "alfred:PAYEMS", "fred:h15",
                                 "fred:SP500", "fred:NIKKEI225", "alfred:WILL5000IND"])
def test_fred_is_held_from_fitted_models(sid: str, none: Path) -> None:
    """Ruling on prohibition (j), 2026-10-07: no FRED id is an input to a fitted model."""
    ok, why = th.gauntlet_terms(sid, none)
    assert ok is False and why.startswith("HELD_TERMS")


def test_a_third_party_clearance_never_lifts_the_fred_hold(tmp_path: Path) -> None:
    clear = tmp_path / "c.json"
    clear.write_text(json.dumps({"cboe": QUOTED}), "utf-8")
    assert th.gauntlet_terms("fred:VIXCLS", clear) == (False, f"HELD_TERMS: {th.FRED_FITTED_HOLD}")
    clear.write_text(json.dumps({"fred": QUOTED}), "utf-8")
    assert th.gauntlet_terms("fred:DFII10", clear)[0] is True
    assert th.gauntlet_terms("fred:VIXCLS", clear)[0] is False       # CBOE still held
    assert th.gauntlet_terms("fred:SP500", clear)[0] is False        # the index owner still held
    clear.write_text(json.dumps({"fred": QUOTED, "cboe": QUOTED}), "utf-8")
    assert th.gauntlet_terms("fred:VIXCLS", clear)[0] is True


@pytest.mark.parametrize("sid", ["DGS10", "DFII10", "T10YIE", "WCESTUS1", "CPIAUCSL", "PCEPI",
                                 "DTWEXBGS", "M2SL", "VIXCLS", "SP500", "SOMETHINGNEW", ""])
def test_no_fred_series_is_fetched_without_a_recorded_label(sid: str, none: Path) -> None:
    """Coordinator 2026-10-07: FRED's labels are VERBATIM_PENDING, so the register is empty and
    every series is held for display too."""
    ok, why = th.fred_display_terms(sid, none, labels=none)
    assert ok is False and why.startswith("HELD_TERMS")


def test_the_label_register_admits_only_a_recorded_admitted_label(tmp_path: Path,
                                                                    none: Path) -> None:
    labels = tmp_path / "labels.json"
    row = {"url": "https://fred.stlouisfed.org/series/DGS10", "captured_at": "2026-10-08"}
    labels.write_text(json.dumps({
        "DGS10": {**row, "label": "Public Domain: Citation Requested"},
        "DFII10": {"label": "Public Domain: Citation Requested"},          # no url / capture
        "M2SL": {**row, "label": "Copyrighted: Pre-approval Required"},    # not admitted
        "VIXCLS": {**row, "label": "Copyrighted: Citation Required"},
        "SP500": {**row, "label": "Copyrighted: Citation Required"}}), "utf-8")
    assert th.fred_display_terms("DGS10", none, labels)[0] is True
    assert th.fred_display_terms("DFII10", none, labels)[0] is False
    assert th.fred_display_terms("M2SL", none, labels)[0] is False
    assert th.fred_display_terms("T10YIE", none, labels)[0] is False
    # a label never lifts a third party's own copyright
    assert th.fred_display_terms("VIXCLS", none, labels)[0] is False
    assert th.fred_display_terms("SP500", none, labels)[0] is False
    clear = tmp_path / "c.json"
    clear.write_text(json.dumps({"cboe": QUOTED}), "utf-8")
    assert th.fred_display_terms("VIXCLS", clear, labels)[0] is True
    # and a label is never a licence for a fitted model
    assert th.gauntlet_terms("fred:DGS10", none)[0] is False


def test_fred_is_cited_never_quoted() -> None:
    assert th.FRED_TERMS_CITATION["verbatim"] == "VERBATIM_PENDING"
    assert "terms_quote" not in th.FRED_TERMS_CITATION
    assert not th.FRED_LABELS.exists() or json.loads(th.FRED_LABELS.read_text("utf-8")) == {}


def test_a_pair_passes_only_when_every_part_does(none: Path) -> None:
    assert th.gauntlet_terms("mt5:bars+desk:sensor_ledger", none)[0] is True
    assert th.gauntlet_terms("ff_calendar_vintage+mt5:bars", none)[0] is False
    assert th.gauntlet_terms("mt5:bars+mystery", none)[0] is False


def test_only_a_quoted_clearance_admits(tmp_path: Path) -> None:
    clear = tmp_path / "c.json"
    clear.write_text(json.dumps({"cboe": {"status": "CLEARED", "by": "x"},
                                 "mystery": {"status": "CLEARED", "terms_url": "u"}}), "utf-8")
    assert th.gauntlet_terms("fred:VIXCLS", clear)[0] is False
    assert th.gauntlet_terms("mystery", clear)[0] is False
    clear.write_text(json.dumps({"cboe": QUOTED, "mystery": QUOTED, "fred": QUOTED}), "utf-8")
    assert th.gauntlet_terms("fred:VIXCLS", clear)[0] is True
    assert th.gauntlet_terms("mystery", clear)[0] is True
    # a source under two holds needs both cleared
    assert th.gauntlet_terms("yahoo:cboe_indices", clear)[0] is False


def test_a_fence_that_fails_holds_everything(none: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    broken = types.ModuleType("libs.data.terms_fence")

    def boom(_sid: str) -> str:
        raise RuntimeError("fence down")

    broken.fenced_source = boom  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "libs.data.terms_fence", broken)
    ok, why = th.gauntlet_terms("mt5:bars", none)
    assert ok is False and "fence failed" in why
    blocking = types.ModuleType("libs.data.terms_fence")
    blocking.fenced_source = lambda sid: "banned platform"  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "libs.data.terms_fence", blocking)
    assert th.gauntlet_terms("mt5:bars", none) == (False, "terms fence: banned platform")


def test_acquisition_gate_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    desk = Path(__file__).resolve().parents[2] / "desks" / "mt5"
    for p in (str(desk), str(desk / "research")):
        if p not in sys.path:
            sys.path.insert(0, p)
    import source_evig as se  # type: ignore[import-not-found]
    assert "terms UNMEASURED" in str(se.acquisition_gate({"id": "unread", "access": "public"}))
    assert se.acquisition_gate({"id": "ok", "access": "public", "machine_use_allowed": True}) \
        is None
    assert se.acquisition_gate({"id": "q", "terms_url": "u", "terms_quote": "use freely"}) is None
    broken = types.ModuleType("libs.data.terms_fence")
    broken.fenced_source = lambda sid: (_ for _ in ()).throw(OSError("x"))  # type: ignore
    monkeypatch.setitem(sys.modules, "libs.data.terms_fence", broken)
    assert "fence failed" in str(se.acquisition_gate({"id": "ok", "machine_use_allowed": True}))
