"""Every Claude-invoking systemd unit must carry the same two environment lines.

WHY THIS EXISTS. On 2026-08-01 `data/miner_runway.json` showed all eleven mining seats with
`last_run: null` -- never run, not once. Four of them (prospector, litminer, dataaxis,
blindrediscovery) carried `Environment=PATH=...` and an `EnvironmentFile=-` for the
token.
`quant-frontier.service`, which drives all SEVEN regional seats, carried neither.

The consequence of the missing PATH is total and silent: systemd starts a service with a nearly
empty environment, so `claude` in ~/.local/bin is not findable and the rotation dies on "command
not found" before reading a prompt. Nothing about the prompts, the runners or the schedule was
wrong -- and every prompt improvement made to those seven regions was landing on a seat that
could never execute.

One unit drifting from its four siblings is not the kind of defect a human notices by reading;
it is the kind a test notices for free.
"""
from __future__ import annotations

from pathlib import Path

_OPS = Path(__file__).resolve().parent.parent.parent / "ops"
#: Units whose ExecStart path leads to a runner that shells out to `claude`.
_CLAUDE_UNITS = ("quant-frontier.service", "quant-prospector.service", "quant-litminer.service",
                 "quant-dataaxis.service", "quant-blindrediscovery.service")


def _unit(name: str) -> str:
    p = _OPS / name
    return p.read_text("utf-8") if p.exists() else ""


def test_every_claude_unit_puts_the_binary_on_PATH():
    """Without this the seat cannot execute at all, and it fails before producing any artifact an
    audit could read -- which is exactly how seven seats stayed dead."""
    for name in _CLAUDE_UNITS:
        src = _unit(name)
        if not src:
            continue
        assert "Environment=PATH=" in src, f"{name} has no PATH; `claude` will not be findable"
        assert "/home/quant/.local/bin" in src, f"{name}'s PATH omits the claude install dir"


def test_every_claude_unit_loads_the_token_file():
    for name in _CLAUDE_UNITS:
        src = _unit(name)
        if not src:
            continue
        assert "EnvironmentFile=" in src, f"{name} never loads CLAUDE_CODE_OAUTH_TOKEN"
        assert ".claude_token.env" in src, f"{name} loads the wrong environment file"


def test_the_token_file_is_optional_so_the_unit_still_starts():
    """The leading `-` is load-bearing. A unit that REFUSES to start when the token is absent
    leaves nothing in the log and nothing for check_miner_runway to read -- the failure becomes
    invisible. Failing loudly at run time is strictly better than not running at all."""
    for name in _CLAUDE_UNITS:
        src = _unit(name)
        if not src:
            continue
        assert "EnvironmentFile=-" in src, (
            f"{name} makes the token file mandatory; a missing file would silently prevent the "
            "unit from starting instead of producing a readable failure")


def test_units_agree_on_the_service_user():
    users = {name: [ln for ln in _unit(name).splitlines() if ln.startswith("User=")]
             for name in _CLAUDE_UNITS if _unit(name)}
    distinct = {tuple(v) for v in users.values() if v}
    assert len(distinct) <= 1, f"units disagree on User=: {users}"
