"""THE AUTHORITATIVE COVERAGE TENSORS AND THE FRONTIER ENGINE (principal, 2026-09-17, LAWS 5d).

TWO TENSORS, ONE LADDER EACH, SPARSE BY CONSTRUCTION.

  WORLD   country x sector x information_type x mechanism x representation x asset x session
          x regime x horizon x execution, every cell in exactly one state of
          UNOBSERVED -> SOURCE_HUNT -> INGESTED -> REPRESENTED -> CANDIDATES -> TESTING ->
          FAILED/FORWARD -> CERTIFIED -> LIVE -> DECAYED. FAILED and FORWARD share a rung;
          DECAYED is reachable from LIVE, CERTIFIED and FORWARD only.
  FOREST  country x language x source_class x sector x mechanism x asset_transmission x
          freshness x accessibility, where source_class is exactly one of the ten source layers,
          in UNSEEN -> SOURCE_HUNT -> DISCOVERED -> VERIFIED -> INGESTED -> REPRESENTED ->
          CANDIDATES -> TESTED -> FORWARD -> LIVE/FAILED.

THE POINT. "Indonesia nickel exports x China industrial cycle x AUD x Asian session x risk-off has
never been tested" must be an EXPLICIT frontier row with a state and a next move, never a blind
spot nobody knows exists. The full product of the vocabularies is astronomically large (ten axes
of twenty to two hundred values each), so a tensor holds ONLY the cells evidence has touched and
the frontier cells the engine enumerated on purpose; a coordinate absent from the store is at the
floor, and `holes()` is how the floor is asked a question.

THE LADDER IS MONOTONE, WITH TWO NAMED DOWN-MOVES. `advance` moves a cell up its ladder and never
down, except to FAILED and DECAYED, each of which is entered only from the states the ladder
names and only with NAMED evidence (a `why` and a `source`). A cell nobody has judged cannot be
"failed" by silence, and a live cell cannot decay because a file went missing (L1.28a).

EVIG -- the expected value of information gain that ranks a hole:

    EVIG = prior P(edge | neighbouring evidence) x reachability x novelty x capacity / cost

  prior         Laplace-smoothed share of positive verdicts among the JUDGED neighbours; with no
                judged neighbour it is the desk's 0.5 prior, never 0 and never 1;
  reachability  the share of the cell's axis components that have data at INGESTED or above
                SOMEWHERE in the tensor (floored, so an unreachable cell ranks as a source hunt
                rather than vanishing);
  novelty       Hamming distance to the nearest TESTED cell over the axes considered, as a share;
  capacity      a proxy the caller measures (UNMEASURED -> the 0.5 prior, named as such);
  cost          the cost of the NEXT rung from the cell's state.

Every factor is returned in the breakdown, so a rank is an argument rather than a number.

COVERAGE OF A COUNTRY RISES ONLY WHEN BOTH CONDITIONS HOLD: every source layer that exists for it
is mapped (a verified source, or an absence declared WITH a reason) AND automatic discovery is
still adding sources. Five obvious sources map at most five layers and prove no discovery, so
`covered()` refuses them by construction. Floors ratchet up only: `ratchet` never lowers one.

Pure and typed: no I/O, no clock read except to stamp `updated`, deterministic ordering.
"""
from __future__ import annotations

import hashlib
import itertools
import json
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

WORLD = "world"
FOREST = "forest"
#: The coordinate a piece of evidence carries when it says nothing about an axis. It is a value
#: like any other, never a wildcard: a price-only candidate on USDJPY lives at country=any and
#: does not cover country=kr.
ANY = "any"
UNMEASURED = "UNMEASURED"
PRIOR = 0.5
REACH_FLOOR = 0.1
CAPACITY_FLOOR = 0.05
MAX_EVIDENCE_PER_STATE = 6

WORLD_AXES: tuple[str, ...] = ("country", "sector", "information_type", "mechanism",
                               "representation", "asset", "session", "regime", "horizon",
                               "execution")
FOREST_AXES: tuple[str, ...] = ("country", "language", "source_class", "sector", "mechanism",
                                "asset_transmission", "freshness", "accessibility")

WORLD_LADDER: tuple[str, ...] = ("UNOBSERVED", "SOURCE_HUNT", "INGESTED", "REPRESENTED",
                                 "CANDIDATES", "TESTING", "FAILED", "FORWARD", "CERTIFIED",
                                 "LIVE", "DECAYED")
FOREST_LADDER: tuple[str, ...] = ("UNSEEN", "SOURCE_HUNT", "DISCOVERED", "VERIFIED", "INGESTED",
                                  "REPRESENTED", "CANDIDATES", "TESTED", "FORWARD", "LIVE",
                                  "FAILED")

#: The ten source layers, ordered from the most official to the most derived.
SOURCE_LAYERS: tuple[str, ...] = ("official", "institutional", "academic", "practitioner",
                                  "retail_ecology", "app_ecosystem", "media", "archive",
                                  "physical_economy", "source_graph")

#: The closed vocabularies the specification fixes. The organ adds the open ones (countries,
#: mechanisms, assets, representations, languages) from the desk's own registries.
INFORMATION_TYPES: tuple[str, ...] = ("physical_exhaust", "supply_chain", "customs", "corporate",
                                      "legal", "labour", "innovation", "consumer", "payments",
                                      "attention", "multimodal", "archives", "official_macro",
                                      "market_data", "positioning", "news")
SECTORS: tuple[str, ...] = ("energy_oil_gas", "power_utilities", "metals_mining",
                            "agriculture_softs", "chemicals_materials", "semiconductors",
                            "technology_software", "autos_machinery", "construction_real_estate",
                            "transport_shipping", "banking_finance", "insurance_pensions",
                            "retail_consumer", "healthcare_pharma", "telecom_media",
                            "tourism_leisure", "government_fiscal", "defence_aerospace",
                            "textiles_light_industry", "households_labour")
SESSIONS: tuple[str, ...] = ("asia", "tokyo_fix", "london", "london_fix", "ny", "overlap",
                             "close", "gotobi", "holiday")
HORIZONS: tuple[str, ...] = ("1h", "4h", "1d", "5d", "20d")
EXECUTIONS: tuple[str, ...] = ("market", "limit", "stop", "bracket", "session_window")
FRESHNESS: tuple[str, ...] = ("realtime", "intraday", "daily", "weekly", "monthly", "quarterly",
                              "archive")
#: The access vocabulary of `desks/mt5/research/ingestion_ledger.py`, same spelling, so a join
#: is a rename and never a re-derivation.
ACCESS_LABELS: tuple[str, ...] = ("PUBLIC", "PUBLIC_WITH_TERMS", "LICENSED", "OPEN_DATA",
                                  "PUBLIC_ARCHIVE", "PUBLIC_SOCIAL", "USER_SUBMITTED",
                                  "ACCESS_UNCLEAR", "PRIVATE", "CONFIDENTIAL_MNPI",
                                  "STOLEN_UNAUTHORIZED")

COVERAGE_STATES: tuple[str, ...] = ("COVERED", "MAPPING", "STALLED", "UNMEASURED")
COVERAGE_RULE = ("a country is COVERED only when every source layer is mapped -- a verified "
                 "source or an absence declared with a reason -- AND automatic discovery is still "
                 "adding sources in the trailing window; five obvious sources is not coverage, "
                 "and a mapped country whose discovery rate is zero is STALLED, not finished")
RULE = ("every cell of the two tensors is in exactly one ladder state; the ladder is monotone "
        "except the named down-moves FAILED and DECAYED, which need named evidence; a hole is an "
        "explicit frontier row ranked by EVIG, never a blind spot; floors ratchet up only")


# ------------------------------------------------------------------------------------ the ladders
@dataclass(frozen=True)
class Ladder:
    """One tensor's state ladder: the order, the rung of every state, and the down-moves.

    `rung` is the height; two states may share a rung (FAILED/FORWARD, LIVE/FAILED). `down_moves`
    names the negative states and the states each may be entered from; `positive_twin` names,
    for a negative state that shares a rung, the positive state on that rung, so a FAILED cell
    that later carries a forward clock reads FORWARD (progress) while FORWARD -> FAILED stays a
    named down-move.
    """

    name: str
    states: tuple[str, ...]
    rung: Mapping[str, int]
    down_moves: Mapping[str, frozenset[str]]
    positive_twin: Mapping[str, str]
    tested_from: str
    positive: frozenset[str]
    negative: frozenset[str]
    ingested_from: str

    @property
    def floor(self) -> str:
        return self.states[0]

    def check(self, state: str) -> str:
        if state not in self.rung:
            raise ValueError(f"{state!r} is not a state of the {self.name} ladder {self.states}")
        return state

    def rank(self, state: str) -> int:
        return int(self.rung[self.check(state)])

    def at_or_above(self, state: str, bar: str) -> bool:
        return self.rank(state) >= self.rank(bar)

    def next_state(self, state: str) -> str | None:
        """The state one rung up on the positive path, or None at the top."""
        r = self.rank(state)
        for s in self.states:
            if self.rung[s] == r + 1 and s not in self.down_moves:
                return s
        return None


WORLD_LADDER_SPEC = Ladder(
    name=WORLD, states=WORLD_LADDER,
    rung={"UNOBSERVED": 0, "SOURCE_HUNT": 1, "INGESTED": 2, "REPRESENTED": 3, "CANDIDATES": 4,
          "TESTING": 5, "FAILED": 6, "FORWARD": 6, "CERTIFIED": 7, "LIVE": 8, "DECAYED": 9},
    down_moves={"FAILED": frozenset({"TESTING", "FORWARD", "CERTIFIED"}),
                "DECAYED": frozenset({"FORWARD", "CERTIFIED", "LIVE"})},
    positive_twin={"FAILED": "FORWARD"},
    tested_from="TESTING", positive=frozenset({"FORWARD", "CERTIFIED", "LIVE"}),
    negative=frozenset({"FAILED", "DECAYED"}), ingested_from="INGESTED")

FOREST_LADDER_SPEC = Ladder(
    name=FOREST, states=FOREST_LADDER,
    rung={"UNSEEN": 0, "SOURCE_HUNT": 1, "DISCOVERED": 2, "VERIFIED": 3, "INGESTED": 4,
          "REPRESENTED": 5, "CANDIDATES": 6, "TESTED": 7, "FORWARD": 8, "LIVE": 9, "FAILED": 9},
    down_moves={"FAILED": frozenset({"TESTED", "FORWARD", "LIVE"})},
    positive_twin={"FAILED": "LIVE"},
    tested_from="TESTED", positive=frozenset({"FORWARD", "LIVE"}),
    negative=frozenset({"FAILED"}), ingested_from="INGESTED")

_LADDERS: dict[str, Ladder] = {WORLD: WORLD_LADDER_SPEC, FOREST: FOREST_LADDER_SPEC}
_AXES: dict[str, tuple[str, ...]] = {WORLD: WORLD_AXES, FOREST: FOREST_AXES}

#: The cost of the NEXT rung from a state, in gauntlet-run units: a hunt is cheap, a forward
#: clock is time nobody can buy.
RUNG_COST: dict[str, dict[str, float]] = {
    WORLD: {"UNOBSERVED": 1.0, "SOURCE_HUNT": 2.0, "INGESTED": 1.0, "REPRESENTED": 1.0,
            "CANDIDATES": 3.0, "TESTING": 3.0, "FAILED": 3.0, "FORWARD": 5.0, "CERTIFIED": 2.0,
            "LIVE": 1.0, "DECAYED": 3.0},
    FOREST: {"UNSEEN": 1.0, "SOURCE_HUNT": 0.5, "DISCOVERED": 1.0, "VERIFIED": 2.0,
             "INGESTED": 1.0, "REPRESENTED": 1.0, "CANDIDATES": 3.0, "TESTED": 5.0,
             "FORWARD": 1.0, "LIVE": 1.0, "FAILED": 3.0},
}


def ladder_of(tensor: str) -> Ladder:
    if tensor not in _LADDERS:
        raise ValueError(f"unknown tensor {tensor!r}; one of {tuple(_LADDERS)}")
    return _LADDERS[tensor]


def axes_of(tensor: str) -> tuple[str, ...]:
    if tensor not in _AXES:
        raise ValueError(f"unknown tensor {tensor!r}; one of {tuple(_AXES)}")
    return _AXES[tensor]


def now_iso() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def named(evidence: Mapping[str, Any] | None) -> bool:
    """Named evidence carries a non-empty `why` and a non-empty `source` (the artifact)."""
    if not evidence:
        return False
    return bool(str(evidence.get("why") or "").strip()) and bool(
        str(evidence.get("source") or "").strip())


# --------------------------------------------------------------------------------------- the cell
@dataclass(frozen=True)
class Cell:
    """One coordinate of one tensor, in one state, with the evidence that put it there."""

    tensor: str
    coordinates: tuple[str, ...]
    state: str
    evidence: dict[str, Any] = field(default_factory=dict)
    updated: str = ""

    def __post_init__(self) -> None:
        axes = axes_of(self.tensor)
        if len(self.coordinates) != len(axes):
            raise ValueError(f"{self.tensor} cell needs {len(axes)} coordinates {axes}, got "
                             f"{len(self.coordinates)}")
        ladder_of(self.tensor).check(self.state)
        object.__setattr__(self, "coordinates", tuple(str(c) for c in self.coordinates))

    @property
    def axes(self) -> tuple[str, ...]:
        return axes_of(self.tensor)

    @property
    def key(self) -> str:
        return "|".join(self.coordinates)

    def values(self) -> dict[str, str]:
        return dict(zip(self.axes, self.coordinates, strict=True))

    def value(self, axis: str) -> str:
        return self.values()[axis]

    def content_hash(self) -> str:
        body = json.dumps({"tensor": self.tensor, "coordinates": list(self.coordinates),
                           "state": self.state}, sort_keys=True)
        return hashlib.sha256(body.encode("utf-8")).hexdigest()[:32]

    def to_json(self) -> dict[str, Any]:
        return {"tensor": self.tensor, "coordinates": list(self.coordinates),
                "state": self.state, "evidence": dict(self.evidence), "updated": self.updated}

    @classmethod
    def from_json(cls, doc: Mapping[str, Any]) -> Cell:
        ev = doc.get("evidence")
        return cls(tensor=str(doc["tensor"]), coordinates=tuple(str(c) for c in doc["coordinates"]),
                   state=str(doc["state"]), evidence=dict(ev) if isinstance(ev, Mapping) else {},
                   updated=str(doc.get("updated") or ""))


def _merge_evidence(old: Mapping[str, Any], state: str, evidence: Mapping[str, Any] | None
                    ) -> dict[str, Any]:
    """Evidence is kept PER STATE and bounded, so a cell reads like a ledger, not a dump."""
    out: dict[str, Any] = {k: (list(v) if isinstance(v, list) else v) for k, v in old.items()}
    if evidence:
        rows = out.get(state)
        bucket: list[Any] = list(rows) if isinstance(rows, list) else []
        entry = dict(evidence)
        if entry not in bucket and len(bucket) < MAX_EVIDENCE_PER_STATE:
            bucket.append(entry)
        out[state] = bucket
    return out


def advance(cell: Cell, state: str, evidence: Mapping[str, Any] | None = None, *,
            at: str | None = None) -> Cell:
    """Move a cell along its ladder. Up is free; down is FAILED or DECAYED with named evidence.

    A move to a lower or equal rung is NOT an error: the ladder is monotone, so the cell keeps
    its state and merely records the evidence. The exception is the positive twin on a shared
    rung (FAILED -> FORWARD, FAILED -> LIVE in the forest), which is progress and moves.
    """
    ladder = ladder_of(cell.tensor)
    state = ladder.check(state)
    stamp = at or now_iso()
    merged = _merge_evidence(cell.evidence, state, evidence)
    if state in ladder.down_moves:
        if cell.state == state:
            return Cell(cell.tensor, cell.coordinates, state, merged, stamp)
        allowed = ladder.down_moves[state]
        if cell.state not in allowed:
            raise ValueError(f"{state} is reachable only from {sorted(allowed)}; the cell is at "
                             f"{cell.state}")
        if not named(evidence):
            raise ValueError(f"{state} requires NAMED evidence (a `why` and a `source`); "
                             f"silence never fails or decays a cell")
        merged["path"] = [*list(merged.get("path") or [cell.state]), state]
        return Cell(cell.tensor, cell.coordinates, state, merged, stamp)
    cur, new = ladder.rank(cell.state), ladder.rank(state)
    twin = ladder.positive_twin.get(cell.state) == state
    if new > cur or (new == cur and state != cell.state and twin):
        merged["path"] = [*list(merged.get("path") or [cell.state]), state]
        return Cell(cell.tensor, cell.coordinates, state, merged, stamp)
    return Cell(cell.tensor, cell.coordinates, cell.state, merged, cell.updated or stamp)


# ------------------------------------------------------------------------------------- the holes
@dataclass(frozen=True)
class Hole:
    """One frontier row: a projected coordinate still at (or below) the asked state."""

    tensor: str
    axes: tuple[str, ...]
    coordinates: tuple[str, ...]
    state: str
    score: float
    breakdown: dict[str, Any] = field(default_factory=dict)

    def values(self) -> dict[str, str]:
        return dict(zip(self.axes, self.coordinates, strict=True))

    @property
    def key(self) -> str:
        return "|".join(f"{a}={v}" for a, v in zip(self.axes, self.coordinates, strict=True))

    def to_json(self) -> dict[str, Any]:
        return {"tensor": self.tensor, "axes": list(self.axes),
                "coordinates": list(self.coordinates), "values": self.values(),
                "state": self.state, "score": round(float(self.score), 6),
                "breakdown": dict(self.breakdown), "key": self.key}


Scorer = Callable[[Mapping[str, str]], "float | tuple[float, Mapping[str, Any]]"]


# ------------------------------------------------------------------------------------ the tensor
class Tensor:
    """A SPARSE tensor: only observed cells and enumerated frontier cells are stored."""

    def __init__(self, name: str, *, vocabulary: Mapping[str, Sequence[str]] | None = None
                 ) -> None:
        self.name = name
        self.axes = axes_of(name)
        self.ladder = ladder_of(name)
        vocab = dict(vocabulary or {})
        for k in vocab:
            if k not in self.axes:
                raise ValueError(f"vocabulary names {k!r}, not an axis of {name}: {self.axes}")
        self.vocabulary: dict[str, tuple[str, ...]] = {
            a: tuple(dict.fromkeys(str(v) for v in vocab.get(a, ()) if str(v)))
            for a in self.axes}
        self._cells: dict[tuple[str, ...], Cell] = {}
        self.last_scan: dict[str, Any] = {}

    # ---- storage
    def __len__(self) -> int:
        return len(self._cells)

    def cells(self) -> list[Cell]:
        return [self._cells[k] for k in sorted(self._cells)]

    def get(self, values: Mapping[str, str] | Sequence[str]) -> Cell | None:
        return self._cells.get(self.coordinates(values))

    def put(self, cell: Cell) -> Cell:
        if cell.tensor != self.name:
            raise ValueError(f"a {cell.tensor} cell cannot enter the {self.name} tensor")
        self._cells[cell.coordinates] = cell
        return cell

    def coordinates(self, values: Mapping[str, str] | Sequence[str]) -> tuple[str, ...]:
        """A full coordinate tuple; axes the caller did not name read ANY."""
        if isinstance(values, Mapping):
            unknown = sorted(set(values) - set(self.axes))
            if unknown:
                raise ValueError(f"{unknown} are not axes of {self.name}: {self.axes}")
            return tuple(str(values.get(a) or ANY) for a in self.axes)
        coords = tuple(str(v) for v in values)
        if len(coords) != len(self.axes):
            raise ValueError(f"{self.name} needs {len(self.axes)} coordinates, got {len(coords)}")
        return coords

    def frontier(self, values: Mapping[str, str] | Sequence[str], *, at: str | None = None
                 ) -> Cell:
        """Make a coordinate an EXPLICIT row at the floor (a known hole), if it is not stored."""
        coords = self.coordinates(values)
        cell = self._cells.get(coords)
        if cell is None:
            cell = Cell(self.name, coords, self.ladder.floor, {"frontier": True},
                        at or now_iso())
            self._cells[coords] = cell
        return cell

    def observe(self, values: Mapping[str, str] | Sequence[str], state: str,
                evidence: Mapping[str, Any] | None = None, *, at: str | None = None) -> Cell:
        """Raise a cell to `state` along the lawful path, creating it at the floor if absent.

        A down-move target (FAILED, DECAYED) on a cell below its entry states first climbs to the
        lowest entry state -- a FAILED verdict implies the cell was TESTING, a retirement implies
        it was at least FORWARD -- and then moves down with the evidence given. A cell already
        above the asked state keeps its state and records the evidence.
        """
        ladder = self.ladder
        state = ladder.check(state)
        coords = self.coordinates(values)
        cell = self._cells.get(coords) or Cell(self.name, coords, ladder.floor, {},
                                               at or now_iso())
        if state in ladder.down_moves and cell.state not in ladder.down_moves[state] \
                and cell.state != state:
            if ladder.rank(cell.state) >= ladder.rank(state):
                # Above the down-move's reach: the positive evidence stands and the verdict is
                # recorded beside it rather than demoting a cell the desk has since funded.
                cell = Cell(cell.tensor, cell.coordinates, cell.state,
                            _merge_evidence(cell.evidence, state, evidence), cell.updated)
                self._cells[coords] = cell
                return cell
            # A verdict IMPLIES the rung it was passed on: a FAILED cell was TESTING, a retired
            # one was at least FORWARD. Climb to the lowest lawful entry, then move down.
            entry = min(ladder.down_moves[state], key=ladder.rank)
            cell = advance(cell, entry, {"implied_by": state, **dict(evidence or {})}, at=at)
        cell = advance(cell, state, evidence, at=at)
        self._cells[coords] = cell
        return cell

    # ---- readings
    def histogram(self) -> dict[str, int]:
        out = dict.fromkeys(self.ladder.states, 0)
        for c in self._cells.values():
            out[c.state] += 1
        return out

    def marginals(self, axes: Sequence[str]) -> dict[tuple[str, ...], dict[str, Any]]:
        """Project onto `axes`: per projected coordinate, the cell count, the per-state counts
        and the BEST (highest-rung) state any cell there reached."""
        idx = self._axis_index(axes)
        out: dict[tuple[str, ...], dict[str, Any]] = {}
        for c in self._cells.values():
            key = tuple(c.coordinates[i] for i in idx)
            row = out.get(key)
            if row is None:
                row = {"n": 0, "states": {}, "best": self.ladder.floor}
                out[key] = row
            row["n"] += 1
            row["states"][c.state] = int(row["states"].get(c.state, 0)) + 1
            if self.ladder.rank(c.state) > self.ladder.rank(str(row["best"])):
                row["best"] = c.state
        return dict(sorted(out.items()))

    def reachability(self, bar: str | None = None) -> dict[str, dict[str, bool]]:
        """axis -> value -> has data at `bar` (default INGESTED) or above SOMEWHERE."""
        bar = bar or self.ladder.ingested_from
        out: dict[str, dict[str, bool]] = {a: {} for a in self.axes}
        for c in self._cells.values():
            reached = self.ladder.at_or_above(c.state, bar)
            for a, v in zip(self.axes, c.coordinates, strict=True):
                if v == ANY:
                    continue
                out[a][v] = bool(out[a].get(v, False) or reached)
        return out

    def _axis_index(self, axes: Sequence[str]) -> tuple[int, ...]:
        if not axes:
            raise ValueError("an axis subset must name at least one axis")
        bad = [a for a in axes if a not in self.axes]
        if bad:
            raise ValueError(f"{bad} are not axes of {self.name}: {self.axes}")
        if len(set(axes)) != len(axes):
            raise ValueError(f"axis subset repeats an axis: {list(axes)}")
        return tuple(self.axes.index(a) for a in axes)

    def holes(self, axes: Sequence[str], k: int, scorer: Scorer | None = None, *,
              at_or_below: str | None = None,
              admissible: Callable[[Mapping[str, str]], bool] | None = None,
              vocabulary: Mapping[str, Sequence[str]] | None = None,
              max_enumerate: int = 200_000) -> list[Hole]:
        """Project onto `axes` and rank the coordinates still at (or below) `at_or_below`.

        The candidate coordinates are the product of the axes' vocabularies (the tensor's own
        unless overridden); ANY and UNMEASURED never enter the product. A coordinate is a hole
        when no stored cell projecting onto it has climbed above the bar (default: the floor).
        The enumeration is bounded and SAYS SO in `last_scan` -- a truncated scan that reports a
        clean count is worse than no scan at all.
        """
        axes = tuple(axes)
        self._axis_index(axes)
        bar = self.ladder.check(at_or_below or self.ladder.floor)
        vocab = dict(self.vocabulary)
        for a, vals in (vocabulary or {}).items():
            vocab[a] = tuple(dict.fromkeys(str(v) for v in vals if str(v)))
        lists: list[tuple[str, ...]] = []
        for a in axes:
            vals = tuple(v for v in vocab.get(a, ()) if v not in (ANY, UNMEASURED))
            if not vals:
                self.last_scan = {"axes": list(axes), "enumerated": 0, "truncated": False,
                                  "covered": 0, "holes": 0, "empty_axis": a,
                                  "why": f"axis {a!r} has no vocabulary; nothing to enumerate"}
                return []
            lists.append(vals)
        marg = self.marginals(axes)
        score = scorer or self.evig_scorer(axes)
        holes: list[Hole] = []
        enumerated = covered = 0
        truncated = False
        for combo in itertools.product(*lists):
            if enumerated >= max_enumerate:
                truncated = True
                break
            enumerated += 1
            values = dict(zip(axes, combo, strict=True))
            if admissible is not None and not admissible(values):
                continue
            row = marg.get(combo)
            state = str(row["best"]) if row is not None else self.ladder.floor
            if self.ladder.rank(state) > self.ladder.rank(bar):
                covered += 1
                continue
            got = score(values)
            if isinstance(got, tuple):
                s, br = float(got[0]), dict(got[1])
            else:
                s, br = float(got), {}
            holes.append(Hole(self.name, axes, combo, state, s, br))
        holes.sort(key=lambda h: (-h.score, h.coordinates))
        self.last_scan = {"axes": list(axes), "enumerated": enumerated, "truncated": truncated,
                          "covered": covered, "holes": len(holes), "bar": bar,
                          "max_enumerate": int(max_enumerate)}
        return holes[:max(int(k), 0)]

    def evig_scorer(self, axes: Sequence[str], *,
                    capacity_of: Callable[[Mapping[str, str]], float | None] | None = None,
                    cost_of: Callable[[Mapping[str, str], str], float | None] | None = None,
                    max_neighbours: int = 400
                    ) -> Callable[[Mapping[str, str]], tuple[float, dict[str, Any]]]:
        """A scorer over the projection onto `axes` that computes EVIG with its breakdown.

        Neighbours are the stored cells (projected) sharing at least one coordinate with the
        hole; reachability is the tensor's own; novelty is the distance to the nearest tested
        projected cell. The projection is built once per scorer, not once per hole.
        """
        axes = tuple(axes)
        idx = self._axis_index(axes)
        marg = self.marginals(axes)
        projected: list[Cell] = []
        by_value: dict[tuple[str, str], list[int]] = {}
        for key, row in marg.items():
            full = [ANY] * len(self.axes)
            for i, j in enumerate(idx):
                full[j] = key[i]
            projected.append(Cell(self.name, tuple(full), str(row["best"]),
                                  {"n": int(row["n"])}, ""))
            for a, v in zip(axes, key, strict=True):
                by_value.setdefault((a, v), []).append(len(projected) - 1)
        reach = self.reachability()

        def _score(values: Mapping[str, str]) -> tuple[float, dict[str, Any]]:
            full = dict.fromkeys(self.axes, ANY)
            full.update({a: str(values.get(a) or ANY) for a in axes})
            cell = Cell(self.name, tuple(full[a] for a in self.axes), self.ladder.floor, {}, "")
            seen: set[int] = set()
            for a in axes:
                for i in by_value.get((a, full[a]), ()):
                    seen.add(i)
                    if len(seen) >= max_neighbours:
                        break
            neighbours = [projected[i] for i in sorted(seen)]
            cap = capacity_of(values) if capacity_of is not None else None
            cost = cost_of(values, cell.state) if cost_of is not None else None
            br = evig_breakdown(cell, neighbours, axes=axes, reach=reach, capacity=cap, cost=cost)
            return float(br["evig"]), br

        return _score

    # ---- json
    def to_json(self) -> dict[str, Any]:
        return {"tensor": self.name, "axes": list(self.axes), "ladder": list(self.ladder.states),
                "vocabulary": {a: list(v) for a, v in self.vocabulary.items()},
                "n_cells": len(self._cells), "histogram": self.histogram(),
                "cells": [c.to_json() for c in self.cells()]}

    @classmethod
    def from_json(cls, doc: Mapping[str, Any]) -> Tensor:
        vocab = doc.get("vocabulary")
        t = cls(str(doc["tensor"]), vocabulary=vocab if isinstance(vocab, Mapping) else None)
        for raw in doc.get("cells") or []:
            if isinstance(raw, Mapping):
                t.put(Cell.from_json(raw))
        return t


# --------------------------------------------------------------------------------------- EVIG
def _hamming(a: Cell, b: Cell, idx: Sequence[int]) -> int:
    return sum(1 for i in idx if a.coordinates[i] != b.coordinates[i])


def evig_breakdown(cell: Cell, neighbours: Iterable[Cell], *, axes: Sequence[str] | None = None,
                   reach: Mapping[str, Mapping[str, bool]] | None = None,
                   capacity: float | None = None, cost: float | None = None) -> dict[str, Any]:
    """Every factor of EVIG for `cell`, and the product. See the module docstring."""
    ladder = ladder_of(cell.tensor)
    all_axes = axes_of(cell.tensor)
    axes = tuple(axes) if axes else all_axes
    bad = [a for a in axes if a not in all_axes]
    if bad:
        raise ValueError(f"{bad} are not axes of {cell.tensor}: {all_axes}")
    idx = [all_axes.index(a) for a in axes]
    near = [n for n in neighbours if n.tensor == cell.tensor and n.coordinates != cell.coordinates]

    # prior P(edge | evidence in neighbouring cells): Laplace-smoothed with the desk's prior
    pos = sum(1 for n in near if n.state in ladder.positive)
    neg = sum(1 for n in near if n.state in ladder.negative)
    prior = (pos + PRIOR) / (pos + neg + 1.0)

    # reachability: each axis component has data at >= INGESTED somewhere
    if reach is None:
        reach_map: dict[str, dict[str, bool]] = {a: {} for a in all_axes}
        for n in near:
            reached = ladder.at_or_above(n.state, ladder.ingested_from)
            for a, v in zip(all_axes, n.coordinates, strict=True):
                if v != ANY:
                    reach_map[a][v] = bool(reach_map[a].get(v, False) or reached)
    else:
        reach_map = {a: dict(reach.get(a, {})) for a in all_axes}
    considered = [(a, cell.coordinates[all_axes.index(a)]) for a in axes]
    concrete = [(a, v) for a, v in considered if v not in (ANY, UNMEASURED)]
    unreachable = [a for a, v in concrete if not reach_map.get(a, {}).get(v, False)]
    reach_frac = (len(concrete) - len(unreachable)) / len(concrete) if concrete else PRIOR
    reachability = max(reach_frac, REACH_FLOOR)

    # novelty: distance to the nearest tested cell over the axes considered
    tested = [n for n in near if ladder.at_or_above(n.state, ladder.tested_from)]
    if tested:
        nearest = min(_hamming(cell, n, idx) for n in tested)
        novelty = nearest / max(len(idx), 1)
    else:
        nearest = len(idx)
        novelty = 1.0
    novelty = max(novelty, 1.0 / max(len(idx), 1)) if tested else 1.0

    # capacity proxy and cost
    if capacity is None:
        cap, cap_basis = PRIOR, "UNMEASURED -> prior 0.5"
    else:
        cap, cap_basis = min(1.0, max(CAPACITY_FLOOR, float(capacity))), "measured"
    if cost is None:
        c, cost_basis = RUNG_COST[cell.tensor].get(cell.state, 1.0), f"RUNG_COST[{cell.state}]"
    else:
        c, cost_basis = max(float(cost), 1e-3), "measured"
    value = prior * reachability * novelty * cap / c
    return {"evig": round(float(value), 6), "prior_p_edge": round(prior, 4),
            "judged_neighbours": {"positive": pos, "negative": neg, "n_neighbours": len(near)},
            "reachability": round(reachability, 4), "reach_fraction": round(reach_frac, 4),
            "unreachable_axes": unreachable, "novelty": round(novelty, 4),
            "nearest_tested_distance": int(nearest), "n_tested_neighbours": len(tested),
            "capacity": round(cap, 4), "capacity_basis": cap_basis, "cost": round(c, 4),
            "cost_basis": cost_basis, "state": cell.state,
            "next_state": ladder.next_state(cell.state), "axes": list(axes)}


def evig(cell: Cell, neighbours: Iterable[Cell], *, axes: Sequence[str] | None = None,
         reach: Mapping[str, Mapping[str, bool]] | None = None, capacity: float | None = None,
         cost: float | None = None) -> float:
    """EVIG = prior x reachability x novelty x capacity / cost. `evig_breakdown` has the parts."""
    return float(evig_breakdown(cell, neighbours, axes=axes, reach=reach, capacity=capacity,
                                cost=cost)["evig"])


# ------------------------------------------------------------------------------ country coverage
def covered(country: str, layer_inventory: Mapping[str, Sequence[Mapping[str, Any]]],
            discovery_rate: Mapping[str, Any] | float | None) -> dict[str, Any]:
    """The principal's two-condition rule, and the verdict names both conditions.

    `layer_inventory` is {layer: [source rows]} in the shape `country_lab.layer_inventory`
    returns (a row with `verified` True maps its layer; a row with `absent_reason` declares the
    layer absent WITH a reason, which is mapped too). `discovery_rate` is either a per-day float
    or `country_lab.discovery_rate`'s mapping (`measured`, `per_day`). An unmeasured rate blocks
    COVERED: absence of evidence about discovery is never evidence that discovery is healthy.
    """
    code = str(country or "").strip().lower() or "unknown"
    layers: dict[str, dict[str, Any]] = {}
    for layer in SOURCE_LAYERS:
        rows = [r for r in layer_inventory.get(layer, ()) if isinstance(r, Mapping)]
        verified = [r for r in rows if bool(r.get("verified"))]
        absent = [r for r in rows if str(r.get("absent_reason") or "").strip()]
        if absent:
            state, why = "ABSENT_DECLARED", str(absent[0]["absent_reason"])
        elif verified:
            state, why = "MAPPED", f"{len(verified)} verified source(s)"
        elif rows:
            state, why = "DECLARED_UNVERIFIED", f"{len(rows)} declared, none fetched yet"
        else:
            state, why = "UNMAPPED", "no source and no declared absence for this layer"
        layers[layer] = {"state": state, "sources": len(rows), "verified": len(verified),
                         "why": why}
    mapped = [k for k, v in layers.items() if v["state"] in ("MAPPED", "ABSENT_DECLARED")]
    unmapped = [k for k, v in layers.items() if v["state"] == "UNMAPPED"]
    unverified = [k for k, v in layers.items() if v["state"] == "DECLARED_UNVERIFIED"]
    n_verified = sum(int(v["verified"]) for v in layers.values())
    untagged = len([r for r in layer_inventory.get("UNTAGGED", ()) if isinstance(r, Mapping)])
    cond_layers = {"met": not unmapped and not unverified, "mapped": mapped,
                   "unmapped": unmapped, "declared_unverified": unverified,
                   "verified_sources": n_verified, "untagged_sources": untagged}

    measured, per_day, why_rate = False, None, "discovery rate not supplied"
    if isinstance(discovery_rate, Mapping):
        measured = bool(discovery_rate.get("measured", discovery_rate.get("per_day") is not None))
        raw = discovery_rate.get("per_day")
        per_day = float(raw) if raw is not None else None
        why_rate = str(discovery_rate.get("why") or "")
        if per_day is None:
            measured = False
    elif discovery_rate is not None:
        measured, per_day, why_rate = True, float(discovery_rate), ""
    cond_disc = {"met": bool(measured and per_day is not None and per_day > 0.0),
                 "measured": measured, "per_day": per_day, "why": why_rate}

    if not measured:
        state = "UNMEASURED"
        why = f"the discovery rate is unmeasured: {why_rate or 'no reading'}"
    elif not cond_layers["met"]:
        state = "MAPPING"
        why = (f"{len(mapped)}/{len(SOURCE_LAYERS)} layers mapped; unmapped={unmapped}; "
               f"declared but never fetched={unverified}")
    elif not cond_disc["met"]:
        state = "STALLED"
        why = (f"every layer is mapped but discovery added nothing for {code} in the window; "
               "the scouts ran out of ideas, not the country out of sources")
    else:
        state = "COVERED"
        why = (f"all {len(SOURCE_LAYERS)} layers mapped or declared absent with a reason, and "
               f"discovery is still adding {per_day}/day")
    return {"country": code, "covered": state == "COVERED", "state": state, "why": why,
            "condition_layers": cond_layers, "condition_discovery": cond_disc,
            "layers": layers, "rule": COVERAGE_RULE}


# --------------------------------------------------------------------------------------- floors
def ratchet(previous_floor: Mapping[str, float] | float | None,
            current: Mapping[str, float] | float) -> dict[str, Any]:
    """A floor never goes down. Returns the new floors and names what sits BELOW its floor.

    For mappings the ratchet is per key: a key seen before keeps max(previous, current); a key
    never seen enters at its current value; a key that vanished from `current` keeps its floor
    (a measurement that stopped is not a floor that dropped). For scalars the same, in one key.
    """
    prev: dict[str, float] = {}
    if isinstance(previous_floor, Mapping):
        for k, v in previous_floor.items():
            try:
                prev[str(k)] = float(v)
            except (TypeError, ValueError):
                continue
    elif previous_floor is not None:
        prev["value"] = float(previous_floor)
    cur: dict[str, float] = {}
    if isinstance(current, Mapping):
        for k, v in current.items():
            try:
                cur[str(k)] = float(v)
            except (TypeError, ValueError):
                continue
    else:
        cur["value"] = float(current)
    floors: dict[str, float] = dict(prev)
    raised: list[str] = []
    below: dict[str, dict[str, float]] = {}
    for k, v in cur.items():
        if k not in floors or v > floors[k]:
            floors[k] = v
            raised.append(k)
        elif v < floors[k]:
            below[k] = {"floor": floors[k], "current": v}
    return {"floors": dict(sorted(floors.items())), "raised": sorted(raised),
            "below_floor": dict(sorted(below.items())),
            "rule": "floors ratchet up only; a measurement below its floor is reported, never "
                    "used to lower it"}


# ----------------------------------------------------------------------------- the named examples
#: The three frontier rows the specification names. Each is a full coordinate of one tensor and
#: the sentence it stands for, so a test can construct it and a reader can recognise it.
EXAMPLE_FRONTIER_ROWS: tuple[dict[str, Any], ...] = (
    {"label": "indonesia_nickel_china_cycle_aud_asia_risk_off", "tensor": WORLD,
     "story": "Indonesia nickel exports x China industrial cycle x AUD x Asian session x "
              "risk-off has never been tested",
     "values": {"country": "id", "sector": "metals_mining", "information_type": "customs",
                "mechanism": "cross_market_lead", "representation": "cross_country_spread",
                "asset": "AUDUSD", "session": "asia", "regime": "risk_off", "horizon": "1d",
                "execution": "market"}},
    {"label": "korea_semiconductor_supply_chain_jpy_asia", "tensor": WORLD,
     "story": "Korean semiconductor supply-chain data x JPY x Asian session has no candidate "
              "history",
     "values": {"country": "kr", "sector": "semiconductors", "information_type": "supply_chain",
                "mechanism": "cross_market_lead", "representation": "surprise",
                "asset": "USDJPY", "session": "asia", "regime": "unconditional",
                "horizon": "1d", "execution": "market"}},
    {"label": "russia_energy_shipping_brent_eurusd", "tensor": WORLD,
     "story": "Russian energy-shipping local sources x Brent x EURUSD have never been tested",
     "values": {"country": "ru", "sector": "energy_oil_gas",
                "information_type": "physical_exhaust", "mechanism": "cross_market_lead",
                "representation": "delta", "asset": "EURUSD", "session": "london",
                "regime": "unconditional", "horizon": "1d", "execution": "market"},
     "transmission": "XBRUSD -> EURUSD"},
    {"label": "russia_energy_shipping_local_sources", "tensor": FOREST,
     "story": "Russian-language physical-economy (shipping) sources for the energy sector, "
              "transmitting through Brent into EURUSD",
     "values": {"country": "ru", "language": "ru", "source_class": "physical_economy",
                "sector": "energy_oil_gas", "mechanism": "cross_market_lead",
                "asset_transmission": "XBRUSD", "freshness": "daily",
                "accessibility": "PUBLIC"}},
)


def example_cells() -> list[Cell]:
    """The named example rows as floor cells, constructible on any tree."""
    out: list[Cell] = []
    for row in EXAMPLE_FRONTIER_ROWS:
        tensor = str(row["tensor"])
        axes = axes_of(tensor)
        values = dict(row["values"])
        out.append(Cell(tensor, tuple(str(values.get(a) or ANY) for a in axes),
                        ladder_of(tensor).floor,
                        {"label": row["label"], "story": row["story"]}, ""))
    return out
