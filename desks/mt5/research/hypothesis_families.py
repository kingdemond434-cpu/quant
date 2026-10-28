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
    L1  rule       judge_coverage.structural_cell plus the row's CATEGORICAL params (bools,
                   words, the categorical leaves of dicts/lists) -- the same rule on the same
                   instrument; params that are thresholds (lookbacks, z, rr, hours inside a
                   session) collapse here.
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

A LIBRARY, NOT AN EXECUTABLE: its clock is the merge (`merge_docket` leg). For a hand census:

    python -c "from research import hypothesis_families as h; h.main(['--dry-run'])"
"""
from __future__ import annotations

import argparse
import contextlib
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
#: DETERMINISTIC work budget for deriving clusters (never wall-clock: under CPU contention a time
#: limit made the clustering depend on load). Symbols are visited in name order; past either bound
#: a symbol is UNMEASURED. Sized for the full Fusion universe (~1,000 symbols, a few hundred
#: leaders): the comparison bound is far above leaders x symbols at that size.
CLUSTER_MAX_LOADS = 5000
CLUSTER_MAX_COMPARISONS = 2_000_000
#: Prefix of the cluster id of an instrument whose co-movement is UNMEASURED (no bars, or past the
#: work budget). It is its own family for the breadth COUNT (absence never convicts), but in the
#: judge ORDER it is not allowed to outrank a measured representative (absence never acquits).
UNMEASURED_PREFIX = "?"
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


def _atomic_write(path: Path, text: str) -> bool:
    """Write-then-replace; True only when the file now holds `text`.

    Windows refuses `os.replace` onto a READ-ONLY destination (WinError 5) where POSIX allows it
    -- the CLAUDE.md port warning. The read-only bit is cleared and the replace retried once; any
    remaining failure returns False and removes the temp file, never raises."""
    import stat
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(text, "utf-8")
        try:
            os.replace(tmp, path)
        except PermissionError:
            if path.exists():
                os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
            os.replace(tmp, path)
        return True
    except OSError:
        with contextlib.suppress(OSError):
            tmp.unlink(missing_ok=True)
        return False


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
    """L1: judge_coverage's structural cell plus the categorical params (`categorical_suffix`)."""
    if _RULE_CACHE is not None:
        got = _RULE_CACHE.get(id(row))
        if got is not None:
            return got
        got = _rule_key(row)
        _RULE_CACHE[id(row)] = got
        return got
    return _rule_key(row)


#: params judge_coverage's structural cell already reads as an axis (or the grid already holds).
_AXIS_PARAMS = frozenset({"timeframe", "session", "selector", "regime", "condition", "direction",
                          "side", "representation", "feature", "horizon"})

#: PROVENANCE, NOT STRUCTURE: params no family or engine path reads (audit 2026-10-28, grepped
#: across mt5desk, external_gauntlet and orthogonal_sweep). `family_formula` takes `population`
#: only to `del` it; `mechanism_genome`/`crossed_slot` are alpha_genome's narrative of how a cell
#: was bred. Keying on them would split ONE executable rule into two L1 rules by where it came
#: from -- the reverse of the bug `categorical_suffix` fixes, and a flattered breadth census.
_PROVENANCE_PARAMS = frozenset({
    "population", "mechanism_genome", "crossed_slot", "label", "title", "note", "notes",
    "mechanism_note", "why", "reason", "claim", "claim_id", "source", "source_url", "url",
    "producer", "provenance", "origin", "author", "payload_hash", "id"})
_PROVENANCE_SUFFIXES = ("_id", "_url", "_hash", "_note")

#: A numeric literal that is not part of an identifier (`ma20`, `range_v2` keep their digits).
_NUM_LITERAL = re.compile(r"(?<![A-Za-z0-9_.])[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?(?![A-Za-z0-9_])")

#: Bumped whenever the L1 key changes. `daily` is recomputed from the whole bank on every pass, so
#: a change RESTATES the series rather than stepping it; the version says which key a file used.
L1_KEY_VERSION = "structural+categorical-v1.1 (2026-10-28)"


def _categorical(v: Any) -> Any:
    """The structural part of a param value: numbers (thresholds) drop out, words stay.

    A bool, or a string that is not a number, names WHICH rule runs (`exit_on_anchor_flip`,
    `base_family`, `conditioner`); dicts and lists keep their categorical leaves only, so a
    nested lookback still collapses. None means "nothing structural here"."""
    if isinstance(v, bool):
        return v
    if v is None or isinstance(v, (int, float)):
        return None
    if isinstance(v, str):
        txt = v.strip()
        try:
            float(txt)
            return None
        except ValueError:
            # thresholds INSIDE a word collapse too: decay(sum(x,240),8) and (x,120),5) are one rule
            return _NUM_LITERAL.sub("#", txt).lower() or None
    if isinstance(v, Mapping):
        out = {str(k): c for k, c in ((k, _categorical(x)) for k, x in v.items()) if c is not None}
        return out or None
    if isinstance(v, (list, tuple, set, frozenset)):
        items = [c for c in (_categorical(x) for x in v) if c is not None]
        if isinstance(v, (set, frozenset)):
            items.sort(key=lambda c: json.dumps(c, sort_keys=True, default=str))
        return items or None
    return str(v).lower()


def _structural_param(key: str) -> bool:
    k = key.lower()
    return (k not in _AXIS_PARAMS and k not in _PROVENANCE_PARAMS
            and not k.endswith(_PROVENANCE_SUFFIXES))


def categorical_suffix(row: Mapping[str, Any]) -> str:
    """`{...}` of the row's categorical params, or "" when it has none (the key is unchanged).

    judge_coverage's structural cell keys only the named axes, so two rules that differ by a
    categorical param -- an exit_operated cell on base_family=breakout versus base_family=carry
    -- collapsed into one L1 rule and the later one was stamped a duplicate (76.7% L1 duplicate
    share measured 2026-10-28; 33.5% once categoricals count). Thresholds still collapse."""
    params = row.get("params") or {}
    if not isinstance(params, Mapping):
        return ""
    cat = {str(k): c for k, c in ((k, _categorical(params[k])) for k in sorted(params, key=str)
                                  if _structural_param(str(k))) if c is not None}
    return json.dumps(cat, sort_keys=True, separators=(",", ":"), default=str) if cat else ""


def _rule_key(row: dict[str, Any]) -> str:
    if _STRUCT is not None:
        base = _STRUCT(row)[1]
    else:
        params = row.get("params") or {}
        base = "|".join(str(x or "?").lower() for x in (
            _fam(row), _sym(row), row.get("horizon") or params.get("horizon"),
            params.get("timeframe") or row.get("timeframe") or "H1",
            row.get("session") or params.get("session") or params.get("selector"),
            params.get("regime"), params.get("direction") or params.get("side"),
            params.get("representation") or params.get("feature")))
    suffix = categorical_suffix(row)
    return f"{base}|{suffix}" if suffix else base


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


#: Family records published in full. FIXED, not memory-derived: at ~354 B a record, a budget set
#: by free memory published ~140 MB/h at 400k families (audit of 8628268b6). The top clusters
#: carry the duplicates; the rest is summarised by size band and mechanism flag.
DETAIL_FAMILIES = 2000


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
                    max_loads: int = CLUSTER_MAX_LOADS,
                    max_comparisons: int = CLUSTER_MAX_COMPARISONS,
                    universe: Path | None = None) -> dict[str, Any]:
    """Leader clustering of instruments on |corr(daily log returns)| >= rho.

    Deterministic: symbols are visited in name order and each joins the FIRST leader it clears,
    else becomes a leader. Leader (not single-linkage) so EURUSD-GBPUSD-GBPJPY-... cannot chain
    one cluster across instruments that do not themselves co-move. A symbol without a series, or
    past the deterministic work budget, is its own cluster `?SYMBOL` and is listed UNMEASURED."""
    import numpy as np
    uni = universe or UNIVERSE
    load = loader or (lambda s: _daily(s, uni))
    t0 = time.monotonic()
    leaders: list[tuple[str, Any]] = []
    cluster: dict[str, str] = {}
    unmeasured: list[str] = []
    loads = comparisons = 0
    for sym in sorted({str(s).upper() for s in symbols if s}):
        if loads >= max_loads or comparisons + len(leaders) > max_comparisons:
            cluster[sym] = UNMEASURED_PREFIX + sym
            unmeasured.append(sym)
            continue
        loads += 1
        r = load(sym)
        if r is None or len(r) < min_days:
            cluster[sym] = UNMEASURED_PREFIX + sym
            unmeasured.append(sym)
            continue
        home = None
        for lead, lr in leaders:
            comparisons += 1
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
    return {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"), "version": 2, "rho": rho,
            "min_common_days": min_days, "symbols": len(cluster),
            "measured": len(cluster) - len(unmeasured), "unmeasured": sorted(unmeasured),
            "clusters": len(sizes),
            "multi_member": {k: sorted(s for s, c in cluster.items() if c == k)
                             for k, n in sizes.most_common() if n > 1},
            "cluster_of": dict(sorted(cluster.items())),
            "work": {"loads": loads, "comparisons": comparisons, "max_loads": max_loads,
                     "max_comparisons": max_comparisons},
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
        fresh = (age < CLUSTER_MAX_AGE_S and want <= set(doc["cluster_of"])
                 and doc.get("version") == 2)
    if (not fresh) and refresh and want:
        doc = derive_clusters(want, loader)
        _atomic_write(p, json.dumps(doc, indent=1))
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
def _bands(sizes: Iterable[int]) -> dict[str, dict[str, int]]:
    """Families and cells per size band: the summary of every family not published in full."""
    edges = ((1, "1"), (2, "2"), (5, "3-5"), (20, "6-20"), (100, "21-100"), (10 ** 18, ">100"))
    out = {lab: {"families": 0, "cells": 0} for _, lab in edges}
    for n in sizes:
        for hi, lab in edges:
            if n <= hi:
                out[lab]["families"] += 1
                out[lab]["cells"] += int(n)
                break
    return out


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
    keep = detail if detail is not None else min(detail_budget(n_l2), DETAIL_FAMILIES)
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
        "families_on_unmeasured_instruments": sum(1 for fk in fam_cells
                                                  if f"|@{UNMEASURED_PREFIX}" in fk),
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
        "families_summarised": max(0, n_l2 - len(records)),
        "family_size_bands": _bands(fam_cells.values()),
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

    AN INSTRUMENT WITH NO MEASURED CO-MOVEMENT DOES NOT JUMP THE QUEUE. Where the cluster map
    exists but a row's instrument is UNMEASURED (no bars, `?` prefix, or absent from the map), the
    row is a representative only if no earlier row claimed the same rule SHAPE on any instrument;
    otherwise it ranks as a member. Without this, every no-bars singleton read as a fresh family
    and outranked co-moving instruments whose correlation had been measured (audit of 8628268b6).
    The breadth COUNT is unchanged by this: an unmeasured instrument is still its own family there.

    Same claim order as `judge_coverage.variant_split` (never-judged first, then oldest
    first_seen, then docket position), so the representative is the row that would have gone
    first anyway. Removes nothing; `coverage_order` reads it as a tie-break after `_variant`."""
    cl = clusters if clusters is not None else load_clusters(refresh=False)[0]
    ids = unjudged_ids or set()
    n = len(rows)
    first = [""] * n
    keys = [0] * n
    shapes = [0] * n
    unknown = [False] * n
    fresh_idx: list[int] = []
    stale_idx: list[int] = []
    for i, row in enumerate(rows):
        first[i] = str(row.get("first_seen") or "9999")
        r = rule_key(row)
        keys[i] = hash(family_key(row, cl, r))
        shapes[i] = hash(rule_shape(r))
        if cl:
            c = cl.get(_sym(row).upper())
            unknown[i] = c is None or c.startswith(UNMEASURED_PREFIX)
        (fresh_idx if (not ids or str(row.get("_cell") or "") in ids) else stale_idx).append(i)
    order = sorted(fresh_idx, key=first.__getitem__) + sorted(stale_idx, key=first.__getitem__)
    seen: set[int] = set()
    seen_shape: set[int] = set()
    marks = [0] * n
    for i in order:
        if keys[i] in seen or (unknown[i] and shapes[i] in seen_shape):
            marks[i] = 1
        seen.add(keys[i])
        seen_shape.add(shapes[i])
    for i, row in enumerate(rows):
        row["_famdup"] = marks[i]
    return {"rows": n, "family_representatives": n - sum(marks), "family_members": sum(marks),
            "rows_on_unmeasured_instruments": sum(unknown),
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
                     accept: Callable[[str], bool] | None = None) -> str | None:
        """The instrument to move a duplicate onto, or None.

        Candidates: instruments the SAME family already runs on (so the rule is buildable there
        and the lane router already admitted that family on it). Excluded: any instrument whose
        correlation cluster already holds this rule shape, and any `accept` refuses (the lane
        law, the judge's unrunnable bank). Chosen: measured instruments before UNMEASURED ones
        (an unmeasured one may co-move with ground already held), then the thinnest family
        coverage, ties by name -- the emptiest lawful ground."""
        fam = _fam(row)
        held = self.shape_clusters.get(hash(rule_shape(rule_key(row))), set())
        ranked = sorted((self._cluster(sym).startswith(UNMEASURED_PREFIX), n, sym)
                        for sym, n in (self.family_symbols.get(fam) or {}).items()
                        if self._cluster(sym) not in held)
        for _unknown, _n, sym in ranked:
            if accept is None or accept(sym):
                return sym
        return None


def _lawful() -> Callable[[str, str], bool] | None:
    """`universe_policy.may_hypothesise`, or None when it cannot be imported -- and None means
    MINT NOTHING (fail closed): a re-aim the two-lane order cannot vouch for is never minted."""
    try:
        from research.universe_policy import may_hypothesise
    except Exception:
        return None

    def ok(sym: str, fam: str) -> bool:
        try:
            return bool(may_hypothesise(sym, fam))
        except Exception:
            return False
    return ok


def _unrunnable() -> Callable[[dict[str, Any]], bool] | None:
    """True for a spec the judge's unrunnable bank holds (judge_coverage.unrunnable_bank, keyed
    by frontier_identity.docket_cell_id). `order_docket` filters those out of the written docket,
    so a child aimed there would vanish and be re-minted every hour (audit probe P2). None when
    the bank or the identity cannot be read -- the caller then mints nothing (fail closed)."""
    try:
        from research.frontier_identity import docket_cell_id
        from research.judge_coverage import unrunnable_bank
        bank = set(unrunnable_bank())
    except Exception:
        return None

    def blocked(spec: dict[str, Any]) -> bool:
        try:
            return str(docket_cell_id(spec)) in bank
        except Exception:
            return True
    return blocked


REAIM_VERSION = "family-reaim-v1"
#: Provenance a child may carry. NOT `contributing_sources` / `n_independent_sources`: no source
#: named the new instrument, so copying them would overstate agreement (deepening_worker scores on
#: them). The child records 0 sources of its own and names its parent instead.
_SAFE = ("source", "producer", "origin", "title", "url", "source_title", "source_url",
         "mechanism", "mechanism_status", "mechanism_note", "timeframe", "chart")


def reaimed_parents(path: Path | None = None) -> set[str]:
    """Every parent identity the LEDGER says was re-aimed -- the only memory of "once, ever".

    Never the child rows in the docket: `order_docket` can filter a child out of the written file,
    and a memory that lives in the docket forgets it (audit probe P2). A malformed (torn) line is
    skipped; an absent ledger is an empty set."""
    out: set[str] = set()
    try:
        with (path or REAIM_LEDGER).open(encoding="utf-8") as fh:
            for ln in fh:
                try:
                    row = json.loads(ln)
                except ValueError:
                    continue
                if isinstance(row, dict) and row.get("parent"):
                    out.add(str(row["parent"]))
    except OSError:
        pass
    return out


def reaim(rows: list[dict[str, Any]], fresh: set[str], reproposed: set[str], *,
          identity_fn: Callable[[dict[str, Any]], str] = identity,
          clusters: Mapping[str, str] | None = None,
          lawful: Callable[[str, str], bool] | None = None,
          blocked: Callable[[dict[str, Any]], bool] | None = None,
          done: set[str] | None = None,
          now: datetime | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Check every fresh row against what was mined before it; re-aim each duplicate.

    `fresh` = identities this pass's producers emitted that the bank did not hold; `reproposed`
    = identities they emitted that the bank DID hold (EXACT duplicates the merge collapsed).
    `done` = parents already re-aimed: the UNION of the ledger (`reaimed_parents`) and every
    `reaimed_from.parent_identity` already in `rows`. The ledger covers a child the judge later
    filtered out of the docket; the docket covers a child that was written but whose ledger line
    never was (crash after the docket write, or a failed report write). `lawful` and
    `blocked` default to the lane law and the unrunnable bank; if either cannot be resolved the
    check still runs and NOTHING is minted (fail closed), with the reason in the report.
    Returns (children, report). Inputs are never removed: a duplicate stays in the docket."""
    at = (now or datetime.now(UTC)).astimezone(UTC).isoformat(timespec="seconds")
    cl = clusters or {}
    law = lawful if lawful is not None else _lawful()
    block = blocked if blocked is not None else _unrunnable()
    closed = [why for why, f in (("lane law (universe_policy) unavailable", law),
                                 ("unrunnable bank unreadable", block)) if f is None]
    idents = [identity_fn(r) for r in rows]
    prior_i = [i for i, ident in enumerate(idents) if ident not in fresh]
    index = MinedIndex((rows[i] for i in prior_i), cl, (idents[i] for i in prior_i))
    present = set(idents)
    # ONCE PER PARENT, EVER -- the ledger OR a child already in the docket, whichever survived.
    done = set(done) if done is not None else reaimed_parents()
    done |= _parents_in(rows)
    counts: Counter[str] = Counter()
    by_producer: dict[str, Counter[str]] = {}
    children: list[dict[str, Any]] = []
    no_target = 0
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
        if status == "NOVEL" or closed:
            continue
        if ident in done:
            counts["already_reaimed"] += 1
            continue
        fam, params = _fam(row), dict(row.get("params") or {})

        def make(sym: str, row: dict[str, Any] = row, fam: str = fam,
                 params: dict[str, Any] = params) -> dict[str, Any]:
            c = {k: row[k] for k in _SAFE if k in row}
            c.update({"symbol": sym, "family": fam, "params": dict(params),
                      "contributing_sources": [], "n_independent_sources": 0})
            return c

        def accept(sym: str, fam: str = fam, make: Callable[[str], dict[str, Any]] = make
                   ) -> bool:
            assert law is not None and block is not None
            if not law(sym, fam):
                return False
            # the bank is keyed by the docket's own cell id, so it is asked about the CHILD ROW
            # itself (row-level timeframe/chart included), exactly as order_docket will see it
            if block(make(sym)):
                counts["target_unrunnable"] += 1
                return False
            return True
        target = index.reaim_target(row, accept)
        if target is None:
            no_target += 1
            continue
        child = make(target)
        key = identity_fn(child)
        if key in present:
            counts["reaim_already_present"] += 1
            continue
        child["reaimed_from"] = {"version": REAIM_VERSION, "parent_identity": ident,
                                 "parent_status": status, "at": at,
                                 "parent_n_independent_sources": row.get("n_independent_sources"),
                                 "why": ("the parent duplicated ground already mined; the same "
                                         "rule is moved to the thinnest lawful instrument whose "
                                         "correlation cluster holds no member of it")}
        child["available_time"] = at
        child["ingested_time"] = at
        child["source_version"] = REAIM_VERSION
        child["payload_hash"] = hashlib.sha256(json.dumps(
            {"symbol": target, "family": fam, "params": params,
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
              "fail_closed": closed or None,
              "target_unrunnable_skips": counts.get("target_unrunnable", 0),
              "reaim_already_present": counts.get("reaim_already_present", 0),
              "already_reaimed_parents": counts.get("already_reaimed", 0),
              "by_producer": {p: dict(c) for p, c in sorted(by_producer.items())},
              "mint_conservation": {"fresh_in": checked, "rows_out": checked + len(children),
                                    "removed": 0},
              "rule": ("a duplicate is KEPT and a re-aimed descendant is minted beside it; "
                       "nothing is deleted, so the mint rate can only rise. Once per parent, "
                       "ever: reaim_ledger.jsonl OR a child already in the docket")}
    return children, report


class Pending:
    """The re-aim's last step, held until the caller has DURABLY written the docket.

    THE ORDER IS THE GUARANTEE (audit of 8628268b6). Children first (the caller's docket write),
    then the report, then the ledger -- so the ledger can never claim a child that does not exist.
    A crash before the docket write leaves no child and no ledger line (the next pass re-mints
    what never existed). A crash after it -- or a failed report write -- leaves children in the
    docket without ledger lines; the next pass reads each child's `reaimed_from.parent_identity`
    out of the docket into its done-set and re-aims none of those parents again. Either way: at
    most once. Durable children are matched to the written rows by IDENTITY KEY, never by object
    id, so a copied row list still counts."""

    def __init__(self, children: list[dict[str, Any]], doc: Mapping[str, Any] | None,
                 report_path: Path | None, ledger_path: Path | None,
                 identity_fn: Callable[[dict[str, Any]], str] = identity) -> None:
        self.children = children
        self.doc = doc
        self.report_path = report_path
        self.ledger_path = ledger_path
        self.identity_fn = identity_fn

    def commit(self, written: Iterable[dict[str, Any]], *, publish_report: bool = True
               ) -> dict[str, Any]:
        """`written` is the row list the caller just wrote. Returns what was recorded."""
        keys = {self.identity_fn(r) for r in written if r.get("reaimed_from")}
        durable = [c for c in self.children if self.identity_fn(c) in keys]
        report_ok = True
        if publish_report and self.doc is not None:
            report_ok = write(self.doc, self.report_path)
        lines = 0
        if report_ok and durable:
            lines = append_reaim_ledger(durable, self.ledger_path)
        return {"children": len(self.children), "durable": len(durable),
                "report_written": report_ok, "ledger_lines": lines,
                "why": None if report_ok else "report write failed: ledger NOT written"}


def _parents_in(rows: Iterable[Mapping[str, Any]]) -> set[str]:
    """Parents whose re-aimed child is already in the docket rows (the ledger's twin)."""
    out: set[str] = set()
    for r in rows:
        rf = r.get("reaimed_from")
        if isinstance(rf, Mapping) and rf.get("parent_identity"):
            out.add(str(rf["parent_identity"]))
    return out


def append_reaim_ledger(children: list[dict[str, Any]], path: Path | None = None) -> int:
    """One line per DURABLE re-aimed child: parent and child identity. Called only by
    `Pending.commit`, after the docket and the report are written. Never raises."""
    if not children:
        return 0
    p = path or REAIM_LEDGER
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        text = "".join(json.dumps({"at": c["reaimed_from"]["at"], "symbol": c["symbol"],
                                   "family": c["family"],
                                   "parent": c["reaimed_from"]["parent_identity"],
                                   "parent_status": c["reaimed_from"]["parent_status"],
                                   "child": identity(c)}, default=str) + "\n"
                       for c in children)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
    except OSError:
        return 0
    return len(children)


# --------------------------------------------------------------------------- the merge hook
def apply(rows: list[dict[str, Any]], *, fresh: set[str], reproposed: set[str],
          identity_fn: Callable[[dict[str, Any]], str] = identity,
          now: datetime | None = None,
          report_path: Path | None = None,
          hyp_dir: Path | None = None
          ) -> tuple[list[dict[str, Any]], dict[str, Any], Pending | None]:
    """`merge_hypotheses`' one call: re-aim fresh duplicates and census the docket.

    Returns (rows plus re-aimed children, compact block for merge_report, Pending). Writes
    NOTHING but the cluster cache: the caller writes the docket and then calls
    `Pending.commit(rows_written)`, which writes the report and, last, the ledger. Never raises:
    a fault costs the census and the re-aim (Pending None), never a row. `hyp_dir` is the caller's
    hypotheses directory (the cluster cache and the ledger live beside the docket it writes)."""
    global _RULE_CACHE
    avail = _mem_available_mb()
    # ~400 B per cached key; cache only when it costs under a quarter of what is free right now.
    if avail is None or avail * 1024 ** 2 * 0.25 > len(rows) * 400:
        _RULE_CACHE = {}
    ledger = (hyp_dir / REAIM_LEDGER.name) if hyp_dir is not None else REAIM_LEDGER
    try:
        syms = {_sym(r).upper() for r in rows} - {""}
        clusters, cmeta = load_clusters(
            syms, path=(hyp_dir / CLUSTERS.name) if hyp_dir is not None else None)
        children, rep = reaim(rows, fresh, reproposed, identity_fn=identity_fn,
                              clusters=clusters, done=reaimed_parents(ledger), now=now)
        # THE REVERT PATH, not a throttle: QUANT_FAMILY_REAIM=0 keeps the check, the stamps and
        # the census and mints no descendant (the duplicates were never removed either way).
        if os.environ.get("QUANT_FAMILY_REAIM", "1") == "0":
            rep["reaim_enabled"] = False
            rep["reaimed_would_have_been"] = len(children)
            rep["reaimed"] = 0
            children = []
        else:
            rep["reaim_enabled"] = True
        out = rows + children
        doc = build(out, clusters=clusters, cluster_meta=cmeta, reaim_report=rep)
        return out, summary(doc), Pending(children, doc, report_path, ledger, identity_fn)
    except Exception as exc:
        return rows, {"status": f"FAILED: {type(exc).__name__}: {exc}"[:300]}, None
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
        "l1_key": L1_KEY_VERSION,
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
            "l3_status", "duplicate_share_l1", "duplicate_share_l2", "k_eff", "k_eff_readings",
            "l1_key")
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


def write(doc: Mapping[str, Any], path: Path | None = None) -> bool:
    """Publish the report atomically; False (never an exception) when it could not be written."""
    return _atomic_write(path or REPORT, json.dumps(doc, indent=1, default=str))


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
        print(f"  -> written={write(doc, a.out)}")
    return 0


__all__ = [
    "FAMILY_INVARIANT_GATES",
    "INHERITANCE_RULE",
    "RETURNS_RHO",
    "SYMBOL_RHO",
    "MinedIndex",
    "Pending",
    "apply",
    "build",
    "census",
    "daily",
    "derive_clusters",
    "family_key",
    "family_split",
    "identity",
    "inheritable",
    "load_clusters",
    "mechanism_line",
    "reaim",
    "reaimed_parents",
    "returns_merge",
    "rule_key",
    "rule_shape",
    "summary",
    "write",
]
