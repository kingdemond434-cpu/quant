"""CONSUMPTION-TIME FRESHNESS (L1.44) -- a decision is only as live as its inputs.

THE CLASS THIS CLOSES. The desk has five producer-side max-age registries (max_audit,
check_ratchets, check_miner_runway, check_exploration, data_health), all hand-enumerated, all
answering "did the producer run?" -- and NONE knowing who READS what. So a dead producer surfaced
as one idleness line among 25 while its frozen artifact kept steering live decisions as if
current. The desk's own record holds at least five hand-found instances of this one unnamed
class: the max_push queue consumed 2h stale by every brain slot (the L1.28c proving instance),
an idle Holm slot fed by a stale snapshot, panel_verdicts 189h old pinning a payload at its
floor, the ADL force-order window firing after its condition had passed, and the 13,155/4,500
two-sources equity split. Severity is set by the CONSUMER, which is why producer-side registries
could never see it.

THE MECHANISM. Every decision-path read of a produced artifact declares its maximum tolerated
age AT THE READ SITE:

    from libs.ops.fresh import read_fresh
    fr = read_fresh("data/cost_model.json", max_age_h=48.0, caller="executor._rt_bps")
    # fr.data (parsed JSON or None), fr.age_h, fr.fresh, fr.why

Each call appends its contract (path, max_age_h, caller, kind) to
data/freshness_contracts.jsonl, TTL-throttled per (caller, path) exactly like lawful.guard's
marker -- so the registry of who-consumes-what BUILDS ITSELF from actual reads. No sixth hand
list to rot, and the registry is simultaneously the producer->consumer edge list that L1.28c's
event-driven end state requires.

THE FOUR DESIGN RULES, each closing a way this class hid:
  * CONTENT `generated` OUTRANKS MTIME. The 10-minute auto-deploy and the puller's revert path
    rewrite files, so mtime lies FRESH after a deploy -- the dangerous direction. All five
    existing registries are mtime-based and share that hole; this helper reads the artifact's
    own stamp first and falls back to mtime only when no stamp exists.
  * FRESH-BUT-EMPTY IS NOT FRESH (R0159). A truncated write or zero-row payload passes every
    age check with a young mtime -- the silent-empty failure this module exists to prevent,
    wearing the age gate as camouflage. A caller may declare content floors at the read site:
    min_rows= (len() of a list/dict payload) and min_bytes= (raw file size). A floor violation
    takes the SAME refusal path as stale -- fresh=False, stale_read recorded, StaleRead under
    mode='strict' -- with the failed floor and the observed value named in `why`. Default None
    = no floor, so no read site changes behaviour until it opts in; and a floor can only
    REMOVE freshness, never grant it to a read the age gate already refused.
  * kind='state' MEANS GUARDIAN-LIVENESS, NEVER OWN-AGE. A valid-until-changed file
    (stage_state.json) is legitimately old; its read is fresh iff the named GUARDIAN organ's
    artifact is alive within the contract. This distinction is what keeps the fence from crying
    wolf on healthy state (L1.43: a gate that cries wolf gets switched off).
  * THE CALLER NAMES ITS DEGRADE DIRECTION. mode='fallback' returns the data with fresh=False
    and the read site decides (a stale denylist still DENIES; a stale cost may only TIGHTEN a
    gate); mode='strict' raises StaleRead, for reads where acting on frozen input is worse than
    not acting -- the executor-grade direction, mirroring lawful.guard(strict=True).

Recording is best-effort BY DESIGN: a telemetry failure must never break a money-path read. That
is not a silent swallow -- an unwritable registry surfaces at the fence as UNMEASURED (zero
contracts can never read OK, L1.28a), so the failure is still loud; the reader is just not the
organ that screams. Fenced by scripts/check_freshness.py.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REGISTRY_REL = "data/freshness_contracts.jsonl"
_MARKERS_REL = "data/.fresh_markers"
CONTRACT_TTL_S = 6 * 3600     # one contract line per (caller, path) per 6h window
STALE_EVENT_TTL_S = 900       # stale/unreadable events at most every 15min per (caller, path)


class StaleRead(RuntimeError):
    """Raised by read_fresh(mode='strict') -- the caller declared frozen input worse than none."""


@dataclass(frozen=True)
class FreshRead:
    data: Any                 # parsed JSON, or None when unreadable/missing
    age_h: float | None       # None when the age itself could not be measured
    fresh: bool
    why: str
    source: str               # generated | mtime | missing | unreadable | guardian:<source>


def _root() -> Path:
    """Where a RELATIVE path resolves, and where the registry is written: the CURRENT WORKING
    DIRECTORY, not an internally-guessed install path.

    WHY, because the first version guessed and that was a bug of this module's own class. Every
    caller's paths are already cwd-relative -- `_STAGE = Path("data/stage_state.json")` and
    `_COST_MODEL = Path("data/cost_model.json")` sit at the top of the executor, and every organ
    on the desk is written the same way -- and every launcher pins cwd to the platform root
    (`cd "$QUANT_ROOT" &&` opens all 113 cron lines; the systemd units set WorkingDirectory=).
    Resolving against a guessed root instead made read_fresh the ONLY reader in its own process
    consuming a different install's artifacts: a checkout under /home/user marking against the
    live box's /home/quant/quant-platform/data/live_guard.json, and a test that chdir'd to a tmp
    fixture silently scoring production state instead of its own. Two roots inside one process is
    precisely the two-sources-of-truth class this module exists to close (the 13,155/4,500 equity
    split in the docstring above), so the helper must not introduce a second one.

    QUANT_FRESH_ROOT overrides for callers that must pin a root without moving cwd.
    """
    env = os.environ.get("QUANT_FRESH_ROOT")
    return Path(env) if env else Path.cwd()


def _age_of(path: Path) -> tuple[float | None, str, Any]:
    """(age_h, source, parsed_data). Content `generated` stamp preferred; mtime is the fallback
    because a deploy-rewritten mtime lies fresh -- the dangerous direction for an age check."""
    try:
        raw = path.read_text("utf-8")
    except OSError:
        return None, "missing", None
    try:
        data = json.loads(raw)
    except ValueError:
        return None, "unreadable", None
    age_gen: float | None = None
    if isinstance(data, dict) and data.get("generated"):
        try:
            at = datetime.fromisoformat(str(data["generated"]))
            if at.tzinfo is None:
                at = at.replace(tzinfo=UTC)
            age_gen = max(0.0, (datetime.now(tz=UTC) - at).total_seconds() / 3600.0)
        except ValueError:
            age_gen = None      # malformed stamp -> fall back to mtime, never hide the artifact
    if age_gen is not None:
        return age_gen, "generated", data
    try:
        return max(0.0, (time.time() - path.stat().st_mtime) / 3600.0), "mtime", data
    except OSError:
        return None, "missing", data


def _rel(root: Path, p: Path) -> str:
    try:
        return str(p.relative_to(root))
    except ValueError:
        return str(p)


def _record(root: Path, event: str, path: str, caller: str, kind: str,
            max_age_h: float, age_h: float | None, guardian: str | None,
            min_rows: int | None = None, min_bytes: int | None = None) -> None:
    """Append to the self-building registry, marker-throttled. Best-effort by design (see module
    docstring): failure here must never break the read; the fence reports the silent registry."""
    key = hashlib.sha1(f"{caller}|{path}|{event}".encode()).hexdigest()[:16]
    suffix = ".c" if event == "contract" else ".s"
    marker = root / _MARKERS_REL / (key + suffix)
    ttl = CONTRACT_TTL_S if event == "contract" else STALE_EVENT_TTL_S
    try:
        if marker.exists() and (time.time() - marker.stat().st_mtime) < ttl:
            return
        marker.parent.mkdir(parents=True, exist_ok=True)
        reg = root / REGISTRY_REL
        reg.parent.mkdir(parents=True, exist_ok=True)
        rec: dict[str, Any] = {
            "ts": datetime.now(tz=UTC).isoformat(), "event": event, "path": path,
            "caller": caller, "kind": kind, "max_age_h": max_age_h,
            "age_h": None if age_h is None else round(age_h, 3),
            "guardian": guardian,
        }
        # Declared content floors join the contract line only when a caller opts in, so the
        # registry line stays byte-identical for every existing (floorless) read site.
        if min_rows is not None:
            rec["min_rows"] = min_rows
        if min_bytes is not None:
            rec["min_bytes"] = min_bytes
        with reg.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
        marker.write_text(datetime.now(tz=UTC).isoformat(), "utf-8")
    except OSError:
        return


def _floor_violation(p: Path, data: Any, min_rows: int | None,
                     min_bytes: int | None) -> str | None:
    """None, or a message naming each content floor that failed and the OBSERVED value.

    The floors close the hole the age check cannot see: a fresh-but-EMPTY artifact (zero rows,
    truncated write) steers a decision with nothing in it while every timestamp reads young.
    min_rows is len() of the parsed payload (list or dict); min_bytes is the raw file size.
    Unverifiable counts as FAILED -- a payload whose rows cannot be counted, or a file whose
    size cannot be stat'd, has not met its declared floor (the same never-weaken direction as
    the rest of this module)."""
    fails: list[str] = []
    if min_rows is not None:
        rows = len(data) if isinstance(data, (list, dict)) else None
        if rows is None or rows < min_rows:
            observed = (f"{rows} row(s)" if rows is not None else
                        f"uncountable {type(data).__name__} payload")
            fails.append(f"min_rows={min_rows} floor failed: observed {observed}")
    if min_bytes is not None:
        try:
            size: int | None = p.stat().st_size
        except OSError:
            size = None
        observed = f"{size}B" if size is not None else "unmeasurable size"
        if size is None or size < min_bytes:
            fails.append(f"min_bytes={min_bytes} floor failed: observed {observed}")
    return "; ".join(fails) if fails else None


def read_fresh(path: Path | str, max_age_h: float, *, caller: str,
               kind: str = "measurement", guardian: Path | str | None = None,
               mode: str = "fallback", min_rows: int | None = None,
               min_bytes: int | None = None, root: Path | None = None) -> FreshRead:
    """Read a produced artifact under a declared freshness contract. See module docstring.

    kind='measurement' -- age is the artifact's own (generated stamp, else mtime).
    kind='state'       -- age is the GUARDIAN artifact's; requires guardian=. The state file's
                          own age is irrelevant by construction (valid-until-changed).
    min_rows= / min_bytes= -- optional CONTENT floors on the read artifact itself (R0159): a
                          fresh-but-empty payload (zero rows, truncated write) fails exactly
                          like stale, with the violated floor and observed value in `why`.
                          None (default) = no floor.
    """
    root = root or _root()
    p = Path(path)
    p = p if p.is_absolute() else root / p
    guardian_rel: str | None = None
    if kind == "state":
        if guardian is None:
            raise ValueError("kind='state' requires guardian= (the organ artifact whose "
                             "liveness makes this state trustworthy)")
        g = Path(guardian)
        g = g if g.is_absolute() else root / g
        guardian_rel = _rel(root, g)
        age, gsource, _gdata = _age_of(g)
        _own_age, _own_source, data = _age_of(p)
        source = f"guardian:{gsource}"
        fresh = age is not None and age <= max_age_h and data is not None
    else:
        age, source, data = _age_of(p)
        fresh = age is not None and age <= max_age_h
    # CONTENT FLOORS (R0159). Checked only on a read the age gate would pass: the floor may
    # only take freshness away (fresh-but-empty -> refused), never hand it back to a read
    # already refused as stale/missing -- so no gate below ever weakens.
    empty_why: str | None = None
    if fresh and (min_rows is not None or min_bytes is not None):
        empty_why = _floor_violation(p, data, min_rows, min_bytes)
        fresh = empty_why is None
    rel = _rel(root, p)
    why = (f"EMPTY: {empty_why} (age {age:.2f}h <= {max_age_h}h via {source})" if empty_why else
           f"fresh ({age:.2f}h <= {max_age_h}h via {source})" if fresh else
           f"STALE {age:.2f}h > {max_age_h}h ({source})" if age is not None else
           f"{source}: no age measurable")
    _record(root, "contract", rel, caller, kind, max_age_h, age, guardian_rel,
            min_rows, min_bytes)
    if not fresh:
        # A floor violation lands here with age still measurable, so it records as the SAME
        # stale_read event a frozen artifact would -- one refusal path, not a softer second one.
        event = "stale_read" if age is not None else "unreadable_read"
        _record(root, event, rel, caller, kind, max_age_h, age, guardian_rel,
                min_rows, min_bytes)
        if mode == "strict":
            raise StaleRead(f"{caller}: {rel} -- {why} (L1.44 strict: frozen input declared "
                            "worse than no input at this read site)")
    return FreshRead(data=data, age_h=age, fresh=fresh, why=why, source=source)
