"""THE ALL-PRODUCER BREADTH CONTROLLER: who feeds the docket, over what, and where to steer next.

RULES-COMPLIANCE ROW 13 (zuck, 2026-11-19/20, PERMANENT): breadth control on EVERY producer --
the symbol x timeframe x mechanism grid, class and exotic quotas, and a controller that keeps
evolving. Until this leg only the conversion-handoff converter was steered; breadth_sweep,
formula_library, expression_factory, the deep-forest and world miners, the seats compiled by
`miner_candidate_compiler` and the generator lanes all minted with no view of each other. This is
the one artifact that holds all of them against the same docket.

WHAT IT READS (and it only reads; every write is its own two files):

    data/hypotheses/external_survivors.json   THE DOCKET -- the one input the sealed judge reads,
                                              so the one place every producer's cells meet.
                                              STREAMED row by row (it is ~2 GB on the box) with
                                              `libs.research.family_firing.iter_json_array`.
    data/universe/universe.json               the asset class of every symbol, through
                                              `research.universe_policy` (MetaTrader's registry;
                                              a symbol absent from it is UNCLASSIFIED).
    reports/JUDGE_COVERAGE.json               `realised_pass_rate`: per family, judged and passed
                                              from the gate-verdict ledger -- the measured yield
                                              a saturation call needs.
    reports/PRODUCER_BREADTH.json             (optional) the per-module seat names, so a seat
    reports/PRODUCER_YIELD.json               stamp folds into its producer; and the producer
    reports/GENERATOR_COVERAGE.json           rosters, so a producer that never reached the
                                              docket is listed DEAD rather than absent.

A PRODUCER IS DISCOVERED, NEVER LISTED. The roster is every `source` stamp the docket carries
(normalised: `miner:<seat>` -> the seat, `orthogonal_sweep:<family>` -> orthogonal_sweep,
`breadth_sweep/<family>` -> breadth_sweep, `gold_hour_sweep_h07_rr2` -> gold_hour_sweep) plus
every producer the three roster artifacts name. One that lands tomorrow is measured tomorrow.

ABSENCE IS NEVER ZERO (L1.28a). No docket, a docket the merge has not rewritten for
`DOCKET_STALE_H`, a docket whose newest cell is older than a day (the MergeDocket hang of 11-23
read as every producer at zero), or a stream cut short by the budget: each makes the window counts
UNMEASURED with the reason, and no producer is called DEAD on them.

WHAT IT WRITES:

    reports/BREADTH_CONTROLLER.json        the measurement (per producer and whole desk)
    data/breadth_controller_steer.json     the ADVISORY control signal producers may read

THE STEER IS ADVICE, NOT A GATE. Nothing here changes a producer, a threshold, a trial count, the
judge, or the sealed `scripts/external_gauntlet.py`; a producer that never reads the steer file
behaves exactly as it did. Every "away" entry carries its missed-growth line (GROWTH GOVERNANCE:
no reduction without one) and a saturated family keeps an exploration floor -- breadth is the
objective and yield the tiebreak, so nothing is steered to zero (`libs.research.funnel_census`).

    python desks/mt5/research/breadth_controller.py [--budget-s 420] [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UNMEASURED = "UNMEASURED"
SCHEMA = "breadth_controller/1"
STEER_SCHEMA = "breadth_controller_steer/1"

OUT = BASE / "reports" / "BREADTH_CONTROLLER.json"
STEER = BASE / "data" / "breadth_controller_steer.json"
DOCKET = BASE / "data" / "hypotheses" / "external_survivors.json"
JUDGE_COVERAGE = BASE / "reports" / "JUDGE_COVERAGE.json"
PRODUCER_BREADTH = BASE / "reports" / "PRODUCER_BREADTH.json"
PRODUCER_YIELD = BASE / "reports" / "PRODUCER_YIELD.json"
GENERATOR_COVERAGE = BASE / "reports" / "GENERATOR_COVERAGE.json"

#: THE 90/10 RULE (zuck): at least 90% of research compute on non-exotic instruments. A docket
#: cell is the unit the judge spends a build on, so the share of CELLS is the compute share this
#: leg can measure; the fence reads the 7-day window (a day is too few cells for some producers).
EXOTIC_CEILING = 0.10
#: A merge that has not rewritten the docket for this long cannot say what anyone minted today.
DOCKET_STALE_H = 6.0
#: The newest cell in the docket older than this means NO producer reached it for a day -- on
#: this desk that has always been the merge stalled (11-23 MergeDocket hang), never every producer
#: dying at once; the windows read UNMEASURED rather than DEAD for all.
DOCKET_SILENT_H = 24.0
#: NARROW: one asset class above this share of a producer's 7d cells, or one symbol above the
#: second share. Below `NARROW_MIN_CELLS` cells a producer is too small to be called narrow.
NARROW_CLASS_SHARE = 0.80
NARROW_SYMBOL_SHARE = 0.50
NARROW_MIN_CELLS = 20
#: SATURATED: a family holding at least this share of the desk's cells whose measured yield is
#: below `LOW_YIELD_FRACTION` of the desk's own survivors-per-1k-judged, on at least
#: `MIN_JUDGED_FOR_YIELD` judged cells. Fewer judged cells is UNMEASURED yield, never low yield.
SATURATION_SHARE = 0.05
LOW_YIELD_FRACTION = 0.5
MIN_JUDGED_FOR_YIELD = 200
#: The exploration floor a saturated family keeps in every producer that mints it. Borrowed from
#: the funnel census so the desk has one floor, not two.
DEFAULT_EXPLORATION_FLOOR = 0.02
#: Output bounds (the artifact is read hourly by RC-1 and by producers; it must stay small).
TOP_SYMBOLS = 10
TOP_FAMILIES = 10
STEER_LIST = 10
FRONTIER_SAMPLE = 200
FRONTIER_PER_FAMILY = 4
LADDER = ("M1", "M5", "M15", "M30", "H1", "H4", "D1")
DEFAULT_BUDGET_S = 420.0
#: Seconds kept back from any budget for the two writes.
WRITE_MARGIN_S = 20.0
UNCLASSIFIED = "unclassified"


# ------------------------------------------------------------------ small readers
def _read(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return default


def _parse_ts(raw: Any) -> datetime | None:
    if not raw:
        return None
    try:
        ts = datetime.fromisoformat(str(raw).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


def _share(n: int, d: int) -> float | str:
    return round(n / d, 4) if d > 0 else UNMEASURED


def _atomic_write(path: Path, doc: Any) -> Path:
    """tmp + os.replace beside the target. The tmp name carries the pid so two writers on the
    box never share one; `os.replace` is atomic on NTFS and POSIX alike."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8", newline="\n")
    os.replace(tmp, path)
    return path


# ------------------------------------------------------------------ the repo's own readers
def _iter_docket(path: Path) -> Iterable[Any]:
    from libs.research.family_firing import iter_json_array
    return iter_json_array(path)


def _class_of_factory() -> Callable[[str], str]:
    """symbol -> asset class from MetaTrader's registry via `universe_policy`, cached per pass.
    A symbol the registry does not hold is UNCLASSIFIED (never guessed from its name)."""
    try:
        from research import universe_policy as up
    except Exception:
        return lambda _s: UNCLASSIFIED
    cache: dict[str, str] = {}

    def of(sym: str) -> str:
        key = str(sym or "").strip().upper()
        if key not in cache:
            try:
                klass = up.asset_class_of(key) if key else ""
            except Exception:
                klass = ""
            cache[key] = klass or UNCLASSIFIED
        return cache[key]
    return of


def is_exotic_class(klass: str) -> bool:
    """The registry's own word: MetaTrader classes exotics as `Forex Exotics` (see
    `research/exotic_cost_bar.exotic_symbols`, which reads the same field the same way)."""
    return "exotic" in str(klass or "").lower()


def lane_symbols() -> tuple[list[str], str]:
    """Every hypothesis-lane symbol with bars on disk (`breadth_rotation.hypothesis_symbols`),
    else every hypothesis-lane symbol in the registry, with which one answered."""
    try:
        from research.breadth_rotation import hypothesis_symbols
        syms = list(hypothesis_symbols())
        if syms:
            return syms, "breadth_rotation.hypothesis_symbols (hypothesis lane with H1 bars)"
    except Exception:
        pass
    try:
        from research import universe_policy as up
        reg = up._registry()
        syms = sorted(s for s in reg if up.lane(s) == up.HYPOTHESIS)
        if syms:
            return syms, "universe_policy registry hypothesis lane (bars not checked here)"
    except Exception:
        pass
    return [], f"{UNMEASURED}: no hypothesis-lane symbol readable (no bars, no registry)"


def buildable_families() -> tuple[list[str], str]:
    """Families the SEALED judge can build (`gauntlet_buildability.census`). A frontier cell the
    judge cannot build is not a frontier: steering toward it mints zero-signal cells."""
    try:
        from research.gauntlet_buildability import BUILDABLE, census
        fams = sorted(f for f, v in census().items() if v.get("verdict") == BUILDABLE)
        if fams:
            return fams, "gauntlet_buildability.census (BUILDABLE)"
    except Exception as exc:
        return [], f"{UNMEASURED}: gauntlet_buildability unavailable ({type(exc).__name__})"
    return [], f"{UNMEASURED}: gauntlet_buildability census empty"


def tf_domain(family: str) -> tuple[str, ...]:
    try:
        from mt5desk.families_orthogonal import timeframe_domain
        dom = tuple(str(t).upper() for t in timeframe_domain(family))
        return tuple(t for t in LADDER if t in dom) or LADDER
    except Exception:
        return LADDER


def exploration_floor() -> float:
    try:
        from libs.research.funnel_census import MIN_FAMILY_SHARE
        return float(MIN_FAMILY_SHARE)
    except Exception:
        return DEFAULT_EXPLORATION_FLOOR


# ------------------------------------------------------------------ producer attribution
_SWEEP_SUFFIX = re.compile(r"_h\d{1,2}(_rr[0-9.]+)?$")


def producer_of(row: dict[str, Any]) -> str:
    """The producer that CAUSED a docket row, from the row's own `source` stamp.

    `miner:<seat>[:<sub>]` is the seat; `<organ>:<detail>` and `<organ>/<detail>` are the organ;
    a per-hour sweep's `gold_hour_sweep_h07_rr2` is `gold_hour_sweep`; a path is its stem. A row
    with no source falls back to the merge lane it arrived through (`producer`, a SOURCES file),
    and a row with neither is UNATTRIBUTED -- counted, never guessed."""
    src = str(row.get("source") or "").strip()
    if src:
        if src.startswith("miner:"):
            parts = src.split(":")
            key = parts[1] if len(parts) > 1 and parts[1] else "miner"
        else:
            head = re.split(r"[:]", src, maxsplit=1)[0]
            if head.endswith((".json", ".py", ".jsonl")):
                key = Path(head).stem
            else:
                key = head.split("/", 1)[0]
            key = _SWEEP_SUFFIX.sub("", key)
        key = key.strip().lower()
        if key:
            return key
    lane = str(row.get("producer") or "").strip()
    if lane:
        return Path(lane.replace("\\", "/")).stem.lower() or "unattributed"
    return "unattributed"


def _roster_names(doc: Any) -> list[str]:
    """Producer names from a roster artifact of any of the shapes the desk writes: a dict keyed by
    producer under `producers`/`generators`/`methods`/`seats`, or a list of rows naming one."""
    out: list[str] = []
    if not isinstance(doc, dict):
        return out
    for key in ("producers", "generators", "methods", "seats"):
        v = doc.get(key)
        if isinstance(v, dict):
            out.extend(str(k) for k in v)
        elif isinstance(v, list):
            for r in v:
                if isinstance(r, dict):
                    name = r.get("producer") or r.get("name") or r.get("method") \
                        or r.get("generator")
                    if name:
                        out.append(str(name))
                elif isinstance(r, str):
                    out.append(r)
    return out


def rosters(producer_breadth: Path, producer_yield: Path,
            generator_coverage: Path) -> tuple[dict[str, list[str]], dict[str, str],
                                                dict[str, str], dict[str, str]]:
    """(known_from, alias -> producer, producer -> PRODUCER_YIELD verdict, input status)."""
    known: dict[str, list[str]] = {}
    alias: dict[str, str] = {}
    yv: dict[str, str] = {}
    status: dict[str, str] = {}
    for label, path in (("PRODUCER_BREADTH", producer_breadth),
                        ("PRODUCER_YIELD", producer_yield),
                        ("GENERATOR_COVERAGE", generator_coverage)):
        doc = _read(path)
        if not isinstance(doc, dict):
            status[label] = f"{UNMEASURED}: {path.name} absent or unreadable"
            continue
        names = _roster_names(doc)
        status[label] = f"read: {len(names)} producer(s)"
        for n in names:
            known.setdefault(n.lower(), []).append(label)
        if label == "PRODUCER_BREADTH" and isinstance(doc.get("producers"), dict):
            for name, row in doc["producers"].items():
                for seat in (row or {}).get("seats") or [] if isinstance(row, dict) else []:
                    s = str(seat).lower()
                    if s and s != str(name).lower():
                        alias.setdefault(s, str(name).lower())
        if label == "PRODUCER_YIELD" and isinstance(doc.get("producers"), list):
            for r in doc["producers"]:
                if isinstance(r, dict) and r.get("producer"):
                    yv[str(r["producer"]).lower()] = str(r.get("verdict") or "")
    return known, alias, yv, status


# ------------------------------------------------------------------ the tally
class Tally:
    """One producer's (or the desk's) counts over the docket."""

    __slots__ = ("cls7", "cls24", "cls_stock", "exo7", "exo24", "exo_stock", "fam7",
                 "fam_stock", "lanes", "last", "n7", "n24", "stock", "sym7", "tf7", "undated")

    def __init__(self) -> None:
        self.stock = self.n24 = self.n7 = self.undated = 0
        self.exo7 = self.exo24 = self.exo_stock = 0
        self.cls7: Counter[str] = Counter()
        self.cls24: Counter[str] = Counter()
        self.cls_stock: Counter[str] = Counter()
        self.sym7: Counter[str] = Counter()
        self.fam7: Counter[str] = Counter()
        self.fam_stock: Counter[str] = Counter()
        self.tf7: Counter[str] = Counter()
        self.lanes: Counter[str] = Counter()
        self.last: datetime | None = None

    def add(self, at: datetime | None, now: datetime, sym: str, klass: str, fam: str, tf: str,
            lane: str) -> None:
        exo = is_exotic_class(klass)
        self.stock += 1
        self.cls_stock[klass] += 1
        self.exo_stock += exo
        if fam:
            self.fam_stock[fam] += 1
        if lane:
            self.lanes[lane] += 1
        if at is None:
            self.undated += 1
            return
        if self.last is None or at > self.last:
            self.last = at
        if at < now - timedelta(days=7):
            return
        self.n7 += 1
        self.cls7[klass] += 1
        self.exo7 += exo
        if sym:
            self.sym7[sym] += 1
        if fam:
            self.fam7[fam] += 1
        self.tf7[tf] += 1
        if at >= now - timedelta(hours=24):
            self.n24 += 1
            self.cls24[klass] += 1
            self.exo24 += exo


def _row_cell(r: dict[str, Any]) -> tuple[str, str, str]:
    params = r.get("params") if isinstance(r.get("params"), dict) else {}
    sym = str(r.get("symbol") or r.get("sym") or "").strip().upper()
    if not sym and isinstance(r.get("symbols"), list) and r["symbols"]:
        sym = str(r["symbols"][0]).strip().upper()
    tf = str(params.get("timeframe") or r.get("timeframe") or "H1").strip().upper()
    return sym, tf, str(r.get("family") or "").strip()


def scan_docket(path: Path, now: datetime, deadline: float, class_of: Callable[[str], str],
                alias: dict[str, str]) -> dict[str, Any]:
    """Stream the docket once. Returns per-producer tallies, the desk tally, the sampled grid and
    the stream's status (ABSENT / UNREADABLE / PARTIAL / COMPLETE)."""
    per: dict[str, Tally] = {}
    desk = Tally()
    sampled: Counter[tuple[str, str, str]] = Counter()
    fam_producers: dict[str, Counter[str]] = {}
    res: dict[str, Any] = {"per": per, "desk": desk, "sampled": sampled,
                           "fam_producers": fam_producers, "rows": 0, "status": "ABSENT",
                           "why": f"{path} absent"}
    if not path.exists():
        return res
    rows = 0
    try:
        for r in _iter_docket(path):
            if rows % 2048 == 0 and time.monotonic() > deadline:
                res.update(status="PARTIAL",
                           why=f"budget exhausted after {rows} row(s); counts are lower bounds")
                res["rows"] = rows
                return res
            rows += 1
            if not isinstance(r, dict):
                continue
            sym, tf, fam = _row_cell(r)
            klass = class_of(sym) if sym else UNCLASSIFIED
            name = producer_of(r)
            name = alias.get(name, name)
            at = _parse_ts(r.get("first_seen"))
            lane = Path(str(r.get("producer") or "").replace("\\", "/")).name
            per.setdefault(name, Tally()).add(at, now, sym, klass, fam, tf, lane)
            desk.add(at, now, sym, klass, fam, tf, lane)
            if sym and fam:
                sampled[(sym, tf, fam)] += 1
            if fam:
                fam_producers.setdefault(fam, Counter())[name] += 1
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        res.update(status="UNREADABLE", why=f"{type(exc).__name__}: {exc}", rows=rows)
        return res
    res.update(status="COMPLETE", why=f"{rows} row(s) streamed", rows=rows)
    return res


def docket_freshness(path: Path, desk: Tally, now: datetime) -> tuple[bool, str, dict[str, Any]]:
    """(windows measurable?, why, facts). The docket is a plain array with no `generated_at`, so
    its age is its mtime; the newest `first_seen` says whether anything reached it lately."""
    facts: dict[str, Any] = {"mtime_age_h": UNMEASURED, "newest_first_seen": None,
                             "newest_first_seen_age_h": UNMEASURED}
    try:
        age = (now.timestamp() - path.stat().st_mtime) / 3600.0
        facts["mtime_age_h"] = round(age, 2)
    except OSError:
        return False, f"{path.name} absent", facts
    if desk.last is not None:
        facts["newest_first_seen"] = desk.last.isoformat(timespec="seconds")
        facts["newest_first_seen_age_h"] = round((now - desk.last).total_seconds() / 3600.0, 2)
    if age > DOCKET_STALE_H:
        return False, (f"{path.name} not rewritten for {age:.1f}h (> {DOCKET_STALE_H:g}h): the "
                       f"merge is not running, so a zero would be its silence, not a producer's"), \
            facts
    if desk.last is None:
        return False, f"{path.name} carries no dated row (`first_seen`)", facts
    silent = (now - desk.last).total_seconds() / 3600.0
    if silent > DOCKET_SILENT_H:
        return False, (f"newest docket cell is {silent:.1f}h old (> {DOCKET_SILENT_H:g}h): no "
                       f"producer reached the docket for a day, which on this desk is the merge "
                       f"stalled, not every producer dead"), facts
    return True, "fresh", facts


# ------------------------------------------------------------------ yield and saturation
def family_yield(path: Path) -> tuple[dict[str, dict[str, Any]], str, float | str]:
    """{family: judged, passed, survivors_per_1k}, status, desk survivors per 1k judged -- from
    JUDGE_COVERAGE.realised_pass_rate (counted from the gate-verdict ledger every pass)."""
    doc = _read(path)
    rows = doc.get("realised_pass_rate") if isinstance(doc, dict) else None
    if not isinstance(rows, list):
        return {}, f"{UNMEASURED}: {path.name} absent or carries no realised_pass_rate", \
            UNMEASURED
    out: dict[str, dict[str, Any]] = {}
    tj = tp = 0
    for r in rows:
        if not isinstance(r, dict) or not r.get("family"):
            continue
        try:
            j, p = int(r.get("judged") or 0), int(r.get("passed") or 0)
        except (TypeError, ValueError):
            continue
        tj += j
        tp += p
        out[str(r["family"])] = {"judged": j, "passed": p,
                                 "survivors_per_1k": round(1000.0 * p / j, 3) if j else None}
    desk = round(1000.0 * tp / tj, 3) if tj else UNMEASURED
    at = doc.get("at") or doc.get("generated_at") if isinstance(doc, dict) else None
    return out, f"{path.name} realised_pass_rate ({len(out)} families, at {at})", desk


def saturation(fam_cells: Counter[str], basis: str, yields: dict[str, dict[str, Any]],
               desk_rate: float | str,
               fam_producers: dict[str, Counter[str]]) -> dict[str, Any]:
    total = sum(fam_cells.values())
    sat: list[dict[str, Any]] = []
    unmeasured: list[dict[str, Any]] = []
    for fam, n in fam_cells.most_common():
        share = n / total if total else 0.0
        if share < SATURATION_SHARE:
            break
        y = yields.get(fam) or {}
        judged = int(y.get("judged") or 0)
        row = {"family": fam, "cells": n, "share": round(share, 4), "judged": judged,
               "passed": int(y.get("passed") or 0),
               "survivors_per_1k_judged": y.get("survivors_per_1k"),
               "top_producers": dict((fam_producers.get(fam) or Counter()).most_common(5))}
        if not isinstance(desk_rate, float) or judged < MIN_JUDGED_FOR_YIELD:
            row["why"] = (f"yield UNMEASURED: {judged} judged < {MIN_JUDGED_FOR_YIELD}"
                          if isinstance(desk_rate, float) else
                          "yield UNMEASURED: no desk survivors-per-1k (JUDGE_COVERAGE absent)")
            unmeasured.append(row)
            continue
        rate = float(y.get("survivors_per_1k") or 0.0)
        if rate < LOW_YIELD_FRACTION * desk_rate:
            row["why"] = (f"{share:.1%} of cells at {rate:g} survivors/1k judged against the "
                          f"desk's {desk_rate:g} (< {LOW_YIELD_FRACTION:g}x)")
            sat.append(row)
    return {"basis": basis, "cells": total, "desk_survivors_per_1k_judged": desk_rate,
            "rule": (f"saturated = share of cells >= {SATURATION_SHARE:.0%} AND survivors per 1k "
                     f"judged < {LOW_YIELD_FRACTION:g}x the desk's, on >= "
                     f"{MIN_JUDGED_FOR_YIELD} judged; fewer judged is UNMEASURED yield, never low"),
            "saturated": sat, "high_share_yield_unmeasured": unmeasured}


# ------------------------------------------------------------------ frontier
def frontier(sampled: Counter[tuple[str, str, str]], symbols: list[str], sym_why: str,
             families: list[str], fam_why: str, class_of: Callable[[str], str],
             tf_of: Callable[[str], tuple[str, ...]]) -> dict[str, Any]:
    """(symbol x timeframe x family) cells of the buildable grid that NO producer has ever put in
    the docket, summarised per axis, with a frontier-first sample to steer toward."""
    if not symbols or not families:
        why = "; ".join(w for w in (sym_why, fam_why) if w.startswith(UNMEASURED)) or UNMEASURED
        return {"status": UNMEASURED, "why": why}
    sym_set = set(symbols)
    fam_set = set(families)
    seen_sym: Counter[str] = Counter()
    seen_fam: Counter[str] = Counter()
    seen_tf: Counter[str] = Counter()
    seen_fc: set[tuple[str, str]] = set()
    seen_ct: set[tuple[str, str]] = set()
    for (s, tf, f), n in sampled.items():
        if s in sym_set:
            seen_sym[s] += n
            seen_ct.add((class_of(s), tf))
        if f in fam_set:
            seen_fam[f] += n
            if s in sym_set:
                seen_fc.add((f, class_of(s)))
        seen_tf[tf] += n
    classes = sorted({class_of(s) for s in symbols})
    by_class: dict[str, list[str]] = {}
    for s in symbols:
        by_class.setdefault(class_of(s), []).append(s)
    space = unsampled = 0
    fam_unsampled: Counter[str] = Counter()
    for f in families:
        for tf in tf_of(f):
            for s in symbols:
                space += 1
                if (s, tf, f) not in sampled:
                    unsampled += 1
                    fam_unsampled[f] += 1
    # FRONTIER FIRST: families never sampled lead, then the least-sampled; inside a family the
    # least-sampled class, then a symbol nobody has touched, on a chart rotated per family.
    order = sorted(families, key=lambda f: (seen_fam.get(f, 0), f))
    sample: list[dict[str, str]] = []
    for i, f in enumerate(order):
        if len(sample) >= FRONTIER_SAMPLE:
            break
        tfs = tf_of(f)
        taken = 0
        for klass in sorted(by_class, key=lambda c: ((f, c) in seen_fc, c)):
            syms = sorted(by_class[klass], key=lambda s: (seen_sym.get(s, 0), s))
            for j, s in enumerate(syms):
                tf = tfs[(i + j) % len(tfs)]
                if (s, tf, f) in sampled:
                    continue
                sample.append({"symbol": s, "timeframe": tf, "family": f, "class": klass})
                taken += 1
                break
            if taken >= FRONTIER_PER_FAMILY or len(sample) >= FRONTIER_SAMPLE:
                break
    fc_never = [{"family": f, "class": c} for f in order for c in classes
                if (f, c) not in seen_fc]
    ct_never = [{"class": c, "timeframe": t} for c in classes for t in LADDER
                if (c, t) not in seen_ct]
    return {
        "status": "MEASURED",
        "symbols_basis": sym_why, "families_basis": fam_why,
        "rule": ("a frontier cell is (symbol x timeframe x family) on the hypothesis lane, a "
                 "family the sealed judge can build and a chart that family declares, that no "
                 "producer has ever put in the docket"),
        "space_cells": space, "sampled_cells": space - unsampled, "unsampled_cells": unsampled,
        "unsampled_share": _share(unsampled, space),
        "families_never_sampled": [f for f in order if not seen_fam.get(f)],
        "symbols_never_sampled": sorted(s for s in symbols if not seen_sym.get(s)),
        "timeframes_never_sampled": [t for t in LADDER if not seen_tf.get(t)],
        "family_x_class_never_sampled": {"n": len(fc_never), "head": fc_never[:STEER_LIST * 5]},
        "class_x_timeframe_never_sampled": ct_never,
        "least_sampled_families": [{"family": f, "cells": seen_fam.get(f, 0),
                                    "unsampled_cells": fam_unsampled.get(f, 0)}
                                   for f in order[:STEER_LIST * 2]],
        "sample": sample,
    }


# ------------------------------------------------------------------ verdicts and steer
def _top(c: Counter[str], n: int, total: int) -> list[dict[str, Any]]:
    return [{"name": k, "cells": v, "share": _share(v, total)} for k, v in c.most_common(n)]


def _missed_growth(kind: str, subject: str, why: str, floor: float | None = None) -> dict:
    """The missed-growth line every reduction carries (GROWTH GOVERNANCE Rule 1). The steer is
    advisory and acts on nothing, so the E[log W] it could cost is UNMEASURED and says so."""
    line = {"rail": "breadth_controller", "side": "cost", "kind": "opportunity_cost",
            "subject": f"{kind}:{subject}", "value": None, "verdict": UNMEASURED,
            "e_log_w": UNMEASURED,
            "units": "survivors forgone in cells a producer would have minted here",
            "why": why, "acting": False}
    if floor is not None:
        line["floor_share"] = floor
    return line


def producer_verdict(t: Tally | None, measured: bool, unmeasured_why: str,
                     complete: bool) -> tuple[str, str]:
    if not measured:
        return UNMEASURED, unmeasured_why
    n24 = t.n24 if t else 0
    if n24 == 0:
        if not complete:
            return UNMEASURED, ("0 cells in 24h in the part of the docket read; the stream was "
                                "cut by the budget, so absence is not measured")
        return "DEAD", "0 docket cells in the last 24h"
    assert t is not None
    if t.n7 >= NARROW_MIN_CELLS:
        k, kn = t.cls7.most_common(1)[0]
        if kn / t.n7 > NARROW_CLASS_SHARE:
            return "NARROW", (f"{kn / t.n7:.0%} of 7d cells in class {k} "
                              f"(> {NARROW_CLASS_SHARE:.0%})")
        if t.sym7:
            s, sn = t.sym7.most_common(1)[0]
            if sn / t.n7 > NARROW_SYMBOL_SHARE:
                return "NARROW", (f"{sn / t.n7:.0%} of 7d cells on {s} "
                                  f"(> {NARROW_SYMBOL_SHARE:.0%})")
    return "CONTRIBUTING", f"{n24} cell(s) in 24h across {len(t.cls7)} class(es)"


def _steer_for(t: Tally | None, verdict: str, why: str, desk_ctx: dict[str, Any],
               floor: float, windows_ok: bool) -> dict[str, Any]:
    """One producer's advisory steer. Family facts use the desk's basis: the 7d window when it is
    measured, else the docket stock (so a stalled merge still names what a producer saturates)."""
    sat = {r["family"]: r for r in desk_ctx["saturated"]}
    fams: Counter[str] = (t.fam7 if windows_ok else t.fam_stock) if t else Counter()
    toward_classes = [c for c in desk_ctx["undersampled_classes"]
                      if not (t and t.n7 and t.cls7.get(c, 0) / t.n7 > NARROW_CLASS_SHARE)]
    own_least: list[str] = []
    if fams:
        desk_fam = desk_ctx["desk_fam"]
        own_least = sorted(fams, key=lambda f: (desk_fam.get(f, 0), f))
        own_least = [f for f in own_least if f not in sat][:STEER_LIST]
    away_fams: list[dict[str, Any]] = []
    floors: dict[str, float] = {}
    for fam in fams:
        if fam in sat:
            r = sat[fam]
            floors[fam] = floor
            away_fams.append({
                "family": fam, "producer_cells": fams[fam],
                "producer_cells_basis": "7d" if windows_ok else "docket stock",
                "why": r["why"],
                "missed_growth": _missed_growth(
                    "family", fam,
                    (f"cells moved out of {fam} forgo its next survivor at the measured "
                     f"{r['survivors_per_1k_judged']} per 1k judged; a low yield from a judge "
                     f"is evidence about that test as much as the mechanism (funnel_census), so "
                     f"the family keeps {floor:.0%} of this producer's cells"), floor)})
    away_classes: list[dict[str, Any]] = []
    away_symbols: list[dict[str, Any]] = []
    if verdict == "NARROW" and t is not None and t.n7:
        k, kn = t.cls7.most_common(1)[0]
        if kn / t.n7 > NARROW_CLASS_SHARE:
            away_classes.append({"class": k, "share_7d": round(kn / t.n7, 4), "why": why,
                                 "missed_growth": _missed_growth(
                                     "class", k,
                                     (f"cells moved off {k} forgo that class's survivors; "
                                      f"the shift is toward classes the desk under-samples, "
                                      f"and {k} keeps every cell above the narrow line"))})
        elif t.sym7:
            s, sn = t.sym7.most_common(1)[0]
            away_symbols.append({"symbol": s, "share_7d": round(sn / t.n7, 4), "why": why,
                                 "missed_growth": _missed_growth(
                                     "symbol", s,
                                     (f"cells moved off {s} forgo its survivors; a symbol "
                                      f"above {NARROW_SYMBOL_SHARE:.0%} of one producer adds "
                                      f"cells, not independent bets"))})
    if desk_ctx["exotic_verdict"] == "BREACH" and t is not None and t.n7 \
            and t.exo7 / t.n7 > EXOTIC_CEILING:
        already = {a["class"] for a in away_classes}
        for k in [c for c in t.cls7 if is_exotic_class(c) and c not in already]:
            away_classes.append({
                "class": k, "share_7d": round(t.cls7[k] / t.n7, 4),
                "why": (f"desk exotic share above the {EXOTIC_CEILING:.0%} ceiling and this "
                        f"producer is at {t.exo7 / t.n7:.0%}"),
                "missed_growth": _missed_growth(
                    "class", k,
                    ("exotic cells moved out forgo exotic survivors; under the strict exotic "
                     "cost bar (research/exotic_cost_bar.py) an exotic must still pay at 2x its "
                     "costs to trade, so the forgone growth is bounded by that bar's pass rate, "
                     "UNMEASURED here"))})
    return {
        "verdict": verdict, "why": why,
        "toward": {
            "classes": toward_classes[:STEER_LIST],
            "symbols": desk_ctx["frontier_symbols"][:STEER_LIST],
            "families_frontier": desk_ctx["frontier_families"][:STEER_LIST],
            "families_own_least_sampled": own_least,
            "cells_frontier_first": "desk.toward.cells_frontier_first",
        },
        "away": {"families": away_fams, "classes": away_classes, "symbols": away_symbols},
        "exploration_floor_share": floors,
    }


# ------------------------------------------------------------------ build
def build(now: datetime | None = None, *, budget_s: float = DEFAULT_BUDGET_S,
          docket: Path | None = None, judge_coverage: Path | None = None,
          producer_breadth: Path | None = None, producer_yield: Path | None = None,
          generator_coverage: Path | None = None,
          class_of: Callable[[str], str] | None = None,
          symbols: tuple[list[str], str] | None = None,
          families: tuple[list[str], str] | None = None,
          tf_of: Callable[[str], tuple[str, ...]] | None = None) -> tuple[dict, dict]:
    """(BREADTH_CONTROLLER document, steer document). Every input can be injected for tests."""
    now = now or datetime.now(UTC)
    t0 = time.monotonic()
    deadline = t0 + max(1.0, budget_s - WRITE_MARGIN_S)
    docket = docket or DOCKET
    judge_coverage = judge_coverage or JUDGE_COVERAGE
    class_of = class_of or _class_of_factory()
    tf_of = tf_of or tf_domain
    known, alias, yverdict, roster_status = rosters(
        producer_breadth or PRODUCER_BREADTH, producer_yield or PRODUCER_YIELD,
        generator_coverage or GENERATOR_COVERAGE)
    scan = scan_docket(docket, now, deadline, class_of, alias)
    per: dict[str, Tally] = scan["per"]
    desk: Tally = scan["desk"]
    complete = scan["status"] == "COMPLETE"
    if scan["status"] in ("ABSENT", "UNREADABLE"):
        measured, why_unmeasured, fresh_facts = False, f"docket {scan['status']}: {scan['why']}", {}
    else:
        measured, why_unmeasured, fresh_facts = docket_freshness(docket, desk, now)
        why_unmeasured = f"docket: {why_unmeasured}"
    windows_ok = measured

    def cells(n: int) -> int | str:
        return n if windows_ok else UNMEASURED

    # ---- whole desk
    tot24, tot7 = desk.n24, desk.n7

    def split(c: Counter[str], total: int) -> dict[str, Any]:
        return {k: {"cells": v, "share": _share(v, total)} for k, v in c.most_common()}

    class_split = {
        "basis": "asset class from MetaTrader's registry (research/universe_policy.asset_class_of);"
                 " a symbol absent from it is unclassified",
        "window_24h": split(desk.cls24, tot24) if windows_ok else UNMEASURED,
        "window_7d": split(desk.cls7, tot7) if windows_ok else UNMEASURED,
        "docket_stock": split(desk.cls_stock, desk.stock) if scan["rows"] else UNMEASURED,
    }
    if windows_ok and tot7 > 0:
        exo_share: float | str = round(desk.exo7 / tot7, 4)
        exo_verdict = "PASS" if exo_share <= EXOTIC_CEILING else "BREACH"
        exo_why = f"{desk.exo7} of {tot7} 7d cells on registry-classed exotics"
    else:
        exo_share, exo_verdict = UNMEASURED, UNMEASURED
        exo_why = why_unmeasured if not windows_ok else "0 cells in 7d: no share to measure"
    exotic_fence = {
        "rule": (f"90/10: at least {1 - EXOTIC_CEILING:.0%} of research compute on non-exotic "
                 f"instruments; measured as the share of docket cells (one judge build each) on "
                 f"symbols MetaTrader classes as exotic"),
        "ceiling": EXOTIC_CEILING, "basis": "7d docket cells",
        "exotic_share_7d": exo_share,
        "exotic_share_24h": _share(desk.exo24, tot24) if windows_ok else UNMEASURED,
        "exotic_share_stock": _share(desk.exo_stock, desk.stock) if scan["rows"] else UNMEASURED,
        "verdict": exo_verdict, "why": exo_why,
    }
    # ---- saturation
    yields, ystatus, desk_rate = family_yield(judge_coverage)
    if windows_ok and tot7 > 0:
        fam_cells, fam_basis = desk.fam7, "7d docket cells"
    else:
        fam_cells, fam_basis = desk.fam_stock, "docket stock (7d window unmeasured or empty)"
    sat = saturation(fam_cells, fam_basis, yields, desk_rate, scan["fam_producers"]) \
        if scan["rows"] else {"basis": UNMEASURED, "saturated": [],
                              "high_share_yield_unmeasured": [],
                              "why": f"docket {scan['status']}: {scan['why']}"}
    sat["yield_source"] = ystatus
    if not isinstance(desk_rate, float) and scan["rows"]:
        sat["status"] = UNMEASURED
    else:
        sat["status"] = "MEASURED" if scan["rows"] else UNMEASURED
    # ---- frontier
    syms, sym_why = symbols if symbols is not None else lane_symbols()
    fams, fam_why = families if families is not None else buildable_families()
    front = frontier(scan["sampled"], syms, sym_why, fams, fam_why, class_of, tf_of) \
        if scan["rows"] else {"status": UNMEASURED, "why": f"docket {scan['status']}"}
    if scan["status"] == "PARTIAL" and front.get("status") == "MEASURED":
        front["status"] = "PARTIAL"
        front["why"] = "docket stream cut by the budget: some 'never sampled' cells may be sampled"
    # under-sampled classes: share of cells against share of lane symbols, lowest first
    lane_cls = Counter(class_of(s) for s in syms)
    ref = desk.cls7 if (windows_ok and tot7) else desk.cls_stock
    ref_total = sum(ref.values())
    ratios: list[tuple[float, str]] = []
    for k, n in lane_cls.items():
        sym_share = n / len(syms) if syms else 0.0
        cell_share = ref.get(k, 0) / ref_total if ref_total else 0.0
        if sym_share > 0:
            ratios.append((cell_share / sym_share, k))
    ratios.sort()
    undersampled = [k for r, k in ratios if r < 1.0
                    and (not is_exotic_class(k) or exo_verdict == "PASS")]
    class_balance = [{"class": k, "cell_share_over_symbol_share": round(r, 4)} for r, k in ratios]
    desk_ctx = {
        "saturated": sat.get("saturated") or [],
        "undersampled_classes": undersampled,
        "desk_fam": fam_cells,
        "exotic_verdict": exo_verdict,
        "frontier_symbols": front.get("symbols_never_sampled") or [],
        "frontier_families": front.get("families_never_sampled") or [],
        "frontier_sample": front.get("sample") or [],
    }
    floor = exploration_floor()
    # ---- per producer
    names = set(per) | set(known)
    rows: dict[str, Any] = {}
    steer_rows: dict[str, Any] = {}
    verdicts: Counter[str] = Counter()
    for name in sorted(names):
        t = per.get(name)
        verdict, vwhy = producer_verdict(t, windows_ok, why_unmeasured, complete)
        if verdict == "DEAD" and (t is None or t.stock == 0):
            vwhy += ("; no docket row has ever carried its name -- rows compiled for it may "
                     "carry the compiler's stamp (e.g. discovery_compiler)")
        verdicts[verdict] += 1
        tt = t or Tally()
        n7 = tt.n7
        row: dict[str, Any] = {
            "known_from": (["docket"] if t is not None else []) + known.get(name, []),
            "cells_24h": cells(tt.n24), "cells_7d": cells(n7),
            "share_24h": _share(tt.n24, tot24) if windows_ok else UNMEASURED,
            "share_7d": _share(n7, tot7) if windows_ok else UNMEASURED,
            "cells_docket_stock": tt.stock, "undated_rows": tt.undated,
            "last_cell_at": tt.last.isoformat(timespec="seconds") if tt.last else None,
            "by_class_7d": split(tt.cls7, n7) if windows_ok else UNMEASURED,
            "top_symbols_7d": _top(tt.sym7, TOP_SYMBOLS, n7) if windows_ok else UNMEASURED,
            "symbols_7d": len(tt.sym7) if windows_ok else UNMEASURED,
            "top_families_7d": _top(tt.fam7, TOP_FAMILIES, n7) if windows_ok else UNMEASURED,
            "timeframes_7d": dict(tt.tf7.most_common()) if windows_ok else UNMEASURED,
            "exotic_share_7d": _share(tt.exo7, n7) if windows_ok else UNMEASURED,
            "saturated_families_minted": sorted(
                f for f in (tt.fam7 if windows_ok else tt.fam_stock)
                if f in {r["family"] for r in desk_ctx["saturated"]}),
            "lanes": dict(tt.lanes.most_common()),
            "producer_yield_verdict": yverdict.get(name) or None,
            "verdict": verdict, "verdict_why": vwhy,
            "counts_complete": complete,
        }
        rows[name] = row
        steer_rows[name] = _steer_for(t, verdict, vwhy, desk_ctx, floor, windows_ok)
    unmeasured_inputs = {k: v for k, v in {
        "docket": None if scan["rows"] else f"{scan['status']}: {scan['why']}",
        "windows": None if windows_ok else why_unmeasured,
        "family_yield": None if isinstance(desk_rate, float) else ystatus,
        **{f"roster:{k}": (v if v.startswith(UNMEASURED) else None)
           for k, v in roster_status.items()},
        "frontier": None if front.get("status") in ("MEASURED", "PARTIAL")
        else front.get("why"),
    }.items() if v}
    gen = now.isoformat(timespec="seconds")
    doc = {
        "schema": SCHEMA, "generated_at": gen,
        "rule": ("per producer that donates docket cells: cells in 24h/7d, share, class and "
                 "symbol split, exotic share, saturated families it mints, and a verdict "
                 "(CONTRIBUTING / NARROW / DEAD / UNMEASURED); whole desk: the 90/10 exotic "
                 "fence, the class split, saturated families and the never-sampled frontier. "
                 "Absent input is UNMEASURED, never zero (L1.28a). Advisory: it changes no "
                 "producer, gate, threshold or trial count."),
        "constants": {"exotic_ceiling": EXOTIC_CEILING, "docket_stale_h": DOCKET_STALE_H,
                      "docket_silent_h": DOCKET_SILENT_H,
                      "narrow_class_share": NARROW_CLASS_SHARE,
                      "narrow_symbol_share": NARROW_SYMBOL_SHARE,
                      "narrow_min_cells": NARROW_MIN_CELLS,
                      "saturation_share": SATURATION_SHARE,
                      "low_yield_fraction": LOW_YIELD_FRACTION,
                      "min_judged_for_yield": MIN_JUDGED_FOR_YIELD,
                      "exploration_floor_share": floor},
        "inputs": {"docket": str(docket), "judge_coverage": str(judge_coverage),
                   "rosters": roster_status},
        "unmeasured_inputs": unmeasured_inputs,
        "docket": {"status": scan["status"], "why": scan["why"], "rows_read": scan["rows"],
                   "windows": "MEASURED" if windows_ok else UNMEASURED,
                   "windows_why": "fresh" if windows_ok else why_unmeasured,
                   "undated_rows": desk.undated, **fresh_facts},
        "desk": {"cells_24h": cells(tot24), "cells_7d": cells(tot7),
                 "cells_docket_stock": desk.stock, "producers": len(rows),
                 "verdicts": dict(verdicts),
                 "dead": sorted(n for n, r in rows.items() if r["verdict"] == "DEAD"),
                 "narrow": sorted(n for n, r in rows.items() if r["verdict"] == "NARROW")},
        "exotic_fence": exotic_fence,
        "class_split": class_split,
        "class_balance": {"basis": ("cell share / share of hypothesis-lane symbols, lowest "
                                    "first; below 1 is under-sampled"),
                          "rows": class_balance},
        "family_saturation": sat,
        "frontier": front,
        "steer_file": str(STEER),
        "wall_s": round(time.monotonic() - t0, 2),
        "producers": rows,
    }
    steer = {
        "schema": STEER_SCHEMA, "generated_at": gen, "advisory": True,
        "rule": ("ADVISORY INPUT ONLY: shift toward the frontier first (never-sampled families, "
                 "symbols and cells; under-sampled classes) and away from saturated families, "
                 "never below the exploration floor; no producer, gate, threshold or trial count "
                 "is changed by this file. Every 'away' carries its missed-growth line."),
        "source": str(OUT),
        "exotic_ceiling": EXOTIC_CEILING, "exotic_fence": exo_verdict,
        "exploration_floor_share": floor,
        "desk": {"toward": {"classes": undersampled[:STEER_LIST],
                            "symbols": desk_ctx["frontier_symbols"][:STEER_LIST],
                            "families": desk_ctx["frontier_families"][:STEER_LIST],
                            "timeframes": front.get("timeframes_never_sampled") or [],
                            "cells_frontier_first": desk_ctx["frontier_sample"][:STEER_LIST * 2]},
                 "away": {"families": [
                     {"family": r["family"], "share": r["share"], "why": r["why"],
                      "floor_share": floor,
                      "missed_growth": _missed_growth(
                          "family", r["family"],
                          (f"desk-wide shift out of {r['family']} forgoes its survivors at "
                           f"{r['survivors_per_1k_judged']} per 1k judged; it keeps {floor:.0%} "
                           f"of every producer's cells so a recovery is still seen"), floor)}
                     for r in desk_ctx["saturated"]]}},
        "producers": steer_rows,
    }
    return doc, steer


def write(doc: dict, steer: dict, out: Path | None = None,
          steer_out: Path | None = None) -> tuple[Path, Path]:
    return _atomic_write(out or OUT, doc), _atomic_write(steer_out or STEER, steer)


def _budget(arg: float) -> float:
    """--budget-s, never past the hourly cycle's cap (QUANT_LEG_BUDGET_S) less a write minute."""
    b = float(arg)
    try:
        cap = float(os.environ.get("QUANT_LEG_BUDGET_S") or 0)
    except ValueError:
        cap = 0.0
    if cap > 0:
        b = min(b, max(30.0, cap - 60.0))
    return b


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--budget-s", type=float, default=DEFAULT_BUDGET_S)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    doc, steer = build(budget_s=_budget(a.budget_s))
    p, s = write(doc, steer)
    if a.json:
        print(json.dumps(doc, indent=1, default=str))
    else:
        d, f = doc["desk"], doc["exotic_fence"]
        print(f"breadth_controller: docket {doc['docket']['status']} "
              f"({doc['docket']['rows_read']} rows, windows {doc['docket']['windows']}); "
              f"cells 24h {d['cells_24h']} 7d {d['cells_7d']}; producers {d['producers']} "
              f"{d['verdicts']}; exotic {f['exotic_share_7d']} -> {f['verdict']}; saturated "
              f"{[r['family'] for r in doc['family_saturation'].get('saturated') or []]}")
        print(f"  -> {p}\n  -> {s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
