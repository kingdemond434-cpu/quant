"""The global mining supervisor's wiring: paths, constants, the desk hooks, the pass report.

Split out of `mining_supervisor.py` for size only; every name here is re-exported by
`mining_supervisor`, which remains the organ the hourly leg runs.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_ROOT), str(_DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.mining import acquirer as acq  # noqa: E402

SOURCE = "global_mining"
DATA = _DESK / "data" / "mining"
REPORTS = _DESK / "reports" / "mining"
#: The organ's own artifact (read by the component registry and the runtime attestation).
REPORT = REPORTS / "MINING_METRICS.json"
#: THE COMMITTED DIGEST. reports/ and data/mining/ are box-only; this one small file is tracked,
#: sits under a state prefix, and is pushed by the box's hourly capture commit, so a reader on
#: GitHub sees the day's metrics, the latest rejections and every source -> cell -> prereg ->
#: verdict chain (the six-event trace's event 1-3 evidence) without the box.
DIGEST = _DESK / "data" / "mining_digest.json"
DIGEST_REJECTIONS = 300
DIGEST_CHAINS = 300

#: THE MECHANICS FEED'S CONSUMER. Every broker/prop page's numeric facts become a point-in-time
#: series in the lake directory the `exogenous_conditioner` family reads (its SERIES_DIR), one
#: row per real vintage stamped with the vintage's own `available_for_decision_at`. Once a series
#: holds the family's minimum observations, each changing column mints conditioner cells on the
#: source's target instruments, judged by the one gauntlet like every other cell.
#: 60, not the family's own 30: the gauntlet needs 60 days of returns before it will judge a
#: cell at all (`external_gauntlet` "no valid cells"), so a shorter series keeps accumulating as
#: UNMEASURED rather than minting cells the judge can only refuse.
try:
    from mt5desk.family_exogenous_conditioner import MIN_OBSERVATIONS as _FAMILY_MIN_OBS
except Exception:                                          # tests and a bare checkout
    _FAMILY_MIN_OBS = 30
COND_MIN_OBS = max(60, int(_FAMILY_MIN_OBS))
#: The committed input for the cost and risk models: every page's latest PIT vintage, split
#: into cost facts and prop-rule limits (extractor.COST_FACTS / RULE_FACTS). Never minted as cells.
#: An archive capture: web.archive.org/web/<timestamp>[flags]/<original url>.
_WAYBACK = re.compile(r"^(?:https?://)?(?:www\.)?web\.archive\.org/web/\d+[a-z_]*/(.+)$", re.I)
def _scout_seats() -> dict[str, str]:
    """seat -> producing scout, from research/scout_roster.py `seats=` (the one declared map)."""
    try:
        from research.scout_roster import SCOUTS
    except Exception:
        return {}
    return {str(seat): str(sc["name"]) for sc in SCOUTS for seat in sc.get("seats") or ()}


def producer_of(source: Any, organ_of: Mapping[str, str]) -> str:
    """The organ that produced a docket row: its seat (`miner:<seat>[:<id>]`, or the row's own
    producer prefix) through the scout map, else `unmapped:<seat>` -- named, never guessed."""
    raw = str(source or "")
    seat = raw.removeprefix("miner:").split(":", 1)[0] if raw.startswith("miner:") else \
        raw.split(":", 1)[0]
    return organ_of.get(seat, f"unmapped:{seat or '?'}")


_INDEX_PAGE = re.compile(r"/(?:index|default)\.(?:html?|php|aspx?)$", re.I)
_SECOND_LEVEL = frozenset({"co", "com", "gov", "org", "ac", "or", "ne", "go", "net", "edu"})


def _site(url: Any) -> str:
    """The registrable domain (example.co.jp, darwinex.com), archive captures unwrapped."""
    raw = str(url or "")
    m = _WAYBACK.match(raw)
    labels = acq.canonical_url(m.group(1) if m else raw).partition("/")[0].split(".")
    if len(labels) < 2:
        return ""
    n = 3 if len(labels) >= 3 and labels[-2] in _SECOND_LEVEL and len(labels[-1]) == 2 else 2
    return ".".join(labels[-n:])


#: THE CONTRACT another lane registers a source against (roster row) and reads back (registry row).
REGISTRY_SCHEMA = _ROOT / "libs" / "mining" / "source_registry.schema.json"
MECHANICS_FACTS = _DESK / "data" / "mechanics_facts.json"
COND_TRANSFORMS: tuple[str, ...] = ("level_z", "delta")
UNI = _DESK / "data" / "universe"
HYP = _DESK / "data" / "hypotheses"
GATE_LEDGER = HYP / "gate_verdict_ledger.jsonl"
GATE_INDEX = HYP / "gate_verdict_index.json"

ACTIVE_WINDOW = timedelta(days=30)
REJECTION_RATE_FLOOR = 0.90
QUEUE_AGE_LIMIT_DAYS = 7.0
DEGRADED_SHARE = 0.5
DEEPENING_CAP = 400
DONATE_BATCH = 5_000

#: THE DOCKET'S AXIS EXPANSION, mirrored. `miner_candidate_compiler.expand_axes` turns every
#: donated H1 row that names no chart or session into one docket cell per intraday chart (with
#: bars) x session, H1 last -- up to 16 gauntlet cells per mining cell. Every one is sealed into
#: the preregistration up front and joined back, so the verdict counts are the docket's.
try:
    from research.miner_candidate_compiler import INTRADAY_CHARTS as _CHARTS
    from research.miner_candidate_compiler import SESSION_AXIS as _SESSIONS
except Exception:                                          # tests and a bare checkout
    _CHARTS, _SESSIONS = ("M5", "M15", "M30"), ("all", "asia", "london", "ny")


def axis_variants(spec: Mapping[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """(axis label, spec) for every docket cell `expand_axes` can make from this spec."""
    params = dict(spec.get("params") or {})
    if "timeframe" in params or "session" in params:
        return [("as_donated", dict(spec))]
    out = []
    for tf in (*_CHARTS, "H1"):
        for sess in _SESSIONS:
            p = dict(params)
            if tf != "H1":
                p["timeframe"] = tf
            if sess != "all":
                p["session"] = sess
            out.append((f"{tf}/{sess}", {**spec, "params": p}))
    return out


# ============================================================================ wiring
@dataclass
class Hooks:
    """Everything the pipeline needs from the desk, injectable so tests run it offline."""
    universe: set[str] | None = None
    family_params: Callable[[str], set[str] | None] | None = None
    bars_available: Callable[[str, str], bool] = lambda sym, tf: True
    gauntlet_cell: Callable[[Mapping[str, Any]], str] = lambda spec: _fallback_gcell(spec)
    may_hypothesise: Callable[[str, str], bool] = lambda sym, fam: True
    prior_verdict: Callable[[str], str | None] = lambda gcell: None
    donate: Callable[[list[dict[str, Any]]], tuple[bool, str]] | None = None
    handoff: Callable[[list[dict[str, Any]]], int] | None = None


def _fallback_gcell(spec: Mapping[str, Any]) -> str:
    payload = json.dumps(dict(spec.get("params") or {}), sort_keys=True, separators=(",", ":"))
    return f"{spec.get('sym') or spec.get('symbol')}.{spec.get('family')}.p=" + \
        hashlib.sha256(payload.encode()).hexdigest()[:16]


def desk_hooks() -> Hooks:
    """The live wiring. Every import is guarded: a missing organ degrades to a named state,
    never to a crash of the hourly cycle."""
    h = Hooks()
    try:
        meta = json.loads((UNI / "universe.json").read_text("utf-8"))
        h.universe = {str(k).upper() for k in meta if not str(k).startswith("_")}
    except (OSError, ValueError):
        h.universe = None
    try:
        from mt5desk.families import FAMILY_REGISTRY

        def family_params(name: str) -> set[str] | None:
            row = FAMILY_REGISTRY.get(name)
            return set((row or {}).get("defaults") or {}) if row else None
        h.family_params = family_params
    except Exception:
        h.family_params = None

    def bars_available(sym: str, tf: str) -> bool:
        return (UNI / f"{sym}_{tf}.parquet").exists() or (
            tf != "H1" and (UNI / f"{sym}_H1.parquet").exists() and tf in ("H4", "D1"))
    h.bars_available = bars_available
    try:
        from research.frontier_identity import cell_id as _gcell
        from research.frontier_identity import docket_cell as _dcell
        # the judge's own row -> cell rule (symbol|sym, a row chart folded into params)
        h.gauntlet_cell = lambda spec: str(_gcell(_dcell(dict(spec))))
    except Exception:
        pass
    try:
        from research.universe_policy import may_hypothesise
        h.may_hypothesise = lambda sym, fam: bool(may_hypothesise(sym, fam))
    except Exception:
        pass
    try:
        idx = json.loads(GATE_INDEX.read_text("utf-8"))
        if isinstance(idx, dict):
            h.prior_verdict = lambda gcell: (str(idx[gcell]) if gcell in idx else None)
    except (OSError, ValueError):
        pass

    def donate(rows: list[dict[str, Any]]) -> tuple[bool, str]:
        from research import proposer_common as pc
        path = pc.donate(SOURCE, rows, tests_run=len(rows))
        last = dict(getattr(pc, "LAST_DONATION", {}) or {})
        return path is not None, json.dumps({k: last.get(k) for k in (
            "donated", "refused_unstamped", "refused_wrong_lane", "path")}, default=str)
    h.donate = donate

    def handoff(tasks: list[dict[str, Any]]) -> int:
        from research.regime_coverage import _merge_into_queue
        _merge_into_queue(tasks, source=SOURCE)
        return len(tasks)
    h.handoff = handoff
    return h


# ============================================================================ pipeline
@dataclass
class PassReport:
    started: str
    sources: list[dict[str, Any]] = field(default_factory=list)
    records_processed: int = 0
    cells_created: int = 0
    donated: int = 0
    verdicts_joined: int = 0
    handed_off: int = 0
    errors: list[str] = field(default_factory=list)


def _pct(vals: list[float], q: float) -> float:
    s = sorted(vals)
    k = max(0, min(len(s) - 1, round(q / 100 * (len(s) - 1))))
    return round(s[k], 3)
