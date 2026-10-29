"""EVERY PRODUCER PRODUCES, OR IT IS REPLACED. Names the dead, and names what takes their budget.

THE LAW (principal, 2026-09-15): every single miner, source, seat and proposer must produce. One
that cannot is replaced with an alternative.

WHY THIS IS A DIFFERENT LAW FROM THE TWO NEXT TO IT, because all three sound similar and they
catch different failures:

    check_ground_conversion   a ground must have MACHINERY pointing at the gauntlet.
    check_row_conversion      a mined row must reach a TERMINAL disposition.
    this file                 a producer must have OUTPUT. Machinery that runs, converts, and
                              yields nothing for weeks is not a pipeline, it is a heater.

AND THE THREE VERDICTS ARE NOT THE SAME PROBLEM. Collapsing them is how a desk spends a year
"fixing the miners":

    PRODUCING   output in the window. Nothing to do.
    STARVED     output, but far below its peers. Usually a BUDGET or an input problem, never a
                reason to delete the producer. `alpha_evolution` measured 2026-09-15: it runs,
                it does not crash, and it proposed ONE cell from 72 tests -- because it evolves
                against a book `pf_allocation` reports as 1 funded sleeve. Deleting it would
                have thrown away a working organ for the sin of being fed nothing.
    DEAD        zero output across the whole window. THIS is the one the law is about, and the
                remedy is not another look: it is a named REPLACEMENT that takes the budget.
    UNMEASURED  no artifact records this producer's output at all. A verdict, never a pass, and
                in practice the most common real state of a new organ (L1.28a).

A REPLACEMENT MUST BE NAMED, NOT IMPLIED. "Try something else" is not a remedy; it is the absence
of one. Every producer declared here carries the alternative that inherits its budget when it
dies, so the decision is made once, in advance, by whoever understood the producer -- and not at
3am by whoever happened to notice the zero.

SECOND HALF, ADDED 2026-09-23 -- EVERY PRODUCER OWES CELLS (LAWS 7). The half above asks whether
a SEAT wrote rows. That is donation, not production. The desk's one judge eats CELLS, so the
second half measures, per producer per hour: cells emitted, unique cells after dedup, cells that
reached the judge, and THE ORTHOGONALITY EACH ADDED -- because a hundred copies of one momentum
rule is one cell's worth of breadth and must score as such. The producer set is DERIVED (the
census, which is itself derived from the component registry and the registry's own generators),
never a hand list, so a producer that lands today is judged today.

    python scripts/check_producer_yield.py
    python scripts/check_producer_yield.py --window-days 7
    python scripts/check_producer_yield.py --yield-window-hours 24
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sqlite3
import sys
import time
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
OUT = DESK / "reports" / "PRODUCER_YIELD.json"

#: The census this fence consumes. It is NOT re-derived here: the census already merges
#: `PRODUCER_CENSUS.json` (every seat/miner/organ with a clock), `COMPONENT_REGISTRY.json` (every
#: executable with a ComponentSpec) and every generator the registry has actually seen. Deriving
#: the roster a second time is how two organs come to disagree about who exists.
CENSUS = DESK / "reports" / "PRODUCTIVITY_CENSUS.json"
REGISTRY_DB = ROOT / "data" / "alpha_registry.sqlite"
# Row-level conservation is measured by the compiler fence.  This joins the producer scoreboard
# to that evidence so a producer cannot satisfy "owes cells" by writing 10,000 prose rows and an
# exemption: every evidence-bearing row must itself produce a valid cell or remain visible debt.
ROW_CONVERSION = DESK / "reports" / "ROW_CONVERSION.json"

#: Declared exemptions and named blockers, SHARED with `scripts/check_productivity_census.py` so
#: an organ declares itself once. A row is either a BLOCKER (`why` >= 20 chars + `owner`) or an
#: EXEMPTION (`exempt: true` + `produces` + `consumer`) -- the second is how a genuinely
#: exploratory organ says what it makes instead of cells and who reads it.
BLOCKERS = ROOT / "docs" / "research" / "productivity_blockers.json"

#: The ratchet. Falls only: the owing count may never rise, the throughput bests may never fall.
RATCHET = ROOT / "docs" / "research" / "producer_yield_ratchet.json"

#: A day of registry rows. Shorter than the census's 7-day compute window on purpose: the census
#: asks "has this thing ever paid", this asks "is it paying NOW", and an hourly desk that has
#: emitted nothing for a day is the failure being looked for.
YIELD_WINDOW_HOURS = 24.0

#: Below this, a LEDGER hour is a costed import or an interrupted leg, not a shift of work. Same
#: figure as the sibling fence, for the same reason: a fence that fires on a hundredth of a ledger
#: hour trains its readers to ignore it. It does NOT apply to registry-attributed compute, which
#: is seconds a generator recorded for a pass it actually ran -- there, any positive number is a
#: pass that happened, and holding it to a ledger-sized floor is how this fence went blind on a
#: host whose compute ledger keys on leg names that name no roster producer.
MIN_COMPUTE_HOURS = 0.25

#: How far throughput may fall below its own best before the fence calls it a regression. It is a
#: FLOOR and never a cap -- nothing here throttles a productive organ, and the remedy for a breach
#: is always to make the barren producer produce, never to slow a working one. Half is wide enough
#: to absorb a cycle that ran short and narrow enough that a collapsed lane cannot hide in it.
THROUGHPUT_FLOOR_FRACTION = 0.5

#: Distinct (family|symbol|horizon) cells read per producer for the orthogonality matrix. The
#: breadth measure is a participation ratio of a singular-value spectrum, so it saturates long
#: before this; the cap bounds the SVD on an 8 GB box rather than shaping the answer.
MAX_CELLS_PER_PRODUCER = 600

#: A verdict, never a zero (L1.28a).
UNMEASURED_STR = "UNMEASURED"

#: Output below this share of the median producer's output is STARVED rather than healthy. It is
#: a RATIO and not a count on purpose: an absolute floor would condemn a deliberately narrow
#: producer and excuse a broad one that collapsed.
STARVED_FRACTION = 0.05

#: producer -> the alternative that inherits its budget if it is ever declared DEAD. Declared in
#: advance, by intent, so a dead producer has a decision attached to it rather than a question.
REPLACEMENTS: dict[str, str] = {
    "alpha_evolution": "representation_discovery -- same expression search, driven by measured "
                       "representations rather than by a funded book it does not have",
    "plumbing_miner": "microstructure_miner",
    "transition_alpha": "regime_transition sweep inside external_gauntlet",
    "weak_signal_compiler": "combination lane of external_gauntlet",
    "fund_playbook": "institutional_cards -- the same mechanism claims, declared rather than mined",
    "microstructure_miner": "execution_twin markout study",
    "style_premia_sweep": "cross_sectional family sweep",
    "cross_asset_graph": "asia_transmission -- economically declared chains at the CAUSAL_ROLE bar",
    "anomaly_factory": "external_gauntlet exploration floor",
    "tail_alpha_search": "drawdown_conditional family sweep",
    "survivor_distiller": "survivor_neighbourhood",
    "factor_model_coevolution": "residual_factors",
    "deep_forest_miner": "asia_plane -- the hard-data half, where the number is the observation",
    "asia_plane": "deep_forest_miner -- the practitioner half; each is the other's fallback",
    "asia_transmission": "cross_asset_graph",
    # The eight seats measured DEAD on 2026-09-15. Each gets a named inheritor rather than a
    # question mark: three of them are MQL5 sub-crawlers whose work the surviving MQL5 seats
    # already do, and the rest have a live organ covering the same ground.
    "brain": "deepening_worker -- the same LLM reasoning, on the queue rather than freeform",
    "cohorts": "cohort_independence in libs/research",
    "fxmerge": "fxblue -- the same public MT4/MT5 account statistics, from a live route",
    "mql5_catalog": "mql5_signals -- the catalogue is a crawl of what the signals seat already reads",
    "mql5_prospector": "mql5_survivors -- survivorship-aware and still writing",
    "mql5_reputation": "mql5_survivors -- reputation is one of its phenotypes",
    "plumbing": "plumbing_miner (the proposer), which is the organ this seat fed",
    "scheduled_chatgpt": "deepseek_cycle -- the seat that is actually donating today",
    # THE SIX MEASURED DEAD WITH NO NAMED ALTERNATIVE on 2026-10-13 (PRODUCER_YIELD of 10-12).
    # Each names a live organ on the same ground; the LLM-born ones also name the research-lab
    # role (#332, desks/mt5/research/llm_lab.py) that takes the ground once it lands.
    "expression_factory": "alpha_recombination -- the same expression search over measured "
                          "parents; llm_lab lab H (program_synthesis) once #332 lands",
    "kimi": "deepseek_cycle -- the same deep-forest seat shape on the free chain; kimi itself "
            "now donates per wave on a 1,020 s leg cap",
    "lab_probability": "mathlab -- the stochastic_processes and extreme_value traditions; "
                       "llm_lab lab C (mathematical) once #332 lands",
    "lab_timeseries": "lab_crossasset -- the sibling lab of the same box writer; llm_lab lab G "
                      "(representation) and role R (code_lab) once #332 lands",
    "world_lab": "dislocation_lab -- the macro department's cross-asset shock ground; world_lab "
                 "reads a causal graph frozen since 2026-09-08 (causal_graph leg)",
    "literature": "academic -- academic_miner and seed_miners arxiv_qfin, the same "
                  "papers-with-a-mechanism ground; literature was a one-off 2026-09-16 hand seed",
    # THE SEATS WITH NO WRITER LEFT, measured 2026-10-29 (PRODUCER_YIELD 11:43Z, intel-ship/send
    # history, and a grep of the tree for each seat's writer). Each names the live organ on the
    # same ground; none had a declared successor, which is why they read NONE DECLARED.
    "recombinants": "alpha_recombination -- research/alpha_recombination.py, the box leg, writes "
                    "the alpha_recombination seat; `recombinants` was the retired side_channels "
                    "writer's seat, last shipped from the VPS 2026-10-14",
    "anomalies": "anomaly_factory -- the same anomaly_miner.scan over the desk's bars, deflated "
                 "and donated; `anomalies` was the VPS discovery cycle's raw dump",
    "lab_crossasset": "dislocation_lab -- the cross-asset shock ground; no writer of this seat "
                      "is left in the tree",
    "lab_microstructure": "microstructure_miner -- the H1 spread/tick-volume surfaces, now on the "
                          "box's proposer_rotation; no writer of this seat is left in the tree",
    "mechanism_genome": "alpha_genome -- the mechanism genome is a field on every alpha_genome "
                        "row (alpha_genome.py:150); no writer of this seat is left in the tree",
    "frontier": "global_frontier -- the frontier_supervisor's live seat (scout_roster names both); "
                "this one holds a single 2026-09-12 file from the VPS",
    "firm_mining": "fund_playbook -- the declared institutional mechanism claims; firm_mining was "
                   "a one-off 2026-09-27 hand seed (scripts/max_audit.py)",
}


# ------------------------------------------------ WHY A PRODUCER IS DEAD (2026-10-29, principal)
#
# THE SYMPTOM IS NOT THE CAUSE. PRODUCER_YIELD of 2026-10-29T11:43Z read 91 of 137 producers DEAD
# and 10 UNMEASURED, and 75 of the dead said "replacement: NONE DECLARED" -- which names the
# symptom and leaves the remedy to whoever reads it. Read against the box's own artifacts the
# hundred-odd rows had about six causes, each with a different fix, so every DEAD or UNMEASURED
# row now carries exactly one `cause`, the `cause_detail` that named it and the `cause_evidence`
# it was read from. The vocabulary is fixed; nothing here guesses, and a producer whose evidence
# this host cannot read is UNMEASURED_CAUSE (L1.28a), never the likeliest-looking cause.
#
#   BACKPRESSURE_GATE   its leg stood down on a judge-backlog / admission / memory gate. A
#                       judge-capacity ask, never a reason to loosen trial charging or cut mining.
#   FETCH_FAILURE       its ground refuses it: a recorded wall (robots, 403, anti-bot), a blocked
#                       source, a platform whose last fetch failed and never yielded. These are
#                       person-released and are NEVER bypassed here.
#   KEY_MISSING         it needs a credential this host does not hold (existence only; no key is
#                       ever read, printed or copied).
#   SCHEDULE            no clock on THIS host runs it, its clock lives on another host whose
#                       transport has gone silent, its leg did not run inside the window, or its
#                       leg was killed at its budget before it wrote.
#   UPSTREAM_DEAD       it consumes bars or ticks and BARS_STATE says that input is stale.
#   WRITES_ELSEWHERE    it produces where the seat count does not look. Rescued in place: the row
#                       becomes PRODUCING with `basis` naming where the output was found.
#   RETIRED_SUPERSEDED  no clock here, and REPLACEMENTS names the organ that took its ground.
#   UNMEASURED_CAUSE    clocked here, but nothing this host recorded says which of the above.
CAUSES: tuple[str, ...] = ("BACKPRESSURE_GATE", "FETCH_FAILURE", "KEY_MISSING", "SCHEDULE",
                           "UPSTREAM_DEAD", "WRITES_ELSEWHERE", "RETIRED_SUPERSEDED",
                           "UNMEASURED_CAUSE")
UNMEASURED_CAUSE = "UNMEASURED_CAUSE"
#: Bumped whenever the rule changes what a seat verdict means. 3 = seats followed through each
#: module's SOURCE and declared file aliases, registry cells count as output, and every DEAD or
#: UNMEASURED row carries a cause from CAUSES.
SEAT_RULE = 3

HOURLY_CYCLE = DESK / "research" / "hourly_cycle.py"
HOURLY_DISCOVERY = DESK / "research" / "hourly_discovery.py"
SEED_MINERS = DESK / "side_channels" / "seed_miners.py"
MODULE_ROOTS: tuple[Path, ...] = (DESK / "research", DESK / "side_channels")
COMPUTE_LEDGER = DESK / "data" / "compute_ledger.jsonl"
#: The ledger is append-only and grows without bound on the box; the classifier needs only the
#: window, so it reads the TAIL. 64 MB holds weeks of hourly rows at ~600 bytes a row.
LEDGER_TAIL_BYTES = 64 * 1024 * 1024
ALT_DATA_YIELD = DESK / "reports" / "ALT_DATA_YIELD.json"
BLOCKED_SOURCES = DESK / "data" / "intelligence" / "blocked_sources.json"
BARS_STATE = DESK / "data" / "BARS_STATE.json"
#: The VPS -> box transport for the VPS's seats (desks/mt5/scripts/intel_ship_adopt.ps1 fetches
#: it into this dedicated ref on every MT5-IntelShip run).
SHIP_REF = "refs/remotes/intel-ship/send"
#: Any other clone sees the same branch under the ordinary remote-tracking name.
SHIP_REF_FALLBACK = "refs/remotes/origin/intel-ship/send"
#: An input older than this is stale for UPSTREAM_DEAD. Bars refresh hourly and the tape every few
#: minutes; a day without either is not a slow feed, it is a dead one.
UPSTREAM_STALE_H = 24.0

#: A producer whose output lands in ANOTHER seat's directory under its own file prefix. The
#: seat-name aliases (asia_plane -> asia, ...) are handled in `audit`; this is the finer case,
#: where the seat is shared and only the file name says who wrote it. deep_forest_miner writes
#: data/intelligence/world/discoveries_deepforest_*.json (deep_forest_miner.WORLD, line ~1594), so
#: counting a `deep_forest` seat that does not exist left it UNMEASURED beside 2,490 rows a week.
SEAT_FILE_ALIASES: dict[str, tuple[str, str]] = {
    "deep_forest_miner": ("world", "discoveries_deepforest_"),
}

#: Seats written by a MULTI-SOURCE leg, keyed by the leg that actually runs the writer. A roster
#: that merely LISTS a seat (scout_roster, producer_breadth) is not its clock, and the productivity
#: census's `clock` column credits exactly those -- `amarkets` read `hourly_cycle:scout_roster`
#: while nothing on the box had fetched it since 2026-09-12. tests/test_producer_yield_fence.py
#: pins `seed_miners` against seed_miners.MINERS and `external_miners` against run_all_miners.
LEG_SEATS: dict[str, tuple[str, ...]] = {
    "seed_miners": (
        "global_frontier", "regional_survivors", "mql5_survivors", "mql5_signals",
        "myfxbook_outlook", "darwinex", "tradingview_scripts", "fxblue", "collective2",
        "quantconnect", "forexpeacearmy", "ff_calendar_vintage", "forextsd_cdx", "quant_se",
        "arxiv_qfin", "bis_speeches", "broker_swaps", "github_topics", "propfirm_boards",
        # regional_survivor_hunters, called by mine_regional_survivors, writes one seat per
        # platform plus the FBS tape (regional_survivor_hunters.py:931 and :954)
        "amarkets", "duplitrade", "equiti_copy", "fbs_tape", "followme_cn", "hfm_pamm",
        "instaforex_copy", "litefinance", "minfx_jp", "mylivefx_br", "octa_masters",
        "readitrades_africa", "roboforex_copyfx", "share4you", "trading_latam"),
    "external_miners": (
        "youtube", "github", "mql5", "tradingview", "quantconnect", "reddit", "central_banks",
        "forexfactory", "cot", "sec_edgar", "earnings", "aaii", "fear_greed", "investing",
        "google_trends", "academic", "correlations", "seasonality", "weather", "shipping",
        "china", "korea"),
}

#: Producers that consume the desk's own bars or tape. Declared, because "reads a parquet" is
#: not visible from outside the organ. With BARS_STATE fresh none of these fire, which is the
#: point: the classifier only says UPSTREAM_DEAD when the input it names is actually stale.
UPSTREAM: dict[str, str] = {
    **dict.fromkeys(("plumbing_miner", "transition_alpha", "weak_signal_compiler",
                     "style_premia_sweep", "cross_asset_graph", "anomaly_factory",
                     "tail_alpha_search", "factor_model_coevolution", "alpha_evolution",
                     "expression_factory", "factor_residual"), "bars"),
    "microstructure_miner": "bars",
}

#: Producers that need a credential, and where the credential lives. EXISTENCE ONLY: the file is
#: stat'ed and the variable tested for being set; neither is ever opened, read or printed.
KEYED: dict[str, tuple[str, str]] = {
    "scheduled_chatgpt": ("data/secrets/llm_panel.json", "OPENROUTER_API_KEY"),
    "kimi": ("data/secrets/llm_panel.json", "OPENROUTER_API_KEY"),
    "deepseek": ("data/secrets/llm_panel.json", "OPENROUTER_API_KEY"),
}

#: Seats whose NAME collides with a leg that does not write them. `frontier` is both a dead seat
#: (one 2026-09-12 VPS file) and the hourly leg running frontier_miner, which writes reports, not
#: that seat; without this the leg's clean runs would be read as the seat's clock.
LEG_NAME_COLLISIONS: frozenset[str] = frozenset({"frontier"})

#: Clock spellings that name no schedule on THIS host. systemd units and cron lines are the VPS's
#: (the trading box runs neither); an import or a library call is not a clock at all.
_OFF_BOX = (".timer", ".service")
_OFF_BOX_PREFIX = ("quant-", "systemd:", "cron:", "full-pipeline")
_NOT_A_CLOCK = ("invoked:", "import:")


def seat_of(producer: str, roots: tuple[Path, ...] | None = None) -> str | None:
    """The seat a module donates into: its own `SOURCE = "..."` (or `SEAT = "..."`), read from the
    source text so a renamed seat is followed, never imported. None when it declares neither."""
    import re
    for root in roots or MODULE_ROOTS:
        try:
            src = (root / f"{producer}.py").read_text(encoding="utf-8")
        except OSError:
            continue
        m = re.search(r'^(?:SOURCE|SEAT)\s*(?::\s*str\s*)?=\s*["\']([A-Za-z0-9_]+)["\']', src,
                      re.M)
        return m.group(1) if m else None
    return None


def seats_written_by(stem: str, roots: tuple[Path, ...] | None = None) -> set[str]:
    """Every seat a module names as its own: its `SOURCE`/`SEAT` constant and any module-level
    output constant pointing into `intelligence/<seat>`. Read, never imported. This is how
    `mathlab` is found to be math_lab.py's seat and `factor_residual` factor_residual_engine.py's."""
    import re
    for root in roots or MODULE_ROOTS:
        try:
            src = (root / f"{stem}.py").read_text(encoding="utf-8")
        except OSError:
            continue
        out = {m.group(1) for m in re.finditer(
            r'^(?:SOURCE|SEAT)\s*(?::\s*str\s*)?=\s*["\']([A-Za-z0-9_]+)["\']', src, re.M)}
        # An OUTPUT path is a module-level constant named for output (INTEL, _OUT, SEAT_DIR, ...).
        # An inline `intelligence / "x"` is as often a READ (tier_s reads alpha_evolution's seat),
        # and a reader is not a clock for the seat it reads.
        out |= {m.group(1) for m in re.finditer(
            r'^_?[A-Z_]*(?:INTEL|OUT|SEAT_DIR|OUT_DIR)\s*=\s*[^\n]*["\']intelligence["\']\s*/\s*'
            r'["\']([A-Za-z0-9_]+)["\']', src, re.M)}
        return out
    return set()


def box_legs(src: str | None = None) -> dict[str, set[str]]:
    """producer-or-module -> the hourly_cycle LEG names (the `_costed` names the compute ledger
    keys on) that run it. Read from hourly_cycle's text, never imported.

    Three spellings, because the cycle uses all three:
        _costed("leg", lambda: _producer("name", "research/module.py", ...))
        def fn(): ... return _producer("name", "research/module.py")   +   _costed("leg", fn)
        _costed("leg", fn)  where the leg name IS the producer
    """
    import re
    if src is None:
        try:
            src = HOURLY_CYCLE.read_text(encoding="utf-8")
        except OSError:
            return {}
    out: dict[str, set[str]] = {}

    def _add(key: str, leg: str) -> None:
        out.setdefault(key, set()).add(leg)

    for m in re.finditer(r'_costed\(\s*"([A-Za-z0-9_]+)"', src):
        _add(m.group(1), m.group(1))
    lam = re.compile(r'_costed\(\s*"([A-Za-z0-9_]+)",\s*lambda[^:]*:\s*_producer\(\s*'
                     r'"([A-Za-z0-9_]+)",\s*"[A-Za-z0-9_/]*?([A-Za-z0-9_]+)\.py"', re.S)
    for m in lam.finditer(src):
        _add(m.group(2), m.group(1))
        _add(m.group(3), m.group(1))
    fn_prod: dict[str, tuple[str, str]] = {}
    for m in re.finditer(r'^def ([A-Za-z0-9_]+)\(\)[^\n]*\n(.*?)(?=^def |\Z)', src, re.S | re.M):
        p = re.search(r'_producer\(\s*"([A-Za-z0-9_]+)",\s*"[A-Za-z0-9_/]*?([A-Za-z0-9_]+)\.py"',
                      m.group(2))
        if p:
            fn_prod[m.group(1)] = (p.group(1), p.group(2))
    for m in re.finditer(r'_costed\(\s*"([A-Za-z0-9_]+)",\s*([A-Za-z0-9_]+)\s*\)', src):
        if m.group(2) in fn_prod:
            name, stem = fn_prod[m.group(2)]
            _add(name, m.group(1))
            _add(stem, m.group(1))
    return out


def box_rotation(path: Path | None = None) -> set[str]:
    """hourly_discovery.BOX_ROTATION, read from the module's text (the leg `proposer_rotation`)."""
    import ast
    try:
        tree = ast.parse((path or HOURLY_DISCOVERY).read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return set()
    for node in tree.body:
        tgt = node.target if isinstance(node, ast.AnnAssign) else (
            node.targets[0] if isinstance(node, ast.Assign) and node.targets else None)
        if isinstance(tgt, ast.Name) and tgt.id == "BOX_ROTATION":
            val = getattr(node, "value", None)
            if isinstance(val, (ast.Tuple, ast.List)):
                return {e.value for e in val.elts
                        if isinstance(e, ast.Constant) and isinstance(e.value, str)}
    return set()


def source_walls(path: Path | None = None) -> dict[str, str]:
    """seed_miners.SOURCE_WALLS as {source: verdict}, read from the text (importing seed_miners
    imports every miner). A wall is a recorded refusal -- robots, 403, anti-bot -- and the miner
    re-probes it on its own cadence; it is evidence here, never something this fence lifts."""
    import re
    try:
        s = (path or SEED_MINERS).read_text(encoding="utf-8")
        i = s.index("SOURCE_WALLS")
        j = s.index("\n}\n", i)
    except (OSError, ValueError):
        return {}
    return {m.group(1): m.group(2) for m in re.finditer(
        r'^    "([A-Za-z0-9_]+)": \{\s*\n\s*"verdict": "([A-Z_0-9]+)"', s[i:j], re.M)}


def _ledger_last(window_h: float, path: Path | None = None) -> dict[str, Any]:
    """{"available": bool, "last": {leg: {"at", "outcome"}}} from the compute ledger's tail.

    `available` is False when the ledger is absent or holds no row inside the window: then no
    leg can be convicted of not running, because the silence is the ledger's (L1.28a).
    """
    p = path or COMPUTE_LEDGER
    out: dict[str, Any] = {"available": False, "last": {}, "path": _rel(p)}
    cutoff = (datetime.now(UTC) - timedelta(hours=window_h)).isoformat(timespec="seconds")
    try:
        with open(p, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - LEDGER_TAIL_BYTES))
            blob = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return out
    last: dict[str, dict[str, str]] = {}
    seen_in_window = False
    for line in blob.splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if not isinstance(r, dict):
            continue
        at = str(r.get("at") or r.get("finished_at") or "")
        leg = str(r.get("run") or "")
        if not leg or at < cutoff:
            continue
        seen_in_window = True
        if at >= last.get(leg, {}).get("at", ""):
            last[leg] = {"at": at, "outcome": str(r.get("outcome") or "")[:200]}
    out.update({"available": seen_in_window, "last": last})
    return out


def _ship_state(root: Path | None = None) -> dict[str, Any]:
    """The VPS -> box transport's last commit time, from the local ref. No network: the ref is
    whatever MT5-IntelShip last fetched. UNMEASURED (None) when git or the ref is absent."""
    import subprocess
    for ref in (SHIP_REF, SHIP_REF_FALLBACK):
        try:
            r = subprocess.run(["git", "log", "-1", "--format=%cI", ref, "--"],
                               cwd=str(root or ROOT), capture_output=True, text=True,
                               timeout=20, check=False)
        except (OSError, subprocess.SubprocessError):
            continue
        stamp = (r.stdout or "").strip() if r.returncode == 0 else ""
        if stamp:
            return {"ref": ref, "last_commit": stamp}
    return {"ref": SHIP_REF, "last_commit": None}


def _age_h(stamp: Any) -> float | None:
    try:
        t = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=UTC)
    return (datetime.now(UTC) - t).total_seconds() / 3600.0


def cause_evidence(window_days: float, cells: dict[str, Any] | None = None) -> dict[str, Any]:
    """Everything `cause_of` reads, gathered once per audit. Every reader degrades to empty."""
    alt = _read(ALT_DATA_YIELD, default={})
    plats = ((alt.get("platforms") or {}).get("rows_by_platform") or {}) if isinstance(
        alt, dict) else {}
    blocked = _read(BLOCKED_SOURCES, default={})
    bars = _read(BARS_STATE, default={})
    clocks: dict[str, set[str]] = {}
    for r in ((cells or {}).get("producers") or []):
        if isinstance(r, dict) and r.get("clock"):
            clocks.setdefault(_base(str(r.get("key") or r.get("producer") or "")),
                              set()).add(str(r["clock"]))
    seat_leg: dict[str, set[str]] = {}
    for leg, seats in LEG_SEATS.items():
        for s in seats:
            seat_leg.setdefault(s, set()).add(leg)
    legs = box_legs()
    for p in box_rotation():
        legs.setdefault(p, set()).add("proposer_rotation")
    # REVERSE: the seats each clocked module writes, so a SEAT row (mathlab, factor_residual)
    # finds the leg that runs its writer even though the leg is named after the module.
    for stem, ls in list(legs.items()):
        for seat in seats_written_by(stem):
            if seat != stem:
                seat_leg.setdefault(seat, set()).update(ls)
    return {
        "window_h": window_days * 24.0,
        "legs": legs,
        "seat_legs": seat_leg,
        "clocks": clocks,
        "ledger": _ledger_last(window_days * 24.0),
        "ship": _ship_state(),
        "walls": source_walls(),
        "platforms": plats if isinstance(plats, dict) else {},
        "blocked": ((blocked.get("sources") or {}) if isinstance(blocked, dict) else {}),
        "bars": (bars.get("summary") or {}) if isinstance(bars, dict) else {},
    }


def _base(key: str) -> str:
    """`miner:qd_frontier:explorer` -> `qd_frontier`; `leg:x`, `seat:x`, `daily:x` -> `x`."""
    k = str(key)
    for pre in ("miner:", "seat:", "leg:", "daily:", "fence:"):
        if k.startswith(pre):
            k = k[len(pre):]
            break
    return k.split(":", 1)[0]


def _cause(cause: str, detail: str, evidence: str, **extra: Any) -> dict[str, Any]:
    assert cause in CAUSES, cause
    return {"cause": cause, "cause_detail": detail, "cause_evidence": evidence, **extra}


def cause_of(name: str, seat: str | None, ev: dict[str, Any]) -> dict[str, Any]:
    """One named cause from CAUSES for a DEAD/UNMEASURED producer, with its evidence. Never raises.

    Tested in a fixed order, most binding first: a retired producer needs no clock; a walled
    ground stays dark however often it is clocked; a stale input starves a producer that runs.
    Only then is the CLOCK asked about, and a clock that ran cleanly without writing is named
    UNMEASURED_CAUSE with what it did, rather than dressed as any of the others.
    """
    keys = {name} | ({seat} if seat else set())
    legs = set().union(*(ev["legs"].get(k, set()) for k in keys),
                       *(ev["seat_legs"].get(k, set()) for k in keys))
    clocks = set().union(*(ev["clocks"].get(k, set()) for k in keys))
    off_box = sorted(c for c in clocks if c.endswith(_OFF_BOX) or c.startswith(_OFF_BOX_PREFIX))
    box_tasks = sorted(c for c in clocks if c.startswith("MT5-"))
    rep = REPLACEMENTS.get(name) or (REPLACEMENTS.get(seat) if seat else None)

    if name in LEG_NAME_COLLISIONS:
        legs = set()
    if rep and not legs and not box_tasks:
        return _cause("RETIRED_SUPERSEDED", "REPLACEMENT_DECLARED",
                      "no clock on this host runs it; REPLACEMENTS names its successor",
                      replacement=rep)
    keyed = KEYED.get(name)
    if keyed:
        f, var = keyed
        if not (ROOT / f).exists() and not os.environ.get(var):
            return _cause("KEY_MISSING", "CREDENTIAL_ABSENT",
                          f"neither {f} nor ${var} is present on this host (existence checked; "
                          "nothing read)")
    for k in sorted(keys):
        wall = ev["walls"].get(k)
        if wall:
            return _cause("FETCH_FAILURE", f"SOURCE_WALL:{wall}",
                          f"seed_miners.SOURCE_WALLS['{k}'] = {wall}: a recorded refusal the "
                          "miner re-probes itself; person-released, never bypassed here")
        plat = ev["platforms"].get(k)
        if isinstance(plat, dict):
            state = str(plat.get("last_state") or "")
            best = plat.get("best_rows")
            if state and state != "ok" and not best:
                return _cause("FETCH_FAILURE", f"PLATFORM:{state}",
                              f"ALT_DATA_YIELD: last_state {state} at {plat.get('last_attempt')}, "
                              f"best_rows {best}: the ground has never yielded a record")
        blk = ev["blocked"].get(k)
        if isinstance(blk, dict):
            return _cause("FETCH_FAILURE", f"BLOCKED:{blk.get('diagnosis') or 'BLOCKED'}",
                          f"blocked_sources.json: {blk.get('diagnosis')} -- "
                          f"{str(blk.get('fix_hint') or '')[:120]}")
    up = UPSTREAM.get(name)
    if up:
        age = ev["bars"].get("newest_bar_age_h" if up == "bars" else "newest_tick_age_h")
        if isinstance(age, (int, float)) and age > UPSTREAM_STALE_H:
            return _cause("UPSTREAM_DEAD", f"{up.upper()}_STALE",
                          f"BARS_STATE: newest {up} is {age:.1f}h old (> {UPSTREAM_STALE_H:g}h)")

    if legs:
        led = ev["ledger"]
        if not led.get("available"):
            return _cause(UNMEASURED_CAUSE, "LEDGER_UNREADABLE",
                          f"clocked here by {sorted(legs)}, but {led.get('path')} holds no row "
                          "inside the window, so no run can be read")
        runs = [(led["last"][g], g) for g in sorted(legs) if g in led["last"]]
        if not runs:
            return _cause("SCHEDULE", "LEG_NOT_RUN_IN_WINDOW",
                          f"leg(s) {sorted(legs)} have no compute-ledger row in "
                          f"{ev['window_h']:g}h: rotated out, outside every plan, or its task "
                          "did not start")
        last, leg = max(runs, key=lambda rg: rg[0]["at"])
        out = last["outcome"]
        if "STOOD_DOWN" in out.upper() or "STOOD DOWN" in out.upper():
            return _cause("BACKPRESSURE_GATE", "LEG_STOOD_DOWN",
                          f"{leg} at {last['at']}: {out}")
        if out.upper().startswith("TIMEOUT") or "TIMEOUTEXPIRED" in out.upper():
            return _cause("SCHEDULE", "BUDGET_KILLED_BEFORE_WRITE",
                          f"{leg} at {last['at']}: {out} -- killed at its cap before it wrote")
        if out and out != "ok":
            return _cause(UNMEASURED_CAUSE, "LEG_FAILED", f"{leg} at {last['at']}: {out}")
        return _cause(UNMEASURED_CAUSE, "RAN_OK_WROTE_NOTHING",
                      f"{leg} ran ok at {last['at']} and wrote no seat row and no registry "
                      "cell: read its own report for the empty screen")
    if box_tasks:
        return _cause(UNMEASURED_CAUSE, "BOX_TASK_UNREAD",
                      f"clocked by box task(s) {box_tasks}; their run record is not read here")
    if off_box:
        ship = ev["ship"].get("last_commit")
        age = _age_h(ship) if ship else None
        if age is not None and age > ev["window_h"]:
            return _cause("SCHEDULE", "OFF_BOX_CLOCK_TRANSPORT_SILENT",
                          f"only clock(s) {off_box} are off this host, and the transport "
                          f"{ev['ship'].get('ref')} last committed {ship} ({age:.0f}h ago)")
        return _cause("SCHEDULE", "OFF_BOX_CLOCK",
                      f"only clock(s) {off_box} are off this host"
                      + (f"; transport {SHIP_REF} last committed {ship}" if ship else
                         f"; transport {SHIP_REF} unreadable here"))
    return _cause("SCHEDULE", "NO_CLOCK", "no leg, task or timer names it on any host")


def _rel(p: Path) -> str:
    """A repo-relative path for a message, never an exception. A fence that crashes while
    explaining a breach reports nothing at all, which is worse than the breach."""
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def _read(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default if default is not None else {}


def _seat_output(window_days: float) -> dict[str, int]:
    """Rows each intelligence seat donated inside the window, from the files themselves.

    Measured off FILE MTIME rather than a row's own stamp: a seat that stopped writing is the
    thing being looked for, and a stale row's internal timestamp would report it as alive.
    """
    cutoff = time.time() - window_days * 86400.0
    out: Counter[str] = Counter()
    for root in (DESK / "data" / "intelligence", ROOT / "data" / "intelligence"):
        for pat in ("*/*.json", "*/*.jsonl"):
            for f in glob.glob(str(root / pat)):
                seat = os.path.basename(os.path.dirname(f))
                try:
                    if os.path.getmtime(f) < cutoff:
                        out.setdefault(seat, 0)
                        continue
                    with open(f, encoding="utf-8", errors="replace") as fh:
                        n = sum(1 for _ in fh)
                except OSError:
                    continue
                out[seat] += max(n, 1)
    return dict(out)


def _alias_output(window_days: float) -> dict[str, int]:
    """Rows each SEAT_FILE_ALIASES producer wrote inside the window: its own file prefix inside the
    shared seat, measured off file mtime exactly as `_seat_output` measures a whole seat."""
    cutoff = time.time() - window_days * 86400.0
    out: dict[str, int] = {}
    for producer, (seat, prefix) in SEAT_FILE_ALIASES.items():
        for root in (DESK / "data" / "intelligence", ROOT / "data" / "intelligence"):
            for f in glob.glob(str(root / seat / f"{prefix}*")):
                try:
                    if os.path.getmtime(f) < cutoff:
                        out.setdefault(producer, 0)
                        continue
                    with open(f, encoding="utf-8", errors="replace") as fh:
                        n = sum(1 for _ in fh)
                except OSError:
                    continue
                out[producer] = out.get(producer, 0) + max(n, 1)
    return out


def audit(window_days: float = 3.0, cells: dict[str, Any] | None = None,
          evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    """The seat half. `cells` (this pass's `yield_audit`) lets a producer whose seat is empty but
    whose cells reached the registry read as PRODUCING, and supplies the productivity census's
    clock column to the cause classifier; `evidence` overrides `cause_evidence` (tests)."""
    seats = _seat_output(window_days)
    any_seat = bool(seats)
    rows: list[dict[str, Any]] = []

    # THE PROPOSERS, from the daily cycle's own list rather than a copy of it. A list that can
    # drift from the runner is a list that reports on organs nobody runs.
    proposers: list[str] = []
    try:
        src = (DESK / "research" / "daily_cycle.py").read_text(encoding="utf-8")
        start = src.find('for name in ("plumbing_miner"')
        if start > 0:
            block = src[start:src.find("):", start)]
            proposers = [t.strip().strip('"') for t in block.split("(", 1)[1].split(",")
                         if t.strip().strip('"').isidentifier()]
    except OSError:
        pass

    # THE SEAT DIRECTORY IS NOT ALWAYS THE MODULE NAME, and a mismatch reads as DEAD. `asia_plane`
    # donates into `data/intelligence/asia/`, so without this it would be reported as producing
    # nothing on the same night it produced 513 cells -- the exact false negative this gate
    # exists to avoid making about anything else.
    for producer, seat in (("asia_plane", "asia"), ("asia_transmission", "asia_transmission"),
                           ("deep_forest_miner", "deep_forest")):
        if producer not in seats and seat in seats:
            seats[producer] = seats[seat]
    universe = list(seats.values())

    # AND THE REST ARE FOLLOWED, NOT LISTED (2026-10-29). A proposer's seat is its module's own
    # `SOURCE`: plumbing_miner donates into `plumbing/`, weak_signal_compiler into
    # `weak_signal_ensemble/`, microstructure_miner into `microstructure/`. Read by module name,
    # ten proposers sat UNMEASURED beside the seat that records them. A proposer whose seat has
    # never been written, on a host that has seats at all, is a measured zero (DEAD).
    seat_for: dict[str, str] = {}
    basis: dict[str, str] = {}
    for producer, n_alias in _alias_output(window_days).items():
        if seats.get(producer) is None or (n_alias and not seats.get(producer)):
            seats[producer] = n_alias
            seat_for[producer] = SEAT_FILE_ALIASES[producer][0]
            basis[producer] = (f"seat_file_alias:{SEAT_FILE_ALIASES[producer][0]}/"
                               f"{SEAT_FILE_ALIASES[producer][1]}*")
    for producer in sorted(set(proposers) | set(REPLACEMENTS)):
        own = seat_of(producer)
        if not own or producer in seat_for:
            continue
        if own == producer:
            # Its seat IS its name and has never been written: a measured zero on a host that
            # has seats at all, never an absence of measurement.
            if seats.get(producer) is None and any_seat:
                seats[producer] = 0
            continue
        seat_for[producer] = own
        if seats.get(producer) is None or (seats.get(own) and not seats.get(producer)):
            if own in seats:
                seats[producer] = seats[own]
                basis[producer] = f"seat_source:{own}"
            elif any_seat:
                seats[producer] = 0

    # CELLS ARE OUTPUT TOO. An organ that writes cells straight to the registry has an empty seat
    # by construction; the cells half measured its emission, so DEAD would be a false negative.
    emitted: dict[str, float] = {}
    for r in ((cells or {}).get("producers") or []):
        if isinstance(r, dict):
            b = _base(str(r.get("key") or r.get("producer") or ""))
            emitted[b] = emitted.get(b, 0.0) + float(r.get("cells_emitted_per_hour") or 0.0)
    ev = evidence if evidence is not None else cause_evidence(window_days, cells)
    median = sorted(universe)[len(universe) // 2] if universe else 0

    for name in sorted(set(proposers) | set(seats) | set(REPLACEMENTS)):
        n = seats.get(name)
        rec: dict[str, Any] = {"producer": name, "rows_in_window": n,
                               "window_days": window_days}
        if name in seat_for:
            rec["seat"] = seat_for[name]
        if name in basis and n:
            rec["basis"] = basis[name]
            rec["resolved_cause"] = "WRITES_ELSEWHERE"
        if n is None:
            rec.update({"verdict": "UNMEASURED",
                        "why": ("no intelligence seat records this producer's output. It may "
                                "write elsewhere, or it may write nowhere -- and those are not "
                                "the same thing, so neither is assumed.")})
        elif n == 0:
            rec.update({"verdict": "DEAD",
                        "why": f"zero rows in {window_days:g} day(s)",
                        "replacement": REPLACEMENTS.get(name,
                                                        "NONE DECLARED -- a dead producer with "
                                                        "no named alternative is an open "
                                                        "decision, which is the defect")})
        elif median and n < median * STARVED_FRACTION:
            rec.update({"verdict": "STARVED",
                        "why": (f"{n} row(s) against a median of {median}. A budget or input "
                                f"problem, NOT a reason to replace the producer.")})
        else:
            rec["verdict"] = "PRODUCING"
        cells_h = emitted.get(name, 0.0) + (emitted.get(seat_for[name], 0.0)
                                            if name in seat_for else 0.0)
        if rec["verdict"] in ("DEAD", "UNMEASURED") and cells_h > 0:
            rec.update({"verdict": "PRODUCING", "basis": "registry_cells",
                        "resolved_cause": "WRITES_ELSEWHERE",
                        "why": (f"its seat is empty, but it emitted {cells_h:.2f} cell(s)/h to "
                                "the registry inside the cells window: output, written "
                                "elsewhere")})
            rec.pop("replacement", None)
        if rec["verdict"] in ("DEAD", "UNMEASURED"):
            try:
                rec.update(cause_of(name, seat_for.get(name), ev))
            except Exception as exc:                      # a classifier bug never kills the fence
                rec.update({"cause": UNMEASURED_CAUSE, "cause_detail": "CLASSIFIER_ERROR",
                            "cause_evidence": f"{type(exc).__name__}: {exc}"[:200]})
            # A RETIREMENT IS ITS OWN DECLARATION: `cause_of` returns the successor it read as
            # `replacement`, so a seat retired through its module's seat name no longer reads
            # NONE DECLARED.
        rows.append(rec)

    census = Counter(str(r["verdict"]) for r in rows)
    dead = [r for r in rows if r["verdict"] == "DEAD"]
    undeclared = [r for r in dead if "NONE DECLARED" in str(r.get("replacement"))]
    return {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "law": ("EVERY PRODUCER PRODUCES, OR IT IS REPLACED BY A NAMED ALTERNATIVE. Zero output "
                "is DEAD and carries a replacement; low output is STARVED and carries a budget "
                "question; no artifact is UNMEASURED and carries neither."),
        "window_days": window_days,
        "median_rows": median,
        "n_producers": len(rows),
        "census": dict(census),
        "dead_without_a_declared_replacement": undeclared,
        # WHY, NOT ONLY WHAT (2026-10-29): every DEAD/UNMEASURED row's cause, counted.
        "seat_rule": SEAT_RULE,
        "causes": dict(Counter(str(r["cause"]) for r in rows if r.get("cause"))),
        "cause_vocabulary": list(CAUSES),
        "resolved_writes_elsewhere": sorted(r["producer"] for r in rows
                                            if r.get("resolved_cause") == "WRITES_ELSEWHERE"),
        "cause_inputs": {
            "ledger": {k: v for k, v in (ev.get("ledger") or {}).items() if k != "last"},
            "ship": ev.get("ship"),
            "n_walls": len(ev.get("walls") or {}),
            "n_platforms": len(ev.get("platforms") or {}),
        },
        "producers": sorted(rows, key=lambda r: (r["verdict"], -(r["rows_in_window"] or 0))),
    }


# ------------------------------------------------------------ EVERY PRODUCER OWES CELLS (LAWS 7)

def _declarations() -> dict[str, dict[str, Any]]:
    """Named blockers and declared exemptions, keyed by producer, from the shared document.

    An absent file is an empty set, never an error: a desk with nothing to declare should not
    have to keep an empty document current, and the failure message says where to write one.
    """
    blob = _read(BLOCKERS, default={})
    rows = blob.get("blockers", blob) if isinstance(blob, dict) else blob
    out: dict[str, dict[str, Any]] = {}
    if isinstance(rows, dict):
        items = list(rows.items())
    elif isinstance(rows, list):
        items = [(r.get("producer") or r.get("key"), r) for r in rows if isinstance(r, dict)]
    else:
        items = []
    for key, val in items:
        if not key:
            continue
        entry = val if isinstance(val, dict) else {"why": str(val)}
        why = str(entry.get("why") or entry.get("reason") or entry.get("blocker") or "").strip()
        owner = str(entry.get("owner") or entry.get("by") or "").strip()
        produces = str(entry.get("produces") or "").strip()
        consumer = str(entry.get("consumer") or entry.get("read_by") or "").strip()
        # TWO WAYS TO PASS, AND THEY MEAN DIFFERENT THINGS. A BLOCKER says "this is broken, here
        # is who owns the fix"; an EXEMPTION says "this makes something other than cells, and
        # here is who reads it". Neither is inferred -- an organ that says nothing is a defect.
        if entry.get("exempt") and len(produces) >= 3 and len(consumer) >= 3:
            out[str(key).strip().lower()] = {"kind": "EXEMPTION", "produces": produces,
                                             "consumer": consumer}
        elif len(why) >= 20 and owner:
            out[str(key).strip().lower()] = {"kind": "BLOCKER", "why": why, "owner": owner}
    return out


def _window_cells(window_hours: float, db: Path | None = None) -> dict[str, Any]:
    """Per-producer cells inside the window, and the cell identities breadth is measured on.

    Read from the registry rather than from the census's funnel because the funnel is ALL-TIME:
    a producer that died a week ago still carries its lifetime cells there, and this fence is
    about the hour. An unreadable registry is UNMEASURED with the reason, never zero (L1.28a).
    """
    # Resolved at CALL time, never bound as a default: a default argument freezes the path at
    # import and quietly ignores every later reconfiguration, which is how a fence comes to read
    # one desk's registry while reporting on another's.
    db = db if db is not None else REGISTRY_DB
    out: dict[str, Any] = {"available": False, "why": "", "per": {}, "cells": {},
                           "window_hours": window_hours}
    if not db.exists():
        out["why"] = f"UNMEASURED: no registry at {db}"
        return out
    # Cut on a normalised prefix so a row stored with a space separator instead of `T` is not
    # silently excluded -- an undercount here would read as a barren producer, the exact false
    # positive this fence must never make.
    cutoff = (datetime.now(UTC) - timedelta(hours=window_hours)).strftime("%Y-%m-%dT%H:%M:%S")
    when = "replace(substr(created_at,1,19),' ','T') >= ?"
    judged = ("(donated_cell is not null or status in "
              "('donated','claimed','retired','judged'))")
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        out["why"] = f"UNMEASURED: registry unopenable ({type(exc).__name__}: {exc})"
        return out
    try:
        cur = con.cursor()
        # CREDIT THE PRODUCER THAT CAUSED THE CELL, NOT THE COMPILER THAT STAMPED IT. Measured
        # 2026-09-17 and documented in `desks/mt5/research/japan/dashboard.py`: cells reach
        # `research_candidates` through `discovery_compiler`, which writes its OWN generator, so
        # `generator LIKE 'japan:%'` returns zero while the department has 54 cells queued. The
        # link that survives the compiler is `discovery_id`. Reading the candidate's stamp alone
        # credits one pass-through with the desk's whole output and reports every real producer
        # as barren -- the exact false accusation this fence exists to avoid making.
        gen = ("lower(coalesce(nullif(d.generator,''), nullif(c.generator,''),"
               "'_unattributed_generator'))")
        cell = ("lower(coalesce(nullif(c.family,''),'?'))||'|'||"
                "lower(coalesce(nullif(c.symbol,''),'?'))||'|'||"
                "lower(coalesce(nullif(c.horizon,''),'?'))")
        src = ("research_candidates c left join discoveries d "
               "on d.discovery_id = c.discovery_id")
        when = when.replace("created_at", "c.created_at")
        judged = judged.replace("donated_cell", "c.donated_cell").replace("status", "c.status")
        per: dict[str, dict[str, int]] = {}
        for key, raw, uniq, sent in cur.execute(
                f"select {gen}, count(*), "  # noqa: S608 -- fragments are literals above
                f"count(distinct coalesce(nullif(c.grid_cell,''), c.content_hash)), "
                f"sum(case when {judged} then 1 else 0 end) "
                f"from {src} where {when} group by 1", (cutoff,)):
            per[str(key)] = {"cells_emitted": int(raw or 0), "unique_cells": int(uniq or 0),
                             "cells_to_judge": int(sent or 0)}
        cells: dict[str, list[str]] = {}
        for key, ident in cur.execute(
                f"select distinct {gen}, {cell} from {src} "  # noqa: S608
                f"where {when} and {judged}", (cutoff,)):
            cells.setdefault(str(key), []).append(str(ident))
        # A window in which NOTHING was created is UNMEASURED, never a verdict on any one
        # producer: if the whole registry is silent the failure is the desk's, and convicting
        # every organ on it would be the fence accusing everybody of one organ's outage (L1.28a).
        out.update({"available": bool(per), "per": per,
                    "cells": {k: sorted(v)[:MAX_CELLS_PER_PRODUCER] for k, v in cells.items()}})
        if not per:
            out["why"] = (f"UNMEASURED: no research_candidates row was created in the last "
                          f"{window_hours:g}h on this host, so no producer can be judged barren "
                          f"against it")
    except sqlite3.Error as exc:
        out["why"] = f"UNMEASURED: registry query failed ({type(exc).__name__}: {exc})"
    finally:
        con.close()
    return out


def _breadth(cells: dict[str, list[str]]) -> dict[str, Any]:
    """The desk's own effective-rank breadth, REUSED rather than re-implemented.

    `libs.research.sandbox_rotation.breadth` is the participation ratio of the singular-value
    spectrum of the producer x (family|symbol|horizon) indicator matrix, with each producer's
    marginal contribution measured as the drop when its row is removed. Two producers emitting
    the same cells therefore each score 0.0 added breadth, which is the whole point. A guarded
    import: numpy absent makes orthogonality UNMEASURED, never a crash in a law gate.
    """
    if not cells:
        return {"available": False, "why": "UNMEASURED: no judged cell in the window"}
    try:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from libs.research.sandbox_rotation import breadth as _b
    except Exception as exc:  # pragma: no cover - environment-dependent
        return {"available": False,
                "why": f"UNMEASURED: effective-rank machinery unimportable ({type(exc).__name__})"}
    try:
        got = _b(cells)
    except Exception as exc:  # pragma: no cover - defensive
        return {"available": False,
                "why": f"UNMEASURED: breadth failed ({type(exc).__name__}: {exc})"}
    got["available"] = True
    return got


def _ratchet_doc() -> dict[str, Any]:
    doc = _read(RATCHET, default={})
    return doc if isinstance(doc, dict) else {}


def _set_aside_summary() -> dict[str, Any]:
    """The producers' own named refusals, read from reports/SET_ASIDE_LEDGER.json.

    An absent ledger is UNMEASURED, never zero: it means no organ has recorded a truncation
    yet, not that no organ truncates. Nothing here gates or caps -- it is the denominator the
    throughput numbers above are otherwise read without.
    """
    try:
        from libs.research import set_aside as sa
    except Exception as exc:                                # pragma: no cover - import guard
        return {"available": False, "why": f"{type(exc).__name__}: {exc}"}
    doc = sa.read()
    totals = doc.get("totals") if isinstance(doc.get("totals"), dict) else {}
    if not totals:
        return {"available": False, "why": "no organ has recorded a named refusal yet",
                "path": _rel(sa.PATH)}
    worst = sorted(totals.items(), key=lambda kv: -int((kv[1] or {}).get("set_aside", 0)))
    return {"available": True, "path": _rel(sa.PATH), "at": doc.get("at"),
            "organs": doc.get("organs"), "stages": len(totals),
            "set_aside_total": doc.get("set_aside_total"),
            "worst": [{"stage": k, "set_aside": v.get("set_aside"), "kept": v.get("kept"),
                       "considered": v.get("considered"), "ordering": v.get("ordering")}
                      for k, v in worst[:10]]}


def yield_audit(window_hours: float = YIELD_WINDOW_HOURS) -> dict[str, Any]:
    """EVERY PRODUCER OWES CELLS: who is paying for its compute, and how orthogonally."""
    census = _read(CENSUS, default={})
    declared = _declarations()
    win = _window_cells(window_hours)
    per = win["per"]
    br = _breadth(win["cells"])
    marginal = br.get("marginal") or {}
    row_doc = _read(ROW_CONVERSION, default={})
    row_rows = row_doc.get("per_producer") if isinstance(row_doc, dict) else []
    row_by_producer = {
        str(r.get("producer") or "").strip().lower(): r
        for r in (row_rows if isinstance(row_rows, list) else []) if isinstance(r, dict)
    }

    rows: list[dict[str, Any]] = []
    owing: list[dict[str, Any]] = []
    exempted: list[dict[str, Any]] = []
    unattributed: list[str] = []
    census_rows = census.get("producers") if isinstance(census.get("producers"), list) else []
    seen: set[str] = set()
    for src in list(census_rows) + [{"producer": k, "key": k} for k in per]:
        if not isinstance(src, dict):
            continue
        key = str(src.get("key") or src.get("producer") or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        m = per.get(key) or {}
        hours = src.get("compute_hours")
        hours = float(hours) if isinstance(hours, (int, float)) else None
        led = src.get("compute_hours_ledger")
        led = float(led) if isinstance(led, (int, float)) else 0.0
        reg_h = src.get("compute_hours_registry")
        reg_h = float(reg_h) if isinstance(reg_h, (int, float)) else 0.0
        # TWO SOURCES OF "IT RAN", TWO FLOORS. A ledger hour is a leg's wall clock and needs the
        # floor; a registry second is a generator recording a pass it actually made, so any
        # positive value is that pass. Neither is inferred from a clock existing: an organ whose
        # compute nothing measured is UNMEASURED here and is counted in `compute_unattributed`
        # rather than accused (L1.28a).
        spent = (led >= MIN_COMPUTE_HOURS) or (reg_h > 0.0)
        row = {
            "producer": src.get("producer") or key,
            "key": key,
            "clock": src.get("clock"),
            "compute_hours_window7d": hours if hours is not None else UNMEASURED_STR,
            # THE FOUR COLUMNS THE LAW ASKS FOR, all per hour so producers on different clocks
            # are comparable at all.
            "cells_emitted_per_hour": round(m.get("cells_emitted", 0) / window_hours, 4),
            "unique_cells_per_hour": round(m.get("unique_cells", 0) / window_hours, 4),
            "cells_to_judge_per_hour": round(m.get("cells_to_judge", 0) / window_hours, 4),
            "orthogonality_added": (round(float(marginal.get(key, 0.0)), 4)
                                    if br.get("available") else UNMEASURED_STR),
        }
        decl = declared.get(key)
        if decl:
            row["declared"] = decl
        row_contract = row_by_producer.get(key)
        if row_contract:
            row["convertible_rows"] = int(row_contract.get("convertible_rows") or 0)
            row["converted_rows"] = int(row_contract.get("converted_rows") or 0)
            row["convertible_conversion_rate"] = row_contract.get(
                "convertible_conversion_rate")
            row["convertible_rows_owed"] = int(row_contract.get("owes_convertible_rows") or 0)
        # OWING: it spent real compute and the judge saw NOTHING from it in the window, and it
        # has not said why. Not "low" -- zero. Low is a budget question and is never a failure
        # here, because cutting the tail of the search distribution is the one reduction in
        # aggressiveness this desk refuses.
        if spent and m.get("unique_cells", 0) == 0 and win.get("available"):
            if decl:
                exempted.append(row)
            else:
                owing.append(row)
        elif (not spent and str(src.get("clock") or "")
                and not str(src.get("clock")).startswith(("invoked:", "import:"))):
            unattributed.append(key)
        rows.append(row)

    n_judge = sum(int(v.get("cells_to_judge", 0)) for v in per.values())
    to_judge_per_h = round(n_judge / window_hours, 4)
    # THE ORTHOGONALITY-WEIGHTED EQUIVALENT, and it is the number to optimise. Total effective
    # rank over the number of producers that reached the judge: 1.0 when every producer works a
    # disjoint region of the cell space, and 1/n when they all emit the same rule n times. So a
    # hundred copies of one momentum rule score as one cell's worth of breadth, exactly as the
    # law says -- volume alone can never move this figure.
    n_rows_matrix = len(win["cells"])
    weight = (float(br.get("total") or 0.0) / n_rows_matrix) if (br.get("available")
                                                                 and n_rows_matrix) else None
    ortho_per_h = round(to_judge_per_h * weight, 4) if weight is not None else UNMEASURED_STR

    rat = _ratchet_doc()
    owing_max = rat.get("owing_max")
    best_judge = rat.get("cells_to_judge_per_hour_best")
    best_ortho = rat.get("orthogonal_cells_to_judge_per_hour_best")
    reason = str(rat.get("regression_reason") or "").strip()

    failures: list[str] = []
    row_debt = [r for r in rows if int(r.get("convertible_rows_owed") or 0) > 0]
    if row_debt:
        failures.append(
            f"{len(row_debt)} producer(s) have convertible source rows that emitted no valid "
            "AlphaCell; declarations and prose volume do not excuse row loss. Owing: "
            + ", ".join(f"{r['producer']}={r['convertible_rows_owed']}" for r in row_debt[:12]))
    if isinstance(owing_max, (int, float)) and len(owing) > owing_max:
        failures.append(
            f"{len(owing)} producer(s) owe cells against a ratchet of {owing_max:g}: the count "
            "of producers burning compute with no unique cell, no declared exemption and no "
            "named blocker may only FALL. Make them produce, declare what they make instead and "
            f"who reads it in {_rel(BLOCKERS)}, or retire them with a reason -- "
            "never throttle a producing one. Owing: "
            + ", ".join(str(r["producer"]) for r in owing[:12]))
    if (isinstance(best_judge, (int, float)) and win.get("available")
            and to_judge_per_h < best_judge * THROUGHPUT_FLOOR_FRACTION and not reason):
        failures.append(
            f"cells reaching the judge fell to {to_judge_per_h:g}/h against a best of "
            f"{best_judge:g}/h (floor {THROUGHPUT_FLOOR_FRACTION:g}x) with no stated reason: set "
            f"`regression_reason` in {_rel(RATCHET)} or find the lane that stopped")
    if (isinstance(best_ortho, (int, float)) and isinstance(ortho_per_h, float)
            and ortho_per_h < best_ortho * THROUGHPUT_FLOOR_FRACTION and not reason):
        failures.append(
            f"ORTHOGONAL cells reaching the judge fell to {ortho_per_h:g}/h against a best of "
            f"{best_ortho:g}/h with no stated reason: the desk is still emitting volume but the "
            "producers have collapsed onto each other's cells, which is the failure this column "
            "exists to catch")

    rows.sort(key=lambda r: (-(r["cells_to_judge_per_hour"] or 0.0),
                             str(r["producer"])))
    return {
        "law": ("EVERY PRODUCER OWES CELLS (LAWS 7). An organ that runs on a clock, consumes "
                "compute and emits no cell inside its own window is a defect with an owner. "
                "Exploratory organs pass by DECLARING what they produce instead and who reads "
                "it. Ratchets fall only; nothing here caps a producer."),
        "window_hours": window_hours,
        "registry": {"available": win.get("available"), "why": win.get("why")},
        "row_conversion": {
            "path": _rel(ROW_CONVERSION),
            "available": bool(row_by_producer),
            "generated_utc": row_doc.get("generated_utc") if isinstance(row_doc, dict) else None,
            "producers_with_convertible_debt": len(row_debt),
            "rule": ("every convertible input row emits at least one valid AlphaCell; a named "
                     "non-alpha refusal remains honest and is not manufactured into a strategy"),
        },
        "census_at": census.get("at"),
        "breadth": {k: v for k, v in br.items() if k != "marginal"},
        "n_producers": len(rows),
        "n_owing": len(owing),
        "n_declared": len(exempted),
        # THE MEASUREMENT GAP, NAMED RATHER THAN SILENT. These carry a self-turning clock and no
        # measured compute at all, so this fence cannot say whether they owe. That is UNMEASURED,
        # which is a verdict about the measurement (L1.28a) -- and the remedy is to make the
        # compute ledger key on producers, not to accuse or excuse them here.
        "compute_unattributed": len(unattributed),
        "compute_unattributed_why": (
            "producers with a declared self-turning clock and no ledger hour and no registry "
            "second: `cost_by_run` keys on the LEG name, and a leg that runs many producers "
            "prices none of them individually"),
        "compute_unattributed_sample": sorted(unattributed)[:20],
        "cells_to_judge_per_hour": to_judge_per_h,
        "orthogonal_cells_to_judge_per_hour": ortho_per_h,
        "orthogonality_weight": None if weight is None else round(weight, 4),
        # WHAT THE PRODUCERS CHOSE NOT TO LOOK AT, from their own named refusals
        # (libs/research/set_aside.py -> reports/SET_ASIDE_LEDGER.json). A throughput number
        # read without this is the numerator of a fraction whose denominator is hidden: an organ
        # carrying 40 of 900 rows is not the same measurement as one carrying 40 of 41. Only the
        # four immutable evaluator files may REFUSE a cell (LAWS 7); everything counted here is a
        # BATCH BUDGET, and this fence names it rather than capping anything.
        "set_aside": _set_aside_summary(),
        "ratchet": {"owing_max": owing_max, "cells_to_judge_per_hour_best": best_judge,
                    "orthogonal_cells_to_judge_per_hour_best": best_ortho,
                    "regression_reason": reason or None},
        "failures": failures,
        "owing": owing,
        "declared": exempted,
        "producers": rows,
    }


def tighten_ratchet(doc: dict[str, Any]) -> dict[str, Any] | None:
    """Ratchets fall only. Returns the new document when it moved, else None.

    The owing count may only fall and the two throughput bests may only rise. Seeding on a first
    run is not an improvement claim -- it is the baseline, recorded so the NEXT run has something
    to be measured against (an absent ratchet is UNMEASURED, never a pass by default).
    """
    rat = _ratchet_doc()
    moved = False
    if doc.get("registry", {}).get("available"):
        cur = rat.get("owing_max")
        if not isinstance(cur, (int, float)) or doc["n_owing"] < cur:
            rat["owing_max"] = doc["n_owing"]
            moved = True
        for field, key in (("cells_to_judge_per_hour_best", "cells_to_judge_per_hour"),
                           ("orthogonal_cells_to_judge_per_hour_best",
                            "orthogonal_cells_to_judge_per_hour")):
            val = doc.get(key)
            if not isinstance(val, (int, float)):
                continue
            cur = rat.get(field)
            if not isinstance(cur, (int, float)) or val > cur:
                rat[field] = val
                moved = True
    if not moved:
        return None
    rat["updated_utc"] = datetime.now(UTC).isoformat(timespec="seconds")
    rat.setdefault("law", "LAWS 7 -- EVERY PRODUCER OWES CELLS. This ratchet falls only.")
    return rat


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--window-days", type=float, default=3.0)
    ap.add_argument("--yield-window-hours", type=float, default=YIELD_WINDOW_HOURS)
    ap.add_argument("--no-ratchet", action="store_true",
                    help="measure and report without tightening the ratchet on disk")
    # THE TWO HALVES KEEP THEIR OWN VERDICTS. The seat half (EVERY PRODUCER PRODUCES, 2026-09-15)
    # is fatal on a dead producer with no named inheritor and rides the fence battery, where that
    # backlog is the worklist. The law gate enforces the CELLS half, so a debt one half is still
    # working through cannot silence the other -- one exit code for two different laws is how a
    # gate comes to be disabled wholesale.
    ap.add_argument("--cells-only", action="store_true",
                    help="judge only EVERY PRODUCER OWES CELLS (the law-gate half)")
    args = ap.parse_args(argv)

    # THE CELLS HALF FIRST: the seat half reads its per-producer emission (a seat that is empty
    # while its cells reach the registry is PRODUCING) and its clock column (the cause classifier).
    yld = yield_audit(window_hours=args.yield_window_hours)
    doc = audit(window_days=args.window_days, cells=yld)
    doc["cells_owed"] = yld
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")

    if not args.no_ratchet:
        moved = tighten_ratchet(yld)
        if moved is not None:
            RATCHET.parent.mkdir(parents=True, exist_ok=True)
            RATCHET.write_text(json.dumps(moved, indent=1) + "\n", encoding="utf-8")

    print(f"producer yield: {doc['n_producers']} producer(s) over {args.window_days:g}d -> "
          f"{doc['census']}   (median {doc['median_rows']} rows)"
          + ("   [seat half REPORTED ONLY under --cells-only]" if args.cells_only else ""))
    for v in ((), ("DEAD", "STARVED", "UNMEASURED"))[not args.cells_only]:
        rs = [r for r in doc["producers"] if r["verdict"] == v]
        if not rs:
            continue
        print(f"\n  {v} {len(rs)}:")
        for r in rs[:12]:
            tail = (f" -> {str(r.get('replacement'))[:60]}" if v == "DEAD"
                    else f"  {str(r.get('why'))[:60]}")
            if r.get("cause"):
                tail = f"  [{r['cause']}:{r.get('cause_detail')}]" + tail
            print(f"    {str(r['producer'])[:26]:26} {r['rows_in_window']!s:>7}{tail}")
    if doc.get("causes"):
        print(f"\n  causes {doc['causes']}   resolved (writes elsewhere) "
              f"{len(doc.get('resolved_writes_elsewhere') or [])}")
    print(f"\nEVERY PRODUCER OWES CELLS ({yld['window_hours']:g}h): {yld['n_producers']} producer(s), "
          f"{yld['n_owing']} owing, {yld['n_declared']} declared")
    print(f"  cells to judge/h {yld['cells_to_judge_per_hour']}   orthogonal equivalent/h "
          f"{yld['orthogonal_cells_to_judge_per_hour']} "
          f"(weight {yld['orthogonality_weight']})   ratchet {yld['ratchet']}")
    top = [r for r in yld["producers"] if r["cells_to_judge_per_hour"]][:10]
    if top:
        print(f"  {'producer':30} {'emit/h':>9} {'uniq/h':>9} {'judge/h':>9} {'ortho':>8}")
        for r in top:
            print(f"  {str(r['producer'])[:30]:30} {r['cells_emitted_per_hour']:>9} "
                  f"{r['unique_cells_per_hour']:>9} {r['cells_to_judge_per_hour']:>9} "
                  f"{r['orthogonality_added']!s:>8}")
    for r in yld["owing"][:12]:
        print(f"  OWES  {str(r['producer'])[:28]:28} {r['compute_hours_window7d']!s:>8}h compute, "
              f"0 unique cells, no declaration")
    for f in yld["failures"]:
        print(f"  FAIL  {f}")
    print(f"  -> {OUT}")
    # A dead producer with NO declared alternative is the fatal state: the law says replace, and
    # there is nothing to replace it with. The second half is fatal on its own ratchets.
    seat_half = [] if args.cells_only else doc["dead_without_a_declared_replacement"]
    return 1 if (seat_half or yld["failures"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
