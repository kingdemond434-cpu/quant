"""A new code_hash / zcache definition RE-JUDGES the cot_positioning cells; it mints no trials.

THE QUESTION (Judge, 2026-10-14, before landing cot-zcache-fix): COT_ZCACHE_VERSION=2 sits in the
body of `family_cot_positioning`, so its code_hash moves 7a57ee8b -> 5c2882a6. Standing order:
trials never inflate -- the same family, cells and hypothesis are charged once.

THE ANSWER, MEASURED HERE: no trial count keys on code_hash. Every charge keys on the cell,
`frontier_identity.cell_id` = symbol (+chart) . family . sha256(params) -- no code identity:

  * `gate_policy.charged_trial_count` returns the spec's fixed campaign count; it takes no
    identity at all.
  * the effective-trials census (`research/effective_trials.py` -> `trial_ledger.
    effective_independent_tests`) reads the external_survivors DOCKET rows, which carry no
    code_hash, and `trial_from_record` reads only family/lineage, `_DESCRIPTOR_KEYS` and params.
  * the DSR lifetime trials (`libs.research.dsr_inputs.effective_trials`) count FIRST judgement
    per cell; a re-judge with a new Sharpe is a new evaluation row and the same trial.
  * the gauntlet series cache key does carry the replay-code identity -- that is what forces the
    re-judge -- but the cache is a series store, not a trial count.
  * `build_cell` refuses a stale-definition cell BY NAME before it has any bars: no series, no
    matrix column, nothing charged.

Each path below is pinned on fixtures, with no network and no desk state read.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_ROOT = Path(__file__).resolve().parents[2]
for _p in (_ROOT, _ROOT / "desks" / "mt5", _ROOT / "desks" / "mt5" / "research"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

OLD_HASH, NEW_HASH = "7a57ee8bf3b231cf", "5c2882a6"

#: The 18 cot_positioning rows of desks/mt5/data/hypotheses/external_survivors.json as of
#: 2026-10-14 (symbol, params), copied so the pin does not depend on box-written state.
_PIT = {"input_source": "cot_point_in_time"}
COT_SURVIVORS: list[tuple[str, dict]] = [
    *((s, dict(_PIT)) for s in ("USDCHF", "GBPUSD", "USDJPY", "EURUSD", "AUDUSD", "USDMXN",
                                "NZDUSD", "USDCAD", "XAGUSD", "XTIUSD")),
    ("EURCZK", {}), ("USDBRL", {}),
    *((s, {"session": ss}) for s in ("EURCZK", "USDBRL") for ss in ("asia", "london", "ny")),
]


def _docket(stamp: str | None = None, version: int | None = None) -> list[dict]:
    rows = []
    for sym, params in COT_SURVIVORS:
        row = {"symbol": sym, "family": "cot_positioning", "params": dict(params),
               "source": "miner:discovery_compiler", "mechanism_note": "positioning_crowding"}
        if stamp is not None:          # a writer that one day stamps the identity on the row
            row.update(code_hash=stamp, behaviour_hash=stamp, cot_zcache_version=version)
        rows.append(row)
    rows.append({"symbol": "EURUSD", "family": "carry", "params": {}, "source": "x"})
    return rows


def _cells(rows: list[dict]) -> list[str]:
    from research.frontier_identity import cell_id, docket_cell
    return [cell_id(docket_cell(r)) for r in rows]


def test_there_are_eighteen_distinct_cot_cells():
    cells = _cells(_docket())[:-1]
    assert len(cells) == 18 == len(set(cells))


# ------------------------------------------------------------------ 1. the 18 survivor rows
def test_rejudging_the_18_survivors_keeps_cell_ids_and_the_trial_charge():
    """A definition/code_hash change leaves the docket's cells, the fixed charge and the
    effective-trials census (organ `effective_trials`) exactly where they were."""
    import effective_trials as et
    from research.gate_policy import charged_trial_count

    before, after = _docket(), _docket(stamp=NEW_HASH, version=2)
    assert _cells(before) == _cells(after)

    m0, m1 = et.measure(before), et.measure(after)
    assert m0["n_nominal"] == m1["n_nominal"] == len(before)
    assert m0["n_effective"] == m1["n_effective"]
    assert m0["by_family"] == m1["by_family"]
    assert et.charge(m0) == et.charge(m1)

    raw = len(before)
    # even a sweep that judged every cell twice (old + new series) is charged the same
    n, basis = charged_trial_count(raw, None, None)
    assert charged_trial_count(2 * raw, None, None)[0] == n
    assert basis.startswith("fixed_campaign_trials"), "the charge must not depend on any identity"


def test_a_code_hash_is_never_part_of_a_trials_content():
    """Even a row that carried the hash at top level is the same trial (same grid, same content)."""
    from libs.research.trial_ledger import content_key, grid_key, trial_from_record

    for a, b in zip(_docket(stamp=OLD_HASH, version=1), _docket(stamp=NEW_HASH, version=2),
                    strict=True):
        ta, tb = trial_from_record(a), trial_from_record(b)
        assert (grid_key(ta), content_key(ta)) == (grid_key(tb), content_key(tb))
        assert "code_hash" not in content_key(ta) and "zcache" not in content_key(ta)


# ------------------------------------------------- 2. the gauntlet series cache (replay key)
def test_the_series_cache_misses_on_a_new_replay_identity_but_the_cell_is_the_same(monkeypatch):
    from desks.mt5.scripts import external_gauntlet as g

    spec = {"sym": "EURUSD", "family": "cot_positioning", "params": dict(_PIT)}
    monkeypatch.setattr(g, "_replay_code_identity", lambda: OLD_HASH)
    k0 = g._cache_key(spec["sym"], spec["family"], spec["params"], "2026-10-13")
    c0 = g.cell_id(spec)
    monkeypatch.setattr(g, "_replay_code_identity", lambda: NEW_HASH)
    k1 = g._cache_key(spec["sym"], spec["family"], spec["params"], "2026-10-13")
    c1 = g.cell_id(spec)
    assert k0 != k1, "the cache must miss so the cell is re-judged over the new definition"
    assert c0 == c1, "...but it is re-judged under the SAME cell id: same trial"


def test_the_replay_identity_covers_the_family_file():
    """The family body (where the definition literal sits) is inside the replay identity."""
    import inspect

    from desks.mt5.scripts import external_gauntlet as g
    src = inspect.getsource(g._replay_code_identity.__wrapped__)
    assert 'glob("famil*.py")' in src


def _sweep(tmp_path: Path, name: str, sharpe_shift: float, swept_at: str) -> Path:
    """A gauntlet sweep report judging the 18 cot cells (as dsr_inputs harvests it)."""
    from research.frontier_identity import cell_id, docket_cell
    verdicts = []
    for i, row in enumerate(_docket()[:-1]):
        cell = docket_cell(row)
        verdicts.append({"cell": cell_id(cell), "family": "cot_positioning",
                         "sym": row["symbol"], "days": 400,
                         "stages": {"in_sample_screen": {"sharpe": 0.01 * i + sharpe_shift}}})
    path = tmp_path / name
    path.write_text(json.dumps({"hunt": "external", "swept_at": swept_at, "verdicts": verdicts,
                                "trial_census": {"method": "none"}}), "utf-8")
    return path


def test_a_rejudge_over_the_new_series_adds_no_lifetime_dsr_trial(tmp_path):
    """New series -> new Sharpes -> new evaluation rows; the lifetime trial count is per cell."""
    from libs.research import dsr_inputs

    ledger = tmp_path / "dsr_trial_sharpes.jsonl"
    dsr_inputs.harvest(_sweep(tmp_path, "v1.json", 0.0, "2026-10-13T00:00:00+00:00"), ledger)
    first = dsr_inputs.effective_trials(dsr_inputs.read_ledger(ledger))
    h = dsr_inputs.harvest(_sweep(tmp_path, "v2.json", 0.003, "2026-10-14T00:00:00+00:00"), ledger)
    assert h["appended"] == 18                      # the re-judge IS recorded, as evaluations
    second = dsr_inputs.effective_trials(dsr_inputs.read_ledger(ledger))
    assert first["by_family"]["cot_positioning"]["nominal"] == 18
    assert second == first


def test_rejudged_verdict_rows_do_not_raise_the_effective_census():
    """Were verdict rows ever fed to the census, a re-judge is an identical (grid, content) and
    adds no effective test; the campaign charge can only stay or fall, never rise."""
    from libs.research.trial_ledger import campaign_charge, effective_independent_tests

    once = [{"cell": c, "family": "cot_positioning", "symbol": r["symbol"], "params": r["params"]}
            for c, r in zip(_cells(_docket()), _docket(), strict=True)][:-1]
    twice = once + [{**r, "code_hash": NEW_HASH} for r in once]
    a, b = effective_independent_tests(once), effective_independent_tests(twice)
    assert b.n_effective == pytest.approx(a.n_effective)
    assert campaign_charge(597, b)[0] <= campaign_charge(597, a)[0]


# --------------------------------------------------------------------------- 3. build_cell
def _stamp_cache(tmp_path: Path, monkeypatch, version: int | None) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    from libs.data import cot_source

    path = tmp_path / "data" / "cot_zcache.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(cot_source, "ZCACHE", path)
    frame = pd.DataFrame({"EURUSD": np.linspace(-1, 1, 400)},
                         index=pd.date_range("2018-01-02", periods=400, freq="7D", tz="UTC"))
    table = pa.Table.from_pandas(frame)
    if version is not None:
        table = table.replace_schema_metadata(
            {**(table.schema.metadata or {}), b"cot_zcache_version": str(version).encode()})
    pq.write_table(table, path)


@pytest.mark.parametrize("version", [None, 1])
def test_build_cell_refuses_a_stale_definition_by_name_and_charges_nothing(
        tmp_path, monkeypatch, version):
    """Stale cache: build_cell fails BY NAME before reading bars, the warm path files the cell
    NOT_RUN (no series -> no matrix column -> no trial), and the cell id is unchanged."""
    from desks.mt5.scripts import external_gauntlet as g

    _stamp_cache(tmp_path, monkeypatch, version)
    spec = {"sym": "EURUSD", "family": "cot_positioning", "params": dict(_PIT)}
    assert g.build_cell(spec["sym"], spec["family"], spec["params"], {}) is None
    assert g.LAST_BUILD_FAILURE and "UNMEASURED" in g.LAST_BUILD_FAILURE

    bars = pd.DataFrame({"open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0]},
                        index=pd.DatetimeIndex(["2026-10-13 10:00"], tz="UTC"))
    monkeypatch.setattr(g, "_bars_for", lambda sym, tf: bars)
    monkeypatch.setattr(g, "cache_load", lambda key: None)
    saved: list = []
    monkeypatch.setattr(g, "cache_save", lambda *a: saved.append(a))
    out = g._warm_one(spec, {})
    assert out["status"] == "NOT_RUN_BUILD_FAILED" and "UNMEASURED" in out["why"]
    assert saved == []                               # no series exists to become a trial
    assert g.cell_id(spec) == _cells(_docket())[COT_SURVIVORS.index(("EURUSD", _PIT))]
