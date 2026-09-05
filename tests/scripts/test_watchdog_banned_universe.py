"""GAP REGISTER #150: the fleet watchdog must never re-arm the banned crypto-exchange universe.

Measured 2026-08-27: `run_cashcarry_executor.py --live --capital 4500` was running, held flat only
by `data/CASHCARRY_KILL`, and this watchdog stood ready to respawn it the moment its heartbeat went
stale. Two other arms were already past their thresholds -- the liquidation listener (heartbeat
absent) and a public tunnel (heartbeat 1112h stale) -- so both would have fired on the next run.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = (ROOT / "scripts" / "watchdog.py").read_text("utf-8")


def _load():
    spec = importlib.util.spec_from_file_location("_wd", ROOT / "scripts" / "watchdog.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_recorders_off_blocks_the_banned_arms(tmp_path, monkeypatch) -> None:
    wd = _load()
    monkeypatch.setattr(wd, "_RECORDERS_OFF", tmp_path / "RECORDERS_OFF")
    monkeypatch.setattr(wd, "_CC_KILL", tmp_path / "CASHCARRY_KILL")
    assert wd._banned_universe_block() is None
    (tmp_path / "RECORDERS_OFF").write_text("", "utf-8")
    assert wd._banned_universe_block() == "data/RECORDERS_OFF set"


def test_cashcarry_kill_alone_blocks_the_banned_arms(tmp_path, monkeypatch) -> None:
    wd = _load()
    monkeypatch.setattr(wd, "_RECORDERS_OFF", tmp_path / "RECORDERS_OFF")
    monkeypatch.setattr(wd, "_CC_KILL", tmp_path / "CASHCARRY_KILL")
    (tmp_path / "CASHCARRY_KILL").write_text("", "utf-8")
    assert wd._banned_universe_block() == "data/CASHCARRY_KILL set"


def test_every_banned_arm_consults_the_gate() -> None:
    """A gate one arm forgets to call is not a gate. Each banned spawn must sit behind `blocked`.

    UPDATED 2026-09-05 (universe mandate). Two of the three arms this originally named --
    `cashcarry-exec` and `liquidation-listener` -- no longer exist to be gated: their scripts were
    deleted with the crypto-exchange desk. Asserting they still consult the gate would have been
    asserting that a deleted arm is politely refused, which is not a property worth holding and
    would have forced the watchdog to keep dead branches alive to satisfy this test.

    What replaces it is STRICTLY STRONGER, and `test_the_retired_arms_cannot_be_spawned_at_all`
    below is the half that matters: an arm that cannot be spawned is safer than one that is
    spawnable-but-refused, because a refusal depends on a kill-file being present and a deletion
    does not. This test keeps the gating requirement for every arm that still exists.
    """
    for arm in ("crypto-exchange execution", "public-tunnel"):
        assert f'refused.append(f"{arm} ' in SRC, f"{arm} does not consult the mandate gate"
    assert SRC.count("_banned_universe_block()") >= 2


def test_the_retired_arms_cannot_be_spawned_at_all() -> None:
    """The banned executors must be UNSPAWNABLE, not merely refused.

    `data/CASHCARRY_KILL` and `data/RECORDERS_OFF` are files, and a file can be removed by anyone
    with shell access or a careless deploy. The mandate says this universe is never hunted again,
    so the guarantee has to survive the kill-file going missing -- which it only does if the
    watchdog carries no branch that could start these processes in the first place.

    COMMENTS ARE STRIPPED BEFORE THE CHECK, on purpose and for the same reason
    `scripts/check_mt5_purity.py` strips them: this watchdog's header RECORDS that it once stood
    ready to respawn `run_cashcarry_executor.py --live --capital 4500`, and that record is the
    evidence for why this test exists. A test that forced the desk to delete its own account of
    the incident would be trading real memory for a cosmetic pass.
    """
    executable = "\n".join(ln for ln in SRC.splitlines() if not ln.lstrip().startswith("#"))
    for retired in ("run_cashcarry_executor.py", "liquidation_listener.py",
                    "run_crypto_portfolio.py", "run_recorder.py"):
        assert retired not in executable, f"watchdog can still spawn {retired}"


def test_the_ruin_rail_is_never_gated() -> None:
    """The dead-man switch is Tier-3 never-touch: a ruin rail must arm under EVERY condition,
    including this one. Gating it would be the fix creating a worse defect than it repairs."""
    dm = SRC.split("if not _fresh(_DM_HB, 300):", 1)[1].split("acted.append(\"deadman\")", 1)[0]
    assert "blocked" not in dm
    assert '_spawn(["scripts/run_deadman_switch.py"], "deadman-switch")' in dm


def test_refusals_are_printed_not_silent() -> None:
    """A silently-skipped arm and a healthy arm print the same line; the desk could not then tell
    'the ban is holding' from 'the heartbeat happened to be fresh'."""
    assert "REFUSED banned-universe arm(s)" in SRC
