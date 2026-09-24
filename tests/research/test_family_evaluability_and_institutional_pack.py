"""TWO GAPS CLOSED THE SAME WAY: a name nothing can evaluate, and a region nothing could mint.

`regional_information` is minted by `pack_cells.emit_world` and is in neither family registry, so
6,336 cells can never be judged. `Global/institutional` held 99 grounds, 77 crawled, 384 verbatim
claims and ZERO cells because `pack_cells.country_pack` resolves a pack by importing
`countries.<country>.pack` and `research/countries/` had no `institutional` and no `global`.

Both are structural and neither is latency -- `PACK_CELLS.json` reached its ENTIRE backlog inside
budget on the pass that emitted nothing. These tests pin the fence that measures the first and
the pack that closes the second, and they pin the properties, never the live counts: a test that
asserted "6,336" would fail the hour the defect started being repaired.
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "scripts", ROOT / "desks" / "mt5", ROOT / "desks" / "mt5" / "research", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import check_family_evaluability as FE  # noqa: E402

# --------------------------------------------------------------- the pack that closes the region

@pytest.mark.parametrize("code", ["institutional", "global"])
def test_the_institutional_lane_resolves_to_a_pack_with_executable_instruments(code: str) -> None:
    """Rung 1 of the mapping ladder is a filesystem import. Before this pack it raised, returned
    `((), "UNMAPPED")`, and `emit_world` refused at pack_cells.py:739 with `targets == []`."""
    pack = importlib.import_module(f"countries.{code}.pack")
    instruments = tuple(getattr(pack, "EXECUTABLE_INSTRUMENTS", ()))
    assert instruments, f"countries/{code}/pack.py names no instrument; the grounds stay refused"
    assert str(getattr(pack, "REGION_COMMAND", "")).strip(), "no REGION_COMMAND to stamp cells"


@pytest.mark.parametrize("code", ["institutional", "global"])
def test_the_lane_crosswalks_to_the_region_that_was_empty(code: str) -> None:
    """A pack that mints under a REGION_COMMAND nothing crosswalks would move the cells from one
    empty bucket to another. `Global/institutional` is the bucket, and both spellings reach it."""
    from libs.research.attribution import REGION_COMMAND_TO_REGION

    pack = importlib.import_module(f"countries.{code}.pack")
    token = str(pack.REGION_COMMAND).strip().upper()          # country_pack uppercases it
    assert REGION_COMMAND_TO_REGION.get(token) == "Global/institutional", token


def test_country_pack_now_answers_for_both_spellings() -> None:
    """The real resolver, not a stand-in: `sources.country` carries BOTH strings for this lane
    (87 grounds `institutional`, 12 `global`), and a pack for only one leaves half refused."""
    from research.pack_cells import country_pack

    for code in ("institutional", "global", "INSTITUTIONAL", " Global "):
        instruments, region = country_pack(code)
        assert instruments, f"{code!r} still resolves to no instrument"
        assert region != "UNMAPPED", f"{code!r} still UNMAPPED"


def test_the_two_spellings_share_one_derivation() -> None:
    """One lane, one list. Two typed lists would drift the first time the broker reclassified a
    symbol, and then a ground's cells would depend on which spelling it happened to be filed
    under -- a split this desk has paid for before."""
    inst = importlib.import_module("countries.institutional.pack")
    glob = importlib.import_module("countries.global.pack")
    assert glob.EXECUTABLE_INSTRUMENTS == inst.EXECUTABLE_INSTRUMENTS


def test_the_pack_never_admits_a_symbol_the_two_lane_mandate_refuses() -> None:
    """Single-name equities are traded on news, never hunted for statistical hypotheses. The
    filter is applied at the SOURCE here, so no downstream lane has to catch it."""
    from research.universe_policy import may_hypothesise

    inst = importlib.import_module("countries.institutional.pack")
    bad = [s for s in inst.EXECUTABLE_INSTRUMENTS if not may_hypothesise(s)]
    assert bad == [], bad


def test_an_unreadable_registry_yields_no_instrument_rather_than_a_guess(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """A pack that invented a ticker when it could not measure one would put a fabricated subject
    under 384 real claims. Empty restores the honest refusal, with its reason already published."""
    inst = importlib.import_module("countries.institutional.pack")
    monkeypatch.setattr(inst, "UNIVERSE", ROOT / "does" / "not" / "exist.json")
    assert inst._quoted() == ()
    assert inst._executable() == ()


# ------------------------------------------------------- the fence that measures the unjudgeable

def test_a_minted_family_no_registry_implements_is_counted_as_unevaluable(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(FE, "registered", lambda: {"momentum", "carry"})
    monkeypatch.setattr(FE, "minted", lambda: ({"momentum": 10, "regional_information": 6336,
                                                "(close / open)": 3}, "test"))
    out = FE.survey()
    assert out["status"] == "MEASURED"
    assert out["unevaluable"] == {"regional_information": 6336}
    assert out["unevaluable_cells"] == 6336
    # An expression in the `family` column is a DIFFERENT defect and is never folded into the
    # number a reader acts on.
    assert out["expression_shaped_family_values"] == {"families": 1, "cells": 3}
    assert out["registered_never_minted"] == ["carry"]


def test_the_unjudgeable_population_may_shrink_and_may_not_grow(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The ratchet is the whole design. A fence that was simply red about 7,122 cells nobody can
    fix this hour would be ignored by the second day (L1.43); one that fails on GROWTH is
    actionable by the producer that grew it."""
    report = tmp_path / "FAMILY_EVALUABILITY.json"
    monkeypatch.setattr(FE, "REPORT", report)
    monkeypatch.setattr(FE, "registered", lambda: {"momentum"})

    monkeypatch.setattr(FE, "minted", lambda: ({"ghost": 100}, "test"))
    findings, doc = FE.check()
    assert findings == [] and doc["high_water_cells"] == 100 and doc["baseline_recorded"]
    report.write_text(json.dumps(doc), "utf-8")

    monkeypatch.setattr(FE, "minted", lambda: ({"ghost": 60}, "test"))
    findings, doc = FE.check()
    assert findings == [] and doc["high_water_cells"] == 60, doc
    report.write_text(json.dumps(doc), "utf-8")

    monkeypatch.setattr(FE, "minted", lambda: ({"ghost": 61}, "test"))
    findings, doc = FE.check()
    assert len(findings) == 1 and "GREW" in findings[0] and "'ghost'" in findings[0]


def test_an_unreadable_registry_is_unmeasured_and_never_a_pass(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Absence never resolves to a clean verdict (L1.28a / WS-005). The two false claims that this
    family "is not minted" were both written off a 0-byte database that read as empty."""
    def _boom() -> tuple[dict[str, int], str]:
        raise OSError("no such database")

    monkeypatch.setattr(FE, "minted", _boom)
    out = FE.survey()
    assert out["status"] == "UNMEASURED"
    assert "UNMEASURED is a verdict" in out["why"]
    assert "unevaluable_cells" not in out


def test_the_fence_is_wired_into_the_law_gate() -> None:
    """Built is not done: a check nothing runs is a claim the desk cannot cash (III.16, L1.49)."""
    src = (ROOT / "scripts" / "run_law_gate.py").read_text("utf-8")
    assert '("check_family_evaluability.py", ())' in src
