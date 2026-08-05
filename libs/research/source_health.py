"""Per-source health ledger -- the desk's memory of WHICH sources are dying, and for how long.

THE GAP THIS CLOSES. scripts/mine_research_queue.py and libs/data/cn_sources.probe_all() already
PROBE every source and record the failure honestly ("zhihu HTTP 403", "baidu anti-bot shell",
"csdn read timeout"). But every run started from zero: a source could be blocked for six weeks,
be re-probed every single day, report the identical failure every single day, and nothing would
ever notice that the failure had a HISTORY. Honest reporting without accumulation is a desk that
re-discovers the same outage forever and never acts on it. This module is the accumulation.

WHAT IT DOES NOT DO. It does not decide anything about mining. It is written to, once, at the end
of a run, and read by scripts/hunt_source_alternatives.py. A ledger that could change what the
miner fetches would make an outage-recorder into a control loop, and the desk has one job for this
file: remember.

TWO HONESTY RULES ARE BUILT INTO THE TYPES, NOT LEFT TO THE CALLER.

  (1) NEVER PROBED IS NOT DEAD. A source with no observation at all is UNKNOWN. Absence of
      evidence is its own state (L1.41); scoring it as a failure would let a source the desk
      simply never tried get condemned -- and then "replaced" -- on the strength of nothing. The
      academic probe already carries a row of exactly this shape (papers.probe_all() hardcodes
      reddit as ok=false without ever making a request), so this is a live hazard, not a
      hypothetical: rows with no measurement field are skipped, not counted as failures.

  (2) BLOCKED FROM THIS BOX IS NOT DEAD GLOBALLY. This container reaches the internet through an
      egress proxy; the VPS does not. The two vantages do not see the same internet, and the
      asymmetry cuts BOTH ways -- a WAF may block the proxy's datacenter egress while the VPS
      sails through, and a source may equally be reachable here only BECAUSE of the proxy. So
      every observation records the vantage it was made from, and the verdict carries a SCOPE:
      evidence from one vantage can only ever support a claim about THAT vantage
      (scope=this_vantage); scope=global requires agreeing evidence from two or more. A DEAD /
      this_vantage verdict is a real, actionable finding -- this box cannot mine that source, so
      hunt a substitute -- but it is never license to delete a source the VPS may be reading fine.

STORAGE follows scripts/classify_regime.py's _append_history idiom exactly: append-only JSONL,
idempotent per UTC day (a second run the same day supersedes that day's row rather than stacking a
duplicate -- the miner is scheduled daily but is also run by hand), lines that will not parse are
PRESERVED verbatim because history is evidence, and the write is same-dir tmp + replace so a
crash mid-write can never leave a torn ledger.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

_ROOT = Path(__file__).resolve().parent.parent.parent
LEDGER_PATH: Final[Path] = _ROOT / "data" / "source_health.jsonl"

#: HOW MANY CONSECUTIVE FAILED RUNS BEFORE A SOURCE IS CALLED DEAD.
#: Five, and the number is a trade between two real costs measured on this desk.
#:
#: TOO LOW and the desk hunts replacements for sources that heal themselves. Every transient this
#: desk has actually seen would trip a threshold of 1 or 2: Sogou serves an anti-bot challenge when
#: rate-limited and clears within hours (libs/data/cn_sources.sogou_weixin says so in its
#: docstring); Bilibili's WBI signing keys rotate daily; and the loudest example is L0052 -- an
#: "OKX BLOCKED, HTTP 403" recorded on 2026-08-01 that turned out to be a User-Agent bot filter,
#: fixed the same day. Chasing substitutes for a source that is fine next morning burns the
#: hunter's whole budget on churn and, worse, teaches the desk to ignore DEAD.
#:
#: TOO HIGH and a genuinely dead lane stays dead while the miner re-probes it. That cost is
#: bounded and, importantly, VISIBLE the whole time: DEGRADED is reported from the FIRST failure,
#: so nothing is hidden during the wait -- only the automatic hunt is deferred.
#:
#: The miner is scheduled daily (ops/crontab.manifest, `0 13 * * *`), so five consecutive failed
#: runs is about five days: longer than every transient above, shorter than a working week of a
#: silently dead research lane.
#: FALSIFIER: if the alternatives hunter starts firing on sources that are healthy again by the
#: time a human reads the report, this number is too low; if a source is dead for more than a
#: week before anything is hunted, it is too high.
DEAD_AFTER_CONSECUTIVE_FAILURES: Final[int] = 5

VERDICT_UNKNOWN: Final[str] = "UNKNOWN"
VERDICT_HEALTHY: Final[str] = "HEALTHY"
VERDICT_DEGRADED: Final[str] = "DEGRADED"
VERDICT_DEAD: Final[str] = "DEAD"
VERDICT_REPLACED: Final[str] = "REPLACED"

#: What the verdict is a claim ABOUT. See honesty rule (2) in the module docstring.
SCOPE_UNKNOWN: Final[str] = "unknown"
SCOPE_THIS_VANTAGE: Final[str] = "this_vantage"
SCOPE_GLOBAL: Final[str] = "global"

#: Where an observation was made from. The container's egress proxy and the VPS's direct route are
#: different internets as far as a WAF is concerned, so they are different vantages.
VANTAGE_PROXIED: Final[str] = "container_egress_proxy"
VANTAGE_DIRECT: Final[str] = "direct"

#: Probe rows and mining lanes name the same platform differently; the ledger must not carry two
#: half-histories for one source.
_ALIASES: Final[dict[str, str]] = {"wechat_sogou": "wechat", "sogou_weixin": "wechat"}


def canonical(source: str) -> str:
    """The one name this desk keeps health under for ``source``."""
    key = source.strip()
    return _ALIASES.get(key, key)


def current_vantage(env: Mapping[str, str] | None = None) -> str:
    """Which internet this process is looking at.

    Presence of a proxy variable is the discriminator because that is exactly what differs
    between this container (HTTPS_PROXY set to a local agent proxy) and the VPS (no proxy at all).
    """
    src = os.environ if env is None else env
    for var in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY"):
        if str(src.get(var, "")).strip():
            return VANTAGE_PROXIED
    return VANTAGE_DIRECT


@dataclass(frozen=True)
class Observation:
    """One source, one run, one vantage. ``ok`` means the source was USABLE, not merely up.

    A 1.5KB anti-bot shell is a 200 OK and is not a source; reachable-but-useless is a failure
    here, with the reason recorded, because mining cannot proceed either way.
    """

    source: str
    ok: bool
    error: str | None = None
    vantage: str | None = None   # None -> resolved to current_vantage() at record time


@dataclass(frozen=True)
class SourceState:
    """Accumulated health for one source, as of its most recent ledger row."""

    source: str
    verdict: str = VERDICT_UNKNOWN
    scope: str = SCOPE_UNKNOWN
    consecutive_failed_runs: int = 0
    last_ok_utc: str | None = None
    last_error: str | None = None
    last_checked_utc: str | None = None
    failing_vantages: tuple[str, ...] = ()
    ok_vantages: tuple[str, ...] = ()
    replaced_by: str | None = None

    @property
    def dead_here(self) -> bool:
        """DEAD from at least this box. True for both scopes -- this box still cannot mine it."""
        return self.verdict == VERDICT_DEAD

    @property
    def dead_globally(self) -> bool:
        """DEAD with evidence from more than one vantage. The only form of 'the source is gone'
        this desk is entitled to assert."""
        return self.verdict == VERDICT_DEAD and self.scope == SCOPE_GLOBAL

    def claim(self) -> str:
        """The verdict written out as the sentence the desk is actually entitled to say."""
        if self.verdict == VERDICT_UNKNOWN:
            return f"{self.source}: never probed -- UNKNOWN, which is not dead and not healthy"
        if self.verdict == VERDICT_REPLACED:
            return f"{self.source}: superseded by {self.replaced_by} -- no longer relied on"
        if self.verdict == VERDICT_HEALTHY:
            where = ("from every vantage tried" if self.scope == SCOPE_GLOBAL
                     else f"from {', '.join(self.ok_vantages) or 'one vantage'} only")
            return f"{self.source}: usable {where}"
        vantages = ", ".join(self.failing_vantages) or "an unrecorded vantage"
        if self.scope == SCOPE_GLOBAL:
            return (f"{self.source}: {self.verdict} after {self.consecutive_failed_runs} "
                    f"consecutive failed runs across {vantages} -- failing from every vantage "
                    f"tried, so this is a claim about the SOURCE")
        return (f"{self.source}: {self.verdict} after {self.consecutive_failed_runs} consecutive "
                f"failed runs, ALL from {vantages} -- a claim about THIS BOX only. The VPS has no "
                f"egress proxy and may reach it fine; do not retire the source on this evidence")


def verdict_for(*, consecutive_failed_runs: int, last_checked_utc: str | None,
                failing_vantages: Sequence[str], ok_vantages: Sequence[str],
                replaced_by: str | None = None,
                dead_after: int = DEAD_AFTER_CONSECUTIVE_FAILURES) -> tuple[str, str]:
    """(verdict, scope) from accumulated counters. Pure -- the whole rule lives here."""
    if replaced_by is not None:
        # A replacement is a DESK decision, and it outranks the network: once the desk is reading
        # a substitute, the old source's reachability stops being the question.
        return VERDICT_REPLACED, _scope_of(failing_vantages or ok_vantages)
    if last_checked_utc is None:
        return VERDICT_UNKNOWN, SCOPE_UNKNOWN      # honesty rule (1)
    if consecutive_failed_runs <= 0:
        return VERDICT_HEALTHY, _scope_of(ok_vantages)
    if consecutive_failed_runs >= dead_after:
        return VERDICT_DEAD, _scope_of(failing_vantages)
    return VERDICT_DEGRADED, _scope_of(failing_vantages)


def _scope_of(vantages: Sequence[str]) -> str:
    """Honesty rule (2): one vantage supports a claim about that vantage and nothing wider."""
    distinct = {v for v in vantages if v}
    if not distinct:
        return SCOPE_UNKNOWN
    return SCOPE_GLOBAL if len(distinct) > 1 else SCOPE_THIS_VANTAGE


# ------------------------------------------------------------------------------- ledger I/O

def _row_to_state(row: Mapping[str, Any]) -> SourceState:
    fail_raw = row.get("failing_vantages")
    ok_raw = row.get("ok_vantages")
    replaced = row.get("replaced_by")
    return SourceState(
        source=str(row.get("source", "")),
        verdict=str(row.get("verdict", VERDICT_UNKNOWN)),
        scope=str(row.get("scope", SCOPE_UNKNOWN)),
        consecutive_failed_runs=int(row.get("consecutive_failed_runs", 0) or 0),
        last_ok_utc=None if row.get("last_ok_utc") is None else str(row["last_ok_utc"]),
        last_error=None if row.get("last_error") is None else str(row["last_error"]),
        last_checked_utc=(None if row.get("last_checked_utc") is None
                          else str(row["last_checked_utc"])),
        failing_vantages=tuple(str(v) for v in fail_raw) if isinstance(fail_raw, list) else (),
        ok_vantages=tuple(str(v) for v in ok_raw) if isinstance(ok_raw, list) else (),
        replaced_by=None if replaced is None else str(replaced),
    )


def _state_to_row(state: SourceState, *, day: str) -> dict[str, Any]:
    return {
        "day": day,
        "source": state.source,
        "verdict": state.verdict,
        "scope": state.scope,
        "consecutive_failed_runs": state.consecutive_failed_runs,
        "last_ok_utc": state.last_ok_utc,
        "last_error": state.last_error,
        "last_checked_utc": state.last_checked_utc,
        "failing_vantages": list(state.failing_vantages),
        "ok_vantages": list(state.ok_vantages),
        "replaced_by": state.replaced_by,
    }


def _read_lines(path: Path) -> list[str]:
    try:
        return [ln for ln in path.read_text("utf-8").splitlines() if ln.strip()]
    except FileNotFoundError:
        return []


def _parsed(line: str) -> dict[str, Any] | None:
    """The row, or None when the line will not parse. Callers PRESERVE unparseable lines."""
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def load_states(path: Path | None = None) -> dict[str, SourceState]:
    """Latest state per source. Sources absent from the ledger are simply absent -- see
    :func:`state_of` for the UNKNOWN default, which is deliberately not invented here."""
    p = LEDGER_PATH if path is None else path
    out: dict[str, SourceState] = {}
    for line in _read_lines(p):
        row = _parsed(line)
        if row is None:
            continue
        name = str(row.get("source", "")).strip()
        if not name:
            continue
        out[canonical(name)] = _row_to_state(row)
    return out


def state_of(source: str, path: Path | None = None) -> SourceState:
    """State for one source. A source the ledger has never seen is UNKNOWN, never DEAD."""
    name = canonical(source)
    return load_states(path).get(name, SourceState(source=name))


def dead_sources(path: Path | None = None) -> list[SourceState]:
    """Every source whose verdict is DEAD, this-vantage or global. Both are worth hunting for:
    a source this box cannot reach is a lane this box cannot mine, whatever the VPS sees."""
    return sorted((s for s in load_states(path).values() if s.dead_here),
                  key=lambda s: (-s.consecutive_failed_runs, s.source))


def record_run(observations: Sequence[Observation], *, path: Path | None = None,
               now: datetime | None = None,
               dead_after: int = DEAD_AFTER_CONSECUTIVE_FAILURES) -> dict[str, SourceState]:
    """Fold one run's observations into the ledger and return the sources it touched.

    IDEMPOTENT PER UTC DAY. Re-running the miner an hour later must not double-count a source's
    failure into DEAD twice as fast, so today's row for a source is REPLACED, and the counter is
    advanced from the state as of the last day BEFORE today -- not from the row this run is about
    to overwrite. Without that second half, replacement alone would still let three runs in one
    day add three to the counter.
    """
    p = LEDGER_PATH if path is None else path
    iso = _utc(now).isoformat(timespec="seconds")
    day = iso[:10]

    wanted = {canonical(o.source) for o in observations}
    kept: list[str] = []
    prior: dict[str, SourceState] = {}
    for line in _read_lines(p):
        row = _parsed(line)
        if row is None:
            kept.append(line)         # never drop a line we cannot parse; history is evidence
            continue
        name = canonical(str(row.get("source", "")))
        if name and str(row.get("day", ""))[:10] == day and name in wanted:
            continue                  # same UTC day, same source -> this run supersedes it
        if name:
            prior[name] = _row_to_state(row)
        kept.append(line)

    touched: dict[str, SourceState] = {}
    for obs in observations:
        name = canonical(obs.source)
        before = prior.get(name, SourceState(source=name))
        vantage = obs.vantage if obs.vantage is not None else current_vantage()
        if obs.ok:
            failing: tuple[str, ...] = ()
            ok_vantages = _add(before.ok_vantages, vantage)
            consecutive = 0
            last_ok: str | None = iso
            last_error: str | None = None
        else:
            failing = _add(before.failing_vantages, vantage)
            ok_vantages = before.ok_vantages
            consecutive = before.consecutive_failed_runs + 1
            last_ok = before.last_ok_utc
            last_error = obs.error
        verdict, scope = verdict_for(
            consecutive_failed_runs=consecutive, last_checked_utc=iso,
            failing_vantages=failing, ok_vantages=ok_vantages,
            replaced_by=before.replaced_by, dead_after=dead_after)
        state = SourceState(
            source=name, verdict=verdict, scope=scope,
            consecutive_failed_runs=consecutive, last_ok_utc=last_ok, last_error=last_error,
            last_checked_utc=iso, failing_vantages=failing, ok_vantages=ok_vantages,
            replaced_by=before.replaced_by)
        touched[name] = state
        kept.append(json.dumps(_state_to_row(state, day=day), ensure_ascii=False))
        prior[name] = state           # a source observed twice in one run must not re-enter twice

    _write(p, kept)
    return touched


def mark_replaced(source: str, replacement: str, *, path: Path | None = None,
                  now: datetime | None = None) -> SourceState:
    """Record that the desk now reads ``replacement`` instead of ``source``.

    Deliberately a SEPARATE call from :func:`record_run`: a replacement is a decision someone
    made after reading a hunt report, not something a probe can conclude on its own.
    """
    p = LEDGER_PATH if path is None else path
    iso = _utc(now).isoformat(timespec="seconds")
    day = iso[:10]
    name = canonical(source)

    kept: list[str] = []
    before = SourceState(source=name)
    for line in _read_lines(p):
        row = _parsed(line)
        if row is None:
            kept.append(line)
            continue
        if canonical(str(row.get("source", ""))) == name:
            before = _row_to_state(row)
            if str(row.get("day", ""))[:10] == day:
                continue
        kept.append(line)

    verdict, scope = verdict_for(
        consecutive_failed_runs=before.consecutive_failed_runs, last_checked_utc=iso,
        failing_vantages=before.failing_vantages, ok_vantages=before.ok_vantages,
        replaced_by=replacement)
    state = replace(before, source=name, verdict=verdict, scope=scope, replaced_by=replacement,
                    last_checked_utc=iso)
    kept.append(json.dumps(_state_to_row(state, day=day), ensure_ascii=False))
    _write(p, kept)
    return state


def _utc(now: datetime | None) -> datetime:
    """Now, in UTC. A NAIVE datetime is rejected rather than localised.

    Silently reading a naive stamp as local time would put the wrong UTC day on a ledger row, and
    the day IS the idempotency key -- two runs an hour apart could land on different days, or two
    different days collapse onto one. That is a corrupted history that looks perfectly healthy.
    """
    if now is None:
        return datetime.now(tz=UTC)
    if now.tzinfo is None or now.tzinfo.utcoffset(now) is None:
        raise ValueError("naive datetime rejected: the health ledger is keyed by UTC day, so an "
                         "ambiguous stamp would corrupt the idempotency key")
    return now.astimezone(UTC)


def _add(existing: Sequence[str], vantage: str) -> tuple[str, ...]:
    return tuple(existing) if vantage in existing else (*existing, vantage)


def _write(path: Path, lines: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text("\n".join(lines) + "\n", "utf-8")
    tmp.replace(path)                 # same-dir tmp + replace: never a torn ledger


# ------------------------------------------------------- deriving observations from a miner run

#: Report keys whose values are {lane: fetched_count}. A lane present in one of these means the
#: miner ACTUALLY FETCHED from it this run, which is the strongest evidence a source is usable.
#: The second element is the platform when the report key alone determines it, and None when the
#: platform must be read off the lane key -- and that difference is NOT cosmetic: the keys of
#: `bilibili_discovered` and `search_discovered` are bare query strings ("量化交易 策略"), while
#: the keys of `cn_article_discovered` and `academic_discovered` are prefixed ("juejin:量化",
#: "arxiv:q-fin.TR"). Deriving the platform from the lane key in all five cases files every
#: Bilibili query under a platform named after the query.
_LANE_COUNTS: Final[tuple[tuple[str, str | None], ...]] = (
    ("channels_scanned", "youtube"),        # keys are channel handles
    ("search_discovered", "youtube"),       # keys are bare search queries
    ("bilibili_discovered", "bilibili"),    # keys are bare search queries
    ("cn_article_discovered", None),        # keys are "juejin:<kw>" / "wechat:<kw>"
    ("academic_discovered", None),          # keys are "arxiv:<cat>" / "ssrn:..." / "hn"
)


def _platform_of(lane: str) -> str:
    """The platform a lane key names. `@neurotrader888` and `search:foo` are both YouTube;
    `juejin:量化` is Juejin; `arxiv:q-fin.TR` is arXiv."""
    head = lane.split(":", 1)[0].strip()
    if head.startswith("@") or head == "search":
        return "youtube"
    return canonical(head)


def _rows(doc: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    raw = doc.get(key)
    return [r for r in raw if isinstance(r, Mapping)] if isinstance(raw, list) else []


def _mapping(doc: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    raw = doc.get(key)
    return raw if isinstance(raw, Mapping) else {}


def _is_measured(row: Mapping[str, Any]) -> bool:
    """Did this probe row come from an actual request?

    papers.probe_all() hardcodes `{"source": "reddit", "ok": False, "error": "HTTP 403 --
    blocked"}` without making one. Counting that as a failed run would march a never-probed source
    to DEAD on the strength of a comment, which is honesty rule (1) exactly inverted. A row that
    carries no measurement -- no result count, no byte count, no reachability -- is DECLARED, not
    measured, and contributes nothing.
    """
    return any(k in row for k in ("n", "bytes", "reachable", "http_status"))


def _probe_ok(row: Mapping[str, Any]) -> tuple[bool, str | None]:
    """(usable, reason) for one probe row, across the two probe shapes on this desk.

    WHAT A PROBE CAN AND CANNOT REFUTE. probe_cn() measures two things: did bytes come back, and
    were there more than 20,000 of them. That is real evidence against a declared "blocked" --
    the L0052 lesson is exactly that a recorded block can be wrong, so the declared status is a
    prior and the probe is the evidence. It is NOT evidence against a declared "needs_browser",
    because a client-rendered shell can be any size at all: BigQuant's shell measures 27,705 bytes
    and sails over the content bar while carrying zero listings. Letting a byte count overturn a
    rendering finding would mark a source HEALTHY that the miner cannot read a single row from,
    which is worse than the silence it replaces -- a dead lane wearing a green badge.
    """
    err = row.get("error")
    reason: str | None = str(err) if err is not None else None
    flag = row.get("ok")
    if isinstance(flag, bool):
        if flag:
            return True, None
        return False, reason if reason is not None else "probe reported ok=false, no reason given"
    if str(row.get("declared", "")) == "needs_browser":
        note = str(row.get("reason") or reason or "listings require a browser")
        return False, (f"declared needs_browser and this probe cannot refute that (it measures "
                       f"bytes, not rendering): {note}")
    if row.get("reachable") is not True:
        if reason is not None:
            return False, reason
        status = row.get("http_status")
        return False, (f"unreachable (HTTP {status})" if status is not None else "unreachable")
    if row.get("looks_like_content") is False:
        detail = f" ({row.get('bytes')} bytes)" if row.get("bytes") is not None else ""
        return False, (reason if reason is not None
                       else f"reachable but served a non-content shell{detail}")
    return True, None


def observations_from_miner_report(doc: Mapping[str, Any]) -> list[Observation]:
    """Turn one reports/research_queue.json document into per-source observations.

    THREE RULES, in order, and the order is the point.

    1. USE OUTRANKS PROBE. A lane the miner actually fetched from is stronger evidence than a
       diagnostic probe of the same platform, so probes only speak for platforms with no lane
       evidence this run. Bilibili is the live case: the miner reads it successfully through
       WBI-signed search, while CN_SOURCES probes the RAW search endpoint, which answers 412
       because it is unsigned. Letting that probe outvote 15 mined rows would mark a working
       source dead.
    2. ANY LANE UP MEANS THE PLATFORM IS UP. Four Juejin queries where one succeeds is a usable
       source, and the failure of the other three is a query problem, not a source death.
    3. NOT ATTEMPTED IS NOT FAILED. `--only bilibili` leaves every other group with no lanes and
       no probes; those sources get NO observation, so their counters neither advance nor reset.
       Absence is absence (L1.41).
    """
    lanes: dict[str, list[bool]] = {}
    reasons: dict[str, str] = {}

    def _note(name: str, ok: bool, reason: str | None) -> None:
        key = canonical(name)
        if not key:
            return
        lanes.setdefault(key, []).append(ok)
        if not ok and reason is not None and key not in reasons:
            reasons[key] = reason

    for key, fixed in _LANE_COUNTS:
        for lane in _mapping(doc, key):
            _note(fixed if fixed is not None else _platform_of(str(lane)), True, None)
    for lane, why in _mapping(doc, "channels_blocked").items():
        _note(_platform_of(str(lane)), False, str(why)[:200])

    # Probes fill in only the platforms no lane spoke for -- rule 1.
    for key in ("cn_source_probe", "academic_probe", "cn_sources"):
        for row in _rows(doc, key):
            raw_name = str(row.get("source") or row.get("name") or "").strip()
            name = canonical(raw_name)
            if not name or name in lanes or not _is_measured(row):
                continue
            ok, reason = _probe_ok(row)
            _note(name, ok, reason)

    vantage = current_vantage()
    out: list[Observation] = []
    for name in sorted(lanes):
        ok = any(lanes[name])
        out.append(Observation(source=name, ok=ok,
                               error=None if ok else reasons.get(name), vantage=vantage))
    return out


def record_from_report(doc: Mapping[str, Any], *, path: Path | None = None,
                       now: datetime | None = None) -> dict[str, SourceState]:
    """The one call the miner makes. Additive: it reads the finished report and writes the ledger.

    Swallows OSError only, for the same reason mine_research_queue._append_yield does: a ledger
    that cannot be written is a lost day of health history, while a miner that dies on it is a
    lost day of RESEARCH. Anything other than a disk failure is a bug and stays loud.
    """
    try:
        return record_run(observations_from_miner_report(doc), path=path, now=now)
    except OSError:
        return {}
