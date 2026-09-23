"""THE POPULATION ARCHIVE -- periodic snapshots of every accessible trading population, forever.

WHY A SNAPSHOT AND NOT A SCRAPE OF THE WINNERS. A leaderboard read once tells you who is up today.
Read every week and KEPT, the same page tells you how many systems there were, which ones stopped
being listed, how long a phenotype survives before it disappears, and what the survivors were
doing that the delisted ones were not. The first is a marketing page; the second is a prospective
cohort study that nobody else is running because nobody else keeps the losers. P(survive | phi)
cannot be computed from any winners-only table at any sample size -- the systems that would answer
it have already been removed from the page by the time anyone looks.

SO THE UNIT OF WORK IS THE WHOLE ACCESSIBLE POPULATION, not the top of it: winners, mediocre,
failed, removed, disappeared. Every capture is immutable and content-addressed under
`data/moat/raw_intel/archaeology/<platform>/<date>/`, every parsed row lands in
`data/archaeology/population.jsonl`, and NOTHING IS EVER DELETED. A row whose system vanished from
the platform is the most valuable row in the file.

WHAT IT REUSES. The desk has ONE http client (`deep_forest_miner._http`) and ONE immutable-capture
contract (`moat_collectors.write_capture`, O_EXCL, refuses to overwrite). This module calls
`moat_collectors.fetch_text` / `fetch_bytes` and mirrors the capture contract into the archaeology
layout; it adds no second crawler, no second set of manners and no second robots reader.

THE ACCESS BOUNDARY IS DECLARED, NOT ASSUMED. Every `Platform` carries `machine_use_allowed` in
{allowed, forbidden, unknown}. Only `allowed` is ever fetched -- `unknown` resolves to NOT FETCHED,
because the absence of a readable permission is not a permission, and `forbidden` is never fetched
at all. The desk's measured walls (`side_channels/seed_miners.SOURCE_WALLS`) are READ here rather
than restated, so a host the desk already found walled tightens this table automatically and one
ledger owns the boundary.

    python -c "from archaeology import snapshots; print(snapshots.summary())"
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parents[2]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research"), str(_DESK / "side_channels")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import deep_forest_miner as dfm  # noqa: E402  (the desk's ONE http client and its parsers)
import moat_collectors as mc  # noqa: E402  (the immutable-capture contract and the fetch doors)

UNMEASURED = mc.UNMEASURED

#: The population table. A module global so a test can point it at `tmp_path`; retention is
#: FOREVER and the file is append-only -- a rewrite would destroy the disappearances.
POPULATION: Path = _ROOT / "data" / "archaeology" / "population.jsonl"

#: Access verdicts -- PROVENANCE LABELS, not doors (LAWS 5e, 2026-09-23). `unknown` is not a
#: shrug and it is not a refusal either: it says no readable policy was found, and the ground is
#: mined with that fact attached. `may_fetch` is the door and it refuses the five acts only.
ALLOWED, FORBIDDEN, UNKNOWN = "allowed", "forbidden", "unknown"

#: What a record is worth before anything is inferred from it.
VERIFICATION: dict[str, float] = {
    "broker_verified": 0.90,      # the broker/regulated venue publishes the statement
    "platform_verified": 0.75,    # the platform publishes stats off a real account it hosts
    "audited_standings": 0.80,    # a competition organiser's own published standings
    "self_reported": 0.30,        # a product page, a forum post, a screenshot
    "hypothetical": 0.20,         # Collective2 states its own records may be hypothetical
    "code": 0.60,                 # source: no performance claim at all, which is honest
    "unverified": 0.15,
}
SNAPSHOT_FIELDS: tuple[str, ...] = ("snapshot_at", "platform", "system_id", "verification",
                                    "status")

#: THREE INDEPENDENT LABELS ON EVERY RECOVERED ITEM (principal, 2026-09-17). They are independent
#: because they answer different questions and a single "quality" field would let one answer hide
#: another: a FRINGE claim on an OPEN_DATA ground is usable-with-low-weight, an AUTHORITATIVE claim
#: on a PRIVATE ground is not usable at all, and neither fact says whether the claim PREDICTS.
#:
#: (1) ACCESS -- may the desk lawfully hold and use this at all, and what weight does its
#: provenance earn. PRIVATE, CONFIDENTIAL_MNPI and STOLEN_UNAUTHORIZED carry the five refused
#: ACTS: they are weight 0 and are never recorded, never fetched, never converted. EVERY OTHER
#: LABEL IS MINED AND TESTED. ACCESS_UNCLEAR sits at 1.00 because access has nothing to say about
#: truth -- credibility is the axis that weights a row, and pricing an unresolved access question
#: at zero was a quarantine wearing an evidence weight's clothes (LAWS 5e, 2026-09-23).
ACCESS_WEIGHT: dict[str, float] = {
    "PUBLIC": 1.00, "OPEN_DATA": 1.00, "PUBLIC_ARCHIVE": 0.95, "LICENSED": 0.90,
    "PUBLIC_WITH_TERMS": 0.85, "PUBLIC_SOCIAL": 0.70, "USER_SUBMITTED": 0.55,
    "ACCESS_UNCLEAR": 1.00, "PRIVATE": 0.0, "CONFIDENTIAL_MNPI": 0.0, "STOLEN_UNAUTHORIZED": 0.0,
}
ACCESS_LABELS: tuple[str, ...] = tuple(ACCESS_WEIGHT)
#: Never recorded, never fetched, never used -- there is no flag that turns this off.
ACCESS_REFUSED: frozenset[str] = frozenset({"PRIVATE", "CONFIDENTIAL_MNPI",
                                            "STOLEN_UNAUTHORIZED"})
#: EMPTY BY CONSTRUCTION. The access quarantine was deleted on 2026-09-23; the name stays so an
#: old reader finds an explicit empty set and a fence can assert it never refills.
ACCESS_QUARANTINE: frozenset[str] = frozenset()

#: (2) CREDIBILITY -- how much the SOURCE has earned. FRINGE and CONTRADICTED are LOW WEIGHT,
#: never zero and never discarded: material that looks false is an evidence object, and a desk
#: that throws it away can never later measure that it was right to doubt it (L1.25).
CREDIBILITY_WEIGHT: dict[str, float] = {
    "AUTHORITATIVE": 1.00, "RELIABLE": 0.75, "UNKNOWN": 0.40, "UNRELIABLE": 0.20,
    "FRINGE": 0.10, "CONTRADICTED": 0.05,
}
CREDIBILITY_LABELS: tuple[str, ...] = tuple(CREDIBILITY_WEIGHT)

#: (3) PREDICTIVE STATE -- what the GAUNTLET has said. Everything recovered here is UNTESTED; only
#: a judged cell may move it, and NARRATIVE_FEATURE is the honest resting place for a claim that
#: is useful as context and was never a prediction.
PREDICTIVE_STATES: tuple[str, ...] = ("UNTESTED", "PREDICTIVE", "NOT_PREDICTIVE",
                                      "NARRATIVE_FEATURE")

#: Access label by platform kind, overridden per platform where the desk knows better.
_ACCESS_BY_KIND: dict[str, str] = {
    "track_record": "PUBLIC_WITH_TERMS", "competition": "PUBLIC_ARCHIVE",
    "product": "PUBLIC_WITH_TERMS", "code": "LICENSED", "forum": "PUBLIC_SOCIAL",
    "institutional": "OPEN_DATA", "archive": "PUBLIC_ARCHIVE",
}
#: Credibility from the verification class -- the two are different questions with one answer here
#: because verification IS what a population's credibility is made of.
_CREDIBILITY_BY_VERIFICATION: dict[str, str] = {
    "broker_verified": "AUTHORITATIVE", "platform_verified": "RELIABLE",
    "audited_standings": "RELIABLE", "code": "RELIABLE", "self_reported": "UNRELIABLE",
    "hypothetical": "UNRELIABLE", "unverified": "UNKNOWN",
}


@dataclass(frozen=True)
class Platform:
    """One accessible population and the terms on which the desk may look at it."""

    name: str
    root: str
    kind: str                       # track_record|competition|product|code|forum|institutional
    machine_use_allowed: str
    verification_class: str
    observable_fields: tuple[str, ...]
    region: str = "global"
    language: str = "en"
    parser: str = "cards"
    family: str = "performance_archaeology"
    note: str = ""
    #: Empty means DERIVED (by kind / by verification class), never means unknown-and-ignored.
    access_label: str = ""
    credibility: str = ""

    @property
    def host(self) -> str:
        m = re.match(r"https?://([^/]+)", self.root)
        return (m.group(1) if m else "").lower()

    @property
    def access(self) -> str:
        return self.access_label or _ACCESS_BY_KIND.get(self.kind, "ACCESS_UNCLEAR")

    @property
    def credibility_label(self) -> str:
        return self.credibility or _CREDIBILITY_BY_VERIFICATION.get(self.verification_class,
                                                                    "UNKNOWN")


#: THE DECLARED POPULATIONS. `machine_use_allowed` is the desk's honest reading of the POLICY, and
#: since LAWS 5e (2026-09-23) it is a LABEL: a host measured as walled is `forbidden`, a host whose
#: policy cannot be read is `unknown`, and BOTH ARE MINED unless the reason names an access
#: control, a login, a paywall or an antibot challenge (`may_fetch`/`BOUNDARY_MARKERS`) -- because
#: reading those would mean defeating them. Regional equivalents are declared even where they are
#: unknown -- a population nobody has registered is one nobody can notice is missing (L1.28a).
PLATFORMS: tuple[Platform, ...] = (
    # ---- family 1: historical performance archaeology -----------------------------------
    Platform("mql5_signals", "https://www.mql5.com/en/signals", "track_record", ALLOWED,
             "platform_verified",
             ("growth", "months", "trades", "win_rate", "profit_factor", "max_drawdown",
              "subscribers", "algo_share", "symbols"),
             parser="cards", note="the desk already mines this ground (side_channels/mql5_*)"),
    Platform("ctrader_copy", "https://ct.spotware.com/copy", "track_record", UNKNOWN,
             "platform_verified", ("return", "drawdown", "fee", "aum", "months"),
             parser="json_rows", access_label="ACCESS_UNCLEAR",
             note="terms unread from this box: UNKNOWN is a label, the ground is mined, and an "
                  "unread licence is ACCESS_UNCLEAR -- mined and tested with that note"),
    Platform("myfxbook", "https://www.myfxbook.com/systems", "track_record", FORBIDDEN,
             "broker_verified", ("gain", "drawdown", "trades", "win_rate", "profit_factor"),
             parser="table", note="measured 2026-08-26: a managed challenge fronts the host; "
                                  "passing it would defeat an access control"),
    Platform("darwinex", "https://www.darwinex.com/darwins", "track_record", UNKNOWN,
             "broker_verified", ("return", "drawdown", "d_score", "risk", "months"),
             parser="json_rows", note="an authenticated API exists; no key on this box"),
    Platform("collective2", "https://collective2.com/leaderboard", "track_record", UNKNOWN,
             "hypothetical", ("return", "drawdown", "trades", "age_days", "subscribers"),
             parser="table",
             access_label="USER_SUBMITTED",
             note="robots PERMITS /leaderboard, the server answers 403 to this box (measured "
                  "2026-08-26): a server refusal, re-probed, never evaded. Collective2 states "
                  "its own records may be HYPOTHETICAL -- the verification class says so"),
    Platform("fxblue", "https://www.fxblue.com/users", "track_record", UNKNOWN, "broker_verified",
             ("growth", "drawdown", "trades", "win_rate", "symbols"), parser="table",
             note="the desk has an fxblue digest (scripts/fxblue_*) fed by hand, not a crawler"),
    Platform("dupliTrade", "https://www.duplitrade.com/strategies", "track_record", UNKNOWN,
             "platform_verified", ("return", "drawdown", "trades", "months"), parser="table",
             access_label="USER_SUBMITTED"),
    Platform("zulutrade", "https://www.zulutrade.com/traders", "track_record", UNKNOWN,
             "platform_verified", ("roi", "drawdown", "trades", "followers", "weeks"),
             parser="json_rows", access_label="USER_SUBMITTED"),
    Platform("naga", "https://naga.com/traders", "track_record", UNKNOWN, "platform_verified",
             ("return", "drawdown", "copiers", "months"), parser="json_rows",
             access_label="USER_SUBMITTED"),
    Platform("etoro", "https://www.etoro.com/people", "track_record", UNKNOWN,
             "platform_verified", ("gain", "drawdown", "copiers", "risk_score"),
             parser="json_rows", access_label="USER_SUBMITTED"),
    Platform("prop_leaderboards", "https://www.fundedtraderboards.example/leaderboard",
             "track_record", UNKNOWN, "self_reported",
             ("return", "drawdown", "days", "payout"), parser="table",
             access_label="ACCESS_UNCLEAR",
             note="prop-firm boards publish payouts, not statements: self-reported by class, and "
                  "the terms are unread -- mined with that label, never quarantined"),
    # ---- family 2: competition archaeology ----------------------------------------------
    Platform("world_cup_championship", "https://www.worldcupchampionships.com/standings",
             "competition", UNKNOWN, "audited_standings",
             ("rank", "return", "drawdown", "year", "division"), parser="standings",
             family="competition_archaeology"),
    Platform("qihuo_ribao_contest", "http://www.qhrb.com.cn/contest", "competition", UNKNOWN,
             "audited_standings", ("rank", "return", "drawdown", "year", "group"),
             parser="standings", region="cn", language="zh", family="competition_archaeology",
             note="期货日报实盘大赛 -- the standings archive the deep-forest mandate names"),
    Platform("lanhai_mijian", "http://www.lanhaimijian.example/rank", "competition", UNKNOWN,
             "audited_standings", ("rank", "return", "drawdown", "year"), parser="standings",
             region="cn", language="zh", family="competition_archaeology",
             access_label="ACCESS_UNCLEAR",
             note="蓝海密剑 -- named in the deep-forest standing order; terms unread"),
    Platform("kaggle_finance", "https://www.kaggle.com/competitions", "competition", UNKNOWN,
             "audited_standings", ("rank", "metric", "team", "year"), parser="json_rows",
             family="competition_archaeology",
             note="terms require the authenticated API for bulk access; none on this box"),
    Platform("quantconnect_alpha", "https://www.quantconnect.com/competitions", "competition",
             UNKNOWN, "audited_standings", ("rank", "return", "sharpe", "year"),
             parser="json_rows", family="competition_archaeology"),
    # ---- family 3/4: product and code archaeology ----------------------------------------
    Platform("mql5_market", "https://www.mql5.com/en/market/mt5", "product", ALLOWED,
             "self_reported",
             ("title", "price", "version", "updated", "reviews", "rating", "symbols",
              "timeframe", "parameters", "changelog"),
             parser="cards", family="product_archaeology"),
    Platform("mql5_codebase", "https://www.mql5.com/en/code", "code", ALLOWED, "code",
             ("title", "author", "published", "downloads", "rating", "category"),
             parser="cards", family="code_archaeology"),
    Platform("github_strategies", "https://api.github.com/search/repositories", "code", ALLOWED,
             "code", ("repo", "stars", "created", "pushed", "language", "archived", "topics"),
             parser="json_rows", family="code_archaeology",
             note="the desk already watches repositories (data/repo_watchlist.json)"),
    Platform("gitee_strategies", "https://gitee.com/api/v5/search/repositories", "code", ALLOWED,
             "code", ("repo", "stars", "created", "pushed", "language"), parser="json_rows",
             region="cn", language="zh", family="code_archaeology",
             note="the deep-forest miner already holds the Gitee route"),
    # ---- family 5: forum-era archaeology --------------------------------------------------
    Platform("forexfactory", "https://www.forexfactory.com/forum", "forum", ALLOWED,
             "self_reported", ("thread", "replies", "started", "last_post", "author"),
             parser="cards", family="forum_archaeology",
             note="the desk already mines this ground (side_channels/forexfactory_miner)"),
    Platform("mql5_forum", "https://www.mql5.com/en/forum", "forum", ALLOWED, "self_reported",
             ("thread", "replies", "started", "author"), parser="cards",
             family="forum_archaeology"),
    Platform("smartlab", "https://smart-lab.ru/algotrading", "forum", UNKNOWN, "self_reported",
             ("post", "author", "date", "comments"), parser="cards", region="ru", language="ru",
             family="forum_archaeology"),
    Platform("elitetrader", "https://www.elitetrader.com/et/forums", "forum", UNKNOWN,
             "self_reported", ("thread", "replies", "started"), parser="cards",
             family="forum_archaeology"),
    # ---- family 7: institutional archaeology ----------------------------------------------
    Platform("sec_edgar", "https://www.sec.gov/cgi-bin/browse-edgar", "institutional", ALLOWED,
             "broker_verified", ("filer", "form", "filed", "period"), parser="table",
             family="institutional_archaeology",
             note="public filings: lawfully observable FUNCTIONS only, never undisclosed "
                  "positions"),
    # ---- the archive of everything above, when the original is gone -----------------------
    Platform("wayback", "https://web.archive.org/web", "archive", ALLOWED, "unverified",
             ("url", "timestamp", "status"), parser="json_rows", family="forum_archaeology",
             note="the deep-forest miner already owns the wayback route"),
)
BY_NAME: dict[str, Platform] = {p.name: p for p in PLATFORMS}


# --------------------------------------------------------------------------- the archive layer
#: THE ELEVEN ARCHIVE KINDS, per region (principal, 2026-09-17). These are the grounds where the
#: record has already been lost once: the population that matters most is the one no live page
#: lists any more.
ARCHIVE_KINDS: tuple[str, ...] = (
    "dead_forums", "historical_pages", "broker_education_portals", "retired_ea_listings",
    "delisted_strategies", "old_research_blogs", "abandoned_code_repos",
    "archived_competition_results", "vanished_newsletters", "fund_failures",
    "public_performance_archives",
)
ARCHIVE_REGIONS: tuple[str, ...] = ("global", "us", "gb", "eu", "ru", "cn", "jp", "kr", "br", "tr")


@dataclass(frozen=True)
class Ground:
    """One named archive ground. A row with no `url` is a NAMED ABSENCE, which is a disposition:
    the desk knows the cell exists, knows it holds nothing yet, and says why."""

    region: str
    archive_kind: str
    name: str
    url: str = ""
    access_label: str = "PUBLIC_ARCHIVE"
    credibility: str = "UNKNOWN"
    note: str = ""


#: The grounds the desk can name TODAY. Everything else in region x kind comes out of
#: `archive_layer()` as an explicit NAMED ABSENCE -- 110 cells, and not one of them is allowed to
#: be a blank. "We have not looked there" and "there is nothing there" are different facts
#: (L1.28a), and only a named absence keeps them apart.
ARCHIVE_LAYER: tuple[Ground, ...] = (
    Ground("global", "historical_pages", "wayback_machine", "https://web.archive.org/web",
           note="the deep-forest miner already owns this route"),
    Ground("global", "abandoned_code_repos", "github_archived",
           "https://api.github.com/search/repositories", access_label="LICENSED",
           credibility="RELIABLE", note="archived:true is a first-class query, not an omission"),
    Ground("global", "retired_ea_listings", "mql5_market_retired",
           "https://www.mql5.com/en/market/mt5", access_label="PUBLIC_WITH_TERMS",
           credibility="UNRELIABLE", note="a delisted product is found by DIFF, not by listing"),
    Ground("global", "delisted_strategies", "mql5_signals_delisted",
           "https://www.mql5.com/en/signals", access_label="PUBLIC_WITH_TERMS",
           credibility="RELIABLE", note="the watchtower's disappearances ARE this ground"),
    Ground("global", "public_performance_archives", "archived_leaderboards",
           "https://web.archive.org/web", note="leaderboards as they stood, via the archive"),
    Ground("us", "dead_forums", "elitetrader_archive",
           "https://www.elitetrader.com/et/forums", access_label="ACCESS_UNCLEAR",
           note="terms unread: MINED with that label attached (LAWS 5e, 2026-09-23)"),
    Ground("us", "fund_failures", "sec_edgar_filings",
           "https://www.sec.gov/cgi-bin/browse-edgar", access_label="OPEN_DATA",
           credibility="AUTHORITATIVE",
           note="lawfully observable FUNCTIONS only, never undisclosed positions"),
    Ground("gb", "dead_forums", "forexfactory_old_threads",
           "https://www.forexfactory.com/forum", access_label="PUBLIC_SOCIAL",
           credibility="UNRELIABLE"),
    Ground("ru", "dead_forums", "smartlab_algotrading", "https://smart-lab.ru/algotrading",
           access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
           note="the RU failure vocabulary lives here"),
    Ground("cn", "archived_competition_results", "qihuo_ribao_standings",
           "http://www.qhrb.com.cn/contest", credibility="RELIABLE",
           note="期货日报实盘大赛, the standings archive the deep-forest mandate names"),
    Ground("cn", "old_research_blogs", "deep_forest_grounds", "",
           note="NAMED ABSENCE HERE ON PURPOSE: the CN blog forest is already worked by "
                "`research/deep_forest_miner.py` over its own grounds file. A second crawler "
                "would double the trial charge and halve the attention"),
    Ground("jp", "dead_forums", "jp_botter_archive", "", access_label="ACCESS_UNCLEAR",
           note="named, unlocated: the JP botter boards are reached by search index, not by a "
                "listing url this desk can hold"),
    Ground("kr", "dead_forums", "kr_algotrading_boards", "", access_label="ACCESS_UNCLEAR",
           note="robots on the main KR boards name this agent family (OP-041): a LABEL, not a "
                "refusal (LAWS 5e) -- the boards are mined; what is missing here is a listing "
                "url this desk can hold, which is why the archive cell is still owed"),
)


def archive_layer(regions: Sequence[str] = ARCHIVE_REGIONS,
                  kinds: Sequence[str] = ARCHIVE_KINDS) -> dict[str, Any]:
    """EVERY region x archive-kind cell as a NAMED GROUND or a NAMED ABSENCE -- never a blank.

    The absences are the product here, not the leftovers. A coverage table with holes in it reads
    as completeness to anybody who skims; a table where every hole says "no ground registered for
    <kind> in <region>: UNMEASURED, not empty" is the only shape that can be worked down.
    """
    have = {(g.region, g.archive_kind): g for g in ARCHIVE_LAYER}
    cells: list[dict[str, Any]] = []
    for region in regions:
        for kind in kinds:
            g = have.get((region, kind))
            if g is not None and g.url:
                cells.append({"region": region, "archive_kind": kind, "state": "GROUND",
                              "name": g.name, "url": g.url, "access_label": g.access_label,
                              "credibility": g.credibility, "note": g.note,
                              "quarantined": g.access_label in ACCESS_QUARANTINE})
            elif g is not None:
                cells.append({"region": region, "archive_kind": kind, "state": "NAMED_ABSENCE",
                              "name": g.name, "url": "", "access_label": g.access_label,
                              "credibility": g.credibility, "note": g.note})
            else:
                cells.append({"region": region, "archive_kind": kind, "state": "NAMED_ABSENCE",
                              "name": "", "url": "",
                              "note": f"no archive ground registered for {kind} in {region}: "
                                      "UNMEASURED, not empty -- the cell is owed"})
    grounds = [c for c in cells if c["state"] == "GROUND"]
    return {"n_cells": len(cells), "n_grounds": len(grounds),
            "n_absences": len(cells) - len(grounds),
            "n_quarantined": sum(1 for c in grounds if c.get("quarantined")),
            "kinds": list(kinds), "regions": list(regions), "cells": cells,
            "by_region": {r: sum(1 for c in grounds if c["region"] == r) for r in regions},
            "rule": "every region x archive-kind cell is a named ground or a named absence; a "
                    "blank cell would be indistinguishable from a searched one"}


# --------------------------------------------------------------------------- store primitives
def now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def today() -> str:
    return datetime.now(tz=UTC).strftime("%Y-%m-%d")


def archive_root() -> Path:
    """Derived from `moat_collectors.MOAT` AT CALL TIME, so a test that points the moat at
    `tmp_path` moves this archive with it and no second root has to be monkeypatched."""
    return mc.MOAT / "raw_intel" / "archaeology"


def _slug(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", str(name or "platform")).strip("._-")[:48]
    return safe or "platform"


def capture(platform_name: str, data: bytes, ext: str = "html", *, at: str = "") -> tuple[
        Path, str, bool]:
    """Land one raw capture under `<archive>/<platform>/<date>/<sha256>.<ext>`. (path, sha, new).

    THE SAME WRITE-ONCE CONTRACT AS THE MOAT'S OWN STORE, and deliberately not a second opinion
    about it: content-addressed, opened O_EXCL, and a path that already holds DIFFERENT bytes
    raises `moat_collectors.ImmutableCaptureError` rather than being repaired. An archive with a
    repair path is a cache; the whole point of keeping the population is that a page which
    changed under the desk cannot change what the desk recorded.
    """
    sha = hashlib.sha256(data).hexdigest()
    target = (archive_root() / _slug(platform_name) / (at or today())
              / f"{sha}.{str(ext).lstrip('.') or 'bin'}")
    target.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
    try:
        fd = os.open(target, flags)
    except FileExistsError:
        existing = target.read_bytes()
        if existing == data:
            return target, sha, False
        raise mc.ImmutableCaptureError(
            f"{target} already holds {len(existing)} bytes that are not the {len(data)} bytes "
            "offered; an archaeology capture is never overwritten") from None
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    return target, sha, True


def append_population(rows: Sequence[Mapping[str, Any]]) -> int:
    """Append-only, one JSON row per line. RETENTION IS FOREVER: this file is never rewritten,
    never compacted and never pruned, because the rows that matter most are the ones whose
    systems no longer exist anywhere else."""
    if not rows:
        return 0
    POPULATION.parent.mkdir(parents=True, exist_ok=True)
    with POPULATION.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(dict(row), sort_keys=True, default=str) + "\n")
    return len(rows)


def load_population(platform: str = "", at: str = "", path: Path | None = None
                    ) -> list[dict[str, Any]]:
    p = path or POPULATION
    if not p.exists():
        return []
    out: list[dict[str, Any]] = []
    with p.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if not isinstance(row, dict):
                continue
            if platform and str(row.get("platform")) != platform:
                continue
            if at and str(row.get("snapshot_at")) != at:
                continue
            out.append(row)
    return out


def snapshot_dates(platform: str = "", path: Path | None = None) -> list[str]:
    return sorted({str(r.get("snapshot_at") or "") for r in load_population(platform, path=path)
                   if r.get("snapshot_at")})


# --------------------------------------------------------------------------- the access boundary
def _walls() -> dict[str, dict[str, Any]]:
    """The desk's MEASURED walls, read rather than restated. Unimportable -> empty, which does not
    loosen anything: the platform table's own verdicts still stand."""
    try:
        from seed_miners import SOURCE_WALLS
    except Exception:
        return {}
    return {str(v.get("host") or "").lower(): dict(v) for v in SOURCE_WALLS.values()
            if isinstance(v, dict)}


#: Strictness order. `machine_use` takes the MAXIMUM of everything it knows, which is what makes
#: the word "tightened" true: a wall may never loosen a declared refusal, and a declaration may
#: never loosen a measured one.
_STRICTNESS: dict[str, int] = {ALLOWED: 0, UNKNOWN: 1, FORBIDDEN: 2}


def machine_use(p: Platform) -> tuple[str, str]:
    """(verdict, why) -- the DECLARED verdict, TIGHTENED by anything the desk has measured.

    THIS IS A LABEL FUNCTION, NOT A DOOR (LAWS 5e, 2026-09-23). `may_fetch` is the door and it
    refuses only the five acts. What this computes is the provenance note that travels with the
    row: `allowed`, `unknown` (no readable policy) or `forbidden` (a declared or measured wall).

    Tightening is a max, not a replacement, and the difference is not pedantry: myfxbook is
    declared `forbidden` here (a managed challenge fronts the host; passing it would defeat an
    access control) and the desk's wall ledger records it as ANTIBOT_CHALLENGE, which on its own
    maps to `unknown`. Letting the wall REPLACE the declaration would have turned a refusal into
    a maybe -- and myfxbook is exactly the row the hard boundary still refuses, so the ordering
    still matters.
    """
    declared = str(p.machine_use_allowed or UNKNOWN).lower()
    reasons: list[tuple[str, str]] = []
    if declared not in _STRICTNESS:
        reasons.append((UNKNOWN, f"platform declares an unknown access verdict {declared!r}"))
    elif declared == ALLOWED:
        reasons.append((ALLOWED, "declared allowed and no measured wall on this host"))
    elif declared == FORBIDDEN:
        reasons.append((FORBIDDEN, p.note or "declared forbidden in the platform table"))
    else:
        reasons.append((UNKNOWN, p.note or "no readable policy for automated extraction; "
                                           "UNKNOWN is a LABEL and the ground is mined "
                                           "(LAWS 5e, 2026-09-23)"))
    wall = _walls().get(p.host)
    if wall is not None:
        verdict = str(wall.get("verdict") or "")
        reasons.append((FORBIDDEN if verdict == "ROBOTS_DISALLOW" else UNKNOWN,
                        f"desk-measured wall {verdict} on {p.host}: "
                        f"{str(wall.get('evidence') or '')[:200]}"))
    barred = mc.robots_barred(p.root)
    if barred:
        reasons.append((FORBIDDEN, barred))
    strictest = max(_STRICTNESS[v] for v, _ in reasons)
    why = "; ".join(w for v, w in reasons if _STRICTNESS[v] == strictest)
    return next(v for v, _ in reasons if _STRICTNESS[v] == strictest), why


#: Tokens in a verdict's reason that name one of the five refused ACTS: something the desk would
#: have to DEFEAT to read the page -- an access control, a login, a paywall, a credential, an
#: antibot challenge. THIS LIST IS THE WHOLE REFUSAL. A robots Disallow, an unreadable policy and
#: an unread terms page are none of these; they are labels (LAWS 5e, 2026-09-23).
BOUNDARY_MARKERS: tuple[str, ...] = (
    "access control", "antibot", "anti-bot", "challenge", "captcha", "login", "sign in",
    "signin", "paywall", "credential", "authenticated", "subscription required",
)


def boundary_hit(why: str) -> str:
    """The hard-boundary marker this reason names, or "" when it names none."""
    low = str(why or "").lower()
    return next((m for m in BOUNDARY_MARKERS if m in low), "")


def may_fetch(p: Platform, *, probe: bool = False) -> tuple[bool, str]:
    """IS THIS PLATFORM FETCHED? Yes, unless its reason names one of the five refused acts.

    LAWS 5e (2026-09-23): this used to fetch ONLY `allowed`, so a robots Disallow, an unread
    terms page and an unreadable policy all resolved to NOT FETCHED -- three discovery brakes,
    and `unknown` was the biggest of them because absence of a readable policy is not a
    prohibition. They are deleted: `machine_use()` still computes the verdict, it is returned as
    a LABEL, and only an access control, a login, a paywall or an antibot challenge refuses --
    because reading those would mean defeating them (hard-boundary acts 1 and 2).
    """
    verdict, why = machine_use(p)
    hit = boundary_hit(f"{why} {p.note}")
    if hit:
        return False, (f"REFUSED on the hard boundary ({hit}): reading this would mean defeating "
                       f"an access control -- {why}")
    label = f"{verdict}: {why}" if verdict != ALLOWED else why
    if probe and mc.robots_still_disallows(p.host):
        label = (f"{label}; live robots probe: {p.host}/robots.txt names this agent -- RECORDED "
                 f"AS A LABEL and fetched anyway (LAWS 5e)")
    return True, label


# --------------------------------------------------------------------------- the parsers
_NUM = r"[-+]?\d[\d\s,]*\.?\d*"
#: An anchor, its attributes in ANY order. Matching href-before-class was a layout assumption, and
#: a layout assumption in a parser is a silent zero the day the platform reorders its attributes.
_ANCHOR = re.compile(r'(?is)<a\s([^>]*)>(.*?)</a>')
_HREF = re.compile(r'(?is)(?:^|\s)href=["\']([^"\']+)["\']')
_CLASS = re.compile(r'(?is)(?:^|\s)class=["\']([^"\']*)["\']')
_CARD_CLASS = re.compile(r"(?i)card|signal|product|topic|thread|strategy|trader|repo")
_ROW = re.compile(r"(?is)<tr[^>]*>(.*?)</tr>")
_CELL = re.compile(r"(?is)<t[dh][^>]*>(.*?)</t[dh]>")


def _f(text: Any) -> float | None:
    """A number out of whatever the page wrote, or None. None is UNMEASURED, never 0.0."""
    if isinstance(text, (int, float)) and not isinstance(text, bool):
        return float(text)
    m = re.search(_NUM, str(text or ""))
    if m is None:
        return None
    try:
        return float(m.group(0).replace(" ", "").replace(",", ""))
    except ValueError:
        return None


def parse_cards(page: str, p: Platform) -> list[dict[str, Any]]:
    """A listing of linked cards (MQL5 signals/market/code, a forum index). The id is the link's
    own numeric or slug tail, so the same system keeps its identity across snapshots."""
    rows: list[dict[str, Any]] = []
    for attrs, inner in _ANCHOR.findall(page or ""):
        hm, cm = _HREF.search(attrs), _CLASS.search(attrs)
        if hm is None or cm is None or not _CARD_CLASS.search(cm.group(1)):
            continue
        href = hm.group(1)
        text = dfm.html_text(inner)
        if not text:
            continue
        sid = re.sub(r"[^A-Za-z0-9_-]+", "-", href.rstrip("/").split("/")[-1])[:80]
        stats = _labelled_numbers(text)
        rows.append({"system_id": sid or hashlib.sha1(href.encode()).hexdigest()[:12],
                     "url": href, "name": text[:160], "stats": stats})
    return rows


def parse_table(page: str, p: Platform) -> list[dict[str, Any]]:
    """An HTML table whose first row is the header. Columns are matched to the platform's own
    `observable_fields`, so a layout change drops a column instead of silently shifting them."""
    trs = _ROW.findall(page or "")
    if not trs:
        return []
    header = [dfm.html_text(c).strip().lower() for c in _CELL.findall(trs[0])]
    idx = {f: i for i, h in enumerate(header) for f in p.observable_fields
           if f.replace("_", " ") in h or h in f}
    out: list[dict[str, Any]] = []
    for tr in trs[1:]:
        cells = [dfm.html_text(c).strip() for c in _CELL.findall(tr)]
        if not cells:
            continue
        name = cells[0]
        href = re.search(r'(?is)href="([^"]+)"', tr)
        stats = {f: _f(cells[i]) for f, i in idx.items() if i < len(cells)}
        sid = re.sub(r"[^A-Za-z0-9_-]+", "-", (href.group(1).rstrip("/").split("/")[-1]
                                               if href else name))[:80]
        out.append({"system_id": sid or name[:80], "url": href.group(1) if href else "",
                    "name": name[:160], "stats": {k: v for k, v in stats.items()
                                                  if v is not None}})
    return out


def parse_standings(page: str, p: Platform) -> list[dict[str, Any]]:
    """Competition standings. Same table shape, but the row carries a RANK and a YEAR, and the
    verification class already says these are the organiser's numbers, not the desk's."""
    rows = parse_table(page, p)
    year = _f(re.search(r"(20\d\d)", page or "").group(1)) if re.search(r"20\d\d", page or "") \
        else None
    for i, r in enumerate(rows, start=1):
        r["stats"].setdefault("rank", float(i))
        if year is not None:
            r["stats"].setdefault("year", year)
    return rows


def parse_json_rows(page: str, p: Platform) -> list[dict[str, Any]]:
    """A JSON listing: a top-level list, or the first list-valued key of an object."""
    try:
        doc = json.loads(page)
    except ValueError:
        return []
    items: Any = doc
    if isinstance(doc, Mapping):
        for key in ("items", "results", "data", "rows", "traders", "strategies", "systems"):
            if isinstance(doc.get(key), list):
                items = doc[key]
                break
        else:
            items = next((v for v in doc.values() if isinstance(v, list)), [])
    out: list[dict[str, Any]] = []
    for it in items if isinstance(items, list) else []:
        if not isinstance(it, Mapping):
            continue
        sid = str(it.get("id") or it.get("system_id") or it.get("full_name") or it.get("name")
                  or it.get("login") or "")[:80]
        if not sid:
            continue
        stats = {f: _f(it.get(f)) for f in p.observable_fields if it.get(f) is not None}
        out.append({"system_id": re.sub(r"[^A-Za-z0-9_./-]+", "-", sid),
                    "url": str(it.get("url") or it.get("html_url") or ""),
                    "name": str(it.get("name") or it.get("full_name") or sid)[:160],
                    "raw": {k: it.get(k) for k in p.observable_fields if k in it},
                    "stats": {k: v for k, v in stats.items() if v is not None}})
    return out


_LABEL = re.compile(r"(?i)\b(growth|gain|return|roi|profit factor|win rate|drawdown|dd|trades|"
                    r"months|weeks|subscribers|copiers|followers|sharpe|rank|price|downloads|"
                    r"rating|replies)\b[^0-9+-]{0,12}(" + _NUM + r")\s*%?")
_LABEL_KEY = {"gain": "growth", "return": "growth", "roi": "growth", "dd": "drawdown",
              "profit factor": "profit_factor", "win rate": "win_rate"}


def _labelled_numbers(text: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for label, num in _LABEL.findall(text or ""):
        key = _LABEL_KEY.get(label.lower(), label.lower().replace(" ", "_"))
        value = _f(num)
        if value is not None:
            out.setdefault(key, value)
    return out


PARSERS = {"cards": parse_cards, "table": parse_table, "standings": parse_standings,
           "json_rows": parse_json_rows}


# --------------------------------------------------------------------------- the three labels
def labels(access: str, credibility: str, *, predictive: str = "UNTESTED") -> dict[str, Any]:
    """THE THREE INDEPENDENT LABELS and the evidence weight they imply.

    `usable` is the one bit downstream reads, and it is deliberately NOT a function of
    credibility: fringe, contradictory and false-looking public material stays usable at low
    weight, because it is evidence about what the world believes and discarding it destroys the
    only record that the desk was right to doubt it. The ONLY thing that makes a row unusable is
    one of the five refused ACTS -- a private, confidential or unauthorised ground. An UNCLEAR
    access path is usable at full weight with the label attached: the quarantine was deleted on
    2026-09-23 (LAWS 5e).
    """
    a = str(access or "ACCESS_UNCLEAR").upper()
    c = str(credibility or "UNKNOWN").upper()
    pstate = str(predictive or "UNTESTED").upper()
    if a not in ACCESS_WEIGHT:
        a = "ACCESS_UNCLEAR"
    if c not in CREDIBILITY_WEIGHT:
        c = "UNKNOWN"
    if pstate not in PREDICTIVE_STATES:
        pstate = "UNTESTED"
    refused, quarantined = a in ACCESS_REFUSED, a in ACCESS_QUARANTINE
    return {"access_label": a, "credibility": c, "predictive_state": pstate,
            "evidence_weight": round(ACCESS_WEIGHT[a] * CREDIBILITY_WEIGHT[c], 6),
            "refused": refused,
            # ALWAYS FALSE since 2026-09-23; the key stays for old readers of the artifact.
            "quarantined": quarantined,
            "usable": not refused,
            "terms_note": ("access path unresolved: mined and tested with the label attached"
                           if a == "ACCESS_UNCLEAR" else ""),
            "why": ("private, confidential or unauthorised material is never recorded and never "
                    "used (one of the five refused acts)" if refused else
                    "ACCESS_UNCLEAR: MINED AND TESTED with the label attached; the quarantine "
                    "was deleted on 2026-09-23" if a == "ACCESS_UNCLEAR" else
                    "usable; credibility sets the weight, never the admission")}


# --------------------------------------------------------------------------- the snapshot
def normalise(p: Platform, raw: Mapping[str, Any], at: str, sha: str = "") -> dict[str, Any]:
    """One population row. `status` is what the LISTING says -- present is `listed`; a
    disappearance is not knowable from one snapshot and is produced by `diff`, never guessed.

    Every row carries the THREE LABELS, because a row that reaches the decompiler without them is
    a row whose licence, credibility and test state are decided by whoever reads it next.
    """
    stats = {k: v for k, v in (raw.get("stats") or {}).items()
             if isinstance(v, (int, float)) and not isinstance(v, bool)}
    lab = labels(str(raw.get("access_label") or p.access),
                 str(raw.get("credibility") or p.credibility_label))
    return {"snapshot_at": at, "platform": p.name, "system_id": str(raw.get("system_id") or ""),
            "url": str(raw.get("url") or ""), "name": str(raw.get("name") or "")[:160],
            "kind": p.kind, "family": p.family, "region": p.region, "language": p.language,
            "verification": p.verification_class,
            "verification_prior": VERIFICATION.get(p.verification_class, 0.15),
            "status": str(raw.get("status") or "listed"), "stats": stats,
            "observed": sorted(stats), "capture_sha": sha, **lab,
            "raw": raw.get("raw") if isinstance(raw.get("raw"), Mapping) else None}


def snapshot(platform: Platform | str, budget_s: float = 60.0, *, fetch: bool = True,
             pages: Sequence[tuple[str, str]] | None = None, at: str = "",
             write: bool = True, probe: bool = False) -> dict[str, Any]:
    """One periodic snapshot of one platform's whole accessible population.

    `pages` is the --no-fetch door: a sequence of (url, body) the caller already holds, used
    verbatim so a test (or a replay off the archive) exercises exactly the parse path a fetch
    would. With `fetch=False` and no pages, the pass records an UNMEASURED reason and writes
    nothing -- an empty population is never reported as a population of zero.
    """
    p = platform if isinstance(platform, Platform) else BY_NAME[str(platform)]
    stamp = at or today()
    started = time.monotonic()
    out: dict[str, Any] = {"platform": p.name, "snapshot_at": stamp, "kind": p.kind,
                           "family": p.family, "verification": p.verification_class,
                           "rows": [], "captures": [], "captures_new": 0,
                           "captures_duplicate": 0, "fetched": 0, "refused": "",
                           "refused_rows": 0, "quarantined_rows": 0,
                           "access_label": p.access, "credibility": p.credibility_label,
                           "unmeasured": [], "seconds": 0.0}
    allowed, why = may_fetch(p, probe=probe)
    out["machine_use_allowed"], out["access_why"] = machine_use(p)
    bodies: list[tuple[str, str]] = list(pages or [])
    if not bodies:
        if not fetch:
            out["unmeasured"].append(f"{p.name}: --no-fetch and no fixture supplied; this "
                                     "platform's population is UNMEASURED this pass, not empty")
            out["seconds"] = round(time.monotonic() - started, 3)
            return out
        if not allowed:
            out["refused"] = why
            out["unmeasured"].append(f"{p.name}: {why}")
            out["seconds"] = round(time.monotonic() - started, 3)
            return out
        body, status, err = mc.fetch_text(p.root, p.language)
        out["fetched"] = 1
        if not body:
            out["unmeasured"].append(f"{p.name}: fetch returned nothing (status {status}"
                                     f"{', ' + err if err else ''})")
            out["seconds"] = round(time.monotonic() - started, 3)
            return out
        bodies = [(p.root, body)]
    parser = PARSERS.get(p.parser, parse_cards)
    rows: list[dict[str, Any]] = []
    for url, body in bodies:
        if budget_s and (time.monotonic() - started) > budget_s:
            out["unmeasured"].append(f"{p.name}: budget {budget_s}s spent with pages unread; "
                                     "the remainder of the population is owed, not absent")
            break
        ext = "json" if p.parser == "json_rows" else "html"
        try:
            _path, sha, created = capture(p.name, body.encode("utf-8", "replace"), ext, at=stamp)
        except mc.ImmutableCaptureError as exc:
            out["unmeasured"].append(f"{p.name}: {exc}")
            continue
        out["captures"].append(sha)
        out["captures_new" if created else "captures_duplicate"] += 1
        for raw in parser(body, p):
            row = normalise(p, raw, stamp, sha)
            if not row["system_id"]:
                continue
            if row["refused"]:
                # Private, confidential or unauthorised material is not recorded AT ALL -- not
                # even as a labelled stub, because a stub is still a copy of something the desk
                # may not hold. Only the count leaves this loop.
                out["refused_rows"] += 1
                continue
            row["source_url"] = url
            out["quarantined_rows"] += int(bool(row["quarantined"]))
            rows.append(row)
    seen: set[str] = set()
    deduped = []
    for r in rows:
        if r["system_id"] in seen:
            continue
        seen.add(r["system_id"])
        deduped.append(r)
    out["rows"] = deduped
    out["n"] = len(deduped)
    # THE BODIES THIS PASS ACTUALLY READ, so the caller can walk their links without fetching them
    # a second time. Not part of any report -- a page is evidence, and evidence lives in the
    # immutable capture, not in a JSON summary.
    out["bodies"] = [(u, b[:200_000]) for u, b in bodies]
    if write and deduped:
        append_population(deduped)
    out["seconds"] = round(time.monotonic() - started, 3)
    return out


# --------------------------------------------------------------------------- the watchtower
_TRACKED = ("growth", "return", "drawdown", "trades", "subscribers", "win_rate", "profit_factor",
            "rank", "months", "stars", "status")


def diff(prev: Iterable[Mapping[str, Any]], cur: Iterable[Mapping[str, Any]],
         *, tracked: Sequence[str] = _TRACKED) -> dict[str, Any]:
    """THE WATCHTOWER. Two snapshots of one population -> what appeared, what DISAPPEARED, and
    what changed state in between.

    A disappearance is the single most informative event this module can record and the only one
    that is invisible to anybody reading the page today: it is the numerator of P(survive | phi)
    and the reason the archive keeps the losers. It is reported as an event, never written back
    over the earlier row -- the row that said `listed` on the day it said it stays true forever.
    """
    a = {str(r.get("system_id")): dict(r) for r in prev if r.get("system_id")}
    b = {str(r.get("system_id")): dict(r) for r in cur if r.get("system_id")}
    appeared = sorted(set(b) - set(a))
    disappeared = sorted(set(a) - set(b))
    changed: list[dict[str, Any]] = []
    for sid in sorted(set(a) & set(b)):
        sa, sb = a[sid].get("stats") or {}, b[sid].get("stats") or {}
        deltas = {}
        for f in tracked:
            va, vb = sa.get(f), sb.get(f)
            if isinstance(va, (int, float)) and isinstance(vb, (int, float)) and va != vb:
                deltas[f] = {"from": va, "to": vb, "delta": round(float(vb) - float(va), 6)}
        if str(a[sid].get("status")) != str(b[sid].get("status")):
            deltas["status"] = {"from": a[sid].get("status"), "to": b[sid].get("status")}
        if deltas:
            changed.append({"system_id": sid, "deltas": deltas})
    prev_at = next((str(r.get("snapshot_at")) for r in a.values()), UNMEASURED)
    cur_at = next((str(r.get("snapshot_at")) for r in b.values()), UNMEASURED)
    n_prev = len(a)
    return {"prev_at": prev_at, "cur_at": cur_at, "n_prev": n_prev, "n_cur": len(b),
            "appeared": appeared, "disappeared": disappeared, "changed": changed,
            "n_appeared": len(appeared), "n_disappeared": len(disappeared),
            "n_changed": len(changed),
            "disappearance_rate": (None if n_prev == 0 else round(len(disappeared) / n_prev, 6)),
            "disappeared_rows": [a[s] for s in disappeared],
            "rule": "a disappearance is a measurement, never a gap; the earlier row is never "
                    "rewritten"}


def watchtower(platform: str, path: Path | None = None) -> dict[str, Any]:
    """`diff` between the two most recent snapshots of one platform, from the population file."""
    dates = snapshot_dates(platform, path=path)
    if len(dates) < 2:
        return {"platform": platform, "status": UNMEASURED,
                "why": f"{len(dates)} snapshot(s) on file: a disappearance needs two, and one "
                       "snapshot is a listing, not a cohort"}
    prev = load_population(platform, dates[-2], path=path)
    cur = load_population(platform, dates[-1], path=path)
    return {"platform": platform, **diff(prev, cur)}


def summary(path: Path | None = None) -> dict[str, Any]:
    """What the archive holds right now: platforms, access verdicts, snapshots, population."""
    rows = load_population(path=path)
    by_platform: dict[str, dict[str, Any]] = {}
    for r in rows:
        d = by_platform.setdefault(str(r.get("platform")), {"n": 0, "snapshots": set()})
        d["n"] += 1
        d["snapshots"].add(str(r.get("snapshot_at")))
    for d in by_platform.values():
        d["snapshots"] = sorted(d["snapshots"])
    verdicts = {p.name: machine_use(p)[0] for p in PLATFORMS}
    census: dict[str, dict[str, int]] = {"access_label": {}, "credibility": {},
                                         "predictive_state": {}}
    for r in rows:
        for axis in census:
            key = str(r.get(axis) or UNMEASURED)
            census[axis][key] = census[axis].get(key, 0) + 1
    return {"at": now(), "archive_root": str(archive_root()), "population": str(POPULATION),
            "n_platforms": len(PLATFORMS), "n_rows": len(rows),
            "fetchable": sorted(k for k, v in verdicts.items() if v == ALLOWED),
            # NOT a refusal list any more: these carry a `forbidden` or `unknown` POLICY LABEL and
            # are mined unless `may_fetch` finds a hard-boundary marker (LAWS 5e, 2026-09-23).
            "policy_labelled": sorted(k for k, v in verdicts.items() if v != ALLOWED),
            "never_fetched": sorted(k for k, v in verdicts.items()
                                    if not may_fetch(BY_NAME[k])[0]),
            "access_verdicts": verdicts, "by_platform": by_platform,
            "labels": census,
            "n_quarantined": sum(1 for r in rows if r.get("quarantined")),
            "archive_layer": {k: v for k, v in archive_layer().items() if k != "cells"},
            "rule": "the whole accessible population, winners and graveyards alike; a forbidden "
                    "or unknown policy is a LABEL and the ground is mined, only an access "
                    "control refuses; retention is forever"}


def platforms_of(family: str = "", kind: str = "") -> list[Platform]:
    return [p for p in PLATFORMS if (not family or p.family == family)
            and (not kind or p.kind == kind)]


def as_rows() -> list[dict[str, Any]]:
    """The platform table as plain rows, for the report."""
    out = []
    for p in PLATFORMS:
        verdict, why = machine_use(p)
        lab = labels(p.access, p.credibility_label)
        out.append({**asdict(p), "host": p.host, "machine_use_allowed": verdict,
                    "access_why": why[:240], **lab,
                    "verification_prior": VERIFICATION.get(p.verification_class, 0.15)})
    return out
