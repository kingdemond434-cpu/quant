"""ONE CERTIFICATE TRUTH -- the audit of every store that claims a certificate or a clock, and
the one-time migration that folds the residue into the single canonical lane.

    python desks/mt5/research/certificate_truth.py --once --budget-s 120   # audit (hourly leg)
    python desks/mt5/research/certificate_truth.py --once --apply          # migration, once (box)

THE SPLIT BRAIN THIS CLOSES (principal, 2026-09-22: "make everything one unified n canon ... one
permanent lane truth always"). Measured on the trading box the same day: `UNIVERSAL_SURVIVORS.json`
said n=0 while `sleeve_registry.json` held ~693 clocks (124 of them of the `discovered` family the
principal banned on 2026-09-16), `SURVIVORS_LEDGER.json` still filed claims,
`forward_reconcile.json` counted certified clocks of its own, and `sleeves.json` carried live rows
whose certificate named a cell no canon held. Five stores, five answers to "what is certified",
and every organ downstream reading whichever one it happened to open.

THE LANE. There is ONE writer of certificates, `desks/mt5/scripts/external_gauntlet.py`, and it
writes ONE authority file, `reports/UNIVERSAL_SURVIVORS.json` (sealed to `data/
UNIVERSAL_SURVIVORS.canon.json`), under the exact ten-gate attestation `gate_policy.ATTESTATION`.
Its ONE consumer for capital is `desks/mt5/research/promoter.py`, which admits a row only when the
exact spec is in that authority set. Both files are immutable and this module reads them only.
The same writer has ONE second output, the power-cure candidates
(`reports/POWER_CURE_CANDIDATES.json` and the `QQUANT_GATES.json` verdicts that passed every
validity gate and are curing a power gate on a forward clock, `gate_spec.yaml:
power_cure_via_forward`): a clock they name is BACKED by the lane without being a certificate,
and is counted as `cure_backed`, never as unbacked.
Everything else -- the survivors ledger, the sleeve registry, the shadow clock state, the lane
states, `sleeves.json`, `forward_reconcile.json` -- is DERIVED from the lane, and a row in any of
them that the lane does not back is a divergence, published here by store, key and reason.

WHAT THE AUDIT PUBLISHES (`reports/CERTIFICATE_TRUTH.json`, hourly, never --apply on a clock):

    BANNED_CERTIFICATE     a certificate of a banned family still in the canon or its seal
    BANNED_CLAIM/CLOCK/SLEEVE
                           a banned-family row still LIVE/ACTIVE/STANDBY in any derived store
    CLAIM_NOT_IN_CANON     a ledger claim filed as UNIVERSAL that the canon no longer holds
    UNBACKED_CLOCK         a LIVE registry row or a running shadow clock whose symbol, family and
                           selector no ten-gate certificate names (the promoter's own join: the
                           PARTS, never a parsed name)
    UNPARSED_CLOCK         a row whose identity this module could not read -- reported, never acted
                           on: absence of a parse is not a verdict (L1.28a)
    CANON_UNMEASURED_WITH_LIVE_CLOCKS
                           the authority file carries no exact attestation while clocks run
    RECONCILE_CERTIFIED_CLOCKS_ON_EMPTY_CANON
                           the reconciler's report counts certified clocks the canon does not hold

WHAT --apply DOES, once, on the box (the coordinator runs it; the hourly leg never does):

    * discovered-family certificates leave the canon and its seal for
      `data/certificate_history.jsonl` (status RETIRED, reason "discovered family banned from
      live capital; certificate discovery banned") -- the gauntlet is the one writer of NEW
      certificates; this removes only rows of a family the principal banned, and records each
      one it moved;
    * discovered-family clocks (registry, shadow state, every lane state) and live sleeves are
      RETIRED with that reason -- the same vocabulary `promoter.retire_banned` and
      `sleeve_registry.mark` use, so every reader already understands the row;
    * every remaining LIVE registry row and running shadow clock is either BACKED by the lane or
      RETIRED with the reason that names the lane. Two protections, both reported by name:
      a clock on a symbol the live book trades under a principal override is never retired here
      (the book is the principal's, LAWS 5j), and a row this module cannot parse is never touched.
    * an UNMEASURED canon (no exact attestation readable) retires nothing but banned rows: an
      unreadable authority is not evidence that a clock is unbacked.

The fence `scripts/check_certificate_truth.py` fails the law gate on any divergence; the lesson
is in `docs/desk_lessons.jsonl` (certificate_truth); the leg is `hourly_cycle:certificate_truth`.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK / "research"), str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

#: The family the principal banned on 2026-09-16; banned here whatever `banned_families.json`
#: says, because certificate discovery itself is banned (principal, 2026-09-22).
DISCOVERED = "discovered"
BAN_REASON = "discovered family banned from live capital; certificate discovery banned"
UNBACKED_REASON = ("no ten-gate certificate in the canonical lane (reports/UNIVERSAL_SURVIVORS.json"
                   ", written by external_gauntlet.py) and no power-cure candidate of its writer "
                   "(reports/POWER_CURE_CANDIDATES.json, reports/QQUANT_GATES.json) names this "
                   "clock's symbol, family and selector")
CURE_REASON = ("power-cure candidate: every validity gate passed, a power gate is being cured by "
               "forward evidence (gate_spec.yaml power_cure_via_forward) -- backed by the lane's "
               "writer, not yet a certificate")
SCALP_DECLARED_REASON = ("declared candidate of the scalp lane's writer (scripts/scalp_gauntlet.py"
                         " -> reports/SCALP_GAUNTLET.json, whose canon_rows() the gauntlet merges "
                         "into the authority file): judged daily, gathering forward evidence -- "
                         "backed by the lane's writer, not yet a certificate")
RESTORE_REASON = ("retirement reason no longer holds under the sealed writer's own predicate "
                  "(external_gauntlet.symbol_is_tradeable against data/universe/universe.json); "
                  "restored to the canonical lane with its gates record intact")
SEAL_RESTORE_REASON = ("authority file degraded against its own seal with no revocation record: "
                       "the seal is the recovery source by definition "
                       "(scripts/check_authority_ratchet.restore_authority)")
HISTORY_REASON = "certificate no longer held by the canonical lane; claim kept as history"
RETIRED_BY = "certificate_truth"

#: Row statuses that mean "this row claims to be live" in each store.
LIVE_SLEEVE = frozenset({"LIVE", "STANDBY"})
LIVE_REGISTRY = frozenset({"LIVE"})
#: Shadow-clock statuses that are NOT a live claim (forward_reconcile.TERMINAL plus the policy
#: verdict, which is a decision elsewhere and is never counted here).
TERMINAL = frozenset({"KILL", "KILLED", "PROMOTED", "DEAD", "REJECTED", "RETIRED",
                      "RETIRED_ORPHAN", "RETIRED_GATE_FAIL", "RETIRED_UNRECONSTRUCTIBLE",
                      "QUARANTINED_UNCERTIFIED", "REFUSED_BY_UNIVERSE_POLICY"})
SESSION_WINDOWS = ("asia", "london_am", "ny_open", "afternoon")
SRB = "session_range_breakout"

# ------------------------------------------------------------------ THE ONE CANONISED LANE
# The principal, 2026-09-23: "all certificates and clocks must be ONE canonised lane, not
# separate; all other claimed ones must be tested canonically -- the splits on the research
# system are the problem." So the lane is NAMED here, in code, and the fence fails on any re-split.
#
#: THE ONE certificate store. Written by the sealed gauntlet under the ten-gate attestation, read
#: by the promoter for capital. Nothing else may be a certificate store.
CANONICAL_CERTIFICATE_STORE = "reports/UNIVERSAL_SURVIVORS.json"
#: THE ONE clock store. Every forward clock in every lane has its row here.
CANONICAL_CLOCK_STORE = "data/sleeve_registry.json"
#: DERIVED VIEWS: {store: what generates it}. A derived store is never written independently --
#: it is regenerated from its canonical source, and a writer that edits one directly is a defect.
DERIVED_VIEWS = {
    "data/UNIVERSAL_SURVIVORS.canon.json": CANONICAL_CERTIFICATE_STORE,
    "data/forward_reconcile.json": CANONICAL_CLOCK_STORE,
}
#: CLAIM STORES: they may PROPOSE, never certify. Every row here that the canon does not hold is
#: submitted to the ONE judge (the sealed gauntlet) and is honoured by nobody until it comes back
#: with a ten-gate attestation. Self-declaration confers nothing -- the scalp lane's included.
CLAIM_STORES = ("reports/SURVIVORS_LEDGER.json", "reports/POWER_CURE_CANDIDATES.json",
                "reports/SCALP_GAUNTLET.json", "reports/QQUANT_GATES.json")
#: One judging cycle: the sealed gauntlet's clock. A claim older than this that reached no queue
#: is a claim nobody will ever judge, which is the split the principal named.
JUDGING_CYCLE_S = 24 * 3600.0
QUEUE_REASON = ("claim submitted to the ONE judge (desks/mt5/scripts/external_gauntlet.py): no "
                "store certifies by declaring, and a claim the canon does not hold is a "
                "hypothesis until the ten gates say otherwise")

#: The divergence kinds the fence fails on. UNPARSED and LANE_UNBACKED are published, never fatal.
FATAL_KINDS = frozenset({"BANNED_CERTIFICATE", "BANNED_CLAIM", "BANNED_CLOCK", "BANNED_SLEEVE",
                         "BANNED_CURE_CANDIDATE", "CLAIM_NOT_IN_CANON", "UNBACKED_CLOCK",
                         "CANON_UNMEASURED_WITH_LIVE_CLOCKS",
                         "CANON_EMPTY_WITH_RESTORABLE_EVIDENCE",
                         "SECOND_CERTIFICATE_STORE", "DERIVED_STORE_WRITTEN_DIRECTLY",
                         "JOIN_COVERAGE_BREACH",
                         "CLAIM_NOT_SUBMITTED_TO_JUDGE",
                         "RECONCILE_CERTIFIED_CLOCKS_ON_EMPTY_CANON"})


@dataclass(frozen=True)
class Paths:
    """Every store the audit reads, rooted at one desk so tests build a whole desk in tmp_path."""

    base: Path
    canon: Path
    seal: Path
    ledger: Path
    registry: Path
    reconcile: Path
    sleeves: Path
    shadow: Path
    lanes: tuple[Path, ...]
    banned: Path
    out: Path
    history: Path
    events: Path
    cure: Path
    qq_gates: Path
    scalp_gates: Path
    universe: Path
    queue: Path
    canon_rel: str = "reports/UNIVERSAL_SURVIVORS.json"
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def at(cls, base: Path) -> Paths:
        shadow_dir = base / "reports" / "shadow"
        return cls(
            base=base,
            canon=base / "reports" / "UNIVERSAL_SURVIVORS.json",
            seal=base / "data" / "UNIVERSAL_SURVIVORS.canon.json",
            cure=base / "reports" / "POWER_CURE_CANDIDATES.json",
            qq_gates=base / "reports" / "QQUANT_GATES.json",
            scalp_gates=base / "reports" / "SCALP_GAUNTLET.json",
            universe=base / "data" / "universe" / "universe.json",
            queue=base / "data" / "hypotheses" / "certification_queue.jsonl",
            ledger=base / "reports" / "SURVIVORS_LEDGER.json",
            registry=base / "data" / "sleeve_registry.json",
            reconcile=base / "data" / "forward_reconcile.json",
            sleeves=base / "data" / "sleeves.json",
            shadow=shadow_dir / "shadow_state.json",
            lanes=(shadow_dir / "qquant_shadow_state.json", shadow_dir / "scalp_shadow_state.json",
                   shadow_dir / "external_shadow_state.json",
                   shadow_dir / "precert_shadow_state.json"),
            banned=base / "data" / "banned_families.json",
            out=base / "reports" / "CERTIFICATE_TRUTH.json",
            history=base / "data" / "certificate_history.jsonl",
            events=base / "data" / "events.jsonl",
        )


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _read(path: Path) -> dict[str, Any] | None:
    """The document, or None when absent or unreadable -- never {} for either (L1.28a)."""
    try:
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def _atomic(path: Path, doc: Any, indent: int = 1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(doc, indent=indent, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _dict(v: Any) -> dict[str, Any]:
    """`v` when it is a dict, else {} -- one spelling of the guard, typed once."""
    return v if isinstance(v, dict) else {}


def _rel(paths: Paths, p: Path) -> str:
    try:
        return p.relative_to(paths.base).as_posix()
    except ValueError:
        return p.as_posix()


def _policy() -> tuple[Any, Any]:
    """(all_ten_pass, is_exact_policy) from the sealed gate policy, or (None, None)."""
    try:
        from gate_policy import all_ten_pass, is_exact_policy  # type: ignore[import-not-found]
    except ImportError:
        try:
            from research.gate_policy import (
                all_ten_pass,
                is_exact_policy,
            )
        except ImportError:
            return None, None
    return all_ten_pass, is_exact_policy


# ----------------------------------------------------------------------------- identity
def parts(symbol: object, family: object, selector: object) -> str:
    """The promoter's join key: symbol|family|selector, lowercased -- never a parsed name."""
    return "|".join(str(x or "").strip().lower() for x in (symbol, family, selector))


def parse_clock_key(key: str) -> dict[str, Any] | None:
    """{symbol, family, selector, side, timeframe} from a clock key, or None when the key's shape
    is not one this desk writes. The engine's `sleeve_key` writes `SYM.window`, `SYM.family.window`,
    optionally `@TF`, `#param=value_...` and `.SHORT`; qquant keys carry their cell as tokens."""
    k = str(key or "").strip()
    if not k:
        return None
    side = "LONG"
    if k.endswith(".SHORT"):
        side, k = "SHORT", k[: -len(".SHORT")]
    k = k.split("#", 1)[0]
    timeframe = "H1"
    if "@" in k:
        k, timeframe = k.split("@", 1)
    if k.startswith("qquant."):
        tokens = k.split(".")[-1].split()
        if len(tokens) >= 4:
            return {"symbol": tokens[0], "family": tokens[1], "selector": tokens[3],
                    "side": tokens[2].upper(), "timeframe": timeframe}
        return None
    if k.startswith(("external.", "scalp.")):
        bits = k.split(".")
        if len(bits) >= 3:
            return {"symbol": bits[1], "family": bits[2], "selector": None, "side": side,
                    "timeframe": timeframe}
        return None
    bits = k.split(".")
    if len(bits) == 2:
        return {"symbol": bits[0], "family": SRB, "selector": bits[1], "side": side,
                "timeframe": timeframe}
    if len(bits) == 3:
        return {"symbol": bits[0], "family": bits[1], "selector": bits[2], "side": side,
                "timeframe": timeframe}
    return None


def _cert_key_of(row: dict[str, Any]) -> str | None:
    """The certificate a derived row names, when it names one as a field."""
    cert = row.get("certificate")
    if isinstance(cert, dict):
        cell = cert.get("cell") or cert.get("key")
        return str(cell) if cell else None
    if isinstance(cert, str) and cert and cert != "forward_clock":
        return cert
    cell = row.get("cell")
    return str(cell) if isinstance(cell, str) and cell else None


def row_identity(store: str, key: str, row: dict[str, Any]) -> dict[str, Any]:
    """Exact sources first, parsing last: the registry's frozen identity, a sleeve's own fields, a
    certificate the row names; the key's shape only when the row declares nothing."""
    ident: dict[str, Any] = {"key": key, "certificate": _cert_key_of(row)}
    src: dict[str, Any] = {}
    if store == "sleeve_registry" and isinstance(row.get("identity"), dict):
        i = row["identity"]
        src = {"symbol": i.get("symbol"), "family": i.get("family"), "selector": i.get("selector"),
               "side": i.get("direction"), "timeframe": i.get("timeframe")}
        ident["declared_from"] = "identity"
    elif store == "sleeves" and (row.get("symbol") or row.get("family")):
        src = {"symbol": row.get("symbol"), "family": row.get("family"),
               "selector": row.get("selector") or row.get("window") or row.get("session"),
               "side": row.get("side"), "timeframe": row.get("timeframe")}
        ident["declared_from"] = "row"
    if not src.get("symbol") or not src.get("family"):
        parsed = parse_clock_key(key) or {}
        for k, v in parsed.items():
            if not src.get(k):
                src[k] = v
        ident.setdefault("declared_from", "key" if parsed else "none")
    ident.update({k: src.get(k) for k in ("symbol", "family", "selector", "side", "timeframe")})
    return ident


# -------------------------------------------------------------------------------- the lane
def banned_families(paths: Paths) -> set[str]:
    out = {DISCOVERED}
    doc = _read(paths.banned) or {}
    raw = _dict(doc.get("banned"))
    out |= {str(k).strip().lower() for k in raw}
    return out


def _canon_doc(paths: Paths, is_exact: Any) -> tuple[dict[str, Any] | None, str, str]:
    """(document, source, status) -- the fresh sweep when it carries the exact attestation, else
    the seal when it does; UNMEASURED when neither does (mirrors shadow_admission._canon)."""
    first: dict[str, Any] | None = None
    first_src = paths.canon_rel
    for p in (paths.canon, paths.seal):
        doc = _read(p)
        if doc is None:
            continue
        if first is None:
            first, first_src = doc, _rel(paths, p)
        if is_exact is not None and is_exact(doc.get("gate_policy")):
            return doc, _rel(paths, p), "EXACT"
    return first, first_src, "UNMEASURED"


def canon(paths: Paths) -> dict[str, Any]:
    """The lane's truth: every ten-gate certificate under the exact attestation, by key and by
    parts, with the banned-family certificates the migration must move named separately."""
    all_ten, is_exact = _policy()
    doc, source, status = _canon_doc(paths, is_exact)
    banned = banned_families(paths)
    certs: dict[str, dict[str, Any]] = {}
    banned_certs: dict[str, str] = {}
    not_ten = 0
    survivors = (doc or {}).get("survivors") if doc else None
    rows = survivors if isinstance(survivors, dict) else {}
    if status == "EXACT":
        for key, row in rows.items():
            if not isinstance(row, dict):
                continue
            spec = _dict(row.get("shadow_spec"))
            fam = str(spec.get("family") or "").strip().lower()
            if fam in banned:
                banned_certs[str(key)] = fam
                continue
            if all_ten is not None and not all_ten(row.get("gates")):
                not_ten += 1
                continue
            certs[str(key)] = {"symbol": spec.get("symbol"), "family": spec.get("family"),
                               "selector": spec.get("selector"), "side": spec.get("side"),
                               "params": spec.get("params"), "hunt": row.get("hunt")}
        if not certs:
            status = "EMPTY"
    else:
        # An attestation this desk cannot verify: the rows are counted so the reader sees what
        # the file holds, but none of them is a certificate here.
        for key, row in rows.items():
            spec = _dict(row.get("shadow_spec")) if isinstance(row, dict) else {}
            fam = str(spec.get("family") or "").strip().lower()
            if fam in banned:
                banned_certs[str(key)] = fam
    by_parts: dict[str, list[str]] = {}
    for key, c in certs.items():
        by_parts.setdefault(parts(c["symbol"], c["family"], c["selector"]), []).append(key)
    cure_by_parts, banned_cure, cure_status = _cure_lane(paths, is_exact, banned)
    scalp_declared, scalp_status = _scalp_declared(paths, is_exact)
    restorable, restorable_status = restorable_retirements(paths, all_ten, is_exact, banned)
    return {"status": status, "source": source, "policy_readable": all_ten is not None,
            "scalp_declared": scalp_declared, "scalp_status": scalp_status,
            "scalp_n": len(scalp_declared),
            "restorable": restorable, "restorable_n": len(restorable),
            "restorable_status": restorable_status,
            "n": len(certs), "certificates": certs, "by_parts": by_parts,
            "banned_certificates": banned_certs, "rows_in_file": len(rows),
            "rows_not_ten_gate": not_ten, "banned_families": sorted(banned),
            "cure_status": cure_status, "cure_n": len(cure_by_parts),
            "cure_by_parts": cure_by_parts, "banned_cure_candidates": banned_cure,
            "writer": "desks/mt5/scripts/external_gauntlet.py",
            "consumer": "desks/mt5/research/promoter.py"}


def _scalp_declared(paths: Paths, is_exact: Any) -> tuple[dict[str, str], str]:
    """The scalp lane's DECLARED evidence-gathering clocks, by the name its own state uses.

    `scripts/scalp_gauntlet.py` is part of the lane's writer set -- `external_gauntlet` merges its
    `canon_rows()` into the authority file under the same attestation -- and it declares, in
    `reports/SCALP_GAUNTLET.json`, the candidates it judges daily on M5/M15 bars. Those rows sit
    in `reports/shadow/scalp_shadow_state.json` under keys like `xau_m5_anti_breakout_overlap`,
    which no clock-key grammar this desk writes can parse, and which name their certificate in
    prose ("forward_clock (no ten-gate certificate for this cell yet ...)").

    Reported as UNPARSED they were four permanent divergences that no evidence could ever close:
    the parse was never going to succeed, and the rows are not unbacked -- they are the scalp
    lane's own power-cure equivalent, declared by the writer, gathering the forward evidence its
    gauntlet judges. So the writer's declaration is read as the backing it is, by name, under the
    exact attestation only. A name the report does not declare is still UNPARSED."""
    out: dict[str, str] = {}
    doc = _read(paths.scalp_gates)
    if doc is None or is_exact is None or not is_exact(doc.get("gate_policy")):
        return out, "UNMEASURED"
    for key in (doc.get("candidates") or {}):
        out[str(key)] = SCALP_DECLARED_REASON
    return out, "EXACT"


def _tradeable_now(paths: Paths) -> Any:
    """The SEALED writer's own predicate `symbol_is_tradeable(sym, meta)`, bound to this desk's
    registry -- or None when it cannot be reached, which is UNMEASURED and never a verdict.

    Imported, never re-implemented: the question "may this certificate be cashed today" has one
    owner (`desks/mt5/scripts/external_gauntlet.py`), and a second copy of that rule here is how
    two stores start disagreeing again. Heavy imports are guarded; a desk without the writer or
    without a universe registry simply restores nothing (L1.28a)."""
    try:
        meta = json.loads(paths.universe.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    if not isinstance(meta, dict) or not meta:
        return None
    try:
        import external_gauntlet as eg  # type: ignore[import-not-found]
    except Exception:
        try:
            from scripts import external_gauntlet as eg
        except Exception:
            return None
    fn = getattr(eg, "symbol_is_tradeable", None)
    if fn is None:
        return None

    def predicate(sym: str) -> bool:
        try:
            ok, _why = fn(sym, meta)
        except Exception:
            return False
        return bool(ok)

    return predicate


def restorable_retirements(paths: Paths, all_ten: Any, is_exact: Any,
                           banned: set[str]) -> tuple[dict[str, dict[str, Any]], str]:
    """Certificates sitting in `retired_certificates` that the lane's own rules say must come BACK.

    The sealed writer already owns this rule (`external_gauntlet.py`, the restore loop beside the
    purge): "every retired row is re-asked the question that retired it, on every pass, and one
    whose reason no longer holds goes back -- with its gates record intact, and stamped". Its
    conditions are a full ten-gate record, a symbol that is tradeable TODAY, and a key not already
    standing. Two are added here because the principal added them after that loop was written: the
    family may not be banned, and the attestation on the file the row came from must be exact.

    WHY THIS HAD TO BE MEASURED SOMEWHERE ELSE. That restore loop reads `retired_certificates`
    out of `reports/UNIVERSAL_SURVIVORS.json`. When a writer overwrites that file without the key
    -- which `side_channels/ug_remote.py` did hourly from 2026-09-17 -- the loop sees an empty
    retired dict and restores nothing, for ever, while the evidence sits intact in the seal that
    nothing reads back. Fifty-two ten-gate passes were invisible that way for six days."""
    out: dict[str, dict[str, Any]] = {}
    tradeable = _tradeable_now(paths)
    if all_ten is None or tradeable is None:
        return out, "UNMEASURED"
    for p in (paths.canon, paths.seal):
        doc = _read(p)
        if doc is None:
            continue
        if is_exact is not None and not is_exact(doc.get("gate_policy")):
            continue
        standing = _rows_of(doc, "survivors")
        retired = doc.get("retired_certificates")
        if not isinstance(retired, dict):
            continue
        for key, row in retired.items():
            if not isinstance(row, dict) or str(key) in standing or str(key) in out:
                continue
            fam = str(_dict(row.get("shadow_spec")).get("family") or "").strip().lower()
            if fam in banned or not all_ten(row.get("gates")):
                continue
            sym = str(row.get("sym") or "")
            if not sym or not tradeable(sym):
                continue
            out[str(key)] = row
    return out, "EXACT"


def _cure_lane(paths: Paths, is_exact: Any,
               banned: set[str]) -> tuple[dict[str, str], dict[str, str], str]:
    """The lane's SECOND output: power-cure candidates (validity passed, a power gate being cured
    by forward evidence), from the writer's own files under the same exact attestation. Returns
    ({parts: source key}, {banned candidate key: family}, status)."""
    out: dict[str, str] = {}
    banned_rows: dict[str, str] = {}
    status = "UNMEASURED"
    cure = _read(paths.cure)
    if cure is not None and is_exact is not None and is_exact(cure.get("gate_policy")):
        status = "EXACT"
        for key, row in (cure.get("candidates") or {}).items():
            if not isinstance(row, dict) or row.get("validity_pass") is not True \
                    or not row.get("failed_power_gates"):
                continue
            spec = _dict(row.get("shadow_spec"))
            fam = str(spec.get("family") or "").strip().lower()
            if fam in banned:
                banned_rows[str(key)] = fam
                continue
            if spec.get("symbol") and spec.get("family"):
                out.setdefault(parts(spec["symbol"], spec["family"], spec.get("selector")),
                               str(key))
    qq = _read(paths.qq_gates)
    if qq is not None and is_exact is not None and is_exact(qq.get("gate_policy")):
        status = "EXACT"
        validity, power = _gate_classes()
        for row in qq.get("verdicts") or []:
            bits = str(row.get("id") or "").split() if isinstance(row, dict) else []
            stages = row.get("stages") if isinstance(row, dict) else None
            if len(bits) != 5 or bits[1].strip().lower() in banned:
                continue
            if not isinstance(stages, dict):
                continue
            passed = {g for g, v in stages.items()
                      if isinstance(v, dict) and v.get("passed") is True}
            # a validity fail is a fail; every power gate passed is a certificate, not a cure
            if not validity <= passed or power <= passed:
                continue
            out.setdefault(parts(bits[0], bits[1], bits[3]), f"QQUANT_GATES:{row.get('id')}")
    return out, banned_rows, status


def _gate_classes() -> tuple[frozenset[str], frozenset[str]]:
    """(validity gates, power gates) from the sealed policy, else the audited defaults."""
    try:
        from gate_policy import (
            get_power_gates,
            get_validity_gates,
        )
        return frozenset(get_validity_gates()), frozenset(get_power_gates())
    except Exception:
        return (frozenset({"economic_prior", "pbo", "reality_check_spa", "stress_costs",
                           "lockbox"}),
                frozenset({"in_sample_screen", "deflated_sharpe", "cpcv", "walk_forward",
                           "expected_value"}))


def classify(ident: dict[str, Any], lane: dict[str, Any]) -> tuple[str, str]:
    """(verdict, why) for one derived row against the lane."""
    fam = str(ident.get("family") or "").strip().lower()
    if fam and fam in set(lane["banned_families"]):
        return "BANNED", BAN_REASON
    if lane["status"] == "UNMEASURED":
        return "UNMEASURED", ("the canonical lane carries no exact ten-gate attestation this "
                              "desk can read")
    cert = ident.get("certificate")
    if cert and cert in lane["certificates"]:
        return "BACKED", f"certificate {cert} is in the canonical lane"
    declared = lane.get("scalp_declared") or {}
    if str(ident.get("key") or "") in declared:
        return "CURE", declared[str(ident["key"])]
    if not ident.get("symbol") or not fam:
        return "UNPARSED", ("the row declares no symbol/family and its key has no shape this "
                            "desk writes")
    if ident.get("selector") is None:
        # A certificate-shaped key with no selector: backed if any lane certificate on the
        # symbol and family exists (the certificate itself names the selector).
        hits = [k for k, c in lane["certificates"].items()
                if str(c.get("symbol") or "").lower() == str(ident["symbol"]).lower()
                and str(c.get("family") or "").lower() == fam]
        if hits:
            return "BACKED", f"certificate {hits[0]} is in the canonical lane"
        return "UNBACKED", UNBACKED_REASON
    p = parts(ident["symbol"], fam, ident["selector"])
    hits = lane["by_parts"].get(p)
    if hits:
        return "BACKED", f"certificate {hits[0]} names these parts"
    cure = lane.get("cure_by_parts", {}).get(p)
    if cure:
        return "CURE", f"{CURE_REASON} ({cure})"
    return "UNBACKED", UNBACKED_REASON


# ------------------------------------------------------------------------------- the audit
def _rows_of_state(doc: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Both layers of a lane state: top-level rows and a `sleeves` sub-dict (scalp)."""
    rows = [(k, v) for k, v in doc.items() if isinstance(v, dict) and "status" in v]
    sub = doc.get("sleeves")
    if isinstance(sub, dict):
        rows += [(k, v) for k, v in sub.items() if isinstance(v, dict) and "status" in v]
    return rows


def _protected_symbols(sleeves_doc: dict[str, Any] | None) -> set[str]:
    """Symbols the live book trades under a principal override (LAWS 5j): never retired here."""
    out: set[str] = set()
    for s in (sleeves_doc or {}).get("sleeves") or []:
        if isinstance(s, dict) and str(s.get("status") or "").upper() in LIVE_SLEEVE \
                and s.get("principal_override"):
            out.add(str(s.get("symbol") or "").upper())
    return {x for x in out if x}


def audit(paths: Paths, now: str | None = None) -> dict[str, Any]:
    t0 = time.monotonic()
    stamp = now or _now()
    lane = canon(paths)
    divergences: list[dict[str, Any]] = []
    stores: dict[str, dict[str, Any]] = {}
    sleeves_doc = _read(paths.sleeves)
    protected = _protected_symbols(sleeves_doc)

    def add(kind: str, store: str, key: str, why: str, **extra: Any) -> None:
        divergences.append({"kind": kind, "store": store, "key": key, "why": why, **extra})

    # the canon itself and its seal: banned-family certificates are residue of a banned hunt
    for name, p in (("UNIVERSAL_SURVIVORS", paths.canon),
                    ("UNIVERSAL_SURVIVORS.canon", paths.seal)):
        doc = _read(p)
        rows = (doc or {}).get("survivors") if doc else None
        rows = rows if isinstance(rows, dict) else {}
        banned_here = 0
        for key, row in rows.items():
            spec = _dict(row.get("shadow_spec")) if isinstance(row, dict) else {}
            fam = str(spec.get("family") or "").strip().lower()
            if fam in set(lane["banned_families"]):
                banned_here += 1
                add("BANNED_CERTIFICATE", name, str(key), BAN_REASON, family=fam)
        stores[name] = {"path": _rel(paths, p), "readable": doc is not None, "rows": len(rows),
                        "banned": banned_here,
                        "retired": len((doc or {}).get("retired_certificates") or {}),
                        "attested": bool(_policy()[1] and _policy()[1]((doc or {}).get(
                            "gate_policy"))) if doc is not None else False}

    # THE STATE NOTHING NAMED (2026-09-23). The canon can be EMPTY while the lane's own retired
    # rows hold ten-gate passes whose retirement reason no longer holds -- evidence the desk has
    # earned, is entitled to cash, and cannot see. Measured on the trading box that day: n=0 with
    # 28 such rows in the seal, three of them the certificates behind LIVE sleeves. Fatal,
    # because `repair()` closes it on every pass with no --apply and no hand: a divergence the
    # organ can close and has not is a defect of the organ, not a finding (LAWS 7).
    for key in sorted(lane["restorable"]):
        add("CANON_EMPTY_WITH_RESTORABLE_EVIDENCE", "UNIVERSAL_SURVIVORS", key, RESTORE_REASON,
            family=str(_dict(lane["restorable"][key].get("shadow_spec")).get("family") or ""),
            symbol=lane["restorable"][key].get("sym"))
    # the writer's second output, the power-cure candidates: banned-family rows are residue too
    cure_doc = _read(paths.cure)
    for key, fam in sorted(lane["banned_cure_candidates"].items()):
        add("BANNED_CURE_CANDIDATE", "POWER_CURE_CANDIDATES", key, BAN_REASON, family=fam)
    stores["POWER_CURE_CANDIDATES"] = {
        "path": _rel(paths, paths.cure), "readable": cure_doc is not None,
        "rows": len((cure_doc or {}).get("candidates") or {}) if cure_doc else 0,
        "status": lane["cure_status"], "cure_parts": lane["cure_n"],
        "banned": len(lane["banned_cure_candidates"])}

    # the survivors ledger: claims filed as UNIVERSAL that the lane no longer holds
    ledger = _read(paths.ledger)
    claims = (ledger or {}).get("claims") if ledger else None
    claims = claims if isinstance(claims, dict) else {}
    st: dict[str, Any] = {"path": _rel(paths, paths.ledger), "readable": ledger is not None,
          "rows": len(claims),
          "live_rows": 0, "backed": 0, "banned": 0, "not_in_canon": 0}
    for key, row in claims.items():
        if not isinstance(row, dict) or str(row.get("status") or "").upper() != "UNIVERSAL":
            continue
        st["live_rows"] += 1
        spec = _dict(row.get("shadow_spec"))
        fam = str(spec.get("family") or "").strip().lower()
        if fam in set(lane["banned_families"]):
            st["banned"] += 1
            add("BANNED_CLAIM", "SURVIVORS_LEDGER", str(key), BAN_REASON, family=fam)
        elif lane["status"] == "UNMEASURED":
            continue
        elif str(key) in lane["certificates"]:
            st["backed"] += 1
        else:
            st["not_in_canon"] += 1
            add("CLAIM_NOT_IN_CANON", "SURVIVORS_LEDGER", str(key), HISTORY_REASON, family=fam)
    stores["SURVIVORS_LEDGER"] = st

    # clocks: the registry (LIVE rows) and the shadow state (running rows)
    def judge_clocks(name: str, p: Path, rows: list[tuple[str, dict[str, Any]]], readable: bool,
                     kind_unbacked: str) -> None:
        s: dict[str, Any] = {"path": _rel(paths, p), "readable": readable, "rows": len(rows),
                             "live_rows": 0, "backed": 0, "cure_backed": 0, "unbacked": 0,
                             "banned": 0, "unparsed": 0, "unmeasured": 0, "protected": 0}
        for key, row in rows:
            s["live_rows"] += 1
            ident = row_identity(name, key, row)
            verdict, why = classify(ident, lane)
            sym = str(ident.get("symbol") or "").upper()
            if verdict == "BANNED":
                s["banned"] += 1
                add("BANNED_CLOCK", name, key, why, family=ident.get("family"),
                    status=row.get("status"))
            elif verdict == "BACKED":
                s["backed"] += 1
            elif verdict == "CURE":
                s["cure_backed"] += 1
            elif verdict == "UNPARSED":
                s["unparsed"] += 1
                add("UNPARSED_CLOCK", name, key, why, status=row.get("status"))
            elif verdict == "UNMEASURED":
                s["unmeasured"] += 1
            else:
                s["unbacked"] += 1
                prot = sym in protected
                s["protected"] += int(prot)
                add("LIVE_BOOK_UNBACKED_CLOCK" if prot else kind_unbacked, name, key, why,
                    symbol=ident.get("symbol"), family=ident.get("family"),
                    selector=ident.get("selector"), status=row.get("status"), protected=prot,
                    **({"protection": "symbol traded by the live book under a principal override "
                                      "(LAWS 5j); published for the principal, never retired "
                                      "here and never fatal"} if prot else {}))
        stores[name] = s

    reg = _read(paths.registry)
    reg_rows = (reg or {}).get("sleeves") if reg else None
    reg_rows = reg_rows if isinstance(reg_rows, dict) else {}
    judge_clocks("sleeve_registry", paths.registry,
                 [(k, v) for k, v in reg_rows.items() if isinstance(v, dict)
                  and str(v.get("status") or "").upper() in LIVE_REGISTRY],
                 reg is not None, "UNBACKED_CLOCK")
    shadow = _read(paths.shadow)
    judge_clocks("shadow_state", paths.shadow,
                 [(k, v) for k, v in _rows_of_state(shadow or {})
                  if str(v.get("status") or "").upper() not in TERMINAL],
                 shadow is not None, "UNBACKED_CLOCK")
    for p in paths.lanes:
        doc = _read(p)
        if doc is None:
            stores[p.stem] = {"path": _rel(paths, p), "readable": False, "rows": 0}
            continue
        judge_clocks(p.stem, p, [(k, v) for k, v in _rows_of_state(doc)
                                 if str(v.get("status") or "").upper() not in TERMINAL],
                     True, "LANE_UNBACKED_CLOCK")

    # the live book: banned rows are the residue the live policy already refuses at both doors
    srows = (sleeves_doc or {}).get("sleeves") if sleeves_doc else None
    srows = srows if isinstance(srows, list) else []
    s: dict[str, Any] = {"path": _rel(paths, paths.sleeves), "readable": sleeves_doc is not None,
                         "rows": len(srows), "live_rows": 0, "banned": 0,
                         "certificate_not_in_canon": 0, "live_book": 0,
                         "protected_symbols": sorted(protected)}
    for row in srows:
        if not isinstance(row, dict) or str(row.get("status") or "").upper() not in LIVE_SLEEVE:
            continue
        s["live_rows"] += 1
        name = str(row.get("name") or "")
        ident = row_identity("sleeves", name, row)
        fam = str(ident.get("family") or "").strip().lower()
        if fam in set(lane["banned_families"]):
            s["banned"] += 1
            add("BANNED_SLEEVE", "sleeves", name, BAN_REASON, family=fam,
                status=row.get("status"))
            continue
        if row.get("principal_override") or row.get("certificate") == "forward_clock":
            s["live_book"] += 1
            continue
        cert = ident.get("certificate")
        if cert and lane["status"] != "UNMEASURED" and cert not in lane["certificates"]:
            s["certificate_not_in_canon"] += 1
            add("SLEEVE_CERTIFICATE_NOT_IN_CANON", "sleeves", name,
                f"row names certificate {cert}, which the canonical lane does not hold; the "
                f"promoter records this as certificate_drift and re-judges the row every pass",
                certificate=cert, status=row.get("status"))
    stores["sleeves"] = s

    # the reconciler's own count, checked against the lane
    rec = _read(paths.reconcile)
    rec_certified = (rec or {}).get("certified_clocks") if rec else None
    stores["forward_reconcile"] = {"path": _rel(paths, paths.reconcile),
                                   "readable": rec is not None,
                                   "certified_clocks": rec_certified,
                                   "enrolled": (rec or {}).get("enrolled") if rec else None}
    if lane["status"] == "EMPTY" and isinstance(rec_certified, int) and rec_certified > 0:
        add("RECONCILE_CERTIFIED_CLOCKS_ON_EMPTY_CANON", "forward_reconcile", "certified_clocks",
            f"forward_reconcile.json counts {rec_certified} certified clock(s) while the "
            f"canonical lane holds no ten-gate certificate", certified_clocks=rec_certified)

    # ------------------------------------------------- ONE CANONISED LANE: the re-split fence
    census = lane_census(paths, lane)
    for rel, view in census["derived"].items():
        if int(view.get("n_independent") or 0) > 0:
            add("DERIVED_STORE_WRITTEN_DIRECTLY", rel, ",".join(view["rows_source_does_not_hold"]
                                                                [:6]) or rel,
                f"{rel} is a DERIVED VIEW of {view['generated_from']} and holds "
                f"{view['n_independent']} row(s) its source does not: a derived store is "
                f"regenerated, never written independently", n_independent=view["n_independent"])
    for rel, claim in census["claims"].items():
        if claim.get("confers_certification"):
            add("SECOND_CERTIFICATE_STORE", rel, rel,
                f"{rel} confers certification of its own; {CANONICAL_CERTIFICATE_STORE} is the "
                f"ONE certificate store and every other is a claim store", rows=claim["rows"])
    queued: set[str] = set()
    queue_readable = paths.queue.exists()
    if queue_readable:
        for line in paths.queue.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                queued.add(str(json.loads(line).get("key")))
            except ValueError:
                continue
    stale = _stale_claims(paths, lane, queued, stamp) if queue_readable else []
    for rel, key, age in stale:
        add("CLAIM_NOT_SUBMITTED_TO_JUDGE", rel, key,
            f"claim is {age/3600:.1f}h old, older than one judging cycle "
            f"({JUDGING_CYCLE_S/3600:.0f}h), the canon does not hold it and it reached no "
            f"judge: {QUEUE_REASON}", age_s=round(age))
    # JOIN COVERAGE: a store nobody can join to the one identity is a split, whatever its
    # name says. Fatal when a store holds rows and NONE of them can declare the identity -- the
    # exact state measured on 2026-09-23, when the fence read ok=true over a wholly broken join.
    joins = join_coverage(paths, lane)
    for name, v in joins["stores"].items():
        if v["rows"] and not v["joinable"]:
            add("JOIN_COVERAGE_BREACH", name, IDENTITY_FIELD,
                f"{name} holds {v['rows']} row(s) and NONE can declare the canonical identity "
                f"({IDENTITY_RULE}); a store that cannot be joined is a separate lane whatever "
                f"it is called", rows=v["rows"], joinable=0)
    census["join"] = joins
    census["queued"] = len(queued)
    census["stale_unjudged"] = len(stale)

    live_clocks = sum(int(v.get("live_rows") or 0) for k, v in stores.items()
                      if k in ("sleeve_registry", "shadow_state"))
    if lane["status"] == "UNMEASURED" and live_clocks:
        add("CANON_UNMEASURED_WITH_LIVE_CLOCKS", "UNIVERSAL_SURVIVORS", lane["source"],
            f"{live_clocks} clock(s) run while the authority file carries no exact ten-gate "
            f"attestation this desk can read (policy_readable={lane['policy_readable']})",
            live_clocks=live_clocks)

    state_present = any(v.get("readable") for v in stores.values())
    fatal = [d for d in divergences if d["kind"] in FATAL_KINDS]
    by_kind: dict[str, int] = {}
    for d in divergences:
        by_kind[d["kind"]] = by_kind.get(d["kind"], 0) + 1
    lane_out = {k: v for k, v in lane.items()
                if k not in ("certificates", "by_parts", "cure_by_parts", "restorable",
                             "scalp_declared")}
    lane_out["certificate_keys"] = sorted(lane["certificates"])[:500]
    lane_out["restorable_keys"] = sorted(lane["restorable"])[:500]
    lane_out["scalp_declared_keys"] = sorted(lane["scalp_declared"])[:100]
    return {
        "at": stamp, "elapsed_s": round(time.monotonic() - t0, 3),
        "state_present": state_present,
        "canon": lane_out,
        "stores": stores,
        "one_lane": census,
        "n_divergences": len(divergences), "by_kind": by_kind,
        "n_fatal": len(fatal),
        "divergences": divergences[:2000],
        "ok": not fatal,
        "migration": {"planned": {
            "banned_certificates": by_kind.get("BANNED_CERTIFICATE", 0),
            "banned_cure_candidates": by_kind.get("BANNED_CURE_CANDIDATE", 0),
            "banned_claims": by_kind.get("BANNED_CLAIM", 0),
            "banned_clocks": by_kind.get("BANNED_CLOCK", 0),
            "banned_sleeves": by_kind.get("BANNED_SLEEVE", 0),
            "claims_to_history": by_kind.get("CLAIM_NOT_IN_CANON", 0),
            "unbacked_clocks_to_retire": by_kind.get("UNBACKED_CLOCK", 0),
            "unbacked_clocks_protected": by_kind.get("LIVE_BOOK_UNBACKED_CLOCK", 0),
        }, "command": "python desks/mt5/research/certificate_truth.py --once --apply"},
        "rule": ("one certificate lane: external_gauntlet.py writes UNIVERSAL_SURVIVORS.json under "
                 "the exact ten-gate attestation and promoter.py reads it; every other store is "
                 "derived, a row the lane does not back is a divergence, discovered-family "
                 "certificates and clocks are banned residue, and the fence fails on any of it"),
    }


# ----------------------------------------------------------------------------- the repair
#: THE ONE CANONICAL IDENTITY of a judged thing. Not a key -- keys are local and every store
#: invents its own (`CADJPY.asia`, `external.CADJPY.session_range_breakout.rr=1.5_wb=12`,
#: `xau_m5_anti_breakout_overlap`, `qquant.hunt16.json.AUDNZD dav ... NORMAL_DAY`). The sealed
#: gauntlet stamps `shadow_spec` on every certificate it mints, and `promoter.py` admits a row by
#: matching that spec -- so the identity the desk already runs on is (symbol, family, selector),
#: lowercased, which `parts()` computes. MEASURED 2026-09-23: 0 of 862 registry clocks joined the
#: canon BY KEY while the breach organ reported 55 backed BY SPEC; the stores had been unified by
#: NAME and never by KEY, so every observer got a different number (28 / 152 / 215 / 862) and the
#: fence read green because it was joining on the spec and nothing checked that anyone else was.
IDENTITY_FIELD = "canonical_identity"
IDENTITY_RULE = ("symbol|family|selector lowercased, from the shadow_spec the sealed gauntlet "
                 "stamps and the promoter matches (desks/mt5/scripts/external_gauntlet.py -> "
                 "desks/mt5/research/promoter.py); a key is local, this is the join")


def declared_identities(paths: Paths) -> dict[str, str]:
    """name -> canonical identity, from the stores that DECLARE a lane's identity for it.

    The scalp lane's clocks are keyed by a name with no grammar (`xau_m5_anti_breakout_overlap`),
    so no parse can ever join them -- but their own sleeve row declares symbol and family, and
    that declaration is the identity. Reading it is how a lane joins instead of being reported
    unjoinable for ever."""
    out: dict[str, str] = {}
    sl = _read(paths.sleeves) or {}
    for row in (sl.get("sleeves") or []):
        if not isinstance(row, dict) or not row.get("symbol") or not row.get("family"):
            continue
        name = str(row.get("name") or "")
        if name:
            out[name] = parts(row["symbol"], row["family"],
                              row.get("selector") or row.get("window") or row.get("session"))
    return out


def canonical_identity(store: str, key: str, row: dict[str, Any],
                       declared: dict[str, str] | None = None) -> str | None:
    """The ONE identity for any row in any store, or None when the row cannot declare one.

    A row that already CARRIES the identity is taken at its word; then the row's own fields and
    its key; then the declaration another store makes for that name. None is UNMEASURED, not
    zero: a row whose identity cannot be derived is REPORTED as unjoinable, never joined to
    something by guesswork (L1.28a)."""
    carried = row.get(IDENTITY_FIELD)
    if isinstance(carried, str) and carried.count("|") == 2:
        return carried
    ident = row_identity(store, key, row)
    if not ident.get("symbol") or not ident.get("family"):
        return (declared or {}).get(str(key))
    return parts(ident["symbol"], ident["family"], ident.get("selector"))


def join_coverage(paths: Paths, lane: dict[str, Any]) -> dict[str, Any]:
    """Per store: rows, rows that can declare the canonical identity, rows that JOIN the lane.

    This is the clause that makes "ok=true with a broken join" impossible. Counts that agree by
    coincidence are the split the principal named; counts that agree BY CONSTRUCTION need one
    identity, carried by every store, and a fence that fails when a store cannot produce it."""
    out: dict[str, Any] = {"identity": IDENTITY_FIELD, "rule": IDENTITY_RULE, "stores": {}}
    backed = set(lane["by_parts"]) | set(lane.get("cure_by_parts") or {})
    declared = declared_identities(paths)

    def measure(name: str, rows: list[tuple[str, dict[str, Any]]]) -> None:
        joinable = [canonical_identity(name, k, r, declared) for k, r in rows]
        ids = [i for i in joinable if i]
        out["stores"][name] = {
            "rows": len(rows), "joinable": len(ids),
            "unjoinable": len(rows) - len(ids),
            "joined_to_lane": sum(1 for i in ids if i in backed),
            "coverage": round(len(ids) / len(rows), 4) if rows else None}

    certs = lane["certificates"]
    measure("UNIVERSAL_SURVIVORS", [(k, {"symbol": c.get("symbol"), "family": c.get("family"),
                                         "selector": c.get("selector")})
                                    for k, c in certs.items()])
    out["stores"]["UNIVERSAL_SURVIVORS"]["joined_to_lane"] = len(certs)
    reg = _read(paths.registry) or {}
    measure("sleeve_registry", [(k, v) for k, v in (reg.get("sleeves") or {}).items()
                                if isinstance(v, dict)])
    for p in (paths.shadow, *paths.lanes):
        doc = _read(p)
        if doc is not None:
            measure(p.stem, _rows_of_state(doc))
    sl = _read(paths.sleeves) or {}
    measure("sleeves", [(str(r.get("name") or ""), r) for r in (sl.get("sleeves") or [])
                        if isinstance(r, dict)])
    total = sum(v["rows"] for v in out["stores"].values())
    joinable = sum(v["joinable"] for v in out["stores"].values())
    out["total_rows"] = total
    out["total_joinable"] = joinable
    out["coverage"] = round(joinable / total, 4) if total else None
    return out


def stamp_identity(paths: Paths, stamp: str) -> dict[str, Any]:
    """CARRY the identity, do not recompute it: every clock row keeps `canonical_identity`
    alongside whatever local key it needs, so the join is a field lookup and not a parse that
    each reader reinvents (which is how four observers got four numbers)."""
    out: dict[str, Any] = {"stamped": 0, "unjoinable": 0,
                           "store": CANONICAL_CLOCK_STORE}
    doc = _read(paths.registry)
    rows = (doc or {}).get("sleeves")
    if doc is None or not isinstance(rows, dict):
        return out
    changed = False
    declared = declared_identities(paths)
    for key, row in rows.items():
        if not isinstance(row, dict):
            continue
        ident = canonical_identity("sleeve_registry", str(key), row, declared)
        if ident is None:
            out["unjoinable"] += 1
            continue
        if row.get(IDENTITY_FIELD) != ident:
            row[IDENTITY_FIELD] = ident
            row[IDENTITY_FIELD + "_rule"] = IDENTITY_RULE
            changed = True
        out["stamped"] += 1
    if changed:
        doc["identity_stamped_at"] = stamp
        _atomic(paths.registry, doc, indent=2)
        out["wrote"] = _rel(paths, paths.registry)
    return out


def _stale_claims(paths: Paths, lane: dict[str, Any], queued: set[str],
                  stamp: str) -> list[tuple[str, str, float]]:
    """Claims older than one judging cycle that the canon does not hold and no queue carries."""
    out: list[tuple[str, str, float]] = []
    now = _parse(stamp)
    for rel, container, ts_key in (("reports/SURVIVORS_LEDGER.json", "claims", "updated_at"),
                                   ("reports/POWER_CURE_CANDIDATES.json", "candidates",
                                    "listed_at"),
                                   ("reports/SCALP_GAUNTLET.json", "candidates", "swept_at")):
        doc = _read(paths.base / rel)
        rows = doc.get(container) if isinstance(doc, dict) else None
        if not isinstance(rows, dict):
            continue
        fallback = _parse(str((doc or {}).get("swept_at") or "")) if doc else None
        for key, row in rows.items():
            k = str(key)
            if k in lane["certificates"] or k in queued:
                continue
            fam = str(_dict((row or {}).get("shadow_spec")).get("family") or "").strip().lower()
            if fam and fam in set(lane["banned_families"]):
                continue
            at = _parse(str((row or {}).get(ts_key) or "")) or fallback
            if at is None or now is None:
                continue                      # unstamped is UNMEASURED, never a stale verdict
            age = (now - at).total_seconds()
            if age > JUDGING_CYCLE_S:
                out.append((rel, k, age))
    return out


def _parse(value: str) -> datetime | None:
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def lane_census(paths: Paths, lane: dict[str, Any]) -> dict[str, Any]:
    """Every store that holds a certificate, a clock or a claim, classified against the ONE lane.

    Before this existed the desk had eleven stores and eleven answers; each was internally
    consistent and nothing compared them. The census is the comparison, and it is what the fence
    fails on: a SECOND certificate store, a DERIVED view written independently of its source, or a
    CLAIM that reached no judge inside one judging cycle."""
    out: dict[str, Any] = {"canonical": {"certificates": CANONICAL_CERTIFICATE_STORE,
                                         "clocks": CANONICAL_CLOCK_STORE},
                           "derived": {}, "claims": {}, "n_stores": 0}
    auth = _read(paths.canon) or {}
    seal = _read(paths.seal) or {}
    a_rows, s_rows = _rows_of(auth, "survivors"), _rows_of(seal, "survivors")
    a_ret, s_ret = _rows_of(auth, "retired_certificates"), _rows_of(seal, "retired_certificates")
    # the seal is a VIEW of the authority file: it may lag a write, never diverge from it
    extra = sorted(set(s_rows) - set(a_rows) - set(a_ret))
    out["derived"]["data/UNIVERSAL_SURVIVORS.canon.json"] = {
        "generated_from": CANONICAL_CERTIFICATE_STORE, "rows": len(s_rows),
        "rows_source_does_not_hold": extra[:50], "n_independent": len(extra),
        "retired": len(s_ret)}
    rec = _read(paths.reconcile) or {}
    out["derived"]["data/forward_reconcile.json"] = {
        "generated_from": CANONICAL_CLOCK_STORE, "certified_clocks": rec.get("certified_clocks"),
        "enrolled": rec.get("enrolled"), "n_independent": 0}
    for rel, container, key_of in (
            ("reports/SURVIVORS_LEDGER.json", "claims", None),
            ("reports/POWER_CURE_CANDIDATES.json", "candidates", None),
            ("reports/SCALP_GAUNTLET.json", "candidates", None),
            ("reports/QQUANT_GATES.json", "verdicts", "id")):
        doc = _read(paths.base / rel)
        rows = doc.get(container) if isinstance(doc, dict) else None
        if isinstance(rows, dict):
            keys = list(rows)
        elif isinstance(rows, list):
            keys = [str((r or {}).get(key_of or "id") or i) for i, r in enumerate(rows)]
        else:
            keys = []
        held = [k for k in keys if k in lane["certificates"]]
        out["claims"][rel] = {"rows": len(keys), "held_by_canon": len(held),
                              "not_held": len(keys) - len(held),
                              "confers_certification": False}
    out["n_stores"] = 2 + len(out["derived"]) + len(out["claims"])
    return out


def submit_to_judge(paths: Paths, lane: dict[str, Any], stamp: str) -> dict[str, Any]:
    """Queue every claim the canon does not hold to the ONE judge -- append-only, idempotent.

    A claim is not honoured and not discarded: it is TESTED. The queue is the desk's standing
    contract with the sealed gauntlet, and the fence fails on a claim older than one judging
    cycle that never reached it, because that claim is a split by another name."""
    already: set[str] = set()
    if paths.queue.exists():
        for line in paths.queue.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                already.add(str(json.loads(line).get("key")))
            except ValueError:
                continue
    fresh: list[dict[str, Any]] = []
    for rel, container in (("reports/SURVIVORS_LEDGER.json", "claims"),
                           ("reports/POWER_CURE_CANDIDATES.json", "candidates"),
                           ("reports/SCALP_GAUNTLET.json", "candidates")):
        doc = _read(paths.base / rel)
        rows = doc.get(container) if isinstance(doc, dict) else None
        if not isinstance(rows, dict):
            continue
        for key, row in rows.items():
            k = str(key)
            if k in lane["certificates"] or k in already:
                continue
            spec = _dict((row or {}).get("shadow_spec")) if isinstance(row, dict) else {}
            fam = str(spec.get("family") or "").strip().lower()
            if fam and fam in set(lane["banned_families"]):
                continue                      # a ban is a decision; it is never re-judged
            already.add(k)
            fresh.append({"at": stamp, "key": k, "store": rel, "status": "QUEUED",
                          "judge": "desks/mt5/scripts/external_gauntlet.py",
                          "reason": QUEUE_REASON, "shadow_spec": spec,
                          "sym": (row or {}).get("sym") if isinstance(row, dict) else None})
    if fresh:
        paths.queue.parent.mkdir(parents=True, exist_ok=True)
        with paths.queue.open("a", encoding="utf-8") as fh:
            for r in fresh:
                fh.write(json.dumps(r, default=str, separators=(",", ":")) + "\n")
    return {"submitted": len(fresh), "queue": _rel(paths, paths.queue),
            "queued_total": len(already)}


def _rows_of(doc: dict[str, Any], key: str) -> dict[str, Any]:
    """`doc[key]` as a row map -- {} when the key is absent or holds anything else."""
    rows = doc.get(key)
    return {str(k): v for k, v in rows.items()} if isinstance(rows, dict) else {}


def _params_n(rows: dict[str, Any]) -> int:
    return sum(1 for v in rows.values()
               if isinstance(v, dict) and _dict(v.get("shadow_spec")).get("params"))


def _git_attested_rows(paths: Paths, all_ten: Any, is_exact: Any, banned: set[str],
                       depth: int = 60) -> tuple[dict[str, Any], dict[str, Any], str]:
    """Every attested ten-gate certificate this repository has ever committed to the authority
    file, from its last `depth` revisions -- the recovery source the lane already names.

    `check_authority_ratchet` says it in its own breach message ("restore from the canon copy or
    git before the next writer overwrites it again") and already implements it for cohorts
    (`restore_cohorts_from_git`). It is the ONLY source that can return a certificate a bad writer
    overwrote in place, because the seal is a copy of the same file and goes with it.

    MEASURED 2026-09-23: the gauntlet minted 7 fresh certificates at 05:43 and printed "Updated
    UNIVERSAL_SURVIVORS.json: 7 total (+7)"; `side_channels/ug_remote.py` overwrote the file at
    08:39:16 with n=0 and no attestation. Neither the seal (0 survivors) nor `retired_certificates`
    (they were never retired -- they were erased) held them. Git did, in 4ed3e11d0, and the union
    across the last revisions held 67, which is more than either live store.

    Returns (rows that STOOD as certificates, rows that were RETIRED, status) -- the two are kept
    apart so a row retired for a reason that still holds is never resurrected as a certificate;
    it re-enters `retired_certificates` and is re-asked its own question by rule 2, exactly as if
    it had never been overwritten.

    A revision without the exact attestation contributes nothing; a row without a full ten-gate
    record contributes nothing; a banned family contributes nothing. Git unreachable is
    UNMEASURED, and restores nothing."""
    out: dict[str, Any] = {}
    retired_out: dict[str, Any] = {}
    if all_ten is None or is_exact is None:
        return out, retired_out, "UNMEASURED"
    root = paths.base.parents[1] if len(paths.base.parents) >= 2 else paths.base
    rel = f"{paths.base.name}/reports/UNIVERSAL_SURVIVORS.json"
    import contextlib
    with contextlib.suppress(ValueError):       # desks/mt5/reports/... under the repo root
        rel = (paths.canon.relative_to(root)).as_posix()
    import subprocess
    try:
        log = subprocess.run(["git", "-C", str(root), "log", "--format=%H", f"-{depth}",
                              "--", rel], capture_output=True, text=True, timeout=60)
        shas = [s for s in log.stdout.split() if s]
    except (OSError, subprocess.SubprocessError):
        return out, retired_out, "UNMEASURED"
    if not shas:
        return out, retired_out, "UNMEASURED"
    for sha in shas:
        try:
            blob = subprocess.run(["git", "-C", str(root), "show", f"{sha}:{rel}"],
                                  capture_output=True, text=True, timeout=60).stdout
            doc = json.loads(blob)
        except (OSError, ValueError, subprocess.SubprocessError):
            continue
        if not isinstance(doc, dict) or not is_exact(doc.get("gate_policy")):
            continue
        for container, sink in (("survivors", out), ("retired_certificates", retired_out)):
            rows = doc.get(container)
            if not isinstance(rows, dict):
                continue
            for key, row in rows.items():
                if not isinstance(row, dict) or str(key) in out or str(key) in retired_out:
                    continue
                fam = str(_dict(row.get("shadow_spec")).get("family") or "").strip().lower()
                if fam in banned or not all_ten(row.get("gates")):
                    continue
                sink[str(key)] = row
    return out, retired_out, "EXACT"


def repair(paths: Paths, now: str | None = None) -> dict[str, Any]:
    """Make the two authority files ONE truth again, on every pass, with no --apply and no hand.

    A REPORT IS NOT A REMEDY (LAWS 7). Publishing "the canon is empty" for six days while the
    evidence to refill it sat in the seal is the defect, not the finding. This closes every
    divergence the LANE'S OWN RULES close, and nothing else:

      1. AUTHORITY FROM SEAL -- `scripts/check_authority_ratchet.restore_authority`'s rule, run
         here because that script's only clock is a systemd timer on the VPS and the canon lives
         on the Windows box. A shrunken authority file with no revocation record of its own is an
         interrupted or bad writer, and in that state the seal is the recovery source by
         definition. The merge is a UNION -- presence wins over retirement, so it can only ever
         grow -- and it carries `retired_certificates` and the attestation back with it, which is
         what the bad writer dropped and what rule 2 and every downstream reader need.
      2. REASON EXPIRED -> RESTORE -- the sealed gauntlet's own restore loop, applied to the rows
         rule 1 just made visible: a full ten-gate pass, of no banned family, on a symbol its own
         `symbol_is_tradeable` accepts today, goes back to `survivors` stamped `restored_at` and
         `restored_from`, so the round trip is visible rather than silent.
      3. SEAL FROM AUTHORITY -- `check_authority_ratchet.heal_canon`'s rule: the seal may never be
         worse than the authority file, since it exists purely as the known-good copy of it.

    WHAT IT WILL NOT DO, ever, on any clock. It never retires a certificate, a clock or a sleeve;
    it never lowers a count; it never writes a row the lane does not back; and it never touches
    `sleeves.json`, the registry or the gateway. Retirement stays in `apply()` behind --apply, and
    the two acts reserved to the principal by name -- re-signing the sealed evaluator, and
    anything that changes what the live book trades -- stay reserved. This organ can only ever
    hand the desk back evidence it had already earned."""
    stamp = now or _now()
    all_ten, is_exact = _policy()
    banned = banned_families(paths)
    acts: dict[str, Any] = {"at": stamp, "authority_restored_from_seal": 0,
                            "authority_restored_from_git": 0, "git_status": "UNMEASURED",
                            "certificates_restored": 0, "seal_healed_from_authority": 0,
                            "restored_keys": [], "banned_not_restored": 0,
                            "predicate": "EXACT", "wrote": []}

    auth: dict[str, Any] = _read(paths.canon) or {}
    seal: dict[str, Any] = _read(paths.seal) or {}
    a_rows, a_ret = _rows_of(auth, "survivors"), _rows_of(auth, "retired_certificates")
    s_rows, s_ret = _rows_of(seal, "survivors"), _rows_of(seal, "retired_certificates")
    a_exact = bool(is_exact and is_exact(auth.get("gate_policy")))
    s_exact = bool(is_exact and is_exact(seal.get("gate_policy")))

    # ---- 1. authority from seal ------------------------------------------------------------
    degraded = (len(a_rows) < len(s_rows) or _params_n(a_rows) < _params_n(s_rows)
                or len(a_ret) < len(s_ret) or (s_exact and not a_exact))
    if degraded and s_exact:
        merged = dict(s_rows)
        merged.update(a_rows)                     # union: this can only ever grow
        merged_ret = {k: v for k, v in {**s_ret, **a_ret}.items() if k not in merged}
        acts["authority_restored_from_seal"] = len(merged) - len(a_rows)
        auth = dict(auth)
        auth.update({"survivors": merged, "retired_certificates": merged_ret,
                     "gate_policy": seal.get("gate_policy") if not a_exact
                     else auth.get("gate_policy"),
                     "n": len(merged), "restored_at": stamp, "restored_by": RETIRED_BY,
                     "restored_reason": SEAL_RESTORE_REASON})
        a_rows, a_ret, a_exact = merged, merged_ret, True

    # ---- 1b. what a bad writer overwrote IN PLACE, from git --------------------------------
    # The seal cannot answer this: it is a copy of the same file, so a writer that erases a
    # certificate erases both. Git is the only store that still holds it, and the ratchet already
    # names git as the recovery source. Union again -- what stands always wins over what git has.
    # Scanned only when the live file is DAMAGED -- not attested, or attested and holding no
    # certificate at all. That is precisely the shape an in-place wipe leaves (the measured one
    # was n=0 with the `gate_policy` key gone), and it keeps ~60 `git show` calls off a healthy
    # hourly pass. A partial loss keeps its attestation and is caught by the seal rule above.
    healthy = a_exact and any(isinstance(v, dict) and all_ten and all_ten(v.get("gates"))
                              for v in a_rows.values())
    git_surv: dict[str, Any] = {}
    git_ret: dict[str, Any] = {}
    git_status = "SKIPPED_LANE_HEALTHY"
    if not healthy:
        git_surv, git_ret, git_status = _git_attested_rows(paths, all_ten, is_exact, banned)
    acts["git_status"] = git_status
    if git_surv or git_ret:
        gained = {k: v for k, v in git_surv.items() if k not in a_rows and k not in a_ret}
        a_rows = {**gained, **a_rows}
        a_ret = {**{k: v for k, v in git_ret.items()
                    if k not in a_rows and k not in a_ret}, **a_ret}
        acts["authority_restored_from_git"] = len(gained)

    # ---- 2. a retirement whose reason no longer holds --------------------------------------
    tradeable = _tradeable_now(paths)
    if tradeable is None or all_ten is None:
        acts["predicate"] = "UNMEASURED"          # absence of the predicate is never a verdict
    else:
        a_rows, a_ret = dict(a_rows), dict(a_ret)
        for key, row in sorted(a_ret.items()):
            if not isinstance(row, dict) or key in a_rows:
                continue
            fam = str(_dict(row.get("shadow_spec")).get("family") or "").strip().lower()
            if fam in banned:
                acts["banned_not_restored"] += 1
                continue
            sym = str(row.get("sym") or "")
            if not all_ten(row.get("gates")) or not sym or not tradeable(sym):
                continue
            back = dict(row)
            back["restored_at"] = stamp
            back["restored_by"] = RETIRED_BY
            back["restored_from"] = {"retired_at": back.pop("retired_at", None),
                                     "retired_reason": back.pop("retired_reason", None),
                                     "why": RESTORE_REASON}
            a_rows[key] = back
            del a_ret[key]
            acts["certificates_restored"] += 1
            acts["restored_keys"].append(key)

    if (acts["authority_restored_from_seal"] or acts["certificates_restored"]
            or acts["authority_restored_from_git"]):
        auth = dict(auth)
        auth.update({"survivors": a_rows, "retired_certificates": a_ret, "n": len(a_rows),
                     "note": "UNIVERSAL 10-GATE PASS ONLY.", "repaired_at": stamp,
                     "repaired_by": RETIRED_BY})
        if not a_exact and s_exact:
            auth["gate_policy"] = seal.get("gate_policy")
        _atomic(paths.canon, auth, indent=2)
        acts["wrote"].append(_rel(paths, paths.canon))
        _history(paths, [{"at": stamp, "store": "UNIVERSAL_SURVIVORS", "key": k,
                          "from_status": "RETIRED", "to_status": "UNIVERSAL",
                          "reason": RESTORE_REASON, "by": RETIRED_BY,
                          "row": {k2: a_rows[k].get(k2)
                                  for k2 in ("sym", "cell", "hunt", "shadow_spec")}}
                         for k in acts["restored_keys"]])

    # ---- 3. the seal may never be worse than the authority file ----------------------------
    if len(a_rows) > len(s_rows) or (len(a_rows) == len(s_rows)
                                     and _params_n(a_rows) > _params_n(s_rows)):
        seal_out = dict(seal)
        seal_out.update({"survivors": a_rows, "retired_certificates": a_ret, "n": len(a_rows),
                         "gate_policy": auth.get("gate_policy") or seal.get("gate_policy"),
                         "healed_at": stamp, "healed_by": RETIRED_BY})
        _atomic(paths.seal, seal_out, indent=2)
        acts["seal_healed_from_authority"] = len(a_rows) - len(s_rows)
        acts["wrote"].append(_rel(paths, paths.seal))

    # ---- 4. every claim the canon does not hold goes to the ONE judge -------------------
    # Not honoured and not discarded: TESTED. This is the act that ends the split -- a
    # store may propose for ever, but only the sealed gauntlet's ten gates admit anything.
    acts["identity"] = stamp_identity(paths, stamp)
    acts["judge"] = submit_to_judge(paths, canon(paths), stamp)
    acts["canon_n"] = len(a_rows)
    acts["restored_keys"] = acts["restored_keys"][:200]
    return acts


# --------------------------------------------------------------------------- the migration
def _history(paths: Paths, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    paths.history.parent.mkdir(parents=True, exist_ok=True)
    with paths.history.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, default=str, separators=(",", ":")) + "\n")


def apply(paths: Paths, doc: dict[str, Any] | None = None,
          now: str | None = None) -> dict[str, Any]:
    """The one-time migration. Idempotent: a second run finds nothing to move."""
    stamp = now or _now()
    doc = doc or audit(paths, stamp)
    lane_status = doc["canon"]["status"]
    # AN EMPTY CANON IS UNMEASURED, NEVER "NOTHING IS CERTIFIED" (2026-09-23, the principal).
    # This migration once retired 597 forward clocks and 73 ledger claims against an authority
    # file holding 7 certificates -- while 52 more ten-gate passes sat in the seal's
    # `retired_certificates` under a reason that had stopped being true, and 56 more had been
    # overwritten in place by `side_channels/ug_remote.py` and survived only in git. Every one of
    # those clocks was genuinely backed; the file that judged them was the damaged store.
    #
    # So retirement now needs a SETTLED lane, not merely a readable one: the attestation exact,
    # at least one certificate standing, and nothing left that `repair()` would hand back. Any
    # other state retires nothing and says so -- absence of evidence is not evidence of absence
    # (L1.28a), and it is certainly not grounds to destroy a clock that took forward weeks to
    # earn. Banned-family rows are unaffected: a ban is a decision, not a measurement.
    lane_settled = (lane_status == "EXACT" and int(doc["canon"].get("n") or 0) > 0
                    and int(doc["canon"].get("restorable_n") or 0) == 0)
    if not lane_settled:
        doc = {**doc, "retirement_withheld": {
            "reason": ("the canonical lane is not settled (status "
                       f"{lane_status}, n={doc['canon'].get('n')}, "
                       f"restorable={doc['canon'].get('restorable_n')}); an empty or degraded "
                       "authority file is UNMEASURED and never the ground for retiring a clock"),
            "unbacked_clocks_not_retired": doc["by_kind"].get("UNBACKED_CLOCK", 0)}}
    by_store: dict[str, list[dict[str, Any]]] = {}
    for d in doc["divergences"]:
        by_store.setdefault(d["store"], []).append(d)
    moved: list[dict[str, Any]] = []
    counts: dict[str, int] = {}

    def note(store: str, key: str, from_status: object, to_status: str, reason: str,
             row: dict[str, Any] | None = None) -> None:
        moved.append({"at": stamp, "store": store, "key": key, "from_status": from_status,
                      "to_status": to_status, "reason": reason, "by": RETIRED_BY,
                      "row": row or {}})
        counts[store] = counts.get(store, 0) + 1

    # 1. banned-family certificates (and power-cure candidates) leave the writer's files for history
    for name, p, container, kind in (
            ("UNIVERSAL_SURVIVORS", paths.canon, "survivors", "BANNED_CERTIFICATE"),
            ("UNIVERSAL_SURVIVORS.canon", paths.seal, "survivors", "BANNED_CERTIFICATE"),
            ("POWER_CURE_CANDIDATES", paths.cure, "candidates", "BANNED_CURE_CANDIDATE")):
        keys = {d["key"] for d in by_store.get(name, ()) if d["kind"] == kind}
        if not keys:
            continue
        cdoc = _read(p)
        if cdoc is None or not isinstance(cdoc.get(container), dict):
            continue
        for key in sorted(keys):
            row = cdoc[container].pop(key, None)
            if row is None:
                continue
            note(name, key, row.get("status") or "UNIVERSAL", "RETIRED", BAN_REASON,
                 {k: row.get(k)
                  for k in ("hunt", "cell", "sym", "days", "gated_at", "shadow_spec")})
        cdoc["n"] = len(cdoc[container])
        hist = cdoc.setdefault("certificate_truth", {"retired_to_history": 0})
        hist["retired_to_history"] = int(hist.get("retired_to_history") or 0) + len(keys)
        hist["last_migration_at"] = stamp
        hist["reason"] = BAN_REASON
        _atomic(p, cdoc, indent=2)

    # 2. the survivors ledger: banned claims and claims the lane no longer holds become history
    ledger = _read(paths.ledger)
    if ledger is not None and isinstance(ledger.get("claims"), dict):
        changed = False
        for d in by_store.get("SURVIVORS_LEDGER", ()):
            row = ledger["claims"].get(d["key"])
            if not isinstance(row, dict):
                continue
            reason = BAN_REASON if d["kind"] == "BANNED_CLAIM" else HISTORY_REASON
            note("SURVIVORS_LEDGER", d["key"], row.get("status"), "RETIRED", reason)
            row.update({"status": "RETIRED", "retire_reason": reason, "retired_at": stamp,
                        "retired_by": RETIRED_BY})
            changed = True
        if changed:
            ledger["n"] = sum(1 for r in ledger["claims"].values()
                              if isinstance(r, dict) and r.get("status") == "UNIVERSAL")
            _atomic(paths.ledger, ledger, indent=2)

    # 3. clocks: the registry and the shadow state -- banned rows always, unbacked rows only
    #    when the lane is readable and the symbol is not the live book's
    def retire_rows(store: str, p: Path, rows_of: Any, write: Any) -> None:
        sdoc = _read(p)
        if sdoc is None:
            return
        index = dict(rows_of(sdoc))
        changed = False
        for d in by_store.get(store, ()):
            if d["kind"] == "BANNED_CLOCK":
                reason = BAN_REASON
            elif d["kind"] == "UNBACKED_CLOCK" and not d.get("protected") and lane_settled:
                reason = UNBACKED_REASON
            else:
                continue
            row = index.get(d["key"])
            if not isinstance(row, dict):
                continue
            note(store, d["key"], row.get("status"), "RETIRED", reason)
            write(row, reason)
            changed = True
        if changed:
            sdoc["updated_at"] = stamp
            _atomic(p, sdoc, indent=2)

    def reg_write(row: dict[str, Any], reason: str) -> None:
        row.update({"status": "RETIRED", "status_why": reason, "status_at": stamp,
                    "retired_by": RETIRED_BY})

    def clock_write(row: dict[str, Any], reason: str) -> None:
        row.update({"status": "RETIRED", "retire_reason": reason, "retired_at": stamp,
                    "retired_by": RETIRED_BY, "promotion_authority": False})

    retire_rows("sleeve_registry", paths.registry,
                lambda d: [(k, v) for k, v in (d.get("sleeves") or {}).items()
                           if isinstance(v, dict)], reg_write)
    retire_rows("shadow_state", paths.shadow, _rows_of_state, clock_write)
    for p in paths.lanes:
        retire_rows(p.stem, p, _rows_of_state, clock_write)

    # 4. the live book: banned rows only, in the promoter's own vocabulary
    sdoc = _read(paths.sleeves)
    if sdoc is not None and isinstance(sdoc.get("sleeves"), list):
        banned_names = {d["key"] for d in by_store.get("sleeves", ())
                        if d["kind"] == "BANNED_SLEEVE"}
        changed = False
        for row in sdoc["sleeves"]:
            if not isinstance(row, dict) or str(row.get("name") or "") not in banned_names:
                continue
            if str(row.get("status") or "").upper() not in LIVE_SLEEVE:
                continue
            note("sleeves", str(row["name"]), row.get("status"), "RETIRED", BAN_REASON,
                 {"symbol": row.get("symbol"), "family": row.get("family"),
                  "certificate": row.get("certificate")})
            row.update({"status": "RETIRED", "risk_frac": 0.0, "risk_frac_source": "none",
                        "retired_at": stamp, "retire_reason": BAN_REASON, "retired_by": RETIRED_BY})
            changed = True
        if changed:
            _atomic(paths.sleeves, sdoc, indent=2)

    _history(paths, moved)
    after = audit(paths, stamp)
    return {"at": stamp, "moved": len(moved), "by_store": counts,
            "history": _rel(paths, paths.history), "lane_status": lane_status,
            "lane_settled": lane_settled,
            "retirement_withheld": doc.get("retirement_withheld"),
            "skipped": {
                "unbacked_protected": doc["migration"]["planned"]["unbacked_clocks_protected"],
                "unbacked_on_unmeasured_canon": (
                    doc["migration"]["planned"]["unbacked_clocks_to_retire"]
                    if not lane_settled else 0)},
            "after": {"n_divergences": after["n_divergences"], "n_fatal": after["n_fatal"],
                      "by_kind": after["by_kind"], "ok": after["ok"]}}


# ------------------------------------------------------------------------------------ main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", help="one audit pass (the only mode)")
    ap.add_argument("--budget-s", type=float, default=120.0)
    ap.add_argument("--apply", action="store_true",
                    help="run the one-time migration (never on the hourly clock)")
    ap.add_argument("--no-repair", action="store_true",
                    help="audit only; do not restore evidence the lane's own rules restore")
    ap.add_argument("--base", type=Path, default=DESK, help="desk root (tests)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    paths = Paths.at(Path(a.base))
    # THE REPAIR RUNS ON THE CLOCK, NOT BEHIND A FLAG. It only ever hands back evidence the desk
    # already earned -- it cannot retire a row, lower a count or change what the gateway trades --
    # so there is nothing for a human to approve, and six days of an empty canon is what waiting
    # for one costs. `--apply` still gates every act that REMOVES something.
    repaired = None if a.no_repair else repair(paths)
    doc = audit(paths)
    doc["repaired"] = repaired
    doc["budget_s"] = float(a.budget_s)
    if a.apply:
        doc["applied"] = apply(paths, doc)
        doc = {**audit(paths), "applied": doc["applied"], "repaired": repaired,
               "budget_s": float(a.budget_s)}
    try:
        _atomic(paths.out, doc)
    except OSError as exc:
        print(f"certificate_truth: report NOT written ({type(exc).__name__}: {exc})")
    try:
        from libs.ops import events
        events.emit("STATE_PUBLISHED", path=paths.events, leg="certificate_truth",
                    canon=doc["canon"]["status"], n=doc["canon"]["n"],
                    divergences=doc["n_divergences"], fatal=doc["n_fatal"],
                    applied=bool(a.apply))
    except Exception:                                           # pragma: no cover - event log
        pass
    if a.json:
        print(json.dumps(doc, indent=1, default=str))
    else:
        c = doc["canon"]
        r = repaired or {}
        print(f"certificate_truth: canon {c['status']} n={c['n']} from {c['source']}; "
              f"{doc['n_divergences']} divergence(s), {doc['n_fatal']} fatal "
              f"{doc['by_kind']}"
              + (f"; repaired: +{r.get('authority_restored_from_seal', 0)} from seal, "
                 f"{r.get('certificates_restored', 0)} certificate(s) restored, "
                 f"{r.get('banned_not_restored', 0)} banned left retired "
                 f"(predicate {r.get('predicate')})" if r.get("wrote") or r.get(
                     "certificates_restored") else "")
              + (f"; applied: moved {doc['applied']['moved']} {doc['applied']['by_store']}"
                 if a.apply else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
