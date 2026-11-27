"""Rule E25: every live source with its terms, robots and paid verdict, published from the box.

One row per HOST (a source is a host the desk contacts), derived from the places the desk already
declares sources: the deep-forest grounds, the lawful side-channel feeds and the refused-host list.
Nothing here is typed by hand per source, so a source added tomorrow is audited tomorrow.

THREE VERDICTS, EACH WITH AN UNMEASURED ANSWER (L1.28a). A host with no terms on record is
TERMS_UNREAD, never "clear". A robots verdict comes only from what the frontier recorded about a
read; no attempt is ROBOTS_UNMEASURED. `paid` is NO_KEY_ANON_READ only when an anonymous read of
the host yielded or came back empty; anything else is PAID_UNMEASURED. The overall verdict is
CLEAR only when the terms are on record, a read succeeded anonymously and nothing refused it.

`REFUSED_HOSTS` hosts are REFUSED whatever else is true: their own terms ban automated access.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
GROUNDS_FILE = ROOT / "desks" / "mt5" / "data" / "deep_forest_sources.json"
FRONTIER_FILE = ROOT / "desks" / "mt5" / "data" / "deep_forest_frontier.json"

READ_OK = ("YIELDED", "EMPTY")


def _read(path: Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _hosts_of(ground: Mapping[str, Any]) -> list[str]:
    urls: list[Any] = [ground.get("url")]
    alt = ground.get("alt")
    urls += alt if isinstance(alt, list) else [alt]
    out: list[str] = []
    for u in urls:
        if isinstance(u, str) and u.startswith(("http://", "https://")):
            host = (urlparse(u).hostname or "").lower()
            if host and host not in out:
                out.append(host)
    return out


def _terms_tables() -> tuple[Mapping[str, Any], Mapping[str, str]]:
    """(TERMS, REFUSED_HOSTS) from the lawful-feed module, or empty tables when unimportable."""
    try:
        import sys
        for p in (str(ROOT / "desks" / "mt5"), str(ROOT / "desks" / "mt5" / "side_channels")):
            if p not in sys.path:
                sys.path.insert(0, p)
        from side_channels import lawful_substitutes as ls  # type: ignore[import-not-found]
        return ls.TERMS, ls.REFUSED_HOSTS
    except Exception:
        return {}, {}


def _host_has_terms(host: str, terms: Mapping[str, Any]) -> bool:
    return any(host == t or host.endswith("." + t) for t in terms)


def _host_refused(host: str, refused: Mapping[str, str]) -> str:
    for t, why in refused.items():
        if host == t or host.endswith("." + t):
            return why
    return ""


def audit(grounds_doc: Any, frontier_doc: Any, terms: Mapping[str, Any],
          refused: Mapping[str, str]) -> dict[str, Any]:
    """The per-host audit, or an UNMEASURED verdict when the grounds are unreadable."""
    if not isinstance(grounds_doc, Mapping):
        return {"status": "UNMEASURED", "why": "deep_forest_sources.json unreadable: the source "
                                               "list is unknown, not empty"}
    vecs = frontier_doc.get("vectors") if isinstance(frontier_doc, Mapping) else None
    vecs = vecs if isinstance(vecs, Mapping) else {}
    hosts: dict[str, dict[str, Any]] = {}

    def row(host: str) -> dict[str, Any]:
        return hosts.setdefault(host, {"grounds": [], "outcomes": set()})

    for g in grounds_doc.get("grounds") or []:
        if not isinstance(g, Mapping):
            continue
        name = str(g.get("name") or "")
        vv = vecs.get(name)
        v: Mapping[str, Any] = vv if isinstance(vv, Mapping) else {}
        for h in _hosts_of(g):
            r = row(h)
            r["grounds"].append(name)
            if v.get("outcome"):
                r["outcomes"].add(str(v["outcome"]))
    for h in list(terms) + list(refused):
        row(h.lower())

    rows: dict[str, Any] = {}
    counts = {"CLEAR": 0, "REFUSED": 0, "UNREAD": 0}
    for h, r in sorted(hosts.items()):
        outs = r["outcomes"]
        why_refused = _host_refused(h, refused)
        terms_v = ("REFUSED" if why_refused else
                   "RECORDED" if _host_has_terms(h, terms) else "TERMS_UNREAD")
        if "BLOCKED" in outs and not (outs & set(READ_OK)):
            robots_v = "REFUSED_OR_BLOCKED"
        elif outs & set(READ_OK):
            robots_v = "READ_OK"
        else:
            robots_v = "ROBOTS_UNMEASURED"
        paid_v = "NO_KEY_ANON_READ" if outs & set(READ_OK) else "PAID_UNMEASURED"
        if terms_v == "REFUSED" or robots_v == "REFUSED_OR_BLOCKED":
            verdict = "REFUSED"
        elif terms_v == "RECORDED" and robots_v == "READ_OK" and paid_v == "NO_KEY_ANON_READ":
            verdict = "CLEAR"
        else:
            verdict = "UNREAD"
        counts[verdict] += 1
        rows[h] = {"verdict": verdict, "terms": terms_v, "robots": robots_v, "paid": paid_v,
                   "refused_why": why_refused or None, "n_grounds": len(r["grounds"]),
                   "grounds": sorted(set(r["grounds"]))[:5]}
    return {
        "status": "MEASURED", "n_hosts": len(rows), "counts": counts,
        "rule": ("E25: free data only, terms and robots respected. UNREAD means the desk has not "
                 "yet read this host's terms or got an anonymous read; it is a debt, never a "
                 "pass, and the miners treat a robots or 401/403/429/451 answer as a hard stop"),
        "hosts": rows,
    }


def current() -> dict[str, Any]:
    terms, refused = _terms_tables()
    return audit(_read(GROUNDS_FILE), _read(FRONTIER_FILE), terms, refused)
