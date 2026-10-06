"""FENCE: no J-Quants (private-use) value reaches a tracked path. The repository is PUBLIC.

J-Quants is permitted for the registered individual's private use only (art. 8; the principal's
answer of 2026-10-06, recorded in libs.ops.token_refresh.TERMS_EVIDENCE["jquants"]). This runs the
asia collector's whole pass against a fake transport inside a scratch git repository that carries
this repository's own .gitignore, then checks EVERY file the pass wrote: either git ignores it, or
it holds no J-Quants value and no private-use row content.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "desks" / "mt5") not in sys.path:
    sys.path.insert(0, str(ROOT / "desks" / "mt5"))

from libs.ops import token_refresh as T  # noqa: E402

SENTINEL = "JQ-PRIVATE-VALUE-7731"      # a value only the J-Quants payload carries
COLUMN = "ForeignersNetJQ"              # a field name only the J-Quants payload carries
API_KEY = "fake-jq-key-0123456789"


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
