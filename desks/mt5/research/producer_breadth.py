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
def breadth_unit(r: dict[str, Any]) -> str:
    """The MECHANISM a donated row belongs to -- the unit breadth counts ONCE.

    A producer that sweeps one mechanism over many symbols and parameter points (specialist_cell's
    wmr_fix_reversal: 352 of its 370 floor-clearing cells, 2026-09-30) mints ONE independent bet,
    not 352. The row's own declared unit wins (`breadth_unit`, or its `family_grid` id); then the
    specialist mechanism in its evidence; then its family. Cells are still counted as cells."""
    unit = r.get("breadth_unit")
    grid = r.get("family_grid")
    if not unit and isinstance(grid, dict):
        unit = grid.get("id")
    ev = r.get("evidence") if isinstance(r.get("evidence"), dict) else {}
    if not unit and ev.get("specialist_mechanism"):
        unit = f"{ev.get('asset_class_desk') or ''}/{ev['specialist_mechanism']}".lstrip("/")
    return str(unit or r.get("family") or "")


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


class Tally:
    """Per-producer counts inside the 24h and 7d windows."""

    def __init__(self) -> None:
        self.n24 = 0
        self.n7 = 0
        self.symbols: set[str] = set()
        self.charts: Counter[str] = Counter()
        self.sessions: Counter[str] = Counter()
        self.families: Counter[str] = Counter()
        #: cells per breadth UNIT (a mechanism): `len(units)` is the producer's k-style breadth
        self.units: Counter[str] = Counter()
        self.buildable = 0
        self.last: datetime | None = None
        self.verdicts: Counter[str] = Counter()

    def add(self, at: datetime | None, now: datetime, syms: list[str], tf: str, sess: str,
            fam: str, params: dict[str, Any] | None, n: int = 1,
            n24: int | None = None, unit: str | None = None) -> None:
        """Count `n` cells stamped `at`. `n24` overrides the 24h share when the caller already
        knows it (a registry group spans many stamps); otherwise it follows `at`."""
        if at is None or at < now - timedelta(days=7):
            return
        self.n7 += n
        if n24 is not None:
            self.n24 += n24
        elif at >= now - timedelta(hours=24):
            self.n24 += n
        self.symbols.update(syms)
        self.charts[tf] += n
        self.sessions[sess] += n
        if fam:
            self.families[fam] += n
        if unit or fam:
            self.units[str(unit or fam)] += n
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
            t.add(gen or at, now, syms, tf, sess, fam, params, unit=breadth_unit(r))
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
            t.units.update({str(k): int(v) for k, v in fams.items()})
            if at and at >= now - timedelta(days=7):
                t.n7 += n
                t.n24 += n if at >= now - timedelta(hours=24) else 0
                built = int(doc.get("cells_built") or 0)
                t.buildable += built
                t.verdicts["BUILDABLE"] += built
                t.verdicts["SET_ASIDE_UNTESTABLE"] += int(doc.get("set_aside_cells") or 0)
                t.last = at
            return t, f"{p.name} (cells merged this pass; breadth = cells built)"
        for r in _rows_of(doc):
            syms, tf, sess, fam, params = _row_facts(r)
            t.add(at, now, syms, tf, sess, fam, params, unit=breadth_unit(r))
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
    generators: dict[str, str] = {}
    for name, row in producers.items():
        for seat in [name, *(row.get("seats") or [])]:
            generators.setdefault(str(seat).lower(), name)
    reg, reg_why = from_registry(generators, now, db)
    budget = {"left": MAX_SEAT_BYTES_TOTAL}
    rows: dict[str, Any] = {}
    fed: Counter[str] = Counter()
    fed_by: dict[str, set[str]] = {}
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
        clocks = clocks_for(str(row.get("module") or ""), name, sources, auto_organs)
        fams = sorted(tally.families)
        clusters: Counter[str] = Counter()
        for fam, n in tally.families.items():
            clusters[_cluster(fam)] += n
        if tally.buildable:
            for fam, n in tally.families.items():
                c = _cluster(fam)
                try:
                    from research.gauntlet_buildability import BUILDABLE, family_verdict
                    ok = family_verdict(fam)[0] == BUILDABLE
                except Exception:
                    ok = True
                if ok and n:
                    fed[c] += n
                    fed_by.setdefault(c, set()).add(name)
        measured_ok = tally.n7 > 0 or not str(measured).startswith(UNMEASURED)
        rows[name] = {
            "module": f"desks/mt5/research/{row.get('module')}.py",
            "seats": row.get("seats") or [],
            "scheduled": bool(clocks), "clocks": clocks,
            "last_run": tally.last.isoformat(timespec="seconds") if tally.last else None,
            "cells_24h": tally.n24 if measured_ok else UNMEASURED,
            "cells_7d": tally.n7 if measured_ok else UNMEASURED,
            # k-style breadth: distinct MECHANISMS minted in 7d. A grid of one mechanism over
            # many symbols and parameter points is one unit here and many cells above.
            "breadth_k": len(tally.units) if measured_ok else UNMEASURED,
            "largest_unit_share": (round(max(tally.units.values()) / sum(tally.units.values()), 4)
                                   if measured_ok and tally.units else UNMEASURED),
            "units": dict(tally.units.most_common()),
            "measured_from": measured,
            "covered": {"symbols": len(tally.symbols), "charts": dict(tally.charts),
                        "sessions": dict(tally.sessions), "families": dict(tally.families)},
            "reachable": reachable(fams, lane),
            "symbol_coverage": (round(len(tally.symbols & set(lane)) / len(lane), 4)
                                if lane and tally.symbols else (0.0 if lane else UNMEASURED)),
            "buildable_share": (round(tally.buildable / tally.n7, 4) if tally.n7 else UNMEASURED),
            "verdicts": dict(tally.verdicts),
            "clusters_fed": dict(clusters),
            "cap": row.get("cap"), "status": row.get("status"), "change": row.get("change"),
        }
    try:
        from libs.research.alpha_clusters import CLUSTERS
        every = [c.key for c in CLUSTERS]
    except Exception:
        every = []
    try:
        from research.gauntlet_buildability import census
        fam_census = census()
    except Exception:
        fam_census = {}
    by_cluster: dict[str, dict[str, list[str]]] = {}
    for fam, v in fam_census.items():
        c = _cluster(fam)
        by_cluster.setdefault(c, {"buildable": [], "unbuildable": []})
        by_cluster[c]["buildable" if v["verdict"] == "BUILDABLE" else "unbuildable"].append(fam)
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
    measured = [r for r in rows.values() if isinstance(r["cells_7d"], int)]
    totals = {
        "producers": len(rows),
        "scheduled": sum(1 for r in rows.values() if r["scheduled"]),
        "unscheduled": sorted(n for n, r in rows.items() if not r["scheduled"]),
        "measured": len(measured),
        "unmeasured": sorted(n for n, r in rows.items() if not isinstance(r["cells_7d"], int)),
        "cells_24h": sum(int(r["cells_24h"]) for r in measured),
        "cells_7d": sum(int(r["cells_7d"]) for r in measured),
        "breadth_k": len({u for r in measured for u in (r.get("units") or {})}),
        "breadth_rule": ("breadth_k counts each mechanism ONCE (a producer's declared "
                         "breadth_unit / family_grid, else the family); cells_24h/7d still count "
                         "every cell, and every cell is still charged to the trial census"),
        "lane_symbols": len(lane) if lane else UNMEASURED,
        "clusters_fed_buildable_7d": dict(sorted(fed.items())),
        "clusters_fed_by": {c: sorted(v) for c, v in sorted(fed_by.items())},
        "empty_clusters_unfed": unfed,
        "family_buildability": fam_census,
    }
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "rule": ("per producer: on a clock or not, last production, cells in 24h and 7d, the "
                 "symbols/charts/sessions/families those cells span against what it could "
                 "reach, the share the SEALED gauntlet can build, and the clusters fed. A "
                 "producer no source can see is UNMEASURED, never zero (L1.28a)."),
        "registry": reg_why,
        "seat_bytes_read": MAX_SEAT_BYTES_TOTAL - budget["left"],
        "wall_s": round(time.monotonic() - t0, 2),
        "totals": totals,
        "producers": rows,
    }


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
        print(f"producer_breadth: {t['producers']} producer(s), {t['scheduled']} on a clock, "
              f"{t['measured']} measured; cells 24h {t['cells_24h']}, 7d {t['cells_7d']}; "
              f"unfed clusters {[u['cluster'] for u in t['empty_clusters_unfed']]}")
        if t["unscheduled"]:
            print(f"  ON NO CLOCK: {', '.join(t['unscheduled'][:30])}")
        print(f"  -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
