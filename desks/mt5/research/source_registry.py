"""W1 -- ONE SOURCE REGISTRY: what the desk reads, what reading it COSTS, and what it ever produced.

THE GAP THIS CLOSES. The desk reads 500 declared grounds, 76 seat directories and a dozen internal
producers, and names them in three vocabularies that never meet: the forest miner stamps a CLUSTER
(`deep_forest_ru`), the provenance ledger a GROUND (`七禾网`), the hypothesis graph a SCIENTIST
(`miner:anomalies`, `external`), the credit report whatever the docket row said. Nothing joins
them, so nobody can answer the only question that matters about a source: over its whole life,
what has it cost and what has it produced?

CREDIBILITY AND ALPHA YIELD ARE SEPARATE VARIABLES, and conflating them is the failure this organ
exists to prevent. A central bank's statistics page is maximally credible and may have produced
nothing testable; an anonymous forum post with a stated rule and a stated horizon may be the origin
of a certified sleeve. Prestige earns a source a licence note and a low cost; it never earns it
budget. BUDGET FOLLOWS MEASURED YIELD -- independent survivors per lead, credited by realised R.

WHAT A LEAD IS, said once because the three ledgers do not overlap. `mined_sources.jsonl` holds one
row per extracted claim keyed by the GROUND that yielded it; `hypothesis_graph.jsonl` one row per
hypothesis keyed by the SCIENTIST that proposed it; the docket one row per COMPILED candidate. A
ground's leads come from the first, a seat's from the second, and a source almost never appears in
both -- that disjointness is itself the finding, and it is published, not smoothed over.

VOLUME IS A COST, NEVER AN OUTPUT (libs.research.source_roi): a ground returning ten thousand pages
and no independent survivor is worse than one returning fifty and one, because it also spends
triage -- the scarcest input in the chain -- and every redundant candidate it mints charges the
family-wise error budget every FX and metals cell then has to clear. And ZERO IS NEITHER A COST NOR
A VERDICT: a kind with no declared price is UNMEASURED and its ROI is None, never 0.0, because 0.0
reads as "measured and worthless" and over a short window that is almost always false (L1.28a). A
source with nothing certified yet is thin, not barren, and the 20% exploration floor is what stops
the judgement confirming itself (L1.52).

IT NEVER INVENTS A URL. The native-language map reports which of the thirteen tracked languages
have a ground ON FILE and which have none, and a gap is handed to the crawler as a gap. No
crypto-exchange ground is ever registered or funded (MT5 universe mandate).

    python desks/mt5/research/source_registry.py [--dry-run]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import tempfile
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import bandit  # noqa: E402

GROUNDS = DESK / "data" / "deep_forest_sources.json"
PROVENANCE = DESK / "data" / "mined_sources.jsonl"
GRAPH = DESK / "data" / "hypothesis_graph.jsonl"
DOCKET = DESK / "data" / "hypotheses" / "external_survivors.json"
GATES = DESK / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
CREDIT = DESK / "reports" / "CREDIT_ASSIGNMENT.json"
NOVELTY = DESK / "reports" / "NOVELTY_GATE.json"
UNSEEN = DESK / "reports" / "UNSEEN_FRONTIER.json"
REGISTRY = DESK / "data" / "source_registry.json"
REPORT = DESK / "reports" / "SOURCE_REGISTRY.json"
SEAT_ROOTS = (DESK / "data" / "intelligence", ROOT / "data" / "intelligence")

#: THE TRACKED NATIVE LANGUAGES. One with no ground on file is a COVERAGE GAP the crawler can act
#: on -- it is listed, never filled with a guessed URL.
NATIVE_LANGUAGES: tuple[str, ...] = ("zh", "ja", "ko", "ru", "ar", "pt", "es", "tr", "hi", "vi",
                                     "fr", "de", "id")
#: A ground's declared kind -> the registry's kind vocabulary.
KIND_MAP: dict[str, str] = {
    "dataset": "official", "macro": "official", "academic": "scholarly", "research": "scholarly",
    "code": "code", "notebook": "code", "forum": "forum", "qa": "forum", "community": "forum",
    "social": "forum", "competition": "competition", "column": "news", "interview": "web",
    "blog": "web", "video": "web", "archive": "web",
}
#: Seats whose donations are a broker's own track record, an official release, a code host or a
#: news wire rather than a model seat. Anything not named here is a `seat`: it spends credit too.
SEAT_KIND: dict[str, str] = {}
for _names, _kind in (
    (("amarkets broker_swaps collective2 darwinex duplitrade equiti_copy fbs_tape fxblue "
      "followme_cn fxmerge hfm_pamm instaforex_copy litefinance mylivefx_br myfxbook_outlook "
      "octa_masters roboforex_copyfx share4you swap_table"), "broker"),
    ("academic arxiv_qfin literature", "scholarly"),
    ("bis_speeches central_banks sec_edgar cot ff_calendar_vintage", "official"),
    (("github github_topics quantconnect mql5 mql5_catalog mql5_prospector mql5_signals "
      "mql5_reputation mql5_survivors tradingview_scripts"), "code"),
    ("forexfactory forexpeacearmy reddit quant_se propfirm_boards forextsd_cdx", "forum"),
    ("investing", "news"), ("youtube tradingview world", "web"),
):
    SEAT_KIND.update(dict.fromkeys(_names.split(), _kind))

#: DECLARED COST OF ONE LEAD in triage units (fetch + parse + dedupe + the licence argument made
#: before a line is reimplemented): `official` is one structured fetch with no triage argument,
#: `forum` the highest burn, `code` pays a licence check, `seat` spends credit as well as compute.
#: A price list, not a measurement, documented so it can be argued with. `unknown` is UNMEASURED --
#: never 0.0, which would hand the budget to whatever the desk had not bothered to cost.
COST_PER_LEAD: dict[str, float | None] = {
    "official": 1.0, "news": 1.2, "web": 1.5, "competition": 2.0, "scholarly": 2.0,
    "broker": 2.0, "code": 2.5, "forum": 3.0, "seat": 4.0, "unknown": None,
}
#: How the ground is REACHED multiplies that price: a rendered fetch costs more than an HTTP GET, a
#: search route pays for the query as well as the page. `unreachable` is UNMEASURED -- the ground is
#: recorded so the gap stays visible (OP-041) and is never funded.
ROUTE_COST: dict[str, float | None] = {
    "http": 1.0, "rss": 0.8, "foreign": 1.0, "juejin": 1.0, "gitee": 1.0, "reddit": 1.2,
    "telegram": 1.2, "wayback": 1.3, "papers": 1.4, "nitter": 1.5, "search": 1.6, "sogou": 1.6,
    "youtube": 2.0, "bilibili": 2.0, "render": 2.5, "unreachable": None,
}
#: Which organ crawls which ground, read off the run wiring: the hourly cycle carries legs
#: `deep_forest`, `world_crawler`, `mine`; `repo_miner` runs from the daily cycle only.
CLOCK_DEEP_FOREST, CLOCK_SEAT, CLOCK_REPO, UNSCHEDULED = (
    "hourly:deep_forest", "hourly:mine", "daily:repo_miner", "UNSCHEDULED")

WILSON_Z = 1.96
#: Pseudo-leads added at the desk's POOLED yield before the bound is taken, so a source with almost
#: no history is judged mostly by what the desk knows in general and earns its own opinion only by
#: being measured. Large counts swamp it.
PRIOR_LEADS = 25.0
#: Below this many leads a source is THIN: its silence carries no information, so it is funded from
#: the exploration floor rather than ranked. EXPLORATION_SHARE never follows measured yield (L1.52).
#: SOFTMAX_K sharpens roi/roi_max: the best source gets e^3 ~ 20x a measured-zero one, never all.
THIN_LEADS, EXPLORATION_SHARE, SOFTMAX_K = 20, 0.20, 3.0
CREDIT_CLIP = (0.5, 2.0)
#: Unicode-aware: an ASCII-only slug collapsed every CJK-named ground onto one id.
_SLUG = re.compile(r"\W+", re.UNICODE)



def _read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def _iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    try:
        with Path(path).open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    row = json.loads(line) if line.strip() else None
                except Exception:
                    continue
                if isinstance(row, dict):
                    yield row
    except OSError:
        return


def _atomic(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, ensure_ascii=False, indent=1, default=str)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        try:
            os.replace(tmp, path)
        except PermissionError:
            # A read-only destination raises WinError 5 on the box and nothing on POSIX. The desk
            # has lost a fix to exactly this before; write through rather than die.
            path.write_text(text, encoding="utf-8")
            Path(tmp).unlink(missing_ok=True)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _slug(name: Any) -> str:
    raw = str(name or "").strip()
    out = _SLUG.sub("_", raw.lower()).strip("_")[:60]
    return out or ("x" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10] if raw else "unnamed")


def _unique(sid: str, rows: dict[str, dict[str, Any]], name: str) -> str:
    """Never let two different sources share one id: that is the merge this registry exists to
    prevent, and a slug collision is exactly how it would happen without anyone noticing."""
    if sid not in rows or rows[sid].get("name") == name:
        return sid
    return f"{sid}_{hashlib.sha1(name.encode('utf-8')).hexdigest()[:6]}"


def wilson_lower(k: float, n: float, z: float = WILSON_Z) -> float:
    """95% lower bound on a rate. Wilson, because these rates are tiny and the normal interval goes
    negative and meaningless at these counts. Fractional counts allowed (shrunk counts)."""
    n = max(0.0, float(n))
    k = min(max(0.0, float(k)), n)
    if n <= 0:
        return 0.0
    p, denom = k / n, 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    return max(0.0, centre - (z / denom) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)))


def _rep(k: float | None, n: float | None) -> dict[str, Any] | None:
    """A reputation entry carries its n: a bound without its sample size invites misreading."""
    if k is None or n is None:
        return None
    return {"p": round(wilson_lower(k, n), 6), "k": round(float(k), 3), "n": int(n)}


def _credit_factor(realised_r: float, n_trades: int) -> float:
    """Realised R as a bounded multiplier on expected yield, shrunk by trade count toward 1.0. The
    bandit already owns this semantic; reuse it so the two can never disagree in direction."""
    fn = getattr(bandit, "_credit_factor", None)
    if callable(fn):
        try:
            return float(fn(float(realised_r), int(n_trades)))
        except Exception:
            pass
    n = max(0, int(n_trades))
    if n <= 0:
        return 1.0
    f = 1.0 + (float(realised_r) / n) * (n / (n + 30.0)) * 2.0
    return min(max(f, CREDIT_CLIP[0]), CREDIT_CLIP[1])



def _ground_url(g: dict[str, Any]) -> str | None:
    alt = g.get("alt")
    return (str(g["url"]) if g.get("url") else
            str(alt[0]) if isinstance(alt, list) and alt else
            f"site:{g['site']}" if g.get("site") else None)


def _licence_note(g: dict[str, Any]) -> str:
    kind = KIND_MAP.get(str(g.get("kind")), "web")
    if str(g.get("route")) == "unreachable":
        return ("NOT FETCHABLE -- recorded so the gap is visible, never routed around "
                f"({g.get('why') or 'no reason on file'})")
    if g.get("snippets_only"):
        return "SEARCH-INDEX SNIPPETS ONLY (OP-041: robots.txt names this agent family)"
    if kind == "code":
        return "REPO LICENCE READ BEFORE ANY REUSE; concepts reimplemented, code never copied"
    if kind == "official":
        return "PUBLIC OFFICIAL RELEASE; cite the release page"
    return "WEB-PUBLIC; concept reimplemented independently, provenance cited, nothing copied"


def _cost_of(kind: str, route: str | None) -> float | None:
    base = COST_PER_LEAD.get(kind)
    mult = ROUTE_COST.get(str(route), 1.0) if route else 1.0
    return None if base is None or mult is None else round(base * mult, 3)


def _row(sid: str, **kw: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "source_id": sid, "name": kw.get("name") or sid, "kind": kw.get("kind") or "unknown",
        "language": kw.get("language"), "region": kw.get("region"),
        "licence_note": kw.get("licence_note") or "UNDECLARED -- declare terms before any reuse",
        "url": kw.get("url"), "ground": kw.get("ground"), "route": kw.get("route"),
        "arm": bandit.arm_of(kw.get("arm_source") or sid),
        "fetch_clock": kw.get("fetch_clock") or UNSCHEDULED,
        "aliases": sorted({str(a) for a in kw.get("aliases") or [] if a}),
    }
    row["cost"] = _cost_of(row["kind"], row["route"])
    if row["cost"] is None:
        row["cost_note"] = "UNMEASURED -- no declared price for this kind/route. Never read as 0."
    if kw.get("task"):
        row["task"] = kw["task"]
    return row


def _seat_activity(p: Path) -> tuple[int, str | None, str | None]:
    """File count and mtime span of a seat's donations. Stat only -- parsing 266 files per seat to
    learn the seat is alive would cost more than everything else in this organ combined."""
    times: list[float] = []
    n = 0
    try:
        with os.scandir(p) as it:
            for e in it:
                if e.is_file() and e.name.endswith((".json", ".jsonl")):
                    n += 1
                    if len(times) < 5000:
                        times.append(e.stat().st_mtime)
    except OSError:
        return 0, None, None
    if not times:
        return n, None, None

    def iso(t: float) -> str:
        return datetime.fromtimestamp(t, tz=UTC).isoformat(timespec="seconds")

    return n, iso(min(times)), iso(max(times))


def seed() -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """The declared population: every ground, every forest cluster, every seat directory."""
    rows: dict[str, dict[str, Any]] = {}
    doc = _read_json(GROUNDS, {}) or {}
    _reg, _gr = doc.get("regions"), doc.get("grounds")
    regions: dict[str, Any] = _reg if isinstance(_reg, dict) else {}
    grounds: list[Any] = _gr if isinstance(_gr, list) else []
    clusters: set[str] = set()
    for g in grounds:
        if not isinstance(g, dict):
            continue
        region = str(g.get("region") or "")
        clusters.add(str(g.get("cluster") or (regions.get(region) or {}).get("cluster") or region))
        sid = _unique(f"ground:{region or 'na'}:{_slug(g.get('name'))}", rows,
                      str(g.get("name")))
        rows[sid] = _row(sid, name=str(g.get("name")), language=g.get("language"), region=region,
                         kind=KIND_MAP.get(str(g.get("kind")), "web"),
                         licence_note=_licence_note(g), url=_ground_url(g),
                         ground=str(g.get("name")), route=str(g.get("route") or "http"),
                         arm_source="deep_forest", fetch_clock=CLOCK_DEEP_FOREST,
                         aliases=[str(g.get("name")), _slug(g.get("name"))])
        rows[sid]["weight"] = g.get("weight")
    heads: dict[str, list[str]] = {}
    for sid, r in rows.items():
        head = str(r["name"]).split()[0] if str(r["name"]).split() else ""
        if head and head != r["name"]:
            heads.setdefault(head, []).append(sid)
    for head, owners in heads.items():
        if len(owners) == 1:
            rows[owners[0]]["aliases"] = sorted({*rows[owners[0]]["aliases"], head})
    for cluster in sorted(c for c in clusters if c):
        name = "deep_forest" if cluster == "cn" else f"deep_forest_{cluster}"
        rows[f"src:{name}"] = _row(
            f"src:{name}", name=name, kind="web", region=cluster, route="http",
            ground=f"the {cluster} forest cluster ({GROUNDS.name})", arm_source=name,
            licence_note="WEB-PUBLIC; per-ground terms live on the ground's own row",
            fetch_clock=CLOCK_DEEP_FOREST, aliases=[name])
    for root in SEAT_ROOTS:
        try:
            seats = sorted(p for p in root.iterdir() if p.is_dir())
        except OSError:
            continue
        for p in seats:
            sid = f"seat:{p.name}"
            if sid in rows:
                continue
            rows[sid] = _row(sid, name=p.name, kind=SEAT_KIND.get(p.name, "seat"), route="http",
                             ground=str(p), arm_source=p.name, fetch_clock=CLOCK_SEAT,
                             licence_note="seat donation; provenance carried on the donated row",
                             aliases=[p.name, f"miner:{p.name}", sid])
            files, first, last = _seat_activity(p)
            rows[sid]["n_donation_files"], rows[sid]["_seen"] = files, (first, last)
    return rows, {"n_grounds": len(grounds), "n_clusters": len(clusters),
                  "n_regions": len(regions), "n_seat_roots": len(SEAT_ROOTS)}



def _index(rows: dict[str, dict[str, Any]]) -> dict[str, str]:
    idx: dict[str, str] = {}
    for sid, r in rows.items():
        idx.setdefault(sid, sid)
        for a in r.get("aliases") or []:
            idx.setdefault(str(a), sid)
    return idx


def _resolve(raw: Any, rows: dict[str, dict[str, Any]], idx: dict[str, str]) -> str:
    """A stamped source string -> a registry row. An unmatched string is REGISTERED as kind
    `unknown` with a task to declare it; it is never dropped and never folded into one bucket."""
    s = str(raw or "").strip() or "UNATTRIBUTED"
    if s in idx:
        return idx[s]
    parts = s.split(":")
    if len(parts) >= 2 and parts[0] in ("miner", "seat", "src", "ground") and parts[1] in idx:
        return idx[parts[1]]
    if parts[0] in idx:
        return idx[parts[0]]
    key = ":".join(parts[:2]) if parts[0] in ("miner", "seat") and len(parts) > 1 else parts[0]
    if "/" in s and not s.startswith(("http", "src:")):     # owner/repo, from repo_miner
        sid = _unique(f"repo:{_slug(s)}", rows, s)
        rows.setdefault(sid, _row(sid, name=s, kind="code", route="http", ground=s,
                                  url=f"https://github.com/{s}", arm_source="repo_miner",
                                  fetch_clock=CLOCK_REPO, aliases=[s],
                                  licence_note=("REPO LICENCE READ BEFORE ANY REUSE; concepts "
                                                "reimplemented, code never copied")))
        idx[s] = sid
        return sid
    sid = _unique(f"src:{_slug(key)}", rows, key)
    if sid not in rows:
        rows[sid] = _row(sid, name=key, kind="unknown", route=None, arm_source=key,
                         fetch_clock=UNSCHEDULED, aliases=[key, s],
                         task=("DECLARE THIS SOURCE: no ground on file. Give it a kind, a licence "
                               "note, a fetch clock and a cost in deep_forest_sources.json or the "
                               "seat map, or the budget cannot price what it already reads."))
    else:
        rows[sid]["aliases"] = sorted({*rows[sid].get("aliases", []), s})
    idx[s] = sid
    return sid


def _blank() -> dict[str, Any]:
    return {"n_leads": 0, "n_novel": None, "n_testable": 0, "n_certified": 0,
            "n_independent_certified": None, "realised_r": None, "n_trades": 0,
            "n_certificates": 0, "first_seen": None, "last_seen": None}


def _touch(c: dict[str, Any], at: Any) -> None:
    at = str(at or "")[:32]
    if at:
        c["first_seen"] = min(c["first_seen"] or at, at)
        c["last_seen"] = max(c["last_seen"] or at, at)


def _novel_by_source(resolve: Callable[[Any], str]) -> tuple[dict[str, int], str]:
    """Per-source novel counts from NOVELTY_GATE.json, tolerantly. It publishes `by_dimension` and
    a `sample` today and no per-source block; when that is what is on disk, novelty is UNMEASURED
    per source and SAYS so rather than being imputed from the desk-wide rate."""
    doc = _read_json(NOVELTY, {}) or {}
    out: dict[str, int] = {}
    if isinstance(doc.get("by_source"), dict):
        for k, v in doc["by_source"].items():
            n = v.get("novel", v.get("n_novel")) if isinstance(v, dict) else v
            if isinstance(n, (int, float)) and not isinstance(n, bool):
                out[resolve(k)] = out.get(resolve(k), 0) + int(n)
        if out:
            return out, "NOVELTY_GATE.by_source"
    for key in ("rows", "sample", "cells"):
        seq = [r for r in doc.get(key) or [] if isinstance(r, dict) and r.get("source")]
        if not seq:
            continue
        for r in seq:
            if r.get("novel") or str(r.get("verdict")).upper() == "NOVEL":
                out[resolve(r["source"])] = out.get(resolve(r["source"]), 0) + 1
        return out, f"NOVELTY_GATE.{key}[].source"
    return {}, "UNMEASURED -- NOVELTY_GATE.json carries no per-source block"


def _unseen_by_source(resolve: Callable[[Any], str]) -> tuple[dict[str, float], str]:
    """Per-source unseen-mechanism estimates from UNSEEN_FRONTIER.json (another organ writes it).
    Tolerant of three shapes; absence is UNMEASURED, never zero."""
    doc = _read_json(UNSEEN, None)
    if doc is None:
        return {}, "UNMEASURED -- UNSEEN_FRONTIER.json absent"
    out: dict[str, float] = {}
    blocks: list[Any] = [doc] + ([doc[k] for k in ("by_source", "sources", "rows", "grounds")
                                  if k in doc] if isinstance(doc, dict) else [])
    def num(v: Any) -> bool:
        return isinstance(v, (int, float)) and not isinstance(v, bool)

    for block in blocks:
        pairs = (block.items() if isinstance(block, dict) else
                 [((r.get("source_id") or r.get("source") or r.get("ground")), r)
                  for r in block if isinstance(r, dict)] if isinstance(block, list) else [])
        for k, v in pairs:
            val = v.get("unseen_estimate", v.get("unseen")) if isinstance(v, dict) else v
            if k and num(val):
                out[resolve(k)] = float(val)  # type: ignore[arg-type]
    return out, ("UNSEEN_FRONTIER.json" if out else
                 "UNMEASURED -- UNSEEN_FRONTIER.json carries no per-source estimate")


def census(rows: dict[str, dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Walk every ledger once and attribute its rows to registry sources."""
    idx = _index(rows)
    counts: dict[str, dict[str, Any]] = {}

    def resolve(raw: Any) -> str:
        return _resolve(raw, rows, idx)

    def get(raw: Any) -> dict[str, Any]:
        return counts.setdefault(resolve(raw), _blank())

    for r in _iter_jsonl(PROVENANCE):                         # GROUND leads
        c = get(r.get("repo"))
        c["n_leads"] += 1
        _touch(c, r.get("at"))
    for r in _iter_jsonl(GRAPH):                              # SCIENTIST leads and fates
        c = get(r.get("source"))
        c["n_leads"] += 1
        _touch(c, r.get("at"))
        c["n_certified"] += 1 if str(r.get("fate")).upper() == "CERTIFIED" else 0
    docket = _read_json(DOCKET, []) or []                     # COMPILED candidates
    if isinstance(docket, dict):
        docket = docket.get("rows") or docket.get("items") or []
    for r in docket if isinstance(docket, list) else []:
        if isinstance(r, dict):
            c = get(r.get("source"))
            c["n_testable"] += 1
            _touch(c, r.get("first_seen"))
    novel, novel_basis = _novel_by_source(resolve)
    for sid, n in novel.items():
        counts.setdefault(sid, _blank())["n_novel"] = int(n)
    credit = _read_json(CREDIT, {}) or {}
    for r in credit.get("by_scientist") or []:
        if isinstance(r, dict):
            c = get(r.get("source"))
            c["realised_r"] = round(float(c["realised_r"] or 0.0)
                                    + float(r.get("realised_r") or 0.0), 4)
            c["n_trades"] += int(r.get("n_trades") or 0)
            c["n_certificates"] += int(r.get("n_certificates") or 0)
    for c in counts.values():
        # INDEPENDENT needs both: certified, and not a re-finding of what the library already has.
        if c["n_novel"] is not None and c["n_certified"]:
            c["n_independent_certified"] = round(
                c["n_certified"] * min(1.0, c["n_novel"] / max(1, c["n_leads"])))
    judged = [bool(r.get("passed")) for r in _iter_jsonl(GATES)]
    return counts, {
        "novelty_basis": novel_basis,
        "credit_basis": str(credit.get("evidence_source") or "UNMEASURED -- no credit report"),
        "judged": {"n_cells_judged": len(judged), "n_passed": sum(judged),
                   "pooled_pass_rate": round(sum(judged) / len(judged), 6) if judged else None,
                   "why": ("the gate ledger carries no `source` column, so it cannot be attributed "
                           "per source; it gives the POOLED rate thin sources are shrunk toward, "
                           "and the missing column is named here rather than worked around")}}


# --------------------------------------------------------------- reputation, intel ROI, shares

def score(rows: dict[str, dict[str, Any]], counts: dict[str, dict[str, Any]],
          unseen: dict[str, float]) -> None:
    """Attach counts, reputation, unseen estimate and intel_roi to every registry row."""
    leads = sum(c["n_leads"] for c in counts.values())
    pooled = (sum(c["n_independent_certified"] or c["n_certified"]
                  for c in counts.values()) / leads) if leads else 0.0
    for sid, row in rows.items():
        c = counts.get(sid) or _blank()
        row.update({k: c[k] for k in ("n_leads", "n_novel", "n_testable", "n_certified",
                                      "n_independent_certified", "realised_r", "n_trades",
                                      "n_certificates")})
        seen = row.pop("_seen", (None, None))
        row["first_seen"], row["last_seen"] = c["first_seen"] or seen[0], c["last_seen"] or seen[1]
        denom = c["n_testable"] or c["n_leads"]
        row["reputation"] = {
            "p_novel": _rep(c["n_novel"], c["n_leads"]),
            "p_testable": _rep(c["n_testable"], c["n_leads"]),
            "p_survivor": _rep(c["n_certified"], denom),
            "p_independent_survivor": _rep(c["n_independent_certified"], denom),
            "dElogW_per_lead": (round(float(c["realised_r"]) / c["n_leads"], 6)
                                if c["realised_r"] is not None and c["n_leads"] else None),
        }
        row["unseen_estimate"] = unseen.get(sid)
        ind, basis = c["n_independent_certified"], "independent survivors per lead"
        if ind is None:
            ind, basis = c["n_certified"], "certified per lead (independence UNMEASURED)"
        expected = wilson_lower(ind + PRIOR_LEADS * pooled, c["n_leads"] + PRIOR_LEADS)
        cred = (_credit_factor(float(c["realised_r"]), c["n_trades"])
                if c["realised_r"] is not None else 1.0)
        cost = row.get("cost")
        row["intel_roi"] = (None if not cost or c["n_leads"] < THIN_LEADS
                            else round(expected * cred / cost, 8))
        row["roi_basis"] = (
            f"{basis}: Wilson LB shrunk with {PRIOR_LEADS:.0f} pseudo-leads at the pooled "
            f"{pooled:.5f} = {expected:.6f}, x realised-R credit {cred:.3f} / cost {cost}"
            if row["intel_roi"] is not None else
            (f"UNMEASURED: {c['n_leads']} lead(s), below the {THIN_LEADS}-lead floor. Under it the "
             "number would be the shrunk prior divided by the declared price, and price is not "
             "evidence -- the exploration floor funds this source instead"
             if cost else "UNMEASURED: this kind/route carries no declared cost"))


def has_evidence(rows: dict[str, dict[str, Any]]) -> bool:
    """Has ANY source with a measured ROI ever produced a survivor? Until one has, every ROI is the
    shrunk prior over a declared price, and sharpening the softmax would hand the budget to
    whichever kind the desk happens to have priced cheapest. The bandit already refuses that
    (MIN_JUDGED: "evidence, not price, allocates"); this is the same refusal one layer out."""
    return any((r.get("n_independent_certified") or r.get("n_certified") or 0) > 0
               for r in rows.values() if r.get("intel_roi") is not None)


def shares(rows: dict[str, dict[str, Any]]) -> dict[str, float]:
    """Crawl-budget shares: a softmax over intel_roi for 80%, a 20% exploration floor for the thin
    and the unseen-rich. An UNREACHABLE ground gets nothing -- it is not defunded by judgement, it
    cannot be fetched at all, and budget sent there is thrown away rather than explored."""
    out = dict.fromkeys(rows, 0.0)
    eligible = [s for s, r in rows.items() if str(r.get("route")) != "unreachable"]
    if not eligible:
        return out
    rois = {s: rows[s]["intel_roi"] for s in eligible if rows[s].get("intel_roi") is not None}
    hi = max(rois.values()) if rois else 0.0
    k = SOFTMAX_K if has_evidence(rows) else 0.0        # flat until something has survived
    weight = ({s: math.exp(k * v / hi) for s, v in rois.items()} if hi > 0
              else dict.fromkeys(rois or dict.fromkeys(eligible), 1.0))
    total = sum(weight.values()) or 1.0
    for s, v in weight.items():
        out[s] += (1.0 - EXPLORATION_SHARE) * v / total
    hi_unseen = max((rows[s].get("unseen_estimate") or 0.0) for s in eligible)
    explorers = {s for s in eligible if rows[s].get("intel_roi") is None}
    if hi_unseen > 0:
        explorers |= {s for s in eligible
                      if (rows[s].get("unseen_estimate") or 0.0) >= hi_unseen / 2.0}
    ew = {s: 1.0 + ((rows[s].get("unseen_estimate") or 0.0) / hi_unseen if hi_unseen else 0.0)
          for s in (explorers or set(eligible))}
    etotal = sum(ew.values()) or 1.0
    for s, v in ew.items():
        out[s] += EXPLORATION_SHARE * v / etotal
    out = {s: round(v, 8) for s, v in out.items()}
    drift = round(1.0 - sum(out.values()), 8)
    if out and abs(drift) > 1e-9:
        top = max(out, key=lambda s: out[s])
        out[top] = round(out[top] + drift, 8)
    return out


def language_map(rows: dict[str, dict[str, Any]]) -> tuple[dict[str, int], list[str]]:
    """Which tracked native languages have at least one GROUND on file, and which have none."""
    by_lang: dict[str, int] = {}
    with_ground: set[str] = set()
    for r in rows.values():
        lang = str(r.get("language") or "UNDECLARED")
        by_lang[lang] = by_lang.get(lang, 0) + 1
        if r.get("ground") and r.get("language"):
            with_ground.add(lang.split("-")[0].lower())
    return (dict(sorted(by_lang.items(), key=lambda t: -t[1])),
            [lang for lang in NATIVE_LANGUAGES if lang not in with_ground])


# ------------------------------------------------------------------------- merge, build and CLI

#: Counts that MERGE BY MAXIMUM. Every ledger this reads is append-only, so a run's census is
#: already cumulative and adding it to the stored value would double-count every row. The maximum
#: accumulates honestly AND survives a rotated or truncated ledger, which would otherwise silently
#: revise a source's whole history downwards.
_MONOTONE = ("n_leads", "n_novel", "n_testable", "n_certified", "n_independent_certified",
             "n_trades", "n_certificates", "n_donation_files")


def merge(old: dict[str, Any], new: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    prior = (old or {}).get("sources") or {}
    for sid, row in new.items():
        was = prior.get(sid)
        if not isinstance(was, dict):
            row["n_runs"] = 1
            continue
        for key in _MONOTONE:
            if was.get(key) is not None or row.get(key) is not None:
                row[key] = max(was.get(key) or 0, row.get(key) or 0)
        firsts = [t for t in (was.get("first_seen"), row.get("first_seen")) if t]
        lasts = [t for t in (was.get("last_seen"), row.get("last_seen")) if t]
        row["first_seen"] = min(firsts) if firsts else None
        row["last_seen"] = max(lasts) if lasts else None
        if row.get("realised_r") is None:
            row["realised_r"] = was.get("realised_r")
        row["n_runs"] = int(was.get("n_runs") or 0) + 1
    return new


def _brief(r: dict[str, Any]) -> dict[str, Any]:
    return {k: r.get(k) for k in ("source_id", "kind", "language", "n_leads", "n_testable",
                                  "n_certified", "realised_r", "intel_roi", "share", "fetch_clock")}


def _p_ind(r: dict[str, Any]) -> float:
    entry = (r.get("reputation") or {}).get("p_independent_survivor")
    return float(entry["p"]) if isinstance(entry, dict) else -1.0


def build() -> tuple[dict[str, Any], dict[str, Any]]:
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    rows, seed_meta = seed()
    counts, meta = census(rows)
    idx = _index(rows)
    unseen, unseen_basis = _unseen_by_source(lambda k: _resolve(k, rows, idx))
    score(rows, counts, unseen)
    rows = merge(_read_json(REGISTRY, {}) or {}, rows)
    sh = shares(rows)
    by_kind: dict[str, int] = {}
    for sid, r in rows.items():
        r["share"], r["last_registered"] = sh.get(sid, 0.0), now
        by_kind[str(r["kind"])] = by_kind.get(str(r["kind"]), 0) + 1
    by_lang, gaps = language_map(rows)
    ranked = sorted((r for r in rows.values() if r.get("intel_roi") is not None),
                    key=lambda r: -float(r["intel_roi"]))
    by_rep = sorted(rows.values(), key=lambda r: (-_p_ind(r), -int(r.get("n_leads") or 0)))
    rule = ("credibility and alpha yield are separate variables; the share follows measured yield "
            "with an exploration floor")
    report = {
        "at": now, "n_sources": len(rows), "by_kind": dict(sorted(by_kind.items())),
        "by_language": by_lang, "language_gaps": gaps,
        "language_gap_note": ("tracked native languages with no ground ON FILE. A gap is handed to "
                              "the crawler as a gap; no URL is ever invented to close one"),
        "top_by_roi": [_brief(r) for r in ranked[:12]],
        "top_by_reputation": [_brief(r) for r in by_rep[:12]],
        "shares": {s: round(v, 6) for s, v in sorted(sh.items(), key=lambda t: -t[1])[:40]},
        "exploration_floor": EXPLORATION_SHARE,
        "roi_regime": ("EVIDENCE" if has_evidence(rows) else "PRIOR_AND_PRICE"),
        "roi_regime_note": ("EVIDENCE: at least one costed source has produced a survivor, so the "
                            "softmax sharpens toward measured yield. PRIOR_AND_PRICE: none has, so "
                            "every roi is the shrunk prior over a declared price -- the softmax is "
                            "flattened and the shares are read as exploration, never as a verdict"),
        "exploration_note": (f"{EXPLORATION_SHARE:.0%} never follows measured yield: it is spread "
                             f"over sources with fewer than {THIN_LEADS} leads and over grounds "
                             f"the unseen-frontier estimate says still hide mechanisms (L1.52)"),
        "cost_table": {"per_lead_by_kind": COST_PER_LEAD, "route_multiplier": ROUTE_COST,
                       "units": "triage units: fetch + parse + dedupe + the licence argument",
                       "why": "a declared price list, auditable and arguable; UNMEASURED is not 0"},
        "unmeasured": {
            "novelty_per_source": meta["novelty_basis"], "unseen_frontier": unseen_basis,
            "credit_evidence": meta["credit_basis"],
            "n_sources_without_a_ground": sum(1 for r in rows.values() if r.get("task")),
            "n_sources_without_a_cost": sum(1 for r in rows.values() if r.get("cost") is None),
            "n_sources_unscheduled": sum(1 for r in rows.values()
                                         if r.get("fetch_clock") == UNSCHEDULED),
            "n_sources_no_roi": sum(1 for r in rows.values() if r.get("intel_roi") is None)},
        "reputation_note": ("every bound is a Wilson LOWER bound and carries its own n; "
                            "`dElogW_per_lead` is realised R per lead -- the desk measures R, not "
                            "dE[logW], and says so rather than renaming one as the other"),
        "judged": meta["judged"], "seed": seed_meta,
        "artifacts": {"registry": str(REGISTRY), "report": str(REPORT)}, "rule": rule,
    }
    return {"at": now, "n_sources": len(rows), "sources": rows, "rule": rule}, report


def _summary(registry: dict[str, Any], report: dict[str, Any], wrote: bool) -> list[str]:
    rows = registry["sources"]

    def tot(key: str) -> int:
        return sum(int(r.get(key) or 0) for r in rows.values())

    top = report["top_by_roi"][0] if report["top_by_roi"] else None
    gaps, un = report["language_gaps"], report["unmeasured"]
    return [
        f"source registry: {report['n_sources']} sources  "
        + "  ".join(f"{k}={v}" for k, v in list(report["by_kind"].items())[:6]),
        f"  funnel: {tot('n_leads')} leads -> {tot('n_testable')} compiled -> "
        f"{tot('n_certified')} certified  (novelty: {un['novelty_per_source'][:44]})",
        f"  credit: {un['credit_evidence']}   judged cells {report['judged']['n_cells_judged']}, "
        f"pooled pass {report['judged']['pooled_pass_rate']}",
        f"  top roi: {top['source_id'] if top else 'NONE MEASURED'} "
        f"roi={top['intel_roi'] if top else None} share={top['share'] if top else None}",
        f"  languages: {len(report['by_language'])} on file; gaps "
        f"{', '.join(gaps) if gaps else 'none of the 13 tracked'}",
        f"  exploration floor {EXPLORATION_SHARE:.0%} over <{THIN_LEADS}-lead sources and "
        f"unseen-rich grounds; {un['n_sources_no_roi']} source(s) carry no measured roi",
        f"  UNMEASURED: {un['n_sources_without_a_ground']} without a ground, "
        f"{un['n_sources_without_a_cost']} without a cost, "
        f"{un['n_sources_unscheduled']} unscheduled",
        f"  {'wrote' if wrote else 'DRY RUN, wrote nothing:'} {REGISTRY}  {REPORT}",
    ]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="W1: one source registry with result-based reputation")
    ap.add_argument("--dry-run", action="store_true", help="measure and print, write nothing")
    args = ap.parse_args(argv)
    registry, report = build()
    if not args.dry_run:
        _atomic(REGISTRY, registry)
        _atomic(REPORT, report)
    for line in _summary(registry, report, not args.dry_run):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
