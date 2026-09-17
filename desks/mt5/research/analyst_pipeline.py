"""THE ANALYST PIPELINE: a lead becomes a hypothesis through named stages, or it dies with a code.

WHY THIS EXISTS (ledger item W5, the principal's 2026-09-16 blueprint). The desk has miners that
find leads and a compiler that turns already-shaped rows into cells. Between them sat an ANALYST
nobody had written: the step that decides whether a raw claim is about an instrument this desk can
trade, whether it names a mechanism, whether the desk already asked the question, what registered
family and parameters the claim actually means, and whether the resulting cell fires often enough
to be worth a gauntlet slot. That work was happening -- diffusely, inside prose readers and seat
prompts -- and NOBODY COULD SAY WHERE LEADS DIED. A funnel whose losses are not coded is not a
funnel; it is a directory that gets smaller.

So: five stages, and every rejection carries a CODE and is COUNTED.

    INTAKE      every lead under data/intelligence/** and the frontier queue, newest artifact
                first, through `libs/research/lead_schema` -- one claim per lead, in the source's
                own words -- minus the ones the cursor says were already worked.
    TRIAGE      an MT5-tradable instrument (the two-lane order decides, by ASSET CLASS, never by a
                symbol list), a mechanism named or inferable, and not a question already asked.
                Codes: operational_row, no_claim_text, no_instrument, event_lane_instrument,
                unclassified_instrument, no_mechanism, duplicate_lead, duplicate_cell.
    STRUCTURING the claim -> a registered family + params + symbols, through the axis registry's
                FAMILY_TABLE (family -> mechanism, inverted here) and the claim's own numbers.
                THE SEAT'S STRUCTURED FIELDS WIN: a lead carrying an `executable` block has had
                its analyst step done and the prose is not re-read. Codes:
                no_family_for_mechanism, family_not_registered, family_not_price_only,
                no_params_from_claim, duplicate_cell.
    PRE-SCREEN  the cheapest honest question: run the family's OWN signal function over the desk's
                H1 bars and count what it fires. Under MIN_TRADES the cell is an anecdote, not a
                hypothesis. Codes: no_bars, signal_error, too_few_trades, budget_exhausted.
    DONATION    `proposer_common.donate` -- the ONE door, which stamps point-in-time or refuses.
    FOLLOW-UP   later runs' gate verdicts joined back to the lead that produced them, so
                conversion is measured PER LEAD KIND rather than asserted in aggregate.

THE LAYER ABOVE `miner_candidate_compiler`, NOT A SECOND COPY OF IT. The compiler decides what an
already-shaped row compiles to and stays the docket's intake; this decides which RAW leads are
worth shaping at all, and hands survivors over through the same discovery contract -- `kind:
"hypothesis"` rows the compiler admits as STRUCTURED_HYPOTHESIS. Its prose readers are reused
where exposed (`text_symbols`, `text_families`, `text_session`, `_text_params`) so the two lanes
cannot drift on what a paragraph names, or mint different cells from the same sentence.

THE SEAT DIRECTORY CANNOT CARRY THE LEAD KIND, AND THE ROW DOES. The donation source is
`analyst_pipeline:<lead_kind>` on every row, as specified -- but the donation DIRECTORY is the
bare seat name, because a colon is not a legal path character on the box that trades (measured:
`mkdir` raises WinError 267). `recent_rows` reads `row["source"]` first and the directory second,
so the per-kind tag survives into the compiler's own accounting, which is what it was for.

PRICE-ONLY BY CONSTRUCTION. The pre-screen has bars and nothing else, so a family needing a swap
table, a peer series or a calendar cannot be honestly screened here. It is refused with
`family_not_price_only` rather than run on its defaults and labelled as the claim's test.

    python analyst_pipeline.py [--dry-run] [--max-leads 200] [--budget-s 240]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parents[1]
for _p in (str(REPO), str(BASE), str(BASE / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UNI = BASE / "data" / "universe"
INTEL_ROOTS = (BASE / "data" / "intelligence", REPO / "data" / "intelligence")
FRONTIER_QUEUE = BASE / "frontier_intel" / "data" / "frontier_queue.jsonl"
GRAPH = BASE / "data" / "hypothesis_graph.jsonl"
GATE_LEDGER = BASE / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
OUT_REPORT = BASE / "reports" / "ANALYST_PIPELINE.json"
LEDGER = BASE / "data" / "analyst_pipeline.jsonl"
CURSOR = BASE / "data" / "analyst_pipeline_cursor.json"

#: Independent signals a cell must fire before its mean is a number rather than an anecdote.
#: The same 30 `proposer_common.MIN_TRADES` uses, so the analyst's floor and the screen's agree.
MIN_TRADES = 30
WINDOW_DAYS = 7
MAX_LEADS = 200
BUDGET_S = 240.0
MAX_TEXT_CHARS = 20_000
MAX_SYMBOLS_PER_LEAD = 4
MAX_FAMILIES_PER_LEAD = 2
MAX_CURSOR_IDS = 50_000
MAX_LEDGER_LINES = 200_000
SEAT = "analyst_pipeline"
#: Row kinds that are machine state rather than a claim about a market. `lead_schema` refuses
#: these too; this list exists so the refusal is COUNTED here instead of happening off-ledger.
OPERATIONAL_KINDS = frozenset({
    "walled", "fetch_error", "stub", "probe", "error", "skipped", "status", "state", "heartbeat",
    "coverage", "cursor", "config", "endpoint", "endpoints", "metric", "metrics", "log",
})
RULE = ("a lead becomes a hypothesis through named stages; every stage's rejection is coded and "
        "counted; conversion is measured per lead kind")


# ============================================================================== the lead shape
def _schema():
    """`libs.research.lead_schema`, the canonical lead. None when it is not on this tree yet."""
    try:
        from libs.research import lead_schema
        return lead_schema
    except Exception:
        return None


def _stub_lead(schema, row: dict, seat: str):
    """A lead for a row the schema declined, built with the SCHEMA'S OWN class -- not a second
    shape. The schema returns nothing for a row that is not evidence, which is right for a schema
    and wrong for a funnel: the row would vanish between two clean-looking numbers. This carries
    it to triage, where it is refused with a code, on the record."""
    text = next((row[k].strip()[:2000] for k in
                 ("claim", "text", "description", "mechanism", "body", "summary", "title")
                 if isinstance(row.get(k), str) and row[k].strip()), "")
    kind = str(row.get("kind") or row.get("type") or "").strip().lower()
    payload = json.dumps(row, sort_keys=True, default=str, separators=(",", ":"))
    return schema.Lead(
        lead_id=hashlib.sha256(payload.encode()).hexdigest()[:16],
        kind=kind or ("other" if text else "not_evidence"),
        source_id=str(row.get("source") or seat or "unknown"), url_or_ref="", seen_at="",
        knowable_at="", language="", claim_text=text, doc_id="", claim_index=0)


# ============================================================================= tolerant reading
def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _rows_of(doc: Any) -> list[dict]:
    if isinstance(doc, list):
        return [r for r in doc if isinstance(r, dict)]
    if isinstance(doc, dict):
        for key in ("discoveries", "rows", "items", "candidates", "leads", "results"):
            if isinstance(doc.get(key), list):
                return [r for r in doc[key] if isinstance(r, dict)]
    return []


def _read_jsonl(path: Path, limit: int = MAX_LEDGER_LINES) -> list[dict]:
    """Every parseable object in a jsonl file. A bad line is skipped, never fatal."""
    out: list[dict] = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for i, line in enumerate(fh):
                if i >= limit:
                    break
                try:
                    row = json.loads(line.strip() or "0")
                except ValueError:
                    continue
                if isinstance(row, dict):
                    out.append(row)
    except OSError:
        pass
    return out


def _atomic_json(path: Path, value: Any) -> None:
    """Atomic where the filesystem allows it. `os.replace` onto a read-only file is WinError 5."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=1, default=str), "utf-8")
    try:
        os.replace(tmp, path)
    except OSError:
        path.write_text(tmp.read_text("utf-8"), "utf-8")
        tmp.unlink(missing_ok=True)


def known_symbols() -> set[str]:
    """The registry's symbols in the registry's OWN case -- a stem is what prices the bars."""
    return {p.stem.removesuffix("_H1") for p in UNI.glob("*_H1.parquet")}


def bars(symbol: str):
    """H1 bars for `symbol`, or None. pandas is imported lazily so `--help` costs nothing."""
    import pandas as pd
    path = UNI / f"{symbol}_H1.parquet"
    if not path.exists():
        return None
    try:
        df = pd.read_parquet(path)
    except (OSError, ValueError, ImportError):
        return None
    if df.empty or "close" not in df.columns:
        return None
    df.index = pd.DatetimeIndex(pd.to_datetime(df.index, utc=True, errors="coerce"))
    return df[~df.index.isna()]


# ============================================================ the desk's own tables, guardedly
def _lane(symbol: str) -> str:
    """`hypothesis`, `event` or `unclassified` -- the two-lane order, by asset class."""
    try:
        from research.universe_policy import lane
        return str(lane(symbol))
    except Exception:
        return "unclassified"


def _family_table() -> dict[str, tuple[str, str, str]]:
    """family -> (mechanism, information_source, execution_style): the axis registry's own."""
    try:
        from research.axis_registry import FAMILY_TABLE
        return dict(FAMILY_TABLE)
    except Exception:
        return {}


def _not_a_family() -> frozenset[str]:
    """Constructors that build a family from a spec rather than being one -- never proposed."""
    try:
        from research.axis_registry import NOT_A_FAMILY
        return frozenset(NOT_A_FAMILY)
    except Exception:
        return frozenset({"generic", "formula", "ensemble", "cross_sectional", "joint_genome"})


def _family_func(name: str):
    """The family's constructor across every population `mt5desk.families` can reach."""
    try:
        from mt5desk.families import get_family_func
        return get_family_func(name)
    except Exception:
        return None


def _compiler():
    """`miner_candidate_compiler`, for its prose readers. None when it cannot be imported."""
    try:
        from research import miner_candidate_compiler as mc
        return mc
    except Exception:
        return None


def _donate(candidates: list[dict], tests_run: int):
    """The ONE donation door: it stamps point-in-time or refuses, and it is not re-implemented."""
    from research.proposer_common import donate
    return donate(SEAT, candidates, tests_run)


def mechanism_families() -> dict[str, list[str]]:
    """mechanism -> the PRICE-ONLY, constructible families that implement it: the axis registry's
    FAMILY_TABLE inverted. It is the desk's only hand-written statement of which family means
    which mechanism, and a second table here is how two organs come to disagree."""
    out: dict[str, list[str]] = {}
    spec = _not_a_family()
    for fam, (mech, info, _style) in _family_table().items():
        if info == "price_only" and mech != "UNKNOWN" and fam not in spec \
                and _family_func(fam) is not None:
            out.setdefault(mech, []).append(fam)
    return {mech: sorted(set(fams)) for mech, fams in out.items()}


#: `mechanism_ontology` contract ids -> the desk's own mechanism token. Three, not thirty: only
#: the contracts whose economics the desk has a price-only family for. An id absent here is not
#: guessed -- it falls through to the family-name and prose paths, and is counted if both miss.
ONTOLOGY_ALIAS = {"CROSS_SECTIONAL_MOMENTUM": "trend_persistence",
                  "ORDER_FLOW_IMBALANCE": "execution_microstructure",
                  "FORCED_LIQUIDATION": "forced_liquidation"}


# ====================================================================================== intake
def leads_of(row: dict, seat: str) -> list[Any]:
    """The row's claims as leads -- or ONE STUB so a non-evidence row is refused on the record.
    Empty only when `lead_schema` is unreachable, which the report states as
    `lead_schema_available: false` rather than as an hour that found nothing (L1.28a)."""
    schema = _schema()
    if schema is None:
        return []
    try:
        leads = list(schema.leads_from_intelligence_row(row, seat=seat))
    except Exception:
        leads = []
    return leads or [_stub_lead(schema, row, seat)]


def lead_rows(now: datetime) -> Iterator[tuple[dict, str]]:
    """(row, seat) over every lead source: the frontier queue first, then the seats.

    LAZY BY CONSTRUCTION, not by taste: 11,258 artifacts sit under `data/intelligence` on this
    box, and materialising them to take 200 leads would read the whole tree every pass on the
    8 GB machine that holds the live terminal. Newest artifact first, so a bound that binds
    defers the OLDEST leads rather than an arbitrary slice."""
    if FRONTIER_QUEUE.exists():
        for row in _read_jsonl(FRONTIER_QUEUE):
            yield row, "frontier_queue"
    cutoff = now - timedelta(days=WINDOW_DAYS)
    dated: list[tuple[float, Path]] = []
    for root in INTEL_ROOTS:
        for p in (root.rglob("*") if root.exists() else ()):
            if not (p.is_file() and p.suffix in (".json", ".jsonl")):
                continue
            try:
                mtime = p.stat().st_mtime
            except OSError:
                continue
            if datetime.fromtimestamp(mtime, tz=UTC) >= cutoff:
                dated.append((mtime, p))
    for _mtime, path in sorted(dated, key=lambda x: x[0], reverse=True):
        rows = _read_jsonl(path) if path.suffix == ".jsonl" else _rows_of(_read_json(path))
        for row in rows:
            yield row, path.parent.name


def intake(now: datetime, max_leads: int, processed: set[str]) -> tuple[list[Any], int]:
    """Leads the cursor has not seen, newest source first. Returns (leads, skipped_by_cursor)."""
    leads: list[Any] = []
    seen_ids: set[str] = set()
    skipped = 0
    for row, seat in lead_rows(now):
        for lead in leads_of(row, seat):
            if lead.lead_id in seen_ids:
                continue
            seen_ids.add(lead.lead_id)
            if lead.lead_id in processed:
                skipped += 1
            else:
                leads.append(lead)
                if len(leads) >= max_leads:
                    return leads, skipped
    return leads, skipped


# ====================================================================================== triage
def _declared_symbols(lead: Any, universe: set[str]) -> list[str]:
    """Instruments the lead DECLARES that the desk can price. Exact codes, case-folded."""
    folded = {u.upper(): u for u in universe}
    out: list[str] = []
    for value in lead.instruments:
        hit = folded.get(str(value).upper().replace("/", "").replace("-", "").strip())
        if hit is not None and hit not in out:
            out.append(hit)
    return out


def _prose_symbols(text: str, universe: set[str]) -> list[str]:
    """What the claim's own words name, read with the COMPILER's reader so the two lanes agree."""
    mc = _compiler()
    if mc is None:
        return []
    try:
        return list(mc.text_symbols(text.lower()[:MAX_TEXT_CHARS], universe))
    except Exception:
        return []


def _prose_families(text: str) -> list[str]:
    mc = _compiler()
    if mc is None:
        return []
    try:
        return [fam for fam, _phrase in mc.text_families(text.lower()[:MAX_TEXT_CHARS])]
    except Exception:
        return []


def declared_family(lead: Any) -> str:
    """The family a seat already resolved for this lead, from its `executable` block."""
    block = getattr(lead, "executable", None)
    fam = block.get("family") if isinstance(block, dict) else None
    return fam.strip() if isinstance(fam, str) else ""


def triage(lead: Any, universe: set[str], seen_cells: set[str],
           seen_claims: set[str]) -> tuple[list[str], str | None]:
    """(symbols the lead may be hunted on, rejection code or None). Never raises."""
    if str(lead.kind).lower() in OPERATIONAL_KINDS:
        return [], "operational_row"
    if not str(lead.claim_text).strip():
        return [], "no_claim_text"
    if lead.dedupe_key() in seen_claims:
        return [], "duplicate_lead"
    symbols = _declared_symbols(lead, universe)
    for s in _prose_symbols(lead.claim_text, universe):
        if s not in symbols:
            symbols.append(s)
    symbols = symbols[:MAX_SYMBOLS_PER_LEAD]
    if not symbols:
        return [], "no_instrument"
    lanes = {s: _lane(s) for s in symbols}
    hunted = [s for s in symbols if lanes[s] == "hypothesis"]
    if not hunted:
        # THE TWO-LANE ORDER, AT THE ANALYST'S DOOR. Trial count is a SHARED cost, so an equity
        # lead refused here lowers the bar every FX and metals cell then has to clear.
        return [], ("event_lane_instrument" if "event" in lanes.values()
                    else "unclassified_instrument")
    fam = declared_family(lead)
    if fam:
        hunted = [s for s in hunted if f"{s.upper()}|{fam}" not in seen_cells]
        if not hunted:
            return [], "duplicate_cell"
    if not (fam or lead.mechanism_ids or _prose_families(lead.claim_text)):
        return [], "no_mechanism"
    return hunted, None


# ================================================================================== structuring
_NUM = r"(\d{1,4}(?:\.\d+)?)"
_LOOKBACK_RE = re.compile(
    rf"(?:look ?back|window|lookback of|over the (?:last|past))\D{{0,12}}{_NUM}", re.I)
_WINDOW_RE = re.compile(rf"{_NUM}\s*[- ]?\s*(?:bar|bars|period|periods|day|days|hour|hours)\b",
                        re.I)
_HOLD_RE = re.compile(rf"(?:hold|held|hold for|exit after|ttl|holding period)\D{{0,14}}{_NUM}",
                      re.I)
_Z_RE = re.compile(rf"{_NUM}\s*(?:sigma|standard deviations?|std|z[- ]scores?)", re.I)
_PCT_RE = re.compile(rf"{_NUM}\s*(?:%|percent|pct)", re.I)

#: Parsed number -> the family parameter names that could hold it, in preference order. Only a
#: name the family's OWN signature carries is ever set: a parameter the analyst invented is
#: filtered out downstream and the family then runs on its defaults, so the docket would carry a
#: cell labelled with the claim's number and tested without it -- a different hypothesis.
PARAM_SLOTS: dict[str, tuple[str, ...]] = {
    "window": ("lookback", "vol_lookback", "range_n", "squeeze_lookback", "bb_n", "rsi_n",
               "trend_ema", "atr_n"),
    "hold": ("hold_bars", "ttl_bars"),
    "z": ("entry_z", "bb_k", "gap_atr", "stop_atr"),
    "pct": ("threshold_pct", "vol_mult"),
}


def parse_claim_numbers(text: str) -> dict[str, Any]:
    """The windows, holds, thresholds and session the claim states IN ITS OWN TEXT. Nothing is
    invented: a key is absent when the claim did not say it, and the family then runs on its own
    defaults -- not on a number the analyst picked and attributed to the source."""
    out: dict[str, Any] = {}
    low = str(text).lower()[:MAX_TEXT_CHARS]
    for rx, key, cast in ((_LOOKBACK_RE, "window", int), (_WINDOW_RE, "window", int),
                          (_HOLD_RE, "hold", int), (_Z_RE, "z", float), (_PCT_RE, "pct", float)):
        m = rx.search(low)
        if m is None or key in out:
            continue
        try:
            value = cast(float(m.group(1)))
        except (TypeError, ValueError):
            continue
        if cast is not int or 1 <= value <= 1000:
            out[key] = value
    mc = _compiler()
    if mc is not None:
        try:
            session = mc.text_session(low)
        except Exception:
            session = None
        if session:
            out["session"] = session
    return out


def family_params(family: str, parsed: dict[str, Any], text: str) -> dict[str, Any] | None:
    """The family's parameters as far as the claim names them, or None when it needs more.

    The compiler's `_text_params` owns the families whose cell is meaningless without a stated
    field (a session for `session_range_breakout`, a month for `calendar_month`) and is reused
    rather than re-derived, so the two lanes mint the same cell."""
    params: dict[str, Any] = {}
    mc = _compiler()
    if mc is not None:
        try:
            base = mc._text_params(family, str(text).lower()[:MAX_TEXT_CHARS])
        except Exception:
            base = {}
        if base is None:
            return None
        params.update(base)
    fn = _family_func(family)
    if fn is None:
        return params
    try:
        from inspect import signature
        accepted = set(signature(fn).parameters)
    except (TypeError, ValueError):
        return params
    for key, slots in PARAM_SLOTS.items():
        if key in parsed:
            for name in slots:
                if name in accepted and name not in params:
                    params[name] = parsed[key]
                    break
    return params


def admissible_family(name: Any) -> str | None:
    """A registered, constructible, PRICE-ONLY family name, or None. Price-only because the
    pre-screen has bars and nothing else: a family needing a swap table or a peer series would
    run on its defaults and be judged as if the claim had been tested."""
    fam = name.strip() if isinstance(name, str) else ""
    row = _family_table().get(fam) if fam else None
    if row is None or row[1] != "price_only" or fam in _not_a_family():
        return None
    return fam if _family_func(fam) is not None else None


def structure(lead: Any, symbols: list[str],
              seen_cells: set[str]) -> tuple[list[dict], str | None]:
    """(cells, rejection code). A cell is {symbol, family, params, mechanism, why, parsed}."""
    families: list[str] = []
    why = ""
    declared = declared_family(lead)
    if declared:
        # THE SEAT ALREADY DID THE ANALYST'S WORK. Re-deriving a family from prose that already
        # states one discards the seat's reading and pays for a second answer to a settled thing.
        fam = admissible_family(declared)
        if fam is None:
            return [], ("family_not_registered" if _family_func(declared) is None
                        else "family_not_price_only")
        families, why = [fam], f"the lead declares the registered family {fam} outright"
    if not families:
        table = mechanism_families()
        spec = lead.structured if isinstance(getattr(lead, "structured", None), dict) else {}
        hints = [*lead.mechanism_ids, spec.get("mechanism")]
        for raw in [h for h in hints if isinstance(h, str) and h.strip()]:
            token = raw.strip().lower().replace("-", "_").replace(" ", "_")
            hit = admissible_family(token)
            if hit is not None:                     # the tag IS a family name (`volume_spike`)
                families.append(hit)
                why = f"the lead's mechanism tag names the family {hit}"
                continue
            mech = ONTOLOGY_ALIAS.get(raw.strip().upper(), token)
            if mech in table:
                families.extend(table[mech][:MAX_FAMILIES_PER_LEAD])
                why = f"mechanism {mech} -> the families the axis registry says implement it"
    for fam in (_prose_families(lead.claim_text) if not families else ()):
        hit = admissible_family(fam)
        if hit is not None:
            families.append(hit)
            why = f"the claim's prose names {hit}"
    families = list(dict.fromkeys(families))[:MAX_FAMILIES_PER_LEAD]
    if not families:
        return [], "no_family_for_mechanism"
    parsed = parse_claim_numbers(lead.claim_text)
    table = _family_table()
    block = lead.executable if isinstance(getattr(lead, "executable", None), dict) else {}
    seat_params = block.get("params") if isinstance(block.get("params"), dict) else {}
    cells: list[dict] = []
    needed_more = False
    for fam in families:
        params = family_params(fam, parsed, lead.claim_text)
        if params is None:
            needed_more = True
            continue
        if fam == declared and seat_params:
            params = {**params, **seat_params}      # the seat's own numbers win over the parse
        cells.extend({"symbol": sym, "family": fam, "params": dict(params), "why": why,
                      "mechanism": table.get(fam, ("UNKNOWN", "", ""))[0], "parsed": dict(parsed)}
                     for sym in symbols if f"{sym.upper()}|{fam}" not in seen_cells)
    if not cells:
        return [], ("no_params_from_claim" if needed_more else "duplicate_cell")
    return cells, None


# =================================================================================== pre-screen
def prescreen(cell: dict) -> tuple[bool, str | None, int]:
    """Run the family's OWN signal function over the desk's bars and count what it fires.

    NOT THE SCREEN AND NOT THE GAUNTLET: it asks only whether the cell exists as a series of
    trades at all. A cell that fires eleven times in seven years is an anecdote, and a gauntlet
    slot spent on it charges every other candidate in the campaign for the privilege."""
    df = bars(cell["symbol"])
    if df is None or len(df) < 200:
        return False, "no_bars", 0
    fn = _family_func(cell["family"])
    if fn is None:
        return False, "signal_error", 0
    try:
        signals = fn(df, **cell["params"])
    except Exception:
        # A family that cannot run on its own bars with the claim's parameters has not refuted
        # the claim; it is a measured fact about this cell, and it is counted as one.
        return False, "signal_error", 0
    n = len(signals) if isinstance(signals, (list, tuple)) else 0
    return (n >= MIN_TRADES), (None if n >= MIN_TRADES else "too_few_trades"), n


# ===================================================================================== donation
def to_candidate(lead: Any, cell: dict, n_signals: int) -> dict:
    """The discovery-contract row: `kind: "hypothesis"` so the compiler admits it as
    STRUCTURED_HYPOTHESIS, with the lead id in `lineage` so follow-up can find it again."""
    return {
        "kind": "hypothesis", "source": f"{SEAT}:{lead.kind}", "family": cell["family"],
        "symbol": cell["symbol"], "symbols": [cell["symbol"]], "params": dict(cell["params"]),
        "timeframe": "H1", "mechanism": cell["mechanism"], "why": cell["why"],
        "title": f"{SEAT}:{lead.kind} {cell['family']} {cell['symbol']}",
        "url": str(getattr(lead, "url_or_ref", "") or ""),
        "lineage": {"lead_id": lead.lead_id, "lead_kind": lead.kind, "stage": SEAT,
                    "source_id": str(getattr(lead, "source_id", "") or ""),
                    "dedupe_key": lead.dedupe_key(), "parsed_from_claim": cell.get("parsed", {})},
        "evidence": {"prescreen_signals": n_signals, "min_trades": MIN_TRADES,
                     "claim": str(lead.claim_text)[:400],
                     "screen": "the family's own signal function over the desk's H1 bars; a "
                               "count of firings, not a return -- the ten gates judge"},
    }


# ==================================================================================== follow-up
def _at(value: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo is not None else t.replace(tzinfo=UTC)


def followup(ledger_rows: list[dict]) -> tuple[dict[str, dict[str, int]], bool]:
    """Later runs' gate verdicts, joined back to the lead that produced the cell.

    The join is (symbol, family) at or after the donation -- the identity the gate ledger
    publishes -- and deliberately not the param hash: the docket re-parameterises a cell between
    proposal and judgement, so an exact-param join would report zero forever, and call that a
    measurement."""
    readable = GATE_LEDGER.exists()
    index: dict[str, list[dict]] = {}
    for row in (_read_jsonl(GATE_LEDGER) if readable else []):
        index.setdefault(f"{str(row.get('sym') or '').upper()}|{row.get('family')}",
                         []).append(row)
    by_kind: dict[str, dict[str, int]] = {}
    for row in ledger_rows:
        if row.get("stage") != "donation" or row.get("outcome") != "donated":
            continue
        bucket = by_kind.setdefault(str(row.get("lead_kind") or "unknown"),
                                    {"donated": 0, "judged": 0, "certified": 0})
        bucket["donated"] += 1
        donated_at = _at(row.get("at"))
        later = [v for v in index.get(
            f"{str(row.get('symbol') or '').upper()}|{row.get('family')}", [])
            if donated_at is None or (_at(v.get("at")) or donated_at) >= donated_at]
        if later:
            bucket["judged"] += 1
            if any(bool(v.get("passed")) or v.get("terminal_gate") == "PASSED" for v in later):
                bucket["certified"] += 1
    return by_kind, readable


# ======================================================================================== state
def read_cursor() -> dict[str, Any]:
    doc = _read_json(CURSOR)
    doc = doc if isinstance(doc, dict) else {}
    doc.setdefault("processed", [])
    doc.setdefault("claim_keys", [])
    return doc


def write_cursor(cursor: dict[str, Any], new_ids: Iterable[str],
                 new_claims: Iterable[str]) -> None:
    processed = list(dict.fromkeys(list(cursor.get("processed", [])) + list(new_ids)))
    claims = list(dict.fromkeys(list(cursor.get("claim_keys", [])) + list(new_claims)))
    _atomic_json(CURSOR, {"at": datetime.now(tz=UTC).isoformat(),
                          "processed": processed[-MAX_CURSOR_IDS:],
                          "claim_keys": claims[-MAX_CURSOR_IDS:], "n_processed": len(processed),
                          "rule": "a lead the pipeline has already worked is never re-worked"})


def append_ledger(rows: list[dict]) -> None:
    if not rows:
        return
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, default=str) + "\n")


def graph_cells() -> tuple[set[str], bool]:
    """`SYMBOL|family` for every cell the hypothesis graph already carries."""
    if not GRAPH.exists():
        return set(), False
    return ({f"{str(r.get('symbol') or '').upper()}|{r.get('family')}"
             for r in _read_jsonl(GRAPH) if r.get("family")}, True)


# ========================================================================================== run
def run(max_leads: int = MAX_LEADS, budget_s: float = BUDGET_S,
        dry_run: bool = False) -> dict[str, Any]:
    """One pass: intake, triage, structure, pre-screen, donate, then measure the whole funnel."""
    started = time.monotonic()
    now = datetime.now(tz=UTC)
    cursor = read_cursor()
    seen_claims = set(cursor.get("claim_keys", []))
    universe = known_symbols()
    seen_cells, graph_read = graph_cells()
    leads, skipped = intake(now, max_leads, set(cursor.get("processed", [])))

    rejects: dict[str, dict[str, int]] = {"triage": {}, "structuring": {}, "prescreen": {}}
    passed = {"triage": 0, "structuring": 0, "prescreen": 0}
    ledger: list[dict] = []
    candidates: list[dict] = []
    worked: list[str] = []
    claim_keys: list[str] = []
    deferred = 0
    stopped_on_budget = False

    def _row(lead: Any, stage: str, outcome: str, **extra: Any) -> dict:
        return {"at": now.isoformat(), "lead_id": lead.lead_id, "lead_kind": lead.kind,
                "stage": stage, "outcome": outcome, **extra}

    def _reject(lead: Any, stage: str, code: str, **extra: Any) -> None:
        rejects[stage][code] = rejects[stage].get(code, 0) + 1
        ledger.append(_row(lead, stage, "rejected", reason=code, **extra))

    for i, lead in enumerate(leads):
        if time.monotonic() - started > budget_s:
            # TIME-BOXED, AND THE REMAINDER IS NOT MARKED DONE. A lead the budget cut off is
            # deferred to the next pass, never written into the cursor as though it was worked.
            deferred, stopped_on_budget = len(leads) - i, True
            break
        worked.append(lead.lead_id)
        claim_keys.append(lead.dedupe_key())
        symbols, code = triage(lead, universe, seen_cells, seen_claims)
        if code is not None:
            _reject(lead, "triage", code)
            continue
        passed["triage"] += 1
        cells, code = structure(lead, symbols, seen_cells)
        if code is not None:
            _reject(lead, "structuring", code)
            continue
        passed["structuring"] += 1
        ledger.append(_row(lead, "structuring", "structured", cells=len(cells),
                           families=sorted({c["family"] for c in cells})))
        donated_any = False
        for cell in cells:
            if time.monotonic() - started > budget_s:
                _reject(lead, "prescreen", "budget_exhausted", symbol=cell["symbol"],
                        family=cell["family"])
                stopped_on_budget = True
                break
            ok, code, n = prescreen(cell)
            if not ok:
                _reject(lead, "prescreen", code or "signal_error", symbol=cell["symbol"],
                        family=cell["family"], signals=n)
                continue
            passed["prescreen"] += 1
            seen_cells.add(f"{cell['symbol'].upper()}|{cell['family']}")
            candidates.append(to_candidate(lead, cell, n))
            donated_any = True
            ledger.append(_row(lead, "donation", "donated", symbol=cell["symbol"],
                               family=cell["family"], params=cell["params"], signals=n))
        if not donated_any:
            ledger.append(_row(lead, "donation", "nothing_survived_prescreen"))

    donated_path = None
    if candidates and not dry_run:
        try:
            donated_path = _donate(candidates, tests_run=passed["prescreen"])
        except Exception as exc:
            # THE DOOR REFUSED, SO NOTHING WAS DONATED, and the ledger must not say otherwise --
            # a donation row the intake never accepted is a certificate of a phantom.
            ledger = [r for r in ledger if r.get("stage") != "donation"]
            candidates = []
            ledger.append({"at": now.isoformat(), "stage": "donation", "outcome": "refused",
                           "reason": f"{type(exc).__name__}: {exc}"})

    if not dry_run:
        append_ledger(ledger)
        write_cursor(cursor, worked, claim_keys)
    history = (_read_jsonl(LEDGER) if LEDGER.exists() else []) + (ledger if dry_run else [])
    by_kind, gate_read = followup(history)
    totals = {k: sum(b[k] for b in by_kind.values()) for k in ("donated", "judged", "certified")}
    report = {
        "at": now.isoformat(),
        "intake": len(leads),
        "triage": {"passed": passed["triage"],
                   "rejected_by_reason": dict(sorted(rejects["triage"].items()))},
        "structured": passed["structuring"],
        "structuring_rejected_by_reason": dict(sorted(rejects["structuring"].items())),
        "prescreened": {"passed": passed["prescreen"],
                        "rejected_by_reason": dict(sorted(rejects["prescreen"].items()))},
        "donated": len(candidates),
        "followup": {"by_lead_kind": {k: by_kind[k] for k in sorted(by_kind)}},
        "conversion": {
            "intake_to_donated": round(len(candidates) / len(leads), 6) if leads else None,
            # UNMEASURED UNTIL SOMETHING HAS BEEN JUDGED (L1.28a). Five donations and no verdict
            # yet is not a 0% certification rate -- it is a rate nobody has measured, and a
            # printed 0.0 reads as a dead lane to every organ downstream.
            "donated_to_certified": (round(totals["certified"] / totals["donated"], 6)
                                     if totals["donated"] and totals["judged"] else None)},
        "unmeasured": {
            "leads_skipped_by_cursor": skipped, "leads_deferred_by_budget": deferred,
            "stopped_on_budget": stopped_on_budget, "lead_schema_available": _schema() is not None,
            "hypothesis_graph_read": graph_read, "gate_ledger_read": gate_read,
            "donations_awaiting_a_verdict": max(totals["donated"] - totals["judged"], 0),
            "note": ("a lead the budget deferred is not a rejection and is not in the cursor; a "
                     "donation with no verdict yet is UNMEASURED, never a failure")},
        "dry_run": bool(dry_run),
        "donation_path": str(donated_path) if donated_path else None,
        "elapsed_s": round(time.monotonic() - started, 3),
        "rule": RULE,
    }
    if not dry_run:
        _atomic_json(OUT_REPORT, report)
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="the analyst pipeline: leads -> testable hypotheses")
    ap.add_argument("--dry-run", action="store_true",
                    help="measure and print; write no artifact, no ledger, no donation")
    ap.add_argument("--max-leads", type=int, default=MAX_LEADS)
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    args = ap.parse_args(argv)
    print(json.dumps(run(max_leads=max(1, args.max_leads), budget_s=max(1.0, args.budget_s),
                         dry_run=bool(args.dry_run)), indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
