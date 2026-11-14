"""China supply-chain / credit KNOWLEDGE GRAPH: which MT5 instruments a Chinese stress shock
reaches, along which economic channel, with what sign and how hard -- GAP_MAP row 31.

WHY A KNOWLEDGE GRAPH AND NOT ANOTHER CORRELATION MATRIX. Chinese AI shops run corporate GNNs on
supply-chain and guarantee/credit graphs: the edges come from who sells to whom and who owes whom,
not from how two prices happened to co-move last quarter. A price-learned graph (the desk's
`gnn_propagation` lead-lag/corr adjacency) cannot tell a stable economic channel from a
coincidence of the training window, and it re-learns the channel from noise every refit. A graph
built from TRADE FLOWS knows that Australia ships ores to China before any price says so, and it
stays put when a calm quarter decorrelates AUD from CNH.

THE GRAPH (typed nodes, signed weighted edges, every edge carrying its basis):

  china ──(share of the country's goods exports bought by China)──> country
  china ──(China's weight in world demand for the commodity)──────> commodity
  commodity ──(the commodity's share of the country's exports)────> country
  country ──(listing)──> instrument          currency: +1 for USDxxx, -1 for xxxUSD;
                                              equity index: -1
  commodity ──(listing)──> instrument        XCUUSD for copper, crude for oil, PGMs
  china ──(direct)──> USDCNH (+1), CHINAH (-1), HK50 (-1)

  Sign convention: the response of the instrument's QUOTED PRICE to a China STRESS shock (stress
  up = Chinese demand/credit worse). AUDUSD -1 (AUD weakens), USDKRW +1 (KRW weakens).

WEIGHTS ARE MEASURED WHERE THE WORLD PUBLISHES THEM. `china -> country` and `commodity ->
country` come from UN Comtrade annual exports (data/axes/china_exposure.json, written by
`research/china_exposure_ingest.py`) and are labelled MEASURED with their year. Where that file
has no row the edge falls back to a STRUCTURAL prior (an ordinal weight with its published
basis named) and is labelled so: a prior is never reported as a measurement. `china ->
commodity` weights are STRUCTURAL by construction (China's share of world demand is a published
industry fact, not a series the desk ingests) and say so.

Safe-haven currencies (JPY, CHF) and gold are deliberately NOT given a sign: a China shock both
cuts their exports and bids them as havens, and the net is an empirical question the contagion
study measures (`unsigned` list), never a prior this file asserts.

EXPOSURE of instrument i = sum over paths china -> ... -> i of the product of edge weights times
the listing sign (`exposures`). ADJACENCY for the learned GNN (`knowledge_adjacency`): two
instruments are linked by their shared channel, A[i, j] = e_i * e_j (rank one through the China
node) plus the direct commodity -> country links, zero diagonal, top-k, row-normalised -- the
same shape `libs.models.learned_propagation.adjacency` returns, so the GNN consumes it unchanged.
It is FIXED (no return enters it), so it carries no look-ahead into any walk-forward fold.
"""
from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
EXPOSURE_FILE = ROOT / "desks" / "mt5" / "data" / "axes" / "china_exposure.json"

MEASURED = "MEASURED"
STRUCTURAL = "STRUCTURAL"
#: Ordinal prior weights, used only where no measurement exists.
PRIOR = {"direct": 1.0, "strong": 0.35, "medium": 0.2, "weak": 0.1}

#: country -> (ISO3, UN Comtrade reporter code, its instruments with listing signs, the prior
#: strength of its China link and that prior's published basis).
COUNTRIES: dict[str, dict[str, Any]] = {
    "AUS": {"m49": 36, "instruments": {"AUDUSD": -1, "AUS200": -1}, "prior": "strong",
            "basis": "China is Australia's largest goods export market (DFAT trade statistics)"},
    "NZL": {"m49": 554, "instruments": {"NZDUSD": -1}, "prior": "strong",
            "basis": "China is New Zealand's largest goods export market (Stats NZ)"},
    "KOR": {"m49": 410, "instruments": {"USDKRW": 1}, "prior": "strong",
            "basis": "China is one of Korea's two largest export markets (KITA)"},
    "ZAF": {"m49": 710, "instruments": {"USDZAR": 1}, "prior": "medium",
            "basis": "China is South Africa's largest single trading partner (SARS)"},
    "BRA": {"m49": 76, "instruments": {"USDBRL": 1}, "prior": "strong",
            "basis": "China is Brazil's largest export market (Secex/MDIC)"},
    "SGP": {"m49": 702, "instruments": {"USDSGD": 1}, "prior": "medium",
            "basis": "China is among Singapore's largest export markets (SingStat)"},
    "JPN": {"m49": 392, "instruments": {"JPN225": -1}, "prior": "medium",
            "basis": "China is one of Japan's two largest export markets (MoF Japan)"},
    "CAN": {"m49": 124, "instruments": {"USDCAD": 1}, "prior": "weak",
            "basis": "Canada's exports go overwhelmingly to the US; China a distant second"},
    "MEX": {"m49": 484, "instruments": {"USDMXN": 1}, "prior": "weak",
            "basis": "Mexico's exports go overwhelmingly to the US"},
    "NOR": {"m49": 579, "instruments": {"USDNOK": 1}, "prior": "weak",
            "basis": "Norway's exports go mainly to Europe"},
    "IND": {"m49": 699, "instruments": {"USDINR": 1}, "prior": "weak",
            "basis": "China is a minor destination of India's exports"},
    "THA": {"m49": 764, "instruments": {"USDTHB": 1}, "prior": "medium",
            "basis": "China is among Thailand's largest export markets"},
    "IDN": {"m49": 360, "instruments": {"USDIDR": 1}, "prior": "strong",
            "basis": "China is Indonesia's largest export market (BPS)"},
    "DEU": {"m49": 276, "instruments": {"EURUSD": -1, "GER40": -1}, "prior": "weak",
            "basis": "China is among Germany's larger non-EU export markets (Destatis)"},
    "GBR": {"m49": 826, "instruments": {"GBPUSD": -1, "UK100": -1}, "prior": "weak",
            "basis": "China is a minor destination of UK goods exports (ONS)"},
}

#: commodity -> (HS chapter or heading the ingest measures, China's demand weight and its basis,
#: the instruments it is quoted as, with listing signs).
COMMODITIES: dict[str, dict[str, Any]] = {
    "ores": {"hs": "26", "china_weight": "strong",
             "basis": "China imports the large majority of seaborne iron ore (World Steel "
                      "Association / UNCTAD iron ore market reports)",
             "instruments": {}},
    "copper": {"hs": "74", "china_weight": "direct",
               "basis": "China consumes about half of world refined copper (ICSG World Copper "
                        "Factbook)",
               "instruments": {"XCUUSD": -1}},
    "fuels": {"hs": "27", "china_weight": "medium",
              "basis": "China is the world's largest crude oil importer (IEA Oil Market Report)",
              "instruments": {"XTIUSD": -1, "XBRUSD": -1}},
    "precious": {"hs": "71", "china_weight": "medium",
                 "basis": "China is the largest buyer of platinum-group metals for autocatalysts "
                          "and jewellery (Johnson Matthey PGM Market Report)",
                 "instruments": {"XPTUSD": -1, "XPDUSD": -1}},
    "dairy": {"hs": "04", "china_weight": "strong",
              "basis": "China is the largest importer of whole milk powder (GDT / Rabobank "
                       "dairy quarterly)",
              "instruments": {}},
}

#: Direct China listings: the shock's own instruments.
DIRECT: dict[str, int] = {"USDCNH": 1, "CHINAH": -1, "HK50": -1}
#: Instruments a China shock reaches with an ambiguous net sign; measured, never assumed.
UNSIGNED: tuple[str, ...] = ("USDJPY", "USDCHF", "XAUUSD", "XAGUSD")
#: Weight of the commodity channel relative to the direct export channel.
COMMODITY_CHANNEL = 0.5


@dataclass
class Edge:
    src: str
    dst: str
    weight: float
    sign: int
    kind: str
    status: str
    basis: str
    year: int | None = None


@dataclass
class Graph:
    nodes: dict[str, str] = field(default_factory=dict)        # node -> type
    edges: list[Edge] = field(default_factory=list)
    measured_year: int | None = None

    def add(self, e: Edge) -> None:
        self.edges.append(e)

    def out(self, node: str) -> list[Edge]:
        return [e for e in self.edges if e.src == node]

    def to_doc(self) -> dict[str, Any]:
        return {"nodes": self.nodes, "edges": [asdict(e) for e in self.edges],
                "measured_year": self.measured_year,
                "n_measured_edges": sum(1 for e in self.edges if e.status == MEASURED),
                "n_structural_edges": sum(1 for e in self.edges if e.status == STRUCTURAL)}


def load_measured(path: Path = EXPOSURE_FILE) -> dict[str, Any]:
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def build(measured: Mapping[str, Any] | None = None) -> Graph:
    """The graph, measured edges where the ingest has them, structural priors elsewhere."""
    m = measured if measured is not None else load_measured()
    rows = (m.get("countries") or {}) if isinstance(m, dict) else {}
    g = Graph(measured_year=m.get("year") if isinstance(m, dict) else None)
    g.nodes["china"] = "economy"
    for inst, sgn in DIRECT.items():
        g.nodes[inst] = "instrument"
        g.add(Edge("china", inst, 1.0, sgn, "direct_listing", STRUCTURAL,
                   "the shock's own market (CNH, H-shares, Hang Seng)"))
    for cname, c in COMMODITIES.items():
        g.nodes[cname] = "commodity"
        g.add(Edge("china", cname, PRIOR[c["china_weight"]], 1, "china_demand", STRUCTURAL,
                   c["basis"]))
        for inst, sgn in c["instruments"].items():
            g.nodes[inst] = "instrument"
            g.add(Edge(cname, inst, 1.0, sgn, "commodity_listing", STRUCTURAL,
                       f"{inst} quotes {cname}"))
    for iso, c in COUNTRIES.items():
        g.nodes[iso] = "country"
        got = rows.get(iso)
        r: dict[str, Any] = got if isinstance(got, dict) else {}
        share = r.get("china_share")
        if isinstance(share, (int, float)) and 0.0 <= float(share) <= 1.0:
            g.add(Edge("china", iso, float(share), 1, "export_share", MEASURED,
                       "UN Comtrade: exports to China / exports to world",
                       r.get("year")))
        else:
            g.add(Edge("china", iso, PRIOR[c["prior"]], 1, "export_share", STRUCTURAL,
                       c["basis"]))
        ch = r.get("chapter_share")
        chapters: dict[str, Any] = ch if isinstance(ch, dict) else {}
        for cname, cm in COMMODITIES.items():
            v = chapters.get(cm["hs"])
            if isinstance(v, (int, float)) and float(v) > 0:
                g.add(Edge(cname, iso, float(v), 1, "commodity_export_share", MEASURED,
                           f"UN Comtrade: HS {cm['hs']} exports / total exports",
                           r.get("year")))
        for inst, sgn in c["instruments"].items():
            g.nodes[inst] = "instrument"
            g.add(Edge(iso, inst, 1.0, sgn, "country_listing", STRUCTURAL,
                       f"{inst} prices {iso}"))
    for inst in UNSIGNED:
        g.nodes.setdefault(inst, "instrument")
    return g


def exposures(g: Graph) -> dict[str, dict[str, Any]]:
    """{instrument: {exposure, channels:[...], measured_share}} by path sum from `china`.

    The commodity channel is scaled by COMMODITY_CHANNEL: a commodity's price is set by world
    demand, of which China is one part, so its pass-through is weaker than a direct export loss.
    """
    out: dict[str, dict[str, Any]] = {}

    def walk(node: str, w: float, path: list[Edge], depth: int) -> None:
        for e in g.out(node):
            ww = w * e.weight
            if e.kind in ("commodity_export_share",):
                ww *= COMMODITY_CHANNEL
            if g.nodes.get(e.dst) == "instrument":
                rec = out.setdefault(e.dst, {"exposure": 0.0, "channels": [],
                                             "measured_mass": 0.0, "total_mass": 0.0})
                contrib = ww * e.sign
                rec["exposure"] += contrib
                chain = [*path, e]
                rec["channels"].append({"path": [x.src for x in chain] + [e.dst],
                                        "contribution": round(contrib, 5),
                                        "status": MEASURED if any(x.status == MEASURED
                                                                  for x in chain)
                                        else STRUCTURAL})
                rec["total_mass"] += abs(contrib)
                if any(x.status == MEASURED for x in chain):
                    rec["measured_mass"] += abs(contrib)
            elif depth < 3:
                walk(e.dst, ww, [*path, e], depth + 1)

    walk("china", 1.0, [], 0)
    for rec in out.values():
        rec["exposure"] = round(rec["exposure"], 5)
        tm = rec.pop("total_mass")
        rec["measured_share"] = round(rec.pop("measured_mass") / tm, 3) if tm else 0.0
        rec["sign"] = int(np.sign(rec["exposure"]))
        rec["channels"].sort(key=lambda c: -abs(c["contribution"]))
    for inst in UNSIGNED:
        out.setdefault(inst, {"exposure": 0.0, "sign": 0, "channels": [],
                              "measured_share": 0.0,
                              "why": "haven vs export channel: net sign is measured, not assumed"})
    return out


def knowledge_adjacency(symbols: Sequence[str], g: Graph | None = None,
                        top_k: int = 5) -> np.ndarray:
    """Signed, fixed, top-k, row-normalised adjacency over `symbols` from the graph.

    A[i, j] = e_i * e_j for instruments sharing the China channel (two AUD-and-KRW-like
    exposures move together under a China shock; opposite-signed ones oppositely), zero for any
    symbol the graph does not reach. Rows with no link stay zero -- the GNN then reads only
    the node's own features there, exactly as with a learned graph that found nothing."""
    g = g or build()
    ex = exposures(g)
    e = np.array([float((ex.get(str(s)) or {}).get("exposure") or 0.0) for s in symbols])
    n = len(symbols)
    a = np.outer(e, e)
    np.fill_diagonal(a, 0.0)
    if top_k and top_k < n - 1:
        keep = np.argsort(-np.abs(a), axis=1)[:, :top_k]
        mask = np.zeros_like(a, dtype=bool)
        np.put_along_axis(mask, keep, True, axis=1)
        a = np.where(mask, a, 0.0)
    s = np.abs(a).sum(axis=1, keepdims=True)
    out: np.ndarray = np.divide(a, s, out=np.zeros_like(a), where=s > 0)
    return out


def reached(g: Graph | None = None, min_abs: float = 0.02) -> dict[str, int]:
    """{instrument: sign} for instruments with |exposure| >= min_abs (the contagion targets)."""
    ex = exposures(g or build())
    return {k: int(v["sign"]) for k, v in ex.items()
            if v.get("sign") and abs(float(v["exposure"])) >= min_abs}


def stress_sources() -> dict[str, int]:
    """The direct listings and copper: the markets a China stress shock is OBSERVED in first."""
    return {**DIRECT, "XCUUSD": -1}


def country_codes() -> dict[str, int]:
    return {iso: int(c["m49"]) for iso, c in COUNTRIES.items()}


def hs_chapters() -> list[str]:
    return sorted({str(c["hs"]) for c in COMMODITIES.values()})


def instruments(g: Graph | None = None) -> list[str]:
    return sorted(k for k, t in (g or build()).nodes.items() if t == "instrument")


def describe(g: Graph | None = None) -> dict[str, Any]:
    g = g or build()
    return {**g.to_doc(), "exposures": exposures(g)}

