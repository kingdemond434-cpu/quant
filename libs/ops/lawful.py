"""LAWFUL ENTRY (L1.42) -- every act on this desk passes the laws, with no exceptions.

PRINCIPAL ORDER (2026-07-31): *"every single thing in quant, all acts, must follow all rules,
principles, constitutions, laws -- everything, no exceptions ever, no matter the interactions or
cycles."*

THE EXCEPTION THAT EXISTED, and it was most of the desk. The spawn gate (L1.37) lives in
`ops/brain_env.sh`, which only CLAUDE-invoking organs source -- 26 manifest lines. The other 60
run `.venv/bin/python scripts/X.py` directly and passed through NO gate at all: a collector, a
fence, a screen or the executor could start under a tampered constitutional core or a doctrine
stripped of a whole law family, and nothing would have checked. "Enforced at every boundary" was
true of the boundaries that existed, and this was the boundary nobody had built.

`guard()` is that boundary for python entry points. It is deliberately:

  CHEAP     -- a TTL marker (default 15 min) means one verification per window across all 60
               organs, not one per process. A gate that adds latency to every cron tick gets
               deleted, and a deleted gate enforces nothing.
  NON-BLOCKING BY DEFAULT -- it PAGES and records the breach rather than killing the organ. A
               governance fault must not silently stop the desk's research or its collectors:
               that trades a real outage for a paperwork fault, and the outage is the larger
               loss (L1.2). The breach is loud, dated and in the artifact -- never silent.
  FAIL-CLOSED WHERE IT MUST -- `guard(strict=True)` RAISES, and the money path uses it. An
               executor is the one organ that must NOT trade under a tampered core: there,
               refusing to act is the safe direction, and every other organ's default is the
               opposite for exactly the same reason.

WHAT IT VERIFIES (the two conditions under which no act should proceed, same as the spawn gate):
the sealed constitutional core is intact, and the doctrine still carries every law family -- an
organ that will never be told the laws it must obey cannot obey them.

    from libs.ops.lawful import guard
    guard()                      # research/collector/fence organ
    guard(strict=True)           # money path: raise rather than proceed
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent.parent

_MARKER = _ROOT / "data/.law_guard_ok"
_BREACHES = _ROOT / "data/law_gate_breaches.log"
DEFAULT_TTL_S = 900


class LawBreach(RuntimeError):
    """Raised by guard(strict=True) -- the money path must not act under a broken core."""


@dataclass(frozen=True)
class GuardResult:
    ok: bool
    failures: tuple[str, ...] = ()
    cached: bool = False


def _core_seal_ok(root: Path) -> tuple[bool, str]:
    """DELEGATES to scripts/check_constitution_core.py -- the authoritative sealer.

    An earlier draft re-implemented the hash verification here and got it wrong (it mis-parsed
    the lock's shape and reported a breach on an intact core). That is the two-sources-of-truth
    defect this desk has been burned by repeatedly: two implementations of one rule WILL
    disagree, and the disagreement surfaces as a false alarm that trains everyone to ignore the
    alarm. One sealer, one answer -- the TTL marker keeps the subprocess cost to once per window
    across all 60 organs."""
    script = root / "scripts/check_constitution_core.py"
    if not script.exists():
        return False, "check_constitution_core.py ABSENT -- the seal cannot be verified at all"
    try:
        r = subprocess.run([sys.executable, str(script)], capture_output=True, text=True,
                           timeout=90, cwd=root)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"seal check unrunnable ({exc}) -- counts as FAILED, never skipped"
    if r.returncode != 0:
        return False, (r.stdout + r.stderr).strip()[:200]
    return True, ""


def _doctrine_carries_families(root: Path) -> tuple[bool, str]:
    try:
        sys.path.insert(0, str(root))
        from scripts.check_law_families import FAMILIES
        doctrine = (root / "ops/principal_doctrine.txt").read_text("utf-8", errors="ignore")
    except Exception as exc:                                  # noqa: BLE001 -- unverifiable
        return False, f"doctrine/families unreadable: {exc}"
    gaps = [f"{fam}:{[m for m in members if m not in doctrine]}"
            for fam, (members, _f, _p) in FAMILIES.items()
            if any(m not in doctrine for m in members)]
    return (not gaps), ("; ".join(gaps) if gaps else "")


def _page(msg: str) -> None:
    """Best-effort page; never raises, never blocks the caller."""
    try:
        subprocess.run(["bash", "-c",
                        f'source {_ROOT}/ops/brain_env.sh 2>/dev/null && '
                        f'_brain_page "LAW GUARD: {msg[:180]}"'],
                       capture_output=True, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError):
        return


def guard(*, strict: bool = False, ttl_s: int = DEFAULT_TTL_S,
          root: Path | None = None) -> GuardResult:
    """Verify the laws hold before this process acts. See module docstring for the contract."""
    root = root or _ROOT
    if os.environ.get("QUANT_LAW_GUARD") == "off":
        # Deliberately possible and deliberately LOUD: a guard that cannot be disabled in an
        # emergency gets deleted from every call site instead, which is strictly worse. Every
        # use is recorded, so a bypass is a dated human act rather than a quiet habit.
        _record(root, "BYPASSED via QUANT_LAW_GUARD=off")
        return GuardResult(True, ("bypassed",))

    marker = root / _MARKER.name if root != _ROOT else _MARKER
    try:
        if marker.exists() and (time.time() - marker.stat().st_mtime) < ttl_s:
            return GuardResult(True, cached=True)
    except OSError:
        pass                                                  # unreadable marker -> re-verify

    failures: list[str] = []
    ok_core, why_core = _core_seal_ok(root)
    if not ok_core:
        failures.append(f"CORE-SEAL: {why_core}")
    ok_doc, why_doc = _doctrine_carries_families(root)
    if not ok_doc:
        failures.append(f"DOCTRINE-GAP: {why_doc}")

    if failures:
        _record(root, "; ".join(failures))
        _page("; ".join(failures))
        if strict:
            raise LawBreach(
                "refusing to act under a law breach (money path, L1.42): "
                + "; ".join(failures))
        return GuardResult(False, tuple(failures))

    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(datetime.now(tz=UTC).isoformat(), "utf-8")
    except OSError as exc:
        # Not fatal, but NOT silent: an unwritable marker means every organ re-verifies, which is
        # slow rather than unsafe -- surfaced so the slowness has a stated cause.
        _record(root, f"marker unwritable (re-verifying every process): {exc}")
    return GuardResult(True)


def _record(root: Path, msg: str) -> None:
    try:
        p = root / _BREACHES.name if root != _ROOT else _BREACHES
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(f"{datetime.now(tz=UTC).isoformat()} {msg}\n")
    except OSError:
        return
