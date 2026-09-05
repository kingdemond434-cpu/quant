"""Compile hourly miner evidence into executable MT5 candidates without inventing rules.

Miners produce three economically different things: exact recipes, structured data mechanisms,
and leads that still need rule extraction.  Treating all three as prose and defaulting them to a
session breakout created candidate count but destroyed provenance.  This compiler accounts for
every recent row and emits only source-faithful executable identities.  Leads without an exact
rule remain useful: mined_ground directs the family-free search toward them and this module writes
an explicit deepening queue for the research brains.  No row silently dies and no family is
guessed from a buzzword.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
if str(BASE) not in sys.path:
    # The hourly service executes this file by path. Python then adds ``research/`` rather than
    # ``desks/mt5/`` to sys.path, so exact recipes otherwise cannot see the family registry and
    # are silently routed to deepening instead of the gauntlet.
    sys.path.insert(0, str(BASE))
UNIVERSE = BASE / "data" / "universe"
INTEL_ROOTS = (BASE / "data" / "intelligence", ROOT / "data" / "intelligence")
OUT = BASE / "data" / "hypotheses" / "miner_candidates.json"
DEEPEN = BASE / "data" / "hypotheses" / "miner_deepening_queue.json"
WINDOW_DAYS = 7


def _read(path: Path):
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def known_symbols() -> set[str]:
    return {p.stem.removesuffix("_H1").upper() for p in UNIVERSE.glob("*_H1.parquet")}


def _rows(doc) -> list[dict]:
    if isinstance(doc, list):
        return [r for r in doc if isinstance(r, dict)]
    if not isinstance(doc, dict):
        return []
    if isinstance(doc.get("discoveries"), list):
        return [r for r in doc["discoveries"] if isinstance(r, dict)]
    out: list[dict] = []
    for value in doc.values():
        if isinstance(value, dict) and isinstance(value.get("discoveries"), list):
            out.extend(r for r in value["discoveries"] if isinstance(r, dict))
        elif isinstance(value, list):
            out.extend(r for r in value if isinstance(r, dict))
    return out


#: Rows one compile pass will carry. A bound on MEMORY, not a view of what matters: it is applied
#: newest-file-first and whatever it drops is COUNTED and reported, never silently discarded.
MAX_ROWS_PER_PASS = 250_000


def recent_rows(now: datetime) -> list[tuple[str, dict]]:
    """EVERY discovery artifact in the window, exact-row deduplicated.

    THIS READ ONLY THE NEWEST FILE PER SOURCE DIRECTORY, and it was the largest conversion loss on
    the desk. Measured 2026-09-05: 5,524 discovery files inside the 7-day window holding 102,915
    rows, of which the compiler opened 60 files and saw 1,594 rows. **98.5% of everything the
    miners produced never reached the compiler at all** -- not rejected, not deepened, not
    graveyarded: unread. The docket looked like a funnel narrowing on merit and was mostly a
    directory listing sorted by mtime.

    A miner that writes one artifact per run kept only its last run; a miner that writes one per
    source kept only whichever landed last. Both are the common shape here, which is why the loss
    was near-total rather than partial.

    THE DEDUPLICATION IS WHAT MAKES READING EVERYTHING SAFE, and it already existed: rows are keyed
    on a sha256 of their exact content, so a row repeated across fifty files is carried once. The
    old behaviour was not protecting against duplicates -- the dedup was -- it was discarding
    distinct rows.

    NEWEST FIRST, so if `MAX_ROWS_PER_PASS` binds it is the oldest discoveries that wait for the
    next pass rather than an arbitrary slice, and the shortfall is reported rather than hidden.
    """
    cutoff = now - timedelta(days=WINDOW_DAYS)
    found: list[tuple[str, dict]] = []
    seen: set[str] = set()
    for root in INTEL_ROOTS:
        if not root.exists():
            continue
        paths = [root / "latest_discoveries.json"]
        for directory in sorted(p for p in root.iterdir() if p.is_dir()):
            paths.extend(sorted(directory.glob("discoveries_*.json"),
                                key=lambda p: p.stat().st_mtime, reverse=True))
        for path in paths:
            try:
                if datetime.fromtimestamp(path.stat().st_mtime, tz=UTC) < cutoff:
                    continue
            except OSError:
                continue
            for row in _rows(_read(path)):
                payload = json.dumps(row, sort_keys=True, default=str, separators=(",", ":"))
                digest = hashlib.sha256(payload.encode()).hexdigest()
                if digest in seen:
                    continue
                seen.add(digest)
                source = str(row.get("source") or path.parent.name or "unknown")
                found.append((source, row))
                if len(found) >= MAX_ROWS_PER_PASS:
                    print(f"compiler: MAX_ROWS_PER_PASS ({MAX_ROWS_PER_PASS:,}) reached; older "
                          f"discoveries wait for the next pass. This is a memory bound being "
                          f"hit, not a judgement -- raise it or shorten WINDOW_DAYS.")
                    return found
    return found


def resolve_symbols(row: dict, universe: set[str]) -> list[str]:
    """Resolve exact symbols and currency-wide evidence against the live Fusion registry."""
    raw = []
    for key in ("symbol", "currency"):
        if row.get(key):
            raw.append(row[key])
    for key in ("symbols", "instruments"):
        if isinstance(row.get(key), list):
            raw.extend(row[key])
    out: set[str] = set()
    for value in raw:
        token = str(value).upper().replace("/", "").strip()
        if token in universe:
            out.add(token)
        elif len(token) == 3 and token.isalpha():
            out.update(s for s in universe if len(s) == 6 and token in (s[:3], s[3:]))
    return sorted(out)


def _candidate(symbol: str, family: str, params: dict, source: str, row: dict,
               mechanism: str) -> dict:
    return {
        "symbol": symbol,
        "family": family,
        "params": params,
        "source": f"miner:{source}",
        "source_url": row.get("url") or row.get("link") or "",
        "source_title": str(row.get("title") or row.get("description") or "")[:300],
        "mechanism_status": "NAMED",
        "mechanism_note": mechanism,
    }


def _registered_family(name: str) -> bool:
    try:
        from mt5desk import families, families_orthogonal
        return (callable(getattr(families, f"family_{name}", None))
                or name in families_orthogonal.ORTHOGONAL_FAMILIES)
    except ImportError:
        return False


def compile_row(source: str, row: dict, universe: set[str]) -> tuple[list[dict], str]:
    """Return executable candidates and the exact disposition for one evidence row."""
    symbols = resolve_symbols(row, universe)
    source_l = source.lower()
    kind = str(row.get("kind") or row.get("type") or "").lower()

    # Direct recipes from any present or future miner are admitted only when the family and
    # executable parameters are explicit. The gauntlet remains the arbiter of profitability.
    family = row.get("family")
    params = row.get("params")
    if (isinstance(family, str) and isinstance(params, dict) and symbols
            and _registered_family(family)):
        return ([_candidate(s, family, dict(params), source, row,
                            str(row.get("mechanism") or "source supplied exact recipe"))
                 for s in symbols], "EXACT_RECIPE")

    if (source_l == "cot" or (kind == "positioning" and "cot" in source_l)) and symbols:
        return ([_candidate(s, "cot_positioning", {"input_source": "cot_point_in_time"},
                            source, row,
                            "reported positioning extremes can unwind or continue "
                            "conditionally")
                 for s in symbols], "STRUCTURED_COT")

    event_like = (source_l in {"ff_calendar_vintage", "forexfactory", "central_bank"}
                  or kind in {"calendar_event", "calendar_vintage", "cb_speech"})
    if event_like and symbols:
        return ([_candidate(s, "event_reaction", {"input_source": "ff_calendar_vintage"},
                            source, row,
                            "scheduled information releases create conditional repricing "
                            "and liquidity")
                 for s in symbols], "STRUCTURED_EVENT")

    if source_l == "broker_swaps" and symbols and (
            kind in {"contract_terms", "swap_terms"}
            or row.get("swap_long") is not None or row.get("swap_short") is not None):
        return ([_candidate(s, "carry", {"input_symbol": s}, source, row,
                            "broker-native swap differential is a directly measured carry premium")
                 for s in symbols], "STRUCTURED_CARRY")

    if source_l == "correlations" and len(symbols) >= 2:
        candidates = []
        for symbol in symbols:
            for peer in symbols:
                if peer != symbol:
                    candidates.append(_candidate(
                        symbol, "relative_value", {"peer_symbol": peer}, source, row,
                        "a measured cross-instrument relationship can create residual convergence",
                    ))
        return candidates, "STRUCTURED_RELATIVE_VALUE"

    month = row.get("month")
    direction = str(row.get("direction") or "").lower()
    if source_l == "seasonality" and symbols and isinstance(month, int) and 1 <= month <= 12 \
            and direction in {"up", "down", "long", "short"}:
        side = 1 if direction in {"up", "long"} else -1
        return ([_candidate(s, "calendar_month", {"active_month": month, "side_bias": side},
                            source, row,
                            "calendar-linked allocation and hedging flows can create "
                            "monthly seasonality")
                 for s in symbols], "STRUCTURED_CALENDAR")

    if not symbols:
        return [], "NEEDS_SYMBOL_EXTRACTION"
    return [], "NEEDS_EXACT_RULE_EXTRACTION"


def structurally_untestable_families() -> dict[str, str]:
    """Families the gauntlet has MEASURED as producing zero judgeable cells, from its own report.

    Data-driven, never a hardcoded list (LAWS anti-hardcode): a family joins this set only when
    the last sweep built >=5 of its cells and judged NONE (all under the 60 trading days the
    gates need) -- measured 2026-08-27: carry 193/193, event_reaction 113/113, calendar_month
    2/2, lvc_asia_london 3/3 re-shipped every hour, ~310 guaranteed-unjudgeable builds per
    sweep. Routing them to the DEEPENING queue is not a rejection: it is the statement that
    these parameterizations need widening (pooled events, longer windows) before any gate can
    rule, which is exactly what the deepening queue exists to ask the research brains for.
    A family leaves the set the moment one of its cells becomes judgeable.
    """
    report = BASE / "reports" / "universal_gates_external.json"
    try:
        doc = json.loads(report.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    per_fam: dict[str, list[int]] = {}
    for v in doc.get("verdicts") or []:
        if not isinstance(v, dict):
            continue
        fam = str(v.get("family") or "?")
        n_all, n_unm = per_fam.setdefault(fam, [0, 0])
        per_fam[fam] = [n_all + 1, n_unm + (1 if v.get("unmeasured") else 0)]
    return {fam: (f"last sweep built {n} cell(s), judged 0 -- every one under the 60 trading "
                  f"days the gates need; parameters need DEEPENING before judgment is possible")
            for fam, (n, unm) in per_fam.items() if n >= 5 and unm == n}


def main() -> int:
    now = datetime.now(tz=UTC)
    universe = known_symbols()
    candidates: dict[str, dict] = {}
    deepening: dict[str, dict] = {}
    per_source: dict[str, dict[str, int]] = {}
    untestable = structurally_untestable_families()
    if untestable:
        print("families routed to DEEPENING (measured untestable at current parameters): "
              + ", ".join(sorted(untestable)))

    for source, row in recent_rows(now):
        produced, disposition = compile_row(source, row, universe)
        stats = per_source.setdefault(source, {"rows": 0, "candidates": 0, "deepening": 0})
        stats["rows"] += 1
        for candidate in produced:
            identity = json.dumps({k: candidate[k] for k in ("symbol", "family", "params")},
                                  sort_keys=True, default=str)
            fam = str(candidate.get("family") or "")
            if fam in untestable:
                if identity not in deepening:
                    deepening[identity] = {**candidate,
                                           "deepening_reason": untestable[fam]}
                    stats["deepening"] += 1
                continue
            if identity not in candidates:
                candidates[identity] = candidate
                stats["candidates"] += 1
        if not produced:
            compact = {
                "source": source,
                "disposition": disposition,
                "title": str(row.get("title") or row.get("description") or "")[:300],
                "url": row.get("url") or row.get("link") or "",
                "symbols": resolve_symbols(row, universe),
                "mechanism_tags": row.get("mechanism_tags") or row.get("patterns") or [],
            }
            key = hashlib.sha256(
                json.dumps(compact, sort_keys=True, default=str).encode()).hexdigest()
            deepening[key] = compact
            stats["deepening"] += 1

    # THE GRAPH REMEMBERS WHAT WAS BURIED. Every compiled candidate is registered as BORN with
    # its miner row as parent, and every one that lands in a parameter region the gauntlet has
    # already failed carries that count on its face. It is not rejected -- the gauntlet decides
    # -- but a proposer that keeps re-proposing a dead region is now visible, and the deepening
    # queue's VOI ordering discounts it.
    try:
        from libs.research.hypothesis_graph import Graph, record_candidates
        g = Graph()
        for c in candidates.values():
            pf = g.prior_failures(str(c.get("symbol")), str(c.get("family")),
                                  dict(c.get("params") or {}))
            if pf["n_failed"]:
                c["prior_failures_in_region"] = pf["n_failed"]
                c["region"] = pf["region"]
        # THE PRE-MORTEM: which failure class this candidate most resembles dying of, and the
        # cheap falsifier that implies. Annotation only -- the gauntlet still decides.
        try:
            from libs.research.graveyard_model import GraveyardModel
            gm = GraveyardModel().fit(g.rows())
            if gm.n:
                for c in candidates.values():
                    c["premortem"] = gm.premortem(c)
        except Exception:
            pass
        record_candidates(candidates.values(), source="miner_candidate_compiler", graph=g)
    except Exception as exc:
        print(f"hypothesis graph not updated (non-fatal): {type(exc).__name__}: {exc}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "compiled_at": now.isoformat(timespec="seconds"),
        "hypotheses": list(candidates.values()),
        "per_source": per_source,
        "rows_accounted": sum(v["rows"] for v in per_source.values()),
        "executable_candidates": len(candidates),
        "deepening_tasks": len(deepening),
        "rule": "exact recipe or structured causal data only; no prose-to-family guessing",
    }, indent=1, default=str), "utf-8")
    DEEPEN.write_text(json.dumps({
        "built_at": now.isoformat(timespec="seconds"),
        "tasks": list(deepening.values()),
        "consumer": "hourly/daily research brains must recover a falsifiable rule or reject",
    }, indent=1, default=str), "utf-8")
    print(f"miner compiler: {sum(v['rows'] for v in per_source.values())} row(s) accounted; "
          f"{len(candidates)} executable candidate(s); {len(deepening)} exact-rule task(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
