"""Live connector -- safety invariants (no live-trading risk in CI; module must stay inert).

The whole point of this module is that it does NOTHING dangerous until three independent,
human-controlled preconditions all hold. Every test here is checking an ABSENCE: no live URL
leak, no signed call without full arming, no withdrawal-class capability anywhere in the module.
"""

from __future__ import annotations

import ast
import inspect

import libs.execution.binance_live as bl
import libs.execution.binance_spot_live as bsl

_DANGEROUS_SUBSTRINGS = ("withdraw", "transfer", "subaccount", "sub-account", "createapikey",
                         "deleteapikey")
_MODULES = (bl, bsl)


def _defined_function_names(mod: object) -> set[str]:
    tree = ast.parse(inspect.getsource(mod))
    return {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}


def _endpoint_path_literals(mod: object) -> list[str]:
    """String literals passed as the first positional arg to _get/_signed -- the actual venue
    endpoint paths this module can reach. Docstrings/comments are deliberately excluded so a
    prose mention (e.g. "withdrawal-disabled key") can't false-positive this check."""
    tree = ast.parse(inspect.getsource(mod))
    out = []
    for n in ast.walk(tree):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id in ("_get", "_signed") and n.args
                and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str)):
            out.append(n.args[0].value)
    return out


def test_base_urls_pinned_to_live_not_testnet() -> None:
    for mod in _MODULES:
        assert mod._BASE.startswith("https://")
        assert "testnet" not in mod._BASE.lower()
        assert "vision" not in mod._BASE.lower()          # testnet.binance.vision tell


def test_no_keys_means_not_armed(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    for mod in _MODULES:
        monkeypatch.setattr(mod, "_KEYFILE", tmp_path / "nope.json")
        monkeypatch.setattr(mod, "_ENABLE_FLAG", tmp_path / "no_enable")
        monkeypatch.setattr(mod, "_VPS_MARKER", tmp_path / "no_vps")
        assert mod.has_keys() is False
        armed, why = mod.is_armed()
        assert armed is False
        assert "keys_present=False" in why


def test_each_precondition_individually_blocks_arming(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Arming requires ALL three -- any single missing precondition must keep it disarmed."""
    import json as _json
    keyfile = tmp_path / "keys.json"
    keyfile.write_text(_json.dumps({"key": "k", "secret": "s"}), "utf-8")
    enable = tmp_path / "enable"
    enable.write_text("", "utf-8")
    vps = tmp_path / "vps"
    vps.write_text("", "utf-8")
    for mod in _MODULES:
        # all three present -> armed
        monkeypatch.setattr(mod, "_KEYFILE", keyfile)
        monkeypatch.setattr(mod, "_ENABLE_FLAG", enable)
        monkeypatch.setattr(mod, "_VPS_MARKER", vps)
        assert mod.is_armed()[0] is True
        # drop each one in turn -> disarmed
        monkeypatch.setattr(mod, "_ENABLE_FLAG", tmp_path / "missing_enable")
        assert mod.is_armed()[0] is False
        monkeypatch.setattr(mod, "_ENABLE_FLAG", enable)
        monkeypatch.setattr(mod, "_VPS_MARKER", tmp_path / "missing_vps")
        assert mod.is_armed()[0] is False
        monkeypatch.setattr(mod, "_VPS_MARKER", vps)
        monkeypatch.setattr(mod, "_KEYFILE", tmp_path / "missing_keys.json")
        assert mod.is_armed()[0] is False
        monkeypatch.setattr(mod, "_KEYFILE", keyfile)


def test_signed_call_refuses_when_not_armed(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    for mod in _MODULES:
        monkeypatch.setattr(mod, "_KEYFILE", tmp_path / "nope.json")
        monkeypatch.setattr(mod, "_ENABLE_FLAG", tmp_path / "no_enable")
        monkeypatch.setattr(mod, "_VPS_MARKER", tmp_path / "no_vps")
        try:
            mod._signed("/anything", {})
        except RuntimeError as e:
            assert "not armed" in str(e)
        else:  # pragma: no cover
            raise AssertionError(f"{mod.__name__}._signed should refuse when unarmed")


def test_no_withdrawal_or_transfer_capability_anywhere() -> None:
    """Capability whitelist is enforced BY CONSTRUCTION: no function name, and no venue
    ENDPOINT PATH actually reachable via ``_get``/``_signed``, may reference a withdrawal/
    transfer/key-management capability. Prose mentions in docstrings (e.g. describing the key
    as "withdrawal-disabled") are deliberately not scanned -- only reachable code is a risk."""
    for mod in _MODULES:
        names = {n.lower() for n in _defined_function_names(mod)}
        paths = [p.lower() for p in _endpoint_path_literals(mod)]
        assert paths, f"{mod.__name__}: no endpoint literals found -- check the AST scan itself"
        for bad in _DANGEROUS_SUBSTRINGS:
            assert not any(bad in n for n in names), \
                f"{mod.__name__} defines a function referencing forbidden capability {bad!r}"
            assert not any(bad in p for p in paths), \
                f"{mod.__name__} calls an endpoint referencing forbidden capability {bad!r}: " \
                f"{[p for p in paths if bad in p]}"


def test_public_endpoints_work_without_arming(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Read-only public market data must NOT require arming (harmless, useful for dry-runs)."""
    for mod in _MODULES:
        monkeypatch.setattr(mod, "_KEYFILE", tmp_path / "nope.json")
        monkeypatch.setattr(mod, "_ENABLE_FLAG", tmp_path / "no_enable")
        monkeypatch.setattr(mod, "_VPS_MARKER", tmp_path / "no_vps")
        calls = []

        def _fake_get(*a, calls=calls, **k):
            calls.append((a, k))
            return {}

        monkeypatch.setattr(mod, "_get", _fake_get)
        mod.book_ticker()
        mod.exchange_filters()
        mod.prices() if hasattr(mod, "prices") else mod.mark_prices()
        assert len(calls) == 3                              # none of these needed _signed
