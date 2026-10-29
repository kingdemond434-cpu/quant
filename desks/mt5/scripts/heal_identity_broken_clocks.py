"""Standing fixer: revive forward clocks stopped by a code identity that no longer exists.

WHY A STANDING FIXER AND NOT A ONE-OFF. `IDENTITY_BROKEN` is write-once by design and only
`reconcile()` ever cleared it -- and only when the frozen hash comes BACK, which is right for a
transient sync and useless when the desk deliberately edits a family. So every real code edit
permanently killed every clock on that family, and nothing in the desk noticed or recovered.
Measured 2026-09-03: 15 of 52 sleeves -- 29% of the forward book, 110 accrued forward-days --
were terminal on `code_hash changed after the clock froze`, all marked within 13 minutes of each
other while module ships landed. They had been accruing nothing while their day counters kept
running, which the same-day fence calls the worst combination: the clock matures on stale data.

TWO DIFFERENT REPAIRS, AND THE DIFFERENCE IS THE POINT:

  * `reconcile()` first -- the identity came back byte-identical, so the whole replayed series is
    the frozen strategy's own output and the WINDOW IS KEPT. Nothing was lost, nothing is
    laundered.
  * `rebase_code()` only when reconcile refuses -- the frozen code exists nowhere, so the desk
    cannot prove the logic is unchanged and the window RESETS. The sleeve re-earns its days
    against the code actually running. That price is deliberate: the pre-registration named one
    strategy and a different one may not inherit its days.

Going forward the common cause is gone: `sleeve_registry.behaviour_hash` records bytecode rather
than source text, so editing a comment or docstring can no longer read as a strategy change.
This fixer exists for rows frozen before that field existed, and for genuine logic edits -- which
should be rare, and which should cost a window.

    python3 desks/mt5/scripts/heal_identity_broken_clocks.py [--apply]

Reports and changes nothing without --apply, because reviving a clock is a change to what the
desk will treat as evidence.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import inspect
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK / "research"))
sys.path.insert(0, str(DESK))
sys.path.insert(0, str(DESK.parents[1]))
REPO = DESK.parents[1]

import sleeve_registry as reg  # noqa: E402


def current_identity(row: dict) -> dict | None:
    """Rebuild the identity this sleeve WOULD freeze today, or None if it cannot be computed.

    UNMEASURED IS A REAL ANSWER (L1.28a). If the family cannot be loaded the row is left exactly
    as it is: a clock that cannot be evaluated is not a clock that may be revived.
    """
    frozen = dict(row.get("identity") or {})
    # A compiler/roster spec is NOT a frozen execution identity. Older versions of this
    # healer froze {symbol, family, selector, params, side}, then compared that incomplete
    # dict with itself and repeatedly declared it restored. The real engine correctly saw
    # direction/timeframe/cost/venue drift. Measured 2026-10-03: three GBPMXN clocks had been
    # falsely "restored" 77 times. Missing fields cannot prove an intact forward window.
    if not frozen or any(field not in frozen for field in reg.IDENTITY_FIELDS):
        return None
    if not all(frozen.get(field) for field in
               ("direction", "timeframe", "code_hash", "cost_hash", "data_venue")):
        return None
    # THE SAME RESOLUTION THE FORWARD ENGINE USES, not a narrower one. `get_family_func` only
    # searches FAMILY_REGISTRY, and the desk's most numerous family -- `discovered`, the one
    # edge_search mints -- lives in ORTHOGONAL_FAMILIES. Resolving with the narrow lookup returned
    # None for every one of those rows, so they were silently skipped and the backfill reported
    # zero: a healer that appeared to run cleanly while covering none of the clocks that needed it.
    fn = family_fn(str(frozen.get("family") or ""))
    if fn is None:
        return None
    ident = dict(frozen)
    ident["code_hash"] = reg.code_hash(fn)
    ident["behaviour_hash"] = reg.behaviour_hash(fn)
    return ident


def family_fn(fam: str) -> Any:
    """The callable the forward engine would run for `fam`, or None when it cannot be loaded."""
    fn = None
    try:
        from mt5desk import families
        fn = getattr(families, f"family_{fam}", None)
    except ImportError:
        return None
    if fn is None:
        try:
            from mt5desk import families_orthogonal as _fo
            fn = _fo.ORTHOGONAL_FAMILIES.get(fam)
        except ImportError:
            fn = None
    return fn


#: Where the hold is published, and how far back the frozen source is looked for.
REPORT = DESK / "reports" / "IDENTITY_HEALER.json"
SOURCE_LOOKBACK = 400
_REVISION_HASHES: dict[tuple[str, str], str | None] = {}


def _def_hash(text: str, name: str) -> str | None:
    """`sleeve_registry.code_hash` of module-level `def name` in `text` (def line to body end)."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
    lines = text.splitlines(keepends=True)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            src = "".join(lines[node.lineno - 1:node.end_lineno])
            return hashlib.sha256(src.encode("utf-8")).hexdigest()[:16]
    return None


def frozen_source_revision(fn: Any, frozen_hash: str, *,
                           lookback: int = SOURCE_LOOKBACK) -> str | None:
    """The git revision whose copy of `fn` hashes to the code_hash a clock froze, else None.

    WHY THE HEALER LOOKS BEFORE IT RESETS (2026-10-29). `rebase_code()` is right only when "the
    frozen code exists nowhere" -- and that was asserted, never measured. On 2026-10-28 three
    families_vector commits put a speed-only, signal-identical fast path INSIDE 18 family bodies;
    every clock on those families went IDENTITY_BROKEN on adopt (51 code_hash-only rows in the
    10-29 shadow_state, 48 formula) and the next healer pass would have reset every one of their
    windows, although the frozen source sat in git one commit back. A frozen source that IS
    recoverable means the window can be proven equivalent by replay, so it must not be reset.

    Unreadable git, a shallow clone that lacks the revision, or a callable with no module-level
    def all answer None -- and None leaves today's behaviour unchanged (L1.28a: no claim of
    recoverability without the revision in hand).
    """
    try:
        path = Path(inspect.getsourcefile(fn) or "").resolve()
        rel = path.relative_to(REPO).as_posix()
    except (TypeError, ValueError, OSError):
        return None
    name = getattr(fn, "__name__", "")
    try:
        revs = subprocess.run(
            ["git", "-C", str(REPO), "log", "--format=%H", "-n", str(lookback), "--", rel],
            capture_output=True, text=True, timeout=60, check=False).stdout.split()
    except (OSError, subprocess.SubprocessError):
        return None
    for rev in revs:
        cache = (rev, f"{rel}:{name}")
        if cache not in _REVISION_HASHES:
            try:
                text = subprocess.run(["git", "-C", str(REPO), "show", f"{rev}:{rel}"],
                                      capture_output=True, text=True, timeout=60,
                                      check=False).stdout
            except (OSError, subprocess.SubprocessError):
                text = ""
            _REVISION_HASHES[cache] = _def_hash(text, name) if text else None
        if _REVISION_HASHES[cache] == frozen_hash:
            return rev
    return None


def vector_hooked(fn: Any) -> bool:
    """Whether `fn` carries a families_vector fast path (speed only, signal-identical by test)."""
    try:
        src = inspect.getsource(fn)
    except (OSError, TypeError):
        return False
    return "families_vector" in src or "_vec." in src


def reattach_hold(row: dict[str, Any]) -> str | None:
    """Why a code_hash-only break must WAIT for an equivalence re-attach instead of resetting.

    The window is held, never reset, when the frozen source is recoverable from git (an
    equivalence replay can prove the old and new code emit the same trades) or the family carries
    a families_vector hook (speed only, pinned signal-identical by test_families_vector_identity*).
    The engine replays from bars, so a held clock loses no day: once re-attached on its original
    forward_start the whole window is recomputed. Returns None when neither holds -- the
    existing rebase path then runs unchanged.
    """
    frozen = row.get("identity") or {}
    fn = family_fn(str(frozen.get("family") or ""))
    if fn is None:
        return None
    rev = frozen_source_revision(fn, str(frozen.get("code_hash") or ""))
    if rev:
        return (f"HELD_FOR_REATTACH: frozen source {frozen.get('code_hash')} recoverable at "
                f"{rev[:10]} -- an equivalence replay can keep the window, so it is not reset")
    if vector_hooked(fn):
        return ("HELD_FOR_REATTACH: family carries a speed-only families_vector hook -- the "
                "code_hash moved, the signals did not; window held for the equivalence replay")
    return None


def backfill_behaviour(registry_path: Path, *, apply: bool) -> int:
    """Record a behaviour hash on every INTACT clock that lacks one. Returns rows immunised.

    WHY THIS IS THE OTHER HALF OF THE FIX. `behaviour_hash` only stops a prose edit from killing a
    clock when BOTH the frozen identity and the current one carry it -- absence never clears a
    drift, deliberately, because a missing hash is not evidence of anything. So every row frozen
    before the field existed is still one comment away from going terminal. Measured 2026-09-03
    after the first repair: 15 of 52 rows carried the field (the ones just rebased) and 37 did
    not. Those 37 were exactly as fragile as the 15 had been an hour earlier.

    THE BACKFILL IS SAFE BECAUSE OF ITS PRECONDITION, WHICH IS NOT NEGOTIABLE. It fires only when
    the frozen `code_hash` still EQUALS the current one. That equality means the function's source
    is byte-identical to what the clock froze, so its bytecode is necessarily the bytecode that
    was frozen too -- recording it asserts nothing new, it writes down a fact the identity check
    has already verified this pass. A row whose code_hash has drifted is skipped entirely: for
    that row the current behaviour is NOT known to be the frozen behaviour, and guessing would be
    the laundering this whole mechanism exists to prevent.
    """
    document = json.loads(registry_path.read_text("utf-8"))
    changed = 0
    for _key, row in (document.get("sleeves") or {}).items():
        frozen = row.get("identity") or {}
        if not frozen or frozen.get("behaviour_hash"):
            continue
        ident = current_identity(row)
        if ident is None:
            continue
        if frozen.get("code_hash") != ident.get("code_hash"):
            continue                    # drifted: current behaviour is not the frozen behaviour
        beh = ident.get("behaviour_hash")
        if not beh or str(beh).startswith("nocode:"):
            continue                    # UNMEASURED is a real answer -- never write a guess
        if apply:
            frozen["behaviour_hash"] = beh
            row["behaviour_backfilled_at"] = datetime.now(tz=UTC).isoformat(timespec="seconds")
        changed += 1
    if changed and apply:
        document["updated_at"] = datetime.now(tz=UTC).isoformat(timespec="seconds")
        tmp = registry_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(document, indent=1), "utf-8")
        reg._replace_with_retry(tmp, registry_path)
    return changed


def is_registered_family(name: str) -> bool:
    """True when `name` is a family the forward engine can actually construct.

    THE ONE AUTHORITY, NEVER A SECOND LIST. `shadow_forward._family_fn` is the resolver the
    engine itself uses (`mt5desk.families.family_<name>` then
    `families_orthogonal.ORTHOGONAL_FAMILIES`). A hardcoded window list here would be a second
    vocabulary that rots away from the first, which is the producer collapse this desk keeps
    paying for. Unreachable resolver reads FALSE -- the caller then falls back to the historic
    behaviour, so an import failure cannot invent a family that is not there.
    """
    try:
        from shadow_forward import _family_fn  # type: ignore[import-not-found]
    except ImportError:                                # pragma: no cover - packaged import
        try:
            from research.shadow_forward import _family_fn  # type: ignore[no-redef]
        except ImportError:
            return False
    try:
        return _family_fn(str(name)) is not None
    except Exception:
        return False


def legacy_identity(key: str, row: dict) -> dict | None:
    """The identity a legacy clock key names: `SYM.window[.STATE]` is the hunt16 lane's
    session_range_breakout at that window, LONG unless the row says otherwise. A key with the
    modern dotted family form is left to the engine's own enrolment.

    SLOT 1 IS NOT ALWAYS A WINDOW, AND ASSUMING IT WAS SWAPPED FAMILY WITH SELECTOR ON EVERY
    MODERN KEY THAT CARRIES NO PARAMS. The guard below used to reject only keys containing `=`
    or `#`, so `XAUUSD.multi_speed_trend.continuous@D1` -- a modern `SYM.family.selector@TF` key
    whose params happen to be empty -- fell through to the hunt16 branch and froze as
    `family=session_range_breakout, selector=multi_speed_trend`: exactly backwards. Measured on
    the trading box 2026-09-24: 1 LIVE row and 20+ RETIRED rows carry that swap, every one of
    them `family=session_range_breakout` beside a selector that is itself a registered family
    name.

    The canonical identity is `symbol|family|selector` lowercased -- what the sealed gauntlet
    stamps and what the promoter matches on -- so a swap there is not cosmetic: it is a row that
    can never join its own certificate, its allocator cell or its ledger. Slot 1 is therefore
    tested against the engine's own family resolver before the window assumption is applied.
    """
    parts = str(key).split(".")
    if len(parts) < 2 or "=" in key or "#" in key:
        return None
    sym, slot1 = parts[0], parts[1]
    if not sym.isupper() or not slot1:
        return None
    if is_registered_family(slot1):
        # `SYM.family.selector[@TF]` -- the modern form with empty params. The timeframe rides
        # on the selector as `@TF` and is split out, because it is an identity field in its own
        # right and leaving it glued to the selector breaks the same join the swap broke.
        selector, _, timeframe = (parts[2] if len(parts) > 2 else "continuous").partition("@")
        ident = {"symbol": sym, "selector": selector or "continuous", "family": slot1,
                 "side": str(row.get("side") or "LONG").upper(), "params": {}}
        if timeframe:
            ident["timeframe"] = timeframe
        return ident
    ident = {"symbol": sym, "selector": slot1, "family": "session_range_breakout",
             "side": str(row.get("side") or "LONG").upper(), "params": {}}
    if len(parts) > 2:
        ident["state"] = parts[2]
    return ident


def cost_fields_for(symbol: str) -> dict[str, float] | None:
    """The cost basis a clock on `symbol` must freeze with, or None when it cannot be measured.

    A LIVE CLOCK WITH NO COST BASIS IS THE DEFECT THIS EXISTS TO STOP. `freeze()` stores
    `cost_fields` so the forward engine keeps replaying the window on the basis it was admitted
    on; `shadow_forward` line 758 falls through to LIVE re-measured costs when they are absent,
    so a null does not read as free -- it reads as a clock whose cost moves under it every pass,
    which is the identity churn the frozen basis exists to prevent. Measured on the trading box
    2026-09-24: 13 LIVE rows carried no cost_fields at all, 8 of them XAUUSD, every one frozen
    by THIS script -- the only `freeze()` caller that omitted the argument.

    `Costs.from_symbol` is the only correct constructor (engine.py documents three separate unit
    traps that hand-rolling it at a call site has already cost this desk), so it is what builds
    the basis here. None on an unreadable registry or an unknown symbol: UNMEASURED is a real
    answer and a guessed cost basis is worse than an absent one.
    """
    try:
        from mt5desk.engine import Costs
    except ImportError:                                # pragma: no cover - packaged import
        return None
    uni = DESK / "data" / "universe" / "universe.json"
    try:
        reg_syms = json.loads(uni.read_text("utf-8"))
    except (OSError, ValueError):
        return None
    meta = (reg_syms.get("symbols") or reg_syms).get(str(symbol))
    if not isinstance(meta, dict):
        return None
    try:
        costs = Costs.from_symbol(meta)
    except (TypeError, ValueError, KeyError):
        return None
    out = {f: float(getattr(costs, f)) for f in
           ("spread_per_lot", "commission_per_lot", "contract_oz", "quote_per_account")}
    return out if all(v == v and abs(v) != float("inf") for v in out.values()) else None


def engine_identities() -> dict[str, dict]:
    """clock key -> identity for every certificate the forward engine enrols (the promoter's own
    resolver); empty when the engine cannot be loaded here."""
    try:
        import promoter
        return dict(promoter.clock_identities() or {})
    except Exception:
        return {}


def execution_identity(spec: dict, fields: dict | None) -> dict | None:
    """Resolve a roster spec through the SAME identity constructor as the forward engine.

    Never bless a spec missing its executable code, measured costs or evidence venue. The
    ordinary forward pass remains the owner when those prerequisites cannot be measured.
    This only freezes previously unfrozen rows; it never rewrites a malformed old identity
    or inherits its window. Such a migration needs an archived, new evidence epoch.
    """
    if fields is None:
        return None
    try:
        from mt5desk.engine import Costs
        from mt5desk.family_inputs import timeframe_of
        from research.h1_source import from_cache
        from shadow_forward import _family_fn

        family = str(spec.get("family") or "")
        symbol = str(spec.get("symbol") or "")
        params = dict(spec.get("params") or {})
        timeframe = str(spec.get("timeframe") or timeframe_of(params))
        fn = _family_fn(family)
        bars = from_cache(symbol, datetime.now(UTC), timeframe)
        if fn is None or bars is None or bars.evidence_venue == "UNKNOWN-VENUE":
            return None
        return reg.identity(
            family=family, symbol=symbol,
            direction=str(spec.get("direction") or spec.get("side") or "LONG"),
            timeframe=timeframe, selector=str(spec.get("selector") or ""),
            condition=spec.get("condition"), params=params,
            code=reg.code_hash(fn), behaviour=reg.behaviour_hash(fn),
            cost=reg.cost_hash(Costs(**fields)), data_venue=bars.evidence_venue)
    except (ImportError, TypeError, ValueError, KeyError, OSError):
        return None


def freeze_unfrozen(registry: dict, *, apply: bool, identities: dict | None = None) -> int:
    """Freeze every running main-lane clock that has no frozen identity. Returns the count.

    Legacy keys (`SYM.window[.STATE]`) freeze the identity their key names; modern keys
    (`SYM.family.selector#params`) freeze the identity the engine enrolled them with."""
    shadow_path = DESK / "reports" / "shadow" / "shadow_state.json"
    try:
        shadow = json.loads(shadow_path.read_text("utf-8"))
    except (OSError, ValueError):
        return 0
    frozen = {k for k, v in (registry.get("sleeves") or {}).items()
              if isinstance(v, dict) and v.get("identity")}
    engine = identities if identities is not None else None
    n = 0
    for key, row in sorted(shadow.items()):
        if not isinstance(row, dict) or key in frozen:
            continue
        if str(row.get("status") or "").upper() not in ("ACTIVE", "PROMOTION CANDIDATE",
                                                        "PROMOTION_CANDIDATE"):
            continue
        ident = legacy_identity(key, row)
        if ident is None and "#" in key:
            if engine is None:
                engine = engine_identities()
            ident = dict(engine.get(key) or {}) or None
        if ident is None:
            continue
        fields = cost_fields_for(str(ident.get("symbol") or ""))
        ident = execution_identity(ident, fields)
        if ident is None:
            print(f"  FREEZE BLOCKED {key}: execution identity unmeasured; engine must freeze it")
            continue
        n += 1
        if apply:
            try:
                # THE COST BASIS IS PART OF THE CLOCK, NOT AN EXTRA. `shadow_forward` has always
                # passed `cost_fields=vars(costs)` here; this caller did not, and every LIVE row
                # it minted was born with a null cost on the money path.
                reg.freeze(key, ident, forward_start=row.get("forward_start"),
                           cost_fields=fields)
                print(f"  FROZEN {key}: {ident.get('symbol')} {ident.get('selector')} "
                      f"{ident.get('family')} {ident.get('side')} "
                      f"forward_start={row.get('forward_start')} "
                      f"cost={'MEASURED' if fields else 'UNMEASURED'}")
            except Exception as exc:
                print(f"  FREEZE FAILED {key}: {type(exc).__name__}: {exc}")
        else:
            print(f"  would freeze {key}")
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="actually revive; without it this only reports")
    args = ap.parse_args()

    registry = json.loads((DESK / "data" / "sleeve_registry.json").read_text("utf-8"))
    # BACKFILL FIRST, AND UNCONDITIONALLY. This ran after an early `return 0` taken when nothing
    # was broken -- so it fired only on cycles where a clock had ALREADY died, which is precisely
    # when immunisation is too late. Immunising healthy rows is the entire point: it is what stops
    # the next prose edit from breaking them. Measured 2026-09-03: the first shipped version left
    # 37 of 52 rows uncovered because every run took that early exit.
    immunised = backfill_behaviour(DESK / "data" / "sleeve_registry.json", apply=args.apply)
    if immunised:
        print(f"identity healer: recorded a behaviour hash on {immunised} intact clock(s) "
              f"-- a prose edit can no longer stop them")
        registry = json.loads((DESK / "data" / "sleeve_registry.json").read_text("utf-8"))

    # NO RUNNING CLOCK WITHOUT A FROZEN IDENTITY (principal 2026-09-16: "no forward lane should
    # ever be inactive; the fixer makes all reachable and working"). The reconciler reported 46
    # ACTIVE clocks with no frozen identity -- legacy hunt16 keys enrolled before the registry
    # froze anything -- and left them standing ("freezing is the engine's job"). It is this
    # healer's job now: freeze each one with the identity its key names and the forward_start
    # the clock already carries. `freeze` is idempotent, so a frozen clock is never re-based.
    frozen_now = freeze_unfrozen(registry, apply=args.apply)
    if frozen_now:
        print(f"identity healer: froze {frozen_now} running clock(s) that had no identity"
              f"{'' if args.apply else ' (dry run -- pass --apply)'}")
        registry = json.loads((DESK / "data" / "sleeve_registry.json").read_text("utf-8"))
    broken = {k: v for k, v in (registry.get("sleeves") or {}).items()
              if str(v.get("status") or "").upper() == "IDENTITY_BROKEN"}
    if not broken:
        print("identity healer: no IDENTITY_BROKEN clocks")
        if args.apply:
            write_report(0, resumed=[], rebased=[], held=[], refused=[])
        return 0

    resumed, rebased, refused, held = [], [], [], []
    for key, row in sorted(broken.items()):
        ident = current_identity(row)
        if ident is None:
            refused.append((key, "family not loadable here; nothing computed, nothing changed"))
            continue
        if args.apply:
            why = reg.reconcile(key, ident, replayed=True)
            if why:
                resumed.append((key, why))
                continue
            if reg.verify(key, ident) == ["code_hash"]:
                hold = reattach_hold(row)
                if hold:
                    held.append((key, hold))
                    continue
            why = reg.rebase_code(key, ident)
            if why:
                rebased.append((key, why))
                continue
            refused.append((key, "drift is not code_hash alone -- a strategy change stays dead"))
        else:
            drift = reg.verify(key, ident)
            if not drift:
                resumed.append((key, "identity intact again -- window would be KEPT"))
            elif drift == ["code_hash"] and (hold := reattach_hold(row)):
                held.append((key, hold))
            elif drift == ["code_hash"]:
                rebased.append((key, f"code {row['identity'].get('code_hash')} -> "
                                     f"{ident.get('code_hash')} -- window would RESET"))
            else:
                refused.append((key, f"drifted on {drift} -- stays dead"))

    verb = "" if args.apply else " (dry run -- pass --apply)"
    print(f"identity healer{verb}: {len(broken)} broken -> "
          f"{len(resumed)} resumed (window kept), {len(rebased)} rebased (window reset), "
          f"{len(held)} held for re-attach (window kept), {len(refused)} left terminal")
    for group, label in ((resumed, "RESUMED"), (rebased, "REBASED"), (held, "HELD"),
                         (refused, "TERMINAL")):
        for key, why in group:
            print(f"  {label:9s} {key[:46]:<48} {why[:96]}")
    if args.apply:
        write_report(len(broken), resumed=resumed, rebased=rebased, held=held, refused=refused)
    return 0


def write_report(broken: int, **groups: list[tuple[str, str]]) -> dict[str, Any]:
    """Publish the pass, with the RED line rule 23 asks for (reports/IDENTITY_HEALER.json).

    RED while any clock is held: a held clock replays nothing until the equivalence re-attach
    lands, so the desk must see it every hour rather than read "healed" off a quiet log.
    """
    held = groups.get("held") or []
    doc = {
        "generated_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "broken": broken,
        **{name: [{"key": k, "why": w} for k, w in rows] for name, rows in groups.items()},
        "verdict": "RED" if held else "GREEN",
        "why": (f"{len(held)} forward clock(s) stopped on a code_hash-only break whose window "
                f"is held for the equivalence re-attach" if held else
                "no clock waits on a re-attach"),
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    tmp = REPORT.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1), "utf-8")
    tmp.replace(REPORT)
    return doc


if __name__ == "__main__":
    sys.exit(main())
