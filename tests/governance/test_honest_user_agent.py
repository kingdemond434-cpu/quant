"""THE FETCH LAW, FENCED: an honest User-Agent everywhere, and no refused host in a side channel.

Two hard rules of the desk's data law (2026-11-18 audit):

1. Every automated request names what is reading (``libs/data/honest_ua.py``). Before this fence
   88 non-test modules sent a desktop-Chrome string (one also published a personal e-mail
   address), so a host's robots.txt could not address the desk and its operators could not tell
   who was reading. ``test_no_module_impersonates_a_browser`` scans every non-test ``.py`` file
   for browser User-Agent tokens and fails on any that is not allowlisted below WITH A REASON.

2. A host whose terms refuse automated collection (``libs/data/refused_hosts.py``) is never
   fetched. ``earnings_miner`` read finance.yahoo.com; it is now a BLOCKED_ON_TERMS stub.
   ``test_no_side_channel_targets_a_refused_host`` reads every URL literal in
   ``desks/mt5/side_channels`` and fails on a refused host that is not allowlisted with a reason.

An allowlist entry that no longer matches anything fails too, so the list cannot rot into a
licence for whatever lands there next.
"""
from __future__ import annotations

import ast
import itertools
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from libs.data.honest_ua import HONEST_UA, ROBOTS_AGENT  # noqa: E402
from libs.data.refused_hosts import refusal  # noqa: E402

#: Tokens only a browser's User-Agent carries.
BROWSER_TOKENS = re.compile(r"Mozilla/\d|AppleWebKit/|Chrome/\d|Safari/\d|Gecko/\d|Firefox/\d")
#: Directories never scanned: tests (they may assert on these strings), vendored/derived trees.
_SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", "site-packages", "tests",
              ".mypy_cache", ".ruff_cache", ".pytest_cache"}

#: repo-relative path -> why a browser token there is NOT a spoofed User-Agent. Every entry must
#: still match, or the test fails. Sealed files that spoof are listed for a human, never edited.
BROWSER_TOKEN_ALLOWLIST: dict[str, str] = {}

#: (repo-relative path, refused domain) -> why the URL literal there is not a fetch of that host.
REFUSED_HOST_ALLOWLIST: dict[tuple[str, str], str] = {
    ("desks/mt5/side_channels/seed_miners.py", "archive.org"): (
        "the Wayback CDX miners stay registered as held routes: seed_miners.fetch() calls "
        "terms_refusal() and raises PermissionError BEFORE any request, and SOURCE_WALLS records "
        "the TERMS_REFUSED verdict with its missed_growth line (asserted below)"),
    ("desks/mt5/side_channels/youtube_miner.py", "youtube.com"): (
        "a citation link built for an output row (https://youtube.com/watch?v=<id>); the module "
        "never requests it"),
}


def _non_test_py_files() -> list[Path]:
    out = []
    for p in ROOT.rglob("*.py"):
        rel = p.relative_to(ROOT)
        if any(part in _SKIP_DIRS for part in rel.parts[:-1]):
            continue
        if rel.name.startswith("test_") or rel.name == "conftest.py":
            continue
        out.append(p)
    return out


def test_the_honest_name_is_honest() -> None:
    assert HONEST_UA.startswith(ROBOTS_AGENT + "/")
    assert not BROWSER_TOKENS.search(HONEST_UA)
    assert "@" not in HONEST_UA and "github.com" not in HONEST_UA, (
        "the client name publishes nothing about who runs the desk")


def test_no_module_impersonates_a_browser() -> None:
    hits: dict[str, list[str]] = {}
    for p in _non_test_py_files():
        try:
            text = p.read_text("utf-8", errors="replace")
        except OSError:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if BROWSER_TOKENS.search(line):
                hits.setdefault(p.relative_to(ROOT).as_posix(), []).append(f"{n}: {line.strip()}")
    offenders = {k: v for k, v in hits.items() if k not in BROWSER_TOKEN_ALLOWLIST}
    assert not offenders, (
        "a module sends (or builds) a browser User-Agent; use libs.data.honest_ua.HONEST_UA, or "
        "allowlist it here with the reason it is not a spoofed UA:\n"
        + "\n".join(f"  {k}\n    " + "\n    ".join(v[:3]) for k, v in sorted(offenders.items())))
    stale = sorted(set(BROWSER_TOKEN_ALLOWLIST) - set(hits))
    assert not stale, f"allowlist entries that no longer match anything: {stale}"
    assert all(why.strip() for why in BROWSER_TOKEN_ALLOWLIST.values())


#: What a User-Agent must never carry: a repository or code-host URL, the repository owner's
#: handle, or an e-mail address. A UA names the client; a person or contact in it is personal
#: data sent to every host (four audit HOLDs of this class on 2026-11-18: #1330, #1335, #1339,
#: #1341). SEC EDGAR's required contact is the owner's own EDGAR_UA key, read at run time, never
#: a literal, so it never appears here.
def _owner_handle() -> str:
    """The repository owner's handle, read from the origin remote so the fence follows the repo
    if it moves; the historic handle stands when no remote is readable (a tarball checkout)."""
    import subprocess
    try:
        url = subprocess.run(["git", "remote", "get-url", "origin"], cwd=ROOT, capture_output=True,
                             text=True, timeout=10, check=False).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        url = ""
    m = re.search(r"github\.com[:/]+([^/]+)/", url)
    return m.group(1) if m else "kingdemond434-cpu"


_HANDLE = re.escape(_owner_handle().split("-")[0])
UA_FORBIDDEN = re.compile(rf"github\.com|gitlab\.com|{_HANDLE}|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\."
                          r"[A-Za-z]{2,}")
_UA_NAME = re.compile(r"(^|_)(UA|USER_AGENT|AGENT|HEADERS?)$|user_?agent", re.I)


def _ua_literals(path: Path) -> list[tuple[int, str]]:
    """String constants a module uses as a User-Agent: assigned to a UA-like name, the value of a
    'User-Agent' dict key, or the argument after curl's -A."""
    try:
        tree = ast.parse(path.read_text("utf-8", errors="replace"), filename=str(path))
    except SyntaxError:
        return []
    out: list[tuple[int, str]] = []

    def strings(node: ast.AST) -> list[ast.Constant]:
        return [n for n in ast.walk(node) if isinstance(n, ast.Constant)
                and isinstance(n.value, str)]

    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names = [t.id for t in targets if isinstance(t, ast.Name)]
            if node.value is not None and any(_UA_NAME.search(n) for n in names):
                out += [(c.lineno, c.value) for c in strings(node.value)]
        elif isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values, strict=True):
                if isinstance(k, ast.Constant) and str(k.value).lower() == "user-agent":
                    out += [(c.lineno, c.value) for c in strings(v)]
        elif isinstance(node, ast.List):
            for a, b in itertools.pairwise(node.elts):
                if isinstance(a, ast.Constant) and a.value in ("-A", "--user-agent"):
                    out += [(c.lineno, c.value) for c in strings(b)]
    return out


def test_no_user_agent_names_a_person_repository_or_contact() -> None:
    hits: dict[str, list[str]] = {}
    for p in _non_test_py_files():
        for line, value in _ua_literals(p):
            if UA_FORBIDDEN.search(value):
                hits.setdefault(p.relative_to(ROOT).as_posix(), []).append(f"{line}: {value!r}")
    assert not hits, (
        "a User-Agent literal names a repository, its owner or an e-mail address; use "
        "libs.data.honest_ua.HONEST_UA:\n"
        + "\n".join(f"  {k}\n    " + "\n    ".join(v[:3]) for k, v in sorted(hits.items())))


def test_the_ua_scan_sees_each_shape() -> None:
    import tempfile
    src = ('UA = "x/1 (+https://github.com/someone/repo)"\n'
           'H = {"User-Agent": "bot me@example.org"}\n'
           f'cmd = ["curl", "-A", "{_owner_handle()}-bot", "u"]\n'
           'OK_UA = "quant-desk-research/1.0 (automated research; honours robots.txt)"\n')
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "m.py"
        f.write_text(src, encoding="utf-8")
        bad = [v for _, v in _ua_literals(f) if UA_FORBIDDEN.search(v)]
    assert len(bad) == 3


def _url_literals(path: Path) -> list[str]:
    tree = ast.parse(path.read_text("utf-8", errors="replace"), filename=str(path))
    urls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            urls.extend(re.findall(r"https?://[^\s\"'<>)]+", node.value))
    return urls


def _refused_domain(url: str) -> str | None:
    from libs.data.refused_hosts import REFUSED_HOSTS, host_of
    host = host_of(url) or ""
    for domain in REFUSED_HOSTS:
        if host == domain or host.endswith("." + domain):
            return domain
    return None


def test_no_side_channel_targets_a_refused_host() -> None:
    root = ROOT / "desks" / "mt5" / "side_channels"
    seen: set[tuple[str, str]] = set()
    offenders: list[str] = []
    for p in sorted(root.rglob("*.py")):
        rel = p.relative_to(ROOT).as_posix()
        if "__pycache__" in rel or "/tests/" in rel or p.name.startswith("test_"):
            continue
        for url in _url_literals(p):
            domain = _refused_domain(url)
            if domain is None:
                continue
            assert refusal(url), url
            key = (rel, domain)
            seen.add(key)
            if key not in REFUSED_HOST_ALLOWLIST:
                offenders.append(f"{rel}: {url}")
    assert not offenders, ("a side channel names a terms-refused host as a URL; make the route a "
                           "BLOCKED_ON_TERMS stub with a missed_growth line:\n  "
                           + "\n  ".join(offenders))
    stale = sorted(set(REFUSED_HOST_ALLOWLIST) - seen)
    assert not stale, f"allowlist entries that no longer match anything: {stale}"


def test_the_allowlisted_wayback_routes_refuse_before_any_request(
        monkeypatch: pytest.MonkeyPatch) -> None:
    sc = ROOT / "desks" / "mt5" / "side_channels"
    monkeypatch.syspath_prepend(str(sc))
    import seed_miners  # type: ignore[import-not-found]

    called: list[str] = []
    monkeypatch.setattr(seed_miners.requests, "get",
                        lambda url, **_: called.append(url))  # pragma: no cover - must not run
    for url in ("http://web.archive.org/cdx/search/cdx?url=x", "https://web.archive.org/web/1/x"):
        try:
            seed_miners.fetch(url)
        except PermissionError as exc:
            assert "BLOCKED_ON_TERMS" in str(exc)
        else:  # pragma: no cover
            raise AssertionError(f"{url} was not refused")
    assert called == []


def test_the_earnings_channel_is_a_blocked_on_terms_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    sc = ROOT / "desks" / "mt5" / "side_channels"
    monkeypatch.syspath_prepend(str(sc))
    src = (sc / "earnings_miner.py").read_text("utf-8")
    assert "requests" not in src and "urlopen" not in src, "the earnings channel makes no request"
    import earnings_miner  # type: ignore[import-not-found]

    rows = earnings_miner.mine_earnings_calendar()
    assert len(rows) == 1
    row = rows[0]
    assert row["kind"] == "stub" and row["needs_selector_work"] is True
    assert row["status"] == "BLOCKED_ON_TERMS" and row["why"].startswith("BLOCKED_ON_TERMS")
    assert row["missed_growth"].startswith("missed_growth:")
    assert "sec_8k_guidance" in row["substitute"]


def test_every_bare_script_fallback_sends_the_same_name() -> None:
    """Scripts that run without the repo root on sys.path carry a literal fallback; it must be the
    shared constant word for word, or the desk reads under two names."""
    pat = re.compile(r'^[ ]+HONEST_UA\s*=\s*"([^"]*)"\s*$', re.M)
    drift = {}
    count = 0
    for p in _non_test_py_files():
        for lit in pat.findall(p.read_text("utf-8", errors="replace")):
            count += 1
            if lit != HONEST_UA:
                drift[p.relative_to(ROOT).as_posix()] = lit
    assert count > 0
    assert not drift, f"fallback literals that differ from libs.data.honest_ua.HONEST_UA: {drift}"


def test_the_youtube_data_api_is_refused_by_path_not_the_whole_google_host():
    """Governance 2026-11-18: the box never contacts YouTube, API included; the rest of
    googleapis.com stays reachable."""
    from libs.data.refused_hosts import refusal
    assert refusal("https://www.googleapis.com/youtube/v3/search?q=x")
    assert refusal("https://youtube.googleapis.com/youtube/v3/search")
    assert refusal("https://www.googleapis.com/books/v1/volumes") is None


def test_youtube_miner_opens_no_connection_even_with_a_key(monkeypatch):
    import sys
    sys.path.insert(0, str(ROOT / "desks" / "mt5"))
    from side_channels import youtube_miner as ym
    calls = []
    monkeypatch.setattr(ym, "API_KEY", "present-but-unused")
    monkeypatch.setattr(ym.requests, "get", lambda *a, **k: calls.append(a))
    assert ym._search_api("gold breakout") == []
    assert calls == []
