"""M8 -- THE SCOUT SWARM: the nineteen declared beats, run as workers, on the frontier's orders.

WHAT WAS MISSING. `scout_roster` names nineteen beats and the organs that cover them; nothing RUNS
a beat. The organs run on their own clocks, unaimed -- `deep_forest_miner` rotates its five hundred
grounds by weight, the crawler follows its own frontier, the seats hunt whatever their prompt said
last -- so the desk has a roster, a set of clocks, and no mechanism by which the measurement "this
cell holds unseen mass" becomes the act "a scout goes there". UNWIRED OR IDLE IS A DEFECT (III.16):
a frontier map nothing reads is a report, not an allocator.

THIS IS THE WIRING. One pass takes `source_frontier.assign` for each beat, runs that beat's organs
pointed at the chosen cells where the organ accepts steering, reads what came back, and pays the
sources by what they produced. The beats run IN-PROCESS in one loop -- they are I/O and
bookkeeping, not compute -- and only the organs are children, which is where the per-beat budget
and the gateway-friendly priority go.

**A BEAT THAT CANNOT BE STEERED SAYS SO.** Measured on this tree today, exactly one roster organ
takes an argument that points it at ground: `deep_forest_miner` (--region, --only, --budget-s).
`asia_collector` takes --id, `world_crawler` and `repo_miner` take budget or cache flags only, and
most of the beats' organs have no argparse at all -- they are run by import. Those beats run
UNPARAMETERISED and publish `steerable: false`, because a swarm that quietly ran an unsteerable
organ and reported the cell it wanted would be inventing the connection it exists to make. The
steering table is checked against each organ's OWN `add_argument` calls at run time, so a renamed
flag drops out of the plan instead of failing forty minutes later.

**EVERY PRODUCTIVE SOURCE SPAWNS SEARCHES.** After a pass the swarm reads the newest intelligence
rows and the registry's claims and pulls the expansion edges out of them: the AUTHORS named, the
CITATIONS and links, the REPOSITORIES, the COMMUNITIES, the DATASETS, and the TERMINOLOGY -- top
domain terms by tf-idf against the vocabulary the desk already has, because a word this corpus uses
and the desk's own does not is the name of something nobody here has looked at. Each becomes a
source row with `status="candidate"` and a `discovered_from` edge. NOTHING IS CRAWLED BLINDLY: a
candidate opens for crawling only once its PARENT's P(testable) clears 0.1 on measured leads, and a
prior-only parent never opens it. That gate is what separates a growing forest from an unbounded
fetch of everything anything ever linked to.

**THE COLD LANE IS FLOORED.** The mix comes from the seated ResearchOS policy
(`active_policy()["miner"]["search_mix"]`, 30/55/15 by default) and cold never falls below 0.10.
Cold search is the only lane that reaches ground the desk's own history cannot point at; it pays
last and rarely, so it is the first thing any short-horizon fitness cuts, and a swarm allowed to
cut it optimises itself into the neighbourhood of what it already knows.

    python desks/mt5/research/scout_swarm.py --once [--budget-s 600]
    python desks/mt5/research/scout_swarm.py --dry-run          # plans, runs nothing
"""
from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import re
import subprocess
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import source_frontier as sf  # noqa: E402
from scout_roster import DECLARED_BEATS, SCOUTS  # noqa: E402

from libs.moat import registry as reg  # noqa: E402

LOCKS = DESK / "data" / "locks"
LOCK = LOCKS / "scout_swarm.lock"
OUT = DESK / "reports" / "SCOUT_SWARM.json"
SEAT_ROOTS: tuple[Path, ...] = (DESK / "data" / "intelligence", ROOT / "data" / "intelligence")

#: One pass's wall budget, shared by the beats in proportion to their measured ROI.
BUDGET_S = float(os.environ.get("SWARM_BUDGET_S", "600"))
#: No beat is ever starved to nothing: an unmeasured beat is unmeasured, not worthless, and a beat
#: with no compute can never produce the measurement that would earn it compute.
BEAT_FLOOR = 0.02
#: Never below this share on cold ground, whatever the seated policy says (the constitutional
#: floor, `research_os_archive.COLD_SEARCH_FLOOR`).
COLD_FLOOR = sf.COLD_FLOOR
#: Cells handed to one beat per pass, split across the three lanes by the search mix.
CELLS_PER_BEAT = int(os.environ.get("SWARM_CELLS_PER_BEAT", "4"))
#: A pass does not start an organ while free physical memory is under this. MEASURED on the box
#: that trades (8 GB, re-measured 2026-09-15): `external_gauntlet` stood down twice with ~250 MB
#: free and 14 resident pythons. Sized for THIS machine; re-measure before changing it.
MIN_FREE_MB = float(os.environ.get("SWARM_MIN_FREE_MB", "1024"))
#: Seconds between passes in resident mode, so an empty swarm does not spin.
MIN_CYCLE_S = float(os.environ.get("SWARM_MIN_CYCLE_S", "600"))
#: Intelligence files newer than this are this pass's harvest; older ones were another pass's.
HARVEST_LOOKBACK_S = float(os.environ.get("SWARM_LOOKBACK_S", "3600"))
BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
MAX_ROWS_PER_SEAT = 400
MAX_EXPANSIONS = 40
TOP_TERMS = 20
UNMEASURED = sf.UNMEASURED

#: How each organ is POINTED. Only the three keys `steer_args` consumes appear here -- `region`,
#: `grounds` (repeatable) and `budget_s` -- and each is verified against the organ's own
#: `add_argument` calls before use, so a renamed flag drops the steering rather than failing the
#: run. A FLAG THAT EXISTS IS NOT A STEER: `asia_collector --id` takes that organ's OWN source ids
#: and `fxblue_track_record_miner --limit` takes a row count, neither of which a frontier CELL can
#: be turned into without a mapping the desk does not have. Listing them here would make the
#: steerable count a claim that cannot be cashed, so they are named and left out.
STEERING: dict[str, dict[str, str]] = {
    "desks/mt5/research/deep_forest_miner.py": {"region": "--region", "grounds": "--only",
                                                "budget_s": "--budget-s"},
    "desks/mt5/research/asia_collector.py": {"budget_s": "--budget"},
    "desks/mt5/side_channels/world_crawler.py": {"budget_s": "--budget-s"},
}
#: Crypto-exchange-native ground is never hunted again (MT5 universe mandate, 2026-08-18). An
#: expansion edge pointing at one is REFUSED and counted, never registered as a candidate source.
CRYPTO_HOSTS: tuple[str, ...] = ("binance", "bybit", "okx", "hyperliquid", "deribit", "kraken",
                                 "coinbase", "bitmex", "kucoin", "huobi", "gate.io", "bitfinex")
_URL_RE = re.compile(r"https?://[^\s<>\"'\\)\]]+")
_DOI_RE = re.compile(r"\b(?:doi:\s*)?10\.\d{4,9}/[^\s\"'<>]+", re.I)
_ARXIV_RE = re.compile(r"\barxiv[:\s]*(\d{4}\.\d{4,5})", re.I)
#: "by X", "author: X" and the CJK/Cyrillic bylines. The full-width colon is written as an
#: escape so no reader can mistake it for the ASCII one; both are accepted.
_AUTHOR_RE = re.compile(
    "(?:\\bby\\s+|\\bauthor[:\\s]+"
    "|(?:\u4f5c\u8005|\u8457\u8005|\uc800\uc790)[:\uff1a]\\s*"
    "|\u0430\u0432\u0442\u043e\u0440[:\\s]+)"
    r"([A-Z][\w.'-]+(?:\s+[A-Z][\w.'-]+){0,2}|[\u4e00-\u9fff]{2,4}|[\uac00-\ud7af]{2,4})")
_HANDLE_RE = re.compile(r"(?<![\w/])@([A-Za-z0-9_]{3,30})\b")
_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{3,24}|[\u4e00-\u9fff]{2,4}")
_REPO_HOSTS = ("github.com", "gitee.com", "gitlab.com", "bitbucket.org")
_COMMUNITY_HOSTS = ("reddit.com", "zhihu.com", "xueqiu.com", "stackexchange.com",
                    "stackoverflow.com", "t.me", "discord", "forum", "bbs", "quora.com",
                    "bilibili.com", "naver.com", "5ch.net", "elitetrader.com", "forexfactory.com")
_DATASET_HINTS = ("fred.stlouisfed", "data.gov", "kaggle.com", "quandl", "figshare", "zenodo",
                  "datahub", "/dataset", "dataset/", ".csv", ".parquet", "/api/", "opendata",
                  "worldbank", "imf.org", "oecd.org", "eurostat")
#: Words a corpus about markets always uses; they carry no information about WHERE it came from.
_STOP = frozenset((
    "this", "that", "with", "from", "have", "which", "when", "there", "their", "about", "would",
    "into", "more", "than", "then", "they", "been", "were", "what", "your", "will", "also", "such",
    "market", "markets", "trade", "trading", "trader", "price", "prices", "https", "http", "www",
    "com", "html", "index", "data", "time", "over", "only", "some", "other", "these", "because",
))


# --------------------------------------------------------------------------------- small helpers

def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return default


#: REUSE, NOT A SECOND OPINION. `department_resident` already owns the desk's definition of free
#: physical memory (GlobalMemoryStatusEx, None where unreadable, and None is never zero). Two
#: readers of the same fact would eventually disagree about whether the box can afford a pass.
from department_resident import free_phys_mb  # noqa: E402


def claim_singleton(path: Path | None = None):
    """Hold the lock for the life of this process; None when another swarm already holds it. The
    keep-alive trigger that restarts a dead resident must be a no-op while one is alive.

    The path is resolved AT CALL TIME, not bound as a default: a default is evaluated once at
    import and would ignore a caller (or a test) that moved LOCK afterwards -- and an unwritable
    parent directory then reads as "another swarm holds the slot", which is a lie about a lock.
    """
    path = Path(path) if path is not None else LOCK
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fh = open(path, "a+", encoding="utf-8")  # noqa: SIM115 -- held for the process lifetime
    except OSError:
        return None
    try:
        if sys.platform == "win32":
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return None
    with contextlib.suppress(OSError):
        fh.seek(0)
        fh.truncate()
        fh.write(f"{os.getpid()} {_now()}\n")
        fh.flush()
    return fh


# --------------------------------------------------------------------------------- the organs

def organ_flags(organ: str) -> frozenset[str]:
    """The long flags an organ's OWN argparse declares. Read from the file, never assumed: the
    steering table is a claim about another file, and a claim the desk cannot cash is a defect."""
    p = ROOT / organ
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return frozenset()
    return frozenset(re.findall(r"add_argument\(\s*[\"'](--[a-z0-9-]+)", text))


def steer_args(organ: str, cells: list[dict[str, Any]], budget_s: float
               ) -> tuple[list[str], list[str]]:
    """The arguments that point THIS organ at THESE cells, and the axes actually used."""
    spec = STEERING.get(organ, {})
    if not spec:
        return [], []
    flags = organ_flags(organ)
    args: list[str] = []
    used: list[str] = []
    countries = [str(c["axes"]["country"]) for c in cells
                 if str(c["axes"]["country"]).lower() != UNMEASURED.lower()]
    langs = [str(c["axes"]["language"]) for c in cells
             if str(c["axes"]["language"]).lower() != UNMEASURED.lower()]
    if spec.get("region") in flags and countries:
        args += [spec["region"], countries[0]]
        used.append("region")
    if spec.get("grounds") in flags:
        for value in dict.fromkeys(countries + langs):
            args += [spec["grounds"], value]
        if countries or langs:
            used.append("grounds")
    if spec.get("budget_s") in flags:
        args += [spec["budget_s"], str(max(30, int(budget_s)))]
    return args, used


def run_organ(organ: str, args: list[str], timeout_s: float) -> dict[str, Any]:
    """One organ as a bounded child, exactly as `hourly_cycle._producer` does it: resolved against
    both roots, a hard timeout, output tail kept, a miss REPORTED rather than run. Not in-process:
    these allocate heavily and can hang on a network call, and neither may take the swarm down."""
    for root in (ROOT, DESK):
        target = root / organ
        if target.exists():
            break
    else:
        return {"status": "MISSING", "why": f"{organ} exists under neither {ROOT} nor {DESK}"}
    kwargs: dict[str, Any] = {}
    if sys.platform == "win32":
        # The loop is in-process; the CHILD is the heavy part, and the gateway must always win.
        kwargs["creationflags"] = BELOW_NORMAL_PRIORITY_CLASS
    t0 = time.monotonic()
    try:
        r = subprocess.run([sys.executable, "-u", "-W", "ignore", str(target), *args],
                           capture_output=True, text=True, cwd=str(root), timeout=timeout_s,
                           check=False, **kwargs)
        return {"status": "ok" if r.returncode == 0 else "exit", "rc": r.returncode,
                "seconds": round(time.monotonic() - t0, 1),
                "tail": (r.stdout or r.stderr or "")[-200:]}
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "rc": None, "seconds": round(time.monotonic() - t0, 1),
                "why": f"exceeded its {timeout_s:.0f}s slice; partial work is whatever it wrote"}
    except OSError as exc:
        return {"status": f"failed_to_start: {type(exc).__name__}", "rc": None,
                "seconds": round(time.monotonic() - t0, 1)}


def seats_of(organ: str) -> tuple[str, ...]:
    """The seat directories the roster says this organ donates to."""
    return tuple(s for sc in SCOUTS if sc["organ"] == organ for s in sc["seats"])


# ------------------------------------------------------------------------------------ the plan

def _matches(beat: dict[str, Any], src: dict[str, Any]) -> bool:
    def _want(want: tuple[str, ...], value: Any) -> bool:
        return not want or "*" in want or str(value or "") in want

    return (_want(tuple(beat["languages"]), src.get("language"))
            and _want(tuple(beat["regions"]), src.get("country"))
            and _want(tuple(beat["kinds"]), src.get("kind")))


def plan(budget_s: float = BUDGET_S, conn: Any = None,
         beats: tuple[dict[str, Any], ...] = DECLARED_BEATS) -> list[dict[str, Any]]:
    """Seconds per beat: proportional to its sources' measured ROI, with a floor under every beat.

    THE FLOOR IS NOT POLITENESS. A beat with no measurement is UNMEASURED, not worthless, and a
    beat given no compute can never produce the measurement that would earn it compute -- the
    starvation loop that makes an ROI allocator look right forever while it reads one corner of
    the world. So every beat keeps BEAT_FLOOR of the pass, and ROI splits what is left.
    """
    c = conn or reg.connect()
    try:
        roi = {r["source_id"]: r for r in sf.roi_table(conn=c, limit=5000)}
        srcs = sf.sources(conn=c)
        rows: list[dict[str, Any]] = []
        for beat in beats:
            mine = [roi[sid] for sid, s in srcs.items()
                    if sid in roi and _matches(beat, s) and roi[sid]["measured"]]
            score = float(sum(r["roi_score"] for r in mine) / len(mine)) if mine else 0.0
            rows.append({"beat": beat["beat"], "organs": list(beat["organs"]),
                         "scope": beat["scope"], "roi": round(score, 9), "n_sources_measured":
                         len(mine), "measured": bool(mine)})
        n = max(1, len(rows))
        floor = min(BEAT_FLOOR, 1.0 / n)
        total = sum(r["roi"] for r in rows)
        for r in rows:
            w = (r["roi"] / total) if total > 0 else 1.0 / n
            r["share"] = round(floor + (1.0 - n * floor) * w, 6)
            r["budget_s"] = round(budget_s * r["share"], 2)
            r["basis"] = (f"mean source ROI over {r['n_sources_measured']} measured source(s)"
                          if r["measured"] else
                          f"{UNMEASURED} -- no source on this beat's axes has a measured lead; "
                          f"the beat keeps its {floor:.3f} floor")
        rows.sort(key=lambda r: (-r["share"], r["beat"]))
        return rows
    finally:
        if conn is None:
            c.close()


def lane_cells(budget_row: dict[str, Any], cells: list[dict[str, Any]], conn: Any,
               mix: dict[str, float]) -> list[dict[str, Any]]:
    """This beat's cells: the mix applied to CELLS_PER_BEAT, cold never below its floor."""
    counts = {m: math.floor(CELLS_PER_BEAT * mix[m]) for m in mix}
    counts["cold"] = max(counts["cold"], math.ceil(CELLS_PER_BEAT * COLD_FLOOR))
    out: list[dict[str, Any]] = []
    for mode in ("exploration", "exploitation", "cold"):
        if counts[mode] > 0:
            out += sf.assign(counts[mode], mode, cells=cells, conn=conn)
    return out


# ----------------------------------------------------------------------------- the harvest

def _seat_rows(seats: tuple[str, ...], since: float, taken: set[str] | None = None
               ) -> tuple[list[dict[str, Any]], list[str]]:
    """The rows a seat donated inside the harvest window, and the files they came from.

    `taken` is the pass's ledger of what has already been harvested. TWO BEATS SHARE AN ORGAN --
    `china_miner` is on both ChinaScout and KoreaScout -- so without it the same donation file is
    read by both and its seat is PAID TWICE for one lead. A doubled lead count is a doubled
    denominator in every posterior downstream, which is worse than no attribution at all.
    """
    rows: list[dict[str, Any]] = []
    files: list[str] = []
    seen = taken if taken is not None else set()
    for seat in seats:
        for root in SEAT_ROOTS:
            d = Path(root) / seat
            try:
                entries = [e for e in os.scandir(d)
                           if e.is_file() and e.name.endswith((".json", ".jsonl"))
                           and e.stat().st_mtime >= since and e.path not in seen]
            except OSError:
                continue
            for e in sorted(entries, key=lambda x: -x.stat().st_mtime)[:8]:
                seen.add(e.path)
                doc = _read_json(Path(e.path), None)
                got = doc if isinstance(doc, list) else (
                    doc.get("rows") or doc.get("discoveries") or doc.get("items") or []
                    if isinstance(doc, dict) else [])
                new = [r for r in got if isinstance(r, dict)][:MAX_ROWS_PER_SEAT]
                if new:
                    rows += new
                    files.append(e.path)
    return rows[:MAX_ROWS_PER_SEAT], files


def _claim_rows(conn: Any, since_iso: str, taken: set[str] | None = None
                ) -> list[dict[str, Any]]:
    """Registry claims written inside the window, each counted by ONE beat (see `_seat_rows`)."""
    seen = taken if taken is not None else set()
    try:
        rows = [dict(r) for r in conn.execute(
            "SELECT claim_id, source_id, text, created_at FROM claims WHERE created_at >= ? "
            "ORDER BY created_at DESC LIMIT ?", (since_iso, MAX_ROWS_PER_SEAT))]
    except Exception:
        return []
    out = [r for r in rows if f"claim:{r['claim_id']}" not in seen]
    seen.update(f"claim:{r['claim_id']}" for r in out)
    return out


def _text_of(row: dict[str, Any]) -> str:
    parts = [str(row.get(k) or "") for k in ("text", "claim", "title", "mechanism", "description",
                                             "why", "url", "author", "summary")]
    return "\n".join(p for p in parts if p)


def urls_in(text: str) -> list[str]:
    """Links a claim CITES. `lead_schema.urls_in_text` owns this when it is importable, so the
    swarm and the lead schema can never disagree about what a citation is."""
    try:
        from libs.research.lead_schema import urls_in_text
        return list(urls_in_text(text, limit=MAX_EXPANSIONS))
    except Exception:
        out: list[str] = []
        for m in _URL_RE.finditer(text or ""):
            u = m.group(0).rstrip(".,;)")
            if u not in out:
                out.append(u)
        return out[:MAX_EXPANSIONS]


def _host(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower()
    except ValueError:
        return ""


def desk_vocabulary(conn: Any, cap: int = 2000) -> tuple[Counter, int]:
    """Document frequency over what the desk ALREADY reads: its registered sources and its claims.
    A term this pass uses heavily and that corpus barely uses is the name of something new."""
    df: Counter = Counter()
    n = 0
    try:
        rows = list(conn.execute("SELECT text FROM claims ORDER BY created_at DESC LIMIT ?",
                                 (cap,)))
    except Exception:
        rows = []
    docs = [str(r["text"] or "") for r in rows]
    with contextlib.suppress(Exception):
        docs += [str(r["meta_json"] or "") + " " + str(r["url"] or "")
                 for r in conn.execute("SELECT meta_json, url FROM sources LIMIT ?", (cap,))]
    for doc in docs:
        n += 1
        df.update(set(_tokens(doc)))
    return df, n


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(str(text or ""))
            if t.lower() not in _STOP and not t.isdigit()]


def terminology(texts: list[str], df: Counter, n_docs: int, top: int = TOP_TERMS
                ) -> list[dict[str, Any]]:
    """Top terms by tf x log((1 + N) / (1 + df)) against the desk's existing vocabulary."""
    tf: Counter = Counter()
    for t in texts:
        tf.update(_tokens(t))
    scored = [{"term": term, "tf": int(c),
               "tfidf": round(c * math.log((1.0 + n_docs) / (1.0 + df.get(term, 0))), 6)}
              for term, c in tf.items() if c >= 2]
    scored.sort(key=lambda r: (-r["tfidf"], r["term"]))
    return scored[:top]


def expansion_edges(rows: list[dict[str, Any]], df: Counter, n_docs: int) -> dict[str, list[Any]]:
    """AUTHORS, CITATIONS, REPOS, COMMUNITIES, DATASETS and TERMINOLOGY out of one pass's harvest.

    Every one is a SEARCH the desk has not run: the author has written elsewhere, the citation has
    a parent, the repository has an implementation, the community has the rest of the conversation,
    the dataset has the evidence, and the term names a thing nobody here has a word for.
    """
    authors: list[str] = []
    citations: list[str] = []
    repos: list[str] = []
    communities: list[str] = []
    datasets: list[str] = []
    texts: list[str] = []
    for row in rows:
        text = _text_of(row)
        texts.append(text)
        for key in ("author", "authors", "trader", "handle"):
            v = row.get(key)
            for a in (v if isinstance(v, list) else [v]):
                if a and str(a).strip() and str(a) not in authors:
                    authors.append(str(a).strip()[:80])
        for m in _AUTHOR_RE.finditer(text):
            a = m.group(1).strip()
            if a and a not in authors:
                authors.append(a[:80])
        for m in _HANDLE_RE.finditer(text):
            a = "@" + m.group(1)
            if a not in authors:
                authors.append(a)
        for url in [*urls_in(text), str(row.get("url") or "")]:
            if not url.startswith("http"):
                continue
            host = _host(url)
            low = url.lower()
            bucket = (repos if any(h in host for h in _REPO_HOSTS) else
                      datasets if any(h in low for h in _DATASET_HINTS) else
                      communities if any(h in host for h in _COMMUNITY_HOSTS) else citations)
            if url not in bucket:
                bucket.append(url)
        for ep in (row.get("endpoints") or []) if isinstance(row.get("endpoints"), list) else []:
            if str(ep) not in datasets:
                datasets.append(str(ep))
        for m in list(_DOI_RE.finditer(text)) + list(_ARXIV_RE.finditer(text)):
            cite = m.group(0)
            if cite not in citations:
                citations.append(cite)
    return {"authors": authors[:MAX_EXPANSIONS], "citations": citations[:MAX_EXPANSIONS],
            "repos": repos[:MAX_EXPANSIONS], "communities": communities[:MAX_EXPANSIONS],
            "datasets": datasets[:MAX_EXPANSIONS],
            "terminology": terminology(texts, df, n_docs)}


# -------------------------------------------------------------------- registering what it found

def _candidate_id(kind: str, value: str) -> str:
    if value.startswith("http"):
        u = urlparse(value)
        return f"{kind}:{(u.netloc or '').lower()}{u.path.rstrip('/')[:60]}"
    return f"{kind}:{sf._slug(value)[:60]}"


def _mandate_refused(value: str) -> bool:
    """Crypto-exchange-native ground is never hunted again. Fusion's crypto CFDs are part of the
    MT5 universe and are reached through the broker, never through an exchange's own site."""
    low = str(value or "").lower()
    return any(h in low for h in CRYPTO_HOSTS)


def register_expansions(parent_id: str, edges: dict[str, list[Any]], conn: Any,
                        dry: bool = False) -> dict[str, Any]:
    """Every edge becomes a CANDIDATE source with its parent's name on it. `last_crawled` stays
    null and `crawl_allowed` is the parent's ROI gate: registration is not permission to fetch."""
    allowed, why = sf.may_crawl(parent_id, conn=conn)
    out = {"registered": 0, "existing": 0, "refused_by_mandate": 0, "crawl_allowed": allowed,
           "gate": why, "ids": []}
    kinds = (("repos", "repo", "code"), ("communities", "community", "community"),
             ("datasets", "dataset", "dataset"), ("citations", "cite", "web"),
             ("authors", "author", "author"), ("terminology", "term", "terminology"))
    for key, prefix, kind in kinds:
        for item in edges.get(key) or []:
            value = str(item["term"] if isinstance(item, dict) else item)
            if _mandate_refused(value):
                out["refused_by_mandate"] += 1
                continue
            sid = _candidate_id(prefix, value)
            out["ids"].append(sid)
            if dry:
                continue
            created = sf.register_source(
                sid, url=value if value.startswith("http") else "", kind=kind,
                discovered_from=parent_id, discovered_via=f"expansion:{key}", status="candidate",
                meta={"value": value, "crawl_allowed": allowed, "gate": why,
                      "found_at": _now()}, conn=conn)
            out["registered" if created else "existing"] += 1
    return out


def _attribute(rows: list[dict[str, Any]], seats: tuple[str, ...], conn: Any,
               dry: bool = False) -> dict[str, int]:
    """Pay the sources for what this pass produced: leads per source, on `source_yield`."""
    per: Counter = Counter()
    for row in rows:
        name = str(row.get("source") or "").strip() or (seats[0] if seats else "")
        if name:
            per[f"seat:{name}"] += 1
    if not dry:
        for sid, n in per.items():
            sf.register_source(sid, kind="seat", discovered_via="seat", discovered_from="swarm",
                               conn=conn)
            sf.bump_source_yield(sid, conn=conn, leads=n, claims=n)
    return dict(per)


# ------------------------------------------------------------------------------------ the pass

def run_beat(beat: dict[str, Any], budget_row: dict[str, Any], cells: list[dict[str, Any]],
             conn: Any, df: Counter, n_docs: int, since: float, dry: bool,
             free_mb: float | None, taken: set[str] | None = None) -> dict[str, Any]:
    """ONE BEAT: pick cells, run its organs at them, read what came back, pay the sources."""
    t0 = time.monotonic()
    budget = float(budget_row["budget_s"])
    organs = [o for o in beat["organs"] if (ROOT / o).is_file()]
    ran: list[dict[str, Any]] = []
    steered: list[str] = []
    slice_s = budget / max(1, len(organs))
    for organ in organs:
        args, used = steer_args(organ, cells, slice_s)
        steered += used
        if dry:
            ran.append({"organ": organ, "args": args, "status": "DRY_RUN", "steered_by": used})
            continue
        if free_mb is not None and free_mb < MIN_FREE_MB:
            ran.append({"organ": organ, "args": args, "steered_by": used,
                        "status": f"STOOD_DOWN: {free_mb:.0f}MB free < {MIN_FREE_MB:.0f}MB"})
            continue
        res = run_organ(organ, args, max(30.0, slice_s))
        ran.append({"organ": organ, "args": args, "steered_by": used, **res})
        if time.monotonic() - t0 > budget:
            break
    seats = tuple(dict.fromkeys(s for o in beat["organs"] for s in seats_of(o)))
    taken = taken if taken is not None else set()
    rows, files = _seat_rows(seats, since, taken)
    rows += _claim_rows(conn, datetime.fromtimestamp(since, tz=UTC).isoformat(timespec="seconds"),
                        taken)
    edges = expansion_edges(rows, df, n_docs)
    per_source = _attribute(rows, seats, conn, dry=dry)
    parent = next(iter(per_source), f"seat:{seats[0]}" if seats else "")
    expanded = (register_expansions(parent, edges, conn, dry=dry) if parent else
                {"registered": 0, "existing": 0, "refused_by_mandate": 0, "crawl_allowed": False,
                 "gate": f"{UNMEASURED} -- this beat has no seat to attribute a parent to"})
    if not dry:
        for cell in cells:
            sf.mark_scouted(cell["cell"], conn=conn)
        reg.worker_heartbeat(f"scout:{beat['beat']}", kind="scout", beat=beat["beat"],
                             department="intelligence", status="running",
                             current_campaign=cells[0]["cell"] if cells else "", generator="swarm",
                             campaigns_done_inc=1, conn=conn)
    status = ("DRY_RUN" if dry else "NO_ORGAN" if not organs else
              "ok" if any(r.get("status") == "ok" for r in ran) else "no_organ_succeeded")
    return {
        "beat": beat["beat"], "cells": [c["cell"] for c in cells],
        "modes": [c["mode"] for c in cells], "organs_run": ran,
        "organs_missing": [o for o in beat["organs"] if not (ROOT / o).is_file()],
        "seconds": round(time.monotonic() - t0, 2), "budget_s": budget,
        "leads": len(rows), "leads_by_source": per_source, "harvest_files": len(files),
        "harvest_basis": (f"seat donation(s) from {list(seats)} inside the window"
                          if seats else
                          f"{UNMEASURED} -- the roster declares no seat directory for this beat's "
                          f"organs, so what they produced is not attributable per source here"),
        "new_sources": expanded["registered"], "expansion": expanded,
        "steerable": bool(steered), "steered_by": sorted(set(steered)),
        "steering_note": ("" if steered else
                          "no organ on this beat accepts a ground/region/source argument today; "
                          "run unparameterised and the cells are a RECORD of intent, not a steer"),
        "status": status, "edges": {k: len(v) for k, v in edges.items()},
        "_edges": edges,
    }


def run_pass(budget_s: float = BUDGET_S, dry: bool = False, conn: Any = None,
             beats: tuple[dict[str, Any], ...] = DECLARED_BEATS) -> dict[str, Any]:
    """One swarm pass over every declared beat, inside one shared wall budget."""
    c = conn or reg.connect()
    t0 = time.monotonic()
    since = time.time() - HARVEST_LOOKBACK_S
    try:
        mix = sf.search_mix()
        cells_all = sf.build_cells(conn=c)
        if not dry:
            # A dry run PLANS. Refreshing the durable map is a write, and a flag whose promise is
            # "runs nothing" must not leave a row behind either.
            sf.write_frontier_map(cells_all, conn=c)
        df, n_docs = desk_vocabulary(c)
        rows = plan(budget_s, conn=c, beats=beats)
        by_name = {b["beat"]: b for b in beats}
        free_mb = free_phys_mb()
        out: list[dict[str, Any]] = []
        taken: set[str] = set()           # one harvest is counted once, whichever beat reaches it
        for budget_row in rows:
            beat = by_name[budget_row["beat"]]
            cells = lane_cells(budget_row, cells_all, c, mix)
            out.append(run_beat(beat, budget_row, cells, c, df, n_docs, since, dry, free_mb,
                                taken))
            if time.monotonic() - t0 > budget_s:
                break
        merged: dict[str, list[Any]] = {k: [] for k in ("authors", "citations", "repos",
                                                        "communities", "datasets", "terminology")}
        for b in out:
            for k, v in b.pop("_edges").items():
                merged[k] += [x for x in v if x not in merged[k]]
        modes = [m for b in out for m in b["modes"]]
        cold_share = round(modes.count("cold") / len(modes), 6) if modes else None
        return {
            "at": _now(), "pass": {"budget_s": budget_s, "seconds": round(time.monotonic() - t0, 2),
                                   "beats_planned": len(rows), "beats_run": len(out),
                                   "dry_run": dry, "free_phys_mb": free_mb},
            "beats": out, "search_mix": mix, "plan": rows,
            "expansions": {k: v[:MAX_EXPANSIONS] for k, v in merged.items()},
            "roi_top": [{"source_id": r["source_id"], "roi_score": r["roi_score"],
                         "p_testable": r["p_testable"]["p"], "leads": r["leads"]}
                        for r in sf.roi_table(conn=c, limit=10)],
            "cold_share_actual": cold_share, "cold_floor": COLD_FLOOR,
            "unmeasured": {
                "n_beats_unsteerable": sum(1 for b in out if not b["steerable"]),
                "n_beats_without_organ": sum(1 for b in out if b["status"] == "NO_ORGAN"),
                "n_beats_unmeasured_roi": sum(1 for r in rows if not r["measured"]),
                "n_beats_without_leads": sum(1 for b in out if not b["leads"]),
                "free_memory": ("UNMEASURED -- GlobalMemoryStatusEx unavailable on this platform"
                                if free_mb is None else f"{free_mb:.0f}MB free"),
                "crawl_gate": (f"a candidate source is crawled only once its parent's "
                               f"P(testable) > {sf.CRAWL_P_TESTABLE}; registration is not "
                               f"permission"),
            },
            "rule": ("every productive source spawns searches for its authors, citations, repos, "
                     "communities, datasets and terminology; cold search never falls below its "
                     "floor"),
        }
    finally:
        if conn is None:
            c.close()


def _summary(doc: dict[str, Any]) -> list[str]:
    p, u = doc["pass"], doc["unmeasured"]
    top = sorted(doc["beats"], key=lambda b: -b["leads"])[:3]
    return [
        f"scout swarm: {p['beats_run']}/{p['beats_planned']} beat(s) in {p['seconds']}s "
        f"of {p['budget_s']}s{' (DRY RUN)' if p['dry_run'] else ''}",
        f"  mix {doc['search_mix']}  cold actual {doc['cold_share_actual']} "
        f"(floor {doc['cold_floor']})",
        "  leads: " + ("  ".join(f"{b['beat']}={b['leads']}" for b in top) or "NONE"),
        "  expansions: " + "  ".join(f"{k}={len(v)}" for k, v in doc["expansions"].items()),
        f"  {u['n_beats_unsteerable']} beat(s) cannot be steered yet, "
        f"{u['n_beats_without_organ']} have no organ in this tree, "
        f"{u['n_beats_unmeasured_roi']} have UNMEASURED ROI",
    ]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="M8: the scout swarm over the nineteen beats")
    ap.add_argument("--once", action="store_true", help="one pass, then exit")
    ap.add_argument("--dry-run", action="store_true", help="plan, run nothing, write nothing")
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    a = ap.parse_args(argv)
    handle = claim_singleton()
    if handle is None:
        print("scout swarm: another swarm holds the slot; exiting", flush=True)
        return 0
    try:
        while True:
            started = time.monotonic()
            doc = run_pass(budget_s=a.budget_s, dry=a.dry_run)
            if not a.dry_run:
                sf._atomic(OUT, doc)
            for line in _summary(doc):
                print(line, flush=True)
            print(f"  {'wrote' if not a.dry_run else 'DRY RUN, wrote nothing:'} {OUT}", flush=True)
            if a.once or a.dry_run:
                return 0
            time.sleep(max(30.0, MIN_CYCLE_S - (time.monotonic() - started)))
    finally:
        with contextlib.suppress(OSError):
            handle.close()


if __name__ == "__main__":
    raise SystemExit(main())
