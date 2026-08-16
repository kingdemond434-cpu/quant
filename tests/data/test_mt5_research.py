from __future__ import annotations

from types import SimpleNamespace

from scripts.ingest_history import _MAXBARS, _REQUEST_CHUNK, _fetch

from libs.data.mt5_research import (
    LIQUID_INTRADAY_CORE,
    research_session_verdict,
    resolve_liquid_intraday_core,
)


def _account(**overrides: object) -> SimpleNamespace:
    values = {"server": "Pinned", "trade_mode": 2, "trade_allowed": False}
    values.update(overrides)
    return SimpleNamespace(**values)


def _terminal(**overrides: object) -> SimpleNamespace:
    values = {"trade_allowed": False}
    values.update(overrides)
    return SimpleNamespace(**values)


def test_demo_is_safe_and_server_is_still_pinned() -> None:
    assert research_session_verdict(_account(trade_mode=0), _terminal()).allowed
    wrong = research_session_verdict(
        _account(trade_mode=0), _terminal(), expected_server="Different"
    )
    assert not wrong.allowed and wrong.mode == "WRONG_SERVER"


def test_live_requires_explicit_server_pinned_double_readonly_proof() -> None:
    assert not research_session_verdict(_account(), _terminal()).allowed
    assert not research_session_verdict(_account(), _terminal(), allow_readonly_live=True).allowed
    ok = research_session_verdict(
        _account(), _terminal(), expected_server="Pinned", allow_readonly_live=True
    )
    assert ok.allowed and ok.mode == "INVESTOR_READONLY"


def test_account_trading_flag_fail_closes_but_terminal_ui_switch_does_not() -> None:
    assert not research_session_verdict(
        _account(trade_allowed=True),
        _terminal(),
        expected_server="Pinned",
        allow_readonly_live=True,
    ).allowed
    verdict = research_session_verdict(
        _account(),
        _terminal(trade_allowed=True),
        expected_server="Pinned",
        allow_readonly_live=True,
    )
    assert verdict.allowed
    assert "terminal-switch-on" in verdict.reason


def test_liquid_core_spans_mt5_asset_classes() -> None:
    assert {"XAUUSD", "XAGUSD", "EURUSD", "USDJPY", "US500", "XTIUSD"} <= set(LIQUID_INTRADAY_CORE)


def test_liquid_core_resolves_broker_aliases_without_duplicates() -> None:
    available = ["EURUSD", "XAUUSD", "SP500.r", "USOUSD", "UKOUSD", "JPN225ft"]
    resolved = resolve_liquid_intraday_core(available)
    assert set(resolved) == set(available)
    assert len(resolved) == len(set(resolved))


def test_native_history_request_stays_below_terminal_crash_ceiling() -> None:
    assert _MAXBARS == 30_000


def test_history_fetch_pages_below_native_crash_ceiling() -> None:
    calls: list[tuple[int, int]] = []

    class MT5:
        def copy_rates_range(self, *_args: object) -> list[int]:
            raise AssertionError("range fallback should not run when paged history exists")

        def copy_rates_from_pos(
            self, _symbol: str, _tf: int, offset: int, count: int
        ) -> list[tuple[int, int]]:
            calls.append((offset, count))
            return [(offset, count)] * count

    result = _fetch(MT5(), "EURUSD", 1, 12_000, 1, object())
    assert len(result) == 12_000
    assert calls == [(0, _REQUEST_CHUNK), (5_000, _REQUEST_CHUNK), (10_000, 2_000)]
    assert tuple(result[0]) == (10_000, 2_000)
