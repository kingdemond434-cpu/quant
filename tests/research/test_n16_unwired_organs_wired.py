"""N16 (backlog 2026-10-13): the EXISTS-UNWIRED organs stay wired.

Each organ named in the backlog row must be (1) a leg the hourly cycle actually calls, (2) in a
department plan and a strategy layer, (3) on a budget, and (4) carried by an organ_contract
freshness row naming its artifact. And the macro state must keep reaching pf_allocator's
posterior. Any one of these going missing is the organ going dark again, so each fails here.
"""
from __future__ import annotations

import ast
import importlib.util
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
CYCLE = DESK / "research" / "hourly_cycle.py"

#: leg -> (script it runs, department, artifact its contract row names)
ORGANS: dict[str, tuple[str, str, str]] = {
    "garch_vol": ("research/garch_vol.py", "macro", "desks/mt5/reports/GARCH_VOL.json"),
    "form4_feed": ("research/form4_feed.py", "intel", "desks/mt5/reports/FORM4.json"),
    "external_federation": ("research/external_federation.py", "intel",
                            "desks/mt5/reports/EXTERNAL_FEDERATION.json"),
    "conversion_ledger": ("research/conversion_ledger.py", "meta",
                          "desks/mt5/data/conversion_ledger.json"),
    "llm_budget_census": ("research/llm_budget_census.py", "meta",
                          "desks/mt5/reports/LLM_BUDGET_CENSUS.json"),
    "fred_macro": ("scripts/collect_fred_macro.py", "macro", "data/fred_macro.json"),
}


def _load(name: str, path: Path) -> Any:
    for p in (str(ROOT), str(DESK), str(DESK / "research")):
        if p not in sys.path:
            sys.path.insert(0, p)
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _costed_legs() -> dict[str, str]:
    """leg name -> the source of the call `_costed(<leg>, ...)` makes, read from the cycle."""
    tree = ast.parse(CYCLE.read_text(encoding="utf-8"))
    src = CYCLE.read_text(encoding="utf-8")
    out: dict[str, str] = {}
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "_costed"
                and node.args and isinstance(node.args[0], ast.Constant)):
            out[str(node.args[0].value)] = ast.get_source_segment(src, node) or ""
    return out


@pytest.mark.parametrize("leg", sorted(ORGANS))
def test_every_n16_organ_is_a_costed_leg_of_the_cycle(leg: str) -> None:
    legs = _costed_legs()
    assert leg in legs, f"{leg} is no longer a _costed leg of hourly_cycle.py: it is unwired"
    script = ORGANS[leg][0]
    if script.startswith("research/"):
        assert script in legs[leg], f"leg {leg} no longer runs {script}"
        assert (DESK / script).exists()


@pytest.mark.parametrize("leg", sorted(ORGANS))
def test_every_n16_organ_has_a_department_a_layer_and_a_plan(leg: str) -> None:
    hc = _load("hourly_cycle_n16", CYCLE)
    from libs.research.layers import LEG_LAYER

    assert hc.department_of(leg) == ORGANS[leg][1]
    assert leg in LEG_LAYER
    assert leg not in hc.OWN_CLOCK_LEGS and leg not in hc.CORE_LEGS
    assert hc.in_plan(leg, f"dept:{ORGANS[leg][1]}"), f"{leg} runs under no department plan"


@pytest.mark.parametrize("leg", ["garch_vol", "form4_feed", "conversion_ledger",
                                 "llm_budget_census"])
def test_every_new_leg_has_a_budget(leg: str) -> None:
    hc = _load("hourly_cycle_n16b", CYCLE)
    assert hc.LEG_BUDGET_SEC.get(leg, 0) > 0


@pytest.mark.parametrize("leg", sorted(ORGANS))
def test_every_n16_organ_has_an_organ_contract_row(leg: str) -> None:
    oc = _load("organ_contract_n16", ROOT / "ops" / "organ_contract.py")
    dept = ORGANS[leg][1].capitalize()
    row = oc.CONTRACTS.get(f"MT5-Dept-{dept} ({leg})")
    assert row is not None, f"no organ_contract freshness row for {leg}"
    assert row[0] == ORGANS[leg][2] and 0 < row[1] <= 1560


# ---------------------------------------------------------------- macro_state -> pf_allocator

def test_macro_state_reaches_the_allocator_posterior(monkeypatch: pytest.MonkeyPatch) -> None:
    """pf_allocator's evidence carries the macro kernel's weights, sleeve by sleeve, and the
    posterior reads them (`robust_elog._posterior_mu` -> diag['macro']). If either half is cut,
    the allocator stops conditioning on the macro state without a single error."""
    from libs.portfolio import macro_state

    pfa = _load("pf_allocator_n16", DESK / "research" / "pf_allocator.py")
    dates = pd.bdate_range("2024-01-01", periods=400)
    rng = np.random.default_rng(3)
    # Sleeve does well on "today-like" days (second half) and badly on the rest.
    like = np.r_[np.zeros(200), np.ones(200)]
    rets = np.where(like > 0, 0.004, -0.004) + rng.normal(0, 0.002, len(dates))
    daily = pd.DataFrame({"EURUSD_london_TREND": rets}, index=dates)

    def fake_kernel(ds: list[str]) -> tuple[np.ndarray, dict]:
        lk = {str(d)[:10]: w for d, w in zip(dates, like + 0.05, strict=True)}
        return np.array([lk.get(str(d)[:10], 0.05) for d in ds]), {"status": "MEASURED"}

    monkeypatch.setattr(macro_state, "kernel_weights", fake_kernel)
    monkeypatch.setattr(macro_state, "now", lambda: {"labels": {}})
    ev = pfa.sleeve_evidence(daily, {}, {})
    assert ev, "sleeve_evidence produced nothing"
    w = np.asarray(ev[0].macro_w, dtype=float)
    assert w.size == len(dates), "SleeveEvidence.macro_w is empty: macro_state is unwired"
    assert np.allclose(w, like + 0.05)

    from libs.portfolio.robust_elog import _posterior_mu

    diag: dict[str, Any] = {}
    _posterior_mu(ev, np.random.default_rng(0), 1, diag=diag)
    tilt = float((diag.get("macro") or {}).get(ev[0].name, {}).get("tilt", 0.0))
    assert tilt > 0, "the regime-weighted contrast no longer tilts the posterior"


# ---------------------------------------------------------------- the organs themselves

def test_garch_vol_scores_against_ewma_on_a_garch_series(tmp_path: Path) -> None:
    pytest.importorskip("arch")
    gv = _load("garch_vol_n16", DESK / "research" / "garch_vol.py")
    rng = np.random.default_rng(7)
    n, om, a, b = 900, 2e-6, 0.10, 0.85
    r = np.zeros(n)
    h = om / (1 - a - b)
    for i in range(n):
        r[i] = np.sqrt(h) * rng.standard_normal()
        h = om + a * r[i] ** 2 + b * h
    idx = pd.date_range("2020-01-01", periods=n, freq="D", tz=UTC) + pd.Timedelta(hours=20)
    close = 100 * np.exp(np.cumsum(r))
    uni = tmp_path / "uni"
    uni.mkdir()
    pd.DataFrame({"open": close, "high": close, "low": close, "close": close},
                 index=idx.rename("time")).to_parquet(uni / "SYN_H1.parquet")
    doc = gv.run(budget_s=60, universe=uni, report=tmp_path / "G.json",
                 cursor=tmp_path / "c.json")
    row = doc["symbols"]["SYN"]
    assert doc["status"] == "MEASURED" and (tmp_path / "G.json").exists()
    assert row["verdict"] in (gv.GARCH_BEATS_EWMA, gv.EWMA_HOLDS)
    assert 0.5 < row["persistence"] < 1.0
    assert row["garch_next_day_vol"] > 0 and row["ewma_next_day_vol"] > 0


def test_garch_vol_short_history_is_unmeasured() -> None:
    gv = _load("garch_vol_n16b", DESK / "research" / "garch_vol.py")
    out = gv.score_symbol(np.random.default_rng(0).normal(0, 0.01, 100))
    assert out["verdict"] == gv.UNMEASURED and "needed" in out["why"]


_IDX = """Description:           Daily Index of EDGAR Dissemination Feed by Form Type
Form Type   Company Name                                                  CIK         Date Filed  File Name
---------------------------------------------------------------------------------------------------------------------------------------------
4           APPLE INC                                                     320193      20261102    edgar/data/320193/0001-26-000001.txt
4           COOK TIMOTHY D                                                1214156     20261102    edgar/data/320193/0001-26-000001.txt
4/A         APPLE INC                                                     320193      20261102    edgar/data/320193/0001-26-000002.txt
10-K        OTHER CO                                                      999         20261102    edgar/data/999/x.txt
"""


def _filing(name: str, title: str, code: str, day: str, accept: str) -> str:
    return f"""<SEC-HEADER>
<ACCEPTANCE-DATETIME>{accept}
</SEC-HEADER>
<XML>
<ownershipDocument>
 <issuer><issuerCik>0000320193</issuerCik><issuerTradingSymbol>AAPL</issuerTradingSymbol></issuer>
 <reportingOwner><reportingOwnerId><rptOwnerName>{name}</rptOwnerName></reportingOwnerId>
  <reportingOwnerRelationship><isOfficer>1</isOfficer><officerTitle>{title}</officerTitle>
  </reportingOwnerRelationship></reportingOwner>
 <nonDerivativeTable><nonDerivativeTransaction>
  <transactionDate><value>{day}</value></transactionDate>
  <transactionCoding><transactionCode>{code}</transactionCode></transactionCoding>
  <transactionAmounts><transactionShares><value>1000</value></transactionShares>
   <transactionPricePerShare><value>200</value></transactionPricePerShare>
   <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
  </transactionAmounts>
  <postTransactionAmounts><sharesOwnedFollowingTransaction><value>5000</value>
  </sharesOwnedFollowingTransaction></postTransactionAmounts>
 </nonDerivativeTransaction></nonDerivativeTable>
</ownershipDocument>
</XML>"""


def test_form4_parsers_keep_only_form_4_and_date_on_acceptance() -> None:
    f4 = _load("form4_feed_n16", DESK / "research" / "form4_feed.py")
    rows = f4.parse_index(_IDX)
    assert [r["cik"] for r in rows] == [320193, 1214156]
    tx = f4.parse_filing(_filing("COOK TIMOTHY D", "CEO", "P", "2026-10-30", "20261102163000"))
    assert len(tx) == 1 and tx[0]["code"] == "P" and tx[0]["issuer_cik"] == 320193
    # Acceptance is US Eastern; the UTC stamp is never EARLIER than the filing was public.
    assert datetime.fromisoformat(tx[0]["filed_at"]) >= datetime(2026, 11, 2, 20, 30, tzinfo=UTC)
    hostile = _filing("X", "CEO", "P", "2026-10-30", "20261102163000").replace(
        "<issuer>", "<!ENTITY a 'b'><issuer>")
    assert f4.parse_filing(hostile) == []
    assert f4.ticker_stems("AAPL.24H") == ["AAPL"] and f4.ticker_stems("AAPLUSD")[-1] == "AAPL"


def test_form4_without_a_user_agent_is_unmeasured_and_fetches_nothing(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    f4 = _load("form4_feed_n16b", DESK / "research" / "form4_feed.py")
    monkeypatch.delenv("QUANT_EDGAR_UA", raising=False)
    monkeypatch.setattr(f4, "REPORT", tmp_path / "FORM4.json")
    doc = f4.run(budget_s=5)
    assert doc["status"] == "UNMEASURED" and "QUANT_EDGAR_UA" in doc["why"]
    assert (tmp_path / "FORM4.json").exists()


def test_form4_end_to_end_builds_a_cluster_from_two_insiders(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    f4 = _load("form4_feed_n16c", DESK / "research" / "form4_feed.py")
    for attr, name in (("DATA", ""), ("TXNS", "t.jsonl"), ("CLUSTERS", "c.json"),
                       ("CURSOR", "cur.json"), ("TICKERS_CACHE", "tk.json"),
                       ("REPORT", "FORM4.json")):
        monkeypatch.setattr(f4, attr, tmp_path / name if name else tmp_path)
    idx = ("4  APPLE INC  320193  20261102  edgar/data/320193/a.txt\n"
           "4  APPLE INC  320193  20261102  edgar/data/320193/b.txt\n")
    pages = {
        "https://www.sec.gov/robots.txt": b"User-agent: *\nDisallow: /cgi-bin/\n",
        f4.TICKERS_URL: b'{"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple"}}',
        "https://www.sec.gov/Archives/edgar/daily-index/2026/QTR4/form.20261102.idx":
            idx.encode(),
        "https://www.sec.gov/Archives/edgar/data/320193/a.txt":
            _filing("COOK TIMOTHY D", "CEO", "P", "2026-10-30", "20261102163000").encode(),
        "https://www.sec.gov/Archives/edgar/data/320193/b.txt":
            _filing("PAREKH KEVAN", "CFO", "P", "2026-10-31", "20261102170000").encode(),
    }
    monkeypatch.setattr(f4, "BACKFILL_DAYS", 2)
    doc = f4.run(budget_s=30, fetch=pages.get, today=date(2026, 11, 3), symbols=["AAPL.24H"])
    assert doc["status"] == "MEASURED" and doc["filings_fetched"] == 2
    assert doc["clusters"] == 1 and doc["top_clusters"][0]["symbol"] == "AAPL.24H"
    assert doc["cursor_day"] == "2026-11-02"
    # A second pass re-reads nothing it already holds.
    doc2 = f4.run(budget_s=30, fetch=pages.get, today=date(2026, 11, 3), symbols=["AAPL.24H"])
    assert doc2["filings_fetched"] == 0 and doc2["clusters"] == 1
