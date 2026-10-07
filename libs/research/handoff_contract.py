"""THE HANDOFF CONTRACT (ARCH-11) -- a quantity keeps its unit, currency, vintage, horizon,
instrument identity and gross/net basis at every hop from research to the order intent.

WHY THIS EXISTS. `desks/mt5/research/forecast_contract.py` made a belief scoreable: a kind, a
horizon, a timestamp. It buckets horizons and checks lookahead, and that is all it checks. Nothing
checked the HANDOFFS -- the files one organ publishes and the next organ reads -- for the six
properties a number needs to mean the same thing on both sides of the file:

    unit          R, a heat fraction, a probability, account currency, points... A risk fraction
                  of 3.0 is 3% to one reader and 300% to the next. The swap term on this desk was
                  read as CURRENCY PER LOT for 181 of 251 symbols while the broker published POINTS
                  (improvement_inbox 2026-08-28), and `tick_value` once vanished from all 197
                  symbols, zeroing every account-currency cost (GAP_REGISTER #142).
    currency      which currency a currency-bearing unit is denominated in.
    known_at      the release VINTAGE: when the information the number rests on became knowable.
                  A vintage later than the publication is lookahead with a timestamp on it.
    horizon_s     the span the quantity holds over. A one-hour edge sized as a one-week one is not
                  a result; forecast_contract's buckets are reused here so the two never disagree.
    instrument_id which instrument -- a Fusion symbol from the universe registry, or BOOK for a
                  quantity about the whole book or the world. A symbol the registry does not quote
                  is a broken identity, not a new instrument.
    gross_or_net  gross or net of costs. Net edge read downstream as gross double-counts costs;
                  gross read as net forgets them.

A document whose headline quantity is in one unit and a named secondary field in another declares
the exception in the optional `field_units` map, validated like the unit itself.

THE CHAIN, in order: forecast -> allocator_input -> gateway_intent. `SURFACES` lists every
published handoff on it: the forecast register, every input `allocator_liveness.inputs()` says
the allocator reads, and the gateway's intent rows (sleeves.json, the allocation). The fence
`scripts/check_handoff_contract.py` reads them and fails on a missing or inconsistent field.

MONEY-PATH PRODUCERS (the promoter, the allocator) cannot be edited from a research session, so
their surfaces sit on `PENDING_MONEY_PATH`: a shrink-only ratchet whose entries must still be
unstamped (a healed entry fails until it is removed). Every other producer stamps its artifact
through `stamp()` and the fence proves the call is in its source.

IT SIZES NOTHING AND VETOES NOTHING. It labels quantities and a fence reads the labels.
"""
from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = "handoff/v1"
KEY = "handoff"
FIELDS: tuple[str, ...] = ("unit", "currency", "known_at", "horizon_s", "instrument_id",
                           "gross_or_net")
#: The chain, in order. A later stage consumes what an earlier one published.
STAGES: tuple[str, ...] = ("forecast", "allocator_input", "gateway_intent")
#: unit -> whether it is denominated in a currency. A currency-bearing unit without a currency
#: is a missing field; a currency on a currency-free unit is an inconsistent one.
UNITS: dict[str, bool] = {
    "R": False,                 # multiples of the trade's own risk
    "R_per_day": False,
    "return_frac": False,       # a fractional return on capital
    "heat_frac": False,         # a fraction of equity at risk (0.03 = 3%), never a percent
    "probability": False,
    "elogw_per_day": False,
    "dimensionless": False,     # tilts, factors, betas, z-scores, shrink weights
    "bucket": False,            # a categorical state label
    "points": False,            # broker points (price increments)
    "lots": False,
    "account_ccy": True,        # money in the account's currency
    "price": True,              # a price, in the instrument's profit currency
}
GROSS_OR_NET: tuple[str, ...] = ("gross", "net", "not_applicable")
BOOK = "BOOK"
UNIVERSE = ROOT / "desks" / "mt5" / "data" / "universe" / "universe.json"
#: A vintage this far past "now" is a clock error, not lookahead; past it, it is lookahead.
FUTURE_SLACK_S = 300.0


@dataclass(frozen=True)
class Handoff:
    """The six carried fields, plus the chain stage that published them."""

    stage: str
    unit: str
    known_at: str
    horizon_s: float
    instrument_id: Any          # a symbol, BOOK, or {"rows": <key>, "field": <dotted field>}
    gross_or_net: str
    currency: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"contract": CONTRACT, **asdict(self)}


def parse_iso(x: Any) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(x))
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def field_defects(h: Mapping[str, Any] | None, *, now: datetime | None = None) -> list[str]:
    """Every missing or malformed carried field. Empty means the block is complete."""
    if not isinstance(h, Mapping):
        return ["no handoff block"]
    out: list[str] = []
    for f in FIELDS:
        if f not in h:
            out.append(f"missing field {f}")
    if out:
        return out
    if h.get("stage") not in STAGES:
        out.append(f"stage {h.get('stage')!r} is not on the chain {list(STAGES)}")
    unit = h.get("unit")
    if unit not in UNITS:
        out.append(f"unit {unit!r} is not a declared unit {sorted(UNITS)}")
    else:
        ccy = h.get("currency")
        if UNITS[unit] and not (isinstance(ccy, str) and len(ccy) == 3 and ccy.isupper()):
            out.append(f"unit {unit} is currency-bearing and currency {ccy!r} is not an ISO code")
        if not UNITS[unit] and ccy not in (None, ""):
            out.append(f"unit {unit} carries no currency but the block names {ccy!r}")
    hz = h.get("horizon_s")
    if (not isinstance(hz, (int, float)) or isinstance(hz, bool) or not math.isfinite(hz)
            or hz <= 0):
        out.append(f"horizon_s {hz!r} must be a positive number of seconds")
    if h.get("gross_or_net") not in GROSS_OR_NET:
        out.append(f"gross_or_net {h.get('gross_or_net')!r} not in {list(GROSS_OR_NET)}")
    known = parse_iso(h.get("known_at"))
    if known is None:
        out.append(f"known_at {h.get('known_at')!r} is not an ISO timestamp")
    else:
        ref = now or datetime.now(UTC)
        if (known - ref).total_seconds() > FUTURE_SLACK_S:
            out.append(f"known_at {h.get('known_at')} is in the future: a vintage that has not "
                       "been released yet is lookahead")
    fu = h.get("field_units")
    if fu is not None:
        if not isinstance(fu, Mapping):
            out.append("field_units, when given, maps a field name to a declared unit")
        else:
            for k, u in fu.items():
                if u not in UNITS:
                    out.append(f"field_units[{k!r}] = {u!r} is not a declared unit")
                elif UNITS[u] and not h.get("currency"):
                    out.append(f"field_units[{k!r}] = {u} is currency-bearing and the block "
                               "names no currency")
    iid = h.get("instrument_id")
    if isinstance(iid, Mapping):
        if not iid.get("rows") or not iid.get("field"):
            out.append("a per-row instrument_id must name both `rows` and `field`")
    elif not (isinstance(iid, str) and iid.strip()):
        out.append("instrument_id is empty")
    return out


def block(stage: str, *, unit: str, horizon_s: float, instrument_id: Any, gross_or_net: str,
          currency: str | None = None, known_at: str | None = None,
          field_units: Mapping[str, str] | None = None) -> dict[str, Any]:
    """A complete handoff block. Raises ValueError on a defective declaration: the arguments are
    the producer's constants, so a bad one is a bug the producer's own test must catch."""
    h = Handoff(stage=stage, unit=unit,
                known_at=known_at or datetime.now(UTC).isoformat(timespec="seconds"),
                horizon_s=float(horizon_s), instrument_id=instrument_id,
                gross_or_net=gross_or_net, currency=currency).as_dict()
    if field_units:
        h["field_units"] = dict(field_units)
    bad = field_defects(h)
    if bad:
        raise ValueError(f"handoff declaration is defective: {bad}")
    return h


def stamp(doc: dict[str, Any], stage: str, **kw: Any) -> dict[str, Any]:
    """Put the handoff block on a document-level artifact and return the document."""
    doc[KEY] = block(stage, **kw)
    return doc


# --------------------------------------------------------------------------- the chain's surfaces
@dataclass(frozen=True)
class Surface:
    name: str
    path: str                   # relative to the repo root
    stage: str
    producer: str               # relative path of the module that writes it
    layout: str = "document"    # "document" (one block) or "jsonl_rows" (a block per row)
    money_path: bool = False


_D = "desks/mt5/data/"
_R = "desks/mt5/reports/"
_P = "desks/mt5/research/"
SURFACES: tuple[Surface, ...] = (
    # forecast: the register every model publishes beliefs into
    Surface("forecast_register", _D + "forecast_register.jsonl", "forecast",
            _P + "forecast_contract.py", layout="jsonl_rows"),
    # allocator_input: every input allocator_liveness.inputs() says pf_allocator reads
    Surface("allocator_evidence", _D + "allocator_evidence.json", "allocator_input",
            _P + "financing_lab.py"),
    Surface("roi_capital_evidence", _D + "roi_capital_evidence.json", "allocator_input",
            _P + "research_roi.py"),
    Surface("net_edge", _R + "NET_EDGE.json", "allocator_input", _P + "net_edge_spine.py"),
    Surface("posterior_alpha", _R + "POSTERIOR_ALPHA.json", "allocator_input",
            _P + "posterior_alpha.py"),
    Surface("exposure_decomposition", _R + "EXPOSURE_DECOMPOSITION.json", "allocator_input",
            _P + "exposure_decomposition.py"),
    Surface("state_vector", _D + "state_vector.json", "allocator_input",
            _P + "state_vector_build.py"),
    Surface("state_admission", _R + "STATE_ADMISSION.json", "allocator_input",
            _P + "state_admission_run.py"),
    Surface("regime_state", _D + "regime_state.json", "allocator_input",
            _P + "regime_monitor.py"),
    Surface("macro_view", _R + "MACRO_VIEW.json", "allocator_input",
            "desks/mt5/mt5desk/macro_view.py"),
    Surface("drift", _R + "DRIFT.json", "allocator_input", _P + "drift_monitor.py"),
    Surface("sleeve_registry", _D + "sleeve_registry.json", "allocator_input",
            _P + "sleeve_registry.py"),
    Surface("sleeves", _D + "sleeves.json", "allocator_input", _P + "promoter.py",
            money_path=True),
    # gateway_intent: what the gateway sizes and places from
    Surface("pf_allocation", _R + "pf_allocation.json", "gateway_intent",
            _P + "pf_allocator.py", money_path=True),
    Surface("pf_forecast_log", _D + "pf_forecast_log.jsonl", "gateway_intent",
            _P + "pf_allocator.py", layout="jsonl_rows", money_path=True),
    Surface("sleeves_intent", _D + "sleeves.json", "gateway_intent", _P + "promoter.py",
            money_path=True),
)

#: MONEY-PATH SURFACES AWAITING THE DESKTOP PASS. RATCHET: may only shrink, and every entry must
#: still be unstamped -- a healed entry fails until it is removed. Adding to it lowers the gate.
PENDING_MONEY_PATH: dict[str, str] = {
    "sleeves": "research/promoter.py writes it; cloud edits to the promoter are refused",
    "sleeves_intent": "research/promoter.py writes it; cloud edits to the promoter are refused",
    "pf_allocation": "research/pf_allocator.py writes it; the allocator is money path",
    "pf_forecast_log": "research/pf_allocator.py appends it; the allocator is money path",
}
PENDING_CEILING = 4


# --------------------------------------------------------------------------- reading the surfaces
def universe(path: Path = UNIVERSE) -> dict[str, dict[str, Any]]:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in doc.items() if isinstance(v, dict)} if isinstance(doc, dict) else {}


def _dotted(row: Any, field: str) -> Any:
    cur = row
    for part in field.split("."):
        if not isinstance(cur, Mapping):
            return None
        cur = cur.get(part)
    return cur


def instruments(doc: Mapping[str, Any], h: Mapping[str, Any]) -> list[Any]:
    """The instrument ids a block declares: one id, or one per row of a per-row spec."""
    iid = h.get("instrument_id")
    if not isinstance(iid, Mapping):
        return [iid]
    rows = doc.get(str(iid.get("rows")))
    seq: Iterable[Any] = rows.values() if isinstance(rows, Mapping) else (rows or [])
    return [_dotted(r, str(iid.get("field"))) for r in seq]


def identity_defects(ids: Iterable[Any], uni: Mapping[str, Any]) -> list[str]:
    """An id is BOOK or a symbol the universe registry quotes. Absence of the registry itself is
    UNMEASURED and reported by the caller, never a pass of every id."""
    bad: dict[str, int] = {}
    for i in ids:
        if i == BOOK:
            continue
        if not isinstance(i, str) or not i.strip():
            bad["<missing>"] = bad.get("<missing>", 0) + 1
        elif uni and i not in uni:
            bad[i] = bad.get(i, 0) + 1
    return [f"instrument {k!r} ({n} row(s)) is neither BOOK nor a symbol the universe registry "
            "quotes" for k, n in sorted(bad.items())]


@dataclass(frozen=True)
class Declaration:
    """One (surface, instrument) reading, for the cross-hop checks."""

    surface: str
    stage: str
    instrument: str
    unit: str
    currency: str | None
    horizon_s: float
    gross_or_net: str


def declarations(surface: Surface, doc: Mapping[str, Any] | None,
                 rows: list[Mapping[str, Any]] | None) -> list[Declaration]:
    out: list[Declaration] = []
    pairs: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
    if rows is not None:
        pairs = [(r, r[KEY]) for r in rows if isinstance(r.get(KEY), Mapping)]
    elif doc is not None and isinstance(doc.get(KEY), Mapping):
        pairs = [(doc, doc[KEY])]
    seen: set[tuple[Any, ...]] = set()
    for src, h in pairs:
        if field_defects(h):
            continue
        for iid in instruments(src, h):
            if not isinstance(iid, str):
                continue
            d = Declaration(surface.name, surface.stage, iid, str(h["unit"]), h.get("currency"),
                            float(h["horizon_s"]), str(h["gross_or_net"]))
            k = tuple(asdict(d).values())
            if k not in seen:
                seen.add(k)
                out.append(d)
    return out


def _bucket(horizon_s: float) -> str:
    try:
        import sys
        p = str(ROOT / "desks" / "mt5" / "research")
        if p not in sys.path:
            sys.path.insert(0, p)
        from forecast_contract import bucket_of  # type: ignore[import-not-found]
        return str(bucket_of(horizon_s))
    except Exception:                                            # pragma: no cover - import guard
        return f"{horizon_s:.0f}s"


def cross_hop(decls: list[Declaration], uni: Mapping[str, Any] | None = None) -> list[str]:
    """Inconsistencies BETWEEN surfaces on the chain, keyed by instrument (BOOK meets every one).

    1. CURRENCY: one instrument's currency-bearing unit names one currency everywhere, and a
       `price` agrees with the profit currency the universe registry gives the instrument.
    2. GROSS -> NET ONLY: once an earlier stage publishes a quantity NET of costs, a later stage
       may not publish the same instrument and unit GROSS -- that adds the costs back silently.
    3. HORIZON: one instrument and unit carry one horizon bucket across stages.
    """
    out: list[str] = []
    order = {s: i for i, s in enumerate(STAGES)}
    uni = uni or {}
    for d in decls:
        prof = (uni.get(d.instrument) or {}).get("currency_profit")
        if d.unit == "price" and prof and d.currency and d.currency != prof:
            out.append(f"{d.surface}: {d.instrument} price in {d.currency}, but the registry's "
                       f"profit currency is {prof}")
    for i, a in enumerate(decls):
        for b in decls[i + 1:]:
            if a.surface == b.surface or a.unit != b.unit:
                continue
            if not (a.instrument == b.instrument or BOOK in (a.instrument, b.instrument)):
                continue
            inst = a.instrument if a.instrument != BOOK else b.instrument
            if UNITS.get(a.unit) and a.currency != b.currency:
                out.append(f"{inst} {a.unit}: {a.surface} says {a.currency}, "
                           f"{b.surface} says {b.currency}")
            lo, hi = (a, b) if order[a.stage] <= order[b.stage] else (b, a)
            if order[lo.stage] < order[hi.stage] and lo.gross_or_net == "net" \
                    and hi.gross_or_net == "gross":
                out.append(f"{inst} {a.unit}: {lo.surface} ({lo.stage}) is NET and "
                           f"{hi.surface} ({hi.stage}) republishes it GROSS")
            if (a.instrument == b.instrument != BOOK and a.stage != b.stage
                    and _bucket(a.horizon_s) != _bucket(b.horizon_s)):
                out.append(f"{inst} {a.unit}: horizon {_bucket(a.horizon_s)} at {a.surface}, "
                           f"{_bucket(b.horizon_s)} at {b.surface}")
    return sorted(set(out))
