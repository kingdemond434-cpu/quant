"""PROPRIETARY DATA MANUFACTURING -- Tier-1 lever. Make datasets nobody can rebuild.

GPT ranked this the single largest opportunity and it is right, for a reason this desk has
already measured: its own information-advantage ranking puts owned order-book snapshots at 1.03
and every other source at 0.37 or below. The gap is not predictive power -- funding scores higher
on that -- it is REPLICATION DIFFICULTY. An edge on public data is an edge everyone can find and
therefore an edge that is already priced.

COLLECTION IS NOT MANUFACTURING, and the distinction is the whole file. Downloading a public
endpoint yields a dataset with a replication cost of roughly zero: a competitor reproduces it in
an afternoon. Manufacturing means producing a series that did not exist in any input -- through
reconstruction, fusion, or observation at timestamps only we hold.

FOUR MANUFACTURING MODES, in ascending order of replication cost:

  OBSERVE      capture at OUR timestamps. The venue publishes a book; it does not publish OUR
               1.5-second snapshots of it. Cheap to run, impossible to backfill -- which is the
               property that matters: every day not recording is a day permanently lost, so this
               is the one mode where delay destroys the asset rather than postponing it.
  RECONSTRUCT  derive a LATENT variable nobody publishes -- queue position, hidden liquidity,
               iceberg residual, true resting depth, participant inventory. Requires the observed
               series plus a model, so replication needs both the data AND the method.
  FUSE         join two sources on a key nobody else aligns, producing a series present in
               neither. Replication cost is multiplicative: a competitor needs every input plus
               the alignment insight.
  SYNTHESISE   transfer a construct from an unrelated domain onto owned data. Highest replication
               cost because the idea itself is the barrier, and the lowest hit rate -- which is
               exactly why it needs an explicit budget rather than being left to spare time.

THE SCORE IS THE POINT. Every manufactured dataset carries an estimated REVERSE-ENGINEERING COST
-- what a competitor must spend, in calendar time and capital, to rebuild it. That number is the
moat, it is the thing to maximise, and it is the term the desk's advantage ranking already uses.
A dataset a rival rebuilds in a weekend is a chore, not an asset, however clever it looks.

Pure scoring and proposal. Collects nothing, promotes nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "MODES",
    "ManufactureSpec",
    "propose_from_owned",
    "reverse_engineering_cost",
    "score_spec",
]

#: mode -> (base replication difficulty 0..1, why). Difficulty is what a COMPETITOR faces, not
#: what we face -- those are different numbers and conflating them is how a desk talks itself
#: into believing a public feed is an advantage because it was annoying to parse.
MODES: dict[str, tuple[float, str]] = {
    "OBSERVE": (0.90, "captured at OUR timestamps; cannot be backfilled by anyone, ever"),
    "RECONSTRUCT": (0.80, "latent variable: needs the observed series AND the method"),
    "FUSE": (0.75, "join nobody else makes; replication needs every input plus the insight"),
    "SYNTHESISE": (0.70, "cross-domain construct; the idea itself is the barrier"),
    "COLLECT": (0.05, "public endpoint -- a competitor rebuilds this in an afternoon"),
}


@dataclass(frozen=True)
class ManufactureSpec:
    """A proposed dataset. `inputs` are what it is built FROM -- the honest replication surface."""

    name: str
    mode: str
    inputs: tuple[str, ...] = ()
    #: Does the series accrue only with calendar time? If so it can never be bought or backfilled,
    #: and every day of delay is permanent loss rather than deferred cost.
    time_accruing: bool = False
    #: Rough build cost in engineer-days. Denominator; small is better, but never the point.
    build_days: float = 1.0
    notes: str = ""
    extra: dict = field(default_factory=dict)


def reverse_engineering_cost(spec: ManufactureSpec) -> float:
    """Estimated cost to a COMPETITOR of rebuilding this, on an arbitrary but consistent scale.

    Three multipliers, and the third is the one desks forget:

      MODE            what kind of manufacturing it is (see MODES).
      INPUT DEPTH     each additional required input multiplies the work -- a competitor needs
                      ALL of them, so fusion compounds difficulty rather than adding to it.
      TIME ACCRUAL    x3 when the series can only be grown by waiting. This is the only barrier
                      money cannot cross: a rival with unlimited capital still cannot buy last
                      month's order book if nobody recorded it. It is also why the desk's own
                      recorder is worth more than its analysis.
    """
    base, _ = MODES.get(spec.mode.upper(), MODES["COLLECT"])
    depth = 1.0 + 0.35 * max(0, len(spec.inputs) - 1)
    clock = 3.0 if spec.time_accruing else 1.0
    return round(base * depth * clock, 4)


def score_spec(spec: ManufactureSpec) -> dict:
    """Replication cost per engineer-day. Ranks what to build FIRST."""
    rc = reverse_engineering_cost(spec)
    days = max(0.25, float(spec.build_days))
    d = {
        "name": spec.name, "mode": spec.mode.upper(), "inputs": list(spec.inputs),
        "reverse_engineering_cost": rc, "build_days": days,
        "moat_per_day": round(rc / days, 4),
        "time_accruing": spec.time_accruing,
        "why": MODES.get(spec.mode.upper(), MODES["COLLECT"])[1],
        "notes": spec.notes,
    }
    if spec.mode.upper() == "COLLECT":
        d["warning"] = ("COLLECTION IS NOT MANUFACTURING. This produces no durable advantage; "
                        "any edge found on it is available to everyone and is already priced. "
                        "Worth doing only as an INPUT to a RECONSTRUCT or FUSE spec.")
    if spec.time_accruing:
        d["urgency"] = ("TIME-ACCRUING: every day not recording is permanently lost. Starting "
                        "late is the only way to lose this asset, and no amount of money "
                        "recovers it afterwards.")
    return d


def propose_from_owned() -> list[ManufactureSpec]:
    """Concrete specs buildable from what the desk ALREADY holds -- no new vendor, no new spend.

    Deliberately grounded rather than imaginative. The desk owns ~4.4GB of self-recorded
    order-book snapshots at 0.4% exploitation, so the highest-value manufacturing available is
    reconstruction and fusion ON DATA IT ALREADY HAS. Proposing exotic new acquisitions while an
    un-replicable asset sits unmined would be the expensive way to avoid the obvious.
    """
    return [
        ManufactureSpec(
            "resting_depth_true", "RECONSTRUCT", ("moat_depth",), time_accruing=True,
            build_days=2.0,
            notes="Displayed depth minus inferred iceberg residual. Everyone sees the displayed "
                  "book; nobody publishes what is actually resting behind it."),
        ManufactureSpec(
            "queue_position_estimate", "RECONSTRUCT", ("moat_depth", "moat_trades"),
            time_accruing=True, build_days=3.0,
            notes="Where our order sits in the queue, inferred from depth deltas against prints. "
                  "Directly sizes adverse selection -- the cost model's largest unknown."),
        ManufactureSpec(
            "liquidity_withdrawal_rate", "RECONSTRUCT", ("moat_depth",), time_accruing=True,
            build_days=1.5,
            notes="Speed and asymmetry of depth vanishing before a move. M_LIQUIDITY_WITHDRAWAL "
                  "is the desk's #1 blind spot: advantage 1.03 at 0.4% coverage, 0 tested."),
        ManufactureSpec(
            "replenishment_halflife", "RECONSTRUCT", ("moat_depth",), time_accruing=True,
            build_days=1.5,
            notes="How fast a level rebuilds after being taken. Distinguishes real liquidity from "
                  "quote-stuffing, which no public feed separates."),
        ManufactureSpec(
            "funding_vs_book_pressure", "FUSE", ("funding_history", "moat_depth"),
            time_accruing=True, build_days=2.0,
            notes="Joins the ONE confirmed edge (funding, IC +0.432) to the highest-advantage "
                  "dataset. Neither input alone contains this series."),
        ManufactureSpec(
            "venue_latency_asymmetry", "FUSE", ("moat_trades", "venue_divergence"),
            time_accruing=True, build_days=2.5,
            notes="Which venue leads, by how much, conditioned on regime. Needs simultaneous "
                  "multi-venue capture -- a competitor must have been recording both, then."),
        ManufactureSpec(
            "inventory_stress_proxy", "SYNTHESISE", ("moat_depth", "moat_trades"),
            time_accruing=True, build_days=4.0,
            notes="Market-maker inventory stress, transferred from dealer-inventory models in "
                  "equity microstructure. Ranked UNTESTED with maximum ERV on this desk."),
    ]
