"""HYPOTHESIS FAMILIES: breadth counted in independent families; mining re-aimed at empty ground.

THE PRINCIPAL, 2026-10-28: "fix inflated breadths n diversify discoveries minings searches to
avoid duplicates already mined or similar ... so we get millions of independent cells edges
instead of same".

WHAT ALREADY EXISTED, AND WHAT IT DID NOT DO. This module extends four organs and replaces none:

    merge_hypotheses._identity      EXACT dedupe (symbol, family, params) at the one funnel every
                                    producer flows through. A re-proposed cell collapses silently:
                                    nothing counted it, nothing told the producer to aim elsewhere.
    judge_coverage.variant_split    the STRUCTURAL cell (family|symbol|horizon|chart|session|
                                    regime|direction|representation): threshold-only variants rank
                                    behind the first claim of their rule. Measured on the box
                                    2026-10-27: 1,551,587 rows -> 427,581 structural cells (72.4%
                                    variants). Symbol-blind across instruments: the same rule on
                                    EURUSD and GBPUSD is two "unseen mechanisms".
    docket_keff / occupancy_map     marginal-k_eff ORDERING against the book. Reports the book's
                                    k_eff; never the docket's own independent-family count.
    novelty_gate                    certified/sleeve twins on the gauntlet head (1,500 rows).

THE FAMILY HIERARCHY (each level a coarsening of the one above; a cell sits in one key per level):

    L0  exact      merge_hypotheses._identity -- the same executable spec.
    L1  rule       judge_coverage.structural_cell -- the same rule on the same instrument; params
                   that are thresholds (lookbacks, z, rr, hours inside a session) collapse here.
    L2  family     L1 with the instrument replaced by its CORRELATION CLUSTER: instruments whose
                   daily log returns on the desk's own H1 bars correlate |rho| >= SYMBOL_RHO are
                   one exposure, so the same rule on both is one bet. An instrument with no
                   measurable series is its own cluster: absence never convicts (L1.28a).
    L3  returns    L2 families whose REALISED trade series correlate |rho| >= RETURNS_RHO on at
                   least MIN_OVERLAP common stamps (shadow ledgers, via novelty_gate). UNMEASURED
                   where no series exists, which is most of an unjudged docket.

BREADTH IS REPORTED AS FAMILIES AND k_eff, NOT CELLS. `reports/HYPOTHESIS_FAMILIES.json` carries
raw cells, L1 rules, L2 families, L3 merged families, the duplicate share, the top duplicate
clusters, and k_eff readings in effective-bet units. The headline k_eff is the inverse-Simpson
count over L3 families (L2 where L3 is unmeasured) -- how many equally-sized independent bets the
docket's cells amount to if each family is one bet. The family count is the UPPER bound (every
family independent); the cross-rule correlation inside a family count is not measurable before a
cell is judged, and the report says so rather than guessing.

EVERY CELL STILL COUNTS IN N. Nothing here removes a row, skips a judgement, or touches a trial
ledger (multiplicity.py and the gauntlet's lifetime union are sealed and unchanged). The judge
ORDER changes: inside each family stream the first claim of an L2 family ranks ahead of later
members (`family_split`, read by `judge_coverage.coverage_order`). A family-level verdict is
INHERITED only where that is statistically honest (`INHERITANCE_RULE`): an exact twin inherits
anything; a family member inherits only a REJECT at a gate whose outcome is a property of the
family or instrument and not of the parameters. A PASS is never inherited. Applying inheritance
in the sealed sweep is a proposal patch (patches/judge_families), where every inheritor is still
appended to the effective-trial census exactly as if judged -- neither inflated nor deflated.

UPSTREAM: DUPLICATES ARE RE-AIMED, NEVER DELETED. At the merge every FRESH row is checked against
what is already mined (`check`): EXACT re-proposal, NEAR (same L1 rule), FAMILY (same L2 family)
or NOVEL. A duplicate is KEPT (it was mined; its existence is recorded) and a RE-AIMED descendant
is minted beside it: the same rule moved to the instrument -- among those the same family already
runs on, and that the two-lane order lets it hypothesise on -- whose correlation cluster holds no
member of this rule and whose family coverage is thinnest. The mint rate therefore never drops: a
duplicate yields one row plus at most one new one. `steering` in the report names the under-covered
regions (family x asset class x chart x alpha cluster x producer) every producer can read.

MECHANISM. Every family record carries a one-line economic mechanism, the most common first
sentence of its members' own `mechanism_note`/`why`/`hypothesis` prose. A family with none is
FLAGGED and counted (`mechanism.missing_families`); it is never discarded.

    python research/hypothesis_families.py            # census of the live docket -> report
    python research/hypothesis_families.py --dry-run  # print, write nothing
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

HYP = BASE / "data" / "hypotheses"
DOCKET = HYP / "external_survivors.json"
REPORT = BASE / "reports" / "HYPOTHESIS_FAMILIES.json"
CLUSTERS = HYP / "symbol_clusters.json"
REAIM_LEDGER = HYP / "reaim_ledger.jsonl"
UNIVERSE = BASE / "data" / "universe"

#: |rho| of daily log returns at or above which two instruments are one exposure. 0.70 is the
#: desk's own redundancy line (improvement_inbox 2026-08-28 records same-cluster alphas measured at
#: 0.84 and different-cluster at well below 0.7); it is a DECLARED constant, never tuned to a count.
SYMBOL_RHO = 0.70
#: |rho| of realised trade R at or above which two families are one bet (novelty_v2's twin band
#: is 0.85 for a CONVICTION; this is a GROUPING for breadth, so the same 0.70 as instruments).
RETURNS_RHO = 0.70
#: Common days two instruments need before their correlation is read at all.
MIN_COMMON_DAYS = 250
#: Common stamps two families need before their trade correlation is read (novelty_v2.MIN_OVERLAP).
MIN_OVERLAP = 20
#: The symbol-cluster cache is re-derived when older than this or when the symbol set grows.
CLUSTER_MAX_AGE_S = 24 * 3600
#: Wall-clock bound on deriving clusters in one pass; symbols not reached stay singletons.
CLUSTER_BUDGET_S = 240.0
#: Top duplicate clusters published in full.
TOP_CLUSTERS = 50

#: Gates whose REJECT is a property of the family (its declared mechanism) or of the instrument,
#: never of a parameter value. Only these may be inherited by a non-identical family member.
FAMILY_INVARIANT_GATES = frozenset({"economic_prior"})
INSTRUMENT_INVARIANT_GATES = frozenset({"symbol_eligibility"})
INHERITANCE_RULE = (
    "an EXACT twin (same executable identity) inherits any verdict -- it is the same test. A "
    "non-identical member of an L1 rule or L2 family inherits ONLY a REJECT at a family-invariant "
    "gate (economic_prior, only between members with the same mechanism_status, which is all "
    "that gate reads) or, on the SAME instrument, at an "
    "instrument-invariant gate (symbol_eligibility). A PASS is never inherited, nor any reject at "
    "a parameter-dependent gate (in_sample_screen, deflated_sharpe, cpcv, walk_forward, lockbox, "
    "stress_costs, swap_cost, pbo, spa): those members are judged, after the representative. "
    "Every inheritor stays in the trial count exactly as if judged.")

_SENT = re.compile(r"(?<=[.;!?])\s+")
_WS = re.compile(r"\s+")


# ------------------------------------------------------------------------------------ helpers
def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _rows_of(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if isinstance(payload, dict):
        for k in ("rows", "survivors", "cells", "candidates"):
            if isinstance(payload.get(k), list):
                return [r for r in payload[k] if isinstance(r, dict)]
    return []


def _sym(row: Mapping[str, Any]) -> str:
    return str(row.get("symbol") or row.get("sym") or "").strip()


def _fam(row: Mapping[str, Any]) -> str:
    return str(row.get("family") or "").strip()


def identity(row: Mapping[str, Any]) -> str:
    """L0: merge_hypotheses._identity, spelled identically (that module is the docket's writer)."""
    params = row.get("params") or {}
    return json.dumps({
        "symbol": _sym(row), "family": _fam(row),
        "params": {k: params[k] for k in sorted(params)},
    }, sort_keys=True, default=str)


def _structural_impl() -> Callable[[dict[str, Any]], tuple[str, str]] | None:
    for mod in ("research.judge_coverage", "judge_coverage"):
        try:
            fn: Callable[[dict[str, Any]], tuple[str, str]] = __import__(
                mod, fromlist=["_grid_and_structural"])._grid_and_structural
            return fn
        except Exception:
            continue
    return None


_STRUCT = _structural_impl()


#: id(row) -> L1 key, live only inside `apply` (one merge pass computes each row's key once and
#: reads it from four places). None outside a pass, so a row mutated later is never misread.
_RULE_CACHE: dict[int, str] | None = None


def rule_key(row: dict[str, Any]) -> str:
    """L1: judge_coverage's structural cell, so the two organs can never disagree on a rule."""
    if _RULE_CACHE is not None:
        got = _RULE_CACHE.get(id(row))
        if got is not None:
            return got
        got = _rule_key(row)
        _RULE_CACHE[id(row)] = got
        return got
    return _rule_key(row)


def _rule_key(row: dict[str, Any]) -> str:
    if _STRUCT is not None:
        return _STRUCT(row)[1]
    params = row.get("params") or {}
    return "|".join(str(x or "?").lower() for x in (
        _fam(row), _sym(row), row.get("horizon") or params.get("horizon"),
        params.get("timeframe") or row.get("timeframe") or "H1",
        row.get("session") or params.get("session") or params.get("selector"),
        params.get("regime"), params.get("direction") or params.get("side"),
        params.get("representation") or params.get("feature")))


def _swap_symbol(rule: str, token: str) -> str:
    parts = rule.split("|")
    if len(parts) > 1:
        parts[1] = token
    return "|".join(parts)


def family_key(row: dict[str, Any], clusters: Mapping[str, str] | None = None,
               rule: str | None = None) -> str:
    """L2: the L1 rule with the instrument replaced by its correlation cluster."""
    r = rule if rule is not None else rule_key(row)
    sym = _sym(row).upper()
    cl = (clusters or {}).get(sym) or sym.lower() or "?"
    return _swap_symbol(r, f"@{cl.lower()}")


def rule_shape(rule: str) -> str:
    """The L1 rule with NO instrument: what 'the same signal across symbols' means."""
    return _swap_symbol(rule, "*")


def _h(text: str) -> int:
    return int.from_bytes(hashlib.blake2b(text.encode("utf-8"), digest_size=8).digest(), "big")


def mechanism_label(row: Mapping[str, Any]) -> str:
    """A short class LABEL the row carries instead of a mechanism (e.g. `volatility_shock`)."""
    for k in ("mechanism", "mechanism_note", "why"):
        v = row.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()[:40]
    return ""


def mechanism_line(row: Mapping[str, Any]) -> str:
    """The row's own one-line economic mechanism: first sentence of its prose, <= 160 chars.
    A class label under 20 characters is NOT a mechanism and returns empty (flagged LABEL_ONLY)."""
    for k in ("mechanism", "mechanism_note", "why", "hypothesis", "rationale", "claim"):
        v = row.get(k)
        if isinstance(v, str):
            t = _WS.sub(" ", v).strip()
            if len(t) >= 20:
                first = _SENT.split(t, maxsplit=1)[0]
                return first[:160]
    return ""


def _mem_available_mb() -> float | None:
    try:
        import psutil  # type: ignore[import-untyped,unused-ignore]
        return float(psutil.virtual_memory().available) / 1024 ** 2
    except Exception:
        return None


def detail_budget(rows: int) -> int:
    """How many family records to keep in full, DERIVED from free memory (never a box figure).

    Each kept record costs about 1.5 KB; spend at most 5% of what is free now, floored at 2,000
    so an unreadable counter still yields a usable report, and never more than the rows."""
    avail = _mem_available_mb()
    budget = 2000 if avail is None else max(2000, int(avail * 0.05 * 1024 / 1.5))
    return min(max(int(rows), 0), budget)


# ------------------------------------------------------------------- the instrument clusters
def _daily(sym: str, universe: Path) -> Any:
    try:
        from research.docket_keff import daily_returns
    except Exception:                                                 # pragma: no cover
        try:
            from docket_keff import daily_returns  # type: ignore[import-not-found,no-redef]
        except Exception:
            return None
    try:
        return daily_returns(sym, universe)
    except Exception:
        return None


def derive_clusters(symbols: Iterable[str], loader: Callable[[str], Any] | None = None, *,
                    rho: float = SYMBOL_RHO, min_days: int = MIN_COMMON_DAYS,
                    budget_s: float = CLUSTER_BUDGET_S,
                    universe: Path | None = None) -> dict[str, Any]:
    """Leader clustering of instruments on |corr(daily log returns)| >= rho.

    Deterministic: symbols are visited in name order and each joins the FIRST leader it clears,
    else becomes a leader. Leader (not single-linkage) so EURUSD-GBPUSD-GBPJPY-... cannot chain
    one cluster across instruments that do not themselves co-move. A symbol without a series, or
    not reached inside the budget, is its own cluster and is listed as UNMEASURED."""
    import numpy as np
    uni = universe or UNIVERSE
    load = loader or (lambda s: _daily(s, uni))
    t0 = time.monotonic()
    leaders: list[tuple[str, Any]] = []
    cluster: dict[str, str] = {}
    unmeasured: list[str] = []
    for sym in sorted({str(s).upper() for s in symbols if s}):
        if time.monotonic() - t0 > budget_s:
            cluster[sym] = sym
            unmeasured.append(sym)
            continue
        r = load(sym)
        if r is None or len(r) < min_days:
            cluster[sym] = sym
            unmeasured.append(sym)
            continue
        home = None
        for lead, lr in leaders:
            j = lr.index.intersection(r.index)
            if len(j) < min_days:
                continue
            a = lr.loc[j].to_numpy(dtype="float64")
            b = r.loc[j].to_numpy(dtype="float64")
            if a.std() <= 0 or b.std() <= 0:
                continue
            if abs(float(np.corrcoef(a, b)[0, 1])) >= rho:
                home = lead
                break
        if home is None:
            leaders.append((sym, r))
            home = sym
        cluster[sym] = home
    sizes = Counter(cluster.values())
    return {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"), "rho": rho,
            "min_common_days": min_days, "symbols": len(cluster),
            "measured": len(cluster) - len(unmeasured), "unmeasured": sorted(unmeasured),
            "clusters": len(sizes),
            "multi_member": {k: sorted(s for s, c in cluster.items() if c == k)
                             for k, n in sizes.most_common() if n > 1},
            "cluster_of": dict(sorted(cluster.items())),
            "elapsed_s": round(time.monotonic() - t0, 2)}


def load_clusters(symbols: Iterable[str] | None = None, *, path: Path | None = None,
                  refresh: bool = True, loader: Callable[[str], Any] | None = None
                  ) -> tuple[dict[str, str], dict[str, Any]]:
    """{SYMBOL: cluster leader}, from the cache, re-derived when stale or when new symbols appear.

    `refresh=False` never derives (the ordering path reads whatever the merge last wrote)."""
    p = path or CLUSTERS
    doc = _read(p)
    want = {str(s).upper() for s in (symbols or []) if s}
    fresh = False
    if isinstance(doc, dict) and isinstance(doc.get("cluster_of"), dict):
        try:
            age = time.time() - datetime.fromisoformat(str(doc.get("at"))).timestamp()
        except ValueError:
            age = float("inf")
        fresh = age < CLUSTER_MAX_AGE_S and want <= set(doc["cluster_of"])
    if (not fresh) and refresh and want:
        doc = derive_clusters(want, loader)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(doc, indent=1), "utf-8")
            os.replace(tmp, p)
        except OSError:
            pass
    if not isinstance(doc, dict) or not isinstance(doc.get("cluster_of"), dict):
        return {}, {"status": "UNMEASURED", "why": "no symbol-cluster cache and none derived"}
    meta = {k: v for k, v in doc.items() if k not in ("cluster_of", "multi_member", "unmeasured")}
    meta["unmeasured_count"] = len(doc.get("unmeasured") or [])
    meta["unmeasured_sample"] = list(doc.get("unmeasured") or [])[:30]
    meta["status"] = "MEASURED" if doc.get("measured") else "UNMEASURED"
    meta["multi_member_clusters"] = len(doc.get("multi_member") or {})
    meta["largest"] = sorted(((k, len(v)) for k, v in (doc.get("multi_member") or {}).items()),
                             key=lambda kv: -kv[1])[:10]
    return {str(k): str(v) for k, v in doc["cluster_of"].items()}, meta


# ------------------------------------------------------------------------------- the census
def _inverse_simpson(counts: Iterable[int]) -> float | None:
    c = [int(x) for x in counts if x]
    tot = sum(c)
    if not tot:
        return None
    return round(tot * tot / sum(x * x for x in c), 3)


def _asset_class(sym: str, cache: dict[str, str]) -> str:
    if sym not in cache:
        try:
            from research.universe_policy import asset_class_of
            cache[sym] = asset_class_of(sym) or "unclassified"
        except Exception:
            cache[sym] = "unclassified"
    return cache[sym]


def _alpha_cluster(fam: str, cache: dict[str, str]) -> str:
    if fam not in cache:
        try:
            from libs.research.alpha_clusters import classify_family
            cache[fam] = str(classify_family(fam))
        except Exception:
            cache[fam] = "UNCLASSIFIED"
    return cache[fam]


def census(rows: list[dict[str, Any]], clusters: Mapping[str, str] | None = None, *,
           returns_groups: Mapping[str, str] | None = None,
           detail: int | None = None) -> dict[str, Any]:
    """One pass over the docket: L1/L2/L3 counts, k_eff readings, mechanism coverage, steering.

    `returns_groups` maps an L2 family key to its L3 group (from `returns_merge`); families not in
    it are their own L3 group. Stamps nothing; removes nothing."""
    cl = clusters or {}
    l1: set[int] = set()
    fam_cells: Counter[str] = Counter()
    fam_rules: dict[str, set[int]] = {}
    fam_syms: dict[str, set[str]] = {}
    fam_mech: dict[str, Counter[str]] = {}
    fam_prod: dict[str, Counter[str]] = {}
    name_cells: Counter[str] = Counter()
    fam_label: dict[str, str] = {}
    ac_cache: dict[str, str] = {}
    alpha_cache: dict[str, str] = {}
    axes: dict[str, dict[str, set[str]]] = {"asset_class": {}, "timeframe": {},
                                            "alpha_cluster": {}, "producer": {}, "family": {}}
    for row in rows:
        r = rule_key(row)
        l1.add(hash(r))
        fk = family_key(row, cl, r)
        fam_cells[fk] += 1
        fam_rules.setdefault(fk, set()).add(hash(r))
        sym = _sym(row).upper()
        fam_syms.setdefault(fk, set()).add(sym)
        m = mechanism_line(row)
        if m:
            fam_mech.setdefault(fk, Counter())[m] += 1
        elif fk not in fam_label:
            lab = mechanism_label(row)
            if lab:
                fam_label[fk] = lab
        prod = str(row.get("producer") or row.get("source") or "?").split(":")[0]
        fam_prod.setdefault(fk, Counter())[prod] += 1
        fname = _fam(row)
        name_cells[fname] += 1
        params = row.get("params") or {}
        tf = str(params.get("timeframe") or row.get("timeframe") or "H1").upper()
        for axis, val in (("asset_class", _asset_class(sym, ac_cache)), ("timeframe", tf),
                          ("alpha_cluster", _alpha_cluster(fname, alpha_cache)),
                          ("producer", prod), ("family", fname)):
            axes[axis].setdefault(val, set()).add(fk)
    raw = len(rows)
    n_l1, n_l2 = len(l1), len(fam_cells)
    groups = returns_groups or {}
    l3_cells: Counter[str] = Counter()
    for fk, n in fam_cells.items():
        l3_cells[groups.get(fk, fk)] += n
    n_l3 = len(l3_cells)
    missing = [fk for fk in fam_cells if not fam_mech.get(fk)]
    missing_cells = sum(fam_cells[fk] for fk in missing)
    keep = detail if detail is not None else detail_budget(n_l2)
    top = fam_cells.most_common(max(int(keep), 0))
    records = []
    for fk, n in top:
        mech = fam_mech.get(fk)
        records.append({
            "family_id": f"F{_h(fk):016x}", "key": fk, "cells": n,
            "rules": len(fam_rules.get(fk, ())), "symbols": sorted(fam_syms.get(fk, ()))[:12],
            "n_symbols": len(fam_syms.get(fk, ())),
            "mechanism": mech.most_common(1)[0][0] if mech else None,
            "mechanism_flag": None if mech else ("LABEL_ONLY" if fk in fam_label else "MISSING"),
            "mechanism_label": None if mech else fam_label.get(fk),
            "producers": dict((fam_prod.get(fk) or Counter()).most_common(5)),
            "l3_group": groups.get(fk)})
    ks = {
        "families_upper_bound": n_l2,
        "k_eff_l2_cells": _inverse_simpson(fam_cells.values()),
        "k_eff_l3_cells": _inverse_simpson(l3_cells.values()),
        "k_eff_family_names": _inverse_simpson(name_cells.values()),
    }
    headline = ks["k_eff_l3_cells"]
    # Steering: per axis, the values holding the fewest families, and declared-but-empty values.
    steer: dict[str, Any] = {}
    declared = {"timeframe": ["M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1"]}
    try:
        from libs.research.alpha_clusters import CLUSTERS as _CL
        declared["alpha_cluster"] = [c.key for c in _CL]
    except Exception:                                                 # pragma: no cover
        pass
    for axis, vals in axes.items():
        counts = {v: len(s) for v, s in vals.items()}
        empty = sorted(set(declared.get(axis, [])) - set(counts))
        thin = sorted(counts.items(), key=lambda kv: (kv[1], kv[0]))[:15]
        steer[axis] = {"values": len(counts), "empty_declared": empty,
                       "thinnest": [{"value": v, "families": n} for v, n in thin],
                       "families_inverse_simpson": _inverse_simpson(counts.values())}
    return {
        "raw_cells": raw,
        "l1_rules": n_l1,
        "l2_families": n_l2,
        "l3_families": n_l3,
        "l3_status": "MEASURED" if groups else "UNMEASURED",
        "duplicate_share_l1": round(1 - n_l1 / raw, 4) if raw else None,
        "duplicate_share_l2": round(1 - n_l2 / raw, 4) if raw else None,
        "cells_per_family": round(raw / n_l2, 3) if n_l2 else None,
        "k_eff": headline,
        "k_eff_readings": ks,
        "k_eff_rule": ("headline = inverse Simpson of cells over L3 families (L2 where L3 is "
                       "unmeasured): the number of equally-sized independent bets the docket's "
                       "cells amount to if each family is one bet. families_upper_bound assumes "
                       "every family independent; cross-rule correlation inside it is unmeasurable "
                       "before judgement and is NOT guessed"),
        "mechanism": {"families_with_mechanism": n_l2 - len(missing),
                      "missing_families": len(missing), "missing_cells": missing_cells,
                      "coverage": round(1 - len(missing) / n_l2, 4) if n_l2 else None,
                      "label_only_families": sum(1 for k in missing if k in fam_label),
                      "label_only_labels": dict(Counter(fam_label[k] for k in missing
                                                        if k in fam_label).most_common(15)),
                      "missing_examples": sorted(missing, key=lambda k: -fam_cells[k])[:20],
                      "rule": ("one-line mechanism = most common first sentence of the members' "
                               "own mechanism/why/hypothesis prose (>= 20 chars). A family with "
                               "only a class label (e.g. 'volatility_shock') is LABEL_ONLY, one "
                               "with nothing is MISSING; both are counted as missing and neither "
                               "is ever discarded")},
        "top_duplicate_families": records[:TOP_CLUSTERS],
        "families": records,
        "families_published": len(records),
        "steering": steer,
    }


# ------------------------------------------------------------------------ the daily metric
DAILY_WINDOW = 60


def daily(rows: list[dict[str, Any]], clusters: Mapping[str, str] | None = None,
          window: int = DAILY_WINDOW) -> dict[str, Any]:
    """Per UTC day of `first_seen`: raw cells mined, NEW independent cells (the first cell of an
    L1 rule never mined before -- net of near-duplicates of anything already mined), NEW
    independent families (the first cell of an L2 family), re-aimed cells, and the duplicate share.

    Recomputed from the whole docket bank every pass (the bank keeps every row and its
    first_seen), so it is idempotent and back-fills its own history; a day is attributed by the
    row's first_seen, never by when this ran. The trend is the 7-day mean against the prior 7."""
    cl = clusters or {}
    dated: list[tuple[str, int, int, bool]] = []
    for row in rows:
        day = str(row.get("first_seen") or "")[:10]
        if len(day) != 10:
            day = "undated"
        r = rule_key(row)
        dated.append((day, hash(r), hash(family_key(row, cl, r)), bool(row.get("reaimed_from"))))
    dated.sort(key=lambda t: t[0])
    seen_r: set[int] = set()
    seen_f: set[int] = set()
    per: dict[str, dict[str, Any]] = {}
    for day, rh, fh, re_ in dated:
        d = per.setdefault(day, {"raw_cells": 0, "new_independent_cells": 0,
                                 "new_independent_families": 0, "reaimed_cells": 0})
        d["raw_cells"] += 1
        d["reaimed_cells"] += int(re_)
        if rh not in seen_r:
            seen_r.add(rh)
            d["new_independent_cells"] += 1
        if fh not in seen_f:
            seen_f.add(fh)
            d["new_independent_families"] += 1
    for d in per.values():
        d["duplicate_share"] = (round(1 - d["new_independent_cells"] / d["raw_cells"], 4)
                                if d["raw_cells"] else None)
    days = sorted(k for k in per if k != "undated")
    series = [{"day": k, **per[k]} for k in days[-window:]]

    def mean(key: str, xs: list[dict[str, Any]]) -> float | None:
        return round(sum(x[key] for x in xs) / len(xs), 2) if xs else None
    last7, prior7 = series[-7:], series[-14:-7]
    trend: dict[str, dict[str, Any]] = {k: {"mean_last_7_days_present": mean(k, last7),
                 "mean_prior_7_days_present": mean(k, prior7)}
             for k in ("raw_cells", "new_independent_cells", "new_independent_families")}
    for v in trend.values():
        a, b = v["mean_last_7_days_present"], v["mean_prior_7_days_present"]
        v["direction"] = (None if a is None or b is None else
                          "UP" if a > b else "DOWN" if a < b else "FLAT")
    return {"days": series, "undated": per.get("undated"), "trend": trend,
            "basis": ("UTC day of first_seen over the whole bank; a day with no mined row is "
                      "absent, not zero; raw volume is reported beside the independent counts "
                      "so a fall in duplicates can never hide a fall in mining"),
            "rule": ("new_independent_cells = first cell of an L1 rule never mined before; "
                     "new_independent_families = first cell of an L2 family; duplicate_share = "
                     "1 - new_independent_cells / raw_cells")}


# --------------------------------------------------------------------------- the L3 merge
def returns_merge(series: Mapping[str, Mapping[str, float]], *, rho: float = RETURNS_RHO,
                  min_overlap: int = MIN_OVERLAP) -> dict[str, str]:
    """{L2 key: L3 leader} by leader clustering on |corr| of realised R over common stamps.

    Only families WITH a series are grouped; two families sharing one source file are never
    compared (a series against itself is 1.00 and says nothing)."""
    import numpy as np
    leaders: list[tuple[str, Mapping[str, float]]] = []
    out: dict[str, str] = {}
    for fk in sorted(series):
        s = series[fk]
        home = None
        for lead, ls in leaders:
            keys = sorted(set(s) & set(ls))
            if len(keys) < min_overlap:
                continue
            a = np.array([ls[k] for k in keys], dtype="float64")
            b = np.array([s[k] for k in keys], dtype="float64")
            if a.std() <= 0 or b.std() <= 0:
                continue
            if abs(float(np.corrcoef(a, b)[0, 1])) >= rho:
                home = lead
                break
        if home is None:
            leaders.append((fk, s))
            home = fk
        out[fk] = home
    return out


def family_series(rows: list[dict[str, Any]], clusters: Mapping[str, str] | None = None
                  ) -> dict[str, dict[str, float]]:
    """One realised-R series per L2 family, from the shadow ledgers novelty_gate already reads.
    Families with no ledger are absent (UNMEASURED), never zero."""
    try:
        from research import novelty_gate as ng
    except Exception:
        try:
            import novelty_gate as ng  # type: ignore[import-not-found,no-redef]
        except Exception:
            return {}
    out: dict[str, dict[str, float]] = {}
    srcs: set[str] = set()
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        key = (_sym(row).upper(), _fam(row).lower(),
               str(row.get("session") or (row.get("params") or {}).get("session") or ""))
        if key in seen:
            continue
        seen.add(key)
        fk = family_key(row, clusters)
        if fk in out:
            continue
        try:
            got = ng._series_for(ng._member(row))
        except Exception:
            got = None
        if not got or not isinstance(got[1], dict) or got[0] in srcs:
            continue
        srcs.add(got[0])
        out[fk] = dict(got[1])
    return out


# ------------------------------------------------------------------------ the judge order
def family_split(rows: list[dict[str, Any]], unjudged_ids: set[str] | None = None,
                 clusters: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Stamp `_famdup` = 0 on the first claim of each L2 family, 1 on every later member.

    Same claim order as `judge_coverage.variant_split` (never-judged first, then oldest
    first_seen, then docket position), so the representative is the row that would have gone
    first anyway. Removes nothing; `coverage_order` reads it as a tie-break after `_variant`."""
    cl = clusters if clusters is not None else load_clusters(refresh=False)[0]
    ids = unjudged_ids or set()
    n = len(rows)
    first = [""] * n
    keys = [0] * n
    fresh_idx: list[int] = []
    stale_idx: list[int] = []
    for i, row in enumerate(rows):
        first[i] = str(row.get("first_seen") or "9999")
        keys[i] = hash(family_key(row, cl))
        (fresh_idx if (not ids or str(row.get("_cell") or "") in ids) else stale_idx).append(i)
    order = sorted(fresh_idx, key=first.__getitem__) + sorted(stale_idx, key=first.__getitem__)
    seen: set[int] = set()
    marks = [0] * n
    for i in order:
        if keys[i] in seen:
            marks[i] = 1
        else:
            seen.add(keys[i])
    for i, row in enumerate(rows):
        row["_famdup"] = marks[i]
    return {"rows": n, "family_representatives": len(seen), "family_members": sum(marks),
            "clusters_status": "MEASURED" if cl else "UNMEASURED"}


def inheritable(rep_verdict: Mapping[str, Any], rep: Mapping[str, Any],
                member: Mapping[str, Any], clusters: Mapping[str, str] | None = None) -> bool:
    """INHERITANCE_RULE as a predicate. `rep_verdict` carries `passed` and `terminal_gate`."""
    if identity(rep) == identity(member):
        return True
    if bool(rep_verdict.get("passed")):
        return False
    gate = str(rep_verdict.get("terminal_gate") or rep_verdict.get("gate") or "")
    same_family = family_key(dict(rep), clusters) == family_key(dict(member), clusters)
    if not same_family:
        return False
    if gate in FAMILY_INVARIANT_GATES:
        # economic_prior reads the row's own mechanism_status (frontier_identity.economic_prior),
        # so it is invariant only across members carrying the SAME status.
        def status(r: Mapping[str, Any]) -> str:
            st = str(r.get("mechanism_status") or "")
            return st or ("STATISTICAL_ONLY" if _fam(r) == "discovered" else "NAMED")
        return _fam(rep) == _fam(member) and status(rep) == status(member)
    if gate in INSTRUMENT_INVARIANT_GATES:
        return _sym(rep).upper() == _sym(member).upper()
    return False


def inherit_plan(specs: list[dict[str, Any]], verdict_index: Mapping[str, str],
                 cell_id_fn: Callable[[dict[str, Any]], str],
                 clusters: Mapping[str, str] | None = None) -> list[dict[str, Any]]:
    """Which UNJUDGED specs may inherit a judged family member's verdict under INHERITANCE_RULE.

    `verdict_index` is the sealed judge's own `gate_verdict_index.json` ({cell: "gate|passed"}).
    A representative is a judged spec whose recorded verdict is a REJECT at an invariant gate; an
    inheritor is a spec in the same L2 family with no recorded verdict. Returns one synthetic
    verdict per inheritor, carrying `inherited_from` -- the caller records it on the graph and
    the gate ledger exactly as a judged verdict, so the trial count is unchanged."""
    cl = clusters or {}
    reps: dict[int, tuple[dict[str, Any], str, str]] = {}
    pending: list[tuple[dict[str, Any], str]] = []
    for sp in specs:
        try:
            cell = cell_id_fn(sp)
        except Exception:
            continue
        key = verdict_index.get(cell)
        if key is None:
            pending.append((sp, cell))
            continue
        gate, _, passed = str(key).partition("|")
        if passed == "0" and gate in FAMILY_INVARIANT_GATES | INSTRUMENT_INVARIANT_GATES:
            reps.setdefault(hash(family_key(sp, cl)), (sp, cell, gate))
    out: list[dict[str, Any]] = []
    for sp, cell in pending:
        got = reps.get(hash(family_key(sp, cl)))
        if got is None:
            continue
        rep, rep_cell, gate = got
        if not inheritable({"passed": False, "terminal_gate": gate}, rep, sp, cl):
            continue
        out.append({"cell": cell, "sym": _sym(sp), "family": _fam(sp),
                    "params": dict(sp.get("params") or {}), "passed": False,
                    "terminal_gate": gate, "inherited_from": rep_cell,
                    "inheritance_rule": "family_invariant_reject"})
    return out


# ------------------------------------------------------------------ upstream: check + re-aim
class MinedIndex:
    """What is already mined, at three levels, for checking a new cell before it is banked."""

    def __init__(self, rows: Iterable[dict[str, Any]], clusters: Mapping[str, str] | None = None,
                 idents: Iterable[str] | None = None):
        self.clusters = dict(clusters or {})
        self.idents: set[int] = set()
        self.rules: set[int] = set()
        self.families: Counter[int] = Counter()
        #: rule shape (no instrument) -> clusters already holding it
        self.shape_clusters: dict[int, set[str]] = {}
        #: family name -> {SYMBOL: cells}, the instruments that family already runs on
        self.family_symbols: dict[str, Counter[str]] = {}
        ids = iter(idents) if idents is not None else None
        for row in rows:
            self.add(row, next(ids) if ids is not None else None)

    def _cluster(self, sym: str) -> str:
        return self.clusters.get(sym.upper(), sym.upper())

    def add(self, row: dict[str, Any], ident: str | None = None) -> None:
        r = rule_key(row)
        sym = _sym(row).upper()
        self.idents.add(hash(ident if ident is not None else identity(row)))
        self.rules.add(hash(r))
        self.families[hash(family_key(row, self.clusters, r))] += 1
        self.shape_clusters.setdefault(hash(rule_shape(r)), set()).add(self._cluster(sym))
        if sym:
            self.family_symbols.setdefault(_fam(row), Counter())[sym] += 1

    def check(self, row: dict[str, Any], ident: str | None = None) -> dict[str, Any]:
        """EXACT | NEAR (same L1 rule) | FAMILY (same L2 family) | NOVEL."""
        r = rule_key(row)
        fk = family_key(row, self.clusters, r)
        if hash(ident if ident is not None else identity(row)) in self.idents:
            status = "EXACT"
        elif hash(r) in self.rules:
            status = "NEAR"
        elif self.families.get(hash(fk)):
            status = "FAMILY"
        else:
            status = "NOVEL"
        return {"status": status, "family_id": f"F{_h(fk):016x}",
                "family_cells": int(self.families.get(hash(fk), 0))}

    def reaim_target(self, row: dict[str, Any],
                     lawful: Callable[[str, str], bool] | None = None) -> str | None:
        """The instrument to move a duplicate onto, or None.

        Candidates: instruments the SAME family already runs on (so the rule is buildable there
        and the lane router already admitted that family on it), the two-lane order permitting.
        Excluded: any instrument whose correlation cluster already holds this rule shape. Chosen:
        the one where the family is thinnest, ties by name -- the emptiest lawful ground."""
        fam = _fam(row)
        held = self.shape_clusters.get(hash(rule_shape(rule_key(row))), set())
        best: tuple[int, str] | None = None
        for sym, n in (self.family_symbols.get(fam) or {}).items():
            if self._cluster(sym) in held:
                continue
            if lawful is not None and not lawful(sym, fam):
                continue
            if best is None or (n, sym) < best:
                best = (n, sym)
        return best[1] if best else None


def _lawful() -> Callable[[str, str], bool]:
    try:
        from research.universe_policy import may_hypothesise
    except Exception:
        return lambda s, f: True

    def ok(sym: str, fam: str) -> bool:
        try:
            return bool(may_hypothesise(sym, fam))
        except Exception:
            return False
    return ok


REAIM_VERSION = "family-reaim-v1"
_SAFE = ("source", "producer", "origin", "title", "url", "source_title", "source_url",
         "mechanism", "mechanism_status", "mechanism_note", "timeframe", "chart",
         "contributing_sources", "n_independent_sources")


def reaim(rows: list[dict[str, Any]], fresh: set[str], reproposed: set[str], *,
          identity_fn: Callable[[dict[str, Any]], str] = identity,
          clusters: Mapping[str, str] | None = None,
          lawful: Callable[[str, str], bool] | None = None,
          now: datetime | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Check every fresh row against what was mined before it; re-aim each duplicate.

    `fresh` = identities this pass's producers emitted that the bank did not hold; `reproposed`
    = identities they emitted that the bank DID hold (EXACT duplicates the merge collapsed).
    Returns (children, report). Inputs are never mutated beyond a `dup_status` stamp and never
    removed: a duplicate stays in the docket and its re-aimed child is added beside it."""
    at = (now or datetime.now(UTC)).astimezone(UTC).isoformat(timespec="seconds")
    cl = clusters or {}
    law = lawful or _lawful()
    idents = [identity_fn(r) for r in rows]
    prior_i = [i for i, ident in enumerate(idents) if ident not in fresh]
    index = MinedIndex((rows[i] for i in prior_i), cl, (idents[i] for i in prior_i))
    present = set(idents)
    # ONCE PER PARENT, EVER. A compiler that re-emits its whole corpus every hour re-proposes the
    # same 50k cells each pass; re-aiming each of them every hour would turn a re-emission into a
    # generator. The bank remembers which parents already have a re-aimed child.
    done = {str((r.get("reaimed_from") or {}).get("parent_identity") or "")
            for r in rows if isinstance(r.get("reaimed_from"), dict)}
    counts: Counter[str] = Counter()
    by_producer: dict[str, Counter[str]] = {}
    children: list[dict[str, Any]] = []
    no_target = 0
    # Fresh rows are checked in docket order and ADDED to the index as they are seen, so two
    # fresh twins of each other are caught too (the second is NEAR the first).
    for row, ident in zip(rows, idents, strict=True):
        if ident in fresh:
            chk = index.check(row, ident)
        elif ident in reproposed:
            chk = {"status": "EXACT"}
        else:
            continue
        status = chk["status"]
        counts[status] += 1
        prod = str(row.get("producer") or "?")
        by_producer.setdefault(prod, Counter())[status] += 1
        row["dup_status"] = status
        if ident in fresh:
            index.add(row, ident)
        if status == "NOVEL":
            continue
        if ident in done:
            counts["already_reaimed"] += 1
            continue
        target = index.reaim_target(row, law)
        if target is None:
            no_target += 1
            continue
        child = {k: row[k] for k in _SAFE if k in row}
        child.update({"symbol": target, "family": _fam(row),
                      "params": dict(row.get("params") or {})})
        key = identity_fn(child)
        if key in present:
            counts["reaim_already_present"] += 1
            continue
        child["reaimed_from"] = {"version": REAIM_VERSION, "parent_identity": ident,
                                 "parent_status": status, "at": at,
                                 "why": ("the parent duplicated ground already mined; the same "
                                         "rule is moved to the thinnest lawful instrument whose "
                                         "correlation cluster holds no member of it")}
        child["available_time"] = at
        child["ingested_time"] = at
        child["source_version"] = REAIM_VERSION
        child["payload_hash"] = hashlib.sha256(json.dumps(
            {"symbol": target, "family": _fam(row), "params": child["params"],
             "parent_identity": ident, "version": REAIM_VERSION},
            sort_keys=True, default=str).encode("utf-8")).hexdigest()
        child["first_seen"] = at
        child["dup_status"] = "REAIMED"
        present.add(key)
        done.add(ident)
        index.add(child, key)
        children.append(child)
    checked = sum(v for k, v in counts.items() if k in ("EXACT", "NEAR", "FAMILY", "NOVEL"))
    dups = checked - counts.get("NOVEL", 0)
    report = {"at": at, "version": REAIM_VERSION, "checked": checked,
              "by_status": {k: counts.get(k, 0) for k in ("EXACT", "NEAR", "FAMILY", "NOVEL")},
              "duplicate_share": round(dups / checked, 4) if checked else None,
              "reaimed": len(children), "no_lawful_empty_target": no_target,
              "reaim_already_present": counts.get("reaim_already_present", 0),
              "already_reaimed_parents": counts.get("already_reaimed", 0),
              "by_producer": {p: dict(c) for p, c in sorted(by_producer.items())},
              "mint_conservation": {"fresh_in": checked, "rows_out": checked + len(children),
                                    "removed": 0},
              "rule": ("a duplicate is KEPT and a re-aimed descendant is minted beside it; "
                       "nothing is deleted, so the mint rate can only rise")}
    return children, report


def append_reaim_ledger(children: list[dict[str, Any]], path: Path | None = None) -> int:
    """One line per re-aimed child: its parent and target, the audit trail of every re-aim."""
    if not children:
        return 0
    p = path or REAIM_LEDGER
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            for c in children:
                fh.write(json.dumps({"at": c["reaimed_from"]["at"], "symbol": c["symbol"],
                                     "family": c["family"],
                                     "parent": c["reaimed_from"]["parent_identity"],
                                     "parent_status": c["reaimed_from"]["parent_status"]},
                                    default=str) + "\n")
    except OSError:
        return 0
    return len(children)


# --------------------------------------------------------------------------- the merge hook
def apply(rows: list[dict[str, Any]], *, fresh: set[str], reproposed: set[str],
          identity_fn: Callable[[dict[str, Any]], str] = identity,
          now: datetime | None = None, publish_report: bool = True,
          report_path: Path | None = None,
          hyp_dir: Path | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """`merge_hypotheses`' one call: re-aim fresh duplicates, census the docket, publish.

    Returns (rows plus re-aimed children, compact block for merge_report). Never raises: a fault
    costs the census and the re-aim, never a row. `hyp_dir` is the caller's hypotheses directory
    (the cluster cache and the re-aim ledger live beside the docket the caller writes)."""
    global _RULE_CACHE
    avail = _mem_available_mb()
    # ~400 B per cached key; cache only when it costs under a quarter of what is free right now.
    if avail is None or avail * 1024 ** 2 * 0.25 > len(rows) * 400:
        _RULE_CACHE = {}
    try:
        syms = {_sym(r).upper() for r in rows} - {""}
        clusters, cmeta = load_clusters(
            syms, path=(hyp_dir / CLUSTERS.name) if hyp_dir is not None else None)
        children, rep = reaim(rows, fresh, reproposed, identity_fn=identity_fn,
                              clusters=clusters, now=now)
        # THE REVERT PATH, not a throttle: QUANT_FAMILY_REAIM=0 keeps the check, the stamps and
        # the census and mints no descendant (the duplicates were never removed either way).
        if os.environ.get("QUANT_FAMILY_REAIM", "1") == "0":
            rep["reaim_enabled"] = False
            rep["reaimed_would_have_been"] = len(children)
            rep["reaimed"] = 0
            children = []
        else:
            rep["reaim_enabled"] = True
        append_reaim_ledger(children,
                            (hyp_dir / REAIM_LEDGER.name) if hyp_dir is not None else None)
        out = rows + children
        doc = build(out, clusters=clusters, cluster_meta=cmeta, reaim_report=rep)
        if publish_report:
            write(doc, report_path)
        return out, summary(doc)
    except Exception as exc:
        return rows, {"status": f"FAILED: {type(exc).__name__}: {exc}"[:300]}
    finally:
        _RULE_CACHE = None


def build(rows: list[dict[str, Any]], *, clusters: Mapping[str, str] | None = None,
          cluster_meta: Mapping[str, Any] | None = None,
          reaim_report: Mapping[str, Any] | None = None,
          with_returns: bool = True) -> dict[str, Any]:
    cl = clusters or {}
    groups: dict[str, str] = {}
    series_n = 0
    if with_returns:
        ser = family_series(rows, cl)
        series_n = len(ser)
        if ser:
            groups = returns_merge(ser)
    body = census(rows, cl, returns_groups=groups)
    body["l3_series_families"] = series_n
    body["daily"] = daily(rows, cl)
    breadth = _read(BASE / "reports" / "EFFECTIVE_BREADTH.json")
    book = (breadth or {}).get("effective") if isinstance(breadth, dict) else None
    return {
        "schema": "hypothesis_families/1",
        "generated_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "producer": "desks/mt5/research/hypothesis_families.py (hourly, merge_docket leg)",
        "status": "MEASURED" if rows else "UNMEASURED",
        **body,
        "symbol_clusters": dict(cluster_meta or {}),
        "intake": dict(reaim_report or {"status": "UNMEASURED",
                                        "why": "census run outside the merge: no fresh rows"}),
        "book_k_eff": ({"effective_breadth": book.get("effective_breadth"),
                        "n_nominal": book.get("n_nominal"),
                        "source": "reports/EFFECTIVE_BREADTH.json"}
                       if isinstance(book, dict) else {"status": "UNMEASURED"}),
        "inheritance": {"rule": INHERITANCE_RULE,
                        "family_invariant_gates": sorted(FAMILY_INVARIANT_GATES),
                        "instrument_invariant_gates": sorted(INSTRUMENT_INVARIANT_GATES),
                        "applied_in_sealed_sweep": False,
                        "why": ("the sealed gauntlet decides what it judges; inheritance there "
                                "is a proposal patch (patches/judge_families) that charges every "
                                "inheritor to the effective-trial census as if judged")},
        "trial_count": {"changed": False,
                        "why": ("this organ reorders and re-aims; it never removes a row, skips a "
                                "judgement or writes a trial ledger, so N is exactly what the "
                                "sealed lifetime union already counts")},
    }


def summary(doc: Mapping[str, Any]) -> dict[str, Any]:
    keep = ("generated_at", "status", "raw_cells", "l1_rules", "l2_families", "l3_families",
            "l3_status", "duplicate_share_l1", "duplicate_share_l2", "k_eff", "k_eff_readings")
    out = {k: doc.get(k) for k in keep}
    out["mechanism_missing_families"] = (doc.get("mechanism") or {}).get("missing_families")
    days = (doc.get("daily") or {}).get("days") or []
    out["daily_latest"] = days[-1] if days else None
    out["daily_trend"] = (doc.get("daily") or {}).get("trend")
    out["intake"] = {k: (doc.get("intake") or {}).get(k) for k in
                     ("checked", "by_status", "duplicate_share", "reaimed",
                      "no_lawful_empty_target")}
    out["report"] = "desks/mt5/reports/HYPOTHESIS_FAMILIES.json"
    return out


def write(doc: Mapping[str, Any], path: Path | None = None) -> Path:
    p = path or REPORT
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    os.replace(tmp, p)
    return p


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--docket", type=Path, default=DOCKET)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--no-derive", action="store_true",
                    help="never derive symbol clusters; read the cache only")
    a = ap.parse_args(argv)
    rows = _rows_of(_read(a.docket))
    syms = {_sym(r).upper() for r in rows} - {""}
    clusters, cmeta = load_clusters(syms, refresh=not a.no_derive)
    doc = build(rows, clusters=clusters, cluster_meta=cmeta)
    line = (f"hypothesis_families: {doc.get('raw_cells')} cells -> {doc.get('l1_rules')} rules -> "
            f"{doc.get('l2_families')} families -> {doc.get('l3_families')} L3; "
            f"dup share {doc.get('duplicate_share_l2')}; k_eff {doc.get('k_eff')}; "
            f"mechanism missing {(doc.get('mechanism') or {}).get('missing_families')}")
    print(line)
    if not a.dry_run:
        print(f"  -> {write(doc, a.out)}")
    return 0


__all__ = [
    "FAMILY_INVARIANT_GATES",
    "INHERITANCE_RULE",
    "RETURNS_RHO",
    "SYMBOL_RHO",
    "MinedIndex",
    "apply",
    "build",
    "census",
    "daily",
    "derive_clusters",
    "family_key",
    "family_split",
    "identity",
    "inherit_plan",
    "inheritable",
    "load_clusters",
    "mechanism_line",
    "reaim",
    "returns_merge",
    "rule_key",
    "rule_shape",
    "summary",
    "write",
]

if __name__ == "__main__":
    raise SystemExit(main())
