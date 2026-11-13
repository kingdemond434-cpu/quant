"""datahub_feeds: contracts register, OpenBB is terms- and robots-gated, absence is UNMEASURED."""
from __future__ import annotations

import pytest

from libs.data import datahub_feeds as F


def test_live_hub_extends_the_desk_hub_with_the_free_terminal_contracts() -> None:
    names = set(F.live_hub().contracts())
    assert {"bars.h1", "terms.swap_diff", "calendar.events"} <= names
    assert {"tanker.port_calls", "tanker.floating_storage", "ais.positions",
            "macro.fred_series", "cot.net_spec", "macro.oecd_cli"} <= names


def test_refused_or_unread_providers_never_reach_openbb() -> None:
    for p in ("imf", "cboe", "finra", "nasdaq", "tmx", "yfinance", "tiingo", "fmp",
              "intrinio", "polygon", "ecb", "bls", "jodi", "famafrench"):
        with pytest.raises(PermissionError):
            F.openbb_call(p, "economy.cpi")
    assert set(F.OPENBB_UPSTREAM) == set(F.OPENBB_CONFIRMED)


def test_robots_refusal_blocks_openbb_before_import(monkeypatch) -> None:
    monkeypatch.setattr(F, "robots_refusal", lambda url: "robots.txt HTTP 503")
    with pytest.raises(PermissionError, match="503"):
        F.openbb_call("oecd", "economy.composite_leading_indicator")


@pytest.mark.parametrize("code,expect_allowed", [(404, True), (410, True), (401, False),
                                                 (403, False), (429, False), (451, False),
                                                 (500, False), (503, False)])
def test_robots_status_codes_fail_closed(monkeypatch, code: int, expect_allowed: bool) -> None:
    import urllib.error
    import urllib.request

    def fake(*_a, **_k):
        raise urllib.error.HTTPError("u", code, "x", {}, None)  # type: ignore[arg-type]

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    F._ROBOTS.clear()
    got = F.robots_refusal(f"https://example.test/p{code}")
    assert (got is None) is expect_allowed


def test_an_absent_ais_series_is_unmeasured_never_zero(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(F, "AIS_SERIES", tmp_path / "missing.parquet")
    monkeypatch.setattr(F, "AIS_LAKE", tmp_path)
    hub = F.live_hub()
    for name in ("tanker.port_calls", "tanker.floating_storage", "ais.positions"):
        with pytest.raises(LookupError):
            hub.get(name)
