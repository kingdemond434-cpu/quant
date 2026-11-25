"""The route probe never contacts SPDR GLD: its terms refuse automated access (2026-11-17).

No network: urlopen is replaced by a function that fails the test if it is ever called.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import check_source_routes as csr  # noqa: E402


@pytest.fixture()
def no_network(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    asked: list[str] = []

    def urlopen(req: Any, *_a: Any, **_k: Any) -> Any:
        asked.append(getattr(req, "full_url", str(req)))
        raise AssertionError("a request was made to a terms-REFUSED route")

    monkeypatch.setattr(csr.urllib.request, "urlopen", urlopen)
    return asked


@pytest.mark.parametrize("url", [
    "https://www.spdrgoldshares.com/usa/assets/uploads/GLD_US_holdings.xlsx",
    "https://spdrgoldshares.com/assets/dynamic/GLD/GLD_US_archive_EN.csv",
])
def test_spdr_gold_shares_is_refused_by_host_and_never_probed(url: str,
                                                            no_network: list[str]) -> None:
    # The fence is the shared host list: every caller (route probe, canary, crawler, robots
    # read) is refused before it builds a request, so the probe keeps no GLD route at all.
    assert csr.refusal(url) and "non-commercial" in csr.refusal(url)
    assert not [r for r in csr.ROUTES if "spdrgoldshares" in str(r.get("url"))]
    out = csr.probe({"name": "gld_holdings", "url": url, "expect": "binary"})
    assert no_network == []
    assert out["status"] == "BLOCKED_ON_TERMS"
    assert out["missed_growth"]["mechanism"] == "gld_holdings_terms_refusal"


def test_any_route_marked_refused_is_never_probed(no_network: list[str]) -> None:
    out = csr.probe({"name": "x", "url": "https://example.test/a.json", "expect": "json",
                     "terms": "refused"})
    assert no_network == [] and out["status"] == "BLOCKED_ON_TERMS"
