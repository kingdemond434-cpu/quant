"""The edge queue: four preregistered mechanisms, each a complete preregistration with falsifiers
and a named payer, flattened to docket records with NO promotion authority; an incomplete spec
names every missing field and may not consume a trial."""
from __future__ import annotations

import dataclasses

from libs.research import edge_queue as eq


def test_the_live_queue_is_four_complete_preregistrations() -> None:
    assert len(eq.QUEUE) == 4 and len({s.id for s in eq.QUEUE}) == 4
    assert eq.validate_queue() == []
    for s in eq.QUEUE:
        assert s.is_complete() == (True, "complete")
        assert s.payer and s.constraint and len(s.falsifiers) >= 4


def test_an_incomplete_spec_names_every_missing_field() -> None:
    bad = dataclasses.replace(eq.FX_FIXING_REVERSAL, payer="", source="", falsifiers=(),
                              observables=())
    ok, why = bad.is_complete()
    assert ok is False
    for field in ("payer", "source", "falsifiers", "observables"):
        assert field in why
    assert "must not consume a trial" in why
    assert "claim" not in why.split("missing", 1)[1]


def test_validate_queue_reports_only_the_broken_spec(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    broken = dataclasses.replace(eq.GOLD_SESSION_HANDOFF, distinguishing_test="")
    monkeypatch.setattr(eq, "QUEUE", (eq.HEDGING_DEMAND_CLOSE_FLOW, broken))
    (row,) = eq.validate_queue()
    assert row[0] == broken.id and "distinguishing_test" in row[1]


def test_records_flatten_the_coordinate_and_carry_no_authority() -> None:
    rows = eq.as_records()
    assert [r["hypothesis_id"] for r in rows] == [s.id for s in eq.QUEUE]
    fx = rows[1]
    assert fx["coordinate"] == "benchmark_flow|london|magnitude|reversal|15m"
    assert fx["region"] == "benchmark_flow|reversal"
    assert fx["universe"][0] == "USDJPY" and isinstance(fx["falsifiers"], list)
    assert "month-end" in " ".join(fx["falsifiers"])
    assert rows[0]["secondary"] and rows[1]["notes"] and rows[3]["secondary"] == ""
    assert all(r["promotion_authority"] is False for r in rows)
