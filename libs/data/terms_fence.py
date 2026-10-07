"""THE TERMS FENCE FOR THE COUNTRY PACKS: which grounds a terms ruling holds, and the one test.

WHY THIS EXISTS. The Asia lane read the China official hosts' terms on 2026-10-06 (PR #229,
branch `claude/asia-cn-official-sge`, `alt_proxies.GATE_TERMS`). CFETS -- chinamoney.com.cn and
its SHIBOR site shibor.org -- carries an explicit clause:

    "No institution or individual shall copy, transmit, save, use, publish, sell, permit others
    to use or process CFETS market data, nor develop or produce work derived therefrom in any
    form without written permission from CFETS."

so it reads `refused`. SAFE (safe.gov.cn) bars commercial reprint and grants nothing permitting a
desk to use the statistics, so it reads `to_confirm` and is held FAIL-CLOSED until a written grant
or a clearer reuse clause is quoted. The PBOC (pbc.gov.cn) and customs (customs.gov.cn)
terms could not be read at all, and fail-closed applies to every to_confirm row, so both are
fenced `to_confirm` too (TERMS_EVIDENCE records each attempt). #229 gates the Asia organs
(the registry, the collector, the parser). The country packs and the generic organs that read
them -- the fixing lab, the dataset acquirer, the source census, the coverage tensor,
pack_cells, source_drain -- are gated here, by the same vocabulary `alt_proxies.status_of`
already speaks on LIVE: `BLOCKED_ON_TERMS:<terms>`.

WHAT A HOLD MEANS. A held row is NEVER fetched, never mints a cell, never claims coverage, and is
NEVER DELETED: the ontology stays open and the gap is named. It is counted as BLOCKED, beside
UNMEASURED, and never as fed or covered. The moment a hold lifts (a written CFETS licence, a SAFE
grant), the row is changed HERE and in #229's table, and every organ reads the new state on its
next pass.

WHAT IT COSTS, stated so the hold is never free (GROWTH GOVERNANCE, Rule 1): the CFETS fix and
close are the inputs of the pack's highest-prior edge (`cn_fix_residual_to_cnh`); with them held
the edge cannot be measured from CFETS values, and USDCNH research is left with the desk's own
tape, the public fixing CLOCK (01:15 / 08:30 UTC, a calendar fact and not CFETS data) and
whatever PBOC announcement is lawful once pbc.gov.cn's terms are read. That is the missed growth,
and it is the cost of trading on data the publisher forbids.

    from libs.data.terms_fence import hold_of
    hold_of("https://www.chinamoney.com.cn/r/cms/www/chinamoney/data/fx/ccpr.json")
    # -> ("refused", "BLOCKED_ON_TERMS:refused -- CFETS ... (ruling: PR #229 ...)")
"""
from __future__ import annotations

import importlib
import re
import sys
import urllib.parse
from collections.abc import Mapping
from pathlib import Path
from typing import Any

#: The status prefix, character for character the one `alt_proxies.status_of` and #229's
#: collector reports emit. A row whose status or licence starts with it is held.
TERMS_BLOCKED = "BLOCKED_ON_TERMS"

#: Where the ruling came from. Carried on every held row so a reader can find the evidence.
RULING = ("PR #229 (claude/asia-cn-official-sge, alt_proxies.GATE_TERMS), terms read "
          "2026-10-06")

CFETS_CLAUSE = ("CFETS market-data terms (https://www.chinamoney.com.cn/english/svcmds/): 'No "
                "institution or individual shall copy, transmit, save, use, publish, sell, "
                "permit others to use or process CFETS market data, nor develop or produce work "
                "derived therefrom in any form without written permission from CFETS.' Covers "
                "the CNY central parity, the CFETS closes, SHIBOR and the LPR")

# ------------------------------------------------------------------ the one source of truth
# THE VERDICTS ARE #229's, NOT A PARALLEL TABLE. `alt_proxies.TERMS_HOSTS` maps a host to a
# terms id and `alt_proxies.terms_gate` answers confirmed / to_confirm / refused for it; this
# module only applies the rule that `to_confirm` and `refused` are both HELD (fail-closed). If
# alt_proxies cannot be imported, the hosts below are held to_confirm: a missing module is never
# permission. That set names hosts only, carries no verdict of its own, and a test pins it to
# alt_proxies' held hosts.
HELD_STATES: tuple[str, ...] = ("refused", "to_confirm")
FAIL_CLOSED_HOSTS: tuple[str, ...] = ("chinamoney.com.cn", "shibor.org", "safe.gov.cn",
                                      "pbc.gov.cn", "customs.gov.cn", "sge.com.cn")
_AP: list[Any] = []


def alt_proxies() -> Any:
    """#229's `research.alt_proxies`, imported once; None when it cannot be imported."""
    if not _AP:
        mod: Any = None
        try:
            desk = Path(__file__).resolve().parents[2] / "desks" / "mt5"
            if str(desk) not in sys.path:
                sys.path.append(str(desk))
            mod = importlib.import_module("research.alt_proxies")
            if not callable(getattr(mod, "terms_gate", None)):
                mod = None
        except Exception:
            mod = None
        _AP.append(mod)
    return _AP[0]


def terms_hosts() -> dict[str, str]:
    """host suffix -> terms id, from alt_proxies (fail-closed placeholder ids without it)."""
    ap = alt_proxies()
    if ap is None:
        return dict.fromkeys(FAIL_CLOSED_HOSTS, "unreadable_alt_proxies")
    return dict(ap.TERMS_HOSTS)


def ref_verdict(ref_or_url: str) -> tuple[str, str]:
    """(state, why) from `alt_proxies.terms_gate`; to_confirm when it cannot be asked."""
    ap = alt_proxies()
    if ap is None:
        return "to_confirm", "alt_proxies unimportable: fail closed"
    state, why = ap.terms_gate(ref_or_url)
    return str(state), str(why)


#: WHAT WAS READ, per terms id: the URL tried, when, and what came back. A host leaves the fence
#: only when alt_proxies' verdict for it turns `confirmed`, which needs a PERMITTING clause
#: quoted verbatim with its URL and fetch date; an unreadable page is never permission.
TERMS_EVIDENCE: dict[str, dict[str, str]] = {
    "cn_cfets_chinamoney": {
        "terms_url": "https://www.chinamoney.com.cn/english/svcmds/",
        "checked_at": "2026-10-06 (read by #229)",
        "permitting_clause": "",
        "result": "REFUSED: explicit no-use-without-written-permission clause"},
    "cn_safe_official": {
        "terms_url": "https://www.safe.gov.cn/safe/flsm/index.html",
        "checked_at": "2026-10-06 (read by #229)",
        "permitting_clause": "",
        "result": "TO_CONFIRM: governs reprinting; grants no use of the data"},
    "cn_pboc_official": {
        "terms_url": "http://www.pbc.gov.cn/ (and http://www.pbc.gov.cn/en/3688006/index.html)",
        "checked_at": "2026-10-06",
        "permitting_clause": "",
        "result": "UNREADABLE: 'URL is disallowed by robots.txt rules' on both pages"},
    "cn_customs_official": {
        "terms_url": ("http://english.customs.gov.cn/statement.html (and "
                      "http://www.customs.gov.cn/customs/wzsm/index.html)"),
        "checked_at": "2026-10-06",
        "permitting_clause": "",
        "result": ("UNREADABLE: 'robots.txt fetch failed: [SSL: CERTIFICATE_VERIFY_FAILED] "
                   "self-signed certificate in certificate chain' on both pages")},
}

# ------------------------------------------------------------------ provenance, not hosts
# A RELAY IS THE SAME DATA. SHIBOR fetched through api.tushare.pro, the parity through akshare or
# any other API, is still CFETS market data, and the clause forbids using it "in any form". A host
# gate never sees a relay, so a series is ALSO held by WHO ORIGINALLY PUBLISHES IT. Each entry is
# a terms id and the series names that publisher originates; the verdict is still alt_proxies'.
_NB = r"(?<![a-z0-9])"
_NE = r"(?![a-z0-9])"
PUBLISHER_SERIES: dict[str, re.Pattern[str]] = {
    "cn_cfets_chinamoney": re.compile(
        rf"{_NB}(?:shibor|lpr|ccpr|cfets|chinamoney|loan[ _-]?prime[ _-]?rate|"
        rf"central[ _-]?parity|cny[ _-]?fix(?:ing)?)(?:_|{_NE})"
        r"|中间价|中間價|贷款市场报价利率|上海银行间同业拆放利率|中国外汇交易中心|全国银行间同业拆借中心",
        re.IGNORECASE),
}


def provenance_hold(*names: str) -> tuple[str, str]:
    """(state, reason) when any of `names` (a series key, an API name, a dataset or publisher
    label) is a series a held publisher ORIGINATES, whatever host relays it; else ("", "")."""
    blob = " ".join(str(n or "") for n in names)
    for ref, pat in PUBLISHER_SERIES.items():
        if pat.search(blob):
            state, why = ref_verdict(ref)
            if state in HELD_STATES:
                return state, reason(state, f"{why} [relayed series, originating publisher: {ref}]")
    return "", ""


#: The fields a pack row or registry row may carry its hold in, checked in this order.
_ROW_FIELDS: tuple[str, ...] = ("terms_status", "status", "licence", "how_to_fetch", "notes",
                                "label")


def status(state: str) -> str:
    """`BLOCKED_ON_TERMS:<state>`, the exact status string the desk already uses."""
    return f"{TERMS_BLOCKED}:{state}"


def reason(state: str, clause: str) -> str:
    """The full held-row text: status, clause and the source of the ruling."""
    return f"{status(state)} -- {clause} (ruling: {RULING})"


def _host(text: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = "https://" + raw.lstrip("/")
    try:
        host = urllib.parse.urlsplit(raw).netloc.lower()
    except ValueError:
        return ""
    return host.rsplit("@", 1)[-1].split(":", 1)[0]


def host_hold(url_or_host: str) -> tuple[str, str]:
    """(state, reason) for a URL or bare host on a held ground, else ("", "")."""
    host = _host(url_or_host)
    if not host or " " in host:
        return "", ""
    ref = next((v for k, v in terms_hosts().items() if host == k or host.endswith("." + k)),
               None)
    if ref is None:
        return "", ""
    state, why = ref_verdict(ref) if alt_proxies() is not None else ("to_confirm", ref)
    if state not in HELD_STATES:
        return "", ""
    return state, reason(state, why)


def _get(row: Any, name: str) -> str:
    if isinstance(row, Mapping):
        return str(row.get(name) or "")
    return str(getattr(row, name, "") or "")


def row_hold(row: Any) -> tuple[str, str]:
    """(state, reason) for a pack row, typed row or registry row that carries a hold.

    Read from, in order: a `BLOCKED_ON_TERMS:<state>` prefix on any of `_ROW_FIELDS`; a
    `terms_ref` naming a held terms id; a `url` / `root` / `roots` on a held host."""
    for name in _ROW_FIELDS:
        text = _get(row, name).strip()
        if text.startswith(TERMS_BLOCKED):
            head = text.split(" ", 1)[0]
            state = head.split(":", 1)[1] if ":" in head else "to_confirm"
            return state or "to_confirm", text
    # A source class flattened to the framework's string (`<id> :: ... :: licence=<licence>`)
    # carries its hold inside the line, never at its head.
    marker = f"licence={TERMS_BLOCKED}"
    label = _get(row, "label")
    if marker in label:
        text = label[label.index(marker) + len("licence="):].strip()
        head = text.split(" ", 1)[0]
        return (head.split(":", 1)[1] if ":" in head else "to_confirm") or "to_confirm", text
    ref = _get(row, "terms_ref")
    if ref:
        state, why = ref_verdict(ref)
        if state in HELD_STATES:
            return state, reason(state, why)
    # A row is held by its hosts only when EVERY host it names is held: a source with one held
    # root among several open ones stays open, and the per-URL gate (`host_hold`, asked by every
    # fetching organ) skips just the held root. Otherwise one mirror root on customs.gov.cn would
    # silence a whole multi-country source.
    hosts = [part for name in ("url", "root") for part in _get(row, name).split(",")
             if part.strip()]
    roots = row.get("roots") if isinstance(row, Mapping) else getattr(row, "roots", None)
    hosts += [str(r) for r in (roots or ()) if str(r).strip()]
    holds = [host_hold(h) for h in hosts]
    if holds and all(h[0] for h in holds):
        refused = [h for h in holds if h[0] == "refused"]
        return (refused or holds)[0]
    return "", ""


def text_hold(text: str) -> tuple[str, str]:
    """(state, reason) for a row flattened to ONE STRING (a pack's positioning or institutional
    line) that carries `BLOCKED_ON_TERMS:<state>` anywhere in it, else ("", "")."""
    raw = str(text or "")
    at = raw.find(TERMS_BLOCKED + ":")
    if at < 0:
        return "", ""
    tail = raw[at:]
    head = tail.split(" ", 1)[0].rstrip(",;)")
    return (head.split(":", 1)[1] or "to_confirm"), tail


def hold_of(row_or_url: Any) -> tuple[str, str]:
    """(state, reason) for a row, a flattened row line or a URL; ("", "") when nothing holds
    it."""
    if isinstance(row_or_url, str):
        got = text_hold(row_or_url)
        return got if got[0] else host_hold(row_or_url)
    return row_hold(row_or_url)


def is_held(row_or_url: Any) -> bool:
    return bool(hold_of(row_or_url)[0])
