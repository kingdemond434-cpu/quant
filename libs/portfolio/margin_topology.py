"""MARGIN TOPOLOGY (L1.64) -- the book's capital structure is a decision, not an inheritance.

WHAT THIS ASKS THAT NOTHING ELSE ON THE DESK DOES. The only deployed sleeve runs inside ONE
margin construction -- long spot in the spot wallet, short USDT-M perp in a separately-margined
futures wallet -- and that construction was never chosen. It fell out of which connectors were
built first (`binance_spot_testnet` + `binance_testnet`: one venue, two wallets). Every fence and
incident repair since has asked "is the accounting right GIVEN the topology" -- R0053 (multi-asset
mode valued $5,000 of USDC at zero and disarmed the ruin rail), R0234 (LIVE equity undercount),
the 07-13 NOMUSDT fire (the wallet holding the short cannot see the hedge, so a -$55 book read as
-40.9%), the 07-19 dead-man cross-wallet accounting break -- and not one asked "is the topology
right". That is the L1.55 distinction (a restraint CHOSEN vs INHERITED) applied to the capital
structure itself, and the L1.45 cycle-blindness shape: every repair individually correct, the
cycle they orbit never questioned.

THE ONE PLACE EFFICIENCY *WAS* MODELLED PROVES THE POINT. `run_capital_plan.py` carried
`_PM_EFFICIENCY = 1.8` -- a hardcoded Portfolio-Margin multiplier applied at every capital level
including the $3,846 seed, where its own `pm_steps` note says PM has an eligibility floor. The
desk modelled only the construction it cannot use at seed, at a value nobody measured, while the
two constructions it CAN use today (Multi-Assets Mode; COIN-M 1x self-collateralised inverse)
were modelled nowhere: `multiAssetsMargin` appears in this repo exclusively as an equity-
accounting hazard. A constant wearing a measurement's clothes (L1.57 family), publishing fiction
to the principal-facing capital plan.

THE ARITHMETIC THAT WAS NEVER WRITTEN DOWN. Let L be the venue leverage the executor actually
sets (3, `run_cashcarry_executor` `fut.set_leverage(sym, 3)` -- pinned by a regression test).
Per $1 of delta-neutral carry notional the inherited construction consumes $1 (spot leg, fully
funded) + $1/L (short-leg initial margin): notional_per_equity = 1/(1 + 1/L) = 0.75. A
self-collateralised construction -- the long leg itself margins the short, either as Multi-Assets
collateral or as the coin backing a COIN-M 1x inverse short -- consumes only the long leg:
notional_per_equity ~= 1.0, a +33% capacity multiplier at identical equity. And liquidation moves
FURTHER away, not closer: the collateral appreciates in lockstep with the short's loss, which at
COIN-M 1x makes the liquidation price literally unreachable (the desk's own mined evidence:
8btc thread-172717, card 31 -- testnet liq price rendered as 一亿, i.e. effectively infinity).
Meanwhile `data/leverage_target.json` carries growth_optimal 2.25 and ruin_cap 2.05: the sizing
ladder's own top rungs are STRUCTURALLY UNREACHABLE under a 0.75x topology ceiling. The sizing
law and the capital structure had never been in the same room.

WHAT THIS MODULE IS. A pure comparator: one row per construction available on the venue(s) the
desk already trades, each carrying the measured `notional_per_equity`, liquidation reachability,
universe coverage, funding book, eligibility floor and the forward-evidence restart a switch
would cost (L2.10). The fence (`scripts/check_margin_topology.py`) grades the LIVE construction
DECIDED / DECIDED-STALE / DIVERGED / INHERITED / UNMEASURED and prices the gap per L1.51.

WHAT THIS IS NOT. It sizes nothing, lifts nothing, promotes nothing and touches no rail. The
SWITCH is a principal-grade act: it restarts forward evidence (L2.10), so the artifact prices
that restart rather than pretending it is free. UNMEASURED is a real answer throughout (L1.28a):
a construction whose venue terms have not been read is listed and refused, never guessed -- and a
decision recorded against ZERO measured alternatives is not a decision, it is paperwork.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

#: The venue leverage the executor actually sets on every short leg. MIRROR, NOT AUTHORITY:
#: the authority is `fut.set_leverage(sym, 3)` in scripts/run_cashcarry_executor.py, and
#: tests/portfolio/test_margin_topology.py greps that source so drift turns the suite red.
EXECUTOR_VENUE_LEVERAGE = 3.0

#: Canonical capital levels for eligibility grading. AUTHORITY MOVED HERE from
#: run_capital_plan.py (which now imports it) so the plan and the comparator cannot disagree
#: about which equity rungs the desk plans at.
CAPITAL_LEVELS: tuple[float, ...] = (3_846.0, 25_000.0, 100_000.0, 500_000.0, 2_000_000.0)

#: The construction the deployed sleeve actually runs. STRUCTURAL, not configured: the executor
#: manages a spot wallet and a separately-margined USDT-M cross wallet, with multiAssetsMargin
#: =False as the accounting baseline every equity reader defends against (libs/execution/
#: collateral.py, R0053). A decision row that names anything else is a DIVERGED verdict.
CURRENT_CONSTRUCTION = "split_spot_usdtm"

MEASURED = "MEASURED"
UNMEASURED = "UNMEASURED"
INELIGIBLE_LISTED = "INELIGIBLE-LISTED"

#: Top-level statuses. Exactly one passes the fence.
DECIDED = "DECIDED"
DECIDED_STALE = "DECIDED-STALE"
DIVERGED = "DIVERGED"
INHERITED = "INHERITED"
TOP_UNMEASURED = UNMEASURED

#: Equity growth that re-opens a construction decision (L1.28c: eligibility is information-
#: arrival bound, and NAV doubling is the arrival). A decision made at $X is stale at $2X.
DECISION_STALE_EQUITY_RATIO = 2.0


@dataclass(frozen=True)
class ConstructionRow:
    """One margin construction, measured or refused -- never guessed."""

    key: str
    label: str
    status: str                          # MEASURED | UNMEASURED | INELIGIBLE-LISTED
    notional_per_equity: float | None    # harvestable carry notional per $1 desk equity
    npe_basis: str                       # the arithmetic + term provenance, or why absent
    liq_unreachable: bool | None         # can the venue liquidate a rally-side move at all?
    liq_note: str
    universe_coverage: float | None      # fraction of the USDT-M carry universe runnable
    coverage_basis: str
    funding_book: str                    # which funding stream the short leg harvests
    eligibility_floor_usd: float | None  # min equity to enable; None = no known floor
    eligibility_basis: str
    forward_evidence_restart: bool       # switching restarts forward clocks (L2.10)
    next_action: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def split_wallet_npe(venue_leverage: float) -> float:
    """Notional per $1 equity for the inherited construction: $1 spot + $1/L short margin."""
    if venue_leverage <= 0:
        raise ValueError(f"venue_leverage must be positive, got {venue_leverage}")
    return 1.0 / (1.0 + 1.0 / venue_leverage)


def multi_assets_npe(haircut: float, venue_leverage: float) -> float:
    """Notional per $1 equity when the long coin itself is Multi-Assets collateral.

    Delta-neutrality pins long value == short notional, so per $1 notional the desk holds the $1
    coin; the short's initial margin (1/L) is covered by the coin's collateral value h. When
    h >= 1/L the coin margins its own hedge and npe = 1.0. When h < 1/L the shortfall must be
    posted in stables on top of the coin: equity per notional = 1 + (1/L - h).
    """
    if not 0.0 <= haircut <= 1.0:
        raise ValueError(f"haircut must be in [0, 1], got {haircut}")
    im = 1.0 / venue_leverage
    shortfall = max(0.0, im - haircut)
    return 1.0 / (1.0 + shortfall)


def coinm_inverse_npe() -> float:
    """COIN-M 1x self-collateralised inverse short: the coin IS the margin. Exactly 1.0.

    The short's coin-denominated PnL offsets the collateral's USD move one-for-one, which is why
    the liquidation price is unreachable (card 31's mined testnet experiment: liq = 一亿).
    """
    return 1.0


def build_rows(terms: dict[str, Any] | None, *,
               venue_leverage: float = EXECUTOR_VENUE_LEVERAGE) -> list[ConstructionRow]:
    """One row per construction. `terms` is data/margin_topology_terms.json (or None).

    Every row a term cannot support is UNMEASURED with the collection step named -- absence
    never resolves to a clean number (L1.28a), and ineligible constructions stay LISTED rather
    than dropping out of the denominator (L1.60).
    """
    t = terms or {}
    rows: list[ConstructionRow] = []

    # (a) the inherited construction -- measured from the executor's own constants, always.
    rows.append(ConstructionRow(
        key="split_spot_usdtm", label="spot wallet + separately-margined USDT-M short (LIVE)",
        status=MEASURED,
        notional_per_equity=round(split_wallet_npe(venue_leverage), 4),
        npe_basis=(f"1/(1 + 1/L) at the executor's own venue leverage L={venue_leverage:g} "
                   "(run_cashcarry_executor fut.set_leverage). Excludes the top-up buffer the "
                   "split wallet needs because the short's wallet cannot see the hedge, so this "
                   "is the construction's UPPER bound."),
        liq_unreachable=False,
        liq_note=("short liquidates on a rally unless the futures wallet is topped up in time -- "
                  "the 07-13 NOMUSDT class. The venue-side stop at +35% exists for exactly this."),
        universe_coverage=1.0,
        coverage_basis="definitionally the current USDT-M carry universe",
        funding_book="USDT-M",
        eligibility_floor_usd=None,
        eligibility_basis="live today; no venue floor",
        forward_evidence_restart=False,
        next_action="none -- this is the construction the book runs",
    ))

    # (b) Multi-Assets Mode: the long coin sits in the futures wallet as collateral.
    ma = t.get("multi_assets_collateral")
    universe = t.get("usdtm_perp_bases")
    if isinstance(ma, dict) and ma:
        ratios = sorted(float(v) for v in ma.values())
        med = ratios[len(ratios) // 2]
        worst = ratios[0]
        if isinstance(universe, list) and universe:
            covered = sorted(set(ma) & set(universe))
            coverage: float | None = round(len(covered) / len(universe), 4)
            cov_basis = (f"{len(covered)}/{len(universe)} USDT-M carry bases on the venue's "
                         f"Multi-Assets collateral list (as_of {t.get('as_of', '?')})")
        else:
            coverage, cov_basis = None, "collateral list read but USDT-M universe term absent"
        rows.append(ConstructionRow(
            key="multi_assets_usdtm", label="Multi-Assets Mode: coin collateral backs the short",
            status=MEASURED,
            notional_per_equity=round(multi_assets_npe(med, venue_leverage), 4),
            npe_basis=(f"self-collateralised at the venue's median collateral ratio {med:g} "
                       f"(worst listed {worst:g}); per-name npe = 1/(1 + max(0, 1/L - h))"),
            liq_unreachable=True,
            liq_note=("collateral appreciates in lockstep with the short's loss; net margin "
                      "drawdown per +x rally ~= x*(1-h), so the boundary recedes as the venue's "
                      "haircut approaches 1"),
            universe_coverage=coverage, coverage_basis=cov_basis,
            funding_book="USDT-M",
            eligibility_floor_usd=0.0,
            eligibility_basis="account-mode toggle; no equity floor on the venue's public terms",
            forward_evidence_restart=True,
            next_action="decision row required before any switch (L1.64); shadow-first",
        ))
    else:
        rows.append(ConstructionRow(
            key="multi_assets_usdtm", label="Multi-Assets Mode: coin collateral backs the short",
            status=UNMEASURED,
            notional_per_equity=None,
            npe_basis="venue collateral-ratio table not on disk -- npe is haircut-dependent",
            liq_unreachable=True,
            liq_note="structural: collateral appreciates with the short's loss",
            universe_coverage=None,
            coverage_basis="needs the venue's Multi-Assets collateral list",
            funding_book="USDT-M",
            eligibility_floor_usd=None,
            eligibility_basis="account-mode toggle; floor unknown until terms read",
            forward_evidence_restart=True,
            next_action=("collect the Multi-Assets collateral-ratio table into "
                         "data/margin_topology_terms.json (check_margin_topology --collect; "
                         "keyless endpoints tried and recorded, else a keyed/manual dated read)"),
        ))

    # (c) COIN-M 1x self-collateralised inverse short.
    cm = t.get("coinm_perp_bases")
    if isinstance(cm, list) and cm and isinstance(universe, list) and universe:
        covered = sorted(set(cm) & set(universe))
        rows.append(ConstructionRow(
            key="coinm_inverse_1x", label="COIN-M 1x inverse short, coin-margined",
            status=MEASURED,
            notional_per_equity=coinm_inverse_npe(),
            npe_basis="the coin IS the margin at 1x; equity per $1 notional is that $1 coin",
            liq_unreachable=True,
            liq_note=("liquidation price unreachable by construction at 1x -- the desk's own "
                      "mined testnet evidence (8btc thread-172717, card 31: liq rendered 一亿)"),
            universe_coverage=round(len(covered) / len(universe), 4),
            coverage_basis=(f"{len(covered)}/{len(universe)} USDT-M carry bases with a live "
                            f"COIN-M perp (as_of {t.get('as_of', '?')})"),
            funding_book="COIN-M",
            eligibility_floor_usd=0.0,
            eligibility_basis="live product; per-name availability is the real constraint",
            forward_evidence_restart=True,
            next_action=("funding differential vs USDT-M per name is UNMEASURED until the R0462 "
                         "COIN-M funding backfill lands -- this row is its first money-path "
                         "consumer"),
        ))
    else:
        rows.append(ConstructionRow(
            key="coinm_inverse_1x", label="COIN-M 1x inverse short, coin-margined",
            status=UNMEASURED,
            notional_per_equity=None,
            npe_basis="arithmetic is exact (1.0) but per-name availability unread -- refusing "
                      "to publish a number whose universe is unknown",
            liq_unreachable=True,
            liq_note="structural at 1x",
            universe_coverage=None,
            coverage_basis="needs COIN-M perp roster x USDT-M carry universe",
            funding_book="COIN-M",
            eligibility_floor_usd=None,
            eligibility_basis="live product; roster unread",
            forward_evidence_restart=True,
            next_action="check_margin_topology --collect (keyless dapi/fapi exchangeInfo)",
        ))

    # (d) Portfolio Margin -- the construction the deleted 1.8 constant pretended to measure.
    pm_npe = t.get("pm_npe")
    pm_floor = t.get("pm_min_equity_usd")
    if isinstance(pm_npe, (int, float)) and isinstance(pm_floor, (int, float)):
        rows.append(ConstructionRow(
            key="portfolio_margin", label="Portfolio Margin cross-collateral",
            status=MEASURED,
            notional_per_equity=round(float(pm_npe), 4),
            npe_basis=f"venue PM terms as_of {t.get('as_of', '?')} ({t.get('pm_source', '?')})",
            liq_unreachable=False,
            liq_note="cross-margined pair; boundary set by the venue's PM risk model",
            universe_coverage=1.0,
            coverage_basis="same USDT-M instrument set, cross-margined -- coverage is "
                           "structural, not a roster read",
            funding_book="USDT-M",
            eligibility_floor_usd=float(pm_floor),
            eligibility_basis=str(t.get("pm_source", "venue terms")),
            forward_evidence_restart=True,
            next_action="eligibility clock: re-grade on every NAV doubling (L1.28c)",
        ))
    else:
        rows.append(ConstructionRow(
            key="portfolio_margin", label="Portfolio Margin cross-collateral",
            status=UNMEASURED,
            notional_per_equity=None,
            npe_basis=("the retired _PM_EFFICIENCY=1.8 constant had no derivation in the repo "
                       "and is NOT carried forward -- a constant is not a measurement (L1.46)"),
            liq_unreachable=False,
            liq_note="cross-margined pair; boundary set by the venue's PM risk model",
            universe_coverage=None,
            coverage_basis="unread",
            funding_book="USDT-M",
            eligibility_floor_usd=None,
            eligibility_basis="min-equity floor unread; the seed level is presumptively below it",
            forward_evidence_restart=True,
            next_action=("record {pm_npe, pm_min_equity_usd, pm_source, as_of} in "
                         "data/margin_topology_terms.json from the venue's PM terms page -- a "
                         "dated read, never a constant"),
        ))

    # (e) Bybit UTA netting -- cross-venue competitor; tape already archived, terms unread.
    rows.append(ConstructionRow(
        key="bybit_uta", label="Bybit unified account (UTA) spot+perp netting",
        status=UNMEASURED,
        notional_per_equity=None,
        npe_basis="UTA margin terms unread",
        liq_unreachable=None,
        liq_note="depends on UTA collateral haircuts, unread",
        universe_coverage=None,
        coverage_basis="Bybit perp roster x carry universe unread",
        funding_book="USDT-M (Bybit)",
        eligibility_floor_usd=None,
        eligibility_basis="requires venue onboarding -- a principal act",
        forward_evidence_restart=True,
        next_action=("read UTA margin/haircut terms into the terms artifact; the desk already "
                     "archives Bybit L2 tape, so the data moat half exists"),
    ))
    return rows


def eligible_at(row: ConstructionRow, equity_usd: float) -> bool:
    """A construction is eligible at a level when its floor is known and cleared."""
    return (row.status == MEASURED and row.eligibility_floor_usd is not None
            and equity_usd >= row.eligibility_floor_usd)


def blended_npe(row: ConstructionRow, current_npe: float) -> float | None:
    """BOOK-level notional_per_equity: the covered slice runs on `row`, the rest stays on the
    inherited construction.

    THE OVERCLAIM THIS PREVENTS, caught on this module's own first consumer run: COIN-M 1x is
    npe=1.0 PER COVERED NAME but covers 3.8% of the carry universe -- publishing 1.0 as the
    book's efficiency would swap the 1.8 fiction for a 1.0 fiction. A +33% construction on 4%
    of names is a +1.3% book, and every book-level number says so. Unknown coverage blends
    nothing (L1.28a): a multiplier over an unread universe is not a measurement.
    """
    if row.notional_per_equity is None or row.universe_coverage is None:
        return None
    cov = row.universe_coverage
    return round(cov * row.notional_per_equity + (1.0 - cov) * current_npe, 6)


def level_table(rows: list[ConstructionRow],
                levels: tuple[float, ...] = CAPITAL_LEVELS) -> list[dict[str, Any]]:
    """Best MEASURED+eligible BOOK-level npe per capital level -- the capital plan's input.

    The inherited construction needs no eligibility term (it is live), so it is always the
    floor; UNMEASURED rows contribute nothing (L1.28a) rather than a hoped-for multiplier, and
    every candidate is coverage-blended (see `blended_npe`) so a narrow construction can never
    lend the whole book its per-name multiplier.
    """
    out: list[dict[str, Any]] = []
    current = next((r for r in rows if r.key == CURRENT_CONSTRUCTION), None)
    cur_npe = current.notional_per_equity if current else None
    for lvl in levels:
        best_key, best_npe = None, None
        for r in rows:
            if cur_npe is None:
                break
            if r.key == CURRENT_CONSTRUCTION:
                npe: float | None = r.notional_per_equity
            elif eligible_at(r, lvl):
                npe = blended_npe(r, cur_npe)
            else:
                npe = None
            if npe is not None and (best_npe is None or npe > best_npe):
                best_key, best_npe = r.key, npe
        out.append({
            "capital_usd": lvl,
            "best_construction": best_key,
            "best_npe": best_npe,
            "npe_basis": "coverage-blended book-level npe (blended_npe)",
            "current_npe": cur_npe,
            "n_unmeasured_at_level": sum(1 for r in rows if r.status == UNMEASURED),
        })
    return out


def grade(rows: list[ConstructionRow], decision: dict[str, Any] | None, *,
          current_key: str = CURRENT_CONSTRUCTION,
          equity_now_usd: float | None = None,
          equity_basis: str = "UNMEASURED") -> tuple[str, str]:
    """(status, why) for the live construction. Exactly one status passes the fence.

    DECIDED        -- a decision row exists, names the construction the book actually runs, was
                      made against >=1 MEASURED alternative, and equity has not doubled since.
    DECIDED-STALE  -- decided, but equity >= 2x the decision's equity (L1.28c re-fire).
    DIVERGED       -- the decision names a construction the book does not run (L1.61 class).
    INHERITED      -- no decision row: the book runs a construction nobody chose. FAILING.
    UNMEASURED     -- no rows at all, or a decision recorded against zero measured
                      alternatives -- paperwork, not a comparison (L1.28a).
    """
    if not rows:
        return TOP_UNMEASURED, "no construction rows built -- nothing to decide against (L1.28a)"
    n_measured_alts = sum(1 for r in rows if r.status == MEASURED and r.key != current_key)
    if decision is None:
        return INHERITED, (
            f"the book runs {current_key} and no decision row exists -- the construction was "
            "inherited from connector order, never chosen. Write data/margin_topology_decision"
            ".json {construction, decided_at, decided_by, equity_at_decision_usd, evidence} "
            "after reading data/margin_topology.json; KEEP-CURRENT is a legitimate verdict.")
    decided = str(decision.get("construction", ""))
    if decided != current_key:
        return DIVERGED, (
            f"decision row names {decided!r} but the book runs {current_key!r} -- either the "
            "switch never executed or the row is fiction; reconcile before trusting either")
    if n_measured_alts < 1:
        return TOP_UNMEASURED, (
            "decision row exists but ZERO alternatives are MEASURED -- a decision against "
            "unmeasured alternatives is paperwork, not a comparison (L1.28a)")
    at = decision.get("equity_at_decision_usd")
    if (isinstance(at, (int, float)) and at > 0 and equity_now_usd is not None
            and equity_now_usd >= DECISION_STALE_EQUITY_RATIO * float(at)):
        return DECIDED_STALE, (
            f"decided at ${float(at):,.0f}, equity now ${equity_now_usd:,.0f} "
            f"({equity_basis}) -- eligibility is information-arrival bound and NAV doubling is "
            "the arrival (L1.28c); re-run the comparison and re-decide")
    return DECIDED, (f"decided {decision.get('decided_at', '?')} "
                     f"by {decision.get('decided_by', '?')}")


def price_uplift(rows: list[ConstructionRow], *,
                 current_key: str = CURRENT_CONSTRUCTION,
                 equity_usd: float | None,
                 equity_basis: str,
                 cagr_validated: float,
                 cagr_if_validated: float) -> dict[str, Any]:
    """L1.51 pricing of the inherited clamp -- what staying un-decided costs, both rungs.

    Refuses dollar figures on a molded paper book (L1.51: a cost from a simulated denominator is
    worse than no number); rates per $10k are published instead, because a rate is honest
    without a real book.
    """
    cur = next((r for r in rows if r.key == current_key), None)
    if cur is None or cur.notional_per_equity is None:
        return {"status": UNMEASURED, "why": "current construction row missing or unmeasured"}
    paper = "PAPER" in equity_basis.upper() or "MOLDED" in equity_basis.upper()
    alts = []
    for r in rows:
        if r.key == current_key or r.notional_per_equity is None:
            continue
        book = blended_npe(r, cur.notional_per_equity)
        # the BOOK delta is what the desk would actually harvest; the per-name multiplier is
        # real but only on the covered slice, and both are published so neither can pose as
        # the other. No coverage term -> no book claim (L1.28a).
        delta = (book - cur.notional_per_equity) if book is not None else 0.0
        alt: dict[str, Any] = {
            "construction": r.key,
            "structural_multiplier": round(r.notional_per_equity / cur.notional_per_equity, 4),
            "structural_basis": "per COVERED name -- applies to the covered slice only",
            "book_multiplier": (round(book / cur.notional_per_equity, 4)
                                if book is not None else None),
            "universe_coverage": r.universe_coverage,
            "delta_notional_per_equity": round(delta, 4),
            # None when equity is unknown -- eligibility is a claim about a specific book size
            "eligible_at_current_equity": (eligible_at(r, equity_usd)
                                           if equity_usd is not None else None),
            "liq_direction": ("liquidation risk FALLS with the raise" if r.liq_unreachable
                              else "liquidation profile changes -- read the row"),
            # both rungs, always (L1.51): the validated rung is honestly $0 until the forward
            # shadow validates; the conservative rung is what the plan itself would use then.
            "usd_per_day_at_validated_cagr": (
                None if paper or equity_usd is None
                else round(equity_usd * delta * cagr_validated / 365.0, 2)),
            "usd_per_day_if_validated": (
                None if paper or equity_usd is None
                else round(equity_usd * delta * cagr_if_validated / 365.0, 2)),
            "per_10k_usd_per_day_if_validated": round(10_000.0 * delta * cagr_if_validated
                                                      / 365.0, 2),
        }
        if paper:
            alt["usd_basis"] = ("UNMEASURABLE-PAPER-BOOK -- equity is a molded/simulated curve; "
                                "dollar figures refused (L1.51), rates per $10k published")
        alts.append(alt)
    return {"status": MEASURED if alts else UNMEASURED,
            "why": ("priced against the current construction" if alts
                    else "no measured alternative to price against -- run --collect"),
            "equity_basis": equity_basis,
            "current_npe": cur.notional_per_equity,
            # eligible-now alternatives outrank larger-but-locked ones (L1.18a's deployment
            # race), and the BOOK multiplier outranks the per-name one -- a large multiplier on
            # a sliver must not headline over a small one on the whole book.
            "alternatives": sorted(alts, key=lambda a: (
                a["eligible_at_current_equity"] is False,
                a["book_multiplier"] is None,
                -(a["book_multiplier"] or 0.0),
                -a["structural_multiplier"]))}
