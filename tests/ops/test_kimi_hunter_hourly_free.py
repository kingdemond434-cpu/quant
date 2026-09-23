"""The kimi hunter runs hourly on the FREE chain, and the two facts are pinned together.

    "make kimi free tier hunter run hourly"            -- the principal, 2026-09-08

The two halves are one change. Before this the live path was a daily 05:40 systemd timer
running `kimi_hunter.py` whose model chain was PAID-FIRST (kimi-k3, kimi-k2, deepseek-r1,
qwen3-235b, then the :free tails) with `--deep` a dead flag nobody read -- so an hourly cadence
on THAT script would have been 24 paid hunts a day. bcc10c20 (reconciled from
claude/wonderful-darwin-7uiobi) gave the routine run its own free-only ROUTINE_MODEL_CHAIN and
made `--deep` real. The timer may be hourly ONLY while the routine chain is free-only; a test
that pinned the cadence without the chain would pin the expensive half.

The third fact is the manifest: check_scheduler_manifest (b) compares the SYSTEMD row's `on=`
to the committed timer's OnCalendar verbatim, so the two must move together or the scheduler
fence adds a TIMER finding on the next law gate.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TIMER = (ROOT / "ops" / "quant-kimi-hunter.timer").read_text("utf-8")
SERVICE = (ROOT / "ops" / "quant-kimi-hunter.service").read_text("utf-8")
HUNTER = (ROOT / "scripts" / "kimi_hunter.py").read_text("utf-8")
MANIFEST = (ROOT / "ops" / "crontab.manifest").read_text("utf-8")

HOURLY = "*-*-* *:40:00 UTC"


def _unit_value(text: str, key: str) -> str:
    m = re.search(rf"^{key}=(.*)$", text, re.M)
    assert m, f"{key} missing"
    return m.group(1).strip()


# ---------------------------------------------------------------------------- the cadence
def test_the_timer_is_hourly_and_survives_a_reboot() -> None:
    assert _unit_value(TIMER, "OnCalendar") == HOURLY
    assert _unit_value(TIMER, "Persistent") == "true"
    assert int(_unit_value(TIMER, "RandomizedDelaySec")) <= 600


def test_the_manifest_systemd_row_carries_the_same_oncalendar() -> None:
    rows = [ln for ln in MANIFEST.splitlines()
            if ln.startswith("SYSTEMD") and 'unit="quant-kimi-hunter.timer"' in ln]
    assert len(rows) == 1, rows
    assert f'on="{HOURLY}"' in rows[0], rows[0]
    assert 'exec="scripts/kimi_hunter.py"' in rows[0]


def test_the_service_runs_the_routine_invocation_not_the_deep_one() -> None:
    exec_line = _unit_value(SERVICE, "ExecStart")
    assert "scripts/kimi_hunter.py" in exec_line
    assert "--deep" not in exec_line
    assert "source ops/free_tier.env" in exec_line
    assert "TimeoutStartSec=1h" in SERVICE              # a slow hour is skipped, never stacked


def test_the_routine_hunt_is_not_also_a_live_cron_row() -> None:
    """One plane per invocation: the routine hunt is the timer's; cron keeps only --deep."""
    active = [ln for ln in MANIFEST.splitlines()
              if "scripts/kimi_hunter.py" in ln and not ln.lstrip().startswith("#")
              and not ln.startswith("SYSTEMD")]
    assert active, "the weekly --deep row must survive"
    assert all("--deep" in ln for ln in active), active


# --------------------------------------------------------------------------- the free chain
def test_the_routine_chain_is_free_tier_only() -> None:
    import scripts.kimi_hunter as K

    chain = K.ROUTINE_MODEL_CHAIN
    assert chain, "an empty routine chain hunts nothing"
    paid = [m for m in chain if not m.endswith(":free")]
    assert not paid, f"an hourly routine on a paid model: {paid}"


def test_the_routine_chain_ends_in_a_verified_answering_tail() -> None:
    """The mandate's three free seats lead; the free panel's verified HEAVY tier trails, so an
    hour in which every preferred seat refuses still hunts instead of writing BLOCKED."""
    import scripts.kimi_hunter as K

    from libs.research.free_panel import HEAVY

    assert K.ROUTINE_MODEL_CHAIN[0] == "moonshotai/kimi-k2:free"
    assert K.ROUTINE_MODEL_CHAIN[-len(HEAVY):] == tuple(HEAVY)


def test_the_routine_run_actually_uses_the_routine_chain() -> None:
    """The flag was dead once; the chain must be SELECTED by it, not just declared."""
    assert 'deep = "--deep" in sys.argv' in HUNTER
    assert "chain = MODEL_CHAIN if deep else ROUTINE_MODEL_CHAIN" in HUNTER


def test_the_deep_run_is_not_hourly() -> None:
    """The paid chain stays on its own 2x/week row; the manifest must not carry an hourly --deep."""
    hourly_deep = [ln for ln in MANIFEST.splitlines()
                   if "kimi_hunter.py --deep" in ln and not ln.lstrip().startswith("#")
                   and re.match(r"^\S+\s+\*\s", ln)]
    assert not hourly_deep, hourly_deep
