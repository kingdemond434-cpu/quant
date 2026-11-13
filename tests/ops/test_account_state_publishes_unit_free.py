"""THE PUBLISHED account_state.json CARRIES NO CURRENCY AMOUNT (Auditor ruling, 2026-11-11).

`ops/publish_account_state.py` writes balance, equity, margin and today's P&L on the box, and
the sync published that file to a PUBLIC repository. The publisher's scrub
(`libs/ops/account_withhold.scrub_for_publish`) now replaces it with a unit-free view: the
descriptive keys in `ACCOUNT_PUBLIC_KEYS` plus percentages. These tests pin the allowed keys,
the arithmetic, the writer's serialisation, the tracked copy, and that every key the writer
emits is either published or withheld by name. All amounts below are placeholders.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ops import account_withhold as aw  # noqa: E402

REL = "desks/mt5/data/account_state.json"

PINNED_PUBLIC = {"updated_at", "source", "venue", "server", "login_withheld", "currency",
                 "open_positions", "margin_level", "positions_file"}
PINNED_DERIVED = {"today_pnl_pct", "today_closed_pnl_pct", "today_floating_pnl_pct",
                  "today_swap_pct", "margin_used_pct", "margin_free_pct"}
#: Every amount the writer records; none may appear in the published view.
AMOUNTS = {"balance", "equity", "margin", "margin_free", "today_pnl", "today_closed_pnl",
           "today_floating_pnl", "swap", "today_swap"}


def _record() -> dict[str, Any]:
    return {"updated_at": "2026-11-11T16:00:00+00:00", "source": "ops/publish_account_state.py",
            "venue": "V", "server": "S", "login_withheld": True, "currency": "USD",
            "balance": 1010.0, "equity": 990.0, "margin_free": 891.0, "today_pnl": -10.0,
            "today_closed_pnl": -4.0, "today_floating_pnl": -6.0, "open_positions": 1,
            "margin": 99.0, "margin_level": 1000.0, "swap": -0.5, "today_swap": -0.25,
            "positions_file": "account_positions.json"}


def test_the_published_keys_are_pinned() -> None:
    assert set(aw.ACCOUNT_PUBLIC_KEYS) == PINNED_PUBLIC
    assert set(aw.ACCOUNT_DERIVED) == PINNED_DERIVED
    assert not (PINNED_PUBLIC | PINNED_DERIVED) & AMOUNTS


def test_amounts_become_percentages_and_never_leave() -> None:
    view, dropped = aw.unit_free_account(_record())
    assert set(dropped) == AMOUNTS
    assert set(view) == PINNED_PUBLIC | PINNED_DERIVED
    assert view["today_pnl_pct"] == round(100 * -10.0 / 1000.0, 4)        # opening equity 1000
    assert view["today_closed_pnl_pct"] == -0.4 and view["today_floating_pnl_pct"] == -0.6
    assert view["margin_used_pct"] == round(100 * 99.0 / 990.0, 4)
    assert view["margin_free_pct"] == round(100 * 891.0 / 990.0, 4)
    text = json.dumps(view)
    for amount in ("1010.0", "990.0", "891.0", "-10.0", "99.0"):
        assert amount not in text


def test_an_unreadable_basis_publishes_null_never_an_amount() -> None:
    rec = _record()
    rec["equity"] = None
    view, _ = aw.unit_free_account(rec)
    assert view["margin_used_pct"] is None and view["today_pnl_pct"] is None
    rec = {**_record(), "equity": 0.0, "today_pnl": 0.0}
    assert aw.unit_free_account(rec)[0]["margin_used_pct"] is None


def test_the_publisher_reserialises_like_the_writer_and_a_view_maps_to_itself() -> None:
    raw = json.dumps(_record(), indent=1).encode("utf-8")
    new, dropped = aw.scrub_for_publish(REL, raw)
    assert new is not None and set(dropped) == AMOUNTS
    assert new == json.dumps(aw.unit_free_account(_record())[0], indent=1).encode("utf-8")
    assert aw.scrub_for_publish(REL, new) == (None, [])
    assert aw.scrub_for_publish(REL, b"not json") == (None, [])
    assert aw.scrub_for_publish(REL, b"[1]") == (None, [])


def test_the_tracked_copy_publishes_without_an_amount() -> None:
    # The box republishes this file every fifteen minutes and its copy wins any merge, so the
    # tracked bytes may be the raw record until the box runs this publisher: judge what the
    # publisher would make of them, which is what reaches the repository.
    raw = (ROOT / REL).read_bytes()
    new, _ = aw.scrub_for_publish(REL, raw)
    doc = json.loads(new if new is not None else raw)
    assert set(doc) <= PINNED_PUBLIC | PINNED_DERIVED
    assert not set(doc) & AMOUNTS


def test_every_key_the_writer_records_is_classified() -> None:
    src = (ROOT / "ops/publish_account_state.py").read_text("utf-8")
    body = src[src.index("rec = {"):]
    body = body[:body.index("}") + 1]
    written = set(re.findall(r'"([a-z_]+)":', body))
    assert written, "the writer's record literal was not found"
    unclassified = written - PINNED_PUBLIC - AMOUNTS
    assert unclassified == set(), f"writer records keys nobody classified: {unclassified}"
