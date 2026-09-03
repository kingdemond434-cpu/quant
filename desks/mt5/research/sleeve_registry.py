"""CANONICAL SLEEVE REGISTRY -- one exact identity, frozen at the clock, verified every cycle.

WHY ONE REGISTRY (principal 2026-08-26). The desk carried a sleeve's identity in five different
shapes at once: a display cell name in the certificate, a `(symbol, selector, condition, family,
is_universe)` tuple in admission, a `SYM.window` key in the forward state, a `sleeves.json` name
in the gateway, and a row label on the dashboard. Nothing forced them to agree, and they did not:
the dashboard reported 37 sleeves while the admission door authorised 6 and the reconciler found
26 of the 37 were stopped clocks. Worse, `shadow_spec` omitted the PARAMS, so five separately
gauntleted XAUUSD variants shared one identity and four were never forward-tested at all. When
identity is ambiguous, every count downstream is a different question answered with the same word.

WHAT AN IDENTITY IS HERE. Everything that, if changed, makes the forward evidence describe a
different strategy:

    family x instrument x direction x timeframe/session x regime/condition x params
          x code_hash (the signal function's own source)
          x cost_hash (spread/commission model actually applied)
          x data_identity (which venue's bars, on which clock)

`code_hash` and `cost_hash` are the two most people leave out and the two that fail silently. A
family function edited mid-window, or a cost model widened, changes what the sleeve DOES without
touching any name or parameter -- and the forward series then splices two different strategies
into one expectancy. That is not a smaller sample, it is a wrong one.

FREEZE, THEN VERIFY. `freeze()` records the identity when the clock starts. `verify()` recomputes
it every cycle and returns the fields that drifted. A drifted sleeve is NOT silently re-based and
NOT deleted: its clock is stopped (`IDENTITY_BROKEN`) and its accrued evidence is preserved for
audit, because evidence collected under a different identity is real evidence about a different
thing. Restarting means a NEW frozen identity and a NEW window -- never inheriting the old clock.

The registry is the single source every consumer reads: shadow health, the reconciler, the
promoter, the dashboard and execution. Absence is never permission -- an unregistered sleeve has
no identity, and a sleeve with no identity cannot promote.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
REGISTRY = BASE / "data" / "sleeve_registry.json"

#: Fields whose drift invalidates a running clock. Order is fixed so the hash is stable.
IDENTITY_FIELDS = ("family", "symbol", "direction", "timeframe", "selector", "condition",
                   "params", "code_hash", "cost_hash", "data_venue")

#: WHAT THE FIELDS MEAN, versioned. A frozen row records the schema it was frozen under, because
#: a field can change MEANING without changing shape and that is invisible to every comparison
#: here. It happened: `data_venue` used to hold `Bars.source` -- the ROUTE the bars arrived by --
#: so a row frozen from a live terminal read "MT5:<server>" while the identical evidence replayed
#: from the parquet cache read "CACHE:<file>", and every clock broke terminally on every run the
#: Windows box was down. It now holds `Bars.evidence_venue`, WHOSE PRINTS the bars are. Rows
#: frozen under an older schema are not pre-registrations of the new quantity and must not be
#: silently re-blessed; `scripts/migrate_identity_venue.py` archives them and starts a NEW window.
IDENTITY_SCHEMA = "venue-2026-08-26"


class RegistryUnreadable(RuntimeError):
    """The registry file EXISTS but could not be read or parsed.

    This is NOT the same answer as "there is no registry yet", and conflating them is what
    re-based the desk's entire forward book (see `_read`).
    """


def _read(path: Path) -> dict:
    """ABSENCE AND UNREADABILITY ARE DIFFERENT ANSWERS, and only one of them is safe.

    This returned `{}` for both, and `freeze()` treats an empty registry as "no clock has ever
    been frozen" -- so a single failed read re-minted every row with `frozen_at = now` and
    silently re-based every forward clock to day zero. MEASURED 2026-08-27 on the committed
    history of `sleeve_registry.json`: 08-26 02:02 all 15 rows frozen 08-26T01:42; 08-27 02:10
    all 15 frozen 08-27T01:13; 08-27 09:25 all 17 frozen 08-27T03:31-03:34. Three complete
    re-bases in 32 hours, none of them archived anywhere -- against a promotion law that requires
    `days >= 14`. No clock had ever survived a day, so the desk was structurally incapable of
    promoting anything to live capital, and `live_readiness.json` reported the cause as "the
    market has not yet supplied the unseen observations" -- a desk defect attributed to the world.

    THE READ FAILS FOR ORDINARY REASONS. The authoritative copy lives on the Windows trading box
    and `ops/pull_desk_state.sh` scp's this exact path every ~2 minutes while `freeze()` writes
    it non-atomically; on Windows an open handle raises `PermissionError` (an OSError), which the
    old `except` swallowed into a clean empty verdict -- WS-005, the one direction nothing
    downstream catches.

    A missing file is still legitimately empty: that is a desk with no registry yet, and
    `freeze()` may create one. Anything else raises, and the writers below let it propagate:
    `shadow_forward` already wraps every registry call in `except Exception` and logs
    "registry unavailable", which skips the row and leaves the running clock untouched. Refusing
    to write is the only safe response to an unknown base -- writing on `{}` is what destroys it.
    """
    try:
        value = json.loads(path.read_text("utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        raise RegistryUnreadable(
            f"{path} exists but could not be read ({type(exc).__name__}: {exc}); refusing to "
            f"treat an unreadable registry as an empty one -- that re-bases every forward clock"
        ) from exc
    if not isinstance(value, dict):
        raise RegistryUnreadable(
            f"{path} parsed as {type(value).__name__}, not an object; refusing to treat a "
            f"malformed registry as an empty one -- that re-bases every forward clock")
    return value


def _write(reg: dict) -> None:
    """Atomic replace -- a half-written registry is exactly the input `_read` must never see.

    `write_text` truncates first, so every write opened a window in which a concurrent reader
    (the 2-minute artifact pull, the dashboard, the reconciler) observes a truncated file. That
    window is the generator of the `RegistryUnreadable` condition above; closing it removes the
    cause rather than only refusing to act on the symptom.
    """
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(REGISTRY.parent), prefix=".sleeve_registry.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(reg, fh, indent=1, default=str)
        os.replace(tmp, REGISTRY)
    finally:
        Path(tmp).unlink(missing_ok=True)


def behaviour_hash(fn: Any) -> str:
    """Hash of what the function DOES -- bytecode and constants -- not how its source reads.

    WHY THIS EXISTS. `code_hash` below hashes `inspect.getsource`, which includes the docstring
    and every comment. So editing a COMMENT breaks every live clock on that family, terminally,
    against a code state that then no longer exists anywhere and that `reconcile()` can never see
    come back. Measured 2026-09-03: 15 of 52 sleeves (29% of the forward book) sat
    IDENTITY_BROKEN on `code_hash changed after the clock froze`, frozen at 32b3bc38d228df35
    while both the VPS and the desk box agreed the current value is 38d9ca40fbd659c6 -- one
    stable answer on both machines, and no clock able to reach it. The same family's hash was
    implicated in the 2026-08-28 incident too, so this is a recurring class, not an incident.

    Bytecode is the right identity for a pre-registration: `co_code` and `co_consts` change when
    the LOGIC changes and do not change when the prose around it does. The docstring is dropped
    explicitly because it is `co_consts[0]` and would otherwise reintroduce exactly the
    sensitivity this removes.

    NOT A LOOSENING, AND IT IS ADDITIVE. This is recorded ALONGSIDE `code_hash`, never instead of
    it, and it is NOT in IDENTITY_FIELDS -- so `sleeve_id` is unchanged and no existing clock is
    re-blessed by its introduction. It is consulted only by `verify()`, and only to answer the
    narrow question "is a code_hash difference a real behaviour change?". A logic edit still
    breaks the clock, which is the property the two-stage law actually needs.
    """
    code = getattr(fn, "__code__", None)
    if code is None:
        return "nocode:" + getattr(fn, "__qualname__", str(fn))
    try:
        consts = tuple(repr(c) for c in (code.co_consts or ())[1:])   # [0] is the docstring
        blob = "|".join((
            code.co_code.hex(),
            ",".join(consts),
            ",".join(code.co_names or ()),
            ",".join(code.co_varnames or ()),
            str(code.co_argcount),
        ))
    except (AttributeError, TypeError):
        return "nocode:" + getattr(fn, "__qualname__", str(fn))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def code_hash(fn: Any) -> str:
    """Hash of the signal function's own source -- the thing a parameter name cannot capture.

    Falls back to the qualified name when source is unavailable (C extensions, exec'd code): a
    weaker identity is still an identity, and pretending we hashed source we could not read would
    be worse than recording that we could not.
    """
    try:
        src = inspect.getsource(fn)
    except (OSError, TypeError):
        return "nosrc:" + getattr(fn, "__qualname__", str(fn))
    # THE FUNCTION'S OWN SOURCE, NOT ITS REGISTRATION. inspect.getsource includes decorator
    # lines, so adding @register_family (search-grid metadata -- param grids, tags) to a family
    # would have broken every live clock on it (nearly happened 2026-08-27: the decorator landed
    # while 15 fresh windows were running). A decorator changes how the SEARCH enumerates the
    # family, never what the frozen sleeve executes; identity starts at the def line.
    lines = src.splitlines(keepends=True)
    for i, ln in enumerate(lines):
        if ln.lstrip().startswith(("def ", "async def ")):
            src = "".join(lines[i:])
            break
    return hashlib.sha256(src.encode("utf-8")).hexdigest()[:16]


def cost_hash(costs: Any) -> str:
    """Hash of the cost model actually applied. Widening costs mid-window changes the strategy."""
    try:
        fields = {k: round(float(v), 6) for k, v in vars(costs).items()
                  if isinstance(v, (int, float)) and not isinstance(v, bool)}
    except TypeError:
        return "nocost"
    return hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()[:16]


def identity(*, family: str, symbol: str, direction: str = "LONG", timeframe: str = "H1",
             selector: str = "", condition: str | None = None,
             params: dict | None = None, code: str = "", cost: str = "",
             data_venue: str = "", behaviour: str = "") -> dict:
    """Build the canonical identity dict plus its stable id.

    `behaviour` is the OPTIONAL bytecode hash from `behaviour_hash`. It is recorded on the row
    but is deliberately NOT in IDENTITY_FIELDS, so it never enters `sleeve_id` and its arrival
    re-blesses nothing. `verify()` consults it for one narrow question -- whether a `code_hash`
    difference is a real behaviour change or only edited prose -- which is what stopped 15 clocks
    dead on 2026-09-03 for a source-text edit that changed no logic.
    """
    ident = {
        "family": str(family), "symbol": str(symbol), "direction": str(direction).upper(),
        "timeframe": str(timeframe), "selector": str(selector),
        "condition": condition or None,
        "params": {k: params[k] for k in sorted(params or {})},
        "code_hash": code, "cost_hash": cost, "data_venue": data_venue,
    }
    if behaviour:
        ident["behaviour_hash"] = str(behaviour)
    else:
        # EVERY NEW CLOCK MUST CARRY ONE. A row frozen without a behaviour hash is one comment
        # edit away from going terminal for a change that altered no logic -- the exact defect
        # that stopped 15 of 52 clocks on 2026-09-03. Callers pass it (shadow_forward does); this
        # names the omission loudly rather than silently minting another fragile row, because a
        # missing hash is indistinguishable from a matching one at verify() time by design.
        ident["behaviour_hash_missing"] = True
    blob = json.dumps({k: ident[k] for k in IDENTITY_FIELDS}, sort_keys=True, default=str)
    ident["sleeve_id"] = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:20]
    return ident


def freeze(key: str, ident: dict, *, forward_start: str | None = None,
           cost_fields: dict | None = None) -> dict:
    """Record the identity for `key` if absent; return the FROZEN identity (never the new one).

    Idempotent by construction: a second freeze on a live key returns what was already frozen, so
    a caller cannot re-base a running clock by calling this again.

    `cost_fields` are the NUMERIC cost-model values the clock froze with, stored so the forward
    engine can keep RUNNING the window on that exact basis. Without them the engine rebuilt costs
    from live universe metadata every cycle, and the spread re-measure (~2x/day) changed
    cost_hash and terminally broke every clock mid-window -- identity churn, not identity
    protection. The doctrine stands: a certificate's cost basis IS part of the strategy, so the
    window runs on the frozen basis and a re-measured cost enters at the NEXT window as a new
    identity, never spliced into a running one. Real execution is judged by markouts regardless.
    """
    reg = _read(REGISTRY)
    rows = reg.setdefault("sleeves", {})
    if key in rows and rows[key].get("identity"):
        # BACKFILL THE CLOCK START, NEVER RE-BASE IT. Idempotence protects the IDENTITY; it must
        # not also freeze in a MISSING pre-registration boundary. `shadow_forward` froze the row
        # before it stamped `forward_start`, so every row was born `forward_start: null` and the
        # early return made the null permanent -- measured 2026-08-27, 17/17 registry rows null
        # while all 17 shadow rows carried a real stamp. The registry is the desk's only
        # freeze-then-verify record of the one field L1.58 promotion turns on (`days >= 14`), so a
        # null there leaves the boundary readable ONLY from the mutable state file the registry
        # exists to be independent of -- and both `forward_reconcile` and `migrate_identity_venue`
        # rewrite that file. A clock silently restarted at NOW would be indistinguishable from one
        # that has run thirteen days. Filling an ABSENT value is therefore the opposite of
        # re-basing: it can only move the boundary EARLIER or leave it unchanged, never later, so
        # it can never buy a window it did not serve. A stamp already present is untouchable.
        if forward_start and not rows[key].get("forward_start"):
            rows[key]["forward_start"] = forward_start
            rows[key]["forward_start_backfilled_at"] = datetime.now(tz=UTC).isoformat(
                timespec="seconds")
            reg["updated_at"] = rows[key]["forward_start_backfilled_at"]
            _write(reg)
        return rows[key]["identity"]
    rows[key] = {
        "identity": ident,
        "identity_schema": IDENTITY_SCHEMA,
        "frozen_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "forward_start": forward_start,
        "status": "LIVE",
    }
    if cost_fields:
        rows[key]["cost_fields"] = {k: round(float(v), 6) for k, v in cost_fields.items()
                                    if isinstance(v, (int, float)) and not isinstance(v, bool)}
    reg["updated_at"] = datetime.now(tz=UTC).isoformat(timespec="seconds")
    _write(reg)
    return ident


def frozen_cost_fields(key: str) -> dict | None:
    """The numeric cost basis `key` froze with, or None for rows frozen before it was stored."""
    row = _read(REGISTRY).get("sleeves", {}).get(key) or {}
    fields = row.get("cost_fields")
    return dict(fields) if isinstance(fields, dict) and fields else None


def verify(key: str, ident: dict) -> list[str]:
    """Return the identity fields that have DRIFTED since freezing. Empty list means intact."""
    row = _read(REGISTRY).get("sleeves", {}).get(key)
    if not row or not row.get("identity"):
        return []                       # never frozen -- freeze() is the caller's next move
    frozen = row["identity"]
    drift = [f for f in IDENTITY_FIELDS
             if json.dumps(frozen.get(f), sort_keys=True, default=str)
             != json.dumps(ident.get(f), sort_keys=True, default=str)]
    # A COMMENT IS NOT A STRATEGY CHANGE. `code_hash` hashes source text, so a docstring or
    # comment edit reads here as a drifted strategy and kills the clock terminally. When BOTH
    # sides recorded a behaviour hash and those AGREE, the bytecode is identical: the function
    # computes exactly what it computed when the clock froze, and the difference is prose.
    # Anything else -- params, symbol, venue, direction, or a behaviour hash that genuinely
    # differs -- still drifts, so a logic change is still a new clock. Rows frozen before this
    # field existed carry no behaviour hash and are unaffected: absence never clears a drift.
    if drift == ["code_hash"]:
        fb, cb = frozen.get("behaviour_hash"), ident.get("behaviour_hash")
        if fb and cb and fb == cb and not str(fb).startswith("nocode:"):
            return []
    return drift


def mark(key: str, status: str, why: str) -> None:
    """Record a terminal or degraded state against a registered sleeve, with its reason."""
    reg = _read(REGISTRY)
    row = reg.setdefault("sleeves", {}).setdefault(key, {})
    row["status"] = status
    row["status_why"] = why
    row["status_at"] = datetime.now(tz=UTC).isoformat(timespec="seconds")
    reg["updated_at"] = row["status_at"]
    _write(reg)


def reconcile(key: str, ident: dict, *, replayed: bool = False) -> str | None:
    """Clear a stopped clock when the identity that stopped it is provably back and unspliced.

    A STATUS THAT ONLY EVER GOES ONE WAY IS NOT A MEASUREMENT (the same argument this engine
    already applies to `BLOCKED_SLEEVE_ERROR`, and L1.37). `mark()` is write-once: nothing in the
    codebase has ever cleared `IDENTITY_BROKEN`, so a clock stopped by an INFRASTRUCTURE event
    stayed dead against a code state that no longer exists anywhere on the box.

    MEASURED 2026-08-28. Six clocks (CADJPY.asia x3, EURJPY.asia x3) were marked
    `code_hash changed after the clock froze` at 15:31 on 2026-08-27. All twelve
    `session_range_breakout` clocks froze the SAME hash `32b3bc38d228df35` -- one family, one
    function, one source -- so six of them cannot have drifted while six did not, in any single
    pass. The desk sync had pushed a stale `families.py` at 11:32:20 that differed from the live
    file by a 20-line DOCSTRING (captured in `data/sync_refused/20260827T113220/`); the pass that
    ran against it began marking rows in registry order and died before reaching the other six.
    The file was restored, and every one of the seventeen rows now recomputes to exactly the hash
    it froze -- yet `check_live_readiness` still blocked rung 0 on "6 sleeve(s) drifted after
    freezing". The producer had recovered; the durable record could not.

    WHY RESUMING IS SOUND HERE, AND WHY IT IS NOT A LOOSENING. The forward engine REPLAYS: every
    pass calls `fam_fn(bars, **params)` over the whole history and recomputes n / cum_r / exp_r
    from scratch, keeping only trades at or after `forward_start`. Nothing from a previous pass
    survives into the numbers. So when the current identity is byte-identical to the frozen one on
    every `IDENTITY_FIELDS` entry, the ENTIRE recorded forward series is by construction the
    frozen strategy's own output -- there is no splice to preserve, and the transient contributed
    no evidence. The two-stage law protects against evidence produced by a different strategy;
    here no such evidence exists. If ANY field still differs the row stays terminal, unchanged.

    `replayed` is the caller's assertion that this clock's evidence is replayed rather than
    accumulated from real fills. A clock that has held order authority has fills that ARE
    historical facts of whatever code was running, and those cannot be recomputed away -- so it is
    never resumed here and must restart with a new identity and a new window.

    Returns the reason when a clock was resumed, else None. The frozen identity, `forward_start`
    and accrued evidence are never touched: this clears a FLAG, it does not re-base a clock.
    """
    if not replayed:
        return None
    reg = _read(REGISTRY)
    row = reg.get("sleeves", {}).get(key)
    if not row or str(row.get("status") or "").upper() != "IDENTITY_BROKEN":
        return None
    if verify(key, ident):
        return None                     # still drifted on some field -- terminal stands
    why = (f"identity intact on every field again (was: {row.get('status_why') or 'unknown'}); "
           f"evidence is replayed from bars, so no observation from the drift survives in it")
    row["status"] = "LIVE"
    row["status_why"] = ""
    row["status_at"] = datetime.now(tz=UTC).isoformat(timespec="seconds")
    row["identity_restored_at"] = row["status_at"]
    row["identity_restored_why"] = why
    # A CLOCK THAT KEEPS FLAPPING IS AN INFRASTRUCTURE ALARM, NOT A HEALTHY CLOCK. The count is
    # kept so a repeatedly-trampled family is visible as such instead of looking permanently fine.
    row["identity_restore_count"] = int(row.get("identity_restore_count") or 0) + 1
    reg["updated_at"] = row["status_at"]
    _write(reg)
    return why


def rebase_cost(key: str, ident: dict, cost_fields: dict) -> str | None:
    """Re-freeze a clock's COST after the desk corrects its own cost model. Nothing else moves.

    THE HOLE `reconcile()` CANNOT FILL. That function clears IDENTITY_BROKEN when the identity
    becomes byte-identical again -- right for a transient (a stale file sync, an outage). A COST
    CORRECTION is neither transient nor reversible: the desk decided the old number was wrong, so
    the frozen hash can never match again and the clock is dead forever.

    MEASURED 2026-09-02. All twelve IDENTITY_BROKEN clocks froze `commission_per_lot: 3.5` -- the
    round-turn figure that sat in a PER-SIDE field, charging $7.00 against a stated $3.50. The
    desk corrected it to Fusion Zero's published 2.25 on 2026-09-01, every cost_hash changed, and
    twelve pre-registered clocks stopped accruing against the `days >= 14` bar. Correcting a known
    error destroyed the evidence gathered while the error stood, permanently, with no way back.

    WHY THIS IS SOUND AND WHY IT IS NOT A LOOSENING:

      * `forward_start` IS NOT TOUCHED. The ratchet holds: pre-registration protects WHICH DAYS
        were observed, and a cost correction does not un-observe a day.
      * THE ENGINE REPLAYS. Every pass recomputes the whole series from bars, so the R multiples
        are recomputed at the corrected cost -- there is no spliced evidence to preserve, and no
        observation priced at the wrong cost survives into the numbers.
      * IT FIRES ON `cost_hash` ALONE. Any other drifted field -- code, params, symbol, venue,
        direction -- and the clock stays terminal. A strategy change is still a new clock.

    THE DANGEROUS DIRECTION IS NAMED, NOT HIDDEN. A "correction" that makes a sleeve CHEAPER is
    the shape of a desk talking itself into an edge, so the old and new cost fields are both
    recorded and `cost_rebase_cheaper` is set when the new charge is lower. A reviewer can find
    every rebase that helped the sleeve it was applied to.

    Returns the reason when a clock was rebased, else None.
    """
    reg = _read(REGISTRY)
    row = reg.get("sleeves", {}).get(key)
    if not row or not row.get("identity"):
        return None
    drift = verify(key, ident)
    if drift != ["cost_hash"]:
        return None                     # sole-cause rule: anything else and the clock stays dead
    old = dict(row.get("cost_fields") or {})
    new = dict(cost_fields or {})
    if not new:
        return None                     # an unmeasured new cost is not a correction (L1.28a)

    def _charge(cf: dict) -> float:
        try:
            qpa = float(cf.get("quote_per_account") or 1.0) or 1.0
            return (float(cf.get("spread_per_lot") or 0.0)
                    + 2.0 * float(cf.get("commission_per_lot") or 0.0)) / qpa
        except (TypeError, ValueError):
            return float("nan")

    before, after = _charge(old), _charge(new)
    cheaper = bool(after == after and before == before and after < before)
    why = (f"cost model corrected after the clock froze "
           f"({old.get('commission_per_lot')}->{new.get('commission_per_lot')} commission, "
           f"{old.get('spread_per_lot')}->{new.get('spread_per_lot')} spread per lot; "
           f"round-trip charge {before:.4f}->{after:.4f} in account units). forward_start "
           f"unchanged; the engine replays, so every observation is repriced at the new cost.")
    row["identity"]["cost_hash"] = ident.get("cost_hash")
    row["cost_fields"] = new
    row["cost_fields_before_rebase"] = old
    row["status"] = "LIVE"
    row["status_why"] = ""
    row["status_at"] = datetime.now(tz=UTC).isoformat(timespec="seconds")
    row["cost_rebased_at"] = row["status_at"]
    row["cost_rebase_why"] = why
    row["cost_rebase_cheaper"] = cheaper
    row["cost_rebase_count"] = int(row.get("cost_rebase_count") or 0) + 1
    reg["updated_at"] = row["status_at"]
    _write(reg)
    return why


def rebase_code(key: str, ident: dict) -> str | None:
    """Restart a clock whose frozen code identity can never be reached again. RESETS the window.

    THE HOLE NEITHER `reconcile()` NOR `rebase_cost()` FILLS. `reconcile` clears IDENTITY_BROKEN
    when the frozen hash comes BACK -- right for a transient, useless when the desk deliberately
    edited the family and the old source exists nowhere. `rebase_cost` re-freezes a corrected COST
    and explicitly keeps `forward_start`, because repricing does not un-observe a day. A CODE
    change is different in exactly the way that matters: if the logic moved, the replayed series
    is a DIFFERENT strategy's output over the old window, and keeping `forward_start` would credit
    one strategy with another's days. That is the precise thing the two-stage law forbids.

    SO THIS RESETS THE WINDOW. The clock lives again, its accrued record is preserved under
    `window_before_rebase` for audit, and `forward_start` becomes now: the sleeve re-earns its
    days against the code that is actually running. Nothing is laundered -- the price of the
    recovery is paid in days, which is the only currency that cannot be faked here.

    MEASURED 2026-09-03: 15 of 52 sleeves (29% of the forward book) were terminal on `code_hash
    changed after the clock froze`, frozen at 32b3bc38d228df35 while both machines agreed the
    current value is 38d9ca40fbd659c6. They had been dead for hours accruing nothing while their
    day counter ran -- "the clock matures on stale data", the worst combination. Going forward
    `behaviour_hash` prevents the common cause (a comment edit reading as a strategy change), so
    this is the recovery path for rows frozen BEFORE that field existed, and for genuine logic
    edits, which should be rare and should cost a window.

    Fires only when `code_hash` is the SOLE drift. Any other field and the clock stays terminal.
    """
    reg = _read(REGISTRY)
    row = reg.get("sleeves", {}).get(key)
    if not row or not row.get("identity"):
        return None
    if str(row.get("status") or "").upper() != "IDENTITY_BROKEN":
        return None
    if verify(key, ident) != ["code_hash"]:
        return None                     # sole-cause rule: anything else and the clock stays dead
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    old_code = row["identity"].get("code_hash")
    why = (f"frozen code identity {old_code} exists nowhere on either machine (current "
           f"{ident.get('code_hash')}); the clock is restarted rather than resumed, so the "
           f"window RESETS and the sleeve re-earns its days against the running code")
    row["window_before_rebase"] = {
        "forward_start": row.get("forward_start"),
        "code_hash": old_code,
        "ended_at": now,
        "why": row.get("status_why") or "",
    }
    row["identity"]["code_hash"] = ident.get("code_hash")
    if ident.get("behaviour_hash"):
        row["identity"]["behaviour_hash"] = ident["behaviour_hash"]
    row["forward_start"] = now
    row["status"] = "LIVE"
    row["status_why"] = ""
    row["status_at"] = now
    row["code_rebased_at"] = now
    row["code_rebase_why"] = why
    row["code_rebase_count"] = int(row.get("code_rebase_count") or 0) + 1
    reg["updated_at"] = now
    _write(reg)
    return why


def live_keys() -> set[str]:
    """Keys the registry considers live -- the ONE answer to 'how many sleeves are running'."""
    return {k for k, v in _read(REGISTRY).get("sleeves", {}).items()
            if str(v.get("status") or "").upper() == "LIVE"}


def snapshot() -> dict:
    """Registry summary for dashboards and health, so they stop counting rows for themselves."""
    rows = _read(REGISTRY).get("sleeves", {})
    by_status: dict[str, int] = {}
    for v in rows.values():
        s = str(v.get("status") or "UNKNOWN").upper()
        by_status[s] = by_status.get(s, 0) + 1
    return {"total": len(rows), "by_status": by_status,
            "live": sorted(live_keys()),
            "note": "the registry is the only authority on sleeve identity and count"}
