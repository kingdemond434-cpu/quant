#!/usr/bin/env python3
"""MINER CONVERSION AND BREADTH -- what each miner actually converts, and what the book still lacks.

TWO QUESTIONS, ONE ANSWER (principal 2026-08-26, items 5 and 6). "Which miners earn their compute"
and "what independent breadth is missing" are the same question asked from opposite ends, because
a miner whose discoveries all become another session-range breakout has converted nothing: the
book already holds that bet, and N_eff does not move when you add a fifteenth copy of it.

WHAT IS MEASURED PER MINER, in the order a decision actually needs it:

  DISCOVERIES  raw rows produced -- the only number miners currently report, and the least useful
  NOVEL        rows whose MECHANISM is not already held. Deduplicated by economic exposure, not
               by title: two writeups calling the same asia-range breakout different names are
               one discovery, and counting them twice is how a desk mistakes volume for breadth
  TESTED       novel rows that actually reached a backtest -- the step where most corpora die
  SURVIVORS    tested rows that cleared the ten gates
  CONVERSION   survivors / discoveries; the only ratio that says whether the miner is earning
  ZERO-YIELD   a miner with discoveries but no survivor across the whole window: it is producing
               noise at cost, and under III.16 that is a defect to fix or retire, not a neutral

WHAT IS MEASURED FOR THE BOOK:

  FAMILY CONCENTRATION -- the share of certificates held by the single largest family. This desk
  is currently ~95% session_range_breakout, which is why N_eff collapses. The gap list is ordered
  by what would add the most INDEPENDENT bet, not by what is easiest to mine: carry, relative
  value, cross-asset residuals, volatility/liquidity transitions, event reactions, COT
  positioning, macro conditionality, execution-derived effects.

WHAT IS MEASURED PER AGENT (2026-09-09, inventory I10). The numerator above -- survivors per
miner -- is handed to `libs.ops.compute_ledger.rank`, the module that exists to be the
denominator and refuses to invent a numerator, and the result is `data/agent_value.json`:
survivors per compute-hour for every miner and LLM seat the ledger has costed, an UNPRICED list
(costed, no survivor count) and an UNCOSTED list (survivor count, no ledger row). A miner whose
rows never reached a backtest is UNJUDGED, not zero-valued: its survivor count is not a
measurement. Today every miner is UNCOSTED, because the ledger names hourly legs and no leg is
a miner -- and the artifact says exactly that, which is the join's first honest reading.

This file MEASURES and REPORTS. It does not retire miners on its own: killing a research line is
a decision with a cost, and the register plus the gap-wirer are where that decision belongs.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# THE REPO ROOT GOES ON sys.path BEFORE `libs` IS IMPORTED, and it is not optional.
# `python scripts/check_miner_conversion.py` makes sys.path[0] the SCRIPTS directory, never the
# root -- so `import libs` raised ModuleNotFoundError on every invocation that was not a `-m` run
# or a test with the root already on the path. That is exactly how the scheduled fence runs:
#   ExecStart=/home/quant/quant-platform/.venv/bin/python scripts/check_miner_conversion.py
# so `quant-miner-conversion.timer` had been dying at import on every fire since `request_repair`
# was added, and a fence that cannot start reports nothing rather than reporting a breach.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ops.repair_invoke import request_repair  # noqa: E402

DESK = ROOT / "desks" / "mt5"
INTEL = [DESK / "data" / "intelligence", ROOT / "data" / "intelligence"]
CERTS = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
HYP = DESK / "data" / "hypotheses" / "external_backtest_results.json"
OUT = ROOT / "data" / "miner_conversion.json"
ALARM = ROOT / "data" / "MINER_YIELD_ALARM.txt"
#: The compiler's artifact: `per_source` rows/candidates/deepening per miner and the `seats`
#: block (the LLM seats, reported with zeros when they donated nothing in the window).
COMPILED = DESK / "data" / "hypotheses" / "miner_candidates.json"
#: AgentValue -- survivors per compute-hour per miner and seat -- ALARM's sibling artifact.
AGENT_VALUE = ROOT / "data" / "agent_value.json"
#: Mirrors `miner_candidate_compiler.SEAT_SOURCES`; the compiled `seats` block's own keys win
#: whenever it is present, this is only the list to report as UNMEASURED when it is not.
SEATS = ("deepseek", "kimi_k3_deep_forest")

WINDOW_DAYS = 14
#: Families that would each add a genuinely different bet, ordered by independence from a
#: session-range book rather than by how easy they are to mine.
#: Names must match the generator registry EXACTLY -- `volatility_transition` here versus
#: `vol_transition` there reported a family as having no generator when one existed, which turns a
#: naming slip into a fabricated acquisition task.
BREADTH_TARGETS = (
    ("carry", "swap/rollover differentials -- a return stream with no directional overlap"),
    ("relative_value", "cross-pair and triangle residuals -- profits when direction does not"),
    ("cross_asset_residual", "metals vs FX vs index residuals after the common factor"),
    ("vol_transition", "regime changes in realised vol -- fires when breakouts stall"),
    ("liquidity_regime", "spread/depth regime shifts -- an execution-derived edge"),
    ("event_reaction", "scheduled macro releases -- a different clock entirely"),
    ("cot_positioning", "COT/positioning extremes -- weekly, uncorrelated to intraday ranges"),
    ("macro_conditional", "rates/DXY conditionality -- changes WHEN other sleeves should fire"),
)


def _read(p: Path):
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _mechanism_key(row: dict) -> str:
    """Dedup key by ECONOMIC EXPOSURE, never by title.

    Two rows are the same discovery if they trade the same family on the same instrument in the
    same session, however differently they are described. Titles are the worst possible key: the
    corpus is full of the same mechanism renamed by each source that found it.
    """
    fam = str(row.get("family") or row.get("mechanism") or "unknown").casefold()
    sym = str(row.get("symbol") or row.get("sym") or "*").upper()
    ses = str(row.get("session") or row.get("window") or row.get("selector") or "*").casefold()
    return f"{fam}|{sym}|{ses}"


#: What `_mechanism_key` returns for a row carrying no family, symbol or session -- i.e. for a row
#: it cannot identify at all, as opposed to one it identified as a repeat.
UNIDENTIFIED_KEY = "unknown|*|*"


def _duplication(keys: list[str]) -> dict:
    """Duplicate rate, or UNMEASURED when the rows cannot be told apart in the first place.

    ONE NUMBER WAS MEANING TWO OPPOSITE THINGS. `1 - distinct/rows` reads 100% when a miner found
    the same idea 36,982 times, and ALSO 100% when the key cannot identify any of them -- and the
    second is the common case, because `_mechanism_key` needs family|symbol|session and a raw
    miner row is a paragraph from a forum or a swap table that carries none of the three.

    Measured 2026-09-06: broker_swaps 36,982 rows -> "1 distinct mechanism, 100.0% duplicate",
    amarkets 17,444 -> the same. Read as duplication that is a damning verdict on a source; read
    correctly it says nothing about the source at all, and the rows may every one be different.
    A rate that reports the same figure for "all identical" and "none identifiable" is not a
    measurement, and this desk does not let an absent measurement wear a passing one's clothes.
    """
    total = len(keys)
    if not total:
        return {"duplicate_rate": None, "duplicate_basis": "no rows in the window"}
    unidentified = sum(1 for k in keys if k == UNIDENTIFIED_KEY)
    identified = total - unidentified
    if identified == 0:
        return {"duplicate_rate": None,
                "duplicate_basis": f"UNMEASURED: none of the {total:,} rows carry a "
                                   f"family/symbol/session, so they cannot be told apart -- "
                                   f"this is not evidence that they are duplicates",
                "unidentified_rows": unidentified}
    keyed = [k for k in keys if k != UNIDENTIFIED_KEY]
    out = {"duplicate_rate": round(1 - len(set(keyed)) / len(keyed), 3),
           "duplicate_basis": "among rows carrying an identity"}
    if unidentified:
        out["unidentified_rows"] = unidentified
    return out


def _source_miner(source: object) -> str:
    """The miner named inside a tested row's provenance string.

    Sources look like `ext_forexfactory_USDCHF_session_range_breakout`: a lane prefix, the MINER,
    then the symbol and family the compiler derived. The symbol is the first ALL-CAPS token, so
    everything before it is the miner name -- parsed positionally rather than by a fixed field
    count, because miner names contain underscores (`github_topics`, `ff_calendar_vintage`) and a
    split-on-underscore-take-index-1 would truncate them to `github` and `ff`.
    """
    text = str(source or "")
    if text.startswith("ext_"):
        text = text[4:]
    parts, name = text.split("_"), []
    for part in parts:
        if part and any(c.isalpha() for c in part) and part == part.upper():
            break                      # an ALL-CAPS token is the symbol; the miner ended before it
        name.append(part)
    return "_".join(name).strip("_")


def _reached(miner: str, tested_by_miner: Counter) -> int:
    """Tested rows attributable to `miner`, matching exactly then by prefix in EITHER direction.

    The provenance token and the directory name are not always identical -- `github` against a
    `github_topics` directory, for instance -- so an equality-only join would report a miner as
    having converted nothing while its rows sit in the results. Prefix matching in both
    directions covers the abbreviation and the expansion; anything looser would attribute one
    miner's conversions to another, which is worse than under-counting.
    """
    if miner in tested_by_miner:
        return tested_by_miner[miner]
    total = 0
    for token, n in tested_by_miner.items():
        if token and (miner.startswith(token) or token.startswith(miner)):
            total += n
    return total


def miner_rows(cutoff: datetime) -> dict[str, list[dict]]:
    """Recent discovery rows per miner directory."""
    out: dict[str, list[dict]] = {}
    for base in INTEL:
        if not base.exists():
            continue
        for src in sorted(d for d in base.iterdir() if d.is_dir()):
            rows: list[dict] = []
            for f in list(src.glob("discoveries_*.json")) + list(src.glob("*.json")):
                try:
                    if datetime.fromtimestamp(f.stat().st_mtime, tz=UTC) < cutoff:
                        continue
                except OSError:
                    continue
                data = _read(f)
                if isinstance(data, list):
                    rows.extend(r for r in data if isinstance(r, dict))
                elif isinstance(data, dict):
                    for v in data.values():
                        if isinstance(v, list):
                            rows.extend(r for r in v if isinstance(r, dict))
            if rows:
                out.setdefault(src.name, []).extend(rows)
    return out


def _short(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def _survivor_value(miner: str, per_miner: dict[str, dict]) -> tuple[float | None, str]:
    """A miner's survivor count as a numerator, or None with the reason it is not one."""
    m = per_miner.get(miner)
    if not isinstance(m, dict):
        return None, "no discovery rows from this source inside the window"
    if int(m.get("reached_backtest") or 0) <= 0:
        return None, ("no tested row carries this source's provenance -- its rows were never "
                      "judged, so 0 survivors is not a measured zero")
    return float(m.get("survivors") or 0), "survivors among rows that reached a backtest"


def agent_value(per_miner: dict[str, dict], compiled: dict | None, *,
                ledger: Path | None = None) -> dict:
    """AgentValue = survivors / compute-hours, per miner and per LLM seat, via compute_ledger.rank.

    THE NUMERATOR IS THIS FILE'S OWN SURVIVOR COUNT and it is handed over only for sources whose
    rows reached a backtest; `rank` supplies the denominator from the ledger and lists what it
    could not price. Nothing here divides by a guessed hour or fills a missing count with zero.
    """
    from libs.ops.compute_ledger import LEDGER, rank
    value_by_run: dict[str, float] = {}
    unjudged: dict[str, str] = {}
    for miner in sorted(per_miner):
        v, why = _survivor_value(miner, per_miner)
        if v is None:
            unjudged[miner] = why
        else:
            value_by_run[miner] = v
    table = rank(value_by_run, path=ledger)

    per_source = (compiled or {}).get("per_source") if isinstance(compiled, dict) else None
    per_source = per_source if isinstance(per_source, dict) else {}
    seats_block = (compiled or {}).get("seats") if isinstance(compiled, dict) else None
    seats: dict = {}
    if not isinstance(compiled, dict):
        seats = {"status": "UNMEASURED",
                 "missing_input": f"{_short(COMPILED)} is absent or unreadable -- the "
                                  f"compiler has not written a per-source table on this host"}
    elif not isinstance(seats_block, dict):
        seats = {"status": "UNMEASURED",
                 "missing_input": (f"{COMPILED.name} (compiled_at "
                                   f"{compiled.get('compiled_at')}) carries no `seats` block -- "
                                   f"it was compiled before miner_candidate_compiler.seat_summary "
                                   f"existed; re-run the compiler"),
                 "per_source_fallback": {s: per_source[s] for s in SEATS if s in per_source}}
    else:
        rows = {}
        for seat, st in sorted(seats_block.items()):
            v, why = _survivor_value(seat, per_miner)
            rows[seat] = {**(st if isinstance(st, dict) else {}),
                          "survivors": v, "survivors_basis": why,
                          "cost": ("UNCOSTED: no compute_ledger row is named after this seat; "
                                   "its runs are outside the costed hourly legs")}
            if seat in table.get("uncosted", []):
                rows[seat]["cost"] = "UNCOSTED: survivor count supplied, no ledger row"
        seats = {"status": "MEASURED" if rows else "UNMEASURED", "seats": rows}

    ranked = table.get("ranked") or []
    if ranked:
        status, missing = "MEASURED", ""
    elif not table.get("costed_runs"):
        status, missing = "UNMEASURED", table.get("why") or "nothing has been costed"
    else:
        status = "UNMEASURED"
        missing = ("compute_ledger rows are named after hourly-cycle legs "
                   f"({', '.join(sorted(table.get('unpriced') or [])[:6])}...), none after a "
                   "miner or a seat, so no agent's hours are known; per-agent value per hour "
                   "needs the miner runner to open a costed run per miner "
                   "(libs.ops.compute_ledger.costed(<miner>))")
    return {
        "measured_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "status": status,
        "missing_input": missing,
        "numerator": {
            "unit": "survivors",
            "basis": (f"certificates whose mechanism key matches a row of the source inside the "
                      f"{WINDOW_DAYS}d window (this file's per-miner SURVIVORS); only sources "
                      f"whose rows reached a backtest are priced -- a source never judged has "
                      f"no measured zero. Not dE[log W]: the allocator's marginal growth per "
                      f"certificate is not yet joined per source"),
            "sources_priced": len(value_by_run),
            "sources_unjudged": len(unjudged),
        },
        "denominator": {
            "unit": "compute_ledger hours (wall-clock)",
            "ledger": _short(ledger or LEDGER),
            "window_days": table.get("window_days"),
            "costed_runs": table.get("costed_runs"),
            "total_hours": table.get("total_hours"),
        },
        "value_by_run": value_by_run,
        "unjudged": unjudged,
        "per_source_rows": {s: per_source[s] for s in sorted(per_source) if s in per_miner},
        "table": table,
        "seats": seats,
        "rule": ("AgentValue = realised survivors / compute-hours, from libs.ops.compute_ledger."
                 "rank; UNPRICED = costed with no survivor count, UNCOSTED = survivor count with "
                 "no ledger row, UNJUDGED = rows never reached a backtest. None of the three is "
                 "a ranking position and none is a zero"),
    }


def main() -> int:
    now = datetime.now(tz=UTC)
    cutoff = now - timedelta(days=WINDOW_DAYS)

    certs = (_read(CERTS) or {}).get("survivors") or {}
    held = {_mechanism_key({"family": (c.get("shadow_spec") or {}).get("family"),
                            "symbol": (c.get("shadow_spec") or {}).get("symbol"),
                            "session": (c.get("shadow_spec") or {}).get("selector")})
            for c in certs.values()}
    fam_counts = Counter(str((c.get("shadow_spec") or {}).get("family") or "unknown")
                         for c in certs.values())

    tested_rows = [r for r in (_read(HYP) or []) if isinstance(r, dict)]
    tested = {_mechanism_key(r) for r in tested_rows}
    tested_by_miner = Counter(_source_miner(r.get("source")) for r in tested_rows)
    tested_by_miner.pop("", None)
    survivor_keys = held

    per_miner: dict[str, dict] = {}
    zero_yield: list[str] = []
    for miner, rows in sorted(miner_rows(cutoff).items()):
        keys = [_mechanism_key(r) for r in rows]
        uniq = set(keys)
        novel = uniq - held
        # MEASURED BY PROVENANCE, NOT BY A RECOMPUTED KEY -- and this is the whole reason the
        # board read 0 for 49 of 53 miners.
        #
        # `_mechanism_key` is family|SYMBOL|session. A tested row has all three. A RAW MINER ROW
        # has none of them: it is a paragraph from a forum, a swap table or a paper, and the
        # symbol and family are what the COMPILER derives from it. So every raw row keys to
        # `unknown|*|*` -- which is why broker_swaps showed 36,982 rows as 1 distinct mechanism at
        # a 100.0% duplicate rate -- and `novel & tested` was empty by construction, whatever the
        # pipeline did. Measured 2026-09-06: the compiler was in fact converting 178,753 rows into
        # 364 executable candidates while this reported that nothing reached a backtest.
        #
        # The tested rows carry `source` (ext_<miner>_<SYMBOL>_<family>) all the way from the
        # miner that found them, so provenance survives the very transformation that destroys the
        # key. Counting it answers the question actually being asked -- did this miner's work
        # reach the gauntlet -- instead of a question no miner could ever answer yes to.
        reached = _reached(miner, tested_by_miner)
        per_miner[miner] = {
            "discoveries": len(rows),
            "distinct_mechanisms": len(uniq),
            "novel_mechanisms": len(novel),
            "reached_backtest": reached,
            "reached_basis": "source provenance on tested rows",
            "survivors": len(uniq & survivor_keys),
            "conversion": round(len(uniq & survivor_keys) / len(rows), 4) if rows else None,
            **_duplication(keys),
        }
        # ZERO-YIELD MEANS TESTED AND FAILED, NOT MERELY UNCERTIFIED. Calling a miner "noise at
        # cost" when its rows never reached a gauntlet blames the source for a plumbing gap, and
        # the remedy that follows -- retire the miner -- deletes work that was never judged.
        if len(rows) >= 20 and reached > 0 and not (uniq & survivor_keys):
            zero_yield.append(miner)

    total_certs = sum(fam_counts.values())
    top_family, top_n = (fam_counts.most_common(1) or [("none", 0)])[0]
    concentration = round(top_n / total_certs, 3) if total_certs else None
    # A family is now three states, not two, and the difference is what to DO about it:
    #   held        -- a certificate exists
    #   reachable   -- a generator exists and its input is present; it just has not certified yet
    #   unreachable -- no generator, or its input is not recorded (an ACQUISITION task, which is a
    #                  completely different piece of work from "nobody mined it")
    try:
        import sys as _sys
        _sys.path.insert(0, str(DESK))
        from mt5desk.families_orthogonal import FAMILY_INPUTS, ORTHOGONAL_FAMILIES
    except Exception:
        ORTHOGONAL_FAMILIES, FAMILY_INPUTS = {}, {}
    missing = []
    for f, why in BREADTH_TARGETS:
        if any(f in k for k in held):
            continue
        needs = FAMILY_INPUTS.get(f, ("unknown", None))[0]
        missing.append({
            "family": f, "why": why,
            "state": "REACHABLE" if f in ORTHOGONAL_FAMILIES else "NO_GENERATOR",
            "needs": needs,
        })

    report = {
        "measured_at": now.isoformat(timespec="seconds"),
        "window_days": WINDOW_DAYS,
        "miners": per_miner,
        "zero_yield_miners": zero_yield,
        "book_breadth": {
            "certificates": total_certs,
            "families": dict(fam_counts),
            "largest_family": top_family,
            "family_concentration": concentration,
            "missing_families": missing,
            "why": ("concentration is the share of certificates in the single largest family. "
                    "Near 1.0 means every certificate is the same bet, and no amount of mining "
                    "inside that family raises the book's effective independent bets."),
        },
        "note": ("Deduplication is by economic exposure (family|symbol|session), never by title: "
                 "the corpus renames the same mechanism per source, and counting those as "
                 "separate discoveries mistakes volume for breadth."),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=1, default=str), "utf-8")

    av = agent_value(per_miner, _read(COMPILED))
    AGENT_VALUE.write_text(json.dumps(av, indent=1, default=str), "utf-8")

    print(f"miner conversion: {len(per_miner)} miner(s) with rows in {WINDOW_DAYS}d; "
          f"{len(zero_yield)} zero-yield")
    print(f"agent value: {av['status']} -- {len(av['table'].get('ranked') or [])} priced, "
          f"{len(av['table'].get('uncosted') or [])} uncosted, "
          f"{len(av['table'].get('unpriced') or [])} unpriced, {len(av['unjudged'])} unjudged; "
          f"seats {av['seats'].get('status')}"
          + (f"\n   missing input: {av['missing_input']}" if av["missing_input"] else ""))
    print(f"book breadth: {total_certs} certificate(s), largest family '{top_family}' "
          f"= {concentration} of the book; {len(missing)} target family(ies) absent")
    for row in missing[:8]:
        print(f"   {row['state']:12} {row['family']:22} needs: {row['needs']}")

    findings = []
    if concentration is not None and concentration > 0.8:
        findings.append(f"BREADTH: {concentration:.0%} of certificates are '{top_family}' -- the "
                        f"book is close to one bet; mining more of it cannot raise N_eff")
    if zero_yield:
        findings.append(f"ZERO-YIELD: {', '.join(zero_yield[:6])} produced 20+ rows and no "
                        f"survivor in {WINDOW_DAYS}d -- noise at cost (III.16)")
    if findings:
        ALARM.write_text("MINER/BREADTH " + now.isoformat(timespec="seconds") + "\n\n"
                         + "\n".join(f"  - {f}" for f in findings) + "\n", "utf-8")
        print("\n" + "\n".join(f"  - {f}" for f in findings))
        request_repair("miner-conversion breach")
        return 1
    if ALARM.exists():
        ALARM.unlink()
    return 0


if __name__ == "__main__":
    sys.exit(main())
