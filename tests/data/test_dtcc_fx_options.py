"""The DTCC public FX option tape: parsed, reduced per pair and day, stamped the next morning."""
from __future__ import annotations

import csv
import io
import json
import math
import zipfile
from datetime import UTC, date, datetime, timedelta

import numpy as np

from libs.data import dtcc_fx_options as dtcc
from libs.data import pit_certificate as pit
from libs.data import repo_mined_feeds as rmf

FIELDS = ["UPI FISN", "Action type", "Execution Timestamp", "UPI Underlier Name",
          "Call currency", "Call amount", "Put currency", "Put amount", "Expiration Date",
          "Strike Price", "Option Premium Amount", "Option Premium Currency"]


def _row(day: date, *, call: bool, strike: float, vol: float, tenor: int = 30,
         notional: float = 10e6, pair: str = "EUR USD") -> dict[str, str]:
    t = tenor / 365.0
    premium = 0.3989 * vol * math.sqrt(t) * strike * notional        # in quote currency
    base, quote = pair.split()
    return {"UPI FISN": "NA/O Van Call" if call else "NA/O Van Put", "Action type": "NEWT",
            "Execution Timestamp": f"{day.isoformat()}T14:00:00Z", "UPI Underlier Name": pair,
            "Call currency": base if call else quote, "Call amount": f"{notional:.2f}+",
            "Put currency": quote if call else base, "Put amount": f"{notional:.2f}",
            "Expiration Date": (day + timedelta(days=tenor)).isoformat(),
            "Strike Price": f"{strike}", "Option Premium Amount": f"{premium:.2f}",
            "Option Premium Currency": quote}


def _zip(rows: list[dict[str, str]]) -> bytes:
    text = io.StringIO()
    w = csv.DictWriter(text, fieldnames=FIELDS)
    w.writeheader()
    w.writerows(rows)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("CFTC_CUMULATIVE_FOREX_2026_01_01.csv", text.getvalue())
    return buf.getvalue()


def _day_rows(day: date, vol: float) -> list[dict[str, str]]:
    near = [_row(day, call=True, strike=1.10, vol=vol), _row(day, call=False, strike=1.10, vol=vol),
            _row(day, call=True, strike=1.1003, vol=vol)]
    wings = [_row(day, call=True, strike=1.13, vol=vol),
             _row(day, call=False, strike=1.07, vol=vol, notional=30e6)]
    ignored = [{**_row(day, call=True, strike=1.10, vol=vol), "Action type": "TERM"},
               {**_row(day, call=True, strike=1.10, vol=vol), "UPI FISN": "NA/O Dig Call"},
               _row(day, call=True, strike=150.0, vol=vol, pair="USD JPY")]
    return near + wings + ignored


def test_reduce_reads_vol_and_the_tape_side():
    day = date(2026, 3, 2)
    by_pair = dtcc._prints(_day_rows(day, 0.08), day)
    assert set(by_pair) == {"EURUSD", "USDJPY"} and len(by_pair["EURUSD"]) == 5
    f = dtcc.reduce_pair(by_pair["EURUSD"])
    assert f is not None and abs(f["atm_vol"] - 0.08) < 0.002
    assert f["call_share"] == 30e6 / 70e6
    assert f["otm_call_share"] == 20e6 / 50e6
    assert dtcc.reduce_pair(by_pair["USDJPY"]) is None            # one print says nothing
    assert dtcc.parse_amount("9999999999.99") is None and dtcc.parse_amount("5,000+") == 5000.0


def _fixture(n_days: int):
    start = date(2025, 1, 1)
    days = [start + timedelta(days=i) for i in range(n_days)]
    vols = 0.07 + 0.02 * np.sin(np.arange(n_days) / 9.0)
    blobs = {f"https://dtcc.test/{d}.zip": _zip(_day_rows(d, float(v)))
             for d, v in zip(days, vols, strict=True)}
    manifest = [{"fileName": f"CFTC_CUMULATIVE_FOREX_{d:%Y_%m_%d}.zip",
                 "fullFilePath": f"https://dtcc.test/{d}.zip"} for d in days]

    def fetch(url: str):
        if url == dtcc.MANIFEST_URL:
            return json.dumps(manifest).encode(), "application/json"
        return blobs.get(url), "application/zip"
    return days, fetch


def test_ingest_backfills_newest_first_a_few_slices_a_pass(tmp_path):
    days, fetch = _fixture(20)
    now = datetime.combine(days[-1] + timedelta(days=2), datetime.min.time(), tzinfo=UTC)
    first = dtcc.ingest(tmp_path, fetch=fetch, now=now, per_pass=6)
    assert first["slices_reduced"][0] == days[-1].isoformat() and first["days_pending"] == 14
    dtcc.ingest(tmp_path, fetch=fetch, now=now, per_pass=50)
    frames = dtcc.frames(tmp_path, now)
    f = frames["dtcc_fx_EURUSD_atm_vol"]
    assert len(f) == 20
    lag = (f["available_time"] - f.index).min()
    assert lag == dtcc.AVAILABLE_AFTER                            # never knowable before 06:00 +1d


def test_tape_registers_with_authority_on_the_second_pass(tmp_path):
    days, fetch = _fixture(230)
    now = datetime.combine(days[-1] + timedelta(days=2), datetime.min.time(), tzinfo=UTC)
    reg: dict = {"by_url": {}, "series": {}}
    for k in range(2):
        dtcc.ingest(tmp_path / "dtcc_fx", fetch=fetch, now=now, per_pass=300)
        rep = rmf.absorb_dtcc(reg, tmp_path, fetch=fetch, certify=pit.certify,
                              write_certificate=lambda c: None,
                              now=now + timedelta(hours=k))
    assert "dtcc_fx_EURUSD_atm_vol" in rep["new_series"]
    assert reg["series"]["dtcc_fx_EURUSD_atm_vol"]["pit_authority"] is True
    assert reg["by_url"][dtcc.MANIFEST_URL]["status"] == "SUCCESS"


def test_unreachable_manifest_is_named():
    assert dtcc.ingest(__import__("pathlib").Path("/nonexistent"),
                       fetch=lambda u: (None, "unreachable"))["status"] == "UNREACHABLE"
