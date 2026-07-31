"""R0152 -- ledger ids allocate past the highest KNOWN id, never by row count.

Count-based allocation minted the same id on two boxes three times on 2026-07-31; these pin
the two properties that end that class: monotonic-past-max locally, and no re-minting of an
id that a renumber has already retired. Origin consultation is forced offline here so the
test is deterministic in CI and on a fresh clone.
"""
from __future__ import annotations

import subprocess

import scripts.recommendations as rec


def _offline(monkeypatch):
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("offline")))


def test_allocates_past_local_max_not_count(monkeypatch):
    _offline(monkeypatch)
    # 2 rows but max id R0152: count-based would mint R0003 and collide on merge
    nid = rec._next_id({"recommendations": [{"id": "R0152"}, {"id": "R0009"}]})
    assert nid == "R0153"


def test_never_remint_a_renumber_retired_id(monkeypatch):
    _offline(monkeypatch)
    nid = rec._next_id({"recommendations": [{"id": "R0150"}]})
    assert nid == "R0151"


def test_empty_ledger_starts_at_one(monkeypatch):
    _offline(monkeypatch)
    assert rec._next_id({"recommendations": []}) == "R0001"
