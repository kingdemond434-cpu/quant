"""The SGE collector was built-never-run (CN card #38, R0649): its parser expected dated rows
with instid/close keys while the official graph endpoint actually serves a minute-curve payload,
so it could parse nothing — the module had zero callers and zero output artifacts. PAYLOAD is
the REAL shape captured live 2026-08-26; if SGE changes shape again this file is where the new
fixture lands.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from research import fetch_sge_premium as S  # noqa: E402

PAYLOAD = {
    "times": ["20:00", "20:01", "20:02", "20:03"],
    "min": 992,
    "data": ["1000.0", None, "991.5", "990.08"],
    "max": 1004,
    "heyue": "Au99.99",
    "delaystr": "2026年08月26日 02:29:56",
}


def test_parse_graph_extracts_last_print_and_beijing_date():
    got = S._parse_graph(PAYLOAD, "Au99.99")
    assert got is not None
    d, px = got
    assert d == pd.Timestamp("2026-08-26")
    assert px == 990.08


def test_parse_graph_refuses_the_silent_contract_fallback():
    """The endpoint answers Au99.99 for an unknown instid; recording that under
    Au(T+D) would fabricate a zero basis, so a heyue mismatch is a refusal."""
    assert S._parse_graph(PAYLOAD, "Au(T+D)") is None


def test_parse_graph_refuses_garbage_rather_than_inventing_a_print():
    assert S._parse_graph(None, "Au99.99") is None
    assert S._parse_graph({**PAYLOAD, "data": [None, "", "null"]}, "Au99.99") is None
    assert S._parse_graph({**PAYLOAD, "delaystr": "no date here"}, "Au99.99") is None
    assert S._parse_graph({**PAYLOAD, "data": ["0.0001"]}, "Au99.99") is None


def test_record_history_upserts_by_date_so_cadence_cannot_duplicate(monkeypatch, tmp_path):
    monkeypatch.setattr(S, "HISTORY", tmp_path / "sge_daily.parquet")
    d = pd.Timestamp("2026-08-26")
    S.record_history({"au9999_cny_g": (d, 990.0), "au_td_cny_g": (d, 991.4)},
                     "sge_official_graph", "t0")
    hist = S.record_history({"au9999_cny_g": (d, 990.5), "au_td_cny_g": (d, 991.4)},
                            "sge_official_graph", "t1")
    assert len(hist) == 1
    assert hist.loc[d, "au9999_cny_g"] == 990.5
    assert round(float(hist.loc[d, "agtd_basis_cny_g"]), 2) == 0.9
    nxt = S.record_history({"au9999_cny_g": (d + pd.Timedelta(days=1), 992.0)},
                           "sge_official_graph", "t2")
    assert len(nxt) == 2
    # the enrichment leg is absent that day: recorded as NaN, never carried forward
    assert pd.isna(nxt.loc[d + pd.Timedelta(days=1), "au_td_cny_g"])
