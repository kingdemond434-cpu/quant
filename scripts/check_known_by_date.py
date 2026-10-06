#!/usr/bin/env python3
"""KNOWN-BY-DATE LINT: every research reader that joins an external dataset by the date it
DESCRIBES, without routing through that dataset's publication lag, is named.

    python scripts/check_known_by_date.py            # the fence: exit 1 on a NEW offender
    python scripts/check_known_by_date.py --json     # the census as JSON
    python scripts/check_known_by_date.py --update   # drop healed names from the floor (never adds)

THE DEFECT CLASS. A daily macro state computed from the day's close, joined to a 03:00 bar by
`s.time.date() in fav_dates`; a CFTC report as-of Tuesday labelled Friday 00:00 and joined on the
label; a monthly print joined on the month it describes. Each reads correctly, types line up, and
each conditions a bar on a number nobody had yet. The desk found and fixed three of these one at
a time (`run_edges_macro_fusion_sweep`, `orthogonal_sweep.COT_RELEASE_LAG_DAYS`,
`orthogonal_sweep.DAILY_MACRO_SERIES`). This names the whole class instead.

WHAT IS A READER. A module under the research trees whose source carries one of a registered
source's `readers` tokens (`libs/tiers/data_os.PUBLICATION_LAGS`), so the dataset list and the
lag list are ONE declaration: adding a source with its readers makes every reader of it subject
to this fence the hour it lands.

WHAT IS A VALID-DATE JOIN. An aligning call (`reindex`, `merge`, `merge_asof`, `join`, `asof`,
`searchsorted`, `get_indexer`) or a membership test on a `.date()` -- the two shapes every
look-ahead of this kind has taken here.

WHAT DECLARES THE LAG. Any of: a read through the bitemporal store (`latest_known`, `as_of(`),
`data_os` (`store_from_series`, `knowledge_time`, `declared_lag`, `known_series`, `known_as_of`),
a knowledge-time column (`available_time`, `knowledge_time`, `usable_at`), a vintage read, or a
named lag constant (`PUBLICATION_LAG`, `RELEASE_LAG`, `KNOWABLE`). The census is module-grained
on purpose: it cannot prove a lag is applied to the right join, only that a reader that joins has
SOMETHING that says when its data was known -- an undeclared one has nothing, which is the
finding.

A RATCHET THAT ONLY TIGHTENS. Today's offenders are the committed floor
(`docs/research/known_by_date_floor.json`); only an ARRIVAL fails, a healed module drops out
(`--update` rewrites the floor to the smaller set and refuses to add a name). Fetchers
(`fetch_*.py`) write datasets and join nothing to bars; they are out of scope by name.

EVERY READER IS ACCOUNTED FOR (2026-09-30). A reader that joins nothing to a bar is not an
offender, but it is not "routed" either: it is routed in code (a lag token), DECLARED in
`data_os.READER_ROUTES` with the basis of why its read is safe (a live read, a read through a
lagging provider, a path mention), or listed as `undeclared`. `assumed` bases are flagged.

THE CERTIFICATE PATH IS FENCED (2026-09-30). Every input provider the gauntlet's `build_cell`
(sealed) or the forward/live `family_inputs.resolve` calls -- `inputs._<name>(...)` and
`resolve_inputs` -- must be declared in `data_os.CERTIFICATE_INPUTS`; every source it declares
must carry a publication lag; and a provider reading a lagged, non-bar source must apply one in
its own body (or in a module helper it calls). Any of the three missing FAILS this fence: a
certificate whose inputs cannot say when they were known certifies a look-ahead.

THE PRODUCER CENSUS: WHICH READS GO THROUGH THE BITEMPORAL STORE (Tier S AC3, 2026-10-06). A
lag token anywhere in a module is enough for the reader census above; it is not enough to say a
value is READ AS KNOWN AT THE DECISION TIME. Every research-side macro / alt-data producer -- a
module under the research trees or `desks/mt5/macro` that carries a macro/alt source token and
JOINS it to a clock (or shifts it by a lag) -- is classed by its read path:

    bitemporal         reads through `libs/tiers/bitemporal.BitemporalStore` (`latest_known`,
                       `store_from_series`, `data_os.pit_align` / `known_series` / `known_as_of`,
                       all store-backed since AC3)
    knowledge_stamped  joins on a row's own knowledge-time column (`knowable_at`,
                       `available_time`, `usable_at`) -- point-in-time, not through the store
    lag_shift          shifts by a lag constant of its own -- point-in-time by arithmetic only
    declared           a live read / mention declared in `data_os.READER_ROUTES` or
                       `data_os.PRODUCER_ROUTES`
    not_pit            none of these: a value joined on the date it describes

A `not_pit` producer FAILS the fence outright. Every non-bitemporal producer is listed in a floor
(`docs/research/bitemporal_producer_floor.json`) that only SHRINKS: a producer ARRIVING outside
the store fails, a producer that moves onto the store drops out (`--update`). The counts are
published in KNOWN_BY_DATE.json under `producers` on the same hourly `pit_canaries` leg.

Artifacts: `desks/mt5/reports/KNOWN_BY_DATE.json` (the reader census and the floor verdict) and
`desks/mt5/reports/PIT_LAG_CENSUS.json` (every declared lag, the assumed ones flagged, the
registry census and the certificate inputs). The box writes both on the hourly `pit_canaries`
leg (`scripts/check_pit_canaries.py`) and publishes them through `sync_shadow_to_git.ps1`.
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.tiers import data_os  # noqa: E402
from libs.tiers.data_os import PUBLICATION_LAGS  # noqa: E402

TREES = ("desks/mt5/research", "desks/mt5/mt5desk", "libs/research")
JOINS = ("reindex", "merge", "merge_asof", "join", "asof", "searchsorted", "get_indexer")
LAG_TOKENS = ("latest_known", ".as_of(", "store_from_series", "knowledge_time", "declared_lag",
              "available_time", "usable_at", "vintage", "PUBLICATION_LAG", "publication_lag",
              "RELEASE_LAG", "KNOWABLE", "data_os.", "known_series", "known_as_of", "pit_align")
FLOOR = ROOT / "docs" / "research" / "known_by_date_floor.json"
OUT = ROOT / "desks" / "mt5" / "reports" / "KNOWN_BY_DATE.json"
LAG_OUT = ROOT / "desks" / "mt5" / "reports" / "PIT_LAG_CENSUS.json"
#: the certificate path's two callers of input providers: the gauntlet (sealed) and the
#: forward/live rebuild that mirrors it
CERT_CALLERS = ("desks/mt5/scripts/external_gauntlet.py", "desks/mt5/mt5desk/family_inputs.py")
REGISTRIES = ("desks/mt5/data/data_registry.json", "desks/mt5/data_registry.json")

# ------------------------------------------------------------------ the producer census (AC3)
PRODUCER_TREES = (*TREES, "desks/mt5/macro")
PRODUCER_FLOOR = ROOT / "docs" / "research" / "bitemporal_producer_floor.json"
#: macro / alt-data tokens beyond the registered sources' `readers`: FRED and ALFRED, vintages,
#: macro states and regimes, surprises, alt-data conditioners
PRODUCER_TOKENS = ("fred", "alfred", "data/vintages", "release_vintages", "macro_regime",
                   "macro_state", "alt_proxies", "alt_data", "event_surprise", "surprise_z",
                   "cot.json", "gdelt", "exogenous_conditioner")
#: a read through the bitemporal store (the three data_os doors are store-backed since AC3)
BITEMPORAL_TOKENS = ("latest_known", "BitemporalStore", "store_from_series", "pit_align",
                     "known_series", "known_as_of", "known_axis_series")
#: a join on the row's own knowledge-time column
KNOWLEDGE_COLUMNS = ("knowable_at", "available_time", "usable_at", "knowledge_time")
#: a module that shifts a dated input by a lag produces a time-aligned value even with no join
SHIFT_TOKENS = ("lag_of(", "knowledge_time(", "PUBLICATION_LAG", "RELEASE_LAG", "PUB_LAG",
                "KNOWABLE", *BITEMPORAL_TOKENS)
PRODUCER_CLASSES = ("bitemporal", "knowledge_stamped", "lag_shift", "declared", "not_pit")


def _joins(tree: ast.AST) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr in JOINS:
            # `"sep".join(...)` and `os.path.join` are string/path joins, not data joins
            if node.func.attr == "join" and isinstance(node.func.value, (ast.Constant,
                                                                         ast.Attribute)):
                continue
            out.append((node.lineno, node.func.attr))
        elif isinstance(node, ast.Compare) and any(isinstance(o, (ast.In, ast.NotIn))
                                                   for o in node.ops):
            left = node.left
            if isinstance(left, ast.Call) and isinstance(left.func, ast.Attribute) \
                    and left.func.attr == "date":
                out.append((node.lineno, ".date() in"))
    return sorted(out)


def scan(root: Path | None = None) -> dict[str, Any]:
    root = root or ROOT
    readers_of = {s: tuple(e.get("readers") or ()) for s, e in PUBLICATION_LAGS.items()}
    offenders: dict[str, dict[str, Any]] = {}
    routed: dict[str, list[str]] = {}
    no_join_routed: dict[str, list[str]] = {}
    declared: dict[str, dict[str, Any]] = {}
    undeclared: dict[str, list[str]] = {}
    n_readers = 0
    for tree_rel in TREES:
        base = root / tree_rel
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*.py")):
            if p.name.startswith(("test_", "fetch_")) or "__pycache__" in p.parts \
                    or "/tests/" in p.as_posix():
                continue
            try:
                text = p.read_text("utf-8")
                tree = ast.parse(text)
            except (OSError, SyntaxError, ValueError):
                continue
            sources = sorted(s for s, toks in readers_of.items() if any(t in text for t in toks))
            if not sources:
                continue
            n_readers += 1
            rel = p.relative_to(root).as_posix()
            joins = _joins(tree)
            lagged = any(t in text for t in LAG_TOKENS)
            if not joins:
                if lagged:
                    no_join_routed[rel] = sources
                elif rel in data_os.READER_ROUTES:
                    route = data_os.READER_ROUTES[rel]
                    declared[rel] = {"sources": sources, "route": route.get("route"),
                                     "basis": route.get("basis"),
                                     "assumed": bool(route.get("assumed"))}
                else:
                    undeclared[rel] = sources
                continue
            if lagged:
                routed[rel] = sources
                continue
            offenders[rel] = {"sources": sources,
                              "joins": [f"{ln}:{kind}" for ln, kind in joins[:8]],
                              "why": (f"reads {', '.join(sources)} and joins by date "
                                      f"({joins[0][1]} at line {joins[0][0]}) with no declared "
                                      "publication lag, store read or knowledge-time column")}
    flagged = sorted(r for r, d in declared.items() if d.get("assumed"))
    return {"generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "trees": list(TREES), "sources": sorted(readers_of),
            "readers": n_readers, "routed": routed, "offenders": offenders,
            "no_join": {"routed_in_code": no_join_routed, "declared": declared,
                        "undeclared": undeclared, "flagged_assumed": flagged},
            "accounting": {"readers": n_readers,
                           "joining": len(routed) + len(offenders),
                           "joining_routed": len(routed),
                           "no_join_routed_in_code": len(no_join_routed),
                           "no_join_declared": len(declared),
                           "undeclared": len(undeclared),
                           "offenders": len(offenders),
                           "routed_or_declared": (len(routed) + len(no_join_routed)
                                                  + len(declared))}}


def _producer_class(rel: str, text: str) -> str:
    if any(t in text for t in BITEMPORAL_TOKENS):
        return "bitemporal"
    if any(t in text for t in KNOWLEDGE_COLUMNS):
        return "knowledge_stamped"
    if any(t in text for t in LAG_TOKENS):
        return "lag_shift"
    if rel in data_os.READER_ROUTES or rel in data_os.PRODUCER_ROUTES:
        return "declared"
    return "not_pit"


def producer_census(root: Path | None = None, floor: set[str] | None = None) -> dict[str, Any]:
    """Every research-side macro / alt-data producer and its read path (module docstring)."""
    root = root or ROOT
    reader_toks = tuple(t for e in PUBLICATION_LAGS.values() for t in (e.get("readers") or ()))
    toks = reader_toks + PRODUCER_TOKENS
    rows: dict[str, dict[str, Any]] = {}
    for tree_rel in PRODUCER_TREES:
        base = root / tree_rel
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*.py")):
            if p.name.startswith(("test_", "fetch_")) or "__pycache__" in p.parts \
                    or "/tests/" in p.as_posix():
                continue
            try:
                text = p.read_text("utf-8")
                tree = ast.parse(text)
            except (OSError, SyntaxError, ValueError):
                continue
            hits = sorted({t for t in toks if t in text})
            if not hits:
                continue
            joins = _joins(tree)
            if not joins and not any(t in text for t in SHIFT_TOKENS):
                continue
            rel = p.relative_to(root).as_posix()
            rows[rel] = {"class": _producer_class(rel, text), "tokens": hits[:6],
                         "joins": [f"{ln}:{kind}" for ln, kind in joins[:3]]}
    counts = {c: sum(1 for r in rows.values() if r["class"] == c) for c in PRODUCER_CLASSES}
    non_store = {r for r, v in rows.items() if v["class"] != "bitemporal"}
    not_pit = sorted(r for r, v in rows.items() if v["class"] == "not_pit")
    floor = floor if floor is not None else read_producer_floor()
    arrived = sorted(non_store - floor) if floor is not None else sorted(non_store)
    n = len(rows)
    return {"producers": rows, "counts": counts, "n": n,
            "pit_routed": counts["bitemporal"], "not_pit_routed": n - counts["bitemporal"],
            "pit_routed_share": round(counts["bitemporal"] / n, 4) if n else None,
            "point_in_time": n - counts["not_pit"],
            "not_pit": not_pit, "floor": sorted(floor or ()), "arrived": arrived,
            "healed": sorted((floor or set()) - non_store),
            "verdict": ("UNMEASURED" if floor is None else
                        "FAIL" if (arrived or not_pit) else "OK")}


def read_producer_floor(path: Path | None = None) -> set[str] | None:
    try:
        doc = json.loads((path or PRODUCER_FLOOR).read_text("utf-8"))
    except (OSError, ValueError):
        return None
    names = doc.get("outside_store") if isinstance(doc, dict) else None
    return set(names) if isinstance(names, list) else None


def write_producer_floor(names: set[str], path: Path | None = None) -> None:
    (path or PRODUCER_FLOOR).write_text(json.dumps({
        "_": ("BITEMPORAL PRODUCER FLOOR (Tier S AC3): research-side macro/alt-data producers "
              "that do NOT read through libs/tiers/bitemporal.BitemporalStore. Only SHRINKS: a "
              "producer routed onto the store drops out (check_known_by_date.py --update); a "
              "new producer outside the store fails the fence and is never added here."),
        "outside_store": sorted(names)}, indent=1) + "\n", "utf-8")


# ---------------------------------------------------------------- the certificate path's inputs
def _functions(tree: ast.AST, text: str) -> dict[str, str]:
    """Module-level function name -> its source segment."""
    out: dict[str, str] = {}
    for node in getattr(tree, "body", []):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out[node.name] = ast.get_source_segment(text, node) or ""
    return out


def _applies_lag(name: str, funcs: dict[str, str]) -> bool:
    """A provider's body carries a lag token, or calls a module helper whose body does (one
    hop: `resolve_inputs` -> `_known` -> `data_os.known_series`)."""
    body = funcs.get(name, "")
    if any(t in body for t in LAG_TOKENS):
        return True
    return any(helper != name and f"{helper}(" in body and any(t in hbody for t in LAG_TOKENS)
               for helper, hbody in funcs.items())


def providers_called(root: Path | None = None) -> dict[str, list[str]]:
    """provider name -> the certificate-path callers that call it (`inputs._x(` or
    `resolve_inputs(`)."""
    root = root or ROOT
    out: dict[str, list[str]] = {}
    for rel in CERT_CALLERS:
        try:
            tree = ast.parse((root / rel).read_text("utf-8"))
        except (OSError, SyntaxError, ValueError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            name = None
            if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) \
                    and f.value.id == "inputs" and f.attr.startswith("_") \
                    and not f.attr.startswith("__"):
                name = f.attr
            elif isinstance(f, ast.Name) and f.id == "resolve_inputs":
                name = "resolve_inputs"
            if name:
                callers = out.setdefault(name, [])
                if rel not in callers:
                    callers.append(rel)
    return out


def certificate_fence(root: Path | None = None) -> dict[str, Any]:
    """Every certificate-path input provider declared, lagged, and applying its lag."""
    root = root or ROOT
    called = providers_called(root)
    rows: dict[str, Any] = {}
    failures: list[str] = []
    funcs_of: dict[str, dict[str, str]] = {}
    for name in sorted(set(called) | set(data_os.CERTIFICATE_INPUTS)):
        decl = data_os.CERTIFICATE_INPUTS.get(name)
        row: dict[str, Any] = {"called_by": called.get(name, [])}
        if decl is None:
            failures.append(f"{name}: called on the certificate path by "
                            f"{', '.join(called[name])} and not declared in "
                            "data_os.CERTIFICATE_INPUTS")
            rows[name] = {**row, "verdict": "UNDECLARED"}
            continue
        lags = {s: data_os.declared_lag(s) for s in decl["sources"]}
        row.update({"module": decl["module"], "families": list(decl["families"]),
                    "route": decl.get("route"),
                    "sources": {s: (None if v is None else {
                        "lag_s": float(v["lag_s"]), "assumed": bool(v.get("assumed"))})
                        for s, v in lags.items()}})
        missing = sorted(s for s, v in lags.items() if v is None)
        if missing:
            failures.append(f"{name}: source(s) {', '.join(missing)} carry no publication lag")
        needs = any(v is not None and float(v["lag_s"]) > 0 and s not in data_os.BAR_SOURCES
                    for s, v in lags.items())
        applies = True
        if needs:
            mod = str(decl["module"])
            if mod not in funcs_of:
                try:
                    text = (root / mod).read_text("utf-8")
                    funcs_of[mod] = _functions(ast.parse(text), text)
                except (OSError, SyntaxError, ValueError):
                    funcs_of[mod] = {}
            funcs = funcs_of[mod]
            if name not in funcs:
                applies = False
                failures.append(f"{name}: declared in {mod} but no such function there")
            elif not _applies_lag(name, funcs):
                applies = False
                failures.append(f"{name}: reads a lagged source but applies no lag in its body "
                                "or in a module helper it calls")
        row["applies_lag"] = applies
        row["assumed"] = sorted(s for s, v in lags.items() if v and v.get("assumed"))
        row["verdict"] = "OK" if not missing and applies else "FAIL"
        rows[name] = row
    return {"providers": rows, "failures": failures,
            "verdict": "FAIL" if failures else "OK"}


def lag_census_doc(root: Path | None = None) -> dict[str, Any]:
    """PIT LAG CENSUS: every declared lag (assumed ones flagged), each registry's census and the
    certificate path's inputs -- the document the box publishes as PIT_LAG_CENSUS.json."""
    root = root or ROOT
    registries: dict[str, Any] = {}
    for rel in REGISTRIES:
        try:
            doc = json.loads((root / rel).read_text("utf-8"))
        except (OSError, ValueError):
            registries[rel] = {"status": data_os.UNMEASURED, "why": "absent or unreadable"}
            continue
        reg = doc.get("datasets") if isinstance(doc, dict) else None
        registries[rel] = (data_os.lag_census(reg) if isinstance(reg, dict) else
                           {"status": data_os.UNMEASURED, "why": "no `datasets` block"})
    return {"generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "publication_lags": {s: {k: e.get(k) for k in ("lag_s", "valid", "basis", "assumed",
                                                           "knowledge_column") if k in e}
                                 for s, e in sorted(PUBLICATION_LAGS.items())},
            "fred_series_lags": dict(sorted(data_os.FRED_SERIES_LAGS.items())),
            "assumed_flagged": data_os.assumed_lags(),
            "registries": registries,
            "certificate_inputs": certificate_fence(root)}


def read_floor(path: Path | None = None) -> set[str] | None:
    try:
        doc = json.loads((path or FLOOR).read_text("utf-8"))
    except (OSError, ValueError):
        return None
    names = doc.get("offenders") if isinstance(doc, dict) else None
    return set(names) if isinstance(names, list) else None


def write_floor(names: set[str], path: Path | None = None) -> None:
    (path or FLOOR).write_text(json.dumps({
        "_": ("KNOWN-BY-DATE FLOOR: research readers that joined an external dataset by valid "
              "date without a declared lag when the fence was built. Only SHRINKS: a module that "
              "routes through data_os / the bitemporal store drops out; a new offender fails "
              "scripts/check_known_by_date.py and is never added here."),
        "offenders": sorted(names)}, indent=1) + "\n", "utf-8")


def publish(doc: dict[str, Any] | None = None, floor: set[str] | None = None,
            out: Path | None = None, lag_out: Path | None = None) -> dict[str, Any]:
    """Write KNOWN_BY_DATE.json and PIT_LAG_CENSUS.json. The box's `pit_canaries` leg calls this,
    so both artifacts are produced on the machine that publishes them."""
    doc = doc if doc is not None else scan()
    floor = floor if floor is not None else (read_floor() or set())
    now = set(doc["offenders"])
    census = lag_census_doc()
    cert = census["certificate_inputs"]
    arrived = sorted(now - floor)
    producers = producer_census()
    doc.update({"floor": sorted(floor), "arrived": arrived, "healed": sorted(floor - now),
                "certificate_inputs": cert, "producers": producers,
                "verdict": ("FAIL" if arrived or cert["failures"]
                            or producers["verdict"] == "FAIL" else "OK")})
    for path, body in ((out or OUT, doc), (lag_out or LAG_OUT, census)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(body, indent=1, default=str), "utf-8")
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--update", action="store_true",
                    help="rewrite the floor to the healed (smaller) set; never adds a name")
    ap.add_argument("--init", action="store_true",
                    help="seal the floor from today's census; refuses if one exists")
    ap.add_argument("--init-producers", action="store_true",
                    help="seal the bitemporal producer floor; only when none exists")
    a = ap.parse_args(argv)
    doc = scan()
    now = set(doc["offenders"])
    floor = read_floor()
    if a.init:
        if floor is not None:
            print(f"REFUSING --init: {FLOOR.relative_to(ROOT)} exists; it only shrinks")
            return 1
        write_floor(now)
        print(f"sealed {FLOOR.relative_to(ROOT)} with {len(now)} offender(s)")
        return 0
    if floor is None:
        print(f"NO FLOOR: {FLOOR.relative_to(ROOT)} is absent or unreadable. A ratchet with "
              "nothing to ratchet against is not a ratchet: seal it with --init and commit it.")
        return 1
    if read_producer_floor() is None:
        print(f"NO PRODUCER FLOOR: {PRODUCER_FLOOR.relative_to(ROOT)} is absent or unreadable; "
              "seal it with --init-producers and commit it.")
        if a.init_producers:
            census = producer_census(floor=set())
            write_producer_floor({r for r, v in census["producers"].items()
                                  if v["class"] != "bitemporal"})
            print(f"sealed {PRODUCER_FLOOR.relative_to(ROOT)}")
            return 0
        return 1
    doc = publish(doc, floor)
    arrived, healed = doc["arrived"], doc["healed"]
    cert = doc["certificate_inputs"]
    prod = doc["producers"]
    if a.json:
        print(json.dumps(doc, indent=1, default=str))
    else:
        acc = doc["accounting"]
        print(f"known-by-date: {doc['readers']} reader(s) of {len(doc['sources'])} declared "
              f"source(s); {len(doc['routed'])} routed through a lag, {len(now)} offender(s) "
              f"(floor {len(floor)}), {len(healed)} healed; no-join: "
              f"{acc['no_join_routed_in_code']} routed in code, {acc['no_join_declared']} "
              f"declared, {acc['undeclared']} undeclared; certificate inputs "
              f"{cert['verdict']} ({len(cert['providers'])} provider(s))")
        for rel in arrived:
            print(f"  NEW OFFENDER {rel}: {doc['offenders'][rel]['why']}")
        for rel in healed:
            print(f"  healed: {rel}")
        for rel in sorted(doc["no_join"]["undeclared"]):
            print(f"  undeclared no-join reader (flagged): {rel}")
        for why in cert["failures"]:
            print(f"  CERTIFICATE INPUT: {why}")
        c = prod["counts"]
        print(f"producers: {prod['n']} macro/alt producer(s); {prod['pit_routed']} read through "
              f"the bitemporal store, {prod['not_pit_routed']} not (knowledge-stamped "
              f"{c['knowledge_stamped']}, lag-shift {c['lag_shift']}, declared {c['declared']}, "
              f"not point-in-time {c['not_pit']}); floor {len(prod['floor'])}, "
              f"{len(prod['healed'])} healed")
        for rel in prod["arrived"]:
            print(f"  NEW PRODUCER OUTSIDE THE STORE {rel}: {prod['producers'][rel]['class']}")
        for rel in prod["not_pit"]:
            print(f"  NOT POINT-IN-TIME {rel}: {prod['producers'][rel]['joins']}")
        for rel in prod["healed"]:
            print(f"  producer healed onto the store: {rel}")
    if a.update and healed and not arrived:
        write_floor(floor & now)
        print(f"  floor shrunk {len(floor)} -> {len(floor & now)} (commit it)")
    if a.update and prod["healed"] and not prod["arrived"]:
        pfloor = set(prod["floor"]) - set(prod["healed"])
        write_producer_floor(pfloor)
        print(f"  producer floor shrunk {len(prod['floor'])} -> {len(pfloor)} (commit it)")
    return 1 if arrived or cert["failures"] or prod["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
