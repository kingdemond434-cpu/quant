"""The public-GitHub repo miner: awesome-lists and quant strategy repos read into hypothesis rows.

    seeds (data/github_repo_seeds.json): lists, repos (the EliteQuant 20-repo batch), searches
      -> REST API, anonymous or GITHUB_TOKEN, paced on the API's own X-RateLimit headers
      -> lists walked for the repos they link (depth-bounded), searches paged on a pushed cursor
      -> each repo: metadata (licence, pushed_at) -> README prose claims
                    (libs.research.mechanism_claims) + strategy files read statically
                    (cell_emitter.rows_for_file, the desk's indicator-call reader)
      -> family + instruments mapped (the compiler's own vocabulary; universe_policy lanes)
      -> deduped against every row this miner ever donated
      -> data/intelligence/github_repos/  (lane `repo`)
         data/intelligence/firm_mining/   (lane `firm`: replications of the named firms' work)
      -> miner_candidate_compiler -> docket -> gauntlet

WHY THIS AND NOT A FOURTH COPY. Three organs already touch GitHub and none of them is this:
`side_channels/github_miner.py` keeps repo NAMES that match ten literal queries and writes rows no
family can be compiled from; `research/repo_miner.py` reads a fixed watchlist's READMEs into the
deepening queue, daily; `research/cell_emitter.py` reads the CODE of a hand-curated ground roster.
None of them DISCOVERS: a repository nobody typed into a file is never read. This organ is the
discovery and prose half, and it reuses the other two's readers rather than writing a third --
the claim grammar from `mechanism_claims`, the family vocabulary from the compiler, the code
reader from `cell_emitter`.

WHY `firm_mining` LIVES HERE (row 100, 2026-11-03). PRODUCER_YIELD read `firm_mining` DEAD (0 rows
in 3 days, no replacement declared) while `quantconnect` wrote 6,876. The cause was not a broken
miner: there was NO miner. The seat was a single hand donation (2026-09-27, 168 hypotheses from
320 sources, docs/research/firm_mining/README.md) with no clock behind it, so the moment its files
aged past the window the census was right to call it dead -- and its own README says the rows
"age out of the docket unless they are re-donated". Re-donating the same 168 rows would have
turned the census green and mined nothing. The firm lane mines the ground the seat names --
public replications of AQR, Man AHL, Bridgewater, WorldQuant, Renaissance, Two Sigma and Winton
work -- on a pushed-date cursor, so it keeps finding NEW repositories. The liveness check below
reads RED when the lane reaches GitHub and still donates nothing, which is the failure that went
unseen for five weeks.

LICENCE. Nothing fetched is executed (static text only; a test walks the AST for it). A verbatim
quote is kept only under a copy-permitted licence (`libs.data.datahub.COPY_PERMITTED`); any other
repository's claim is carried as a description this module writes from the extracted fields.

CRYPTO-EXCHANGE GROUND (standing order 2026-08-18). A repository whose metadata names a
crypto-exchange venue is never queued, and a claim that names one is dropped and COUNTED.

THE YIELD IS MEASURED, NEVER CLAIMED. `reports/GITHUB_REPO_MINER.json` carries per-pass API calls,
the rate limit before and after, per-repo outcome, rows per seat, duplicates dropped, and a
per-seat liveness verdict over the trailing 72 h (the PRODUCER_YIELD window):
    GREEN       rows donated in the window
    RED         at least one pass reached GitHub in the window and donated nothing
    UNMEASURED  no pass reached GitHub in the window (rate-limited, offline, never ran)
`--check` reads that artifact and exits 1 on RED or on an artifact older than its clock allows.

    python desks/mt5/research/github_repo_miner.py --once --budget-s 300
    python desks/mt5/research/github_repo_miner.py --check
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

ORGAN = "github_repo_miner"
SEEDS = _DESK / "data" / "github_repo_seeds.json"
STATE = _DESK / "data" / "github_repo_miner_state.json"
INTEL = _DESK / "data" / "intelligence"
REPORT = _DESK / "reports" / "GITHUB_REPO_MINER.json"
UNIVERSE = _DESK / "data" / "universe" / "universe.json"
API = "https://api.github.com"
RAW = "https://raw.githubusercontent.com"
UNMEASURED = "UNMEASURED"

#: lane -> intelligence seat directory. The firm lane writes the seat the census already tracks.
SEATS: dict[str, str] = {"repo": "github_repos", "firm": "firm_mining"}

#: The liveness window: the same three days PRODUCER_YIELD judges a seat over.
YIELD_WINDOW_H = 72.0
#: The leg's artifact is late past this. It runs inside the intel department's resident pass,
#: whose length is set by its forests (3,300 s caps), so one hour is the cadence and six is the
#: point at which "slow pass" has become "not running".
MAX_REPORT_AGE_H = 6.0
#: The issue board raises any `<repo>/data/*_ALARM.txt` it knows (research/issue_board.ALARMS).
ALARM = _ROOT / "data" / "GITHUB_MINER_ALARM.txt"
#: Core API calls left for the other organs sharing this host's quota (cell_emitter's trees,
#: repo_miner's READMEs). Rate-limit COMPLIANCE, not a mining cap: with a token it is 6% of 5,000.
RESERVE_ANON, RESERVE_TOKEN = 10, 300
#: Seconds held back to write donations, state and the report.
WRITE_RESERVE_S = 20.0
#: Memory bounds on the state file (an 8 GB build box shares it). Oldest entries leave first; a
#: claim forgotten this way can be donated once more, which the compiler's own dedup absorbs.
SEEN_CAP, QUEUE_CAP, HISTORY_CAP = 60_000, 20_000, 500

#: Path segments of github.com URLs that are site pages, never a repository owner.
_NOT_OWNERS = frozenset({"topics", "sponsors", "orgs", "features", "marketplace", "about",
                         "settings", "login", "join", "explore", "trending", "collections",
                         "apps", "site", "pricing", "enterprise", "security", "customer-stories",
                         "readme", "notifications", "issues", "pulls", "search", "contact"})
_GH_LINK = re.compile(r"github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)")

#: (status, body text, response headers). Injectable so tests never touch the network.
Fetch = Callable[[str, str], tuple[int | None, str, dict[str, str]]]


# ============================================================================ network

def _http_get(url: str, accept: str = "") -> tuple[int | None, str, dict[str, str]]:
    """GET with the host's token on api.github.com only. Never raises; the token is never logged."""
    hdr = {"User-Agent": "quant-github-repo-miner"}
    if accept:
        hdr["Accept"] = accept
    tok = os.environ.get("GITHUB_TOKEN")
    if tok and url.startswith(API):
        hdr["Authorization"] = f"Bearer {tok}"
    ctx = None
    with contextlib.suppress(Exception):
        from libs.data.polite_fetch import ssl_context
        ctx = ssl_context()
    try:
        req = urllib.request.Request(url, headers=hdr)
        with urllib.request.urlopen(req, timeout=20, context=ctx) as fh:
            body = fh.read(2_000_000).decode("utf-8", errors="replace")
            return int(getattr(fh, "status", 200) or 200), body, dict(fh.headers.items())
    except urllib.error.HTTPError as exc:
        heads = dict(exc.headers.items()) if exc.headers is not None else {}
        exc.close()
        return int(exc.code), "", heads
    except Exception as exc:                                       # transport, TLS, timeout
        return None, "", {"x-error": f"{type(exc).__name__}: {str(exc)[:120]}"}


class Quota:
    """The API's own counters, read from every response. A pass stops when they say so."""

    def __init__(self, core: int | None, search: int | None, reserve: int) -> None:
        self.core, self.search, self.reserve = core, search, reserve
        self.calls: Counter[str] = Counter()
        self.exhausted = ""

    def may(self, kind: str) -> bool:
        left = self.search if kind == "search" else self.core
        if left is None:                       # an unread counter: try, and read the headers
            return not self.exhausted
        floor = 1 if kind == "search" else self.reserve
        if left <= floor:
            self.exhausted = self.exhausted or f"{kind} quota at {left} (reserve {floor})"
            return False
        return True

    def note(self, kind: str, headers: dict[str, str]) -> None:
        self.calls[kind] += 1
        low = {k.lower(): v for k, v in headers.items()}
        with contextlib.suppress(KeyError, TypeError, ValueError):
            left = int(low["x-ratelimit-remaining"])
            if kind == "search":
                self.search = left
            else:
                self.core = left


def read_quota(fetch: Fetch) -> tuple[dict[str, Any], Quota]:
    """GET /rate_limit (free: it does not count against the quota it reports)."""
    reserve = RESERVE_TOKEN if os.environ.get("GITHUB_TOKEN") else RESERVE_ANON
    status, text, _h = fetch(f"{API}/rate_limit", "application/vnd.github+json")
    snap: dict[str, Any] = {"auth": "token" if os.environ.get("GITHUB_TOKEN") else "anonymous",
                            "status": status, "reserve": reserve}
    core = search = None
    if status == 200 and text:
        with contextlib.suppress(ValueError, AttributeError, TypeError):
            res = json.loads(text).get("resources") or {}
            core = int(res["core"]["remaining"])
            search = int(res["search"]["remaining"])
            snap.update({"core_remaining": core, "core_limit": res["core"].get("limit"),
                         "search_remaining": search})
    return snap, Quota(core, search, reserve)


def _api(fetch: Fetch, quota: Quota, path: str, kind: str = "core") -> tuple[int | None, Any]:
    if not quota.may(kind):
        return None, None
    status, text, heads = fetch(f"{API}{path}", "application/vnd.github+json")
    quota.note(kind, heads)
    if status == 403 and str({k.lower(): v for k, v in heads.items()}
                             .get("x-ratelimit-remaining")) == "0":
        quota.exhausted = quota.exhausted or f"{kind} quota hit 0 (HTTP 403)"
    if status is None or not (200 <= status < 300) or not text:
        return status, None
    try:
        return status, json.loads(text)
    except ValueError:
        return status, None


# ============================================================================ reading

def _load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _atomic(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False, default=str), "utf-8")
    os.replace(tmp, path)


def _universe(path: Path = UNIVERSE) -> set[str]:
    d = _load(path, {})
    return {str(k).upper() for k in d} if isinstance(d, dict) else set()


def _copy_allowed(lic: str) -> bool:
    try:
        from libs.data.datahub import copy_allowed
        return bool(copy_allowed(lic))
    except Exception:
        return lic in {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "Unlicense",
                       "CC0-1.0"}


def repo_links(readme: str, self_full: str = "") -> list[str]:
    """owner/repo for every github.com repository a README links, in order, deduplicated."""
    out: dict[str, None] = {}
    for owner, name in _GH_LINK.findall(readme or ""):
        name = re.sub(r"\.git$", "", name.split("#")[0].split("?")[0]).rstrip(".")
        if not name or owner.lower() in _NOT_OWNERS or name.lower() in {"blob", "tree", "wiki"}:
            continue
        full = f"{owner}/{name}"
        if full.lower() != self_full.lower():
            out.setdefault(full, None)
    return list(out)


#: README names tried on the raw host, in order. raw.githubusercontent.com is outside the API
#: quota, so reading the README there leaves the anonymous 60/h for metadata and trees.
README_NAMES = ("README.md", "readme.md", "README.MD", "Readme.md", "README.rst", "README")


def readme_text(fetch: Fetch, full: str, branch: Any = None) -> str | None:
    """The README's text from the raw host, or None when no README name answers."""
    ref = quote(str(branch)) if branch else "HEAD"
    for name in README_NAMES:
        status, text, _h = fetch(f"{RAW}/{full}/{ref}/{name}", "")
        if status and 200 <= status < 300 and text:
            return text
    return None


def _crypto_venue(text: str) -> str | None:
    try:
        from libs.research.mechanism_claims import forbidden_venue
        return forbidden_venue(text or "")
    except Exception:
        return None


_VENUE_NATIVE = re.compile(r"funding[ _]?rate|perpetual|\bperps?\b|liquidation|open[ _]?interest|"
                           r"order[ _]?book", re.I)


def _is_crypto(sym: str) -> bool:
    try:
        from research import universe_policy as up
        return up.asset_class_of(sym) in {"crypto", "cryptocurrency"}
    except Exception:
        return False


def _families(text: str) -> list[tuple[str, str]]:
    try:
        import miner_candidate_compiler as mcc
        return list(mcc.text_families(text.lower()))
    except Exception:
        return []


def _may(sym: str, family: str | None) -> bool:
    try:
        from research import universe_policy as up
        return bool(up.may_hypothesise(sym, family))
    except Exception:
        return False


def claim_rows(full: str, meta: dict[str, Any], text: str, seed: dict[str, Any],
               universe: set[str], *, now: str) -> tuple[list[dict[str, Any]], Counter[str]]:
    """Hypothesis rows for the prose claims in one repository's description + README."""
    from libs.research.mechanism_claims import extract_claims
    drops: Counter[str] = Counter()
    lane = str(seed.get("lane") or "repo")
    lic = str(meta.get("license") or "NONE")
    permissive = _copy_allowed(lic)
    rows: list[dict[str, Any]] = []
    for c in extract_claims(text, max_claims=60):
        claim = str(c.get("claim") or "")
        if _crypto_venue(claim):
            drops["crypto_exchange_venue"] += 1
            continue
        fams = _families(claim)
        fam = fams[0][0] if fams else None
        inst = c.get("instruments") or {}
        named = [s.upper() for s in inst.get("analogues") or [] if s.upper() in universe]
        if named and _VENUE_NATIVE.search(claim):
            # Funding, perpetuals, liquidations and exchange books do not exist on a CFD: such a
            # claim keeps only its non-crypto instruments (cell_emitter's rule, on prose).
            kept = [s for s in named if not _is_crypto(s)]
            drops["crypto_venue_native_mechanism"] += len(named) - len(kept)
            if not kept:
                continue
            named = kept
        basis = "named_in_text"
        if not named:
            named = [s for s in seed.get("default_instruments") or [] if s.upper() in universe]
            basis = "seed_default (declared transfer: the text names no instrument)"
        symbols = [s for s in named if _may(s, fam)]
        if not symbols:
            drops["no_admissible_instrument" if not named else "lane_fenced"] += 1
            continue
        desc = (f"{full} README states a {c.get('mechanism_class') or 'mechanism'} rule"
                f" on {', '.join(inst.get('mentioned') or symbols)}: quantities "
                f"{', '.join(c.get('quantities') or [])}; direction "
                f"{', '.join(c.get('direction') or [])}; horizon "
                f"{', '.join(c.get('horizon') or [])}"
                + (f"; mapped by the phrase '{fams[0][1]}' to {fam}" if fam else
                   "; no registered family named, extract the exact rule"))
        row: dict[str, Any] = {
            "kind": "hypothesis", "source": SEATS[lane], "organ": ORGAN, "lane": lane,
            "repo": full, "url": meta.get("url"), "file": "README", "license": lic,
            "copy_allowed": permissive, "code_copied": False, "stars": meta.get("stars"),
            "pushed_at": meta.get("pushed_at"), "batch": seed.get("batch"),
            "symbols": symbols, "instrument_basis": basis,
            "mechanism": desc, "testable_claim": desc,
            "mechanism_class": c.get("mechanism_class"), "horizon": c.get("horizon"),
            "claim_hash": c.get("claim_hash"), "mined_at": now,
            "evidence": "PUBLIC_REPO_CLAIM",
            "title": f"{full}: {fam or c.get('mechanism_class') or 'claim'}",
        }
        if fam:
            row["family"] = fam
        if permissive:
            # Copy-permitted: the claim itself is the strongest witness, carried verbatim.
            row["quote"] = claim[:400]
            row["text"] = claim[:400]
        if lane == "firm":
            row.update({"firm": seed.get("firm"), "cluster": "github_replications"})
        rows.append(row)
    return rows, drops


def code_rows(fetch: Fetch, quota: Quota, full: str, meta: dict[str, Any], seed: dict[str, Any],
              policy: dict[str, Any], universe: set[str], cursor: int, deadline: float,
              *, now: str) -> tuple[list[dict[str, Any]], int, Counter[str]]:
    """Strategy files read by the desk's static indicator reader. (rows, next cursor, drops)."""
    drops: Counter[str] = Counter()
    branch = str(meta.get("default_branch") or "master")
    _s, tree = _api(fetch, quota, f"/repos/{full}/git/trees/{quote(branch)}?recursive=1")
    if not isinstance(tree, dict):
        drops["tree_unreached"] += 1
        return [], cursor, drops
    exts = tuple(str(e).lower() for e in policy.get("code_extensions") or [".py"])
    pat = re.compile(str(policy.get("code_path_pattern") or r"(?i)strateg"))
    paths = sorted(str(t.get("path")) for t in tree.get("tree") or []
                   if isinstance(t, dict) and t.get("type") == "blob"
                   and str(t.get("path")).lower().endswith(exts) and pat.search(str(t.get("path"))))
    if not paths:
        drops["no_strategy_files"] += 1
        return [], cursor, drops
    try:
        import cell_emitter as ce
    except Exception:
        drops["code_reader_unavailable"] += 1
        return [], cursor, drops
    off = cursor % len(paths)
    batch = (paths[off:] + paths[:off])[:int(policy.get("files_per_repo") or 6)]
    lane = str(seed.get("lane") or "repo")
    ground = {"name": full, "region": seed.get("region"), "license": meta.get("license"),
              "default_instruments": seed.get("default_instruments") or [], "venue": "open"}
    rows: list[dict[str, Any]] = []
    for p in batch:
        if time.monotonic() > deadline:
            drops["budget_stop"] += 1
            break
        url = f"{RAW}/{full}/{branch}/{quote(p)}"
        status, src, _h = fetch(url, "")                   # raw host: outside the API quota
        if not (status and 200 <= status < 300 and src):
            drops[f"fetch_{status or 'transport'}"] += 1
            continue
        if len(src.encode("utf-8", "replace")) > int(policy.get("max_file_bytes") or 400_000):
            drops["file_too_large"] += 1
            continue
        got, _reading, d = ce.rows_for_file(src, p, url, ground, universe)
        drops.update(d)
        for r in got:
            r.update({"source": SEATS[lane], "organ": ORGAN, "lane": lane, "repo": full,
                      "mined_at": now, "batch": seed.get("batch"),
                      "pushed_at": meta.get("pushed_at")})
            if lane == "firm":
                r.update({"firm": seed.get("firm"), "cluster": "github_replications"})
        rows.extend(got)
    return rows, (off + len(batch)) % len(paths), drops


def row_key(row: dict[str, Any]) -> str:
    """The identity a row is deduplicated on: what was claimed, where, on which instruments."""
    basis = "|".join(str(x) for x in (
        row.get("repo"), row.get("file"), row.get("claim_hash") or row.get("content_sha256"),
        row.get("family"), ",".join(sorted(row.get("symbols") or []))))
    return hashlib.sha256(basis.encode()).hexdigest()[:24]


# ============================================================================ liveness

def liveness(history: list[dict[str, Any]], now: datetime,
             window_h: float = YIELD_WINDOW_H) -> dict[str, dict[str, Any]]:
    """Per seat: GREEN, RED or UNMEASURED over the trailing window. Never a blank, never a zero
    for a window in which nothing reached GitHub (L1.28a)."""
    cut = now - timedelta(hours=window_h)
    inside = []
    for h in history:
        with contextlib.suppress(KeyError, ValueError, TypeError):
            if datetime.fromisoformat(str(h["utc"])) >= cut:
                inside.append(h)
    reached = [h for h in inside if h.get("online")]
    out: dict[str, dict[str, Any]] = {}
    for lane, seat in SEATS.items():
        n = sum(int((h.get("rows") or {}).get(seat) or 0) for h in reached)
        if not reached:
            out[seat] = {"verdict": UNMEASURED, "rows_in_window": None, "passes_online": 0,
                         "why": (f"no pass reached GitHub in {window_h:g}h ({len(inside)} "
                                 f"pass(es) ran; rate limit, network or no clock)")}
        elif n > 0:
            out[seat] = {"verdict": "GREEN", "rows_in_window": n, "passes_online": len(reached)}
        else:
            out[seat] = {"verdict": "RED", "rows_in_window": 0, "passes_online": len(reached),
                         "why": (f"{len(reached)} pass(es) reached GitHub in {window_h:g}h and "
                                 f"donated nothing new to {seat} (lane {lane!r}): the seeds and "
                                 f"the discovered queue are mined out or the readers drop "
                                 f"everything -- widen the searches/lists in {SEEDS.name} or "
                                 f"read the pass drops")}
    return out


# ============================================================================ the pass

def _due(rec: dict[str, Any] | None, now: datetime, rescan_h: float) -> bool:
    if not rec or not rec.get("scanned_utc"):
        return True
    try:
        return now - datetime.fromisoformat(str(rec["scanned_utc"])) >= timedelta(hours=rescan_h)
    except ValueError:
        return True


def run(*, budget_s: float = 300.0, write: bool = True, fetch: Fetch | None = None,
        seeds: Path = SEEDS, state_path: Path = STATE, intel_dir: Path = INTEL,
        report_path: Path = REPORT, universe_path: Path = UNIVERSE,
        now: datetime | None = None) -> dict[str, Any]:
    t0 = time.monotonic()
    with contextlib.suppress(ValueError):
        cap = float(os.environ.get("QUANT_LEG_BUDGET_S") or 0)
        if cap:
            budget_s = min(budget_s, cap - WRITE_RESERVE_S)
    deadline = t0 + max(1.0, budget_s)
    fetch = fetch or _http_get
    now = now or datetime.now(tz=UTC)
    stamp = now.isoformat(timespec="seconds")
    reg = _load(seeds, {})
    policy = dict(reg.get("policy") or {})
    rescan_h = float(168 if policy.get("rescan_after_h") is None else policy["rescan_after_h"])
    universe = _universe(universe_path)
    state = _load(state_path, {})
    repos_st: dict[str, dict[str, Any]] = dict(state.get("repos") or {})
    seen: dict[str, str] = dict(state.get("seen") or {})
    queue: list[dict[str, Any]] = [q for q in state.get("queue") or [] if isinstance(q, dict)]
    search_cursor: dict[str, str] = dict(state.get("search_cursor") or {})
    history: list[dict[str, Any]] = [h for h in state.get("history") or [] if isinstance(h, dict)]

    if not universe:
        # AN UNREADABLE UNIVERSE IS UNMEASURED (cell_emitter's #116 rule): every claim would
        # drop as no_admissible_instrument and be recorded as mined.
        doc = {"generated_utc": stamp, "organ": ORGAN, "mode": "LIVE",
               "verdict": UNMEASURED, "liveness": liveness(history, now),
               "why": f"{UNMEASURED}: universe registry {universe_path} missing or unreadable"}
        if write:
            _atomic(report_path, doc)
        return doc

    quota_snap, quota = read_quota(fetch)
    per_repo: dict[str, dict[str, Any]] = {}
    drops: Counter[str] = Counter()
    rows: list[dict[str, Any]] = []
    discovered = 0
    dupes = 0
    known = {str(s.get("repo")).lower() for s in reg.get("repos") or [] if s.get("repo")}
    known |= {str(s.get("repo")).lower() for s in reg.get("lists") or [] if s.get("repo")}
    known |= {k.lower() for k in repos_st}
    known |= {str(q.get("repo")).lower() for q in queue}

    def enqueue(full: str, lane: str, firm: Any, via: str, depth: int) -> None:
        nonlocal discovered
        if full.lower() in known or len(queue) >= QUEUE_CAP:
            return
        known.add(full.lower())
        queue.append({"repo": full, "lane": lane, "firm": firm, "via": via, "depth": depth,
                      "queued_utc": stamp})
        discovered += 1

    # 1. SEARCHES, on the search quota (separate from core). A pushed-date cursor per query makes
    #    every pass a delta: only repositories pushed since the last page are new to it.
    for s in reg.get("searches") or []:
        if time.monotonic() > deadline or not quota.may("search"):
            break
        q = str(s.get("q") or "")
        since = search_cursor.get(q, "2015-01-01")
        _st, res = _api(fetch, quota, "/search/repositories?sort=updated&order=asc&per_page=50"
                        f"&q={quote(q + ' pushed:>' + since)}", kind="search")
        if not isinstance(res, dict):
            continue
        newest = since
        for it in res.get("items") or []:
            full = str(it.get("full_name") or "")
            if not full:
                continue
            newest = max(newest, str(it.get("pushed_at") or "")[:10] or newest)
            if _crypto_venue(f"{full} {it.get('description') or ''}"):
                drops["crypto_exchange_repo"] += 1
                continue
            enqueue(full, str(s.get("lane") or "repo"), s.get("firm"), f"search:{q}", 1)
        search_cursor[q] = newest

    # 2. WORK ORDER: the seeded batch, then the lists, then the discovered queue (oldest first).
    work: list[tuple[dict[str, Any], str]] = []
    for s in reg.get("repos") or []:
        disp = str(s.get("disposition") or "mine")
        if not s.get("repo") or disp in {"not_relevant", "method_only"}:
            per_repo[str(s.get("repo") or s.get("name"))] = {"status": disp.upper(),
                                                            "why": s.get("why")}
            continue
        work.append((s, "list" if disp == "list" else "repo"))
    work += [({**s, "lane": s.get("lane") or "repo", "depth": 0}, "list")
             for s in reg.get("lists") or [] if s.get("repo")]
    queued = list(queue)
    for qe in queued:
        tail = str(qe.get("repo")).split("/")[-1].lower()
        work.append((qe, "list" if tail.startswith("awesome") and int(qe.get("depth") or 0) <
                     int(policy.get("list_depth") or 2) else "repo"))

    lane_reached: Counter[str] = Counter()
    for seed, kind in work:
        full = str(seed["repo"])
        rec = repos_st.get(full)
        if not _due(rec, now, rescan_h):
            continue
        if time.monotonic() > deadline or not quota.may("core"):
            per_repo.setdefault(full, {"status": "NOT_REACHED_THIS_PASS",
                                       "why": quota.exhausted or "budget"})
            continue
        lane = str(seed.get("lane") or "repo")
        status, meta_raw = _api(fetch, quota, f"/repos/{full}")
        via = "api"
        if status in (404, 451):                # gone or blocked: a verdict about the repo
            per_repo[full] = {"status": f"UNREACHED: HTTP {status}"}
            repos_st[full] = {"scanned_utc": stamp, "status": f"HTTP {status}"}
            queue[:] = [x for x in queue if x.get("repo") != full]
            continue
        if not isinstance(meta_raw, dict):
            if quota.exhausted:
                per_repo[full] = {"status": "NOT_REACHED_THIS_PASS", "why": quota.exhausted}
                continue
            # THE METADATA CALL FAILED BUT THE REPOSITORY MAY STILL BE READABLE. raw.github
            # serves README text outside the API quota (and outside a proxy's per-repo API
            # gate), so the prose half still runs. Without metadata the licence is UNKNOWN,
            # which is treated as not copy-permitted, and there is no tree, so no code half.
            meta_raw, via = {"html_url": f"https://github.com/{full}"}, f"raw (api HTTP {status})"
        meta = {"url": meta_raw.get("html_url"), "pushed_at": meta_raw.get("pushed_at"),
                "license": ((meta_raw.get("license") or {}).get("spdx_id")
                            or ("NONE" if via == "api" else "UNKNOWN")),
                "stars": meta_raw.get("stargazers_count"),
                "default_branch": meta_raw.get("default_branch")}
        st: dict[str, Any] = {"status": "OK", "via": via, "lane": lane, "kind": kind,
                              "license": meta["license"], "stars": meta["stars"], "rows": 0}
        per_repo[full] = st
        unchanged = bool(via == "api" and rec and rec.get("pushed_at") == meta["pushed_at"])
        if _crypto_venue(f"{full} {meta_raw.get('description') or ''}") and kind == "repo":
            st["status"] = "FENCED: crypto-exchange venue"
            drops["crypto_exchange_repo"] += 1
            lane_reached[lane] += 1
        elif unchanged:
            st["status"] = "UNCHANGED (pushed_at as last scan)"
            lane_reached[lane] += 1
        else:
            readme = readme_text(fetch, full, meta.get("default_branch"))
            if readme is None:
                st["status"] = f"UNREACHED: metadata {via}, README absent on raw"
                if via != "api":
                    continue
                readme = ""
            lane_reached[lane] += 1
            readme = readme[:int(policy.get("max_readme_bytes") or 400_000)]
            if kind == "list":
                links = repo_links(readme, full)[:int(policy.get("max_links_per_list") or 400)]
                for link in links:
                    enqueue(link, lane, seed.get("firm"), f"list:{full}",
                            int(seed.get("depth") or 0) + 1)
                st["links"] = len(links)
            got, d = claim_rows(full, meta, f"{meta_raw.get('description') or ''}\n{readme}",
                                seed, universe, now=stamp)
            drops.update(d)
            if kind == "list":
                # A list's README is a catalogue of one-line blurbs; only a blurb that names a
                # registered family is a hypothesis worth a judge's trial. The repos it links
                # are queued and read in full on their own turn.
                drops["list_claim_without_family"] += sum(1 for r in got if not r.get("family"))
                got = [r for r in got if r.get("family")]
            if kind == "repo" and via == "api":
                cg, cur, cd = code_rows(fetch, quota, full, meta, seed, policy, universe,
                                        int((rec or {}).get("file_cursor") or 0), deadline,
                                        now=stamp)
                drops.update(cd)
                got += cg
                st["file_cursor"] = cur
            for r in got:
                k = row_key(r)
                if k in seen:
                    dupes += 1
                    continue
                seen[k] = stamp
                rows.append(r)
                st["rows"] += 1
        repos_st[full] = {"scanned_utc": stamp, "pushed_at": meta["pushed_at"],
                          "status": st["status"], "lane": lane,
                          "file_cursor": st.get("file_cursor",
                                                int((rec or {}).get("file_cursor") or 0))}
        queue[:] = [x for x in queue if x.get("repo") != full]

    # 3. DONATE, one file per seat, only when it holds rows: an empty donation file would be
    #    counted as output by a census that counts lines, which is the lie this organ exists to end.
    by_seat: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_seat.setdefault(str(r["source"]), []).append(r)
    donated: dict[str, str] = {}
    if write:
        for seat, rs in by_seat.items():
            out = intel_dir / seat / f"discoveries_github_{now:%Y%m%d_%H%M%S}.json"
            _atomic(out, {"source": seat, "organ": ORGAN, "mined_at": stamp, "discoveries": rs})
            donated[seat] = str(out)
        with contextlib.suppress(Exception):
            from libs.data.datahub import record_mined_source
            if intel_dir == INTEL:                   # provenance only for live donations
                for r in rows:
                    record_mined_source(repo=str(r.get("repo")), url=str(r.get("url")),
                                        commit=str(r.get("pushed_at")),
                                        license_=str(r.get("license")), file=str(r.get("file")),
                                        mechanism=str(r.get("mechanism"))[:200],
                                        code_copied=False)

    reached_n = sum(lane_reached.values())
    # ONLINE means GitHub answered a call this pass made. A pass the quota stopped before its
    # first call learned nothing, and its zero is UNMEASURED, never RED.
    online = reached_n > 0 or (quota_snap.get("status") == 200
                               and sum(quota.calls.values()) > 0)
    history.append({"utc": stamp, "online": online, "repos_reached": reached_n,
                    "lane_reached": dict(lane_reached),
                    "rows": {seat: len(rs) for seat, rs in by_seat.items()},
                    "api_calls": dict(quota.calls), "rate_limited": bool(quota.exhausted)})
    history = history[-HISTORY_CAP:]
    live = liveness(history, now)
    verdicts = {v["verdict"] for v in live.values()}
    verdict = "RED" if "RED" in verdicts else "GREEN" if "GREEN" in verdicts else UNMEASURED
    if write:
        if len(seen) > SEEN_CAP:
            seen = dict(sorted(seen.items(), key=lambda kv: kv[1])[-SEEN_CAP:])
        _atomic(state_path, {"repos": repos_st, "seen": seen, "queue": queue[:QUEUE_CAP],
                             "search_cursor": search_cursor, "history": history,
                             "updated_utc": stamp})
    batch_rows = [s for s in reg.get("repos") or [] if s.get("batch")]
    doc = {
        "generated_utc": stamp, "organ": ORGAN, "mode": "LIVE",
        "verdict": verdict, "liveness": live,
        "pass": {"online": online, "repos_reached": reached_n, "lane_reached": dict(lane_reached),
                 "rows_donated": {seat: len(rs) for seat, rs in by_seat.items()},
                 "rows_total": len(rows), "duplicates_dropped": dupes,
                 "discovered": discovered, "queue_depth": len(queue),
                 "api_calls": dict(quota.calls), "rate_limit_before": quota_snap,
                 "rate_limit_after": {"core_remaining": quota.core,
                                      "search_remaining": quota.search},
                 "stopped_by": quota.exhausted or None,
                 "drops": dict(drops),
                 "seconds": round(time.monotonic() - t0, 2)},
        "batch": {"name": "elitequant_20_2026-09-30", "n": len(batch_rows),
                  "dispositions": dict(Counter(str(s.get("disposition")) for s in batch_rows))},
        "per_repo": per_repo,
        "donated_to": donated,
        "consumers": [
            "desks/mt5/research/miner_candidate_compiler.py reads data/intelligence/** -> "
            "STRUCTURED_HYPOTHESIS (family named) / EXACT_RECIPE (code_rule) / deepening",
            "scripts/check_producer_yield.py counts data/intelligence/firm_mining and "
            "data/intelligence/github_repos as seats",
            "hourly leg github_miner_alive (this file --check) turns RED into a failing leg",
        ],
        "boundary": ("MINTS ONLY, through the compiler's door. Static text; nothing fetched is "
                     "executed; a quote is kept only under a copy-permitted licence; "
                     "crypto-exchange venues fenced; share CFDs only through "
                     "universe_policy.may_hypothesise."),
    }
    if write:
        _atomic(report_path, doc)
    return doc


def check(report_path: Path = REPORT, now: datetime | None = None,
          max_age_h: float = MAX_REPORT_AGE_H) -> tuple[int, str]:
    """(exit code, line). 1 on RED or a report older than its clock; 2 when absent (UNMEASURED)."""
    doc = _load(report_path, None)
    if not isinstance(doc, dict):
        return 2, f"{UNMEASURED}: {report_path} absent or unreadable -- the miner never ran here"
    now = now or datetime.now(tz=UTC)
    try:
        age_h = (now - datetime.fromisoformat(str(doc["generated_utc"]))).total_seconds() / 3600
    except (KeyError, ValueError):
        return 1, "RED: report carries no readable generated_utc"
    if age_h > max_age_h:
        return 1, (f"RED: report {age_h:.1f}h old (> {max_age_h:g}h): the hourly leg "
                   f"github_repo_miner is not running")
    live = doc.get("liveness") or {}
    reds = {s: v for s, v in live.items() if v.get("verdict") == "RED"}
    if reds:
        return 1, "RED: " + "; ".join(f"{s}: {v.get('why')}" for s, v in reds.items())
    return 0, ("OK: " + ", ".join(f"{s} {v.get('verdict')} ({v.get('rows_in_window')})"
                                  for s, v in live.items()))


def raise_alarm(code: int, line: str, path: Path | None = None) -> None:
    """RED raises the alarm file the issue board reads; anything else clears it. UNMEASURED
    clears too: an absent report is the leg's own MISSING state in the runtime attestation,
    and paging on it would page every clone that never ran the miner."""
    p = path or ALARM
    if code == 1:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(line + "\n", "utf-8")
    else:
        with contextlib.suppress(FileNotFoundError):
            p.unlink()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=300.0)
    ap.add_argument("--dry-run", action="store_true", help="write nothing")
    ap.add_argument("--check", action="store_true",
                    help="read the report: exit 1 on RED or stale, 2 when absent")
    a = ap.parse_args(argv)
    if a.check:
        code, line = check()
        fence = _DESK / "reports" / "github_miner_alive_fence.json"
        _atomic(fence, {"generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                        "exit": code, "verdict": line.split(":", 1)[0], "line": line,
                        "artifact": str(REPORT.relative_to(_ROOT))})
        raise_alarm(code, line)
        print(f"GITHUB REPO MINER LIVENESS  {line}")
        return code
    doc = run(budget_s=a.budget_s, write=not a.dry_run)
    p = doc.get("pass") or {}
    print(f"GITHUB REPO MINER [{doc['verdict']}]  reached {p.get('repos_reached')} repo(s), "
          f"donated {p.get('rows_donated')}, dupes {p.get('duplicates_dropped')}, "
          f"discovered {p.get('discovered')}, queue {p.get('queue_depth')}, "
          f"calls {p.get('api_calls')}, stopped_by {p.get('stopped_by')}")
    for seat, v in (doc.get("liveness") or {}).items():
        print(f"  {seat:14} {v['verdict']:10} rows_in_window={v.get('rows_in_window')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
