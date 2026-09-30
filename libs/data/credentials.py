"""EVERY ENVIRONMENT CREDENTIAL THE DESK CAN USE: which provider, which fetcher reads it, under
which NAME, which legs and families it feeds, and whether it is set on this host.

WHY A REGISTRY OF NAMES (2026-09-30). The principal is registering free API keys on the Windows
trading box with `setx`. A key set under a name no reader looks for is a key that unlocks nothing,
silently, and six lanes built readers for these keys on six branches with no shared list of names.
Measured the day this was written: the EDGAR User-Agent is read as `QUANT_EDGAR_UA` on live and in
two lanes, as `SEC_EDGAR_UA` in the disclosure lane, and the principal's instruction names
`SEC_EDGAR_USER_AGENT`; the LLM seat's `deepseek_cycle` reads only `OPENROUTER_API_KEY` while
`llm_seat` accepts four names. This module is the one place those names are written down, and
`desks/mt5/research/credential_coverage.py` turns it into an hourly artifact.

THE STATUS OF A VARIABLE, per host, from presence ONLY:

    SET              present under a name every registered consumer reads
    MISMATCHED_NAME  present, but under a name at least one registered consumer does NOT read --
                     that consumer is still dark and the fix is a rename, not a signup
    BLOCKED_AUTH     absent under every accepted name and every secrets-file key name

NO VALUE IS EVER READ HERE. `os.environ` is consulted with `in` and for a non-empty test; a
secrets file is parsed and only its KEY NAMES are kept (the parsed values are dropped inside the
reader and never returned, logged or written). Nothing in this module returns a string derived
from a credential's value -- not a prefix, not a length, not a hash. A fetcher that needs the
value reads it itself, through `accepted_names()`, and puts it only in its own request.

THE ESTIMATE IS AN ESTIMATE. `Estimate.cells_per_day` is arithmetic on declared quantities (series
x mapped symbols x cells per pair, bounded by the consumer's per-pass donation cap x 24 passes),
labelled as such everywhere it is shown. The measured number is the consumer's own donation files,
which the coverage leg reads; the estimate only ranks keys nobody has set yet.
"""
from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
#: The two secrets directories the desk uses. Neither is ever committed (`data/secrets/**` never
#: leaves the box); a file here is read for its key NAMES only.
SECRETS_DIRS: tuple[Path, ...] = (ROOT / "data" / "secrets", DESK / "data" / "secrets")

SET = "SET"
MISMATCHED_NAME = "MISMATCHED_NAME"
BLOCKED_AUTH = "BLOCKED_AUTH"
UNMEASURED = "UNMEASURED"
STATUSES = (SET, MISMATCHED_NAME, BLOCKED_AUTH)

#: Status words other lanes use for "the key is absent", all of which ARE BLOCKED_AUTH. The
#: coverage report maps them so one vocabulary reaches the principal.
BLOCKED_SYNONYMS: frozenset[str] = frozenset({
    "BLOCKED_NO_KEY", "NEEDS_CREDENTIAL", "BLOCKED_ON_KEY", "DARK", "NO_KEY", "BLOCKED_AUTH"})

LIVE = "live"


@dataclass(frozen=True)
class Consumer:
    """One reader of a credential.

    `reads` lists every NAME this reader accepts -- environment names bare, secrets-file keys as
    `file:<relative path>#<key>`. A consumer whose `reads` lacks the name the principal set is the
    MISMATCHED_NAME case. `branch` is where the reader lives (`live`, or the unmerged branch and
    PR); `seats` are the `data/intelligence/<seat>/` directories its cells are donated under, the
    consumer's own artifact the coverage leg counts 24h cells from.
    """

    path: str
    reads: tuple[str, ...]
    branch: str = LIVE
    leg: str | None = None
    seats: tuple[str, ...] = ()
    note: str = ""


@dataclass(frozen=True)
class Estimate:
    """Declared quantities behind a cells/day ESTIMATE. None where the consumer declares none."""

    series: int = 0
    symbols: int = 0
    cells_per_pair: int = 0
    per_pass_cap: int | None = None
    basis: str = ""

    @property
    def grid(self) -> int:
        return int(self.series) * int(self.symbols) * int(self.cells_per_pair)

    @property
    def cells_per_day(self) -> int | None:
        if self.grid <= 0:
            return None
        return min(self.grid, self.per_pass_cap * 24) if self.per_pass_cap else self.grid


@dataclass(frozen=True)
class CredentialVar:
    env: str                              #: the canonical name (the principal's `setx` name)
    provider: str
    signup_url: str
    free_tier: str
    unlocks: str                          #: datasets
    instruments: tuple[str, ...]          #: MT5 instruments the cells land on
    families: tuple[str, ...]
    consumers: tuple[Consumer, ...]
    aliases: tuple[str, ...] = ()         #: other env names some reader accepts
    secrets: tuple[str, ...] = ()         #: `file:<path>#<key>` names a reader accepts
    kind: str = "key"                     #: key | id | secret | login | user_agent | token
    group: str = ""                       #: vars that only work together (id + secret)
    principal_list: bool = False          #: on the principal's 2026-09-30 setx list
    built: str = "BUILT"                  #: BUILT | NOT_BUILT: <why>
    estimate: Estimate = field(default_factory=Estimate)

    @property
    def accepted(self) -> tuple[str, ...]:
        return (self.env, *self.aliases)


# ------------------------------------------------------------------------------ consumers ---
_KS = "desks/mt5/research/keyed_sources.py"
_KS_LEG = "keyed_sources"
_KS_SEATS = ("keyed_sources", "keyed_sources_indirect")
#: Cells per (series, symbol) the keyed_sources leg mints: 8 direct exogenous_conditioner cells
#: (2 transforms x 2 thresholds x 2 sides) + 6 indirect (3 certified parents x gt/lt).
KS_CELLS_PER_PAIR = 14
KS_PER_PASS = 1200


def _ks(var: str, note: str = "") -> Consumer:
    return Consumer(_KS, (var,), LIVE, _KS_LEG, _KS_SEATS, note)


_DISC = "desks/mt5/research/corporate_disclosure.py"
_DISC_BRANCH = "claude/asia-disclosure (in progress)"
_DISC_FILE = "file:desks/mt5/data/secrets/disclosure_apis.json"
_ALT = "desks/mt5/research/alt_proxies.py"
_ALT_BRANCH = "claude/alpha-capture-substitute (#131)"
_FS = "libs/data/free_stack.py"
_FS_BRANCH = "claude/free-stack-sources (#129)"
_FS_SEATS = ("free_stack_proposer",)
_LLM_NAMES = ("OPENROUTER_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY", "XAI_API_KEY")

REGISTRY: tuple[CredentialVar, ...] = (
    # ------------------------------------------------------------- the principal's list ---
    CredentialVar(
        env="GITHUB_TOKEN", provider="GitHub REST API (personal access token, no scopes)",
        signup_url="https://github.com/settings/tokens",
        free_tier="5,000 requests/h authenticated vs 60/h anonymous; code search needs a token",
        unlocks="code search and repository trees of public strategy repositories",
        instruments=("every hypothesis-lane symbol the extracted rules name",),
        families=("rule families extracted from code (EXACT_RECIPE)",),
        consumers=(
            Consumer("desks/mt5/research/cell_emitter.py", ("GITHUB_TOKEN",),
                     "claude/cell-emitter (#116)", "cell_emitter", ("cell_emitter",),
                     "code search is skipped without the token"),
            Consumer("libs/data/papers.py", ("GITHUB_TOKEN",), LIVE, None, (),
                     "also reads ~/.gh_token; run by ops/run_research_cycle.sh on the VPS"),
            Consumer("desks/mt5/research/repo_miner.py", ("GITHUB_TOKEN",), LIVE, None, ()),
            Consumer("desks/mt5/side_channels/github_miner.py", ("GITHUB_TOKEN",), LIVE, None,
                     ("github",))),
        principal_list=True, kind="token",
        estimate=Estimate(50, 4, 3, None, "cell_emitter code search: ~50 files/query, ~4 "
                          "symbols and ~3 rule cells per file (declared shape; UNMEASURED yield)")),
    CredentialVar(
        env="REDDIT_CLIENT_ID", provider="Reddit OAuth app-only (script app)",
        signup_url="https://www.reddit.com/prefs/apps",
        free_tier="100 queries/min per OAuth client (free, non-commercial)",
        unlocks="subreddit listings (r/Forex, r/Gold, r/oil, r/Daytrading ...) beyond the "
                "anonymous JSON's rate limit and 403 walls",
        instruments=("XAUUSD", "XAGUSD", "XTIUSD", "EURUSD", "USDJPY", "NAS100", "US500"),
        families=("exogenous_conditioner",),
        consumers=(_ks("REDDIT_CLIENT_ID", "reddit_oauth: instrument mention counts"),),
        group="reddit", principal_list=True, kind="id",
        estimate=Estimate(7, 1, KS_CELLS_PER_PAIR, KS_PER_PASS,
                          "keyed_sources reddit_oauth: 7 instrument-mention series, each on its "
                          "own instrument")),
    CredentialVar(
        env="REDDIT_SECRET", provider="Reddit OAuth app-only (script app)",
        signup_url="https://www.reddit.com/prefs/apps",
        free_tier="(pair of REDDIT_CLIENT_ID)", unlocks="(pair of REDDIT_CLIENT_ID)",
        instruments=(), families=("exogenous_conditioner",),
        consumers=(Consumer(_KS, ("REDDIT_SECRET", "REDDIT_CLIENT_SECRET"), LIVE, _KS_LEG,
                            _KS_SEATS),),
        aliases=("REDDIT_CLIENT_SECRET",), group="reddit", principal_list=True, kind="secret"),
    CredentialVar(
        env="TELEGRAM_API_ID", provider="Telegram MTProto API (my.telegram.org app)",
        signup_url="https://my.telegram.org/apps",
        free_tier="free; a USER session must be created once by hand (phone code) -- never "
                  "automatically",
        unlocks="full channel history of public finance channels (t.me/s shows ~20 recent posts)",
        instruments=("XAUUSD", "USDCNH", "USDJPY", "XTIUSD", "HK50", "USDKRW"),
        families=("exogenous_conditioner",),
        consumers=(Consumer(_KS, ("TELEGRAM_API_ID", "TG_API_ID"), LIVE, _KS_LEG, _KS_SEATS,
                            "telethon; BLOCKED_DEPENDENCY without the package or a session"),),
        aliases=("TG_API_ID",), group="telegram", principal_list=True, kind="id",
        estimate=Estimate(6, 1, KS_CELLS_PER_PAIR, KS_PER_PASS,
                          "keyed_sources telegram_mtproto: 6 instrument-mention series")),
    CredentialVar(
        env="TELEGRAM_API_HASH", provider="Telegram MTProto API",
        signup_url="https://my.telegram.org/apps", free_tier="(pair of TELEGRAM_API_ID)",
        unlocks="(pair of TELEGRAM_API_ID)", instruments=(), families=(),
        consumers=(Consumer(_KS, ("TELEGRAM_API_HASH", "TG_API_HASH"), LIVE, _KS_LEG,
                            _KS_SEATS),),
        aliases=("TG_API_HASH",), group="telegram", principal_list=True, kind="secret"),
    CredentialVar(
        env="FRED_API_KEY", provider="St. Louis Fed FRED / ALFRED",
        signup_url="https://fredaccount.stlouisfed.org/apikeys",
        free_tier="120 requests/min, free",
        unlocks="22 daily macro series (fred_macro), ALFRED vintages (first print / revision)",
        instruments=("EURUSD", "USDJPY", "XAUUSD", "US500", "NAS100", "US30"),
        families=("macro_conditional", "exogenous_conditioner"),
        consumers=(
            Consumer("scripts/collect_fred_macro.py",
                     ("FRED_API_KEY", "file:data/secrets/fred.json#key"), LIVE, "fred_macro"),
            Consumer("desks/mt5/research/fetch_alfred.py",
                     ("FRED_API_KEY", "file:data/secrets/fred.json#key"),
                     "live (env + secrets/fred_api_key); data/secrets/fred.json lands with "
                     "claude/global-media-factory (#123)", "fetch_alfred",
                     ("world_cells",)),
            Consumer("scripts/screen_fred_macro_axis.py",
                     ("FRED_API_KEY", "file:data/secrets/fred.json#key"), LIVE, None, (),
                     "manual screen; accepts the env var since claude/key-coverage")),
        secrets=("file:data/secrets/fred.json#key",), principal_list=True,
        estimate=Estimate(22, 6, 8, None, "22 fred_macro series x 6 mapped symbols x 8 "
                          "conditioner cells (world_cells on #123 declares its own grid)")),
    CredentialVar(
        env="EIA_API_KEY", provider="US Energy Information Administration API v2",
        signup_url="https://www.eia.gov/opendata/register.php",
        free_tier="free; ~5,000 requests/h, 5,000 rows per request",
        unlocks="weekly crude, gasoline, distillate and Cushing stocks; weekly natural-gas "
                "storage (Lower 48)",
        instruments=("XTIUSD", "XBRUSD", "XNGUSD", "USDCAD"),
        families=("exogenous_conditioner",),
        consumers=(_ks("EIA_API_KEY"),), principal_list=True,
        estimate=Estimate(5, 3, KS_CELLS_PER_PAIR, KS_PER_PASS,
                          "keyed_sources eia: 5 weekly series x ~3 energy symbols")),
    CredentialVar(
        env="NASDAQ_DATA_LINK_KEY", provider="Nasdaq Data Link (ex-Quandl) free tables",
        signup_url="https://data.nasdaq.com/sign-up",
        free_tier="50,000 calls/day with a free key (anonymous: 50/day)",
        unlocks="LBMA gold/silver fixes, OPEC basket, CFTC COT (QDL tables)",
        instruments=("XAUUSD", "XAGUSD", "XBRUSD", "XTIUSD"),
        families=("exogenous_conditioner",),
        consumers=(Consumer(_KS, ("NASDAQ_DATA_LINK_KEY", "NASDAQ_DATA_LINK_API_KEY",
                                  "QUANDL_API_KEY"), LIVE, _KS_LEG, _KS_SEATS),),
        aliases=("NASDAQ_DATA_LINK_API_KEY", "QUANDL_API_KEY"), principal_list=True,
        estimate=Estimate(5, 2, KS_CELLS_PER_PAIR, KS_PER_PASS,
                          "keyed_sources nasdaq_data_link: 5 series x ~2 symbols")),
    CredentialVar(
        env="EDINET_API_KEY", provider="Japan FSA EDINET API v2",
        signup_url="https://api.edinet-fsa.go.jp/api/auth/index.aspx?mode=1",
        free_tier="free Subscription-Key",
        unlocks="statutory filings (securities reports, large-holding reports) with minute stamps",
        instruments=("JPN225", "USDJPY"), families=("exogenous_conditioner", "exogenous_gate",
                                                   "news_reaction"),
        consumers=(Consumer(_DISC, ("EDINET_API_KEY", f"{_DISC_FILE}#EDINET_API_KEY"),
                            _DISC_BRANCH, "corporate_disclosure", ("corporate_disclosure",),
                            "status word there: BLOCKED_NO_KEY"),),
        secrets=(f"{_DISC_FILE}#EDINET_API_KEY",), principal_list=True,
        estimate=Estimate(1, 1, 400, 400, "corporate_disclosure DONATE_PER_PASS=400 shared by "
                          "every disclosure source; one source's share is UNMEASURED")),
    CredentialVar(
        env="DART_API_KEY", provider="Korea FSS OpenDART",
        signup_url="https://opendart.fss.or.kr/uss/umt/EgovMberInsertView.do",
        free_tier="20,000 calls/day, free", unlocks="Korean corporate filings",
        instruments=("USDKRW", "NAS100"), families=("exogenous_conditioner", "exogenous_gate",
                                                    "news_reaction"),
        consumers=(Consumer(_DISC, ("DART_API_KEY", f"{_DISC_FILE}#DART_API_KEY"),
                            _DISC_BRANCH, "corporate_disclosure", ("corporate_disclosure",)),),
        secrets=(f"{_DISC_FILE}#DART_API_KEY",), principal_list=True,
        estimate=Estimate(1, 1, 400, 400, "corporate_disclosure shared DONATE_PER_PASS=400")),
    CredentialVar(
        env="ESTAT_APP_ID", provider="Japan e-Stat API 3.0 (Statistics Bureau)",
        signup_url="https://www.e-stat.go.jp/mypage/user/preregister",
        free_tier="free application ID",
        unlocks="Tokyo CPI (alt_proxies, #131); household spending and machinery orders "
                "(keyed_sources, through #131's getStatsData parser)",
        instruments=("USDJPY", "EURJPY", "AUDJPY", "JPN225"),
        families=("exogenous_conditioner",),
        consumers=(
            Consumer(_ALT, ("ESTAT_APP_ID",), _ALT_BRANCH, "alt_proxies",
                     ("alt_proxies", "alt_proxies_indirect"),
                     "parse_estat_cpi (the one e-Stat parser); status word BLOCKED_ON_KEY"),
            _ks("ESTAT_APP_ID", "household spending + machinery orders; parser imported from "
                "alt_proxies, BLOCKED_DEPENDENCY until #131 merges")),
        principal_list=True, kind="id",
        estimate=Estimate(3, 4, KS_CELLS_PER_PAIR, KS_PER_PASS,
                          "1 alt_proxies + 2 keyed_sources e-Stat series x 4 JPY symbols")),
    CredentialVar(
        env="KOSIS_API_KEY", provider="Statistics Korea KOSIS OpenAPI",
        signup_url="https://kosis.kr/openapi/index/index.jsp",
        free_tier="free key", unlocks="Korea CPI and exports (monthly)",
        instruments=("USDKRW", "AUDUSD", "NAS100", "JPN225"),
        families=("exogenous_conditioner",),
        consumers=(_ks("KOSIS_API_KEY"),), principal_list=True,
        estimate=Estimate(2, 4, KS_CELLS_PER_PAIR, KS_PER_PASS,
                          "keyed_sources kosis: 2 series x 4 KRW-proxy symbols")),
    CredentialVar(
        env="TUSHARE_TOKEN", provider="TuShare Pro",
        signup_url="https://tushare.pro/register",
        free_tier="free token with points-gated endpoints (index daily is open at 120 points)",
        unlocks="China index/futures daily bars and fundamentals",
        instruments=("CHINAH", "HK50", "USDCNH", "XCUUSD"),
        families=("exogenous_conditioner", "alt_series_momentum", "alt_conditioned"),
        consumers=(Consumer(_FS, ("TUSHARE_TOKEN",), _FS_BRANCH, "free_stack_hunt", _FS_SEATS,
                            "status word there: NEEDS_CREDENTIAL"),),
        principal_list=True, kind="token",
        estimate=Estimate(4, 3, 56, 1500, "free_stack_proposer: 28 cells x 2 charts per "
                          "(column, symbol); ~4 TuShare columns x 3 proxies (declared shape)")),
    CredentialVar(
        env="JQ_USER", provider="JoinQuant jqdatasdk", signup_url="https://www.joinquant.com/",
        free_tier="free trial account (daily quota)", unlocks="China A-share/futures data",
        instruments=("CHINAH", "HK50", "USDCNH"),
        families=("exogenous_conditioner", "alt_series_momentum", "alt_conditioned"),
        consumers=(Consumer(_FS, ("JQ_USER",), _FS_BRANCH, "free_stack_hunt", _FS_SEATS,
                            "needs the jqdatasdk package too"),),
        group="joinquant", principal_list=True, kind="login",
        estimate=Estimate(4, 3, 56, 1500, "free_stack_proposer grid, ~4 columns x 3 proxies")),
    CredentialVar(
        env="JQ_PASS", provider="JoinQuant jqdatasdk", signup_url="https://www.joinquant.com/",
        free_tier="(pair of JQ_USER)", unlocks="(pair of JQ_USER)", instruments=(),
        families=(), consumers=(Consumer(_FS, ("JQ_PASS",), _FS_BRANCH, "free_stack_hunt",
                                         _FS_SEATS),),
        group="joinquant", principal_list=True, kind="secret"),
    CredentialVar(
        env="OPENROUTER_API_KEY", provider="LLM seat (OpenRouter first; OpenAI / DeepSeek / "
                                           "xAI accepted by llm_seat)",
        signup_url="https://openrouter.ai/keys",
        free_tier="free models are rate-limited per day; paid models metered (desk cap $20/mo)",
        unlocks="the deepening seat (rule extraction from 28k+ worked rows), CRO, survivor "
                "panel, kimi/deepseek hunters",
        instruments=("every hypothesis-lane symbol",),
        families=("STRUCTURED_HYPOTHESIS from the seats",),
        consumers=(
            Consumer("libs/ops/llm_seat.py", (*_LLM_NAMES, "file:data/secrets/llm_panel.json"),
                     LIVE, "deepening_worker", ("deepening",),
                     "KEY_ENV_VARS at libs/ops/llm_seat.py:78 decides the names, in order"),
            Consumer("libs/ops/deepseek_cycle.py",
                     ("OPENROUTER_API_KEY", "file:data/secrets/llm_panel.json"), LIVE, None,
                     ("deepseek",), "reads OPENROUTER_API_KEY only; run by "
                                    "ops/run_deepseek_factory.sh")),
        aliases=("OPENAI_API_KEY", "DEEPSEEK_API_KEY", "XAI_API_KEY"),
        secrets=("file:data/secrets/llm_panel.json",), principal_list=True,
        estimate=Estimate(1, 1, 700, None, "deepening worker: ~700 structured rows/day at the "
                          "free tier's daily request cap (declared, UNMEASURED yield)")),
    # ------------------------------------------------------- found in the lanes' readers ---
    CredentialVar(
        env="SEC_EDGAR_USER_AGENT", provider="SEC EDGAR (no key: a contact User-Agent)",
        signup_url="https://www.sec.gov/os/accessing-edgar-data",
        free_tier="no registration; <=10 requests/s with a declared User-Agent "
                  "('Desk Name admin@domain')",
        unlocks="8-K/6-K full-text search, XBRL company facts",
        instruments=("US500", "NAS100", "US30"),
        families=("news_reaction", "analyst_revision_drift", "exogenous_conditioner"),
        consumers=(
            Consumer("desks/mt5/research/sandboxes/edgar_transmission.py",
                     ("QUANT_EDGAR_UA", "SEC_EDGAR_USER_AGENT", "SEC_EDGAR_UA"), LIVE, None, (),
                     "accepts all three since claude/key-coverage"),
            Consumer("desks/mt5/research/alpha_capture.py", ("QUANT_EDGAR_UA",), _ALT_BRANCH,
                     "alpha_capture", ("alpha_capture",)),
            Consumer(_DISC, ("SEC_EDGAR_UA", "QUANT_EDGAR_UA", f"{_DISC_FILE}#SEC_EDGAR_UA"),
                     _DISC_BRANCH, "corporate_disclosure", ("corporate_disclosure",)),
            Consumer("desks/mt5/research/sec_fundamentals.py", ("QUANT_EDGAR_UA",),
                     "claude/semis-and-fundamentals (#136)", None, ())),
        aliases=("QUANT_EDGAR_UA", "SEC_EDGAR_UA"), secrets=(f"{_DISC_FILE}#SEC_EDGAR_UA",),
        kind="user_agent",
        estimate=Estimate(1, 1, 400, 400, "shares corporate_disclosure's 400/pass; "
                          "alpha_capture's EDGAR share UNMEASURED")),
    CredentialVar(
        env="JQUANTS_REFRESH_TOKEN", provider="JPX J-Quants (free plan: 12 weeks delayed)",
        signup_url="https://jpx-jquants.com/",
        free_tier="free plan; statements 12 weeks late -- BACKTEST ONLY, not live-usable",
        unlocks="Japanese financial statements with company forecasts",
        instruments=("JPN225",), families=("exogenous_conditioner",),
        consumers=(Consumer(_DISC, ("JQUANTS_REFRESH_TOKEN", "JQUANTS_TOKEN",
                                    f"{_DISC_FILE}#JQUANTS_REFRESH_TOKEN"),
                            _DISC_BRANCH, "corporate_disclosure", ("corporate_disclosure",)),),
        aliases=("JQUANTS_TOKEN",), secrets=(f"{_DISC_FILE}#JQUANTS_REFRESH_TOKEN",),
        group="jquants", kind="token",
        estimate=Estimate(1, 1, 50, None, "backtest-only statements; shared disclosure cap")),
    CredentialVar(
        env="JQUANTS_MAIL", provider="JPX J-Quants login (mints the refresh token)",
        signup_url="https://jpx-jquants.com/", free_tier="(alternative to the refresh token)",
        unlocks="(pair of JQUANTS_PASSWORD)", instruments=(), families=(),
        consumers=(Consumer(_DISC, ("JQUANTS_MAIL", f"{_DISC_FILE}#JQUANTS_MAIL"), _DISC_BRANCH,
                            "corporate_disclosure", ("corporate_disclosure",)),),
        secrets=(f"{_DISC_FILE}#JQUANTS_MAIL",), group="jquants", kind="login"),
    CredentialVar(
        env="JQUANTS_PASSWORD", provider="JPX J-Quants login",
        signup_url="https://jpx-jquants.com/", free_tier="(pair of JQUANTS_MAIL)",
        unlocks="(pair of JQUANTS_MAIL)", instruments=(), families=(),
        consumers=(Consumer(_DISC, ("JQUANTS_PASSWORD", f"{_DISC_FILE}#JQUANTS_PASSWORD"),
                            _DISC_BRANCH, "corporate_disclosure", ("corporate_disclosure",)),),
        secrets=(f"{_DISC_FILE}#JQUANTS_PASSWORD",), group="jquants", kind="secret"),
    CredentialVar(
        env="FIRMS_MAP_KEY", provider="NASA FIRMS (VIIRS thermal detections)",
        signup_url="https://firms.modaps.eosdis.nasa.gov/api/map_key/",
        free_tier="free MAP_KEY, 5,000 transactions / 10 min",
        unlocks="daily thermal detections over Chinese steel/coke/smelter footprints",
        instruments=("XCUUSD", "AUDUSD", "CHINAH", "HK50"), families=("exogenous_conditioner",),
        consumers=(Consumer(_ALT, ("FIRMS_MAP_KEY",), _ALT_BRANCH, "alt_proxies",
                            ("alt_proxies", "alt_proxies_indirect")),),
        estimate=Estimate(6, 4, 3, 24, "alt_proxies: 5 clusters + total x 4 symbols; direct "
                          "cells only after a release-gain PASS, indirect 24/pass")),
    CredentialVar(
        env="KOBIS_API_KEY", provider="Korea Box Office Information System (KOBIS, KOFIC)",
        signup_url="https://www.kobis.or.kr/kobisopenapi/homepg/apikey/ckUser/findApiKeyList.do",
        free_tier="free key, 3,000 calls/day",
        unlocks="daily box-office admissions and sales (Korean consumer-spending proxy)",
        instruments=("USDKRW",), families=("exogenous_conditioner",),
        consumers=(Consumer("Asia thread (alt_proxies/event_factors)", ("KOBIS_API_KEY",),
                            "Asia thread (not on origin yet)", "alt_proxies",
                            ("alt_proxies",)),),
        estimate=Estimate(1, 2, 8, None, "one daily admissions series x ~2 KRW proxies x 8 "
                          "conditioner cells (declared by the Asia thread, UNMEASURED)")),
    CredentialVar(
        env="SEOUL_API_KEY", provider="Seoul Open Data Plaza (data.seoul.go.kr)",
        signup_url="https://data.seoul.go.kr/together/mypage/actkeyMain.do",
        free_tier="free key, 1,000 rows/call",
        unlocks="Seoul subway ridership, card-spend and floating-population tables",
        instruments=("USDKRW",), families=("exogenous_conditioner",),
        consumers=(Consumer("Asia thread (alt_proxies/event_factors)", ("SEOUL_API_KEY",),
                            "Asia thread (not on origin yet)", "alt_proxies",
                            ("alt_proxies",)),),
        estimate=Estimate(2, 2, 8, None, "~2 mobility series x ~2 KRW proxies x 8 cells "
                          "(declared by the Asia thread, UNMEASURED)")),
    # -------------------------------------------------- the coordinator's candidates -------
    CredentialVar(
        env="ECOS_API_KEY", provider="Bank of Korea ECOS OpenAPI",
        signup_url="https://ecos.bok.or.kr/api/#/AuthKeyApply",
        free_tier="free key; 100,000 rows per call",
        unlocks="BoK base rate, KRW/USD, export and import price indices, M2 (monthly/daily)",
        instruments=("USDKRW", "AUDUSD", "NAS100", "JPN225"),
        families=("exogenous_conditioner",), consumers=(_ks("ECOS_API_KEY"),),
        estimate=Estimate(3, 4, KS_CELLS_PER_PAIR, KS_PER_PASS,
                          "keyed_sources ecos: 3 series x 4 KRW-proxy symbols")),
    CredentialVar(
        env="BLS_API_KEY", provider="US Bureau of Labor Statistics API v2",
        signup_url="https://data.bls.gov/registrationEngine/",
        free_tier="500 queries/day, 50 series/query, 20 years (v1 keyless: 25/day, 10 years)",
        unlocks="CPI components (core services, shelter), average hourly earnings, PPI final "
                "demand -- the components FRED's headline list does not carry",
        instruments=("EURUSD", "USDJPY", "XAUUSD", "US500", "NAS100"),
        families=("exogenous_conditioner",), consumers=(_ks("BLS_API_KEY"),),
        estimate=Estimate(4, 5, KS_CELLS_PER_PAIR, KS_PER_PASS,
                          "keyed_sources bls: 4 component series x 5 USD symbols")),
    CredentialVar(
        env="BEA_API_KEY", provider="US Bureau of Economic Analysis API",
        signup_url="https://apps.bea.gov/API/signup/",
        free_tier="free; 100 requests/min", unlocks="NIPA GDP, PCE, trade balance detail",
        instruments=("EURUSD", "USDJPY", "US500"), families=("exogenous_conditioner",),
        consumers=(),
        built=("NOT_BUILT: FRED/ALFRED already carry GDP, PCE and the trade balance WITH "
               "vintages (fetch_alfred); BEA adds industry/regional detail with no MT5 mapping")),
    CredentialVar(
        env="FINNHUB_API_KEY", provider="Finnhub",
        signup_url="https://finnhub.io/register",
        free_tier="60 calls/min; company news, earnings calendar, basic financials (news "
                  "sentiment and economic calendar are premium)",
        unlocks="earnings calendar and company news for the share-CFD EVENT lane",
        instruments=("share CFDs (event lane only)",), families=("news_reaction",),
        consumers=(),
        built=("NOT_BUILT: the event-lane consumer (news_reaction on claude/asia-disclosure) is "
               "unmerged; a calendar with no consumer is a dataset that feeds no producer. Wire "
               "after asia-disclosure lands")),
    CredentialVar(
        env="TIINGO_API_KEY", provider="Tiingo", signup_url="https://www.tiingo.com/account/api/"
                                                          "token",
        free_tier="1,000 requests/day, 500 symbols/month; news API is paid",
        unlocks="EOD equity/ETF bars (duplicates the broker's own bars)",
        instruments=(), families=(), consumers=(),
        built="NOT_BUILT: EOD bars duplicate MT5 bars; news is not on the free tier"),
    CredentialVar(
        env="ALPHAVANTAGE_API_KEY", provider="Alpha Vantage",
        signup_url="https://www.alphavantage.co/support/#api-key",
        free_tier="25 requests/day", unlocks="price series and a few US macro series",
        instruments=(), families=(), consumers=(),
        built="NOT_BUILT: 25 calls/day, prices duplicate MT5 bars, macro duplicates FRED"),
    CredentialVar(
        env="TWELVE_DATA_API_KEY", provider="Twelve Data",
        signup_url="https://twelvedata.com/register", free_tier="800 requests/day",
        unlocks="price series", instruments=(), families=(), consumers=(),
        built="NOT_BUILT: prices duplicate the broker's own bars"),
    CredentialVar(
        env="POLYGON_API_KEY", provider="Polygon.io (now Massive) free tier",
        signup_url="https://polygon.io/dashboard/signup", free_tier="5 calls/min, EOD only",
        unlocks="US equity EOD aggregates", instruments=(), families=(), consumers=(),
        built="NOT_BUILT: EOD aggregates duplicate MT5 bars at 5 calls/min"),
    CredentialVar(
        env="OPENFIGI_API_KEY", provider="OpenFIGI", signup_url="https://www.openfigi.com/api",
        free_tier="keyless 25 req/min; key 250 req/min",
        unlocks="identifier mapping (ticker/ISIN -> FIGI) for disclosure-to-instrument joins",
        instruments=(), families=(), consumers=(),
        built="NOT_BUILT: a mapping utility, not a dataset; no cell rides on it yet"),
    CredentialVar(
        env="NEWSAPI_KEY", provider="NewsAPI.org", signup_url="https://newsapi.org/register",
        free_tier="100 requests/day, developer use only (not for production)",
        unlocks="headline search", instruments=(), families=(), consumers=(),
        built="NOT_BUILT: the free licence forbids production use; GDELT is keyless"),
    CredentialVar(
        env="GNEWS_API_KEY", provider="GNews", signup_url="https://gnews.io/register",
        free_tier="100 requests/day, 10 articles/request", unlocks="headline search",
        instruments=(), families=(), consumers=(),
        built="NOT_BUILT: 1,000 headlines/day and no event-lane consumer on live yet"),
)

BY_ENV: dict[str, CredentialVar] = {v.env: v for v in REGISTRY}

#: No key needed. `wired_in` names the file(s) on live that fetch it; the coverage leg checks
#: each path exists on this checkout. A keyless source that nothing reads is listed with an
#: empty tuple, which the report shows as NOT_WIRED.
KEYLESS: tuple[dict[str, Any], ...] = (
    {"provider": "CFTC Commitments of Traders (publicreporting.cftc.gov)",
     "wired_in": ("desks/mt5/mt5desk/fetch_cot.py", "desks/mt5/mt5desk/fetch_tff.py")},
    {"provider": "ECB Data Portal / SDW (data-api.ecb.europa.eu)",
     "wired_in": ("desks/mt5/research/axis_ingest.py", "desks/mt5/research/data_axis_miner.py")},
    {"provider": "Eurostat", "wired_in": ("desks/mt5/macro/sources.py",)},
    {"provider": "Statistics Canada", "wired_in": ("desks/mt5/macro/sources.py",)},
    {"provider": "Reserve Bank of Australia", "wired_in": ("desks/mt5/macro/sources.py",
                                                           "desks/mt5/research/asia_collector.py")},
    {"provider": "ABS (api.data.abs.gov.au)",
     "wired_in": ("desks/mt5/research/macro_region/intelligence.py",),
     "note": "named in the macro-region pack; no scheduled series fetcher found"},
    {"provider": "BIS statistics (stats.bis.org)", "wired_in": (),
     "note": "referenced in country packs only"},
    {"provider": "OECD SDMX (sdmx.oecd.org)", "wired_in": ()},
    {"provider": "IMF SDMX (api.imf.org)", "wired_in": (),
     "note": "IMF PortWatch is read by alt_proxies (#131)"},
    {"provider": "SEC EDGAR (User-Agent only; see SEC_EDGAR_USER_AGENT)",
     "wired_in": ("desks/mt5/research/sandboxes/edgar_transmission.py",)},
    {"provider": "Reddit anonymous JSON / RSS", "wired_in": ("desks/mt5/side_channels/"
                                                            "reddit_miner.py",)},
    {"provider": "Telegram public preview (t.me/s)",
     "wired_in": ("desks/mt5/research/deep_forest_miner.py",)},
)


# --------------------------------------------------------------------------- presence -------
def _secret_key_names(path: Path) -> frozenset[str]:
    """The top-level KEY NAMES of a secrets JSON file. Values are dropped inside this function."""
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return frozenset()
    if not isinstance(doc, dict):
        return frozenset()
    names = {str(k) for k, v in doc.items() if v not in (None, "", {}, [])}
    del doc
    return frozenset(names)


def secret_present(spec: str, root: Path = ROOT) -> bool:
    """`file:<relative path>[#<key>]` -> does that file exist and (if named) hold that key."""
    if not spec.startswith("file:"):
        return False
    rel, _, key = spec[5:].partition("#")
    p = root / rel
    if not p.exists():
        return False
    return (not key) or key in _secret_key_names(p)


def env_present(name: str, environ: Mapping[str, str] | None = None) -> bool:
    env = os.environ if environ is None else environ
    return bool(str(env.get(name, "")).strip())


def accepted_names(var: str) -> tuple[str, ...]:
    """Every environment NAME some reader accepts for `var`, canonical first. A fetcher reads the
    value itself through these names; this module never does."""
    v = BY_ENV.get(var)
    return v.accepted if v else (var,)


def present_names(v: CredentialVar, environ: Mapping[str, str] | None = None,
                  root: Path = ROOT) -> list[str]:
    """Which accepted env names and secrets-file names are present. Names only."""
    got = [n for n in v.accepted if env_present(n, environ)]
    got += [s for s in v.secrets if secret_present(s, root)]
    return got


def status(v: CredentialVar, environ: Mapping[str, str] | None = None,
           root: Path = ROOT) -> dict[str, Any]:
    """SET / MISMATCHED_NAME / BLOCKED_AUTH for one variable, with the consumers left dark."""
    found = present_names(v, environ, root)
    if not found:
        return {"status": BLOCKED_AUTH, "present_as": [], "dark_consumers": [c.path for c in
                                                                           v.consumers]}
    dark = [c.path for c in v.consumers if not any(n in c.reads for n in found)]
    return {"status": MISMATCHED_NAME if dark else SET, "present_as": found,
            "dark_consumers": dark}


def name_mismatches() -> list[dict[str, Any]]:
    """Static: every consumer that does NOT read the canonical (principal's) name."""
    out: list[dict[str, Any]] = []
    for v in REGISTRY:
        for c in v.consumers:
            if v.env not in c.reads:
                out.append({"var": v.env, "consumer": c.path, "branch": c.branch,
                            "reads": [n for n in c.reads if not n.startswith("file:")],
                            "secrets": [n for n in c.reads if n.startswith("file:")]})
    return out


KS_ROSTER = DESK / "data" / "source_rosters" / "keyed_sources.json"


def estimate_for(v: CredentialVar, roster: Path = KS_ROSTER) -> Estimate:
    """The ESTIMATE behind a var's rank. For the keyed_sources leg it is DERIVED from the roster
    (mapped (series, instrument) pairs x cells per pair, bounded by the per-pass cap x 24), so it
    cannot drift from what the leg will actually mint; for other lanes it is the declared shape."""
    if not any(c.path == _KS for c in v.consumers) or v.kind in ("secret",):
        return v.estimate
    try:
        rows = json.loads(roster.read_text("utf-8")).get("sources") or []
    except (OSError, ValueError, AttributeError):
        return v.estimate
    series = pairs = 0
    for r in rows:
        if isinstance(r, dict) and (r.get("key_env") or [None])[0] == v.env:
            for spec in (r.get("series") or {}).values():
                series += 1
                pairs += len((spec or {}).get("instruments") or {})
    if not pairs:
        return v.estimate
    return Estimate(pairs, 1, KS_CELLS_PER_PAIR, KS_PER_PASS,
                    f"keyed_sources roster: {series} series, {pairs} (series, instrument) pairs "
                    f"x {KS_CELLS_PER_PAIR} cells (8 direct + 6 indirect)")


def normalise_status(word: str) -> str:
    """Another lane's word for an absent key -> BLOCKED_AUTH; anything else unchanged."""
    w = str(word or "").split(":", 1)[0].strip().upper()
    return BLOCKED_AUTH if w in BLOCKED_SYNONYMS else str(word)


def setx_line(v: CredentialVar) -> str:
    """The principal's one-line set command, with a PLACEHOLDER value only."""
    return f'setx {v.env} "<{v.kind}>"'


__all__ = ["BLOCKED_AUTH", "BY_ENV", "KEYLESS", "MISMATCHED_NAME", "REGISTRY", "SET", "UNMEASURED",
           "Consumer", "CredentialVar", "Estimate", "accepted_names", "env_present", "estimate_for",
           "name_mismatches", "normalise_status", "present_names", "secret_present", "setx_line",
           "status"]
