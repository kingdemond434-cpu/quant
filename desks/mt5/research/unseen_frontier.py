"""THE UNSEEN FRONTIER: how much mechanism ground the desk has never seen, counted the way a
field ecologist counts the species it has NOT caught yet.

WHY THIS EXISTS (Global Intelligence Organization item W3, principal 2026-09-16)

Every miner here reports what it FOUND. None could say what it MISSED. A crawler returning 200
claims from one forum is silent on whether that forum holds 210 mechanisms or 2,000 -- and the
difference decides whether the next hour spent there is the best hour the desk has or a waste of
the multiplicity budget. The answer is already in the catch, in the shape of the REPEATS: a haul
of singletons comes from ground still mostly unseen, a haul of the same thing over and over from
ground that is emptied. Chao1 reads exactly that -- singletons squared over twice the doubletons
-- and Good-Turing turns the singleton share into the chance that the NEXT sighting is something
already in hand.

A MECHANISM IS THE SPECIES, AND A PARAMETER VARIANT IS NOT A NEW ONE. That is the whole reason
this is not a row count: `hypothesis_graph.jsonl` carries 24,150 `discovered` rows whose parameter
kinds are the identical four (band, feature, horizon, side). Counted as rows it is the richest
ground on the desk. Counted as SPECIES -- the mechanism cluster plus the ordered set of parameter
KINDS and feature NAMES, never their values -- most of it is one mechanism sampled twenty-four
thousand times, which is the measurement the allocator needs and the row count actively hides.

WHAT IT REFUSES TO GUESS. A row naming no mechanism this desk's vocabulary knows AND no feature is
not bucketed, not inferred and not quietly dropped: it is COUNTED in `unmeasured` (L1.28a). That
is 57k intake rows today -- track records tagged `ea_robot`/`gold`, swap tables, speeches -- and
folding such venue tags into the species key would have read 7,496 amarkets rows as ONE saturated
species. Under-counting species points straight at "stop hunting here", so a coarse tag may
RESOLVE a mechanism when it names one and never stands in for a feature. A ground with no
sightings is UNMEASURED, never exhausted: exhaustion needs per-axis evidence (L1.51), and
SATURATING -- which also needs 300 quiet leads, so no thin ground can claim it -- is the strongest
word here. The vocabulary is the desk's own (`axis_registry.classify_family`); if that import
fails it falls back to `AXIS_REGISTRY.json`'s axis and every family maps to UNKNOWN, counted.

WHAT IT NEVER DOES. It ranks ground; it never gates one. Nothing vetoes a candidate, caps a book
or shrinks a fraction, and SATURATING is not a licence to stop hunting -- only the desk saying
where the next hour buys less than the hour before it did.

    python desks/mt5/research/unseen_frontier.py [--dry-run]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from itertools import chain
from pathlib import Path
from typing import Any, NamedTuple

import numpy as np

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parents[1]
for _p in (str(REPO), str(BASE), str(BASE / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

CLAIMS = BASE / "data" / "deep_forest_claims.jsonl"
DEEP_FOREST = BASE / "reports" / "DEEP_FOREST.json"
INTELLIGENCE = BASE / "data" / "intelligence"
GRAPH = BASE / "data" / "hypothesis_graph.jsonl"
AXIS_REPORT = BASE / "reports" / "AXIS_REGISTRY.json"
OUT_REPORT = BASE / "reports" / "UNSEEN_FRONTIER.json"
OUT_HISTORY = BASE / "data" / "unseen_frontier_history.jsonl"

#: The box holding the live terminal has 8 GB and a dozen resident pythons. Every bound here says
#: TOO_LARGE or TRUNCATED in the report rather than pretending the input was absent.
MAX_INPUT_BYTES = 64 * 1024 * 1024
MAX_JSONL_LINES = 200_000
MAX_HISTORY_LINES = 50_000
MAX_DISCOVERY_FILES = 3000
MAX_SIGHTINGS = 400_000
UNKNOWN = "UNKNOWN"
LEAD_BUCKET = 100
CURVE_POINTS = 120
RECENT_LEADS = 300
RECENT_NEW_SPECIES = 3
SATURATED_COVERAGE = 0.90
OPEN_COVERAGE = 0.60
HISTORY_KEEP = 20
TOP_N = 10
Z95 = 1.959964

RULE = ("N_unseen from Chao1/Good-Turing over canonical mechanism hashes; parameter variants are "
        "one species")

#: The deep forest's coarse claim class -> the desk's own mechanism vocabulary. BY HAND and short
#: of a guess: `other` maps to nothing, because a claim whose class is "other" has said its class
#: is unknown, and the count of those is exactly the thing worth seeing.
CLASS_MECHANISM = {
    "policy": "macro_release", "calendar": "calendar_seasonality",
    "positioning": "positioning_crowding", "inventory": "inventory_shock",
    "flow": "hedging_demand_close_flow", "carry": "carry_rollover",
    "cross_asset": "cross_market_lead", "microstructure": "execution_microstructure",
    "reversion": "range_reversion", "momentum": "trend_persistence",
}
#: Parameter keys whose VALUE is a name rather than a magnitude -- the feature being measured, not
#: how much of it. Only these contribute their value to the species key. Symbol-valued keys
#: (`factor_symbols`, `driver_symbol`, `peer_symbol`) deliberately do NOT: one mechanism run over
#: five hundred pairs is one mechanism sampled five hundred times, and the instrument already has
#: an axis of its own in the cell key.
FEATURE_KEYS = frozenset({"feature", "features", "factor", "factors", "expr", "expression",
                          "signal", "indicator", "quantity", "quantities", "input_source",
                          "mechanism"})
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
_TS_KEYS = ("found_at", "available_time", "at", "ingested_time", "published", "date",
            "event_time", "published_time", "generated_utc")
_AC_CACHE: dict[str, str] = {}


class Sighting(NamedTuple):
    """One observation of one mechanism by one miner, on one ground, at one time."""

    ground_id: str
    language: str
    source: str
    site: str
    asset_class: str
    mechanism: str
    species: str
    at: str
    obs_id: str


# ------------------------------------------------------------------ tolerant reading
def _read_json(path: Path, note: dict[str, str]) -> Any:
    """Parse `path`, or record exactly why it produced nothing. Never raises."""
    try:
        size = path.stat().st_size
    except OSError:
        note[path.name] = "ABSENT"
        return None
    if size > MAX_INPUT_BYTES:
        note[path.name] = f"TOO_LARGE({size})"
        return None
    try:
        doc = json.loads(path.read_text("utf-8-sig"))
    except (OSError, ValueError) as exc:
        note[path.name] = f"UNREADABLE({type(exc).__name__})"
        return None
    note[path.name] = "READ"
    return doc


def _iter_jsonl(path: Path, note: dict[str, str], cap: int) -> Iterator[dict[str, Any]]:
    """Stream a JSONL ledger. 18 MB of graph is never materialised as a list on an 8 GB box."""
    try:
        handle = path.open(encoding="utf-8-sig")
    except OSError:
        note[path.name] = "ABSENT"
        return
    seen = 0
    with handle as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            if seen >= cap:
                note[path.name] = f"TRUNCATED({cap})"
                return
            seen += 1
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                yield row
    note[path.name] = f"READ({seen})"


# ------------------------------------------------------------------ the desk's own vocabulary
def classify_family(family: Any) -> str:
    """The mechanism the desk's own family table gives this family, or UNKNOWN. Never guesses."""
    try:
        from axis_registry import classify_family as _cf
    except Exception:
        return UNKNOWN
    try:
        return str(_cf(family)[0]) or UNKNOWN
    except Exception:
        return UNKNOWN


def asset_class_of(symbols: Any) -> str:
    """The broker registry's class for the first symbol that has one; UNKNOWN otherwise."""
    candidates = symbols if isinstance(symbols, list | tuple) else [symbols]
    for sym in candidates:
        key = str(sym or "").strip()
        if not key:
            continue
        if key not in _AC_CACHE:
            try:
                from research.universe_policy import asset_class_of as _ac
                _AC_CACHE[key] = _tok(_ac(key))
            except Exception:
                _AC_CACHE[key] = ""
        if _AC_CACHE[key]:
            return _AC_CACHE[key]
    return UNKNOWN


def vocabulary(note: dict[str, str]) -> frozenset[str]:
    """The mechanism axis as AXIS_REGISTRY.json last published it -- the report's own words."""
    doc = _read_json(AXIS_REPORT, note)
    axes = doc.get("axes") if isinstance(doc, dict) else None
    mech = axes.get("mechanism") if isinstance(axes, dict) else None
    return frozenset(str(k) for k in mech) if isinstance(mech, dict) else frozenset()


# ------------------------------------------------------------------ the species key
def _tok(value: Any) -> str:
    return "_".join(str(value or "").strip().lower().replace("-", " ").replace("_", " ").split())


def _names(value: Any, out: set[str] | None = None) -> set[str]:
    """Every NAME inside a value: words, never numbers. `ts_rank(spread, 240)` -> ts, rank,
    spread. The 240 is a parameter value, and a parameter value is never a new species."""
    acc: set[str] = out if out is not None else set()
    if isinstance(value, str):
        acc.update(w.lower() for w in _WORD.findall(value))
    elif isinstance(value, list | tuple | set):
        for item in value:
            _names(item, acc)
    elif isinstance(value, dict):
        for item in value.values():
            _names(item, acc)
    return acc


def kind_set(params: Any, extra_names: Any = None) -> frozenset[str]:
    """The ordered set of parameter KINDS and feature NAMES that identifies a mechanism."""
    kinds: set[str] = set()
    if isinstance(params, dict):
        for key, val in params.items():
            token = _tok(key)
            if not token:
                continue
            kinds.add(token)
            if token in FEATURE_KEYS:
                _names(val, kinds)
    if extra_names is not None:
        _names(extra_names, kinds)
    return frozenset(k for k in kinds if k)


def species_key(mechanism: str, kinds: frozenset[str]) -> str:
    """The canonical mechanism hash: the cluster plus the ordered kind set, hashed for the
    ledger. Two rows that differ only in what their parameters are SET TO hash identically."""
    payload = f"{mechanism}|{' '.join(sorted(kinds))}"
    return hashlib.blake2b(payload.encode("utf-8"), digest_size=8).hexdigest()


def mechanism_of(family: Any = None, tags: Any = None, mech_class: Any = None) -> str:
    """Family table first, then a tag that is itself a family, then the coarse claim class."""
    if family:
        named = classify_family(family)
        if named != UNKNOWN:
            return named
    for tag in tags if isinstance(tags, list | tuple) else ():
        named = classify_family(tag)
        if named != UNKNOWN:
            return named
        mapped = CLASS_MECHANISM.get(_tok(tag))
        if mapped:
            return mapped
    return CLASS_MECHANISM.get(_tok(mech_class), UNKNOWN)


def _stamp(row: dict[str, Any]) -> str:
    for key in _TS_KEYS:
        val = row.get(key)
        if isinstance(val, str) and val:
            return val
    return ""


def _obs_id(row: dict[str, Any], fallback: str) -> str:
    for key in ("claim_hash", "id", "mechanism_key", "signal_id"):
        val = row.get(key)
        if val:
            return str(val)
    url, title = str(row.get("url") or ""), str(row.get("title") or "")
    payload = f"{url}|{title}" if (url or title) else fallback
    return hashlib.blake2b(payload.encode("utf-8"), digest_size=8).hexdigest()


def sighting(row: dict[str, Any], *, language: Any, source: Any, site: Any, symbols: Any,
             family: Any = None, tags: Any = None, mech_class: Any = None, params: Any = None,
             names: Any = None, fallback: str = "") -> Sighting | None:
    """A row becomes a sighting only when it names a mechanism or a feature; a row that names
    neither is not a sighting of anything and is counted as such by the caller."""
    mechanism = mechanism_of(family, tags, mech_class)
    kinds = kind_set(params, names)
    if mechanism == UNKNOWN and not kinds:
        return None
    lang = _tok(language) or UNKNOWN
    src = _tok(source) or UNKNOWN
    return Sighting(ground_id=sys.intern(f"{lang}|{src}"), language=sys.intern(lang),
                    source=sys.intern(src), site=str(site or UNKNOWN),
                    asset_class=sys.intern(asset_class_of(symbols)),
                    mechanism=sys.intern(mechanism),
                    species=sys.intern(species_key(mechanism, kinds)),
                    at=_stamp(row), obs_id=_obs_id(row, fallback))


# ------------------------------------------------------------------ the four grounds
def _keep(out: list[Sighting], shot: Sighting | None, stats: Counter[str]) -> None:
    """A sighting joins the haul; a row that sighted nothing joins the count of what did not."""
    if shot is None:
        stats["rows_without_mechanism"] += 1
    else:
        out.append(shot)


def _claim_shot(row: dict[str, Any], i: int, source: Any, symbols: Any) -> Sighting | None:
    """A mined claim: its class is the mechanism, its quantities are the feature names."""
    return sighting(row, language=row.get("language") or row.get("lang"), source=source,
                    site=row.get("ground"), symbols=symbols,
                    mech_class=row.get("mechanism_class"), names=row.get("quantities"),
                    fallback=f"claim:{i}")


def from_claims(note: dict[str, str], stats: Counter[str]) -> list[Sighting]:
    """`deep_forest_claims.jsonl`: one mined claim, its language, its ground, its quantities."""
    out: list[Sighting] = []
    for i, row in enumerate(_iter_jsonl(CLAIMS, note, MAX_JSONL_LINES)):
        stats["claim_rows"] += 1
        inst = row.get("instruments")
        _keep(out, _claim_shot(row, i, row.get("source"),
                               inst.get("analogues") if isinstance(inst, dict) else None), stats)
    return out


def from_deep_forest(note: dict[str, str], stats: Counter[str]) -> tuple[list[Sighting], set[str]]:
    """`DEEP_FOREST.json`: the miner's own top claims, and every ground it has NAMED -- a ground
    the crawler knows and has never returned a claim from is unseen territory by the plainest
    measure there is, so it is counted rather than inferred away."""
    doc = _read_json(DEEP_FOREST, note)
    if not isinstance(doc, dict):
        return [], set()
    named = {str(g.get("ground")) for g in (doc.get("grounds") or [])
             if isinstance(g, dict) and g.get("ground")}
    out: list[Sighting] = []
    for i, row in enumerate(doc.get("top_claims") or []):
        if not isinstance(row, dict):
            continue
        stats["deep_forest_rows"] += 1
        _keep(out, _claim_shot(row, i, row.get("source") or "deep_forest",
                               row.get("symbols")), stats)
    return out, named


def _discovery_files() -> list[Path]:
    try:
        paths = list(INTELLIGENCE.glob("*/discoveries_*.json"))
    except OSError:
        return []
    paths.sort(key=lambda p: (p.stat().st_mtime if p.exists() else 0.0), reverse=True)
    return paths[:MAX_DISCOVERY_FILES]


def from_discoveries(note: dict[str, str], stats: Counter[str]) -> list[Sighting]:
    """The seats' intake: `data/intelligence/<seat>/discoveries_*.json`, newest files first."""
    files = _discovery_files()
    stats["discovery_files_seen"] = len(files)
    if not files:
        note[INTELLIGENCE.name] = "ABSENT"
        return []
    out: list[Sighting] = []
    for path in files:
        try:
            doc = json.loads(path.read_text("utf-8-sig"))
        except (OSError, ValueError):
            stats["discovery_files_unreadable"] += 1
            continue
        rows = doc if isinstance(doc, list) else doc.get("discoveries")
        if not isinstance(rows, list):
            continue
        stats["discovery_files_read"] += 1
        for i, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            stats["discovery_rows"] += 1
            _keep(out, sighting(
                row, language=row.get("lang") or row.get("language"),
                source=row.get("source") or path.parent.name,
                site=row.get("ground") or path.parent.name, symbols=row.get("symbols"),
                family=row.get("family"), tags=row.get("mechanism_tags"),
                mech_class=row.get("mechanism_class"), params=row.get("params"),
                names=row.get("mechanism"), fallback=f"{path.name}:{i}"), stats)
    note[INTELLIGENCE.name] = f"READ({stats['discovery_files_read']}/{len(files)})"
    return out


def from_graph(note: dict[str, str], stats: Counter[str]) -> list[Sighting]:
    """`hypothesis_graph.jsonl`: family, source, and the params fingerprint -- KINDS, not values."""
    out: list[Sighting] = []
    for i, row in enumerate(_iter_jsonl(GRAPH, note, MAX_JSONL_LINES)):
        stats["graph_rows"] += 1
        _keep(out, sighting(row, language=row.get("lang") or row.get("language"),
                            source=str(row.get("source") or "").split(":")[0],
                            site=str(row.get("source") or UNKNOWN), symbols=row.get("symbol"),
                            family=row.get("family"), params=row.get("params"),
                            fallback=f"graph:{i}"), stats)
    return out


def collect(note: dict[str, str], stats: Counter[str]) -> tuple[list[Sighting], set[str]]:
    """Every sighting the box can see, deduped on observation id, ordered by first sighting.

    The claims ledger is read before the report that summarises it, so a claim listed in both
    keeps the richer row. A REPEAT telling is a different row with a different id and survives --
    repeats are the entire signal Chao1 reads.
    """
    top, named = from_deep_forest(note, stats)
    seen: set[str] = set()
    out: list[Sighting] = []
    for shot in chain(from_claims(note, stats), top, from_discoveries(note, stats),
                      from_graph(note, stats)):
        if shot.obs_id in seen:
            stats["duplicate_observations"] += 1
            continue
        seen.add(shot.obs_id)
        out.append(shot)
        if len(out) >= MAX_SIGHTINGS:
            note["sightings"] = f"TRUNCATED({MAX_SIGHTINGS})"
            break
    out.sort(key=lambda s: (s.at or "9999", s.obs_id))
    return out, named


# ------------------------------------------------------------------ the estimators
def chao1(counts: Sequence[int]) -> dict[str, Any]:
    """Chao1 with its log-normal 95% CI, and Good-Turing sample coverage.

    f2 = 0 takes the bias-corrected branch -- the case a thinly sampled ground is nearly always
    in, and the case where the uncorrected ratio would divide by zero.
    """
    freqs = [int(c) for c in counts if int(c) > 0]
    n, s_obs = sum(freqs), len(freqs)
    f1 = sum(1 for c in freqs if c == 1)
    f2 = sum(1 for c in freqs if c == 2)
    if f2 > 0:
        n_hat = s_obs + (f1 * f1) / (2.0 * f2)
        ratio = f1 / f2
        var = f2 * (0.5 * ratio ** 2 + ratio ** 3 + 0.25 * ratio ** 4)
    else:
        n_hat = s_obs + f1 * (f1 - 1) / 2.0
        var = f1 * (f1 - 1) / 2.0 + f1 * (2 * f1 - 1) ** 2 / 4.0
        var -= (f1 ** 4) / (4.0 * n_hat) if n_hat > 0 else 0.0
    var = max(float(var), 0.0)
    delta = float(n_hat - s_obs)
    if delta > 0 and var > 0:
        spread = math.exp(Z95 * math.sqrt(math.log1p(var / (delta * delta))))
        ci = [s_obs + delta / spread, s_obs + delta * spread]
    else:
        ci = [float(s_obs), float(n_hat)]
    return {"n": n, "s_obs": s_obs, "f1": f1, "f2": f2,
            "n_hat": round(float(n_hat), 6), "n_unseen": round(max(0.0, delta), 6),
            "ci95": [round(ci[0], 6), round(ci[1], 6)], "bias_corrected": f2 == 0,
            "coverage": round(1.0 - f1 / n, 9) if n else None,
            "saturation": round(s_obs / n_hat, 9) if n_hat > 0 else None}


def discovery_curve(order: Sequence[str]) -> list[dict[str, int]]:
    """New species per `LEAD_BUCKET` leads, in the order the ground actually yielded them."""
    buckets: list[int] = []
    seen: set[str] = set()
    for i, sp in enumerate(order):
        idx = i // LEAD_BUCKET
        while len(buckets) <= idx:
            buckets.append(0)
        if sp not in seen:
            seen.add(sp)
            buckets[idx] += 1
    curve: list[dict[str, int]] = []
    cumulative, total = 0, len(order)
    for idx, new in enumerate(buckets):
        cumulative += new
        start = idx * LEAD_BUCKET
        curve.append({"lead": start, "leads": min(LEAD_BUCKET, total - start),
                      "new_species": new, "cumulative_species": cumulative})
    return curve


def recent_new_species(order: Sequence[str], window: int = RECENT_LEADS) -> int:
    """Species whose FIRST sighting falls inside the last `window` leads -- the saturation test."""
    if not order:
        return 0
    cut = max(0, len(order) - window)
    seen = set(order[:cut])
    fresh: set[str] = set()
    for sp in order[cut:]:
        if sp not in seen:
            seen.add(sp)
            fresh.add(sp)
    return len(fresh)


def fit_saturation(curve: Sequence[dict[str, int]]) -> dict[str, Any] | None:
    """S(n) = S_max * n / (n + k), fitted in the linearisation 1/S = 1/S_max + (k/S_max)(1/n).

    Three points is the floor. Below it there is no curve and None is the honest answer, and a
    fit whose asymptote comes out non-positive says so rather than publishing a number.
    """
    pts = [(p["lead"] + p["leads"], p["cumulative_species"]) for p in curve
           if p["leads"] > 0 and p["cumulative_species"] > 0]
    if len(pts) < 3:
        return None
    x = np.array([1.0 / n for n, _ in pts], dtype=float)
    y = np.array([1.0 / s for _, s in pts], dtype=float)
    design = np.vstack([np.ones_like(x), x]).T
    coeff = np.linalg.lstsq(design, y, rcond=None)[0]
    intercept, slope = float(coeff[0]), float(coeff[1])
    if intercept <= 0 or slope < 0:
        return {"fitted": False, "why": "the linearised fit gives no positive asymptote",
                "points": len(pts)}
    s_max = 1.0 / intercept
    half = slope * s_max
    obs = np.array([float(s) for _, s in pts])
    pred = np.array([s_max * n / (n + half) if (n + half) > 0 else 0.0 for n, _ in pts])
    ss_res = float(((obs - pred) ** 2).sum())
    ss_tot = float(((obs - obs.mean()) ** 2).sum())
    return {"fitted": True, "s_max": round(s_max, 6), "half_at_leads": round(half, 6),
            "r2": round(1.0 - ss_res / ss_tot, 6) if ss_tot > 0 else None, "points": len(pts)}


def verdict(coverage: float | None, fresh: int, n: int) -> str:
    """SATURATING needs BOTH a covered sample and a quiet recent tail; OPEN is the coverage floor
    on its own; between them is MIXED, and a ground with nothing in it is UNMEASURED."""
    if not n or coverage is None:
        return "UNMEASURED"
    if coverage > SATURATED_COVERAGE and fresh < RECENT_NEW_SPECIES:
        return "SATURATING"
    if coverage < OPEN_COVERAGE:
        return "OPEN"
    return "MIXED"


def estimate(order: Sequence[str], *, curve: bool = True) -> dict[str, Any]:
    """The whole reading for one ordered stream of species sightings."""
    block = chao1(list(Counter(order).values()))
    fresh = recent_new_species(order)
    block[f"new_species_last_{RECENT_LEADS}"] = fresh
    block["verdict"] = verdict(block["coverage"], fresh, block["n"])
    if curve:
        full = discovery_curve(order)
        block["fit"] = fit_saturation(full)
        block["discovery_curve"] = full[-CURVE_POINTS:]
        block["curve_points_dropped"] = max(0, len(full) - CURVE_POINTS)
    return block


# ------------------------------------------------------------------ history
def read_history(note: dict[str, str]) -> dict[str, list[dict[str, Any]]]:
    """Prior runs, per ground, so the discovery curve spans runs and not just this hour's haul."""
    hist: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in _iter_jsonl(OUT_HISTORY, note, MAX_HISTORY_LINES):
        gid = str(row.get("ground_id") or "")
        if gid:
            hist[gid].append({k: row.get(k) for k in
                              ("at", "n", "s_obs", "n_hat", "coverage", "verdict")})
    return {gid: rows[-HISTORY_KEEP:] for gid, rows in hist.items()}


# ------------------------------------------------------------------ the report
def _headline(block: dict[str, Any]) -> dict[str, Any]:
    return {k: block[k] for k in
            ("n", "s_obs", "n_hat", "n_unseen", "coverage", "saturation", "verdict")}


def build() -> dict[str, Any]:
    """Read every ground, estimate every ground and every cell, and say what went unmeasured."""
    note: dict[str, str] = {}
    stats: Counter[str] = Counter()
    vocab = vocabulary(note)
    sightings, named_grounds = collect(note, stats)
    history = read_history(note)

    by_ground: dict[str, list[Sighting]] = defaultdict(list)
    by_cell: dict[str, list[Sighting]] = defaultdict(list)
    for shot in sightings:
        by_ground[shot.ground_id].append(shot)
        by_cell[f"{shot.asset_class}|{shot.mechanism}"].append(shot)

    grounds: dict[str, Any] = {}
    for gid, shots in by_ground.items():
        block = estimate([s.species for s in shots])
        sites = Counter(s.site for s in shots)
        block.update({"language": shots[0].language, "source": shots[0].source,
                      "sites": [s for s, _ in sites.most_common(5)], "n_sites": len(sites),
                      "asset_classes": sorted({s.asset_class for s in shots}),
                      "mechanisms": sorted({s.mechanism for s in shots}),
                      "first_seen": shots[0].at, "last_seen": shots[-1].at,
                      "history": history.get(gid, [])})
        grounds[gid] = block

    cells: dict[str, Any] = {}
    for key, shots in by_cell.items():
        block = estimate([s.species for s in shots], curve=False)
        block.update({"asset_class": shots[0].asset_class, "mechanism": shots[0].mechanism,
                      "grounds": len({s.ground_id for s in shots})})
        cells[key] = block

    ranked = [(gid, b) for gid, b in grounds.items() if b["n"]]
    most_open = sorted(ranked, key=lambda kv: (-kv[1]["n_unseen"], -kv[1]["n"]))[:TOP_N]
    most_saturated = sorted(ranked,
                            key=lambda kv: (-(kv[1]["saturation"] or 0.0), -kv[1]["n"]))[:TOP_N]
    sampled_sites = {s.site for s in sightings}
    return {
        "at": datetime.now(UTC).isoformat(),
        "n_sightings": len(sightings),
        "n_species": len({s.species for s in sightings}),
        "grounds": grounds,
        "cells": cells,
        "most_open": [{"ground_id": g, **_headline(b)} for g, b in most_open],
        "most_saturated": [{"ground_id": g, **_headline(b)} for g, b in most_saturated],
        "unmeasured": {
            "inputs": note,
            "rows_without_mechanism": int(stats["rows_without_mechanism"]),
            "duplicate_observations": int(stats["duplicate_observations"]),
            "sightings_unknown_mechanism": sum(1 for s in sightings if s.mechanism == UNKNOWN),
            "sightings_unknown_asset_class": sum(1 for s in sightings
                                                 if s.asset_class == UNKNOWN),
            "sightings_without_timestamp": sum(1 for s in sightings if not s.at),
            "grounds_named_by_the_miner": len(named_grounds),
            "grounds_never_sampled": len(named_grounds - sampled_sites),
            "grounds_unmeasured": sorted(g for g, b in grounds.items() if not b["n"]),
            "mechanism_vocabulary": len(vocab),
            "mechanisms_outside_the_vocabulary": sorted(
                {s.mechanism for s in sightings} - vocab - {UNKNOWN}) if vocab else [],
            "discovery_files_seen": int(stats["discovery_files_seen"]),
            "discovery_files_read": int(stats["discovery_files_read"]),
            "discovery_files_unreadable": int(stats["discovery_files_unreadable"]),
            "rows_read": {k: int(stats[k]) for k in
                          ("claim_rows", "deep_forest_rows", "discovery_rows", "graph_rows")},
        },
        "rule": RULE,
    }


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def write(report: dict[str, Any]) -> Path:
    """The report atomically, then one history row per ground appended so the curve grows."""
    _atomic_write(OUT_REPORT, json.dumps(report, indent=1, ensure_ascii=False, default=str))
    rows = [json.dumps({"at": report["at"], "ground_id": gid,
                        **{k: b[k] for k in ("n", "s_obs", "f1", "f2", "n_hat", "n_unseen",
                                             "coverage", "saturation", "verdict")}},
                       ensure_ascii=False, default=str)
            for gid, b in sorted(report["grounds"].items())]
    if rows:
        OUT_HISTORY.parent.mkdir(parents=True, exist_ok=True)
        with OUT_HISTORY.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(rows) + "\n")
    return OUT_REPORT


def _rank_line(label: str, row: dict[str, Any] | None, *keys: str) -> str:
    body = " ".join(f"{k}={row[k]}" for k in keys) if row else "none"
    return f"  {label}  {row['ground_id'] + ' ' + body if row else body}"


def summary(report: dict[str, Any], target: str) -> list[str]:
    """Six lines: what was read, how much is seen, how much is not, and where to go next."""
    un = report["unmeasured"]
    verdicts = Counter(b["verdict"] for b in report["grounds"].values())
    return [
        f"UNSEEN FRONTIER {report['at']}  inputs: "
        + ", ".join(f"{k}={v}" for k, v in un["inputs"].items()),
        f"  sightings {report['n_sightings']}  species {report['n_species']}  "
        f"grounds {len(report['grounds'])}  cells {len(report['cells'])}",
        "  verdicts  " + ("  ".join(f"{k}={v}" for k, v in sorted(verdicts.items())) or "none"),
        _rank_line("most open", (report["most_open"] or [None])[0], "n_unseen", "coverage"),
        _rank_line("most saturated", (report["most_saturated"] or [None])[0], "saturation", "n"),
        f"  unmeasured  rows_without_mechanism={un['rows_without_mechanism']} "
        f"unknown_mechanism={un['sightings_unknown_mechanism']} "
        f"never_sampled_grounds={un['grounds_never_sampled']} -> {target}",
    ]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="unseen-species estimates over mechanism sightings")
    ap.add_argument("--dry-run", action="store_true", help="print the summary, write nothing")
    args = ap.parse_args(argv)
    report = build()
    target = "DRY RUN (nothing written)" if args.dry_run else str(write(report))
    for line in summary(report, target):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
