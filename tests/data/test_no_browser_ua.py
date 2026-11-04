"""No non-test code carries a browser or named-crawler User-Agent (auditor ruling 2026-10-14).

The desk identifies itself as itself: `libs.data.polite_fetch.DESK_UA`. A browser string
("Mozilla/5.0 ... Chrome/... Safari/...") or another company's crawler name in a request is
impersonation, and a refusal of the honest name is recorded as a hold, never routed around with a
disguise. This scan reads every tracked non-test .py file's STRING LITERALS (by AST, so comments
explaining the rule do not trip it) and fails on any browser or crawler UA token. Probe scripts,
retired scripts and code templates are included: a probe that reaches a site is a fetcher.

The ONLY allow-list entry is the detection code itself -- the token tuple in polite_fetch that
`honest_headers` matches against.
"""
from __future__ import annotations

import ast
import io
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]

#: Browser engines/products and other companies' crawlers, as they appear in a UA string. A bare
#: "Mozilla/" (the "Mozilla/5.0" every browser string opens with) is enough on its own.
UA_TOKEN = re.compile(
    r"mozilla/|applewebkit|gecko/|chrome/\d|chromium/\d|crios/\d|safari/\d|firefox/\d"
    r"|\bedg/\d|\bedge/\d|\bopr/\d|\bopera/\d|opera mini|presto/\d|msie \d|trident/\d"
    r"|googlebot|adsbot-google|bingbot|baiduspider|yandexbot|duckduckbot|applebot"
    r"|facebookexternalhit|petalbot|bytespider", re.I)
#: Cheap pre-filter on the raw source: a file with none of these fragments cannot fold to a UA
#: token (a token split across a `+` still leaves one of its halves here).
_FRAGMENTS = re.compile(
    r"mozi|illa|webkit|gecko|chrom|crios|safari|firefox|fox/|edg|opr|opera|presto|msie|trident"
    r"|google|bingb|baidu|yandex|duckduck|applebot|facebookext|petal|bytesp", re.I)

#: (file, assignment target) whose string elements ARE the detector's token list.
ALLOWED_ASSIGNMENTS = {("libs/data/polite_fetch.py", "IMPERSONATION_UA_TOKENS")}


def _is_test(rel: str) -> bool:
    parts = rel.split("/")
    name = parts[-1]
    # Only the test tree and pytest's own files. `side_channels/cot_test.py` is a probe that
    # reaches the network, not a test, so a `_test.py` suffix does not exempt a file.
    return "tests" in parts[:-1] or name.startswith("test_") or name == "conftest.py"


def _tracked_py() -> list[str]:
    try:
        out = subprocess.run(["git", "ls-files", "-z", "--", "*.py"], cwd=ROOT,
                             capture_output=True, check=True, timeout=60).stdout
        files = [f for f in out.decode("utf-8", "replace").split("\0") if f]
    except (OSError, subprocess.SubprocessError):
        files = [p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*.py")
                 if ".git" not in p.parts and ".claude" not in p.parts]
    return sorted(f for f in files if not _is_test(f))


def _allowed_nodes(tree: ast.AST, rel: str) -> set[int]:
    keep: set[int] = set()
    for node in ast.walk(tree):
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        for t in targets:
            if isinstance(t, ast.Name) and (rel, t.id) in ALLOWED_ASSIGNMENTS:
                keep.update(id(n) for n in ast.walk(node))
    return keep


def _fold(node: ast.AST) -> str | None:
    """The text a string expression evaluates to, as far as it is static: str and bytes
    constants, `+` concatenations of them, and f-strings with each placeholder read as "0" (so
    `f"Chrome/{v}"` reads "Chrome/0"). None when the node is not a string expression."""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, str):
            return node.value
        if isinstance(node.value, bytes):
            return node.value.decode("latin-1")
        return None
    if isinstance(node, ast.JoinedStr):
        return "".join(_fold(v) or "0" if isinstance(v, ast.Constant) else "0"
                       for v in node.values)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _fold(node.left), _fold(node.right)
        if left is None and right is None:
            return None
        return (left if left is not None else "0") + (right if right is not None else "0")
    return None


def browser_ua_literals(rel: str, src: str) -> list[int]:
    """Line numbers of string expressions in `src` (str/bytes literals, concatenations,
    f-strings) that carry a browser/crawler UA token."""
    if not _FRAGMENTS.search(src):
        return []
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return [0]
    allowed = _allowed_nodes(tree, rel)
    hits: set[int] = set()
    for n in ast.walk(tree):
        if id(n) in allowed or not isinstance(n, (ast.Constant, ast.JoinedStr, ast.BinOp)):
            continue
        text = _fold(n)
        if text and UA_TOKEN.search(text):
            hits.add(n.lineno)
    return sorted(hits)


def test_no_non_test_file_carries_a_browser_ua() -> None:
    hits: dict[str, list[int]] = {}
    scanned = 0
    for rel in _tracked_py():
        p = ROOT / rel
        if not p.is_file():
            continue                      # sparse checkout: not on disk here
        scanned += 1
        lines = browser_ua_literals(rel, p.read_text(encoding="utf-8", errors="replace"))
        if lines:
            hits[rel] = lines
    assert scanned > 100, f"scanned only {scanned} files -- the walk is broken, not the code clean"
    assert not hits, ("browser/crawler User-Agent literals in non-test code (use "
                      f"libs.data.polite_fetch.DESK_UA): {hits}")


def test_the_scanner_catches_what_it_must_and_spares_the_detector() -> None:
    assert browser_ua_literals("x.py", 'UA = "Mozilla/5.0 (X11) AppleWebKit/537.36"\n') == [1]
    assert browser_ua_literals("x.py", 'h = {"User-Agent": "Googlebot/2.1"}\n') == [1]
    assert browser_ua_literals("x.py", 'h = {"User-Agent": "Opera/9.80 Presto/2.12"}\n') == [1]
    assert browser_ua_literals("x.py", 'tpl = """\\nua = \\"Chrome/125.0\\"\\n"""\n') == [1]
    assert browser_ua_literals("x.py", 'UA = "Mozilla/5.0"\n') == [1]
    assert browser_ua_literals("x.py", 'UA = b"Mozilla/5.0 (X11)"\n') == [1]
    assert browser_ua_literals("x.py", 'UA = "Mozi" + "lla/5.0"\n') == [1]
    assert browser_ua_literals("x.py", 'UA = f"Chrome/{v} Safari/537"\n') == [1]
    assert browser_ua_literals("x.py", 'UA = f"x {v} " + "Firefox/" + v\n') == [1]
    assert browser_ua_literals("x.py", 'UA = "Mozilla/5.0 Gecko/20100101 Firefox/128.0"\n') == [1]
    assert browser_ua_literals("x.py", 'UA = "Mozilla/5.0 Edg/126.0"\n') == [1]
    # a comment is not a literal, and "operations" is not Opera
    assert browser_ua_literals("x.py", '# Mozilla/5.0 was here\nx = "operations"\n') == []
    detector = 'IMPERSONATION_UA_TOKENS = ("mozilla/", "googlebot")\n'
    assert browser_ua_literals("libs/data/polite_fetch.py", detector) == []
    assert browser_ua_literals("libs/data/other.py", detector) == [1]


# ------------------------------------------------------------------ what actually goes on the wire
class _Resp(io.BytesIO):
    def __init__(self, body: bytes, url: str) -> None:
        super().__init__(body)
        self.status = 200
        self.url = url
        self.headers = {"Content-Type": "text/plain" if url.endswith("robots.txt")
                        else "text/html"}


def _recording_opener(sent: list[tuple[str, str]]) -> Any:
    def opener(req: Any, timeout: float = 0, context: Any = None) -> _Resp:
        sent.append((req.full_url, str(req.get_header("User-agent"))))
        body = (b"User-agent: *\nDisallow:\n" if req.full_url.endswith("/robots.txt")
                else b"<html><body>EURUSD carry</body></html>")
        return _Resp(body, req.full_url)
    return opener


def test_polite_fetch_get_sends_exactly_the_desk_ua_on_every_request() -> None:
    from libs.data import polite_fetch as pf
    sent: list[tuple[str, str]] = []
    r = pf.get("https://a.test/p", opener=_recording_opener(sent), gate=None,
               access=pf.HostAccess(path=None), sleep=lambda s: None,
               headers={"User-Agent": "Mozilla/5.0 (X11) AppleWebKit/537.36 Chrome/124.0"})
    assert r.ok and [u for u, _ in sent] == ["https://a.test/robots.txt", "https://a.test/p"]
    assert all(ua == pf.DESK_UA for _, ua in sent), sent


def test_world_crawler_sends_exactly_the_desk_ua_on_every_request(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.data import polite_fetch as pf
    side = str(ROOT / "desks" / "mt5" / "side_channels")
    for p in (str(ROOT / "desks" / "mt5"), side):
        if p not in sys.path:
            sys.path.insert(0, p)
    import world_crawler as wc  # type: ignore[import-not-found]
    sent: list[tuple[str, str]] = []
    opener = _recording_opener(sent)
    monkeypatch.setattr(wc, "_open", lambda req, timeout: opener(req, timeout))
    raw, why = wc.fetch("https://a.test/page", wc.HostAccess(path=None, now=1_000_000.0))
    assert raw and why == "" and len(sent) == 2
    assert all(ua == pf.DESK_UA for _, ua in sent), sent
    assert wc.UA == pf.DESK_UA
