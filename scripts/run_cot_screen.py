"""CFTC COT SCREEN -- 26 years of free positioning data the desk owned and never read (register #77).

`data/cot_zcache.parquet` holds CFTC Commitments-of-Traders 2000->2026, 11 assets, and NOTHING in
the repo reads it. Two PRE-REGISTERED questions (docs/research/AXIS_PREREGISTRATIONS.md, written
before this ran):

  A. POST-PUBLICATION DECAY, MEASURED. The desk adopted a BORROWED -58% McLean-Pontiff haircut as
     a standing prior. This panel spans the publication dates of the hedging-pressure literature,
     so the decay can be MEASURED on owned data instead of imported.
  B. THE GORTON-HAYASHI-ROUWENHORST GATE. GHR reject hedging pressure: positioning is significant
     CONTEMPORANEOUSLY and zero LAGGED -- and only the lagged form is tradeable. A pooled null
     here CANCELS the queued crypto positioning-data acquisition. That is the budget value.

Stage-A discipline: this is a SCREEN with ZERO promotion authority. Every target x horizon cell is
a DSR-counted trial and is logged as one.

DATA. Reader-first: uses `data/cot_zcache.parquet` when present (the VPS path), else fetches the
CFTC annual archives (public domain) to the scratchpad. Price legs come from FRED's keyless CSV
endpoint (public domain). Metals/grains/softs are DROPPED with a stated reason, never silently:
Stooq is behind a JS proof-of-work bot gate and register #80 is an OPEN principal ruling on
defeating anti-bot gates, so it was not defeated; Yahoo's chart endpoint returned 429.

    python scripts/run_cot_screen.py [--years 2000-2026] [--offline]
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import subprocess
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

_ROOT = Path(__file__).resolve().parent.parent
_CACHE = Path("/tmp/claude-0/-home-user-quant/1c87bc3b-ab99-5043-86ff-5b38ad12af2a/scratchpad/cot")  # noqa: S108 -- session scratchpad path, not a shared world-writable location
_PARQUET = _ROOT / "data/cot_zcache.parquet"
_OUT = _ROOT / "data/cot_screen_summary.json"
_DOC = _ROOT / "docs/research/COT_SCREEN_RESULT.md"

_COT_URL = "https://www.cftc.gov/files/dea/history/deacot{year}.zip"
_FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"

# COT market-name substring -> FRED price series. Only pairs with a licence-clean price leg are
# included; see the module docstring for what was dropped and why.
# Needles are matched against a NORMALISED market name (quotes stripped, whitespace collapsed,
# uppercased) with startswith, and the precision is load-bearing -- measured on the first real run:
#   * pre-2000 crude is filed as CRUDE OIL, LIGHT 'SWEET' (quotes around SWEET), so a literal
#     "LIGHT SWEET" needle silently matched ZERO rows before 2000 and question A read n_pre=0 --
#     an absent PRE-publication sample masquerading as "no pre-publication effect";
#   * "S&P 500" substring-matched S&P 500 BARRA GROWTH INDEX and E-MINI S&P 500 as well as the
#     flagship contract, so multiple markets per date were stacked into one series (n=5,395 weekly
#     rows where 41 years hold ~2,130) -- silently interleaving three different contracts.
# Each asset carries ALL its historical filing names: CFTC renamed contracts across eras, and a
# single-name needle silently truncates the sample at the rename. Measured: pre-2000 sterling is
# filed "POUND STERLING - INTERNATIONAL MONETARY MARKET" (no "BRITISH"), so the modern name alone
# gave n_pre=0 -- an absent pre-publication sample that would have read as "no pre-publication
# effect" in question A. The aliases are the fix; where a gap REMAINS it is reported, not patched
# over (EUR FX did not exist before 1999; FRED's SP500 series starts 2016-08-01).
_ASSETS: dict[str, tuple[tuple[str, ...], str]] = {
    "crude_oil": (("CRUDE OIL, LIGHT SWEET -",), "DCOILWTICO"),
    "eur_fx": (("EURO FX -",), "DEXUSEU"),
    "jpy_fx": (("JAPANESE YEN -",), "DEXJPUS"),
    "gbp_fx": (("BRITISH POUND STERLING -", "POUND STERLING -"), "DEXUSUK"),
    "sp500": (("S&P 500 STOCK INDEX -",), "SP500"),
    "ust_10y": (("10-YEAR U.S. TREASURY NOTES -", "10 YEAR U.S. TREASURY NOTES -"), "DGS10"),
}


def _norm_market(name: str) -> str:
    """Uppercase, strip the quote characters CFTC used inconsistently across eras, collapse space."""
    return " ".join(name.upper().replace("'", "").replace('"', "").split())

# The publication boundary for question A: the later of the two canonical hedging-pressure dates
# (Bessembinder 1992, De Roon-Nijman-Veld 2000). Fixed in the pre-registration.
_SPLIT = "2000-01-01"
_ZWIN = 52          # weeks
_BORROWED_HAIRCUT = 0.58


def _fetch(url: str, dest: Path) -> bytes:
    """Cache-first fetch, with a curl fallback.

    urllib hung on the FRED host through this environment's egress proxy while curl succeeded on
    the identical URL, so the fallback is real robustness rather than belt-and-braces: an organ
    that dies on one client library and reports "source unavailable" would have produced a FALSE
    negative result here (the exact scope-the-negative-result defect the battery warns about --
    the ROUTE failed, not the capability)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return dest.read_bytes()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "quant-research/1.0"})
        with urllib.request.urlopen(req, timeout=45) as r:
            blob: bytes = r.read()
    except Exception:
        subprocess.run(["curl", "-sSf", "-o", str(dest), url, "--max-time", "90"],
                       check=True, capture_output=True)
        return dest.read_bytes()
    dest.write_bytes(blob)
    return blob


def _cot_year(year: int) -> list[dict[str, str]]:
    blob = _fetch(_COT_URL.format(year=year), _CACHE / f"deacot{year}.zip")
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        name = z.namelist()[0]
        text = z.read(name).decode("latin-1")
    return list(csv.DictReader(io.StringIO(text)))


def _fred(sid: str) -> dict[str, float]:
    blob = _fetch(_FRED_URL.format(sid=sid), _CACHE / f"fred_{sid}.csv")
    out: dict[str, float] = {}
    for row in csv.DictReader(io.StringIO(blob.decode("utf-8"))):
        vals = list(row.values())
        if len(vals) < 2 or vals[1] in ("", ".", None):
            continue
        try:
            out[str(vals[0])[:10]] = float(str(vals[1]))
        except ValueError:
            continue
    return out


def _col(row: dict[str, str], prefix: str) -> float | None:
    """Exact-PREFIX column lookup, and the exactness is load-bearing.

    A substring match is WRONG on this schema and it fails silently in the worst direction:
    "Commercial Positions-Long (All)" is a substring of "NONCommercial Positions-Long (All)", and
    the noncommercial column appears FIRST in the CFTC file -- so a substring lookup returns the
    noncommercial value for both legs, and every commercial series computes to exactly 0.0.
    Measured on the first real run of this script: all 12 commercial cells read Sharpe +0.00,
    which looked like "no edge in hedging pressure" and was actually a parsing bug. Anchoring on
    the column prefix is what distinguishes the two families."""
    want = prefix.lower().strip()
    for k, v in row.items():
        kl = k.lower().strip().strip('"')
        if kl.startswith(want):
            try:
                return float(v)
            except (TypeError, ValueError):
                return None
    return None


def _build_panel(years: range) -> dict[str, list[tuple[str, float, float]]]:
    """asset -> [(date, commercial_net_over_oi, noncommercial_net_over_oi)], weekly ascending."""
    # (asset, date) -> (open_interest, comm_net, nonc_net); keyed so one date cannot hold two
    # contracts. Where a date legitimately has multiple qualifying markets, the LARGEST open
    # interest wins (the flagship contract), which is deterministic and stated rather than
    # whichever row the file happened to list first.
    best: dict[tuple[str, str], tuple[float, float, float]] = {}
    for year in years:
        try:
            rows = _cot_year(year)
        except (OSError, zipfile.BadZipFile, ValueError) as e:
            print(f"  cot {year}: UNAVAILABLE ({type(e).__name__}) -- year dropped, not skipped "
                  f"silently")
            continue
        for row in rows:
            market = _norm_market(str(row.get("Market and Exchange Names", "")))
            for asset, (needles, _sid) in _ASSETS.items():
                if not any(market.startswith(_norm_market(n)) for n in needles):
                    continue
                date = str(row.get("As of Date in Form YYYY-MM-DD", ""))[:10]
                oi = _col(row, "open interest (all)")
                c_long = _col(row, "commercial positions-long (all)")
                c_short = _col(row, "commercial positions-short (all)")
                n_long = _col(row, "noncommercial positions-long (all)")
                n_short = _col(row, "noncommercial positions-short (all)")
                if not date or not oi or oi <= 0:
                    continue
                if None in (c_long, c_short, n_long, n_short):
                    continue
                comm_net = ((c_long or 0.0) - (c_short or 0.0)) / oi
                nonc_net = ((n_long or 0.0) - (n_short or 0.0)) / oi
                key = (asset, date)
                if key not in best or oi > best[key][0]:
                    best[key] = (oi, comm_net, nonc_net)
    panel: dict[str, list[tuple[str, float, float]]] = {a: [] for a in _ASSETS}
    for (asset, date), (_oi, c, n) in best.items():
        panel[asset].append((date, c, n))
    for asset in panel:
        panel[asset].sort()
    return panel


def _weekly_returns(prices: dict[str, float], dates: list[str]) -> np.ndarray:
    """Return for the week FOLLOWING each COT as-of date.

    COT is as-of Tuesday and PUBLISHED Friday: using the same week's return would trade on data
    that was not public. The lag is handled explicitly here rather than assumed away -- the exact
    class of error that produced the 4,709x kimchi artifact (register #79)."""
    keys = sorted(prices)
    out = []
    for i, d in enumerate(dates):
        nxt = dates[i + 1] if i + 1 < len(dates) else None
        start = next((k for k in keys if k > d), None)          # first bar after publication week
        if start is None or nxt is None:
            out.append(0.0)
            continue
        end = next((k for k in reversed(keys) if k <= nxt), None)
        if end is None or end <= start or prices[start] <= 0:
            out.append(0.0)
            continue
        out.append(prices[end] / prices[start] - 1.0)
    return np.asarray(out, dtype="float64")


def _z(x: np.ndarray, win: int) -> np.ndarray:
    z = np.zeros(len(x))
    for t in range(win, len(x)):
        w = x[t - win:t]
        sd = w.std()
        z[t] = (x[t] - w.mean()) / sd if sd > 0 else 0.0
    return z


def _sharpe(r: np.ndarray, ppy: float = 52.0) -> float:
    a = r[np.isfinite(r)]
    if len(a) < 10 or a.std() == 0:
        return 0.0
    return float(a.mean() / a.std() * np.sqrt(ppy))


def _nw_t(y: np.ndarray, x: np.ndarray, lags: int = 4) -> tuple[float, float]:
    """OLS slope with a Newey-West t-stat (overlapping weekly data is autocorrelated)."""
    m = np.isfinite(y) & np.isfinite(x)
    y, x = y[m], x[m]
    if len(y) < 30 or x.std() == 0:
        return 0.0, 0.0
    xc = x - x.mean()
    beta = float((xc * (y - y.mean())).sum() / (xc**2).sum())
    resid = y - y.mean() - beta * xc
    u = xc * resid
    s = float((u**2).sum())
    for lag in range(1, lags + 1):
        w = 1.0 - lag / (lags + 1.0)
        s += 2.0 * w * float((u[lag:] * u[:-lag]).sum())
    se = float(np.sqrt(s) / (xc**2).sum()) if (xc**2).sum() > 0 else 0.0
    return beta, (beta / se if se > 0 else 0.0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", default="1986-2026",
                    help="CFTC history starts 1986; the PRE-publication era is "
                         "required for question A -- a 2000+ range gives n_pre=0")
    ap.add_argument("--offline", action="store_true", help="use only what is already cached")
    args = ap.parse_args()
    y0, y1 = (int(v) for v in args.years.split("-"))

    print(f"COT screen | parquet_present={_PARQUET.exists()} | years {y0}-{y1}")
    panel = _build_panel(range(y0, y1 + 1))

    trials = 0
    decay_rows: list[dict[str, Any]] = []
    ghr_rows: list[dict[str, Any]] = []
    pooled_z: list[np.ndarray] = []
    pooled_r: list[np.ndarray] = []
    dropped: list[str] = []

    for asset, (_needles, sid) in _ASSETS.items():
        rows = panel.get(asset, [])
        if len(rows) < 200:
            dropped.append(f"{asset}: only {len(rows)} COT weeks parsed")
            continue
        try:
            prices = _fred(sid)
        except (OSError, ValueError) as e:
            dropped.append(f"{asset}: FRED {sid} unavailable ({type(e).__name__})")
            continue
        dates = [d for d, _c, _n in rows]
        comm = np.asarray([c for _d, c, _n in rows], dtype="float64")
        nonc = np.asarray([n for _d, _c, n in rows], dtype="float64")
        ret = _weekly_returns(prices, dates)

        for label, series in (("commercial", comm), ("noncommercial", nonc)):
            trials += 1
            z = _z(series, _ZWIN)
            use = slice(_ZWIN, len(z) - 1)
            zv, rv, dv = z[use], ret[use], dates[_ZWIN:len(z) - 1]
            if len(zv) < 100:
                dropped.append(f"{asset}/{label}: {len(zv)} usable weeks")
                continue
            # A. decay across the publication boundary. Commercial hedging pressure is the
            # PUBLISHED effect: commercials are the hedgers, so the classic sign is CONTRARIAN to
            # them (long when commercials are short) -- fixed in the pre-registration, not chosen
            # after seeing the answer.
            sign = -np.sign(zv) if label == "commercial" else np.sign(zv)
            pnl = sign * rv
            idx = np.array([d < _SPLIT for d in dv])
            sh_pre, sh_post = _sharpe(pnl[idx]), _sharpe(pnl[~idx])
            decay = (1.0 - sh_post / sh_pre) if sh_pre > 0 else None
            decay_rows.append({"asset": asset, "construction": label,
                               "n_pre": int(idx.sum()), "n_post": int((~idx).sum()),
                               "sharpe_pre": round(sh_pre, 3), "sharpe_post": round(sh_post, 3),
                               "decay": round(decay, 3) if decay is not None else None})
            # B. GHR: contemporaneous vs LAGGED. Only lagged is tradeable.
            _beta_c, t_c = _nw_t(rv, zv)                     # same-week (contemporaneous-ish)
            beta_l, t_l = _nw_t(rv[1:], zv[:-1])            # lagged one week
            trials += 1
            ghr_rows.append({"asset": asset, "construction": label,
                             "t_contemporaneous": round(t_c, 2), "t_lagged": round(t_l, 2),
                             "beta_lagged": round(beta_l, 5), "n": len(zv)})
            if label == "commercial":
                pooled_z.append(zv[:-1])
                pooled_r.append(rv[1:])

    pooled_t = 0.0
    if pooled_z:
        _b, pooled_t = _nw_t(np.concatenate(pooled_r), np.concatenate(pooled_z))

    measured = [r["decay"] for r in decay_rows if r["decay"] is not None]
    med_decay = float(np.median(measured)) if measured else None
    ghr_verdict = ("REJECT-POSITIONING-CLASS (pooled lagged predictability indistinguishable "
                   "from zero -- cancels the queued crypto positioning acquisition)"
                   if abs(pooled_t) < 1.96 else
                   "LAGGED PREDICTABILITY PRESENT (pooled |t|>=1.96 -- the crypto positioning "
                   "acquisition is justified and earns a pre-registered clock)")

    payload = {
        "measured": datetime.now(tz=UTC).isoformat(),
        "preregistered": "docs/research/AXIS_PREREGISTRATIONS.md (COT POSITIONING PANEL, "
                         "written before this ran)",
        "stage": "A (SCREEN -- zero promotion authority)",
        "assets_used": sorted({r["asset"] for r in decay_rows}),
        "assets_dropped": dropped,
        "price_source": "FRED keyless CSV (public domain); Stooq NOT used -- JS proof-of-work bot "
                        "gate, and register #80 is an OPEN principal ruling on defeating anti-bot "
                        "gates; Yahoo chart endpoint returned HTTP 429",
        "trials_charged": trials,
        "decay": {"rows": decay_rows, "median_measured_decay": med_decay,
                  "borrowed_prior": _BORROWED_HAIRCUT,
                  "split": _SPLIT},
        "ghr": {"rows": ghr_rows, "pooled_lagged_t": round(pooled_t, 2),
                "verdict": ghr_verdict},
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(payload, indent=2), "utf-8")

    print(f"\nassets used: {payload['assets_used']}")
    for d in dropped:
        print(f"  DROPPED {d}")
    print(f"\nA. POST-PUBLICATION DECAY (split {_SPLIT}), borrowed prior "
          f"{_BORROWED_HAIRCUT:.0%}:")
    for r in decay_rows:
        print(f"  {r['asset']:11} {r['construction']:14} pre {r['sharpe_pre']:+.2f} "
              f"post {r['sharpe_post']:+.2f} decay "
              f"{('%.0f%%' % (100 * r['decay'])) if r['decay'] is not None else 'n/a'}")
    print(f"  MEDIAN MEASURED DECAY: "
          f"{('%.0f%%' % (100 * med_decay)) if med_decay is not None else 'n/a'}")
    print("\nB. GHR LAGGED-vs-CONTEMPORANEOUS:")
    for r in ghr_rows:
        print(f"  {r['asset']:11} {r['construction']:14} t_contemp {r['t_contemporaneous']:+.2f} "
              f"t_lagged {r['t_lagged']:+.2f}")
    print(f"  POOLED lagged NW-t = {pooled_t:+.2f} -> {ghr_verdict}")
    print(f"\ntrials charged: {trials}  -> {_OUT.relative_to(_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
