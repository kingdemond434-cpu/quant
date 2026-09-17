"""W4 -- THE SCOUT ROSTER: the desk's intelligence organs as ONE managed team, with beats.

THE GAP THIS CLOSES. The desk has forty-odd organs that read the outside world: a crawler that
grows its own frontier, a forest miner working five hundred declared grounds in twenty-six
languages, a frontier supervisor reading research organisations, academic and preprint readers,
competition and track-record miners, filing readers, dataset acquirers, broker-change watchers,
and two LLM seats. There has never been a ROSTER. Nothing anywhere says which organ covers which
ground, on which clock, at what cost, or what any of them ever produced -- so the only question a
desk can ask about an intelligence team, WHO IS COVERING WHAT AND WHO IS COVERING NOTHING, has
never had an answer. A ground with no scout then reads exactly like a ground that yielded nothing,
which is the absence-as-verdict failure the laws forbid (L1.28a).

A SCOUT IS FOUR THINGS AND THIS ORGAN MEASURES ALL FOUR. A BEAT (which grounds, languages, asset
classes and kinds it works), a CADENCE (the clock that actually fires it, read off the repo's own
clock files through `wiring_ceo`'s reader so the two can never disagree about what a clock is), a
MEASURED YIELD (leads -> testable -> cells -> certified, joined from the source registry, the
knowledge graph when one exists and the hypothesis graph when one does not), and a COST (wall
seconds from the compute ledger, API spend when anything records it -- nothing does today, and
that is published as UNMEASURED rather than as zero).

AN OPEN BEAT IS NAMED, NOT ASSUMED COVERED, AND A BEAT GOES OPEN TWO WAYS. Nobody claims it -- a
declared ground, language, kind or asset class on no scout's beat, or a DECLARED_BEAT with no
organ behind it. Or, and this is the one a paper roster hides, EVERY SCOUT THAT CLAIMS IT HAS
STOPPED FILING: measured on this box the declared coverage is 500/500 grounds and 26/26 languages,
and the number of those claimed by a scout still filing is far lower. Both kinds are listed, the
second with the names of the scouts that own it, and each carries the scout best placed to take
it -- chosen by MEASURED leads on grounds of the same kind then the same language, never a scout
with no measurement, which is a guess wearing a roster's clothes.

STATUS IS DERIVED FROM THE CLOCK THE SCOUT ACTUALLY HAS. Output inside one cadence is `active`;
inside two is `idle`; beyond two is `broken`. A scout with no clock, or with nowhere to leave an
artifact, is UNMEASURED -- which is a verdict about the wiring, not a pass mark. Measured while
this was written: `scripts/kimi_hunter.py` donates to `data/intelligence/kimi`, a directory that
has never been created, so the hourly LLM seat's whole output is unobservable from here.

IT STARTS AND STOPS NOTHING. This is a report. The wiring CEO acts on unwired organs, the bandit
allocates crawl budget, the promoter promotes; this one says who is on which beat and who is not.

    python desks/mt5/research/scout_roster.py [--dry-run] [--idle-days 3]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

GROUNDS = DESK / "data" / "deep_forest_sources.json"
REGISTRY = DESK / "data" / "source_registry.json"
KNOWLEDGE = DESK / "reports" / "KNOWLEDGE_GRAPH.json"
GRAPH = DESK / "data" / "hypothesis_graph.jsonl"
LEDGER = DESK / "data" / "compute_ledger.jsonl"
SPEND = ROOT / "data" / "panel_budget_state.json"
SEAT_ROOTS = (DESK / "data" / "intelligence", ROOT / "data" / "intelligence")
OUT = DESK / "reports" / "SCOUT_ROSTER.json"

#: Clock files `wiring_ceo.CLOCK_FILES` does not carry. `hourly_discovery` dispatches organs by
#: NAME out of a dict rather than importing them, so an organ reached only from there looks
#: unclocked to every reader that greps for imports -- `acquire_datasets` is exactly that case.
EXTRA_CLOCK_FILES: tuple[str, ...] = ("desks/mt5/research/hourly_discovery.py",)
#: The asset classes a beat can be declared over (the hypothesis lane's vocabulary plus the event
#: lane's share CFDs, which are traded but never hunted for statistical hypotheses).
ASSET_CLASSES: tuple[str, ...] = ("fx", "metals", "energy", "indices", "softs", "bonds",
                                  "crypto_cfd", "equity_cfd")
IDLE_DAYS = 3
#: Individual uncovered grounds listed by name before the tail is summarised as a count.
MAX_OPEN_GROUNDS = 40
_DUR = {"s": 1.0, "sec": 1.0, "m": 60.0, "min": 60.0, "h": 3600.0, "hour": 3600.0,
        "d": 86400.0, "day": 86400.0, "w": 604800.0, "week": 604800.0}


def _scout(name: str, organ: str, *, kinds: tuple[str, ...] = (),
           languages: tuple[str, ...] = ("*",), regions: tuple[str, ...] = ("*",),
           classes: tuple[str, ...] = ("*",), seats: tuple[str, ...] = (),
           artifacts: tuple[str, ...] = (), runs: tuple[str, ...] = (),
           note: str = "") -> dict[str, Any]:
    """One roster row. `kinds=()` means the scout works NO declared ground -- it grows its own --
    which is a beat, not a gap, and must never be scored as uncovered ground."""
    return {"name": name, "organ": organ, "kinds": kinds, "languages": languages,
            "regions": regions, "asset_classes": classes, "seats": seats,
            "artifacts": artifacts, "runs": runs, "note": note}


#: THE ROSTER, declared as data so a test can prove every organ on it exists. Kinds are the
#: grounds file's OWN vocabulary (`deep_forest_sources.json:grounds[].kind`), never a re-coining.
SCOUTS: tuple[dict[str, Any], ...] = (
    _scout("world_crawler", "desks/mt5/side_channels/world_crawler.py",
           seats=("world",), artifacts=("desks/mt5/reports/world_crawl.json",),
           runs=("world_crawler",),
           note="follows its own frontier: ground nobody declared, every language"),
    _scout("deep_forest_miner", "desks/mt5/research/deep_forest_miner.py",
           kinds=("forum", "column", "blog", "research", "community", "academic", "social",
                  "video", "competition", "qa", "code", "interview", "archive", "notebook"),
           artifacts=("desks/mt5/reports/DEEP_FOREST.json",
                      "desks/mt5/data/deep_forest_claims.jsonl"),
           runs=("deep_forest",), note="the declared practitioner forest, all regions, rotated"),
    _scout("acquire_datasets", "desks/mt5/research/acquire_datasets.py", kinds=("dataset",),
           artifacts=("desks/mt5/reports/dataset_acquisition.json",), runs=("acquire_datasets",),
           note="fetches, date-checks and registers the dataset grounds as primitives"),
    _scout("central_bank_miner", "desks/mt5/side_channels/central_bank_miner.py",
           kinds=("macro",), seats=("central_banks", "bis_speeches"),
           classes=("fx", "bonds", "metals"), note="central-bank communications and auctions"),
    _scout("repo_miner", "desks/mt5/research/repo_miner.py", kinds=("code", "notebook"),
           seats=("github", "github_topics"), artifacts=("desks/mt5/reports/REPO_MINER.json",),
           runs=("repo_miner",), note="watched repositories on GitHub and Gitee"),
    _scout("frontier_supervisor", "desks/mt5/frontier_intel/frontier_supervisor.py",
           kinds=("research",), regions=("institutional", "global"),
           seats=("frontier", "global_frontier"),
           artifacts=("desks/mt5/reports/FRONTIER_INTELLIGENCE.json",), runs=("frontier",),
           note="how the strongest research organisations find edges"),
    _scout("academic_miner", "desks/mt5/side_channels/academic_miner.py",
           kinds=("academic",), seats=("academic", "arxiv_qfin", "literature"),
           note="arXiv q-fin, SSRN and the journals: papers with a stated mechanism"),
    _scout("sec_edgar_miner", "desks/mt5/side_channels/sec_edgar_miner.py", regions=("us",),
           classes=("equity_cfd", "indices"), seats=("sec_edgar",),
           note="regulatory filings: the event lane's ground, never a hypothesis ground"),
    _scout("cot_miner", "desks/mt5/side_channels/cot_miner.py",
           classes=("fx", "metals", "energy", "indices", "softs"), seats=("cot",),
           note="CFTC positioning releases, lag-stamped at ingest"),
    _scout("swap_table_miner", "desks/mt5/side_channels/swap_table_miner.py",
           seats=("swap_table", "broker_swaps"),
           note="broker-change watcher: the financing the desk actually pays"),
    _scout("broker_physics_miner", "desks/mt5/side_channels/broker_physics_miner.py",
           seats=("amarkets", "fbs_tape", "litefinance"),
           note="broker-change watcher: spreads, hours and execution rules"),
    _scout("fxblue_track_record_miner", "desks/mt5/scripts/fxblue_track_record_miner.py",
           kinds=("competition",), seats=("fxblue",),
           note="published track records: a competition record with numbers and a method"),
    _scout("mql5_survivor_hunter", "desks/mt5/side_channels/mql5_survivor_hunter.py",
           kinds=("code",), seats=("mql5", "mql5_signals", "mql5_survivors"),
           note="MQL5 signals that survived, and the code behind them"),
    _scout("seed_miners", "desks/mt5/side_channels/seed_miners.py",
           seats=("darwinex", "collective2", "myfxbook_outlook", "propfirm_boards", "quant_se",
                  "forexpeacearmy", "forextsd_cdx", "ff_calendar_vintage", "tradingview_scripts"),
           note="the hourly seed sweep: twenty track-record and forum sources in one pass"),
    _scout("regional_survivor_hunters", "desks/mt5/side_channels/regional_survivor_hunters.py",
           regions=("br", "mx", "ar", "cl", "co", "pe", "za", "ng", "ke", "jp"),
           languages=("pt", "es", "ja"),
           seats=("regional_survivors", "trading_latam", "readitrades_africa", "minfx_jp"),
           note="regional track records: the world map the English sources do not reach"),
    _scout("china_miner", "desks/mt5/side_channels/china_miner.py", languages=("zh", "zh-Hant"),
           regions=("cn", "tw", "hk"), kinds=("column", "community"), seats=("china",),
           note="the Chinese ground the forest miner does not reach by route"),
    _scout("korea_miner", "desks/mt5/side_channels/korea_miner.py", languages=("ko",),
           regions=("kr",), kinds=("community",), seats=("korea",),
           note="Korean communities and disclosure"),
    _scout("asia_collector", "desks/mt5/research/asia_collector.py",
           languages=("ja", "ko", "zh", "zh-Hant"), regions=("jp", "kr", "cn", "tw", "hk"),
           kinds=("dataset",), seats=("asia", "asia_endpoints"), runs=("asia_collector",),
           note="the Asian data plane: endpoints, not prose"),
    _scout("youtube_corpus", "scripts/collect_youtube_corpus.py", kinds=("video",),
           seats=("youtube",), note="video transcripts: a stated rule said out loud"),
    _scout("kimi_hunter", "scripts/kimi_hunter.py", seats=("kimi",),
           note="LLM seat, free-tier chain, three waves; donates raw ore with zero authority"),
    _scout("deepseek_cycle", "scripts/run_deepseek_cycle.py", seats=("deepseek",),
           note="LLM seat, second flywheel: independent cold-phase findings, donated"),
    _scout("gpt_hunter", "scripts/gpt_hunter.py", seats=("scheduled_chatgpt",),
           note="LLM seat: practitioner corpus and scheduled hunts"),
    _scout("data_prospector", "desks/mt5/research/data_prospector.py", kinds=("dataset",),
           artifacts=("desks/mt5/reports/DATA_PROSPECTOR.json",), runs=("data_prospector",),
           note="which public dataset the desk is missing, priced by what it would decide"),
    _scout("unknown_unknowns", "desks/mt5/research/unknown_unknowns.py",
           artifacts=("desks/mt5/reports/UNKNOWN_UNKNOWNS.json",), runs=("exogenous_search",),
           note="the exogenous search: ground nobody has named yet"),
)


def _beat(beat: str, *organs: str, languages: tuple[str, ...] = ("*",),
          regions: tuple[str, ...] = ("*",), kinds: tuple[str, ...] = (),
          scope: str = "grounds") -> dict[str, Any]:
    return {"beat": beat, "organs": organs, "languages": languages, "regions": regions,
            "kinds": kinds, "scope": scope}


#: THE NINETEEN NAMED BEATS (principal 2026-09-16). Each names the organ(s) that cover it TODAY or
#: no organ at all, in which case it is OPEN and says so. An organ path here must exist: citing a
#: file that is not in the tree would make the roster's coverage number a claim the desk cannot
#: cash (L1.49), and the suite pins that.
DECLARED_BEATS: tuple[dict[str, Any], ...] = (
    _beat("ChinaScout", "desks/mt5/research/deep_forest_miner.py",
          "desks/mt5/side_channels/china_miner.py",
          languages=("zh", "zh-Hant"), regions=("cn", "tw", "hk")),
    _beat("JapanScout", "desks/mt5/research/deep_forest_miner.py",
          "desks/mt5/research/asia_collector.py", languages=("ja",), regions=("jp",)),
    _beat("KoreaScout", "desks/mt5/research/deep_forest_miner.py",
          "desks/mt5/side_channels/korea_miner.py", languages=("ko",), regions=("kr",)),
    _beat("IndiaScout", "desks/mt5/research/deep_forest_miner.py",
          languages=("hi", "en"), regions=("in",)),
    _beat("RussiaScout", "desks/mt5/research/deep_forest_miner.py",
          languages=("ru",), regions=("ru",)),
    _beat("ArabicScout", "desks/mt5/research/deep_forest_miner.py",
          languages=("ar",), regions=("sa", "ae", "eg", "ma", "il")),
    _beat("LatAmScout", "desks/mt5/research/deep_forest_miner.py",
          "desks/mt5/side_channels/regional_survivor_hunters.py",
          languages=("pt", "es"), regions=("br", "mx", "ar", "cl", "co", "pe")),
    _beat("AcademicScout", "desks/mt5/side_channels/academic_miner.py",
          "desks/mt5/side_channels/world_frontier.py",
          "desks/mt5/frontier_intel/frontier_supervisor.py", kinds=("academic", "research")),
    _beat("GitHubScout", "desks/mt5/research/repo_miner.py",
          "desks/mt5/side_channels/github_miner.py", kinds=("code", "notebook")),
    _beat("GiteeScout", "desks/mt5/research/repo_miner.py",
          kinds=("code", "notebook"), languages=("zh",), regions=("cn",)),
    _beat("GovernmentDataScout", "desks/mt5/side_channels/sec_edgar_miner.py",
          "desks/mt5/research/acquire_datasets.py", "desks/mt5/research/fetch_fred.py",
          kinds=("dataset",)),
    _beat("CentralBankScout", "desks/mt5/side_channels/central_bank_miner.py",
          "desks/mt5/side_channels/bis_speech_tone.py", "desks/mt5/research/cb_tone_screen.py",
          kinds=("macro",)),
    _beat("ExchangeScout", "desks/mt5/research/fetch_futures_curves.py",
          "desks/mt5/research/fetch_sge_premium.py",
          "desks/mt5/side_channels/broker_physics_miner.py", scope="internal"),
    _beat("MQL5Scout", "desks/mt5/side_channels/mql5_survivor_hunter.py",
          "desks/mt5/side_channels/mql5_signals.py", scope="internal"),
    _beat("DarwinexScout", "desks/mt5/side_channels/seed_miners.py", scope="internal"),
    _beat("ForumScout", "desks/mt5/research/deep_forest_miner.py",
          "desks/mt5/side_channels/forexfactory_miner.py",
          "desks/mt5/side_channels/reddit_miner.py",
          kinds=("forum", "qa", "community", "social")),
    _beat("CompetitionScout", "desks/mt5/research/deep_forest_miner.py",
          "desks/mt5/scripts/fxblue_track_record_miner.py", kinds=("competition",)),
    _beat("FailureScout", "desks/mt5/research/negative_knowledge.py",
          "desks/mt5/research/residual_queue.py", "desks/mt5/research/conversion_ledger.py",
          scope="internal"),
    _beat("DatasetScout", "desks/mt5/research/value_of_data.py",
          "desks/mt5/research/data_prospector.py", "desks/mt5/research/acquire_datasets.py",
          kinds=("dataset",)),
)

#: THE NINE SPECIALIST ROLES. Not beats: these are the jobs a lead passes through on its way from
#: a sentence on a forum to a judged cell. Mapped to the organ that already does the job, or OPEN.
SPECIALISTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("MechanismExtractor", ("libs/research/mechanism_claims.py",
                            "desks/mt5/research/deep_forest_miner.py")),
    ("NoveltyJudge", ("desks/mt5/research/novelty_gate.py",)),
    ("CrossAssetMapper", ("desks/mt5/research/cross_asset_graph.py",
                          "desks/mt5/research/world_causal_graph.py")),
    ("FusionMapper", ("libs/research/mechanism_claims.py",
                      "desks/mt5/research/universe_policy.py")),
    ("PITAuditor", ("desks/mt5/research/pit_audit.py", "scripts/check_pit_canaries.py")),
    ("DataScout", ("desks/mt5/research/data_prospector.py",
                   "desks/mt5/research/data_axis_miner.py",
                   "desks/mt5/research/acquire_datasets.py")),
    ("CostJudge", ("desks/mt5/research/cost_surface.py", "desks/mt5/research/cost_honesty.py",
                   "desks/mt5/research/cost_to_edge.py")),
    ("Falsifier", ("desks/mt5/research/falsifier_run.py",
                   "desks/mt5/research/placebo_test.py")),
    ("CandidateCompiler", ("desks/mt5/research/miner_candidate_compiler.py",)),
)


# ------------------------------------------------------------------------------- small readers

def _read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return default


def _atomic(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, ensure_ascii=False, indent=1, default=str)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        try:
            os.replace(tmp, path)
        except PermissionError:
            # A read-only destination raises WinError 5 on the box and nothing on POSIX. The desk
            # has lost a fix to exactly this before; write through rather than die.
            path.write_text(text, encoding="utf-8")
            Path(tmp).unlink(missing_ok=True)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=UTC).isoformat(timespec="seconds")


def _parse(at: str | None) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(at))
    except (TypeError, ValueError):
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def grounds() -> list[dict[str, Any]]:
    doc = _read_json(GROUNDS, {}) or {}
    return [g for g in (doc.get("grounds") or []) if isinstance(g, dict)]


# ---------------------------------------------------------------------------- clocks, cadences

def _field(spec: str, span: int) -> int:
    """How many times one systemd OnCalendar field fires per cycle."""
    spec = spec.strip()
    if not spec or spec == "*":
        return span
    m = re.fullmatch(r"(?:\*|\d+)/(\d+)", spec)
    if m:
        return max(1, span // max(1, int(m.group(1))))
    return max(1, len([x for x in spec.split(",") if x]))


def _duration(text: str) -> float | None:
    m = re.fullmatch(r"(\d+)\s*(s|sec|m|min|h|hour|d|day|w|week)s?", text.strip().lower())
    return float(m.group(1)) * _DUR[m.group(2)] if m else None


def cadence_of_oncalendar(value: str) -> float | None:
    """Seconds between fires, from a systemd `OnCalendar=`. Unparseable is None, never a guess."""
    v = re.sub(r"\s+(?:UTC|utc)$", "", value.strip())
    for word, secs in (("minutely", 60.0), ("hourly", 3600.0), ("daily", 86400.0),
                       ("weekly", 604800.0), ("monthly", 2592000.0)):
        if v.lower() == word:
            return secs
    parts = v.split()
    time_part = parts[-1] if parts else v
    if ":" not in time_part:
        return None
    fields = time_part.split(":")
    cadence = 86400.0 / max(1, _field(fields[0], 24) * _field(fields[1], 60))
    if len(parts) > 1 and re.match(r"^[A-Za-z]{3}", parts[0]):
        cadence *= 7.0 / max(1, len(parts[0].split(",")))
    return cadence


def cadence_of_trigger(trigger: str) -> float | None:
    """Seconds between fires, from a `box_tasks.manifest` trigger phrase. UNDECLARED is None --
    the manifest says in its own header that nobody here may invent a cadence."""
    t = trigger.strip().lower()
    if not t or "undeclared" in t or "startup" in t or "continuous" in t:
        return None
    m = re.search(r"every\s+(\d+)?\s*(minute|min|hour|day)", t)
    if m:
        return float(m.group(1) or 1) * {"minute": 60.0, "min": 60.0, "hour": 3600.0,
                                         "day": 86400.0}[m.group(2)]
    for word, secs in (("hourly", 3600.0), ("daily", 86400.0), ("weekly", 604800.0)):
        if word in t:
            return secs
    return None


def clock_texts() -> dict[str, str]:
    """REUSE, NOT A SECOND OPINION. `wiring_ceo._clock_texts` is the repo's definition of what a
    clock file is (the two cycles, the box manifest, the crontab manifest, every unit and wrapper
    under ops/ and desks/mt5/scripts). A private reader, imported deliberately: a roster that
    disagreed with the wiring CEO about whether an organ is clocked would be worse than no roster.
    """
    out: dict[str, str] = {}
    try:
        import wiring_ceo
        out.update(dict(wiring_ceo._clock_texts()))
    except Exception:                                    # a reader is never fatal
        out = {}
    for rel in EXTRA_CLOCK_FILES:
        p = ROOT / rel
        if rel not in out and p.is_file():
            try:
                out[rel] = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
    return out


def clock_index() -> list[dict[str, Any]]:
    """Every clock the repo declares, as (label, cadence, searchable text).

    ONE HOP THROUGH THE WRAPPER, because a systemd unit almost never names the organ: it names an
    `ops/*.sh` that does. `quant-deepseek.timer` -> `quant-deepseek.service` ->
    `ops/run_deepseek_factory.sh` -> `scripts/run_deepseek_cycle.py` is three links, and a reader
    that stopped at the unit would report the desk's second LLM seat as unclocked.
    """
    texts = clock_texts()
    out: list[dict[str, Any]] = []
    for rel, secs in (("desks/mt5/research/hourly_cycle.py", 3600.0),
                      ("desks/mt5/research/daily_cycle.py", 86400.0),
                      ("desks/mt5/research/hourly_discovery.py", 3600.0)):
        if rel in texts:
            out.append({"clock": rel, "cadence_s": secs, "blob": texts[rel]})
    for line in texts.get("desks/mt5/ops/box_tasks.manifest", "").splitlines():
        if not line.startswith("TASK "):
            continue
        name = re.search(r'name="([^"]*)"', line)
        trig = re.search(r'trigger="([^"]*)"', line)
        out.append({"clock": f"box:{name.group(1) if name else '?'}",
                    "cadence_s": cadence_of_trigger(trig.group(1) if trig else ""), "blob": line})
    for rel, text in texts.items():
        if not rel.endswith(".timer"):
            continue
        cadence = None
        for line in text.splitlines():
            key, _, val = line.partition("=")
            k = key.strip().lower()
            if k == "oncalendar":
                cadence = cadence_of_oncalendar(val) or cadence
            elif k in ("onunitactivesec", "onbootsec") and cadence is None:
                cadence = _duration(val)
        blob = text + texts.get(rel[:-6] + ".service", "")
        for script in set(re.findall(r"[\w./-]+\.(?:sh|cmd|ps1)", blob)):
            blob += texts.get(script.lstrip("./"), "") + texts.get("ops/" + Path(script).name, "")
        out.append({"clock": rel, "cadence_s": cadence, "blob": blob})
    return out


def clock_of(organ: str, index: list[dict[str, Any]]) -> tuple[str | None, float | None]:
    """The tightest clock that names this organ, by path, basename, `-m` form or bare stem."""
    stem = Path(organ).stem
    needles = (organ, organ.replace("/", "\\"), Path(organ).name)
    mods = (f"-m {stem}", f"import {stem}", f'"{stem}"', f"'{stem}'", f"research.{stem}",
            f"side_channels.{stem}", f"frontier_intel.{stem}", f"scripts.{stem}")
    hits = [e for e in index
            if any(n in e["blob"] for n in needles) or any(m in e["blob"] for m in mods)]
    if not hits:
        return None, None
    timed = [e for e in hits if e["cadence_s"]]
    best = min(timed, key=lambda e: float(e["cadence_s"])) if timed else hits[0]
    return str(best["clock"]), best["cadence_s"]


# -------------------------------------------------------------------------- beats and the join

def _wants(want: tuple[str, ...], value: Any) -> bool:
    return bool(want) and ("*" in want or str(value or "") in want)


def claims(scout: dict[str, Any], ground: dict[str, Any]) -> bool:
    """Does this scout's beat cover this ground? A scout declaring no kinds claims none: it grows
    its own frontier, and crediting it with declared ground it never visits would hide a gap."""
    return (_wants(scout["kinds"], ground.get("kind"))
            and _wants(scout["languages"], ground.get("language"))
            and _wants(scout["regions"], ground.get("region")))


def registry_sources() -> dict[str, dict[str, Any]]:
    doc = _read_json(REGISTRY, {}) or {}
    src = doc.get("sources")
    return src if isinstance(src, dict) else {}


def cells_by_source(sources: dict[str, dict[str, Any]]) -> tuple[dict[str, int], str]:
    """Distinct judged CELLS per registry source. The knowledge graph owns this when it exists;
    it does not exist today, so the hypothesis graph's `region` -- which IS the cell key -- is the
    fallback, and the basis says which one answered. Absence of both is UNMEASURED, never 0."""
    doc = _read_json(KNOWLEDGE, None)
    if isinstance(doc, dict):
        block = doc.get("by_source")
        if isinstance(block, dict):
            out = {}
            for k, v in block.items():
                n = v.get("cells", v.get("n_cells")) if isinstance(v, dict) else v
                if isinstance(n, (int, float)) and not isinstance(n, bool):
                    out[str(k)] = int(n)
            if out:
                return out, "reports/KNOWLEDGE_GRAPH.json:by_source"
    alias: dict[str, str] = {}
    for sid, row in sources.items():
        alias.setdefault(sid, sid)
        for a in row.get("aliases") or []:
            alias.setdefault(str(a), sid)
    seen: dict[str, set[str]] = {}
    try:
        with Path(GRAPH).open(encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                sid = alias.get(str(row.get("source") or ""))
                if sid and row.get("region"):
                    seen.setdefault(sid, set()).add(str(row["region"]))
    except OSError:
        return {}, "UNMEASURED -- no knowledge graph and no hypothesis graph on disk"
    return ({k: len(v) for k, v in seen.items()},
            "data/hypothesis_graph.jsonl: distinct `region` per source (KNOWLEDGE_GRAPH absent)")


def sources_of(scout: dict[str, Any], sources: dict[str, dict[str, Any]],
               claimed: set[str]) -> list[str]:
    """Registry rows this scout owns: the grounds its beat claims, plus its own seat directories."""
    out = [sid for sid, row in sources.items() if str(row.get("ground") or "") in claimed]
    out += [f"seat:{s}" for s in scout["seats"] if f"seat:{s}" in sources]
    return sorted(set(out))


def _last_output(scout: dict[str, Any]) -> tuple[str | None, str]:
    """When this scout last left something on disk: newest donation in any of its seat
    directories, or newest of its declared artifacts. A declared seat directory that does not
    exist is NAMED -- the kimi seat's donation directory has never been created."""
    times: list[float] = []
    missing: list[str] = []
    for seat in scout["seats"]:
        found = False
        for root in SEAT_ROOTS:
            d = Path(root) / seat
            try:
                with os.scandir(d) as it:
                    for e in it:
                        if e.is_file() and e.name.endswith((".json", ".jsonl")):
                            found = True
                            times.append(e.stat().st_mtime)
            except OSError:
                continue
        if not found:
            missing.append(seat)
    for rel in scout["artifacts"]:
        p = ROOT / rel
        if p.is_file():
            times.append(p.stat().st_mtime)
    basis = ("seat donations and declared artifacts" if times else
             "NO OUTPUT PATH ON DISK: " + (", ".join(missing) or "no seat, no artifact declared"))
    return (_iso(max(times)) if times else None), basis


def status_of(cadence_s: float | None, last_at: str | None, now: datetime) -> str:
    """active inside one cadence, idle inside two, broken beyond two. No clock or no observable
    output is UNMEASURED -- a verdict about the wiring, never a pass mark."""
    at = _parse(last_at)
    if not cadence_s or at is None:
        return "UNMEASURED"
    age = (now - at).total_seconds()
    if age <= float(cadence_s):
        return "active"
    return "idle" if age <= 2.0 * float(cadence_s) else "broken"


_KIND_MAP: dict[str, str] | None = None


def registry_kind(raw: Any) -> str:
    """A ground declares `interview`; the source registry files it as `web`. Compare like with
    like by going through the REGISTRY'S OWN map -- a second vocabulary coined here would make
    every similarity lookup miss silently, which reads as "no similar ground" and is a lie."""
    global _KIND_MAP
    if _KIND_MAP is None:
        try:
            from source_registry import KIND_MAP
            _KIND_MAP = dict(KIND_MAP)
        except Exception:                                # a reader is never fatal
            _KIND_MAP = {}
    return _KIND_MAP.get(str(raw or ""), str(raw or ""))


def best_scout(kind: str | None, language: str | None, rows: list[dict[str, Any]],
               ground_only: bool = False) -> tuple[str | None, str]:
    """Who should take an open beat: the scout with the most MEASURED leads on grounds of the same
    kind, then the same language, then the most leads anywhere. A scout with no measurement is
    never proposed -- an assignment made on no evidence is a guess wearing a roster's clothes.

    `ground_only` restricts the pool to scouts that already work DECLARED GROUND. Without it the
    highest-volume seat-only scout wins every open beat: measured here, `swap_table_miner` (1,397
    broker-swap leads, zero grounds) was proposed for the Arabic and Korean forests."""
    pool = [r for r in rows
            if not ground_only or int((r.get("beat") or {}).get("n_grounds") or 0) > 0]
    for key, want, why in (("by_kind", registry_kind(kind), "kind"),
                           ("by_lang", language, "language")):
        if not want:
            continue
        ranked = [(float(r[key].get(want, 0) or 0), r["name"]) for r in pool]
        ranked = [t for t in ranked if t[0] > 0]
        if ranked:
            top = max(ranked)
            return top[1], f"most measured leads on grounds of the same {why} ({top[0]:.0f})"
    ranked = [(float(r["yield"]["leads"] or 0), r["name"]) for r in pool
              if (r["yield"]["leads"] or 0) > 0]
    if ranked:
        top = max(ranked)
        return top[1], (f"most measured leads anywhere ({top[0]:.0f}); none on a similar ground"
                        + (" among the scouts that work declared ground" if ground_only else ""))
    return None, "UNMEASURED -- no scout has a measured lead to place this beat on"


# --------------------------------------------------------------------------------- the roster

def _beat_status(beat: dict[str, Any], clocked: dict[str, float | None],
                 covered: set[str], gs: list[dict[str, Any]]) -> tuple[str, str]:
    present = [o for o in beat["organs"] if (ROOT / o).is_file()]
    if not present:
        return "OPEN", ("no organ in this tree covers this beat"
                        if beat["organs"] else "declared with no organ")
    on_clock = [o for o in present if clocked.get(o)]
    if not on_clock:
        return "PARTIAL", f"{len(present)} organ(s) exist, none on a clock this repo declares"
    if beat["scope"] == "internal":
        return "COVERED", f"{len(on_clock)} organ(s) on a clock; no external ground to cover"
    mine = [g for g in gs if _wants(beat["languages"], g.get("language"))
            and _wants(beat["regions"], g.get("region"))
            and (not beat["kinds"] or _wants(beat["kinds"], g.get("kind")))]
    if not mine:
        return "PARTIAL", "organ(s) on a clock, but no declared ground matches this beat's axis"
    hit = sum(1 for g in mine if str(g.get("name")) in covered)
    if hit == len(mine):
        return "COVERED", f"{len(on_clock)} organ(s) on a clock; all {hit} ground(s) claimed"
    return "PARTIAL", f"{hit}/{len(mine)} ground(s) on this axis are claimed by a roster scout"


def build(idle_days: float = IDLE_DAYS) -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    gs, sources = grounds(), registry_sources()
    cells, cells_basis = cells_by_source(sources)
    index = clock_index()
    try:
        from libs.ops.compute_ledger import cost_by_run
        costs, cost_basis = cost_by_run(path=LEDGER), "libs/ops/compute_ledger.cost_by_run"
    except Exception as exc:                             # a reader is never fatal
        costs, cost_basis = {}, f"UNMEASURED -- compute ledger unreadable ({type(exc).__name__})"

    rows: list[dict[str, Any]] = []
    covered: set[str] = set()
    live: set[str] = set()
    owners: dict[str, list[str]] = {}
    for sc in SCOUTS:
        mine = [g for g in gs if claims(sc, g)]
        names = {str(g.get("name")) for g in mine}
        covered |= names
        clock, cadence = clock_of(sc["organ"], index)
        last_at, last_basis = _last_output(sc)
        sids = sources_of(sc, sources, names)
        by_kind: dict[str, float] = {}
        by_lang: dict[str, float] = {}
        tally = dict.fromkeys(("leads", "testable", "certified"), 0)
        for sid in sids:
            row = sources[sid]
            n = int(row.get("n_leads") or 0)
            tally["leads"] += n
            tally["testable"] += int(row.get("n_testable") or 0)
            tally["certified"] += int(row.get("n_certified") or 0)
            by_kind[str(row.get("kind"))] = by_kind.get(str(row.get("kind")), 0.0) + n
            by_lang[str(row.get("language"))] = by_lang.get(str(row.get("language")), 0.0) + n
        cost_s = sum(float(costs[r]["wall_s"]) for r in sc["runs"] if r in costs) or None
        # A BEAT IS ONLY COVERED WHILE ITS SCOUT IS STILL FILING. A ground claimed only by organs
        # that are broken or on no clock is NOT a covered ground -- reading it as one is how a
        # roster turns a dead beat into a green number, which is the whole failure this organ
        # exists to prevent. `live` is the set that a still-reporting scout claims.
        if status_of(cadence, last_at, now) in ("active", "idle"):
            live |= names
        for g in names:
            owners.setdefault(g, []).append(sc["name"])
        rows.append({
            "name": sc["name"], "organ_file": sc["organ"], "note": sc["note"],
            "beat": {"grounds": sorted(names)[:12], "n_grounds": len(names),
                     "languages": list(sc["languages"]),
                     "asset_classes": list(sc["asset_classes"]),
                     "kinds": list(sc["kinds"]), "regions": list(sc["regions"])},
            "clock": clock, "cadence_s": cadence, "last_output_at": last_at,
            "last_output_basis": last_basis,
            "status": status_of(cadence, last_at, now),
            "yield": {"leads": tally["leads"], "testable": tally["testable"],
                      "cells": sum(int(cells.get(s, 0)) for s in sids) if cells else None,
                      "certified": tally["certified"]},
            "cost_s": round(cost_s, 2) if cost_s else None,
            "leads_per_hour": (round(tally["leads"] / (cost_s / 3600.0), 3)
                               if cost_s else None),
            "n_sources": len(sids), "by_kind": by_kind, "by_lang": by_lang,
        })

    clocked = {r["organ_file"]: r["cadence_s"] for r in rows}
    for beat in DECLARED_BEATS:
        for organ in beat["organs"]:
            clocked.setdefault(organ, clock_of(organ, index)[1])
    declared = []
    for beat in DECLARED_BEATS:
        status, why = _beat_status(beat, clocked, covered, gs)
        declared.append({"beat": beat["beat"], "organs": list(beat["organs"]),
                         "organs_missing": [o for o in beat["organs"] if not (ROOT / o).is_file()],
                         "scope": beat["scope"], "status": status, "why": why})
    specialists = []
    for role, organs in SPECIALISTS:
        present = [o for o in organs if (ROOT / o).is_file()]
        on_clock = [o for o in present if clocked.setdefault(o, clock_of(o, index)[1])]
        specialists.append({"role": role, "organs": list(organs), "organs_present": present,
                            "status": ("OPEN" if not present else
                                       "COVERED" if on_clock else "PARTIAL")})

    opens = open_beats(gs, covered, live, owners, rows, declared)
    flags = idle_flags(rows, now, idle_days)
    ages = np.array([(now - _parse(r["last_output_at"])).total_seconds() / 86400.0
                     for r in rows if _parse(r["last_output_at"])], dtype=float)
    langs = {str(g.get("language")) for g in gs if g.get("language")}
    langs_covered = {str(g.get("language")) for g in gs
                     if g.get("language") and str(g.get("name")) in covered}
    langs_live = {str(g.get("language")) for g in gs
                  if g.get("language") and str(g.get("name")) in live}
    classes = {c for sc in SCOUTS for c in sc["asset_classes"] if c != "*"}
    any_star = any("*" in sc["asset_classes"] for sc in SCOUTS)
    return {
        "at": now.isoformat(timespec="seconds"), "n_scouts": len(rows), "scouts": rows,
        "open_beats": opens, "idle_flags": flags,
        "declared_beats": declared, "specialists": specialists,
        "coverage": {
            "grounds_covered": len(covered), "grounds_total": len(gs),
            "grounds_covered_live": len(live),
            "languages_covered": len(langs_covered), "languages_total": len(langs),
            "languages_covered_live": len(langs_live),
            "live_note": ("`_live` counts only what a scout that is still filing claims; the "
                          "plain count is what the roster claims on paper, and the gap between "
                          "them is the beat the desk THINKS it covers"),
            "asset_classes_covered": len(ASSET_CLASSES) if any_star else len(classes),
            "asset_classes_total": len(ASSET_CLASSES),
            "beats_covered": sum(1 for b in declared if b["status"] == "COVERED"),
            "beats_total": len(declared),
            "median_days_since_output": round(float(np.median(ages)), 3) if ages.size else None,
        },
        "status_census": {s: sum(1 for r in rows if r["status"] == s)
                          for s in ("active", "idle", "broken", "UNMEASURED")},
        "unmeasured": {
            "cells_basis": cells_basis, "cost_basis": cost_basis,
            "api_spend": ("UNMEASURED -- no per-seat spend is recorded anywhere; "
                          f"{SPEND.name} is absent, so an LLM seat's cost is its wall seconds "
                          "only and must never be read as free"),
            "n_scouts_without_a_clock": sum(1 for r in rows if not r["cadence_s"]),
            "n_scouts_without_output": sum(1 for r in rows if not r["last_output_at"]),
            "n_scouts_uncosted": sum(1 for r in rows if r["cost_s"] is None),
            "n_beats_open": sum(1 for b in declared if b["status"] == "OPEN"),
            "n_specialists_open": sum(1 for s in specialists if s["status"] == "OPEN"),
        },
        "rule": ("every scout has a beat, a clock, a measured yield and a cost; an open beat is "
                 "named, not assumed covered"),
    }


def _axis_rows(axis: str, buckets: dict[str, list[dict[str, Any]]], covered: set[str],
               live: set[str], owners: dict[str, list[str]],
               rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per axis value nobody is working, in either of the two ways a beat goes open: no
    scout claims it at all, or every scout that claims it has stopped filing. The second is the
    one a paper roster hides, so it is reported with the names of the scouts that own it."""
    out: list[dict[str, Any]] = []
    for value, items in sorted(buckets.items()):
        names = [str(g.get("name")) for g in items]
        kind = str(items[0].get("kind"))
        lang = value if axis == "lang" else str(items[0].get("language"))
        if not any(n in covered for n in names):
            who, basis = best_scout(kind, lang, rows, ground_only=True)
            out.append({"ground_or_axis": f"{axis}:{value}", "n_grounds": len(items),
                        "why_open": f"{len(items)} declared ground(s), none claimed by any scout",
                        "current_scouts": [], "best_scout": who, "best_scout_basis": basis})
        elif not any(n in live for n in names):
            dead = sorted({s for n in names for s in owners.get(n, [])})
            who, basis = best_scout(kind, lang, rows, ground_only=True)
            out.append({"ground_or_axis": f"{axis}:{value}", "n_grounds": len(items),
                        "why_open": (f"{len(items)} declared ground(s) claimed only by scouts "
                                     "that are broken or on no clock this repo declares: "
                                     + ", ".join(dead)),
                        "current_scouts": dead, "best_scout": who, "best_scout_basis": basis})
    return out


def open_beats(gs: list[dict[str, Any]], covered: set[str], live: set[str],
               owners: dict[str, list[str]], rows: list[dict[str, Any]],
               declared: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every axis nobody is working: a declared beat with no organ, a language or kind whose
    grounds no LIVE scout claims, an asset class no scout names, and the unclaimed grounds."""
    out: list[dict[str, Any]] = []
    for beat in declared:
        if beat["status"] != "OPEN":
            continue
        who, why = best_scout(None, None, rows)
        out.append({"ground_or_axis": f"beat:{beat['beat']}", "why_open": beat["why"],
                    "current_scouts": [], "best_scout": who, "best_scout_basis": why})
    by_lang: dict[str, list[dict[str, Any]]] = {}
    by_kind: dict[str, list[dict[str, Any]]] = {}
    for g in gs:
        by_lang.setdefault(str(g.get("language") or "UNDECLARED"), []).append(g)
        by_kind.setdefault(str(g.get("kind") or "UNDECLARED"), []).append(g)
    out += _axis_rows("lang", by_lang, covered, live, owners, rows)
    out += _axis_rows("kind", by_kind, covered, live, owners, rows)
    named = {c for sc in SCOUTS for c in sc["asset_classes"]}
    if "*" not in named:
        for klass in ASSET_CLASSES:
            if klass not in named:
                who, why = best_scout(None, None, rows)
                out.append({"ground_or_axis": f"class:{klass}", "current_scouts": [],
                            "why_open": "no scout on the roster names this asset class",
                            "best_scout": who, "best_scout_basis": why})
    loose = sorted((g for g in gs if str(g.get("name")) not in covered),
                   key=lambda g: -float(g.get("weight") or 0.0))
    for g in loose[:MAX_OPEN_GROUNDS]:
        who, why = best_scout(str(g.get("kind")), str(g.get("language")), rows, ground_only=True)
        out.append({"ground_or_axis": str(g.get("name")), "current_scouts": [],
                    "why_open": (f"declared ground (kind={g.get('kind')}, "
                                 f"language={g.get('language')}, region={g.get('region')}) "
                                 "claimed by no scout's beat"),
                    "best_scout": who, "best_scout_basis": why})
    if len(loose) > MAX_OPEN_GROUNDS:
        out.append({"ground_or_axis": f"+{len(loose) - MAX_OPEN_GROUNDS} more unclaimed grounds",
                    "why_open": "listed by weight; the tail is counted, never dropped",
                    "current_scouts": [], "best_scout": None,
                    "best_scout_basis": "see the named rows above"})
    return out


def idle_flags(rows: list[dict[str, Any]], now: datetime, idle_days: float) -> list[dict[str, Any]]:
    """A scout whose beat produced nothing recently, with what the silence cost in leads."""
    out = []
    for r in rows:
        at = _parse(r["last_output_at"])
        days = (now - at).total_seconds() / 86400.0 if at else None
        if (days is None or days < idle_days) and r["yield"]["leads"] > 0:
            continue
        rate = r["leads_per_hour"]
        missed = (round(float(rate) * float(days or 0.0) * 24.0, 1) if rate else None)
        out.append({
            "scout": r["name"], "organ_file": r["organ_file"], "status": r["status"],
            "days_since_output": round(days, 2) if days is not None else None,
            "n_grounds": r["beat"]["n_grounds"], "leads": r["yield"]["leads"],
            "missed_leads": missed,
            "why": ("no observable output at all" if days is None else
                    f"silent {days:.1f}d (>= {idle_days}d)" if days >= idle_days else
                    "on its clock, but its beat has never yielded a lead"),
            "missed_leads_basis": ("measured leads/hour x hours silent" if missed is not None else
                                   "UNMEASURED -- no costed run, so the silence cannot be priced"),
        })
    return sorted(out, key=lambda r: -(r["days_since_output"] or 1e9))


def _summary(doc: dict[str, Any]) -> list[str]:
    c, u = doc["coverage"], doc["unmeasured"]
    census = "  ".join(f"{k}={v}" for k, v in doc["status_census"].items())
    top = sorted((r for r in doc["scouts"] if r["yield"]["leads"]),
                 key=lambda r: -r["yield"]["leads"])[:3]
    return [
        f"scout roster: {doc['n_scouts']} scouts  {census}",
        f"  beats: {c['beats_covered']}/{c['beats_total']} COVERED, {u['n_beats_open']} OPEN; "
        f"specialists {len(doc['specialists']) - u['n_specialists_open']}/"
        f"{len(doc['specialists'])} on an organ",
        f"  grounds {c['grounds_covered']}/{c['grounds_total']} on paper but "
        f"{c['grounds_covered_live']} claimed by a scout still filing; languages "
        f"{c['languages_covered']}/{c['languages_total']} ({c['languages_covered_live']} live), "
        f"classes {c['asset_classes_covered']}/{c['asset_classes_total']}",
        "  top yield: " + ("  ".join(f"{r['name']}={r['yield']['leads']}" for r in top)
                           or "NONE MEASURED"),
        f"  open beats {len(doc['open_beats'])}, idle flags {len(doc['idle_flags'])}; "
        f"{u['n_scouts_without_a_clock']} without a clock, {u['n_scouts_uncosted']} uncosted",
        f"  cells: {u['cells_basis'][:72]}",
    ]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="W4: the scout roster, its beats and its open beats")
    ap.add_argument("--dry-run", action="store_true", help="measure and print, write nothing")
    ap.add_argument("--idle-days", type=float, default=IDLE_DAYS,
                    help="flag a scout whose beat produced nothing for this many days")
    args = ap.parse_args(argv)
    doc = build(idle_days=args.idle_days)
    if not args.dry_run:
        _atomic(OUT, doc)
    for line in _summary(doc):
        print(line)
    print(f"  {'wrote' if not args.dry_run else 'DRY RUN, wrote nothing:'} {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
