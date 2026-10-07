"""THE UNKNOWN UNKNOWNS: organisations nobody listed, and capabilities nobody named.

    "it also mines all unknowns of unknowns abt these chinese western firms ai ml quant shops etc
     all asian etc"                                                  -- the principal, 2026-09-05

WHY A REGISTRY IS NOT ENOUGH, and why this file is the one that keeps the miner from going stale.
`registry.FIRMS` is a list somebody wrote down, so it can only ever find what that person already
knew to look for. Every genuinely new capability arrives from an organisation not on the list, in
a capability group the ontology has no row for, or through a claim nobody has verified -- and a
miner that only walks its registry converges on confirming what it already believed within weeks.

THREE KINDS OF UNKNOWN, and they need different machinery:

  UNKNOWN FIRM        an organisation this registry has never named. Discovered by co-occurrence:
                      a name that keeps appearing beside organisations we DO track, in sources we
                      already read, is a candidate for the registry. Cheap, and it is how every
                      list of firms actually grows.
  UNKNOWN CAPABILITY  a finding that maps to NO ontology group. The ontology deliberately refuses
                      to fuzzy-match, so these land here rather than being forced into the nearest
                      row -- and a cluster of them is the signal that the ontology itself is
                      short a category, which is a bigger finding than any single card.
  UNADDRESSED         a capability group the ontology names and this desk has NO module for. Not
                      "we are weak at it" -- "we have never done it". These are where the largest
                      real differences to an elite organisation live, and they are knowable today
                      without crawling anything.

THE ANTI-CONVERGENCE BUDGET. §29 of the mandate reserves exploration capital so exploitation does
not make the research system intellectually stagnant, and the same argument applies one level up:
a fixed fraction of every cycle goes to the unknown lanes REGARDLESS of their score, because their
score is computed from a model that by construction does not know about them. Spending zero on
unknowns is how a miner becomes a search for confirmation.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    from . import ontology, registry
except ImportError:
    # RUN AS A SCRIPT BY THE HOURLY LEG `frontier_unknowns`. The relative import alone made that
    # leg exit 1 every hour ("attempted relative import with no known parent package", measured
    # 2026-10-07), so nothing this module discovers had ever been recorded on a schedule.
    _HERE = Path(__file__).resolve().parent
    for _p in (str(_HERE.parent), str(_HERE.parents[2])):
        if _p not in sys.path:
            sys.path.insert(0, _p)
    from frontier_intel import ontology, registry  # type: ignore[no-redef]

BASE = Path(__file__).resolve().parent.parent
CANDIDATES = BASE / "frontier_intel" / "data" / "firm_candidates.jsonl"
#: THE ONTOLOGY EXTENSION (DATA-14): candidate classes that RECUR are promoted here automatically,
#: with provenance. Rows use the class-row shape of the equivalence ontology's extension file
#: (group / name / terms / layer / cadence / mandate_id / part) so that file's loader can merge it
#: unchanged; the provenance and lifecycle keys ride beside them.
EXTENSION = BASE / "frontier_intel" / "data" / "ontology_extension.json"
LOOP_LEDGER = BASE / "data" / "discovery_loop" / "ledger.json"
LOOP_REPORT = BASE / "reports" / "DISCOVERY_LOOP.json"
FRONTIER_QUEUE = BASE / "frontier_intel" / "data" / "frontier_queue.jsonl"
TASK_QUEUE = BASE / "data" / "task_queue.jsonl"
REPORT = BASE / "reports" / "FRONTIER_UNKNOWNS.json"
#: Distinct sources OR distinct countries a candidate class must be seen in before it is
#: promoted. One source is an extraction; three independent ones are a category the ontology lacks.
MIN_RECURRENCE = 3
UNMEASURED = "UNMEASURED"
#: Words that recur everywhere and name no class: never promoted however often they are seen.
_CLASS_STOP = frozenset("""government ministry office department national statistics statistic
official agency bureau authority institute portal service services report reports bulletin
release releases publication publications survey surveys indicator indicators table tables
dataset datasets database catalog catalogue register registry yearly monthly annual quarterly
english french german spanish search results result title titles index about contact archive
wikipedia wikip google category kategorie categoria market markets trading trader traders
analysis economic economy interactive investing investment strategy strategies online
download downloads website homepage welcome blog article articles news update updated
""".split())

#: Fraction of each cycle's attention reserved for the unknown lanes whatever they score.
#: DERIVED FROM THE MANDATE'S OWN RANGE (5-15% for unknown-unknowns) and set at the middle of it.
#: Higher would starve the queue the desk can actually price; lower stops being a budget and
#: becomes a rounding error that the first busy hour spends elsewhere.
EXPLORATION_FRACTION = 0.10

#: An organisation-shaped token: two-to-four capitalised words, or a known corporate suffix. Kept
#: crude ON PURPOSE -- this proposes candidates for a human-or-agent decision, it does not admit
#: them. A precise extractor here would be a second, worse named-entity recogniser.
_ORG = re.compile(
    r"\b((?:[A-Z][A-Za-z0-9&.\-]+(?:\s+|-)){1,3}"
    r"(?:Capital|Asset|Assets|Management|Investment|Investments|Technologies|Technology|"
    r"Research|Securities|Trading|Partners|Fund|Funds|Quant|Quantitative|Labs|Lab|AI))\b")

#: Words that make an organisation-shaped token a false positive: our own vocabulary, and the
#: generic phrases every article about quant funds contains.
_NOISE = frozenset({
    "the fund", "a fund", "hedge fund", "quant fund", "mutual fund", "index fund",
    "asset management", "investment management", "artificial intelligence",
    "machine learning", "quantitative research", "quantitative trading",
})


#: Words that appear in half of all firm names and identify none of them. A candidate matched to a
#: tracked firm on one of these alone would collapse every "X Capital" into whichever tracked firm
#: happened to contain "capital".
_GENERIC = frozenset({
    "capital", "asset", "assets", "management", "investment", "investments", "technologies",
    "technology", "research", "securities", "trading", "partners", "fund", "funds", "quant",
    "quantitative", "labs", "lab", "ai", "group", "invest", "holdings", "the", "and",
})


def _distinctive(name: str) -> frozenset[str]:
    """The tokens that actually identify a firm: everything minus the industry vocabulary."""
    return frozenset(t for t in name.lower().replace("-", " ").split() if t not in _GENERIC)


def _same_firm(candidate: str, known: set[str]) -> bool:
    """Is this candidate a tracked firm written a different way?

    TOKEN OVERLAP, NOT SUBSTRING, and this file's own test found why. "Man AHL Capital" keys to
    "AHL Capital"; the registry holds "Man AHL"; neither string contains the other, so a substring
    test reported a tracked firm as an exciting new discovery. Sharing a DISTINCTIVE token --
    "ahl" -- is the signal, and dropping the industry vocabulary first is what stops every
    "<Something> Capital" collapsing into the first tracked firm whose name contains "capital".
    """
    mine = _distinctive(candidate)
    return bool(mine) and any(mine & _distinctive(k) for k in known)


@dataclass(frozen=True)
class Unknown:
    """One thing the miner did not previously know about, and why it is worth a look."""

    kind: str               # FIRM | CAPABILITY | UNADDRESSED
    name: str
    mentions: int
    seen_with: tuple[str, ...]
    why: str


def unknown_firms(texts: list[str], min_mentions: int = 2) -> list[Unknown]:
    """Organisation names appearing in what we already read that the registry does not know.

    CO-OCCURRENCE IS THE WHOLE SIGNAL. A name appearing once in one article is noise; a name
    appearing repeatedly, in sources we read because they discuss firms we track, is what the
    registry is missing. `min_mentions` is the only knob and it is deliberately low: the cost of a
    false candidate is one investigation, and the cost of a missed one is a permanent blind spot.
    """
    known = {n.lower() for n in registry.BY_NAME}
    counts: Counter[str] = Counter()
    beside: dict[str, set[str]] = {}
    for text in texts:
        found = {m.group(1).strip() for m in _ORG.finditer(text or "")}
        tracked = {f for f in registry.BY_NAME if f.lower() in (text or "").lower()}
        for name in found:
            # KEYED ON THE LAST TWO WORDS, because the same organisation is written several ways
            # in the same corpus: "Shanghai Qingyuan Capital" in one article and "Qingyuan
            # Capital" in the next are one candidate, and counting them separately halves every
            # mention count and pushes real firms below `min_mentions`. The trailing tokens are
            # the stable part of a firm name; the leading ones are cities and qualifiers.
            key = " ".join(name.split()[-2:]).strip()
            low = key.lower()
            if low in known or low in _NOISE or len(key) < 4:
                continue
            if _same_firm(low, known):
                continue                      # a tracked firm written a different way
            counts[key] += 1
            beside.setdefault(key, set()).update(tracked)
    out = []
    for name, n in counts.most_common():
        if n < min_mentions:
            continue
        with_ = tuple(sorted(beside.get(name, ())))
        out.append(Unknown(
            "FIRM", name, n, with_,
            why=(f"named {n} time(s) in sources we already read"
                 + (f", beside {', '.join(with_[:3])}" if with_ else "")
                 + " -- the registry does not know it, and a registry only finds what its author "
                   "already knew to list")))
    return out


def unknown_capabilities(findings: list[dict[str, Any]]) -> list[Unknown]:
    """Findings that map to no ontology group -- and the ontology gap a cluster of them implies.

    `ontology.map_to_capabilities` refuses to fuzzy-match on purpose, so an unmappable finding is
    not silently filed under the nearest row. It lands here. ONE of them is a badly-extracted
    card; a CLUSTER of them saying similar things is the ontology missing a category, which is a
    larger finding than any card in the cluster.
    """
    out: list[Unknown] = []
    for f in findings:
        text = " ".join(str(f.get(k) or "") for k in
                        ("capability_domain", "public_observation", "underlying_principle"))
        if ontology.map_to_capabilities(text):
            continue
        out.append(Unknown(
            "CAPABILITY", str(f.get("frontier_id") or f.get("title") or "?"), 1,
            (str(f.get("firm") or ""),),
            why=("maps to no capability group: either the extraction failed to name one, or the "
                 "ontology is short a category. A cluster of these is the second, and the "
                 "ontology is edited once rather than per article")))
    return out


def unaddressed_capabilities() -> list[Unknown]:
    """Capability groups the ontology names and this desk has NO module for.

    KNOWABLE WITHOUT CRAWLING ANYTHING, which is what makes this the cheapest high-value query in
    the package: it is a fact about our own tree. "We are weak at execution research" is an
    opinion; "no module on this desk addresses MARKET_IMPACT" is a measurement, and it is the kind
    of gap that stays open for years precisely because nothing ever names it.
    """
    return [Unknown("UNADDRESSED", name, 0, (),
                    why=(f"{ontology.BY_NAME[name].what} -- and no module on this tree owns it. "
                         f"Not a weakness: a category of work never started"))
            for name in ontology.unaddressed()]


def record_candidates(rows: list[Unknown], path: Path | None = None) -> int:
    """Append discovered unknowns, so a candidate found once is not rediscovered for ever."""
    p = CANDIDATES if path is None else path
    if not rows:
        return 0
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps({"kind": r.kind, "name": r.name, "mentions": r.mentions,
                                     "seen_with": list(r.seen_with), "why": r.why}) + "\n")
    except OSError:
        return 0
    return len(rows)


def survey(texts: list[str] | None = None,
           findings: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Every unknown lane in one pass, with the exploration budget attached.

    Returns the three lanes and the fraction of the cycle reserved for them. THE BUDGET IS
    REPORTED RATHER THAN ENFORCED HERE: this module discovers, the supervisor spends. A discovery
    module that also controlled the schedule would be able to justify its own budget.
    """
    firms = unknown_firms(texts or [])
    caps = unknown_capabilities(findings or [])
    unaddressed = unaddressed_capabilities()
    return {
        "exploration_fraction": EXPLORATION_FRACTION,
        "why_reserved": ("the score of an unknown is computed by a model that by construction "
                         "does not know about it, so a purely scored queue spends zero here and "
                         "the miner converges on confirming what it already believed"),
        "unknown_firms": [u.__dict__ for u in firms],
        "unknown_capabilities": [u.__dict__ for u in caps],
        "unaddressed_capabilities": [u.__dict__ for u in unaddressed],
        "counts": {"firms": len(firms), "capabilities": len(caps),
                   "unaddressed": len(unaddressed)},
    }


# ------------------------------------------------------------------ the ontology never closes
def _host(url: str) -> str:
    s = re.sub(r"^[a-z][a-z0-9+.-]*://", "", str(url or "").strip().lower())
    s = s.split("/", 1)[0].split(":", 1)[0]
    return s[4:] if s.startswith("www.") else s


def _country(host: str) -> str:
    tld = host.rsplit(".", 1)[-1] if "." in host else ""
    if len(tld) == 2 and tld.isalpha() and tld not in {"io", "ai", "co", "tv", "me", "eu"}:
        return "GB" if tld == "uk" else tld.upper()
    return UNMEASURED


def candidate_class_rows(loop_records: Mapping[str, Mapping[str, Any]] | None = None,
                         frontier_rows: Iterable[Mapping[str, Any]] = ()
                         ) -> list[dict[str, Any]]:
    """Every observation of a class the ontology does not have, one row per (class, source).

        information_class  salient words of an UNCLASSIFIED unseeded source (discovery loop)
        capability         a frontier finding whose capability names no ontology group
        actor              an organisation named in a finding that the registry does not know
    """
    rows: list[dict[str, Any]] = []
    for host, r in (loop_records or {}).items():
        # A DATA class needs a data source: a host that served at least one data endpoint. Pages
        # with no endpoint are prose, and their words name topics, not information classes.
        if str(r.get("data_type") or "") != "UNCLASSIFIED" or not int(r.get("endpoints") or 0):
            continue
        for w in r.get("candidate_words") or []:
            w = str(w).lower()
            if w in _CLASS_STOP or len(w) < 5:
                continue
            rows.append({"axis": "information_class", "name": w, "source": str(host),
                         "country": str(r.get("country") or UNMEASURED),
                         "at": (r.get("stages") or {}).get("DISCOVERED"),
                         "evidence": (r.get("sample") or [""])[0][:160]})
    for f in frontier_rows:
        src = _host(str(f.get("source_url") or "")) or str(f.get("source_kind") or "")
        if not src:
            continue
        cap = str(f.get("capability") or "").strip()
        if cap and cap.upper() not in ontology.NAMES and not ontology.map_to_capabilities(cap):
            rows.append({"axis": "capability", "name": cap.lower(), "source": src,
                         "country": _country(src), "at": f.get("at"),
                         "evidence": str(f.get("claim") or "")[:160]})
        for u in unknown_firms([str(f.get("claim") or "")], min_mentions=1):
            rows.append({"axis": "actor", "name": u.name, "source": src,
                         "country": _country(src), "at": f.get("at"),
                         "evidence": u.why[:160]})
    return rows


def _terms(name: str) -> str:
    words = [re.escape(w) for w in re.findall(r"[A-Za-z0-9]+", name)]
    return r"\b" + r"\W+".join(words) + r"\b" if words else re.escape(name)


def _read_doc(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def promote_recurring(rows: Iterable[Mapping[str, Any]], *, min_recurrence: int = MIN_RECURRENCE,
                      path: Path | None = None, now: datetime | None = None,
                      write: bool = True, met: Iterable[str] = ()) -> dict[str, Any]:
    """Promote every candidate class seen in >= `min_recurrence` distinct sources OR countries.

    AUTOMATIC AND ADDITIVE. A promoted class is appended to the extension file with its
    provenance (the sources, countries, first sighting, evidence); a class already promoted has
    its provenance widened, never removed -- the ontology is open and nothing here closes it.
    """
    at = (now or datetime.now(UTC)).isoformat(timespec="seconds")
    p = EXTENSION if path is None else path
    doc = _read_doc(p)
    classes: list[dict[str, Any]] = [c for c in doc.get("classes") or [] if isinstance(c, dict)]
    by_key = {f"{c.get('group')}:{c.get('name')}": c for c in classes}
    groups: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {"sources": set(), "countries": set(), "first": None, "evidence": []})
    for r in rows:
        g = groups[(str(r["axis"]), str(r["name"]))]
        g["sources"].add(str(r["source"]))
        if r.get("country") and r["country"] != UNMEASURED:
            g["countries"].add(str(r["country"]))
        if r.get("at") and (g["first"] is None or str(r["at"]) < g["first"]):
            g["first"] = str(r["at"])
        if r.get("evidence") and len(g["evidence"]) < 3:
            g["evidence"].append(str(r["evidence"]))
    promoted: list[str] = []
    widened: list[str] = []
    below: list[dict[str, Any]] = []
    for (axis, name), g in sorted(groups.items()):
        key = f"{axis}:{name}"
        n_src, n_cty = len(g["sources"]), len(g["countries"])
        if key in by_key:
            prov = by_key[key].setdefault("provenance", {})
            srcs = sorted(set(prov.get("sources") or []) | g["sources"])
            if len(srcs) > len(prov.get("sources") or []):
                widened.append(key)
            prov.update({"sources": srcs[:50], "n_sources": max(len(srcs),
                                                                int(prov.get("n_sources") or 0)),
                         "countries": sorted(set(prov.get("countries") or []) | g["countries"]),
                         "last_seen": at})
            continue
        if n_src < min_recurrence and n_cty < min_recurrence:
            below.append({"key": key, "sources": n_src, "countries": n_cty})
            continue
        row = {"group": axis, "name": name, "terms": _terms(name), "layer": "auto",
               "cadence": UNMEASURED, "mandate_id": "AUTO-DATA-14", "part": "auto",
               "status": "PROMOTED_AUTO", "lifecycle": "MISSION_OPEN",
               "provenance": {"sources": sorted(g["sources"])[:50], "n_sources": n_src,
                              "countries": sorted(g["countries"]), "first_seen": g["first"],
                              "promoted_at": at, "evidence": g["evidence"],
                              "rule": (f"seen in >= {min_recurrence} distinct sources or "
                                       f"countries (frontier_intel/unknowns.promote_recurring)")}}
        classes.append(row)
        by_key[key] = row
        promoted.append(key)
    # LIFECYCLE: a class whose mission the discovery loop saw met (an unseeded source matching it
    # was acquired) moves MISSION_OPEN -> MISSION_MET; it stays in the ontology either way.
    done = set(met)
    for c in classes:
        if f"{c.get('group')}:{c.get('name')}" in done:
            c["lifecycle"] = "MISSION_MET"
    out_doc = {"generated_at": at, "classes": classes, "known": list(doc.get("known") or []),
               "rule": ("auto-extension: recurring candidate classes are promoted with provenance "
                        "and routed to acquisition as missions; the same acquisition, PIT, "
                        "validation, ROI and lifecycle rules apply to them as to every class")}
    if write:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(out_doc, indent=1, ensure_ascii=False), "utf-8")
        os.replace(tmp, p)
    below.sort(key=lambda r: (-r["sources"], -r["countries"], r["key"]))
    return {"candidates": len(groups), "promoted_now": promoted, "widened": widened,
            "total_promoted": len(classes), "below_threshold_top": below[:20],
            "min_recurrence": min_recurrence, "classes": classes}


def route_missions(classes: Iterable[Mapping[str, Any]], queue: Any,
                   met: Iterable[str] = ()) -> dict[str, Any]:
    """Every promoted class with an open mission becomes an INFORMATION-lane `acquire_class` task
    (deduped per class), linked to the strategy-lane `screen_class` its completion queues. The
    discovery loop completes the task when an unseeded source matching the class is acquired."""
    done = set(met)
    queue.link("acquire_class", "screen_class")
    queued, skipped = [], []
    for c in classes:
        key = f"{c.get('group')}:{c.get('name')}"
        if key in done or c.get("lifecycle") == "MISSION_MET":
            continue
        got = queue.submit("acquire_class", lane="information",
                           payload={"key": key, "terms": c.get("terms"), "axis": c.get("group")},
                           priority=float((c.get("provenance") or {}).get("n_sources") or 0),
                           dedupe_key=f"acquire_class|{key}")
        (queued if got is not None else skipped).append(key)
    return {"queued": queued, "already_open": skipped}


def _frontier_rows(path: Path = FRONTIER_QUEUE) -> list[dict[str, Any]]:
    try:
        lines = path.read_text("utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def run(*, write: bool = True, now: datetime | None = None) -> dict[str, Any]:
    """One pass: candidate classes -> promotion -> missions. The hourly `frontier_unknowns` leg."""
    loop = _read_doc(LOOP_LEDGER).get("records") or {}
    frontier = _frontier_rows()
    rows = candidate_class_rows(loop, frontier)
    met = [str(m.get("key")) for m in
           ((_read_doc(LOOP_REPORT).get("missions") or {}).get("met") or [])]
    promo = promote_recurring(rows, now=now, write=write, met=met)
    missions: dict[str, Any] = {"queue": UNMEASURED}
    if write:
        try:
            from libs.ops.task_queue import TaskQueue
            missions = route_missions(promo["classes"], TaskQueue(TASK_QUEUE), met)
        except Exception as exc:  # noqa: BLE001 - promotion stands even when routing cannot run
            missions = {"queue": f"UNROUTED: {type(exc).__name__}: {exc}"[:200]}
    surveyed = survey([str(f.get("claim") or "") for f in frontier], frontier)
    out = {"generated_at": (now or datetime.now(UTC)).isoformat(timespec="seconds"),
           "inputs": {"loop_records": len(loop), "frontier_rows": len(frontier),
                      "candidate_rows": len(rows)},
           "promotion": {k: v for k, v in promo.items() if k != "classes"},
           "missions": missions, "missions_met": met,
           "survey_counts": surveyed["counts"],
           "extension": str(EXTENSION)}
    if write:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(out, indent=1, default=str), "utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="unknown unknowns: promote recurring classes")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    out = run(write=not args.dry_run)
    pr = out["promotion"]
    print(f"frontier unknowns: {out['inputs']['candidate_rows']} candidate row(s), "
          f"{pr['candidates']} class(es); promoted now {len(pr['promoted_now'])}, "
          f"total {pr['total_promoted']}; missions {out['missions']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
