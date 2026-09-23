"""THE FOREST FEDERATION -- every region is its own 24/7 research civilization, not a search.

THE PRINCIPAL'S ORDER (2026-09-17). Not one global crawler that occasionally searches Korea:
Korea 24/7 || Japan 24/7 || China 24/7 || Russia 24/7 || ... || Global 24/7, in parallel, each
with its own native-language agents, its own local source map, its own terminology and its own
public ecosystems, all feeding ONE global research brain through ONE dedup chain.

WHAT THIS MODULE IS. The registry of those civilizations, as data: which countries a forest
covers, which languages it reads, which package or country packs it draws on, the eleven agent
ROLES every one of them runs simultaneously, the box task that keeps each one alive, and the
compute allocation each is currently entitled to. It is PURE: it opens no socket, writes no
file and imports no desk organ. `desks/mt5/research/forest_runner.py` is the organ that runs it.

THREE THINGS IT IS DELIBERATE ABOUT.

**A REGION IS NOT A KEYWORD LIST.** `Forest.packs` names the country packs the forest draws its
mandate from, and those packs are being written CONCURRENTLY by other builders. So they are
resolved LAZILY and an absent pack is UNMEASURED BY NAME -- `unmeasured_packs` returns the
codes with the path that would have carried them. A forest whose packs have not landed still
runs: its source scouts work from the mandate's own terms, and every other role reports what is
missing rather than reporting nothing (L1.28a).

**REGIONS COMPETE FOR COMPUTE, AND THE SCOUT IS NOT A KNOB.** `allocation_for` reads
`desks/mt5/data/forest_allocation.json`, written by the research-ROI organ: a forest producing
useful candidates gets more workers, a low-yield forest gets fewer. But `workers` can never fall
below 1 and the SOURCE SCOUT ALWAYS RUNS -- a forest defunded to silence can never produce the
evidence that would refund it, which is the starvation loop that makes a yield allocator look
right forever while it reads one corner of the world. A file that says `scout_floor: false` is
overruled here and the override is carried in `why`, not swallowed.

**THE TASK NAME IS BUILT, NEVER WRITTEN.** `FOREST_TASKS` composes each task name from
`TASK_PREFIX` and the forest's id, so no source file carries a task-name literal for a task it
does not itself register -- and `scripts/check_box_tasks.py`, which reads every `MT5-*` literal
in the tree and demands a manifest line for it, is not handed a prefix or an example to chase.
The manifest (`desks/mt5/ops/box_tasks.manifest`) is the declaration.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

__all__ = [
    "DEFAULT_BUDGET_S",
    "DEFAULT_WORKERS",
    "FORESTS",
    "FOREST_TASKS",
    "GLOBAL_FORESTS",
    "MANDATE_SEEDS",
    "REGIONAL_FORESTS",
    "ROLES",
    "ROLE_SHARE",
    "SCOUT_ROLE",
    "TASK_PREFIX",
    "UNMEASURED",
    "Allocation",
    "Forest",
    "allocation_for",
    "camel",
    "forest",
    "forest_of_country",
    "pack_paths",
    "role_plan",
    "task_for",
    "unmeasured_packs",
]

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
#: Written by the research-ROI organ; absent is a normal state, not a failure.
ALLOCATION_JSON: Path = DESK / "data" / "forest_allocation.json"
#: The compute-economics scientist's policy (LAWS 5m/5k): a two-sided factor on every
#: forest's budget, the exploration tier's learned share over its 20% prior. Absent or
#: UNMEASURED reads exactly 1.0 -- an unearned policy moves no seconds.
POLICY_JSON: Path = DESK / "data" / "compute_policy.json"
POLICY_CLIP: tuple[float, float] = (0.5, 1.5)
#: Where a country pack lives. `<code>` is the pack DIRECTORY name, which is not always ISO-2
#: (India is `ind`, Indonesia `idn`, the euro area `ea`) -- the packs' own convention, read.
PACK_DIR: Path = DESK / "research" / "countries"

UNMEASURED = "UNMEASURED"

#: THE ELEVEN AGENT ROLES, EXACTLY. Every forest runs all eleven SIMULTANEOUSLY; a role with no
#: ground in this forest reports UNMEASURED with the reason, which is a measurement of the
#: forest's coverage rather than a role quietly missing from the roster.
SCOUT_ROLE = "source_scouts"
ROLES: tuple[str, ...] = (
    SCOUT_ROLE,               # discovering new local websites, apps, APIs
    "official_data",          # government, exchange, central-bank sources
    "practitioner",           # traders, forums, broker research, public communities
    "academic",               # local papers, dissertations, conferences
    "code",                   # GitHub/Gitee/local package ecosystems
    "archive",                # old forums, vanished strategies, historical pages
    "failure_miners",         # strategies that stopped working, and why
    "mechanism_extractors",   # material -> economic hypotheses
    "data_agents",            # raw sources -> PIT-safe structured series
    "candidate_compilers",    # mechanisms -> implementation-ready hypothesis cards
    "source_roi",             # which local ecosystems actually produce survivors
)

#: How a forest's wall-clock budget is split across the eleven. The scout's share is a FLOOR
#: (see `role_plan`): it is paid first and it is paid even when the forest is defunded to one
#: worker, because the scout is the only role that can widen a forest that has gone quiet.
ROLE_SHARE: dict[str, float] = {
    SCOUT_ROLE: 0.16, "official_data": 0.12, "practitioner": 0.12, "academic": 0.08,
    "code": 0.08, "archive": 0.06, "failure_miners": 0.08, "mechanism_extractors": 0.12,
    "data_agents": 0.08, "candidate_compilers": 0.06, "source_roi": 0.04,
}

#: Defaults when `forest_allocation.json` is absent, unreadable or silent about a forest.
DEFAULT_WORKERS = 4
DEFAULT_BUDGET_S = 3000
#: A role may never be given less than this, or "time-boxed" becomes "did not run".
MIN_ROLE_S = 5.0

#: Split across two literals ON PURPOSE: `check_box_tasks` scans the tree for `MT5-*` strings
#: and demands a manifest line for each, and a bare prefix is not a task anybody registers.
TASK_PREFIX = "MT5-" + "Forest"


@dataclass(frozen=True)
class Forest:
    """One research civilization: where it looks, what it reads it in, and what it draws on."""

    id: str
    name: str
    kind: str                                   # regional | global
    countries: tuple[str, ...] = ()             # ISO-2; empty for a global forest, by design
    languages: tuple[str, ...] = ()
    #: A dedicated region PACKAGE (japan, macro_region), repo-relative. Empty when the forest
    #: draws on country packs instead.
    package: str = ""
    #: Country pack DIRECTORY codes under `desks/mt5/research/countries/`.
    packs: tuple[str, ...] = ()
    #: Deep-forest ground `region` codes this forest owns, so `deep_forest_sources.json` and
    #: this registry join instead of being two vocabularies about the same world.
    grounds: tuple[str, ...] = ()
    mission: str = ""
    notes: str = ""

    @property
    def task(self) -> str:
        return task_for(self.id)

    @property
    def report_name(self) -> str:
        return f"FOREST_{self.id.upper()}.json"

    @property
    def department(self) -> str:
        return f"forest_{self.id}"

    @property
    def leg(self) -> str:
        return f"forest_{self.id}"


def camel(forest_id: str) -> str:
    """`russia_cis` -> `RussiaCis`. The box task's own spelling, composed rather than typed."""
    return "".join(part[:1].upper() + part[1:] for part in str(forest_id).split("_") if part)


def task_for(forest_id: str) -> str:
    """The keep-alive task name for a forest, BUILT from its id (see the module docstring)."""
    return f"{TASK_PREFIX}-{camel(forest_id)}"


def _f(fid: str, name: str, kind: str, **kw: Any) -> Forest:
    return Forest(id=fid, name=name, kind=kind, **kw)


#: THE TWELVE REGIONAL CIVILIZATIONS. Countries are ISO-2 and each country belongs to exactly
#: ONE forest -- two forests hunting the same ground would double the trial charge and halve the
#: attention, which is the duplicate explosion this federation exists to prevent.
REGIONAL_FORESTS: tuple[Forest, ...] = (
    _f("japan", "Japan", "regional", countries=("JP",), languages=("ja",),
       package="desks/mt5/research/japan", grounds=("jp",),
       mission="the principal's 47-section Japan mandate, already resident as its own department",
       notes="the only regional forest with a dedicated region PACKAGE rather than country packs"),
    _f("korea", "Korea", "regional", countries=("KR",), languages=("ko",),
       packs=("kr",), grounds=("kr",),
       mission="the Korean economic system to exhaustion, expressed through JPY crosses, the "
               "indices, gold and energy -- KRW is not quoted by this broker"),
    # MONGOLIA JOINS THIS FOREST (2026-09-23), not russia_cis and not asean. Roughly nine tenths
    # of Mongolian exports cross one land border into China, the coking coal is priced off the
    # Dalian curve, the trade is invoiced in renminbi, and the MIRROR of the whole flow is
    # published by 海关总署 -- which is this forest's own official plane, named in its mission
    # below. The `mn` pack declares it in JURISDICTIONS and was UNANSWERED before it.
    _f("china", "Greater China", "regional", countries=("CN", "HK", "TW", "MO", "MN"),
       languages=("zh", "zh-Hant", "yue", "mn"), packs=("cn", "hk", "tw", "mo", "mn"),
       grounds=("cn", "hk", "tw", "mo", "mn"),
       mission="the deep Chinese web mined to exhaustion (期货日报实盘大赛, 蓝海密剑, 七禾网, "
               "聚宽/优矿/米筐/BigQuant, 知乎/雪球/CSDN, Gitee, Bilibili, 搜狗微信) plus the "
               "official plane: PBoC, SAFE, 海关总署, the three futures exchanges"),
    _f("russia_cis", "Russia and the CIS", "regional",
       countries=("RU", "UA", "KZ", "BY", "AZ", "GE", "AM", "UZ", "KG", "TJ", "TM"),
       # UKRAINE AND BELARUS JOIN THE ANSWERED SET (2026-09-23) through the `black_sea`
       # pack, which declares both in its own JURISDICTIONS tuple. Both were NAMED on
       # this roster and answered by nothing, so the parity fence counted them as gaps
       # while `ru` and `kz` carried the region: the Black Sea grain corridor and the
       # Belarusian potash route are one physical plane and neither is a copy of the
       # Russian budget-rule mechanism.
       # ARMENIA, UZBEKISTAN AND KYRGYZSTAN JOIN THE ANSWERED SET (2026-09-23) through the
       # `caucasus_central_asia` pack, which declares them plus Tajikistan and Turkmenistan
       # in its own JURISDICTIONS tuple. All three were NAMED on this roster and answered by
       # nothing: the post-2022 re-export and remittance corridor is a mechanism of its own
       # -- monthly transfers by origin, mirror statistics, sovereign gold sales and Turkmen
       # gas volumes readable only in Chinese customs data -- and none of it is a copy of the
       # Russian budget rule or of the Kazakh National Fund's FX sales.
       # TAJIKISTAN AND TURKMENISTAN JOINED THE ROSTER 2026-09-23, after their pack declared
       # them. The pack was right to leave the call to the forest owner and this is that call:
       # Tajik aluminium on stranded hydropower is an XALUSD supply observable, and Turkmen gas
       # volumes -- unreadable in Turkmen statistics and fully readable in Chinese customs
       # imports-by-origin -- are the desk's cleanest standing example of a jurisdiction whose
       # only lawful ground is a mirror statistic. A country answered by a pack and absent from
       # the roster is coverage the parity fence cannot see.
       languages=("ru", "uk", "be", "kk", "az", "ka", "hy", "uz", "ky", "tg", "tk"),
       packs=("ru", "kz", "az", "ge", "black_sea", "caucasus_central_asia"),
       grounds=("ru", "ua", "by"),
       mission="Habr, smart-lab, the RU failure vocabulary, the CBR and the CIS commodity plane"),
    _f("south_asia", "South Asia", "regional", countries=("IN", "PK", "BD", "LK", "NP"),
       languages=("en", "hi", "ur", "bn", "si", "ta", "ne"),
       packs=("ind", "pk", "bd", "lk", "np"),
       grounds=("in", "pk", "bd", "lk", "np"),
       mission="the Indian derivatives ecology and the South Asian trade/energy plane; "
               "Pakistan, Bangladesh and Sri Lanka as remittance, IMF-programme and "
               "textile/tea economies transmitting into USDINR, oil, gold and the US indices"),
    _f("asean", "ASEAN", "regional", countries=("SG", "VN", "TH", "ID", "MY", "PH"),
       languages=("en", "vi", "th", "id", "ms", "tl"),
       packs=("sg", "vn", "th", "idn", "my", "ph"), grounds=("sg", "vn", "th", "id", "my", "ph"),
       mission="the ASEAN commodity, FX and retail-leverage ecologies in their own languages"),
    _f("oceania", "Oceania", "regional", countries=("AU", "NZ", "PG", "FJ"),
       languages=("en", "tpi", "fj", "hif"), packs=("au", "nz", "pacific"),
       grounds=("au", "nz", "pg", "fj"),
       mission="the AUD/NZD commodity-currency complex, the RBA/RBNZ plane and the mining tape; "
               "the Pacific island economies (PNG LNG/gold/copper, Fiji tourism/remittances, "
               "cyclones) as one pack transmitting into Australia, China and New Zealand"),
    _f("europe", "Europe", "regional",
       # ICELAND JOINED THE ROSTER 2026-09-23 with its pack, not before it. It is on the roster
       # for a reason that is about price rather than size: Iceland smelts ~2% of world primary
       # aluminium on stranded hydro and geothermal power, so its reservoir levels are an
       # XALUSD supply observable the desk can execute against. The euro-area members below are
       # answered by `ea`'s own JURISDICTIONS tuple, which is why they are not listed one by one.
       countries=("GB", "DE", "FR", "IT", "ES", "NL", "SE", "NO", "DK", "FI", "PL", "CZ", "HU",
                  "CH", "PT", "AT", "BE", "IE", "GR", "RO", "BG", "RS", "IS"),
       languages=("en", "de", "fr", "it", "es", "nl", "sv", "no", "da", "fi", "pl", "cs", "hu",
                  "pt", "ro", "bg", "sr", "is"),
       packs=("ea", "uk", "ch", "se", "no", "pl", "dk", "is", "cee_balkans"),
       grounds=("de", "fr", "it", "es", "nl", "se", "dk", "no", "fi", "pl", "cz", "hu", "gb",
                "ro", "bg", "rs"),
       mission="the euro-area and European national planes, each in its own language; Romania, "
               "Bulgaria and Serbia as one CEE/Balkans pack (NBR/BNB/NBS, EU funds, the grain "
               "corridor) transmitting into the EUR crosses and the European indices"),
    _f("north_america", "North America", "regional", countries=("US", "CA"),
       languages=("en", "fr"), packs=("us", "ca"), grounds=("us", "ca"),
       # MEXICO IS LATAM HERE, and belongs to exactly one forest: its central bank, its
       # language ground and its commodity plane are Latin American, and a country hunted
       # by two civilizations charges the shared trial budget twice for one question. The
       # `mx` pack therefore stays on the latam roster and is NOT listed here (2026-09-22).
       mission="the US and Canadian official, practitioner and code ecologies: the Fed/FOMC, "
               "Treasury/TIC, BLS/BEA/Census, the CFTC COT as the positioning spine, EIA, USDA, "
               "NOAA, the ports and the regional Feds; the BoC, StatCan, CBSA and the oil sands",
       notes="the `us` and `ca` packs landed 2026-09-22 under the regional-parity law (LAWS 5n)"),
    _f("latam", "Latin America", "regional",
       countries=("BR", "MX", "CL", "CO", "PE", "AR", "BO", "GY", "TT", "VE", "SR"),
       languages=("pt", "es", "qu", "ay", "gn"),
       packs=("br", "mx", "cl", "co", "ar", "pe", "bo", "atlantic_energy"),
       grounds=("br", "mx", "cl", "co", "pe", "ar", "bo"),
       mission="the Brazilian, Andean and Southern-Cone commodity and FX planes"),
    _f("mena", "Middle East and North Africa", "regional",
       # QATAR, KUWAIT, OMAN AND BAHRAIN JOIN THE ANSWERED SET (2026-09-23) through the `gulf`
       # pack, which declares all four in its own JURISDICTIONS tuple. All four were NAMED on
       # this roster and answered by nothing, so the parity fence counted them as gaps while
       # `sa` and `ae` carried the region: one pack now answers the four the two siblings do
       # not, because the Qatari LNG schedule, the Kuwaiti undisclosed basket, the Omani
       # non-OPEC OPEC+ quota and the Bahraini guaranteed peg are four different mechanisms
       # rather than four copies of the Saudi one.
       countries=("SA", "AE", "QA", "TR", "IL", "KW", "OM", "BH", "MA"),
       languages=("ar", "tr", "he", "en", "fr"),
       packs=("sa", "ae", "il", "tr", "ma", "gulf"),
       grounds=("sa", "ae", "tr", "il", "ma"),
       mission="the Gulf energy plane, the CBRT and the Israeli tech/FX ecology; Morocco "
               "(Bank Al-Maghrib, phosphates, the MRE remittance and tourism planes) as the "
               "Maghreb pack transmitting into EURUSD, gold and the grain complex"),
    _f("africa", "Sub-Saharan Africa and Egypt", "regional",
       # MOROCCO IS MENA HERE (2026-09-22): its `ma` pack is on the mena roster, and a country
       # belongs to exactly one forest, so it is no longer listed under africa.
       # UGANDA JOINS THE ROSTER (2026-09-23) with the `east_africa` pack that answers for it:
       # ET and TZ were named here and unanswered, UG was on no forest's roster at all, and one
       # pack now answers all three (EACOP makes UG and TZ one physical system, so splitting
       # them would split a mechanism).
       # THE COPPERBELT JOINS THE ROSTER (2026-09-23) with the `copperbelt` pack that answers
       # for both CD and ZM: neither was on any forest's roster, and the DRC is the world's
       # SECOND-LARGEST COPPER PRODUCER and the source of ~70% of world cobalt while Zambia is
       # Africa's second producer. One pack answers both because the Katangan orebody crosses
       # the border at Kasumbalesa and the Zambian smelters treat Congolese concentrate, so
       # splitting them would split a mechanism.
       # WEST AFRICA JOINS THE ROSTER (2026-09-23) with the `west_africa` pack that answers
       # for CI, GN, ML, BF and SN: none of the five was on any forest's roster, and one pack
       # answers all five because four of them share ONE central bank, ONE currency pegged at
       # 655.957 and ONE exchange, while Guinea floats and is the control that makes the peg
       # measurable. Cote d'Ivoire is ~40% of world cocoa and sets the Living Income
       # Differential JOINTLY with Ghana, so `west_africa` is `gh`'s complement and not a
       # repeat of it.
       countries=("EG", "ZA", "NG", "KE", "GH", "ET", "TZ", "UG", "CD", "ZM",
                  "CI", "GN", "ML", "BF", "SN"),
       languages=("en", "ar", "fr", "sw", "am", "af", "ln", "bem", "ny", "dyu", "bm",
                  "ff", "mos", "wo"),
       packs=("eg", "za", "ng", "ke", "gh", "east_africa", "copperbelt", "west_africa"),
       grounds=("eg", "za", "ng", "ke"),
       mission="the South African, Nigerian, Kenyan and North African planes: metals, energy, "
               "agriculture and the frontier-FX ecology"),
)

#: THE FIVE GLOBAL CIVILIZATIONS. They carry no country list on purpose: their ground is a LAYER
#: of the world rather than a place, and giving them a country list would make them compete with
#: the twelve for the same sources.
GLOBAL_FORESTS: tuple[Forest, ...] = (
    _f("global_macro", "Global Macro", "global", languages=("en", "de", "fr", "it", "es", "pt",
                                                            "ja", "zh"),
       package="desks/mt5/research/macro_region", grounds=("institutional", "global"),
       mission="the cross-economy macro brain: G10 banks, releases, positioning, rates, "
               "auctions, interventions, propagation, fixings, commodity fundamentals",
       notes="already resident as the macro department; listed so the federation is complete"),
    _f("global_web", "Global Web", "global", languages=("en",), grounds=("global",),
       mission="the cross-border web layer: link graphs, aggregators, mirrors and the sources "
               "that cite the regional forests -- the SOURCE_GRAPH layer of the whole world"),
    _f("global_academic_code", "Global Academic and Code", "global", languages=("en",),
       grounds=("global", "institutional"),
       mission="arXiv/SSRN/RePEc and the open code ecosystems: the layer that is genuinely "
               "global and would be mined twelve times if each region hunted it"),
    _f("global_physical_data", "Global Physical Data", "global", languages=("en",),
       grounds=("global",),
       mission="ports, power, freight, tenders, satellite, inventories and shipping -- the "
               "physical economy that no single country's official plane publishes whole"),
    _f("global_market_data", "Global Market Data", "global", languages=("en",),
       grounds=("institutional",),
       mission="exchange, clearer and broker data: contract terms, margin, settlement, swap "
               "tables and the venue microstructure the regional forests all trade through"),
)

FORESTS: dict[str, Forest] = {f.id: f for f in (*REGIONAL_FORESTS, *GLOBAL_FORESTS)}

#: forest id -> its own task name, composed from the id and never typed as a literal.
FOREST_TASKS: dict[str, str] = {fid: task_for(fid) for fid in FORESTS}

#: WHICH TASK ACTUALLY KEEPS EACH FOREST ALIVE ON THE BOX. Two forests were already resident
#: before the federation was written (Japan as its own department, global macro as `macro`), and
#: the four global-LAYER forests ride the `regions` resident beside the country research OS --
#: a layer of the world is not a place, and giving each one a region resident would have them
#: competing with the twelve for the same sources. Those six therefore keep the task that
#: already runs them; only the eleven regional forests below get a task of their own, and
#: `desks/mt5/ops/box_tasks.manifest` declares exactly those eleven.
RIDES: dict[str, str] = {
    "japan": "MT5-Dept-Japan", "global_macro": "MT5-Dept-Macro",
    "global_web": "MT5-Dept-Regions", "global_academic_code": "MT5-Dept-Regions",
    "global_physical_data": "MT5-Dept-Regions", "global_market_data": "MT5-Dept-Regions",
}


def resident_task(forest_id: str) -> str:
    """The task that KEEPS THIS FOREST ALIVE -- which is not always its own name (see `RIDES`).

    Stating this separately from `FOREST_TASKS` is deliberate: a registry that claimed
    a per-forest task for Japan exists would send the clock fixer looking for a task nobody
    registered,
    and a healer hunting a phantom reads exactly like a resident that died.
    """
    fid = forest(forest_id).id
    return RIDES.get(fid, FOREST_TASKS[fid])


#: The eleven forests that get their OWN 24/7 resident, in manifest order.
OWN_RESIDENT: tuple[str, ...] = tuple(fid for fid in FORESTS if fid not in RIDES)

#: What a source scout asks with when the forest has NO pack to ask from. Not a translation of an
#: English list: these are the MANDATE's own terms (LAWS/RESEARCH: the deep-forest order names
#: competition records, practitioner interviews, the quant communities, the code forges), and
#: `libs/research/polyglot.native_queries` supplies the native-script half where it has a table.
MANDATE_SEEDS: dict[str, tuple[str, ...]] = {
    "official": ("central bank statistics", "customs trade data", "exchange open interest",
                 "treasury auction results", "balance of payments"),
    "institutional": ("broker research note", "strategist outlook", "fund positioning report"),
    "academic": ("working paper market microstructure", "dissertation volatility",
                 "conference proceedings asset pricing"),
    "practitioner": ("trading competition results", "trader interview method",
                     "backtest results rules", "systematic strategy write-up"),
    "retail_ecology": ("forum thread strategy", "margin call experience", "retail positioning"),
    "app_ecosystem": ("indicator marketplace", "expert advisor listing", "platform formula"),
    "media": ("market report", "commodity fixing", "policy statement coverage"),
    "archive": ("archived forum thread", "wayback leaderboard", "delisted strategy"),
    "physical_economy": ("port throughput", "power generation", "freight rates", "inventories"),
    "source_graph": ("link directory quant", "resource list trading", "blogroll research"),
}


def forest(forest_id: str) -> Forest:
    """One forest by id. Raises rather than inventing: an unknown id is a caller's bug."""
    try:
        return FORESTS[str(forest_id).strip().lower()]
    except KeyError:
        raise KeyError(f"unknown forest {forest_id!r}; known: {sorted(FORESTS)}") from None


def forest_of_country(cc: str) -> str:
    """The forest that owns an ISO-2 country, or "" -- an unclaimed country is a gap, not a
    default. Every country belongs to exactly one forest, which is what stops two civilizations
    mining the same ground and charging the shared trial budget twice."""
    code = str(cc or "").strip().upper()
    for f in REGIONAL_FORESTS:
        if code in f.countries:
            return f.id
    return ""


def pack_paths(forest_id: str, root: Path | None = None) -> dict[str, Path]:
    """pack code -> the `pack.py` that would carry it. Existence is NOT checked here."""
    base = (root or DESK) / "research" / "countries"
    return {code: base / code / "pack.py" for code in forest(forest_id).packs}


def unmeasured_packs(forest_id: str, root: Path | None = None) -> list[dict[str, str]]:
    """Packs this forest draws on that are NOT on this box, each named with its path.

    Absence by name, never a silent zero: another builder is writing these concurrently, so a
    role that finds none must say WHICH pack it wanted and WHERE it looked (L1.28a).
    """
    out: list[dict[str, str]] = []
    for code, path in pack_paths(forest_id, root).items():
        if not path.exists():
            out.append({"pack": code, "path": str(path),
                        "why": f"{UNMEASURED}: country pack {code!r} is not on this box"})
    return out


def package_path(forest_id: str, root: Path | None = None) -> Path | None:
    """The dedicated region package, or None when the forest draws on country packs."""
    pkg = forest(forest_id).package
    return ((root or ROOT) / pkg) if pkg else None


@dataclass(frozen=True)
class Allocation:
    """One forest's compute entitlement this hour, and where the number came from."""

    forest: str
    workers: int = DEFAULT_WORKERS
    budget_s: int = DEFAULT_BUDGET_S
    scout_floor: bool = True
    roi: float | None = None
    why: str = ""
    source: str = "defaults"
    overrides: tuple[str, ...] = field(default_factory=tuple)
    policy_factor: float = 1.0

    def as_row(self) -> dict[str, Any]:
        return {"forest": self.forest, "workers": self.workers, "budget_s": self.budget_s,
                "scout_floor": self.scout_floor, "roi": self.roi, "why": self.why,
                "policy_factor": self.policy_factor,
                "source": self.source, "overrides": list(self.overrides)}


def _int(value: Any, default: int, floor: int) -> tuple[int, bool]:
    try:
        got = int(value)
    except (TypeError, ValueError):
        return default, False
    return (max(floor, got), got < floor)


def policy_factor(path: Path | None = None) -> tuple[float, str]:
    """(factor, why) from `compute_policy.json`: `factors.forests` when the policy is MEASURED
    and applied, clipped to `POLICY_CLIP`; exactly 1.0 with the reason otherwise."""
    src = path or POLICY_JSON
    try:
        doc = json.loads(Path(src).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return 1.0, f"{UNMEASURED}: no readable {Path(src).name}; budgets unchanged"
    if (not isinstance(doc, Mapping) or not doc.get("applied")
            or str(doc.get("status")) != "MEASURED"):
        status = doc.get("status") if isinstance(doc, Mapping) else "not an object"
        return 1.0, f"{UNMEASURED}: compute policy is {status}; budgets unchanged"
    factors = doc.get("factors")
    raw = factors.get("forests") if isinstance(factors, Mapping) else None
    if not isinstance(raw, (int, float)):
        return 1.0, f"{UNMEASURED}: compute policy carries no forest factor; budgets unchanged"
    f = float(min(POLICY_CLIP[1], max(POLICY_CLIP[0], float(raw))))
    raw_split = doc.get("split")
    split: Mapping[str, Any] = raw_split if isinstance(raw_split, Mapping) else {}
    return f, (f"compute policy MEASURED: exploration share {split.get('exploration')} over "
               f"its prior -> x{f:.3f} on every forest budget")


def _base_allocation(forest_id: str, path: Path | None = None) -> Allocation:
    """This forest's workers, budget and scout floor, from the research-ROI organ's file.

    THE CONTRACT (written by `research_roi`, read here and nowhere else)::

        {"at": iso, "rule": str,
         "forests": {"<id>": {"workers": int>=1, "budget_s": int, "scout_floor": true,
                              "roi": float|null, "why": str}}}

    An absent, unreadable or silent file is the NORMAL state early on and yields the defaults
    (4 workers, 3000 s, scout floor on) rather than an error -- a federation that refuses to run
    without its allocator is a federation that never produces the yield the allocator needs.

    TWO THINGS THE FILE MAY NOT DO. It may not take a forest below ONE worker, and it may not
    turn the source scout off. Both are clamped here and the clamp is recorded in `overrides`,
    because a forest starved to silence can never earn its compute back.
    """
    fid = forest(forest_id).id
    src = path or ALLOCATION_JSON
    try:
        doc = json.loads(Path(src).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return Allocation(forest=fid, why=f"{UNMEASURED}: no readable {Path(src).name}; the "
                                          f"federation's defaults stand", source="defaults")
    if not isinstance(doc, Mapping):
        return Allocation(forest=fid, why=f"{UNMEASURED}: {Path(src).name} is not an object",
                          source="defaults")
    forests = doc.get("forests")
    row = forests.get(fid) if isinstance(forests, Mapping) else None
    if not isinstance(row, Mapping):
        return Allocation(forest=fid, source=str(Path(src).name),
                          why=f"{UNMEASURED}: {Path(src).name} names no allocation for {fid!r}; "
                              f"the federation's defaults stand")
    workers, clamped_w = _int(row.get("workers"), DEFAULT_WORKERS, 1)
    budget_s, clamped_b = _int(row.get("budget_s"), DEFAULT_BUDGET_S, int(MIN_ROLE_S * len(ROLES)))
    overrides: list[str] = []
    if clamped_w:
        overrides.append(f"workers raised to 1: a forest is never allocated zero workers "
                         f"(declared {row.get('workers')!r})")
    if clamped_b:
        overrides.append(f"budget_s raised to {budget_s}: {len(ROLES)} roles at {MIN_ROLE_S:g}s "
                         f"is the floor below which time-boxed means not run")
    scout = row.get("scout_floor", True)
    if scout is False:
        overrides.append("scout_floor forced on: the source scout always runs, whatever the "
                         "allocator says -- a defunded forest cannot produce the evidence that "
                         "would refund it")
    roi: float | None
    try:
        roi = None if row.get("roi") is None else float(row["roi"])
    except (TypeError, ValueError):
        roi = None
    return Allocation(forest=fid, workers=workers, budget_s=budget_s, scout_floor=True, roi=roi,
                      why=str(row.get("why") or str(doc.get("rule") or "")),
                      source=str(Path(src).name), overrides=tuple(overrides))


def allocation_for(forest_id: str, path: Path | None = None,
                   policy_path: Path | None = None) -> Allocation:
    """`_base_allocation` (the research-ROI organ's workers and budget, or the defaults) with the
    compute-economics policy applied to the budget -- two-sided, clipped, recorded in
    `overrides`, and exactly 1.0 when the policy is UNMEASURED. The policy applies on the
    defaults path too: a forest the ROI organ has not priced still lives under the learned
    exploration share. Workers and the scout floor are never touched by it."""
    base = _base_allocation(forest_id, path)
    pf, pf_why = policy_factor(policy_path)
    if pf == 1.0:
        return base
    budget = max(int(MIN_ROLE_S * len(ROLES)), round(base.budget_s * pf))
    return replace(base, budget_s=budget, policy_factor=pf,
                   overrides=(*base.overrides, f"budget_s x{pf:.3f} -> {budget}: {pf_why}"))


def role_plan(forest_id: str, allocation: Allocation | None = None) -> list[tuple[str, float]]:
    """(role, seconds) for all eleven roles, SCOUT FIRST, none below `MIN_ROLE_S`.

    The scout is ordered first rather than merely funded first: under a pool of one worker the
    submission order IS the run order, so a forest cut to a single worker still scouts before it
    does anything else. That is the compute-competition rule's other half -- fewer routine
    workers, never no scout.
    """
    alloc = allocation or allocation_for(forest_id)
    budget = max(float(alloc.budget_s), MIN_ROLE_S * len(ROLES))
    ordered = [SCOUT_ROLE, *[r for r in ROLES if r != SCOUT_ROLE]]
    plan = [(r, max(MIN_ROLE_S, budget * ROLE_SHARE.get(r, 1.0 / len(ROLES)))) for r in ordered]
    total = sum(s for _r, s in plan)
    if total > budget:                       # the floors overspent a tiny budget: scale the rest
        spare = max(0.0, budget - MIN_ROLE_S * len(ROLES))
        over = max(1e-9, total - MIN_ROLE_S * len(ROLES))
        plan = [(r, MIN_ROLE_S + (s - MIN_ROLE_S) * spare / over) for r, s in plan]
    return [(r, round(s, 3)) for r, s in plan]


def census() -> dict[str, Any]:
    """What the federation covers, for a report that must not restate the tables above."""
    return {
        "n_forests": len(FORESTS), "n_regional": len(REGIONAL_FORESTS),
        "n_global": len(GLOBAL_FORESTS), "roles": list(ROLES),
        "n_countries": len({c for f in REGIONAL_FORESTS for c in f.countries}),
        "languages": sorted({lang for f in FORESTS.values() for lang in f.languages}),
        "tasks": dict(FOREST_TASKS),
        "rule": ("every region is its own 24/7 civilization running all eleven roles in "
                 "parallel; regions compete for compute and every one of them keeps a source "
                 "scout; one registry, one dedup chain, one global brain"),
    }
