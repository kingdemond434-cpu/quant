"""THE RELEASE AUTHORITY'S POLICY -- a pure, deterministic decision over facts the authority
gathered itself. No model, no session, no comment text decides here; the same facts always give
the same verdict, so the decision can be re-derived by anyone from the evidence it names.

CLASSES (strictest file wins):
  ROOT        -- a file in ROOT_POLICY.json root_files, ROOT_POLICY.json itself, a shrunk
                 grow_only list, or a ceiling change the envelope does not allow. The authority
                 never CLEARs ROOT; it signs a HOLD saying so, and zuck's own path decides.
  CONTROLLER  -- the gate's PROTECTED tier (a check that judges PRs: .github/, ops/release/, test
                 configuration). Needs the base-run `trusted-eval` job on top of every gating and
                 AUTO job: the PR's own `pull_request` runs are self-attested for these files.
  AUTO / LOW  -- the gate's own tiers; every gating and AUTO job.

VERDICTS: "CLEAR" (sign it), "HOLD" (sign it: a no that no later evidence on this head can
change -- ROOT, REFUSED, a standing AUDIT HOLD), "FAIL" (a required check failed; signed as
nothing, the gate refuses it by itself, and a passing re-run may still CLEAR the head), "WAIT"
(sign nothing: checks still running, behind the base, review queued). Unavailable evidence is
WAIT or HOLD, never CLEAR.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
POLICY_FILE = HERE / "ROOT_POLICY.json"
CEILINGS = "ops/release/ceilings.json"


def load_policy(path: Path = POLICY_FILE) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _match(name: str, pats: Iterable[str]) -> bool:
    low = name.lower()
    return any(fnmatch.fnmatchcase(low, p.lower()) for p in pats)


def root_digest(read: Callable[[str], bytes | None], names: Iterable[str], policy: Mapping) -> str:
    """sha256 over (path, sha256(bytes)) of every root file present in the tree `read` serves.
    `names`: every path in that tree (git ls-files). A missing root file hashes as absent, so
    deleting one changes the digest too."""
    pats = list(policy["root_files"])
    rows = {}
    for n in sorted(set(names)):
        if _match(n, pats) and "__pycache__" not in n:
            data = read(n)
            rows[n] = hashlib.sha256(data).hexdigest() if data is not None else "absent"
    blob = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


def _lines(text: str | None) -> set[str]:
    if text is None:
        return set()
    return {
        ln.strip() for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")
    }


def envelope_check(base: Mapping | None, head: Mapping | None, env: Mapping) -> list[str]:
    """Every way the head's ceilings.json leaves the pre-delegated envelope (empty: inside it).
    A ceilings file that cannot be read on either side is a violation."""
    if not isinstance(base, Mapping) or not isinstance(head, Mapping):
        return ["ops/release/ceilings.json cannot be read on the base or the head"]
    out: list[str] = []
    fixed = env.get("fixed") or {}
    raisable = env.get("raisable") or {}
    bmax, hmax = base.get("max") or {}, head.get("max") or {}
    for path in sorted(set(bmax) | set(hmax)):
        b, h = bmax.get(path) or {}, hmax.get(path) or {}
        for knob in sorted(set(b) | set(h)):
            if knob not in h:
                out.append(f"{path}:{knob} ceiling removed")
                continue
            new = h[knob]
            if knob not in b:
                continue  # a new ceiling only tightens what was unbounded
            old = b[knob]
            if not isinstance(new, int | float) or not isinstance(old, int | float):
                if new != old:
                    out.append(f"{path}:{knob} ceiling is not a number")
                continue
            if new <= old:
                continue  # tighter or equal: always allowed
            if knob in (fixed.get(path) or ()):
                out.append(f"{path}:{knob} is a firm rule ({old} -> {new}): never raised")
                continue
            spec = (raisable.get(path) or {}).get(knob)
            if not spec:
                out.append(f"{path}:{knob} raised {old} -> {new}: not in the delegated envelope")
                continue
            if new > float(spec["hard_max"]):
                out.append(f"{path}:{knob} raised to {new}, above its hard max {spec['hard_max']}")
            if old > 0 and (new - old) / old > float(spec["max_step_frac"]) + 1e-12:
                out.append(
                    f"{path}:{knob} raised {old} -> {new}, more than one step "
                    f"({spec['max_step_frac']:.0%}) in one PR"
                )
    for sect in ("equal", "source"):
        if (base.get(sect) or {}) != (head.get(sect) or {}):
            # only additions of new pinned rows are allowed
            bs, hs = base.get(sect) or {}, head.get(sect) or {}
            for path, rows in bs.items():
                for k, v in (rows or {}).items():
                    if (hs.get(path) or {}).get(k, object()) != v:
                        out.append(f"{sect} pin {path}:{k} changed or removed")
    bsup, hsup = base.get("superset") or {}, head.get("superset") or {}
    for path, name in bsup.items():
        if hsup.get(path) != name:
            out.append(f"superset rail {path}:{name} changed or removed")
    return out


def classify(
    files: list[str],
    gate_tier: str,
    policy: Mapping,
    read_base: Callable[[str], str | None],
    read_head: Callable[[str], str | None],
) -> tuple[str, list[str]]:
    """(class, reasons). `files`: every changed path (both sides of a rename)."""
    if gate_tier == "REFUSED":
        return "REFUSED", ["a secrets path: never merged"]
    root = [f for f in files if _match(f, policy["root_files"])]
    reasons = [f"root file {f}" for f in root]
    for f in files:
        if _match(f, policy.get("grow_only") or ()):
            lost = _lines(read_base(f)) - _lines(read_head(f))
            if lost:
                reasons.append(f"{f} lost {len(lost)} entr(y/ies): grow-only lists never shrink")
    if CEILINGS in files:

        def js(t: str | None) -> Any:
            try:
                return json.loads(t) if t is not None else None
            except ValueError:
                return None

        reasons += [
            f"envelope: {v}"
            for v in envelope_check(
                js(read_base(CEILINGS)), js(read_head(CEILINGS)), policy.get("envelope") or {}
            )
        ]
    if reasons:
        return "ROOT", reasons
    if gate_tier == "PROTECTED":
        return "CONTROLLER", ["changes a check that judges PRs: base-run trusted-eval required"]
    return gate_tier, []


def decide(f: Mapping[str, Any]) -> tuple[str, list[str]]:
    """The verdict over the authority's facts:
    open/same_repo/base_ok: the PR itself; cls/cls_reasons: classify(); checks: ("pass" |
    "pending" | "fail", why) over every job the class requires, provenance-checked; review_queued:
    the reviewer ended UNAVAILABLE; hold: a trusted AUDIT HOLD stands on the PR (why);
    deactivated: merges are switched off; fresh/fresh_why: up_to_date(); patch_id: the change's
    byte identity (None: unreadable)."""
    if not (f.get("open") and f.get("same_repo") and f.get("base_ok")):
        return "WAIT", ["not an open same-repo PR into LIVE"]
    cls = f.get("cls")
    if cls in ("REFUSED", "ROOT"):
        return "HOLD", [f"{cls}: " + "; ".join(f.get("cls_reasons") or [])]
    if cls not in ("CONTROLLER", "AUTO", "LOW"):
        return "HOLD", [f"unknown class {cls!r}: fail closed"]
    if f.get("hold"):
        return "HOLD", [f"an AUDIT HOLD stands: {f['hold']}"]
    if f.get("deactivated"):
        return "WAIT", ["merges are DEACTIVATED"]
    if not f.get("patch_id"):
        return "WAIT", ["the change's patch-id could not be computed"]
    state, why = f.get("checks") or ("pending", "no checks read")
    if state == "fail" and f.get("review_queued"):
        return "WAIT", ["independent-review queued: no free reviewer answered (never a pass)"]
    if state == "fail":
        # not signed: a re-run may pass on the same head, and the gate refuses a failed check
        # by itself. Only a verdict that no later evidence can change is signed as HOLD.
        return "FAIL", [f"a required check failed: {why}"]
    if state != "pass":
        return "WAIT", [f"checks not finished: {why}"]
    if not f.get("fresh"):
        return "WAIT", [f"not up to date: {f.get('fresh_why')}"]
    return "CLEAR", [f"{cls}: every required check passed on the exact head ({why})"]


def required_jobs(cls: str, gating: tuple[str, ...], auto: tuple[str, ...], policy: Mapping):
    """The head's own check runs every class needs. A CONTROLLER PR's base-run trusted-eval is
    not a check run on the head (pull_request_target runs on the base), so it is read apart."""
    return gating + auto
