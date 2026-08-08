"""VIDEO / TRANSCRIPT INTELLIGENCE — the source class this desk's own miners cannot reach.

WHY THIS IS A SEPARATE ORGAN. The Claude-side miners cannot reliably retrieve YouTube transcripts,
and the network-denied research clone cannot retrieve them at all. That is not a small gap: a large
share of the practitioner knowledge this desk is benchmarked against exists ONLY as spoken word in
video, has no paper, no repository and no article, and is therefore invisible to every collector
the desk currently runs. A blind spot that large is not a missing feature, it is a missing sense.

So the retrieval job belongs to whichever organ can actually do it -- the GPT seat -- and this
module is the LEDGER that makes its work auditable, resumable and honest. It does not fetch
anything. It records what was fetched, at what completeness, and what remains.

**THE ONE DISCIPLINE THIS FILE EXISTS TO ENFORCE: PARTIAL IS NEVER FULL.** A transcript that
covers the first eight minutes of a fifty-minute video is a different object from a transcript, and
the difference is invisible downstream -- an extraction from a partial transcript looks exactly
like an extraction from a complete one, and "we mined that channel" becomes true-sounding and
wrong. `TranscriptStatus` is therefore ordered, `is_complete` is narrow, and `exhausted()` refuses
to call a channel done while any economically relevant video is below NEAR_FULL.

**A CHANNEL IS NEVER PERMANENTLY EXHAUSTED.** New uploads reopen it by construction: exhaustion is
computed against the videos ENUMERATED, and enumeration has a timestamp. The report says
CURRENTLY_EXHAUSTED, never DONE.

**CREATOR COUNT IS NOT EVIDENCE COUNT.** Twenty creators describing an RSI-oversold system are
frequently one mechanism copied nineteen times. `effective_independent_sources` collapses them, so
popularity cannot masquerade as replication.

Records and measures. Fetches nothing, validates no strategy, promotes nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "MIN_STATUS_FOR_EXTRACTION",
    "TRANSCRIPT_STATUS",
    "UNRESOLVED_REASONS",
    "ChannelCoverage",
    "VideoRecord",
    "effective_independent_sources",
    "exhausted",
    "source_roi",
    "summarise",
    "unresolved_high_value",
]

#: Ordered weakest to strongest. The ordering is load-bearing: `MIN_STATUS_FOR_EXTRACTION` is an
#: index into it, so raising the bar is a one-line change rather than a scattered comparison.
TRANSCRIPT_STATUS: tuple[str, ...] = (
    "UNAVAILABLE",        # nothing retrievable by any lawful public route
    "DESCRIPTION_ONLY",   # description/chapters only -- titles of ideas, not the ideas
    "PARTIAL",            # a fragment. NEVER to be recorded as FULL
    "NEAR_FULL",          # complete but for gaps that do not change the meaning
    "FULL",               # beginning to end
)

#: Below this, an extraction is a claim about a fragment and must not be recorded as a claim about
#: the video. DESCRIPTION_ONLY yields the TITLES of ideas and none of their content.
MIN_STATUS_FOR_EXTRACTION: str = "NEAR_FULL"

#: Why a transcript could not be obtained. Recorded rather than dropped: a video silently skipped
#: is indistinguishable from a video that contained nothing, and only one of those is true.
UNRESOLVED_REASONS: tuple[str, ...] = (
    "TRANSCRIPT_DISABLED", "TRANSCRIPT_UNAVAILABLE", "FETCH_FAILED", "VIDEO_REMOVED",
    "ACCESS_LIMIT", "SOURCE_UNRESOLVED", "OTHER",
)


@dataclass(frozen=True)
class VideoRecord:
    """One video, its transcript completeness, and what was actually taken from it."""

    video_id: str
    channel: str
    title: str
    published_at: str = ""
    url: str = ""
    #: Does this video plausibly contain economically useful material? Set by triage, not by hope.
    economically_relevant: bool = True
    transcript_status: str = "UNAVAILABLE"
    transcript_source: str = ""
    #: Verified that the transcript begins at the start and ends at the end. Two booleans rather
    #: than one because a transcript truncated at the END is the commonest silent failure: the
    #: conclusions, the failures and the caveats all live in the last ten minutes.
    start_verified: bool = False
    end_verified: bool = False
    #: Another video_id when this is a re-upload or a duplicate cut.
    duplicate_of: str = ""
    mechanisms_extracted: int = 0
    failures_extracted: int = 0
    claims_extracted: int = 0
    #: Residual mechanisms that survived dedupe against the existing quant.
    residuals_new: int = 0
    unresolved_reason: str = ""
    #: Estimated economic value of what is still unread here. Drives the unresolved queue.
    estimated_value: float = 0.0

    def __post_init__(self) -> None:
        if self.transcript_status not in TRANSCRIPT_STATUS:
            raise ValueError(f"transcript_status must be one of {TRANSCRIPT_STATUS}")
        if self.unresolved_reason and self.unresolved_reason not in UNRESOLVED_REASONS:
            raise ValueError(f"unresolved_reason must be one of {UNRESOLVED_REASONS}")

    @property
    def rank(self) -> int:
        return TRANSCRIPT_STATUS.index(self.transcript_status)

    @property
    def extractable(self) -> bool:
        """Complete enough that an extraction is a claim about the VIDEO rather than a fragment.

        Requires BOTH ends verified even at FULL. A transcript labelled FULL whose end was never
        checked is a labelling claim, and this is the one place the desk can still catch it.
        """
        return (self.rank >= TRANSCRIPT_STATUS.index(MIN_STATUS_FOR_EXTRACTION)
                and self.start_verified and self.end_verified)

    @property
    def processed(self) -> bool:
        return self.extractable and (self.mechanisms_extracted + self.failures_extracted
                                     + self.claims_extracted) > 0


@dataclass(frozen=True)
class ChannelCoverage:
    """One creator corpus and how much of it the desk has actually consumed."""

    channel: str
    creator: str = ""
    category: str = ""
    #: Videos the enumerator FOUND. Distinct from videos that exist -- enumeration can be
    #: incomplete, and `enumeration_complete` says whether the denominator is trustworthy.
    videos: tuple[VideoRecord, ...] = field(default_factory=tuple)
    enumeration_complete: bool = False
    last_swept: str = ""
    #: Cost so far, for the ROI decision about whether to keep mining this creator.
    processing_cost_units: float = 0.0

    @property
    def relevant(self) -> tuple[VideoRecord, ...]:
        return tuple(v for v in self.videos if v.economically_relevant and not v.duplicate_of)


def exhausted(c: ChannelCoverage) -> tuple[bool, str]:
    """(currently_exhausted, why). NEVER 'done' -- a new upload reopens the corpus by itself."""
    rel = c.relevant
    if not c.enumeration_complete:
        return False, (
            f"{c.channel}: enumeration incomplete, so the denominator is unknown. "
            f"{len(rel)} relevant video(s) found is a LOWER bound and calling the corpus covered "
            "would be a statement about what was looked at, not about what exists")
    if not rel:
        return True, (f"{c.channel}: enumerated, zero economically relevant videos. Currently "
                      "exhausted -- and a new upload reopens it")
    unprocessed = [v for v in rel if not v.processed]
    if unprocessed:
        blocked = [v for v in unprocessed if v.unresolved_reason]
        return False, (
            f"{c.channel}: {len(unprocessed)} of {len(rel)} relevant video(s) unprocessed"
            + (f", {len(blocked)} of them externally blocked ("
               f"{sorted({v.unresolved_reason for v in blocked})})" if blocked else "")
            + ". A blocked video is EXTERNALLY_BLOCKED, never covered")
    return True, (f"{c.channel}: all {len(rel)} relevant video(s) consumed end-to-end as of "
                  f"{c.last_swept or 'an unrecorded sweep'}. CURRENTLY exhausted -- new uploads "
                  "reopen the corpus automatically")


def unresolved_high_value(channels: list[ChannelCoverage],
                          *, floor: float = 0.0) -> list[dict[str, object]]:
    """Videos that could not be retrieved and are worth returning to. §XV.

    A video dropped silently is indistinguishable from a video that contained nothing, and only one
    of those is true. Ranked by estimated value so the retry queue is economic rather than
    chronological.
    """
    out = []
    for c in channels:
        for v in c.relevant:
            if v.unresolved_reason and v.estimated_value >= floor:
                out.append({"channel": c.channel, "video_id": v.video_id, "title": v.title,
                            "reason": v.unresolved_reason, "url": v.url,
                            "estimated_value": v.estimated_value,
                            "status": v.transcript_status})
    out.sort(key=lambda d: -float(str(d["estimated_value"])))
    return out


def source_roi(c: ChannelCoverage) -> tuple[float | None, str]:
    """Residual mechanisms per unit of processing cost. Decides CADENCE, never deletion.

    A creator who was historically valuable is not thereby valuable now -- the question is whether
    the NEXT video is expected to contain something the desk does not already have. Falling ROI
    lowers the sweep cadence; it never removes the source, because a new strategy, a new failure
    or a new dataset reopens it.
    """
    if c.processing_cost_units <= 0:
        return None, (f"{c.channel}: no processing cost recorded, so ROI is UNMEASURED and the "
                      "mining cadence for this creator is currently a habit rather than a decision")
    residuals = sum(v.residuals_new for v in c.relevant)
    roi = residuals / c.processing_cost_units
    return roi, (
        f"{c.channel}: {residuals} residual mechanism(s) survived dedupe per "
        f"{c.processing_cost_units:g} cost unit(s) = {roi:.2f}. "
        + ("Marginal information is low -- LOWER THE CADENCE, do not delete the source"
           if roi < 0.1 else "Still producing genuinely new material"))


def effective_independent_sources(mechanism: str,
                                  creators: dict[str, float]) -> tuple[float, str]:
    """How many INDEPENDENT discoveries a mechanism really has. §XXII.

    `creators` maps creator -> estimated probability that this creator arrived at the mechanism
    independently (rather than from the same paper, the same community post, or each other).
    Twenty creators at p=0.05 are one discovery; three at p=0.9 are nearly three.

    Repeated popularity is not replication. It is usually diffusion, and diffusion is a CROWDING
    signal rather than an evidence signal -- which is exactly what §XXIII proposes testing.
    """
    if not creators:
        return 0.0, f"{mechanism}: no creators recorded"
    eff = sum(max(0.0, min(1.0, p)) for p in creators.values())
    n = len(creators)
    return eff, (
        f"{mechanism}: {n} creator(s) discuss it, {eff:.2f} effective independent discoveries. "
        + ("Popularity without independence -- treat this as DIFFUSION (a crowding input), not as "
           "replication" if eff < 0.5 * n else
           "Genuinely repeated independent discovery raises this mechanism's priority"))


def summarise(channels: list[ChannelCoverage]) -> dict[str, object]:
    """Report shape for `data/intelligence/video_channel_coverage.json`."""
    if not channels:
        return {"channels": 0, "headline": (
            "no video coverage recorded. A source class this desk's own miners cannot retrieve is "
            "also a source class nobody is tracking, which makes the blind spot invisible as well "
            "as large")}
    rows = []
    for c in channels:
        done, why = exhausted(c)
        roi, roi_why = source_roi(c)
        rel = c.relevant
        by_status = {s: sum(1 for v in rel if v.transcript_status == s) for s in TRANSCRIPT_STATUS}
        rows.append({
            "channel": c.channel, "creator": c.creator, "category": c.category,
            "videos_enumerated": len(c.videos),
            "economically_relevant": len(rel),
            "enumeration_complete": c.enumeration_complete,
            "by_transcript_status": {k: v for k, v in by_status.items() if v},
            "extractable": sum(1 for v in rel if v.extractable),
            "processed": sum(1 for v in rel if v.processed),
            "residuals_new": sum(v.residuals_new for v in rel),
            "currently_exhausted": done, "why": why,
            "source_roi": None if roi is None else round(roi, 3), "roi_note": roi_why,
            "last_swept": c.last_swept,
        })
    rows.sort(key=lambda r: (r["currently_exhausted"], -int(str(r["economically_relevant"]))))
    blocked = unresolved_high_value(channels)
    open_channels = [r for r in rows if not r["currently_exhausted"]]
    # PARTIAL-BUT-EXTRACTED IS THE DEFECT WORTH LEADING WITH: it is the only way a fragment gets
    # recorded as knowledge, and it is silent everywhere downstream.
    fragments = [
        {"channel": c.channel, "video_id": v.video_id, "title": v.title,
         "status": v.transcript_status}
        for c in channels for v in c.relevant
        if not v.extractable and (v.mechanisms_extracted + v.claims_extracted) > 0]
    return {
        "channels": len(channels),
        "rows": rows,
        "open_channels": len(open_channels),
        "unresolved_high_value": blocked,
        "extractions_from_incomplete_transcripts": fragments,
        "headline": (
            f"{len(fragments)} extraction(s) came from transcripts below "
            f"{MIN_STATUS_FOR_EXTRACTION} -- a claim about a fragment recorded as a claim about "
            "the video, which is invisible everywhere downstream" if fragments else
            f"{len(open_channels)} of {len(channels)} channel(s) still open; "
            f"{len(blocked)} video(s) externally blocked and queued for retry"),
        "note": ("PARTIAL is never FULL and DESCRIPTION_ONLY yields the titles of ideas rather "
                 "than the ideas. A channel is only ever CURRENTLY exhausted: exhaustion is "
                 "computed against the videos enumerated, so a new upload reopens it by "
                 "construction. Falling source ROI lowers the sweep cadence and never deletes "
                 "the source."),
    }
