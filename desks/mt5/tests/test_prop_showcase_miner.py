"""Prop-firm payout showcases -> claims -> charged cells (BACKLOG row 38). No network."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import prop_showcase_miner as psm  # noqa: E402

STORY = ("How a gold scalper secured $50,333 in 2 weeks. I trade XAUUSD at the London open, "
         "waiting for the breakout of the Asian range, risk-to-reward 1:2, holding for minutes. "
         "I also take pullbacks on NAS100 at the New York open.")


def test_extract_reads_instrument_session_style_rr_payout() -> None:
    c = psm.extract(STORY)
    assert {"gold", "nasdaq"} <= set(c["instruments"])
    assert {"london", "new_york", "asia"} <= set(c["sessions"])
    assert {"scalp", "breakout", "pullback"} <= set(c["styles"])
    assert c["rr"] == [2.0]
    assert c["payout_usd_max"] == 50333
    assert c["horizon"] == "intraday"


def test_extract_says_not_stated_rather_than_no() -> None:
    c = psm.extract("Congratulations to our trader on the payout!")
    assert c["instruments"] == [] and c["styles"] == [] and c["rr"] == []


def test_cells_map_to_registered_families_on_broker_stamp_hours() -> None:
    from mt5desk import families
    claim = {"firm": "ftmo", "url": "u1", **psm.extract(STORY)}
    out = psm.cells([claim], {"XAUUSD", "NAS100"})
    assert out, "a story with instrument + style must build cells"
    for c in out:
        assert callable(getattr(families, f"family_{c['family']}")), c["family"]
    srb = [c for c in out if c["family"] == "session_range_breakout" and c["symbol"] == "XAUUSD"]
    # London open is stamp 10 on NY+7: pre-open range 7-10 broken at 10
    assert any(c["params"]["range_start"] == 7 and c["params"]["signal_at"] == 10 for c in srb)
    assert all(c["params"].get("rr") == 2.0 for c in srb)


def test_support_counts_distinct_stories_and_firms() -> None:
    a = {"firm": "ftmo", "url": "u1", **psm.extract(STORY)}
    b = {"firm": "the5ers", "url": "u2", **psm.extract(STORY)}
    top = psm.cells([a, b, dict(a)], {"XAUUSD", "NAS100"})[0]
    assert top["support"] == 2 and top["firms"] == ["ftmo", "the5ers"]


def test_symbol_without_bars_builds_nothing() -> None:
    claim = {"firm": "ftmo", "url": "u1", **psm.extract(STORY)}
    assert psm.cells([claim], set()) == []


def test_story_slug_filter_keeps_stories_and_drops_rules_pages() -> None:
    urls = ["https://ftmo.com/en/blog/how-a-gold-scalper-secured-50333-in-2-weeks/",
            "https://ftmo.com/en/blog/trading-rules-update/",
            "https://ftmo.com/en/faq/payout/"]
    assert psm._story_urls(urls, ("/en/blog/",)) == [urls[0]]


class _FakeFetcher(psm._Fetcher):
    def __init__(self, pages: dict[str, tuple[int, bytes]]) -> None:
        super().__init__(delay_s=0.0)
        self.pages = pages
        self.hits: list[str] = []

    def _raw(self, url: str, limit: int = 3_000_000) -> tuple[int, bytes]:
        self.hits.append(url)
        return self.pages.get(url, (404, b""))


def _redirect(monkeypatch: pytest.MonkeyPatch, tmp: Path) -> None:
    monkeypatch.setattr(psm, "INTEL", tmp / "intel")
    monkeypatch.setattr(psm, "SEEN", tmp / "intel" / "seen.json")
    monkeypatch.setattr(psm, "CLAIMS", tmp / "claims.jsonl")


def test_harvest_respects_robots_and_never_crosses_walls(tmp_path: Path,
                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    _redirect(monkeypatch, tmp_path)
    story = "https://a.example/blog/how-a-gold-trader-earned-big/"
    banned = "https://a.example/blog/private-trader-story/"
    walled = "https://a.example/blog/walled-trader-story/"
    sm = (f"<urlset><url><loc>{story}</loc></url><url><loc>{banned}</loc></url>"
          f"<url><loc>{walled}</loc></url></urlset>").encode()
    page = (f"<html><head><title>Gold trader</title><meta property='article:published_time' "
            f"content=\"2026-05-01T00:00:00+00:00\"></head><body>{STORY}</body></html>").encode()
    f = _FakeFetcher({
        "https://a.example/robots.txt": (200, b"User-agent: *\nDisallow: /blog/private\n"
                                              b"Sitemap: https://a.example/sm.xml\n"),
        "https://a.example/sm.xml": (200, sm),
        story: (200, page),
        walled: (403, b""),
        # a host whose robots.txt is walled is never fetched at all
        "https://b.example/robots.txt": (403, b""),
    })
    rep = psm.harvest(f, {"a": {"home": "https://a.example", "paths": ("/blog/",)},
                          "b": {"home": "https://b.example", "paths": ("/blog/",)}})
    assert banned not in f.hits
    assert not any(u.startswith("https://b.example/") and not u.endswith("robots.txt")
                   for u in f.hits)
    assert f.log.get("walled_403") == 1 and f.log.get("robots_refused") == 1
    claims = psm.load_claims(tmp_path / "claims.jsonl")
    assert len(claims) == 1 and claims[0]["knowable_from"].startswith("2026-05-01")
    assert rep["by_firm"]["a"]["claims_with_mechanism"] == 1
    # raw text is vaulted under the gitignored intel dir, never in the claims file
    assert list((tmp_path / "intel").glob("*.txt.gz"))
    assert "risk-to-reward" not in (tmp_path / "claims.jsonl").read_text()
    # a second pass does not re-read seen stories
    f.hits.clear()
    psm.harvest(f, {"a": {"home": "https://a.example", "paths": ("/blog/",)}})
    assert story not in f.hits


def _bars(n: int = 4000) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    idx = pd.date_range("2025-01-01", periods=n, freq="h", tz="UTC")
    c = 2000 + np.cumsum(rng.normal(0, 2, n))
    return pd.DataFrame({"open": c, "high": c + 2, "low": c - 2, "close": c,
                         "spread": 20.0}, index=idx)


def test_every_screened_cell_is_charged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from research import alt_proxies as ap
    from research import proposer_common as pc
    uni = tmp_path / "uni"
    uni.mkdir()
    (uni / "XAUUSD_H1.parquet").write_bytes(b"")
    monkeypatch.setattr(pc, "UNI", uni)
    monkeypatch.setattr(pc, "bars", lambda s: _bars())
    monkeypatch.setattr(pc, "cost_frac", lambda *a, **k: 0.0002)
    charged: list[tuple] = []
    monkeypatch.setattr(ap, "_donate", lambda *a, **k: charged.append(a) or {"donated": 0})
    claim = {"firm": "ftmo", "url": "u1", **psm.extract(STORY)}
    rep = psm.propose([claim], budget_s=120, write=True)
    assert rep["tests_run"] > 0 and rep["cells_built"] >= rep["tests_run"]
    assert charged and charged[0][1] == psm.SOURCE and charged[0][3] == rep["tests_run"]


def test_daily_cycle_and_component_declare_the_producer() -> None:
    src = (DESK / "research" / "daily_cycle.py").read_text("utf-8")
    assert '"prop_showcase_miner"' in src and callable(psm.run)
    from desks.mt5.ops.components import explicit_specs
    spec = next(s for s in explicit_specs() if s.component_id == "daily:proposers:prop_showcase")
    assert spec.outputs[0] == "desks/mt5/reports/PROP_SHOWCASE.json"
    assert spec.restart_action == "restart:task:MT5-Daily"


def test_source_is_external_in_the_registry() -> None:
    from libs.moat import registry as reg
    assert reg.origin_of(psm.SOURCE) == "EXTERNAL"


def test_raw_vault_is_gitignored() -> None:
    gi = (ROOT / ".gitignore").read_text("utf-8")
    assert "desks/mt5/data/intelligence/prop_showcase/" in gi
    assert json.dumps(psm.SELECTION_PRIORS)  # serialisable for the candidate evidence


def test_own_yield_reads_census_rows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "py.json").write_text(json.dumps({"producers": [
        {"producer": "prop_showcase_miner", "verdict": "PRODUCING"}]}))
    (tmp_path / "pc.json").write_text(json.dumps({"certificates": {"prop_showcase_story": 3},
                                                   "forward": {"other": 1}}))
    monkeypatch.setattr(psm, "PRODUCER_YIELD", tmp_path / "py.json")
    monkeypatch.setattr(psm, "PRODUCTIVITY_CENSUS", tmp_path / "pc.json")
    y = psm._own_yield()
    assert y["producer_yield"]["verdict"] == "PRODUCING"
    assert y["census"] == {"certificates/prop_showcase_story": 3}
