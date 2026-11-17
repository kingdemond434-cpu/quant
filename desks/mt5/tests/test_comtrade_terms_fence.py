"""UN Comtrade is BLOCKED_ON_TERMS: no organ on this tree contacts it (verdict 2026-11-14).

The licence agreement (comtradeplus.un.org/en/license-agreement, section 5) prohibits "automated
browsing or downloading" without the UN's prior written permission, binding on users "without
subscription", with no carve-out for the keyless preview API.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import shadow_institutional as si  # noqa: E402
from research import acquire_datasets as AD  # noqa: E402
from research import data_axis_miner as DAM  # noqa: E402

_REFUSED = ("https://comtradeapi.un.org/public/v1/preview/C/M/HS",
            "https://comtradeplus.un.org/", "https://comtrade.un.org",
            "https://api.stlouisfed.org/fred/series", "https://query1.finance.yahoo.com/v8/x")


def _no_network(*_a, **_k):
    raise AssertionError("a terms-refused host was contacted")


@pytest.mark.parametrize("url", _REFUSED)
def test_the_acquirer_refuses_without_contact(url: str, monkeypatch) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", _no_network)
    assert AD.terms_refusal(url)
    assert AD._fetch(url) == (None, "terms")


def test_other_hosts_are_not_caught_by_the_suffix() -> None:
    for url in ("https://data-api.ecb.europa.eu/x", "https://notcomtrade.un.org.example.com/",
                "https://www.un.org/en/", "https://api.eia.gov/v2/"):
        assert AD.terms_refusal(url) is None, url


def test_no_comtrade_endpoint_is_ever_queued(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(AD, "REGISTRY", tmp_path / "registry.json")
    monkeypatch.setattr(AD, "WORLD", tmp_path / "world")
    monkeypatch.setattr(AD, "_SEED_ENDPOINTS", (*AD._SEED_ENDPOINTS, _REFUSED[0]))
    (tmp_path / "world").mkdir()
    (tmp_path / "world" / "discoveries_1.json").write_text(
        json.dumps([{"host": "comtradeapi.un.org", "endpoints": [_REFUSED[0] + "?r=156"]}]),
        encoding="utf-8")
    queued = [u for u, _h in AD._endpoints(100_000)]
    assert queued, "the acquirer still has a frontier"
    assert not [u for u in queued if "comtrade" in u.lower()]


def test_the_shadow_sensors_are_refused_at_the_door(monkeypatch) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", _no_network)
    rows = [s for ens in si.ENSEMBLES.values() for s in ens if "comtrade" in s.url]
    assert {s.sensor_id for s in rows} == {"cn_customs_exports", "cn_iron_ore_imports"}
    guard = si.Guard(no_fetch=False)
    for s in rows:
        assert s.machine_use_allowed is False and s.licence.startswith("BLOCKED_ON_TERMS")
        got, why = guard.get(s)
        assert got is None and "BLOCKED_ON_TERMS" in why
    assert not si.check_sensors([s for ens in si.ENSEMBLES.values() for s in ens])


def test_the_axis_miner_never_probes_comtrade(monkeypatch) -> None:
    def probe(url: str) -> dict:
        assert "comtrade" not in url
        return {"reachable": True, "status": 200}
    monkeypatch.setattr(DAM, "probe", probe)
    rows = {r["id"]: r for r in DAM.build(do_probe=True)["axes"]}
    assert rows["un_comtrade"]["probe"]["why"].startswith("BLOCKED_ON_TERMS")
