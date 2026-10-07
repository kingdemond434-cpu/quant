"""FENCE: no J-Quants (private-use) value reaches a tracked path. The repository is PUBLIC.

FOUR LAYERS (audit of #218, 2026-10-07; a planted print in `_print_summary` passed the first):
  (a) the J-Quants pass's STDOUT AND STDERR, and the hourly leg that runs it, carry no planted
      value -- hourly_cycle keeps each leg's stdout tail in the TRACKED sync_marker.json;
  (b) a static allowlist of the modules that may reference data/lake/private_use;
  (c) a downstream grep, after a planted run, over EVERY unignored file of a scratch repository
      carrying this repository's .gitignore, sync_marker.json included, and over this
      repository's own tracked and unignored files;
  (d) private-lineage cells never reach the E8 book (prop capital is not the individual's own).

J-Quants is permitted for the registered individual's private use only (art. 8; the principal's
answer of 2026-10-06, recorded in libs.ops.token_refresh.TERMS_EVIDENCE["jquants"]). This runs the
asia collector's whole pass against a fake transport inside a scratch git repository that carries
this repository's own .gitignore, then checks EVERY file the pass wrote: either git ignores it, or
it holds no J-Quants value and no private-use row content.
"""
from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
import sys
import urllib.request
import uuid
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "desks" / "mt5") not in sys.path:
    sys.path.insert(0, str(ROOT / "desks" / "mt5"))

from libs.ops import token_refresh as T  # noqa: E402

# PLANTED SENTINELS, minted per run so that no tracked file -- this one included -- can carry
# them: a hit anywhere after a planted run is a leak, never a coincidence.
SENTINEL = f"JQPRIV{uuid.uuid4().hex}"      # a value only the J-Quants payload carries
COLUMN = f"JQCOL{uuid.uuid4().hex[:12]}"     # a field name only the J-Quants payload carries
API_KEY = f"fake-jq-key-{uuid.uuid4().hex}"
PLANTED = (SENTINEL, COLUMN, API_KEY)


class _Resp:
    def __init__(self, body: bytes) -> None:
        self.status = 200
        self.headers = {"Content-Type": "application/json"}
        self._body = body

    def read(self, n: int = -1) -> bytes:
        return self._body

    def __enter__(self) -> _Resp:
        return self

    def __exit__(self, *a: Any) -> None:
        return None


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                          check=False)


@pytest.fixture
def scratch_repo(tmp_path: Path) -> Path:
    if shutil.which("git") is None:
        pytest.skip("git is not installed")
    repo = tmp_path / "repo"
    repo.mkdir()
    assert _git(repo, "init", "-q").returncode == 0
    shutil.copyfile(ROOT / ".gitignore", repo / ".gitignore")
    return repo


def test_no_jquants_value_reaches_a_tracked_path(monkeypatch: pytest.MonkeyPatch,
                                                  scratch_repo: Path) -> None:
    from research import asia_collector as C

    base = scratch_repo / "desks" / "mt5"
    for name, rel in (("VAULT", "data/lake/vault"), ("SERIES", "data/lake/series"),
                      ("STATE", "data/lake/collector_state.json"),
                      ("PRIVATE", "data/lake/private_use"),
                      ("OUT", "reports/ASIA_COLLECTOR.json"),
                      ("FOUND", "data/intelligence/asia_endpoints")):
        monkeypatch.setattr(C, name, base / rel)
    monkeypatch.setenv("QUANT_TOKEN_CACHE_DIR",
                       str(scratch_repo / "data" / "secrets" / "token_cache"))
    monkeypatch.setattr(T, "_read_key", lambda n: API_KEY if n == "JQUANTS_API_KEY" else "")
    monkeypatch.setattr(C, "_robots_allows", lambda u, agent="": (True, "stub"))
    payload = json.dumps({"data": [{"Date": "2026-10-02", COLUMN: SENTINEL}]}).encode()
    sent: list[Any] = []

    def opened(self: Any, req: Any, data: Any = None, timeout: float = 0) -> _Resp:
        sent.append(req)
        return _Resp(payload)
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", opened)
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _Resp(payload))

    C.main(["--id", "jpx_jquants"])
    assert sent and sent[0].get_header("X-api-key") == API_KEY

    # The pass really collected, and wrote the values where they belong.
    report = json.loads((base / "reports" / "ASIA_COLLECTOR.json").read_text("utf-8"))
    (row,) = report["rows"]
    assert row["status"] == "COLLECTED" and row["private_use"] is True
    assert set(row) <= set(C.PRIVATE_REPORT_KEYS) | {"parse"}
    assert report["series_written"] == [] and report["n_private_use"] == 1
    private_files = [p for p in (base / "data/lake/private_use").rglob("*") if p.is_file()]
    assert any(SENTINEL in p.read_text("utf-8", errors="replace") for p in private_files
               if p.suffix == ".json")
    assert not (base / "data/lake/series").exists() and not (base / "data/lake/vault").exists()

    written = [p for p in scratch_repo.rglob("*")
               if p.is_file() and ".git" not in p.relative_to(scratch_repo).parts[:1]
               and p.name != ".gitignore"]
    assert written, "the pass wrote nothing -- the fence would be vacuous"
    leaks = []
    for p in written:
        rel = str(p.relative_to(scratch_repo))
        if _git(scratch_repo, "check-ignore", "-q", rel).returncode == 0:
            continue                                          # ignored: never reaches git
        text = p.read_bytes().decode("utf-8", errors="replace")
        if SENTINEL in text or COLUMN in text or API_KEY in text:
            leaks.append(rel)
            continue
        if p.suffix == ".json":
            doc = json.loads(text)
            rows = doc.get("rows", []) if isinstance(doc, dict) else []
            for r in rows:
                if isinstance(r, dict) and (r.get("private_use") or "jquants" in str(r.get("id"))):
                    extra = set(r) - set(C.PRIVATE_REPORT_KEYS) - {"parse"}
                    if extra or set(r.get("parse") or {}) - {"parsed", "kind", "n"}:
                        leaks.append(f"{rel}: {sorted(extra)}")
    assert not leaks, f"J-Quants / private-use content on a tracked path: {leaks}"


def test_every_private_use_destination_is_gitignored(scratch_repo: Path) -> None:
    """Every path J-Quants data can reach is ignored by the repository's own .gitignore."""
    for rel in ("desks/mt5/data/lake/private_use/vault/jpx_jquants/0123456789abcdef.gz",
                "desks/mt5/data/lake/private_use/vault/jpx_jquants/0123456789abcdef.meta.json",
                "desks/mt5/data/lake/private_use/series/jpx_jquants.json",
                "desks/mt5/data/lake/private_use/series/jpx_jquants.parquet",
                "desks/mt5/data/lake/private_use/series/jpx_jquants.csv",
                "desks/mt5/data/lake/collector_state.json",
                "desks/mt5/reports/ASIA_COLLECTOR.json",
                "data/secrets/token_cache/jquants.json"):
        assert _git(scratch_repo, "check-ignore", "-q", rel).returncode == 0, rel


def test_public_row_strips_values_and_keeps_counts() -> None:
    from research import asia_collector as C

    rec = {"id": "jpx_jquants", "status": "COLLECTED", "http": 200, "bytes": 99,
           "private_use": True, "url": "https://api.jquants.com/v2/x",
           "vault": {"blob": "/x/y.gz", "sha256": "ab"}, "validators": {"etag": "e"},
           "parse": {"parsed": True, "kind": "csv", "n": 3, "columns": [COLUMN], "path": "/p"}}
    out = C.public_row(rec)
    assert out["parse"] == {"parsed": True, "kind": "csv", "n": 3}
    assert "vault" not in out and "url" not in out and COLUMN not in json.dumps(out)
    other = {"id": "boj", "status": "COLLECTED", "parse": {"path": "/q", "n": 1}}
    assert C.public_row(other) is other


# ---------------------------------------------------------------------------------------------
# (a) stdout / stderr, and the hourly leg that runs the pass; (c) the downstream grep
# ---------------------------------------------------------------------------------------------

def _plant(monkeypatch: pytest.MonkeyPatch, scratch_repo: Path) -> Any:
    """Point the collector at the scratch repository and give it a fake J-Quants transport
    whose payload carries the planted sentinels. Returns the collector module."""
    from research import asia_collector as C

    base = scratch_repo / "desks" / "mt5"
    for name, rel in (("VAULT", "data/lake/vault"), ("SERIES", "data/lake/series"),
                      ("STATE", "data/lake/collector_state.json"),
                      ("PRIVATE", "data/lake/private_use"),
                      ("OUT", "reports/ASIA_COLLECTOR.json"),
                      ("FOUND", "data/intelligence/asia_endpoints")):
        monkeypatch.setattr(C, name, base / rel)
    monkeypatch.setenv("QUANT_TOKEN_CACHE_DIR",
                       str(scratch_repo / "data" / "secrets" / "token_cache"))
    monkeypatch.setattr(T, "_read_key", lambda n: API_KEY if n == "JQUANTS_API_KEY" else "")
    monkeypatch.setattr(C, "_robots_allows", lambda u, agent="": (True, "stub"))
    payload = json.dumps({"data": [{"Date": "2026-10-02", COLUMN: SENTINEL}]}).encode()
    monkeypatch.setattr(urllib.request.OpenerDirector, "open",
                        lambda self, req, data=None, timeout=0: _Resp(payload))
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _Resp(payload))
    return C


def _leaks_in(text: str) -> list[str]:
    return [s for s in PLANTED if s in text]


def _run_hourly_leg(monkeypatch: pytest.MonkeyPatch, C: Any,
                    streams: list[str] | None = None) -> dict[str, Any]:
    """hourly_cycle's REAL `asia_collector` leg, with its subprocess replaced by the collector run
    in-process (so the planted transport and scratch paths apply) and its stdout and stderr
    captured exactly as `_producer` captures a child's. Returns the leg's result dict -- the
    thing hourly_cycle writes into sync_marker.json -- and appends the FULL stdout and stderr to
    `streams`: the tail is only the last few hundred characters, so a fence on the tail alone
    passes a value printed early in the pass."""
    import contextlib
    import io

    import research.hourly_cycle as H

    def fake_run(argv: list[str], **kw: Any) -> subprocess.CompletedProcess[str]:
        out, err = io.StringIO(), io.StringIO()
        script = next(i for i, a in enumerate(argv) if str(a).endswith("asia_collector.py"))
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                rc = C.main([str(a) for a in argv[script + 1:]] + ["--id", "jpx_jquants"])
            except SystemExit as exc:                          # pragma: no cover
                rc = int(exc.code or 0)
        if streams is not None:
            streams.extend((out.getvalue(), err.getvalue()))
        return subprocess.CompletedProcess(argv, rc, out.getvalue(), err.getvalue())

    monkeypatch.setattr(H, "_run_tree", fake_run)
    return H.asia_collector()


def test_jquants_pass_prints_no_private_value(monkeypatch: pytest.MonkeyPatch,
                                              scratch_repo: Path,
                                              capfd: pytest.CaptureFixture[str]) -> None:
    """(a) The pass's stdout and stderr carry counts and status only."""
    C = _plant(monkeypatch, scratch_repo)
    C.main(["--id", "jpx_jquants"])
    out, err = capfd.readouterr()
    assert "jpx_jquants" in out and "private use" in out      # the pass did report
    assert not _leaks_in(out) and not _leaks_in(err), "a private value was printed"


def test_hourly_leg_tail_carries_no_private_value(monkeypatch: pytest.MonkeyPatch,
                                                  scratch_repo: Path) -> None:
    """(a) The hourly leg that runs the pass keeps its stdout/stderr tail in sync_marker.json."""
    C = _plant(monkeypatch, scratch_repo)
    streams: list[str] = []
    leg = _run_hourly_leg(monkeypatch, C, streams)
    assert leg.get("exit_code") == 0 and "jpx_jquants" in str(leg.get("tail"))
    assert streams and "jpx_jquants" in streams[0]
    assert not _leaks_in(json.dumps(leg)), "a private value reached the leg's recorded tail"
    assert not _leaks_in("\n".join(streams)), "a private value reached the leg's stdout/stderr"


def test_a_planted_print_is_caught(monkeypatch: pytest.MonkeyPatch,
                                   scratch_repo: Path) -> None:
    """The fence is not vacuous: the exact regression the audit planted -- a print of a private
    row inside `_print_summary` -- reaches the leg tail, and this fence sees it there."""
    C = _plant(monkeypatch, scratch_repo)
    real = C._print_summary

    def planted_early(rows: list[dict[str, Any]], *a: Any) -> int:
        print(json.dumps(rows, default=str))
        for p in (C.PRIVATE / "series").glob("*.json"):
            print(p.read_text("utf-8"))
        return real(rows, *a)
    monkeypatch.setattr(C, "_print_summary", planted_early)
    streams: list[str] = []
    _run_hourly_leg(monkeypatch, C, streams)
    assert _leaks_in("\n".join(streams)), "the fence missed a planted print in the stream"

    def planted_last(rows: list[dict[str, Any]], *a: Any) -> int:
        rc = real(rows, *a)
        print(f"  {SENTINEL}")
        return rc
    monkeypatch.setattr(C, "_print_summary", planted_last)
    leg = _run_hourly_leg(monkeypatch, C)
    assert _leaks_in(json.dumps(leg)), "the fence missed a planted print in the leg tail"


def _files_that_reach_git(repo: Path) -> list[str]:
    """Every file in the scratch repository that git would carry: unignored ones, AND ones this
    repository TRACKS although .gitignore names them (sync_marker.json is force-added: ignored by
    pattern, tracked by fact -- a fence on "unignored" alone would skip exactly that file)."""
    r = _git(repo, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
    assert r.returncode == 0, r.stderr
    out = {x for x in r.stdout.split("\0") if x}
    for p in repo.rglob("*"):
        rel = p.relative_to(repo).as_posix()
        if p.is_file() and not rel.startswith(".git/") and rel not in out:
            t = subprocess.run(["git", "-C", str(ROOT), "ls-files", "--", rel],
                               capture_output=True, text=True, check=False)
            if t.stdout.strip():
                out.add(rel)
    return sorted(out)


def test_downstream_grep_finds_no_planted_value_on_any_file_git_carries(
        monkeypatch: pytest.MonkeyPatch, scratch_repo: Path) -> None:
    """(c) After a planted run through the hourly leg, the leg result is written where
    hourly_cycle writes it (desks/mt5/data/sync_marker.json, a TRACKED file), and every
    unignored file of the scratch repository is grepped for every planted value."""
    C = _plant(monkeypatch, scratch_repo)
    leg = _run_hourly_leg(monkeypatch, C)
    marker = scratch_repo / "desks" / "mt5" / "data" / "sync_marker.json"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({"last_cycle": "planted", "asia_collector": leg}, indent=1),
                      encoding="utf-8")
    # the private lake really holds the planted value, and its attribution sidecar
    priv = [p for p in (scratch_repo / "desks/mt5/data/lake/private_use").rglob("*")
            if p.is_file()]
    assert any(SENTINEL in p.read_text("utf-8", errors="replace") for p in priv
               if p.suffix == ".json")
    assert any(p.name.endswith(".attribution.json") for p in priv)

    files = _files_that_reach_git(scratch_repo)
    assert "desks/mt5/data/sync_marker.json" in files, "sync_marker.json must be checked"
    assert not any("private_use" in f for f in files), files
    leaks = [f for f in files
             if _leaks_in((scratch_repo / f).read_bytes().decode("utf-8", errors="replace"))]
    assert not leaks, f"planted J-Quants value on an unignored path: {leaks}"


def test_no_planted_value_in_this_repository() -> None:
    """(c) And none reached THIS repository's tracked or unignored files: the planted values are
    minted per run, so any hit is a write that escaped the scratch paths."""
    if shutil.which("git") is None:
        pytest.skip("git is not installed")
    args = ["git", "-C", str(ROOT), "grep", "--untracked", "-I", "-l", "-F"]
    for s in PLANTED:
        args += ["-e", s]
    r = subprocess.run(args, capture_output=True, text=True, check=False, timeout=600)
    assert r.returncode == 1 and not r.stdout.strip(), r.stdout[:2000]


# ---------------------------------------------------------------------------------------------
# (b) the static allowlist of modules that may reference the private lake
# ---------------------------------------------------------------------------------------------

#: The ONLY non-test modules that may reference data/lake/private_use (or the collector's
#: `PRIVATE` constant that names it). A new reader is a new place a private value can leak from,
#: so adding one is a reviewed edit to this list, never a silent import.
PRIVATE_USE_ALLOWLIST = frozenset({
    "desks/mt5/research/asia_collector.py",            # writes the private lake (#218)
    "desks/mt5/research/alt_proxies.py",               # Paths.private_series / read_jquants_*
    "desks/mt5/research/proposer_common.py",           # PRIVATE_INTEL: the private donation door
    "desks/mt5/research/countries/jp/official_plane.py",  # jquants_cells -> private donation
    "desks/mt5/research/miner_candidate_compiler.py",  # compile_private, the one reader
})

#: Every private root: the lake (#218), the private intake and the private compile (#251).
PRIVATE_DIRS = ("private_use", "intelligence_private", "hypotheses_private")
#: Module constants that name a private root.
PRIVATE_NAMES = frozenset({"PRIVATE", "PRIVATE_INTEL", "PRIVATE_INTEL_ROOTS", "PRIVATE_OUT",
                           "PRIVATE_REF", "private_series", "private_vault"})
_PATHLIKE = re.compile(r"^[\w.\-/\\]*(?:" + "|".join(PRIVATE_DIRS) + r")[\w.\-/\\]*$")


def _names_private_lake(node: ast.AST) -> bool:
    # a path-like literal naming it: "lake/private_use", "data\\lake\\private_use\\x"
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        v = node.value
        return v not in PRIVATE_DIRS and bool(_PATHLIKE.match(v)) and ("/" in v or "\\" in v)
    # the collector's constant, imported or reached as an attribute
    if isinstance(node, ast.ImportFrom):
        return any(a.name in PRIVATE_NAMES for a in node.names)
    return isinstance(node, ast.Attribute) and node.attr in PRIVATE_NAMES


def _references_private_lake(tree: ast.AST) -> list[int]:
    hits: list[int] = []
    for node in ast.walk(tree):
        # Path / "private_use" (or "private_use" / x)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            for side in (node.left, node.right):
                if isinstance(side, ast.Constant) and side.value in PRIVATE_DIRS:
                    hits.append(node.lineno)
        elif _names_private_lake(node):
            hits.append(node.lineno)
    return hits


def test_only_allowlisted_modules_reference_the_private_lake() -> None:
    """(b) Every tracked non-test .py file is parsed; any reference to data/lake/private_use
    outside the allowlist fails."""
    if shutil.which("git") is None:
        pytest.skip("git is not installed")
    r = subprocess.run(["git", "-C", str(ROOT), "grep", "-l", "-E",
                        "|".join((*PRIVATE_DIRS, *sorted(PRIVATE_NAMES))), "--", "*.py"],
                       capture_output=True, text=True, check=False)
    offenders: dict[str, list[int]] = {}
    seen_allowed = set()
    for rel in r.stdout.split():
        parts = Path(rel).parts
        if "tests" in parts or Path(rel).name.startswith("test_"):
            continue
        path = ROOT / rel
        if not path.exists():
            continue
        lines = _references_private_lake(ast.parse(path.read_text("utf-8")))
        if not lines:
            continue
        if rel in PRIVATE_USE_ALLOWLIST:
            seen_allowed.add(rel)
        else:
            offenders[rel] = lines
    assert not offenders, f"modules reference the private lake outside the allowlist: {offenders}"
    assert seen_allowed == PRIVATE_USE_ALLOWLIST, (
        f"allowlisted but not found referencing it (stale entry?): "
        f"{sorted(PRIVATE_USE_ALLOWLIST - seen_allowed)}")


def test_the_allowlist_check_sees_each_reference_shape() -> None:
    for src in ('from pathlib import Path\nP = Path("x") / "lake" / "private_use"\n',
                'P = "desks/mt5/data/lake/private_use/series"\n',
                'from research.asia_collector import PRIVATE\n',
                'import research.asia_collector as collector\nx = collector.PRIVATE\n',
                'P = BASE / "data" / "intelligence_private"\n',
                'from research.proposer_common import PRIVATE_INTEL\n',
                'x = pc.PRIVATE_INTEL / "jquants"\n',
                'x = paths.private_series / "jpx_jquants.json"\n'):
        assert _references_private_lake(ast.parse(src)), src
    # prose naming the directory is not a read of it
    assert not _references_private_lake(ast.parse(
        'NOTE = "writes only under the gitignored desks/mt5/data/lake/private_use/ dir"\n'))


# ---------------------------------------------------------------------------------------------
# (d) lineage, and E8
# ---------------------------------------------------------------------------------------------

def test_private_records_carry_the_lineage_and_are_e8_ineligible(
        monkeypatch: pytest.MonkeyPatch, scratch_repo: Path) -> None:
    C = _plant(monkeypatch, scratch_repo)
    C.main(["--id", "jpx_jquants"])
    report = json.loads((scratch_repo / "desks/mt5/reports/ASIA_COLLECTOR.json")
                        .read_text("utf-8"))
    (row,) = report["rows"]
    assert row["lineage"] == T.PRIVATE_LINEAGE and row["e8_ineligible"] is True
    side = json.loads(next((scratch_repo / "desks/mt5/data/lake/private_use/series")
                           .glob("*.attribution.json")).read_text("utf-8"))
    assert side["terms_url"] and side["permitting_url"] == "https://jpx-jquants.com/en/help/usage"
    assert side["conditions"]["corporate_use_permitted"] is False and side["e8_ineligible"]


def _survivor(sym: str, fam: str, **spec_extra: Any) -> dict[str, Any]:
    return {"shadow_spec": {"symbol": sym, "family": fam, "selector": "asia", **spec_extra},
            "gates": {"expected_value": {"ev": 0.3}, "stress_costs": {"exp_x3": 0.1}},
            "days": 200}


def test_e8_book_refuses_private_lineage(monkeypatch: pytest.MonkeyPatch,
                                         tmp_path: Path) -> None:
    """COORDINATOR RULING (2026-10-07): J-Quants-derived cells never feed an E8 sleeve; the
    refusal is named in the book. A Fusion-only cell is unaffected."""
    from prop import e8_book as B

    surv = tmp_path / "UNIVERSAL_SURVIVORS.json"
    surv.write_text(json.dumps({"survivors": {
        "pub": _survivor("USDJPY", "session_range_breakout"),
        "priv_spec": _survivor("JP225", "overnight_gap_decay", lineage=T.PRIVATE_LINEAGE),
        "priv_flag": {**_survivor("EURJPY", "carry"), "e8_ineligible": True},
        "priv_parent": {**_survivor("GBPJPY", "carry"),
                        "parents": [{"source": "jpx_jquants", "private_use": True}]},
    }}), encoding="utf-8")
    monkeypatch.setattr(B, "SURVIVORS", surv)
    monkeypatch.setattr(B, "_family_banned", lambda fam: False)
    doc = B.select(tradeable=None)
    chosen = {r["key"] for r in doc["sleeves"]}
    refused = {r["key"] for r in doc["refused_private_lineage"]}
    assert "pub" in chosen
    assert refused == {"priv_spec", "priv_flag", "priv_parent"} and not (chosen & refused)
    assert doc["n_refused_private_lineage"] == 3
