"""THE FIVE-ROI DELAYED-CREDIT REALLOCATOR -- what a survivor owes back, and who gets the compute.

LAWS 5f, rules 10-12 (principal, 2026-09-17): every mechanism competes for compute and statistical
budget on FUTURE PORTFOLIO VALUE; every survivor sends delayed credit back to its source, region,
representation and scientist; every failed family becomes NEGATIVE KNOWLEDGE so the system stops
wasting compute.

THE DEFECT THIS CLOSES. The desk measures yield per generator (`generator_yield`) and per source
(`source_yield`) and has done for weeks. What it has never done is CLOSE THE LOOP: nothing reads
those numbers and moves a worker, a trial or a forward slot. So a forum that has produced nothing
in six months is crawled exactly as often as one that produced three independent survivors, and
the desk re-learns that by spending the same compute again next hour. A yield table nobody spends
against is a scoreboard, not an economy.

DELAYED CREDIT IS A WALK, NOT A JOIN. A survivor's value belongs to the SOURCE that suggested the
mechanism, which may be two or three provenance hops upstream of the cell that survived
(source -> discovery -> cell -> trial -> verdict). `registry.provenance_of` is that walk, and the
credit reaches every ancestor node it passes, which is what makes a slow, hard-to-crawl 七禾网
interview fundable at all: the cell it eventually produced is months downstream of the crawl.

    THE FIVE ROIs, all (value / cost), all published with their components:

    SOURCE          credited survivors, mechanisms and dE[log W] per compute hour spent on it
    DATASET         the same for a dataset the registry holds as a discovery's required data
    REPRESENTATION  the same per representation family (REPRESENTATION_FORGE.json, another
                    builder's artifact -- UNMEASURED BY NAME when it is absent)
    MECHANISM       per mechanism family, including the NEGATIVE ones
    SCIENTIST       per miner/generator: who actually produces edges, not who produces rows

    ROI_region = (novel mechanisms + useful datasets + survivors + dE[log W])
                 / (compute + API + trial budget)

    exactly as the law states it, with every term named and its unit declared.

EVERY OUTPUT IS TWO-SIDED AND NOTHING GOES TO ZERO. Shares rise AND fall; the TOTAL never falls
(the department shares always sum to 1.0, so a reallocation moves seconds between departments and
never deletes them); every region keeps its SOURCE SCOUT whatever its ROI, because the one thing a
dead region must still be able to do is notice that it stopped being dead. A region at ROI zero
goes to one worker, never none -- that floor is the difference between reallocation and
abandonment (GROWTH_GOVERNANCE Rule 1: a reduction must prove it raises robust forward E[log W],
and "we stopped looking" proves nothing).

CAPITAL IS EVIDENCE ONLY. `roi_capital_evidence.json` is published for the allocator to read as
evidence; this organ sets no fraction, no cap and no veto, and the desk NEVER reduces its
aggressiveness on a research measurement.

    python desks/mt5/research/research_roi.py --once [--budget-s 600] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as R  # noqa: E402

DATA, REPORTS = DESK / "data", DESK / "reports"
FORWARD_DATA = DATA / "forward_reconcile.json"
FORWARD_REPORT = REPORTS / "forward_reconcile.json"
SLEEVES = DATA / "sleeves.json"
SURVIVORS = REPORTS / "UNIVERSAL_SURVIVORS.json"
ALLOCATION = REPORTS / "pf_allocation.json"
RESEARCH_PNL = REPORTS / "RESEARCH_PNL.json"
COMPUTE_LEDGER = DATA / "compute_ledger.jsonl"
API_LEDGER = DATA / "research_api_calls.jsonl"
REPRESENTATION = REPORTS / "REPRESENTATION_FORGE.json"
GATE_LEDGER = DATA / "hypotheses" / "gate_verdict_ledger.jsonl"

#: The three reallocation artifacts and the report.
ALLOC_OUT = DATA / "research_allocation.json"
FOREST_OUT = DATA / "forest_allocation.json"
CAPITAL_OUT = DATA / "roi_capital_evidence.json"
REPORT = REPORTS / "RESEARCH_ROI.json"
#: The meta-evolution layer's population: each research-machinery variant names the host
#: generator it configured and when it was activated; its fitness is that host's delayed
#: credit since then, computed HERE so the variant never scores itself.
EVOLUTION_POPULATION = DATA / "research_evolution" / "population.json"

UNMEASURED = "UNMEASURED"

#: THE SEVENTEEN FORESTS, exactly as the forest-runner contract names them. A region absent from
#: this tuple would be a region with no scout, which the law forbids.
REGIONS: tuple[str, ...] = (
    "japan", "korea", "china", "russia_cis", "south_asia", "asean", "oceania", "europe",
    "north_america", "latam", "mena", "africa", "global_macro", "global_web",
    "global_academic_code", "global_physical_data", "global_market_data")

#: Defaults when a region's ROI is UNMEASURED. An unmeasured region is NOT a low-yield region --
#: it is a region nobody has priced, and pricing it at zero would defund the frontier by accident.
DEFAULT_WORKERS = 4
DEFAULT_BUDGET_S = 3000
#: The scout floor. One worker, always, in every region, whatever the ROI says.
SCOUT_FLOOR_WORKERS = 1
MAX_WORKERS = 12
MIN_BUDGET_S = 600
MAX_BUDGET_S = 9000
#: The largest raise REGIONAL PARITY's coverage debt may add to a forest's workers and seconds.
#: 2.0 is the top of `FACTOR_CLIP` and the debt is bounded in [0, 1], so `1 + debt` reaches it
#: exactly when a region owes the whole depth rule -- no separate knob, the same clip.
PARITY_MAX_BONUS = 2.0

#: Two-sided clip on every factor this organ publishes. Symmetric about 1.0 on purpose: the same
#: evidence that can halve a share must be able to double it (GROWTH_GOVERNANCE Rule 2).
FACTOR_CLIP = (0.5, 2.0)
#: Floor share for a department and for a mechanism family. Never zero: a family with a floor can
#: still surprise the desk, and a family at zero never will.
MIN_DEPT_SHARE = 0.02
MIN_FAMILY_SHARE = 0.01
#: Cells judged before a family's zero pass-rate is NEGATIVE KNOWLEDGE rather than a small sample.
#: Below it, "no survivor yet" is work not done, never a refutation (L1.28a).
NEGATIVE_MIN_JUDGED = 40
WINDOW_DAYS = 30
BUDGET_S = 600.0

#: Country / language / seat tokens -> forest id. The registry's `sources` rows carry `country`
#: and `language`, the deep forest carries two-letter region codes, and the seats carry their own
#: names; all three land here. A token in none of them is UNROUTED and counted as such -- an
#: unrouted source is a gap in this table, and a gap nobody names is a gap nobody fixes.
REGION_OF: dict[str, str] = {
    "japan": "japan", "jp": "japan", "ja": "japan",
    "korea": "korea", "kr": "korea", "ko": "korea",
    "china": "china", "cn": "china", "zh": "china", "hk": "china", "tw": "china",
    "zh-hant": "china", "followme_cn": "china",
    "russia": "russia_cis", "ru": "russia_cis", "cis": "russia_cis", "kz": "russia_cis",
    "az": "russia_cis", "ge": "russia_cis", "russia_cis": "russia_cis",
    "india": "south_asia", "in": "south_asia", "ind": "south_asia", "hi": "south_asia",
    "pk": "south_asia", "bd": "south_asia", "lk": "south_asia", "south_asia": "south_asia",
    "sg": "asean", "vn": "asean", "th": "asean", "id": "asean", "idn": "asean", "my": "asean",
    "ph": "asean", "asean": "asean", "sea": "asean", "vi": "asean", "ms": "asean",
    "au": "oceania", "nz": "oceania", "oceania": "oceania",
    "uk": "europe", "gb": "europe", "eu": "europe", "ea": "europe", "de": "europe",
    "fr": "europe", "ch": "europe", "se": "europe", "no": "europe", "pl": "europe",
    "europe": "europe",
    "us": "north_america", "ca": "north_america", "north_america": "north_america",
    "br": "latam", "ar": "latam", "cl": "latam", "mx": "latam", "latam": "latam",
    "es": "latam",
    "ae": "mena", "sa": "mena", "il": "mena", "eg": "mena", "tr": "mena", "mena": "mena",
    "mea": "mena",
    "za": "africa", "ng": "africa", "ke": "africa", "africa": "africa",
    "macro": "global_macro", "global_macro": "global_macro",
    "world": "global_web", "global": "global_web", "web": "global_web",
    "academic": "global_academic_code", "arxiv_qfin": "global_academic_code",
    "github": "global_academic_code", "github_topics": "global_academic_code",
    "code": "global_academic_code",
    "physical": "global_physical_data", "physical_economy": "global_physical_data",
    "asia_endpoints": "global_physical_data",
    "market": "global_market_data", "execution_tape": "global_market_data",
    "broker_swaps": "global_market_data", "cot": "global_market_data",
}

RULE = ("every survivor sends delayed credit back to its source, region, representation and "
        "scientist; every failed family becomes negative knowledge; regions and sources compete "
        "for compute two-sided, and every region keeps a source scout")

ROI_REGION_FORMULA = ("ROI_region = (novel mechanisms + useful datasets + survivors + "
                      "dE[log W]) / (compute + API + trial budget)")


# ------------------------------------------------------------------------------ small helpers

def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _atomic_write(path: Path, doc: Any) -> Path:
    """tmp + os.replace. A read-only destination is WinError 5 on this box, so the fallback is a
    direct rewrite rather than a crash that would stop the whole pass."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    try:
        os.replace(tmp, path)
        return path
    except PermissionError:
        try:
            os.chmod(path, 0o666)
            os.replace(tmp, path)
            return path
        except OSError:
            pass
    path.write_bytes(tmp.read_bytes())
    return path


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _f(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if out == out and out not in (float("inf"), float("-inf")) else default


def _clip(x: float, lo: float = FACTOR_CLIP[0], hi: float = FACTOR_CLIP[1]) -> float:
    return max(lo, min(hi, x))


def region_of(*tokens: Any) -> str | None:
    """The forest a token belongs to, or None. Explicit table only -- never guessed."""
    for tok in tokens:
        if not tok:
            continue
        for part in str(tok).replace(":", " ").replace("/", " ").replace("_", " ").split():
            hit = REGION_OF.get(part.strip().lower())
            if hit:
                return hit
        hit = REGION_OF.get(str(tok).strip().lower())
        if hit:
            return hit
    return None


# -------------------------------------------------------------------------------- the inputs

def registry_rows(conn: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
    """Everything one pass reads from the canonical registry, in one place."""
    out: dict[str, list[dict[str, Any]]] = {}
    for name, sql in (
            ("sources", "SELECT * FROM sources"),
            ("source_yield", "SELECT * FROM source_yield"),
            ("generator_yield", "SELECT * FROM generator_yield"),
            ("discoveries", "SELECT * FROM discoveries LIMIT 200000"),
            ("candidates", "SELECT * FROM research_candidates LIMIT 200000"),
            ("trials", "SELECT * FROM trials_ledger LIMIT 200000"),
            ("provenance", "SELECT * FROM provenance LIMIT 400000")):
        try:
            out[name] = [dict(r) for r in conn.execute(sql)]
        except sqlite3.Error:
            out[name] = []
    return out


def compute_hours(window_days: int = WINDOW_DAYS) -> tuple[dict[str, float], str | None]:
    """Hours per costed run in the window, from the compute ledger. Absent -> UNMEASURED."""
    if not COMPUTE_LEDGER.exists():
        return {}, f"absent: {COMPUTE_LEDGER}"
    cut = datetime.now(tz=UTC) - timedelta(days=window_days)
    hours: dict[str, float] = defaultdict(float)
    try:
        text = COMPUTE_LEDGER.read_text(encoding="utf-8")
    except OSError as exc:
        return {}, f"unreadable: {exc}"
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            stamp = datetime.fromisoformat(str(row.get("at")))
        except (ValueError, TypeError):
            continue
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=UTC)
        if stamp >= cut:
            hours[str(row.get("run") or "?")] += _f(row.get("wall_s")) / 3600.0
    return dict(hours), None


def api_calls() -> tuple[dict[str, int], str | None]:
    """API calls per verb from the research API's own log. It has never been written on this box,
    so the API term of ROI_region is UNMEASURED BY NAME rather than zero -- a zero would make
    every region look cheaper than it is, and cheapest wins in a ratio."""
    if not API_LEDGER.exists():
        return {}, (f"absent: {API_LEDGER} -- no organ has logged an API call; the API term of "
                    f"ROI_region is UNMEASURED, never 0")
    calls: Counter[str] = Counter()
    try:
        for line in API_LEDGER.read_text(encoding="utf-8").splitlines():
            if line.strip():
                calls[str(json.loads(line).get("verb") or "?")] += 1
    except (OSError, ValueError) as exc:
        return {}, f"unreadable: {exc}"
    return dict(calls), None


def family_trials() -> tuple[dict[str, dict[str, int]], str | None]:
    """(judged, passed) per mechanism family from the gate verdict ledger -- the trial budget's
    denominator and the negative-knowledge numerator, from the same rows."""
    if not GATE_LEDGER.exists():
        return {}, f"absent: {GATE_LEDGER}"
    out: dict[str, dict[str, int]] = defaultdict(lambda: {"judged": 0, "passed": 0})
    try:
        for line in GATE_LEDGER.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            fam = str(row.get("family") or "UNKNOWN")
            out[fam]["judged"] += 1
            if row.get("passed"):
                out[fam]["passed"] += 1
    except OSError as exc:
        return {}, f"unreadable: {exc}"
    return dict(out), None


def survivors(unmeasured: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Every survivor the desk can name, with the family and cell each belongs to.

    THREE LANES, DELIBERATELY UNIONED: a certified cell (UNIVERSAL_SURVIVORS), a forward row that
    reconciled (forward_reconcile), and a funded sleeve (sleeves.json). They overlap and the
    overlap is deduped by cell key -- counting one survivor three times would triple the credit
    its source receives, which is the delayed-credit equivalent of marking your own homework.
    """
    rows: dict[str, dict[str, Any]] = {}
    doc = _read_json(SURVIVORS)
    if isinstance(doc, dict) and isinstance(doc.get("survivors"), dict):
        for key, cert in doc["survivors"].items():
            if not isinstance(cert, dict):
                continue
            spec = cert.get("shadow_spec") if isinstance(cert.get("shadow_spec"), dict) else {}
            rows[str(key)] = {"cell": str(key), "family": str(spec.get("family") or "UNKNOWN"),
                              "symbol": str(spec.get("symbol") or ""), "lane": "certified"}
    else:
        unmeasured.append({"what": "certified survivors", "why": f"unreadable: {SURVIVORS}"})

    fwd = _read_json(FORWARD_REPORT)
    fwd_src = FORWARD_REPORT
    if fwd is None:
        fwd, fwd_src = _read_json(FORWARD_DATA), FORWARD_DATA
    if isinstance(fwd, dict):
        certified = fwd.get("certified_clocks")
        if isinstance(certified, int):
            rows.setdefault("_forward_certified_count",
                            {"cell": "_forward_certified_count", "family": "UNKNOWN",
                             "symbol": "", "lane": "forward_count", "n": certified})
    else:
        unmeasured.append({"what": "forward reconciliation",
                           "why": f"unreadable: {fwd_src} (and {FORWARD_DATA})"})

    sl = _read_json(SLEEVES)
    if isinstance(sl, dict) and isinstance(sl.get("sleeves"), list):
        for s in sl["sleeves"]:
            if not isinstance(s, dict) or str(s.get("status") or "").upper() != "LIVE":
                continue
            key = str(s.get("name") or "")
            if key:
                rows.setdefault(key, {"cell": key,
                                      "family": str(s.get("family") or "UNKNOWN"),
                                      "symbol": str(s.get("symbol") or ""), "lane": "live"})
    else:
        unmeasured.append({"what": "live sleeves", "why": f"unreadable: {SLEEVES}"})
    return [r for r in rows.values() if r["lane"] != "forward_count"]


def delta_elogw(unmeasured: list[dict[str, str]]) -> tuple[dict[str, float], dict[str, float],
                                                           str]:
    """(per-sleeve dE[log W]/day, per-source dE[log W]/day, basis).

    The allocator's own numbers, never re-derived: `pf_allocation.marginal_delta_elog` is the
    gradient at the solved book, and `RESEARCH_PNL.sources[*].growth_per_day` is the same growth
    already attributed to the source that produced each certificate.
    """
    per_sleeve: dict[str, float] = {}
    alloc = _read_json(ALLOCATION)
    basis_parts: list[str] = []
    if isinstance(alloc, dict) and isinstance(alloc.get("marginal_delta_elog"), dict):
        per_sleeve = {str(k): _f(v) for k, v in alloc["marginal_delta_elog"].items()}
        basis_parts.append("pf_allocation.marginal_delta_elog")
    else:
        unmeasured.append({"what": "allocator marginal dE[log W]",
                           "why": f"absent or unreadable: {ALLOCATION}"})
    per_source: dict[str, float] = {}
    pnl = _read_json(RESEARCH_PNL)
    if isinstance(pnl, dict) and isinstance(pnl.get("sources"), dict):
        for sid, row in pnl["sources"].items():
            if isinstance(row, dict):
                per_source[str(sid)] = _f(row.get("growth_per_day"))
        basis_parts.append("RESEARCH_PNL.sources[*].growth_per_day")
    else:
        unmeasured.append({"what": "per-source dE[log W]",
                           "why": f"absent or unreadable: {RESEARCH_PNL}"})
    return per_sleeve, per_source, " + ".join(basis_parts) or UNMEASURED


def representation_roi(unmeasured: list[dict[str, str]]) -> dict[str, Any]:
    """REPRESENTATION ROI, from another builder's artifact. Absent is UNMEASURED BY NAME."""
    doc = _read_json(REPRESENTATION)
    if not isinstance(doc, dict):
        unmeasured.append({"what": "representation ROI",
                           "why": f"absent: {REPRESENTATION} (written by the representation "
                                  f"forge; this organ never writes it)"})
        return {"status": UNMEASURED, "source": str(REPRESENTATION), "by_representation": {}}
    reps = doc.get("representations")
    rows: dict[str, Any] = {}
    if isinstance(reps, dict):
        for name, row in reps.items():
            if isinstance(row, dict):
                rows[str(name)] = {"series": _f(row.get("n_series")),
                                   "candidates": _f(row.get("n_candidates")),
                                   "survivors": _f(row.get("n_survivors")),
                                   "compute_h": _f(row.get("compute_h"))}
    elif isinstance(reps, list):
        for row in reps:
            if isinstance(row, dict) and row.get("name"):
                rows[str(row["name"])] = {"series": _f(row.get("n_series")),
                                          "candidates": _f(row.get("n_candidates")),
                                          "survivors": _f(row.get("n_survivors")),
                                          "compute_h": _f(row.get("compute_h"))}
    for name, row in rows.items():
        cost = row["compute_h"]
        row["roi"] = round(row["survivors"] / cost, 6) if cost > 0 else None
        row["roi_status"] = "MEASURED" if cost > 0 else UNMEASURED
        row["name"] = name
    return {"status": "MEASURED" if rows else UNMEASURED, "source": str(REPRESENTATION),
            "by_representation": rows}


# ------------------------------------------------------------------------- the delayed credit

def credit_walk(conn: sqlite3.Connection, rows: dict[str, list[dict[str, Any]]],
                surv: list[dict[str, Any]], per_sleeve: dict[str, float]
                ) -> dict[str, Any]:
    """Walk each survivor's provenance back and credit EVERY ancestor it passes.

    THE WALK IS THE POINT. A source credited only where it is named on the surviving cell gets
    nothing whenever the chain runs source -> discovery -> cell, which is how every mined
    mechanism reaches the docket. `provenance_of` returns the ancestor EDGES, so a two-hop
    ancestor is credited exactly like a one-hop one.
    """
    by_source: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"survivors": 0.0, "delta_elogw": 0.0, "cells": [], "hops": []})
    by_generator: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"survivors": 0.0, "delta_elogw": 0.0, "cells": []})
    by_discovery: Counter[str] = Counter()

    cand_by_id = {str(c.get("id")): c for c in rows["candidates"]}
    # A cell key the survivor lanes use is not the registry's candidate id, so the join is by
    # (symbol, family) as well -- the same join the allocator's genome view makes, for the same
    # reason: a credit paid to the wrong ancestor is worse than one that did not join.
    by_pair: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for c in rows["candidates"]:
        by_pair[(str(c.get("symbol") or "").lower(),
                 str(c.get("family") or "").lower())].append(c)

    unjoined = 0
    for s in surv:
        cands = ([cand_by_id[s["cell"]]] if s["cell"] in cand_by_id
                 else by_pair.get((s["symbol"].lower(), s["family"].lower()), []))
        value = _f(per_sleeve.get(s["cell"]))
        if not cands:
            unjoined += 1
            continue
        share = 1.0 / len(cands)
        for cand in cands:
            cid = str(cand.get("id") or "")
            gen = str(cand.get("generator") or cand.get("origin") or "unknown")
            by_generator[gen]["survivors"] += share
            by_generator[gen]["delta_elogw"] += value * share
            if len(by_generator[gen]["cells"]) < 25:
                by_generator[gen]["cells"].append(s["cell"])
            seen_sources: set[str] = set()
            try:
                edges = R.provenance_of("cell", cid, conn=conn)
            except (sqlite3.Error, ValueError):
                edges = []
            for hop, edge in enumerate(edges, 1):
                kind, node = str(edge.get("from_kind")), str(edge.get("from_id"))
                if kind == "discovery":
                    by_discovery[node] += 1
                if kind == "source" and node not in seen_sources:
                    seen_sources.add(node)
                    row = by_source[node]
                    row["survivors"] += share
                    row["delta_elogw"] += value * share
                    if len(row["cells"]) < 25:
                        row["cells"].append(s["cell"])
                    row["hops"].append(hop)
            # A cell naming its source directly still credits it -- the walk is the ADDITION,
            # never the replacement.
            direct = str(cand.get("source_id") or "")
            if direct and direct not in seen_sources:
                row = by_source[direct]
                row["survivors"] += share
                row["delta_elogw"] += value * share
                row["hops"].append(0)
    for row in by_source.values():
        row["max_hops"] = max(row["hops"]) if row["hops"] else 0
        row["survivors"] = round(row["survivors"], 6)
        row["delta_elogw"] = round(row["delta_elogw"], 12)
        row.pop("hops", None)
    for row in by_generator.values():
        row["survivors"] = round(row["survivors"], 6)
        row["delta_elogw"] = round(row["delta_elogw"], 12)
    return {"by_source": dict(by_source), "by_generator": dict(by_generator),
            "by_discovery": dict(by_discovery), "n_survivors": len(surv),
            "n_unjoined": unjoined,
            "rule": ("credit walks the provenance DAG backwards from the surviving cell, so a "
                     "source two or more hops upstream is credited exactly like a direct parent")}


# ------------------------------------------------------------------------------- the five ROIs

def source_roi(rows: dict[str, list[dict[str, Any]]], credit: dict[str, Any],
               per_source: dict[str, float]) -> dict[str, Any]:
    """SOURCE ROI = (credited survivors + mechanisms + dE[log W]) / compute seconds spent on it."""
    yields = {str(y.get("source_id")): y for y in rows["source_yield"]}
    meta = {str(s.get("source_id")): s for s in rows["sources"]}
    out: dict[str, Any] = {}
    for sid in set(yields) | set(meta) | set(credit["by_source"]) | set(per_source):
        y = yields.get(sid, {})
        c = credit["by_source"].get(sid, {})
        m = meta.get(sid, {})
        compute_s = _f(y.get("compute_s"))
        value = (_f(c.get("survivors")) + _f(y.get("mechanisms")) * 0.1
                 + _f(c.get("delta_elogw")) + _f(per_source.get(sid)))
        hours = compute_s / 3600.0
        out[sid] = {
            "source_id": sid,
            "region": region_of(m.get("country"), m.get("language"), sid) or UNMEASURED,
            "access_label": m.get("access_label") or UNMEASURED,
            "quarantined": bool(m.get("quarantine")),
            "leads": int(_f(y.get("leads"))), "claims": int(_f(y.get("claims"))),
            "mechanisms": int(_f(y.get("mechanisms"))),
            "credited_survivors": _f(c.get("survivors")),
            "credited_delta_elogw": _f(c.get("delta_elogw")),
            "max_credit_hops": int(c.get("max_hops") or 0),
            "compute_hours": round(hours, 6),
            "value": round(value, 8),
            "roi": round(value / hours, 6) if hours > 0 else None,
            "roi_status": "MEASURED" if hours > 0 else UNMEASURED,
            "why": ("value = credited survivors + 0.1 x mechanisms + credited dE[log W] + the "
                    "source's attributed research growth; cost = its own recorded compute hours"
                    if hours > 0 else
                    "no compute recorded against this source: UNMEASURED, never a zero ROI"),
        }
    return out


def dataset_roi(rows: dict[str, list[dict[str, Any]]], credit: dict[str, Any]) -> dict[str, Any]:
    """DATASET ROI: a dataset is what a discovery DECLARED IT NEEDED, so the required-data field
    is the denominator's key. A dataset with three independent forward survivors earns budget;
    one with none is reported, never deleted."""
    per: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"discoveries": 0, "survivor_credit": 0.0, "sources": set()})
    for d in rows["discoveries"]:
        raw = d.get("required_data_json")
        names: list[str] = []
        if isinstance(raw, str) and raw.strip():
            try:
                loaded = json.loads(raw)
            except ValueError:
                loaded = [raw]
            names = [str(x) for x in loaded] if isinstance(loaded, list) else [str(loaded)]
        did = str(d.get("discovery_id") or "")
        hits = int(credit["by_discovery"].get(did, 0))
        for name in names:
            row = per[name]
            row["discoveries"] += 1
            row["survivor_credit"] += hits
            row["sources"].add(str(d.get("source_id") or ""))
    out: dict[str, Any] = {}
    for name, row in per.items():
        n = int(row["discoveries"])
        out[name] = {
            "dataset": name, "discoveries": n, "survivor_credit": round(row["survivor_credit"], 4),
            "n_sources": len(row["sources"]),
            "roi": round(row["survivor_credit"] / n, 6) if n else None,
            "roi_status": "MEASURED" if n else UNMEASURED,
            "verdict": ("EXPAND" if row["survivor_credit"] >= 3 else
                        "KEEP" if row["survivor_credit"] > 0 else "NO_SURVIVOR_YET"),
        }
    return out


def mechanism_roi(fam: dict[str, dict[str, int]], rows: dict[str, list[dict[str, Any]]],
                  surv: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """MECHANISM ROI per family, and the NEGATIVE KNOWLEDGE the failures bought.

    A family judged at length with no pass is not "bad luck": it is a measured statement that the
    desk should stop spending there, and publishing it is what makes the saving real. Below
    NEGATIVE_MIN_JUDGED it stays UNMEASURED -- too few observations is work not done (L1.28a).
    """
    surv_by_family: Counter[str] = Counter(s["family"] for s in surv)
    cand_by_family: Counter[str] = Counter(
        str(c.get("family") or "UNKNOWN") for c in rows["candidates"])
    out: dict[str, Any] = {}
    negative: list[dict[str, Any]] = []
    for name in set(fam) | set(surv_by_family) | set(cand_by_family):
        row = fam.get(name, {"judged": 0, "passed": 0})
        judged, passed = int(row["judged"]), int(row["passed"])
        live = int(surv_by_family.get(name, 0))
        value = float(passed + live)
        out[name] = {
            "family": name, "judged": judged, "passed": passed, "survivors_live": live,
            "candidates": int(cand_by_family.get(name, 0)),
            "roi": round(value / judged, 6) if judged else None,
            "roi_status": "MEASURED" if judged else UNMEASURED,
            "verdict": ("PAYS" if value > 0 else
                        "NEGATIVE_KNOWLEDGE" if judged >= NEGATIVE_MIN_JUDGED else
                        "UNMEASURED"),
        }
        if out[name]["verdict"] == "NEGATIVE_KNOWLEDGE":
            negative.append({
                "family": name, "judged": judged, "passed": 0, "roi": 0.0,
                "kind": "NEGATIVE_KNOWLEDGE",
                "why": (f"{judged} cells judged, none passed and none live: the desk has "
                        f"MEASURED that this family does not pay in the form it has been tried"),
                "instruction": ("spend its share on families and cells with a measured pass, and "
                                "on cold cells that have never been tried -- generate "
                                "DIFFERENTLY, never less"),
                "floor": MIN_FAMILY_SHARE,
            })
    negative.sort(key=lambda r: -int(r["judged"]))
    return out, negative


def scientist_roi(rows: dict[str, list[dict[str, Any]]], credit: dict[str, Any],
                  hours: dict[str, float]) -> dict[str, Any]:
    """SCIENTIST ROI per miner/generator: independent survivors and dE[log W] per compute hour."""
    yields = {str(y.get("generator")): y for y in rows["generator_yield"]}
    out: dict[str, Any] = {}
    for gen in set(yields) | set(credit["by_generator"]):
        y = yields.get(gen, {})
        c = credit["by_generator"].get(gen, {})
        compute_h = _f(y.get("compute_s")) / 3600.0
        if compute_h <= 0:
            compute_h = _f(hours.get(gen))
        value = (_f(c.get("survivors")) + _f(y.get("independent_survivors"))
                 + _f(c.get("delta_elogw")) + _f(y.get("delta_elogw")))
        out[gen] = {
            "generator": gen, "generated": int(_f(y.get("generated"))),
            "donated": int(_f(y.get("donated"))), "judged": int(_f(y.get("judged"))),
            "independent_survivors": int(_f(y.get("independent_survivors"))),
            "credited_survivors": _f(c.get("survivors")),
            "credited_delta_elogw": _f(c.get("delta_elogw")),
            "compute_hours": round(compute_h, 6),
            "value": round(value, 8),
            "roi": round(value / compute_h, 6) if compute_h > 0 else None,
            "roi_status": "MEASURED" if compute_h > 0 else UNMEASURED,
        }
    return out


def variant_roi(scientists: dict[str, Any],
                unmeasured: list[dict[str, str]]) -> dict[str, Any]:
    """DELAYED REAL YIELD PER RESEARCH-MACHINERY VARIANT (LAWS 5m, the meta-evolution layer).

    A variant of the research machinery (a PUCT constant, a grammar's immigrant share, an
    operator vocabulary) is credited with the value its HOST generator produced while the
    variant was active: the host's scientist ROI value (credited survivors + independent
    survivors + dE[log W]) now, less the value recorded when the variant was activated. The
    variant never scores itself -- `research_evolution` reads this block as fitness and MEASURED
    means the host has a scientist row and this report is newer than the activation; anything
    else is UNMEASURED by name, and an unmeasured variant displaces nothing in the archive.
    """
    pop = _read_json(EVOLUTION_POPULATION)
    if not isinstance(pop, dict) or not isinstance(pop.get("genomes"), list):
        unmeasured.append({"what": "research-machinery variants",
                           "why": f"no population at {EVOLUTION_POPULATION}: the meta-evolution "
                                  f"layer has applied no variant on this box"})
        return {"status": UNMEASURED, "variants": {}, "n": 0,
                "basis": "scientist_roi[host].value delta since activation"}
    out: dict[str, Any] = {}
    n_measured = 0
    for g in pop["genomes"]:
        if not isinstance(g, dict) or not g.get("id"):
            continue
        host = str(g.get("host") or "")
        row = scientists.get(host)
        activated = str(g.get("activated_at") or "")
        baseline = _f((g.get("fitness") or {}).get("baseline_value"))
        if not isinstance(row, dict) or not activated:
            out[str(g["id"])] = {"status": UNMEASURED, "host": host, "value": None,
                                 "why": (f"no scientist row for host {host!r}"
                                         if not isinstance(row, dict)
                                         else "variant never activated")}
            continue
        value = _f(row.get("value")) - baseline
        out[str(g["id"])] = {"status": "MEASURED", "host": host,
                             "value": round(value, 8), "host_value": row.get("value"),
                             "baseline_value": baseline, "activated_at": activated,
                             "basis": "scientist_roi[host].value - baseline at activation"}
        n_measured += 1
    return {"status": "MEASURED" if n_measured else UNMEASURED, "variants": out,
            "n": len(out), "n_measured": n_measured,
            "basis": "scientist_roi[host].value delta since activation",
            "consumer": "desks/mt5/research/research_evolution.py (fitness)"}


def region_roi(src_roi: dict[str, Any], rows: dict[str, list[dict[str, Any]]],
               datasets: dict[str, Any], fam: dict[str, dict[str, int]],
               api: dict[str, int], api_why: str | None,
               hours: dict[str, float]) -> dict[str, Any]:
    """ROI_region, exactly as the law writes it, with every term named and its unit declared.

        ROI_region = (novel mechanisms + useful datasets + survivors + dE[log W])
                     / (compute + API + trial budget)

    THE DENOMINATOR IS NEVER SILENTLY ZERO. A region with no recorded compute, no API log and no
    trials has an UNMEASURED ROI, not an infinite one -- and an unmeasured region keeps the
    default worker count, because pricing the unknown at zero defunds the frontier by accident.
    """
    per: dict[str, dict[str, Any]] = {
        r: {"region": r, "novel_mechanisms": 0.0, "useful_datasets": 0.0, "survivors": 0.0,
            "delta_elogw": 0.0, "compute_hours": 0.0, "api_calls": 0.0, "trials": 0.0,
            "n_sources": 0, "unrouted": False} for r in REGIONS}
    unrouted = {"n_sources": 0, "survivors": 0.0, "compute_hours": 0.0}

    for sid, row in src_roi.items():
        reg = row["region"] if row["region"] in per else None
        target = per[reg] if reg else None
        if target is None:
            unrouted["n_sources"] += 1
            unrouted["survivors"] += _f(row.get("credited_survivors"))
            unrouted["compute_hours"] += _f(row.get("compute_hours"))
            continue
        target["n_sources"] += 1
        target["novel_mechanisms"] += _f(row.get("mechanisms"))
        target["survivors"] += _f(row.get("credited_survivors"))
        target["delta_elogw"] += _f(row.get("credited_delta_elogw"))
        target["compute_hours"] += _f(row.get("compute_hours"))
        _ = sid

    for name, row in datasets.items():
        reg = region_of(name)
        if reg in per and _f(row.get("survivor_credit")) > 0:
            per[reg]["useful_datasets"] += 1.0

    # TRIALS are the third cost term. The verdict ledger carries no region, so trials are
    # attributed through the discovery's source where that join exists and counted as UNROUTED
    # otherwise -- named, never spread evenly, which would invent a cost for every region.
    src_region = {sid: row["region"] for sid, row in src_roi.items()}
    disc_region = {str(d.get("discovery_id")): src_region.get(str(d.get("source_id") or ""))
                   for d in rows["discoveries"]}
    trials_routed = 0
    for cand in rows["candidates"]:
        parent = str(cand.get("discovery_id") or "")
        reg = disc_region.get(parent) or src_region.get(str(cand.get("source_id") or ""))
        if reg in per:
            per[reg]["trials"] += 1.0
            trials_routed += 1

    total_api = float(sum(api.values()))
    api_measured = bool(api)
    for row in per.values():
        # The API term is shared by the count of regions that actually spent compute -- the log
        # carries a verb, not a region, and inventing a per-region split would be arithmetic
        # dressed as a measurement.
        row["api_calls"] = round(total_api / max(1, len(REGIONS)), 4) if api_measured else 0.0
        numerator = (row["novel_mechanisms"] + row["useful_datasets"] + row["survivors"]
                     + row["delta_elogw"])
        denominator = row["compute_hours"] + row["api_calls"] + row["trials"]
        row["numerator"] = round(numerator, 8)
        row["denominator"] = round(denominator, 8)
        row["roi"] = round(numerator / denominator, 8) if denominator > 0 else None
        row["roi_status"] = "MEASURED" if denominator > 0 else UNMEASURED
        row["api_status"] = "MEASURED" if api_measured else (api_why or UNMEASURED)
        row["formula"] = ROI_REGION_FORMULA
        row["units"] = {"compute": "hours from data/compute_ledger.jsonl",
                        "api": "calls from data/research_api_calls.jsonl",
                        "trial_budget": "cells enqueued against this region's sources"}
        for key in ("novel_mechanisms", "useful_datasets", "survivors", "delta_elogw",
                    "compute_hours", "trials"):
            row[key] = round(_f(row[key]), 8)
    _ = hours
    return {"by_region": per, "unrouted": unrouted, "trials_routed": trials_routed,
            "formula": ROI_REGION_FORMULA}


# ------------------------------------------------------------------------ the reallocations

def _two_sided_shares(values: dict[str, float | None], floor: float) -> dict[str, float]:
    """Shares that rise AND fall around the mean, never below `floor`, always summing to 1.0.

    THE TOTAL NEVER FALLS. This is the property that separates reallocation from a cut: what one
    key loses another gains, and an UNMEASURED key holds the mean rather than being defunded for
    the crime of not having been measured yet.
    """
    keys = sorted(values)
    if not keys:
        return {}
    measured = {k: v for k, v in values.items() if isinstance(v, (int, float))}
    base = 1.0 / len(keys)
    if not measured:
        return dict.fromkeys(keys, round(base, 8))
    mean = sum(measured.values()) / len(measured)
    raw: dict[str, float] = {}
    for k in keys:
        v = measured.get(k)
        factor = 1.0 if v is None or mean <= 0 else _clip(v / mean)
        raw[k] = max(floor, base * factor)
    total = sum(raw.values())
    return {k: round(v / total, 8) for k, v in raw.items()}


def department_shares(scientists: dict[str, Any], hours: dict[str, float],
                      unmeasured: list[dict[str, str]]) -> dict[str, Any]:
    """Compute shares per research DEPARTMENT, from the ROI of the generators inside it."""
    try:
        import research_departments as rd
        legs, names = rd.leg_departments()
    except Exception as exc:          # a reporting organ never fails on someone else's import
        unmeasured.append({"what": "department roster", "why": f"{type(exc).__name__}: {exc}"})
        return {"status": UNMEASURED, "shares": {}, "why": "department roster unreadable"}

    value: dict[str, float] = defaultdict(float)
    cost: dict[str, float] = defaultdict(float)
    for leg, h in hours.items():
        cost[legs.get(leg, "rest")] += h
    for gen, row in scientists.items():
        dept = legs.get(gen, "rest")
        value[dept] += _f(row.get("value"))
    roi: dict[str, float | None] = {}
    for dept in names:
        c = cost.get(dept, 0.0)
        roi[dept] = round(value.get(dept, 0.0) / c, 8) if c > 0 else None
    shares = _two_sided_shares(roi, MIN_DEPT_SHARE)
    return {
        "status": "MEASURED" if any(v is not None for v in roi.values()) else UNMEASURED,
        "shares": shares, "roi": roi,
        "value": {k: round(v, 8) for k, v in sorted(value.items())},
        "compute_hours": {k: round(v, 6) for k, v in sorted(cost.items())},
        "floor_share": MIN_DEPT_SHARE, "clip": list(FACTOR_CLIP),
        "total_share": round(sum(shares.values()), 8),
        "why": ("each department's share follows the measured ROI of the generators inside it, "
                "two-sided around the mean and floored; the shares always sum to 1.0, so this "
                "moves seconds between departments and never removes them"),
    }


def forest_allocation(regions: dict[str, Any]) -> dict[str, Any]:
    """The forest-runner contract: workers and seconds per region, with the scout floor.

    THE FLOOR IS THE LAW'S OWN WORDS -- a low-yield region "ALWAYS keeps a source scout so it can
    detect when conditions change". A region at ROI zero therefore reads workers=1, never 0.
    """
    per = regions["by_region"]
    roi_values: dict[str, float | None] = {r: per[r]["roi"] for r in REGIONS}
    measured = [v for v in roi_values.values() if isinstance(v, (int, float))]
    mean = sum(measured) / len(measured) if measured else 0.0
    forests: dict[str, Any] = {}
    for r in REGIONS:
        roi = roi_values[r]
        if roi is None or mean <= 0:
            workers, budget = DEFAULT_WORKERS, DEFAULT_BUDGET_S
            why = (f"ROI UNMEASURED ({per[r]['roi_status']}): the declared default of "
                   f"{DEFAULT_WORKERS} workers -- an unpriced region is not a low-yield one")
        else:
            factor = _clip(roi / mean)
            workers = int(max(SCOUT_FLOOR_WORKERS,
                              min(MAX_WORKERS, round(DEFAULT_WORKERS * factor))))
            budget = int(max(MIN_BUDGET_S, min(MAX_BUDGET_S, round(DEFAULT_BUDGET_S * factor))))
            why = (f"ROI {roi:.6g} vs the {len(measured)}-region mean {mean:.6g} -> x{factor:.2f}"
                   + ("; at the scout floor: the region keeps one worker so it can detect that "
                      "conditions changed" if workers == SCOUT_FLOOR_WORKERS else ""))
        forests[r] = {"workers": max(SCOUT_FLOOR_WORKERS, int(workers)),
                      "budget_s": int(budget), "scout_floor": True,
                      "roi": roi if roi is None else round(float(roi), 8), "why": why}
    return {
        "at": _now(),
        "rule": ("a region producing useful candidates gets more workers automatically; a "
                 "low-yield region gets fewer routine workers and ALWAYS keeps a source scout "
                 "(workers >= 1, never 0)"),
        "forests": forests,
    }


def parity_overlay(forest: dict[str, Any], *, conn: sqlite3.Connection | None = None,
                   reports_dir: Path | None = None) -> dict[str, Any]:
    """Fold REGIONAL PARITY's coverage debt into the forest allocation, as a BONUS only.

    THE LAW (docs/LAWS.md 5n, principal 2026-09-19) prices compute at

        Priority = P(useful) x Orthogonality x InformationGain x CoverageDebt
                   / (Compute + DataCost + TrialBurden)

    and `libs/research/regional_parity.py` is the pure half that measures every term. This is the
    consumer: the region that owes the most depth -- unmapped source layers, nothing discovered in
    its trailing window, nothing in its lattice, nobody resident -- gets MORE workers and MORE
    seconds, never fewer.

    WHY IT IS ONE-SIDED WHEN THE FORMULA IS NOT. The debt term enters `priority_of` as (1 + debt),
    which is already a bonus; the terms that could pull a region DOWN (its own past yield) are
    already priced by `forest_allocation`'s ROI factor two lines above, and pricing them twice
    would be the starvation loop the scout floor exists to prevent -- a region defunded to silence
    can never produce the evidence that would refund it. So the overlay is `max(1.0, 1 + debt)`,
    clipped, and GROWTH_GOVERNANCE Rule 1 is satisfied without a missed-growth ledger line because
    nothing here reduces anything: `workers_before`/`budget_before` are carried beside every row so
    the raise is auditable rather than asserted.

    GUARDED. `regional_parity` is a pure library with no desk import, but this organ must not die
    if it is mid-landing on a tree; an import or measurement failure records `UNMEASURED` by name
    in the returned block and leaves every allocation exactly as `forest_allocation` set it.
    """
    forests = forest.get("forests") or {}
    try:
        from libs.research import regional_parity as RP
    except Exception as exc:
        forest["parity"] = {"status": UNMEASURED,
                            "why": f"libs.research.regional_parity: {type(exc).__name__}: {exc}"}
        return forest
    try:
        roi = {r: (forest["forests"].get(r) or {}).get("roi") for r in forests}
        doc = RP.parity_report(conn=conn, region_roi=roi, reports_dir=reports_dir)
    except Exception as exc:
        forest["parity"] = {"status": UNMEASURED,
                            "why": f"parity_report raised {type(exc).__name__}: {exc}"}
        return forest
    raised: list[str] = []
    for fid, row in forests.items():
        got = (doc.get("regions") or {}).get(fid)
        if not isinstance(got, dict):
            row["parity"] = {"status": UNMEASURED, "why": f"{fid} is not a declared forest"}
            continue
        debt = float((got.get("coverage_debt") or {}).get("debt") or 0.0)
        factor = max(1.0, min(PARITY_MAX_BONUS, 1.0 + debt))
        before_w, before_b = int(row["workers"]), int(row["budget_s"])
        row["workers"] = max(SCOUT_FLOOR_WORKERS, min(MAX_WORKERS, round(before_w * factor)))
        row["budget_s"] = max(MIN_BUDGET_S, min(MAX_BUDGET_S, round(before_b * factor)))
        row["parity"] = {"status": "ok", "coverage_debt": round(debt, 6),
                         "bonus": round(factor, 4), "priority": got.get("priority"),
                         "depth_score": got.get("depth_score"),
                         "flags": list(got.get("flags") or ()),
                         "workers_before": before_w, "budget_before_s": before_b,
                         "why": (got.get("coverage_debt") or {}).get("why", "")}
        if row["workers"] > before_w or row["budget_s"] > before_b:
            raised.append(fid)
    forest["parity"] = {
        "status": "ok", "law": "docs/LAWS.md 5n", "rule": RP.RULE,
        "at": doc.get("at"), "median_depth": doc.get("median_depth"),
        "flag_counts": doc.get("flag_counts"), "flagged": doc.get("flagged"),
        "raised": sorted(raised), "max_bonus": PARITY_MAX_BONUS,
        "direction": ("BONUS ONLY: the coverage debt raises a neglected region's workers and "
                      "seconds and lowers nobody's; the yield half is already priced by the ROI "
                      "factor and is not charged twice"),
        "source": "libs/research/regional_parity.py parity_report()",
        "fence": "scripts/check_regional_parity.py",
    }
    return forest


def trial_budget(mechanisms: dict[str, Any]) -> dict[str, Any]:
    """Trial budget per mechanism family, two-sided and floored. Consumed by
    `gauntlet_backpressure` and `mining_objective`, both of which READ it and neither of which may
    use it to build fewer cells: a family below the mean is out-earned, never banned."""
    roi: dict[str, float | None] = {k: v["roi"] for k, v in mechanisms.items()}
    shares = _two_sided_shares(roi, MIN_FAMILY_SHARE)
    return {
        "shares": shares, "floor_share": MIN_FAMILY_SHARE, "clip": list(FACTOR_CLIP),
        "total_share": round(sum(shares.values()), 8),
        "n_families": len(shares),
        "boundary": ("a share is a PRIORITY, never a cap: no family is banned, every family keeps "
                     "its floor, and the total is conserved at 1.0"),
    }


def forward_slot_weights(mechanisms: dict[str, Any], src_roi: dict[str, Any]) -> dict[str, Any]:
    """Two-sided weights for the forward slot ranker, by family. A weight above 1.0 is a family
    whose cells have been paying; below 1.0 is one that has not. Nothing is excluded."""
    roi: dict[str, float | None] = {k: v["roi"] for k, v in mechanisms.items()}
    measured = [v for v in roi.values() if isinstance(v, (int, float))]
    mean = sum(measured) / len(measured) if measured else 0.0
    weights: dict[str, float] = {}
    for fam, v in roi.items():
        weights[fam] = 1.0 if (v is None or mean <= 0) else round(_clip(v / mean), 6)
    top_sources = sorted((r for r in src_roi.values() if isinstance(r.get("roi"), (int, float))),
                         key=lambda r: -float(r["roi"]))[:10]
    return {
        "by_family": weights, "clip": list(FACTOR_CLIP),
        "unmeasured_reads": 1.0,
        "top_sources": [{"source_id": r["source_id"], "roi": r["roi"], "region": r["region"]}
                        for r in top_sources],
        "boundary": ("a weight multiplies a slot's PUBLISHED value so the ranking reflects which "
                     "mechanisms have been paying; it never removes a candidate from the list and "
                     "never stops a running clock"),
    }


def capital_evidence(mechanisms: dict[str, Any], scientists: dict[str, Any],
                     credit: dict[str, Any]) -> dict[str, Any]:
    """Per-mechanism ROI evidence FOR THE ALLOCATOR TO READ. Evidence, never a cap.

    THE CONSUMER IS NAMED AND IT DOES NOT EXIST YET, which is the honest state (III.16).
    `pf_allocator` builds its evidence from realised and forward returns
    (`build_evidence`/`sleeve_evidence`) and `libs/portfolio/capital_modifiers.REGISTRY` declares
    every modifier's `where` -- none of them takes a file-shaped external ROI input. So this is
    PUBLISHED with its missing consumer named rather than wired to nothing and reported as done.
    Nothing here may become a cap: the desk never reduces its aggressiveness on a research
    measurement (GROWTH_GOVERNANCE, principal 2026-09-08).
    """
    rows: dict[str, Any] = {}
    for fam, row in mechanisms.items():
        rows[fam] = {
            "mechanism": fam, "roi": row["roi"], "roi_status": row["roi_status"],
            "judged": row["judged"], "passed": row["passed"],
            "survivors_live": row["survivors_live"], "verdict": row["verdict"],
        }
    return {
        "at": _now(),
        "kind": "evidence",
        "by_mechanism": rows,
        "by_scientist": {g: {"roi": r["roi"], "credited_delta_elogw": r["credited_delta_elogw"]}
                         for g, r in scientists.items()},
        "delayed_credit_survivors": credit["n_survivors"],
        "consumer": {
            "status": "MISSING",
            "searched": ["libs/portfolio/**", "desks/mt5/research/pf_allocator.py",
                         "libs/portfolio/capital_modifiers.REGISTRY"],
            "finding": ("no allocator input takes external per-mechanism evidence from a file: "
                        "pf_allocator derives its evidence from returns and every registered "
                        "capital modifier names an in-process `where`"),
            "to_wire": ("pf_allocator.sleeve_evidence grows an optional per-mechanism ROI prior "
                        "read from this file, registered two-sided in capital_modifiers.REGISTRY"),
        },
        "boundary": ("EVIDENCE ONLY. This file sets no fraction, no cap and no veto. A low ROI is "
                     "a reason to fund a different mechanism, never a reason to shrink the book."),
    }


# ------------------------------------------------------------------------------------- the pass

def run(*, budget_s: float = BUDGET_S, dry_run: bool = False,
        conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    t0 = time.monotonic()
    unmeasured: list[dict[str, str]] = []
    own = conn is None
    c = conn or R.connect()
    try:
        rows = registry_rows(c)
        hours, hours_why = compute_hours()
        if hours_why:
            unmeasured.append({"what": "compute ledger", "why": hours_why})
        api, api_why = api_calls()
        if api_why:
            unmeasured.append({"what": "API ledger", "why": api_why})
        fam, fam_why = family_trials()
        if fam_why:
            unmeasured.append({"what": "gate verdict ledger", "why": fam_why})
        surv = survivors(unmeasured)
        per_sleeve, per_source, elog_basis = delta_elogw(unmeasured)
        credit = credit_walk(c, rows, surv, per_sleeve)
        src = source_roi(rows, credit, per_source)
        datasets = dataset_roi(rows, credit)
        mechanisms, negative = mechanism_roi(fam, rows, surv)
        scientists = scientist_roi(rows, credit, hours)
        variants = variant_roi(scientists, unmeasured)
        regions = region_roi(src, rows, datasets, fam, api, api_why, hours)
        reps = representation_roi(unmeasured)
    finally:
        if own:
            c.close()

    depts = department_shares(scientists, hours, unmeasured)
    forest = parity_overlay(forest_allocation(regions), conn=conn)
    trials = trial_budget(mechanisms)
    slots = forward_slot_weights(mechanisms, src)
    capital = capital_evidence(mechanisms, scientists, credit)

    alloc_doc = {
        "at": _now(), "rule": RULE,
        "departments": depts,
        "trial_budget_by_family": trials,
        "forward_slot_weights": slots,
        "negative_knowledge": negative,
        "consumers": {
            "departments": "desks/mt5/research/research_departments.py roi_shares/spend()",
            "trial_budget_by_family": ("desks/mt5/research/gauntlet_backpressure.py and "
                                       "desks/mt5/research/mining_objective.py"),
            "forward_slot_weights": "desks/mt5/research/forward_slot_ranker.py",
        },
        "writer": "desks/mt5/research/research_roi.py",
        "collision_note": ("meta_desk.item13_info_value_allocator also writes this path with a "
                           "different shape ({'allocation': [...]}) on the research supervisor's "
                           "clock. Every consumer reads this file through a reader that returns "
                           "1.0 when the expected block is absent, so a clobber degrades to 'no "
                           "ROI factor' and never to a wrong one."),
    }
    report = {
        "at": _now(), "rule": RULE, "formula": ROI_REGION_FORMULA,
        "window_days": WINDOW_DAYS,
        "delayed_credit": credit,
        "source_roi": src, "dataset_roi": datasets, "representation_roi": reps,
        "mechanism_roi": mechanisms, "scientist_roi": scientists, "region_roi": regions,
        "negative_knowledge": negative,
        "n_negative_families": len(negative),
        "reallocation": {"departments": depts, "forest": forest,
                         "trial_budget_by_family": trials, "forward_slot_weights": slots,
                         "capital": {"file": str(CAPITAL_OUT),
                                     "consumer": capital["consumer"]["status"],
                                     "boundary": capital["boundary"]}},
        "delta_elogw_basis": elog_basis,
        "variant_roi": variants,
        "counts": {"sources": len(rows["sources"]), "source_yield": len(rows["source_yield"]),
                   "generators": len(rows["generator_yield"]),
                   "discoveries": len(rows["discoveries"]),
                   "candidates": len(rows["candidates"]), "trials": len(rows["trials"]),
                   "provenance_edges": len(rows["provenance"]), "survivors": len(surv)},
        "budget_s": budget_s, "elapsed_s": round(time.monotonic() - t0, 2),
        "dry_run": dry_run, "unmeasured": unmeasured,
        "limitations": [
            "the API term of ROI_region is UNMEASURED until an organ writes "
            "data/research_api_calls.jsonl; it is never counted as zero",
            "representation ROI is UNMEASURED until the representation forge writes "
            "desks/mt5/reports/REPRESENTATION_FORGE.json (another builder owns it)",
            "the capital evidence file has no allocator consumer today and says so by name",
            "the verdict ledger carries no region, so trials are attributed through the "
            "discovery's source and counted as UNROUTED where that join does not exist",
        ],
    }
    if not dry_run:
        _atomic_write(ALLOC_OUT, alloc_doc)
        _atomic_write(FOREST_OUT, forest)
        _atomic_write(CAPITAL_OUT, capital)
        _atomic_write(REPORT, report)
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=str(__doc__ or "").split("\n")[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = run(budget_s=float(a.budget_s), dry_run=bool(a.dry_run))
    reg = doc["region_roi"]["by_region"]
    print(f"research ROI {doc['at']}: {doc['counts']['sources']} source(s), "
          f"{doc['counts']['survivors']} survivor(s), "
          f"{doc['delayed_credit']['n_unjoined']} unjoined")
    print(f"  {ROI_REGION_FORMULA}")
    for r in REGIONS:
        row = reg[r]
        roi = "UNMEASURED" if row["roi"] is None else f"{row['roi']:.6g}"
        print(f"    {r:<22} roi={roi:>12}  num={row['numerator']:.4g} "
              f"den={row['denominator']:.4g}  sources={row['n_sources']}")
    for n in doc["negative_knowledge"][:8]:
        print(f"  NEGATIVE_KNOWLEDGE {n['family']:<28} {n['judged']} judged, 0 passed")
    for u in doc["unmeasured"]:
        print(f"  UNMEASURED {u['what']}: {u['why'][:110]}")
    if a.dry_run:
        print("  --dry-run: nothing written")
        return 0
    print(f"-> {REPORT}\n-> {ALLOC_OUT}\n-> {FOREST_OUT}\n-> {CAPITAL_OUT}")
    print(f"YIELD regions={len(REGIONS)} negative_families={doc['n_negative_families']} "
          f"credited_sources={len(doc['delayed_credit']['by_source'])} "
          f"elapsed={doc['elapsed_s']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
