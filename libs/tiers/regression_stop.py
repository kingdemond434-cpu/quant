"""THE AUTOMATIC REGRESSION STOP AND ROLLBACK (Tier S layer 28, verifier gap B, 2026-09-30).

Until this module the rollback was a plan the twin published and a human ran
(`tier_s.py --rollback-to <sha> --apply-rollback`): a release that made the live book worse kept
trading, and kept PROMOTING, until someone read TWIN.json. The `twin` organ now calls `run()`
every hour.

FORWARD REGRESSION, DEFINED FROM WHAT THE DESK ALREADY MEASURES. Each closed live trade carries its
realised `r_multiple` (the live ledger) and its sleeve's FORWARD expectancy `exp_r` (the shadow
forward clock of the same group, `tier_s.shadow_rows`). The trade's RESIDUAL is

    d = r_multiple - exp_r[group]

-- what the live release banked beyond (or short of) what the sleeve's own forward clock expects,
so the comparison is not moved by WHICH sleeves happened to trade. Trades are assigned to the
sealed release that was running when they closed (LIVE_MANIFEST / RELEASE.json `at`). The current
release REGRESSED when, over residuals of the current release versus the previous one,

    n_cur >= MIN_N  and  n_prev >= MIN_N  and  mean_cur < mean_prev  and  Welch t < -T_CRIT

-- the same thresholds (30 pairs, |t| > 2) the twin's `evaluate` uses for a REJECT. Anything short
of that is HOLDING or UNMEASURED, never a clean pass and never a stop.

ON A REGRESSION, THREE THINGS, ALL WRITTEN TO `data/tier_s/RELEASE_STOP.json`:

  1. THE STOP. The regressed release's code SHA is recorded; `promotion_authority.block` withholds
     every NEW live row while the running release (RELEASE.json `code_sha`) is the stopped one
     (`RELEASE_REGRESSION_STOP`), billed by the `tier_s_evidence_block` rail like every door
     verdict. It sizes nothing and touches no open position.
  2. THE ROLLBACK, APPLIED. `libs.tiers.rollback.plan` names the previous sealed release; the
     UNSEALED code paths between them are restored in ONE commit (`rollback.apply`, never pushes,
     never rewrites history), only when those paths are clean in the working tree (an uncommitted
     edit is never clobbered: APPLY_DEFERRED, said with the paths).
  3. THE SEALED REMAINDER, AS A PATCH. Paths under seal -- the immutable evaluator's list and the
     release's signed `money_path` (gateway.py and its siblings) -- are NOT rewritten by an organ:
     the diff that would return them is written as `data/tier_s/rollback_sealed.patch` for
     Adopt-And-Seal / the principal, and the stop holds until the running release changes.

The stop CLEARS by itself when the running release is no longer the stopped one (the rollback or
a newer release was adopted); it is never cleared by the clock alone.

Nothing here kills a process, restarts a gateway or reaches the terminal.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.tiers import rollback
from libs.tiers.replay import parse_t

ROOT = Path(__file__).resolve().parents[2]
STOP_REL = Path("desks") / "mt5" / "data" / "tier_s" / "RELEASE_STOP.json"
PATCH_REL = Path("desks") / "mt5" / "data" / "tier_s" / "rollback_sealed.patch"
RELEASE_REL = Path("desks") / "mt5" / "data" / "RELEASE.json"
MIN_N = 30
T_CRIT = 2.0
#: the kill switch for the APPLY step only (detection, the stop and the artifact always run)
ENV_NO_APPLY = "TIER_S_AUTO_ROLLBACK_OFF"


def _root(root: Path | None) -> Path:
    return Path(root) if root is not None else ROOT


def _mean_sd(xs: Sequence[float]) -> tuple[float, float]:
    m = sum(xs) / len(xs)
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) if len(xs) > 1 else 0.0
    return m, sd


def forward_regression(trades: Iterable[Mapping[str, Any]], releases: Sequence[Mapping[str, Any]],
                       exp_by_group: Mapping[str, Any], *, min_n: int = MIN_N,
                       t_crit: float = T_CRIT) -> dict[str, Any]:
    """The verdict on the CURRENT sealed release: REGRESSED / HOLDING / UNMEASURED (module doc)."""
    sealed = [r for r in releases if r.get("sha") and r.get("sealed", True)]
    if len(sealed) < 2:
        return {"verdict": "UNMEASURED", "why": f"{len(sealed)} sealed release(s) known"}
    cur, prev = sealed[-1], sealed[-2]
    t_cur, t_prev = parse_t(cur.get("at")), parse_t(prev.get("at"))
    if t_cur is None or t_prev is None:
        return {"verdict": "UNMEASURED", "why": "a sealed release carries no seal time",
                "current": cur.get("sha"), "previous": prev.get("sha")}
    a: list[float] = []
    b: list[float] = []
    unpriced = 0
    for tr in trades:
        when = parse_t(tr.get("time"))
        try:
            r = float(tr["r_multiple"])
            e = float((exp_by_group.get(str(tr.get("_group"))) or {})["exp_r"])
        except (KeyError, TypeError, ValueError):
            unpriced += 1
            continue
        if when is None or not (math.isfinite(r) and math.isfinite(e)):
            unpriced += 1
            continue
        if when >= t_cur:
            a.append(r - e)
        elif when >= t_prev:
            b.append(r - e)
    base = {"current": cur.get("sha"), "previous": prev.get("sha"), "n_current": len(a),
            "n_previous": len(b), "unpriced_trades": unpriced, "min_n": min_n, "t_crit": t_crit,
            "metric": "residual R = live r_multiple - forward exp_r of the sleeve's group"}
    if len(a) < min_n or len(b) < min_n:
        return {**base, "verdict": "UNMEASURED",
                "why": f"{len(a)} / {len(b)} priced trades under the current / previous release; "
                       f"{min_n} each are needed"}
    ma, sa = _mean_sd(a)
    mb, sb = _mean_sd(b)
    se = math.sqrt(sa * sa / len(a) + sb * sb / len(b))
    diff = ma - mb
    t = diff / se if se > 0 else (-math.inf if diff < 0 else math.inf if diff > 0 else 0.0)
    verdict = "REGRESSED" if diff < 0 and t < -t_crit else "HOLDING"
    return {**base, "verdict": verdict, "mean_current": round(ma, 6),
            "mean_previous": round(mb, 6), "difference": round(diff, 6),
            "t": round(t, 3) if math.isfinite(t) else None}


def sealed_paths(root: Path | None = None) -> set[str]:
    """The immutable evaluator's list plus the running release's signed money path."""
    from libs.research.immutable_rails import evaluator_immutable
    r = _root(root)
    out = set(evaluator_immutable(r / "scripts" / "check_immutable_evaluator.py")
              or evaluator_immutable())
    rel = _read(r / RELEASE_REL) or {}
    out.update(str(p) for p in rel.get("money_path") or [] if isinstance(p, str))
    out.add("desks/mt5/mt5desk/gateway.py")
    return {p.replace("\\", "/") for p in out}


def _read(p: Path) -> Any:
    try:
        return json.loads(p.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def _write(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    os.replace(tmp, p)


def running_release(root: Path | None = None) -> str | None:
    rel = _read(_root(root) / RELEASE_REL) or {}
    sha = rel.get("code_sha") or rel.get("live_sha")
    return str(sha) if sha else None


def _dirty(paths: Sequence[str], root: Path | None) -> list[str]:
    if not paths:
        return []
    out = subprocess.run(["git", "status", "--porcelain", "--", *paths], cwd=_root(root),
                         capture_output=True, text=True, check=True).stdout
    return [ln[3:] for ln in out.splitlines() if ln.strip()]


def _sealed_patch(target: str, paths: Sequence[str], root: Path | None) -> str:
    """A git diff (HEAD -> target) over the sealed paths only: `git apply` returns them."""
    if not paths:
        return ""
    return subprocess.run(["git", "diff", "--binary", "HEAD", target, "--", *paths],
                          cwd=_root(root), capture_output=True, text=True, check=True).stdout


def _same(a: str | None, b: str | None) -> bool:
    return bool(a) and bool(b) and (str(a).startswith(str(b)) or str(b).startswith(str(a)))


def run(trades: Iterable[Mapping[str, Any]], releases: Sequence[Mapping[str, Any]],
        exp_by_group: Mapping[str, Any], *, root: Path | None = None,
        now: datetime | None = None, apply: bool | None = None) -> dict[str, Any]:
    """Detect, stop, roll back (unsealed), patch (sealed); write RELEASE_STOP.json. Returns it."""
    r = _root(root)
    now = now or datetime.now(UTC)
    stop_path = r / STOP_REL
    prior = _read(stop_path) if stop_path.exists() else None
    reg = forward_regression(trades, releases, exp_by_group)
    running = running_release(r)
    if apply is None:
        # a test suite that happens to drive the twin over a real checkout never commits in it;
        # a test that means to apply passes apply=True over its own scratch repository
        apply = (os.environ.get(ENV_NO_APPLY, "") not in ("1", "true", "yes")
                 and "PYTEST_CURRENT_TEST" not in os.environ)
    doc: dict[str, Any] = {"generated_utc": now.isoformat(), "regression": reg,
                           "running_release": running,
                           "rule": ("REGRESSED = residual R (live r - forward exp_r) under the "
                                    "current sealed release below the previous one with Welch "
                                    f"t < -{T_CRIT:g} over >= {MIN_N} trades each; a stop "
                                    "withholds new LIVE rows while that release runs, the "
                                    "unsealed code is rolled back in one commit, the sealed "
                                    "remainder is a patch; the stop clears only when the "
                                    "running release changes")}
    stopped = (prior or {}).get("release") if isinstance(prior, dict) else None
    if (isinstance(prior, dict) and prior.get("state") == "STOPPED" and stopped
            and running and not _same(stopped, running)):
        # the running release moved off the stopped one: the stop has done its work
        doc.update(state="CLEARED", release=stopped, cleared_at=now.isoformat(),
                   why=f"running release {running[:12]} is no longer the stopped {stopped[:12]}")
        _write(stop_path, doc)
        return doc
    if isinstance(prior, dict) and prior.get("state") == "STOPPED" and reg["verdict"] != \
            "REGRESSED":
        # a stop is never cleared by the clock or by a later quiet window: only by a new release
        doc.update({k: prior.get(k) for k in ("release", "stopped_at", "rollback", "sealed_patch",
                                              "why")}, state="STOPPED")
        _write(stop_path, doc)
        return doc
    if reg["verdict"] != "REGRESSED":
        doc.update(state="CLEAR", release=None,
                   why=f"forward regression {reg['verdict']}: no stop")
        _write(stop_path, doc)
        return doc
    release = str(reg["current"])
    doc.update(state="STOPPED", release=release,
               stopped_at=(prior or {}).get("stopped_at") if _same(stopped, release)
               else now.isoformat(),
               why=(f"forward regression: residual R {reg['mean_current']:+.4f} under "
                    f"{release[:12]} vs {reg['mean_previous']:+.4f} under "
                    f"{str(reg['previous'])[:12]} (t={reg['t']}, n={reg['n_current']}/"
                    f"{reg['n_previous']}); no new LIVE row is promoted under this release"))
    rb: dict[str, Any] = {"state": "UNAVAILABLE"}
    try:
        p = rollback.plan(str(reg["previous"]), root=r)
    except (subprocess.CalledProcessError, OSError) as exc:
        p = {"available": False, "why": f"{type(exc).__name__}: {exc}"}
    if isinstance(prior, dict) and _same(stopped, release) and \
            (prior.get("rollback") or {}).get("state") == "APPLIED":
        rb = dict(prior["rollback"])                    # applied once; never twice
    elif not p.get("available"):
        rb = {"state": "UNAVAILABLE", "why": p.get("why")}
    elif not p.get("sealed"):
        rb = {"state": "REFUSED", "why": f"{p.get('target')} is not a sealed release"}
    else:
        code = [str(x) for x in p.get("code_paths") or []]  # type: ignore[attr-defined]
        seal = sealed_paths(r)
        free = [c for c in code if c not in seal]
        held = [c for c in code if c in seal]
        rb = {"target": p["target"], "unsealed_paths": free, "sealed_paths": held}
        if held:
            patch = _sealed_patch(str(p["target"]), held, r)
            (r / PATCH_REL).parent.mkdir(parents=True, exist_ok=True)
            (r / PATCH_REL).write_text(patch, "utf-8")
            doc["sealed_patch"] = {"path": str(PATCH_REL).replace("\\", "/"), "paths": held,
                                   "why": "sealed/signed paths are never rewritten by an organ; "
                                          "`git apply` this patch through Adopt-And-Seal"}
        dirty = _dirty(free, r)
        if not free:
            rb["state"] = "NOTHING_UNSEALED"
        elif not apply:
            rb["state"] = "APPLY_OFF"
            rb["why"] = f"{ENV_NO_APPLY} is set: detection and the stop ran, the apply did not"
        elif dirty:
            rb["state"] = "APPLY_DEFERRED"
            rb["why"] = f"uncommitted edits on {dirty[:5]}: never clobbered"
        else:
            try:
                commit = rollback.apply({**p, "code_paths": free}, root=r)
                rb.update(state="APPLIED", commit=commit, applied_at=now.isoformat())
            except (rollback.RollbackRefused, subprocess.CalledProcessError, OSError) as exc:
                rb.update(state="APPLY_FAILED", why=f"{type(exc).__name__}: {exc}")
    doc["rollback"] = rb
    _write(stop_path, doc)
    return doc


def stop_reason(root: Path | None = None) -> str | None:
    """The door's reading: a STOPPED release that is still the running one withholds.

    Absent is no stop. A stop file that exists but cannot be read raises (the door fails closed).
    An unknown running release with a standing stop withholds too: silence is not the all-clear."""
    r = _root(root)
    p = r / STOP_REL
    if not p.exists():
        return None
    doc = json.loads(p.read_text("utf-8-sig"))
    if not isinstance(doc, dict):
        raise ValueError(f"{p.name} is not a JSON object")
    if doc.get("state") != "STOPPED" or not doc.get("release"):
        return None
    running = running_release(r)
    if running and not _same(str(doc["release"]), running):
        return None
    return (f"RELEASE_REGRESSION_STOP: release {str(doc['release'])[:12]} regressed forward "
            f"({doc.get('why')}); rollback {((doc.get('rollback') or {}).get('state'))}")
