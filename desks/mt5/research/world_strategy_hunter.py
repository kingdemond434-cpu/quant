#!/usr/bin/env python3
"""THE WORLD STRATEGY HUNTER -- every strategy shared or described anywhere, mapped, gapped, grown.

PRINCIPAL 2026-10-28/29 (hourly item 18): hunt every strategy shared or described anywhere --
forums, blogs, videos, social, messaging, repos, papers, code marketplaces, competitions, every
language and region -- widen breadth, coverage and depth every pass, and track coverage % against
100%.

A PLANNER OVER THE DEEP-FOREST MINER, NOT A SECOND MINER. The miner already reaches grounds by
route, extracts verbatim claims in 26 languages, dedupes on the mechanism key and queues one
deepening task per mechanism (the path the coverage steer and the true-duplicate dedup sit on).
What it lacked was a MAP to measure itself against. This organ:

  1. MAPS. `data/world_strategy_map.json` (data) declares countries, their languages and the
     kinds of place strategies are shared. A CELL is country x language x kind; each takes the
     best hunt-frontier outcome of its grounds: YIELDED > EMPTY > BLOCKED > NAMED_ONLY > GAP.
  2. GAPS. Non-worked cells are ranked (country prior x kind weight, primary language first) and
     rolled up per region, language and kind.
  3. GROWS. Mints native-language SEARCH grounds for the top GAP cells into
     `data/world_hunter_grounds.json`, which the miner loads beside its curated file; promotes
     EMERGENT PLACES (hosts the miner's own claims keep landing on that no ground names); and
     DEEPENS worked minted grounds with an instrument rotation.
  4. COUNTS. Place coverage (worked cells / map cells), strategy coverage (distinct mechanisms /
     Chao1 estimate, the closed form `source_frontier` uses) and NEW CIVILIZATIONS per pass.

THE DENOMINATOR IS A DECLARED MAP, NEVER "THE WEB", whose size is unmeasurable. The map only
GROWS (L1.50), so declaring more world LOWERS the figure; the cross product can only deflate it.
Languages the extractor cannot read are EXTRACTOR_GAP: named with their countries, never minted.

IT NEVER opens a socket (the miner owns every fetch, through polite_fetch: no login, paywall,
CAPTCHA or rate-limit bypass), adds a judge path, mints a hypothesis, removes or demotes a ground,
or throttles mining. A public claim is a hypothesis, never a cert.

    python desks/mt5/research/world_strategy_hunter.py            # one pass
    python desks/mt5/research/world_strategy_hunter.py --dry-run  # report only, mint nothing
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

DATA = DESK / "data"
MAP = DATA / "world_strategy_map.json"
CURATED = DATA / "deep_forest_sources.json"
#: The miner reads this beside its curated file (`deep_forest_miner._load_sources`).
MINTED = DATA / "world_hunter_grounds.json"
FRONTIER = DATA / "deep_forest_frontier.json"
CLAIMS = DATA / "deep_forest_claims.jsonl"
PASSES = DATA / "world_hunter_passes.jsonl"
REPORT = DESK / "reports" / "WORLD_STRATEGY_HUNT.json"

#: Grounds minted per pass for GAP cells. Not a cap on ideas: it paces minting to what the miner
#: can work, because a ground minted faster than any run reaches it is only a NAMED_ONLY row. The
#: whole map is minted inside a day at this rate, and `--max-new 0` mints every gap at once.
MAX_NEW_PER_PASS = 120
#: Distinct claims an unregistered host must carry before it becomes a ground of its own.
EMERGENT_MIN_CLAIMS = 2
#: Queries a minted ground keeps; deepening rotates the oldest out once it is full.
MAX_QUERIES = 8
#: Language-neutral MT5 instruments the deepening rotation walks, one per worked pass.
DEPTH_INSTRUMENTS = ("XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "GBPJPY", "AUDUSD", "NAS100",
                     "US30", "GER40", "XTIUSD", "XAGUSD", "USDCAD", "EURJPY", "US500")
MINTED_BY = "world_strategy_hunter"

#: Map kind -> the deep-forest `kind` a minted ground carries (the miner's evidence grading and the
#: scout roster both key on that vocabulary, so a minted ground must speak it).
FOREST_KIND = {"forum": "forum", "blog": "blog", "video": "video", "social": "social",
               "messaging": "public_messaging", "repo": "code", "paper": "research",
               "code_marketplace": "platform_native_strategy", "competition": "competition"}
#: Best outcome first. GAP = nothing registered; the rest are the hunt-frontier outcomes.
RANK = {"YIELDED": 4, "EMPTY": 3, "BLOCKED": 2, "NAMED_ONLY": 1, "GAP": 0}
WORKED = frozenset({"YIELDED", "EMPTY"})


# ------------------------------------------------------------------------------------ io
def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        lines = path.read_text("utf-8").splitlines()
    except OSError:
        return out
    for ln in lines:
        with contextlib.suppress(ValueError):
            row = json.loads(ln)
            if isinstance(row, dict):
                out.append(row)
    return out


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text, "utf-8")
    try:
        os.replace(tmp, path)
    except PermissionError:  # Windows: a reader holds the destination
        path.write_text(text, "utf-8")
        with contextlib.suppress(OSError):
            tmp.unlink()


def extractable_languages() -> frozenset[str]:
    """The languages `mechanism_claims` can extract a claim from; empty if libs is absent."""
    try:
        from libs.research import mechanism_claims as mc
        return frozenset(mc.LANGUAGES)
    except Exception:
        return frozenset()


# ------------------------------------------------------------------------------------ map
def load_world(path: Path) -> dict[str, Any]:
    """The map with compact rows expanded: countries as `country_columns` rows, vocab as lists
    in `vocab_keys` order. Dict-shaped entries are accepted as they are."""
    w = _read_json(path, {})
    if not isinstance(w, dict):
        return {}
    cols = list(w.get("country_columns") or [])
    countries = []
    for c in w.get("countries") or []:
        row = dict(zip(cols, c, strict=False)) if isinstance(c, list) else dict(c)
        iso = str(row.get("iso") or "")
        row.setdefault("market", "US" if iso == "global" else iso.upper())
        countries.append(row)
    keys = list(w.get("vocab_keys") or [])
    vocab = {lang: dict(zip(keys, v, strict=False)) if isinstance(v, list) else dict(v)
             for lang, v in (w.get("vocab") or {}).items()}
    return {**w, "countries": countries, "vocab": vocab}


def kind_of(ground: Mapping[str, Any], kinds: Mapping[str, Any]) -> str | None:
    """The map kind a registered ground belongs to, or None (datasets, macro, rulebooks ...:
    grounds that are not a place strategies are shared, so they sit outside the map)."""
    if ground.get("map_kind") in kinds:
        return str(ground["map_kind"])
    gk = str(ground.get("kind") or "")
    for k, spec in kinds.items():
        if gk == k or gk in (spec.get("from_ground_kinds") or ()):
            return str(k)
    return None


def country_of(ground: Mapping[str, Any]) -> str:
    region = str(ground.get("region") or "cn").lower()
    return "global" if region == "institutional" else region


def cell_key(iso: str, lang: str, kind: str) -> str:
    return f"{iso}|{lang}|{kind}"


def map_cells(world: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Every declared cell, with the prior the gap ranking reads."""
    kinds = world.get("kinds") or {}
    cells: dict[str, dict[str, Any]] = {}
    for c in world.get("countries") or []:
        langs = list(c.get("languages") or [])
        for i, lang in enumerate(langs):
            for kind, spec in kinds.items():
                cells[cell_key(c["iso"], lang, kind)] = {
                    "country": c["iso"], "country_name": c.get("name"),
                    "cluster": c.get("cluster"), "language": lang, "kind": kind,
                    "market": c.get("market") or str(c["iso"]).upper(),
                    "score": round(float(c.get("prior") or 0.5)
                                   * float(spec.get("weight") or 1.0)
                                   * (1.0 if i == 0 else 0.7), 4),
                    "grounds": [], "state": "GAP"}
    return cells


def _host(url: str) -> str:
    h = (urlparse(url).hostname or "").lower()
    return h[4:] if h.startswith("www.") else h


#: Hosts a ground reaches through a platform route rather than a `site` or `url` field.
ROUTE_HOSTS = {"bilibili": "bilibili.com", "sogou": "sogou.com", "juejin": "juejin.cn",
               "gitee": "gitee.com", "reddit": "reddit.com", "youtube": "youtube.com",
               "telegram": "t.me", "papers": "arxiv.org"}


def registered_hosts(grounds: Iterable[Mapping[str, Any]]) -> set[str]:
    hosts: set[str] = set()
    for g in grounds:
        if str(g.get("route") or "") in ROUTE_HOSTS:
            hosts.add(ROUTE_HOSTS[str(g["route"])])
        if g.get("site"):
            hosts.add(_host(f"https://{str(g['site']).split('/')[0]}"))
        for u in [g.get("url"), *(g.get("alt") or [])]:
            if u:
                hosts.add(_host(str(u)))
    hosts.discard("")
    return hosts


def place(world: Mapping[str, Any], grounds: list[dict[str, Any]],
          vectors: Mapping[str, Any], claims: list[dict[str, Any]]
          ) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    """Put every ground in its cell and give each cell its best measured outcome.

    A ground in a country or language the map does not declare still counts: its cell is ADDED
    (the map grows to fit the world the desk already reaches, never the reverse) and the count of
    such cells is reported so the map file can be widened by name.
    """
    kinds = world.get("kinds") or {}
    cells = map_cells(world)
    declared = len(cells)
    yielded_by_ground = Counter(str(r.get("ground") or "") for r in claims)
    off_map = 0
    for g in grounds:
        kind = kind_of(g, kinds)
        if kind is None:
            continue
        iso, lang = country_of(g), str(g.get("language") or "en")
        key = cell_key(iso, lang, kind)
        if key not in cells:
            off_map += 1
            cells[key] = {"country": iso, "country_name": iso, "cluster": g.get("cluster"),
                          "language": lang, "kind": kind, "market": str(g.get("market") or ""),
                          "score": 0.5, "grounds": [], "state": "GAP", "off_map": True}
        name = str(g.get("name") or "")
        v = vectors.get(name) or {}
        outcome = str(v.get("outcome") or "NAMED_ONLY") if isinstance(v, Mapping) else "NAMED_ONLY"
        if yielded_by_ground.get(name):
            outcome = "YIELDED"
        if outcome not in RANK:
            outcome = "NAMED_ONLY"
        cell = cells[key]
        cell["grounds"].append(name)
        if RANK[outcome] > RANK[cell["state"]]:
            cell["state"] = outcome
    return cells, {"declared": declared, "off_map": off_map}


# ------------------------------------------------------------------------------- coverage
def chao1(counts: Iterable[int]) -> dict[str, Any]:
    """Observed distinct mechanisms and the Chao1 estimate of how many the tellings imply.

    f1 = mechanisms told once, f2 = told twice. With no doubleton the bias-corrected branch
    f1(f1-1)/2 is used -- the branch a thinly read world is nearly always in.
    """
    c = [int(x) for x in counts if int(x) > 0]
    s_obs = len(c)
    f1, f2 = sum(1 for x in c if x == 1), sum(1 for x in c if x == 2)
    if s_obs == 0:
        return {"observed": 0, "estimated": None, "coverage_pct": None, "f1": 0, "f2": 0,
                "verdict": "UNMEASURED: the claims ledger holds no mechanism yet"}
    unseen = (f1 * f1) / (2.0 * f2) if f2 else f1 * (f1 - 1) / 2.0
    est = s_obs + unseen
    return {"observed": s_obs, "estimated": round(est, 1),
            "coverage_pct": round(100.0 * s_obs / est, 2) if est else None,
            "f1": f1, "f2": f2}


def rollup(cells: Mapping[str, Mapping[str, Any]], by: str) -> dict[str, dict[str, Any]]:
    out: dict[str, Counter[str]] = defaultdict(Counter)
    for c in cells.values():
        out[str(c[by])][c["state"]] += 1
        out[str(c[by])]["cells"] += 1
    rows: dict[str, dict[str, Any]] = {}
    for k, cnt in out.items():
        worked = sum(cnt[s] for s in WORKED)
        rows[k] = {"cells": cnt["cells"], "worked": worked, "yielded": cnt["YIELDED"],
                   "named_only": cnt["NAMED_ONLY"], "blocked": cnt["BLOCKED"],
                   "gap": cnt["GAP"],
                   "coverage_pct": round(100.0 * worked / cnt["cells"], 1)
                   if cnt["cells"] else 0.0}
    return dict(sorted(rows.items(), key=lambda kv: (kv[1]["coverage_pct"], -kv[1]["cells"])))


# ---------------------------------------------------------------------------------- growth
def _queries(world: Mapping[str, Any], lang: str, kind: str) -> list[str]:
    vocab = (world.get("vocab") or {}).get(lang) or {}
    out: list[str] = []
    for t in (world.get("kinds") or {}).get(kind, {}).get("templates") or []:
        with contextlib.suppress(KeyError):
            q = str(t).format(**vocab)
            if q not in out:
                out.append(q)
    return out


def mint_for_cell(world: Mapping[str, Any], cell: Mapping[str, Any], now: str
                  ) -> list[dict[str, Any]]:
    """One search ground per platform site of the cell's kind (one site-less ground if it has
    none), in the deep-forest grounds file's own row shape."""
    kind, lang, iso = cell["kind"], cell["language"], cell["country"]
    queries = _queries(world, lang, kind)
    if not queries:
        return []
    sites = list((world.get("kinds") or {}).get(kind, {}).get("sites") or []) or [""]
    out = []
    for site in sites:
        g: dict[str, Any] = {
            "name": f"WSH {iso}/{lang}/{kind}" + (f"@{site}" if site else ""),
            "region": iso, "cluster": cell.get("cluster") or "west", "language": lang,
            "route": "search", "kind": FOREST_KIND.get(kind, kind), "map_kind": kind,
            "weight": round(max(0.3, min(1.2, float(cell.get("score") or 0.5))), 2),
            "why": (f"world strategy hunter: GAP cell {cell_key(iso, lang, kind)} "
                    f"({cell.get('country_name')}); native-language strategy queries"),
            "queries": list(queries), "market": cell.get("market") or "",
            "minted_by": MINTED_BY, "minted_utc": now, "cell": cell_key(iso, lang, kind),
            "depth": 0}
        if site:
            g["site"] = site
        out.append(g)
    return out


def _known(host: str, hosts: set[str]) -> bool:
    """A host is registered when it, or any parent domain of it, is (zhuanlan.zhihu.com is
    reached by the zhihu.com ground)."""
    parts = host.split(".")
    return any(".".join(parts[i:]) in hosts for i in range(len(parts) - 1))


def emergent_places(claims: list[dict[str, Any]], hosts: set[str], minted_names: set[str],
                    now: str, min_claims: int = EMERGENT_MIN_CLAIMS) -> list[dict[str, Any]]:
    """Hosts the miner's own claims keep landing on that no ground names: places nobody declared.

    Each becomes a search ground with `site=` that host, in the language, region and kind of the
    claims that found it. A host already registered (as a site, a url or an alt) is never minted.
    """
    by_host: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in claims:
        h = _host(str(r.get("url") or ""))
        if h and not _known(h, hosts):
            by_host[h].append(r)
    out = []
    for h, rows in sorted(by_host.items()):
        distinct = {str(r.get("claim_hash") or r.get("claim") or "") for r in rows}
        name = f"WSH emergent {h}"
        if len(distinct) < min_claims or name in minted_names:
            continue
        lang = Counter(str(r.get("lang") or r.get("language") or "en") for r in rows
                       ).most_common(1)[0][0]
        region = Counter(str(r.get("region") or "global") for r in rows).most_common(1)[0][0]
        cluster = Counter(str(r.get("cluster") or "west") for r in rows).most_common(1)[0][0]
        kind = Counter(str(r.get("ground_kind") or "blog") for r in rows).most_common(1)[0][0]
        titles = [str(r.get("title") or "")[:60] for r in rows if r.get("title")][:3]
        out.append({"name": name, "region": region, "cluster": cluster, "language": lang,
                    "route": "search", "kind": kind, "site": h, "weight": 0.9,
                    "queries": [t for t in titles if t] or [h],
                    "why": (f"world strategy hunter: EMERGENT place -- {len(distinct)} distinct "
                            f"claims landed on {h} and no ground named it"),
                    "minted_by": MINTED_BY, "minted_utc": now, "emergent": True, "depth": 0})
    return out


def deepen(world: Mapping[str, Any], g: dict[str, Any], vectors: Mapping[str, Any]) -> bool:
    """Add the next instrument query to a minted ground the miner has already worked."""
    v = vectors.get(str(g.get("name"))) or {}
    attempt = str(v.get("last_attempt") or "") if isinstance(v, Mapping) else ""
    if not attempt or attempt == g.get("deepened_after"):
        return False
    vocab = (world.get("vocab") or {}).get(str(g.get("language"))) or {}
    word = vocab.get("strategy") or "strategy"
    depth = int(g.get("depth") or 0)
    q = f"{word} {DEPTH_INSTRUMENTS[depth % len(DEPTH_INSTRUMENTS)]}"
    qs = [x for x in (g.get("queries") or []) if x != q] + [q]
    g["queries"] = qs[-MAX_QUERIES:]
    g["depth"], g["deepened_after"] = depth + 1, attempt
    return True


# -------------------------------------------------------------------------------- the pass
def run(*, dry_run: bool = False, max_new: int = MAX_NEW_PER_PASS,
        now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    stamp = now.isoformat()
    world = load_world(MAP)
    if not world.get("countries"):
        empty: dict[str, Any] = {"generated_utc": stamp,
                                 "verdict": f"UNMEASURED: no world map at {MAP}"}
        if not dry_run:
            _atomic(REPORT, json.dumps(empty, indent=1))
        return empty
    curated = list((_read_json(CURATED, {}) or {}).get("grounds") or [])
    minted_doc = _read_json(MINTED, {}) or {}
    minted = [g for g in (minted_doc.get("grounds") or []) if isinstance(g, dict)]
    vectors = (_read_json(FRONTIER, {}) or {}).get("vectors") or {}
    claims = _jsonl(CLAIMS)
    readable = set(world.get("vocab") or {}) & (extractable_languages() or set(
        world.get("vocab") or {}))

    cells_before, _ = place(world, curated + minted, vectors, claims)
    gaps_before = {k for k, c in cells_before.items() if c["state"] == "GAP"}

    # GROW: deepen what has been worked, promote emergent places, mint the top GAP cells.
    deepened = sum(deepen(world, g, vectors) for g in minted)
    names = {str(g.get("name")) for g in curated + minted}
    emergent = emergent_places(claims, registered_hosts(curated + minted), names, stamp)
    new_grounds: list[dict[str, Any]] = list(emergent)
    extractor_gap_cells = [c for c in cells_before.values()
                           if c["state"] == "GAP" and c["language"] not in readable]
    mintable = sorted((c for c in cells_before.values()
                       if c["state"] == "GAP" and c["language"] in readable),
                      key=lambda c: (-c["score"], c["country"], c["language"], c["kind"]))
    if max_new > 0:
        mintable = mintable[:max_new]
    for c in mintable:
        new_grounds.extend(g for g in mint_for_cell(world, c, stamp) if g["name"] not in names)
    minted_all = minted + new_grounds

    cells, shape = place(world, curated + minted_all, vectors, claims)
    total = len(cells)
    states = Counter(c["state"] for c in cells.values())
    worked = sum(states[s] for s in WORKED)
    registered = total - states["GAP"]
    new_cells = sorted(k for k in gaps_before if cells.get(k, {}).get("state") != "GAP")
    new_pairs = sorted({f"{k.split('|')[0]}|{k.split('|')[1]}" for k in new_cells}
                       - {f"{c['country']}|{c['language']}" for c in cells_before.values()
                          if c["state"] != "GAP"})
    strategy = chao1(Counter(str(r.get("mechanism_key") or "") for r in claims
                             if r.get("mechanism_key")).values())
    ex_langs: dict[str, list[str]] = defaultdict(list)
    for c in extractor_gap_cells:
        if c["country"] not in ex_langs[c["language"]]:
            ex_langs[c["language"]].append(c["country"])
    gap_list = sorted((c for c in cells.values() if c["state"] not in WORKED),
                      key=lambda c: (RANK[c["state"]], c["language"] not in readable, -c["score"]))
    report: dict[str, Any] = {
        "generated_utc": stamp,
        "target": "100% coverage: every forum, site and discussion worldwide, every strategy "
                  "shared or described, anything MT5-related and testable (principal "
                  "2026-10-28/29, hourly item 18)",
        "coverage": {
            "place_pct": round(100.0 * worked / total, 2) if total else 0.0,
            "place_denominator": (f"{total} cells of the declared world map (country x language"
                                  " x kind); the map only grows, so this falls when more world "
                                  "is declared -- it is never the web's true size, which is "
                                  "unmeasurable"),
            "registered_pct": round(100.0 * registered / total, 2) if total else 0.0,
            "yielded_pct": round(100.0 * states["YIELDED"] / total, 2) if total else 0.0,
            "strategy": strategy,
            "strategy_denominator": "Chao1 over the deep-forest claims ledger's mechanism keys",
        },
        "cells": {"total": total, "declared": shape["declared"], "off_map": shape["off_map"],
                  "by_state": dict(states)},
        "this_pass": {
            "new_civilizations": len(new_cells) + len(emergent),
            "new_cells": len(new_cells), "new_country_language_pairs": len(new_pairs),
            "emergent_places": [g["site"] for g in emergent],
            "grounds_minted": len(new_grounds), "grounds_deepened": deepened,
            "minted_total": len(minted_all), "dry_run": dry_run},
        "by_region": rollup(cells, "country"),
        "by_language": rollup(cells, "language"),
        "by_kind": rollup(cells, "kind"),
        "gap_list": [{"cell": cell_key(c["country"], c["language"], c["kind"]),
                      "country": c.get("country_name"), "state": c["state"],
                      "score": c["score"], "grounds": c["grounds"][:4],
                      "extractor_gap": c["language"] not in readable}
                     for c in gap_list[:300]],
        "extractor_gaps": {lang: {"countries": sorted(cs),
                                  "cells": sum(1 for c in extractor_gap_cells
                                               if c["language"] == lang)}
                           for lang, cs in sorted(ex_langs.items())},
        "rules": "no socket opened here; every fetch is the deep-forest miner's through "
                 "polite_fetch (no login, paywall, CAPTCHA or rate-limit bypass); every claim "
                 "goes through the mechanism-key dedup and the coverage steer to the gauntlet; "
                 "a public claim is never a cert; nothing is removed or demoted",
    }
    if not dry_run:
        _atomic(MINTED, json.dumps({
            "note": "Grounds minted by research/world_strategy_hunter.py for GAP cells of "
                    "data/world_strategy_map.json and for emergent places. The deep-forest miner "
                    "loads them beside deep_forest_sources.json. Never edited by hand; a ground "
                    "is never removed (widen the map instead).",
            "updated_utc": stamp, "grounds": minted_all}, ensure_ascii=False, indent=1))
        _atomic(REPORT, json.dumps(report, ensure_ascii=False, indent=1))
        PASSES.parent.mkdir(parents=True, exist_ok=True)
        with PASSES.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"utc": stamp, **report["this_pass"],
                                 "place_pct": report["coverage"]["place_pct"],
                                 "strategy_pct": strategy.get("coverage_pct"),
                                 "cells": total}) + "\n")
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-new", type=int, default=MAX_NEW_PER_PASS,
                    help="GAP cells minted this pass (0 = every gap)")
    a = ap.parse_args(argv)
    rep = run(dry_run=a.dry_run, max_new=a.max_new)
    cov, tp = rep.get("coverage") or {}, rep.get("this_pass") or {}
    print(json.dumps({"place_pct": cov.get("place_pct"),
                      "strategy_pct": (cov.get("strategy") or {}).get("coverage_pct"),
                      "cells": (rep.get("cells") or {}).get("total"),
                      "new_civilizations": tp.get("new_civilizations"),
                      "grounds_minted": tp.get("grounds_minted"),
                      "verdict": rep.get("verdict")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
