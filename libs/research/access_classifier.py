"""THE ACCESS ROUTER -- classification ROUTES USE; robots and terms decide whether the desk FETCHES.

LAWS 5e (principal's standing order, 2026-09-23, permanent, replacing the 2026-09-17 text), AS
AMENDED 2026-11-17 (Governance, refused act 6). THE DESK MINES AND TESTS EVERYTHING IT CAN SEE ON
THE OPEN INTERNET, WITHIN WHAT THE HOST'S ROBOTS.TXT AND TERMS ALLOW AN AUTOMATED CLIENT. On that
content, licence, source class and credibility are ROUTING AND PROVENANCE LABELS on the row: they
describe what the desk may REDISTRIBUTE or publish, and how much weight the evidence carries, and
they never stop discovery, ingestion, representation or testing.

THE 2026-11-17 AMENDMENT: ROBOTS AND TERMS DECIDE WHETHER THE DESK FETCHES -- refused act 6, "no
automated fetch that the host's robots.txt or terms refuse". A robots `Disallow` for the path, a
robots.txt the desk cannot read (fail closed, enforced at the fetch path by `robots_gate`), terms
that forbid automated access, scraping or data mining, or terms the desk has NOT READ or cannot
read REFUSE the automated fetch; a mirror, cache or archive of a refused page is the same
refusal. A refused source is still CATALOGUED from what the desk lawfully saw elsewhere (its name,
URL, a search snippet): act 6 is not carried by a refused label -- `classify()` labels the row
PUBLIC_WITH_TERMS with the reason in `terms_note` and returns `fetch_allowed=False` ("registered,
never scraped"). It is not dropped. `FETCH_REFUSALS` names the three brakes the amendment
restored as refusals under act 6. A refused source is fetched only through the permission route
of LAWS 5e (a governance ruling naming it), which this pure module does not adjudicate.

WHAT "UNREAD" MEANS IN A PURE MODULE. `classify()` does no IO, so it refuses on what the metadata
SAYS: `robots` of disallow/disallowed/barred/blocked/unreadable; a terms verdict (`terms_verdict`,
`terms_status` or a bare `terms` value) of to_confirm/unread/unreadable/refused; `terms_read`
false; `machine_use_allowed=false`; a declared machine-extraction ban; no-automation terms text.
`robots: unknown` or no robots key, and NO terms verdict at all, are UNMEASURED here -- they do
not refuse in `classify()`, because the fetch path is where robots.txt and the terms are actually
read: `robots_gate` fails closed on an unreadable robots file, and the terms gate of the fetching
organ must refuse a host whose terms it has not read. A `fetch_allowed=True` verdict is therefore
necessary, never sufficient.

The failure this module exists to prevent is not a legal one: it is a TIMID one. A crawler that
meets an unfamiliar page and discards it "because it looks risky" throws away most of the world's
information for no measured reason, and nothing in the desk ever records that it happened. Things
published on the open internet are lawful to read. The 2026-09-17 version of this module carried a
quarantine, a machine-extraction veto and a robots refusal; 2026-09-23 deleted all three, and
2026-11-17 RESTORED the robots and terms items as refusals of the automated FETCH only (see
`FETCH_REFUSALS`). The quarantine stays deleted. There is no ACCESS_UNCLEAR quarantine any more:
an unclear row is mined and tested with its label attached. Fringe, retail, forum, archive and
machine-translated ground are FIRST-CLASS INPUTS.

WHAT REMAINS REFUSED IS ABOUT ACTS, NOT ABOUT CONTENT, AND IT IS EXACTLY SIX (`HARD_BOUNDARY`).
Acts 1-5 refuse the source outright through the three refused labels; act 6 refuses the
automated FETCH and leaves the source catalogued. Nothing else is a brake. A later session must
not re-derive the old caution from silence: if an act is not one of those six, the desk mines it.

THE PIPELINE IS FIVE STAGES AND EVERY SOURCE WALKS ALL FIVE:

    DISCOVER -> CAPTURE METADATA -> LEGAL/ACCESS CLASSIFICATION -> EVIDENCE CLASSIFICATION
    -> RESEARCH

`route()` returns WHICH stage decided, because "we did not use this source" is an answer that
must name its reason. A source dropped at CAPTURE_METADATA (no identity at all) and a source
refused at LEGAL_ACCESS (a credential dump) are different facts, and a pipeline that reports both
as "skipped" is a pipeline nobody can audit.

THREE INDEPENDENT DIMENSIONS, NEVER COLLAPSED. This is the whole design:

    access_label      WHAT THE DESK MAY REDISTRIBUTE and how the row is provenanced (never
                      whether it may be mined: everything off the hard boundary is mined)
    credibility       is the claim likely TRUE
    predictive_state  does its EXISTENCE predict anything

An anonymous forum post is perfectly lawful and unreliable. A government release is lawful,
authoritative and frequently useless for alpha. A public rumour can be lawful, FALSE as a factual
claim, and still PREDICTIVE as a crowding or narrative feature -- which is why `preserve()` never
drops a fringe or contradicted claim, it lowers its weight and keeps it as an evidence object.
Collapsing the three into one "quality score" is how a desk deletes its own crowding signal.

THE HARD BOUNDARY is specific, short, absolute and SIX ACTS long (`HARD_BOUNDARY`). PRIVATE,
CONFIDENTIAL_MNPI and STOLEN_UNAUTHORIZED are the three labels that carry acts 1-5, and they are
REFUSED with the reason recorded -- recorded, because a refusal nobody wrote down gets re-proposed
next month by a miner that never heard about it. If a page is behind a login or a paywall the desk
does not break in; EVERYTHING REACHABLE WITHOUT BREAKING IN IS MINED, including the open surface
of a paywalled domain.

ACCESS_UNCLEAR IS MINED AND TESTED WITH ITS LABEL ATTACHED. There is no quarantine. An unresolved
access question is a PROVENANCE NOTE on the row, not a reason to leave the content unread.

PURE. No IO, no clock, no network, no registry. `desks/mt5/research/evidence_router.py` is the
organ that walks the registry and the intelligence rows through these functions.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Literal, cast

# --------------------------------------------------------------------------------- the principle

#: The order, verbatim. Carried as a constant so an organ can print the rule it is applying and
#: a fence can check the text still says what the law says.
PRINCIPLE = ("The desk mines and tests everything it can see on the open internet, within what "
             "the host's robots.txt and terms allow an automated client. Robots and terms decide "
             "whether the desk fetches: a robots Disallow, an unreadable robots.txt, or terms "
             "that forbid automated access or that the desk has not read refuse the automated "
             "fetch, and the source is catalogued, never fetched. On content the desk may fetch, "
             "licence, source class and credibility are routing and provenance labels: they "
             "describe what may be redistributed and how much weight the evidence carries, and "
             "they never stop ingestion, representation or testing of that content.")

#: THE HARD BOUNDARY -- six ACTS, verbatim and absolute (LAWS 5e; act 6 is the Governance
#: amendment of 2026-11-17). Nothing in this module or its callers may widen it, and nothing may
#: add a seventh. These are acts, not content: they describe things the desk does not DO, never
#: subjects it may not read. Acts 1-5 are carried by `REFUSED_LABELS`; act 6 is carried on the
#: row as PUBLIC_WITH_TERMS with `fetch_allowed=False` (catalogued, never fetched).
HARD_BOUNDARY: tuple[str, ...] = (
    "no credential theft or logging in as someone else",
    "no bypassing an access control or a paywall",
    "no material non-public information",
    "no stolen or leaked private data",
    "no personal data harvesting or doxxing",
    "no automated fetch that the host's robots.txt or terms refuse",
)

#: The number is load-bearing: a fence checks it, so a later session cannot quietly add a
#: seventh brake and call it a boundary.
HARD_BOUNDARY_COUNT = 6

#: The act a fetch refusal applies, by its index in `HARD_BOUNDARY`.
FETCH_ACT = HARD_BOUNDARY[5]

#: DELETED BRAKES, named so a later session recognises them if it meets one in old code or prose
#: and does not mistake it for a live rule. Each was a discovery brake, not a legal requirement.
#: (The robots, machine-use and machine-extraction items that were here are RESTORED as fetch
#: refusals by the 2026-11-17 amendment; they live in `FETCH_REFUSALS` now.)
REMOVED_BRAKES: tuple[str, ...] = (
    "ACCESS_UNCLEAR quarantine (metadata kept, content not consumed)",
    "'public/licensed sources only' as a pre-filter on discovery",
    "source-class and credibility used to drop rather than weight a row",
)

#: LIVE REFUSALS OF THE AUTOMATED FETCH -- LAWS 5e as amended 2026-11-17 (Governance): "three
#: items once listed here are NOT brakes and are RESTORED as refusals under act 6: robots.txt
#: Disallow read as a refusal, the machine-extraction veto, and `machine_use_allowed=false` read
#: as 'registered, never scraped'." Each applies refused act 6 (`FETCH_ACT`): the row is kept and
#: catalogued (PUBLIC_WITH_TERMS, reason in `terms_note`) from what the desk lawfully saw
#: elsewhere, and it is never fetched. A mirror, cache or archive of a refused page is the same
#: refusal.
FETCH_REFUSALS: tuple[str, ...] = (
    "machine-extraction veto on PUBLIC_WITH_TERMS",
    "robots.txt Disallow treated as a refusal",
    "machine_use_allowed=false treated as 'registered, never scraped'",
)

#: The uses a fetch refusal withholds. What remains -- register, read_manual (a person reading
#: it), derive_features / alpha_input / narrative_feature on what was lawfully seen elsewhere --
#: is the catalogue entry, which the amendment keeps.
FETCH_USES: tuple[str, ...] = ("fetch_api", "machine_extract", "store_raw")

#: Robots verdicts that refuse the fetch. `unknown` is NOT here: in this pure module it means
#: "not yet read", and the fetch path's `robots_gate` fails closed on an unreadable file.
ROBOTS_REFUSING: tuple[str, ...] = ("disallow", "disallowed", "barred", "blocked", "unreadable")

#: Terms verdicts that refuse the fetch: unread or unreadable terms are not "no ban" (LAWS 5e act
#: 6; the desk's own terms vocabulary is confirmed / to_confirm / refused).
TERMS_REFUSING: tuple[str, ...] = ("to_confirm", "unread", "unreadable", "refused", "forbidden")

#: Literal phrases in declared terms that forbid automated access, scraping or data mining.
#: Deliberately literal: a terms page that merely EXISTS is a label, not a refusal.
TERMS_REFUSAL_MARKERS: tuple[str, ...] = (
    "no scraping", "scraping is prohibited", "scraping is not permitted", "prohibits scraping",
    "automated access is prohibited", "prohibits automated access", "no automated access",
    "automated access is not permitted", "data mining is prohibited", "prohibits data mining",
    "no data mining", "no robots or spiders",
)

#: The five stages, in order. `route()` reports which one decided.
STAGES: tuple[str, ...] = ("DISCOVER", "CAPTURE_METADATA", "LEGAL_ACCESS", "EVIDENCE_CLASS",
                           "RESEARCH")

# ------------------------------------------------------------------------------ the three axes

AccessLabel = Literal["PUBLIC", "PUBLIC_WITH_TERMS", "LICENSED", "OPEN_DATA", "PUBLIC_ARCHIVE",
                      "PUBLIC_SOCIAL", "USER_SUBMITTED", "ACCESS_UNCLEAR", "PRIVATE",
                      "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED"]
ACCESS_LABELS: tuple[AccessLabel, ...] = ("PUBLIC", "PUBLIC_WITH_TERMS", "LICENSED", "OPEN_DATA",
                                          "PUBLIC_ARCHIVE", "PUBLIC_SOCIAL", "USER_SUBMITTED",
                                          "ACCESS_UNCLEAR", "PRIVATE", "CONFIDENTIAL_MNPI",
                                          "STOLEN_UNAUTHORIZED")

Credibility = Literal["AUTHORITATIVE", "RELIABLE", "UNRELIABLE", "FRINGE", "CONTRADICTED",
                      "UNKNOWN"]
CREDIBILITIES: tuple[Credibility, ...] = ("AUTHORITATIVE", "RELIABLE", "UNRELIABLE", "FRINGE",
                                          "CONTRADICTED", "UNKNOWN")

PredictiveState = Literal["UNTESTED", "PREDICTIVE", "NOT_PREDICTIVE", "NARRATIVE_FEATURE"]
PREDICTIVE_STATES: tuple[PredictiveState, ...] = ("UNTESTED", "PREDICTIVE", "NOT_PREDICTIVE",
                                                  "NARRATIVE_FEATURE")

#: The ten source classes of LAWS 5f, exactly.
SourceClass = Literal["official", "institutional", "academic", "practitioner", "retail_ecology",
                      "app_ecosystem", "media", "archive", "physical_economy", "source_graph"]
SOURCE_CLASSES: tuple[SourceClass, ...] = ("official", "institutional", "academic",
                                           "practitioner", "retail_ecology", "app_ecosystem",
                                           "media", "archive", "physical_economy", "source_graph")

#: HOW the desk came to hold the content. `leaked_looking` is not an accusation -- it is the
#: honest name for material whose provenance looks like an unauthorised dump, which routes to
#: STOLEN_UNAUTHORIZED rather than being quietly used.
Obtained = Literal["public_page", "api", "user_submission", "archive", "licensed_feed",
                   "leaked_looking", "UNKNOWN"]
OBTAINED: tuple[Obtained, ...] = ("public_page", "api", "user_submission", "archive",
                                  "licensed_feed", "leaked_looking", "UNKNOWN")

# ------------------------------------------------------------------------------- allowed uses

#: The vocabulary of USES. Restricting a use is surgical only if the uses have names.
USES: tuple[str, ...] = ("register", "read_manual", "fetch_api", "machine_extract", "store_raw",
                         "derive_features", "alpha_input", "narrative_feature", "redistribute")

#: EVERY USE A MINING PIPELINE NEEDS. `redistribute` is deliberately NOT here -- it is the one
#: use a licence can actually take away, and it is granted per-label below.
MINING_USES: tuple[str, ...] = ("register", "read_manual", "fetch_api", "machine_extract",
                                "store_raw", "derive_features", "alpha_input",
                                "narrative_feature")

#: THE ROUTING TABLE, AS DATA (LAWS 5e). One row per label: what may be done, whether the source
#: is refused outright (acts 1-5 only), and the CEILING on the EVIDENCE weight anything
#: derived from it may carry. THE CAP IS ABOUT EVIDENCE, NEVER ABOUT LEGALITY, and it never stops
#: the row being mined or tested -- a capped row is tested exactly as hard as any other and its
#: result simply carries less weight. `quarantine` is retained as a field and is False on every
#: row: the quarantine was deleted on 2026-09-23 and the key stays only so old readers do not
#: KeyError.
ROUTING: dict[AccessLabel, dict[str, Any]] = {
    "PUBLIC": {
        "allowed_uses": MINING_USES,
        "quarantine": False, "refused": False, "evidence_weight_cap": 1.0,
        "reason": "public page: observe, extract and research it; reliability is a SEPARATE axis",
    },
    "PUBLIC_WITH_TERMS": {
        # LAWFULLY FETCHABLE ROWS ARE MINED IN FULL: these terms bear on REDISTRIBUTION, which is
        # the use withheld. A row whose robots or terms REFUSE the automated fetch (2026-11-17)
        # also carries this label, but `_verdict(..., fetch_refusal=...)` strips `FETCH_USES` from
        # its verdict, so it is catalogued and never fetched.
        "allowed_uses": MINING_USES,
        "quarantine": False, "refused": False, "evidence_weight_cap": 1.0,
        "reason": ("public with terms: MINED AND TESTED IN FULL when lawfully fetchable; the "
                   "label routes redistribution and provenance. Robots or terms that refuse the "
                   "automated fetch make it catalogued, never fetched (LAWS 5e, 2026-11-17)"),
    },
    "LICENSED": {
        "allowed_uses": MINING_USES,
        "quarantine": False, "refused": False, "evidence_weight_cap": 1.0,
        "reason": "licensed: used strictly per its licence; redistribution is not implied",
    },
    "OPEN_DATA": {
        "allowed_uses": (*MINING_USES, "redistribute"),
        "quarantine": False, "refused": False, "evidence_weight_cap": 1.0,
        "reason": "open data licence: the widest lawful use the desk has, redistribution included",
    },
    "PUBLIC_ARCHIVE": {
        "allowed_uses": MINING_USES,
        "quarantine": False, "refused": False, "evidence_weight_cap": 1.0,
        "reason": ("public archive: FIRST-CLASS ground; the point-in-time record is exactly what "
                   "a PIT desk wants"),
    },
    "PUBLIC_SOCIAL": {
        "allowed_uses": MINING_USES,
        "quarantine": False, "refused": False, "evidence_weight_cap": 0.6,
        "reason": ("public social, forum and retail ground: FIRST-CLASS input, mined and tested "
                   "in full; the weight ceiling is about EVIDENCE, not legality, and the "
                   "crowding/narrative use is first-class"),
    },
    "USER_SUBMITTED": {
        "allowed_uses": MINING_USES,
        "quarantine": False, "refused": False, "evidence_weight_cap": 0.5,
        "reason": "submitted by a user: usable, provenance is the submitter and is recorded",
    },
    "ACCESS_UNCLEAR": {
        # MINED AND TESTED WITH THE LABEL ATTACHED. The 2026-09-17 quarantine (`register` only,
        # cap 0.0) is DELETED: an unresolved access question is a provenance note, never a reason
        # to leave content unread. The cap is 1.0 because access has nothing to say about truth --
        # credibility is the axis that weights the row.
        "allowed_uses": MINING_USES,
        "quarantine": False, "refused": False, "evidence_weight_cap": 1.0,
        "reason": ("access path unresolved: MINED AND TESTED with the label attached; the "
                   "unclear-access quarantine was deleted on 2026-09-23"),
    },
    "PRIVATE": {
        "allowed_uses": (),
        "quarantine": False, "refused": True, "evidence_weight_cap": 0.0,
        "reason": ("behind a login or an access control, or personal data: the desk does not "
                   "break in and does not harvest people (hard boundary acts 1, 2 and 5)"),
    },
    "CONFIDENTIAL_MNPI": {
        "allowed_uses": (),
        "quarantine": False, "refused": True, "evidence_weight_cap": 0.0,
        "reason": ("material non-public information: never an alpha input and never traded on "
                   "(hard boundary act 3)"),
    },
    "STOLEN_UNAUTHORIZED": {
        "allowed_uses": (),
        "quarantine": False, "refused": True, "evidence_weight_cap": 0.0,
        "reason": ("stolen or leaked private data, or material obtained by bypassing an access "
                   "control or paywall (hard boundary acts 1, 2 and 4)"),
    },
}

#: The three labels that carry refused ACTS 1-5. They are the only labels that refuse a source
#: outright; act 6 refuses the automated fetch and leaves the row catalogued (`fetch_allowed`).
REFUSED_LABELS: tuple[AccessLabel, ...] = ("PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED")

#: Every other label is mined. Named as data so a fence can assert the list did not shrink.
MINED_LABELS: tuple[AccessLabel, ...] = tuple(
    lab for lab in ACCESS_LABELS if lab not in REFUSED_LABELS)

#: Evidence-weight ceiling by credibility. UNRELIABLE, FRINGE and CONTRADICTED are LOW, never
#: zero and never dropped: a false public rumour that everyone is reading is a crowding feature,
#: and the desk that deletes it has deleted a measurement of what other people believe.
CREDIBILITY_WEIGHT: dict[Credibility, float] = {
    "AUTHORITATIVE": 1.0, "RELIABLE": 0.8, "UNKNOWN": 0.4,
    "UNRELIABLE": 0.25, "FRINGE": 0.15, "CONTRADICTED": 0.1,
}

#: Default credibility by source class, where nothing else is measured. A PRIOR, not a verdict:
#: any measured credibility on the metadata wins.
CLASS_CREDIBILITY: dict[SourceClass, Credibility] = {
    "official": "AUTHORITATIVE", "institutional": "RELIABLE", "academic": "RELIABLE",
    "practitioner": "UNKNOWN", "retail_ecology": "UNRELIABLE", "app_ecosystem": "UNKNOWN",
    "media": "UNKNOWN", "archive": "RELIABLE", "physical_economy": "RELIABLE",
    "source_graph": "UNKNOWN",
}

#: MNPI HEURISTICS: non-public corporate figures before their scheduled release, and the language
#: of an insider handing over numbers. These SUSPECT a label -- they are deliberately literal
#: phrases, because a fuzzy MNPI detector that fires on every earnings preview would push the
#: desk back toward the timid global filter this law forbids.
MNPI_MARKERS: tuple[str, ...] = (
    "pre-release earnings", "prerelease earnings", "unreleased earnings", "before the embargo",
    "embargoed results", "under embargo", "insider tip", "from someone inside", "not yet public",
    "unpublished results", "board minutes", "draft 10-k", "draft 10-q", "leaked guidance",
    "material nonpublic", "material non-public",
)

#: UNAUTHORISED-DUMP HEURISTICS: proprietary data pastes and credential lists.
DUMP_MARKERS: tuple[str, ...] = (
    "credential list", "password dump", "combolist", "combo list", "database leak", "data leak",
    "leaked database", "hacked", "breach dump", "dehashed", "proprietary dataset paste",
    "paywall bypass", "cracked", "pirated", "torrent of the dataset",
)

#: Domains and path fragments that mean PRIVATE by construction -- an authenticated surface.
PRIVATE_MARKERS: tuple[str, ...] = (
    "localhost", "127.0.0.1", "192.168.", "10.0.0.", "/admin/", "/wp-admin/", "intranet.",
    "webmail.", "/account/", "/internal/", "vpn.",
)

#: Open-data licence tokens.
OPEN_LICENCES: tuple[str, ...] = ("cc0", "cc-by", "cc by", "public domain", "odbl", "odc-by",
                                  "pddl", "mit", "apache-2.0", "bsd", "open government licence",
                                  "ogl")


#: STRING -> LITERAL lookups, built from the tuples above. A `.get` with a default is explicit
#: and version-independent; narrowing a `str` with `x in TUPLE` happens to satisfy today's mypy
#: and is exactly the version-specific inference this repo's pyproject forbids relying on.
_OBTAINED_BY_NAME: dict[str, Obtained] = {o: o for o in OBTAINED}
_CREDIBILITY_BY_NAME: dict[str, Credibility] = {c: c for c in CREDIBILITIES}
_PREDICTIVE_BY_NAME: dict[str, PredictiveState] = {p: p for p in PREDICTIVE_STATES}
_CLASS_CREDIBILITY_BY_NAME: dict[str, Credibility] = {str(k): v
                                                      for k, v in CLASS_CREDIBILITY.items()}


def _text(meta: dict[str, Any], *keys: str) -> str:
    """Lower-cased concatenation of the named metadata fields. Missing reads empty, never None."""
    parts: list[str] = []
    for k in keys:
        v = meta.get(k)
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, (list, tuple)):
            parts.extend(str(x) for x in v)
        elif v is not None:
            parts.append(str(v))
    return " ".join(parts).lower()


def _flag(meta: dict[str, Any], key: str) -> bool | None:
    """A tri-state metadata flag: True, False, or UNMEASURED (None). Absence is never False."""
    v = meta.get(key)
    if isinstance(v, bool):
        return v
    if isinstance(v, str) and v.strip().lower() in ("true", "false"):
        return v.strip().lower() == "true"
    return None


def credibility_of(source_class: str = "", declared: str = "") -> Credibility:
    """The credibility axis, read INDEPENDENTLY of access: a measured value wins, otherwise the
    source class's prior, otherwise UNKNOWN. Never derived from the access label -- that is the
    collapse this law forbids."""
    if declared in _CREDIBILITY_BY_NAME:
        return _CREDIBILITY_BY_NAME[declared]
    return _CLASS_CREDIBILITY_BY_NAME.get(source_class, "UNKNOWN")


@dataclass(frozen=True)
class AccessVerdict:
    """What the desk DOES with one source, and why.

    `fetch_allowed` (2026-11-17) answers "may the desk FETCH this automatically": False on a
    robots Disallow, a declared `machine_use_allowed=false`, a declared machine-extraction ban or
    terms that forbid automated access (`FETCH_REFUSALS`), and on refused acts 1-5. Such a
    row is CATALOGUED, never fetched: it keeps `register`, loses `FETCH_USES`, and stays in the
    pipeline with its reason in `terms_note`.

    `machine_use_allowed` is `fetch_allowed and not refused` -- the restored meaning,
    "registered, never scraped" when False. A True verdict is necessary, never sufficient: the
    fetch path still reads robots.txt through `robots_gate`, which fails closed.
    """

    access_label: AccessLabel
    allowed_uses: tuple[str, ...]
    quarantine: bool
    refused: bool
    reason: str
    evidence_weight_cap: float
    #: The metadata fact that decided the label, so a verdict can be argued with.
    basis: str = "source metadata"
    #: False when the row is refused on the hard boundary OR its automated fetch is refused by
    #: robots or terms (LAWS 5e as amended 2026-11-17).
    machine_use_allowed: bool = True
    #: THE ROUTING LABEL THAT REPLACED THE BRAKE: may the desk republish this outside itself?
    #: A terms or robots note lands here and NOWHERE ELSE, so it can never stop mining again.
    redistribute_allowed: bool = False
    #: Free-text provenance note carried with the row (terms, robots, paywall, licence).
    terms_note: str = ""
    #: May the desk FETCH this source automatically? False on a fetch refusal (robots / terms,
    #: `FETCH_REFUSALS`) or a hard-boundary refusal. Necessary, never sufficient: the fetch path
    #: still reads robots.txt through `robots_gate` (fail closed).
    fetch_allowed: bool = True
    #: The robots/terms fact that refused the fetch, or "".
    fetch_refusal: str = ""

    def may(self, use: str) -> bool:
        """Is `use` permitted? The only question a caller should ever ask this object."""
        return use in self.allowed_uses

    @property
    def mined(self) -> bool:
        """True when the desk mines, ingests, represents and tests this row -- everything that is
        not one of refused acts 1-5. A fetch-refused row is still mined from its catalogue
        entry (what was lawfully seen elsewhere); `fetchable` says whether it may be fetched."""
        return not self.refused

    @property
    def fetchable(self) -> bool:
        """True when an automated fetch is not refused by the hard boundary, robots or terms."""
        return self.fetch_allowed and not self.refused


def _verdict(label: AccessLabel, basis: str, *, reason: str | None = None,
             terms_note: str = "", fetch_refusal: str = "") -> AccessVerdict:
    row = ROUTING[label]
    uses = cast(tuple[str, ...], row["allowed_uses"])
    refused = bool(row["refused"])
    if fetch_refusal:
        uses = tuple(u for u in uses if u not in FETCH_USES)
    fetch_ok = not refused and not fetch_refusal
    return AccessVerdict(
        access_label=label, allowed_uses=uses, quarantine=False,
        refused=refused, reason=reason or str(row["reason"]),
        evidence_weight_cap=float(row["evidence_weight_cap"]), basis=basis,
        machine_use_allowed=fetch_ok, redistribute_allowed="redistribute" in uses,
        terms_note=terms_note, fetch_allowed=fetch_ok, fetch_refusal=fetch_refusal)


def fetch_refusal_of(meta: dict[str, Any]) -> str:
    """The robots/terms fact that REFUSES the automated fetch (LAWS 5e as amended 2026-11-17),
    or "". Refused act 6 (`FETCH_ACT`). Pure: `robots` absent or `unknown`, and no terms verdict
    at all, are UNMEASURED and refuse nothing here -- the fetch path reads the files, and
    `robots_gate` fails closed on an unreadable robots.txt."""
    reasons: list[str] = []
    robots = str(meta.get("robots") or "unknown").strip().lower()
    if robots in ROBOTS_REFUSING:
        reasons.append(f"robots={robots}")
    if _flag(meta, "machine_use_allowed") is False:
        reasons.append("the source declares machine_use_allowed=false")
    if (_flag(meta, "machine_extraction_allowed") is False
            or _flag(meta, "machine_extraction_forbidden") is True):
        reasons.append("the source forbids machine extraction")
    if _flag(meta, "terms_forbid_automated") is True:
        reasons.append("the terms forbid automated access")
    if _flag(meta, "terms_read") is False:
        reasons.append("the terms are unread (terms_read=false)")
    for key in ("terms_verdict", "terms_status", "terms"):
        verdict = str(meta.get(key) or "").strip().lower()
        if verdict in TERMS_REFUSING:
            reasons.append(f"{key}={verdict} (unread, unreadable or refusing terms)")
            break
    if _flag(meta, "mirror_of_refused") is True:
        reasons.append("a mirror, cache or archive of a refused page")
    terms = _text(meta, "terms", "licence_note", "terms_note")
    hit = next((m for m in TERMS_REFUSAL_MARKERS if m in terms), "")
    if hit:
        reasons.append(f"the terms say {hit!r}")
    return "; ".join(reasons)


def classify(meta: dict[str, Any]) -> AccessVerdict:
    """The LEGAL/ACCESS stage: one source's metadata -> one access verdict.

    ORDER MATTERS AND IT IS THE HARD BOUNDARY FIRST -- acts 1-5, and nothing else. Anything
    that looks like an unauthorised dump, material non-public information, or an authenticated
    private surface is refused before any other reading can rescue it: a licence field saying
    "public" on a credential list does not make it public. Everything AFTER the boundary is MINED,
    within act 6, because that is the other half of the same order: the boundary is six acts wide
    so the permission can be everything else.

    THE FETCH REFUSAL (2026-11-17) IS READ BEFORE THE PERMISSIVE LABELS. A robots Disallow or
    terms forbidding automated access refuse the automated fetch whatever the licence says (an
    open-data licence does not override a host's robots file), so such a row is catalogued as
    PUBLIC_WITH_TERMS with `fetch_allowed=False` and the reason in `terms_note`. Never dropped.

    Metadata keys read (all optional; absence is UNMEASURED, never a permission):
      url / domain, source_class, obtained, licence, robots (allowed/disallowed/unreadable/
      unknown -- unknown is "not yet read" and refuses nothing here), machine_use_allowed,
      machine_extraction_allowed / machine_extraction_forbidden, terms_forbid_automated, terms
      (free text), title / text / description (heuristic surface), requires_auth, paywalled,
      is_open_data, credibility.
    """
    url = _text(meta, "url", "domain", "source_id")
    # `claim` IS THE ROUTER'S OWN PRIMARY CONTENT KEY and was missing from this list until
    # 2026-09-23, so a credential dump or an MNPI line arriving as {"claim": ...} -- the shape
    # `route()` itself builds -- reached none of the marker scans below and was labelled on its
    # url alone. Widening the boundary's reach is the one direction this module may move.
    blob = _text(meta, "claim", "title", "text", "description", "note", "licence_note", "terms",
                 "how_obtained", "provenance")
    licence = _text(meta, "licence", "license", "licence_note")
    obtained_raw = str(meta.get("obtained") or meta.get("how_obtained") or "UNKNOWN")
    obtained: Obtained = _OBTAINED_BY_NAME.get(obtained_raw, "UNKNOWN")

    # ------------------------------------------------------------------ 1. the hard boundary
    if obtained == "leaked_looking" or any(m in blob for m in DUMP_MARKERS):
        hit = next((m for m in DUMP_MARKERS if m in blob), "obtained=leaked_looking")
        return _verdict("STOLEN_UNAUTHORIZED", f"unauthorised-dump marker {hit!r}")
    if any(m in blob for m in MNPI_MARKERS):
        hit = next(m for m in MNPI_MARKERS if m in blob)
        return _verdict("CONFIDENTIAL_MNPI", f"MNPI marker {hit!r}")
    if _flag(meta, "is_mnpi") is True:
        return _verdict("CONFIDENTIAL_MNPI", "declared is_mnpi=true")
    if _flag(meta, "requires_auth") is True or any(m in url for m in PRIVATE_MARKERS):
        hit = next((m for m in PRIVATE_MARKERS if m in url), "requires_auth=true")
        return _verdict("PRIVATE", f"authenticated or internal surface ({hit})")
    if _flag(meta, "is_private") is True:
        return _verdict("PRIVATE", "declared is_private=true")

    # ------------------------------------------- 2. the fetch refusal: catalogued, never fetched
    refusal = fetch_refusal_of(meta)
    if refusal:
        note = (f"FETCH REFUSED (LAWS 5e act 6, 2026-11-17): {refusal}; catalogued, never "
                "fetched")
        if _flag(meta, "paywalled") is True:
            note += "; paywalled"
        return _verdict("PUBLIC_WITH_TERMS", refusal,
                        reason=(f"registered, never scraped: {refusal}. The source is catalogued "
                                "from what the desk lawfully saw elsewhere (name, URL, a search "
                                "snippet) and the automated fetch is refused"),
                        terms_note=note, fetch_refusal=refusal)

    # ------------------------------------------------------------- 3. the permissive readings
    if obtained == "user_submission":
        return _verdict("USER_SUBMITTED", "obtained=user_submission")
    if _flag(meta, "is_open_data") is True or any(t in licence for t in OPEN_LICENCES):
        hit = next((t for t in OPEN_LICENCES if t in licence), "is_open_data=true")
        return _verdict("OPEN_DATA", f"open licence ({hit})")
    if obtained == "licensed_feed" or _flag(meta, "is_licensed") is True:
        return _verdict("LICENSED", f"licensed feed ({licence or 'licence unnamed'})")
    if obtained == "archive" or str(meta.get("source_class") or "") == "archive":
        return _verdict("PUBLIC_ARCHIVE", "public archive")

    # TERMS NOTES AND PAYWALLS THAT DO NOT REFUSE THE FETCH ARE LABELS, NOT BRAKES. A row whose
    # robots or terms refuse the automated fetch was caught in step 2 above; what reaches here is
    # lawfully fetchable, MINED AND TESTED IN FULL, and the label withholds only `redistribute`.
    notes: list[str] = []
    if _flag(meta, "paywalled") is True:
        # The open surface of a paywalled domain is mined; the wall itself is never bypassed
        # (hard boundary act 2), which is enforced by the DUMP_MARKERS branch above.
        notes.append("paywalled: the open surface is mined, the wall is never bypassed")
    if _flag(meta, "has_terms") is True or "terms of service" in blob or "terms of use" in blob:
        notes.append("declared terms present")
    if notes:
        note = "; ".join(notes)
        return _verdict("PUBLIC_WITH_TERMS", note,
                        reason=(f"{ROUTING['PUBLIC_WITH_TERMS']['reason']} [{note}]"),
                        terms_note=note)

    klass = str(meta.get("source_class") or "")
    if klass in ("retail_ecology", "app_ecosystem") or _flag(meta, "is_social") is True:
        return _verdict("PUBLIC_SOCIAL", f"source_class={klass or 'social'}")

    # --------------------------------------------------------- 4. unknown is a QUESTION, not a no
    if not url and not klass and obtained == "UNKNOWN":
        return _verdict("ACCESS_UNCLEAR",
                        "no url, no source class and no obtained-path: nothing identifies what "
                        "this is or how it was reached")
    if obtained in ("public_page", "api") or url.startswith(("http://", "https://")) or klass:
        return _verdict("PUBLIC", f"obtained={obtained}, source_class={klass or 'UNKNOWN'}")
    return _verdict("ACCESS_UNCLEAR", "access path unresolved")


# --------------------------------------------------------------------------- evidence objects

@dataclass(frozen=True)
class EvidenceObject:
    """One preserved claim, with its three INDEPENDENT labels and the weight they imply.

    PRESERVATION IS THE POINT. A fringe, contradicted or unreliable PUBLIC claim is kept with a
    lowered weight and a `narrative_feature` flag -- never dropped -- because its EXISTENCE is
    data about what other people believe, whatever its truth value.
    """

    source_id: str
    claim_text: str
    access_label: AccessLabel
    credibility: Credibility = "UNKNOWN"
    predictive_state: PredictiveState = "UNTESTED"
    evidence_weight: float = 0.0
    contradictions: tuple[str, ...] = ()
    narrative_feature: bool = False
    provenance: dict[str, Any] = field(default_factory=dict)

    def preserve(self) -> EvidenceObject:
        """Return this object as the desk KEEPS it: weight recomputed, never dropped.

        The three prohibited labels are the one exception, and even they are not deleted here --
        `route()` refuses them upstream with a recorded reason, and anything that reaches this
        method carries weight 0.0 and no alpha use.
        """
        cap = float(ROUTING[self.access_label]["evidence_weight_cap"])
        weight = min(cap, CREDIBILITY_WEIGHT.get(self.credibility, 0.4))
        # A claim that is doubted or contradicted is a NARRATIVE FEATURE: it stops being a fact
        # the desk believes and becomes a measurement of what the crowd is reading.
        narrative = bool(self.narrative_feature
                         or self.credibility in ("UNRELIABLE", "FRINGE", "CONTRADICTED")
                         or bool(self.contradictions))
        state: PredictiveState = self.predictive_state
        if state == "UNTESTED" and narrative and weight > 0.0:
            state = "NARRATIVE_FEATURE"
        return replace(self, evidence_weight=round(weight, 6), narrative_feature=narrative,
                       predictive_state=state)


@dataclass(frozen=True)
class RoutedEvidence:
    """The result of one walk down the five-stage pipeline."""

    stage: str
    verdict: AccessVerdict
    evidence: EvidenceObject | None
    researchable: bool
    why: str

    @property
    def dropped(self) -> bool:
        """True only when nothing at all was kept -- one of refused acts 1-5, or a row with
        no identity and no content at all."""
        return self.evidence is None


def route(source_meta: dict[str, Any], content_meta: dict[str, Any] | None = None
          ) -> RoutedEvidence:
    """DISCOVER -> CAPTURE METADATA -> LEGAL/ACCESS -> EVIDENCE -> RESEARCH, and which stage ruled.

    Never "looks risky -> discard", and no longer "unclear -> quarantine". There are exactly two
    outcomes: RESEARCHABLE with its labels attached, or refused with a named reason on one of
    acts 1-5 of the hard boundary. A fetch-refused row (act 6, robots / terms, 2026-11-17) is
    the first kind: researchable from its catalogue entry, with `verdict.fetch_allowed` False so
    no caller fetches it.
    """
    content = dict(content_meta or {})
    sid = str(source_meta.get("source_id") or source_meta.get("url") or
              source_meta.get("domain") or "")

    # STAGE 1/2: is there anything at all to classify?
    if not sid and not content.get("claim") and not content.get("text"):
        return RoutedEvidence(
            stage="CAPTURE_METADATA", verdict=_verdict("ACCESS_UNCLEAR", "empty row"),
            evidence=None, researchable=False,
            why="no source identity and no content: nothing was captured to classify")

    # STAGE 3: legal / access. The metadata of BOTH halves is read -- a clean domain hosting a
    # credential dump is the dump, not the domain.
    verdict = classify({**source_meta, **content})
    if verdict.refused:
        return RoutedEvidence(
            stage="LEGAL_ACCESS", verdict=verdict, evidence=None, researchable=False,
            why=f"REFUSED: {verdict.reason} [{verdict.basis}]")

    claim = str(content.get("claim") or content.get("text") or content.get("title") or "")
    cred_raw = str(content.get("credibility") or source_meta.get("credibility") or "")
    klass_raw = str(source_meta.get("source_class") or "")
    cred: Credibility = credibility_of(klass_raw, cred_raw)
    state_raw = str(content.get("predictive_state") or "UNTESTED")
    state: PredictiveState = _PREDICTIVE_BY_NAME.get(state_raw, "UNTESTED")
    contradictions = tuple(str(c) for c in (content.get("contradictions") or ()))

    obj = EvidenceObject(
        source_id=sid, claim_text=claim, access_label=verdict.access_label, credibility=cred,
        predictive_state=state, contradictions=contradictions,
        narrative_feature=bool(content.get("narrative_feature")),
        provenance={"basis": verdict.basis, "obtained": source_meta.get("obtained"),
                    "url": source_meta.get("url"),
                    "machine_use_allowed": verdict.machine_use_allowed,
                    "fetch_allowed": verdict.fetch_allowed,
                    "redistribute_allowed": verdict.redistribute_allowed,
                    "terms_note": verdict.terms_note},
    ).preserve()

    # STAGE 4/5: evidence classification, then research. EVERY row that cleared acts 1-5 is
    # RESEARCHABLE -- a low-credibility or unclear-access claim is researched at a lower weight,
    # which is the independence rule doing its job. There is no quarantine stage any more.
    return RoutedEvidence(
        stage="RESEARCH", verdict=verdict, evidence=obj,
        researchable=verdict.may("alpha_input") or verdict.may("narrative_feature"),
        why=(f"{verdict.access_label} x {obj.credibility} x {obj.predictive_state} -> weight "
             f"{obj.evidence_weight}"
             + (f"; {verdict.terms_note} (catalogued from what was lawfully seen elsewhere)"
                if not verdict.fetch_allowed
                else (f"; routing label: {verdict.terms_note} (redistribution withheld, mining "
                      "is not)" if verdict.terms_note else ""))))
