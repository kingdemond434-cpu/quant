"""THE RESEARCH GENOME AND THE QUALITY-DIVERSITY ARCHIVE (LAWS 5k).

Every candidate is the tuple C = (M, D, R, G, S, H, E, F): mechanism, data source,
representation, geography, state/regime/session, horizon, execution dependency, failure mode.
Two candidates are NEAR-DUPLICATES when most of that tuple is the same, whatever their
parameters; near-duplicates are one FAMILY, and the family is what the effective-trial ledger
charges and the online-FDR wealth is kept for.

WHAT ALREADY EXISTED, AND IS EXTENDED RATHER THAN REPEATED. `libs.research.alpha_genome`
gives a strategy ONE identity (the sha of symbol, family, params) so four record shapes can be
joined; that identity is exact and parameter-bearing, which is what a join needs and the
opposite of what a family needs. `desks/mt5/research/alpha_evolution.Evaluator.archive`
(Tier-1 G16) keeps the best EXPRESSION per (mechanism, horizon, regime, asset) cell inside one
evolutionary run, and `desks/mt5/research/qd_frontier` keeps one elite per eight-axis
behavioural niche from the desk's evidence artifacts. This module is the registry-level layer
above both: the genome is stamped on every candidate from the registry's own columns, the
family id follows from the near-duplicate rule, and `QDArchive` keeps elites over the law's
own grid -- mechanism x data family x region x asset x session x regime x horizon x execution
dependency -- with an EMPTY-CELL BONUS so the scheduler is paid to search cells nobody has lit
rather than improve one family forever. `EMPTY_CELL_BONUS` is the registry's own constant
(`libs.moat.registry.EMPTY_CELL_BONUS`), passed in, so the two priorities cannot disagree.

THE NEAR-DUPLICATE RULE IS TRANSITIVE BY CONSTRUCTION. Families are the connected components of
the near-duplicate graph inside one mechanism (a different mechanism is never the same family),
which means a chain A~B~C is one family even when A and C differ on three axes. That is the
conservative reading for a trial charge -- the ledger prices the family by its measured
redundancy, so a wide family is not under-charged -- and the honest one for wealth: a lineage
that keeps mutating one axis at a time is one lineage. Family ids are the smallest exact-tuple
hash in the component, so they are stable under growth unless a lexicographically smaller
tuple joins, in which case the report's member list is the join.

UNMEASURED IS A VALUE. An axis the registry did not fill is the literal "UNMEASURED", it counts
as a MATCH between two candidates only when both are unmeasured on it (absence is not
similarity: two unknowns are one unknown), and the archive keys it as its own value so the
count of cells whose failure mode nobody wrote down is a number.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

#: C = (M, D, R, G, S, H, E, F), in the law's order.
AXES: tuple[str, ...] = ("mechanism", "data", "representation", "geography", "state",
                         "horizon", "execution", "failure")
#: The quality-diversity grid of LAWS 5k.
ARCHIVE_AXES: tuple[str, ...] = ("mechanism", "data", "geography", "asset", "session", "regime",
                                 "horizon", "execution")
#: "most of the tuple": this many of the eight axes equal (mechanism always among them).
NEAR_DUPLICATE_MIN_EQUAL = 6
UNMEASURED = "UNMEASURED"
#: The registry's empty-cell bonus, mirrored as a default so a caller without the registry
#: gets the same number; the organ passes `libs.moat.registry.EMPTY_CELL_BONUS` explicitly.
EMPTY_CELL_BONUS = 0.5

_CCY_REGION: dict[str, str] = {
    "USD": "US", "EUR": "EU", "GBP": "UK", "JPY": "JP", "CHF": "CH", "AUD": "AU", "NZD": "NZ",
    "CAD": "CA", "SEK": "SE", "NOK": "NO", "DKK": "DK", "PLN": "PL", "HUF": "HU", "CZK": "CZ",
    "TRY": "TR", "ZAR": "ZA", "MXN": "MX", "SGD": "SG", "HKD": "HK", "CNH": "CN", "CNY": "CN",
    "KRW": "KR", "INR": "IN", "BRL": "BR", "ILS": "IL", "THB": "TH",
}
_SYMBOL_REGION: dict[str, str] = {
    "JPN225": "JP", "JP225": "JP", "NIKKEI": "JP", "AUS200": "AU", "HK50": "HK", "CHINA50": "CN",
    "CN50": "CN", "EUSTX50": "EU", "GER40": "DE", "DE40": "DE", "FRA40": "FR", "UK100": "UK",
    "SPA35": "ES", "ITA40": "IT", "SWI20": "CH", "NETH25": "NL", "US30": "US", "US500": "US",
    "SPX500": "US", "NAS100": "US", "US2000": "US", "USTEC": "US", "VIX": "US", "SG30": "SG",
    "IN50": "IN", "KOSPI": "KR", "KR200": "KR", "TWN": "TW",
}
_GLOBAL_CLASSES = frozenset({"commodities", "metals", "energy", "soft_commodity",
                             "soft_commodities", "crypto", "crypto_cfd"})


def geography_of(symbol: Any, asset_class: Any = None) -> str:
    """The region a symbol's price is made in: a currency pair names its two currencies' regions
    joined (USDJPY -> US-JP), an index its exchange's country, a commodity or crypto CFD is
    GLOBAL, an equity CFD defaults to US (Fusion's share book), anything else UNMEASURED."""
    sym = str(symbol or "").upper().replace(".", "").replace("_", "")
    if not sym:
        return UNMEASURED
    if sym in _SYMBOL_REGION:
        return _SYMBOL_REGION[sym]
    for k, v in _SYMBOL_REGION.items():
        if sym.startswith(k):
            return v
    if len(sym) == 6 and sym[:3] in _CCY_REGION and sym[3:] in _CCY_REGION:
        return f"{_CCY_REGION[sym[:3]]}-{_CCY_REGION[sym[3:]]}"
    klass = str(asset_class or "").lower()
    if klass in _GLOBAL_CLASSES or sym.startswith(("XAU", "XAG", "XPT", "XPD", "BTC", "ETH",
                                                    "UKOIL", "USOIL", "BRENT", "WTI", "NATGAS")):
        return "GLOBAL"
    if klass in ("equities", "shares", "stocks", "equity", "us_shares"):
        return "US"
    if sym.startswith("USD") or sym.endswith("USD"):
        return "US"
    return UNMEASURED


@dataclass(frozen=True)
class Genome:
    """C = (M, D, R, G, S, H, E, F) plus the three archive-only axes (asset, session, regime)
    and the identity the desk already joins on."""

    mechanism: str
    data: str
    representation: str
    geography: str
    state: str
    horizon: str
    execution: str
    failure: str
    asset: str = UNMEASURED
    session: str = UNMEASURED
    regime: str = UNMEASURED
    symbol: str = ""
    family: str = ""
    candidate_id: str = ""
    params: dict[str, Any] = field(default_factory=dict)

    def tuple8(self) -> tuple[str, ...]:
        return tuple(getattr(self, a) for a in AXES)

    def exact_key(self) -> str:
        return hashlib.sha256("|".join(self.tuple8()).encode("utf-8")).hexdigest()[:16]

    def archive_cell(self) -> str:
        return "|".join(str(getattr(self, a)) for a in ARCHIVE_AXES)

    def descriptors(self) -> dict[str, str]:
        """The axes as the trial ledger's descriptors (the eight plus asset/session/regime)."""
        out = {a: str(getattr(self, a)) for a in AXES}
        out.update({"asset": self.asset, "session": self.session, "regime": self.regime})
        return out

    def to_dict(self) -> dict[str, Any]:
        d = {a: getattr(self, a) for a in AXES}
        d.update({"asset": self.asset, "session": self.session, "regime": self.regime,
                  "symbol": self.symbol, "family": self.family, "exact_key": self.exact_key(),
                  "archive_cell": self.archive_cell()})
        return d


def _s(v: Any) -> str:
    return str(v).strip() if v not in (None, "") else UNMEASURED


def _params_of(rec: Mapping[str, Any]) -> dict[str, Any]:
    p = rec.get("params")
    if isinstance(p, Mapping):
        return dict(p)
    raw = rec.get("params_json")
    if isinstance(raw, str) and raw:
        try:
            v = json.loads(raw)
            return dict(v) if isinstance(v, Mapping) else {}
        except ValueError:
            return {}
    return {}


def genome_of(rec: Mapping[str, Any]) -> Genome:
    """Stamp a genome from the registry's own vocabulary (a `research_candidates` row, a sweep
    cell, a discovery payload). Every axis is read from the record; nothing is inferred from
    prose. Mechanism falls back to the family name (a family IS a mechanism when the compiler
    named no finer one); data is the information source; representation is the transformation
    on its chart; state is regime x session; execution is the execution style from the
    parameters, else the PIT status, else the subtype when it is an execution variant."""
    params = _params_of(rec)
    family = _s(rec.get("family") or rec.get("trial_family"))
    symbol = str(rec.get("symbol") or rec.get("sym") or "")
    chart = _s(rec.get("chart") or rec.get("timeframe"))
    transformation = _s(rec.get("transformation") or rec.get("subtype"))
    representation = (f"{transformation}@{chart}" if transformation != UNMEASURED
                      or chart != UNMEASURED else UNMEASURED)
    regime = _s(rec.get("regime") or params.get("regime"))
    session = _s(rec.get("session") or params.get("session"))
    state = (f"{regime}/{session}" if regime != UNMEASURED or session != UNMEASURED
             else UNMEASURED)
    execution = _s(params.get("execution_style") or rec.get("execution_style")
                   or rec.get("execution") or rec.get("pit_status")
                   or (rec.get("subtype") if rec.get("subtype") == "execution" else None))
    failure = _s(rec.get("failure_class") or rec.get("failure_mode") or rec.get("falsifier"))
    return Genome(
        mechanism=_s(rec.get("mechanism")) if rec.get("mechanism") else family,
        data=_s(rec.get("information") or rec.get("information_source") or rec.get("data")),
        representation=representation,
        geography=_s(rec.get("geography")) if rec.get("geography") else geography_of(
            symbol, rec.get("asset_class")),
        state=state,
        horizon=_s(rec.get("horizon")),
        execution=execution,
        failure=failure,
        asset=_s(rec.get("asset_class") or rec.get("asset")),
        session=session, regime=regime, symbol=symbol.upper(), family=family,
        candidate_id=str(rec.get("id") or rec.get("candidate_id") or ""), params=params)


def equal_axes(a: Genome, b: Genome) -> int:
    """Axes on which two genomes agree; an axis unmeasured on BOTH does not count as agreement."""
    return sum(1 for x, y in zip(a.tuple8(), b.tuple8(), strict=True)
               if x == y and x != UNMEASURED)


def is_near_duplicate(a: Genome, b: Genome, min_equal: int = NEAR_DUPLICATE_MIN_EQUAL) -> bool:
    return a.mechanism == b.mechanism and a.mechanism != UNMEASURED and equal_axes(
        a, b) >= min_equal


def _find(parent: list[int], i: int) -> int:
    while parent[i] != i:
        parent[i] = parent[parent[i]]
        i = parent[i]
    return i


def assign_families(genomes: Sequence[Genome],
                    min_equal: int = NEAR_DUPLICATE_MIN_EQUAL) -> list[str]:
    """One family id per genome: connected components of the near-duplicate graph inside each
    mechanism, named by the smallest exact-tuple hash in the component. Genomes with an
    identical eight-tuple are merged first (no pairwise work), then the distinct tuples of a
    mechanism are compared pairwise -- distinct tuples per mechanism are few even when
    candidates are many."""
    n = len(genomes)
    parent = list(range(n))
    by_exact: dict[str, int] = {}
    exact_keys = [g.exact_key() for g in genomes]
    reps_by_mech: dict[str, list[int]] = {}
    for i, g in enumerate(genomes):
        k = exact_keys[i]
        if k in by_exact:
            parent[_find(parent, i)] = _find(parent, by_exact[k])
            continue
        by_exact[k] = i
        reps_by_mech.setdefault(g.mechanism, []).append(i)
    for mech, reps in reps_by_mech.items():
        if mech == UNMEASURED:
            continue
        tuples = [genomes[i].tuple8() for i in reps]
        for a in range(len(reps)):
            ta = tuples[a]
            for b in range(a + 1, len(reps)):
                tb = tuples[b]
                eq = 0
                for x, y in zip(ta, tb, strict=True):
                    if x == y and x != UNMEASURED:
                        eq += 1
                if eq >= min_equal:
                    ra, rb = _find(parent, reps[a]), _find(parent, reps[b])
                    if ra != rb:
                        parent[rb] = ra
    root_key: dict[int, str] = {}
    for i in range(n):
        r = _find(parent, i)
        k = exact_keys[i]
        if r not in root_key or k < root_key[r]:
            root_key[r] = k
    return [f"fam_{root_key[_find(parent, i)]}" for i in range(n)]


# ------------------------------------------------------------------ the QD archive
@dataclass(frozen=True)
class Elite:
    cell: str
    candidate_id: str
    quality: float
    basis: str
    family_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"cell": self.cell, "candidate_id": self.candidate_id,
                "quality": round(self.quality, 6), "basis": self.basis,
                "family_id": self.family_id}


@dataclass
class QDArchive:
    """Elites per cell of the law's grid. `put` keeps the better of the incumbent and the
    challenger by (quality, basis rank) -- a forward number outranks an in-sample one at equal
    quality only when the caller ranks bases; here quality is what the caller measured and the
    tie goes to the incumbent, so an archive never churns on equal evidence."""

    bonus: float = EMPTY_CELL_BONUS
    cells: dict[str, Elite] = field(default_factory=dict)
    occupants: dict[str, int] = field(default_factory=dict)

    def put(self, cell: str, candidate_id: str, quality: float, basis: str = UNMEASURED,
            family_id: str = "") -> bool:
        self.occupants[cell] = self.occupants.get(cell, 0) + 1
        have = self.cells.get(cell)
        if have is None or quality > have.quality:
            self.cells[cell] = Elite(cell, candidate_id, float(quality), basis, family_id)
            return True
        return False

    def is_empty(self, cell: str) -> bool:
        return cell not in self.cells

    def priority(self, cell: str, value: float) -> float:
        """The scheduler's priority for a proposal into `cell`: value x (1 + bonus) when the
        cell is empty, value otherwise -- the registry's own empty-cell rule."""
        return float(value) * (1.0 + self.bonus if self.is_empty(cell) else 1.0)

    def axis_values(self) -> dict[str, list[str]]:
        seen: dict[str, set[str]] = {a: set() for a in ARCHIVE_AXES}
        for cell in self.cells:
            parts = cell.split("|")
            if len(parts) != len(ARCHIVE_AXES):
                continue
            for a, v in zip(ARCHIVE_AXES, parts, strict=True):
                seen[a].add(v)
        return {a: sorted(v) for a, v in seen.items()}

    def cells_possible(self) -> int:
        n = 1
        for vals in self.axis_values().values():
            n *= max(1, len(vals))
        return n

    def occupancy(self) -> dict[str, Any]:
        filled = len(self.cells)
        possible = self.cells_possible()
        return {"cells_filled": filled, "cells_possible": possible,
                "occupancy": round(filled / possible, 6) if possible else 0.0,
                "candidates_placed": sum(self.occupants.values()),
                "axis_cardinality": {a: len(v) for a, v in self.axis_values().items()}}

    def empty_high_value(self, limit: int = 25) -> list[dict[str, Any]]:
        """Empty cells one axis away from populated ones, valued at the mean quality of their
        populated neighbours times (1 + bonus). These are the cells the scheduler is paid to
        search next, ranked; an archive with no elites has none (UNMEASURED, not zero)."""
        vals = self.axis_values()
        scores: dict[str, list[float]] = {}
        for cell, elite in self.cells.items():
            parts = cell.split("|")
            if len(parts) != len(ARCHIVE_AXES):
                continue
            for i, a in enumerate(ARCHIVE_AXES):
                for v in vals[a]:
                    if v == parts[i]:
                        continue
                    nb = parts.copy()
                    nb[i] = v
                    key = "|".join(nb)
                    if key not in self.cells:
                        scores.setdefault(key, []).append(elite.quality)
        rows: list[dict[str, Any]] = [
            {"cell": k, "value": round(sum(v) / len(v) * (1.0 + self.bonus), 6),
             "neighbours": len(v)} for k, v in scores.items()]
        rows.sort(key=lambda r: (-float(r["value"]), -int(r["neighbours"]), str(r["cell"])))
        return rows[:limit]

    def to_dict(self, limit: int = 200) -> dict[str, Any]:
        top = sorted(self.cells.values(), key=lambda e: -e.quality)[:limit]
        return {**self.occupancy(), "bonus": self.bonus,
                "elites": [e.to_dict() for e in top]}


def stamp_all(records: Iterable[Mapping[str, Any]]) -> tuple[list[Genome], list[str]]:
    """Genomes and family ids for a batch of records, in input order."""
    genomes = [genome_of(r) for r in records]
    return genomes, assign_families(genomes)
