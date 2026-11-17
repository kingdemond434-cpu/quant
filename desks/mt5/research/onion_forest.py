"""THE ONION FOREST -- public text from the onion layer that names a testable market mechanism.

    python research/onion_forest.py --once [--budget-s 600] [--dry-run] [--no-network]

WHAT IT IS. The miner of the `onion` civilisation in the forest federation
(`libs/research/forests.py`; it rides MT5-Dept-Regions through the `forest_onion` hourly leg, and
`forest_runner`'s practitioner role calls `run` here exactly where a regional forest calls
`deep_forest_miner`). The owner's N7 proposal (2026-10-13) and the tor-proxy ruling
(2026-11-17, with its 20:33-20:35Z addendum) fix its ground:

* official onion mirrors of public outlets and institutions, and individually reviewed onion
  sources -- an ALLOWLIST (`data/onion_sources.json`), never a crawl;
* text claims only; publicly posted insider claims and rumours ARE hunted, as testable rumour
  claims, exactly like deep-forest claims;
* NEVER markets, Dread or market-adjacent forums, leak/dump/ransomware or carding SITES, or a
  recursive crawler (`FORBIDDEN_KINDS`: the roster cannot hold one -- `load_roster` raises).

WHAT HAPPENS EACH PASS.
1. ROSTER. Every assessed row gets an EFFECTIVE verdict (`effective_verdict`): ALLOWED only when
   the address is VERIFIED from the publisher's own clearnet page and the terms are ALLOWED; a
   mirror inherits its publisher's terms and robots. Everything else is named with its reason and
   a missed_growth line.
2. BOX READS (`verify_roster`, clearnet, robots-gated through deep_forest_miner.access_refusal,
   honest UA, NEVER over Tor). The publisher's page is read and the candidate onion address must
   appear on it VERBATIM to become VERIFIED; the terms page is read, hashed, and a stated refusal
   of robots / scraping / data mining marks the row BLOCKED_ON_TERMS automatically. A refusal can
   be read by a machine; a permission cannot, so ALLOWED is only ever a reviewed roster value.
   Results go to `data/onion_roster_state.json`; the roster file is reviewed input, never written.
3. TOR. `libs/data/onion_fetch.tor_status`: TOR_ABSENT / SOCKS_ABSENT are normal states that the
   report carries with their missed_growth lines.
4. MINE. For each ALLOWED row, its listed feeds only, through `onion_fetch.OnionFetcher` (.onion
   only, allowlist only, robots fail-closed, polite, no redirects). Items are ranked by the
   EVOLVING MISSION's term weights; claims come from `mechanism_claims.extract`, the same
   extractor deep_forest_miner uses. Feed enclosures (small text/CSV/PDF on the same onion host)
   are read as ATTACHED, UNVERIFIED claims.
5. GUARDS, BY CONTENT SHAPE, NEVER BY KEYWORD (`dump_shape`). A body that is a breach dump --
   credential pairs, Luhn-valid card numbers, bulk personal-data tables -- is dropped BEFORE any
   write; only a count and a missed_growth line survive. The word "leaked" excludes nothing: a
   post that says it is leaked is a rumour claim with `claimed_leak=true`.
6. TAGS. `claim_type` (rumour / report / attached), `claimed_leak`, and MNPI_RISK when a claim
   purports to be inside information about ONE issuer: its share-CFD symbols are stripped, so it
   can never reach a share-CFD cell, while it may still inform macro / FX / commodity rumour
   regimes. First-seen, corroboration and lag-to-confirmation are measured over the ledger.
7. OUTPUT. Claims -> `data/onion_claims.jsonl` (read back by the forest's practitioner role);
   story_mechanism tasks -> the deepening queue (deep_forest_miner.build_tasks + the shared queue
   merge, source `onion_forest`) -> miner_candidate_compiler -> gauntlet; discovery rows ->
   `data/intelligence/onion/` for the compiler.
8. EVOLVE. `libs/research/mission_evolution.evolve` rewrites the mission and its term/source
   weights from this pass's yield; every version is appended to `data/forest_missions/onion.jsonl`
   with its parent. A pass that tried nothing (Tor absent) holds the mission and says why.
9. REPORT. `reports/ONION_FOREST.json`.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import re
import sys
import time
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
REPO = DESK.parents[1]
for _p in (str(REPO), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import onion_fetch as OF  # noqa: E402
from libs.research import forests as F  # noqa: E402
from libs.research import mechanism_claims as mc  # noqa: E402
from libs.research import mission_evolution as ME  # noqa: E402

FOREST = "onion"
SOURCE = "onion_forest"
SEAT = "onion"
ROSTER = DESK / "data" / "onion_sources.json"
STATE = DESK / "data" / "onion_roster_state.json"
CLAIMS = DESK / "data" / "onion_claims.jsonl"
MISSION_LOG = F.mission_log(FOREST, DESK)
INTEL = DESK / "data" / "intelligence" / SEAT
REPORT = DESK / "reports" / "ONION_FOREST.json"

ALLOWED_KINDS = frozenset({"news_mirror", "institution_mirror", "public_forum", "dataset",
                           "index"})
#: Kinds the roster can never hold. Declared-kind guard, so a reviewer cannot file a market as
#: a "news_mirror" and a test pins it; the excluded CATEGORIES are named in the roster file.
FORBIDDEN_KINDS = frozenset({"market", "darknet_market", "marketplace", "vendor_shop",
                             "dread", "market_forum", "leak_site", "dump_site", "ransomware",
                             "ransomware_leak", "carding", "paste_dump", "crawler",
                             "search_crawl"})
VERDICTS = ("ALLOWED", "BLOCKED_ON_TERMS", "UNVERIFIED_ADDRESS", "TERMS_UNREAD",
            "REVIEW_PENDING", "REFUSED")
ITEMS_PER_FEED = 40
VERIFY_EVERY_S = 7 * 24 * 3600
MAX_VERIFY_PER_PASS = 12

#: The seed vocabulary of the evolving mission: the mandate's macro, commodity and FX words
#: plus the rumour register the owner ordered hunted (20:33Z "insider claimed is hunted").
SEED_TERMS: tuple[str, ...] = (
    "central bank", "interest rate", "inflation", "sanctions", "export ban", "tariff", "opec",
    "oil", "gas", "gold", "currency", "devaluation", "default", "capital controls", "shortage",
    "strike", "insider", "rumour", "sources say")
BASE_MISSION = ("Read public text on allowlisted onion mirrors and reviewed onion sources for "
                "claims that name a testable market mechanism for an MT5 instrument (FX, metals, "
                "energy, indices, softs): policy, supply, flow and rumour claims, with their "
                "first-seen time, corroboration and lag to confirmation.")


def now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


class RosterError(ValueError):
    """The roster holds something it may never hold."""


# =========================================================================== roster
def validate_roster(doc: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    rows = doc.get("sources") if isinstance(doc, Mapping) else None
    if not isinstance(rows, list):
        return ["roster has no 'sources' list"]
    seen: set[str] = set()
    for i, r in enumerate(rows):
        if not isinstance(r, Mapping):
            errors.append(f"row {i} is not an object")
            continue
        rid = str(r.get("id") or "")
        kind = str(r.get("kind") or "").strip().lower()
        if not rid or rid in seen:
            errors.append(f"row {i}: missing or duplicate id {rid!r}")
        seen.add(rid)
        if kind in FORBIDDEN_KINDS:
            errors.append(f"{rid}: kind {kind!r} is FORBIDDEN (markets, Dread, leak/dump/"
                          f"ransomware, carding and crawlers never enter the roster)")
        elif kind not in ALLOWED_KINDS:
            errors.append(f"{rid}: kind {kind!r} is not one of {sorted(ALLOWED_KINDS)}")
        for key in ("publisher", "address_status", "address_source", "terms_url",
                    "terms_verdict", "terms_why"):
            if not str(r.get(key) or "").strip():
                errors.append(f"{rid}: missing {key}")
        if str(r.get("terms_verdict")) not in ("ALLOWED", "BLOCKED_ON_TERMS", "TERMS_UNREAD",
                                               "REFUSED"):
            errors.append(f"{rid}: terms_verdict {r.get('terms_verdict')!r} is not a verdict")
        host = str(r.get("onion_host") or "")
        if host and not OF.onion_host(f"http://{host}/"):
            errors.append(f"{rid}: onion_host {host!r} is not a v3 .onion host")
        for u in r.get("feed_urls") or []:
            if OF.onion_host(u) is None:
                errors.append(f"{rid}: feed {u!r} is not a .onion URL (Tor carries .onion only)")
            elif host and OF.onion_host(u) != host and not str(OF.onion_host(u)).endswith(
                    "." + host):
                errors.append(f"{rid}: feed {u!r} is not on the row's own onion host")
    return errors


def load_roster(path: Path = ROSTER) -> dict[str, Any]:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    errors = validate_roster(doc)
    if errors:
        raise RosterError("; ".join(errors))
    return doc


def _read_json(path: Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def effective_verdict(row: Mapping[str, Any], state: Mapping[str, Any] | None = None
                      ) -> tuple[str, str]:
    """(verdict, why). ALLOWED needs a VERIFIED address AND reviewed ALLOWED terms."""
    st = dict((state or {}).get(str(row.get("id")), {}) or {})
    tv = str(row.get("terms_verdict") or "TERMS_UNREAD")
    if tv == "REFUSED":
        return "REFUSED", str(row.get("terms_why") or "refused")
    if tv == "BLOCKED_ON_TERMS":
        return "BLOCKED_ON_TERMS", str(row.get("terms_why") or "")
    if st.get("terms_auto") == "BLOCKED_ON_TERMS":
        return "BLOCKED_ON_TERMS", f"box terms read: {st.get('terms_auto_why')}"
    host = str(row.get("onion_host") or "")
    verified = bool(host) and (str(row.get("address_status")) == "VERIFIED"
                               or st.get("address_verified_host") == host)
    if not verified:
        return "UNVERIFIED_ADDRESS", ("no onion address known from the publisher's own page"
                                      if not host else
                                      f"{host} not yet found verbatim on "
                                      f"{row.get('address_source')}")
    if tv != "ALLOWED":
        return "TERMS_UNREAD", str(row.get("terms_why") or "terms not reviewed")
    if str(row.get("kind")) == "public_forum":
        rv = row.get("review") if isinstance(row.get("review"), Mapping) else {}
        if not (rv.get("login_required") is False and rv.get("not_market_leak_or_carding")
                is True):
            return "REVIEW_PENDING", ("a public forum is read only after review: no login, terms "
                                      "allow, not a market, leak or carding venue")
    if not (row.get("feed_urls") or []):
        return "ALLOWED", "allowed, but no feed listed yet"
    return "ALLOWED", "address verified from the publisher's page; terms reviewed ALLOWED"


def missed_growth(row: Mapping[str, Any], verdict: str, why: str) -> str:
    return (f"missed_growth: {row.get('publisher')} ({row.get('id')}) is {verdict}: {why[:160]}. "
            f"Its onion-layer claims ({row.get('mechanism_note') or 'none named'}) stay "
            f"UNMEASURED from this lane. A gap, not a zero.")


# =========================================================================== box reads
#: Phrases by which a publisher's terms REFUSE automated reading. Used only to refuse.
TERMS_REFUSAL = re.compile(
    r"(?i)(scrap(e|ing)|data[ -]?min(e|ing)|text and data mining|robots?,? spiders?|"
    r"automated (means|systems?|tools?|software)|crawl(er|ing)?)[^.]{0,160}"
    r"|(may not|must not|shall not|prohibit\w*|not permitted)[^.]{0,120}"
    r"(scrap|data[ -]?min|robot|spider|crawl|automated)")

ClearnetGet = Callable[[str], tuple[int | None, str]]


def _clearnet_get(url: str) -> tuple[int | None, str]:
    """Clearnet, robots-gated, honest UA -- deep_forest_miner's own gate. NEVER over Tor."""
    if OF.onion_host(url):
        return None, "ONION_URL: box reads are clearnet only"
    try:
        from libs.data import polite_fetch as pf
        from research import deep_forest_miner as dfm
    except Exception as exc:
        return None, f"UNAVAILABLE: {type(exc).__name__}"
    why = dfm.access_refusal(url)
    if why:
        return None, why
    r = pf.get(url, headers=dict(dfm._UA), timeout=25.0, retries=1, leg=SOURCE)
    return r.status, (r.text or "")


def verify_roster(rows: Iterable[Mapping[str, Any]], state: dict[str, Any], *,
                  get: ClearnetGet = _clearnet_get, at: str | None = None,
                  clock: Callable[[], float] = time.time) -> list[dict[str, Any]]:
    """Read each candidate's publisher page and terms page (clearnet). Writes only `state`."""
    out: list[dict[str, Any]] = []
    t = clock()
    done = 0
    for r in rows:
        rid = str(r.get("id"))
        if str(r.get("terms_verdict")) == "REFUSED" or done >= MAX_VERIFY_PER_PASS:
            continue
        st = state.setdefault(rid, {})
        if t - float(st.get("checked_epoch") or 0) < VERIFY_EVERY_S:
            continue
        done += 1
        row: dict[str, Any] = {"id": rid}
        host = str(r.get("onion_host") or "")
        if host and str(r.get("address_status")) != "VERIFIED":
            code, text = get(str(r.get("address_source")))
            found = bool(code and 200 <= code < 300 and host in text)
            row["address_read"] = {"status": code, "found_verbatim": found,
                                   "why": "" if code else text[:160]}
            if found:
                st["address_verified_host"] = host
                st["address_verified_at"] = at or now()
        code, text = get(str(r.get("terms_url")))
        if code and 200 <= code < 300 and text:
            st["terms_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
            st["terms_read_at"] = at or now()
            m = TERMS_REFUSAL.search(text)
            if m:
                st["terms_auto"] = "BLOCKED_ON_TERMS"
                st["terms_auto_why"] = f"terms text: {m.group(0)[:200]!r}"
            row["terms_read"] = {"status": code, "refusal_found": bool(m)}
        else:
            row["terms_read"] = {"status": code, "why": text[:160]}
        st["checked_epoch"] = t
        out.append(row)
    return out


# =========================================================================== content guards
#: email:secret pairs, anywhere in the text (feed text arrives with its newlines collapsed).
_CRED = re.compile(r"(?<!\S)[^\s:;|,@]{1,64}@[^\s:;|,@]{1,64}\.[a-z]{2,24}[:;|,]\S{4,}(?!\S)",
                   re.IGNORECASE)
_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
_EMAIL = re.compile(r"[^\s@]{1,64}@[^\s@]{1,64}\.[a-z]{2,24}", re.IGNORECASE)
_PII_HEADER = re.compile(r"(?i)\b(e-?mail|password|passwd|phone|ssn|social security|dob|"
                         r"date of birth|address|passport|card ?number|cvv)\b")


def _luhn(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
        alt = not alt
    return total % 10 == 0


def dump_shape(text: str) -> str | None:
    """The shape of a breach dump, or None. CONTENT SHAPE ONLY -- never a keyword: a post about
    a leak is a claim; a body that IS credentials, cards or a personal-data table is not kept."""
    body = text or ""
    if len(_CRED.findall(body)) >= 3:
        return "credential_pairs"
    cards = {re.sub(r"\D", "", m) for m in _CARD.findall(body)}
    if sum(1 for c in cards if 13 <= len(c) <= 19 and _luhn(c)) >= 3:
        return "card_numbers_luhn"
    if len({m.lower() for m in _EMAIL.findall(body)}) >= 10:
        return "bulk_pii_table"
    lines = [ln for ln in body.splitlines() if ln.strip()]
    for i, ln in enumerate(lines[:5]):
        if len({m.lower() for m in _PII_HEADER.findall(ln)}) >= 2 and \
                len(lines) - i - 1 >= 10 and ln.count(",") + ln.count("\t") + ln.count("|") >= 2:
            return "bulk_pii_table"
    return None


_RUMOUR = re.compile(r"(?i)\b(insider|rumou?r|sources? (say|said|familiar)|people familiar|"
                     r"according to (sources|people)|reportedly|unconfirmed|leak(ed|s)?|"
                     r"confidential|not yet public|internal (memo|document))\b")
_LEAK = re.compile(r"(?i)\bleak(ed|s|ing)?\b")


def _is_equity(symbol: str) -> bool:
    try:
        from research import universe_policy as up
        return bool(up.is_equity(symbol))
    except Exception:
        return False


def tag_claim(claim: dict[str, Any], *, attached: bool = False,
              is_equity: Callable[[str], bool] = _is_equity) -> dict[str, Any]:
    """claim_type, claimed_leak, MNPI_RISK -- and share-CFD symbols stripped under MNPI_RISK."""
    text = str(claim.get("claim") or "")
    rumour = bool(_RUMOUR.search(text))
    claim["claim_type"] = "attached" if attached else ("rumour" if rumour else "report")
    claim["claimed_leak"] = bool(_LEAK.search(text))
    if attached:
        claim["provenance_note"] = "attached, unverified"
    inst = dict(claim.get("instruments") or {})
    named = [str(s) for s in (inst.get("analogues") or []) + (inst.get("mentioned") or [])]
    equities = sorted({s for s in named if is_equity(s)})
    claim["mnpi_risk"] = bool((rumour or attached) and len(equities) == 1)
    if claim["mnpi_risk"]:
        claim["exclude_share_cfd"] = True
        for key in ("analogues", "mentioned"):
            if isinstance(inst.get(key), list):
                inst[key] = [s for s in inst[key] if not is_equity(str(s))]
        claim["instruments"] = inst
        claim["mnpi_why"] = (f"purports inside information about one issuer ({equities[0]}): "
                             f"kept out of share-CFD cells; may inform macro/FX/commodity "
                             f"rumour regimes")
    return claim


# =========================================================================== mining
_ENCL = re.compile(r"(?is)<enclosure\b([^>]*)>")


def enclosures(xml: str) -> list[dict[str, Any]]:
    out = []
    for m in _ENCL.finditer(xml or ""):
        attrs = dict(re.findall(r'(\w+)=["\']([^"\']*)["\']', m.group(1)))
        size: int | None
        try:
            size = int(attrs.get("length") or "")
        except ValueError:
            size = None
        out.append({"url": attrs.get("url", ""), "type": attrs.get("type", ""), "size": size})
    return out


def _parse_feed(xml: str) -> list[dict[str, str]]:
    from research import deep_forest_miner as dfm
    return dfm.parse_feed(xml)


def _attachment_text(body: bytes, ctype: str, url: str) -> str:
    if "pdf" in ctype.lower() or url.lower().endswith(".pdf"):
        from libs.research import pdf_text
        try:
            return pdf_text.extract(body)[0]
        except Exception:
            return ""
    return body.decode("utf-8", errors="replace")


def mine(fetcher: OF.OnionFetcher, rows: list[Mapping[str, Any]], mission: ME.Mission, *,
         deadline: float, at: str, clock: Callable[[], float] = time.monotonic,
         is_equity: Callable[[str], bool] = _is_equity) -> dict[str, Any]:
    """Read each fetchable row's feeds; return claims, the yield and the guard counts."""
    claims: list[dict[str, Any]] = []
    term_yield: dict[str, int] = {}
    src_yield: dict[str, int] = {}
    harvest: dict[str, int] = {}
    tried_s: list[str] = []
    dropped = {"dump_shape": 0, "by_shape": {}}
    attachments = {"read": 0, "refused": 0}
    terms = sorted(mission.terms, key=lambda t: (-mission.terms[t], t))
    order = sorted(rows, key=lambda r: (-mission.sources.get(str(r.get("id")), 1.0),
                                        str(r.get("id"))))
    for row in order:
        rid = str(row.get("id"))
        for feed in row.get("feed_urls") or []:
            if clock() > deadline:
                break
            res = fetcher.fetch(feed)
            if not res.ok:                    # a refusal or failure is not evidence against it
                continue
            if rid not in tried_s:
                tried_s.append(rid)
            items = _parse_feed(res.text)

            def _score(it: Mapping[str, str]) -> float:
                low = f"{it.get('title')} {it.get('summary')}".lower()
                return sum(mission.terms[t] for t in terms if t in low)
            items = sorted(items, key=lambda it: (-_score(it), str(it.get("url"))))
            docs: list[tuple[Mapping[str, str], str, bool]] = [
                (it, f"{it.get('title')}. {it.get('summary')}", False)
                for it in items[:ITEMS_PER_FEED]]
            if row.get("attachments"):
                for enc in enclosures(res.text)[:5]:
                    got = fetcher.fetch(enc["url"], attachment=True, content_type=enc["type"],
                                        size=enc["size"])
                    if got.ok:
                        attachments["read"] += 1
                        docs.append(({"title": "attachment", "url": enc["url"]},
                                     _attachment_text(got.body, got.content_type, enc["url"]),
                                     True))
                    else:
                        attachments["refused"] += 1
            for it, text, attached in docs:
                shape = dump_shape(text)
                if shape:                                # dropped BEFORE any write: count only
                    dropped["dump_shape"] += 1
                    dropped["by_shape"][shape] = dropped["by_shape"].get(shape, 0) + 1
                    continue
                low = text.lower()
                got = mc.extract(text)["claims"]
                for c in got:
                    c = tag_claim(dict(c), attached=attached, is_equity=is_equity)
                    c.update({"ground": rid, "ground_kind": row.get("kind"), "region": FOREST,
                              "language": row.get("language"), "cluster": FOREST,
                              "source": SOURCE, "route": "onion_feed",
                              "url": str(it.get("url") or feed), "title": it.get("title"),
                              "evidence_grade": ("ATTACHED_UNVERIFIED" if attached
                                                 else "NEWS_REPORT"),
                              "published_time": it.get("published") or None,
                              "available_time": at, "fetched_utc": at, "first_seen": at,
                              "source_hash": hashlib.sha256(text.encode()).hexdigest()[:32],
                              "score": mc.claim_score(c)})
                    claims.append(c)
                    src_yield[rid] = src_yield.get(rid, 0) + 1
                    for t in terms:
                        if t in low:
                            term_yield[t] = term_yield.get(t, 0) + 1
                    inst = c.get("instruments") or {}
                    for word in [c.get("mechanism_class"), *(inst.get("analogues") or [])]:
                        if word and word != "other":
                            harvest[str(word)] = harvest.get(str(word), 0) + 1
    y = ME.Yield(terms=term_yield, sources=src_yield,
                 tried_terms=terms if tried_s else (), tried_sources=tried_s, harvest=harvest)
    return {"claims": claims, "yield": y, "dropped": dropped, "attachments": attachments}


# =========================================================================== measurement
def corroboration(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Per mechanism key: first seen, distinct sources, and the lag from the first RUMOUR telling
    to the first non-rumour telling by ANOTHER source (UNMEASURED when there is none)."""
    by: dict[str, list[Mapping[str, Any]]] = {}
    for r in rows:
        k = str(r.get("mechanism_key") or r.get("claim_hash") or "")
        if k:
            by.setdefault(k, []).append(r)
    lags, corroborated = [], 0
    for tellings in by.values():
        tellings = sorted(tellings, key=lambda r: str(r.get("fetched_utc") or ""))
        if len({str(t.get("ground")) for t in tellings}) > 1:
            corroborated += 1
        first_r = next((t for t in tellings if t.get("claim_type") == "rumour"), None)
        if first_r is None:
            continue
        conf = next((t for t in tellings if t.get("claim_type") == "report"
                     and t.get("ground") != first_r.get("ground")
                     and str(t.get("fetched_utc")) >= str(first_r.get("fetched_utc"))), None)
        if conf is not None:
            with contextlib.suppress(ValueError):
                a = datetime.fromisoformat(str(first_r.get("fetched_utc")))
                b = datetime.fromisoformat(str(conf.get("fetched_utc")))
                lags.append((b - a).total_seconds() / 3600.0)
    return {"mechanisms": len(by), "corroborated": corroborated,
            "rumours_confirmed": len(lags),
            "median_lag_to_confirmation_h": (sorted(lags)[len(lags) // 2] if lags
                                             else "UNMEASURED: no rumour has a later "
                                                  "confirming report from another source yet")}


def _ledger(path: Path = CLAIMS, max_rows: int = 20000) -> list[dict[str, Any]]:
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()[-max_rows:]
    except OSError:
        return []
    out = []
    for ln in lines:
        with contextlib.suppress(ValueError):
            out.append(json.loads(ln))
    return out


# =========================================================================== the pass
def _donate(claims: list[dict[str, Any]], at: str) -> dict[str, Any]:
    """Claims -> story_mechanism tasks (deepening queue) and intelligence discovery rows."""
    out: dict[str, Any] = {"tasks_queued": 0, "intelligence_rows": 0, "intelligence_file": None}
    if not claims:
        return out
    try:
        from research import deep_forest_miner as dfm
        tasks = dfm.build_tasks(claims)
        tags = {str(c.get("claim_hash")): c for c in claims}
        for t in tasks:
            c = tags.get(str(t.get("claim_hash")), {})
            t.update({"source": SOURCE, "claim_type": c.get("claim_type"),
                      "claimed_leak": c.get("claimed_leak"), "mnpi_risk": c.get("mnpi_risk"),
                      "exclude_share_cfd": bool(c.get("exclude_share_cfd"))})
        from research.regime_coverage import _merge_into_queue
        with dfm._xlock("deepening_queue", timeout_s=120.0):
            _merge_into_queue(tasks, source=SOURCE)
        out["tasks_queued"] = len(tasks)
        rows = [{"source": SEAT, "kind": "story_mechanism", "title": t.get("title"),
                 "description": t.get("description"), "url": t.get("url"),
                 "symbols": t.get("symbols"), "claim_type": t.get("claim_type"),
                 "claimed_leak": t.get("claimed_leak"), "mnpi_risk": t.get("mnpi_risk"),
                 "exclude_share_cfd": t.get("exclude_share_cfd"),
                 "published_time": t.get("published_time"),
                 "available_time": t.get("available_time")} for t in tasks]
        from libs.research.source_provenance import stamp_rows
        INTEL.mkdir(parents=True, exist_ok=True)
        path = INTEL / f"discoveries_onion_{at[:16].replace(':', '').replace('-', '')}.json"
        path.write_text(json.dumps(stamp_rows(rows), indent=1, ensure_ascii=False, default=str),
                        encoding="utf-8")
        out.update({"intelligence_rows": len(rows), "intelligence_file": str(path.name)})
    except Exception as exc:
        out["why"] = f"{type(exc).__name__}: {str(exc)[:200]}"
    return out


def current_mission(roster_ids: list[str], at: str, log: Path = MISSION_LOG) -> ME.Mission:
    got = ME.head(log)
    if got is not None:
        return got
    return ME.seed(FOREST, BASE_MISSION, SEED_TERMS, roster_ids, stamp=at)


def run(budget_s: float = 600.0, *, write: bool = True, network: bool = True,
        status: Mapping[str, Any] | None = None, transport: OF.Transport | None = None,
        clearnet_get: ClearnetGet | None = None, at: str | None = None,
        roster_path: Path = ROSTER, report_path: Path = REPORT,
        is_equity: Callable[[str], bool] = _is_equity, **_ignored: Any) -> dict[str, Any]:
    """One pass. Never raises on a network or Tor absence; a forbidden roster DOES raise."""
    at = at or now()
    deadline = time.monotonic() + max(10.0, float(budget_s))
    roster = load_roster(roster_path)
    rows = list(roster["sources"])
    state = dict(_read_json(STATE) or {}) if write else {}
    verification: list[dict[str, Any]] = []
    if network:
        verification = verify_roster(rows, state, get=clearnet_get or _clearnet_get, at=at)
        if write:
            STATE.parent.mkdir(parents=True, exist_ok=True)
            STATE.write_text(json.dumps(state, indent=1, sort_keys=True), encoding="utf-8")
    verdicts = []
    missed: list[str] = []
    for r in rows:
        v, why = effective_verdict(r, state)
        verdicts.append({"id": r.get("id"), "publisher": r.get("publisher"),
                         "kind": r.get("kind"), "verdict": v, "why": why})
        if v != "ALLOWED":
            missed.append(missed_growth(r, v, why))
    fetchable = [r for r, v in zip(rows, verdicts, strict=True) if v["verdict"] == "ALLOWED"]
    tor = dict(status) if status is not None else (
        OF.tor_status() if network else {"status": OF.TOR_ABSENT, "why": "--no-network",
                                         "missed_growth": OF.MISSED_TOR})
    if tor.get("missed_growth"):
        missed.append(str(tor["missed_growth"]))
    ids = [str(r.get("id")) for r, v in zip(rows, verdicts, strict=True)
           if v["verdict"] != "REFUSED"]
    parent = current_mission(ids, at)
    fetcher = OF.OnionFetcher(rows=fetchable, status=tor, transport=transport,
                              is_fetchable=lambda r: effective_verdict(r, state)[0] == "ALLOWED")
    mined = mine(fetcher, fetchable, parent, deadline=deadline, at=at, is_equity=is_equity) \
        if fetchable and tor.get("status") == OF.TOR_PRESENT else {
            "claims": [], "yield": ME.Yield(), "dropped": {"dump_shape": 0, "by_shape": {}},
            "attachments": {"read": 0, "refused": 0}}
    if mined["dropped"]["dump_shape"]:
        missed.append(f"missed_growth: {mined['dropped']['dump_shape']} body/bodies had the shape "
                      f"of a breach dump ({mined['dropped']['by_shape']}) and were dropped "
                      f"unread before any write; whatever claim they carried is not measured. "
                      f"Possessing such data is itself unlawful.")
    child, diff, changed = ME.evolve(parent, mined["yield"], at, sources=ids)
    first_version = ME.head(MISSION_LOG) is None
    if write and (changed or first_version):
        if first_version:
            ME.append(MISSION_LOG, parent, {"seeded": True})
        if changed:
            ME.append(MISSION_LOG, child, diff)
    if not changed:
        diff["held_why"] = ("no source was tried this pass (" + str(tor.get("status")) + ", "
                            + f"{len(fetchable)} fetchable row(s)); a mission is only rewritten "
                              f"from observed yield")
        missed.append("missed_growth: the onion mission did not evolve this pass because "
                      "nothing was read; its terms keep their weights until yield is observed.")
    claims = mined["claims"]
    donated: dict[str, Any] = {"tasks_queued": 0, "intelligence_rows": 0}
    if write and claims:
        CLAIMS.parent.mkdir(parents=True, exist_ok=True)
        with CLAIMS.open("a", encoding="utf-8") as fh:
            for c in claims:
                fh.write(json.dumps(c, ensure_ascii=False, default=str) + "\n")
        donated = _donate(claims, at)
    ledger = _ledger() if write else claims
    counts = {v: sum(1 for x in verdicts if x["verdict"] == v) for v in VERDICTS}
    doc = {
        "at": at, "forest": FOREST, "task": F.resident_task(FOREST),
        "tor": tor,
        "roster": {"assessed": len(rows), "allowed": counts["ALLOWED"],
                   "refused": counts["REFUSED"] + counts["BLOCKED_ON_TERMS"],
                   "unverified": counts["UNVERIFIED_ADDRESS"], "by_verdict": counts,
                   "rows": verdicts, "excluded_by_rule": roster.get("excluded_by_rule"),
                   "public_forum_candidates": [v for v in verdicts
                                               if v["kind"] == "public_forum"]},
        "verification": verification,
        "claims": {"new": len(claims), "ledger": len(ledger),
                   "rumour": sum(1 for c in claims if c.get("claim_type") == "rumour"),
                   "claimed_leak": sum(1 for c in claims if c.get("claimed_leak")),
                   "mnpi_risk": sum(1 for c in claims if c.get("mnpi_risk")),
                   "attachments": mined["attachments"],
                   "dropped_dump_shape": mined["dropped"]["dump_shape"],
                   "corroboration": corroboration(ledger)},
        "candidates_donated": donated,
        "mission": {"version": child.version, "parent": child.parent,
                    "generation": child.generation, "text": child.text, "changed": changed,
                    "diff": diff, "log": str(MISSION_LOG.relative_to(DESK)),
                    "chain": ME.verify_chain(MISSION_LOG) if write else "dry run"},
        "fetch_log": fetcher.log[:60],
        "missed_growth": missed,
        "rule": ("Tor carries .onion hosts only; allowlist only, no crawl, no redirects; a mirror "
                 "inherits its publisher's terms and robots; text claims only; rumours and "
                 "'leaked' claims are hunted as claims; breach dumps are dropped by content "
                 "shape before any write; MNPI_RISK claims never reach share-CFD cells"),
    }
    if write:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(doc, indent=1, ensure_ascii=False, default=str),
                               encoding="utf-8")
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=str(__doc__ or "").splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=600.0)
    ap.add_argument("--dry-run", action="store_true", help="write nothing")
    ap.add_argument("--no-network", action="store_true", help="no Tor probe, no box reads")
    a = ap.parse_args(argv)
    doc = run(a.budget_s, write=not a.dry_run, network=not a.no_network)
    r = doc["roster"]
    print(f"onion forest: tor={doc['tor'].get('status')} assessed={r['assessed']} "
          f"allowed={r['allowed']} refused={r['refused']} unverified={r['unverified']} "
          f"claims={doc['claims']['new']} mission={doc['mission']['version']} "
          f"changed={doc['mission']['changed']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
