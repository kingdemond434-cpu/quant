"""Compile hourly miner evidence into executable MT5 candidates without inventing rules.

Miners produce three economically different things: exact recipes, structured data mechanisms,
and leads that still need rule extraction.  Treating all three as prose and defaulting them to a
session breakout created candidate count but destroyed provenance.  This compiler accounts for
every recent row and emits only source-faithful executable identities.  Leads without an exact
rule remain useful: mined_ground directs the family-free search toward them and this module writes
an explicit deepening queue for the research brains.  No row silently dies and no family is
guessed from a buzzword.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
if str(BASE) not in sys.path:
    # The hourly service executes this file by path. Python then adds ``research/`` rather than
    # ``desks/mt5/`` to sys.path, so exact recipes otherwise cannot see the family registry and
    # are silently routed to deepening instead of the gauntlet.
    sys.path.insert(0, str(BASE))
UNIVERSE = BASE / "data" / "universe"
INTEL_ROOTS = (BASE / "data" / "intelligence", ROOT / "data" / "intelligence")
OUT = BASE / "data" / "hypotheses" / "miner_candidates.json"
DEEPEN = BASE / "data" / "hypotheses" / "miner_deepening_queue.json"
WINDOW_DAYS = 7
#: The LLM seats' source names as they appear on their donated rows (`libs/ops/deepseek_cycle.py`
#: `_donate`, `scripts/kimi_hunter.py` `_donate`). Reported as one block in the compiled artifact
#: so "what did the seats put in the docket" is a field, not a grep -- and a seat that donated
#: nothing in the window is reported with zeros, because that is the measurement, not an absence.
SEAT_SOURCES = frozenset({"deepseek", "kimi_k3_deep_forest"})


def _read(path: Path):
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def known_symbols() -> set[str]:
    return {p.stem.removesuffix("_H1").upper() for p in UNIVERSE.glob("*_H1.parquet")}


def _rows(doc) -> list[dict]:
    if isinstance(doc, list):
        return [r for r in doc if isinstance(r, dict)]
    if not isinstance(doc, dict):
        return []
    if isinstance(doc.get("discoveries"), list):
        return [r for r in doc["discoveries"] if isinstance(r, dict)]
    out: list[dict] = []
    for value in doc.values():
        if isinstance(value, dict) and isinstance(value.get("discoveries"), list):
            out.extend(r for r in value["discoveries"] if isinstance(r, dict))
        elif isinstance(value, list):
            out.extend(r for r in value if isinstance(r, dict))
    return out


#: Rows one compile pass will carry. A bound on MEMORY, not a view of what matters: it is applied
#: newest-file-first and whatever it drops is COUNTED and reported, never silently discarded.
#:
#: RAISED 2026-09-05 with the intake widening below. The two roots hold ~223,000 rows inside the
#: window once every artifact is read (102,915 from `discoveries_*` plus 119,902 from everything
#: else), so 250,000 would bind within days of normal mining and start deferring real evidence for
#: a reason that is purely arithmetic.
#:
#: AND THE BOUND IT CLAIMS TO BE WAS MEASURED RATHER THAN FEARED. A full pass over the widened
#: intake -- 178,752 deduplicated rows across both roots -- takes 6.9 seconds at a peak RSS of
#: 368 MB. The desk box carries 3.1 GB resident of 8.4 GB, so a pass at four times today's intake
#: still fits with room, which is what this ceiling is set to allow. A number chosen for memory
#: that nobody ever measured is just a smaller version of the filename filter below.
MAX_ROWS_PER_PASS = 1_000_000

#: What the last intake pass left unread when the bound bound (2026-09-08). The shortfall used
#: to be a printed line and nothing else -- research opportunity cost that no artifact carried.
_LAST_INTAKE: dict = {"deferred_files": 0, "files_seen": 0, "bound_hit": False}

#: Artifacts under the intelligence roots that are a miner's OWN BOOKKEEPING, not evidence:
#: cursors, coverage registries, denylists, run checkpoints, population counts. They are matched
#: by exact filename at the root of a tree, never by substring, because "state" and "coverage" are
#: also perfectly good words for evidence and a substring rule would silently swallow a source.
#:
#: WHY AN EXCLUSION LIST RATHER THAN AN INCLUSION ONE. The old reader admitted only
#: `discoveries_*.json`, which is an inclusion list, and it is exactly what caused the loss this
#: module now documents twice: a miner that names its output `signals_*.json` or `articles_*.json`
#: was not rejected, it was NEVER READ. An inclusion list fails closed against the desk's own
#: future miners; an exclusion list fails open, and open is the correct direction here because an
#: unrecognised artifact that holds no rows costs nothing and one that holds rows is evidence.
_OPERATIONAL_STATE = frozenset({
    "anomaly_cursor.json", "blocked_sources.json", "coverage_registry.json",
    "frontier_coverage.json", "frontier_state.json", "gpt_hunter_state.json",
    "identity_graph.json", "midnight_codex_status.json", "midnight_completion.json",
    "midnight_completion_checkpoint.json", "midnight_morning_report.json",
    "mt5_midnight_state.json", "regional_hunters_state.json", "scheduled_chat_assimilation.json",
    "seed_miners_state.json", "source_populations.json", "survivor_funnel.json",
    "video_channel_coverage.json",
})


def _is_operational_state(rel: Path) -> bool:
    """Is this artifact a miner's bookkeeping rather than its evidence?

    Only at the ROOT of an intelligence tree (`len(rel.parts) == 1`). A file with one of these
    names inside a source directory is that source's output and is read: the names are generic
    enough that a per-source `coverage_registry.json` would plausibly hold rows.
    """
    return len(rel.parts) == 1 and rel.name in _OPERATIONAL_STATE


def recent_rows(now: datetime) -> list[tuple[str, dict]]:
    """EVERY discovery artifact in the window, exact-row deduplicated.

    THIS READ ONLY THE NEWEST FILE PER SOURCE DIRECTORY, and it was the largest conversion loss on
    the desk. Measured 2026-09-05: 5,524 discovery files inside the 7-day window holding 102,915
    rows, of which the compiler opened 60 files and saw 1,594 rows. **98.5% of everything the
    miners produced never reached the compiler at all** -- not rejected, not deepened, not
    graveyarded: unread. The docket looked like a funnel narrowing on merit and was mostly a
    directory listing sorted by mtime.

    A miner that writes one artifact per run kept only its last run; a miner that writes one per
    source kept only whichever landed last. Both are the common shape here, which is why the loss
    was near-total rather than partial.

    AND THEN THE FILENAME WAS STILL A FILTER. Reading every `discoveries_*.json` fixed the first
    loss and left a second, larger one untouched: the glob is an INCLUSION LIST, and a miner that
    names its output anything else was not rejected -- it was never read. Measured hours after the
    first fix, 119,902 rows in 583 artifacts inside the same window, none of them reaching the
    compiler:

        anomalies_*.json      97,405   the desk's OWN measured anomalies, fully structured
        mql5_*.json            7,569   catalogue rows
        quantocracy_*.json     6,908   blogosphere index
        macrosynergy_prs.json  2,363
        codebase_*.json        1,715   crawler output
        signals_*.json         1,630   crawler output
        forum_*.json             654   crawler output
        videos_*.json            544   crawler output

    The principal's rule is the general form of that measurement: anything a crawler or miner
    produces that is not already a direct candidate gets reverse-engineered and sent to the
    gauntlet. So the read is now EVERY json artifact under either root, at any depth, minus a
    short list of named operational-state files -- an exclusion list, which fails OPEN against a
    miner nobody has written yet, where the inclusion list failed closed against every one of them.

    THE DEDUPLICATION IS WHAT MAKES READING EVERYTHING SAFE, and it already existed: rows are keyed
    on a sha256 of their exact content, so a row repeated across fifty files is carried once. The
    old behaviour was not protecting against duplicates -- the dedup was -- it was discarding
    distinct rows.

    NEWEST FIRST, so if `MAX_ROWS_PER_PASS` binds it is the oldest discoveries that wait for the
    next pass rather than an arbitrary slice, and the shortfall is reported rather than hidden.
    """
    cutoff = now - timedelta(days=WINDOW_DAYS)
    found: list[tuple[str, dict]] = []
    seen: set[str] = set()
    _LAST_INTAKE.update({"deferred_files": 0, "files_seen": 0, "bound_hit": False})
    all_paths: list[Path] = []
    for root in INTEL_ROOTS:
        if not root.exists():
            continue
        all_paths.extend(sorted((p for p in root.rglob("*.json")
                                 if p.is_file()
                                 and not _is_operational_state(p.relative_to(root))),
                                key=lambda p: p.stat().st_mtime, reverse=True))
    for i, path in enumerate(all_paths):
        try:
            if datetime.fromtimestamp(path.stat().st_mtime, tz=UTC) < cutoff:
                continue
        except OSError:
            continue
        _LAST_INTAKE["files_seen"] = i + 1
        for row in _rows(_read(path)):
            payload = json.dumps(row, sort_keys=True, default=str, separators=(",", ":"))
            digest = hashlib.sha256(payload.encode()).hexdigest()
            if digest in seen:
                continue
            seen.add(digest)
            source = str(row.get("source") or path.parent.name or "unknown")
            found.append((source, row))
            if len(found) >= MAX_ROWS_PER_PASS:
                # THE SHORTFALL IS RECORDED, NOT ONLY PRINTED: the files this pass never opened
                # are research the desk chose not to do this hour, and the compiled artifact
                # carries that count (`intake.deferred_files`).
                _LAST_INTAKE.update({"deferred_files": len(all_paths) - (i + 1),
                                     "bound_hit": True})
                print(f"compiler: MAX_ROWS_PER_PASS ({MAX_ROWS_PER_PASS:,}) reached; "
                      f"{len(all_paths) - (i + 1)} file(s) wait for the next pass. This is a "
                      f"memory bound being hit, not a judgement -- raise it or shorten "
                      f"WINDOW_DAYS.")
                return found
    return found


def resolve_symbols(row: dict, universe: set[str]) -> list[str]:
    """Resolve exact symbols and currency-wide evidence against the live Fusion registry."""
    raw = []
    for key in ("symbol", "currency"):
        if row.get(key):
            raw.append(row[key])
    for key in ("symbols", "instruments"):
        if isinstance(row.get(key), list):
            raw.extend(row[key])
    out: set[str] = set()
    for value in raw:
        token = str(value).upper().replace("/", "").strip()
        if token in universe:
            out.add(token)
        elif len(token) == 3 and token.isalpha():
            out.update(s for s in universe if len(s) == 6 and token in (s[:3], s[3:]))
    return sorted(out)


def _lead_lag_lag(row: dict) -> int | None:
    """The lag, in bars, an anomaly row measured -- from the row, never assumed.

    The scanner writes it two ways and both are read: `horizon` as an integer, and encoded in the
    condition text (`lead_lag_BNBUSD_lag1`). A row that carries neither returns None and goes to
    deepening, because a lead-lag recipe without a lag is not a rule -- it is the shape of one.
    """
    horizon = row.get("horizon")
    if isinstance(horizon, int) and 1 <= horizon <= 168:
        return horizon
    cond = str(row.get("condition") or "")
    if "_lag" in cond:
        tail = cond.rsplit("_lag", 1)[-1]
        if tail.isdigit() and 1 <= int(tail) <= 168:
            return int(tail)
    return None


def _genome_id(symbol: str, family: str, params: dict) -> str | None:
    """The one identity a strategy carries from here to the deal (libs/research/alpha_genome).

    STAMPED AT THE PEN, not derived later by a matcher: the graph node, the certificate and the
    StrategyArtifact all hash the same (symbol, family, params) through `hypothesis_graph.node_id`,
    so a candidate that carries the id joins to every later shape by key. Absent libs (this file
    also runs from the desk root on the box) means no id rather than a crash.
    """
    try:
        from libs.research.alpha_genome import genome_id
        return genome_id(symbol, family, params)
    except Exception:
        return None


def _candidate(symbol: str, family: str, params: dict, source: str, row: dict,
               mechanism: str) -> dict:
    gid = _genome_id(symbol, family, params)
    return {
        **({"genome_id": gid} if gid else {}),
        "symbol": symbol,
        "family": family,
        "params": params,
        "source": f"miner:{source}",
        "source_url": row.get("url") or row.get("link") or "",
        "source_title": str(row.get("title") or row.get("description") or "")[:300],
        "mechanism_status": "NAMED",
        "mechanism_note": mechanism,
        # THE MISSION THAT CAUSED THIS ROW RIDES ONTO THE CANDIDATE (Tier-1 P17 / AP4). The
        # portfolio's missions are queue rows keyed by mission_id; a candidate that does not
        # carry the id cannot be counted as the mission's yield, and the acceptance property
        # "the portfolio creates research missions" is measured on exactly that count.
        **({"mission_id": row["mission_id"]} if row.get("mission_id") else {}),
    }


def _registered_family(name: str) -> bool:
    try:
        from mt5desk import families, families_orthogonal
        return (callable(getattr(families, f"family_{name}", None))
                or name in families_orthogonal.ORTHOGONAL_FAMILIES)
    except ImportError:
        return False


# ================================================================== extraction FROM PROSE
#
# WHY THIS EXISTS. `resolve_symbols` reads four STRUCTURED fields -- symbol, currency, symbols,
# instruments -- and nothing else. Every prose miner (world, reddit, github, bis_speeches,
# arxiv_qfin, amarkets, mql5_catalog, forextsd_cdx ...) writes its evidence to `title` / `text` /
# `summary` / `description` and an EMPTY `symbols` list, so each of those rows reached
# `compile_row` with no symbol, took the NEEDS_SYMBOL_EXTRACTION exit, and converted at exactly
# zero. MEASURED 2026-09-08 on the board: world 10,062 rows -> 1 distinct -> 0 tested;
# bis_speeches 6,160 -> 1 -> 0; reddit 6,962 -> 1 -> 0; github_topics 6,754 -> 1 -> 0. Not
# because the prose named nothing, because nothing read the prose.
#
# WHAT IT IS AND IS NOT. Deterministic vocabulary against the live registry: an instrument is
# extracted only if the registry can price it, a family only if it is registered AND price-only
# (a family that needs swap terms or a peer instrument cannot be built from a paragraph), a
# session only from the ONE forward engine's own window names. Nothing is guessed from prose
# that the gauntlet does not then judge; a text candidate is a HYPOTHESIS with the family's
# default parameters, and the matched phrase is written onto it so a reader can see exactly
# which words put it in the docket. The ten gates remain the only arbiter of profitability.
#
# BOUNDS, because a docket is a budget: at most four instruments and two families per row, the
# two longest phrase matches winning; bare three-letter currency codes are NOT expanded from
# prose (a speech that says "the euro" would otherwise mint ten pairs); operational rows -- a
# walled site, a fetch error, a stub -- are refused outright, because an error message contains
# no mechanism and extracting instruments from one manufactures candidates out of plumbing.

_OPERATIONAL_KINDS = frozenset({"walled", "fetch_error", "stub", "probe", "error", "skipped"})
_TEXT_FIELDS = ("title", "text", "summary", "description", "abstract", "body", "content",
                "snippet", "headline", "claim", "hypothesis", "mechanism", "notes",
                "testable_claim")
_TEXT_LIST_FIELDS = ("trading_terms", "mechanism_tags", "policy_signals", "tags", "keywords")
_MAX_TEXT_CHARS = 20_000
_MAX_TEXT_SYMBOLS = 4
_MAX_TEXT_FAMILIES = 2

#: Instrument aliases -> registry symbols, in preference order. A target is used ONLY when it is
#: in the live universe: the alias list is vocabulary, the registry is the authority, and an
#: alias can never mint a symbol the desk cannot price.
_ALIASES: dict[str, tuple[str, ...]] = {
    "gold": ("XAUUSD",), "xau": ("XAUUSD",), "silver": ("XAGUSD",), "xag": ("XAGUSD",),
    "brent": ("UKOIL", "BRENT", "XBRUSD"), "wti": ("USOIL", "WTI", "XTIUSD"),
    "crude": ("USOIL", "UKOIL", "WTI", "BRENT"), "crude oil": ("USOIL", "UKOIL"),
    "nasdaq": ("NAS100", "USTEC", "US100"), "s&p 500": ("US500", "SPX500", "SP500"),
    "s&p": ("US500", "SPX500", "SP500"), "spx": ("US500", "SPX500", "SP500"),
    "dow jones": ("US30", "DJ30"), "dax": ("GER40", "DE40", "GER30", "DE30"),
    "ftse": ("UK100",), "nikkei": ("JPN225", "JP225"),
    "bitcoin": ("BTCUSD",), "btc": ("BTCUSD",), "ethereum": ("ETHUSD",), "ether": ("ETHUSD",),
    "cable": ("GBPUSD",), "fiber": ("EURUSD",), "loonie": ("USDCAD",), "aussie": ("AUDUSD",),
    "kiwi": ("NZDUSD",), "swissy": ("USDCHF",),
}

#: Phrase -> price-only family. Every family here takes bars and nothing else; the longest
#: matched phrase decides. A family that needs an external input (carry, cot_*, event_reaction,
#: relative_value, lead_lag ...) is deliberately absent: it cannot be built from a paragraph.
_FAMILY_VOCAB: dict[str, tuple[str, ...]] = {
    "session_range_breakout": ("opening range breakout", "session range breakout",
                               "range breakout", "asian range breakout", "london breakout",
                               "session breakout", "orb strategy", "opening range"),
    "failed_breakout": ("failed breakout", "false breakout", "fakeout", "fake breakout",
                        "bull trap", "bear trap", "failed break"),
    "level_breakout": ("resistance breakout", "support breakout", "key level breakout",
                       "break of structure", "breakout above resistance",
                       "breakdown below support", "level breakout"),
    "monday_gap": ("monday gap", "weekend gap", "sunday gap", "monday open gap"),
    "overnight_gap_decay": ("gap fill", "gap fade", "overnight gap", "gap and go",
                            "fading the gap", "gap close"),
    "overnight_drift": ("overnight drift", "overnight return", "close to open",
                        "overnight premium"),
    "dow_effect": ("day of the week", "day-of-week", "monday effect", "friday effect",
                   "turnaround tuesday", "weekday effect", "weekend effect"),
    "turn_of_month": ("turn of the month", "turn-of-the-month", "month end rebalancing",
                      "month-end rebalancing", "end of month effect", "first day of the month"),
    "calendar_month": ("january effect", "sell in may", "santa rally", "santa claus rally",
                       "december rally", "seasonal pattern", "seasonality", "seasonal tendency",
                       "seasonal bias"),
    "mean_reversion_rsi": ("rsi oversold", "rsi overbought", "rsi divergence",
                           "rsi mean reversion", "relative strength index", "rsi(2)", "rsi 2"),
    "mean_reversion_bollinger": ("bollinger band", "bollinger bands", "bollinger bounce",
                                 "lower band bounce", "upper band fade"),
    "volatility_squeeze": ("volatility squeeze", "bollinger squeeze", "ttm squeeze",
                           "keltner squeeze", "volatility contraction", "narrow range",
                           "inside bar breakout", "nr7"),
    "trend_ma_cross": ("moving average crossover", "ma crossover", "ema crossover",
                       "sma crossover", "golden cross", "death cross", "ma cross"),
    "london_close_momentum": ("london close", "london fix momentum", "london closing"),
    "asia_momentum": ("asian session momentum", "asia session momentum", "tokyo momentum"),
    "momentum_volgate": ("momentum with volatility filter", "volatility-gated momentum",
                         "momentum vol filter"),
    "range_reversion": ("range trading", "range-bound", "range bound", "trading the range",
                        "buy support sell resistance", "mean reversion in a range"),
    "volume_spike": ("volume spike", "volume surge", "climax volume", "unusual volume",
                     "volume breakout"),
    "pullback_entry": ("pullback entry", "buy the dip", "buy the pullback", "retracement entry",
                       "fibonacci retracement", "fib retracement",
                       "pullback to the moving average"),
    "pin_bar_reversal": ("pin bar", "pinbar", "hammer candle", "shooting star", "rejection wick",
                         "long wick reversal"),
    "engulfing_reversal": ("engulfing candle", "bullish engulfing", "bearish engulfing",
                           "engulfing pattern"),
    "ict_fvg": ("fair value gap", "fvg", "order block", "liquidity sweep", "liquidity grab",
                "smart money concept", "ict concept", "breaker block"),
    "retail_overlap_reversal": ("retail sentiment", "contrarian retail", "fade retail",
                                "fade the crowd", "retail positioning", "position ratio"),
    "vol_mean_reversion": ("volatility mean reversion", "vix mean reversion", "vol crush",
                           "volatility risk premium", "short volatility"),
    "vol_transition": ("volatility regime", "vol regime", "regime change in volatility",
                       "low vol to high vol", "volatility expansion"),
    "drawdown_conditional": ("after a drawdown", "buy after decline", "drawdown recovery",
                             "post-drawdown", "after a selloff"),
    "spread_state": ("spread widening", "wide spread", "spread regime", "spread compression"),
    "comex_settlement": ("comex settlement", "comex close", "gold settlement", "comex fix"),
}

_SESSION_VOCAB: dict[str, tuple[str, ...]] = {
    "asia": ("asian session", "asia session", "asian range", "tokyo session", "asian open",
             "tokyo open"),
    "london_am": ("london open", "london session", "london breakout", "european open",
                  "frankfurt open", "european session"),
    "ny_open": ("new york open", "ny open", "us open", "new york session", "ny session",
                "wall street open"),
    "afternoon": ("afternoon session", "london close", "us afternoon", "late session"),
}
#: The ONE forward engine's windows, exactly as `external_gauntlet.WINDOWS_KNOWN` names them, so
#: a text-extracted session cell is the same cell a certified one would be.
_SESSION_PARAMS: dict[str, dict] = {
    "asia": {"range_start": 7},
    "london_am": {"range_start": 10, "range_end": 13, "signal_at": 13},
    "ny_open": {"range_start": 13, "range_end": 14, "signal_at": 14},
    "afternoon": {"range_start": 14, "range_end": 17, "signal_at": 17},
}
_MONTHS = {m: i for i, m in enumerate(("january", "february", "march", "april", "may", "june",
                                        "july", "august", "september", "october", "november",
                                        "december"), start=1)}
_UP_WORDS = ("rally", "rallies", "rise", "rises", "rising", "bullish", "strong", "strength",
             "outperform", "gain", "gains", "higher", "positive", "buy")
_DOWN_WORDS = ("fall", "falls", "falling", "drop", "drops", "bearish", "weak", "weakness",
               "underperform", "decline", "declines", "lower", "negative", "sell", "short")

_REG_CACHE: dict[str, bool] = {}


def _registered_cached(name: str) -> bool:
    if name not in _REG_CACHE:
        _REG_CACHE[name] = _registered_family(name)
    return _REG_CACHE[name]


def _phrase_re(phrase: str):
    import re
    return re.compile(r"(?<![a-z0-9])" + re.escape(phrase.lower()) + r"(?![a-z0-9])")


def _row_text(row: dict) -> str:
    parts: list[str] = []
    for key in _TEXT_FIELDS:
        v = row.get(key)
        if isinstance(v, str) and v.strip():
            parts.append(v)
    for key in _TEXT_LIST_FIELDS:
        v = row.get(key)
        if isinstance(v, list):
            parts.extend(str(x) for x in v if isinstance(x, (str, int, float)))
    return " ".join(parts)[:_MAX_TEXT_CHARS].lower()


def _declared_symbols(row: dict, universe: set[str]) -> list[str]:
    """Instruments the row DECLARES in a structured field, registry-priced, exact codes only.

    `resolve_symbols` is the structured miners' rule and expands a bare currency to its pairs,
    which is right for a CPI print and wrong for a paragraph or a seat's hypothesis. This is the
    narrower reading the prose path and a seat's row share: what the row itself named, if the
    desk can price it, and nothing minted from a three-letter code.
    """
    raw: list = [row["symbol"]] if row.get("symbol") else []
    for key in ("symbols", "instruments"):
        if isinstance(row.get(key), list):
            raw.extend(row[key])
    out: list[str] = []
    for value in raw:
        token = str(value).upper().replace("/", "").replace("-", "").strip()
        if token in universe and token not in out:
            out.append(token)
    return out


def text_symbols(text: str, universe: set[str]) -> list[str]:
    """Instruments the prose names that the registry can price. Exact six-letter codes,
    slash/dash pairs, and aliases; never a bare three-letter currency expanded to its pairs."""
    import re
    found: list[str] = []
    for m in re.finditer(r"(?<![a-z0-9])([a-z]{6})(?![a-z0-9])", text):
        s = m.group(1).upper()
        if s in universe and s not in found:
            found.append(s)
    for m in re.finditer(r"(?<![a-z0-9])([a-z]{3})\s?[/\-]\s?([a-z]{3})(?![a-z0-9])", text):
        s = (m.group(1) + m.group(2)).upper()
        if s in universe and s not in found:
            found.append(s)
    for alias, targets in _ALIASES.items():
        if _phrase_re(alias).search(text):
            for t in targets:
                if t in universe:
                    if t not in found:
                        found.append(t)
                    break
    return found[:_MAX_TEXT_SYMBOLS]


def text_families(text: str) -> list[tuple[str, str]]:
    """(family, matched phrase), longest phrase first, at most two, registered families only."""
    hits: dict[str, str] = {}
    for fam, phrases in _FAMILY_VOCAB.items():
        for ph in phrases:
            if _phrase_re(ph).search(text) and len(ph) > len(hits.get(fam, "")):
                hits[fam] = ph
    ranked = sorted(((fam, ph) for fam, ph in hits.items() if _registered_cached(fam)),
                    key=lambda x: (-len(x[1]), x[0]))
    return ranked[:_MAX_TEXT_FAMILIES]


def text_session(text: str) -> str | None:
    best: tuple[int, str] | None = None
    for sess, phrases in _SESSION_VOCAB.items():
        for ph in phrases:
            if _phrase_re(ph).search(text) and (best is None or len(ph) > best[0]):
                best = (len(ph), sess)
    return best[1] if best else None


def _text_params(family: str, text: str) -> dict | None:
    """The family's parameters as far as the prose names them; None when the family needs
    something the prose did not say (a month for calendar_month)."""
    if family == "session_range_breakout":
        sess = text_session(text)
        return dict(_SESSION_PARAMS[sess]) if sess else {}
    if family == "calendar_month":
        month = next((n for name, n in _MONTHS.items() if _phrase_re(name).search(text)), None)
        if month is None:
            return None
        up = any(_phrase_re(w).search(text) for w in _UP_WORDS)
        down = any(_phrase_re(w).search(text) for w in _DOWN_WORDS)
        if up == down:
            return None                              # no direction, or both: not a recipe
        return {"active_month": month, "side_bias": 1 if up else -1}
    return {}                                        # family defaults, judged as such


def compile_from_text(source: str, row: dict, universe: set[str]) -> tuple[list[dict], str]:
    """Candidates the row's PROSE supports, or the exact reason it supports none."""
    kind = str(row.get("kind") or row.get("type") or "").lower()
    if kind in _OPERATIONAL_KINDS or row.get("needs_selector_work"):
        return [], "OPERATIONAL_ROW"
    text = _row_text(row)
    if not text:
        return [], "NEEDS_SYMBOL_EXTRACTION"
    # THE ROW'S OWN DECLARED INSTRUMENTS COME FIRST (2026-09-08). A seat writes
    # `symbols: ["USDJPY"]` and prose that says "the yen"; reading the prose alone lost the
    # instrument the row had already stated and sent a row carrying both a family phrase and a
    # priced instrument to deepening. Declared first, prose after, the same four-instrument bound.
    symbols = _declared_symbols(row, universe)
    for s in text_symbols(text, universe):
        if s not in symbols:
            symbols.append(s)
    symbols = symbols[:_MAX_TEXT_SYMBOLS]
    if not symbols:
        return [], "NEEDS_SYMBOL_EXTRACTION"
    families = text_families(text)
    if not families:
        return [], "NEEDS_EXACT_RULE_EXTRACTION"
    out: list[dict] = []
    for fam, phrase in families:
        params = _text_params(fam, text)
        if params is None:
            continue
        for sym in symbols:
            out.append(_candidate(
                sym, fam, dict(params), source, row,
                f"text extraction: '{phrase}' named with {sym} in the row's prose; "
                + ("session/month taken from the text" if params else "family defaults")
                + " -- a hypothesis for the ten gates, not a claim"))
    return (out, "TEXT_EXTRACTED") if out else ([], "NEEDS_EXACT_RULE_EXTRACTION")


def compile_row(source: str, row: dict, universe: set[str]) -> tuple[list[dict], str]:
    """Return executable candidates and the exact disposition for one evidence row."""
    symbols = resolve_symbols(row, universe)
    source_l = source.lower()
    kind = str(row.get("kind") or row.get("type") or "").lower()

    # Direct recipes from any present or future miner are admitted only when the family and
    # executable parameters are explicit. The gauntlet remains the arbiter of profitability.
    family = row.get("family")
    params = row.get("params")
    if (isinstance(family, str) and isinstance(params, dict) and symbols
            and _registered_family(family)):
        return ([_candidate(s, family, dict(params), source, row,
                            str(row.get("mechanism") or "source supplied exact recipe"))
                 for s in symbols], "EXACT_RECIPE")

    if (source_l == "cot" or (kind == "positioning" and "cot" in source_l)) and symbols:
        return ([_candidate(s, "cot_positioning", {"input_source": "cot_point_in_time"},
                            source, row,
                            "reported positioning extremes can unwind or continue "
                            "conditionally")
                 for s in symbols], "STRUCTURED_COT")

    event_like = (source_l in {"ff_calendar_vintage", "forexfactory", "central_bank"}
                  or kind in {"calendar_event", "calendar_vintage", "cb_speech"})
    if event_like and symbols:
        return ([_candidate(s, "event_reaction", {"input_source": "ff_calendar_vintage"},
                            source, row,
                            "scheduled information releases create conditional repricing "
                            "and liquidity")
                 for s in symbols], "STRUCTURED_EVENT")

    if source_l == "broker_swaps" and symbols and (
            kind in {"contract_terms", "swap_terms"}
            or row.get("swap_long") is not None or row.get("swap_short") is not None):
        return ([_candidate(s, "carry", {"input_symbol": s}, source, row,
                            "broker-native swap differential is a directly measured carry premium")
                 for s in symbols], "STRUCTURED_CARRY")

    # THE DESK'S OWN ANOMALY SCANNER IS A STRUCTURED SOURCE, and it is the largest one there is:
    # 97,405 of the 119,902 rows the compiler could not previously see are `anomalies_*.json`.
    # A lead-lag row names both instruments, the lag and the sign of the measured relationship,
    # which is a complete `family_lead_lag` recipe -- `driver_symbol`, `lag`, `direction` -- and
    # nothing about it is guessed from prose. That distinction is the whole rule of this module:
    # the scanner MEASURED that BNBUSD at lag 1 leads BCHUSD at |t|=38.6 over n=44,237, the same
    # class of evidence as a swap differential or a COT print.
    #
    # AN UNNAMED MECHANISM IS STILL NOT A CANDIDATE, and this does not change that. The rows carry
    # `mechanism_status: UNNAMED` and their own note says "an OBSERVATION, not a candidate"; what
    # makes this one admissible is not that the desk believes the correlation, it is that the row
    # specifies an EXACT EXECUTABLE RULE and the gauntlet's ten gates are the thing that decides
    # whether it survives. Every other anomaly shape -- a conditional return with no family hint,
    # `hour_q0-0.05` and the external-series conditions -- still goes to DEEPENING, which is where
    # a mechanism gets named, and that is the majority of the file.
    if kind == "anomaly" and symbols and row.get("against"):
        hint = str(row.get("family_hint") or "").lower()
        peer = str(row["against"]).upper().replace("/", "").strip()
        if peer in universe and hint == "lead_lag":
            lag = _lead_lag_lag(row)
            if lag is not None:
                corr = row.get("corr")
                direction = "opposite" if isinstance(corr, (int, float)) and corr < 0 else "same"
                return ([_candidate(s, "lead_lag",
                                    {"driver_symbol": peer, "lag": lag, "direction": direction},
                                    source, row,
                                    "a measured lead-lag between two instruments can transmit "
                                    "through a shared factor, a common venue or quote latency")
                         for s in symbols if s != peer], "STRUCTURED_LEAD_LAG")
        if peer in universe and hint == "cross_asset_residual":
            # The scanner measures the residual on the family's OWN defaults -- a 240-bar lookback
            # at 2sd -- so only what it actually varied is written onto the recipe: the factor it
            # measured against and the horizon it measured over. Restating a default as a param
            # would freeze today's default into every candidate and silently fork the two the day
            # the family's changes.
            hold = row.get("horizon")
            if isinstance(hold, int) and 1 <= hold <= 168:
                return ([_candidate(s, "cross_asset_residual",
                                    {"factor_symbols": [peer], "ttl_bars": hold},
                                    source, row,
                                    "a measured cross-instrument residual can revert when the "
                                    "shared factor reasserts itself")
                         for s in symbols if s != peer], "STRUCTURED_CROSS_ASSET_RESIDUAL")

    if source_l == "correlations" and len(symbols) >= 2:
        candidates = []
        for symbol in symbols:
            for peer in symbols:
                if peer != symbol:
                    candidates.append(_candidate(
                        symbol, "relative_value", {"peer_symbol": peer}, source, row,
                        "a measured cross-instrument relationship can create residual convergence",
                    ))
        return candidates, "STRUCTURED_RELATIVE_VALUE"

    month = row.get("month")
    direction = str(row.get("direction") or "").lower()
    if source_l == "seasonality" and symbols and isinstance(month, int) and 1 <= month <= 12 \
            and direction in {"up", "down", "long", "short"}:
        side = 1 if direction in {"up", "long"} else -1
        return ([_candidate(s, "calendar_month", {"active_month": month, "side_bias": side},
                            source, row,
                            "calendar-linked allocation and hedging flows can create "
                            "monthly seasonality")
                 for s in symbols], "STRUCTURED_CALENDAR")

    # A SEAT'S HYPOTHESIS NAMES ITS FAMILY OUTRIGHT (2026-09-08). The DeepSeek seat donates
    # `{"kind": "hypothesis", "family": "overnight_gap_decay", "symbols": ["USDJPY"], ...}`
    # (libs/ops/deepseek_cycle.py `_donate`) and the desk's own generators can write the same
    # shape. MEASURED: such a row has no `params`, so it missed EXACT_RECIPE, and the prose path
    # below re-derived the family from the text alone -- a row whose prose did not happen to
    # repeat a vocabulary phrase went to deepening WITH its family and instrument already on it.
    # The prose path admits a family from a matched phrase with the family's defaults; a row that
    # states the registered family is at least that explicit, and is held to the same bounds:
    # price-only families (`_FAMILY_VOCAB` -- nothing that needs a swap table or a peer) and
    # whatever parameters the text names (`_text_params`, so a calendar_month with no month is
    # still not a recipe). Declared instruments only: a seat saying "EUR" is not a CPI print.
    if kind == "hypothesis" and isinstance(family, str) and family in _FAMILY_VOCAB \
            and _registered_cached(family):
        declared = _declared_symbols(row, universe)[:_MAX_TEXT_SYMBOLS]
        params = _text_params(family, _row_text(row)) if declared else None
        if params is not None:
            return ([_candidate(s, family, dict(params), source, row,
                                f"seat hypothesis: the row names {family} on {s} outright; "
                                + ("session/month taken from the text" if params
                                   else "family defaults")
                                + " -- a hypothesis for the ten gates, not a claim")
                     for s in declared], "STRUCTURED_HYPOTHESIS")

    # PROSE, LAST. Every structured shape above is exact and wins; only a row none of them
    # claims is read as text. Before this line the prose miners converted at zero.
    text_cands, text_disp = compile_from_text(source, row, universe)
    if text_cands:
        return text_cands, text_disp
    if not symbols and text_disp == "OPERATIONAL_ROW":
        return [], text_disp
    # THE LABEL SAYS WHAT IS ACTUALLY MISSING. A row with no structured instrument whose prose
    # DID name one (the seats' rows: "gold basis pressure") was labelled NEEDS_SYMBOL_EXTRACTION
    # here, overriding the prose path's own finding; the deepening worker then spent its call
    # recovering an instrument the row already had, not the rule it lacked.
    if not symbols and text_disp != "NEEDS_EXACT_RULE_EXTRACTION":
        return [], "NEEDS_SYMBOL_EXTRACTION"
    return [], "NEEDS_EXACT_RULE_EXTRACTION"


def structurally_untestable_families() -> dict[str, str]:
    """Families the gauntlet has MEASURED as producing zero judgeable cells, from its own report.

    Data-driven, never a hardcoded list (LAWS anti-hardcode): a family joins this set only when
    the last sweep built >=5 of its cells and judged NONE (all under the 60 trading days the
    gates need) -- measured 2026-08-27: carry 193/193, event_reaction 113/113, calendar_month
    2/2, lvc_asia_london 3/3 re-shipped every hour, ~310 guaranteed-unjudgeable builds per
    sweep. Routing them to the DEEPENING queue is not a rejection: it is the statement that
    these parameterizations need widening (pooled events, longer windows) before any gate can
    rule, which is exactly what the deepening queue exists to ask the research brains for.
    A family leaves the set the moment one of its cells becomes judgeable.
    """
    report = BASE / "reports" / "universal_gates_external.json"
    try:
        doc = json.loads(report.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    per_fam: dict[str, list[int]] = {}
    for v in doc.get("verdicts") or []:
        if not isinstance(v, dict):
            continue
        fam = str(v.get("family") or "?")
        n_all, n_unm = per_fam.setdefault(fam, [0, 0])
        per_fam[fam] = [n_all + 1, n_unm + (1 if v.get("unmeasured") else 0)]
    return {fam: (f"last sweep built {n} cell(s), judged 0 -- every one under the 60 trading "
                  f"days the gates need; parameters need DEEPENING before judgment is possible")
            for fam, (n, unm) in per_fam.items() if n >= 5 and unm == n}


def seat_summary(per_source: dict[str, dict[str, int]]) -> dict[str, dict[str, int]]:
    """Per-seat conversion for the compiled artifact: rows seen, candidates, deepening tasks.

    A seat absent from `per_source` is reported with zeros rather than omitted: "the seat donated
    nothing inside the window" is the measurement the desk most needs to see, and a missing key
    reads as "not tracked".
    """
    return {s: dict(per_source.get(s) or {"rows": 0, "candidates": 0, "deepening": 0})
            for s in sorted(SEAT_SOURCES)}


def main() -> int:
    now = datetime.now(tz=UTC)
    universe = known_symbols()
    candidates: dict[str, dict] = {}
    deepening: dict[str, dict] = {}
    per_source: dict[str, dict[str, int]] = {}
    untestable = structurally_untestable_families()
    if untestable:
        print("families routed to DEEPENING (measured untestable at current parameters): "
              + ", ".join(sorted(untestable)))

    # CROSS-ENGINE AGREEMENT (2026-09-08). Two engines proposing the SAME cell already collide
    # on one identity here; the collision was thrown away. It is kept now as the count of
    # distinct sources behind each candidate -- a cell the symbolic search AND the causal graph
    # AND a crawler all name is a different object from one a single crawler named, and the
    # trial allocator can order on it.
    sources_by_identity: dict[str, set[str]] = {}
    for source, row in recent_rows(now):
        produced, disposition = compile_row(source, row, universe)
        stats = per_source.setdefault(source, {"rows": 0, "candidates": 0, "deepening": 0})
        stats["rows"] += 1
        for candidate in produced:
            identity = json.dumps({k: candidate[k] for k in ("symbol", "family", "params")},
                                  sort_keys=True, default=str)
            fam = str(candidate.get("family") or "")
            if fam in untestable:
                if identity not in deepening:
                    deepening[identity] = {**candidate,
                                           "deepening_reason": untestable[fam]}
                    stats["deepening"] += 1
                continue
            sources_by_identity.setdefault(identity, set()).add(source)
            if identity not in candidates:
                candidates[identity] = candidate
                stats["candidates"] += 1
        if not produced:
            compact = {
                "source": source,
                "disposition": disposition,
                "title": str(row.get("title") or row.get("description") or "")[:300],
                "url": row.get("url") or row.get("link") or "",
                "symbols": resolve_symbols(row, universe),
                "mechanism_tags": row.get("mechanism_tags") or row.get("patterns") or [],
            }
            key = hashlib.sha256(
                json.dumps(compact, sort_keys=True, default=str).encode()).hexdigest()
            deepening[key] = compact
            stats["deepening"] += 1
    # AFTER the intake loop, never inside it: 4aaede35 placed this loop between the candidate
    # loop and the `if not produced` block, which moved the deepening of non-producing rows
    # into the per-candidate loop -- every prose row that compiled to nothing was dropped
    # instead of deepened, and the last row's `produced` decided it for all of them.
    for identity, candidate in candidates.items():
        srcs = sorted(sources_by_identity.get(identity, ()))
        candidate["n_independent_sources"] = len(srcs)
        if len(srcs) > 1:
            candidate["agreeing_sources"] = srcs

    seats = seat_summary(per_source)
    seats_dark = [s for s, st in seats.items() if not st["rows"]]
    for s, st in seats.items():
        print(f"seat {s}: {st['rows']} row(s) -> {st['candidates']} candidate(s), "
              f"{st['deepening']} deepening"
              + ("" if st["rows"] else "  (nothing donated inside the window)"))
    if seats_dark:
        # LOUD, because a seat on an hourly clock that donates nothing for a week is either
        # unfunded, unrouted or broken, and every one of those has looked like "no findings".
        print(f"SEATS DARK inside the {WINDOW_DAYS}-day window: {', '.join(seats_dark)}",
              flush=True)
    agreement = sum(1 for c in candidates.values() if c.get("n_independent_sources", 0) > 1)
    # DISAGREEMENT IS A SIGNAL TOO (Tier-1 item G20, 2026-09-09). Two engines naming the same
    # symbol under DIFFERENT families is not a tie to discard: it is the cell whose test settles
    # which engine was right, which is the highest-information trial the hour can buy. The cell
    # is named here (`contested`) so the trial allocator can weight it; the compiler itself
    # allocates nothing.
    families_by_symbol: dict[str, dict[str, set[str]]] = {}
    for c in candidates.values():
        srcs = set(c.get("agreeing_sources") or [str(c.get("source") or "")])
        families_by_symbol.setdefault(str(c.get("symbol")), {}) \
            .setdefault(str(c.get("family")), set()).update(srcs)
    contested = {sym: {f: sorted(s) for f, s in fams.items()}
                 for sym, fams in families_by_symbol.items()
                 if len(fams) > 1 and len(set().union(*fams.values())) > 1}
    for c in candidates.values():
        if str(c.get("symbol")) in contested:
            c["contested"] = True
    disagreement = {"contested_symbols": len(contested),
                    "cells": dict(sorted(contested.items())[:40])}

    # THE GRAPH REMEMBERS WHAT WAS BURIED. Every compiled candidate is registered as BORN with
    # its miner row as parent, and every one that lands in a parameter region the gauntlet has
    # already failed carries that count on its face. It is not rejected -- the gauntlet decides
    # -- but a proposer that keeps re-proposing a dead region is now visible, and the deepening
    # queue's VOI ordering discounts it.
    #
    # EVERY FAILURE IN HERE IS NAMED IN THE ARTIFACT (2026-09-08). Measured on the box: 632 of
    # 632 compiled candidates carried no premortem and no prior-failure count, and the graph
    # held no compiler row at all -- this block was failing every hour and `except: pass` made
    # it look like a graph with nothing to say.
    graph_note: dict = {"updated": False, "premortem": False}
    try:
        from libs.research.hypothesis_graph import Graph, record_candidates
        g = Graph()
        for c in candidates.values():
            pf = g.prior_failures(str(c.get("symbol")), str(c.get("family")),
                                  dict(c.get("params") or {}))
            if pf["n_failed"]:
                c["prior_failures_in_region"] = pf["n_failed"]
                c["region"] = pf["region"]
        # THE PRE-MORTEM: which failure class this candidate most resembles dying of, and the
        # cheap falsifier that implies. Annotation only -- the gauntlet still decides.
        try:
            from libs.research.graveyard_model import GraveyardModel
            gm = GraveyardModel().fit(g.rows())
            if gm.n:
                for c in candidates.values():
                    c["premortem"] = gm.premortem(c)
                graph_note["premortem"] = True
            else:
                graph_note["premortem_why"] = "graveyard model fitted on zero rows"
        except Exception as exc:
            graph_note["premortem_why"] = f"{type(exc).__name__}: {exc}"[:300]
            print(f"premortem not stamped (non-fatal): {graph_note['premortem_why']}")
        record_candidates(candidates.values(), source="miner_candidate_compiler", graph=g)
        graph_note["updated"] = True
    except Exception as exc:
        graph_note["why"] = f"{type(exc).__name__}: {exc}"[:300]
        print(f"hypothesis graph not updated (non-fatal): {graph_note['why']}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "compiled_at": now.isoformat(timespec="seconds"),
        "hypotheses": list(candidates.values()),
        "per_source": per_source,
        "seats": seats,
        "seats_dark": seats_dark,
        "agreement": {"candidates_with_2plus_sources": agreement},
        "disagreement": disagreement,
        "intake": {"max_rows_per_pass": MAX_ROWS_PER_PASS, **_LAST_INTAKE},
        "graph": graph_note,
        "rows_accounted": sum(v["rows"] for v in per_source.values()),
        "executable_candidates": len(candidates),
        "deepening_tasks": len(deepening),
        "rule": "exact recipe or structured causal data only; no prose-to-family guessing",
    }, indent=1, default=str), "utf-8")
    DEEPEN.write_text(json.dumps({
        "built_at": now.isoformat(timespec="seconds"),
        "tasks": list(deepening.values()),
        "consumer": "hourly/daily research brains must recover a falsifiable rule or reject",
    }, indent=1, default=str), "utf-8")
    print(f"miner compiler: {sum(v['rows'] for v in per_source.values())} row(s) accounted; "
          f"{len(candidates)} executable candidate(s); {len(deepening)} exact-rule task(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
