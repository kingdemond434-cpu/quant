"""THE SOUTH-AMERICA INTERACTION MINER: local state as a SENSOR, not only as a thing to trade.

THE PRINCIPAL'S ORDER (2026-09-17) IS THE WHOLE DESIGN. South America is a regional research
civilization connecting FX, commodities, rates, capital controls, agriculture and China-sensitive
trade -- and its local states are SENSORS for XAUUSD, XAGUSD, oil, AUD, the JPY crosses, the USD
pairs and the global indices, beyond the local instruments. That matters most where the local
instrument does not exist: USDCLP, USDPEN, USDARS and USDCOP are absent from this broker, so the
Chilean copper state, the Argentine brecha and the Colombian coffee formula can ONLY ever be
sensors here. Refusing to mine them because they are not tradable would throw away the half of
the continent that is most informative.

WHAT THIS FILE IS. Two things, and they are different objects:

    FAMILIES        one per declared mechanism, each recording a DISCOVERY in the moat registry
                    with generator `latam:<family>` and `payload.region` set to the country the
                    mechanism belongs to. The compiler turns those into cells; nothing here
                    compiles anything itself. A family is a HYPOTHESIS with a falsifier, and it
                    is recorded whether or not this box can measure it today.

    CROSS-REGION    three named triples that each need a leg from ANOTHER command. Saudi liquidity
    TRIPLES         x an oil shock x the Brazilian commodity state; Chile/Peru copper x the
                    Chinese demand state x Korean semiconductor exports; Brazilian rates x the
                    Japanese carry state x USD volatility. Each names the artifact it reads, and
                    when that artifact is not on this box the triple is UNMEASURED BY NAME rather
                    than dropped -- because a triple that vanishes when a leg is missing is
                    indistinguishable from a triple nobody wrote.

THE SCREEN IS CONDITIONAL AND ITS NULL PERMUTES THE CONDITION. A triple's claim is never "X leads
Y"; it is "X leads Y WHEN Z is in a particular state". Testing that with an unconditional
correlation measures the wrong thing, and testing it with a conditional correlation against a
normal-theory p-value ignores that the condition itself is autocorrelated -- a state that persists
for months gives far fewer independent observations than its row count suggests. So the null
PERMUTES THE CONDITION LABELS and recomputes the conditional statistic, which asks exactly the
right question: how often does a randomly placed state of the same size produce a conditional
lead this large? Nothing else in this file is subtle; this is.

A SCREEN IS NOT A VERDICT. Everything here is a SCREEN in the sense the desk uses the word: it
ranks and it triages, and the gauntlet judges. A family that screens well is a candidate for
trials, not an edge.

    python desks/mt5/research/south_america_interaction.py
    python desks/mt5/research/south_america_interaction.py --dry-run   # writes NOTHING
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = BASE / "reports" / "SOUTH_AMERICA_INTERACTION.json"
COUNTRIES = BASE / "research" / "countries"

OK, UNMEASURED, BLOCKED = "ok", "UNMEASURED", "BLOCKED"

#: The generator prefix every discovery this file writes carries. The compiler groups by it and
#: `generator_yields` measures the whole command's conversion by it, so it is one token and it
#: never changes.
GENERATOR_PREFIX = "latam"

#: Screen constants, stated once so a reader and a test read the same numbers.
MIN_N = 24                  # below this a conditional screen is POORLY_MEASURED, never a verdict
MIN_CONDITION_N = 8         # a conditional statistic needs this many days inside the state
N_PERM = 500                # permutation draws; the null permutes the CONDITION, never returns
P_MAX = 0.05
DEFAULT_LAGS: tuple[int, ...] = (1, 2, 3, 5, 10)

RULE = ("local South American state is mined as a SENSOR for the instruments this desk can "
        "actually trade; a family is a hypothesis with a falsifier, a cross-region triple whose "
        "leg is absent is UNMEASURED BY NAME, and every screen's null permutes the CONDITION "
        "rather than the returns")


# --------------------------------------------------------------------------- the families
#: EVERY DECLARED MECHANISM, AS DATA. `region` is the country code the mechanism belongs to and
#: becomes `payload.region` on the discovery; `symbols` are broker symbols and every one of them
#: is in `desks/mt5/data/universe/universe.json`. `sensor_for` is the principal's instruction made
#: explicit: what this local state is being read as evidence ABOUT, beyond the local instrument.
FAMILIES: tuple[dict[str, Any], ...] = (
    {"id": "br_carry_rates", "region": "br", "country": "Brazil",
     "mechanism": "Brazilian real-rate differential and its carry position",
     "information": "carry", "sensor_for": ("XAUUSD", "USDJPY", "AUDJPY"),
     "symbols": ("USDBRL", "USDMXN", "USDZAR", "XAUUSD", "AUDJPY"),
     "state": "the Selic-Fed differential and the carry-to-vol ratio",
     "rationale": "the largest funded carry position in EM FX; its unwind is a GLOBAL "
                  "dollar-funding event rather than a Brazilian one, so the Brazilian state is "
                  "evidence about gold and the yen crosses and not only about the real",
     "falsifier": "USDBRL drawdowns cluster no more with other high-carry EM crosses than with "
                  "zero-carry crosses of the same volatility, once the dollar factor is removed"},
    {"id": "br_commodity_demand", "region": "br", "country": "Brazil",
     "mechanism": "Brazilian terms of trade -- iron ore, crude and the safra in one current "
                  "account",
     "information": "macro", "sensor_for": ("AUDUSD", "XCUUSD", "USDCNH"),
     "symbols": ("USDBRL", "SOYBEAN", "SUGAR", "XCUUSD", "XTIUSD", "AUDUSD"),
     "state": "export volumes by chapter against the commodity index in BRL",
     "rationale": "Brazil and Australia sell the same Chinese demand; a Brazilian volume state is "
                  "therefore information about that demand, and AUD is where it is liquid",
     "falsifier": "no Brazilian terms-of-trade sensitivity in AUDUSD once the dollar factor and "
                  "Chinese equity risk are controlled for"},
    {"id": "br_foreign_flow", "region": "br", "country": "Brazil",
     "mechanism": "fluxo cambial: exporter conversion against dividend repatriation",
     "information": "macro", "sensor_for": ("USDBRL", "US500"),
     "symbols": ("USDBRL", "SOYBEAN", "CORN", "US500"),
     "state": "the commercial and financial legs SEPARATELY; the net hides both",
     "rationale": "two forced flows on OPPOSITE calendars; the net series that everyone quotes "
                  "cannot see either of them",
     "falsifier": "no seasonal difference in USDBRL between the safra and repatriation windows "
                  "once the global dollar's own January seasonal is removed"},
    {"id": "br_risk_state", "region": "br", "country": "Brazil",
     "mechanism": "Brazilian fiscal risk as the conditioning state for the carry",
     "information": "macro", "sensor_for": ("USDMXN", "USDZAR", "US2000"),
     "symbols": ("USDBRL", "USDMXN", "USDZAR", "US2000", "XAUUSD"),
     "state": "fiscal announcements, the primary result and the local real rate",
     "rationale": "carry pays in a stable fiscal state and does not in a deteriorating one; the "
                  "unconditional carry cell is two different trades averaged together",
     "falsifier": "the carry's return distribution is the same in both fiscal states"},
    {"id": "cl_pe_copper_cycle", "region": "cl", "country": "Chile and Peru",
     "mechanism": "Andean copper supply acceleration conditioned on the Chinese demand state",
     "information": "cross_asset", "sensor_for": ("AUDUSD", "XAUUSD", "US500"),
     "symbols": ("XCUUSD", "AUDUSD", "USDCNH", "CHINAH", "XAUUSD"),
     "state": "a DISCRETE supply state (expanding, flat, contracting) against a China state",
     "rationale": "supply and demand shocks have OPPOSITE price-quantity signatures; pooling them "
                  "measures neither, and the conditional form is the whole hypothesis",
     "falsifier": "copper's relationship to AUD and to risk is the same in every China state, "
                  "which would make the conditioning worthless"},
    {"id": "cl_pe_mining_shock", "region": "cl", "country": "Chile and Peru",
     "mechanism": "scheduled Chilean strike windows and unscheduled Peruvian blockades",
     "information": "event", "sensor_for": ("XCUUSD", "XAGUSD", "XAUUSD"),
     "symbols": ("XCUUSD", "XZNUSD", "XAGUSD", "AUDUSD"),
     "state": "an announced-risk window versus an unannounced disruption",
     "rationale": "the two countries supply the scheduled and unscheduled halves of one event "
                  "class, which is the identification: anticipation versus surprise",
     "falsifier": "no copper response around either class relative to matched control windows"},
    {"id": "cl_pe_fx_stress", "region": "cl", "country": "Chile and Peru",
     "mechanism": "Andean currency stress read through the metal, because the currencies are "
                  "absent here",
     "information": "cross_asset", "sensor_for": ("AUDUSD", "XAUUSD", "US500"),
     "symbols": ("XCUUSD", "AUDUSD", "USDBRL", "XAUUSD", "US500"),
     "state": "political and intervention episodes in Chile (free float) and Peru (managed)",
     "rationale": "CLP is the crowded copper expression, so a Chilean political shock unwinds a "
                  "POSITION that is also in copper; Peru's managed sol is the control",
     "falsifier": "copper shows no abnormal move around Chilean political events that do not "
                  "affect mine output"},
    {"id": "ar_dislocation", "region": "ar", "country": "Argentina",
     "mechanism": "the official-versus-parallel brecha as a capital-control state",
     "information": "macro", "sensor_for": ("USDBRL", "USDMXN", "XAUUSD"),
     "symbols": ("USDBRL", "USDMXN", "USDZAR", "USDTRY", "XAUUSD"),
     "state": "a DECLARED band (convertible, managed, cepo_light, cepo_hard, cepo_extreme) with "
              "dated transitions",
     "rationale": "capital-control intensity is a dummy variable everywhere else and a daily "
                  "published series here; it is the extreme case that should LEAD the milder ones",
     "falsifier": "brecha widening episodes carry no information for EM peers beyond the global "
                  "dollar move on the same days"},
    {"id": "ar_reserve_stress", "region": "ar", "country": "Argentina",
     "mechanism": "reserve depletion and the hazard of a regime transition",
     "information": "macro", "sensor_for": ("XAUUSD", "USDTRY", "USDBRL"),
     "symbols": ("USDBRL", "USDTRY", "XAUUSD", "SOYBEAN"),
     "state": "gross reserves, the estimated gross-net gap and the transition history",
     "rationale": "every discrete devaluation in the sample was preceded by a measured drawdown; "
                  "the object is a TRANSITION PROBABILITY and not a level",
     "falsifier": "no relationship between measured depletion and the probability of a brecha "
                  "regime transition in the following quarter"},
    {"id": "ar_capital_controls", "region": "ar", "country": "Argentina",
     "mechanism": "the MEP-CCL spread as the price of cross-border settlement",
     "information": "macro", "sensor_for": ("USDBRL", "US2000", "XAUUSD"),
     "symbols": ("USDBRL", "US2000", "XAUUSD"),
     "state": "the spread between two routes of the same bond trade",
     "rationale": "the peso's level and the bond's credit move are common to both legs and "
                  "cancel; what is left is the pure cost of getting money out of a country",
     "falsifier": "the spread shows no relationship to measured outflow or to dated regulatory "
                  "tightening"},
    {"id": "ar_soy_shock", "region": "ar", "country": "Argentina",
     "mechanism": "retenciones and preferential FX windows timing world soybean-meal supply",
     "information": "event", "sensor_for": ("SOYBEAN", "CORN", "USDBRL"),
     "symbols": ("SOYBEAN", "CORN", "WHEAT", "USDBRL"),
     "state": "dated Boletin Oficial policy events and the DJVE registration burst after them",
     "rationale": "Argentina is the largest exporter of soybean meal and oil and its shipment "
                  "TIMING is a tax decision, so world supply moves on a policy date",
     "falsifier": "no abnormal soybean or meal behaviour after announced retenciones changes "
                  "relative to matched non-event weeks"},
    {"id": "sa_agriculture_safra", "region": "br", "country": "South America (agriculture)",
     "mechanism": "the southern-hemisphere crop state: CONAB and USDA prints on a safra calendar",
     "information": "event", "sensor_for": ("SOYBEAN", "CORN", "SUGAR", "COFARA"),
     "symbols": ("SOYBEAN", "CORN", "SUGAR", "SUGARRAW", "COFARA", "COFROB", "USDBRL"),
     "state": "first-print crop estimates, the planting and harvest windows, weather episodes",
     "rationale": "two independent crop prints a month (CONAB and USDA on different dates) plus "
                  "Brazil and Argentina as substitute suppliers -- the identification is the "
                  "substitution, and COFROB is the built-in non-Brazilian coffee control",
     "falsifier": "no softs response to first-print crop revisions beyond the USDA print on the "
                  "same month, which would make CONAB redundant"},
    {"id": "mx_proxy_risk", "region": "mx", "country": "Mexico",
     "mechanism": "the peso as the world's EM hedge proxy",
     "information": "cross_asset", "sensor_for": ("US500", "USDBRL", "USDZAR"),
     "symbols": ("USDMXN", "MXNJPY", "USDBRL", "USDZAR", "US500"),
     "state": "global risk turns, measured against peer EM currencies with the same carry",
     "rationale": "when a fund cannot sell the asset it wants to hedge it sells the peso, so "
                  "USDMXN is a SENSOR for global risk appetite more than for Mexico",
     "falsifier": "USDMXN shows no excess sensitivity to global risk relative to USDBRL and "
                  "USDZAR once carry and volatility are controlled for"},
    {"id": "co_oil_coffee", "region": "co", "country": "Colombia",
     "mechanism": "Colombian crude supply interruptions and the published coffee formula",
     "information": "event", "sensor_for": ("XBRUSD", "COFARA"),
     "symbols": ("XBRUSD", "XTIUSD", "COFARA", "COFROB", "USDBRL"),
     "state": "a counted pipeline-interruption class and a farm-gate price that is an equation",
     "rationale": "the coffee price leg is PUBLISHED as a formula, so only the quantity leg is a "
                  "research question -- the cleanest price/quantity separation in the book",
     "falsifier": "internal coffee purchase volumes show no relationship to the published "
                  "reference once the harvest calendar is controlled for"},
)


# --------------------------------------------------------------------------- the cross-region legs
#: EACH LEG NAMES WHERE IT WOULD BE READ FROM. A leg that is absent is reported with the exact
#: paths that were looked at, because "UNMEASURED" with no address is not a measurement either.
LEG_SOURCES: dict[str, tuple[str, ...]] = {
    "br_commodity_state": ("desks/mt5/reports/SOUTH_AMERICA_BR_PLANE.json",
                           "desks/mt5/data/latam/br/"),
    "cl_pe_copper_state": ("desks/mt5/reports/SOUTH_AMERICA_CL_PLANE.json",
                           "desks/mt5/data/latam/cl/"),
    "ar_brecha_state": ("desks/mt5/reports/SOUTH_AMERICA_AR_PLANE.json",
                        "desks/mt5/data/latam/ar/"),
    "me_saudi_liquidity": ("desks/mt5/research/countries/sa/data_plane.py",
                           "desks/mt5/research/countries/ae/data_plane.py",
                           "desks/mt5/reports/MIDDLE_EAST_PLANE.json",
                           "desks/mt5/reports/SAUDI_LIQUIDITY.json"),
    "kr_semiconductor_nowcast": ("desks/mt5/research/countries/kr/nowcast.py",
                                 "desks/mt5/reports/KR_NOWCAST.json",
                                 "desks/mt5/data/intelligence/kr/"),
    "jp_carry_state": ("desks/mt5/research/japan/carry_state.py",
                       "desks/mt5/reports/JAPAN_CARRY_STATE.json",
                       "desks/mt5/reports/CARRY_STATE.json"),
    "cn_demand_state": ("desks/mt5/reports/ASIA_TRANSMISSION.json",
                        "desks/mt5/reports/ASIA_PLANE.json"),
    "usd_vol_state": ("desks/mt5/data/universe/USDX_H1.parquet",
                      "desks/mt5/data/axes/cot.json"),
}

#: THE THREE CROSS-REGION TRIPLES the principal named. Each is a CONDITIONAL claim: the driver
#: leads the target ONLY when the third leg is in a particular state. A triple with a missing leg
#: is UNMEASURED, and the missing leg is named.
TRIPLES: tuple[dict[str, Any], ...] = (
    {"id": "saudi_liquidity_x_oil_shock_x_br_commodity",
     "legs": ("me_saudi_liquidity", "usd_vol_state", "br_commodity_state"),
     "driver": "me_saudi_liquidity", "condition": "br_commodity_state",
     "targets": ("USDX", "XAUUSD", "US500", "XBRUSD"),
     "regions": ("mea", "latam"),
     "claim": "a Gulf liquidity impulse meeting an oil shock reaches the dollar, gold and global "
              "risk DIFFERENTLY depending on whether the Brazilian commodity state is expanding "
              "or contracting -- because the same oil move is a terms-of-trade gain for one "
              "commodity bloc and a cost shock for the other",
     "why_conditional": "an unconditional test averages a petro-surplus recycling channel with a "
                        "commodity-importer cost channel and finds neither",
     "falsifier": "the Gulf-liquidity-to-dollar relationship is identical in every Brazilian "
                  "commodity state, which would mean the South American leg carries no "
                  "information at all"},
    {"id": "cl_pe_copper_x_china_x_kr_semis",
     "legs": ("cl_pe_copper_state", "cn_demand_state", "kr_semiconductor_nowcast"),
     "driver": "cl_pe_copper_state", "condition": "cn_demand_state",
     "targets": ("AUDUSD", "USDJPY", "NAS100", "HK50", "XAUUSD"),
     "regions": ("latam", "asia"),
     "claim": "Andean copper acceleration conditioned on the Chinese demand state leads AUD, the "
              "yen crosses and the technology indices -- and the Korean semiconductor export "
              "nowcast is the independent confirmation that the demand state is real rather than "
              "a copper-specific supply story",
     "why_conditional": "copper alone cannot tell a supply squeeze from a demand impulse; Korea's "
                        "export print is a demand read with no copper supply in it, which is why "
                        "it is the third leg rather than a fourth target",
     "falsifier": "copper's lead over AUD and the indices is the same whatever the Chinese state, "
                  "or reverses out of sample"},
    {"id": "br_rates_x_jp_carry_x_usd_vol",
     "legs": ("br_commodity_state", "jp_carry_state", "usd_vol_state"),
     "driver": "br_commodity_state", "condition": "jp_carry_state",
     "targets": ("USDJPY", "AUDJPY", "USDBRL", "XAUUSD"),
     "regions": ("latam", "asia"),
     "claim": "the Brazilian rate state and the Japanese carry state are the two ends of the same "
              "funded position: when the yen funding leg tightens, the high-carry receiving leg "
              "unwinds, and the pair defines a CARRY-UNWIND REGIME that is neither Brazilian nor "
              "Japanese",
     "why_conditional": "the same Brazilian rate move is a carry build in one Japanese funding "
                        "state and a forced unwind in the other; averaging them is how a real "
                        "carry-unwind mechanism measures as noise",
     "falsifier": "the Brazilian rate state's relationship to the yen crosses is the same in "
                  "every Japanese carry state"},
)


# --------------------------------------------------------------------------- small helpers
def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _read_json(path: Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def resolve_leg(leg: str, *, root: Path | None = None) -> dict[str, Any]:
    """Is this cross-region leg on THIS box, and if not, exactly which paths were looked at?

    The paths are reported whether or not the leg resolves. An UNMEASURED with no address is not
    a measurement: the next session cannot act on it, and it reads identically to a leg nobody
    ever declared.
    """
    base = Path(root) if root is not None else ROOT
    paths = LEG_SOURCES.get(leg, ())
    found = [p for p in paths if (base / p).exists()]
    return {"leg": leg, "outcome": OK if found else UNMEASURED,
            "found": found, "looked_in": list(paths),
            "why": "" if found else f"{leg}: none of {list(paths)} is on this box, so the leg "
                                    f"carries no series and every triple that needs it is "
                                    f"UNMEASURED by name rather than dropped"}


# --------------------------------------------------------------------------- the screen
def _conditional_stat(driver: np.ndarray, target: np.ndarray, mask: np.ndarray,
                      lag: int) -> float:
    """Correlation of driver[t-lag] with target[t], restricted to days where the condition holds."""
    if lag < 1 or lag >= driver.size:
        return float("nan")
    x = driver[:-lag]
    y = target[lag:]
    m = mask[lag:]
    if m.sum() < MIN_CONDITION_N:
        return float("nan")
    xs = x[m]
    ys = y[m]
    if xs.size < MIN_CONDITION_N:
        return float("nan")
    sx = float(np.std(xs))
    sy = float(np.std(ys))
    if sx <= 0.0 or sy <= 0.0:
        return float("nan")
    return float(np.mean((xs - np.mean(xs)) * (ys - np.mean(ys))) / (sx * sy))


def conditional_lead_lag(driver: Any, target: Any, condition: Any, *,
                         lags: tuple[int, ...] = DEFAULT_LAGS, n_perm: int = N_PERM,
                         seed: int = 20260917) -> dict[str, Any]:
    """Does `driver` lead `target` WHEN `condition` holds, against a permuted-condition null?

    THE NULL PERMUTES THE CONDITION LABELS, and that choice is the whole statistical content of
    this function. Two alternatives are wrong in ways that matter here. Permuting the RETURNS
    destroys their autocorrelation and produces a null that is far too tight, so everything looks
    significant. A normal-theory p-value on the conditional correlation ignores that the condition
    is itself persistent -- a state that lasts for months supplies far fewer independent
    observations than its row count -- and is wrong in the same direction. Permuting the condition
    keeps both series exactly as they are and asks the honest question: how often does a randomly
    placed state of THE SAME SIZE produce a conditional lead this large?

    The best lag is chosen across `lags` and the null is computed over the SAME search, so the
    multiplicity of choosing a lag is inside the p-value rather than ignored.
    """
    d = np.asarray(driver, dtype=float).ravel()
    t = np.asarray(target, dtype=float).ravel()
    c = np.asarray(condition).ravel()
    n = min(d.size, t.size, c.size)
    d, t, c = d[:n], t[:n], c[:n]
    mask = c.astype(bool) if c.dtype != bool else c
    if n < MIN_N:
        return {"outcome": UNMEASURED, "n": int(n), "p": None, "stat": None, "lag": None,
                "why": f"conditional screen needs at least {MIN_N} aligned observations; it has "
                       f"{int(n)}"}
    if int(mask.sum()) < MIN_CONDITION_N:
        return {"outcome": UNMEASURED, "n": int(n), "n_condition": int(mask.sum()), "p": None,
                "stat": None, "lag": None,
                "why": f"the condition holds on {int(mask.sum())} of {int(n)} observations, "
                       f"below the floor of {MIN_CONDITION_N}; this is POORLY_MEASURED and is "
                       f"not a negative result"}

    def best(m: np.ndarray) -> tuple[float, int]:
        got: list[tuple[float, int]] = []
        for lag in lags:
            stat = _conditional_stat(d, t, m, lag)
            if not np.isnan(stat):
                got.append((abs(stat), lag))
        if not got:
            return float("nan"), 0
        return max(got, key=lambda r: r[0])

    obs_abs, obs_lag = best(mask)
    if np.isnan(obs_abs):
        return {"outcome": UNMEASURED, "n": int(n), "n_condition": int(mask.sum()), "p": None,
                "stat": None, "lag": None,
                "why": "no lag produced a computable conditional statistic (a constant series or "
                       "too few conditioned observations at every lag)"}
    signed = _conditional_stat(d, t, mask, obs_lag)

    rng = np.random.default_rng(seed)
    hits = 0
    draws = 0
    for _ in range(int(n_perm)):
        perm = rng.permutation(mask)
        null_abs, _lag = best(perm)
        if np.isnan(null_abs):
            continue
        draws += 1
        if null_abs >= obs_abs:
            hits += 1
    if draws == 0:
        return {"outcome": UNMEASURED, "n": int(n), "p": None, "stat": float(signed),
                "lag": int(obs_lag),
                "why": "no permutation draw produced a computable statistic, so there is no null "
                       "to compare against"}
    p = (hits + 1.0) / (draws + 1.0)
    return {"outcome": OK, "n": int(n), "n_condition": int(mask.sum()),
            "stat": float(signed), "lag": int(obs_lag), "p": float(p),
            "null_draws": int(draws), "lags_searched": list(lags),
            "passes": bool(p <= P_MAX),
            "rule": "the null PERMUTES THE CONDITION LABELS, not the returns: it asks how often a "
                    "randomly placed state of the same size produces a conditional lead this "
                    "large, and the lag search is inside the null rather than outside it"}


def screen_triple(triple: dict[str, Any], series: dict[str, Any], *,
                  n_perm: int = N_PERM) -> dict[str, Any]:
    """Screen one cross-region triple, or say which leg is missing.

    `series` maps leg name -> array. A triple needs its driver, its condition and at least one
    target series; anything absent is named and the triple reports UNMEASURED rather than a null.
    """
    missing = [leg for leg in triple["legs"] if leg not in series]
    target_keys = [t for t in triple["targets"] if t in series]
    if missing or not target_keys:
        return {"id": triple["id"], "outcome": UNMEASURED,
                "missing_legs": missing,
                "missing_targets": [t for t in triple["targets"] if t not in series],
                "why": f"{triple['id']}: " +
                       (f"legs {missing} are not on this box" if missing else
                        "no declared target series is on this box") +
                       "; the triple is recorded UNMEASURED by name because a triple that "
                       "disappears when a leg is absent is indistinguishable from one nobody "
                       "wrote",
                "claim": triple["claim"], "regions": list(triple["regions"])}
    out: dict[str, Any] = {"id": triple["id"], "outcome": OK, "claim": triple["claim"],
                           "regions": list(triple["regions"]), "targets": {}}
    for key in target_keys:
        out["targets"][key] = conditional_lead_lag(
            series[triple["driver"]], series[key], series[triple["condition"]], n_perm=n_perm)
    passed = [k for k, v in out["targets"].items() if v.get("passes")]
    out["passing_targets"] = passed
    out["n_passing"] = len(passed)
    out["outcome"] = OK if out["targets"] else UNMEASURED
    return out


# --------------------------------------------------------------------------- recording
def _registry() -> Any:
    """`libs.moat.registry`, or None when it is not importable on this box."""
    try:
        from libs.moat import registry
    except Exception:
        return None
    return registry


def record_families(*, dry_run: bool = False, conn: Any = None) -> dict[str, Any]:
    """Record one discovery per declared family, stamped with its region.

    `generator` is `latam:<family>` and `payload.region` is the country code, so the compiler and
    `generator_yields` can both measure this command's conversion without a second registry.
    A family whose mechanism this box cannot measure today is STILL recorded: a hypothesis with a
    falsifier is the unit of work here, and withholding it until its data arrives is how a
    research programme silently narrows to whatever was already collected.
    """
    reg = _registry()
    if reg is None:
        return {"outcome": UNMEASURED, "recorded": [], "n": 0, "n_new": 0,
                "why": "libs.moat.registry is not importable on this box; no discovery was "
                       "written and none is claimed"}
    recorded: list[dict[str, Any]] = []
    for fam in FAMILIES:
        gen = f"{GENERATOR_PREFIX}:{fam['id']}"
        if dry_run:
            recorded.append({"family": fam["id"], "generator": gen, "discovery_id": "dry-run",
                             "created": False})
            continue
        did, created = reg.record_discovery(
            source_id=f"{GENERATOR_PREFIX}:{fam['region']}", source_type="claim",
            mechanism=fam["mechanism"], origin="MOAT", generator=gen,
            actor=fam["country"], constraint=fam["state"],
            information=fam["information"], assets=list(fam["symbols"]),
            economic_rationale=fam["rationale"], falsifier=fam["falsifier"],
            exact_rule=f"{fam['id']}: {fam['state']} conditions the reaction of "
                       f"{list(fam['sensor_for'])}",
            payload={"region": fam["region"], "country": fam["country"],
                     "command": "SOUTH_AMERICA", "family": fam["id"],
                     "sensor_for": list(fam["sensor_for"]), "symbols": list(fam["symbols"])},
            conn=conn)
        recorded.append({"family": fam["id"], "generator": gen, "discovery_id": did,
                         "created": bool(created), "region": fam["region"]})
    return {"outcome": OK, "recorded": recorded, "n": len(recorded),
            "n_new": sum(1 for r in recorded if r["created"]),
            "by_region": {code: sum(1 for r in recorded if r.get("region") == code)
                          for code in sorted({f["region"] for f in FAMILIES})},
            "rule": "a family is recorded whether or not this box can measure it today; "
                    "withholding a hypothesis until its data arrives narrows the programme to "
                    "whatever was already collected"}


# --------------------------------------------------------------------------- the pass
def run(*, dry_run: bool = False, series: dict[str, Any] | None = None,
        root: Path | None = None, n_perm: int = N_PERM, conn: Any = None,
        out: Path | None = None) -> dict[str, Any]:
    """One pass: record every family, resolve every cross-region leg, screen what can be screened.

    `--dry-run` writes NOTHING -- no discovery and no report. It is the shape a scheduler uses to
    check the organ is alive without spending a registry row.
    """
    planted = dict(series or {})
    legs = {leg: resolve_leg(leg, root=root) for leg in sorted(LEG_SOURCES)}
    for leg in planted:
        if leg in legs:
            legs[leg] = {"leg": leg, "outcome": OK, "found": ["supplied by the caller"],
                         "looked_in": list(LEG_SOURCES.get(leg, ())), "why": ""}
    families = record_families(dry_run=dry_run, conn=conn)
    screens = [screen_triple(tr, planted, n_perm=n_perm) for tr in TRIPLES]
    unmeasured: list[dict[str, Any]] = [
        {"what": leg, "why": row["why"]} for leg, row in sorted(legs.items())
        if row["outcome"] != OK]
    unmeasured += [{"what": s["id"], "why": s["why"]} for s in screens
                   if s["outcome"] != OK and s.get("why")]
    doc = {
        "at": _now(),
        "command": "SOUTH_AMERICA",
        "families": [{"id": f["id"], "region": f["region"], "country": f["country"],
                      "mechanism": f["mechanism"], "sensor_for": list(f["sensor_for"]),
                      "symbols": list(f["symbols"]), "falsifier": f["falsifier"]}
                     for f in FAMILIES],
        "n_families": len(FAMILIES),
        "discoveries_recorded": families,
        "cross_region": [{"id": t["id"], "legs": list(t["legs"]), "driver": t["driver"],
                          "condition": t["condition"], "targets": list(t["targets"]),
                          "regions": list(t["regions"]), "claim": t["claim"],
                          "why_conditional": t["why_conditional"], "falsifier": t["falsifier"],
                          "legs_present": [lg for lg in t["legs"]
                                           if legs.get(lg, {}).get("outcome") == OK]}
                         for t in TRIPLES],
        "screens": screens,
        "legs": legs,
        "unmeasured": unmeasured,
        "n_unmeasured": len(unmeasured),
        "dry_run": bool(dry_run),
        "rule": RULE,
    }
    if not dry_run:
        target = Path(out) if out is not None else OUT
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        doc["report_path"] = str(target)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="South America interaction miner: families, cross-region triples, screens")
    ap.add_argument("--dry-run", action="store_true",
                    help="record nothing and write no report; print the pass that would run")
    ap.add_argument("--perm", type=int, default=N_PERM, help="permutation draws per screen")
    ap.add_argument("--out", default=None, help="report path override")
    args = ap.parse_args(argv)
    doc = run(dry_run=args.dry_run, n_perm=args.perm,
              out=Path(args.out) if args.out else None)
    print(json.dumps({k: doc[k] for k in ("at", "command", "n_families", "n_unmeasured",
                                          "dry_run")}, ensure_ascii=False, indent=1))
    for row in doc["unmeasured"]:
        print(f"  UNMEASURED {row['what']}: {row['why']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
