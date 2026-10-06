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

import urllib.parse
from collections.abc import Mapping
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
                "the CNY central parity, the CFETS closes and SHIBOR")
SAFE_CLAUSE = ("SAFE legal statement (https://www.safe.gov.cn/safe/flsm/index.html): commercial "
               "reprint barred; non-commercial reprint only by permitted media with attribution; "
               "no grant to use the data. Held to_confirm and FAIL-CLOSED until a written SAFE "
               "grant or a clearer reuse clause is quoted")

#: FAIL-CLOSED APPLIES TO EVERY to_confirm ROW (coordinator ruling, 2026-10-06). The PBOC and
#: customs hosts were read for terms on that date and neither could be read, so both are fenced.
PBOC_CLAUSE = ("pbc.gov.cn: no site statement readable (2026-10-06: the fetcher is "
               "robots-disallowed on http://www.pbc.gov.cn/ and its English site, and #229 "
               "found no route from the container proxy). Held to_confirm and FAIL-CLOSED "
               "until the footer's site statement is read and quoted")
CUSTOMS_CLAUSE = ("customs.gov.cn: no statement readable (2026-10-06: "
                  "http://english.customs.gov.cn/statement.html and the Chinese site fail on a "
                  "self-signed certificate chain before robots.txt can be read). Held "
                  "to_confirm and FAIL-CLOSED until the STATEMENT page is read and quoted")

#: Terms ids (#229's `terms_ref` vocabulary) -> (state, clause).
TERMS_REFS: dict[str, tuple[str, str]] = {
    "cn_cfets_chinamoney": ("refused", CFETS_CLAUSE),
    "cn_safe_official": ("to_confirm", SAFE_CLAUSE),
    "cn_pboc_official": ("to_confirm", PBOC_CLAUSE),
    "cn_customs_official": ("to_confirm", CUSTOMS_CLAUSE),
}

#: WHAT WAS READ, per terms id: the URL tried, when, and what came back. A host leaves the fence
#: only when its entry here quotes a PERMITTING clause verbatim with its URL and fetch date; an
#: unreadable page is never permission.
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

#: Registrable host suffix -> terms id. Matched on the suffix so www./en./any sub-host is held
#: together with its root, as #229's `TERMS_HOSTS` does.
TERMS_HOSTS: dict[str, str] = {
    "chinamoney.com.cn": "cn_cfets_chinamoney",
    "shibor.org": "cn_cfets_chinamoney",
    "safe.gov.cn": "cn_safe_official",
    "pbc.gov.cn": "cn_pboc_official",
    "customs.gov.cn": "cn_customs_official",
}

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
    if not host:
        return "", ""
    ref = next((v for k, v in TERMS_HOSTS.items() if host == k or host.endswith("." + k)), None)
    if ref is None:
        return "", ""
    state, clause = TERMS_REFS[ref]
    return state, reason(state, clause)


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
    if ref in TERMS_REFS:
        state, clause = TERMS_REFS[ref]
        return state, reason(state, clause)
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
