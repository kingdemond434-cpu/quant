"""THE ROOT PATH (zuck 2026-11-10 23:18Z / 23:19Z: "everything literally everything autonomous",
"never ever need to manually comment paste anything fr merges any type"). SEALED CORE.

After the final sitting, a ROOT PR (one that changes the merge machinery itself: audit_gate.py,
the release authority, the publisher, trusted-eval) merges with no owner comment when ALL hold.
Both the release authority (policy.decide) and the box gate (audit_gate.py) import THIS module
from their own pinned checkout, so a PR is always judged by the base's rules, never its own:

  1. an AUDIT CLEAR comment for the exact head, and the Auditor's synced registry row agrees;
  2. every job in ROOT_JOBS green on the exact head, by GitHub Actions. A failed
     independent-review or replay-shadow is re-run automatically ONCE on the same head, and only
     when its failure cites no file:line and does not flag control machinery; a second failure,
     or any other failure, blocks. No adjudication, no empty commit;
  3. the BASE's trusted-eval passed on the exact head;
  4. up to date with LIVE, the merge pinned to the head sha;
  5. a release-authority Ed25519 attestation (class ROOT) for the exact head and patch;
  6. ROOT_VETO_H (72 h) since a veto notice for THIS head was DELIVERED (a recorded receipt:
     the alert command's exit 0 AND its "delivered N" with N > 0). The notice names the PR, the
     head and the ROOT files it changes. A new push is a new head: a new notice, a new window.
     An AUDIT HOLD, DEACTIVATE, a HOLD row or any red check in the window: no merge;
  7. one at a time: no ROOT merge while an earlier one is not yet re-pinned and adopted.

THE SEALED CORE never takes this path (the project's rule: a pin approved from a phone may never
re-pin its own door). A PR that changes a SEALED_CORE file, or any SEALED_VALUES constant, or
whose ROOT reasons are anything but "root file X" (a grow-only list shrinking, a sizing envelope
change), is refused here and waits for zuck's own CLEAR + APPROVE MERGES, as today. Lifting that
is zuck's call alone.

RESIDUAL RISK (stated for the sitting note, Auditor 2026-11-10): every session posts with one
GitHub identity, and the registry ref is landed by a session, so the comment and the row are two
records, not two independent keys. Against a deliberate forge the 72 h delivered window is
DETECTION, not prevention, until an authenticated Auditor channel exists.

Pure: no I/O here. The callers read GitHub, the box files and the clock, and pass facts in.
"""

from __future__ import annotations

import ast
import fnmatch
import re
from collections.abc import Callable, Iterable, Mapping
from datetime import datetime
from typing import Any

#: Condition 6: the ROOT veto window, three times the normal 24 h.
ROOT_VETO_H = 72.0
#: Condition 2: the jobs that must be green on the exact head. Kept HERE, not read from
#: audit_gate's GATING_JOBS / AUTO_JOBS, so a ROOT PR that shortens those lists does not shorten
#: what the next ROOT PR needs.
ROOT_JOBS = (
    "quality",
    "mt5-money-path",
    "coverage-floor",
    "risk-invariants",
    "replay-shadow",
    "independent-review",
)
#: Condition 2: the only jobs that get the one automatic re-run, and how many re-runs.
RERUNNABLE = ("independent-review", "replay-shadow")
RERUNS = 1
#: Condition 3.
TRUSTED_EVAL = "trusted-eval"
#: The box command that delivers the veto notice, and the Auditor's synced rows file (#818).
NOTIFY_ENV = "QUANT_REGISTRY_NOTIFY"
AUDITOR_ROWS_ENV = "QUANT_AUDITOR_ROWS"
#: The class an attestation carries for this path.
ROOT_CLASS = "ROOT"

#: Files no PR may change through this path. ROOT_POLICY.json holds the root_files list, the
#: grow-only lists and the sizing envelope (risk limits), so all of it is sealed.
SEALED_CORE = (
    "ops/release/authority/ROOT_POLICY.json",
    "ops/release/authority/root_path.py",
    "ops/release/authority/repin.py",
    "ops/release/authority/install_repin.ps1",
    "scripts/check_immutable_evaluator.py",
)
#: Constants in other files that steer where the path's records come from or go to. A PR that
#: changes, removes or re-assigns one is SEALED (an absent constant that a PR adds with exactly
#: this value is not a change of it).
SEALED_VALUES: dict[tuple[str, str], Any] = {
    (".github/scripts/audit_gate.py", "REGISTRY_NOTIFY_ENV"): "QUANT_REGISTRY_NOTIFY",
    (".github/scripts/audit_gate.py", "REGISTRY_HOLD_H"): 24.0,
    (".github/scripts/audit_gate.py", "AUTHORITY_PUBKEY_ENV"): "QUANT_AUTHORITY_PUBKEY",
    (".github/scripts/audit_gate.py", "AUTHORITY_DIR_ENV"): "QUANT_AUTHORITY_ATTESTATIONS",
    (".github/scripts/audit_gate.py", "AUTHORITY_PIN_ENV"): "QUANT_AUTHORITY_ROOT_PIN",
    (".github/scripts/audit_gate.py", "AUTHORITY_KILL"): "DEACTIVATE",
    (".github/scripts/audit_gate.py", "AUDITOR_ROWS_ENV"): "QUANT_AUDITOR_ROWS",
    ("ops/release/auditor_sync.py", "REF"): "refs/heads/audit-registry",
    ("ops/release/auditor_sync.py", "FILE"): "REGISTRY_ROWS.jsonl",
    ("ops/release/auditor_sync.py", "MEMECOIN_FILE"): "MEMECOIN_REGISTRY_ROWS.jsonl",
    (".github/scripts/memecoin_gate.py", "MEMECOIN_REGISTRY_ENV"): "MEMECOIN_AUDIT_REGISTRY",
}

_UNREADABLE = object()
_ROOT_REASON = "root file "
#: A failure that names a place: path/file.ext:123.
_CITES_LINE = re.compile(r"[\w./\\-]+\.[A-Za-z0-9]{1,8}:\d+")
_CONTROL = re.compile(r"touches_control|control machinery", re.IGNORECASE)
_RISK = re.compile(r"risk_increasing|risk increase", re.IGNORECASE)
#: A model's FAIL vote: its findings stay in the job log (never relayed), so whether they cite a
#: line cannot be read, and a failure that may cite a line is never re-run.
_VOTED = re.compile(r"voted FAIL|findings are in the job log", re.IGNORECASE)
_DELIVERED = re.compile(r"\bdelivered\s+(\d+)\b")


# ----------------------------------------------------------------------------- the sealed core


def _sealed_file(name: str) -> bool:
    low = name.replace("\\", "/").lower()
    return any(fnmatch.fnmatchcase(low, p.lower()) for p in SEALED_CORE)


def _binds(node: ast.AST, name: str) -> bool:
    """Does `node` (re)bind `name` in its own scope?"""
    targets: list[ast.AST] = []
    if isinstance(node, ast.Assign):
        targets = list(node.targets)
    elif isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr, ast.For, ast.AsyncFor)):
        targets = [node.target]
    elif isinstance(node, (ast.With, ast.AsyncWith)):
        targets = [i.optional_vars for i in node.items if i.optional_vars is not None]
    elif isinstance(node, ast.Delete):
        targets = list(node.targets)
    elif isinstance(node, (ast.Import, ast.ImportFrom)):
        return any((a.asname or a.name.split(".")[0]) == name or a.name == "*" for a in node.names)
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.ExceptHandler)):
        return node.name == name
    return any(isinstance(n, ast.Name) and n.id == name for t in targets for n in ast.walk(t))


def py_constant(src: str | None, name: str) -> Any:
    """The value of module constant `name` in Python source `src`: None when absent, _UNREADABLE
    when it cannot be pinned down (a parse error, a non-literal value, more than one binding of
    the name anywhere in the module, or a `global` re-binding)."""
    if src is None:
        return None
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError):
        return _UNREADABLE
    found: list[ast.AST] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Global, ast.Nonlocal)) and name in node.names:
            return _UNREADABLE
        if _binds(node, name):
            found.append(node)
    if not found:
        return None
    if len(found) > 1:
        return _UNREADABLE
    node = found[0]
    if node not in tree.body or isinstance(node, ast.AugAssign):
        return _UNREADABLE
    value = getattr(node, "value", None)
    if value is None:
        return _UNREADABLE
    try:
        return ast.literal_eval(value)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        return _UNREADABLE


def sealed_touch(
    files: Iterable[str],
    read_base: Callable[[str], str | None],
    read_head: Callable[[str], str | None],
) -> list[str]:
    """Why this change touches the SEALED CORE (empty: it does not). `files`: every changed path,
    both sides of a rename."""
    changed = {f.replace("\\", "/") for f in files}
    out = [f"sealed core file {f}" for f in sorted(changed) if _sealed_file(f)]
    for (path, name), pinned in SEALED_VALUES.items():
        if path not in changed:
            continue
        hv, bv = py_constant(read_head(path), name), py_constant(read_base(path), name)
        if hv is _UNREADABLE:
            out.append(f"sealed value {path}:{name} cannot be read on the head")
        elif hv != bv and not (bv is None and hv == pinned):
            out.append(f"sealed value {path}:{name} changes ({bv!r} -> {hv!r})")
    return out


def eligible(cls_reasons: Iterable[str]) -> tuple[bool, str]:
    """May a ROOT PR with these classify() reasons take the ROOT path? Only when it is ROOT
    purely because it changes root files: a shrinking grow-only list, a sizing-envelope change or
    a sealed-core change stays zuck's."""
    reasons = list(cls_reasons)
    if not reasons:
        return False, "no ROOT reason given: fail closed"
    other = [r for r in reasons if not r.startswith(_ROOT_REASON)]
    if other:
        return False, "not a root-file-only change, so zuck's path: " + "; ".join(other)
    sealed = [r for r in reasons if _sealed_file(r[len(_ROOT_REASON) :])]
    if sealed:
        return False, "the sealed core never takes the ROOT path: " + "; ".join(sealed)
    return True, "root files only: " + ", ".join(r[len(_ROOT_REASON) :] for r in reasons)


# ----------------------------------------------------------------------------- the checks


def failure_flags(texts: Iterable[str]) -> list[str]:
    """Why a failed job's own annotations rule out the automatic re-run (empty: they do not)."""
    out: list[str] = []
    for t in texts:
        if _CITES_LINE.search(t):
            out.append("its failure cites a line")
        if _CONTROL.search(t):
            out.append("its failure flags control machinery")
        if _RISK.search(t):
            out.append("its failure flags a risk increase")
        if _VOTED.search(t):
            out.append("a reviewer voted FAIL and its findings may cite a line")
    return sorted(set(out))


def jobs(attempts: Mapping[str, list[Mapping[str, Any]]]) -> tuple[str, str, str | None]:
    """("pass" | "pending" | "rerun" | "fail", why, the job to re-run). `attempts[name]`: every
    GENUINE run of that ROOT job on the exact head, oldest first, each {"status",
    "conclusion", "unavailable": the reviewer's UNAVAILABLE mark, "flags": failure_flags(...) or
    None when the annotations were unreadable}."""
    pending: list[str] = []
    rerun: str | None = None
    for name in ROOT_JOBS:
        runs = list(attempts.get(name) or [])
        if not runs:
            pending.append(f"{name} (not started)")
            continue
        last = runs[-1]
        if last.get("status") != "completed":
            pending.append(name)
            continue
        if last.get("conclusion") == "success":
            continue
        if last.get("unavailable"):  # no free reviewer answered: queued, never a pass or a fail
            pending.append(f"{name} (queued: no free reviewer answered)")
            continue
        concl = last.get("conclusion")
        flags = last.get("flags")
        failed = [r for r in runs if r.get("status") == "completed"
                  and r.get("conclusion") != "success" and not r.get("unavailable")]  # fmt: skip
        if name not in RERUNNABLE:
            return "fail", f"{name} {concl}: no re-run on the ROOT path", None
        if len(failed) > RERUNS:
            return "fail", f"{name} {concl} again after {RERUNS} re-run", None
        if flags is None:
            return "fail", f"{name} {concl}: its annotations cannot be read, so no re-run", None
        if flags:
            return "fail", f"{name} {concl}: " + ", ".join(flags), None
        rerun = rerun or name
    if pending:
        return "pending", "waiting on: " + ", ".join(pending), None
    if rerun:
        return "rerun", f"{rerun} failed once and names nothing: one automatic re-run", rerun
    return "pass", f"all {len(ROOT_JOBS)} ROOT jobs green on the exact head", None


def registry_agrees(rows: Iterable[Mapping[str, Any]], pr: int, head: str) -> tuple[bool, str]:
    """Condition 1, second record: the Auditor's newest row for `pr` is CLEAR for `head`."""
    mine = [r for r in rows if r.get("pr") == pr]
    if not mine:
        return False, "no Auditor registry row"
    last = mine[-1]
    if last.get("verdict") != "CLEAR" or last.get("sha") != head:
        return (
            False,
            f"the Auditor's newest row is {last.get('verdict')} {str(last.get('sha'))[:9]}",
        )
    return True, f"Auditor registry CLEAR {head[:9]}"


def comment_clear(found: list[Mapping[str, Any]], head: str) -> tuple[bool, str]:
    """Condition 1, first record: the newest AUDIT verdict comment is CLEAR for `head`."""
    if not found:
        return False, "no AUDIT verdict comment"
    last = found[-1]
    if last.get("verdict") != "CLEAR" or last.get("sha") != head:
        return (
            False,
            f"the newest AUDIT comment is {last.get('verdict')} {str(last.get('sha'))[:9]}",
        )
    return True, f"AUDIT CLEAR {head[:9]}"


# ----------------------------------------------------------------------------- the veto window


def notice(pr: int, head: str, root_files: Iterable[str]) -> tuple[str, str]:
    """(title, body) of the ROOT veto notice, in plain words."""
    files = ", ".join(sorted(root_files)) or "(none listed)"
    title = (
        f"PR #{pr} {head[:9]} CHANGES HOW MERGES ARE APPROVED: auto-merges in "
        f"{ROOT_VETO_H:.0f} h unless vetoed"
    )
    body = (
        f"PR #{pr} at {head} changes the merge machinery itself: {files}. The Auditor CLEARed it "
        f"and every check passed. The box merges it after {ROOT_VETO_H:.0f} h. To stop it: an "
        "AUDIT HOLD on the PR, a HOLD row, DEACTIVATE merges, or a new push."
    )
    return title, body


def receipt(returncode: int, stdout: str) -> str | None:
    """The delivery receipt of one notice send, or None when it was not delivered."""
    if returncode != 0:
        return None
    got = [int(n) for n in _DELIVERED.findall(stdout or "")]
    if not got or max(got) <= 0:
        return None
    return " ".join((stdout or "").split())[:200]


def window(rec: Mapping[str, Any] | None, head: str, now: datetime) -> tuple[str, str]:
    """("open" | "elapsed" | "none", why) for the ROOT window of `head`. `rec`: the gate's own
    record {"head", "at", "receipt"} of the last DELIVERED ROOT notice for this PR."""
    if not rec or rec.get("head") != head or not rec.get("receipt"):
        return "none", f"no delivered ROOT notice for {head[:9]}"
    try:
        at = datetime.fromisoformat(str(rec.get("at")))
    except ValueError:
        return "none", "the ROOT notice record has an unreadable time"
    if at.tzinfo is None or at > now:
        return "none", "the ROOT notice record has a bad time"
    age_h = (now - at).total_seconds() / 3600.0
    if age_h < ROOT_VETO_H:
        return "open", f"ROOT veto window {age_h:.1f} of {ROOT_VETO_H:.0f} h"
    return "elapsed", f"ROOT veto window passed ({age_h:.0f} h, no veto)"


# ----------------------------------------------------------------------------- the verdicts


def authority_verdict(f: Mapping[str, Any]) -> tuple[str, list[str]]:
    """The release authority's verdict on a ROOT PR (policy.decide calls this for class ROOT).
    Facts beyond policy.decide's: sealed (sealed_touch()), root_jobs (jobs()), trusted_eval
    ("pass" | "pending" | "fail", why). CLEAR here signs a class-ROOT attestation; the gate still
    needs the comment, the registry row, the window and one-at-a-time before anything merges."""
    if f.get("sealed"):
        return "HOLD", ["SEALED CORE, zuck's path only: " + "; ".join(f["sealed"])]
    ok, why = eligible(f.get("cls_reasons") or [])
    if not ok:
        return "HOLD", [f"ROOT: {why}"]
    if f.get("hold"):
        return "HOLD", [f"an AUDIT HOLD stands: {f['hold']}"]
    if f.get("deactivated"):
        return "WAIT", ["merges are DEACTIVATED"]
    if not f.get("patch_id"):
        return "WAIT", ["the change's patch-id could not be computed"]
    state, jwhy, _ = f.get("root_jobs") or ("pending", "no checks read", None)
    if state == "fail":
        return "FAIL", [f"ROOT path: {jwhy}"]
    if state != "pass":
        return "WAIT", [f"ROOT path: {jwhy}"]
    te, twhy = f.get("trusted_eval") or ("pending", "trusted-eval not read")
    if te == "fail":
        return "FAIL", [f"ROOT path: {twhy}"]
    if te != "pass":
        return "WAIT", [f"ROOT path: {twhy}"]
    if not f.get("fresh"):
        return "WAIT", [f"not up to date: {f.get('fresh_why')}"]
    return "CLEAR", [f"ROOT path ({why}): {jwhy}; {twhy}"]


def gate_verdict(g: Mapping[str, Any]) -> tuple[str, str]:
    """The box gate's action on a ROOT-attested PR: "MERGE" | "NOTIFY" (send the notice now) |
    "RERUN" | "WAIT" | "HOLD", and why. Facts: sealed, cls_reasons, hold, deactivated,
    in_flight (why an earlier ROOT merge is not yet re-pinned and adopted, or ""), comment,
    registry (each (bool, why)), attested (bool, why), root_jobs (jobs()), trusted_eval,
    fresh/fresh_why, window (window())."""
    if g.get("sealed"):
        return "HOLD", "SEALED CORE, zuck's path only: " + "; ".join(g["sealed"])
    ok, why = eligible(g.get("cls_reasons") or [])
    if not ok:
        return "HOLD", f"ROOT: {why}"
    if g.get("hold"):
        return "HOLD", f"an AUDIT HOLD stands: {g['hold']}"
    if g.get("deactivated"):
        return "WAIT", "merges are DEACTIVATED"
    if g.get("in_flight"):
        return "WAIT", f"one ROOT merge at a time: {g['in_flight']}"
    for key in ("comment", "registry", "attested"):
        good, kwhy = g.get(key) or (False, f"{key} not read")
        if not good:
            return "WAIT", kwhy
    state, jwhy, _ = g.get("root_jobs") or ("pending", "no checks read", None)
    if state == "rerun":
        return "RERUN", jwhy
    if state == "fail":
        return "HOLD", f"ROOT path: {jwhy}"
    if state != "pass":
        return "WAIT", jwhy
    te, twhy = g.get("trusted_eval") or ("pending", "trusted-eval not read")
    if te != "pass":
        return ("HOLD" if te == "fail" else "WAIT"), twhy
    if not g.get("fresh"):
        return "WAIT", f"not up to date: {g.get('fresh_why')}"
    w, wwhy = g.get("window") or ("none", "no ROOT notice")
    if w == "none":
        return "NOTIFY", wwhy
    if w == "open":
        return "WAIT", wwhy
    return "MERGE", f"ROOT path: {jwhy}; {twhy}; {wwhy}"
