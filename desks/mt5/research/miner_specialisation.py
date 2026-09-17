"""M24 -- P(valuable candidate | miner, domain): the organisation specialises on measurement.

THE PRINCIPAL'S ORDER (2026-09-16, the resource exchange) was that every department runs at full
useful throughput and spare capacity goes to the best current opportunity without ever shutting a
department down. `research_departments.py` prices SIX departments that way. This organ prices the
level below it -- the MINER, and the DOMAIN it is mining -- because a department is a budget line
and a miner is a thing that either finds edges in metals or does not.

WHAT IS MEASURED. For every (miner, domain) pair: the Beta posterior of producing a VALUABLE
candidate, with Jeffreys priors (0.5, 0.5), from the desk's own judged record.

    valuable = judged AND (passed OR terminal gate at or beyond the MEDIAN gate depth)

THE SECOND CLAUSE IS THE POINT AND IT IS NOT A CONSOLATION PRIZE. A cell that dies at
`symbol_eligibility` cost one gate and taught the desk that a miner does not know what this broker
trades. A cell that reaches `walk_forward` cleared the economic prior, the in-sample screen, the
deflated Sharpe and the purged folds -- it bought eight gates of real information and then failed.
Paying a miner only for certificates prices 48 rows out of 35,199 and calls every other miner
identical; paying it for DEPTH prices what the compute actually bought. The median is taken over
the judged population so the bar moves with the desk rather than with a number somebody typed.

WHAT IS NOT INVENTED. The miner is known per hypothesis (the graph's `source`, the registry's
`generator`); the terminal gate is known per VERDICT. Only the registry's candidate rows carry
both, and on this box `research_candidates` is empty until something runs
`registry.sync_from_desk()`. So the depth join has a DECLARED precedence -- exact cell id, then
the (symbol, family) median, then none -- and every cell publishes how many of its rows came from
each. A posterior resting on coarse joins says so on its face instead of in a caveat nobody reads.

ELASTIC SCALING, WHICH IS THE ORDER'S OTHER HALF. Every miner keeps a FLOOR share and no
measurement can take it: a miner switched off stops producing the evidence that would have
switched it back on, and that is a one-way door. The excess -- (1 - FLOOR_BUDGET) of the budget --
follows the HOTTEST QUEUE: the (miner, domain) cells with the highest posterior times queue depth,
because a high posterior over an empty queue buys nothing this hour. Two-sided by construction
(GROWTH_GOVERNANCE Rule 2): the strong cell is allowed MORE than its baseline, and the weak one
never goes to zero.

THE CONTRACT (`desks/mt5/data/miner_routing.json`, for research_departments and the residents)

    {at, routing: {<domain>: [{miner, p, ci, n}, ...]},     # best miners per domain, p desc
     specialities: {<miner>: [<domain>, ...]},              # beats its own average by > 1 SD
     elastic: {<miner>: {floor, suggested_share, heat}}}    # floor > 0 always; shares sum to 1

    A consumer reads it, or it does not: this organ writes the file and edits nothing. `floor` is
    the guaranteed baseline and `suggested_share` is the elastic ask; a domain absent from
    `routing` is UNMEASURED and must not be read as "no miner is good at it".

    python desks/mt5/research/miner_specialisation.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

GRAPH = DESK / "data" / "hypothesis_graph.jsonl"
GATE_LEDGER = DESK / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
ROUTING = DESK / "data" / "miner_routing.json"
OUT = DESK / "reports" / "MINER_SPECIALISATION.json"

MAX_LINES = 500_000
#: Judged rows a (miner, domain) cell needs before its posterior is MEASURED. Below it the
#: posterior is still defined -- Jeffreys makes sure of that -- but it is the prior wearing a
#: number, and routing compute on it would be routing on the shape of a Beta density.
MIN_JUDGED = 10
#: Share of the budget that is FLOOR: split equally, untouchable, so no miner is ever switched
#: off by a measurement. The rest is elastic and follows the hottest queue.
FLOOR_BUDGET = 0.50
#: Posterior draws for the credible interval. numpy's Generator gives exact Beta variates; a
#: fixed seed makes the published interval reproducible from the same counts.
DRAWS = 4000
SEED = 20260917
CI = (2.5, 97.5)
TOP_PER_DOMAIN = 5
UNKNOWN = "UNKNOWN"

#: Mirrored from `libs/research/hypothesis_graph.GATE_ORDER` -- local, so this organ measures the
#: machinery without importing it. Depth is the INDEX: `symbol_eligibility` is 0 and
#: `expected_value` is 11, and a cell that passed everything is len(GATE_ORDER).
GATE_ORDER: tuple[str, ...] = (
    "symbol_eligibility", "economic_prior", "observations", "in_sample_screen", "deflated_sharpe",
    "pbo", "reality_check_spa", "cpcv", "walk_forward", "stress_costs", "lockbox",
    "expected_value")
#: Gates outside GATE_ORDER that the ledger really carries, placed by what they test.
GATE_DEPTH_EXTRA: dict[str, int] = {"swap_cost": len(GATE_ORDER) - 1,
                                    "PASSED": len(GATE_ORDER)}

#: WHICH SOURCE NAMES A LANGUAGE. DECLARED from `bandit.SOURCE_ARM`'s forest names; a source that
#: names no language has no language domain, which is not the same as English.
SOURCE_LANGUAGE: dict[str, str] = {
    "deep_forest": "zh", "deep_forest_jp": "ja", "deep_forest_kr": "ko",
    "deep_forest_tw_hk": "zh_hant", "deep_forest_sea": "sea", "deep_forest_in": "hi",
    "deep_forest_south_asia": "south_asia", "deep_forest_anz": "en", "deep_forest_mena": "ar",
    "deep_forest_africa": "africa", "deep_forest_west": "en", "deep_forest_eu": "eu",
    "deep_forest_nordics": "nordic", "deep_forest_east_eu": "east_eu", "deep_forest_ru": "ru",
    "deep_forest_latam": "es_pt", "deep_forest_institutional": "en",
}

try:  # an organ that cannot run without an import is an organ that does not run (III.16)
    from libs.moat import registry as _registry
except Exception:  # pragma: no cover - only on a tree without libs/
    _registry = None  # type: ignore[assignment]


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _rel(path: Path) -> str:
    """`path` inside the repo, or its plain string: a tmp path has no relative form."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _read_jsonl(path: Path, note: dict[str, str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8-sig", errors="replace") as fh:
            for i, raw in enumerate(fh):
                if i >= MAX_LINES:
                    note[path.name] = f"TRUNCATED({MAX_LINES})"
                    return rows
                line = raw.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
    except OSError:
        note[path.name] = "ABSENT"
        return rows
    note[path.name] = "READ"
    return rows


def miner_of(row: dict[str, Any]) -> str:
    """The miner that produced a row: the registry's generator, else the source's head segment."""
    gen = str(row.get("generator") or "").strip()
    src = str(row.get("source") or "").strip()
    name = gen or src
    if not name:
        return UNKNOWN
    head = name.split(":")[0]
    return head or UNKNOWN


def axes_of(symbol: Any, family: Any, params: Any = None) -> dict[str, str]:
    try:
        import axis_registry as ar
        return ar.axis_cell(symbol, family, params if isinstance(params, dict) else None)
    except Exception:
        return {"asset_class": UNKNOWN, "mechanism": UNKNOWN}


def domains_of(row: dict[str, Any]) -> list[str]:
    """The domains one candidate belongs to: its asset class, its mechanism class, its language.

    A row belongs to several domains at once and is counted in each -- these are different
    QUESTIONS about the same miner ("is it good at metals", "is it good at forced flow"), not a
    partition, and forcing a partition would make the mechanism answer unavailable.
    """
    a = axes_of(row.get("symbol"), row.get("family"), row.get("params"))
    out = [f"asset:{a.get('asset_class') or UNKNOWN}",
           f"mechanism:{a.get('mechanism') or UNKNOWN}"]
    src = str(row.get("generator") or row.get("source") or "").split(":")[0]
    lang = SOURCE_LANGUAGE.get(src)
    if lang:
        out.append(f"language:{lang}")
    return out


def gate_depth(gate: Any) -> int | None:
    """How far a cell got before it died; None when the ledger names no gate."""
    g = str(gate or "")
    if g in GATE_DEPTH_EXTRA:
        return GATE_DEPTH_EXTRA[g]
    return GATE_ORDER.index(g) if g in GATE_ORDER else None


def depth_index(ledger: list[dict[str, Any]]) -> tuple[dict[str, int], dict[str, float], float]:
    """Per-cell depth, per (symbol, family) median depth, and the MEDIAN over judged rows.

    The median is the bar `valuable` uses. It is computed over every judged verdict that names a
    gate this desk knows, so it moves as the gauntlet's own funnel moves.
    """
    exact: dict[str, int] = {}
    coarse: dict[str, list[int]] = defaultdict(list)
    depths: list[int] = []
    for r in ledger:
        d = gate_depth(r.get("terminal_gate"))
        if d is None:
            continue
        cell = str(r.get("cell") or "")
        if cell:
            exact[cell] = d
        key = f"{str(r.get('sym') or '').upper()}|{r.get('family') or ''!s}"
        coarse[key].append(d)
        depths.append(d)
    med = float(np.median(np.asarray(depths, dtype=float))) if depths else 0.0
    return exact, {k: float(np.median(np.asarray(v, dtype=float)))
                   for k, v in coarse.items()}, med


def _judged_rows(graph: list[dict[str, Any]], reg_rows: list[dict[str, Any]]
                 ) -> tuple[list[dict[str, Any]], str]:
    """The judged record, registry first. Latest row per id; BORN rows are the queue, not a label.

    PRECEDENCE, DECLARED: `research_candidates` carries the generator AND the terminal gate on one
    row, so when it holds anything it is the evidence. The hypothesis graph is the fallback and it
    carries a FATE but no gate, which is exactly why the depth join below exists.
    """
    if reg_rows:
        out = [{"id": str(r.get("id") or ""), "generator": r.get("generator"),
                "source": r.get("origin"), "symbol": r.get("symbol"), "family": r.get("family"),
                "params": {}, "cell": str(r.get("donated_cell") or r.get("id") or ""),
                "passed": bool(r.get("survived")), "terminal_gate": r.get("terminal_gate"),
                "judged": str(r.get("status") or "") in ("judged", "survived")}
               for r in reg_rows]
        return [r for r in out if r["judged"]], "registry.research_candidates"
    latest: dict[str, dict[str, Any]] = {}
    for r in graph:
        rid = str(r.get("id") or "")
        if rid:
            latest[rid] = r
    out = []
    for r in latest.values():
        fate = str(r.get("fate") or "").upper()
        out.append({"id": str(r.get("id") or ""), "generator": "", "source": r.get("source"),
                    "symbol": r.get("symbol"), "family": r.get("family"),
                    "params": r.get("params"), "cell": "",
                    "passed": fate == "CERTIFIED",
                    "terminal_gate": None,
                    "judged": fate in ("FAILED", "BURIED", "CERTIFIED")})
    return [r for r in out if r["judged"]], "hypothesis_graph.fate"


def _queue_rows(graph: list[dict[str, Any]], reg_rows: list[dict[str, Any]]
                ) -> tuple[list[dict[str, Any]], str]:
    """What is WAITING, per miner and domain -- the depth half of the heat."""
    if reg_rows:
        q = [r for r in reg_rows if str(r.get("status") or "") in ("queued", "claimed", "donated")]
        if q:
            return q, "registry.research_candidates(status in queued/claimed/donated)"
    latest: dict[str, dict[str, Any]] = {}
    for r in graph:
        rid = str(r.get("id") or "")
        if rid:
            latest[rid] = r
    return ([r for r in latest.values() if str(r.get("fate") or "").upper() == "BORN"],
            "hypothesis_graph.fate == BORN")


def posterior(n_valuable: int, n_judged: int, rng: np.random.Generator) -> dict[str, Any]:
    """Beta(0.5 + valuable, 0.5 + judged - valuable): mean, SD and a sampled credible interval."""
    a = 0.5 + float(n_valuable)
    b = 0.5 + float(max(0, n_judged - n_valuable))
    mean = a / (a + b)
    sd = float(np.sqrt(a * b / ((a + b) ** 2 * (a + b + 1.0))))
    draws = rng.beta(a, b, size=DRAWS)
    lo, hi = (float(x) for x in np.percentile(draws, CI))
    return {"alpha": round(a, 3), "beta": round(b, 3), "p": round(float(mean), 5),
            "sd": round(sd, 5), "ci": [round(lo, 5), round(hi, 5)], "n": int(n_judged),
            "n_valuable": int(n_valuable)}


def cells(judged: list[dict[str, Any]], exact: dict[str, int], coarse: dict[str, float],
          median_depth: float) -> dict[tuple[str, str], dict[str, Any]]:
    """Counts per (miner, domain): judged, valuable, and how the depth was joined."""
    acc: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {"judged": 0, "valuable": 0, "passed": 0,
                 "join": {"exact": 0, "coarse": 0, "none": 0}})
    for r in judged:
        miner = miner_of(r)
        depth: float | None = gate_depth(r.get("terminal_gate"))
        how = "exact" if depth is not None else ""
        if depth is None and r.get("cell") and r["cell"] in exact:
            depth, how = float(exact[r["cell"]]), "exact"
        if depth is None:
            key = f"{str(r.get('symbol') or '').upper()}|{r.get('family') or ''!s}"
            if key in coarse:
                depth, how = coarse[key], "coarse"
        if depth is None:
            how = "none"
        valuable = bool(r.get("passed")) or (depth is not None and depth >= median_depth)
        for dom in domains_of(r):
            c = acc[(miner, dom)]
            c["judged"] += 1
            c["valuable"] += int(valuable)
            c["passed"] += int(bool(r.get("passed")))
            c["join"][how or "none"] += 1
    return dict(acc)


def queue_depth(queue: list[dict[str, Any]]) -> dict[tuple[str, str], int]:
    out: Counter[tuple[str, str]] = Counter()
    for r in queue:
        miner = miner_of(r)
        for dom in domains_of(r):
            out[(miner, dom)] += 1
    return dict(out)


def routing_table(post: dict[tuple[str, str], dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Per domain, the MEASURED miners ordered by posterior mean. Unmeasured cells never appear."""
    by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for (miner, dom), p in post.items():
        if p["n"] < MIN_JUDGED:
            continue
        by_domain[dom].append({"miner": miner, "p": p["p"], "ci": p["ci"], "n": p["n"],
                               "n_valuable": p["n_valuable"]})
    return {d: sorted(rows, key=lambda r: -r["p"])[:TOP_PER_DOMAIN]
            for d, rows in sorted(by_domain.items())}


def specialities(post: dict[tuple[str, str], dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Domains where a miner beats ITS OWN average by more than one posterior SD.

    The SD is the CELL's, not the miner's: the claim being made is about that cell, so a thin cell
    must clear a wider gap to be called a speciality. A miner with one measured domain has no
    average to beat and therefore no speciality -- which is the honest reading of one number.
    """
    by_miner: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    for (miner, dom), p in post.items():
        if p["n"] >= MIN_JUDGED:
            by_miner[miner].append((dom, p))
    out: dict[str, list[dict[str, Any]]] = {}
    for miner, rows in sorted(by_miner.items()):
        if len(rows) < 2:
            continue
        avg = float(np.mean([p["p"] for _, p in rows]))
        hits = [{"domain": d, "p": p["p"], "own_average": round(avg, 5), "sd": p["sd"],
                 "excess": round(p["p"] - avg, 5), "n": p["n"]}
                for d, p in rows if p["p"] - avg > p["sd"]]
        if hits:
            out[miner] = sorted(hits, key=lambda h: -h["excess"])
    return out


def elastic(miners: list[str], post: dict[tuple[str, str], dict[str, Any]],
            depth: dict[tuple[str, str], int]) -> dict[str, dict[str, Any]]:
    """Floor + hottest-queue excess. Every miner stays ON; the floor is never zero.

    heat(miner) = sum over its MEASURED domains of p x queue_depth -- a posterior over an empty
    queue buys nothing this hour, and a deep queue under a weak posterior buys little either.
    With no measured heat anywhere the excess is split equally: an unmeasured machine reallocates
    nothing (L1.28a), it does not starve everybody.
    """
    if not miners:
        return {}
    floor = FLOOR_BUDGET / len(miners)
    heat: dict[str, float] = dict.fromkeys(miners, 0.0)
    hot: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for (miner, dom), p in post.items():
        if p["n"] < MIN_JUDGED or miner not in heat:
            continue
        q = int(depth.get((miner, dom), 0))
        if q <= 0:
            continue
        heat[miner] += p["p"] * q
        hot[miner].append({"domain": dom, "p": p["p"], "queue": q,
                           "heat": round(p["p"] * q, 3)})
    total = sum(heat.values())
    out: dict[str, dict[str, Any]] = {}
    for m in miners:
        excess = ((1.0 - FLOOR_BUDGET) * heat[m] / total if total > 0
                  else (1.0 - FLOOR_BUDGET) / len(miners))
        out[m] = {"floor": round(floor, 6), "suggested_share": round(floor + excess, 6),
                  "heat": round(heat[m], 3),
                  "hottest": sorted(hot.get(m, []), key=lambda h: -h["heat"])[:3],
                  "basis": "measured heat" if total > 0 else "UNMEASURED: excess split equally"}
    return out


def build(now: datetime | None = None) -> dict[str, Any]:
    at = now or _now()
    note: dict[str, str] = {}
    graph = _read_jsonl(GRAPH, note)
    ledger = _read_jsonl(GATE_LEDGER, note)
    reg_rows: list[dict[str, Any]] = []
    reg_note = "libs.moat.registry unavailable"
    yields: list[dict[str, Any]] = []
    if _registry is not None:
        try:
            reg_rows = _registry.candidates(limit=200000)
            yields = _registry.generator_yields()
            reg_note = f"{len(reg_rows)} candidate row(s)"
        except Exception as exc:
            reg_note = f"{type(exc).__name__}: {exc}"
    judged, basis = _judged_rows(graph, reg_rows)
    queue, queue_basis = _queue_rows(graph, reg_rows)
    exact, coarse, median_depth = depth_index(ledger)
    counts = cells(judged, exact, coarse, median_depth)
    rng = np.random.default_rng(SEED)
    post = {k: {**posterior(v["valuable"], v["judged"], rng), "join": v["join"],
                "n_passed": v["passed"]}
            for k, v in sorted(counts.items())}
    depth = queue_depth(queue)
    miners = sorted({m for m, _ in counts} | {m for m, _ in depth})
    domains = sorted({d for _, d in counts})
    routing = routing_table(post)
    spec = specialities(post)
    ela = elastic(miners, post, depth)
    measured = [k for k, v in post.items() if v["n"] >= MIN_JUDGED]
    unmeasured_cells = [{"miner": m, "domain": d, "n": post[(m, d)]["n"]}
                        for (m, d) in sorted(post) if post[(m, d)]["n"] < MIN_JUDGED]
    unmeasured: dict[str, Any] = {k: v for k, v in note.items() if v != "READ"}
    if not judged:
        unmeasured["judged_record"] = "no judged candidate on either evidence path"
    if not ledger:
        unmeasured["gate_depth"] = ("the verdict ledger is empty, so no cell has a gate depth: "
                                    "`valuable` collapses to `passed` and says so")
    if unmeasured_cells:
        unmeasured["cells_below_min_judged"] = {
            "n": len(unmeasured_cells), "min_judged": MIN_JUDGED,
            "why": "a posterior on fewer than the floor is the prior wearing a number",
            "sample": unmeasured_cells[:15]}
    joins = Counter()
    for v in counts.values():
        joins.update(v["join"])
    return {
        "at": at.isoformat(timespec="seconds"),
        "n_miners": len(miners), "n_domains": len(domains),
        "measured_cells": len(measured), "n_cells": len(post),
        "evidence": {
            "judged_basis": basis, "queue_basis": queue_basis,
            "n_judged_rows": len(judged), "n_queue_rows": len(queue),
            "registry": reg_note,
            "median_gate_depth": median_depth,
            "median_gate": (GATE_ORDER[int(median_depth)] if 0 <= int(median_depth)
                            < len(GATE_ORDER) else None),
            "depth_join": dict(joins),
            "depth_join_rule": ("exact cell id first, then the (symbol, family) median depth, "
                                "then none. A coarse join attributes a family's typical death to "
                                "every miner that proposed it -- counted here, never hidden."),
            "generator_yields": [
                {k: r.get(k) for k in ("generator", "generated", "judged", "survivors",
                                       "independent_survivors", "yield")}
                for r in yields][:20],
        },
        "definition": {
            "valuable": ("judged AND (passed OR terminal gate depth >= the median gate depth "
                         f"over judged verdicts, today {median_depth})"),
            "posterior": "Beta(0.5 + valuable, 0.5 + judged - valuable), Jeffreys",
            "min_judged": MIN_JUDGED,
            "ci": f"{CI[0]}-{CI[1]}% of {DRAWS} posterior draws, seed {SEED}",
            "speciality": "posterior mean exceeds the miner's own mean over its measured domains "
                          "by more than that cell's posterior SD",
        },
        "routing_top": routing,
        "specialities": spec,
        "elastic": ela,
        "unmeasured": unmeasured,
        "rule": ("the organisation specialises by measured value per miner per domain; every "
                 "department stays on, excess compute follows the hottest queue"),
    }


def contract(doc: dict[str, Any]) -> dict[str, Any]:
    """The file research_departments and the residents read. Narrow on purpose."""
    return {
        "at": doc["at"],
        "routing": {d: [{"miner": r["miner"], "p": r["p"], "ci": r["ci"], "n": r["n"]}
                        for r in rows] for d, rows in doc["routing_top"].items()},
        "specialities": {m: [h["domain"] for h in rows]
                         for m, rows in doc["specialities"].items()},
        "elastic": {m: {"floor": v["floor"], "suggested_share": v["suggested_share"],
                        "heat": v["heat"]} for m, v in doc["elastic"].items()},
        "min_judged": MIN_JUDGED, "floor_budget": FLOOR_BUDGET,
        "writer": "desks/mt5/research/miner_specialisation.py",
        "report": _rel(OUT),
        "rule": doc["rule"],
        "reading": ("a domain absent from `routing` is UNMEASURED and must not be read as 'no "
                    "miner is good at it'; `floor` is guaranteed and `suggested_share` is the "
                    "elastic ask"),
    }


def _atomic_write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
    return path


def write(doc: dict[str, Any], report: Path | None = None,
          routing: Path | None = None) -> tuple[Path, Path]:
    r = _atomic_write(routing or ROUTING, json.dumps(contract(doc), indent=1, default=str))
    p = _atomic_write(report or OUT, json.dumps(doc, indent=1, default=str))
    return p, r


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="measure and print; write nothing")
    a = ap.parse_args(argv)
    doc = build()
    ev = doc["evidence"]
    print(f"miner specialisation {doc['at']}   {doc['n_miners']} miner(s) x "
          f"{doc['n_domains']} domain(s), {doc['measured_cells']}/{doc['n_cells']} cell(s) "
          f"MEASURED (>= {MIN_JUDGED} judged)")
    print(f"  evidence: {ev['judged_basis']} ({ev['n_judged_rows']} judged), queue "
          f"{ev['queue_basis']} ({ev['n_queue_rows']}), median gate "
          f"{ev['median_gate']} @ {ev['median_gate_depth']}, joins {ev['depth_join']}")
    for dom, rows in list(doc["routing_top"].items())[:10]:
        best = rows[0]
        print(f"  {dom:<28} {best['miner']:<18} p={best['p']:.3f} "
              f"ci={best['ci']} n={best['n']}")
    for miner, rows in doc["specialities"].items():
        print(f"  speciality  {miner:<18} " + ", ".join(
            f"{h['domain']} (+{h['excess']:.3f})" for h in rows[:3]))
    for m, v in doc["elastic"].items():
        print(f"  elastic     {m:<18} floor {v['floor']:.4f} -> {v['suggested_share']:.4f} "
              f"(heat {v['heat']}, {v['basis']})")
    if a.dry_run:
        print("  --dry-run: nothing written")
        return 0
    p, r = write(doc)
    print(f"-> {p}\n-> {r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
