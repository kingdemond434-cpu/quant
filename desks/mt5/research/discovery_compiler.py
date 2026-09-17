"""THE UNIVERSAL DISCOVERY-TO-CELL COMPILER -- nothing the desk finds may die of neglect.

THE PRINCIPAL'S RULE, 2026-09-17 (ledger item M7). No miner row, research finding, failure,
external lead, moat artifact, unexplained residual or discovered mechanism may exist without an
explicit machine disposition into gauntlet-testable cells, or a recorded reason why conversion is
impossible. UNPROCESSED -> INTERPRETED -> EXPANDED -> COMPILED -> QUEUED -> TESTED, or
BLOCKED(reason). NEVER SILENTLY DROPPED.

WHAT THAT RULE IS ABOUT, because it reads like bookkeeping and is not. This desk's failure has
never been finding things. It is that a thing found on Tuesday is a JSON file by Thursday and a
directory nobody reads by the following month: 90 seat directories under `data/intelligence/`,
8,872 anomalies in one file, a frontier queue, a graveyard, a residual queue, standing questions
-- all of it real work, none of it joined to the docket the gauntlet actually judges. The
conversion rate from finding to tested cell was never measured, and an unmeasured conversion rate
COUNTS AS ZERO (sealed core). This organ is the join, and `conversion_debt()` is the number it
exists to drive down.

THE SEVEN STEPS.

  1. INTAKE     every UNPROCESSED registry discovery, PLUS what the registry cannot yet see: seat
                donations, the frontier queue, alpha cards, the graveyard, the residual queue and
                the standing questions. A byte/mtime cursor makes a second run in the same hour
                cost nothing and change nothing.
  2. INTERPRET  claim text and mechanism field -> ONE canonical mechanism id. UNKNOWN is allowed
                and RECORDED: it measures the desk's own vocabulary, and a forced guess would put
                the wrong economics -- and therefore the wrong closure -- on a real find.
  3. CLOSURE    Closure(d) = A x T x S x H x R x M x I under ECONOMIC COMPATIBILITY, enumerated by
                the twelve miners of `transformation_miners`. NOT THE CARTESIAN PRODUCT: a session
                mechanism never gets D1; a month-end flow claim gets the crosses whose legs carry
                the flow and the quarter-end regime, not a random exotic.
  4. GATES      three, in order, each refusing with a NAMED and COUNTED reason -- ECONOMIC (the
                ontology admits the cell), DATA/PIT (bars for symbol x chart, the required data
                resolves, the stamp is knowable), NOVELTY (content hash, grid twin, or the
                novelty gate's redundancy census).
  5. COMPILE    a survivor becomes an EXACT RULE with a registered family, enqueued carrying its
                discovery_id and transformation, and donated so the docket sees it.
  6. TESTED     is NOT set here. The registry bridge sets it when the gauntlet judges; a compiler
                that marked its own output tested would be grading its own homework.
  7. PROVENANCE discovery -> mechanism -> cell, so a survivor traces back to the miner that found
                it and a miner is paid by the independent survivors it produced.

WHY `possible_cells` IS HONEST. It is the size of the closure the twelve miners enumerate, and
every member is either GENERATED this pass or BLOCKED with a named reason -- a gate refusal, a
per-miner compute budget, or the per-discovery cap. So
`unexplained_missing = possible - generated - blocked` reaches ZERO not because the number was
chosen to make it, but because nothing may leave without a disposition. The day a change drops a
child on the floor, that subtraction is where it shows up.

    python desks/mt5/research/discovery_compiler.py --dry-run
    python desks/mt5/research/discovery_compiler.py --budget-s 240 --max-discoveries 200
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import time
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parents[1]
for _p in (str(BASE), str(BASE / "research"), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as R  # noqa: E402
from research import transformation_miners as TM  # noqa: E402

INTEL = BASE / "data" / "intelligence"
FRONTIER_QUEUE = BASE / "frontier_intel" / "data" / "frontier_queue.jsonl"
GRAVEYARD_MD = REPO / "backups" / "moat" / "graveyard"
GRAVEYARD_JSON = BASE / "data" / "graveyard.json"
RESIDUAL_QUEUE = BASE / "reports" / "RESIDUAL_QUEUE.json"
STANDING_QUESTIONS = BASE / "reports" / "STANDING_QUESTIONS.json"
NOVELTY_GATE = BASE / "reports" / "NOVELTY_GATE.json"
UNIVERSE = BASE / "data" / "universe"
AXES = BASE / "data" / "axes"
CURSOR = BASE / "data" / "discovery_compiler_cursor.json"
OUT = BASE / "reports" / "DISCOVERY_COMPILER.json"

SOURCE = "discovery_compiler"
BUDGET_S = 240
MAX_DISCOVERIES = 200
#: Children carried forward per discovery. A COMPUTE BUDGET and it says so: the remainder is
#: counted as blocked with a named reason and is owed, never refused (L1.61).
MAX_CHILDREN = 40
MAX_INTAKE_FILE_BYTES = 32 * 1024 * 1024
MAX_ROWS_PER_FILE = 400

RULE = ("no discovery exists without a disposition; maximum conversion is every economically "
        "defensible transformation, never the cartesian product")


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _write_atomic(path: Path, payload: Any) -> None:
    """Atomic where the filesystem allows it. `os.replace` onto a read-only destination is legal
    on POSIX and raises WinError 5 here -- the way a VPS-tested fix once broke the trading box."""
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, indent=1, default=str)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(body, encoding="utf-8")
    try:
        os.replace(tmp, path)
    except OSError:
        path.write_text(body, encoding="utf-8")


def _read_json(path: Path) -> Any:
    try:
        if not path.exists() or path.stat().st_size > MAX_INTAKE_FILE_BYTES:
            return None
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


#: Keys a donation file hangs its rows off. Read in order; the first list wins.
_ROW_KEYS = ("discoveries", "anomalies", "hypotheses", "candidates", "rows", "items", "leads",
             "claims", "findings")


def rows_of(doc: Any) -> list[dict[str, Any]]:
    """The rows inside an intake document, whatever shape the seat chose.

    Three shapes are live on this box today and all three are read: a bare list (axis_registry's
    donations), `{"source":..., "discoveries":[...]}` (every `proposer_common.donate` writer), and
    `{"anomalies":[...], "trials": n}` (the anomaly scanner). A doc in a fourth shape yields
    nothing and is COUNTED as unreadable rather than assumed empty.
    """
    if isinstance(doc, list):
        return [r for r in doc if isinstance(r, dict)]
    if not isinstance(doc, dict):
        return []
    for key in _ROW_KEYS:
        val = doc.get(key)
        if isinstance(val, list):
            return [r for r in val if isinstance(r, dict)]
        if isinstance(val, dict):
            return [r for r in val.values() if isinstance(r, dict)]
    return [doc] if any(k in doc for k in ("family", "symbol", "mechanism", "claim")) else []


# --------------------------------------------------------------------------- the cursor
def load_cursor(path: Path | None = None) -> dict[str, Any]:
    doc = _read_json(path or CURSOR)
    if not isinstance(doc, dict):
        return {"at": None, "files": {}, "runs": 0}
    doc.setdefault("files", {})
    doc.setdefault("runs", 0)
    return doc


def _fresh(cursor: dict[str, Any], path: Path) -> bool:
    """True when this file has content the last run did not see. Idempotence lives here: a
    second pass in the same hour re-reads nothing and re-records nothing."""
    try:
        st = path.stat()
    except OSError:
        return False
    seen = cursor["files"].get(str(path))
    return not (isinstance(seen, dict) and seen.get("size") == st.st_size
                and seen.get("mtime") == int(st.st_mtime))


def _mark(cursor: dict[str, Any], path: Path, **extra: Any) -> None:
    try:
        st = path.stat()
    except OSError:
        return
    cursor["files"][str(path)] = {"size": st.st_size, "mtime": int(st.st_mtime), "at": _now(),
                                  **extra}


# --------------------------------------------------------------------------- interpret
def interpret(text: str, declared: str = "") -> tuple[str, str]:
    """Claim text -> ONE canonical mechanism id, or UNKNOWN with the reason recorded.

    A DECLARED mechanism wins when it names a contract: the seat that wrote it knew what it meant.
    Otherwise the text is scored against each contract's keywords and the best non-zero score
    wins. UNKNOWN IS A REAL ANSWER (L1.28a): it says the desk's mechanism vocabulary does not yet
    cover this claim, which is a gap worth seeing, and a forced guess would attach the wrong
    economics -- and therefore the wrong closure -- to a real find.
    """
    d = " ".join(str(declared or "").strip().lower().replace("-", "_").split())
    if d in TM.CONTRACTS:
        return d, f"declared: the row names {d} directly"
    blob = f"{declared} {text}".lower()
    best, score = "", 0
    for mid, contract in TM.CONTRACTS.items():
        # A PHRASE OUTWEIGHS A TOKEN, and it has to. "london" appears in half the claims this
        # desk reads and settles nothing; "month end" appears in the ones that are actually about
        # a dated rebalancing obligation. Scoring them equally let the first contract in iteration
        # order win every tie, which is a vocabulary decided by dict order.
        hits = sum(1 + 2 * k.count(" ") for k in contract.keywords if k in blob)
        hits += 3 if mid.replace("_", " ") in blob else 0
        if hits > score:
            best, score = mid, hits
    if not best:
        return TM.UNKNOWN_MECHANISM, ("no contract keyword appears in the claim; UNKNOWN is "
                                      "recorded rather than guessed, and the conservative closure "
                                      "applies")
    return best, f"{score} keyword hit(s) for {best}"


# --------------------------------------------------------------------------- the context
def _macro_states(axes_dir: Path) -> dict[str, list[str]]:
    """Named macro states from `data/axes/*.json`, and NOTHING when the files carry none.

    An axis file with 0 series (fred.json on this box today) contributes no state, and the macro
    miner then records UNMEASURED rather than concluding the mechanism has no macro conditionality.
    """
    out: dict[str, list[str]] = {}
    if not axes_dir.exists():
        return out
    for path in sorted(axes_dir.glob("*.json")):
        doc = _read_json(path)
        if not isinstance(doc, dict):
            continue
        axis = str(doc.get("axis") or path.stem)
        series = doc.get("series")
        if isinstance(series, dict) and series:
            out.setdefault(axis, []).extend(sorted(series)[:4])
            continue
        rows = doc.get("rows")
        if isinstance(rows, list) and rows and isinstance(rows[0], dict):
            numeric = sorted(k for k, v in rows[0].items()
                             if isinstance(v, (int, float)) and not isinstance(v, bool))
            for key in numeric[:2]:
                out.setdefault(axis, []).extend([f"{key}_high", f"{key}_low"])
    return {k: sorted(set(v)) for k, v in out.items() if v}


def _orthogonal_families() -> Iterable[str]:
    from mt5desk import families_orthogonal as fo
    return fo.ORTHOGONAL_FAMILIES


def _hunt16_families() -> Iterable[str]:
    from mt5desk.executables import hunt16_families
    return hunt16_families()


def build_context(*, universe_dir: Path | None = None, axes_dir: Path | None = None,
                  instruments: Mapping[str, list[str]] | None = None,
                  families: Iterable[str] | None = None,
                  defaults: Mapping[str, dict[str, Any]] | None = None,
                  max_per_miner: int = 8) -> TM.Context:
    """ONE context per run: instruments, families, family defaults, contracts, macro states, and
    the two probes (bars on disk, the two-lane verdict). Built once because twelve miners times
    two hundred discoveries is 2,400 chances to reopen the universe registry."""
    uni = universe_dir or UNIVERSE
    inst = dict(instruments) if instruments is not None else {}
    fams: set[str] = set(families or ())
    defs: dict[str, dict[str, Any]] = {k: dict(v) for k, v in (defaults or {}).items()}
    lane_ok = None
    if instruments is None:
        try:
            import axis_registry as ar
            inst = ar.instruments_by_class()
        except Exception:
            inst = {}
    if families is None:
        # ALL THREE POPULATIONS, the way `families.get_family_func` and
        # `executables.resolve_family` resolve them. FAMILY_REGISTRY is only the 27 DECORATED
        # families; the orthogonal set and hunt16 are equally real code the forward engine already
        # runs. Reading the registry alone made a live sleeve read as "no such family" once
        # (2026-09-12) -- absence of a decorator is not absence of an implementation, and here it
        # would have blocked every child whose mechanism only an orthogonal family implements.
        try:
            from mt5desk.families import FAMILY_REGISTRY
            fams = set(FAMILY_REGISTRY)
            defs = {k: dict(v.get("defaults") or {}) for k, v in FAMILY_REGISTRY.items()}
        except Exception:
            fams = set()
        for extra in (_orthogonal_families, _hunt16_families):
            try:
                fams |= set(extra())
            except Exception:
                continue
    try:
        from research.universe_policy import may_hypothesise
        lane_ok = may_hypothesise
    except Exception:
        lane_ok = None
    return TM.Context(
        instruments={k: list(v) for k, v in inst.items()}, families=frozenset(fams), defaults=defs,
        ontology=dict(TM.CONTRACTS), macro_states=_macro_states(axes_dir or AXES),
        bars_available=lambda sym, chart: (uni / f"{sym}_{str(chart).upper()}.parquet").exists(),
        lane_ok=lane_ok, max_per_miner=max_per_miner)


def _family_pool(ctx: TM.Context, mechanism_id: str, information: str) -> list[str]:
    """Registered families that implement (mechanism, information). A child whose mechanism has
    no implemented family is BLOCKED by name -- never quietly assigned a family that would test a
    different claim."""
    try:
        import axis_registry as ar
        table = ar.FAMILY_TABLE
        not_a_family = ar.NOT_A_FAMILY
    except Exception:
        return []
    pool = sorted(f for f, (m, i, _s) in table.items()
                  if m == mechanism_id and i == information and f not in not_a_family
                  and (not ctx.families or f in ctx.families))
    if pool:
        return pool
    return sorted(f for f, (m, _i, _s) in table.items()
                  if m == mechanism_id and f not in not_a_family
                  and (not ctx.families or f in ctx.families))


# --------------------------------------------------------------------------- intake
def _record(source_id: str, source_type: str, spec: dict[str, Any], *, mechanism: str,
            origin: str, generator: str, conn: Any = None) -> tuple[str, bool]:
    return R.record_discovery(
        source_id=source_id, source_type=source_type, mechanism=mechanism[:400], origin=origin,
        generator=generator, assets=spec.get("assets") or [], sessions=[spec.get("session")],
        horizons=[spec.get("chart")], regimes=[spec.get("regime")],
        exact_rule_if_known=spec.get("exact_rule") or "", required_data=spec.get("required_data"),
        information=spec.get("information") or "", novelty=spec.get("novelty"),
        confidence=spec.get("confidence"), falsifier=spec.get("falsifier") or "",
        economic_rationale=str(spec.get("why") or "")[:800], payload=spec, conn=conn)


def _spec_from_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """One intake row, whatever seat wrote it, normalised into the miners' parent shape."""
    params = row.get("params") if isinstance(row.get("params"), dict) else {}
    sym = str(row.get("symbol") or row.get("sym") or row.get("target") or "").strip().upper()
    syms = row.get("symbols") if isinstance(row.get("symbols"), list) else []
    if not sym and syms:
        sym = str(syms[0]).strip().upper()
    chart = str(row.get("chart") or row.get("timeframe") or params.get("timeframe") or "").upper()
    session = str(row.get("session") or params.get("session") or "").lower()
    text = " ".join(str(row.get(k) or "") for k in
                    ("mechanism", "why", "question", "claim", "title", "note", "thesis"))
    cell = row.get("axis_cell") if isinstance(row.get("axis_cell"), dict) else {}
    return {"symbol": sym, "assets": [s for s in ([sym, *map(str, syms)]) if s],
            "family": str(row.get("family") or ""), "params": dict(params),
            "chart": chart or str(cell.get("chart") or ""),
            "session": session or str(cell.get("session") or "all"),
            "regime": str(row.get("regime") or cell.get("regime") or params.get("regime") or ""),
            "information": str(row.get("information") or cell.get("information_source") or ""),
            "asset_class": str(row.get("asset_class") or cell.get("asset_class") or ""),
            "economic_actor": str(cell.get("economic_actor") or ""),
            "failure_class": str(row.get("failure_class") or row.get("rejection_reason") or ""),
            "side": str(row.get("side") or params.get("side_mode") or ""),
            "exact_rule": str(row.get("exact_rule") or row.get("cell") or ""),
            "required_data": row.get("required_data"), "novelty": row.get("novelty"),
            "confidence": row.get("confidence"), "falsifier": str(row.get("falsifier") or ""),
            "why": text.strip(), "declared_mechanism": str(row.get("mechanism") or "")}


def intake(cursor: dict[str, Any], *, conn: Any = None, limit: int = MAX_DISCOVERIES,
           deadline: float | None = None, record: bool = True
           ) -> tuple[list[dict[str, Any]], dict[str, int], list[dict[str, str]]]:
    """Everything the desk found and has not yet disposed of. Returns (discoveries, by_source,
    unmeasured).

    A source absent on this box lands in `unmeasured` as a NAMED gap, never as a zero that reads
    like a clean sweep. `record=False` is the dry run: nothing is written to the canonical
    registry, ids are synthesised from the content hash and dedupe is within the pass only -- so
    a dry run reports what it WOULD take in without having already taken it in, which is the only
    reading of "dry" that is safe to hand somebody.
    """
    got: list[dict[str, Any]] = []
    by_source: dict[str, int] = {}
    unmeasured: list[dict[str, str]] = []
    seen: set[str] = set()

    def out_of_time() -> bool:
        return deadline is not None and time.monotonic() > deadline

    def add(source_id: str, source_type: str, spec: dict[str, Any], *, origin: str,
            generator: str) -> None:
        if len(got) >= limit:
            return
        mech = spec.get("declared_mechanism") or spec.get("why") or source_type
        if not record:
            key = R.content_hash(source_id, str(spec.get("symbol") or ""), spec,
                                 str(spec.get("chart") or ""))
            if key in seen:
                return
            seen.add(key)
            got.append({"discovery_id": f"dry_{key}", "source_type": source_type,
                        "origin": origin, **spec})
            by_source[source_type] = by_source.get(source_type, 0) + 1
            return
        did, created = _record(source_id, source_type, spec, mechanism=str(mech), origin=origin,
                               generator=generator, conn=conn)
        if created:
            got.append({"discovery_id": did, "source_type": source_type, "origin": origin, **spec})
            by_source[source_type] = by_source.get(source_type, 0) + 1

    for row in R.discoveries(state="UNPROCESSED", limit=limit, conn=conn):
        payload = row.get("payload_json")
        spec = json.loads(payload) if isinstance(payload, str) and payload.startswith("{") else {}
        merged: dict[str, Any] = {**row, **spec}
        if not merged.get("symbol") and isinstance(row.get("assets_json"), str):
            # A discovery another organ recorded carries its instruments in `assets_json` and no
            # `symbol`. Reading only `symbol` would make every foreign discovery instrument-less,
            # and an instrument-less parent produces a closure of nothing -- a silent drop wearing
            # a successful run.
            with contextlib.suppress(ValueError, TypeError):
                merged["symbols"] = [s for s in json.loads(row["assets_json"]) if s]
        got.append({"discovery_id": str(row["discovery_id"]), "source_type": "registry",
                    "origin": row.get("origin"), **_spec_from_row(merged)})
        by_source["registry_unprocessed"] = by_source.get("registry_unprocessed", 0) + 1
        if len(got) >= limit:
            return got, by_source, unmeasured

    if INTEL.exists():
        files = sorted([*INTEL.glob("*/*.json"), *INTEL.glob("*/*.jsonl")],
                       key=lambda p: p.stat().st_mtime if p.exists() else 0.0, reverse=True)
        for path in files:
            if len(got) >= limit or out_of_time():
                break
            if not _fresh(cursor, path):
                continue
            if path.suffix == ".jsonl":
                doc = [json.loads(ln) for ln in _jsonl_lines(path)]
            else:
                doc = _read_json(path)
            for row in rows_of(doc)[:MAX_ROWS_PER_FILE]:
                add(f"intel:{path.parent.name}:{path.name}", "intelligence", _spec_from_row(row),
                    origin=R.origin_of(path.parent.name), generator=f"seat:{path.parent.name}")
            _mark(cursor, path)
    else:
        unmeasured.append({"what": "data/intelligence", "why": "the seat donation tree is absent "
                                                               "on this host; seat conversion is "
                                                               "UNMEASURED, not zero"})

    if FRONTIER_QUEUE.exists():
        if _fresh(cursor, FRONTIER_QUEUE):
            for raw in _jsonl_lines(FRONTIER_QUEUE)[:MAX_ROWS_PER_FILE]:
                try:
                    row = json.loads(raw)
                except ValueError:
                    continue
                if not isinstance(row, dict):
                    continue
                spec = _spec_from_row(row)
                spec["why"] = f"{row.get('firm', '')} {row.get('capability', '')} {spec['why']}"
                add(f"frontier:{row.get('candidate_id') or row.get('at')}", "frontier_queue", spec,
                    origin="EXTERNAL", generator="frontier_intel")
            _mark(cursor, FRONTIER_QUEUE)
    else:
        unmeasured.append({"what": str(FRONTIER_QUEUE), "why": "no frontier queue on this host"})

    for card in R.cards(conn=conn)[:limit]:
        if len(got) >= limit:
            break
        spec = _spec_from_row({"symbol": card.get("symbol") or card.get("market"),
                               "family": card.get("family"), "chart": card.get("chart"),
                               "mechanism": card.get("mechanism") or card.get("thesis"),
                               "why": card.get("thesis")})
        add(f"card:{card.get('id')}", "alpha_card", spec, origin="MOAT", generator="alpha_cards")

    for row in _graveyard_rows():
        if len(got) >= limit:
            break
        add(row["source_id"], "graveyard", _spec_from_row(row), origin="MOAT",
            generator="graveyard")

    rq = _read_json(RESIDUAL_QUEUE)
    if rq is None:
        unmeasured.append({"what": str(RESIDUAL_QUEUE),
                           "why": "no residual queue artifact on this box: the unexplained-residual"
                                  " intake is UNMEASURED, which is a real answer and a named gap"})
    elif _fresh(cursor, RESIDUAL_QUEUE):
        for row in rows_of(rq)[:MAX_ROWS_PER_FILE]:
            add(f"residual:{row.get('id') or row.get('cell') or row.get('symbol')}",
                "residual_queue", _spec_from_row(row), origin="DESK", generator="residual_queue")
        _mark(cursor, RESIDUAL_QUEUE)

    sq = _read_json(STANDING_QUESTIONS)
    if sq is None:
        unmeasured.append({"what": str(STANDING_QUESTIONS),
                           "why": "no standing-questions artifact on this box"})
    elif _fresh(cursor, STANDING_QUESTIONS):
        for qid, block in (sq.get("questions") or {}).items():
            for finding in (block.get("findings") or [])[:20] if isinstance(block, dict) else []:
                if not isinstance(finding, dict):
                    continue
                spec = _spec_from_row(finding)
                spec["why"] = (f"{qid}: {finding.get('feature') or finding.get('axis') or ''} "
                               f"on {spec['symbol']} ({block.get('why') or ''})")[:600]
                add(f"question:{qid}:{finding.get('feature') or finding.get('axis')}:"
                    f"{spec['symbol']}", "standing_question", spec, origin="DESK",
                    generator="standing_questions")
        _mark(cursor, STANDING_QUESTIONS)

    return got, by_source, unmeasured


def _jsonl_lines(path: Path) -> list[str]:
    try:
        if path.stat().st_size > MAX_INTAKE_FILE_BYTES:
            return []
        return [ln for ln in path.read_text(encoding="utf-8", errors="replace").splitlines()
                if ln.strip()]
    except OSError:
        return []


def _graveyard_rows() -> list[dict[str, Any]]:
    """The graveyard is MARKDOWN on this box and the desk is right to keep it that way -- it is
    read by humans. Its headings and mechanism-of-death lines are what a machine needs: the
    failure class is what licenses a resurrection, so a kill with no stated cause yields a row
    with no failure class and the resurrection miner correctly declines it."""
    out: list[dict[str, Any]] = []
    doc = _read_json(GRAVEYARD_JSON)
    if doc is not None:
        for row in rows_of(doc)[:MAX_ROWS_PER_FILE]:
            out.append({**row, "source_id": f"graveyard:{row.get('id') or row.get('cell')}"})
    if not GRAVEYARD_MD.exists():
        return out
    try:
        text = GRAVEYARD_MD.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    title, buf = "", []
    for line in text.splitlines():
        if line.startswith("### "):
            if title:
                out.append(_graveyard_entry(title, buf))
            title, buf = line[4:].strip(), []
        elif title:
            buf.append(line)
    if title:
        out.append(_graveyard_entry(title, buf))
    return out[:MAX_ROWS_PER_FILE]


_DEATH_TO_CLASS: tuple[tuple[str, str], ...] = (
    ("cost", "cost_killed"), ("spread", "cost_killed"), ("regime", "regime_specific"),
    ("direction", "wrong_direction"), ("sign", "wrong_direction"), ("horizon", "wrong_horizon"),
    ("timeframe", "wrong_horizon"), ("duplicate", "redundant"), ("redundant", "redundant"),
    ("no edge", "no_edge"), ("zero external importers", "no_edge"), ("unstable", "unstable"),
    ("execution", "execution_killed"), ("decay", "forward_decay"), ("wrong asset", "wrong_asset"),
)


def _graveyard_entry(title: str, body: list[str]) -> dict[str, Any]:
    blob = " ".join(body).lower()
    fc = next((cls for token, cls in _DEATH_TO_CLASS if token in blob), "")
    return {"source_id": f"graveyard:{title[:120]}", "title": title, "why": " ".join(body)[:600],
            "failure_class": fc, "mechanism": title}


# --------------------------------------------------------------------------- the three gates
def gate_economic(child: Mapping[str, Any], ctx: TM.Context) -> tuple[bool, str]:
    """GATE 1 -- does the ontology admit this cell at all? The cheapest refusal there is."""
    sym = str(child.get("symbol") or "")
    if not sym:
        return False, "economic:no_instrument"
    if not ctx.hypothesis_lane(sym):
        return False, "economic:two_lane_mandate"
    contract = ctx.contract(child.get("mechanism_id"))
    ok, why = TM.compatible(contract, chart=str(child.get("chart") or ""),
                            session=str(child.get("session") or "all"),
                            regime=str(child.get("regime") or ""),
                            asset_class=str(child.get("asset_class") or ""))
    if not ok:
        return False, f"economic:incompatible ({why})"
    if not TM.currency_ok(contract, sym):
        return False, "economic:instrument_carries_no_leg_this_flow_names"
    fam = str(child.get("family") or "")
    if not fam:
        return False, "economic:no_family_implements_this_mechanism"
    if ctx.families and fam not in ctx.families:
        return False, f"economic:family_not_registered ({fam})"
    if child.get("params", {}).get("residual_tag") == "residual" \
            and contract is not None and not contract.residualisable:
        return False, "economic:mechanism_is_not_residualisable"
    return True, why


def gate_data(child: Mapping[str, Any], ctx: TM.Context) -> tuple[bool, str]:
    """GATE 2 -- can this cell be measured on data the desk HOLDS, point-in-time?

    Bars for symbol x chart, every declared information axis resolvable, and a PIT status. A macro
    or positioning conditioner with no axis file is refused HERE with its name in the reason, so
    the gap reads as a data gap rather than as a mechanism that failed.
    """
    sym, chart = str(child.get("symbol") or ""), str(child.get("chart") or "").upper()
    if not chart:
        return False, "data:no_chart"
    if not ctx.has_bars(sym, chart):
        return False, f"data:no_bars ({sym}_{chart}.parquet)"
    axis = str(child.get("params", {}).get("macro_axis") or "")
    if axis and axis not in ctx.macro_states:
        return False, f"data:macro_axis_absent ({axis})"
    info = str(child.get("information") or "")
    if info in ("macro", "positioning", "carry") and not ctx.macro_states:
        return False, f"data:no_axis_file_for_{info}"
    pit = pit_status(child, ctx)
    if pit == "UNKNOWN":
        return False, "data:pit_unknown (no knowable_at for the conditioning axis)"
    return True, f"data:ok ({pit})"


def pit_status(child: Mapping[str, Any], ctx: TM.Context) -> str:
    """PIT_BAR_CLOSE for a price-only cell (a bar is knowable at its own close); PIT_STAMPED when
    the conditioning axis file carries `knowable_at`; UNKNOWN otherwise, which the data gate
    refuses. Absence of a stamp is never permission (the 2026-09-05 census: 0 of 4,768 rows
    carried an available_time and nothing could notice)."""
    info = str(child.get("information") or "price_only")
    axis = str(child.get("params", {}).get("macro_axis") or "")
    if axis:
        return "PIT_STAMPED" if axis in ctx.macro_states else "UNKNOWN"
    if info in ("", "price_only", "cross_asset", "microstructure", "seasonality"):
        return "PIT_BAR_CLOSE"
    return "PIT_STAMPED" if ctx.macro_states else "UNKNOWN"


def gate_novelty(child: Mapping[str, Any], ctx: TM.Context, *, coverage: Mapping[str, int],
                 hashes: set[str], redundant: set[str], conn: Any = None) -> tuple[bool, str]:
    """GATE 3 -- is this cell a twin of one the desk already holds?

    Three independent reads and any one of them refuses: the registry's content hash (the same
    rule already enqueued), the breadth grid coordinate (a cell already crowded), and
    `NOVELTY_GATE.json`'s redundancy census when it exists. A crowded grid cell is not a refusal
    on its own -- the empty-cell bonus in `score_candidate` already prefers empty ones -- so only
    an EXACT twin blocks here; breadth is priced, not vetoed.
    """
    h = child.get("content_hash") or ""
    if h and h in hashes:
        return False, "novelty:exact_twin_already_enqueued"
    key = f"{child.get('symbol')}.{child.get('family')}"
    if key in redundant:
        return False, f"novelty:redundant_in_novelty_gate ({key})"
    cell = R.grid_cell({**child, "mechanism": child.get("mechanism_id")})
    if coverage.get(cell, 0) and h and conn is not None:
        row = conn.execute("SELECT 1 FROM research_candidates WHERE content_hash=? LIMIT 1",
                           (h,)).fetchone()
        if row is not None:
            return False, "novelty:exact_twin_in_registry"
    return True, f"novelty:new ({cell})"


def _redundant_keys() -> set[str]:
    doc = _read_json(NOVELTY_GATE)
    if not isinstance(doc, dict):
        return set()
    twins = doc.get("twins_named")
    return {str(k).removeprefix("external.") for k in twins} if isinstance(twins, dict) else set()


# --------------------------------------------------------------------------- closure & compile
def parent_of(disc: Mapping[str, Any], ctx: TM.Context) -> dict[str, Any]:
    """A registry discovery, normalised into the parent the twelve miners read."""
    spec = dict(disc)
    sym = str(spec.get("symbol") or "").upper()
    mid, _why = interpret(str(spec.get("why") or ""), str(spec.get("declared_mechanism") or ""))
    contract = TM.CONTRACTS.get(mid)
    spec["mechanism_id"] = mid
    spec["symbol"] = sym
    spec["asset_class"] = spec.get("asset_class") or ctx.class_of(sym)
    spec["chart"] = (str(spec.get("chart") or "").upper() or "H1")
    spec["session"] = str(spec.get("session") or "all").lower() or "all"
    # UNCONDITIONAL IS A VALUE, NOT A BLANK. `grid_cell` renders a falsy axis as the literal
    # "unknown", and an unconditional arm is not an unknown one -- it is the control every
    # conditional is measured against. Normalising HERE also keeps `_hash_of` and the hash
    # `enqueue_candidate` recomputes from the same fields in agreement; they disagreed while this
    # was blank on one side and filled on the other, which would silently defeat the dedupe.
    spec["regime"] = str(spec.get("regime") or "unconditional").lower()
    spec["information"] = (spec.get("information")
                           or (contract.information if contract else "price_only"))
    spec["economic_actor"] = spec.get("economic_actor") or (contract.actor if contract else "")
    spec["horizon"] = TM.CHART_GRID_HORIZON.get(spec["chart"], "unknown")
    spec["params"] = dict(spec.get("params") or {})
    return spec


def closure(parent: Mapping[str, Any], ctx: TM.Context) -> tuple[list[dict[str, Any]],
                                                                 dict[str, int], int]:
    """The twelve miners' enumeration, deduped by content hash. Returns
    (children, by_miner_counts, closure_size) where closure_size counts the truncated members
    too -- every one of which is blocked with a named reason by the caller."""
    before = len(ctx.truncated)
    by_miner_rows = TM.run_all(parent, ctx)
    truncated = sum(int(t.get("n") or 0) for t in ctx.truncated[before:])
    seen: set[str] = set()
    parent_hash = _hash_of(parent)
    seen.add(parent_hash)
    children: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for miner, rows in by_miner_rows.items():
        counts[miner] = 0
        for row in rows:
            h = _hash_of(row)
            if h in seen:
                continue
            seen.add(h)
            row = {**row, "content_hash": h, "miner": miner}
            children.append(row)
            counts[miner] += 1
    return children, counts, len(children) + truncated


def _hash_of(spec: Mapping[str, Any]) -> str:
    return R.content_hash(str(spec.get("family") or ""), str(spec.get("symbol") or ""),
                          spec.get("params") or {}, str(spec.get("chart") or ""),
                          str(spec.get("session") or ""), str(spec.get("regime") or ""),
                          str(spec.get("horizon") or ""))


def _with_family(child: dict[str, Any], ctx: TM.Context) -> dict[str, Any]:
    if child.get("family") and (not ctx.families or child["family"] in ctx.families):
        return child
    pool = _family_pool(ctx, str(child.get("mechanism_id") or ""),
                        str(child.get("information") or "price_only"))
    if pool:
        # SPREAD DETERMINISTICALLY, NOT ALPHABETICALLY (the lesson `axis_registry.family_for`
        # already paid for): pool[0] gives every cell of a mechanism the same family, which is one
        # idea proposed sixty times. Off the content hash, not `hash()` -- PYTHONHASHSEED makes
        # the builtin vary per process, and a cell that changes family between runs is a
        # different hypothesis wearing the same id.
        salt = str(child.get("content_hash") or child.get("symbol") or "0")
        idx = int(salt[:8], 16) if all(ch in "0123456789abcdef" for ch in salt[:8]) else len(salt)
        child = dict(child)
        child["family"] = pool[idx % len(pool)]
        child["content_hash"] = _hash_of(child)
    return child


def donate(rows: list[dict[str, Any]], tests_run: int) -> str | None:
    """The docket's door. Indirected through this module so a test can monkeypatch ONE name, and
    called ONCE per run -- `proposer_common.donate` names its file by the minute, so two calls in
    the same minute would write one filename twice."""
    try:
        from research.proposer_common import donate as _donate
    except Exception as exc:
        return f"donation door unreachable ({type(exc).__name__}: {exc})"
    path = _donate(SOURCE, rows, tests_run)
    return str(path) if path else None


def _donation_row(child: Mapping[str, Any], parent: Mapping[str, Any]) -> dict[str, Any]:
    return {"kind": "hypothesis", "source": SOURCE, "family": child.get("family"),
            "symbol": child.get("symbol"), "symbols": [child.get("symbol")],
            "params": dict(child.get("params") or {}), "timeframe": child.get("chart"),
            "chart": child.get("chart"), "session": child.get("session"),
            "regime": child.get("regime"), "mechanism": child.get("mechanism_id"),
            "transformation": child.get("transformation"),
            "cell": f"{child.get('symbol')}.{child.get('family')}.{child.get('content_hash')}",
            "title": (f"{child.get('transformation')} of {parent.get('symbol') or 'a discovery'}"
                      f" -> {child.get('symbol')} {child.get('chart')} {child.get('session')}"),
            "why": child.get("why"), "parent_discovery_ids": child.get("parent_discovery_ids"),
            "discovery_id": parent.get("discovery_id")}


# --------------------------------------------------------------------------- the organ
def _dispose(child: dict[str, Any], ctx: TM.Context, *, coverage: Mapping[str, int],
             hashes: set[str], redundant: set[str], conn: Any) -> tuple[bool, str]:
    """The three gates in order. The FIRST refusal is the reason recorded -- a child refused by
    economics is not also a data gap, and reporting it as both would double-count the debt."""
    for gate in (lambda: gate_economic(child, ctx),
                 lambda: gate_data(child, ctx),
                 lambda: gate_novelty(child, ctx, coverage=coverage, hashes=hashes,
                                      redundant=redundant, conn=conn)):
        ok, why = gate()
        if not ok:
            return False, why
    return True, "passed all three gates"


def _expand_one(disc: Mapping[str, Any], ctx: TM.Context, *, coverage: dict[str, int],
                hashes: set[str], redundant: set[str], conn: Any, dry_run: bool,
                donations: list[dict[str, Any]], blocked: dict[str, int],
                by_miner: dict[str, dict[str, int]]) -> dict[str, Any]:
    """One discovery, all the way: interpret, expand, gate, compile, queue.

    Every member of the closure leaves here with a disposition, or this function is broken -- and
    the artifact's `unexplained_missing_cells` is exactly the instrument that would say so.
    """
    did = str(disc.get("discovery_id") or "")
    parent = parent_of(disc, ctx)
    mechanism_id = str(parent["mechanism_id"])
    if not dry_run:
        R.set_discovery_state(did, "INTERPRETED", mechanism_id=mechanism_id, conn=conn)

    children, counts, possible = closure(parent, ctx)
    for miner, n in counts.items():
        by_miner.setdefault(miner, {"children": 0, "passed": 0, "blocked": 0})["children"] += n
    capped = children[:MAX_CHILDREN]
    over = len(children) - len(capped)
    budget_left_behind = possible - len(children)
    n_blocked = budget_left_behind + over
    if budget_left_behind:
        blocked["budget:miner_compute_cap"] = (blocked.get("budget:miner_compute_cap", 0)
                                               + budget_left_behind)
    if over:
        blocked["budget:per_discovery_cap"] = blocked.get("budget:per_discovery_cap", 0) + over
    if not dry_run:
        R.set_discovery_state(did, "EXPANDED", possible_cells=possible,
                              generated_cells=len(capped), conn=conn)

    compiled = 0
    for raw in capped:
        child = _with_family({**raw, "mechanism_id": mechanism_id,
                              "economic_actor": parent.get("economic_actor")}, ctx)
        ok, why = _dispose(child, ctx, coverage=coverage, hashes=hashes, redundant=redundant,
                           conn=conn)
        slot = by_miner.setdefault(str(child.get("miner") or "?"),
                                   {"children": 0, "passed": 0, "blocked": 0})
        if not ok:
            key = why.split(" (")[0]
            blocked[key] = blocked.get(key, 0) + 1
            n_blocked += 1
            slot["blocked"] += 1
            if not dry_run:
                R.remember("conversion", f"{did} -> {child.get('transformation')} blocked: {why}",
                           kind="blocked_cell", memory_key=f"blocked:{child['content_hash']}",
                           payload={"discovery_id": did, "child": child.get("content_hash"),
                                    "miner": child.get("miner"), "reason": why}, conn=conn)
            continue
        slot["passed"] += 1
        compiled += 1
        hashes.add(str(child["content_hash"]))
        cell = R.grid_cell({**child, "mechanism": mechanism_id})
        coverage[cell] = coverage.get(cell, 0) + 1
        if dry_run:
            continue
        cid, _created = R.enqueue_candidate(
            family=str(child["family"]), symbol=str(child["symbol"]),
            params=dict(child.get("params") or {}), origin=str(disc.get("origin") or "DESK"),
            mechanism=mechanism_id, status="queued", discovery_id=did,
            transformation=str(child.get("transformation") or ""),
            generator=f"{SOURCE}:{child.get('miner')}", chart=str(child.get("chart") or ""),
            session=str(child.get("session") or ""), regime=str(child.get("regime") or ""),
            horizon=str(child.get("horizon") or ""),
            asset_class=str(child.get("asset_class") or ""),
            information=str(child.get("information") or ""),
            economic_actor=str(child.get("economic_actor") or ""),
            causal_rationale=str(child.get("why") or "")[:800],
            parent_ids=list(child.get("parent_discovery_ids") or []),
            pit_status=pit_status(child, ctx), source_id=str(disc.get("source_type") or ""),
            conn=conn)
        R.link("mechanism", mechanism_id, "cell", cid, "compiled", conn=conn)
        R.link("miner", f"{SOURCE}:{child.get('miner')}", "cell", cid, "generated", conn=conn)
        donations.append(_donation_row(child, parent))

    if not dry_run:
        R.set_discovery_state(
            did, "QUEUED" if compiled else "BLOCKED",
            reason=None if compiled else ("every economically defensible child of this discovery "
                                          "was refused by a named gate; the closure is disposed, "
                                          "not idle"),
            possible_cells=possible, generated_cells=len(capped), compiled_cells=compiled,
            queued_cells=compiled, blocked_cells=n_blocked, conn=conn)
    return {"discovery_id": did, "mechanism_id": mechanism_id, "possible": possible,
            "generated": len(capped), "compiled": compiled, "blocked": n_blocked}


def run(*, dry_run: bool = False, budget_s: int = BUDGET_S,
        max_discoveries: int = MAX_DISCOVERIES, cursor_path: Path | None = None,
        out: Path | None = None, ctx: TM.Context | None = None) -> dict[str, Any]:
    """INTAKE -> INTERPRET -> CLOSURE -> GATES -> COMPILE -> QUEUE, inside a wall-clock budget."""
    started = time.monotonic()
    deadline = started + max(1, int(budget_s))
    cpath = cursor_path or CURSOR
    cursor = load_cursor(cpath)
    ctx = ctx if ctx is not None else build_context()
    conn = R.connect()
    report: dict[str, Any] = {
        "at": _now(), "dry_run": bool(dry_run), "budget_s": int(budget_s),
        "intake": {"by_source": {}, "n": 0}, "interpreted": 0, "expanded": 0, "compiled": 0,
        "queued": 0, "blocked": {"by_reason": {}, "n": 0}, "possible_cells": 0,
        "generated_cells": 0, "unexplained_missing_cells": None, "conversion_coverage": None,
        "by_miner": {}, "mechanisms": {}, "unmeasured": [], "budget_stopped": False,
        "donated": 0, "donation_path": None, "notes": [], "priors_lowered": [], "rule": RULE,
    }
    try:
        discoveries, by_source, unmeasured = intake(cursor, conn=conn, limit=max_discoveries,
                                                    deadline=deadline, record=not dry_run)
        report["intake"]["by_source"] = by_source
        report["intake"]["n"] = len(discoveries)
        report["unmeasured"].extend(unmeasured)

        coverage = dict(R.grid_coverage(conn=conn))
        hashes = {str(r["content_hash"]) for r in R.candidates(limit=20000, conn=conn)
                  if r.get("content_hash")}
        redundant = _redundant_keys()
        donations: list[dict[str, Any]] = []
        blocked: dict[str, int] = {}
        by_miner: dict[str, dict[str, int]] = {}

        for disc in discoveries:
            if time.monotonic() > deadline:
                report["budget_stopped"] = True
                report["unmeasured"].append({
                    "what": f"{len(discoveries) - report['expanded']} discovery(ies) not expanded",
                    "why": f"the {budget_s}s wall-clock budget ran out; they stay UNPROCESSED and "
                           "are the first rows the next pass takes -- deferred, never dropped"})
                break
            got = _expand_one(disc, ctx, coverage=coverage, hashes=hashes, redundant=redundant,
                              conn=conn, dry_run=dry_run, donations=donations, blocked=blocked,
                              by_miner=by_miner)
            report["interpreted"] += 1
            report["expanded"] += 1
            report["compiled"] += got["compiled"]
            report["queued"] += got["compiled"]
            report["possible_cells"] += got["possible"]
            report["generated_cells"] += got["generated"]
            slot = report["mechanisms"].setdefault(got["mechanism_id"],
                                                   {"discoveries": 0, "compiled": 0})
            slot["discoveries"] += 1
            slot["compiled"] += got["compiled"]

        report["blocked"]["by_reason"] = dict(sorted(blocked.items()))
        report["blocked"]["n"] = sum(blocked.values())
        report["by_miner"] = {k: by_miner[k] for k in TM.MINERS if k in by_miner}
        report["notes"] = ctx.notes[:80]
        report["truncated"] = ctx.truncated[:40]
        report["priors_lowered"] = ctx.priors[:40]
        if not dry_run:
            for p in ctx.priors:
                R.remember("prior", p["why"], kind="mechanism_prior",
                           memory_key=f"prior_down:{p['mechanism_id']}", payload=p, conn=conn)
        if donations and not dry_run:
            report["donation_path"] = donate(donations, report["possible_cells"])
            report["donated"] = len(donations)
            # MEASURED, NOT HIDDEN. `proposer_common.donate` writes its OWN thin candidate row per
            # donated cell (`_record_in_registry`, chart only, no session/regime/horizon), so
            # `research_candidates` carries two rows for every cell compiled here: the fully-axed
            # one written above and the door's chart-only twin, whose content hash therefore
            # differs and does not dedupe. Every donating organ on this desk has the same twin.
            # The fix belongs at the shared door, not in a second copy of it here; naming it in
            # the artifact is what stops the count being read as double the breadth.
            report["registry_twins"] = {
                "n": len(donations),
                "why": "the shared donation door enqueues a chart-only twin per donated cell; "
                       "candidate COUNTS include it, the axed row from this organ is the one "
                       "whose grid_cell is informative"}
            R.generator_yield_update(SOURCE, generated=report["generated_cells"],
                                     donated=len(donations),
                                     compute_s=time.monotonic() - started, conn=conn)
        debt = R.conversion_debt(conn=conn)
        report["conversion_coverage"] = debt.get("conversion_coverage")
        report["unexplained_missing_cells"] = debt.get("unexplained_missing_cells")
        report["conversion_debt"] = debt
        if not by_source:
            report["unmeasured"].append({
                "what": "intake", "why": "no source produced a NEW discovery this pass; the "
                                         "cursor says every readable artifact was already "
                                         "disposed of, which is idempotence, not an empty desk"})
    finally:
        conn.close()
    report["wall_s"] = round(time.monotonic() - started, 2)
    if not dry_run:
        cursor["at"] = report["at"]
        cursor["runs"] = int(cursor.get("runs") or 0) + 1
        _write_atomic(cpath, cursor)
        _write_atomic(out if out is not None else OUT, report)
    return report


def summary_lines(report: Mapping[str, Any]) -> list[str]:
    cov = report.get("conversion_coverage")
    lines = [f"intake {report.get('intake', {}).get('n', 0)} "
             f"{report.get('intake', {}).get('by_source')}",
             f"expanded {report.get('expanded')} -> possible {report.get('possible_cells')} "
             f"generated {report.get('generated_cells')} compiled {report.get('compiled')} "
             f"blocked {report.get('blocked', {}).get('n', 0)}",
             f"conversion coverage {'UNMEASURED' if cov is None else format(cov, '.1%')}; "
             f"unexplained missing {report.get('unexplained_missing_cells')}"]
    for miner, c in (report.get("by_miner") or {}).items():
        lines.append(f"  {miner:24} children {c['children']:4}  passed {c['passed']:4}  "
                     f"blocked {c['blocked']:4}")
    for reason, n in (report.get("blocked", {}).get("by_reason") or {}).items():
        lines.append(f"  BLOCKED {reason:46} {n}")
    for u in report.get("unmeasured") or []:
        lines.append(f"  UNMEASURED {u.get('what')}: {u.get('why')}")
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true",
                    help="intake, expand and gate, then STOP: no discovery recorded, no candidate "
                         "enqueued, no donation, no cursor and no artifact -- a dry run that "
                         "wrote to the canonical registry would not be a dry run")
    ap.add_argument("--budget-s", type=int, default=BUDGET_S, help="wall-clock budget")
    ap.add_argument("--max-discoveries", type=int, default=MAX_DISCOVERIES)
    args = ap.parse_args(argv)
    report = run(dry_run=args.dry_run, budget_s=args.budget_s,
                 max_discoveries=args.max_discoveries)
    for line in summary_lines(report):
        print(line)
    print("dry run -- nothing enqueued, nothing donated, nothing written" if args.dry_run
          else f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
