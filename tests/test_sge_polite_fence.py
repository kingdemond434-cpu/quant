"""sge.com.cn is reached only through libs.data.polite_fetch, and its unread terms make it
IDEAS_ONLY: the SGE premium fetch is refused before any request and reads UNMEASURED."""
from __future__ import annotations

import ast
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import polite_fetch  # noqa: E402
from libs.data import terms_fence as tf  # noqa: E402

SGE = "sge.com.cn"
_BARE = {("requests", "get"), ("requests", "post"), ("requests", "request"),
         ("requests", "head"), ("urllib.request", "urlopen"), ("request", "urlopen")}


def _callee(node: ast.Call) -> tuple[str, str] | None:
    f = node.func
    if isinstance(f, ast.Attribute):
        return ast.unparse(f.value), f.attr
    if isinstance(f, ast.Name) and f.id == "urlopen":
        return "request", "urlopen"
    return None


def _offenders(path: Path) -> list[str]:
    src = path.read_text("utf-8", "replace")
    if SGE not in src:
        return []
    tree = ast.parse(src)
    consts = {t.id for n in tree.body if isinstance(n, ast.Assign)
              for t in n.targets if isinstance(t, ast.Name) and SGE in ast.unparse(n.value)}
    out = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = ast.unparse(fn)
        if SGE not in body and not any(c in body for c in consts):
            continue
        for call in (n for n in ast.walk(fn) if isinstance(n, ast.Call)):
            if _callee(call) in _BARE:
                out.append(f"{path.relative_to(ROOT)}:{call.lineno} {fn.name}")
    return out


def test_no_function_that_names_sge_calls_a_bare_requests_or_urlopen() -> None:
    bad: list[str] = []
    for d in ("desks", "libs", "scripts", "ops"):
        for p in (ROOT / d).rglob("*.py"):
            if "tests" in p.parts or ".claude" in p.parts:
                continue
            bad += _offenders(p)
    assert not bad, f"sge.com.cn reached by a bare fetch: {bad}"


def test_sge_host_row_is_ideas_only_with_consumers_in_its_missed_growth_cause() -> None:
    row = tf.SOURCE_POLICY["sge"]
    assert row["hosts"] == (SGE,) and tf.status("sge") == tf.IDEAS_ONLY
    assert tf.terms_state("sge") == tf.UNREAD and tf.terms_verdict("sge") == "to_confirm"
    for u in ("https://www.sge.com.cn/graph/quotations?instid=Au99.99",
              "https://en.sge.com.cn/data_BenchmarkPrice", "https://www.sge.com.cn/sjzx/mrhq"):
        assert tf.input_source(u) == "sge", u
    assert tf.input_source("sge_benchmark") == "sge"
    assert tf.platform_of_url("https://www.sge.com.cn/sjzx/mrhq") is None   # ideas still read
    mg = row["missed_growth"]
    assert mg["delta_elogw"] == "UNMEASURED"
    for name in ("fetch_sge_premium", "macro_state_engine", "dislocation_lab", "asia_plane",
                 "XAU_locbasis_split", "external_survivors"):
        assert name in mg["cause"], name
    from research import alt_proxies as A
    assert A.BY_ID["cn_sge_premium"].terms == "to_confirm" == A.TERMS["cn_sge_premium"][0]


def test_sge_premium_fetch_is_refused_before_any_request_and_reads_unmeasured(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from research import fetch_sge_premium as S

    def _no_bare(*a: Any, **k: Any) -> Any:
        raise AssertionError("bare fetch")
    monkeypatch.setattr(urllib.request, "urlopen", _no_bare)
    import requests
    monkeypatch.setattr(requests, "get", _no_bare)

    def _no_open(*a: Any, **k: Any) -> Any:
        raise AssertionError("polite_fetch sent a request for a refused route")
    real_get = polite_fetch.get
    monkeypatch.setattr(polite_fetch, "get",
                        lambda url, **kw: real_get(url, opener=_no_open, **kw))
    monkeypatch.setattr(S, "REPORTS", tmp_path)
    monkeypatch.setattr(S, "HISTORY", tmp_path / "sge_daily.parquet")
    assert S.main() == 0
    rep = json.loads((tmp_path / "sge_premium.json").read_text("utf-8"))
    assert rep["status"] == "UNMEASURED" and "IDEAS_ONLY" in rep["refusal"]
    assert rep["missed_growth"]["delta_elogw"] == "UNMEASURED"
    assert rep["policy_row"] == "sge" and rep["consumers"]
    assert "rows" not in rep and not (tmp_path / "sge_daily.parquet").exists()


def test_route_probe_reaches_sge_only_through_polite_fetch(
        monkeypatch: pytest.MonkeyPatch) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import check_source_routes as R

    def _no_bare(*a: Any, **k: Any) -> Any:
        raise AssertionError("bare urlopen")
    monkeypatch.setattr(urllib.request, "urlopen", _no_bare)
    seen: list[str] = []

    def fake(url: str, **kw: Any) -> polite_fetch.Response:
        seen.append(url)
        return polite_fetch.Response(url=url, verdict="ROBOTS_DISALLOW",
                                     error="ROBOTS_DISALLOW: disallowed")
    monkeypatch.setattr(polite_fetch, "get", fake)
    r = R.probe({"name": "sge_quotations", "url": "https://www.sge.com.cn/graph/quotations",
                 "expect": "any"})
    assert seen and r["status"] == "UNMEASURED"


def test_dislocation_and_asia_plane_read_a_refusal_as_unmeasured() -> None:
    text = (DESK / "research" / "dislocation_lab.py").read_text("utf-8")
    assert 'sge_premium UNMEASURED' in text
    plane = (DESK / "research" / "asia_plane.py").read_text("utf-8")
    assert 'input_source("sge_benchmark")' in plane
