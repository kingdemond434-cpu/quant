"""Library-layer observability (gap #56) -- and the fence that keeps it safe.

The desk already OWNED a structured logger (libs/core/logging.py, correlation ids + secret
redaction) that 1 of 318 library modules used. These tests pin the ACTIVATION: the money path
now leaves a trail, the library still never configures handlers (so importing it cannot change
any script's output), and -- the load-bearing one -- no log call in the touched files can leak a
key, secret or signature.

WHY `libs/execution/binance_live.py` IS NO LONGER IN `_WIRED` (2026-09-05, MT5-only purge). That
module was the retired crypto-exchange live connector and it is gone from disk; a parametrisation
over a path that does not exist is a test that fails for the wrong reason, not a fence. The fence
itself is UNCHANGED and still binds on every wired module that survives. The two Binance modules
that DO survive -- `binance_testnet.py` / `binance_spot_testnet.py`, the Tier-3 deadman rail's own
plumbing -- were deliberately never wired to `libs.core.logging` and are held byte-for-byte frozen,
so they are not candidates for this list. Any NEW module that grows a `_log` on the money path
must be added here.
"""
from __future__ import annotations

import ast
import logging
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_WIRED = ("libs/execution/staging.py", "libs/risk/gate.py")
_FORBIDDEN = ("key", "secret", "signature", "sig", "token", "password", "credential",
              "query", "body")


def _log_call_args(path: Path) -> list[tuple[int, list[str]]]:
    """Every `_log.<level>(...)` call in the file, as (lineno, [arg source strings])."""
    tree = ast.parse(path.read_text("utf-8"))
    out: list[tuple[int, list[str]]] = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name) and node.func.value.id == "_log"):
            out.append((node.lineno, [ast.unparse(a) for a in node.args]))
    return out


@pytest.mark.parametrize("rel", _WIRED)
def test_every_wired_module_has_a_module_logger(rel: str) -> None:
    src = (_ROOT / rel).read_text("utf-8")
    assert "from libs.core.logging import get_logger" in src
    assert "_log = get_logger(__name__)" in src


@pytest.mark.parametrize("rel", _WIRED)
def test_no_log_call_can_leak_a_credential(rel: str) -> None:
    """THE FENCE. A log line naming `key`, `secret`, `sig`, or the signed query/body would put
    live credentials in a file on disk. Scanned structurally, not by eyeballing."""
    for lineno, args in _log_call_args(_ROOT / rel):
        for arg in args:
            lowered = arg.lower()
            for bad in _FORBIDDEN:
                # Word-ish match so 'reduce_only'/'stop_price' don't trip on substrings.
                assert not any(tok == bad for tok in lowered.replace("(", " ").replace(")", " ")
                               .replace(",", " ").replace(".", " ").split()), \
                    f"{rel}:{lineno} log arg {arg!r} references forbidden name {bad!r}"


@pytest.mark.parametrize("rel", _WIRED)
def test_log_calls_use_lazy_percent_formatting(rel: str) -> None:
    """No f-strings inside log calls: the first arg must be a plain format string, so formatting
    work (and any exception inside it) never happens on a suppressed level in the hot path."""
    for lineno, args in _log_call_args(_ROOT / rel):
        assert args, f"{rel}:{lineno} empty log call"
        assert "f'" not in args[0] and 'f"' not in args[0], \
            f"{rel}:{lineno} uses an f-string as the log format"


@pytest.mark.parametrize("rel", _WIRED)
def test_library_never_configures_handlers(rel: str) -> None:
    """A library that attaches handlers or sets levels hijacks the owning script's logging."""
    src = (_ROOT / rel).read_text("utf-8")
    for banned in ("basicConfig", "addHandler", "setLevel", "StreamHandler", "FileHandler"):
        assert banned not in src, f"{rel} calls {banned} -- the owning script owns configuration"


def test_stage_transitions_are_logged(caplog: pytest.LogCaptureFixture,
                                      tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.execution import staging
    monkeypatch.setattr(staging, "_STATE", tmp_path / "stage_state.json")
    # F0013: pin the logger. A bare at_level() only raises the ROOT threshold; whether the
    # record ever reaches caplog then depends on what levels/propagation earlier tests left on
    # the module logger -- order-dependent flakiness (passed 15/15 isolated, failed in full CI).
    with caplog.at_level(logging.INFO, logger="libs.execution.staging"):
        ok, _ = staging.promote({})            # empty evidence -> gate not met
        assert ok is False
        assert any("promote REFUSED" in r.message for r in caplog.records)


def test_risk_gate_rejection_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    from libs.risk.gate import _reject
    with caplog.at_level(logging.WARNING, logger="libs.risk.gate"):
        d = _reject("fail-closed: invalid equity", [])
        assert d.approved is False
        assert any("risk gate REJECTED" in r.message for r in caplog.records)


# REMOVED 2026-09-05: `test_unarmed_signed_call_is_logged_and_still_raises` exercised
# `libs/execution/binance_live._signed`, the retired crypto-exchange live connector, which is
# deleted. Its claim -- "logging ADDS a trail without changing behaviour, the refusal still
# raises" -- has no surviving subject: the frozen deadman-rail connectors carry no `_log`. It is
# recorded here rather than silently dropped so the claim can be re-pinned on the MT5 gateway's
# signed path when that path grows a logger.
