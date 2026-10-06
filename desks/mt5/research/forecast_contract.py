#!/usr/bin/env python3
"""P4 -- THE UNIVERSAL FORECAST CONTRACT. Models publish beliefs. Models own no positions.

WHY THE SEPARATION IS THE WHOLE POINT. A model that both predicts and sizes cannot be scored,
because its P&L confounds two skills: whether it saw the future, and whether it bet well on what
it saw. Split them and each becomes measurable on its own terms -- the forecast against the
outcome, the sizing against the forecast. Merge them and a good forecaster with bad sizing is
indistinguishable from the reverse, and the desk cannot tell which half to fix.

It also removes the only route by which a research model can move money. A `Belief` carries no
lot size, no direction to act on, no authority. It is a claim about a random variable with a
horizon and a stated uncertainty. The allocator reads beliefs and decides capital; that is A6's
job and it is the only organ that has it.

THE CONTRACT, and every field exists because its absence made a forecast unscoreable:

    model_id     WHO said it. Scoring is per model or it is not scoring.
    at           WHEN it was said, which must be before the outcome is knowable. A belief with
                 no timestamp cannot be checked for lookahead and is therefore worthless as
                 evidence, however good its number.
    subject      WHAT it is about: instrument, horizon, and the quantity being predicted.
    kind         WHICH proper scoring rule applies. A probability is scored by Brier, a magnitude
                 by MAE, a distribution by CRPS -- and using the wrong one silently rewards the
                 wrong behaviour, which is worse than not scoring at all.
    value        THE BELIEF: p in [0,1] for PROBABILITY, a real for MAGNITUDE, quantiles for
                 DISTRIBUTION.
    horizon_s    HOW FAR ahead. Two models are comparable only at equal horizon; a one-hour
                 forecast beating a one-week forecast is not a result.
    confidence   The model's own stated uncertainty, which is scored too. A model that is always
                 certain is not confident, it is uncalibrated, and this is what catches it.
    features     The information the belief was formed on, for P82's provenance graph and for
                 the leakage check: a feature stamped later than `at` is lookahead.

THE TRAINING-CUTOFF AND FEATURE-AVAILABILITY CLAUSES (2026-10-06). `features` named the inputs but
nothing said WHEN each became knowable, and nothing said what data the model was FITTED on -- so
the two commonest leaks a forecast record can carry (a feature published after the forecast, and
a model trained on the window it is being scored over) were both unprovable. Five more fields:

    family                 Which registered model family (`model_roles.FAMILIES`) published it,
                           and so which decision roles it may speak in.
    role                   The decision role this belief speaks to. A role outside the family's
                           declared set is REFUSED: a volatility model may not publish a mean.
    training_cutoff        The latest timestamp of any data the model was fitted on. Must be
                           STRICTLY before `at` and before the outcome window opens.
    outcome_start          When the outcome window opens; defaults to `at`. A window opening
                           before the belief is a forecast of something already partly seen.
    feature_available_at   (feature, ISO time it became knowable) for EVERY declared feature.
                           A stamp after `at` is lookahead and REFUSED. A declared feature with
                           no stamp is REFUSED -- an unstamped input cannot be checked, and an
                           uncheckable input is assumed to leak (L1.28a: absence is never a pass).

VERIFIED, ACCEPTED, REFUSED ARE THREE THINGS. A belief that names a registered family must carry
the whole contract or it is REFUSED. A belief with no family -- every row published before these
fields existed, and any model not yet registered -- is still scoreable and still ACCEPTED, but it
is recorded as `verification: UNVERIFIED` with the reason, and `contract_report` counts it
separately. Old rows are never upgraded to VERIFIED by being read: a row earns VERIFIED only by
carrying the stamps that prove it.

WHAT THIS MODULE REFUSES. A belief that cannot be scored is rejected at publication rather than
stored and quietly skipped later. `REFUSED` rows are kept with their reason, because a model
whose beliefs are systematically malformed is a defect to fix, and deleting the evidence of it
is how that defect survives. Absence is never a pass (L1.28a).
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any, Literal


def _load_roles() -> ModuleType:
    """The sibling `model_roles`, whichever way this file was loaded.

    Loaded BY PATH from beside this file, never by a bare `import`, because this module is itself
    loaded three ways (as a script by hourly_cycle, by path in tests, as `research.*`) and only the
    path is the same in all three. Registered under its own name so every later importer shares
    one registry instead of each holding a private copy of the roles.
    """
    mod = sys.modules.get("model_roles")
    if mod is not None:
        return mod
    spec = importlib.util.spec_from_file_location(
        "model_roles", Path(__file__).resolve().parent / "model_roles.py")
    if spec is None or spec.loader is None:
        raise ImportError("model_roles.py is missing beside forecast_contract.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["model_roles"] = mod
    spec.loader.exec_module(mod)
    return mod


_roles = _load_roles()

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
REGISTER = BASE / "data" / "forecast_register.jsonl"
REPORT = BASE / "reports" / "FORECAST_CONTRACT.json"

Kind = Literal["PROBABILITY", "MAGNITUDE", "DISTRIBUTION"]

#: Scoring rule per belief kind. The mapping is the contract's teeth: a kind with no rule here
#: cannot be published, because publishing it would create a belief nothing can ever grade.
RULES: dict[str, str] = {
    "PROBABILITY": "brier",
    "MAGNITUDE": "absolute_error",
    "DISTRIBUTION": "crps",
}

#: Horizons the desk compares across. A belief may name any horizon, but the league (P79) only
#: ever ranks models WITHIN one of these buckets -- comparing a 5-minute forecaster against a
#: daily one on one table is the single easiest way to manufacture a fake champion.
HORIZON_BUCKETS: tuple[tuple[str, int, int], ...] = (
    ("intraday", 0, 4 * 3600),
    ("session", 4 * 3600, 36 * 3600),
    ("swing", 36 * 3600, 10 * 86400),
    ("position", 10 * 86400, 400 * 86400),
)


def bucket_of(horizon_s: float) -> str:
    for name, lo, hi in HORIZON_BUCKETS:
        if lo <= horizon_s < hi:
            return name
    return "unbucketed"


@dataclass(frozen=True)
class Belief:
    """One scoreable claim about the future. Carries no position and no authority."""

    model_id: str
    subject: str
    kind: str
    value: Any
    horizon_s: float
    at: str
    confidence: float | None = None
    features: tuple[str, ...] = ()
    note: str = ""
    # -- the 2026-10-06 clauses; all defaulted so every existing caller and row still reads.
    family: str = ""
    role: str = ""
    training_cutoff: str | None = None
    outcome_start: str | None = None
    feature_available_at: tuple[tuple[str, str], ...] = ()

    def bucket(self) -> str:
        return bucket_of(self.horizon_s)


def _finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def defects(b: Belief) -> list[str]:
    """Every reason this belief cannot be scored. Empty list means publishable.

    Returns ALL defects rather than the first, because a model publishing malformed beliefs
    usually has several and fixing them one round-trip at a time wastes the operator's day.
    """
    out: list[str] = []
    if not b.model_id or not str(b.model_id).strip():
        out.append("no model_id -- a belief nobody owns cannot be scored to anyone")
    if not b.subject or not str(b.subject).strip():
        out.append("no subject -- nothing states what this is a belief ABOUT")
    if b.kind not in RULES:
        out.append(f"kind {b.kind!r} has no scoring rule; known kinds are {sorted(RULES)}")
    if not _finite(b.horizon_s) or b.horizon_s <= 0:
        out.append("horizon_s must be a positive number of seconds -- two models are comparable "
                   "only at equal horizon")
    try:
        datetime.fromisoformat(str(b.at))
    except (TypeError, ValueError):
        out.append("`at` is not an ISO timestamp -- without it the belief cannot be checked for "
                   "lookahead, which makes it worthless as evidence whatever its number")
    if b.kind == "PROBABILITY":
        if not _finite(b.value) or not 0.0 <= float(b.value) <= 1.0:
            out.append("a PROBABILITY belief must carry a value in [0, 1]")
    elif b.kind == "MAGNITUDE":
        if not _finite(b.value):
            out.append("a MAGNITUDE belief must carry a finite real value")
    elif b.kind == "DISTRIBUTION":
        ok = isinstance(b.value, dict) and b.value and all(
            _finite(k if _finite(k) else float(k)) and _finite(v) for k, v in b.value.items())
        if not ok:
            out.append("a DISTRIBUTION belief must carry {quantile: value} with numeric keys")
    if b.confidence is not None and (not _finite(b.confidence)
                                    or not 0.0 <= float(b.confidence) <= 1.0):
        out.append("confidence, when given, is a probability in [0, 1] and is scored too: a "
                   "model that is always certain is uncalibrated, not confident")
    out.extend(_provenance_defects(b))
    return out


def _ts(x: Any) -> datetime | None:
    """ISO -> aware datetime. Naive stamps are read as UTC, the desk's clock for every ledger;
    comparing a naive stamp to an aware one would otherwise raise instead of judging."""
    try:
        d = datetime.fromisoformat(str(x).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def _stamps(b: Belief) -> tuple[dict[str, str], list[str]]:
    out: dict[str, str] = {}
    bad: list[str] = []
    for pair in b.feature_available_at or ():
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            bad.append(f"feature_available_at entry {pair!r} is not a (feature, time) pair")
            continue
        out[str(pair[0])] = str(pair[1])
    return out, bad


def _provenance_defects(b: Belief) -> list[str]:
    """Family/role, training cutoff and feature availability. Empty list = nothing refused here.

    WHAT IS REFUSED vs WHAT IS MERELY UNVERIFIED. Anything stated and WRONG is refused: a cutoff
    at or after `at`, a feature available after `at`, a role the family does not hold. Anything
    ABSENT is refused only when the belief names a registered family, because naming a family is
    opting into the full contract; a family-less belief is reported UNVERIFIED by `verification`.
    Declared features without stamps are refused WHATEVER the family: an unstamped input cannot
    be checked, and that is true of a legacy model too.
    """
    out: list[str] = []
    at = _ts(b.at)
    fam = _roles.spec(b.family) if b.family else None
    if b.family and fam is None:
        out.append(f"family {b.family!r} is not registered in model_roles.FAMILIES -- an "
                   "unregistered family has no declared role and may change nothing")
    if b.role:
        if b.role not in {str(r) for r in _roles.Role}:
            out.append(f"role {b.role!r} is not a decision role; known roles are "
                       f"{sorted(str(r) for r in _roles.Role)}")
        elif fam is not None and not fam.may(b.role):
            out.append(f"role violation: {b.family} may speak in "
                       f"{sorted(str(r) for r in fam.roles)}, not {b.role}")
    elif fam is not None:
        out.append("a registered family must name the decision role its belief speaks to")
    # -- the outcome window, then the training cutoff against it
    window = at
    if b.outcome_start is not None:
        o_start = _ts(b.outcome_start)
        if o_start is None:
            out.append("outcome_start is not an ISO timestamp")
        elif at is not None and o_start < at:
            out.append("outcome window opens before the belief (outcome_start < at) -- part of "
                       "the outcome was knowable when it was formed")
        else:
            window = o_start
    if b.training_cutoff is not None:
        tc = _ts(b.training_cutoff)
        if tc is None:
            out.append("training_cutoff is not an ISO timestamp -- a model whose fitting window "
                       "cannot be read cannot be shown not to have trained on its own test")
        else:
            if at is not None and not tc < at:
                out.append(f"training_cutoff {b.training_cutoff} is not strictly before `at` "
                           f"{b.at} -- the model was fitted on data it claims to forecast")
            if window is not None and not tc < window:
                out.append(f"training_cutoff {b.training_cutoff} is not before the outcome "
                           "window -- the model trained on the window it is scored over")
    elif fam is not None:
        out.append("no training_cutoff -- a registered family must state the end of the data "
                   "it was fitted on, or its record cannot be shown free of training leakage")
    # -- feature availability
    stamps, bad = _stamps(b)
    out.extend(bad)
    feats = [str(f) for f in b.features or ()]
    if fam is not None and not fam.uses_features and feats:
        out.append(f"{b.family} is declared to use no features but this belief names {feats}")
    if fam is not None and fam.uses_features and not feats:
        out.append(f"{b.family} is a feature model but declares no features -- an empty list "
                   "cannot be checked for lookahead")
    for f in feats:
        if f not in stamps:
            out.append(f"feature {f!r} has no available_at stamp -- an unstamped input cannot "
                       "be checked for lookahead and is assumed to leak")
            continue
        when = _ts(stamps[f])
        if when is None:
            out.append(f"feature {f!r} available_at {stamps[f]!r} is not an ISO timestamp")
        elif at is not None and when > at:
            out.append(f"lookahead: feature {f!r} became available {stamps[f]}, after the "
                       f"belief at {b.at}")
    for f in sorted(set(stamps) - set(feats)):
        out.append(f"availability stamped for undeclared feature {f!r} -- the features list is "
                   "incomplete, so the lookahead check would run on the wrong set")
    return out


def verification(b: Belief) -> tuple[str, list[str]]:
    """REFUSED / UNVERIFIED / VERIFIED, with every reason. Only VERIFIED is a clean bill.

    VERIFIED needs: no defects, a registered family and role, and a training cutoff (feature
    stamps are already enforced by `defects`). Anything less that is still scoreable is
    UNVERIFIED -- readable and usable as evidence, never reported as checked.
    """
    bad = defects(b)
    if bad:
        return "REFUSED", bad
    missing: list[str] = []
    if not b.family:
        missing.append("no model family -- decision role and training cutoff were not checked")
    if b.training_cutoff is None:
        missing.append("no training_cutoff")
    return ("UNVERIFIED", missing) if missing else ("VERIFIED", [])


def verify_row(row: dict[str, Any]) -> tuple[str, list[str]]:
    """Re-judge a register row, old or new, under the CURRENT contract.

    A row written before the provenance fields existed is rebuilt with their defaults and comes
    back UNVERIFIED (or REFUSED, if it was malformed) -- never VERIFIED by omission.
    """
    kw = {k: row[k] for k in Belief.__dataclass_fields__ if k in row}
    kw["features"] = tuple(kw.get("features") or ())
    kw["feature_available_at"] = tuple(tuple(p) if isinstance(p, (list, tuple)) else p
                                       for p in kw.get("feature_available_at") or ())
    try:
        b = Belief(**kw)
    except TypeError as exc:
        return "REFUSED", [f"row cannot be read as a Belief: {exc}"]
    return verification(b)


@dataclass
class Publication:
    accepted: list[dict[str, Any]] = field(default_factory=list)
    refused: list[dict[str, Any]] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return {"accepted": len(self.accepted), "refused": len(self.refused)}


def publish(beliefs: list[Belief], register: Path | None = None) -> Publication:
    """Validate and append. A belief that cannot be scored never enters the register.

    REFUSALS ARE RECORDED, NOT DROPPED. A model whose beliefs are systematically malformed is a
    defect to fix; silently skipping them at scoring time would hide it behind a plausible-looking
    sample size, which is the same shape as every other silent-success bug on this desk.
    """
    reg = register if register is not None else REGISTER
    pub = Publication()
    now = datetime.now(UTC).isoformat(timespec="seconds")
    for b in beliefs:
        status, why = verification(b)
        bad = why if status == "REFUSED" else []
        row = asdict(b) | {"rule": RULES.get(b.kind), "bucket": b.bucket(),
                           "published_at": now, "verification": status,
                           "unverified_because": why if status == "UNVERIFIED" else []}
        if bad:
            pub.refused.append(row | {"status": "REFUSED", "defects": bad})
        else:
            pub.accepted.append(row | {"status": "ACCEPTED"})
    reg.parent.mkdir(parents=True, exist_ok=True)
    with reg.open("a", encoding="utf-8") as fh:
        for row in pub.accepted + pub.refused:
            fh.write(json.dumps(row, default=str) + "\n")
    return pub


def read_register(register: Path | None = None, limit: int | None = None) -> list[dict[str, Any]]:
    reg = register if register is not None else REGISTER
    rows: list[dict[str, Any]] = []
    try:
        with reg.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        return []
    return rows[-limit:] if limit else rows


def leakage(row: dict[str, Any], feature_stamps: dict[str, str]) -> str | None:
    """Was this belief formed on information that did not exist yet?

    THE ONE CHECK THAT CANNOT BE DONE LATER. Once a feature file is overwritten its old timestamp
    is gone, so lookahead becomes unprovable in either direction -- and an unprovable forecast
    record is exactly as useful as no record. Run against point-in-time stamps at publication.
    """
    at = _ts(row.get("at"))
    if at is None:
        return "belief has no readable timestamp"
    # The row's OWN stamps are read too; the caller's point-in-time stamps outrank them.
    own = {str(p[0]): str(p[1]) for p in row.get("feature_available_at") or ()
           if isinstance(p, (list, tuple)) and len(p) == 2}
    stamps_all = own | dict(feature_stamps)
    late = []
    for f in row.get("features") or ():
        stamp = stamps_all.get(f)
        if not stamp:
            continue
        when = _ts(stamp)
        if when is None:
            continue
        if when > at:
            late.append(f"{f} stamped {stamp}")
    return ("lookahead: formed on information newer than the belief -- " + "; ".join(late)) \
        if late else None


def contract_report(register: Path | None = None) -> dict[str, Any]:
    """What the register says about every model publishing into it."""
    rows = read_register(register)
    models: dict[str, dict[str, Any]] = {}
    for r in rows:
        m = models.setdefault(str(r.get("model_id") or "unattributed"), {
            "accepted": 0, "refused": 0, "buckets": {}, "kinds": {}, "defects": {},
            "verification": {"VERIFIED": 0, "UNVERIFIED": 0, "REFUSED": 0}})
        # RE-JUDGED ON READ, not trusted from the row: a row stored before the provenance
        # clauses carries no `verification` field, and a stored "VERIFIED" from an older rule
        # set is only as good as that rule set. A stored REFUSED stays refused.
        v = "REFUSED" if r.get("status") == "REFUSED" else verify_row(r)[0]
        m["verification"][v] += 1
        if r.get("status") == "ACCEPTED":
            m["accepted"] += 1
            m["buckets"][r.get("bucket")] = m["buckets"].get(r.get("bucket"), 0) + 1
            m["kinds"][r.get("kind")] = m["kinds"].get(r.get("kind"), 0) + 1
        else:
            m["refused"] += 1
            for d in r.get("defects") or ():
                key = d.split("--")[0].strip()[:60]
                m["defects"][key] = m["defects"].get(key, 0) + 1
    for m in models.values():
        total = m["accepted"] + m["refused"]
        m["refusal_rate"] = round(m["refused"] / total, 4) if total else None
    doc = {
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "beliefs": len(rows),
        "models": models,
        "rules": RULES,
        "verification": {k: sum(m["verification"][k] for m in models.values())
                         for k in ("VERIFIED", "UNVERIFIED", "REFUSED")},
        "model_roles": _roles.roles_report(),
        "horizon_buckets": {n: [lo, hi] for n, lo, hi in HORIZON_BUCKETS},
        "contract": ("A model publishes BELIEFS and owns no position. A belief carries no lot "
                     "size and no authority; the capital allocator reads beliefs and decides "
                     "money. Splitting them is what makes either half measurable: merged, a "
                     "good forecaster who sizes badly is indistinguishable from the reverse."),
    }
    return doc


def main(argv: list[str] | None = None) -> int:
    doc = contract_report()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    print(f"forecast contract: {doc['beliefs']} belief(s) from {len(doc['models'])} model(s)")
    worst = sorted(doc["models"].items(),
                   key=lambda kv: kv[1]["refusal_rate"] or 0, reverse=True)[:5]
    for name, m in worst:
        if m["refused"]:
            print(f"   {name:28} refused {m['refused']}/{m['accepted'] + m['refused']} "
                  f"({m['refusal_rate']:.0%})")
            for d, n in sorted(m["defects"].items(), key=lambda kv: -kv[1])[:2]:
                print(f"      {n:4}x {d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
