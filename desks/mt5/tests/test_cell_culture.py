"""Culture provenance on every cell: the schema, the one inference rule, the doors and the index.

Every path the index reads or writes is redirected into `tmp_path`; the registry is a throwaway
file. The tests that matter most are the ones that prove UNMEASURED stays UNMEASURED -- a
survivor's culture is never the symbol's home, and a row nothing speaks for is never guessed.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import cell_culture as CC  # noqa: E402
from research import cell_culture_index as X  # noqa: E402


# --------------------------------------------------------------------------------- the schema
def test_every_inference_is_schema_valid_and_names_its_rule() -> None:
    for row in ({"symbol": "JPN225"}, {"symbol": "XAUUSD"}, {},
                {"symbol": "USDKRW", "claim": "개미 투자자들이 추격 매수"}):
        got = CC.infer(row)
        assert CC.validate(got) == []
        for f in CC.FIELDS:
            how = got[CC.DERIVATION_FIELD][f]
            assert how in (CC.DECLARED, CC.UNMEASURED) or how.startswith("inferred:")


def test_validator_names_every_breach() -> None:
    bad = {"source_culture": "Korea", "participant_structure": "whales",
           "failure_mode_hypothesis": "", "crowding_prior": "extreme"}
    problems = " ".join(CC.validate(bad))
    for word in ("source_culture", "participant_structure", "failure_mode_hypothesis",
                 "crowding_prior"):
        assert word in problems
    assert any("absent" in p for p in CC.validate({}))


def test_nothing_on_the_row_is_unmeasured_never_guessed() -> None:
    got = CC.infer({"symbol": "XAUUSD", "family": "carry"})
    assert got["source_culture"] == CC.UNMEASURED
    assert got["failure_mode_hypothesis"] == CC.UNMEASURED
    assert got["crowding_prior"] == CC.UNMEASURED


def test_symbol_home_is_the_weakest_rule_and_always_named() -> None:
    got = CC.infer({"symbol": "JPN225"})
    assert got["source_culture"] == "JP/ja"
    assert got[CC.DERIVATION_FIELD]["source_culture"] == "inferred:symbol_home"
    assert not CC.is_source_derived(got[CC.DERIVATION_FIELD])
    assert CC.symbol_home("USDKRW") == "KR" and CC.symbol_home("USDCNH") == "CN"
    assert CC.symbol_home("EURUSD") == "EA" and CC.symbol_home("XAUUSD") is None


@pytest.mark.parametrize(("row", "culture", "rule"), [
    ({"source_id": "pack:ru:official:ru_cbr"}, "RU/ru", "inferred:ground_position"),
    ({"source": "miner:asia:safe_fx_settlement"}, "CN/zh", "inferred:asia_sources"),
    ({"source_url": "https://www.boj.or.jp/statistics/index.htm"}, "JP/ja",
     "inferred:deep_forest_host"),
    ({"source_url": "https://unregistered-example.co.jp/stat"}, "JP/ja", "inferred:url_tld"),
    ({"claim": "Банк России держит ставку"}, "RU/ru", "inferred:script_cyrillic"),
    ({"claim": "日銀の介入でドル円が反落"}, "JP/ja", "inferred:script_kana"),
    ({"claim": "央行中间价连续走强"}, "CN/zh", "inferred:script_han"),
    ({"source": "miner:followme_cn"}, "CN/zh", "inferred:seat_name"),
    ({"source": "ext_forexfactory_CADJPY_session_range_breakout"}, "GLOBAL",
     "inferred:global_english_venue"),
    ({"source": "fund_playbook:aqr:A"}, "US/en", "inferred:fund_domicile"),
])
def test_source_rules_fire_in_order(row: dict[str, Any], culture: str, rule: str) -> None:
    got = CC.infer({"symbol": "EURUSD", "family": "carry", **row})
    assert (got["source_culture"], got[CC.DERIVATION_FIELD]["source_culture"]) == (culture, rule)
    assert CC.is_source_derived(got[CC.DERIVATION_FIELD])


def test_physical_gold_policy_and_retail_structures_from_evidence() -> None:
    gold = CC.infer({"symbol": "XAUUSD", "region": "ae", "claim": "Dubai gold premium widens"})
    assert (gold["source_culture"], gold["participant_structure"]) == ("AE/ar", "physical_flow")
    assert "physical" in gold["failure_mode_hypothesis"]
    pboc = CC.infer({"symbol": "USDCNH", "source_id": "pack:cn:official:pboc"})
    assert pboc["participant_structure"] == "policy_driven"
    ants = CC.infer({"symbol": "USDKRW", "claim": "개미 투자자들이 추격 매수"})
    assert (ants["source_culture"], ants["participant_structure"]) == ("KR/ko", "retail_heavy")


def test_crowding_prior_low_high_and_unmeasured() -> None:
    kr = {"symbol": "USDKRW", "family": "asia_momentum", "claim": "개미 추격 매수"}
    assert CC.infer(kr, english_families=frozenset({"carry"}))["crowding_prior"] == "low"
    # an English source already covers the family: not low, and nothing else is guessed
    assert CC.infer(kr, english_families=frozenset({"asia_momentum"}))["crowding_prior"] == (
        CC.UNMEASURED)
    # the English-coverage set is unmeasured: low can never be inferred
    assert CC.infer(kr, english_families=None)["crowding_prior"] == CC.UNMEASURED
    rsi = {"symbol": "EURUSD", "family": "mean_reversion_rsi",
           "source_title": "The RSI trick that works when the price is oversold in the session"}
    assert CC.infer(rsi, english_families=None)["crowding_prior"] == "high"


def test_legacy_plain_keys_are_normalised_not_dropped() -> None:
    """#118's specialist_cell / residual_search emitted the pre-schema form: bare "US", no
    crowding prior. The door normalises it and never drops it."""
    got = CC.normalise({"source_culture": "US", "participant_structure": "retail_heavy"})
    assert got["source_culture"] == "US/en" and got["crowding_prior"] == CC.UNMEASURED
    assert got[CC.DERIVATION_FIELD]["source_culture"] == CC.DECLARED
    assert CC.infer({"source_culture": "kr"})["source_culture"] == "KR/ko"
    assert CC.normalise({"participant_structure": "whales"})["participant_structure"] == (
        CC.UNMEASURED)


def test_a_carried_value_keeps_the_rule_that_first_reached_it() -> None:
    first = CC.infer({"source": "miner:followme_cn", "symbol": "EURUSD"})
    again = CC.infer({**first, "symbol": "GBPUSD"})
    assert again[CC.DERIVATION_FIELD]["source_culture"] == "inferred:seat_name"


def test_carry_never_raises_and_keeps_declared_values() -> None:
    row = {"symbol": "EURUSD", "source_culture": "BR/pt"}
    CC.carry(row, {"url": "https://www.mql5.com/x"})
    assert row["source_culture"] == "BR/pt"
    assert CC.validate(row) == []


# ----------------------------------------------------------------------------------- the doors
def test_compiled_candidates_carry_the_donors_culture() -> None:
    from research import miner_candidate_compiler as mcc
    row = {"symbol": "USDJPY", "family": "asia_momentum", "params": {"rr": 1.5},
           "url": "https://kabutan.jp/news", "title": "ミセス・ワタナベの逆張り",
           "source_culture": "JP/ja"}
    cand = mcc._candidate("USDJPY", "asia_momentum", {"rr": 1.5}, "minfx_jp", row, "m")
    assert cand["source_culture"] == "JP/ja"
    assert cand["participant_structure"] == "retail_heavy"
    assert cand[CC.DERIVATION_FIELD]["source_culture"] == CC.DECLARED
    assert CC.validate(cand) == []


def test_the_registry_stamps_culture_at_both_doors(tmp_path: Path,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.moat import registry as R
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    try:
        did, _ = R.record_discovery(source_id="pack:kr:official:bok", source_type="data_pack",
                                    mechanism="m", origin="pack_cells", generator="pack_cells")
        cid, _ = R.enqueue_candidate(family="carry", symbol="USDKRW", params={"a": 1},
                                     origin="DESK", discovery_id=did, source_culture="KR")
        conn = R.connect()
        d = conn.execute("select source_culture, participant_structure from discoveries "
                         "where discovery_id=?", (did,)).fetchone()
        c = conn.execute("select source_culture, culture_derivation from research_candidates "
                         "where id=?", (cid,)).fetchone()
        conn.close()
        assert tuple(d) == ("KR/ko", "policy_driven")
        assert c["source_culture"] == "KR/ko"
        assert json.loads(c["culture_derivation"])["source_culture"] == CC.DECLARED
    finally:
        R.set_path(None)


def test_the_docket_feed_carries_the_registry_columns() -> None:
    from libs.moat import docket_feed as DF
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("create table research_candidates(seq integer primary key, id text, "
                 "symbol text, family text, params_json text, chart text, origin text, "
                 "mechanism text, grid_cell text, score real, created_at text, "
                 "content_hash text, judged_at text, status text, source_culture text, "
                 "participant_structure text, failure_mode_hypothesis text, "
                 "crowding_prior text, culture_derivation text)")
    conn.execute("insert into research_candidates(id,symbol,family,params_json,source_culture,"
                 "culture_derivation) values('c1','USDKRW','carry','{}','KR/ko',"
                 "'{\"source_culture\": \"declared\"}')")
    rows = list(DF.candidate_rows(conn))
    assert rows[0]["source_culture"] == "KR/ko"
    assert rows[0]["culture_derivation"] == {"source_culture": "declared"}


def test_deep_forest_works_culture_gap_grounds_first_and_drops_none() -> None:
    from research import deep_forest_miner as dfm
    grounds = [{"name": f"{r}{i}", "region": r, "weight": 1.0} for r in ("us", "kr") for i in
               range(2)]
    plain = [g["name"] for g in dfm.schedule(grounds, 0)]
    gapped = [g["name"] for g in dfm.schedule(grounds, 0, gaps=frozenset({"kr"}))]
    assert sorted(plain) == sorted(gapped)
    assert gapped[:2] == ["kr0", "kr1"]


# ------------------------------------------------------------------------------------ the index
def test_iter_json_array_streams_every_element(tmp_path: Path) -> None:
    for doc in ([], [1, 2, {"a": "]"}], [{"x": "y" * 3000} for _ in range(40)]):
        f = tmp_path / "d.json"
        f.write_text(json.dumps(doc, indent=1), encoding="utf-8")
        assert list(X.iter_json_array(f, chunk=64)) == doc


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    reports = tmp_path / "reports"
    monkeypatch.setattr(X, "INDEX", reports / "CELL_CULTURE_INDEX.jsonl")
    monkeypatch.setattr(X, "SUMMARY", reports / "CELL_CULTURE.json")
    monkeypatch.setattr(X, "CURSOR", reports / "cell_culture_cursor.json")
    graph = tmp_path / "hypothesis_graph.jsonl"
    rows = [
        {"id": "g1", "symbol": "USDKRW", "family": "asia_momentum", "fate": "BORN",
         "source": "miner:korea", "why": "개미 추격", "params": {}},
        {"id": "g2", "symbol": "EURUSD", "family": "carry", "fate": "BORN",
         "source": "miner:discovery_compiler", "params": {}},
        {"id": "g2", "symbol": "EURUSD", "family": "carry", "fate": "FAILED",
         "source": "miner:discovery_compiler", "params": {}},
    ]
    graph.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    docket = tmp_path / "external_survivors.json"
    docket.write_text(json.dumps([
        {"genome_id": "g3", "symbol": "USDJPY", "family": "session_range_breakout",
         "params": {}, "source": "ext_forexfactory_USDJPY_session_range_breakout"},
        {"genome_id": "g4", "symbol": "XAUUSD", "family": "carry", "params": {},
         "source": "miner:discovery_compiler"}]), encoding="utf-8")
    certs = tmp_path / "UNIVERSAL_SURVIVORS.json"
    certs.write_text(json.dumps({"survivors": {
        "external.USDJPY.session_range_breakout": {
            "cell": "USDJPY.session_range_breakout",
            "shadow_spec": {"symbol": "USDJPY", "family": "session_range_breakout"}},
        "external.XAUUSD.carry": {
            "cell": "XAUUSD.carry", "shadow_spec": {"symbol": "XAUUSD", "family": "carry"}},
    }}), encoding="utf-8")
    sleeves = tmp_path / "sleeves.json"
    sleeves.write_text(json.dumps({"sleeves": [
        {"name": "gold_london", "symbol": "XAUUSD", "family": "session_window",
         "status": "LIVE"}]}), encoding="utf-8")
    shadow = tmp_path / "shadow"
    shadow.mkdir()
    (shadow / "shadow_state.json").write_text(json.dumps({
        "USDKRW.asia": {"status": "ACTIVE"}, "EURUSD.asia": {"status": "RETIRED_ORPHAN"}}),
        encoding="utf-8")
    return {"graph": graph, "docket": docket, "certificates": certs, "sleeves": sleeves,
            "shadow_dir": shadow, "registry": tmp_path / "absent.sqlite",
            "donations": tmp_path / "no_donations"}


def _run(world: dict[str, Path], budget: float = 60.0) -> dict[str, Any]:
    return X.run(budget, **world)  # type: ignore[arg-type]


def _index(world: dict[str, Path]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for line in X.INDEX.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        out[row.get("cell_id") or row["id"]] = row
    return out


def test_tiers_resolve_first_and_publish_their_coverage(world: dict[str, Path]) -> None:
    doc = _run(world)
    tiers = doc["tiers"]
    assert tiers["a_survivors"]["n"] == 2
    assert tiers["b_live_forward"]["n"] == 2          # the LIVE sleeve + the ACTIVE clock
    assert tiers["c_backlog"]["n"] == 2               # two BORN graph cells
    idx = _index(world)
    # (a) with lineage: the forum row names the venue, so the certificate is GLOBAL, en
    usdjpy = idx["USDJPY.session_range_breakout"]
    assert usdjpy["source_culture"] == "GLOBAL"
    assert usdjpy["certificate"] == "external.USDJPY.session_range_breakout"
    assert usdjpy[CC.DERIVATION_FIELD]["source_culture"].startswith("inferred:lineage_docket")
    # (a) whose lineage ends at the compiler with no donation: UNMEASURED WITH A REASON, and the
    # symbol's home is reported beside it, never substituted for it
    gold = idx["XAUUSD.carry"]
    assert gold["source_culture"] == CC.UNMEASURED
    assert gold["culture_reason"] == X.DESK_ORGAN
    live = idx["live:gold_london"]
    assert live["source_culture"] == CC.UNMEASURED and live["culture_reason"] == X.NO_LINEAGE
    # the forward clock on USDKRW inherits the ONE culture its symbol+family carries in the
    # backlog only when that is unanimous -- here the backlog has no USDKRW session_window cell
    assert idx["USDKRW.asia"]["source_culture"] == CC.UNMEASURED
    assert "EURUSD.asia" not in idx                   # retired clocks are not tier (b)


def test_the_backlog_is_incremental_and_the_summary_is_honest(world: dict[str, Path]) -> None:
    first = _run(world)
    assert first["stores"]["graph"]["lines_this_pass"] == 3
    second = _run(world)
    assert second["stores"]["graph"]["lines_this_pass"] == 0
    # aggregates persist across passes: the same cells, counted once
    assert second["headline"]["cells"]["cells"] == first["headline"]["cells"]["cells"] == 2
    with world["graph"].open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"id": "g5", "symbol": "USDTRY", "family": "carry",
                             "fate": "BORN", "claim": "Türk yatırımcı",  # noqa: RUF001
                             "params": {}}) + "\n")
    third = _run(world)
    assert third["stores"]["graph"]["lines_this_pass"] == 1
    assert third["headline"]["cells"]["cells"] == 3
    h = third["headline"]["cells"]
    assert h["non_western_cells"]["non_western"] >= 1
    assert h["survivors"] == 2
    assert isinstance(h["share_unmeasured"]["source_culture"], float)


def test_an_empty_denominator_is_unmeasured_not_zero(world: dict[str, Path]) -> None:
    world["graph"].write_text("", encoding="utf-8")
    doc = _run(world)
    assert doc["headline"]["cells"]["share_culture_inferred"] == CC.UNMEASURED


def test_gaps_name_zero_and_thin_culture_ground_and_reach_the_producers(
        world: dict[str, Path]) -> None:
    X.write(_run(world))
    doc = json.loads(X.SUMMARY.read_text(encoding="utf-8"))
    gaps = {(g["asset_class"], g["culture"], g["participant_structure"]): g
            for g in doc["gaps"]}
    assert ("metals", "AE/ar", "physical_flow") in gaps
    assert gaps[("metals", "AE/ar", "physical_flow")]["state"] == "ZERO"
    assert ("fx", "BR/pt", "retail_heavy") in gaps
    # the Korean backlog cell came from a Korean source: KR fx is THIN, never ZERO
    kr = [g for g in doc["gaps"] if g["culture"] == "KR/ko" and g["asset_class"] == "fx"]
    assert kr and all(g["state"] == "THIN" for g in kr)
    cultures = X.gap_cultures(X.SUMMARY)
    assert "ae" in cultures and "br" in cultures
    assert cultures.index("ae") < cultures.index("kr")      # ZERO before THIN
    assert X.gap_cultures(X.SUMMARY.parent / "absent.json") == []


def test_the_index_carries_the_join_keys_tier_s_reads(world: dict[str, Path]) -> None:
    """research/culture_orthogonality.py (#113) keys CELL_CULTURE_INDEX.jsonl by
    `cell_id or cell or key or id`, hunt prefix stripped: the certificate rows must answer
    under exactly the cell the certificate names."""
    _run(world)
    rows = [json.loads(x) for x in X.INDEX.read_text(encoding="utf-8").splitlines()]
    certs = [r for r in rows if r.get("tier") == "a_survivors"]
    assert {r["cell_id"] for r in certs} == {"USDJPY.session_range_breakout", "XAUUSD.carry"}
    assert all(CC.validate(r) == [] for r in rows)
    assert X.strip_hunt("external.EURCHF.discovered.p=ab") == "EURCHF.discovered.p=ab"
