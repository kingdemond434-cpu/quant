"""J-QUANTS, PRIVATE END TO END: collector store -> cells -> compiler, and nothing tracked learns a
value. The repository is PUBLIC and J-Quants is permitted for private use only (art. 8; the
principal's answer of 2026-10-06, libs.ops.token_refresh.TERMS_EVIDENCE["jquants"]).

The data here is SYNTHETIC (V2 `/v2/equities/investor-types` field names, the same shape as
tests/fixtures/alt_proxies/jp_jquants_investor_types.json); bars are synthetic too. Nothing here
is a measurement.
"""
from __future__ import annotations

import json
import random
import shutil
import subprocess
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import alt_proxies as A  # noqa: E402
from research import proposer_common as pc  # noqa: E402

NOW = datetime(2026, 9, 30, 12, tzinfo=UTC)
#: Every synthetic J-Quants value carries this digit run, so a leaked value is findable as text.
SENTINEL = 773_1
#: Strings only a private cell or candidate carries.
PRIVATE_MARKERS = ("private:jquants", "jquants:investor_types", "t_gross", "net_per_trade",
                   "foreigners_net_kjpy", "FrgnBal")


def _numbers(obj: Any) -> list[float]:
    if isinstance(obj, bool):
        return []
    if isinstance(obj, (int, float)):
        return [float(obj)]
    if isinstance(obj, dict):
        return [x for v in obj.values() for x in _numbers(v)]
    if isinstance(obj, list):
        return [x for v in obj for x in _numbers(v)]
    return []


def _carries_a_value(text: str) -> bool:
    """True when any JSON number in `text` is one of the synthetic J-Quants values."""
    docs: list[Any] = []
    for ln in text.splitlines() if text.lstrip().startswith("{") and "\n{" in text else [text]:
        try:
            docs.append(json.loads(ln))
        except ValueError:
            continue
    return any(SENTINEL * 100 <= abs(x) < (SENTINEL + 1) * 1000
               for d in docs for x in _numbers(d))


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                          check=False)


def _weeks(n: int = 156, seed: int = 7) -> list[dict[str, Any]]:
    """n weekly TSE Prime rows: published the Thursday after the week ending Friday."""
    rng = random.Random(seed)
    end = date(2026, 9, 18)
    rows = []
    for k in range(n):
        we = end - timedelta(weeks=n - 1 - k)
        sign = 1 if rng.random() < 0.5 else -1
        rows.append({"PubDate": (we + timedelta(days=6)).isoformat(), "EnDate": we.isoformat(),
                     "Section": "TSEPrime",
                     "FrgnBal": sign * (SENTINEL * 1000 + rng.randrange(1, 999)),
                     "IndBal": -sign * (SENTINEL * 100 + rng.randrange(1, 99))})
    return rows


def _bars(rows: list[dict[str, Any]]) -> Any:
    """H1 bars whose next 24 hours follow the sign of each week's foreign net flow."""
    import numpy as np
    import pandas as pd
    idx = pd.date_range("2023-09-01", "2026-09-30", freq="h", tz="UTC")
    rng = np.random.default_rng(3)
    step = rng.normal(0.0, 0.0002, len(idx))
    for r in rows:
        t = pd.Timestamp(r["PubDate"], tz="UTC") + pd.Timedelta(hours=11)
        pos = int(idx.searchsorted(t))
        step[pos:pos + 30] += 0.0006 * (1 if r["FrgnBal"] > 0 else -1)
    close = 150.0 * np.exp(np.cumsum(step))
    openp = np.concatenate([[close[0]], close[:-1]])
    return pd.DataFrame({"open": openp, "high": np.maximum(openp, close),
                         "low": np.minimum(openp, close), "close": close}, index=idx)


@pytest.fixture
def scratch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """A scratch git repo carrying THIS repository's .gitignore, a private J-Quants store in it,
    and the door's writers pointed into it."""
    if shutil.which("git") is None:
        pytest.skip("git is not installed")
    repo = tmp_path / "repo"
    repo.mkdir()
    assert _git(repo, "init", "-q").returncode == 0
    shutil.copyfile(ROOT / ".gitignore", repo / ".gitignore")
    desk = repo / "desks" / "mt5"
    paths = A.Paths(desk)
    rows = _weeks()
    paths.private_series.mkdir(parents=True)
    (paths.private_series / "jpx_jquants.json").write_text(json.dumps({"data": rows}), "utf-8")
    bars = _bars(rows)
    monkeypatch.setattr(pc, "PRIVATE_INTEL", desk / "data" / "intelligence_private")
    monkeypatch.setattr(pc, "INTEL", desk / "data" / "intelligence")
    monkeypatch.setattr(pc, "bars", lambda sym: bars if sym == "USDJPY" else None)
    monkeypatch.setattr(pc, "cost_frac", lambda sym, meta, close: 1e-5)
    monkeypatch.setattr(pc, "universe_meta", lambda: {})
    monkeypatch.setattr(pc, "artifact_hours", lambda d: {})
    registry: list[Any] = []
    monkeypatch.setattr(pc, "_record_in_registry", lambda *a, **k: registry.append(a))
    return {"repo": repo, "desk": desk, "paths": paths, "rows": rows, "registry": registry}


# ------------------------------------------------------------------------------ the reader
def test_reader_reads_the_private_store_and_never_the_shared_lake(tmp_path: Path) -> None:
    paths = A.Paths(tmp_path / "desk")
    body = (ROOT / "tests" / "fixtures" / "alt_proxies" / "jp_jquants_investor_types.json"
            ).read_bytes()
    paths.series.mkdir(parents=True)
    (paths.series / "jpx_jquants.json").write_bytes(body)        # the shared lake: not read
    assert A.read_jquants_investor_types(paths) == []
    paths.private_series.mkdir(parents=True)
    (paths.private_series / "jpx_jquants.json").write_bytes(body)
    got = A.read_jquants_investor_types(paths)
    assert got and {o.series for o in got} >= {"foreigners_net_kjpy"}
    assert str(paths.private_series).endswith("data/lake/private_use/series")
    assert str(paths.private_vault).endswith("data/lake/private_use/vault")


# ------------------------------------------------------------------------------ the cells
def test_cells_are_screened_deflated_and_donated_privately(scratch: dict[str, Any]) -> None:
    from countries.jp import official_plane as J
    lane = J.jquants_cells(scratch["paths"], NOW)
    assert set(lane) <= set(J.JQ_PUBLIC_KEYS)
    assert lane["status"] == "PRIVATE_USE:CELLS_BUILT"
    # 2 investor types x 4 features x 2 directions x 2 holds on the one instrument with bars
    assert lane["looks"] == 2 * 4 * 2 * 2 and lane["trials_charged"] == lane["looks"]
    assert lane["proposed"] >= 1 and lane["donated"] == lane["proposed"]
    # no digest of private content on the tracked side (audit of #251): it sits beside the file
    assert "private_ref" not in lane
    root = scratch["desk"] / "data" / "intelligence_private" / "jquants"
    (disc,) = sorted(root.glob("discoveries_*.json"))
    (ref,) = sorted(root.glob("ref_discoveries_*.json"))
    assert len(json.loads(ref.read_text("utf-8"))["private_ref"]) == 16
    doc = json.loads(disc.read_text("utf-8"))
    assert doc["tests_run"] == lane["looks"]
    from libs.ops import token_refresh as T
    for c in doc["discoveries"]:
        assert c["data_source"] == "jquants:investor_types" and c["private_use"] is True
        # the lineage the E8 book refuses on survives the donation door
        assert c["lineage"] == T.PRIVATE_LINEAGE and c["e8_ineligible"] is True
        assert c["family"] == "exogenous_conditioner" and c["available_time"]
        assert c["evidence"]["n_tests_sweep"] == lane["looks"]
    feats = {c["params"]["signal"] for c in doc["discoveries"]}
    assert feats <= set(J.JQ_FEATURES)
    # the canonical registry (backed up to a tracked path) never saw them; prereg stayed private
    assert scratch["registry"] == []
    assert (root / "preregistrations_private.jsonl").exists()
    assert not (scratch["desk"] / "data" / "intelligence").exists()
    # every look charged on the tracked side ledger, as a bare count
    (charge,) = [json.loads(x) for x in
                 scratch["paths"].null_trials.read_text("utf-8").splitlines() if x]
    assert set(charge) == {"at", "source", "tests_run", "by_family", "why"}
    assert charge["tests_run"] == lane["looks"]
    assert charge["by_family"] == {"exogenous_conditioner": lane["looks"]}


def test_lane_is_blocked_without_the_recorded_condition(scratch: dict[str, Any],
                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    from countries.jp import official_plane as J

    from libs.ops import token_refresh as T
    ev = {k: dict(v) for k, v in T.TERMS_EVIDENCE.items()}
    ev["jquants"].pop("condition", None)
    monkeypatch.setattr(T, "TERMS_EVIDENCE", ev)
    lane = J.jquants_cells(scratch["paths"], NOW)
    assert lane["status"] == "BLOCKED_ON_TERMS:to_confirm"
    assert not (scratch["desk"] / "data" / "intelligence_private").exists()
    assert not scratch["paths"].null_trials.exists()


def test_private_donation_refuses_a_root_outside_the_private_tree(
        scratch: dict[str, Any], tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="PRIVATE_INTEL"):
        pc.donate("jquants", [{"symbol": "USDJPY", "family": "x", "params": {}}], 1,
                  private_root=tmp_path / "elsewhere")


# ------------------------------------------------------------------------------ the compiler
def test_compiler_compiles_private_rows_into_the_private_sibling_only(
        scratch: dict[str, Any]) -> None:
    from countries.jp import official_plane as J

    from research import miner_candidate_compiler as M
    J.jquants_cells(scratch["paths"], NOW)
    out = scratch["desk"] / "data" / "hypotheses_private" / "miner_candidates_private.json"
    summary = M.compile_private(datetime.now(UTC),
                                roots=(scratch["desk"] / "data" / "intelligence_private",),
                                out=out, universe={"USDJPY", "EURJPY", "JPN225"})
    assert summary["status"] == "COMPILED_PRIVATE" and summary["candidates"] >= 1
    doc = json.loads(out.read_text("utf-8"))
    assert doc["private_use"] is True and len(doc["hypotheses"]) == summary["candidates"]
    assert all(h["family"] == "exogenous_conditioner" for h in doc["hypotheses"])
    section = M.private_intake_section(summary)
    assert set(section) <= set(M.PRIVATE_SUMMARY_KEYS)
    assert not any(m in json.dumps(section) for m in PRIVATE_MARKERS)
    # the public intake never globs the private root
    assert all("intelligence_private" not in str(r) for r in M.INTEL_ROOTS)


def test_compiler_main_carries_only_the_private_summary() -> None:
    src = (DESK / "research" / "miner_candidate_compiler.py").read_text("utf-8")
    assert '"private_intake": private_note,' in src
    assert "private_intake_section(compile_private(" in src


# ------------------------------------------------------------------------------ the report
def test_jp_plane_report_carries_jquants_as_counts_and_status(scratch: dict[str, Any]) -> None:
    from countries.jp import official_plane as J
    out = scratch["desk"] / "reports" / "JP_OFFICIAL_PLANE.json"
    doc = J.run(paths=scratch["paths"], report_default=out, now=NOW)
    lanes = {r["dataset"]: r for r in doc["lanes"]}
    jq = lanes["jp_jquants_investor_types"]
    assert set(jq) <= set(J.JQ_PUBLIC_KEYS)
    assert jq["terms"] == "confirmed_private_use" and jq["status"].startswith("PRIVATE_USE:")
    for k, v in jq.items():
        assert v is None or isinstance(v, (str, bool, int)), k
    assert doc["private_use_lanes"] == ["jp_jquants_investor_types"]
    text = out.read_text("utf-8")
    assert not any(m in text for m in PRIVATE_MARKERS) and not _carries_a_value(text)


# ------------------------------------------------------------------------------ THE FENCE
def test_fence_every_written_file_is_ignored_or_free_of_jquants(scratch: dict[str, Any]) -> None:
    """J-Quants store -> cells -> compiler -> report in a scratch repo carrying this repository's
    .gitignore: every file the chain wrote is ignored by git, or holds no J-Quants value, derived
    value or cell."""
    from countries.jp import official_plane as J

    from research import miner_candidate_compiler as M
    repo, desk = scratch["repo"], scratch["desk"]
    J.run(paths=scratch["paths"], report_default=desk / "reports" / "JP_OFFICIAL_PLANE.json",
          now=NOW)
    summary = M.compile_private(datetime.now(UTC),
                                roots=(desk / "data" / "intelligence_private",),
                                out=desk / "data" / "hypotheses_private"
                                / "miner_candidates_private.json",
                                universe={"USDJPY", "EURJPY", "JPN225"})
    assert summary["candidates"] >= 1, "the chain produced nothing -- the fence would be vacuous"
    tracked_out = desk / "data" / "hypotheses" / "miner_candidates.json"
    tracked_out.parent.mkdir(parents=True, exist_ok=True)
    tracked_out.write_text(json.dumps({"private_intake": M.private_intake_section(summary)}),
                           "utf-8")

    written = [p for p in repo.rglob("*") if p.is_file()
               and p.relative_to(repo).parts[0] != ".git" and p.name != ".gitignore"]
    ignored, tracked = [], []
    for p in written:
        rel = str(p.relative_to(repo))
        (ignored if _git(repo, "check-ignore", "-q", rel).returncode == 0 else tracked).append(rel)
    # the private stores really were written, and really are ignored
    assert any("intelligence_private/jquants/discoveries_" in r for r in ignored)
    assert any("hypotheses_private/miner_candidates_private.json" in r for r in ignored)
    assert any("lake/private_use/series/jpx_jquants.json" in r for r in ignored)
    leaks = []
    for rel in tracked:
        text = (repo / rel).read_text("utf-8", errors="replace")
        if any(m in text for m in PRIVATE_MARKERS) or _carries_a_value(text):
            leaks.append(rel)
    assert sorted(tracked) == sorted(["desks/mt5/data/null_pass_trials.jsonl",
                                      "desks/mt5/data/hypotheses/miner_candidates.json"]), tracked
    assert not leaks, f"J-Quants content on a tracked path: {leaks}"
    for ln in (desk / "data" / "null_pass_trials.jsonl").read_text("utf-8").splitlines():
        assert set(json.loads(ln)) == {"at", "source", "tests_run", "by_family", "why"}
    section = json.loads(tracked_out.read_text("utf-8"))["private_intake"]
    assert set(section) <= set(M.PRIVATE_SUMMARY_KEYS)



# ------------------------------------------------------------------------------ audit of #251
def test_two_private_passes_in_one_minute_never_overwrite(scratch: dict[str, Any]) -> None:
    root = scratch["desk"] / "data" / "intelligence_private" / "jquants"
    rows = [{"symbol": "USDJPY", "family": "exogenous_conditioner", "params": {"a": 1},
             "kind": "hypothesis", "symbols": ["USDJPY"], "available_time": NOW.isoformat(),
             "event_time": NOW.isoformat()}]
    a = pc.donate("jquants", [dict(r) for r in rows], 1, private_root=root)
    b = pc.donate("jquants", [dict(r) for r in rows], 1, private_root=root)
    assert a and b and a != b and Path(a).exists() and Path(b).exists()


def test_private_summary_carries_bare_counts_only(scratch: dict[str, Any]) -> None:
    from countries.jp import official_plane as J

    from research import miner_candidate_compiler as M
    assert "private_ref" not in M.PRIVATE_SUMMARY_KEYS
    assert "private_ref" not in J.JQ_PUBLIC_KEYS
    J.jquants_cells(scratch["paths"], NOW)
    out = scratch["desk"] / "data" / "hypotheses_private" / "miner_candidates_private.json"
    summary = M.compile_private(datetime.now(UTC),
                                roots=(scratch["desk"] / "data" / "intelligence_private",),
                                out=out, universe={"USDJPY", "EURJPY", "JPN225"})
    section = M.private_intake_section(summary)
    for k, v in section.items():
        assert k == "status" or k == "rule" or isinstance(v, int), (k, v)
    assert json.loads(out.with_name(out.stem + ".ref.json").read_text("utf-8"))["private_ref"]
    from libs.ops import token_refresh as T
    for h in json.loads(out.read_text("utf-8"))["hypotheses"]:
        assert T.has_private_lineage(h) and h["e8_ineligible"] is True


#: A STANDALONE number token (not digits inside an identifier such as a BOJ series code).
_NUM = __import__("re").compile(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?(?![\w])")


def _text_carries_a_value(text: str) -> bool:
    """Any number token in free text (stdout) that is one of the synthetic J-Quants values."""
    for tok in _NUM.findall(text):
        try:
            x = abs(float(tok.replace(",", "")))
        except ValueError:
            continue
        if SENTINEL * 100 <= x < (SENTINEL + 1) * 1000:
            return True
    return False


def _leaks(text: str) -> list[str]:
    out = [m for m in PRIVATE_MARKERS if m in text]
    if _carries_a_value(text) or _text_carries_a_value(text):
        out.append("<a J-Quants value>")
    return out


def _captured(fn: Any) -> tuple[Any, str]:
    import contextlib
    import io
    o, e = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
        res = fn()
    return res, o.getvalue() + "\n" + e.getvalue()


def _tracked_status() -> str:
    return subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain",
                           "--untracked-files=no"], capture_output=True, text=True,
                          check=False).stdout


def _files_that_reach_git(repo: Path) -> list[str]:
    """Unignored files of the scratch repo, plus files whose path THIS repository tracks even
    though .gitignore names it (sync_marker.json, runtime_state.json-style force-adds)."""
    r = _git(repo, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
    out = {x for x in r.stdout.split("\0") if x}
    for p in repo.rglob("*"):
        rel = p.relative_to(repo).as_posix()
        if p.is_file() and not rel.startswith(".git/") and rel not in out:
            t = subprocess.run(["git", "-C", str(ROOT), "ls-files", "--", rel],
                               capture_output=True, text=True, check=False)
            if t.stdout.strip():
                out.add(rel)
    return sorted(out)


def test_fence_the_whole_private_chain_prints_and_publishes_nothing_private(
        scratch: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    """(a) stdout/stderr of EVERY organ the private lane passes through -- the Japan plane, the
    compiler's main pass, global_research_os's Japan department and runtime attestation -- and
    the results each returns; (c) a downstream grep over every file of the scratch repository
    that git would carry (force-tracked paths included); (d) the private candidates are refused
    by the E8 book; and this repository's own tracked files are untouched."""
    from countries.jp import official_plane as J

    from research import miner_candidate_compiler as M
    repo, desk, paths = scratch["repo"], scratch["desk"], scratch["paths"]
    before = _tracked_status()
    texts: list[str] = []

    # 1. the Japan plane, J-Quants lane included
    doc, out = _captured(lambda: J.run(paths=paths, now=NOW,
                                       report_default=desk / "reports" / "JP_OFFICIAL_PLANE.json"))
    texts += [out, json.dumps(doc, default=str)]
    jq = {r["dataset"]: r for r in doc["lanes"]}["jp_jquants_investor_types"]
    assert jq["status"] == "PRIVATE_USE:CELLS_BUILT" and jq["donated"] >= 1

    # 2. the compiler's MAIN pass, every write pointed into the scratch desk
    hyp = desk / "data" / "hypotheses"
    for name, target in (("OUT", hyp / "miner_candidates.json"),
                         ("DEEPEN", hyp / "miner_deepening_queue.json"),
                         ("DEEPEN_WORKED", hyp / "deepening_worked.jsonl"),
                         ("DEEPENED", hyp / "deepened_candidates.json"),
                         ("CURSOR", hyp / "miner_compiler_cursor.json"),
                         ("FACTORY_RECEIPTS", desk / "data" / "factory_federation" / "r"),
                         ("PRIVATE_OUT", desk / "data" / "hypotheses_private"
                          / "miner_candidates_private.json")):
        monkeypatch.setattr(M, name, target)
    monkeypatch.setattr(M, "INTEL_ROOTS", (desk / "data" / "intelligence",))
    monkeypatch.setattr(M, "PRIVATE_INTEL_ROOTS", (desk / "data" / "intelligence_private",))
    monkeypatch.setattr(M, "_graph_snapshot", lambda *a, **k: (_ for _ in ()).throw(
        RuntimeError("graph stubbed in the fence")))
    import research.build_failure_bank as bfb

    class _NoBank:
        def __init__(self, *a: Any, **k: Any) -> None:
            raise RuntimeError("bank stubbed in the fence")
    monkeypatch.setattr(bfb, "Bank", _NoBank)
    _rc, out = _captured(M.main)
    texts.append(out)
    compiled = json.loads((hyp / "miner_candidates.json").read_text("utf-8"))
    intake = compiled["private_intake"]
    assert intake["status"] == "COMPILED_PRIVATE" and intake["candidates"] >= 1, intake
    assert set(intake) <= set(M.PRIVATE_SUMMARY_KEYS)

    # 3. global_research_os's Japan department, over the same private store
    from research import alt_proxies as A_
    from research import global_research_os as G
    monkeypatch.setattr(A_, "DEFAULT_PATHS", paths)
    rows, out = _captured(lambda: G.department_rows(dry_run=True, codes=["jp"]))
    texts += [out, json.dumps(rows, default=str)]
    assert rows and rows[0]["miner_dispositions"][0]["outcome"] == "RAN"

    # 4. runtime attestation over the scratch tree (its runtime_state.json is a TRACKED path)
    from research import runtime_attestation as RA
    _rc, out = _captured(lambda: RA.main(["--once", "--root", str(repo), "--budget-s", "20"]))
    texts.append(out)

    leaks = {i: _leaks(t) for i, t in enumerate(texts) if _leaks(t)}
    assert not leaks, f"a private value reached an organ's stdout/stderr or result: {leaks}"

    # (c) every file git would carry from the scratch tree
    files = _files_that_reach_git(repo)
    assert "desks/mt5/data/hypotheses/miner_candidates.json" in files
    assert "desks/mt5/reports/JP_OFFICIAL_PLANE.json" in files
    assert not any(d in f for f in files for d in ("private_use", "intelligence_private",
                                                     "hypotheses_private"))
    bad = [f for f in files
           if _leaks((repo / f).read_text("utf-8", errors="replace"))]
    assert not bad, f"J-Quants content on a path git carries: {bad}"

    # (d) E8: a survivor built from a private candidate is refused, a public one is not
    from prop import e8_book as B
    priv = json.loads((desk / "data" / "hypotheses_private"
                       / "miner_candidates_private.json").read_text("utf-8"))["hypotheses"][0]
    surv = repo.parent / "SURV.json"
    surv.write_text(json.dumps({"survivors": {
        "priv": {"shadow_spec": {**priv, "selector": "asia"}, "days": 300,
                 "gates": {"expected_value": {"ev": 0.9}}},
        "pub": {"shadow_spec": {"symbol": "EURUSD", "family": "carry", "selector": "asia"},
                "days": 300, "gates": {"expected_value": {"ev": 0.1}}}}}), "utf-8")
    monkeypatch.setattr(B, "SURVIVORS", surv)
    monkeypatch.setattr(B, "_family_banned", lambda fam: False)
    book = B.select(tradeable=None)
    assert {r["key"] for r in book["refused_private_lineage"]} == {"priv"}
    assert {r["key"] for r in book["sleeves"]} == {"pub"}

    assert _tracked_status() == before, "the fence run wrote into this repository's tracked files"


def test_only_compile_private_reads_the_private_intake_roots() -> None:
    """STATIC. Inside a function, the private intake/compile roots (intelligence_private,
    hypotheses_private and the constants naming them) are referenced ONLY by
    `miner_candidate_compiler.compile_private` (the one reader) and by the two writers that put
    rows there (`proposer_common.donate`, `jp.official_plane._private_root`). Module-level
    declarations of the constants are allowed; any other function is a new reader."""
    import ast
    names = {"PRIVATE_INTEL", "PRIVATE_INTEL_ROOTS", "PRIVATE_OUT", "PRIVATE_REF"}
    dirs = ("intelligence_private", "hypotheses_private")
    allowed = {("desks/mt5/research/miner_candidate_compiler.py", "compile_private"),
               ("desks/mt5/research/proposer_common.py", "donate"),
               ("desks/mt5/research/countries/jp/official_plane.py", "_private_root")}
    r = subprocess.run(["git", "-C", str(ROOT), "grep", "-l", "-E",
                        "|".join((*dirs, *sorted(names))), "--", "*.py"],
                       capture_output=True, text=True, check=False)
    found: set[tuple[str, str]] = set()
    for rel in r.stdout.split():
        if "tests" in Path(rel).parts or Path(rel).name.startswith("test_"):
            continue
        tree = ast.parse((ROOT / rel).read_text("utf-8"))
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for node in ast.walk(fn):
                hit = ((isinstance(node, ast.Name) and node.id in names)
                       or (isinstance(node, ast.Attribute) and node.attr in names)
                       or (isinstance(node, ast.Constant) and isinstance(node.value, str)
                           and any(d in node.value for d in dirs)
                           and " " not in node.value))
                if hit:
                    found.add((rel, fn.name))
    extra = found - allowed
    assert not extra, f"functions reading the private intake roots outside the allowlist: {extra}"
    assert ("desks/mt5/research/miner_candidate_compiler.py", "compile_private") in found
