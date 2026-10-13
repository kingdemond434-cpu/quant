"""THE FIVE LAB ROLES: verdicts rank the proposers, and nothing a role makes has authority.

  * the verdict loop credits certified cells to the lab and model that proposed them and ranks on
    certified k_eff per call, so a lab that floods the docket with dead cells ranks last;
  * the evidence-start map only ever moves LATER and skips cells whose guard is per-document;
  * missed moves are the largest recent moves on symbols no LIVE sleeve trades;
  * code-lab source outside the whitelist is refused before it runs; a feature that reads the
    future fails the causality test; a passing one becomes a lake series and an exact cell;
  * scouted sources behind a login, paywall, robots bar or challenge never join the registry;
  * the sleeve red team is advisory, typed, and names the live sleeves it did not attack.
"""
from __future__ import annotations

import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import llm_lab as lab  # noqa: E402
import llm_lab_roles as roles  # noqa: E402

CAUSAL = ("def feature(df):\n"
          "    r = np.log(df['close']).diff()\n"
          "    return r.rolling(24).sum() / r.rolling(240).std()\n")
PEEKS = ("def feature(df):\n"
         "    return np.log(df['close']).diff().shift(-1)\n")


@pytest.fixture()
def tmp_roles(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for name in ("CREDIT", "EVIDENCE_START", "MISSED", "DAILY", "CODE_LEDGER", "SCOUTED",
                 "RED_TEAM"):
        monkeypatch.setattr(roles, name, tmp_path / "llm_lab" / f"{name.lower()}.json")
    for name in ("CODE_DIR", "SERIES_DIR", "BARS_DIR", "DONATE_DIR"):
        monkeypatch.setattr(roles, name, tmp_path / name.lower())
    monkeypatch.setattr(roles, "SLEEVES", tmp_path / "sleeves.json")
    monkeypatch.setattr(lab, "MODEL_CUTOFFS", tmp_path / "cutoffs.json")
    return tmp_path


def _bars(path: Path, sym: str, shock_day: int | None = None, n_days: int = 120) -> None:
    import numpy as np
    import pandas as pd
    rng = np.random.default_rng(abs(hash(sym)) % 2**32)
    n = n_days * 24
    r = rng.normal(0, 0.0008, n)
    if shock_day is not None:
        r[shock_day * 24: shock_day * 24 + 6] += 0.01
    idx = pd.date_range("2026-06-01", periods=n, freq="h", tz="UTC")
    c = 100 * np.exp(np.cumsum(r))
    path.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"open": c, "high": c * 1.0005, "low": c * 0.9995, "close": c,
                  "volume": 1.0}, index=idx).to_parquet(path / f"{sym}_H1.parquet")


def _donations(d: Path, rows: list[dict[str, Any]]) -> None:
    d.mkdir(parents=True, exist_ok=True)
    (d / "discoveries_x.json").write_text(json.dumps({"discoveries": rows}))


def test_verdicts_rank_labs_by_certified_keff_per_call(tmp_roles: Path) -> None:
    _donations(roles.DONATE_DIR, [
        {"cell_id": "a1", "lab": "K", "model": "openrouter_free:m1", "symbol": "EURUSD",
         "family": "carry"},
        *[{"cell_id": f"b{i}", "lab": "A", "model": "openrouter_free:m2", "symbol": "GBPUSD",
           "family": "formula"} for i in range(3)]])
    ledger = tmp_roles / "verdicts.jsonl"
    ledger.write_text("\n".join(json.dumps(r) for r in [
        {"cell": "a1", "passed": True},
        *[{"cell": f"b{i}", "passed": False, "terminal_gate": "deflated_sharpe"}
          for i in range(3)],
        {"cell": "not_ours", "passed": True}]) + "\n")
    asks = [("K", "openrouter_free:m1")] * 2 + [("A", "openrouter_free:m2")] * 6
    doc = roles.verdict_loop(ledger, roles.DONATE_DIR, asks)
    k, a = doc["labs"]["K"], doc["labs"]["A"]
    assert k["certified"] == 1 and k["keff"] > 0 and a["certified"] == 0
    assert a["gates"] == {"deflated_sharpe": 3} and doc["judged_cells"] == 4
    assert k["keff_per_call"] > a["keff_per_call"] == 0.0
    assert any("died at deflated_sharpe" in ln for ln in doc["feedback"]["A"])
    assert "novelty counts are NOT a ranking input" in doc["ranking_rule"]
    rng = random.Random(1)  # noqa: S311 - not crypto
    first = [roles.thompson(doc["labs"], ["A", "K"], rng)[0] for _ in range(300)]
    assert first.count("K") > 200, "the lab that certified ranks first most of the time"
    # Calls accumulate: a second pass with no new verdicts lowers A's draw, never raises it.
    again = roles.verdict_loop(ledger, roles.DONATE_DIR, [("A", "openrouter_free:m2")] * 4)
    assert again["labs"]["A"]["calls"] == 10 and again["labs"]["K"]["calls"] == 2


def test_assign_model_and_lab_order_spend_against_the_credit(tmp_roles: Path) -> None:
    reg = {"p:good": {"status": "REGISTERED", "novel": 0},
           "p:noisy": {"status": "REGISTERED", "novel": 500, "replies": 500}}
    labs = {x.key: {"calls": 40, "keff": 0.0} for x in lab.INVENTORS}
    labs["B"] = {"calls": 40, "keff": 12.0}
    credit = {"models": {"p:good": {"calls": 10, "keff": 3.0}, "p:noisy": {"calls": 500}},
              "labs": labs}
    rng = random.Random(3)  # noqa: S311 - not crypto
    picks = [lab.assign_model(reg, rng, set(), credit) for _ in range(200)]
    assert picks.count("p:good") > 190, "novel-cell volume no longer buys a model its rank"
    order = [x.key for x in lab.prioritised(rng, credit)]
    assert order[:4] == list(lab.PRIORITY_LABS) and order[4] == "B"
    assert sorted(order) == sorted(x.key for x in lab.INVENTORS)


def test_evidence_start_only_moves_later(tmp_roles: Path) -> None:
    rows = [{"cell_id": "c1", "symbol": "EURUSD", "family": "formula", "params": {"expr": "x"},
             "lookahead_guard": {"evidence_from": "2026-10-13"}},
            {"cell_id": "c2", "lookahead_guard": {"evidence_from": "per-document"}},
            {"cell_id": "c3", "lookahead_guard": {"evidence_from": "1900-01-01"}}]
    assert roles.record_evidence_start(rows) == 1
    roles.record_evidence_start([{"cell_id": "c1",
                                  "lookahead_guard": {"evidence_from": "2025-01-01"}}])
    assert json.loads(roles.EVIDENCE_START.read_text()) == {"c1": {
        "from": "2026-10-13", "sym": "EURUSD", "family": "formula", "params": {"expr": "x"}}}


def test_missed_moves_skip_symbols_a_live_sleeve_trades(tmp_roles: Path) -> None:
    _bars(roles.BARS_DIR, "USDJPY", shock_day=118)
    _bars(roles.BARS_DIR, "XAUUSD", shock_day=118)
    _bars(roles.BARS_DIR, "EURUSD")
    roles.SLEEVES.write_text(json.dumps({"sleeves": [{"name": "g", "symbol": "XAUUSD",
                                                      "status": "LIVE"}]}))
    moves = roles.missed_moves({"USDJPY": "forex", "XAUUSD": "metals", "EURUSD": "forex"})
    assert moves and moves[0]["symbol"] == "USDJPY" and moves[0]["z"] > 4
    assert all(m["symbol"] != "XAUUSD" for m in moves)


def test_code_lab_whitelist_refuses_before_running() -> None:
    assert roles.code_refusal(CAUSAL) == ""
    bad = {
        "import os\ndef feature(df):\n    return df['close']\n": "import",
        "def feature(df):\n    return open('x').read()\n": "not",
        "def feature(df):\n    return df.__class__\n": "__class__",
        "def feature(df):\n    df.to_csv('C:/x.csv')\n    return df['close']\n": "to_csv",
        "def feature(df):\n    return getattr(df, 'close')\n": "getattr",
        "def helper():\n    pass\ndef feature(df):\n    return df['close']\n": "exactly one",
    }
    for src, needle in bad.items():
        assert needle in roles.code_refusal(src), src


@pytest.mark.parametrize("src", [
    # the auditor's measured escapes (2026-10-13): attribute CHAINS that never name a banned word
    "def feature(df):\n    pd.io.common.os.system('id')\n    return df['close']\n",
    "def feature(df):\n    np.ctypeslib.ctypes.CDLL(None)\n    return df['close']\n",
    "def feature(df):\n    np.genfromtxt('secrets')\n    return df['close']\n",
    "def feature(df):\n    np.lib.format.open_memmap('x', mode='w+')\n    return df['close']\n",
    "def feature(df):\n    x = df.close.values.tofile\n    return df['close']\n",
    "def feature(df):\n    return pd.read_csv('x')\n",
    "def feature(df):\n    return df.pipe(print)\n",
    "def feature(df):\n    s = __builtins__\n    return df['close']\n",
])
def test_attribute_chains_cannot_reach_the_os(src: str) -> None:
    assert roles.code_refusal(src)


def test_role_r_stands_down_without_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QUANT_LLM_CODE_LAB", raising=False)
    monkeypatch.setattr(roles, "_OS_NAME", "nt")
    assert roles.code_lab_isolated().startswith("DISABLED_NO_ISOLATION")
    dons, tally = roles.code_lab(Path("absent.json"), {}, max_items=3, deadline=1e18)
    assert dons == [] and tally["state"].startswith("DISABLED")
    monkeypatch.setenv("QUANT_LLM_CODE_LAB", "1")
    assert roles.code_lab_isolated() == ""


def test_sandbox_runs_the_causality_test() -> None:
    ok = roles.sandbox(CAUSAL)
    assert ok["ok"] and ok["causal"]
    peek = roles.sandbox(PEEKS)
    assert not peek["ok"] and "causal" in peek["why"]
    spin = roles.sandbox("def feature(df):\n    while True:\n        pass\n", timeout=4)
    assert not spin["ok"] and "timeout" in spin["why"]


@dataclass
class _Reply:
    text: str
    provider: str = "openrouter_free"
    model: str = "m:free"


def test_code_lab_turns_rule_debt_into_an_exact_cell(tmp_roles: Path) -> None:
    _bars(roles.BARS_DIR, "EURUSD")
    debt = tmp_roles / "debt.json"
    debt.write_text(json.dumps({"rows": {"d1": {
        "id": "d1", "state": "OPEN", "blockers": ["NEEDS_EXACT_RULE_EXTRACTION"],
        "first_seen": "2026-10-01", "payload": {
            "mechanism": "exhausted trend after a day of one-way flow", "falsifier": "no reversal",
            "symbols": ["EURUSD"], "needs": ["a one-day flow imbalance rule"]}}}}))

    def chat(system: str, user: str, **kw: Any) -> _Reply:
        return _Reply(json.dumps({"code": CAUSAL, "side_when_high": -1, "why": "24h z"}))

    dons, tally = roles.code_lab(debt, {"EURUSD": "forex"}, max_items=3, deadline=1e12,
                                 chat=chat)
    assert tally == {"asked": 1, "converted": 1} and len(dons) == 1
    d = dons[0]
    assert d["family"] == "exogenous_conditioner" and d["params"]["side_when_high"] == -1
    assert d["lookahead_guard"]["evidence_from"] == lab._now()[:10]
    assert json.loads(debt.read_text())["rows"]["d1"]["state"] == "RESOLVED"
    from mt5desk import family_exogenous_conditioner as fec
    s = fec.conditioner(d["params"]["source"], "value", "level_z", root=roles.SERIES_DIR)
    assert s is not None and len(s) > 30
    import miner_candidate_compiler as mc
    cands, disp = mc.compile_row("llm_lab", d, {"EURUSD"})
    assert disp == "EXACT_RECIPE" and cands[0]["lookahead_guard"] == d["lookahead_guard"]


def test_source_scout_rows_are_filtered_and_probed_politely() -> None:
    text = "\n".join(json.dumps(r) for r in [
        {"name": "ok", "url": "https://stat.example.go.jp/data.csv", "targets": ["USDJPY"],
         "expect": "csv"},
        {"name": "login", "url": "https://x.example/login/data", "targets": ["USDJPY"]},
        {"name": "known", "url": "https://known.example/a", "targets": ["USDJPY"]},
        {"name": "no target", "url": "https://y.example/a", "targets": ["BTCUSDT"]}])
    rows, why = roles.scout_rows(text, ("ja", "Japan"), {"known.example"}, {"USDJPY": "forex"})
    assert [r["name"] for r in rows] == ["ok"] and rows[0]["plane"] == "llm_scout"
    assert why == {"login or paywall path": 1, "host already in the registry": 1,
                   "no MT5 target": 1}
    pages = {"https://stat.example.go.jp/robots.txt": (404, b"")}
    for body, code, want in [(b"1,2,3", 200, "REACHABLE"), (b"", 403, "GATED:HTTP_403"),
                             (b"<div>captcha</div>", 200, "GATED:CHALLENGE")]:
        pages["https://stat.example.go.jp/data.csv"] = (code, body)
        assert roles.probe(rows[0], get=lambda u: pages.get(u, (404, b"")),
                           resolve=_public) == want
    pages["https://stat.example.go.jp/robots.txt"] = (200, b"User-agent: *\nDisallow: /")
    assert roles.probe(rows[0], get=lambda u: pages.get(u, (404, b"")),
                       resolve=_public) == "ROBOTS_DISALLOW"


def _public(host: str) -> list[str]:
    return ["93.184.216.34"]


@pytest.mark.parametrize(("url", "addrs"), [
    ("http://127.0.0.1:11434/api/pull", ["127.0.0.1"]),
    ("http://ollama.local/", ["192.168.1.5"]),
    ("http://metadata/", ["169.254.169.254"]),
    ("http://[::1]/", ["::1"]),
    ("http://10.0.0.1/", ["10.0.0.1"]),
    ("file:///etc/passwd", ["93.184.216.34"]),
    ("https://user:pw@example.com/", ["93.184.216.34"]),
    ("https://rebinds.example/", ["93.184.216.34", "127.0.0.1"]),
])
def test_scout_never_fetches_a_private_host(url: str, addrs: list[str]) -> None:
    """Audit must-fix 8: a model-named URL may not reach loopback, the LAN or link-local."""
    from libs.ops.public_host import public_url
    assert public_url(url, resolve=lambda h: addrs)

    def never(u: str) -> tuple[int, bytes]:
        raise AssertionError("fetched a refused URL")
    assert roles.probe({"url": url}, get=never, resolve=lambda h: addrs).startswith("REFUSED")
    assert public_url("https://www.boj.or.jp/en/", resolve=_public) == ""


def test_collector_reads_only_reachable_scouted_rows() -> None:
    src = (_DESK / "research" / "asia_collector.py").read_text(encoding="utf-8")
    assert 'SCOUTED = BASE / "data" / "llm_lab" / "scouted_sources.json"' in src
    assert 's.get("probe") == "REACHABLE"' in src
    assert "not public_url(" in src


def test_sleeve_red_team_is_advisory_and_typed() -> None:
    sleeves = [{"name": "gold_asia", "symbol": "XAUUSD", "family": "f", "status": "LIVE"},
               {"name": "audchf_gap", "symbol": "AUDCHF", "family": "g", "status": "LIVE"}]

    def chat(system: str, user: str, **kw: Any) -> _Reply:
        return _Reply("\n".join(json.dumps(r) for r in [
            {"sleeve": "gold_asia", "failure_mode": "crowding", "argument": "a" * 40,
             "observable": "spread at 04:00", "test": "spread z", "horizon_days": 30},
            {"sleeve": "gold_asia", "failure_mode": "bad_luck", "argument": "b" * 40},
            {"sleeve": "ghost", "failure_mode": "crowding", "argument": "c" * 40}]))

    doc, calls = roles.red_team(sleeves, chat=chat, deadline=1e12, max_calls=4)
    assert calls == 1 and doc["advisory"] is True and "NONE" in doc["authority"]
    assert doc["attacked"] == ["gold_asia"] and doc["unattacked"] == ["audchf_gap"]
    assert doc["modes"] == {"crowding": 1}


def _cov(models: dict, pass_cov: dict, tallies: dict | None = None) -> dict:
    tallies = tallies if tallies is not None else {"A": {"asked": 1, "proposals": 2}}
    roles._write_json(roles.DAILY, {"Q": lab._now()[:10], "T": lab._now()[:10]})
    return roles.coverage_report(models, pass_cov, tallies, {"R": {}, "S": {}}, {"docs": 3},
                                 {}, {}, seat_on=True, dry_run=False)


def test_coverage_is_red_for_every_model_or_lab_that_did_not_produce(tmp_roles: Path) -> None:
    models = {"openrouter_free:a": {"status": "REGISTERED"},
              "openrouter_free:b": {"status": "REGISTERED"},
              "openrouter_free:c": {"status": "REGISTERED"},
              "openrouter_free:gone": {"status": "DELISTED"}}
    doc = _cov(models, {"openrouter_free:a": {"asked": 1, "answered": 1},
                        "openrouter_free:b": {"asked": 1, "answered": 0,
                                              "fell_through_to": ["groq:x"]}},
               {"A": {"asked": 1, "proposals": 2}, "B": {"asked": 1, "proposals": 0}})
    assert doc["verdict"] == "RED" and doc["models_available"] == 3
    assert doc["models_answered"] == 1
    assert set(doc["red"]) == {"model openrouter_free:b: FELL_THROUGH",
                               "model openrouter_free:c: NOT_ASKED", "lab B: SILENT"}
    assert doc["models"]["openrouter_free:gone"]["state_this_cycle"] == "DELISTED"
    green = _cov({"openrouter_free:a": {"status": "REGISTERED"}},
                 {"openrouter_free:a": {"asked": 1, "answered": 1}})
    assert green["verdict"] == "GREEN" and not green["red"]


def test_the_fence_fails_on_red_stale_or_absent_reports(tmp_path: Path) -> None:
    import llm_coverage_fence as fence
    p = tmp_path / "LLM_COVERAGE.json"
    assert fence.verdict(p)[0] == 1
    now = lab._now()
    p.write_text(json.dumps({"generated_at": now, "verdict": "GREEN", "models_available": 2,
                             "models_answered": 2, "red": []}))
    assert fence.verdict(p) == (0, "GREEN: 2/2 models answered; 0 gap(s)")
    p.write_text(json.dumps({"generated_at": now, "verdict": "RED", "red": ["lab B: SILENT"]}))
    code, text = fence.verdict(p)
    assert code == 1 and "lab B: SILENT" in text
    p.write_text(json.dumps({"generated_at": "2026-01-01T00:00:00+00:00", "verdict": "GREEN"}))
    assert "stale" in fence.verdict(p)[1]


def test_the_coverage_leg_is_wired() -> None:
    src = (_DESK / "research" / "hourly_cycle.py").read_text(encoding="utf-8")
    assert '"llm_coverage", "research/llm_coverage_fence.py"' in src
    from libs.research import layers
    assert "llm_coverage" in str(layers.__dict__)


def test_the_local_model_installer_checks_what_it_runs() -> None:
    """Audit must-fix 9: a pinned version, Authenticode on every binary, models pinned by digest,
    a locked ACL and a LOCAL SERVICE server (no PowerShell here, so the text is the contract)."""
    src = (_DESK / "scripts" / "install_local_llm.ps1").read_text(encoding="utf-8")
    assert "--version $ver" in src and "install.lock.json" in src
    assert src.count("Assert-Signed $") >= 2 and "Get-AuthenticodeSignature" in src
    assert "NT AUTHORITY\\LOCALSERVICE" in src and "-UserId 'SYSTEM'" not in src
    assert "/inheritance:r" in src and "S-1-5-19" in src
    assert "pinned ${pinned}" in src and "& $ollama rm $m" in src
    assert "6 GB floor" in src


def test_a_scouted_source_cannot_redirect_or_resolve_to_a_private_host() -> None:
    """Audit should-fix on #332: the collector re-checks the host at fetch time and on every
    redirect, not only when the scouted row was ingested."""
    import urllib.error
    import urllib.request

    import asia_collector as ac
    req = urllib.request.Request("http://169.254.169.254/latest/meta-data/")
    with pytest.raises(urllib.error.URLError, match="refused"):
        ac._open(req, {"origin": "llm_source_scout"}, 1.0)
    h = ac._PublicOnlyRedirects()
    with pytest.raises(urllib.error.URLError, match="redirect refused"):
        h.redirect_request(urllib.request.Request("https://example.org/"), None, 302, "Found",
                           {}, "http://10.0.0.5/admin")
