"""THE PUBLISHED gateway_state.json CARRIES NO ACCOUNT AMOUNT (2026-11-11).

`sync_shadow_to_git.ps1` publishes the gateway's restart state to a PUBLIC repository every
fifteen minutes. It carried `equity`, `day_start_equity.equity` and each open position's
`profit`. `libs/ops/account_withhold.scrub_for_publish` now re-serialises the blob without them,
keeping only the top-level keys named in `GATEWAY_PUBLIC_KEYS`. These tests pin the allowed keys,
the redaction, the writer's serialisation, and the tracked copy itself. All amounts below are
placeholders, never a real account's.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ops import account_withhold as aw  # noqa: E402

REL = "desks/mt5/data/gateway_state.json"

#: Pinned on purpose: adding a published key is a reviewed change to this test, never a side
#: effect of the gateway growing a new field.
PINNED = {
    "armed", "bracket", "bracket_cancelled", "brackets", "broker_utc_offset_h",
    "daily_loss_stood_down", "day_start_equity", "generic", "last_bracket_date",
    "last_reconcile", "lot", "netting_booked", "orig_stop_dist", "paused_snapshot_at", "pending",
    "placement_health", "placement_pass", "placement_pass_clock", "placement_tick_broker",
    "placement_tick_utc", "position", "rails_logged", "restart_reconcile", "scalp",
    "vetoed_today",
}


def _state() -> dict[str, Any]:
    return {
        "armed": True, "lot": 0.01, "equity": 1234.56, "margin_free": 1200.0,
        "sizing_equity": 1234.56, "some_future_key": {"x": 1},
        "day_start_equity": {"date": "2026-11-11", "equity": 1300.0},
        "position": [{"ticket": 1, "type": 0, "volume": 0.01, "price_open": 4000.0, "sl": 3990.0,
                      "tp": 4020.0, "profit": -7.5, "symbol": "XAUUSD"}],
        "pending": None, "last_reconcile": "2026-11-11T16:00:00+00:00",
        "placement_health": {"consecutive_total_rejections": 0, "last_ok": "2026-11-11"},
        "generic": {"s": {"last_signal_bar": "2026-11-11 08:00:00+00:00", "trail_k": 1.5}},
    }


def _walk_keys(node: Any, path: str = "") -> list[str]:
    out: list[str] = []
    if isinstance(node, dict):
        for k, v in node.items():
            here = f"{path}.{k}" if path else str(k)
            out.append(here)
            out += _walk_keys(v, here)
    elif isinstance(node, list):
        for v in node:
            out += _walk_keys(v, f"{path}[]")
    return out


def test_the_allowed_keys_are_pinned_and_none_is_an_amount() -> None:
    assert set(aw.GATEWAY_PUBLIC_KEYS) == PINNED
    assert {k for k in PINNED if aw.MONEY_KEY.search(k)} == {"day_start_equity"}
    assert "equity" not in PINNED and "margin_free" not in PINNED


def test_redaction_drops_every_amount_and_keeps_the_rest() -> None:
    view, dropped = aw.redact_money(_state())
    assert set(dropped) >= {"equity", "margin_free", "sizing_equity", "some_future_key",
                            "day_start_equity.equity", "position[].profit"}
    assert view["day_start_equity"] == {"date": "2026-11-11"}
    assert view["position"][0]["symbol"] == "XAUUSD" and "profit" not in view["position"][0]
    assert view["generic"]["s"]["trail_k"] == 1.5
    assert set(view) <= PINNED
    assert not [k for k in _walk_keys(view)
                if aw.MONEY_KEY.search(k.rsplit(".", 1)[-1]) and k != "day_start_equity"]
    text = json.dumps(view)
    for amount in ("1234.56", "1200.0", "1300.0", "-7.5"):
        assert amount not in text


def test_the_publisher_reserialises_like_the_gateway_and_leaves_clean_bytes_alone() -> None:
    raw = json.dumps(_state(), indent=2, default=str).encode("utf-8")
    new, dropped = aw.scrub_for_publish(REL, raw)
    assert new is not None and dropped
    view, _ = aw.redact_money(_state())
    assert new == json.dumps(view, indent=2, default=str).encode("utf-8")
    again, gone = aw.scrub_for_publish(REL, new)
    assert again is None and gone == []


def test_unparseable_bytes_pass_through_for_the_fence_to_judge() -> None:
    assert aw.scrub_for_publish(REL, b"not json") == (None, [])
    assert aw.scrub_for_publish(REL, b"[1, 2]") == (None, [])


def test_the_tracked_copy_publishes_without_an_amount() -> None:
    # The box republishes this file every fifteen minutes and its copy wins any merge, so the
    # tracked bytes may be the raw state until the box runs this publisher: judge what the
    # publisher would make of them, which is what reaches the repository.
    raw = (ROOT / REL).read_bytes()
    new, _ = aw.scrub_for_publish(REL, raw)
    doc = json.loads(new if new is not None else raw)
    assert set(doc) <= PINNED
    leaks = [k for k in _walk_keys(doc)
             if aw.MONEY_KEY.search(k.rsplit(".", 1)[-1]) and k != "day_start_equity"]
    assert leaks == []


def test_every_top_level_key_the_gateway_writes_is_published_or_withheld_by_name() -> None:
    src = (ROOT / "desks/mt5/mt5desk/gateway.py").read_text("utf-8")
    written = set(re.findall(r'\bst\["([a-z_]+)"\]\s*=(?!=)', src))
    written |= set(re.findall(r'\bst\.setdefault\("([a-z_]+)"', src))
    unnamed = {k for k in written if k not in PINNED and not aw.MONEY_KEY.search(k)}
    assert unnamed == set(), f"gateway writes top-level keys nobody classified: {unnamed}"


def test_the_cli_reblobs_the_state_in_a_repo(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    raw = json.dumps(_state(), indent=2, default=str).encode("utf-8")
    blob = subprocess.run(["git", "-C", str(tmp_path), "hash-object", "-w", "--stdin"],
                          input=raw, capture_output=True, check=True).stdout.decode().strip()
    proc = subprocess.run([sys.executable, str(ROOT / "libs/ops/account_withhold.py"),
                           "--repo", str(tmp_path)], input=f"{blob}\t{REL}\n",
                          capture_output=True, text=True, check=True)
    new_blob, rel = proc.stdout.strip().split("\t")
    assert rel == REL and new_blob != blob
    body = subprocess.run(["git", "-C", str(tmp_path), "cat-file", "blob", new_blob],
                          capture_output=True, check=True).stdout.decode()
    assert "1234.56" not in body and '"equity"' not in body
    assert "1234.56" not in proc.stderr and "equity" in proc.stderr
