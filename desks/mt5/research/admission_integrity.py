"""THE RESEARCH-INTEGRITY DOOR: a new certificate reaches a forward clock only when the certifier
is known to discriminate and the certificate has been independently replicated.

Principal's audit, 2026-09-30: the research organs must DECIDE something, not only report.
Two organs already measured the two facts this door needs, and nothing read either of them:

    PLACEBO AUDIT (`research/placebo_audit.py`, hourly leg `placebo_audit`)
        plants eight known defects beside a known-good edge and runs all of them through the real
        certifier. `status == "GATE_BLIND"` means the certifier ADMITTED a planted trap -- it has
        gone blind to a whole defect class, so any certificate it mints now may carry exactly that
        defect. That is a PROGRAM-LEVEL alarm: it does not say which certificate is bad, it says
        the judge's word is currently worth nothing for that class.

    REPLICATION (`research/replication_civilization.py`, hourly leg `replication_civilization`)
        rebuilds a certificate from its WRITTEN specification and the raw bars in a second
        implementation and compares. REPLICATED is the only verdict that says the implementation
        does what the specification says. MISMATCH is quarantined by name; UNMEASURED (no written
        rule for the family, no bars) and a certificate the lane has not reached yet are both
        UNREPLICATED -- absence never resolves to a clean verdict (L1.28a).

WHERE THE DOOR STANDS, AND WHY THERE. Promotion to LIVE is decided in `research/promoter.py`
(sealed), and it promotes only a row whose FORWARD CLOCK has matured. So the unsealed hand-off
that controls both "enters the forward clock" and "can ever enter promotion" is the moment a clock
is CREATED:

    shadow_forward.certified_sleeves()   H1 / external / every canon certificate
    qquant_shadow.main()                 `qquant.*` certificates, keyed by certificate id

Both ask `IntegrityGate.hold(...)` before creating a clock that does not exist yet.

WHAT THE DOOR NEVER DOES.
  * It never touches a clock that already exists. A running clock keeps accruing evidence and
    keeps its promotion path; the promoter's own gates judge it as before. Only NEW enrolment waits.
  * It is not a quota. There is no count, no slot, no ranking -- the fence in
    `scripts/check_forward_enrolment.py` forbids all three and still passes. Every certificate
    that clears both facts enrols on the same pass, however many there are.
  * It deploys no capital and removes none. Forward clocks gather evidence; the door decides
    which evidence the desk is willing to START gathering on the certifier's word.

RELEASE IS AUTOMATIC. A fresh placebo audit that no longer reads GATE_BLIND lifts the alarm on the
next pass; a certificate the replication lane marks REPLICATED (under the SAME spec fingerprint)
enrols on the next pass. The replication lane judges never-judged certificates FIRST, so a new
certificate waits about one hour, not a full rotation.

A LIBRARY, NOT AN ORGAN: it runs on the clocks of the three organs that import it (the enrolment
engine, the qquant lane and the `forward_enrolment` census, which publishes `summary()` in
reports/FORWARD_ENROLMENT.json under `integrity`).
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent

PLACEBO_REPORT = BASE / "reports" / "PLACEBO_AUDIT.json"
REPLICATION_VERDICTS = BASE / "data" / "replication_civilization" / "verdicts.json"

#: The placebo leg is hourly; a report older than a day no longer describes today's certifier.
#: A stale CLEAR is UNMEASURED (it releases nothing it did not already release). A stale ALARM
#: still holds: an alarm is lifted by an audit that clears it, never by the audit going quiet.
PLACEBO_FRESH_S = 26 * 3600

ALARM, CLEAR, UNMEASURED = "ALARM", "CLEAR", "UNMEASURED"
REPLICATED, MISMATCH = "REPLICATED", "MISMATCH"
UNREACHED, STALE_SPEC = "UNREACHED", "STALE_SPEC"

HELD_PLACEBO = "HELD_PLACEBO_ALARM"
HELD_UNREPLICATED = "HELD_UNREPLICATED"
HELD_MISMATCH = "HELD_REPLICATION_MISMATCH"


def _read(path: Path) -> Any:
    try:
        return json.loads(Path(path).read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _parse_ts(raw: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def spec_fingerprint(symbol: Any, family: Any, selector: Any, side: Any,
                     params: Mapping[str, Any] | None) -> str:
    """One hash for "the strategy this certificate specifies".

    A replication verdict is about a SPEC, not a name: a certificate re-minted under the same name
    with different parameters is a different strategy and its old verdict does not carry over.
    `None` and an absent side hash alike, so a spec that predates the side field is stable.
    """
    # An absent family IS the breakout: `shadow_admission.authorized_runs` defaults it so, and the
    # two sides of this hash must agree or no default-family certificate could ever be released.
    doc = {"symbol": str(symbol or ""), "family": str(family or "session_range_breakout"),
           "selector": str(selector or ""), "side": str(side or "").upper(),
           "params": {str(k): v for k, v in sorted(dict(params or {}).items())}}
    return hashlib.sha1(json.dumps(doc, sort_keys=True, default=str).encode("utf-8")
                        ).hexdigest()[:16]


def placebo_alarm(path: Path | None = None, now: datetime | None = None) -> dict[str, Any]:
    """The program-level alarm, read off the latest placebo audit."""
    p = Path(path or PLACEBO_REPORT)
    t = now or datetime.now(UTC)
    doc = _read(p)
    if not isinstance(doc, dict):
        return {"state": UNMEASURED, "blocks": False, "source": p.name,
                "why": f"{p.name} absent or unreadable: whether the certifier discriminates is "
                       "UNMEASURED, which is a real answer and not a clearance"}
    status = str(doc.get("status") or "")
    blind = [str(x) for x in (doc.get("blind_to") or [])]
    measured = _parse_ts(doc.get("measured_at"))
    age_s = (t - measured).total_seconds() if measured else None
    base = {"source": p.name, "audit_status": status, "blind_to": blind,
            "audit_recall": doc.get("audit_recall"), "measured_at": doc.get("measured_at"),
            "age_s": None if age_s is None else round(age_s, 1)}
    if status == "GATE_BLIND" or blind:
        return {**base, "state": ALARM, "blocks": True,
                "why": (f"the certifier ADMITTED planted trap(s) {blind} in the placebo audit of "
                        f"{doc.get('measured_at')}: a certificate minted now may carry exactly "
                        "that defect, so no NEW certificate starts a forward clock until a fresh "
                        "audit catches every trap again. Running clocks are untouched.")}
    if age_s is None or age_s > PLACEBO_FRESH_S:
        return {**base, "state": UNMEASURED, "blocks": False,
                "why": (f"the latest placebo audit is "
                        f"{'unstamped' if age_s is None else f'{age_s / 3600:.1f}h old'}"
                        f" (fresh = {PLACEBO_FRESH_S // 3600}h): the certifier's recall today "
                        "is UNMEASURED; no alarm is raised on an absence")}
    if status == "OK":
        return {**base, "state": CLEAR, "blocks": False,
                "why": "every planted trap caught and every positive admitted on a fresh audit"}
    return {**base, "state": status or UNMEASURED, "blocks": False,
            "why": (f"audit status {status!r}: no planted trap was admitted, so the certifier is "
                    "not blind; a welded or unjudged plant is a defect for the gate's owner, "
                    "not a reason to distrust an admission")}


@dataclass
class IntegrityGate:
    """Both facts, read once per pass, applied to every certificate that has no clock yet."""

    alarm: dict[str, Any] = field(default_factory=dict)
    verdicts: dict[str, dict[str, Any]] = field(default_factory=dict)
    replication_source: str = ""

    @classmethod
    def load(cls, *, placebo: Path | None = None, verdicts: Path | None = None,
             now: datetime | None = None) -> IntegrityGate:
        vp = Path(verdicts or REPLICATION_VERDICTS)
        doc = _read(vp)
        rows = (doc.get("certificates") if isinstance(doc, dict) else None) or {}
        return cls(alarm=placebo_alarm(placebo, now),
                   verdicts={str(k): v for k, v in rows.items() if isinstance(v, dict)},
                   replication_source=(vp.name if isinstance(doc, dict)
                                       else f"{vp.name} absent"))

    def replication(self, certificate: str, fingerprint: str) -> tuple[str, str]:
        row = self.verdicts.get(str(certificate))
        if row is None:
            return UNREACHED, ("the replication lane has not judged this certificate yet; it "
                               "judges never-judged certificates first, so this clears within "
                               "about one hourly pass")
        if str(row.get("fp") or "") != fingerprint:
            return STALE_SPEC, ("the recorded replication verdict is for a DIFFERENT spec "
                                "fingerprint (the certificate was re-minted); it is re-judged "
                                "first on the next pass")
        verdict = str(row.get("verdict") or UNMEASURED)
        why = "; ".join(str(w) for w in (row.get("why") or []))[:300]
        return verdict, why

    def hold(self, certificate: str, *, symbol: Any, family: Any, selector: Any, side: Any,
             params: Mapping[str, Any] | None) -> str | None:
        """None = the certificate may start a clock; otherwise the named reason it waits."""
        if self.alarm.get("blocks"):
            return f"{HELD_PLACEBO}: {self.alarm.get('why')}"
        fp = spec_fingerprint(symbol, family, selector, side, params)
        verdict, why = self.replication(certificate, fp)
        if verdict == REPLICATED:
            return None
        if verdict == MISMATCH:
            return (f"{HELD_MISMATCH}: an independent rebuild from the written spec disagrees "
                    f"with the desk's implementation ({why})")
        return (f"{HELD_UNREPLICATED} ({verdict}): no independent replication under this spec "
                f"yet -- {why or 'no reason recorded'}")

    def summary(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for row in self.verdicts.values():
            v = str(row.get("verdict") or UNMEASURED)
            counts[v] = counts.get(v, 0) + 1
        return {"placebo_alarm": self.alarm, "replication_source": self.replication_source,
                "replication_verdicts": counts,
                "rule": ("a NEW certificate starts a forward clock only when the latest placebo "
                         "audit shows the certifier admitted no planted trap AND an independent "
                         "rebuild under the same spec fingerprint is REPLICATED; running clocks "
                         "are never touched; no quota, no count, no ranking")}


def lane_clock_keys(shadow_dir: Path | None = None,
                    lanes: tuple[str, ...] = ("shadow_state.json", "qquant_shadow_state.json",
                                              "scalp_shadow_state.json",
                                              "external_shadow_state.json")
                    ) -> set[str]:
    """Every key that already owns a clock in any lane. A key here is never held."""
    d = Path(shadow_dir or (BASE / "reports" / "shadow"))
    keys: set[str] = set()
    for name in lanes:
        doc = _read(d / name)
        if not isinstance(doc, dict):
            continue
        for k, v in doc.items():
            if isinstance(v, dict) and not str(v.get("status") or "").startswith("HELD_"):
                keys.add(str(k))
        sleeves = doc.get("sleeves")
        if isinstance(sleeves, dict):
            keys |= {str(k) for k in sleeves}
    return keys
