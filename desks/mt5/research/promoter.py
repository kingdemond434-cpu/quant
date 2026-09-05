"""Auto-promotion / auto-retirement for shadow-validated sleeves.

Runs daily at 22:00 UTC inside the gateway loop (after shadow_forward.main()).

CAPITAL IS EARNED BY dE[log W], AND THE ASYMMETRY IS THE POINT (principal, 2026-09-05):

    "Don't rank candidates primarily by Sharpe. Rank by dE[log W] after adding the candidate to
     the existing portfolio ... Now make that principle the actual automatic admission criterion."

    "Never have 'this strategy is allocated 3% forever'. Have 'this strategy currently earns 7.4%
     portfolio risk because its posterior edge, uncertainty, conditional state and covariance make
     that the current robust log-optimal allocation.' Five minutes/hour/session later, it can
     be 0%."

    "promotion slow / demotion immediate, evidence-based allocation, and fractional Kelly."

WHAT THAT CHANGES HERE, AND WHAT IT SUPERSEDES. The 2026-09-04 order ("all promotion candidates
get into the live account immediately, no waiting, no permission, always") is about the ROSTER and
it still stands: a matured candidate is written to `data/sleeves.json` on the run its clock
matures, and nothing holds it in a queue. What it never said, and what the 2026-09-05 order now
settles, is how much CAPITAL that row carries. Three rules, all of them stricter than what stood:

  ADDING RISK IS SLOW. A row goes to `status: LIVE` only when the accumulated evidence is in --
  the forward clock matured, the certificate stands, the cost re-grade is not failing -- AND
  `pf_allocator`'s fresh admission scan says adding it to the book the desk is actually holding
  RAISES robust E[log W] at the same total heat. A candidate that does not is written
  `status: STANDBY` with the number that refused it. Standby is not retirement: the row, its
  clock and its certificate all stand, and it is re-judged every run. Every LATER move out of
  standby needs `PROMOTE_ADMIT_STREAK` consecutive positive readings, counted on the row itself,
  so a marginal sitting on zero cannot flap the book in and out on sampling noise.

  REMOVING RISK IS IMMEDIATE. One current reading is enough. A LIVE sleeve the latest solve gives
  no heat goes to STANDBY on that reading alone -- no trade count, no drawdown bar, no waiting.
  It is NOT retired and NOT killed in its shadow clock: the moment the solve wants it again it
  comes back. That is the "0%, and five minutes later it can be 7.4%" the principal asked for.

  SIZE IS AN OUTPUT, NOT A CONSTANT. `PROMOTED_RISK_FRAC` used to be written onto every promoted
  row -- literally "this strategy is allocated 3% forever". The row now carries the heat the
  allocator's own solve gave that sleeve, with `risk_frac_source` naming where it came from, and
  the old constant survives only as a CEILING on what this module may write, so nothing here can
  raise size by fiat.

RETIREMENT IS UNCHANGED and stays the one-way door: its thresholds are untouched, and it still
writes KILL into the shadow clock. Standby is the reversible one; retirement is not.

PROMOTE (automatic, on the run the clock matures -- principal 2026-09-04):
  - every lane's forward clock (shadow_forward, qquant_shadow, scalp_shadow) says
    PROMOTION CANDIDATE and the sleeve is not yet promoted: it is written to
    data/sleeves.json on THIS run, and the gateway trades it on its next pass (< 1 min)
    IF the allocator's fresh dE[log W] scan admits it -- otherwise the row is written
    STANDBY and re-judged every run (see ADDING RISK IS SLOW above). The refusals are the
    certificate (a candidate whose exact spec is not in the ten-gate authority set is
    BLOCKED_UNIVERSAL_GATES, because a candidate without a certificate is not a candidate)
    and the marginal (a candidate that does not raise the book's robust growth gets no
    capital, however good its standalone Sharpe).
  - XAUUSD window challengers no longer wait for, or die to, the armed gold book. The
    comparison against the armed window's forward expectancy is still MEASURED and written
    on the sleeve row (`vs_armed`) for the allocator and the attribution to read; capital
    is then the allocator's decision by dElogW, never a promoter's heuristic (growth
    governance rule 1: a risk reduction that has not proved it raises E[log W] does not
    gate).
  - scalp sleeves carry their exact recipe (timeframe, family, session, ATR geometry) and
    exec="scalp_market"; the gateway executes them through mt5desk/scalp_exec.py.

RETIRE (fully automatic):
  - for each LIVE promoted sleeve: forward stats from the live ledger:
    * n >= 10 and rolling-20 exp <= 0      -> RETIRED (edge gone)
    * forward maxDD < -25R                 -> RETIRED (tail breach)
    * n >= 50 and exp < 0.05R              -> RETIRED (weak)
  - retired sleeves are removed from trading config and marked KILL in shadow
    state (never re-promoted).

The armed gold book is NOT managed here (hunt5 authority, armed by human).
"""

import json
import math
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mt5desk import provenance
from shadow_admission import authorized_specs

BASE = Path(__file__).resolve().parent.parent
SHADOW_DIR = BASE / "reports" / "shadow"
SLEEVES_FILE = BASE / "data" / "sleeves.json"
LEDGER = BASE / "data" / "live_ledger.jsonl"
LOG = BASE / "logs" / "promoter.log"
#: The recertification audit (scripts/recertify_canon.py, daily before this runs): every
#: standing certificate re-judged under the CURRENT cost model. A certificate that no longer
#: passes its own ten gates at today's costs is not promoted, whatever its forward clock says.
RECERT_AUDIT = BASE / "reports" / "recertification_audit.json"
#: An audit older than this is a report, not a gate: costs may have moved since, and the daily
#: step that refreshes it is the cure -- blocking forever on a stale re-judge would be a veto
#: nobody re-measures (rule 1).
RECERT_FRESH_H = 72.0

#: A cross-process append collision on Windows clears in milliseconds. Six tries over ~0.5s
#: outlasts it; longer would be a promoter that waits on a log file, the wrong priority.
_LOG_RETRIES = 6
_LOG_RETRY_SLEEP_S = 0.03

# SIZING (principal 2026-08-25): the gateway sizes promoted sleeves at order time -- 3% of
# equity base risk off the bracket's own stop distance (mt5desk/sizing.py), authority-ramped
# 0.75%/1.5%/3% by live trade count. Raising a sleeve's risk_frac above the base requires
# recorded economic justification and is capped at MAX_RISK_FRAC there.
#
# NO LONGER THE ALLOCATION -- ONLY THE CEILING ON ONE (principal 2026-09-05). This constant was
# written verbatim onto every promoted row, which is exactly the "allocated 3% forever" the
# principal ordered removed. `promoted_risk_frac()` now derives the number from the allocator's
# own solve for that sleeve and clamps it HERE, so this change can only ever reduce what the
# promoter writes, never raise it.
PROMOTED_RISK_FRAC = 0.03

#: The allocation artifact whose `admission` block is the criterion, and whose `book` is the
#: current reading. Module-level so a test can point the promoter at a fixture tree.
ALLOCATION = BASE / "reports" / "pf_allocation.json"
#: How old the allocator's scan may be and still price capital. `pf_allocator` re-measures on its
#: hourly heavy clock and the short clocks carry the last one forward stamped with its age, so a
#: scan older than this means the allocator has not run for a day -- the same 26h
#: `libs.portfolio.allocator_proof.MAX_AGE_S` allows the sizing certificate, one freshness rule.
#: Taken from the allocator's own published expiry when it is readable (`admission.max_age_s`),
#: so the rule cannot drift apart between the writer and this reader.
ADMISSION_MAX_AGE_H = 26.0
#: Consecutive passes a STANDBY sleeve's dE[log W] must be positive before it takes capital AGAIN.
#: One reading removes risk; two consecutive readings restore it. That asymmetry is the whole
#: instruction, and it is what stops a sleeve whose marginal sits on zero from flapping the book
#: in and out on sampling noise. First promotion does not use it: a candidate has already spent
#: the forward clock's 50 trades / 14 days earning the right to be judged at all.
PROMOTE_ADMIT_STREAK = 2
#: What each direction costs in evidence, said out loud so the asymmetry cannot be edited away by
#: accident. Read by `desks/mt5/tests/test_marginal_admission.py`.
EVIDENCE_TO_ADD_RISK = ("matured forward clock", "standing certificate", "no fresh cost regrade",
                        "a fresh, positive dE[log W] against the held book")
EVIDENCE_TO_REMOVE_RISK = ("the current dE[log W] reading",)
PROMOTED_LOT = 0.01     # legacy display value; sleeve_set() overrides lot to "auto_ramp"
CHAMPION_MARGIN = 0.02   # challenger must beat armed forward exp by this much
RETIRE_MIN_N = 10
RETIRE_MAX_DD = -25.0
RETIRE_MIN_EXP = 0.05

GOLD_WINDOWS = ["asia", "london_am", "ny_open", "afternoon"]


def _sleeve_timeframe(params: dict | None) -> str:
    """The chart a certificate was hunted on. Absent means H1 -- the desk-wide spelling, see
    `research/frontier_identity`: every certificate written before the M1..D1 ladder is an H1
    one, and naming H1 explicitly would rename all of them at once."""
    return str((params or {}).get("timeframe") or "H1").upper()


def plog(msg: str) -> None:
    """Append one line to the promoter log. A locked log NEVER fails the promoter.

    WINDOWS LOCKS FILES EXCLUSIVELY AND THIS RUNS ON WINDOWS. Two processes appending collide, and
    the loser raised PermissionError out of `plog` -- called from inside the promotion pass, so a
    LOGGING collision aborted the PROMOTION. Measured 2026-09-03 on the desk box, every shadow
    cycle reported status FAILED with errors.promoter = PermissionError on promoter.log, a file
    that was writable, appendable and last modified a week earlier. The cycle had 43 sleeves with
    forward trades and zero evidence-blocked sleeves; the only thing that failed was note-taking.

    `print` happens first and unconditionally, so the line still reaches the cycle's captured
    output and nothing is lost -- a log the desk could not write is worth strictly less than a
    promotion it did not run.
    """
    line = f"{datetime.now(tz=UTC).isoformat(timespec='seconds')} {msg}"
    print(line)
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return
    for attempt in range(_LOG_RETRIES):
        try:
            with LOG.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
            return
        except (PermissionError, OSError):
            if attempt == _LOG_RETRIES - 1:
                return
            time.sleep(_LOG_RETRY_SLEEP_S * (attempt + 1))


def load_shadow() -> dict:
    p = SHADOW_DIR / "shadow_state.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def artifact_of(row: dict) -> dict:
    """The StrategyArtifact behind a sleeve row: its version hash and what the validator says.

    libs/research/strategy_artifact.py was "the only object that may reach the allocator" and
    had no importer on this tree (found 2026-09-05). It is RECORDED on every LIVE row here, so
    what trades is named by a hash of its mechanism, recipe, instruments and certificates, and
    a reader can tell two rows with the same name apart across a code change. It does not add
    a refusal: the universal rule (promotion is the forward clock's) stands, and a row the
    validator dislikes carries `artifact.problems` for the health report to show -- a row with
    no family or no symbol is untradeable by construction and is the one case dropped.
    """
    try:
        from libs.research.strategy_artifact import StrategyArtifact, validate
        fam = str(row.get("family") or ("session_range_breakout" if row.get("window") else ""))
        sym = str(row.get("symbol") or "").upper()
        recipe = {k: row[k] for k in ("selector", "state", "params", "timeframe", "session",
                                      "stop_atr", "target_atr", "max_hold", "window")
                  if k in row}
        a = StrategyArtifact(
            strategy_id=str(row.get("name") or ""), mechanism=fam,
            source=str(row.get("certificate") or ""), family=fam, params=dict(recipe),
            symbols=[sym] if sym else [], timeframes=[str(row.get("timeframe") or "H1")],
            entry={"family": fam, "selector": row.get("selector"), "side": row.get("side")},
            exit={"ttl_bars": row.get("max_hold"), "stop_atr": row.get("stop_atr"),
                  "target_atr": row.get("target_atr")},
            execution={"policy": str(row.get("exec") or "family_market")},
            state_conditioning={"state": row.get("state")},
            data_requirements=[f"bars.{row.get('timeframe') or 'H1'}:{sym}"] if sym else [],
            feature_ids=[], cost_assumptions={"cost_hash": row.get("cost_hash"),
                                              "cost_r": row.get("cost_r")},
            validation_certificate={"status": "PASS" if row.get("certificate") else "",
                                    "certificate": row.get("certificate")},
            lockbox_certificate={}, shadow_evidence={"n": row.get("shadow_n"),
                                                     "exp": row.get("shadow_exp")})
        v = validate(a)
        return {"version_hash": v["version_hash"], "ok": bool(v["ok"]),
                "problems": list(v["problems"])}
    except Exception as exc:                                        # noqa: BLE001
        return {"version_hash": None, "ok": False,
                "problems": [f"artifact unavailable: {type(exc).__name__}: {exc}"]}


def save_sleeves(sleeves: list[dict]) -> None:
    SLEEVES_FILE.parent.mkdir(parents=True, exist_ok=True)
    kept: list[dict] = []
    for row in sleeves:
        if str(row.get("status") or "").upper() == "LIVE":
            art = artifact_of(row)
            row["artifact"] = art
            if "no family" in art["problems"] or "no symbol" in art["problems"]:
                plog(f"{row.get('name')}: LIVE row dropped -- untradeable by construction "
                     f"({', '.join(art['problems'])})")
                continue
        kept.append(row)
    SLEEVES_FILE.write_text(json.dumps({"sleeves": kept}, indent=2),
                            encoding="utf-8")


def load_sleeves() -> list[dict]:
    if not SLEEVES_FILE.exists():
        return []
    try:
        return json.loads(SLEEVES_FILE.read_text(encoding="utf-8")).get("sleeves", [])
    except Exception:
        return []


def load_ledger() -> list[dict]:
    """Closed trades from the account THIS DESK IS CURRENTLY TRADING, and no others.

    THE FILE IS NOT ONE ACCOUNT'S HISTORY. The broker is switched by editing one line of
    data/terminal_path.txt, so the moment that points at a Fusion DEMO terminal, demo fills append
    to this same file -- and they are read below to RETIRE live sleeves and to judge gold
    challengers against the armed book. Demo fills are optimistic in exactly the dimension that
    matters (a demo server fills stops at the trigger with no slippage), so a sleeve could be kept
    alive by practice results, or a newly funded live account judged on demo history sitting above
    it in the file.

    Rows predating provenance match nothing and are excluded. That is a deliberate loss of
    history: the alternative is silently treating pre-switch trades as belonging to whatever
    account happens to be connected today, which is the defect itself.
    """
    if not LEDGER.exists():
        return []
    try:
        rows = [json.loads(line) for line in LEDGER.read_text(encoding="utf-8").splitlines()
                if line.strip()]
    except Exception:
        return []
    try:
        import MetaTrader5 as mt5
        acc = provenance.current_account(mt5.account_info())
    except Exception:
        acc = provenance.current_account(None)
    kept = [r for r in rows if provenance.same_account(r, acc)]
    if len(kept) != len(rows):
        plog(f"ledger: {len(kept)}/{len(rows)} rows are from the account in hand "
             f"(login={acc['login']} server={acc['server']} kind={acc['kind']}); "
             f"{len(rows) - len(kept)} from another account or predating provenance, excluded")
    return kept


def armed_forward_exp(ledger: list[dict], window: str) -> float | None:
    """Armed gold sleeve forward exp from the live ledger (same window)."""
    rs = [r["r_multiple"] for r in ledger if r["sleeve"] == f"gold_{window}"]
    if len(rs) < 5:
        return None
    return sum(rs) / len(rs)


def sleeve_forward_stats(ledger: list[dict], name: str) -> dict:
    rs = [r["r_multiple"] for r in ledger if r["sleeve"] == name]
    n = len(rs)
    if n == 0:
        return {"n": 0, "exp": 0.0, "max_dd": 0.0, "roll20_exp": 0.0}
    roll = rs[-20:] if n >= 20 else rs
    cum = []
    acc = 0.0
    for r in rs:
        acc += r
        cum.append(acc)
    max_dd = min(cum[i] - max(cum[:i + 1]) for i in range(len(cum)))
    return {"n": n, "exp": sum(rs) / n, "max_dd": float(max_dd),
            "roll20_exp": sum(roll) / len(roll)}


#: The hardcoded live book, by the names gateway.sleeve_set() emits. Kept here rather than
#: imported because promoter runs on the research side and gateway imports MetaTrader5, which is
#: Windows-only; a wrong name here retires nothing rather than the wrong thing, and the names are
#: asserted against the gateway by tests/test_gold_retire_names.py.
GOLD_SLEEVE_NAMES = ("gold_asia", "gold_london_am", "gold_afternoon")

#: Windows the gateway must stop emitting. Absent file = nothing retired, which is the state the
#: desk has been in until now, so behaviour is unchanged until a rule actually fires.
GOLD_RETIRED_FILE = BASE / "data" / "GOLD_RETIRED.json"


def _load_gold_retired() -> dict:
    try:
        v = json.loads(GOLD_RETIRED_FILE.read_text(encoding="utf-8"))
        return v if isinstance(v, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_gold_retired(rows: dict) -> None:
    GOLD_RETIRED_FILE.parent.mkdir(parents=True, exist_ok=True)
    GOLD_RETIRED_FILE.write_text(json.dumps(rows, indent=2), encoding="utf-8")


def degenerate_evidence(ledger: list[dict], name: str) -> str:
    """Why this sleeve's r-series cannot support a retirement, or "" when it can.

    RETIRING IS AS CONSEQUENTIAL AS PROMOTING AND HAD NONE OF THE GUARDS. Measured 2026-09-01:
    gold_asia was auto-retired on n=30 with exp EXACTLY -1.000R, roll20 EXACTLY -1.000R and
    max_dd -29.0 -- thirty consecutive losses of precisely one R -- while the account those
    sleeves trade went 500.00 -> 603.84 on the same day, +103.84. Real trading does not produce
    thirty identical outcomes; a constant series is the signature of a broken r_multiple
    computation, and the ledger it was read from is not on either box now.

    A series with NO DISPERSION carries no information about performance. Acting on it is not
    conservative -- it stops a book on a bug, and the stop looks exactly like a verdict
    afterwards. So dispersion is required before any retire rule may fire. This does not soften
    a single threshold: a genuinely losing sleeve has losing trades of DIFFERENT sizes and still
    trips every rule below.
    """
    rs = [r.get("r_multiple") for r in ledger if r.get("sleeve") == name]
    rs = [float(x) for x in rs if isinstance(x, (int, float))]
    if len(rs) < 2:
        return ""
    if len({round(x, 9) for x in rs}) == 1:
        return (f"every one of {len(rs)} r_multiples is exactly {rs[0]:+.3f} -- a constant series "
                f"is a computation defect, not performance; refusing to retire on it")
    if all(x == 0.0 for x in rs):
        return f"all {len(rs)} r_multiples are 0.0 -- risk_per_lot was unmeasurable on every fill"
    return ""


# ------------------------------------------------------------------- dE[log W] AS THE CRITERION

def _join_keys(name: str, symbol: str = "", family: str = "", selector: str = "") -> list[str]:
    """Every key a sleeve can be recognised by, most specific first.

    THE TWO SIDES NAME THE SAME SLEEVE DIFFERENTLY, and pretending otherwise is how a join
    silently matches nothing. `pf_allocator` prices `SYM_family_window`; the forward clocks key
    `SYM.window[.STATE]` or the certificate's own key. So the join is on the PARTS -- symbol,
    mechanism, selector -- with the raw name first for the case where they already agree, and
    every key is lowercased because neither side promises a case convention.
    """
    out = [str(name).strip().lower()] if name else []
    sym, fam, sel = (str(symbol).strip().lower(), str(family).strip().lower(),
                     str(selector).strip().lower())
    if sym and fam and sel:
        out.append(f"{sym}|{fam}|{sel}")
    if sym and sel:
        out.append(f"{sym}|{sel}")
    return out


def _index(rows: dict[str, dict]) -> dict[str, dict]:
    """Join key -> candidate row. AMBIGUOUS KEYS ARE DROPPED, never resolved by guessing.

    Two sleeves on the same symbol and selector but different mechanisms would both answer to
    `sym|selector`; funding one on the other's measurement is worse than not funding either, so a
    key that two rows claim is removed and those rows stay reachable only by their exact names.
    """
    idx: dict[str, dict] = {}
    clash: set[str] = set()
    for name, row in rows.items():
        if not isinstance(row, dict):
            continue
        for k in _join_keys(name, str(row.get("symbol") or ""), str(row.get("family") or ""),
                            str(row.get("selector") or "")):
            if k in idx and idx[k] is not row:
                clash.add(k)
            idx[k] = row
    for k in clash:
        idx.pop(k, None)
    return idx


def allocation_view(now: datetime | None = None) -> dict:
    """What the allocator currently says about every sleeve, or a named refusal to say anything.

    Returns `{fresh, why, age_h, at, candidates, book, zeroed, total_heat}` where `candidates` and
    `book` are indexed by every key `_join_keys` can produce. `fresh` is False -- and every
    capital decision below then refuses to ADD risk -- when the artifact is absent, unreadable,
    stale, or carries no measured admission scan. Absence is never permission (L1.28a): a desk
    that cannot price a candidate's marginal has not measured that the candidate raises growth.
    """
    try:
        doc = json.loads(ALLOCATION.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {"fresh": False, "why": f"{ALLOCATION.name} unreadable ({type(exc).__name__})",
                "candidates": {}, "book": {}, "zeroed": {}, "total_heat": 0.0, "age_h": None}
    stamp = str(doc.get("generated_utc") or "")
    try:
        age_h = ((now or datetime.now(tz=UTC)) - datetime.fromisoformat(stamp)
                 ).total_seconds() / 3600.0
    except ValueError:
        age_h = float("inf")
    adm = doc.get("admission") if isinstance(doc.get("admission"), dict) else {}
    # THE PARTS OF EVERY PRICED SLEEVE, so a FUNDED sleeve joins on the same terms a candidate
    # does. `book` is name -> heat and carries no symbol or mechanism; without this the funded
    # half of the join would only ever match on an exact name.
    universe = adm.get("universe") if isinstance(adm.get("universe"), dict) else {}
    book_rows = {str(k): {"heat": float(v), **{f: str((universe.get(str(k)) or {}).get(f) or "")
                                               for f in ("symbol", "family", "selector")}}
                 for k, v in (doc.get("book") or {}).items()
                 if isinstance(v, (int, float))}
    view = {
        "at": stamp, "age_h": (None if not math.isfinite(age_h) else round(age_h, 2)),
        "total_heat": float((doc.get("heat") or {}).get("total") or 0.0),
        "candidates": _index(adm.get("candidates") or {}),
        "book": _index(book_rows),
        # ROSTERED AND GIVEN NOTHING BY THIS SOLVE. A real reading, and the one a demotion may act
        # on when the admission scan's own budget did not reach the sleeve.
        "zeroed": _index({str(k): {"why": str(v),
                                   **{f: str((universe.get(str(k)) or {}).get(f) or "")
                                      for f in ("symbol", "family", "selector")}}
                          for k, v in (doc.get("book_zeroed") or {}).items()}),
        "admission_status": str(adm.get("status") or "ABSENT"),
        "admission_at": str(adm.get("measured_utc") or ""),
        "carried_from": str(adm.get("carried_from") or ""),
    }
    # THE SCAN HAS ITS OWN AGE, AND IT IS NOT THE ARTIFACT'S. The allocator measures the admission
    # scan on its HEAVY clock and the short clocks carry the answer forward into a freshly
    # timestamped artifact. So a scan taken a day ago can sit inside a file written a minute ago,
    # and reading the file's timestamp alone would be reading a stale measurement as fresh --
    # exactly the defect the carry-forward stamp exists to make visible. Both must be inside the
    # window; the older of the two is the one that decides.
    scan_age_h = age_h
    try:
        scan_age_h = max(age_h, ((now or datetime.now(tz=UTC))
                                 - datetime.fromisoformat(view["admission_at"])
                                 ).total_seconds() / 3600.0)
    except (TypeError, ValueError):
        pass
    view["scan_age_h"] = None if not math.isfinite(scan_age_h) else round(scan_age_h, 2)
    # THE WRITER'S OWN EXPIRY WHEN IT PUBLISHES ONE. Two copies of a freshness rule is how one of
    # them is silently edited; the local constant is the fallback for an artifact that carries
    # none, and a longer published expiry is never accepted -- stricter, never looser.
    max_age_h = ADMISSION_MAX_AGE_H
    published = adm.get("max_age_s")
    if isinstance(published, (int, float)) and 0 < float(published) / 3600.0 <= max_age_h:
        max_age_h = float(published) / 3600.0
    view["max_age_h"] = round(max_age_h, 2)
    if scan_age_h > max_age_h:
        view["fresh"] = False
        view["why"] = (f"the allocation is {age_h:.1f}h old and its admission scan "
                       f"{scan_age_h:.1f}h old (max {max_age_h:.0f}h): it describes a "
                       f"book that no longer exists, so it may not price capital")
        return view
    if view["admission_status"] != "MEASURED":
        view["fresh"] = False
        view["why"] = (f"the allocator published no measured admission scan "
                       f"(status {view['admission_status']!r}); no candidate has a dE[log W]")
        return view
    view["fresh"] = True
    view["why"] = (f"allocation {age_h:.1f}h old, admission scan {scan_age_h:.1f}h old over "
                   f"{len(adm.get('candidates') or {})} candidate(s) taken "
                   f"{view['admission_at']}" + (" (carried forward)" if view["carried_from"]
                                                else ""))
    return view


def admission_of(view: dict, name: str, symbol: str = "", family: str = "",
                 selector: str = "") -> tuple[dict | None, str]:
    """The sleeve's current reading and the key it joined on, or (None, why there is none).

    THREE PLACES A READING CAN COME FROM, most specific first, and each is a different sentence:

        the admission scan   this candidate was re-solved INTO the book and here is its dE[log W]
        the funded book      the allocator is already holding it, and its heat IS the reading
        the zeroed list      it is rostered and this solve gave it nothing -- a real refusal

    None means NONE OF THE THREE, which is not a refusal: it is a sleeve the allocator has never
    priced, or one the admission budget did not reach. That distinction matters, because a
    demotion may act on a refusal and must never act on a compute limit.
    """
    keys = _join_keys(name, symbol, family, selector)
    for k in keys:
        row = (view.get("candidates") or {}).get(k)
        if isinstance(row, dict):
            return row, f"joined on {k!r}"
    for k in keys:
        row = (view.get("book") or {}).get(k)
        if isinstance(row, dict):
            # Already funded by the allocator: its marginal was measured when it entered and its
            # heat IS the current reading. There is no candidate row for something already held.
            return ({"delta_elogw_per_day": None, "heat_earned": float(row.get("heat") or 0.0),
                     "admit": float(row.get("heat") or 0.0) > 0.0,
                     "why": f"already funded by the allocator at {float(row['heat']):.2%} heat"},
                    f"joined on {k!r} (funded book)")
    for k in keys:
        row = (view.get("zeroed") or {}).get(k)
        if isinstance(row, dict):
            return ({"delta_elogw_per_day": None, "heat_earned": 0.0, "admit": False,
                     "why": str(row.get("why") or "this solve gave the sleeve no heat")},
                    f"joined on {k!r} (zeroed by this solve)")
    return None, (f"no allocator row answers to any of {keys!r}: this sleeve is not in the priced "
                  f"universe, or the admission scan's budget did not reach it, so its marginal "
                  f"contribution has not been measured on this pass")


def promoted_risk_frac(row: dict | None, *, cap: float = PROMOTED_RISK_FRAC) -> tuple[float, str]:
    """The risk fraction to WRITE on a row: the allocator's own heat for it, clamped by `cap`.

    THE CLAMP IS ONE-SIDED ON PURPOSE. The allocator may want more than the old constant, and on
    the money path it gets it -- `gateway` sizes a funded sleeve from the book directly
    (`from_book`), not from this field. What this field does is bound what the promoter writes for
    the case where the book cannot be read, and raising THAT by fiat is exactly what the rules
    forbid. So the number moves down freely with the evidence and never up past what stood.
    """
    h = None
    if isinstance(row, dict):
        try:
            h = float(row.get("heat_earned"))
        except (TypeError, ValueError):
            h = None
    if h is None or not (h > 0.0):
        return 0.0, ("the allocator's solve gives this sleeve no heat; the row carries zero and "
                     "the sleeve holds no capital until a solve wants it")
    frac = min(h, float(cap))
    return round(frac, 6), (
        f"the allocator's current solve gives this sleeve {h:.2%} heat"
        + (f", written at the {cap:.0%} promoter ceiling" if h > cap else ""))


def capital_verdict(view: dict, name: str, *, symbol: str = "", family: str = "",
                    selector: str = "", streak: int = 0,
                    first_promotion: bool = True) -> dict:
    """May this sleeve hold capital right now, and why. The single door both lanes use.

    Returns `{status, risk_frac, why, delta_elogw_per_day, heat_earned, streak, joined}` with
    `status` in {LIVE, STANDBY, UNMEASURED}. Never returns RETIRED: retirement is a different,
    one-way decision with its own thresholds, and conflating "the book does not want you today"
    with "you are finished" is precisely the conflation the principal's demotion rule removes.

    UNMEASURED IS NOT STANDBY, and the difference decides what may act on it. STANDBY is a
    REFUSAL -- the allocator looked and said no -- and a demotion may act on it. UNMEASURED means
    nobody looked: the sleeve is not in the priced universe, the artifact is stale, or the scan's
    budget ran out. A row that has never held capital gets none either way (capital requires a
    measured marginal); a row that HOLDS capital keeps it, because removing risk on a compute
    limit is not a risk decision, it is an outage wearing one.
    """
    out: dict = {"status": "UNMEASURED", "risk_frac": 0.0, "streak": int(streak),
                 "delta_elogw_per_day": None, "heat_earned": None, "joined": ""}
    if not view.get("fresh"):
        out["why"] = (f"no fresh dE[log W] measurement: {view.get('why', 'unavailable')}. "
                      f"Nothing is added and nothing is removed -- the row and its clock stand "
                      f"and the next allocator pass decides.")
        return out
    row, joined = admission_of(view, name, symbol, family, selector)
    out["joined"] = joined
    if row is None:
        out["why"] = (f"{joined}. Capital requires a measured marginal, and an unmeasured one is "
                      f"not a positive one -- but it is not a refusal either, so risk already "
                      f"held is not removed on it.")
        return out
    out["delta_elogw_per_day"] = row.get("delta_elogw_per_day")
    out["heat_earned"] = row.get("heat_earned")
    if not row.get("admit"):
        out["status"] = "STANDBY"
        out["streak"] = 0
        out["why"] = f"standby on the current reading -- {row.get('why', 'not admitted')}"
        return out
    # CAPPED, because the number's only job is to answer "has it been positive often enough".
    # An uncapped counter on a long-lived LIVE row grows into the hundreds and then reads, after
    # a demotion, as if the sleeve had already earned its way back.
    out["streak"] = min(int(streak) + 1, PROMOTE_ADMIT_STREAK)
    if not first_promotion and out["streak"] < PROMOTE_ADMIT_STREAK:
        out["status"] = "STANDBY"
        out["why"] = (f"admitted on this reading ({out['streak']}/{PROMOTE_ADMIT_STREAK} "
                      f"consecutive) -- risk was removed from this sleeve once, and restoring it "
                      f"takes consecutive readings where removing it took one. "
                      f"{row.get('why', '')}")
        return out
    frac, why_frac = promoted_risk_frac(row)
    if not (frac > 0.0):
        out["status"] = "STANDBY"
        out["why"] = f"admitted but sized at zero: {why_frac}"
        return out
    out.update({"status": "LIVE", "risk_frac": frac,
                # BOTH NUMBERS, because they can legitimately differ: the gateway sizes a funded
                # sleeve straight from the book (`from_book`), and this field is only what the
                # promoter is permitted to WRITE. A row showing 3% beside an allocator that solved
                # 7.4% would otherwise read as the constant coming back.
                "allocator_heat": out["heat_earned"],
                "written_at_promoter_ceiling": bool(
                    isinstance(out["heat_earned"], (int, float))
                    and float(out["heat_earned"]) > PROMOTED_RISK_FRAC),
                "why": f"{row.get('why', 'admitted')}; {why_frac} ({joined})"})
    return out


def _door_status(cap: dict) -> str:
    """What a NEWLY promoted row's status is: LIVE only on a measured admission, else STANDBY.

    UNMEASURED and STANDBY differ for a row that already HOLDS capital -- one may remove it, the
    other may not. For a row being written for the first time there is nothing to preserve, so
    both mean the same thing: it joins the roster and holds no capital until a solve wants it.
    """
    return "LIVE" if str(cap.get("status") or "") == "LIVE" else "STANDBY"


def load_qquant_shadow() -> dict:
    """The qquant (hunt-certified) forward clock, kept in its own state file."""
    p = SHADOW_DIR / "qquant_shadow_state.json"
    try:
        v = json.loads(p.read_text(encoding="utf-8"))
        return v if isinstance(v, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def load_scalp_shadow() -> dict:
    """The scalp lane's forward clock (research/scalp_shadow.py), rows under `sleeves`."""
    p = SHADOW_DIR / "scalp_shadow_state.json"
    try:
        v = json.loads(p.read_text(encoding="utf-8"))
        return v if isinstance(v, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def promote_scalp(sleeves: list[dict], sshadow: dict, existing: set,
                  gate_authority: set | None = None, view: dict | None = None) -> bool:
    """The scalp lane's automatic door (principal 2026-09-04).

    A scalp sleeve promotes when its own Fusion-native forward clock says PROMOTION_CANDIDATE
    (the canon 50-trade / day-14-with-20 schedule, positive expectancy and the drawdown bound,
    judged after the frozen pre-registration boundary in scalp_shadow.py). THE FORWARD CLOCK IS
    THIS LANE'S CERTIFICATE: the ten-gate gauntlet has no path that certifies an M5/M15 scalp
    spec, so demanding one here made the lane a dead end -- a matured candidate nothing could
    ever promote. The bar itself is the main lane's own forward bar, not a weaker one. A clock
    fed by a proxy (non-Fusion) source carries no capital authority and is skipped with the
    reason logged, exactly as the lane itself states.

    The row carries the lane's EXACT recipe from its own state (timeframe, family, session,
    stop/target ATR multiples, max hold) so the gateway executes what was replayed and nothing
    else. No champion comparison: a scalp is an additive mechanism, not a challenger to a gold
    window, and capital is the allocator's decision.
    """
    changed = False
    rows = sshadow.get("sleeves") if isinstance(sshadow.get("sleeves"), dict) else {}
    for name, row in rows.items():
        if not isinstance(row, dict) or row.get("status") != "PROMOTION_CANDIDATE":
            continue
        if name in existing:
            continue
        if not row.get("promotion_authority"):
            plog(f"{name}: scalp PROMOTION_CANDIDATE on a proxy feed; no capital authority")
            continue
        if not row.get("matured", True):
            plog(f"{name}: scalp status says candidate but the clock is not matured; refused")
            continue
        choice = row.get("choice") if isinstance(row.get("choice"), dict) else {}
        tf = str(row.get("timeframe") or "")
        try:
            recipe = {"timeframe": tf, "family": str(choice["family"]),
                      "session": str(choice.get("session") or "all"),
                      "stop_atr": float(choice["stop_atr"]),
                      "target_atr": float(choice["target_atr"]),
                      "max_hold": int(choice["max_hold"])}
        except (KeyError, TypeError, ValueError) as exc:
            plog(f"{name}: scalp candidate refused -- exact recipe missing from its clock "
                 f"({type(exc).__name__}: {exc})")
            continue
        if not tf:
            plog(f"{name}: scalp candidate refused -- no timeframe on its clock")
            continue
        # The ten-gate certificate, when scripts/scalp_gauntlet.py has minted one for this
        # exact cell, is NAMED on the row; it changes nothing about the door (the forward clock
        # promotes either way), it tells the reader which kind of evidence stands behind it.
        spec = ("XAUUSD", str(name), None, "gold_scalp", False)
        cert = (f"ten_gate:scalp.{name}" if spec in (gate_authority or set())
                else "forward_clock")
        # THE CAPITAL DOOR IS dE[log W] (principal 2026-09-05). The clock decides that the sleeve
        # is real; the allocator decides whether adding it to the book the desk holds raises
        # robust growth. A refusal writes STANDBY, not a rejection: the row and its clock stand.
        cap = capital_verdict(view or {}, name, symbol="XAUUSD",
                              family=str(recipe.get("family") or "gold_scalp"),
                              selector=str(name))
        sleeves.append({"name": name, "symbol": "XAUUSD", **recipe,
                        "exec": "scalp_market", "lot": "auto_ramp",
                        "risk_frac": cap["risk_frac"], "status": _door_status(cap),
                        "risk_frac_source": "allocator_marginal" if cap["risk_frac"] else "none",
                        "admission": cap,
                        "certificate": cert,
                        "forward_verdict": row.get("forward_verdict"),
                        "promoted_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                        "shadow_exp": row.get("expectancy_r", 0.0),
                        "shadow_n": row.get("n", 0), "shadow_days": row.get("days", 0)})
        plog(f"PROMOTED (scalp) {name} -> {_door_status(cap)} at {cap['risk_frac']:.2%} risk "
             f"(exec=scalp_market {tf} {recipe['family']}/{recipe['session']}; shadow "
             f"exp={float(row.get('expectancy_r') or 0.0):.3f}R n={row.get('n', 0)}) -- "
             f"{cap['why']}")
        changed = True
    return changed


def clock_identities() -> dict[str, dict]:
    """clock key -> {symbol, selector, family, params, side} for every certificate the forward
    engine enrols, keyed exactly as the engine keys its rows.

    UNIVERSAL PROMOTION (principal 2026-09-05: "nothing should ever be blocked"). The main lane
    used to parse a clock key as `SYM.window[.STATE]`, assume the session-range-breakout family,
    and skip every other key with a bare `continue` -- so 65 of the 66 certificates in canon
    (orthogonal families on exotic crosses) could mature a forward clock and never be looked at.
    The identity now comes from the same enrolment the engine used, so a matured clock of ANY
    family has a symbol, selector, family, params and side the promoter can write to a sleeve row.
    """
    try:
        import shadow_forward as sf
        out: dict[str, dict] = {}
        for row in sf.certified_sleeves():
            r = list(row) + ["LONG"]
            sym, win, params, fam, side = r[0], r[1], r[2], r[3], r[4]
            key = sf.sleeve_key(sym, win, params, fam, side)
            out[key] = {"symbol": str(sym), "selector": str(win), "family": str(fam),
                        "params": dict(params or {}), "side": str(side).upper()}
        return out
    except Exception as exc:
        plog(f"clock identities unavailable ({type(exc).__name__}: {exc}); keys parsed by shape")
        return {}


def regrade_failures(now: datetime | None = None) -> dict[str, dict]:
    """certificate -> audit row for every certificate the latest recertification re-judged as
    COST_REGRADE_FAIL, when that audit is fresh enough to act on.

    WHY THIS GATES PROMOTION. A ten-gate pass is a claim about net-of-cost economics. The
    gauntlet's cost model was corrected three times in the survivor-manufacturing direction
    (gold per-ounce spread in a per-lot field, no account-currency conversion on commission, a
    contractual fee scaled by stress), and every certificate graded before a correction was
    tested against costs that flattered it. `recertify_canon` re-judges each one at today's
    costs and writes this audit; canon itself never shrinks from a script, so the promoter is
    where the corrected measurement has to bind -- a matured forward clock on a certificate
    that fails its own gates at real costs is evidence for a strategy whose economics were
    mis-stated, not a sleeve to fund. Stricter, never looser: thresholds are untouched.
    """
    try:
        doc = json.loads(RECERT_AUDIT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    stamp = str(doc.get("audited_at") or "")
    try:
        age_h = ((now or datetime.now(tz=UTC)) - datetime.fromisoformat(stamp)
                 ).total_seconds() / 3600.0
    except ValueError:
        age_h = float("inf")
    if age_h > RECERT_FRESH_H:
        plog(f"recertification audit is {age_h:.0f}h old (> {RECERT_FRESH_H:.0f}h) -- reported, "
             f"not binding; the daily recertify step refreshes it")
        return {}
    return {str(r.get("certificate")): r for r in (doc.get("rows") or [])
            if isinstance(r, dict) and r.get("status") == "COST_REGRADE_FAIL"}


def regrade_block(name: str, fails: dict[str, dict]) -> dict | None:
    """The failing audit row for `name`, matched exactly or across the canon's prefixing
    convention (`external.<cell>`, `<hunt>.<cell>` on one side, the bare cell on the other)."""
    if name in fails:
        return fails[name]
    for cert, row in fails.items():
        if cert.endswith("." + name) or name.endswith("." + cert):
            return row
    return None


def _after(a: str, b: str) -> bool:
    """Is timestamp `a` strictly later than `b`? False whenever either cannot be parsed.

    COMPARED AS INSTANTS, NOT AS STRINGS. The two sides are written by different writers at
    different precisions ("...:00+00:00" against "...:00.123456+00:00"), and lexicographic order
    on those disagrees with time order -- which would silently invert the "do not judge a sleeve
    on a measurement that predates it" guard.
    """
    try:
        return datetime.fromisoformat(a) > datetime.fromisoformat(b)
    except (TypeError, ValueError):
        return False


def reconcile_capital(sleeves: list[dict], view: dict, *, now: datetime | None = None,
                      only: set[str] | None = None) -> bool:
    """Move every standing row toward what the CURRENT solve says, in both directions.

    THE ASYMMETRY, EXPLICIT AND IN ONE PLACE (principal, 2026-09-05: "promotion slow / demotion
    immediate"):

        LIVE -> STANDBY needs ONE reading. The latest solve gives this sleeve no heat, so it
        holds none. No trade count, no drawdown bar, no waiting. `demoted_at` and `demote_reason`
        say why. It is NOT retired: the row stands, the shadow clock is untouched, `retired_at`
        is not set, and the sleeve is judged again on the next pass.

        STANDBY -> LIVE needs PROMOTE_ADMIT_STREAK consecutive positive readings, counted on the
        row itself. A sleeve whose marginal sits on zero would otherwise be admitted and demoted
        alternately forever, and every one of those flips is turnover the desk pays for.

        RETIRED never moves. Retirement is the one-way door with its own thresholds; standby is
        the reversible one. Conflating them is what this function exists to stop.

    A sleeve promoted since the allocation was taken is left alone: the solve has not had a
    chance to see it, and demoting on a measurement that predates the sleeve would be reading
    absence as evidence. `only`, when given, limits this to rows that already existed before this
    pass's promotion doors ran -- a row written moments ago has just been judged by
    `capital_verdict` and re-judging it here would demote it on its own promotion.

    Returns True when any row changed. Pure over `sleeves` (mutated in place) and `view`.
    """
    if not view.get("fresh"):
        plog(f"capital reconciliation SKIPPED: {view.get('why', 'no fresh allocation')}. "
             f"Rows stand as they are -- an unmeasured reading removes nothing and adds nothing.")
        return False
    changed = False
    at = str(view.get("at") or "")
    stamp = (now or datetime.now(tz=UTC)).isoformat(timespec="seconds")
    for s in sleeves:
        status = str(s.get("status") or "").upper()
        if status not in ("LIVE", "STANDBY"):
            continue                                    # RETIRED is a one-way door
        if only is not None and str(s.get("name") or "") not in only:
            continue
        # EVERY READING IS RECORDED, not only the ones that move a row. The streak that governs
        # restoration lives ON the row, so a pass whose verdict changed nothing but whose count
        # advanced still has to be written -- otherwise "two consecutive readings" silently
        # becomes "two readings in the same second".
        before = json.dumps(s, sort_keys=True, default=str)
        promoted_at = str(s.get("promoted_at") or "")
        if status == "LIVE" and _after(promoted_at, at):
            s.setdefault("admission", {})["why"] = (
                f"promoted {promoted_at}, after the {at} allocation: not judged on a measurement "
                f"that predates the sleeve")
            changed = changed or json.dumps(s, sort_keys=True, default=str) != before
            continue
        cap = capital_verdict(view, str(s.get("name") or ""),
                              symbol=str(s.get("symbol") or ""),
                              family=str(s.get("family") or ""),
                              selector=str(s.get("selector") or s.get("window") or ""),
                              streak=int(s.get("admit_streak") or 0),
                              # A LIVE row is not ADDING risk, it is keeping what it holds, so the
                              # streak does not apply to it -- only to a STANDBY row taking
                              # capital, which is the direction the principal ordered made slow.
                              first_promotion=(status == "LIVE"))
        s["admission"] = cap
        s["admit_streak"] = cap["streak"]
        if cap["status"] == "UNMEASURED":
            # NOBODY LOOKED. Not in the priced universe, or the scan's budget ran out. Removing
            # risk on that is removing it on a compute limit, which is an outage wearing a risk
            # decision; adding it would be adding on nothing at all. The row stands, and the
            # reason stands on it so the gap is visible rather than silent.
            changed = changed or json.dumps(s, sort_keys=True, default=str) != before
            continue
        if cap["status"] == "LIVE" and status == "STANDBY":
            s.update({"status": "LIVE", "risk_frac": cap["risk_frac"],
                      "risk_frac_source": "allocator_marginal",
                      "restored_at": stamp, "restore_reason": cap["why"]})
            s.pop("demoted_at", None)
            s.pop("demote_reason", None)
            plog(f"RESTORED {s['name']} -> LIVE at {cap['risk_frac']:.2%} risk after "
                 f"{cap['streak']} consecutive positive reading(s) -- {cap['why']}")
            changed = True
        elif cap["status"] == "STANDBY" and status == "LIVE":
            s.update({"status": "STANDBY", "risk_frac": 0.0, "risk_frac_source": "none",
                      "demoted_at": stamp, "demote_reason": cap["why"]})
            plog(f"DEMOTED {s['name']} -> STANDBY (0% risk, NOT retired) on the current "
                 f"reading -- {cap['why']}")
            changed = True
        elif status == "LIVE" and abs(float(s.get("risk_frac") or 0.0) - cap["risk_frac"]) > 1e-9:
            # SIZE IS AN OUTPUT OF THE CURRENT SOLVE, not a constant carried from promotion day.
            old = float(s.get("risk_frac") or 0.0)
            s.update({"risk_frac": cap["risk_frac"], "risk_frac_source": "allocator_marginal"})
            plog(f"RESIZED {s['name']}: {old:.2%} -> {cap['risk_frac']:.2%} -- {cap['why']}")
        changed = changed or json.dumps(s, sort_keys=True, default=str) != before
    return changed


def load_cert_specs() -> dict[str, dict]:
    """Certificate key -> published shadow_spec, exact policy only (fail closed)."""
    from gate_policy import all_ten_pass, is_exact_policy
    p = BASE / "reports" / "UNIVERSAL_SURVIVORS.json"
    try:
        certs = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not is_exact_policy(certs.get("gate_policy")):
        return {}
    out = {}
    for key, cert in (certs.get("survivors") or {}).items():
        if isinstance(cert, dict) and all_ten_pass(cert.get("gates")) \
                and isinstance(cert.get("shadow_spec"), dict):
            out[key] = cert["shadow_spec"]
    return out


def promote_generic(sleeves: list[dict], qshadow: dict, existing: set,
                    gate_authority: set, regrade: dict[str, dict] | None = None,
                    view: dict | None = None) -> bool:
    """GAP 124: hunt-certified (qquant) candidates gain the same automatic door.

    A qquant sleeve promotes when its OWN Fusion-native forward clock says
    PROMOTION_CANDIDATE (the canon 50-trade / day-14-with-20 schedule lives in
    qquant_shadow.py, not re-derived here) AND its certificate's published
    shadow_spec is in the exact-policy authority set. The sleeve row carries
    exec="family_market": the gateway executes it through the family-executor
    path, which stays LOG-ONLY until data/GENERIC_EXEC_ENABLED exists -- wired
    end to end, armed by one explicit human act (LAWS §4).
    """
    changed = False
    cert_specs = load_cert_specs()
    fails = regrade_failures() if regrade is None else regrade
    for key, row in qshadow.items():
        if not isinstance(row, dict) or row.get("status") != "PROMOTION_CANDIDATE":
            continue
        if key in existing:
            continue
        spec = cert_specs.get(key)
        if not spec:
            plog(f"{key}: qquant PROMOTION_CANDIDATE but no exact-policy shadow_spec; refused")
            continue
        bad = regrade_block(key, fails)
        if bad:
            row["status"] = "BLOCKED_COST_REGRADE"
            row["gate_reason"] = ("fails its own ten gates at the current cost model: "
                                  + ", ".join(bad.get("gates_failing_now") or ["unspecified"]))
            plog(f"{key}: candidate refused -- {row['gate_reason']} "
                 f"(cost/lot now {bad.get('cost_per_lot_now')})")
            changed = True
            continue
        tup = (str(spec["symbol"]), str(spec["selector"]), spec.get("condition") or None,
               str(spec["family"]), spec.get("is_universe") is True)
        row["certificate_drift"] = bool(gate_authority) and tup not in gate_authority
        if row["certificate_drift"]:
            # The ten gates gated this clock's enrolment; a spec missing from TODAY's authority
            # set is registry drift, recorded here and blocking nothing (principal 2026-09-05).
            plog(f"{key}: spec not in the current authority set -- recorded as drift, "
                 f"promotion proceeds on the clock's own certificate")
        cap = capital_verdict(view or {}, key, symbol=tup[0], family=tup[3], selector=tup[1])
        sleeves.append({"name": key, "symbol": tup[0], "selector": tup[1],
                        "state": tup[2], "family": tup[3],
                        "side": str(spec.get("side", "LONG")).upper(),
                        "exec": "family_market",
                        "lot": "auto_ramp", "risk_frac": cap["risk_frac"],
                        "risk_frac_source": "allocator_marginal" if cap["risk_frac"] else "none",
                        "admission": cap,
                        "status": _door_status(cap),
                        "promoted_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                        "shadow_exp": row.get("exp_r", 0.0)})
        plog(f"PROMOTED (generic) {key} -> {_door_status(cap)} at {cap['risk_frac']:.2%} risk, "
             f"exec=family_market (shadow exp={row.get('exp_r', 0.0):.3f}R "
             f"n={row.get('n', 0)}) -- {cap['why']}"
             + ("; orders LOG-ONLY until data/GENERIC_EXEC_ENABLED"
                if _door_status(cap) == "LIVE" else ""))
        changed = True
    return changed


def main() -> None:
    shadow = load_shadow()
    sleeves = load_sleeves()
    ledger = load_ledger()
    existing = {s["name"] for s in sleeves}
    gate_authority = authorized_specs(BASE)
    regrade_fails = regrade_failures()
    identities = clock_identities()
    changed = False

    # WHAT THE ALLOCATOR CURRENTLY SAYS. Read ONCE per pass: the three promotion doors and the
    # reconciliation below must all decide from the same solve, or two rows written in the same
    # run could carry two different answers to "what does the book want".
    view = allocation_view()
    plog(f"allocation view: {'FRESH' if view.get('fresh') else 'NOT USABLE'} -- "
         f"{view.get('why', '')}")

    qshadow = load_qquant_shadow()
    qchanged = promote_generic(sleeves, qshadow, existing, gate_authority,
                               regrade=regrade_fails, view=view)
    sshadow = load_scalp_shadow()
    schanged = promote_scalp(sleeves, sshadow, existing, gate_authority, view=view)
    changed = changed or qchanged or schanged

    for key, st in shadow.items():
        if not isinstance(st, dict):
            continue
        if st.get("status") != "PROMOTION CANDIDATE":
            continue
        if key in existing:
            continue
        # THE CLOCK'S IDENTITY, from the enrolment that started it. Keys carry an optional
        # third field ("SYM.window" or "SYM.window.STATE") for breakouts and the family name for
        # everything else; the identity map resolves both, and the parse below is only the
        # fallback for a key the enrolment no longer lists.
        ident = identities.get(key)
        parts = key.split(".")
        if ident:
            sym, win, family = ident["symbol"], ident["selector"], ident["family"]
            side_txt = ident.get("side", "LONG")
            params = ident.get("params") or {}
            cond = parts[2] if (family == "session_range_breakout" and len(parts) > 2) else None
        else:
            sym, win = parts[0], parts[1]
            family, side_txt, params = "session_range_breakout", "LONG", {}
            cond = parts[2] if len(parts) > 2 else None
        gate_spec = (sym, win, cond, family, False)
        # THE TEN GATES GATE ENROLMENT, NOT PROMOTION. A clock exists only because a certificate
        # enrolled it (grandfathering ended 2026-08-26), so re-checking the authority set here
        # could only refuse on registry DRIFT -- a renamed or re-keyed certificate -- and that is
        # how matured clocks were held out of the book. Drift is recorded on the row; it blocks
        # nothing. The one measured refusal is a fresh cost re-grade failure (rule 1: stricter).
        st["certificate_drift"] = gate_spec not in gate_authority if gate_authority else False
        if st["certificate_drift"]:
            plog(f"{key}: certificate not in the current authority set -- recorded as drift, "
                 f"promotion proceeds on the clock's own enrolment")
        bad = regrade_block(key, regrade_fails)
        if bad:
            st["status"] = "BLOCKED_COST_REGRADE"
            st["promotion_authority"] = False
            st["gate_reason"] = ("fails its own ten gates at the current cost model: "
                                 + ", ".join(bad.get("gates_failing_now") or ["unspecified"]))
            plog(f"{key}: live promotion refused -- {st['gate_reason']}")
            changed = True
            continue
        cap = capital_verdict(view, key, symbol=sym, family=family, selector=win)
        row = {"name": key, "symbol": sym, "lot": PROMOTED_LOT, "risk_frac": cap["risk_frac"],
               "risk_frac_source": "allocator_marginal" if cap["risk_frac"] else "none",
               "admission": cap,
               "status": _door_status(cap),
               "promoted_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
               "shadow_exp": st.get("exp_r", 0.0), "family": family,
               "side": side_txt, "certificate_drift": st["certificate_drift"]}
        if family == "session_range_breakout":
            if win not in GOLD_WINDOWS:
                st["executor_gap"] = f"bracket window {win!r} is not one the gateway runs"
                plog(f"{key}: PROMOTION CANDIDATE with no executor -- {st['executor_gap']}")
                continue
            # THE ARMED-BOOK COMPARISON IS MEASURED, NOT A GATE (principal 2026-09-04). Until
            # then a gold challenger WAITED while the armed window had no forward rows and was
            # KILLED when its expectancy trailed the window's by CHAMPION_MARGIN. Neither had
            # proved it raised E[log W]; both held a certified, matured sleeve out of the book.
            # The number is kept on the row so the allocator's dElogW and attribution read it.
            vs_armed = None
            if sym == "XAUUSD":
                armed_exp = armed_forward_exp(ledger, win)
                if armed_exp is not None:
                    vs_armed = {"armed_exp_r": round(float(armed_exp), 4),
                                "margin_r": round(float(st.get("exp_r", 0.0))
                                                  - float(armed_exp), 4),
                                "trails_by_more_than": bool(
                                    float(st.get("exp_r", 0.0)) < armed_exp - CHAMPION_MARGIN)}
                    plog(f"{key}: challenger vs armed {win}: {float(st.get('exp_r', 0.0)):.3f}R "
                         f"vs {armed_exp:.3f}R -- recorded, promotion proceeds")
            # Carried through to the gateway, which refuses to trade a conditioned sleeve whose
            # state it cannot confirm; without it the gateway would trade the UNCONDITIONED
            # strategy under this sleeve's name.
            row.update({"window": win, "vs_armed": vs_armed, "state": cond})
        else:
            # A MISSING MODULE MUST NOT KILL THE PROMOTION PASS. This import is the one thing
            # standing between a matured candidate and capital, and on 2026-09-05 the healer
            # shipped this file's caller to the box a minute before the callee was on its list.
            # An ImportError here would have taken every non-gold promotion with it, silently,
            # for as long as the two files disagreed. Absent module -> the gap is UNKNOWN and
            # named on the row, which refuses the row rather than the pass.
            try:
                from mt5desk import executables
                # THE CHART IS PART OF THE QUESTION (2026-09-05). `gateway.run_family_sleeves`
                # reads TIMEFRAME_H1 unconditionally, so promoting a certificate hunted on
                # another chart would put real capital into signals computed from bars it was
                # never certified on. Asked ONLY when the chart is not H1, so an hourly row makes
                # byte-identical the call it has always made -- including against a box whose
                # `executables` predates the argument, where a non-H1 row instead raises here and
                # is refused by the handler below. Fail-closed on the one path that spends money.
                gap = (executables.executor_gap(family) if _sleeve_timeframe(params) == "H1"
                       else executables.executor_gap(family, _sleeve_timeframe(params)))
            except Exception as exc:                                    # noqa: BLE001
                gap = (f"executor registry unavailable on this box "
                       f"({type(exc).__name__}: {exc}) -- refusing the row, not the pass")
            if gap:
                # NAMED, NEVER SILENT, NEVER A ROW THE BOOK CANNOT TRADE. A LIVE row for a family
                # the gateway cannot execute would be funded by the allocator and held as air.
                st["executor_gap"] = gap
                plog(f"{key}: PROMOTION CANDIDATE with no executor -- {gap}")
                changed = True
                continue
            st.pop("executor_gap", None)
            row.update({"selector": win, "state": cond, "params": params,
                        "exec": "family_market", "lot": "auto_ramp"})
        sleeves.append(row)
        plog(f"PROMOTED {key} -> {_door_status(cap)} at {cap['risk_frac']:.2%} risk "
             f"({family} {side_txt}, exec={row.get('exec', 'bracket')}; shadow "
             f"exp={st.get('exp_r', 0.0):.3f}R n={st.get('n', 0)}) -- {cap['why']}")
        changed = True

    # ---------------------------------------------------- CAPITAL, ON THE CURRENT READING
    # Demotion needs one reading and restoration needs several: `reconcile_capital` is where that
    # asymmetry lives. It runs BEFORE retirement so a sleeve the solve no longer wants is at 0%
    # risk on this pass whatever the retirement thresholds later decide, and it never retires
    # anything itself.
    if reconcile_capital(sleeves, view, only=existing):
        changed = True

    for s in sleeves:
        # RETIREMENT JUDGES STANDBY ROWS TOO. A sleeve demoted to 0% keeps its live record, and a
        # record that trips the retirement bar must still retire it -- otherwise a demotion would
        # be a way to escape the one-way door and be restored months later on a stale certificate.
        if str(s.get("status") or "").upper() not in ("LIVE", "STANDBY"):
            continue
        why_not = degenerate_evidence(ledger, s["name"])
        if why_not:
            plog(f"RETIRE-REFUSED {s['name']}: {why_not}")
            continue
        fs = sleeve_forward_stats(ledger, s["name"])
        retire = False
        reason = ""
        if fs["n"] >= RETIRE_MIN_N and fs["roll20_exp"] <= 0.0:
            retire, reason = True, f"roll20 exp {fs['roll20_exp']:.3f}R <= 0"
        elif fs["max_dd"] < RETIRE_MAX_DD:
            retire, reason = True, f"forward maxDD {fs['max_dd']:.1f}R < {RETIRE_MAX_DD}R"
        elif fs["n"] >= 50 and fs["exp"] < RETIRE_MIN_EXP:
            retire, reason = True, f"n={fs['n']} exp {fs['exp']:.3f}R < {RETIRE_MIN_EXP}R"
        if retire:
            s["status"] = "RETIRED"
            s["retired_at"] = datetime.now(tz=UTC).isoformat(timespec="seconds")
            s["retire_reason"] = reason
            # THE SLEEVE'S NAME *IS* ITS SHADOW KEY -- it was written from `key` at promotion.
            # Rebuilding it from symbol+window silently dropped the state, so retiring
            # "CADJPY.asia.FAILED_BREAK" wrote KILL onto "CADJPY.asia": a different sleeve, also
            # in the shadow set, which had done nothing wrong. Meanwhile the conditioned sleeve
            # kept PROMOTION CANDIDATE, so the next run promoted it again -- the desk oscillating
            # promote/retire forever, against this module's own "never re-promoted" guarantee.
            skey = s["name"]
            if skey in shadow:
                shadow[skey]["status"] = "KILL"
            if isinstance(qshadow.get(skey), dict):
                qshadow[skey]["status"] = "KILL"
                qchanged = True
            srows = sshadow.get("sleeves") if isinstance(sshadow.get("sleeves"), dict) else {}
            if isinstance(srows.get(skey), dict):
                srows[skey]["status"] = "KILL"
                schanged = True
            plog(f"AUTO-RETIRED {s['name']} ({reason})")
            changed = True

    # ---------------------------------------------------------------- the gold book
    # THE ARMED GOLD BOOK NOW DECAYS LIKE EVERYTHING ELSE (principal, 2026-09-01). It used to be
    # exempt -- "The armed gold book is NOT managed here" -- because it predates the gauntlet and
    # is armed by a person. The consequence was that the desk's ONLY live sleeves were the only
    # ones with no automatic decay protection: the three retire rules below walked sleeves.json,
    # which is empty, so they applied to nothing that could actually lose money. A gold book whose
    # edge died would have degraded indefinitely with no organ able to notice.
    #
    # RETIREMENT HERE DOES NOT DELETE ANYTHING. It writes the window into data/GOLD_RETIRED.json
    # with its reason; gateway.sleeve_set() reads that file and stops emitting the window. Undo is
    # deleting the entry, which keeps re-arming a person's act exactly as it is today.
    #
    # SAFE BEFORE THE LEDGER FILLS: sleeve_forward_stats returns n=0/max_dd=0.0 for a sleeve with
    # no rows, and every rule below requires either n >= 10 or a drawdown worse than -25R, so an
    # empty or missing ledger retires nothing. It arms itself only once real fills are recorded.
    gold_retired = _load_gold_retired()
    for gname in GOLD_SLEEVE_NAMES:
        if gname in gold_retired:
            continue
        why_not = degenerate_evidence(ledger, gname)
        if why_not:
            plog(f"RETIRE-REFUSED {gname}: {why_not}")
            continue
        fs = sleeve_forward_stats(ledger, gname)
        retire = False
        reason = ""
        if fs["n"] >= RETIRE_MIN_N and fs["roll20_exp"] <= 0.0:
            retire, reason = True, f"roll20 exp {fs['roll20_exp']:.3f}R <= 0"
        elif fs["max_dd"] < RETIRE_MAX_DD:
            retire, reason = True, f"forward maxDD {fs['max_dd']:.1f}R < {RETIRE_MAX_DD}R"
        elif fs["n"] >= 50 and fs["exp"] < RETIRE_MIN_EXP:
            retire, reason = True, f"n={fs['n']} exp {fs['exp']:.3f}R < {RETIRE_MIN_EXP}R"
        if retire:
            gold_retired[gname] = {
                "retired_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                "reason": reason, "n": fs["n"], "exp": fs["exp"],
                "roll20_exp": fs["roll20_exp"], "max_dd": fs["max_dd"]}
            _save_gold_retired(gold_retired)
            plog(f"AUTO-RETIRED {gname} ({reason}) -- gateway stops emitting this window")
            changed = True

    if qchanged:
        (SHADOW_DIR / "qquant_shadow_state.json").write_text(
            json.dumps(qshadow, indent=2), encoding="utf-8")
    if schanged:
        (SHADOW_DIR / "scalp_shadow_state.json").write_text(
            json.dumps(sshadow, indent=2), encoding="utf-8")
    if changed:
        save_sleeves(sleeves)
        (SHADOW_DIR / "shadow_state.json").write_text(
            json.dumps(shadow, indent=2), encoding="utf-8")
        plog(f"sleeves.json updated: {[s['name'] for s in sleeves if s['status']=='LIVE']}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        plog("promoter error: " + traceback.format_exc())
