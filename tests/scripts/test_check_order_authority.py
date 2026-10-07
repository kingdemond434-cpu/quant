"""ARCH-12: research holds a read-only terminal; only the order path can reach order_send."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ops import mt5_readonly as ro  # noqa: E402


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fence = _load("_quant_check_order_authority", "scripts/check_order_authority.py")


def _fake_mt5() -> ModuleType:
    m = ModuleType("MetaTrader5")
    m.TIMEFRAME_H1 = 16385  # type: ignore[attr-defined]
    m.calls = []  # type: ignore[attr-defined]
    for fn in ("initialize", "copy_rates_from_pos", "symbol_info_tick", "positions_get",
               "order_send", "order_delete", "order_check", "Buy", "Sell", "Close", "login"):
        def _f(*a, _n=fn, **k):
            m.calls.append(_n)  # type: ignore[attr-defined]
            return True
        setattr(m, fn, _f)
    return m


def test_reads_and_constants_pass_through() -> None:
    m = _fake_mt5()
    r = ro.ReadOnlyMT5(m)
    assert r.TIMEFRAME_H1 == 16385
    assert r.copy_rates_from_pos("XAUUSD", r.TIMEFRAME_H1, 0, 10) is True
    assert r.positions_get() is True
    assert r.initialize(path="C:/t/terminal64.exe", timeout=1000) is True


@pytest.mark.parametrize("name", ["order_send", "order_delete", "order_check", "Buy", "Sell",
                                  "Close", "login"])
def test_every_non_read_callable_is_refused(name: str) -> None:
    m = _fake_mt5()
    with pytest.raises(ro.ReadOnlyTerminalError):
        getattr(ro.ReadOnlyMT5(m), name)
    assert name not in m.calls  # type: ignore[attr-defined]


def test_an_unknown_future_function_is_refused_by_default() -> None:
    m = _fake_mt5()
    m.order_send_async = lambda *a: True  # type: ignore[attr-defined]
    with pytest.raises(ro.ReadOnlyTerminalError):
        ro.ReadOnlyMT5(m).order_send_async  # noqa: B018


@pytest.mark.parametrize("kw", ["login", "password", "server"])
def test_initialize_refuses_credentials(kw: str) -> None:
    m = _fake_mt5()
    with pytest.raises(ro.ReadOnlyTerminalError):
        ro.ReadOnlyMT5(m).initialize(**{kw: "x"})
    with pytest.raises(ro.ReadOnlyTerminalError):
        ro.ReadOnlyMT5(m).initialize("path", 12345)
    assert "initialize" not in m.calls  # type: ignore[attr-defined]


def test_the_proxy_cannot_be_rewired() -> None:
    r = ro.ReadOnlyMT5(_fake_mt5())
    with pytest.raises(ro.ReadOnlyTerminalError):
        r.order_send = print  # type: ignore[attr-defined]
    assert "order_send" not in dir(r)


def test_the_proxy_closes_the_door_order_door_would_open() -> None:
    """order_door.guard over the read-only proxy still cannot send: the venue call is refused."""
    with pytest.raises(ro.ReadOnlyTerminalError):
        ro.ReadOnlyMT5(_fake_mt5()).order_send({"action": 1})


@pytest.mark.parametrize(("src", "kind"), [
    ("import MetaTrader5 as mt5\n", "import"),
    ("from MetaTrader5 import initialize\n", "import"),
    ("import importlib\nimportlib.import_module('MetaTrader5')\n", "import"),
    ("__import__('MetaTrader5')\n", "import"),
    ("def f(mt5):\n    mt5.order_send({})\n", "write_call"),
    ("def f(m):\n    m.order_delete(1)\n", "write_call"),
])
def test_the_fence_sees_every_route(src: str, kind: str) -> None:
    assert [h["kind"] for h in fence.offences(src)] == [kind]


def test_reads_through_the_proxy_are_clean() -> None:
    src = ("from libs.ops.mt5_readonly import readonly_mt5\nmt5 = readonly_mt5()\n"
           "mt5.copy_rates_from_pos('X', 1, 0, 5)\n")
    assert fence.offences(src) == []


def test_the_repository_is_clean_and_the_pending_list_only_shrinks() -> None:
    doc = fence.measure(ROOT)
    assert doc["verdict"] == "PASS", doc["problems"]
    assert len(fence.PENDING_DESKTOP) <= fence.PENDING_CEILING == 3


def test_it_is_a_commit_law_fence() -> None:
    gate = _load("_quant_run_law_gate_oa", "scripts/run_law_gate.py")
    assert "check_order_authority.py" in [n for n, _ in gate._LAW_FENCES]
