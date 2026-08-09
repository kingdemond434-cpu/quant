#!/usr/bin/env python3
"""EXTERNAL INTELLIGENCE — the video blind spot, the return claims, and the coverage matrix.

THREE QUESTIONS THIS DESK COULD NOT ANSWER BEFORE TODAY::

    which economically relevant videos exist that we have never consumed?
    who has publicly outperformed us, and WHAT actually produced their return?
    has any known external return engine been omitted from our build, silently?

**THE VIDEO HALF EXISTS BECAUSE OF A CAPABILITY BOUNDARY, NOT A PREFERENCE.** The Claude-side
miners cannot reliably retrieve YouTube transcripts and the network-denied research clone cannot
retrieve them at all, so a large body of practitioner knowledge -- much of it with no paper, no
repository and no article behind it -- is invisible to every collector this desk runs. The GPT seat
can retrieve it. This script owns the LEDGER that makes that work auditable and resumable; it does
not fetch, and it cannot.

**THE COVERAGE MATRIX IS SEEDED FROM THE SPECIFICATION, HONESTLY.** Every engine the mandate names
enters at its true adoption level, which for most of them is IDENTIFIED and SPECIFIED and nothing
else. That produces an uncomfortable headline on the first run, and the uncomfortable headline is
the deliverable: a matrix that opened at "mostly adopted" would be measuring the author's optimism.

Reads ledgers, writes a report. Fetches nothing, validates nothing, promotes nothing.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research.competitor_coverage import EngineCoverage  # noqa: E402
from libs.research.competitor_coverage import summarise as coverage_summary  # noqa: E402
from libs.research.practitioner_corpus import Disagreement, PractitionerRecord  # noqa: E402
from libs.research.practitioner_corpus import summarise as practitioner_summary  # noqa: E402
from libs.research.return_claims import ReturnClaim  # noqa: E402
from libs.research.return_claims import summarise as claims_summary  # noqa: E402
from libs.research.video_intelligence import ChannelCoverage, VideoRecord  # noqa: E402
from libs.research.video_intelligence import summarise as video_summary  # noqa: E402

DATA = ROOT / "data" / "intelligence"
OUT = DATA / "external_intel.json"
VIDEO_LEDGER = DATA / "video_channel_coverage.json"
CLAIMS_LEDGER = DATA / "extreme_return_claims.json"
COVERAGE_LEDGER = ROOT / "docs" / "research" / "COMPETITOR_COVERAGE.json"
PRACTITIONER_LEDGER = DATA / "practitioner_corpus.json"


def _load(p: Path) -> object | None:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def video_section() -> dict[str, object]:
    raw = _load(VIDEO_LEDGER)
    channels: list[ChannelCoverage] = []
    if isinstance(raw, dict):
        for c in raw.get("channels", []):
            vids = []
            for v in c.get("videos", []):
                try:
                    vids.append(VideoRecord(
                        video_id=str(v["video_id"]), channel=str(c.get("channel", "")),
                        title=str(v.get("title", "")),
                        published_at=str(v.get("published_at", "")),
                        url=str(v.get("url", "")),
                        economically_relevant=bool(v.get("economically_relevant", True)),
                        transcript_status=str(v.get("transcript_status", "UNAVAILABLE")),
                        transcript_source=str(v.get("transcript_source", "")),
                        start_verified=bool(v.get("start_verified", False)),
                        end_verified=bool(v.get("end_verified", False)),
                        duplicate_of=str(v.get("duplicate_of", "")),
                        mechanisms_extracted=int(v.get("mechanisms_extracted", 0)),
                        failures_extracted=int(v.get("failures_extracted", 0)),
                        claims_extracted=int(v.get("claims_extracted", 0)),
                        residuals_new=int(v.get("residuals_new", 0)),
                        unresolved_reason=str(v.get("unresolved_reason", "")),
                        estimated_value=float(v.get("estimated_value", 0.0))))
                except (KeyError, ValueError, TypeError):
                    continue
            channels.append(ChannelCoverage(
                channel=str(c.get("channel", "?")), creator=str(c.get("creator", "")),
                category=str(c.get("category", "")), videos=tuple(vids),
                enumeration_complete=bool(c.get("enumeration_complete", False)),
                last_swept=str(c.get("last_swept", "")),
                processing_cost_units=float(c.get("processing_cost_units", 0.0))))
    return video_summary(channels)


def claims_section() -> dict[str, object]:
    raw = _load(CLAIMS_LEDGER)
    claims: list[ReturnClaim] = []
    if isinstance(raw, dict):
        for c in raw.get("claims", []):
            try:
                claims.append(ReturnClaim(
                    subject=str(c["subject"]), source=str(c.get("source", "")),
                    observed_at=str(c.get("observed_at", "")),
                    evidence_class=str(c["evidence_class"]),
                    reported_return=float(c.get("reported_return", 0.0)),
                    horizon_days=float(c.get("horizon_days", 0.0)),
                    starting_capital=float(c.get("starting_capital", 0.0)),
                    ending_capital=float(c.get("ending_capital", 0.0)),
                    net_of_costs=bool(c.get("net_of_costs", False)),
                    realised=bool(c.get("realised", False)),
                    flows_disclosed=bool(c.get("flows_disclosed", False)),
                    max_leverage=c.get("max_leverage"),
                    max_concentration=c.get("max_concentration"),
                    estimated_beta=c.get("estimated_beta"),
                    reported_drawdown=c.get("reported_drawdown"),
                    strategy_family=str(c.get("strategy_family", "")),
                    mechanism=str(c.get("mechanism", "")),
                    attribution={str(k): float(v)
                                 for k, v in (c.get("attribution") or {}).items()},
                    contradictions=str(c.get("contradictions", ""))))
            except (KeyError, ValueError, TypeError):
                continue
    return claims_summary(claims)


def coverage_section() -> dict[str, object]:
    raw = _load(COVERAGE_LEDGER)
    engines: list[EngineCoverage] = []
    if isinstance(raw, dict):
        for e in raw.get("engines", []):
            try:
                engines.append(EngineCoverage(
                    engine=str(e["engine"]),
                    external_uses=str(e.get("external_uses", "UNKNOWN")),
                    external_evidence=str(e.get("external_evidence", "")),
                    our_equivalent=str(e.get("our_equivalent", "")),
                    dimensions_met=tuple(e.get("dimensions_met") or ()),
                    measured_value=str(e.get("measured_value", "")),
                    residual_gap=str(e.get("residual_gap", "")),
                    expected_close_value=float(e.get("expected_close_value", 0.0)),
                    estimated_cost_units=float(e.get("estimated_cost_units", 0.0))))
            except (KeyError, ValueError, TypeError):
                continue
    return coverage_summary(engines)


def practitioner_section() -> dict[str, object]:
    """GPT Hunter's THIRD mission: people, not channels.

    A practitioner's corpus spans a dozen channels and none of them is it. This section stays
    UNMEASURED until the GPT seat has enumerated at least one person, and an empty ledger here
    means the seat has not run -- not that there is nobody worth reading.
    """
    raw = _load(PRACTITIONER_LEDGER)
    rows = raw.get("practitioners") if isinstance(raw, dict) else None
    records = []
    for r in (rows if isinstance(rows, list) else []):
        if not isinstance(r, dict):
            continue
        records.append(PractitionerRecord(**{
            k: (tuple(v) if isinstance(v, list) else v) for k, v in r.items()
            if k in PractitionerRecord.__dataclass_fields__}))
    disagreements = []
    draw = raw.get("disagreements") if isinstance(raw, dict) else None
    for d in (draw if isinstance(draw, list) else []):
        if isinstance(d, dict):
            disagreements.append(Disagreement(**{
                k: v for k, v in d.items() if k in Disagreement.__dataclass_fields__}))
    return practitioner_summary(records, disagreements=disagreements)


def build() -> dict[str, object]:
    video = video_section()
    claims = claims_section()
    coverage = coverage_section()
    try:
        practitioners = practitioner_section()
    except (TypeError, ValueError, KeyError) as e:
        practitioners = {"measured": False, "headline": (
            f"practitioner ledger present but MALFORMED ({type(e).__name__}: {e}) -- UNMEASURED. "
            "A ledger that cannot be parsed knows exactly as much as one that is empty")}
    blocked = video.get("unresolved_high_value") or []
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "video_intelligence": video,
        "extreme_return_claims": claims,
        "competitor_coverage": coverage,
        "practitioner_corpus": practitioners,
        "externally_blocked_sources": len(blocked) if isinstance(blocked, list) else 0,
        "next_action": _next_action(video, claims, coverage),
        "note": ("Transcript retrieval belongs to the GPT seat: the Claude-side miners cannot "
                 "reliably obtain YouTube captions and a network-denied clone cannot obtain them "
                 "at all. This script owns the LEDGER, not the fetch -- it makes the work "
                 "auditable, resumable and honest about what remains unread."),
    }


def _next_action(video: dict, claims: dict, coverage: dict) -> str:
    """The single highest-value external-intelligence action, chosen in a fixed precedence.

    Fragment-extractions rank first because they are the only entry here that has already put
    something WRONG into the desk's knowledge; everything else is merely absent, and absent is
    cheaper than false.
    """
    frag = video.get("extractions_from_incomplete_transcripts") or []
    if frag:
        return (f"{len(frag)} extraction(s) came from transcripts below NEAR_FULL -- re-fetch "
                "those transcripts complete and re-extract; a claim about a fragment recorded as "
                "a claim about the video is the only error here that is already in the corpus")
    rows = coverage.get("residual_frontier") or []
    if rows and isinstance(rows, list):
        top = rows[0]
        return (f"close the residual on {top['engine']} (first missing: {top['first_missing']})"
                + (f" -- {top['residual_gap']}" if top.get("residual_gap") else ""))
    if int(video.get("open_channels", 0) or 0):
        return f"{video['open_channels']} channel(s) still open -- continue corpus enumeration"
    if claims.get("claims"):
        return f"investigate {claims.get('top_priority')}: highest-priority return claim"
    return ("seed the ledgers: no channels enumerated, no claims recorded, no coverage matrix "
            "populated. The blind spot is currently invisible as well as large")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    rep = build()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(rep, indent=1), "utf-8")
    print("=== EXTERNAL INTELLIGENCE ===")
    print(f"  VIDEO    : {rep['video_intelligence']['headline']}")       # type: ignore[index]
    print(f"  CLAIMS   : {rep['extreme_return_claims']['headline']}")    # type: ignore[index]
    print(f"  COVERAGE : {rep['competitor_coverage']['headline']}")      # type: ignore[index]
    print(f"  NEXT     : {rep['next_action']}")
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
