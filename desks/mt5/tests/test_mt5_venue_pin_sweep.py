"""Every swept MT5 attach goes by the desk's terminal path and refuses a non-Fusion account.

THE COIN FLIP (2026-11-11): the box runs Fusion and FTMO logged in side by side, and a pathless
`mt5.initialize()` landed on FTMO about two runs in three. Each organ below now attaches through
`mt5_session.attach_or_initialize` with the desk's `terminal_path.txt`, then proves the account
with `mt5_session.venue_refusal`; a refusal shuts the connection and the organ answers with its
existing failure value -- never a number read off the wrong broker.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import config  # noqa: E402

from research import mt5_session  # noqa: E402

TERMINAL = r"C:\Fusion\terminal64.exe"
FUSION = "FusionMarkets-Live"
FTMO = "FTMO-Server3"


class FakeMT5:
    """One terminal: attached already (`held`) or opened by `initialize`, on `server`."""

    TIMEFRAME_M1 = 1

    def __init__(self, server: str, *, held: bool = True, tdir: str = r"C:\Fusion") -> None:
        self.server, self.attached, self.tdir = server, held, tdir
        self.calls: list[str] = []
        self.init_kwargs: list[dict[str, Any]] = []

    def initialize(self, **kwargs: Any) -> bool:
        self.calls.append("initialize")
        self.init_kwargs.append(kwargs)
        self.attached = True
        return True

    def shutdown(self) -> None:
        self.calls.append("shutdown")
        self.attached = False

    def terminal_info(self) -> Any:
        if not self.attached:
            return None
        return SimpleNamespace(path=self.tdir, connected=True, trade_allowed=True, ping_last=0,
                               name="MetaTrader 5", build=5000)

    def account_info(self) -> Any:
        if not self.attached:
            return None
        return SimpleNamespace(login=1, server=self.server, trade_mode=2, margin=100.0,
                               equity=10000.0, margin_so_so=50.0, currency="USD",
                               balance=10000.0, leverage=500.0, company="x", profit=0.0,
                               margin_free=9900.0)

    def last_error(self) -> tuple[int, str]:
        return (1, "ok")

    # what a measured read would go on to ask -- reached only past the venue check
    def symbol_info_tick(self, symbol: str) -> Any:
        self.calls.append("read")
        return None

    def positions_get(self) -> tuple[()]:
        self.calls.append("read")
        return ()

    def history_deals_get(self, *a: Any) -> list[Any]:
        self.calls.append("read")
        return []

    def symbol_info(self, symbol: str) -> Any:
        self.calls.append("read")
        return None


@pytest.fixture
def desk_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "terminal_path", lambda: TERMINAL)


def _install(monkeypatch: pytest.MonkeyPatch, fake: FakeMT5) -> FakeMT5:
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake)
    return fake


# ------------------------------------------------------------------ 1. pf_allocator (money path)
def test_account_margin_goes_through_attach_without_autostart(monkeypatch, desk_terminal):
    from research import pf_allocator as pa
    seen: list[dict[str, Any]] = []
    real = mt5_session.attach_or_initialize

    def spy(mt5: Any, **kwargs: Any) -> bool:
        seen.append(kwargs)
        return real(mt5, **kwargs)

    monkeypatch.setattr(mt5_session, "attach_or_initialize", spy)
    fake = _install(monkeypatch, FakeMT5(FUSION))
    assert pa.account_margin() == (100.0, 10000.0, "measured from the live terminal")
    assert seen == [{"path": TERMINAL, "timeout": 15000, "allow_autostart": False}]
    assert fake.calls == []                       # held connection used and left alone


def test_account_margin_never_launches_a_terminal(monkeypatch, desk_terminal):
    from research import pf_allocator as pa
    fake = _install(monkeypatch, FakeMT5(FUSION, held=False))
    margin, equity, why = pa.account_margin()
    assert (margin, equity) == (None, None) and "unreachable" in why
    assert "initialize" not in fake.calls


def test_account_margin_refuses_a_non_fusion_server(monkeypatch, desk_terminal):
    from research import pf_allocator as pa
    fake = _install(monkeypatch, FakeMT5(FTMO))
    margin, equity, why = pa.account_margin()
    assert (margin, equity) == (None, None)
    assert "wrong venue" in why and FTMO in why
    assert fake.calls == ["shutdown"]


def test_account_margin_refuses_another_terminal_on_a_fusion_server(monkeypatch, desk_terminal):
    from research import pf_allocator as pa
    fake = _install(monkeypatch, FakeMT5(FUSION, tdir=r"C:\Other"))
    margin, _, why = pa.account_margin()
    assert margin is None and "not the configured" in why
    assert fake.calls == ["shutdown"]


# ------------------------------------------------------------- 4. account readers in research
def test_constrained_book_refuses_ftmo(monkeypatch, desk_terminal):
    import constrained_book as cb
    fake = _install(monkeypatch, FakeMT5(FTMO, held=False))
    got, why = cb._terminal_account()
    assert got == {"margin": None, "equity": None, "stop_out_level": None}
    assert "wrong venue" in why
    assert fake.init_kwargs == [{"path": TERMINAL, "timeout": 15000}]
    assert fake.calls == ["initialize", "shutdown"]


def test_constrained_book_measures_fusion_and_closes_what_it_opened(monkeypatch, desk_terminal):
    import constrained_book as cb
    fake = _install(monkeypatch, FakeMT5(FUSION, held=False))
    got, why = cb._terminal_account()
    assert why == "terminal" and got["margin"] == 100.0
    assert fake.calls == ["initialize", "shutdown"]


def test_financing_lab_refuses_ftmo_and_names_it(monkeypatch, desk_terminal):
    from research import financing_lab as FL
    fake = _install(monkeypatch, FakeMT5(FTMO))
    out = FL.read_account()
    assert out["source"] != "live terminal"
    assert any("wrong venue" in u for u in out["unmeasured"])
    assert "read" not in fake.calls and "shutdown" in fake.calls


def test_ops_redundancy_terminal_health_refuses_ftmo(monkeypatch, desk_terminal):
    import ops_redundancy as ops
    fake = _install(monkeypatch, FakeMT5(FTMO))
    out = ops.terminal_health()
    assert out["terminal"]["status"] == "UNMEASURED"
    assert "wrong venue" in out["terminal"]["why"]
    assert "read" not in fake.calls and "shutdown" in fake.calls


def test_cost_truth_snapshot_refuses_ftmo(monkeypatch, desk_terminal):
    import cost_truth as CT
    fake = _install(monkeypatch, FakeMT5(FTMO))
    snap = CT.terminal_snapshot(["XAUUSD"], 5.0, 10)
    assert snap["status"] == CT.UNMEASURED and "wrong venue" in snap["why"]
    assert "read" not in fake.calls and fake.calls == ["shutdown"]


def test_fusion_spread_tape_refuses_ftmo(monkeypatch, desk_terminal):
    import fusion_spread_tape as FST
    fake = _install(monkeypatch, FakeMT5(FTMO))
    live = FST.live_snapshot(["XAUUSD"])
    assert live["status"] == FST.UNMEASURED and "wrong venue" in live["why"]
    fake.attached = True
    assert FST.deals_from_terminal() == []
    assert "read" not in fake.calls


def test_fill_bar_gaps_terminal_refuses_ftmo(monkeypatch, desk_terminal):
    spec = importlib.util.spec_from_file_location(
        "fill_bar_gaps_venue", DESK / "scripts" / "fill_bar_gaps.py")
    assert spec and spec.loader
    fbg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fbg)
    _install(monkeypatch, FakeMT5(FTMO))
    mt5, why = fbg._terminal()
    assert mt5 is None and "wrong venue" in why


# ---------------------------------------------------------------- 3. session-0 SYSTEM organs
def test_zentech_snapshot_refuses_ftmo(monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "build_zentech_state_venue", ROOT / "scripts" / "build_zentech_state.py")
    assert spec and spec.loader
    bz = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bz)
    tdir = str(bz.DESK / "data" / "terminal_path.txt")
    configured = Path(tdir).read_text("utf-8").strip() if Path(tdir).exists() else ""
    attached = configured.rsplit("/", 1)[0].rsplit("\\", 1)[0] if configured else r"C:\Fusion"
    fake = _install(monkeypatch, FakeMT5(FTMO, tdir=attached))
    assert bz._mt5_snapshot() == {}
    assert fake.calls == ["shutdown"]
    fake.server, fake.attached = FUSION, True
    assert bz._mt5_snapshot()["server"] == FUSION


# ------------------------------------------------------------------------------ 5. libs
def test_bar_source_refuses_ftmo_and_accepts_an_explicit_venue(monkeypatch, desk_terminal):
    from libs.data.errors import MT5Error
    from libs.data.mt5_source import MT5BarSource
    fake = _install(monkeypatch, FakeMT5(FTMO))
    with pytest.raises(MT5Error, match="wrong venue"):
        MT5BarSource()
    assert fake.calls == ["shutdown"]
    fake.attached = True
    src = MT5BarSource(path=TERMINAL, expected_prefix="FTMO-")
    assert src._mt5 is fake


# ------------------------------------------------------------------- no bare attach is left
SWEPT = (
    "desks/mt5/research/pf_allocator.py", "scripts/build_zentech_state.py",
    "desks/mt5/research/deepen_universe.py", "desks/mt5/scripts/refresh_cost_fields.py",
    "desks/mt5/research/constrained_book.py", "desks/mt5/research/cost_truth.py",
    "desks/mt5/research/financing_lab.py", "desks/mt5/research/ops_redundancy.py",
    "desks/mt5/research/fusion_spread_tape.py", "desks/mt5/scripts/fill_bar_gaps.py",
    "desks/mt5/scripts/check_gold_live.py", "desks/mt5/scripts/download_remaining.py",
    "desks/mt5/research/expand_universe.py", "libs/data/mt5_source.py",
    "libs/execution/broker.py", "scripts/ingest_multiasset.py",
)


@pytest.mark.parametrize("rel", SWEPT)
def test_no_swept_site_attaches_without_the_pin(rel: str) -> None:
    src = (ROOT / rel).read_text(encoding="utf-8")
    assert not re.search(r"\bmt5\.initialize\(", src), f"{rel}: a bare mt5.initialize() is back"
    assert "attach_or_initialize(" in src and "venue_refusal(" in src
