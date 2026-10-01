"""Shared test isolation for desks/mt5/tests.

THE ORDER DOOR'S LEDGER NEVER LANDS IN THE REPO FROM A TEST. `mt5desk.order_door` appends one row
per money action to `desks/mt5/data/order_door_ledger.jsonl` -- the box's real evidence, a
state path the box commits. Every test that drives a lane through a fake venue (the E8 gold
windows, the prop executor, the gateway harnesses) goes through that door, so without this
each run would write fake orders into the file the desk audits its real ones from.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _order_door_writes_to_tmp(tmp_path_factory, monkeypatch):
    monkeypatch.setenv("MT5_ORDER_DOOR_DIR", str(tmp_path_factory.mktemp("order_door")))
    yield
