"""Panel evidence asymmetry + dissent scoring -- effective-N applied to OPINIONS.

The desk already refuses to treat N correlated trials as N independent ones: DSR deflates by the
number of independent MECHANISM clusters, not the raw tally (§31). The panel never got the same
treatment. Thirteen frontier models all read THE SAME dossier, so "12 of 13 agreed" can be one
framing echoed twelve times -- and a dossier written BY the audited system is exactly the input
most likely to carry a framing. Correlated seats are correlated trials wearing a different hat.

TWO HALVES, and they only work together:

  ASYMMETRY  -- seats are given DIFFERENT slices of the evidence, so they cannot converge on the
                same artifact. Agreement across seats that saw different evidence is genuinely
                independent corroboration; agreement across seats that saw the same page is one
                observation counted many times.
  MEASUREMENT-- the split itself is scored. Which seats dissented, whether dissent tracked the
                evidence they held, and -- over time -- whether contested findings turned out
                BETTER or WORSE than unanimous ones. Nobody knows that answer for this desk, and
                it is cheap to learn from rulings the desk already writes.

DELIBERATELY HYBRID. Most seats keep the full dossier; a minority are partitioned. Full-context
seats catch findings that need cross-referencing (the thing a partitioned seat structurally
cannot see), partitioned seats catch what the narrative omits. Making every seat blind would
trade one blind spot for another, which is not an upgrade.

Related prior art in the desk: GAP #20's stripped-context probe -- ONE auditor per quarter gets
raw artifacts only. This generalises that from n=1/quarter to a standing minority of every run,
and adds the measurement half it never had.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict

#: Evidence blocks a seat may or may not receive.
BLOCKS = ("narrative", "rulings", "graveyard", "source")

#: Evidence profiles. The value is the set of blocks that seat receives.
#:   full      -- everything (status quo; the majority of seats stay here)
#:   raw       -- SOURCE ONLY. No narrative at all: the auditee cannot frame what it cannot write.
#:                This is GAP #20's stripped-context probe, promoted from quarterly-n=1 to standing.
#:   narrative -- prose + outcomes, NO raw source. Sees the story, must judge it on its own terms.
#:   outcomes  -- rulings + graveyard only. Judges what the desk has already SETTLED, with no
#:                current-state narrative to anchor on -- the seat most able to notice that a
#:                'new' finding is a re-run of a closed one.
PROFILES: Mapping[str, tuple[str, ...]] = {
    "full": ("narrative", "rulings", "graveyard", "source"),
    "raw": ("source",),
    "narrative": ("narrative", "rulings", "graveyard"),
    "outcomes": ("rulings", "graveyard"),
}

#: Partition plan: how many NON-full seats, and which profiles, as a function of roster size.
#: Kept small on purpose -- the marginal value of a third blind seat is far below the cost of
#: losing a third cross-referencing seat.
def partition_plan(n_seats: int) -> tuple[str, ...]:
    """Profiles for the non-full minority, longest-first. Empty for tiny rosters.

    A roster under 5 gets NO partitioning: with few seats, every one of them is load-bearing for
    cross-referencing, and blinding 1 of 4 costs more coverage than the independence is worth.
    """
    if n_seats < 5:
        return ()
    if n_seats < 9:
        return ("raw",)
    if n_seats < 13:
        return ("raw", "outcomes")
    return ("raw", "raw", "outcomes", "narrative")


def assign_profiles(seat_names: Sequence[str], *, run_key: str) -> dict[str, str]:
    """Deterministically assign an evidence profile to each seat for this run.

    Deterministic and reproducible from ``run_key`` (so a run can be replayed and audited), but
    ROTATING across runs (so the same model is not permanently the blind one -- that would confound
    'this seat dissents' with 'this seat is always blind' and make the dissent score meaningless).
    """
    plan = partition_plan(len(seat_names))
    if not plan:
        return dict.fromkeys(seat_names, "full")
    ordered = sorted(seat_names)
    # rotate the starting offset by a hash of the run key -- stable within a run, moves between
    digest = hashlib.sha256(run_key.encode("utf-8")).hexdigest()
    offset = int(digest[:8], 16) % len(ordered)
    rotated = ordered[offset:] + ordered[:offset]
    out = dict.fromkeys(seat_names, "full")
    for seat, profile in zip(rotated, plan, strict=False):
        out[seat] = profile
    return out


def compose_dossier(blocks: Mapping[str, str], profile: str) -> str:
    """Build the payload for one seat from the blocks its profile allows."""
    allowed = PROFILES.get(profile, PROFILES["full"])
    parts = [blocks[b] for b in BLOCKS if b in allowed and blocks.get(b)]
    if not parts:  # never send an empty payload -- a seat with nothing to read returns noise
        return blocks.get("narrative", "")
    header = (
        f"## EVIDENCE PROFILE: {profile.upper()}\n"
        f"You have been given a DELIBERATELY PARTIAL view: {', '.join(allowed)}. Other seats hold "
        "different slices. This is by design -- your independent read is the point, so do NOT "
        "speculate about what you cannot see, and do NOT hedge because material is missing. "
        "Judge what is in front of you and say plainly where your view is bounded.\n\n"
    )
    return header + "\n\n".join(parts)


class ThemeSplit(BaseModel):
    """How divided the panel was on one theme -- and whether the split tracked the evidence."""

    model_config = ConfigDict(frozen=True)

    theme: str
    n_raised: int
    n_seats: int
    dissent: float                    # 0.0 unanimous .. 1.0 maximally split
    profiles_raising: tuple[str, ...]
    cross_profile: bool               # raised by seats holding DIFFERENT evidence

    @property
    def independent_corroboration(self) -> bool:
        """Agreement that survived an evidence partition -- the only agreement worth extra weight.

        Two seats reading the same page agreeing is one observation. Two seats reading DIFFERENT
        pages agreeing is two. This flag is the whole return on the asymmetry.
        """
        return self.n_raised >= 2 and self.cross_profile


def theme_splits(
    per_seat_themes: Mapping[str, Sequence[str]], profiles: Mapping[str, str]
) -> tuple[ThemeSplit, ...]:
    """Score each theme's split across the roster, tagged by which evidence profiles raised it."""
    n = len(per_seat_themes)
    if not n:
        return ()
    raisers: dict[str, list[str]] = {}
    for seat, themes in per_seat_themes.items():
        for t in set(themes):
            raisers.setdefault(t, []).append(seat)
    out = []
    for theme, seats in raisers.items():
        k = len(seats)
        # Dissent peaks at a 50/50 split and is 0 when everyone (or nearly nobody) agrees.
        frac = k / n
        dissent = round(1.0 - abs(2.0 * frac - 1.0), 3)
        profs = tuple(sorted({profiles.get(s, "full") for s in seats}))
        out.append(ThemeSplit(theme=theme, n_raised=k, n_seats=n, dissent=dissent,
                              profiles_raising=profs, cross_profile=len(profs) > 1))
    return tuple(sorted(out, key=lambda s: (-s.n_raised, s.theme)))


class DiversityReport(BaseModel):
    """What the partition bought this run."""

    model_config = ConfigDict(frozen=True)

    n_seats: int
    profile_counts: Mapping[str, int]
    splits: tuple[ThemeSplit, ...]
    n_independently_corroborated: int
    n_contested: int                  # dissent >= 0.5 -- the panel genuinely split
    verdict: str


def diversity_report(
    per_seat_themes: Mapping[str, Sequence[str]],
    profiles: Mapping[str, str],
    *,
    contested_at: float = 0.5,
) -> DiversityReport:
    """Summarise the run: what was corroborated across evidence lines, and what split the room."""
    splits = theme_splits(per_seat_themes, profiles)
    counts: dict[str, int] = {}
    for p in profiles.values():
        counts[p] = counts.get(p, 0) + 1
    corroborated = [s for s in splits if s.independent_corroboration]
    contested = [s for s in splits if s.dissent >= contested_at]
    if not splits:
        verdict = "no themes raised -- nothing to score"
    elif len(counts) == 1:
        verdict = (f"{len(splits)} theme(s), roster UNPARTITIONED ({len(profiles)} seats, one "
                   "profile) -- agreement here is not independent corroboration, it is one "
                   "dossier read many times.")
    else:
        verdict = (
            f"{len(corroborated)}/{len(splits)} theme(s) raised across DIFFERENT evidence "
            f"profiles (independent corroboration); {len(contested)} genuinely contested "
            f"(dissent >= {contested_at:.1f}). Contested is not noise to be averaged away -- it "
            "is where the seats' evidence actually disagrees, and the most informative place to "
            "look."
        )
    return DiversityReport(
        n_seats=len(profiles), profile_counts=counts, splits=splits,
        n_independently_corroborated=len(corroborated), n_contested=len(contested),
        verdict=verdict,
    )
