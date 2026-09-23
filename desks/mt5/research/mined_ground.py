"""TURN MINER + MOAT OUTPUT INTO GAUNTLET INPUT -- the missing half of every mining cycle.

WHY NOTHING THE MINERS FOUND EVER BECAME A SURVIVOR (principal 2026-08-26: "the python gauntlet
must do this for all local miner minings too, all discoveries extracted for survivors" and "moat
mining must work with the python miner for survivors always, every hour, into that same
gauntlet"). 740 discovery files exist. Not one has ever reached the ten gates, and the reason is
shape, not quality:

    {"source": "propfirm_boards", "kind": "fetch_error", "title": "...",
     "url": "...", "text": "...", "symbols": [], "needs_selector_work": true}

That is a WEB ARTEFACT. The gauntlet judges realised trades, so it needs (symbol, family, params).
No amount of scheduling connects the two -- and 22 miners were scored "zero-yield" for producing
things the desk had no way to test.

WHAT A MINED DISCOVERY ACTUALLY CONTRIBUTES. Not a strategy: a POINTER TO GROUND. A leaderboard
naming AUDCAD, a writeup about gold's London fix, a moat row showing unusual spread behaviour on
an index -- each says "there may be something here", which is a claim about WHERE to look, not
about what to trade. So this converts discoveries into a ranked search target list, and the
generic searcher does the finding. Mining supplies attention; the searcher supplies hypotheses;
the ten gates supply the verdict. Nobody's job is confused with anyone else's.

THE MOAT IS THE SAME SHAPE AND GETS THE SAME PATH. Its rows are the desk's own recorded tape --
the one dataset nobody else has -- so a symbol appearing there with unusual behaviour is a
stronger pointer than a forum post, and it is weighted accordingly. It is not a separate pipeline:
it feeds the identical target list, hourly, into the identical gauntlet.

WHAT IT REFUSES. It never invents a hypothesis from prose. A discovery with no resolvable MT5
symbol contributes nothing and is counted as such -- `fetch_error` rows and empty `symbols` lists
are reported, not quietly dropped, because a miner producing only fetch errors is a broken miner
and that fact should be visible rather than averaged away.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
INTEL = [BASE / "data" / "intelligence", BASE.parent.parent / "data" / "intelligence"]
#: THE MT5 MOAT IS THE TICK TAPE, NOT moat_series.jsonl. That file is 340MB of the RETIRED
#: crypto moat -- its rows are keyed "bybit/1000CATUSDT" and contain no MT5 symbol, so pointing
#: moat scanning at it reported "the moat found nothing" while the desk's real proprietary tape
#: sat unused beside it. The MT5 moat is data/tape/ticks/<SYMBOL>/<day>.parquet: the desk's own
#: broker-native quotes, which is precisely the dataset nobody else can buy.
MOAT_TAPE = BASE / "data" / "tape" / "ticks"
UNIVERSE = BASE / "data" / "universe"
OUT = BASE / "data" / "hypotheses" / "mined_targets.json"

WINDOW_DAYS = 7
#: Moat rows are the desk's own tape -- nobody else has them -- so a symbol surfacing there is a
#: stronger pointer than a forum mention and ranks above it.
MOAT_WEIGHT = 3.0
MINER_WEIGHT = 1.0


def _read(p: Path):
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def known_symbols() -> set[str]:
    """The tradable universe, from the registry -- never a hardcoded list."""
    return {(p.stem.rpartition("_")[0] or p.stem).upper()
            for p in UNIVERSE.glob("*.parquet")}


def _symbols_in(row: dict, universe: set[str]) -> set[str]:
    """Symbols a discovery actually names. Declared field first, then text, never a guess.

    THE OLD PATTERN ONLY SPOKE FX: `[A-Z]{3,6}(USD|JPY|...)` cannot match US500, NAS100 or a
    company-name symbol like Apple -- so a miner writing about index breadth or a single stock
    scored "names NO symbol" no matter how specific it was, and 20 of 42 miners sat dead on
    ground the universe actually lists. Uppercase alnum tokens catch every code-style symbol;
    the alias scan catches the equity CFDs the broker lists by NAME. Membership in the live
    universe remains the only admission -- text never invents a symbol.
    """
    found: set[str] = set()
    declared = row.get("symbols")
    if isinstance(declared, list):
        found |= {str(s).upper() for s in declared if str(s).upper() in universe}
    blob = " ".join(str(row.get(k) or "") for k in ("title", "text", "url", "mechanism"))
    if blob.strip():
        up = blob.upper()
        for token in set(re.findall(r"\b[A-Z][A-Z0-9]{1,9}\b", up)):
            if token in universe:
                found.add(token)
        # Company-name symbols carry chars the token walk cannot ('&', '-', length): scan for
        # each such universe name directly, on word boundaries, in the uppercased text.
        for sym in universe:
            if sym in found or re.fullmatch(r"[A-Z][A-Z0-9]{1,9}", sym):
                continue
            if re.search(r"(?<![A-Z0-9])" + re.escape(sym) + r"(?![A-Z0-9])", up):
                found.add(sym)
    return found


def scan_miners(universe: set[str], cutoff: datetime) -> tuple[Counter, dict]:
    """Symbol attention from recent miner output, plus per-miner health."""
    weights: Counter = Counter()
    health: dict[str, dict] = {}
    for base in INTEL:
        if not base.exists():
            continue
        for src in sorted(d for d in base.iterdir() if d.is_dir()):
            rows_seen = errors = symbol_rows = 0
            for f in src.glob("discoveries_*.json"):
                try:
                    if datetime.fromtimestamp(f.stat().st_mtime, tz=UTC) < cutoff:
                        continue
                except OSError:
                    continue
                data = _read(f)
                rows = data if isinstance(data, list) else []
                if isinstance(data, dict):
                    for v in data.values():
                        if isinstance(v, list):
                            rows.extend(v)
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    rows_seen += 1
                    if str(row.get("kind") or "").endswith("error"):
                        errors += 1
                        continue
                    syms = _symbols_in(row, universe)
                    if syms:
                        symbol_rows += 1
                        for s in syms:
                            weights[s] += MINER_WEIGHT
            if rows_seen:
                health[src.name] = {
                    "rows": rows_seen, "fetch_errors": errors,
                    "rows_naming_a_symbol": symbol_rows,
                    "usable_rate": round(symbol_rows / rows_seen, 3),
                }
    return weights, health


def scan_moat(universe: set[str], cutoff: datetime) -> Counter:
    """Symbols the desk's OWN tape flags -- the pointer nobody else can buy."""
    weights: Counter = Counter()
    if not MOAT_TAPE.exists():
        # The tape lives on the desk box. Its state builder publishes a per-symbol coverage
        # summary every 5 minutes and the pull carries it here, so the moat counts on BOTH boxes
        # instead of silently contributing zero wherever the parquet happens not to be.
        summary = _read(BASE / "data" / "moat_coverage.json")
        if isinstance(summary, dict):
            for sym, days in (summary.get("coverage") or {}).items():
                if str(sym).upper() in universe:
                    try:
                        weights[str(sym).upper()] += MOAT_WEIGHT * int(days)
                    except (TypeError, ValueError):
                        continue
        return weights
    for d in MOAT_TAPE.iterdir():
        if not d.is_dir():
            continue
        sym = d.name.upper()
        if sym not in universe:
            continue
        # Weight by RECENT COVERAGE: a symbol the desk has been taping this week is ground it can
        # research with data nobody else holds, and depth of coverage is the strength of that
        # pointer. Days are counted, not bytes -- one huge file is not a week of observation.
        days = 0
        for f in d.glob("*.parquet"):
            try:
                if datetime.fromtimestamp(f.stat().st_mtime, tz=UTC) >= cutoff:
                    days += 1
            except OSError:
                continue
        if days:
            weights[sym] += MOAT_WEIGHT * days
    return weights


def main() -> int:
    now = datetime.now(tz=UTC)
    cutoff = now - timedelta(days=WINDOW_DAYS)
    universe = known_symbols()

    miner_w, health = scan_miners(universe, cutoff)
    moat_w = scan_moat(universe, cutoff)
    total: Counter = Counter()
    total.update(miner_w)
    total.update(moat_w)

    # THE UNIVERSE IS THE FLOOR, ATTENTION IS THE ORDER (principal 2026-08-28: "all miners
    # always hunt all MT5 universe classes ... no hardcoded exclusion"). Miner attention and
    # moat coverage decide WHAT GOES FIRST; they may never decide what is reachable at all. A
    # symbol no source happens to mention scored zero and never appeared in the target list, so
    # whole classes the desk owns went unhunted -- BOND at zero coverage while three gilt/UST
    # instruments sat tradable (measured 2026-08-28). Every usable symbol now enters at score
    # 0.0 behind the ranked ground, so the rotation cursor reaches all of them in finite time.
    for sym in sorted(universe):
        total.setdefault(sym, 0.0)

    targets = [{"symbol": s, "score": round(w, 2),
                "from_miners": round(miner_w.get(s, 0.0), 2),
                "from_moat": round(moat_w.get(s, 0.0), 2)}
               for s, w in total.most_common()]
    dead = sorted(k for k, v in health.items()
                  if v["rows"] >= 10 and v["rows_naming_a_symbol"] == 0)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "built_at": now.isoformat(timespec="seconds"),
        "window_days": WINDOW_DAYS,
        "universe_size": len(universe),
        "targets": targets,
        "miner_health": health,
        "miners_naming_no_symbol": dead,
        "note": ("Mining supplies ATTENTION, not hypotheses: a discovery points at ground worth "
                 "searching. edge_search does the finding on these symbols first, and the same "
                 "ten gates judge the result. Moat rows weigh more because the desk's own tape "
                 "is the one pointer nobody else has."),
    }, indent=1, default=str), "utf-8")

    print(f"mined ground: {len(targets)} symbol(s) with attention "
          f"({len(miner_w)} from miners, {len(moat_w)} from the moat)")
    for row in targets[:10]:
        print(f"   {row['symbol']:10} score={row['score']:<7} "
              f"miners={row['from_miners']:<6} moat={row['from_moat']}")
    if dead:
        print(f"  miners producing rows but naming NO symbol: {', '.join(dead[:8])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
