"""Pass-10 written replication specs: four families (carry is in the live SPEC_BOOK), RuleSpec shape, WRITTEN only, defaults equal
to the implementation's own signature, and nothing in the file is a verdict."""
from __future__ import annotations

import copy
import inspect
import json
import sys
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import replication_spec_entries as rse  # noqa: E402

#: Keys a written rule names that the implementation takes from elsewhere (not a kwarg).
SPEC_ONLY = {"macro_conditional": {"macro_series"}}


def _impl(row: dict[str, Any]) -> Any:
    import importlib
    mod = row["implementation"]["path"].removeprefix("desks/mt5/").removesuffix(".py")
    return getattr(importlib.import_module(mod.replace("/", ".")),
                   row["implementation"]["function"])


def test_the_file_loads_and_names_the_four_families() -> None:
    doc = rse.load()
    assert [r["family"] for r in doc["families"]] == list(rse.FAMILIES)
    assert all(r["status"] == "WRITTEN" for r in doc["families"])


@pytest.mark.parametrize("family", rse.FAMILIES)
def test_defaults_are_the_implementations_own(family: str) -> None:
    doc = rse.load()
    row = next(r for r in doc["families"] if r["family"] == family)
    sig = inspect.signature(_impl(row))
    for key, value in row["defaults"].items():
        if key in SPEC_ONLY.get(family, set()):
            continue
        assert key in sig.parameters, f"{family}: {key} is not a parameter of the family"
        assert sig.parameters[key].default == value, f"{family}.{key}"
    for key in row["native"]:
        assert key in sig.parameters or key in SPEC_ONLY.get(family, set()) or key == "symbol"


@pytest.mark.parametrize("family", rse.FAMILIES)
def test_every_default_is_named_in_the_written_text(family: str) -> None:
    doc = rse.load()
    text = rse.full_text(doc, family)
    row = next(r for r in doc["families"] if r["family"] == family)
    for key in row["defaults"]:
        assert key in text, f"{family}: the text never names {key}"
    assert text.endswith(doc["cell_contract"])


def test_rulespec_kwargs_fit_the_lanes_rulespec() -> None:
    import replication_civilization as rc
    fields = set(inspect.signature(rc.RuleSpec).parameters)
    kwargs = rse.as_rulespec_kwargs(rse.load())
    for fam, kw in kwargs.items():
        # The live RuleSpec predates external_cell/native/peers_key; those are the fields the
        # wiring change adds (APPLY.md). Everything else must already fit.
        older = {"external_cell", "native", "peers_key"}
        assert set(kw) - older <= fields, fam
        # A written family the live book has since taken up (formula, cross_asset_residual) is
        # not a second contract: on every default both name, the live value must equal the
        # written one (live may add fields of its own), and selector_params must match.
        live = rc.SPEC_BOOK.get(fam)
        if live is not None:
            for key, value in kw["defaults"].items():
                if key in live.defaults:
                    assert live.defaults[key] == value, f"{fam}.{key}: written != live"
            assert kw["selector_params"] == live.selector_params, \
                f"{fam}: written selector_params differ from live"


@pytest.mark.parametrize("status", ["REPLICATED", "MISMATCH", "UNMEASURED", ""])
def test_a_row_with_any_status_but_written_is_refused(status: str) -> None:
    doc = copy.deepcopy(rse.load())
    doc["families"][0]["status"] = status
    with pytest.raises(rse.SpecError):
        rse.validate(doc)


@pytest.mark.parametrize("word", ["replicated", "Mismatch", "REPLICATED"])
def test_the_verdict_word_ban_ignores_case(word: str) -> None:
    doc = copy.deepcopy(rse.load())
    doc["families"][1]["builder"]["where"] = f"{word} on the box"
    with pytest.raises(rse.SpecError):
        rse.validate(doc)


def test_a_live_rulespec_without_the_new_fields_is_refused_by_name() -> None:
    import dataclasses

    import replication_civilization as rc
    names = [f.name for f in dataclasses.fields(rc.RuleSpec)]
    if set(names) >= rse.NEEDS_FIELDS:
        pytest.skip("RuleSpec already carries the 7db43ab66 fields")
    with pytest.raises(rse.SpecError, match="7db43ab66"):
        rse.as_rulespec_kwargs(rse.load(), names)
    assert rse.as_rulespec_kwargs(rse.load(), [*names, *rse.NEEDS_FIELDS])


def test_a_verdict_word_anywhere_in_a_row_is_refused() -> None:
    doc = copy.deepcopy(rse.load())
    doc["families"][2]["builder"]["status"] = "REPLICATED"
    with pytest.raises(rse.SpecError):
        rse.validate(doc)


def test_a_missing_family_is_refused(tmp_path: Path) -> None:
    doc = copy.deepcopy(rse.load())
    doc["families"] = doc["families"][:3]
    p = tmp_path / "s.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(rse.SpecError):
        rse.load(p)


def test_drift_reports_a_moved_or_unreadable_file() -> None:
    doc = copy.deepcopy(rse.load())
    doc["families"][0]["implementation"]["git_blob_at_write"] = "0" * 40
    doc["families"][1]["implementation"]["path"] = "no/such/file.py"
    first, second = (r["family"] for r in doc["families"][:2])
    moved = rse.drift(doc)
    assert first in moved and "moved" in moved[first]
    assert moved[second].startswith("UNMEASURED")


def test_carry_is_left_to_the_live_spec_book_and_cannot_be_written_twice() -> None:
    import replication_civilization as rc
    assert "carry" in rc.SPEC_BOOK
    assert "carry" not in rse.FAMILIES
    doc = copy.deepcopy(rse.load())
    extra = copy.deepcopy(doc["families"][0])
    extra["family"] = "carry"
    doc["families"].append(extra)
    with pytest.raises(rse.SpecError, match="carry"):
        rse.validate(doc)
