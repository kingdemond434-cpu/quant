"""LLM data discovery: a free model's data-source proposal is vetted fail-closed, queued per seat,
routed into the keyed_sources roster (the one keyless fetcher), lands in the lake with PIT z
columns, is offered back by alt_catalog with its discoverer, and is counted per method in the
funnel. Every input is synthetic and lives in `tmp_path`; no model and no network are called."""
from __future__ import annotations

import json
import shutil
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import alt_catalog as ac  # noqa: E402
from research import data_discovery as dd  # noqa: E402

NOW = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)
UNI = {"EURUSD", "XAUUSD", "USDJPY", "AAPL.US"}
MECH = "euro area banks hoard dollar funding at quarter end, forcing EURUSD basis demand"
GOOD = ("DATA_SOURCE | ECB | BSI | M.U2.Y.V.M30.X.I.U2.2300.Z01.A | M | 10 | "
        f"EURUSD:-1, XAUUSD:+1, AAPL.US:+1, GBPCAD:+1 | {MECH}")


def _may(sym: str) -> bool:
    return not sym.endswith(".US")               # a share CFD: event lane only


def _vet(raw: dict[str, Any], **kw: Any) -> tuple[dict[str, Any] | None, str]:
    return dd.vet(raw, universe=UNI, may_hypothesise=_may, **kw)


def _raw(**over: Any) -> dict[str, Any]:
    r = dd.parse_lines(GOOD)[0]
    r.update(over)
    return r


# ------------------------------------------------------------------ parser and vetting ----
def test_a_valid_line_is_normalised_with_the_url_built_from_the_provider_table() -> None:
    p, why = _vet(dd.parse_lines("prose first\n" + GOOD)[0])
    assert why == "" and p is not None
    assert p["provider"] == "ECB" and p["id"].startswith("disc_ecb_")
    assert p["path"] == "BSI/M.U2.Y.V.M30.X.I.U2.2300.Z01.A?format=csvdata"
    # monthly: a declared 10-day lag is RAISED to the floor (early would back-date history)
    assert p["lag_days"] == dd.LAG_FLOOR_DAYS["M"]
    # share CFD (event lane) and off-registry symbol dropped; the hypothesis lane kept
    assert p["instruments"] == {"EURUSD": -1, "XAUUSD": 1}
    assert p["series"] and all(c.isalnum() or c == "_" for c in p["series"])


@pytest.mark.parametrize(("over", "reason"), [
    ({"provider": "FRED"}, "provider_not_on_keyless_allowlist"),
    ({"mechanism": MECH + " (needs an api_key from the portal)"}, "not_free_or_keyed"),
    ({"mechanism": MECH + " via a paid feed of the same"}, "not_free_or_keyed"),
    ({"mechanism": MECH + " like binance funding rates"}, "crypto_exchange_ground"),
    ({"mechanism": MECH + " see https://evil.example.com/x"}, "endpoint_off_the_allowlist"),
    ({"key": "M.U2+US.Y"}, "key_not_one_series"),
    ({"key": "M..Y.V"}, "key_not_one_series"),
    ({"key": "M.U2/../x"}, "key_not_one_series"),
    ({"dataflow": "https://x"}, "dataflow_not_structural"),
    ({"freq": "A"}, "frequency_not_D_W_M_Q"),
    ({"freq": "D"}, "frequency_not_in_the_key"),
    ({"lag_days": "soon"}, "lag_not_a_number"),
    ({"lag_days": 9999}, "lag_out_of_range"),
    ({"instruments": {"AAPL.US": 1}}, "no_hypothesis_lane_instrument"),
    ({"instruments": {"EURUSD": 2}}, "no_hypothesis_lane_instrument"),
    ({"mechanism": "rates"}, "no_mechanism"),
    ({"_malformed": "DATA_SOURCE | ECB"}, "malformed"),
])
def test_every_hard_boundary_rejects_with_its_reason(over: dict[str, Any], reason: str) -> None:
    p, why = _vet(_raw(**over))
    assert p is None and why == reason


def test_a_short_line_is_malformed_and_a_duplicate_is_refused() -> None:
    assert dd.parse_lines("DATA_SOURCE | ECB | BSI")[0].get("_malformed")
    p, _ = _vet(_raw())
    full = dd.PROVIDERS["ECB"]["base"] + p["path"]
    assert _vet(_raw(), known_paths={full}) == (None, "duplicate_of_a_fetched_series")


# --------------------------------------------------------------------------- the queue ----
def test_record_queues_per_seat_with_counts_and_never_re_adds(tmp_path: Path) -> None:
    raws = [_raw(), _raw(provider="FRED"), {"_malformed": "x"}]
    got = dd.record("kimi", raws, organ="kimi_hunt", model="m", root=tmp_path,
                    universe=UNI, may_hypothesise=_may, now=NOW)
    assert (got["proposed"], got["accepted"], got["rejected"]) == (3, 1, 2)
    doc = json.loads(dd.queue_path("kimi", tmp_path).read_text("utf-8"))
    assert doc["counts"] == {"proposed": 3, "accepted": 1, "rejected": 2}
    assert doc["rejected_by_reason"] == {"provider_not_on_keyless_allowlist": 1, "malformed": 1}
    (row,) = doc["accepted"].values()
    assert row["discovered_by"] == "kimi_hunt" and row["method"] == dd.METHOD
    assert row["lake_series"] == f"ks_{row['id']}__{row['series']}"
    again = dd.record("kimi", [_raw()], organ="kimi_hunt", root=tmp_path, universe=UNI,
                      may_hypothesise=_may, now=NOW)
    assert again["accepted"] == 0 and again["reasons"] == {"duplicate_of_a_fetched_series": 1}
    assert len(json.loads(dd.queue_path("kimi", tmp_path).read_text("utf-8"))["accepted"]) == 1


def test_routing_into_the_keyed_sources_roster_re_vets_and_skips_what_it_holds(
        tmp_path: Path) -> None:
    import keyed_sources as K
    dd.record("kimi", [_raw()], organ="kimi_hunt", root=tmp_path, universe=UNI,
              may_hypothesise=_may, now=NOW)
    # A tampered row (arrived through git) with an OR key is re-vetted away on read.
    q = dd.queue_path("deepseek", tmp_path)
    q.parent.mkdir(parents=True)
    bad, _ = _vet(_raw(key="M.U2.Y.V.M30.X.I.U2.2300.Z01.B"))
    q.write_text(json.dumps({"accepted": {bad["id"]: {**bad, "key": "M.U2+US.Y",
                                                      "discovered_by": "deepseek"}}}), "utf-8")
    rows = dd.discovered_rows([], roots=[tmp_path])
    assert len(rows) == 1
    r = rows[0]
    assert all(k in r for k in K.REQUIRED) and K.machine_use_allowed(r)
    assert r["kind"] == "sdmx" and r["key_env"] == [] and r["auth"] == "none"
    assert r["base"] == dd.PROVIDERS["ECB"]["base"]
    assert r["discovered_by"] == "kimi_hunt" and r["method"] == dd.METHOD
    # what the roster already carries (same base + path) is not unioned twice
    assert dd.discovered_rows(rows, roots=[tmp_path]) == []


def _monthly_csv(n: int, last: date) -> bytes:
    lines = ["KEY,TIME_PERIOD,OBS_VALUE"]
    y, m = last.year, last.month
    for i in range(n):
        lines.append(f"X,{y:04d}-{m:02d},{100 + (i * 7) % 5}")
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    return "\n".join(lines).encode()


def test_keyed_sources_fetches_a_discovered_source_into_the_lake_with_pit_z(
        tmp_path: Path) -> None:
    import keyed_sources as K
    desk = tmp_path / "desks" / "mt5"
    (desk / "data" / "source_rosters").mkdir(parents=True)
    (desk / "data" / "source_rosters" / "keyed_sources.json").write_text(
        json.dumps({"sources": []}), "utf-8")
    (desk / "data" / "universe").mkdir(parents=True)
    shutil.copy(_DESK / "data" / "universe" / "universe.json",
                desk / "data" / "universe" / "universe.json")
    paths = K.Paths(desk)
    assert paths.intelligence == (desk / "data" / "intelligence",)
    dd.record("kimi", [_raw()], organ="kimi_hunt", root=desk / "data" / "intelligence",
              universe=UNI, may_hypothesise=_may, now=NOW)
    p, _ = _vet(_raw())
    seen: list[str] = []

    def get(req: Any) -> bytes:
        seen.append(req.url)
        if req.url.startswith(dd.PROVIDERS["ECB"]["base"] + "BSI/"):
            return _monthly_csv(40, date(2026, 9, 1))
        raise OSError("offline")

    calls: list[tuple[str, list[dict[str, Any]], int]] = []
    doc = K.run(paths, environ={}, get=get, now=NOW,
                donate=lambda s, c, t: calls.append((s, c, t)) or {"donated": len(c)})
    assert seen and all(u.startswith(dd.PROVIDERS["ECB"]["base"]) for u in seen)
    rec = doc["sources"][p["id"]]
    assert rec["status"] == "OK" and rec["discovered_by"] == "kimi_hunt"
    assert doc["discovered_sources"]["rows"] == [p["id"]]
    lake = desk / "data" / "lake" / "series" / f"{dd.lake_series(p)}.csv"
    head = lake.read_text("utf-8").splitlines()[0].split(",")
    assert {"available_time", "z", "chg_z"} <= set(head)
    # the series is an alt_catalog source with PIT z specs (ks_ z / chg_z are verified PIT)
    cat = ac.catalog(lake.parent)
    (row,) = [r for r in cat["series"] if r["series"] == dd.lake_series(p)]
    assert f"alt:{dd.lake_series(p)}:chg_z:gt:0" in row["specs"]
    # backfill is stamped no earlier than period end + the floored lag
    import pandas as pd
    df = pd.read_csv(lake)
    first = df.iloc[0]
    assert (pd.Timestamp(first["available_time"]) - pd.Timestamp(first["event_time"],
                                                                  tz="UTC")).days >= 35
    direct = [c for s, cs, _ in calls if s == K.SEAT for c in cs]
    assert direct and all(c["discovered_by"] == "kimi_hunt" and c["method"] == dd.METHOD
                          for c in direct)
    assert all(t == len(cs) for _, cs, t in calls)          # every minted cell charged


# ----------------------------------------------- alt_catalog provenance and breadth -------
def test_cells_on_discovered_series_carry_provenance_and_are_distinct_breadth(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lake = tmp_path / "lake"
    lake.mkdir()
    names = ["ks_disc_ecb_aaaa1111__m_u2", "ks_disc_bis_bbbb2222__m_us"]
    for n in names:
        rows = [f"2026-01-{i + 1:02d},2026-02-{i + 1:02d}T00:00:00Z,{i},{i % 3 - 1},0.5"
                for i in range(12)]
        (lake / f"{n}.csv").write_text("event_time,available_time,value,z,chg_z\n"
                                       + "\n".join(rows) + "\n", "utf-8")
    monkeypatch.setattr(ac, "discovered", lambda: {n: {"discovered_by": "deepseek",
                                                       "method": dd.METHOD} for n in names})
    cat = ac.catalog(lake)
    assert all(r.get("discovered_by") == "deepseek" for r in cat["series"])
    fam = ac.families()[0]
    text = "\n".join(f"ALT_CELL | {fam} | EURUSD | alt:{n}:z:gt:0 | {MECH}" for n in names)
    cells, why = ac.parse_cells(text, cat=cat, organ="kimi_hunt")
    assert len(cells) == 2 and not why
    assert all(c["discovered_by"] == "deepseek" and c["method"] == dd.METHOD for c in cells)
    ids = {ac._cell(c) for c in cells}
    assert None not in ids and len(ids) == 2


# ----------------------------------------------------------------- funnel by_method -------
def test_method_view_counts_each_stage_and_is_unmeasured_without_a_queue(
        tmp_path: Path) -> None:
    none = dd.method_view(None, roots=[tmp_path / "absent"], lake=tmp_path / "lake")
    m = none[dd.METHOD]
    assert m["proposals"] == dd.UNMEASURED and m["rows"] == dd.UNMEASURED
    assert m["landed"] == dd.UNMEASURED                     # no lake dir on this host

    root = tmp_path / "intel"
    dd.record("kimi", [_raw(), _raw(provider="FRED")], organ="kimi_hunt", root=root,
              universe=UNI, may_hypothesise=_may, now=NOW)
    p, _ = _vet(_raw())
    lake = tmp_path / "lake"
    lake.mkdir()
    (lake / f"{dd.lake_series(p)}.csv").write_text("event_time,available_time,z\n", "utf-8")
    cov = {"series": {dd.lake_series(p): {"generators_seeing": ["deepseek"], "rows": 3,
                                          "testable_rows": 2, "judged": 1, "certified": 0},
                      "ks_bis_policy_rates__policy_rate_US": {
                          "generators_seeing": [], "rows": 5, "testable_rows": 5,
                          "judged": 2, "certified": 1}}}
    v = dd.method_view(cov, roots=[root], lake=lake)
    m = v[dd.METHOD]
    assert {k: m[k] for k in v["stages"]} == {
        "proposals": 2, "accepted": 1, "landed": 1, "offered": 1, "rows": 3, "testable": 2,
        "judged": 1, "certified": 0}
    assert m["rejected_by_reason"] == {"provider_not_on_keyless_allowlist": 1}
    assert m["by_organ"]["kimi_hunt"]["accepted"] == 1
    assert v["registered_sources"]["rows"] == 5
    cov["series"][dd.lake_series(p)]["judged"] = dd.UNMEASURED
    assert dd.method_view(cov, roots=[root], lake=lake)[dd.METHOD]["judged"] == dd.UNMEASURED


def test_the_funnel_build_carries_by_method(tmp_path: Path) -> None:
    from research import funnel
    paths = funnel.Paths.at(tmp_path / "desk")
    assert paths.intelligence == (tmp_path / "desk" / "data" / "intelligence",)
    blk = funnel.method_block(paths, {"series": {}})
    assert blk[dd.METHOD]["proposals"] == dd.UNMEASURED


def test_producer_loop_alt_gaps_lead_with_discovered_series(tmp_path: Path) -> None:
    from research import producer_loop as pl
    f = tmp_path / "FUNNEL.json"
    f.write_text(json.dumps({"by_alt_source": {
        "zero_coverage_series": ["aaa_old", "ks_disc_ecb_x__y"],
        "series": {"ks_disc_ecb_x__y": {"discovered_by": "kimi_hunt"}, "aaa_old": {}}}}),
        "utf-8")
    assert pl.alt_gaps(f) == ["ks_disc_ecb_x__y", "aaa_old"]


def test_prompt_blocks_name_the_line_and_the_json_contract() -> None:
    txt = dd.prompt_block(existing=["WS_CBPOL/M.US/all"])
    assert "DATA_SOURCE |" in txt and "WS_CBPOL/M.US/all" in txt and "ECB" in txt
    assert '"data_sources"' in dd.prompt_block(json_contract=True)
