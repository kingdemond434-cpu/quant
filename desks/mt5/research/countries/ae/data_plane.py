"""UAE DATA PLANE -- the CBUAE funding lane with its deposit control, and the Fujairah stockpile.

Built on the Middle East lane base in `countries.sa.data_plane` (one store, one network door, one
key file, one report shape). What is UAE-specific lives here: the catalogues, the funding verdict
that refuses to say STRESS on a rate leg alone, and the weekly physical-inventory state.
"""
from __future__ import annotations

from typing import Any

from countries._declared_data_plane import declared_lanes
from countries._declared_data_plane import report_path as _report_path
from countries.sa import data_plane as _me
from countries.sa.data_plane import (
    LICENSED,
    MIN_N,
    NOT_PIT_SAFE,
    UNMEASURED,
    Z_BAND,
    CatalogueRow,
    MenaLane,
    level_state,
    zscore,
)

CODE = "ae"
REPORT = _report_path(CODE)
DECLARED = declared_lanes(CODE)

#: DECLARED root of the CBUAE open-data endpoint; verified=False until it returns bytes here
_CBUAE_API = "https://opendata.centralbank.ae/api/v1/datasets"
#: months of deposit history the funding control needs, and the growth horizon it reads
CONTROL_MIN_N = 3
CONTROL_HORIZON = 3


class CbuaeLane(MenaLane):
    """The Central Bank of the UAE: EIBOR by tenor and the banking system's deposit base.

    THE CONTROL IS THE POINT. A Gulf funding widening that deposit growth explains is a credit
    cycle drawing on liquidity (the 2022-2023 widenings), not funding stress. `funding_state`
    therefore needs BOTH legs and is UNMEASURED without the deposit series.
    """

    LANE = "cbuae"
    COUNTRY = "ae"
    KEY = "cbuae"
    CATALOGUE = (
        CatalogueRow("cbuae_daily_liquidity", "Central Bank of the UAE (CBUAE)",
                     "EIBOR by tenor and the Base Rate", "daily", "none once fixed",
                     "free, public (CBUAE terms)", "2010-01",
                     "CBUAE EIBOR page and the monetary-operations release; published about "
                     "11:00 GST (07:00 UTC)", 0.4, url=f"{_CBUAE_API}/eibor/records",
                     series=("eibor_3m", "eibor_1m", "base_rate"),
                     key_required=True, key_name="cbuae", key_param="apikey"),
        CatalogueRow("cbuae_banking_indicators", "Central Bank of the UAE (CBUAE)",
                     "bank deposits and the loan-to-deposit ratio", "monthly", "minor",
                     "free, public (CBUAE terms)", "2000-01",
                     "CBUAE statistics; THE control series for every EIBOR-spread claim", 35.0,
                     url=f"{_CBUAE_API}/banking-indicators/records",
                     series=("bank_deposits_aed", "loan_to_deposit"),
                     key_required=True, key_name="cbuae", key_param="apikey"),
        CatalogueRow("cbuae_monetary_aggregates", "Central Bank of the UAE (CBUAE)",
                     "M1, M2 and M3", "monthly",
                     "restated into the quarterly review; both vintages are kept",
                     "free, public (CBUAE terms)", "2000-01",
                     "CBUAE statistics pages or its open-data endpoint; key named in "
                     "data/secrets/mena_apis.json", 35.0,
                     url=f"{_CBUAE_API}/monetary-aggregates/records", series=("m3_aed",),
                     key_required=True, key_name="cbuae", key_param="apikey",
                     vintage="provisional"),
        CatalogueRow("gulf_credit_spreads_licensed", "index providers (licensed terminals)",
                     "Gulf sovereign and bank CDS and bond spreads", "daily", "not applicable",
                     "LICENSED: index-provider data, not redistributable", "2008-01",
                     "NOT AVAILABLE TO THIS DESK: catalogued so any Gulf-risk claim that needs "
                     "it is UNMEASURED by name", 0.0, pit_feasible=NOT_PIT_SAFE, access=LICENSED),
    )

    def _funding_leg(self) -> tuple[list[float], str]:
        """The EIBOR 3M spread over the Base Rate where both are stored for enough days, else
        the EIBOR level itself -- named in the result so a reader knows which leg was read."""
        eibor = self.known("eibor_3m")
        base = self.known("base_rate")
        spread = [eibor[p] - base[p] for p in sorted(eibor) if p in base]
        if len(spread) >= MIN_N:
            return spread, "eibor_3m - base_rate"
        return [eibor[p] for p in sorted(eibor)], "eibor_3m"

    def funding_state(self) -> dict[str, Any]:
        """DRAIN, STRESS, EASING or NEUTRAL -- and UNMEASURED without the deposit control."""
        values, leg = self._funding_leg()
        deposits = self.panel("bank_deposits_aed")
        out: dict[str, Any] = {"lane": self.LANE, "name": "funding_state", "series": leg,
                               "label": "regional_funding", "n": len(values), "min_n": MIN_N,
                               "control": "bank_deposits_aed", "n_control": len(deposits),
                               "z": None, "deposit_growth": None}
        if len(values) < MIN_N:
            return {**out, "state": UNMEASURED,
                    "why": f"UNMEASURED: {len(values)} day(s) of {leg} stored, the rate leg "
                           f"needs {MIN_N}"}
        z = zscore(values)
        out["z"] = round(z, 4)
        if len(deposits) < CONTROL_MIN_N:
            return {**out, "state": UNMEASURED,
                    "why": f"UNMEASURED: the deposit control has {len(deposits)} month(s), "
                           f"needs {CONTROL_MIN_N}; a rate leg without its control is no verdict"}
        base = deposits[-1 - min(CONTROL_HORIZON, len(deposits) - 1)]
        growth = (deposits[-1] / base - 1.0) if base else 0.0
        out["deposit_growth"] = round(growth, 6)
        if z > Z_BAND:
            if growth > 0:
                return {**out, "state": "DRAIN",
                        "why": f"funding widened (z={z:+.2f}) while deposits grew "
                               f"{growth:+.2%}: a credit cycle drawing on liquidity, not stress"}
            return {**out, "state": "STRESS",
                    "why": f"funding widened (z={z:+.2f}) with deposits at {growth:+.2%}: "
                           f"the widening is not explained by credit demand"}
        if z < -Z_BAND:
            return {**out, "state": "EASING",
                    "why": f"funding narrowed (z={z:+.2f}); deposits {growth:+.2%}"}
        return {**out, "state": "NEUTRAL",
                "why": f"funding inside its band (z={z:+.2f}); deposits {growth:+.2%}"}

    def states(self) -> list[dict[str, Any]]:
        return [self.funding_state()]


class FujairahLane(MenaLane):
    """The Fujairah Oil Industry Zone weekly stockpile: the region's best public high-frequency
    PHYSICAL series, and the only keyless Gulf ground. Fujairah sits on the Indian Ocean side of
    the Strait of Hormuz -- the storage hub outside the chokepoint -- so a build or a draw here is
    the physical market's own answer to transit risk."""

    LANE = "fujairah"
    COUNTRY = "ae"
    KEY = ""
    CATALOGUE = (
        CatalogueRow("fujairah_oil_stocks_weekly",
                     "Fujairah Oil Industry Zone (FOIZ), via the weekly public release",
                     "light distillates, middle distillates and heavy residues in storage, and "
                     "the total", "weekly", "none",
                     "publicly distributed weekly; verify redistribution terms before bulk "
                     "storage", "2017-01",
                     "the weekly public release, normally Wednesday; store the release "
                     "timestamp with the value", 2.0,
                     url="https://fujairahoilindustryzone.com/api/weekly-stocks",
                     series=("fujairah_light_distillates", "fujairah_middle_distillates",
                             "fujairah_heavy_residues", "fujairah_total_stocks")),
    )

    def inventory_state(self, series: str = "fujairah_total_stocks") -> dict[str, Any]:
        """BUILD or DRAW on the stockpile, with the four-week change as the confirming leg.

        The headline is the TOTAL; when the total is flat the product class carrying the move is
        what matters, so the state is read on the class with the largest absolute z."""
        candidates = [series, *(s for s in self.CATALOGUE[0].series if s != series)]
        panels = {name: self.panel(name) for name in candidates}
        chosen = max(candidates, key=lambda n: (len(panels[n]) >= MIN_N,
                                                abs(zscore(panels[n])) if panels[n] else 0.0))
        values = panels[chosen]
        state = level_state(values, label="physical_inventory", up="BUILD", down="DRAW")
        change = values[-1] - values[-5] if len(values) >= 5 else None
        state["change_4w"] = change
        if state["state"] == "BUILD" and (change is None or change <= 0):
            state.update(state="NEUTRAL", why=f"{state['why']}; the four-week change does not "
                                              f"confirm a build")
        elif state["state"] == "DRAW" and (change is None or change >= 0):
            state.update(state="NEUTRAL", why=f"{state['why']}; the four-week change does not "
                                              f"confirm a draw")
        state["control"] = {"series": "fujairah_total_stocks",
                            "n": len(panels[series]),
                            "z": round(zscore(panels[series]), 4) if panels[series] else None}
        return {"lane": self.LANE, "name": "inventory_state", "series": chosen, **state}

    def states(self) -> list[dict[str, Any]]:
        return [self.inventory_state()]


LANES: tuple[type[MenaLane], ...] = (CbuaeLane, FujairahLane)


def run(**kwargs: Any) -> dict[str, Any]:
    """The UAE lanes through the shared Middle East pass; the miner's registry and report win."""
    kwargs["registry"] = kwargs.get("registry") or LANES
    kwargs["report_default"] = kwargs.get("report_default") or REPORT
    return _me.run(**kwargs)
