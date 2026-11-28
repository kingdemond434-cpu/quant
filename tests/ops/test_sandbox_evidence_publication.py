"""THE SANDBOX EVIDENCE CROSSES THE PUBLIC WIRE, AND ONLY WHAT THE GOVERNANCE RULING ALLOWED.

zuck, 2026-11-17: every sandbox must show fresh production every pass. The runner, the roster,
the liveness verdict and the organ censuses were written hourly on the trading box and never
left it, so a dark or stalled system could not be named from the branch. Governance agreed
(20:44Z) to add them to `sync_shadow_to_git.ps1`'s `$reportPaths` on four conditions, each
pinned here:

  1. the script change is literal quoted paths inside the allowlist block, every one under
     STATE_PREFIXES and none a governed or secret path;
  2. `.gitignore` gains only the matching `!` lines;
  3. a pinned negative test for each violation;
  4. a secret and account-field scan, with the redaction done by the PRODUCER, because the
     repository is public.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from libs.ops import release
from libs.ops.public_report import PATH, WITHHELD, public_string, redact

ROOT = Path(__file__).resolve().parents[2]
SYNC = ROOT / "desks" / "mt5" / "scripts" / "sync_shadow_to_git.ps1"
GITIGNORE = ROOT / ".gitignore"

#: The paths the ruling named. A copy on purpose: the block may only ever grow by a ruling.
PUBLISHED = (
    "desks/mt5/reports/SANDBOX_RUNNER.json",
    "desks/mt5/reports/SANDBOX_ROSTER.json",
    "desks/mt5/reports/SANDBOX_LIVENESS.json",
    "desks/mt5/data/sandbox_runner_state.json",
    "desks/mt5/reports/ORGAN_CENSUS.json",
    "desks/mt5/reports/PRODUCER_CENSUS.json",
    "desks/mt5/reports/PRODUCTIVITY_CENSUS.json",
    "desks/mt5/reports/dead_architecture.json",
)

#: Each published path, the producer that writes it, and the expression that must pass its
#: document through `redact(` on the way to disk.
PRODUCERS = {
    "desks/mt5/reports/SANDBOX_RUNNER.json": ("desks/mt5/research/sandbox_runner.py",
                                              "_write(report_path, redact(doc))"),
    "desks/mt5/data/sandbox_runner_state.json": ("desks/mt5/research/sandbox_runner.py",
                                                 "_write(state_path, redact(state))"),
    "desks/mt5/reports/SANDBOX_ROSTER.json": ("desks/mt5/research/sandbox_roster.py",
                                              "_write(REPORT, redact(doc))"),
    "desks/mt5/reports/SANDBOX_LIVENESS.json": ("scripts/check_sandbox_liveness.py",
                                                "_write(OUT, redact(rep))"),
    "desks/mt5/reports/ORGAN_CENSUS.json": ("scripts/check_organ_census.py",
                                            "json.dumps(redact(doc)"),
    "desks/mt5/reports/PRODUCER_CENSUS.json": ("scripts/check_seat_health.py",
                                               "json.dumps(redact(census_doc)"),
    "desks/mt5/reports/PRODUCTIVITY_CENSUS.json": ("desks/mt5/research/productivity_census.py",
                                                   "json.dumps(redact(census)"),
    "desks/mt5/reports/dead_architecture.json": ("scripts/check_dead_architecture.py",
                                                 "json.dumps(redact(doc)"),
}

_SECRETISH = re.compile(r"(?i)(^|/)(secrets?|authority|key)(/|$)|\.key$|_ACCOUNT\.json|ARMED|"
                        r"credential|password|token")


def _report_block() -> str:
    src = SYNC.read_text("utf-8", errors="ignore")
    start = src.index("$reportPaths = @(")
    return src[start:src.index("\n)", start)]


def _listed() -> list[str]:
    return re.findall(r'^\s*"([^"]+)",?\s*$', _report_block(), flags=re.M)


def violations(rel: str, *, listed_line: str | None = None) -> list[str]:
    """Every way `rel` breaks the ruling. Empty means it may ride the wire."""
    out: list[str] = []
    line = listed_line if listed_line is not None else f'    "{rel}",'
    if not re.fullmatch(r'\s*"[A-Za-z0-9_./-]+",?\s*', line):
        out.append("not a literal quoted path")
    if any(c in rel for c in "$*?[]{}") or rel.startswith("/") or ".." in rel.split("/"):
        out.append("not a plain repo-relative path")
    if not release.is_state_path(rel):
        out.append("not under STATE_PREFIXES")
    if release.is_governed_state(rel):
        out.append("governed state")
    if _SECRETISH.search(rel):
        out.append("secret or account path")
    return out


# --- condition 1: literal, state, never governed or secret --------------------------------------

def test_the_block_is_found() -> None:
    assert len(_listed()) >= 20, "the $reportPaths parse found almost nothing: the fence is blind"


@pytest.mark.parametrize("rel", PUBLISHED)
def test_every_ruled_path_is_listed_and_lawful(rel: str) -> None:
    assert rel in _listed(), f"{rel} is not in $reportPaths, so it never leaves the box"
    line = next(ln for ln in _report_block().splitlines() if f'"{rel}"' in ln)
    assert violations(rel, listed_line=line) == []


@pytest.mark.parametrize(("rel", "line", "why"), [
    ("desks/mt5/reports/$name.json", None, "not a plain repo-relative path"),
    ("desks/mt5/reports/*.json", None, "not a plain repo-relative path"),
    ("desks/mt5/reports/X.json", '    ("desks/mt5/reports/" + $x),', "not a literal quoted path"),
    ("desks/mt5/research/sandbox_runner.py", None, "not under STATE_PREFIXES"),
    ("libs/ops/release.py", None, "not under STATE_PREFIXES"),
    ("../outside.json", None, "not a plain repo-relative path"),
    ("desks/mt5/data/ALLOCATOR_SOVEREIGN.json", None, "governed state"),
    ("desks/mt5/data/LIVE_MANIFEST.jsonl", None, "governed state"),
    ("desks/mt5/data/GENERIC_EXEC_ENABLED.json", None, "governed state"),
    ("desks/mt5/data/secrets/broker.json", None, "secret or account path"),
    ("data/secrets/github.json", None, "secret or account path"),
    ("desks/mt5/data/FTMO_LIVE_ACCOUNT.json", None, "secret or account path"),
    ("desks/mt5/data/E8_ACCOUNT.json", None, "secret or account path"),
    ("desks/mt5/data/FTMO_FOLLOWER_ARMED", None, "secret or account path"),
    ("desks/mt5/data/api_token.json", None, "secret or account path"),
])
def test_each_violation_is_refused(rel: str, line: str | None, why: str) -> None:
    assert why in violations(rel, listed_line=line)


# --- condition 2: .gitignore gains only the matching ! lines -------------------------------------

def _ignored(rel: str) -> bool:
    return subprocess.run(["git", "check-ignore", "-q", "--", rel], cwd=ROOT,
                          check=False).returncode == 0


@pytest.mark.parametrize("rel", PUBLISHED)
def test_every_ruled_path_survives_gitignore(rel: str) -> None:
    assert not _ignored(rel), f"{rel} is listed but ignored: git add stages nothing, silently"


def test_gitignore_block_is_only_the_matching_negations() -> None:
    text = GITIGNORE.read_text("utf-8")
    start = text.index("# The sandbox federation's evidence and the organ censuses")
    tail = text[start:].splitlines()
    rules = [ln for ln in tail if ln.strip() and not ln.startswith("#")]
    reports = [p for p in PUBLISHED if "/reports/" in p]
    assert rules[:len(reports)] == [f"!{p}" for p in reports], rules


def test_no_ruled_path_is_ignored_by_name_elsewhere() -> None:
    """A later broad rule would re-ignore them; last match wins, so the negations must stay last
    among the rules that touch these names."""
    for rel in PUBLISHED:
        why = subprocess.run(["git", "check-ignore", "-v", "--no-index", "--", rel], cwd=ROOT,
                             capture_output=True, text=True, check=False).stdout
        assert not why or "!" in why.split("\t")[0], why


# --- condition 4: the producer redacts, and the scan proves it -----------------------------------

@pytest.mark.parametrize("rel", PUBLISHED)
def test_the_producer_redacts_before_writing(rel: str) -> None:
    src_rel, expr = PRODUCERS[rel]
    src = (ROOT / src_rel).read_text("utf-8")
    assert re.search(r"from libs\.ops\.public_report import [\w, ]*\bredact\b", src), src_rel
    assert expr in src, f"{src_rel} writes {rel} without redact(): {expr!r} not found"


_CREDENTIAL = re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_|\bsk-[A-Za-z0-9_-]{16,}|"
                         r"PRIVATE KEY-----")
_BOX = Path("C:/opt/quant")
_DIRTY = {
    "root": r"C:\Users\Administrator\sandboxes",
    "python": r"C:\Program Files\Python313\python.exe",
    "host": "vmi3571445",
    "COMPUTERNAME": "VMI3571445",
    "login": 51234567,
    "account": "51234567",
    "server": "FusionMarkets-Live",
    "api_key": "abc123def456",
    "detail": r"C:\opt\quant\desks\mt5\reports\SANDBOX_RUNNER.json is absent",
    "why": "adapter raised: OSError at /home/quant/quant-platform/x.py via 203.0.113.7",
    "note": "server=FusionMarkets-Live login: 51234567 equity 101,234.50 on dash.example.xyz",
    "leak": "token ghp_abcdefghijklmnopqrstuvwxyz0123456789 and sk-abcdefghijklmnop1234",
    "share": r"\\fileserver\share\dump.csv",
    "rows": [{"system_id": "gh:owner/repo", "pnl": 1.25, "sharpe": 0.8, "runs": 3,
              "cells": ["momentum|EURUSD|1h"], "folder": r"C:\opt\quant\sandboxes\gh_owner"}],
}
_NEEDLES = ("vmi3571445", "VMI3571445", "51234567", "FusionMarkets", "abc123def456",
            "Administrator", "Program Files", "/home/quant", "203.0.113.7", "101,234",
            "dash.example.xyz", "ghp_", "sk-abc", "fileserver", "C:\\", "C:/")


def test_redaction_leaves_no_host_account_or_secret() -> None:
    blob = json.dumps(redact(_DIRTY, _BOX))
    leaked = [n for n in _NEEDLES if n in blob]
    assert not leaked, f"published bytes still carry {leaked}"


def test_redaction_keeps_the_research_and_repo_paths() -> None:
    clean = redact(_DIRTY, _BOX)
    row = clean["rows"][0]
    assert (row["pnl"], row["sharpe"], row["runs"]) == (1.25, 0.8, 3)
    assert row["cells"] == ["momentum|EURUSD|1h"] and row["system_id"] == "gh:owner/repo"
    assert row["folder"] == "sandboxes/gh_owner"
    assert clean["detail"] == "desks/mt5/reports/SANDBOX_RUNNER.json is absent"
    assert clean["host"] == WITHHELD and clean["root"] == PATH


def test_public_string_never_raises_on_odd_input() -> None:
    for s in ("", "C:", "\\\\", "/", "/home", "x" * 10_000):
        assert isinstance(public_string(s, _BOX), str)


@pytest.mark.parametrize("rel", PUBLISHED)
def test_a_copy_present_here_is_already_clean(rel: str) -> None:
    """On the box (or after a publish lands) the real bytes are scanned too."""
    p = ROOT / rel
    if not p.is_file():
        pytest.skip(f"{rel} is not on this host")
    text = p.read_text("utf-8", errors="ignore")
    found = [m.group(0)[:6] for m in _CREDENTIAL.finditer(text)]
    assert not found, f"{rel} on this host carries credential-shaped text: {found}"


# --- AUDIT HOLD MF1 (2026-11-17): exception text quoted credentials through redact() -------------

_HEX40 = "0123456789abcdef0123456789abcdef01234567"
_HEX32 = "fedcba9876543210fedcba9876543210"


@pytest.mark.parametrize(("text", "secret"), [
    ("adapter raised: ConnectionError: HTTPSConnectionPool(host='api.example.gov', port=443): "
     f"Max retries exceeded with url: /v1/obs?series=GDP&api_key={_HEX40}&fmt=json", _HEX40),
    (f"REJECTED_WITH_EVIDENCE: GET https://api.example.gov/v2?registrationkey={_HEX32} -> 401",
     _HEX32),
    ('cell import failed: ValueError: bad config {"token": "s3cr3t-value-123", "n": 3}',
     "s3cr3t-value-123"),
    ("ledger_error: KeyError {'api_key': 'abcdEFGH1234zz'}", "abcdEFGH1234zz"),
    ("errors: login refused password=hunter2hunter2 for the seat", "hunter2hunter2"),
    ("adapter raised: HTTPError 403: Authorization: Bearer eyJhbGciOi.payload.sig", "eyJhbGciOi"),
    ("clone failed: https://bob:pw-123456@git.example.org/r.git", "pw-123456"),
])
def test_exception_text_never_carries_a_credential(text: str, secret: str) -> None:
    for doc in (text, {"why_unmeasured": text}, {"errors": [text]}):
        out = json.dumps(redact(doc, _BOX))
        assert secret not in out, f"{secret!r} survived: {out}"
        assert "withheld" in out


def test_a_count_named_like_a_secret_keeps_its_number() -> None:
    clean = redact({"n_token": 3, "token_count": 4, "n_tokens": 5, "token": "abc",
                    "login": 51234567}, _BOX)
    assert (clean["n_token"], clean["token_count"]) == (3, 4)
    assert clean["token"] == WITHHELD and clean["login"] == WITHHELD


def test_a_withheld_query_is_still_readable() -> None:
    out = public_string(f"GET /v1?series=GDP&api_key={_HEX40}", _BOX)
    assert out == f"GET /v1?series={WITHHELD}&api_key={WITHHELD}"


# --- AUDIT HOLD 2 (2026-11-17): a denylist cannot fence an exception's message ------------------
#
# So no published field carries one. A writer formats an exception ONLY through
# `public_report.exc_text(exc)` (its type name; the message goes to the task's log on the box),
# error-named keys keep only a type name, and subprocess output keys are withheld whole.

from libs.ops.public_report import WITHHELD_OUTPUT, exc_text  # noqa: E402

_AUDIT_STRINGS = (
    f"GET https://www.example.mx/api/indicadores/{_HEX40}/json failed",       # key in the path
    "headers={'X-Api-Key': 'abcd1234efgh5678'}",                              # header dict
    '{"token": "abc 123 secret"}',                                            # spaced value
    f"retrying with key={_HEX32}",                                            # bare key=
    f"GET /v1?api_key%3D{_HEX40}",                                            # URL-encoded
)


@pytest.mark.parametrize("message", _AUDIT_STRINGS)
def test_an_exception_publishes_its_type_and_nothing_else(message: str) -> None:
    for exc in (ValueError(message), ConnectionError(message), KeyError(message)):
        assert exc_text(exc) == type(exc).__name__
        for doc in ({"why": f"adapter raised: {exc_text(exc)}"}, {"error": exc_text(exc)},
                    {"errors": [f"EURUSD/momentum: {exc_text(exc)}"]}):
            assert message not in json.dumps(redact(doc, _BOX))


@pytest.mark.parametrize("message", _AUDIT_STRINGS)
def test_an_error_field_holding_a_message_is_withheld(message: str) -> None:
    """The backstop for a writer that bypasses exc_text: error keys keep a type name only."""
    for key in ("error", "install_error", "ledger_error", "rejected", "errors"):
        out = redact({key: message if key != "errors" else [message]}, _BOX)
        assert json.dumps(out).count(WITHHELD_OUTPUT) == 1, (key, out)


@pytest.mark.parametrize("message", _AUDIT_STRINGS)
def test_a_typed_message_in_free_text_loses_its_message(message: str) -> None:
    for exc_type in ("ValueError", "HTTPError", "ConnectTimeout", "JSONDecodeError"):
        out = public_string(f"adapter raised: {exc_type}: {message}", _BOX)
        assert message not in out and exc_type in out, out


def test_subprocess_output_is_withheld_whole() -> None:
    doc = {"stdout_tail": ["Looking in indexes: https://u:p@pypi.example/simple"],
           "tail": "token abc", "stderr": "x", "traceback": "Traceback ..."}
    assert set(redact(doc, _BOX).values()) == {WITHHELD_OUTPUT}


#: Every module whose text can reach a published sandbox or census report.
_CHAIN = sorted({
    *(p.relative_to(ROOT).as_posix() for p in (ROOT / "libs/research/adapters").glob("*.py")),
    *(p.relative_to(ROOT).as_posix()
      for p in (ROOT / "desks/mt5/research/sandboxes").glob("*.py")),
    "desks/mt5/research/sandbox_runner.py", "desks/mt5/research/sandbox_roster.py",
    "desks/mt5/research/sandbox_provision.py", "desks/mt5/research/productivity_census.py",
    "scripts/check_sandbox_liveness.py", "scripts/check_organ_census.py",
    "scripts/check_seat_health.py", "scripts/check_dead_architecture.py",
    "libs/research/sandbox.py", "libs/research/licence_reader.py", "libs/ops/producer_census.py",
    "libs/ops/organ_census.py",
})
_ALLOWED_CALLS = {"exc_text", "type", "isinstance", "print", "getattr", "hasattr"}
_LOG_METHODS = {"exception", "warning", "error", "info", "debug", "exc_text"}


def _formats_an_exception(src: str) -> list[int]:
    """Lines where an `except ... as NAME` body uses NAME other than through exc_text/type/print
    (or re-raising): each is a place an exception's MESSAGE could reach a report."""
    import ast

    tree = ast.parse(src)
    parent: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent[child] = node
    bad: list[int] = []
    for h in ast.walk(tree):
        if not isinstance(h, ast.ExceptHandler) or not h.name:
            continue
        for stmt in h.body:
            for n in ast.walk(stmt):
                if not (isinstance(n, ast.Name) and n.id == h.name
                        and isinstance(n.ctx, ast.Load)):
                    continue
                p: ast.AST | None = parent.get(n)
                ok = False
                while p is not None and not ok:
                    if isinstance(p, ast.Call):
                        f = p.func
                        ok = ((isinstance(f, ast.Name) and f.id in _ALLOWED_CALLS)
                              or (isinstance(f, ast.Attribute) and f.attr in _LOG_METHODS))
                    if isinstance(p, ast.Raise):
                        ok = True
                    if isinstance(p, ast.stmt):
                        break
                    p = parent.get(p)
                if not ok:
                    bad.append(n.lineno)
    return bad


def test_the_chain_is_found() -> None:
    assert len(_CHAIN) >= 100, f"only {len(_CHAIN)} modules found: the scan is blind"


@pytest.mark.parametrize("rel", _CHAIN)
def test_no_writer_in_the_chain_formats_an_exception_message(rel: str) -> None:
    lines = _formats_an_exception((ROOT / rel).read_text("utf-8"))
    assert not lines, (f"{rel} formats an exception outside exc_text() at line(s) {lines}: its "
                       "message could reach a public report")


def test_the_scan_catches_the_shape_it_fences() -> None:
    src = ("try:\n    pass\nexcept Exception as exc:\n    why = f'{type(exc).__name__}: {exc}'\n"
           "    other = str(exc)\n    ok = exc_text(exc)\n")
    assert _formats_an_exception(src) == [4, 5]
