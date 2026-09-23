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

WHAT THIS MODULE REFUSES. A belief that cannot be scored is rejected at publication rather than
stored and quietly skipped later. `REFUSED` rows are kept with their reason, because a model
whose beliefs are systematically malformed is a defect to fix, and deleting the evidence of it
is how that defect survives. Absence is never a pass (L1.28a).
"""
from __future__ import annotations

import json
import math
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

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
    return out


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
        bad = defects(b)
        row = asdict(b) | {"rule": RULES.get(b.kind), "bucket": b.bucket(),
                           "published_at": now}
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
    try:
        at = datetime.fromisoformat(str(row.get("at")))
    except (TypeError, ValueError):
        return "belief has no readable timestamp"
    late = []
    for f in row.get("features") or ():
        stamp = feature_stamps.get(f)
        if not stamp:
            continue
        try:
            when = datetime.fromisoformat(str(stamp))
        except (TypeError, ValueError):
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
            "accepted": 0, "refused": 0, "buckets": {}, "kinds": {}, "defects": {}})
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
