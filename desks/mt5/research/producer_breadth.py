"""PRODUCER BREADTH: what every cell producer actually minted, over what, and what it could reach.

THE PRINCIPAL'S ASK (2026-09-30): "make all producers produce orthogonal worldwide global breadth
cells possible for the gauntlet 24/7 through maximum quantity breadth and depth in coverage and
max potential" -- and then "testable". This is the MEASUREMENT half of that order, hourly: one
artifact that says, per producer, whether it is on a clock, when it last produced, how many
cells it minted in 24h and 7d, which symbols / charts / sessions / families those cells span
AGAINST what that producer could reach, what share of them the SEALED gauntlet can actually
build (`research/gauntlet_buildability`), and which alpha clusters they feed. Its totals name
the clusters that are still unfed and WHY: no family, a family the sealed judge cannot build, or
a buildable family nobody mints.

IT READS, IT NEVER WRITES A LEDGER. Sources, in order of authority:

    1. the canonical registry (`data/alpha_registry.sqlite`, `research_candidates` joined to
       `discoveries` exactly as `scripts/check_producer_yield` joins them, crediting the
       producer that CAUSED the cell rather than the compiler that stamped it);
    2. the producer's seat under `data/intelligence/<seat>/` (the donation contract every
       proposer writes), read newest-first under a byte budget;
    3. the producer's own report (`reports/BREADTH_SWEEP.json` for the sweep that writes the
       docket directly) or the merge SOURCES artifact it owns.

A producer none of these can see is UNMEASURED with the reason -- never zero (L1.28a). Which of
the three answered is recorded per producer as `measured_from`.

`INVENTORY` below is the per-producer record of what caps its breadth, read from the code on
2026-09-30, and what this branch did about it. It is DATA that travels in the artifact, so the
next session reads the caps without re-deriving them; the measured columns beside it say whether
the widening actually shows up in minted cells.

    python desks/mt5/research/producer_breadth.py            # write reports/PRODUCER_BREADTH.json
    python desks/mt5/research/producer_breadth.py --json     # and print it
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = BASE / "reports" / "PRODUCER_BREADTH.json"
INTEL = BASE / "data" / "intelligence"
HYP = BASE / "data" / "hypotheses"
REGISTRY_DB = ROOT / "data" / "alpha_registry.sqlite"
HOURLY_CYCLE = BASE / "research" / "hourly_cycle.py"
HOURLY_DISCOVERY = BASE / "research" / "hourly_discovery.py"
DAILY_CYCLE = BASE / "research" / "daily_cycle.py"
AUTO_LEGS = BASE / "data" / "auto_legs.json"
RESEARCH = BASE / "research"

UNMEASURED = "UNMEASURED"
SESSIONS = ("all", "asia", "london", "ny")
LADDER = ("M1", "M5", "M15", "M30", "H1", "H4", "D1")
#: Seat files read per pass, newest first, and the byte ceiling across them. The intelligence
#: tree is ~3 GB and the build box has 8 GB; a reader that loads it whole is the defect
#: `CLAUDE.md` names ("anything that hard-codes a budget off the 96 GB figure will thrash").
MAX_SEAT_BYTES_PER_FILE = 32 * 1024 * 1024
MAX_SEAT_BYTES_TOTAL = 384 * 1024 * 1024
MAX_ARTIFACT_BYTES = 48 * 1024 * 1024

#: WHAT CAPS EACH PRODUCER'S BREADTH, read from its code on 2026-09-30, and what was done.
#: `status`: WIDENED (this branch lifted an artificial cap), WIRED (was on no clock), LEFT_FULL
#: (already at the breadth its data allows), LEFT_UNTESTABLE (its family cannot be built by the
#: sealed gauntlet, so widening would mint more zero-signal cells), LEFT_BANNED (it mints the
#: permanently banned `discovered`), LEFT_BY_DESIGN (the bound is the mechanism, not a slice),
#: UNBLOCKED (was LEFT_UNTESTABLE; the re-signed gauntlet now builds its family -- its cap is
#: the next thing to lift, and the row says so until that lands).
#: `module` is a STEM on purpose: a `research/<x>.py` literal here reads to the component
#: registry's reach walk as this file INVOKING that organ, and would hand it a false clock.
INVENTORY: dict[str, dict[str, Any]] = {
    "breadth_sweep": {
        "module": "breadth_sweep", "seats": [], "report": "BREADTH_SWEEP.json",
        "cap": ("every hypothesis-lane symbol with bars x every chart on disk x 4 sessions; "
                "READY grids for peer/factor/COT/tape/macro families on fixed pair and factor "
                "lists; MAX_NEW_PER_RUN 40,000 taken alphabetically; minted lead_lag, "
                "execution_state, triangle and event_reaction cells the sealed gauntlet builds "
                "with ZERO signals, and relative_value/macro_conditional/... on charts their "
                "family declares inexpressible"),
        "status": "WIDENED",
        "change": ("mints only cells the sealed gauntlet can build (gauntlet_buildability + "
                   "timeframe_refusal), set-aside counted by name; the 40k cap now takes the "
                   "least-judged (symbol, family) first instead of the alphabet; writes "
                   "reports/BREADTH_SWEEP.json. Fixed peer pairs left: relative_value is the most "
                   "attacked cluster (1,596 cells, 0 certificates)"),
    },
    "qd_frontier": {
        "module": "qd_frontier", "seats": ["qd_frontier"],
        "cap": "PROPOSAL_SYMBOLS=3 taken as the FIRST three of each asset class, every pass",
        "status": "WIDENED",
        "change": ("a rotating window of 3 over the whole class, least-judged first, one window "
                   "further per proposal and per hour; the per-pass count is unchanged"),
    },
    "htf_anchor_proposer": {
        "module": "htf_anchor_proposer", "seats": ["video_anchor_exit"],
        "cap": "on NO clock (III.16); charts H1/H4/D1 only; symbols walked by name",
        "status": "WIRED",
        "change": ("hourly leg `htf_anchor`; M15/M30 minted wherever that chart's bars exist; "
                   "symbols walked least-judged first; the 1,200-row rotating slice is unchanged"),
    },
    "empty_cluster_forcer": {
        "module": "empty_cluster_forcer", "seats": ["breadth"],
        "cap": ("on NO clock (III.16); a fixed 12-name PREFERRED tuple; called clusters owned by "
                "untestable families PROPOSER_OWNED"),
        "status": "WIRED",
        "change": ("hourly leg `empty_cluster_forcer --donate`; a rotating least-judged window "
                   "over the whole lane; a cluster whose every family is unbuildable by the "
                   "sealed gauntlet is BLOCKED_BY_SEALED_GAUNTLET with the remedy named, and "
                   "only buildable families are minted"),
    },
    "cross_asset_graph": {
        "module": "cross_asset_graph", "seats": ["cross_asset_graph"],
        "cap": "book_symbols()[:12] (alphabetical prefix of the live book)",
        "status": "UNBLOCKED",
        "change": ("Sealed pass 2 (76895fedc, 2026-10-01) added the build_cell lead_lag branch, "
                   "so its cells now load their driver (0 -> 3,670 signals on GBPUSD<-EURUSD). "
                   "The book_symbols()[:12] cap is NOT yet lifted: that is the next build."),
    },
    "asia_transmission": {
        "module": "asia_transmission", "seats": ["asia_transmission"],
        "cap": "on no hourly clock; lead_lag only",
        "status": "UNBLOCKED",
        "change": ("lead_lag is buildable since 76895fedc (see cross_asset_graph); wiring it "
                   "onto an hourly clock is the next build"),
    },
    "event_surprise": {
        "module": "event_surprise", "seats": ["event_surprise"],
        "cap": "MAX_DONATIONS=10, MAX_SOURCES_PER_PASS=16; event_reaction only",
        "status": "UNBLOCKED",
        "change": ("Sealed pass 2 (76895fedc) made the event_reaction branch pass "
                   "events_for_symbol(events, sym) with symbol=sym, so its cells carry signals. "
                   "MAX_DONATIONS=10 is NOT yet lifted: that is the next build."),
    },
    "event_response_atlas": {
        "module": "event_response_atlas", "seats": ["event_response_atlas"],
        "cap": "event_reaction only", "status": "UNBLOCKED",
        "change": "as event_surprise: the re-signed event_reaction branch (76895fedc) feeds the "
                  "right shape; widening is the next build",
    },
    "edge_search": {
        "module": "edge_search", "artifact": "edge_search_results.json",
        "cap": "family `discovered` only", "status": "LEFT_BANNED",
        "change": "NOT fed: `discovered` is PERMANENTLY banned and the gauntlet discards its cells",
    },
    "backfill_coverage": {
        "module": "backfill_coverage", "artifact": "coverage_search_results.json",
        "cap": "PER_CLASS=3 prefix; family `discovered` only; on no clock", "status": "LEFT_BANNED",
        "change": "NOT fed or wired: every row it writes is the banned `discovered` family",
    },
    "anomaly_factory": {
        "module": "anomaly_factory", "seats": ["anomaly_factory", "anomalies"],
        "cap": "family `discovered`", "status": "LEFT_BANNED",
        "change": "NOT fed: the banned family",
    },
    "orthogonal_sweep": {
        "module": "orthogonal_sweep", "artifact": "orthogonal_candidates.json",
        "cap": ("every (symbol, chart) with bars, yield-interleaved by class and chart; "
                "timeframe_refusal already honoured"),
        "status": "LEFT_FULL", "change": "none needed: sweeps every pair and refuses by name",
    },
    "moat_miner": {
        "module": "moat_miner", "artifact": "moat_candidates.json",
        "cap": "symbols with >= 30 days of recorded tick tape (the desk's own moat)",
        "status": "LEFT_FULL", "change": "bounded by the tape it owns, not by a slice",
    },
    "session_structure_miner": {
        "module": "session_structure_miner", "seats": ["session_structure"],
        "cap": "every registry instrument's own derived session; RR x wait sweep",
        "status": "LEFT_FULL", "change": "none needed",
    },
    "descendants": {
        "module": "descendants", "seats": ["descendants"],
        "cap": "MAX_PER_ROOT=4, MAX_NEIGHBOURS=3 around each survivor; chart ladder M5..D1",
        "status": "LEFT_BY_DESIGN",
        "change": "the bound is one axis-step from a survivor; it inherits survivors' breadth",
    },
    "trajectory_evolution": {
        "module": "trajectory_evolution", "seats": ["trajectory_evolution"],
        "cap": "evolves failed trajectories at their failing step", "status": "LEFT_BY_DESIGN",
        "change": "breadth is inherited from the verdict ledger it evolves",
    },
    "graveyard_resurrection": {
        "module": "graveyard_resurrection", "seats": ["graveyard_resurrection"],
        "cap": "MAX_CANDIDATES=60, MAX_FAMILY_SHARE=0.5", "status": "LEFT_BY_DESIGN",
        "change": "a per-pass bound over the graveyard with a family-share floor on diversity",
    },
    "alpha_recombination": {
        "module": "alpha_recombination", "seats": ["alpha_recombination"],
        "cap": "MAX_COMBINATIONS=40, MAX_GENES=3 over live/certified genes",
        "status": "LEFT_BY_DESIGN", "change": "recombines what already survived",
    },
    "axis_proposer": {
        "module": "axis_proposer", "seats": ["axis_registry"],
        "cap": "MAX_HARVEST=4 per source", "status": "LEFT_BY_DESIGN",
        "change": "the per-source bound is its multiplicity budget; sources rotate",
    },
    "pack_cells": {
        "module": "pack_cells", "seats": [],
        "cap": "SIGNALS_PER_PACK_PER_PASS=6; targets named by the pack", "status": "LEFT_FULL",
        "change": "cursor-rotated over packs already",
    },
    "timeframe_fanout": {
        "module": "timeframe_fanout", "seats": [],
        "cap": "PARENTS_PER_LANE_PER_PASS=40, every chart of the ladder", "status": "LEFT_FULL",
        "change": "rotates parents; already fans every chart",
    },
    "mass_screen": {
        "module": "mass_screen", "seats": [],
        "cap": ("every hypothesis-lane symbol once per UTC day; five fixed grammars over a fixed "
                "feature set; forwards only BH survivors"),
        "status": "LEFT_BY_DESIGN",
        "change": "the screen's FDR is its multiplicity budget; its width is charged in full",
    },
    "unknown_unknown": {
        "module": "unknown_unknown", "seats": [],
        "cap": ("every hypothesis-lane symbol once per UTC day; a daily-rotating sample of the "
                "expression grammars; donates only novel BH survivors"),
        "status": "NEW",
        "change": ("2026-09-30: open-ended expression search (typed grammar + GP), novelty "
                   "against the named features, full screened width charged"),
    },
    "producer_swarm": {
        "module": "producer_swarm", "seats": [],
        "cap": ("thousands of individual producers, one per (family x class x chart x session x "
                "transform); hourly ceiling shared across the lap; measured one by one in "
                "`swarm` below"),
        "status": "NEW",
        "change": ("2026-09-30: registry-driven swarm, buildable cells only, least-judged first, "
                   "holes first; every producer measured individually"),
    },
    "style_premia_sweep": {
        "module": "style_premia_sweep", "seats": ["style_premia"],
        "cap": "H1 only (declared in FAMILY_TIMEFRAMES)", "status": "LEFT_BY_DESIGN",
        "change": "the family's windows are inline hourly bar counts; H1 is its only honest chart",
    },
}


# ------------------------------------------------------------------ small readers
def _read(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _text(p: Path) -> str:
    try:
        return p.read_text("utf-8")
    except OSError:
        return ""


def _parse_ts(raw: Any) -> datetime | None:
    if not raw:
        return None
    try:
        ts = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


_STAMP = re.compile(r"(20\d{6})[_T]?(\d{2})?(\d{2})?")


def _file_time(p: Path) -> datetime | None:
    """A donation file's own time: the stamp in its name, else its mtime."""
    m = _STAMP.search(p.name)
    if m:
        day, hh, mm = m.group(1), m.group(2) or "00", m.group(3) or "00"
        try:
            return datetime.strptime(f"{day}{hh}{mm}", "%Y%m%d%H%M").replace(tzinfo=UTC)
        except ValueError:
            pass
    try:
        return datetime.fromtimestamp(p.stat().st_mtime, tz=UTC)
    except OSError:
        return None


# ------------------------------------------------------------------ the producer set
def discovered_producers() -> dict[str, dict[str, Any]]:
    """Every research module that donates through `proposer_common.donate` or writes a seat,
    with the seat name its own SOURCE/SEAT constant declares -- DERIVED, so a proposer that lands
    tomorrow is measured tomorrow. The INVENTORY rows win where both name a producer."""
    out: dict[str, dict[str, Any]] = {}
    const = re.compile(r'^(?:SOURCE|SEAT)\s*(?::\s*str)?\s*=\s*"([A-Za-z0-9_]+)"', re.M)
    for path in sorted(RESEARCH.glob("*.py")):
        src = _text(path)
        if "donate(" not in src or path.stem in ("proposer_common", "producer_breadth"):
            continue
        seats = sorted(set(const.findall(src)))
        out[path.stem] = {"module": path.stem, "seats": seats,
                          "cap": UNMEASURED, "status": "NOT_INVENTORIED",
                          "change": "not inventoried by hand; measured below"}
    for name, row in INVENTORY.items():
        out[name] = {**out.get(name, {}), **row}
    return out


def clocks_for(module: str, name: str, sources: dict[str, Any],
               auto_organs: list[str]) -> list[str]:
    """The clocks that run `module`: an hourly-cycle leg, the VPS discovery roster, the daily
    cycle, or an auto-clocked organ. Read from each clock's own source text."""
    stem = Path(module).stem
    found: list[str] = []
    hc = sources.get("hourly_cycle", "")
    # The leg is the name `_producer` is called with for this script -- the one spelling the
    # cycle, the ledger and the rotation all share. A module the cycle imports in-process has no
    # such call and is named by its stem.
    legs = re.findall(r'_producer\(\s*"([a-z0-9_]+)",\s*"research/' + re.escape(stem) + r'\.py"',
                      hc)
    if legs:
        found.extend(f"hourly_cycle:{leg}" for leg in dict.fromkeys(legs))
    elif re.search(rf'_costed\("({re.escape(name)}|{re.escape(stem)})"', hc):
        found.append(f"hourly_cycle:{name}")
    elif re.search(rf'\b(import|from)\s+(research\.)?{re.escape(stem)}\b', hc):
        found.append(f"hourly_cycle:{stem} (in-process)")
    if re.search(rf'^\s*"{re.escape(stem)}"\s*:', sources.get("hourly_discovery", ""), re.M):
        found.append("hourly_discovery (VPS timer quant-hourly-discovery)")
    if f'"{stem}"' in sources.get("daily_cycle", ""):
        found.append("daily_cycle")
    if any(o.endswith(f"/{stem}.py") or o.endswith(f"{stem}.py") for o in auto_organs):
        found.append("auto_legs")
    # A box task or VPS unit runs its organs through a runner script; the script naming the
    # module is the clock's evidence (e.g. ops/run_frontier_audit.cmd, installed as a box task).
    for runner, text in (sources.get("_runners") or {}).items():
        if f"{stem}.py" in text:
            found.append(f"runner:{runner}")
    return found


def runner_scripts() -> dict[str, str]:
    """Every runner script a box task or VPS unit invokes, by name -> text."""
    out: dict[str, str] = {}
    for root, pats in ((ROOT / "ops", ("*.sh", "*.cmd", "*.service")),
                       (BASE / "scripts", ("*.ps1", "*.cmd"))):
        for pat in pats:
            for p in sorted(root.glob(pat)):
                out[p.name] = _text(p)
    return out


# ------------------------------------------------------------------ measurement
def _row_facts(r: dict[str, Any]) -> tuple[list[str], str, str, str, dict[str, Any]]:
    params = r.get("params") if isinstance(r.get("params"), dict) else {}
    syms = r.get("symbols") if isinstance(r.get("symbols"), list) else None
    if not syms:
        s = r.get("symbol") or r.get("sym")
        syms = [s] if s else []
    tf = str(params.get("timeframe") or r.get("timeframe") or r.get("chart") or "H1").upper()
    sess = str(params.get("session") or r.get("session") or "all").lower()
    fam = str(r.get("family") or "")
    return [str(s) for s in syms if s], tf, sess, fam, params


class Window:
    """What one producer's cells spanned inside one window."""

    def __init__(self) -> None:
        self.symbols: set[str] = set()
        self.charts: Counter[str] = Counter()
        self.sessions: Counter[str] = Counter()
        self.families: Counter[str] = Counter()

    def add(self, syms: list[str], tf: str, sess: str, fam: str, n: int) -> None:
        self.symbols.update(syms)
        self.charts[tf] += n
        self.sessions[sess] += n
        if fam:
            self.families[fam] += n


class Tally:
    """Per-producer counts inside the 24h and 7d windows."""

    def __init__(self) -> None:
        self.n24 = 0
        self.n7 = 0
        self.symbols: set[str] = set()
        self.charts: Counter[str] = Counter()
        self.sessions: Counter[str] = Counter()
        self.families: Counter[str] = Counter()
        self.buildable = 0
        self.last: datetime | None = None
        self.verdicts: Counter[str] = Counter()
        #: the 24h window's breadth, beside the 7d fields above (which ARE the 7d window)
        self.w24 = Window()

    def add(self, at: datetime | None, now: datetime, syms: list[str], tf: str, sess: str,
            fam: str, params: dict[str, Any] | None, n: int = 1,
            n24: int | None = None) -> None:
        """Count `n` cells stamped `at`. `n24` overrides the 24h share when the caller already
        knows it (a registry group spans many stamps); otherwise it follows `at`."""
        if at is None or at < now - timedelta(days=7):
            return
        self.n7 += n
        if n24 is not None:
            self.n24 += n24
            in24 = n24
        else:
            in24 = n if at >= now - timedelta(hours=24) else 0
            self.n24 += in24
        if in24:
            self.w24.add(syms, tf, sess, fam, in24)
        self.symbols.update(syms)
        self.charts[tf] += n
        self.sessions[sess] += n
        if fam:
            self.families[fam] += n
        verdict = _verdict(fam, params, tf)
        self.verdicts[verdict] += n
        if verdict == "BUILDABLE":
            self.buildable += n
        if self.last is None or at > self.last:
            self.last = at


_VERDICT_CACHE: dict[tuple[str, str, str], str] = {}


def _verdict(fam: str, params: dict[str, Any] | None, tf: str) -> str:
    """The sealed gauntlet's verdict on a cell. `params=None` means the source does not carry
    them (a registry group): the family and the chart are judged, the parameters are not."""
    try:
        from mt5desk.families_orthogonal import timeframe_refusal

        from research.gauntlet_buildability import (
            BUILDABLE,
            TIMEFRAME_REFUSED,
            cell_verdict,
            family_verdict,
        )
    except Exception:
        return UNMEASURED
    need = "?" if params is None else "|".join(sorted(params))
    key = (fam, tf, need)
    if key not in _VERDICT_CACHE:
        if params is None:
            v = family_verdict(fam)[0]
            if v == BUILDABLE and timeframe_refusal(fam, tf):
                v = TIMEFRAME_REFUSED
        else:
            p = dict(params)
            p["timeframe"] = tf
            v = cell_verdict(fam, p)[0]
        _VERDICT_CACHE[key] = v
    return _VERDICT_CACHE[key]


def from_registry(generators: dict[str, str], now: datetime,
                  db: Path | None = None) -> tuple[dict[str, Tally], str]:
    """Registry rows of the last 7 days, credited to the producer that caused them."""
    db = db if db is not None else REGISTRY_DB
    out: dict[str, Tally] = {}
    if not db.exists():
        return out, f"{UNMEASURED}: no registry at {db}"
    cut = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S")
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=10)
    except sqlite3.Error as exc:
        return out, f"{UNMEASURED}: registry unopenable ({type(exc).__name__})"
    try:
        cols = {r[1] for r in con.execute("pragma table_info(research_candidates)")}
        chart = "c.chart" if "chart" in cols else "''"
        sess = "c.session" if "session" in cols else "''"
        gen_c = "c.generator" if "generator" in cols else "''"
        has_disc = bool(con.execute("select 1 from sqlite_master where type='table' and "
                                    "name='discoveries'").fetchone())
        if has_disc and "discovery_id" in cols:
            gen = f"lower(coalesce(nullif(d.generator,''), nullif({gen_c},''), ''))"
            src = "research_candidates c left join discoveries d on d.discovery_id=c.discovery_id"
        else:
            gen = f"lower(coalesce({gen_c}, ''))"
            src = "research_candidates c"
        q = (f"select {gen}, coalesce(c.family,''), coalesce(c.symbol,''), "  # noqa: S608
             f"coalesce({chart},''), coalesce({sess},''), "
             f"max(replace(substr(c.created_at,1,19),' ','T')), count(*), "
             f"sum(case when replace(substr(c.created_at,1,19),' ','T') >= ? then 1 else 0 end) "
             f"from {src} where replace(substr(c.created_at,1,19),' ','T') >= ? "
             f"group by 1,2,3,4,5")
        cut24 = (now - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S")
        for g, fam, sym, ch, se, last, n, n24 in con.execute(q, (cut24, cut)):
            name = generators.get(str(g))
            if not name:
                continue
            t = out.setdefault(name, Tally())
            t.add(_parse_ts(last), now, [str(sym)] if sym else [], str(ch or "H1").upper(),
                  str(se or "all").lower(), str(fam), None, n=int(n or 0), n24=int(n24 or 0))
    except sqlite3.Error as exc:
        return out, f"{UNMEASURED}: registry query failed ({type(exc).__name__}: {exc})"
    finally:
        con.close()
    return out, f"registry {db.name}: {sum(t.n7 for t in out.values())} cell(s) in 7d"


def _rows_of(doc: Any) -> list[dict[str, Any]]:
    if isinstance(doc, list):
        return [r for r in doc if isinstance(r, dict)]
    if isinstance(doc, dict):
        for k in ("discoveries", "hypotheses", "rows", "cells", "candidates"):
            v = doc.get(k)
            if isinstance(v, list):
                return [r for r in v if isinstance(r, dict)]
    return []


def from_seats(seats: list[str], now: datetime, budget: dict[str, int]) -> tuple[Tally, str]:
    """A producer's seat files of the last 7 days, newest first, under the shared byte budget."""
    t = Tally()
    files: list[tuple[datetime, Path]] = []
    for seat in seats:
        d = INTEL / seat
        if not d.is_dir():
            continue
        for p in d.glob("*.json"):
            at = _file_time(p)
            if at is not None and at >= now - timedelta(days=7):
                files.append((at, p))
    if not files:
        return t, f"{UNMEASURED}: no seat file in 7d under {', '.join(seats) or '(no seat)'}"
    files.sort(key=lambda x: x[0], reverse=True)
    skipped = 0
    for at, p in files:
        try:
            size = p.stat().st_size
        except OSError:
            continue
        if size > MAX_SEAT_BYTES_PER_FILE or budget["left"] - size < 0:
            skipped += 1
            continue
        budget["left"] -= size
        doc = _read(p)
        gen = _parse_ts(doc.get("generated_at")) if isinstance(doc, dict) else None
        for r in _rows_of(doc):
            syms, tf, sess, fam, params = _row_facts(r)
            t.add(gen or at, now, syms, tf, sess, fam, params)
    why = f"{len(files) - skipped} seat file(s) in 7d"
    if skipped:
        why += f"; {skipped} over the byte budget left UNMEASURED"
    return t, why


def from_artifact(name: str, now: datetime) -> tuple[Tally, str]:
    """A merge SOURCES artifact (data/hypotheses/<name>) or a producer report (reports/<name>)."""
    t = Tally()
    for p in (HYP / name, BASE / "reports" / name):
        if not p.exists():
            continue
        if p.stat().st_size > MAX_ARTIFACT_BYTES:
            return t, f"{UNMEASURED}: {name} over {MAX_ARTIFACT_BYTES >> 20} MB"
        doc = _read(p, {})
        at = _parse_ts((doc or {}).get("generated_at") if isinstance(doc, dict) else None) \
            or _file_time(p)
        if isinstance(doc, dict) and "cells_built" in doc:           # breadth_sweep's report
            n = int(doc.get("cells_merged") or 0)
            fams = doc.get("families") or {}
            t.symbols.update(str(s) for s in doc.get("symbols") or [])
            t.charts.update({str(k): int(v) for k, v in (doc.get("charts") or {}).items()})
            t.sessions.update({str(k): int(v) for k, v in (doc.get("sessions") or {}).items()})
            t.families.update({str(k): int(v) for k, v in fams.items()})
            if at and at >= now - timedelta(days=7):
                t.n7 += n
                t.n24 += n if at >= now - timedelta(hours=24) else 0
                if at >= now - timedelta(hours=24) and n:
                    t.w24.symbols.update(t.symbols)
                    t.w24.charts.update(t.charts)
                    t.w24.sessions.update(t.sessions)
                    t.w24.families.update(t.families)
                built = int(doc.get("cells_built") or 0)
                t.buildable += built
                t.verdicts["BUILDABLE"] += built
                t.verdicts["SET_ASIDE_UNTESTABLE"] += int(doc.get("set_aside_cells") or 0)
                t.last = at
            return t, f"{p.name} (cells merged this pass; breadth = cells built)"
        for r in _rows_of(doc):
            syms, tf, sess, fam, params = _row_facts(r)
            t.add(at, now, syms, tf, sess, fam, params)
        return t, f"{p.name}"
    return t, f"{UNMEASURED}: {name} absent"


# ------------------------------------------------------------------ reach
def reachable(families: list[str], lane: list[str]) -> dict[str, Any]:
    """What a producer of `families` could reach: the whole lane, every chart those families
    declare, every session, and the families themselves when buildable."""
    try:
        from mt5desk.families_orthogonal import timeframe_domain
        charts = sorted({tf for f in families for tf in timeframe_domain(f)} or set(LADDER),
                        key=LADDER.index)
    except Exception:
        charts = list(LADDER)
    return {"symbols": len(lane), "charts": charts, "sessions": list(SESSIONS)}


def _cluster(fam: str) -> str:
    try:
        from libs.research.alpha_clusters import classify_family
        return str(classify_family(fam))
    except Exception:
        return UNMEASURED


#: THE FLAG THRESHOLDS the daily CRO duty reads. NARROW: under this share of the lane's symbols,
#: or under NARROW_MIN_CLASSES asset classes when the lane holds at least that many. UNTESTABLE:
#: under this share of the producer's cells buildable by the SEALED gauntlet.
NARROW_SYMBOL_SHARE = 0.25
NARROW_MIN_CLASSES = 3
UNTESTABLE_BELOW = 0.90
SWARM_VISITS = BASE / "reports" / "swarm" / "producer_swarm_visits.jsonl"
SWARM_GENERATOR = "producer_swarm"


def _swarm_registry() -> dict[str, Any]:
    try:
        from research.producer_swarm import load_registry
        return load_registry()
    except BaseException:
        return {}


def class_map(symbols: set[str] | list[str], reg: dict[str, Any]) -> dict[str, str]:
    """symbol -> asset class, by the swarm registry's own class table (one taxonomy desk-wide)."""
    try:
        from research.producer_swarm import swarm_class
    except Exception:
        return {}
    out: dict[str, str] = {}
    for sym in symbols:
        k = swarm_class(str(sym), reg) if reg else None
        out[str(sym)] = k or "unclassified"
    return out


def _share(n: int, of: int) -> float | str:
    return round(n / of, 4) if of else UNMEASURED


def breadth_of(symbols: set[str], charts: Counter[str], sessions: Counter[str],
               families: Counter[str], *, lane_n: int, lane_classes: set[str],
               reach_charts: list[str], n_families: int, n_clusters: int,
               classes: dict[str, str]) -> dict[str, Any]:
    """Counts, and shares of what the producer's lane makes possible, for one window."""
    cls = {classes.get(s, "unclassified") for s in symbols} - {"unclassified"}
    clusters = {_cluster(f) for f in families} - {UNMEASURED, "UNCLASSIFIED"}
    ch = {c for c, n in charts.items() if n}
    se = {x for x, n in sessions.items() if n}
    return {"symbols": len(symbols), "symbol_share": _share(len(symbols), lane_n),
            "asset_classes": len(cls), "asset_class_share": _share(len(cls & lane_classes),
                                                                   len(lane_classes)),
            "charts": len(ch), "chart_share": _share(len(ch & set(reach_charts)),
                                                     len(reach_charts)),
            "sessions": len(se), "session_share": _share(len(se & set(SESSIONS)), len(SESSIONS)),
            "families": len(families), "family_share": _share(len(families), n_families),
            "clusters": len(clusters), "cluster_share": _share(len(clusters), n_clusters)}


def flags_for(*, scheduled: bool, clocks: list[str], cells_24h: Any, cells_7d: Any,
              b24: dict[str, Any], b7: dict[str, Any], buildable_share: Any, lane_n: int,
              lane_classes_n: int, measured_from: str = "",
              idle_why: str | None = None) -> tuple[list[str], dict[str, str]]:
    """IDLE / NARROW / UNTESTABLE / UNMEASURED, each with its reason. UNMEASURED is never 0."""
    flags: list[str] = []
    why: dict[str, str] = {}
    if not scheduled:
        flags.append("IDLE")
        why["IDLE"] = "on no clock (III.16): no hourly leg, timer, daily cycle or runner runs it"
    elif cells_24h == 0:
        flags.append("IDLE")
        why["IDLE"] = (f"scheduled ({', '.join(clocks[:3])}) and minted 0 cells in 24h"
                       + (f": {idle_why}" if idle_why else ""))
    if not isinstance(cells_24h, int):
        flags.append("UNMEASURED")
        why["UNMEASURED"] = measured_from or "no source measures this producer"
    window, b = (("24h", b24) if isinstance(cells_24h, int) and cells_24h > 0 else
                 ("7d", b7) if isinstance(cells_7d, int) and cells_7d > 0 else (None, None))
    if b is not None:
        reasons = []
        share = b.get("symbol_share")
        if isinstance(share, float) and share < NARROW_SYMBOL_SHARE:
            reasons.append(f"{b['symbols']} of {lane_n} lane symbols ({share:.0%}) in {window}, "
                           f"under {NARROW_SYMBOL_SHARE:.0%}")
        need = min(NARROW_MIN_CLASSES, lane_classes_n)
        if b.get("asset_classes", 0) < need:
            reasons.append(f"{b.get('asset_classes', 0)} asset class(es) in {window} where the "
                           f"lane allows {lane_classes_n} (floor {need})")
        if reasons:
            flags.append("NARROW")
            why["NARROW"] = "; ".join(reasons)
    if isinstance(buildable_share, float) and buildable_share < UNTESTABLE_BELOW:
        flags.append("UNTESTABLE")
        why["UNTESTABLE"] = (f"{buildable_share:.0%} of its 7d cells are buildable by the sealed "
                             f"gauntlet, under {UNTESTABLE_BELOW:.0%}")
    return flags, why


def _swarm_registry_counts(now: datetime, db: Path | None) -> tuple[dict[str, dict[str, Any]],
                                                                     str]:
    """{producer id: {n7, n24, sym7, sym24}} from the registry's swarm rows (source_id = id)."""
    db = db if db is not None else REGISTRY_DB
    if not db.exists():
        return {}, f"{UNMEASURED}: no registry at {db}"
    cut7 = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S")
    cut24 = (now - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S")
    out: dict[str, dict[str, Any]] = {}
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=10)
    except sqlite3.Error as exc:
        return {}, f"{UNMEASURED}: registry unopenable ({type(exc).__name__})"
    try:
        cols = {r[1] for r in con.execute("pragma table_info(research_candidates)")}
        if not {"generator", "source_id"} <= cols:
            return {}, f"{UNMEASURED}: registry has no generator/source_id columns"
        ts = "replace(substr(created_at,1,19),' ','T')"
        q = (f"select source_id, symbol, count(*), sum(case when {ts} >= ? then 1 else 0 end) "  # noqa: S608
             f"from research_candidates where generator = ? and {ts} >= ? "
             f"group by source_id, symbol")
        for pid, sym, n, n24 in con.execute(q, (cut24, SWARM_GENERATOR, cut7)):
            r = out.setdefault(str(pid), {"n7": 0, "n24": 0, "sym7": set(), "sym24": set()})
            r["n7"] += int(n or 0)
            r["n24"] += int(n24 or 0)
            r["sym7"].add(str(sym))
            if n24:
                r["sym24"].add(str(sym))
    except sqlite3.Error as exc:
        return {}, f"{UNMEASURED}: registry query failed ({type(exc).__name__}: {exc})"
    finally:
        con.close()
    return out, f"registry {db.name}: {sum(r['n7'] for r in out.values())} swarm cell(s) in 7d"


def _swarm_visits(now: datetime, path: Path | None = None) -> dict[str, tuple[str, str]]:
    """{producer id: (last visit time, outcome)} over the last 7 days of the visits ledger."""
    p = path or SWARM_VISITS
    floor = (now - timedelta(days=7)).isoformat(timespec="seconds")
    out: dict[str, tuple[str, str]] = {}
    try:
        with p.open(encoding="utf-8") as fh:
            for ln in fh:
                try:
                    r = json.loads(ln)
                except ValueError:
                    continue
                t = str(r.get("t") or "")
                if t >= floor and t >= out.get(str(r.get("p")), ("", ""))[0]:
                    out[str(r.get("p"))] = (t, str(r.get("o") or ""))
    except OSError:
        return {}
    return out


def swarm_section(now: datetime, db: Path | None, *, scheduled: bool, clocks: list[str],
                  n_families: int, n_clusters: int,
                  datasets: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Every swarm producer measured individually, and rolled up by family and by culture."""
    try:
        from research.producer_swarm import culture_fields, instantiate, non_western_share
        roster, census = (instantiate(datasets=datasets) if datasets is not None
                          else instantiate())
    except BaseException as exc:          # SystemExit from an unreadable registry included
        return {"status": UNMEASURED,
                "why": f"swarm roster unbuildable ({type(exc).__name__}: {exc})",
                "producers": {}, "by_family": {}}
    counts, why = _swarm_registry_counts(now, db)
    measured = not why.startswith(UNMEASURED)
    visits = _swarm_visits(now)
    rows: dict[str, Any] = {}
    fam: dict[str, dict[str, Any]] = {}
    cult: dict[str, dict[str, Any]] = {}
    for p in roster:
        c = counts.get(p.pid, {"n7": 0, "n24": 0, "sym7": set(), "sym24": set()})
        n24 = int(c["n24"]) if measured else UNMEASURED
        n7 = int(c["n7"]) if measured else UNMEASURED
        lane_n = len(p.lane)
        params = dict(p.base)
        v = _verdict(p.family, {**params, "symbol": p.lane[0]} if p.lane else params, p.chart)
        bshare: Any = (1.0 if v == "BUILDABLE" else 0.0) if isinstance(n7, int) and n7 else \
            UNMEASURED
        last = visits.get(p.pid)
        idle_why = None
        if isinstance(n24, int) and n24 == 0:
            idle_why = (f"last visit {last[0]} said {last[1]}" if last else
                        "not visited in 7d (its lap position has not come round)")
        if measured:
            b24 = {"symbols": len(c["sym24"]), "symbol_share": _share(len(c["sym24"]), lane_n),
                   "asset_classes": 1 if c["sym24"] else 0}
            b7 = {"symbols": len(c["sym7"]), "symbol_share": _share(len(c["sym7"]), lane_n),
                  "asset_classes": 1 if c["sym7"] else 0}
        else:
            b24 = b7 = {"symbols": UNMEASURED, "symbol_share": UNMEASURED}
        flags, reasons = flags_for(scheduled=scheduled, clocks=clocks, cells_24h=n24,
                                   cells_7d=n7, b24=b24, b7=b7, buildable_share=bshare,
                                   lane_n=lane_n, lane_classes_n=1, measured_from=why,
                                   idle_why=idle_why)
        rows[p.pid] = {"family": p.family, "class": p.klass, "chart": p.chart,
                       "session": p.session, "transform": p.transform, "cluster": p.cluster,
                       **{k: v for k, v in culture_fields(p).items()
                          if k in ("source_culture", "participant_structure", "crowding_prior",
                                   "swarm_culture")},
                       "dataset": p.dataset or None,
                       "lane_symbols": lane_n, "cells_24h": n24, "cells_7d": n7,
                       "symbols_24h": b24["symbols"], "symbols_7d": b7["symbols"],
                       "symbol_share_24h": b24["symbol_share"],
                       "symbol_share_7d": b7["symbol_share"],
                       "buildable_share": bshare, "verdict": v,
                       "last_visit": last[0] if last else None,
                       "last_outcome": last[1] if last else None,
                       "flags": flags, "reasons": reasons}
        f = fam.setdefault(p.family, {"producers": 0, "active": 0, "idle": 0, "narrow": 0,
                                      "untestable": 0, "unmeasured": 0, "cells_24h": 0,
                                      "cells_7d": 0, "classes_24h": set(), "charts_24h": set(),
                                      "sessions_24h": set(), "cluster": p.cluster})
        f["producers"] += 1
        f["active"] += int(isinstance(n24, int) and n24 > 0)
        for flag in ("IDLE", "NARROW", "UNTESTABLE", "UNMEASURED"):
            f[flag.lower()] += int(flag in flags)
        if isinstance(n24, int) and n24:
            f["cells_24h"] += n24
            f["classes_24h"].add(p.klass)
            f["charts_24h"].add(p.chart)
            f["sessions_24h"].add(p.session)
        if isinstance(n7, int):
            f["cells_7d"] += n7
        cu = cult.setdefault(p.culture, {"producers": 0, "active": 0, "cells_24h": 0,
                                         "cells_7d": 0})
        cu["producers"] += 1
        cu["active"] += int(isinstance(n24, int) and n24 > 0)
        cu["cells_24h"] += n24 if isinstance(n24, int) else 0
        cu["cells_7d"] += n7 if isinstance(n7, int) else 0
    for f in fam.values():
        for k in ("classes_24h", "charts_24h", "sessions_24h"):
            f[k] = sorted(f[k])
    c24 = sum(v["cells_24h"] for v in cult.values())
    return {"status": "MEASURED" if measured else UNMEASURED, "registry": why,
            "roster": census, "producers": rows, "by_family": dict(sorted(fam.items())),
            "by_culture": dict(sorted(cult.items())),
            "non_global_share_of_cells_24h": (
                round(1 - cult.get("GLOBAL", {}).get("cells_24h", 0) / c24, 4) if c24 and measured
                else UNMEASURED),
            "non_western_share_of_cells_24h": (
                non_western_share({k: v["cells_24h"] for k, v in cult.items()})
                if c24 and measured else UNMEASURED)}


def build(now: datetime | None = None, db: Path | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    t0 = time.monotonic()
    producers = discovered_producers()
    sources: dict[str, Any] = {"hourly_cycle": _text(HOURLY_CYCLE),
                               "hourly_discovery": _text(HOURLY_DISCOVERY),
                               "daily_cycle": _text(DAILY_CYCLE),
                               "_runners": runner_scripts()}
    auto = _read(AUTO_LEGS, {}) or {}
    auto_organs = [str(e.get("organ") or "") for e in (auto.get("legs") or [])
                   if isinstance(e, dict)]
    try:
        from research.breadth_rotation import hypothesis_symbols
        lane = hypothesis_symbols()
    except Exception:
        lane = []
    sreg = _swarm_registry()
    generators: dict[str, str] = {}
    for name, row in producers.items():
        for seat in [name, *(row.get("seats") or [])]:
            generators.setdefault(str(seat).lower(), name)
    reg, reg_why = from_registry(generators, now, db)
    budget = {"left": MAX_SEAT_BYTES_TOTAL}
    try:
        from research.gauntlet_buildability import census
        fam_census = census()
    except Exception:
        fam_census = {}
    buildable_fams = [f for f, v in fam_census.items() if v.get("verdict") == "BUILDABLE"]
    reachable_clusters = sorted({_cluster(f) for f in buildable_fams}
                                - {UNMEASURED, "UNCLASSIFIED"})
    rows: dict[str, Any] = {}
    fed: Counter[str] = Counter()
    fed24: Counter[str] = Counter()
    fed_by: dict[str, set[str]] = {}
    tallies: dict[str, Tally] = {}
    for name in sorted(producers):
        row = producers[name]
        tally, measured = reg.get(name), "registry"
        if tally is None or tally.n7 == 0:
            if row.get("report"):
                tally, measured = from_artifact(str(row["report"]), now)
            elif row.get("artifact"):
                tally, measured = from_artifact(str(row["artifact"]), now)
            elif row.get("seats"):
                tally, measured = from_seats(list(row["seats"]), now, budget)
            else:
                tally, measured = Tally(), f"{UNMEASURED}: no seat, report or registry rows"
        tallies[name] = tally
        clocks = clocks_for(str(row.get("module") or ""), name, sources, auto_organs)
        fams = sorted(tally.families)
        clusters: Counter[str] = Counter()
        for fam, n in tally.families.items():
            clusters[_cluster(fam)] += n
        if tally.buildable:
            for window, cnt, sink in (("7d", tally.families, fed), ("24h", tally.w24.families,
                                                                     fed24)):
                for fam, n in cnt.items():
                    c = _cluster(fam)
                    try:
                        from research.gauntlet_buildability import BUILDABLE, family_verdict
                        ok = family_verdict(fam)[0] == BUILDABLE
                    except Exception:
                        ok = True
                    if ok and n:
                        sink[c] += n
                        if window == "7d":
                            fed_by.setdefault(c, set()).add(name)
        measured_ok = tally.n7 > 0 or not str(measured).startswith(UNMEASURED)
        cells_24h: Any = tally.n24 if measured_ok else UNMEASURED
        cells_7d: Any = tally.n7 if measured_ok else UNMEASURED
        reach = reachable(fams, lane)
        cmap = class_map(set(lane) | tally.symbols, sreg)
        lane_classes = {cmap.get(s, "unclassified") for s in lane} - {"unclassified"}
        kw = {"lane_n": len(lane), "lane_classes": lane_classes,
              "reach_charts": list(reach["charts"]), "n_families": len(buildable_fams),
              "n_clusters": len(reachable_clusters), "classes": cmap}
        if measured_ok:
            b24 = breadth_of(tally.w24.symbols, tally.w24.charts, tally.w24.sessions,
                             tally.w24.families, **kw)
            b7 = breadth_of(tally.symbols, tally.charts, tally.sessions, tally.families, **kw)
        else:
            b24 = b7 = {"status": UNMEASURED, "why": str(measured)}
        bshare: Any = round(tally.buildable / tally.n7, 4) if tally.n7 else UNMEASURED
        flags, reasons = flags_for(scheduled=bool(clocks), clocks=clocks, cells_24h=cells_24h,
                                   cells_7d=cells_7d, b24=b24, b7=b7, buildable_share=bshare,
                                   lane_n=len(lane), lane_classes_n=len(lane_classes),
                                   measured_from=str(measured))
        rows[name] = {
            "module": f"desks/mt5/research/{row.get('module')}.py",
            "seats": row.get("seats") or [],
            "scheduled": bool(clocks), "clocks": clocks,
            "last_run": tally.last.isoformat(timespec="seconds") if tally.last else None,
            "cells_24h": cells_24h,
            "cells_7d": cells_7d,
            "measured_from": measured,
            "breadth": {"24h": b24, "7d": b7},
            "flags": flags, "flag_reasons": reasons,
            "covered": {"symbols": len(tally.symbols), "charts": dict(tally.charts),
                        "sessions": dict(tally.sessions), "families": dict(tally.families)},
            "reachable": reach,
            "symbol_coverage": (round(len(tally.symbols & set(lane)) / len(lane), 4)
                                if lane and tally.symbols else (0.0 if lane else UNMEASURED)),
            "buildable_share": bshare,
            "verdicts": dict(tally.verdicts),
            "clusters_fed": dict(clusters),
            "cap": row.get("cap"), "status": row.get("status"), "change": row.get("change"),
        }
    try:
        from libs.research.alpha_clusters import CLUSTERS
        every = [c.key for c in CLUSTERS]
    except Exception:
        every = []
    by_cluster: dict[str, dict[str, list[str]]] = {}
    for fam, v in fam_census.items():
        c = _cluster(fam)
        by_cluster.setdefault(c, {"buildable": [], "unbuildable": []})
        by_cluster[c]["buildable" if v["verdict"] == "BUILDABLE" else "unbuildable"].append(fam)
    swarm_row = rows.get("producer_swarm") or {}
    ds_list, datasets = dataset_section(now, db)
    swarm = swarm_section(now, db, scheduled=bool(swarm_row.get("scheduled")),
                          clocks=list(swarm_row.get("clocks") or []),
                          n_families=len(buildable_fams), n_clusters=len(reachable_clusters),
                          datasets=ds_list)
    for pid, r in (swarm.get("producers") or {}).items():
        if isinstance(r.get("cells_7d"), int) and r["cells_7d"] and r["verdict"] == "BUILDABLE":
            fed[r["cluster"]] += r["cells_7d"]
            fed_by.setdefault(r["cluster"], set()).add(f"producer_swarm:{pid.split('.')[0]}")
        if isinstance(r.get("cells_24h"), int) and r["cells_24h"] and \
                r["verdict"] == "BUILDABLE":
            fed24[r["cluster"]] += r["cells_24h"]
    unfed: list[dict[str, Any]] = []
    for c in every:
        if fed.get(c):
            continue
        b = by_cluster.get(c, {"buildable": [], "unbuildable": []})
        why = ("NO_FAMILY: no registered family classifies here" if not (b["buildable"]
                                                                        or b["unbuildable"])
               else "BLOCKED_BY_SEALED_GAUNTLET: every family here is unbuildable by the "
                    "sealed build_cell" if not b["buildable"]
               else "UNMINTED: a buildable family exists and no measured producer minted it "
                    "in 7d")
        unfed.append({"cluster": c, "why": why, "buildable_families": b["buildable"],
                      "unbuildable_families": b["unbuildable"]})
    holes = coverage_holes(tallies, swarm, lane, sreg, reachable_clusters, fed24)
    swarm["culture_gap"] = culture_gap_section(
        now, db, sorted(str(k) for k in (sreg.get("cultures") or {})
                        if not str(k).startswith("_")))
    measured = [r for r in rows.values() if isinstance(r["cells_7d"], int)]
    totals = {
        "producers": len(rows),
        "scheduled": sum(1 for r in rows.values() if r["scheduled"]),
        "unscheduled": sorted(n for n, r in rows.items() if not r["scheduled"]),
        "measured": len(measured),
        "unmeasured": sorted(n for n, r in rows.items() if not isinstance(r["cells_7d"], int)),
        "cells_24h": sum(int(r["cells_24h"]) for r in measured),
        "cells_7d": sum(int(r["cells_7d"]) for r in measured),
        "lane_symbols": len(lane) if lane else UNMEASURED,
        "clusters_fed_buildable_7d": dict(sorted(fed.items())),
        "clusters_fed_buildable_24h": dict(sorted(fed24.items())),
        "clusters_fed_by": {c: sorted(v) for c, v in sorted(fed_by.items())},
        "empty_clusters_unfed": unfed,
        "coverage_holes": holes,
        "family_buildability": fam_census,
    }
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "rule": ("per producer: on a clock or not, last production, cells in 24h and 7d, the "
                 "symbols/asset classes/charts/sessions/families/clusters those cells span in "
                 "24h and 7d as counts and as shares of what its lane makes possible, the share "
                 "the SEALED gauntlet can build, and flags IDLE / NARROW / UNTESTABLE / "
                 "UNMEASURED each with its reason. A producer no source can see is UNMEASURED, "
                 "never zero (L1.28a). Swarm producers are measured one by one under `swarm`."),
        "thresholds": {"narrow_symbol_share": NARROW_SYMBOL_SHARE,
                       "narrow_min_asset_classes": NARROW_MIN_CLASSES,
                       "untestable_buildable_share_below": UNTESTABLE_BELOW},
        "headline": headline(rows, swarm, unfed, holes, datasets),
        "registry": reg_why,
        "seat_bytes_read": MAX_SEAT_BYTES_TOTAL - budget["left"],
        "wall_s": round(time.monotonic() - t0, 2),
        "totals": totals,
        "producers": rows,
        "swarm": swarm,
        "datasets": datasets,
    }


def coverage_holes(tallies: dict[str, Tally], swarm: dict[str, Any], lane: list[str],
                   sreg: dict[str, Any], reachable_clusters: list[str],
                   fed24: Counter[str]) -> dict[str, Any]:
    """What NO producer reached in 24h, by axis -- the swarm's hole list for the next hour."""
    syms: set[str] = set()
    charts: set[str] = set()
    sessions: set[str] = set()
    for t in tallies.values():
        syms |= t.w24.symbols
        charts |= {c for c, n in t.w24.charts.items() if n}
        sessions |= {x for x, n in t.w24.sessions.items() if n}
    swarm_classes: set[str] = set()
    for r in (swarm.get("producers") or {}).values():
        if isinstance(r.get("cells_24h"), int) and r["cells_24h"]:
            charts.add(r["chart"])
            sessions.add(r["session"])
            swarm_classes.add(r["class"])
    measured = [n for n, t in tallies.items() if t.n7 or t.n24]
    swarm_measured = swarm.get("status") == "MEASURED"
    if not measured and not swarm_measured:
        return {"window": "24h", "status": UNMEASURED,
                "why": "no producer is measured, so no axis can be called unfed",
                "clusters": [], "asset_classes": [], "charts": [], "sessions": []}
    classes_all = class_map(set(lane), sreg)
    lane_classes = set(classes_all.values()) - {"unclassified"}
    roster = (swarm.get("roster") or {}).get("classes") or {}
    lane_classes |= {k for k, n in roster.items() if n}
    hit_classes = (set(class_map(syms, sreg).values()) | swarm_classes) - {"unclassified"}
    on_disk = sorted({p.name.rsplit("_", 1)[1][: -len(".parquet")]
                      for p in (BASE / "data" / "universe").glob("*_*.parquet")}
                     & set(LADDER), key=LADDER.index)
    return {"window": "24h", "status": "MEASURED",
            "measured_hand_written_producers": len(measured),
            "swarm_measured": swarm_measured,
            "clusters": sorted(c for c in reachable_clusters if not fed24.get(c)),
            "asset_classes": sorted(lane_classes - hit_classes),
            "charts": [c for c in on_disk if c not in charts],
            "sessions": [s for s in SESSIONS if s not in sessions],
            "rule": ("an axis value the lane makes possible (a cluster with a buildable family, "
                     "a class with members, a chart with bars on disk, a session) that NO "
                     "producer minted a cell on in 24h; producer_swarm visits the producers "
                     "aimed at these first")}


#: The culture-gap producers (branch claude/culture-gap-producers): read and counted when that
#: organ is on this tree, reported as a gap when it is not -- never duplicated here.
CULTURE_GAP_MODULE = BASE / "research" / "culture_gap_cells.py"
CULTURE_GAP_REPORT = BASE / "reports" / "CULTURE_GAP_CELLS.json"
CULTURE_GAP_GENERATOR = "culture_gap_cells"


def culture_gap_section(now: datetime, db: Path | None,
                        declared: list[str]) -> dict[str, Any]:
    """The cultures the swarm cannot reach and whether a culture-gap producer reaches them.

    Counts the registry's cells in 7d by the jurisdiction of their `source_culture` column (every
    producer, not only the swarm) and the culture-gap organ's own cells by generator, for the
    swarm registry's declared cultures. Absent organ: `present` False and every declared culture
    with no cell is listed as the gap it is."""
    present = CULTURE_GAP_MODULE.exists()
    out: dict[str, Any] = {"producer": str(CULTURE_GAP_MODULE.relative_to(ROOT)),
                           "present": present,
                           "report": (str(CULTURE_GAP_REPORT.relative_to(ROOT))
                                      if CULTURE_GAP_REPORT.exists() else None)}
    db = db if db is not None else REGISTRY_DB
    by_j: Counter[str] = Counter()
    gap_cells: Counter[str] = Counter()
    if not db.exists():
        out["registry"] = f"{UNMEASURED}: no registry at {db}"
    else:
        cut7 = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S")
        ts = "replace(substr(created_at,1,19),' ','T')"
        try:
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=10)
            try:
                cols = {r[1] for r in con.execute("pragma table_info(research_candidates)")}
                if "source_culture" not in cols:
                    out["registry"] = (f"{UNMEASURED}: registry has no source_culture column "
                                       "(the culture door has not run on it)")
                else:
                    gen = "generator" if "generator" in cols else "''"
                    q = (f"select source_culture, {gen}, count(*) from "  # noqa: S608
                         f"research_candidates where {ts} >= ? group by 1, 2")
                    for sc, g, n in con.execute(q, (cut7,)):
                        j = str(sc or "").split("/", 1)[0].upper()
                        by_j[j] += int(n or 0)
                        if str(g or "") == CULTURE_GAP_GENERATOR:
                            gap_cells[j] += int(n or 0)
                    out["registry"] = f"registry {db.name}: 7d cells by source_culture"
            finally:
                con.close()
        except sqlite3.Error as exc:
            out["registry"] = f"{UNMEASURED}: registry query failed ({type(exc).__name__})"
    measured = not str(out.get("registry", "")).startswith(UNMEASURED)
    out["cells_7d_by_culture"] = ({t: by_j.get(t, 0) for t in declared} if measured
                                  else UNMEASURED)
    out["culture_gap_cells_7d"] = ({t: gap_cells.get(t, 0) for t in declared} if measured
                                   else UNMEASURED)
    out["culture_gap_producer_cultures"] = (sorted(t for t in declared if gap_cells.get(t))
                                            if measured else UNMEASURED)
    return out


def dataset_section(now: datetime, db: Path | None) -> tuple[list[dict[str, Any]] | None,
                                                             dict[str, Any]]:
    """(the discovered datasets, the census) -- UNMEASURED with its reason, never an empty 0."""
    try:
        from research.dataset_census import census, discover
        found = discover()
        return found, census(now, db, datasets=found)
    except Exception as exc:
        return None, {"status": UNMEASURED,
                      "why": f"dataset census failed ({type(exc).__name__}: {exc})",
                      "datasets": {}, "unfed": [], "totals": {}}


def headline(rows: dict[str, Any], swarm: dict[str, Any], unfed: list[dict[str, Any]],
             holes: dict[str, Any], datasets: dict[str, Any] | None = None) -> dict[str, Any]:
    """The first thing the daily CRO duty reads."""
    srows = swarm.get("producers") or {}

    def tally(rs: Any) -> dict[str, int]:
        rs = list(rs)
        return {"producers": len(rs),
                "active": sum(1 for r in rs if isinstance(r.get("cells_24h"), int)
                              and r["cells_24h"] > 0),
                "idle": sum(1 for r in rs if "IDLE" in r.get("flags", [])),
                "narrow": sum(1 for r in rs if "NARROW" in r.get("flags", [])),
                "untestable": sum(1 for r in rs if "UNTESTABLE" in r.get("flags", [])),
                "unmeasured": sum(1 for r in rs if "UNMEASURED" in r.get("flags", []))}
    legacy = tally(rows.values())
    sw = tally(srows.values())
    total = {k: legacy[k] + sw[k] for k in legacy}
    gaps: list[str] = []
    for u in unfed:
        if str(u.get("why", "")).startswith(("UNMINTED", "BLOCKED")):
            gaps.append(f"cluster {u['cluster']} unfed in 7d: {u['why'].split(':')[0]}")
    label = {"clusters": "cluster", "asset_classes": "asset class", "charts": "chart",
             "sessions": "session"}
    for axis in ("clusters", "asset_classes", "charts", "sessions"):
        for v in holes.get(axis) or []:
            gaps.append(f"{label[axis]} {v}: no measured producer minted on it in 24h")
    idle_sched = sorted((n for n, r in rows.items() if r["scheduled"]
                         and "IDLE" in r["flags"]))
    gaps += [f"producer {n} IDLE while scheduled: {rows[n]['flag_reasons'].get('IDLE', '')}"
             for n in idle_sched[:10]]
    narrow = sorted((n for n, r in rows.items() if "NARROW" in r["flags"]))
    gaps += [f"producer {n} NARROW: {rows[n]['flag_reasons'].get('NARROW', '')}"
             for n in narrow[:10]]
    fam_idle = sorted(((f, v["idle"]) for f, v in (swarm.get("by_family") or {}).items()
                       if v.get("idle")), key=lambda x: -x[1])
    gaps += [f"swarm family {f}: {k} producer(s) idle in 24h" for f, k in fam_idle[:5]]
    ds = datasets or {}
    dt = ds.get("totals") or {}
    rows_ds = ds.get("datasets") or {}
    # A DATASET THAT FEEDS NO PRODUCER IS A DEFECT TO WIRE FIRST (principal, 2026-09-30), so it
    # leads the list the CRO duty reads rather than being cut off at its tail.
    gaps = [f"dataset {k} feeds no producer: {rows_ds.get(k, {}).get('why', '')}"
            for k in (ds.get("unfed_conditionable") or [])[:5]] + gaps
    roster = swarm.get("roster") or {}
    cov = roster.get("cultures") or {}
    gap = swarm.get("culture_gap") or {}
    d18 = ds.get("d18") or {}
    return {
            # THE BREADTH FIGURE: distinct mechanisms (the swarm's family code paths). The swarm's
            # producer count is those code paths crossed with its axes -- permutations, kept as
            # the secondary field it is.
            "breadth_figure": "distinct_mechanisms",
            "distinct_mechanisms": roster.get("distinct_mechanisms", UNMEASURED),
            "permutations": roster.get("permutations", UNMEASURED),
            "producers_total": total["producers"], "active": total["active"],
            "idle": total["idle"], "narrow": total["narrow"],
            "untestable": total["untestable"], "unmeasured": total["unmeasured"],
            "hand_written": legacy, "swarm": sw,
            "datasets": ({"total": dt.get("datasets"), "feeding": dt.get("feeding"),
                          "unfed": dt.get("unfed"), "unmeasured": dt.get("unmeasured"),
                          "conditionable": dt.get("conditionable"),
                          "unfed_conditionable": dt.get("unfed_conditionable")}
                         if dt else {"status": ds.get("status", UNMEASURED),
                                     "why": ds.get("why")}),
            # CRO D18 (the dataset-exploitation fence) reads these: every dataset without a
            # fetched series file is UNFED.
            "datasets_d18": ({k: d18.get(k) for k in (
                "datasets", "fetched", "fetched_unmeasured", "series_file_present", "unfed",
                "unfed_no_fetched_series", "unfed_not_producing", "unmeasured")}
                if d18 else {"status": UNMEASURED, "why": "no dataset census"}),
            "culture": {"swarm_by_culture_producers": {
                            k: v.get("producers") for k, v in
                            (swarm.get("by_culture") or {}).items()},
                        "non_global_share_of_swarm_cells_24h":
                            swarm.get("non_global_share_of_cells_24h", UNMEASURED),
                        # GLOBAL (the CFTC included) is never non-Western
                        "non_western_share_of_swarm_cells_24h":
                            swarm.get("non_western_share_of_cells_24h", UNMEASURED),
                        "non_western_share_of_swarm_producers":
                            roster.get("non_western_share", UNMEASURED),
                        "cultures_declared": cov.get("declared", UNMEASURED),
                        "cultures_with_real_producers": cov.get("with_producers", UNMEASURED),
                        "cultures_with_home_instruments":
                            cov.get("with_home_instruments", UNMEASURED),
                        "xauusd_only_lanes": cov.get("xauusd_only_lanes", UNMEASURED),
                        "cultures_without_producers": cov.get("without_producers", UNMEASURED),
                        "culture_gap_producer_present": gap.get("present", UNMEASURED),
                        "culture_gap_producer_cultures":
                            gap.get("culture_gap_producer_cultures", UNMEASURED)},
            "top_gaps": gaps[:25]}


def write(doc: dict[str, Any], out: Path | None = None) -> Path:
    path = out or OUT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    tmp.replace(path)
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    doc = build()
    path = write(doc)
    t = doc["totals"]
    if a.json:
        print(json.dumps(doc, indent=1, default=str))
    else:
        h = doc["headline"]
        print(f"producer_breadth: {h.get('distinct_mechanisms')} distinct mechanism(s) (the "
              f"breadth figure); {h['producers_total']} producer permutation(s) "
              f"({h['swarm']['producers']} swarm), {h['active']} active, {h['idle']} idle, "
              f"{h['narrow']} narrow, "
              f"{h['untestable']} untestable, {h['unmeasured']} unmeasured")
        print(f"  hand-written: {t['producers']} producer(s), {t['scheduled']} on a clock, "
              f"{t['measured']} measured; cells 24h {t['cells_24h']}, 7d {t['cells_7d']}; "
              f"unfed clusters {[u['cluster'] for u in t['empty_clusters_unfed']]}")
        if t["unscheduled"]:
            print(f"  ON NO CLOCK: {', '.join(t['unscheduled'][:30])}")
        dh = (doc.get("headline") or {}).get("datasets") or {}
        print(f"  datasets: {dh.get('total')} on disk, {dh.get('feeding')} feeding a producer, "
              f"{dh.get('unfed')} unfed ({dh.get('unfed_conditionable')} conditionable, wired "
              f"first by producer_swarm), {dh.get('unmeasured')} unmeasured")
        d18 = (doc.get("headline") or {}).get("datasets_d18") or {}
        print(f"  D18: {d18.get('fetched')} fetched, {d18.get('series_file_present')} with a "
              f"series file, {d18.get('unfed')} UNFED ({d18.get('unfed_no_fetched_series')} "
              f"without a fetched series)")
        print(f"  -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
