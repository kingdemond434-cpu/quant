"""MODEL CHAIN -- one source of truth, and the ranking that lets the desk upgrade itself.

THE PROBLEM. The fallback chain `claude-fable-5 claude-opus-5 claude-opus-4-8` was hardcoded in
THREE places (ops/brain_env.sh, ops/run_frontier_miner.sh, scripts/run_deep_sweep.py). Any change
-- including an automatic upgrade -- silently updated one and left two stale, so organs would
disagree about which model they run and the disagreement would be invisible. Capacity policy hit
exactly this failure earlier (a constant re-inlined next to a scorer, fenced by
check_capacity_single_source); this is the same defect wearing a different name.

So the chain lives in `ops/model_chain.env` -- generated, committed, sourced by every shell organ,
imported by every python organ. This module owns the ranking logic and nothing else, which is what
makes the auto-upgrader testable without a network.

WHY RANKING IS EXPLICIT AND CONSERVATIVE. "Newer flagship" cannot be inferred from a string. The
desk therefore ranks only what it can defend:
  * FAMILY TIER is a declared ladder, not a guess. Unknown families rank -1 and are never
    auto-adopted -- they are PROPOSED, because silently promoting an unrecognised model into the
    path that sizes real positions is the kind of convenience that ends compounding.
  * VERSION is parsed from the trailing numeric segment, so `4-8` -> 4.8 and `5` -> 5.0, giving
    the ordering opus-4-8 < opus-5. A model with no parseable version ranks below every parseable
    one rather than above -- unknown is not "newest".

An upgrade is only ever a PREPEND. The outgoing head stays in the chain directly beneath the new
one, so a newly-promoted model that starts erroring or throttling falls back to the exact model
the desk was running yesterday, with no human awake.
"""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
CHAIN_FILE = _ROOT / "ops/model_chain.env"

# The declared ladder. Fable and Opus are peers at the flagship tier: the desk's policy
# (principal 2026-07-30) is fable-first-to-exhaustion, then opus -- an ORDERING decision inside a
# tier, not a capability ranking, which is why they share tier 3.
FAMILY_TIER: dict[str, int] = {"opus": 3, "fable": 3, "sonnet": 2, "haiku": 1}

FLAGSHIP_TIER = 3

# Never longer than this: a chain deeper than four is untestable at cycle start, and every extra
# entry is another model whose failure mode nobody has seen.
MAX_CHAIN = 4

# The compiled-in floor used when ops/model_chain.env is missing or corrupt. It tracks
# DEFAULT_CHAIN (opus-first, principal 2026-08-12) rather than the old fable-first order, so a
# lost chain file degrades to the CURRENT policy instead of quietly restoring the previous one.
_FALLBACK_CHAIN = ("claude-opus-5", "claude-opus-4-8", "claude-fable-5")


def parse_model(model_id: str) -> tuple[int, float]:
    """(family_tier, version). Unknown family -> -1. Unparseable version -> -1.0.

    Deliberately total: it never raises on a model id it has not seen, because the caller's job is
    to REFUSE unknowns, and a crash in the upgrader would take the whole cycle down with it.
    """
    m = re.match(r"^claude-([a-z]+)-([0-9][0-9-]*)", model_id.strip().lower())
    if not m:
        # Legacy shape: claude-3-5-sonnet-20241022 -- family after the digits.
        alt = re.match(r"^claude-([0-9][0-9-]*)-([a-z]+)", model_id.strip().lower())
        if not alt:
            return (-1, -1.0)
        family, ver = alt.group(2), alt.group(1)
    else:
        family, ver = m.group(1), m.group(2)
    tier = FAMILY_TIER.get(family, -1)
    # A trailing YYYYMMDD snapshot is a DATE, not a version segment. Left in, `haiku-4-5-20251001`
    # parses as 4.52 instead of 4.5 -- which orders two snapshots of the same model against each
    # other and would churn the chain on every re-dating. Only the first two segments are version.
    parts = [p for p in ver.split("-") if p.isdigit() and len(p) < 5][:2]
    if not parts:
        return (tier, -1.0)
    version = float(parts[0]) + (float(f"0.{parts[1]}") if len(parts) > 1 else 0.0)
    return (tier, version)


def is_flagship(model_id: str) -> bool:
    return parse_model(model_id)[0] >= FLAGSHIP_TIER


def is_upgrade(candidate: str, incumbent: str) -> bool:
    """Is `candidate` a strictly newer FLAGSHIP than the current chain head?

    Three refusals, each deliberate:
      * an unknown family is never an upgrade (it may not even be a chat model);
      * a lower tier is never an upgrade, so a new sonnet never displaces an opus;
      * an equal version is never an upgrade, so a re-dated snapshot of the same model does not
        churn the chain every night for no capability gain.
    """
    c_tier, c_ver = parse_model(candidate)
    i_tier, i_ver = parse_model(incumbent)
    if c_tier < FLAGSHIP_TIER:
        return False
    if c_tier != i_tier:
        return c_tier > i_tier
    return c_ver > i_ver


def promote(candidate: str, chain: list[str]) -> list[str]:
    """Prepend `candidate`, keeping the outgoing head directly beneath it.

    The old head is retained ON PURPOSE. A model promoted at 03:00 that turns out to be throttled,
    slower, or rejected by the plan must degrade to the exact model the desk ran yesterday without
    waking anyone -- that is the whole point of a chain, and it is why an upgrade is never a
    replacement.
    """
    out = [candidate] + [m for m in chain if m != candidate]
    return out[:MAX_CHAIN]


def read_chain(var: str = "_BRAIN_MODEL_CHAIN") -> list[str]:
    """The live chain for one seat variable. Falls back to the compiled-in constant so a
    missing/corrupt file can never leave an organ with NO model -- the failure would be an outage,
    not a downgrade."""
    if CHAIN_FILE.exists():
        for raw in CHAIN_FILE.read_text("utf-8").splitlines():
            # The file is SHELL: every assignment carries an `export ` prefix. Matching without
            # stripping it silently never matches, so every python reader would fall back to the
            # compiled-in constant -- including the upgrader itself, which would then re-evaluate
            # against a stale head forever and never see its own promotion.
            line = raw.strip().removeprefix("export ").strip()
            if line.startswith(f"{var}="):
                chain = line.split("=", 1)[1].strip().strip('"').split()
                if chain:
                    return chain
    return list(MINER_CHAIN if var == "_MINER_MODEL_CHAIN" else _FALLBACK_CHAIN)


# ---------------------------------------------------------------------------- SEATS
#
# TWO CHAINS, NOT ONE (principal 2026-08-12, supersedes the single fable-first chain of 07-30):
#   "do opus 5 for all things always instead of fable except for miners locally --
#    miners, data, all similar families do fable."
#
# WHY THE DESK NEEDS TWO. Fable and Opus are PEERS at the flagship tier (FAMILY_TIER above), so
# this is a POOL decision, not a capability one. Fable draws a metered credit pool that CAN
# exhaust; opus-5/opus-4-8 sit on the Max subscription seat. Routing everything at one head means
# whichever pool that is becomes the desk's single point of starvation -- which is exactly what
# happened on 07-24, when one max-effort dig drained fable and every organ died at once.
#
# Splitting by seat spends the two pools in parallel instead of in series. The miners are the
# right organs to hold on the metered pool because their work is RESUMABLE by construction (a
# region without a real log today is re-dug next invocation), so a mid-dig credit death costs
# nothing but a retry. Reasoning organs -- CRO, capability hunt, the recommendation worker, the
# deep sweep, and interactive sessions -- are not resumable in that sense: a starved cycle there
# is a LOST cycle, so they take the seat that does not run out.
SEAT_DEFAULT = "default"
SEAT_MINER = "miner"

#: Everything not named a miner. Opus head, opus fallback, and fable LAST as an emergency floor:
#: if both Max-seat models are unavailable the desk degrades to the metered pool rather than going
#: dark, because an organ with no model at all is the worse failure (same argument as read_chain).
DEFAULT_CHAIN: tuple[str, ...] = ("claude-opus-5", "claude-opus-4-8", "claude-fable-5")

#: The mining / data-collection family. Fable head by principal policy; the opus seats remain
#: beneath it so exhaustion is a paged, self-healing walk-down rather than an outage.
MINER_CHAIN: tuple[str, ...] = ("claude-fable-5", "claude-opus-5", "claude-opus-4-8")

#: Organs on the miner seat, by their organ label (the string each ops/ script passes to
#: brain_mutex / dig_dry_run). MEMBERSHIP IS A DATA DECISION: adding a miner means adding a row
#: here, never editing a shell script, so the seat policy cannot drift per-organ the way the model
#: chain itself drifted across three files before 07-30.
MINER_ORGANS: frozenset[str] = frozenset({
    "frontier",            # ops/run_frontier_miner.sh -- 7 regional digs
    "litminer",            # ops/run_litminer_dig.sh -- literature mining
    "prospector",          # ops/run_prospector_dig.sh -- source prospecting
    "dataaxis",            # ops/run_dataaxis_dig.sh -- new data-axis discovery (data family)
    "blindrediscovery",    # ops/run_blindrediscovery_dig.sh -- blind rediscovery mining
    "moatminer",           # ops/run_moat_miner.sh -- proprietary-moat collection
    "crypto_factory",      # ops/run_crypto_factory.sh -- bulk candidate generation
})


def seat_for(organ: str) -> str:
    """Which seat an organ runs on. Prefix-matched so `frontier-cn` resolves to `frontier`.

    An UNKNOWN organ gets SEAT_DEFAULT -- Opus. That default is deliberate and asymmetric: a new
    organ mis-seated onto Opus costs subscription headroom, while one mis-seated onto Fable can
    silently drain the metered pool the miners depend on. The cheaper mistake is the default.
    """
    label = str(organ or "").strip().lower().replace("-", "_")
    for m in MINER_ORGANS:
        if label == m or label.startswith(m + "_"):
            return SEAT_MINER
    return SEAT_DEFAULT


def chain_for(organ_or_seat: str) -> list[str]:
    """The fallback chain for an organ label or a seat name. Never empty."""
    s = str(organ_or_seat or "").strip().lower()
    seat = s if s in (SEAT_DEFAULT, SEAT_MINER) else seat_for(s)
    return list(MINER_CHAIN if seat == SEAT_MINER else DEFAULT_CHAIN)


def promote_into(chain: list[str], candidate: str, *, pin_head: bool = False) -> list[str]:
    """Promote a newly-adopted flagship into one chain, optionally keeping its head PINNED.

    pin_head exists because of a defect this would otherwise reintroduce on the next auto-upgrade.
    The miner chain's head is fable BY PRINCIPAL POLICY, not by capability ranking -- so an
    unattended 03:00 adoption of, say, opus-6 would prepend it and silently move every miner onto
    the Max seat, reversing a routing decision no human was awake to review. With pin_head the
    candidate lands directly BENEATH the pinned head instead: the miners still gain the newer
    model on walk-down, and the pool split survives the upgrade.
    """
    if not chain:
        return [candidate]
    if not pin_head:
        return promote(candidate, chain)
    head = chain[0]
    rest = [m for m in chain[1:] if m != candidate]
    return [head, candidate, *rest][:MAX_CHAIN]


def render_chain(chain: list[str], *, reason: str, sealed: str,
                 miner_chain: list[str] | None = None) -> str:
    miner = list(miner_chain) if miner_chain else list(MINER_CHAIN)
    return (
        "# GENERATED by scripts/run_model_upgrade.py -- DO NOT HAND-EDIT.\n"
        "# Single source of truth for the desk's model fallback chains (libs/ops/model_chain.py).\n"
        "# Sourced by ops/brain_env.sh + every ops/ organ; imported by python organs.\n"
        "# Order IS the policy: head is consumed to exhaustion, then the desk walks down. Every\n"
        "# step past the head pages the principal via brain_auth_check.\n"
        "#\n"
        "# TWO SEATS (principal 2026-08-12): OPUS 5 for all things; FABLE only for the miner /\n"
        "# data-collection family. The two pools are spent in PARALLEL rather than in series, so\n"
        "# neither is the desk's single point of starvation. Seat membership is data --\n"
        "# libs.ops.model_chain.MINER_ORGANS -- never a per-script export.\n"
        f"# last change: {sealed}\n"
        f"# reason: {reason}\n"
        f'export _BRAIN_MODEL_CHAIN="{" ".join(chain)}"\n'
        f'export _MINER_MODEL_CHAIN="{" ".join(miner)}"\n'
        f'export ANTHROPIC_MODEL="${{ANTHROPIC_MODEL:-{chain[0]}}}"\n'
    )
