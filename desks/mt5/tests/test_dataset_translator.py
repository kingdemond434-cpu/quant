"""The dataset translator (TRANSLATION RULE, principal 2026-11-18): every ontology symbol is a
registry symbol, the named examples infer the right country / commodity / currency, cells land
only on hypothesis-lane symbols and only from a real series, the wired share is the arithmetic it
claims to be, and a dataset added to a roster is mapped on the very next pass.

Every input is planted under `tmp_path`; the only repository files read are the ontology and the
broker registry, which are the things under test.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import dataset_translator as dt  # noqa: E402

REG = dt.tradable_registry()
ONTO, DROPPED = dt.load_ontology(REG)


def _roster(path: Path, sources: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"sources": sources}), "utf-8")
    return path


def _datasets(tmp: Path, *, free_stack: list[dict[str, Any]] | None = None,
              deep_forest: list[dict[str, Any]] | None = None,
              stems: dict[str, Path] | None = None) -> list[dict[str, Any]]:
    df = tmp / "df.jsonl"
    df.write_text("\n".join(json.dumps(r) for r in deep_forest or []), "utf-8")
    return dt.enumerate_datasets(
        registry=REG, stems=stems or {},
        free_stack=_roster(tmp / "fs.json", free_stack or []), deep_forest=df,
        axes=tmp / "no_axes", keyed=tmp / "no_keyed.json", env_keys=tmp / "no_keys.json")


def _lake(tmp: Path, stem: str, cols: str = "available_time,value") -> dict[str, Path]:
    lake = tmp / "lake"
    lake.mkdir(exist_ok=True)
    p = lake / f"{stem}.csv"
    p.write_text(cols + "\n2026-01-01T00:00:00Z,1.0\n", "utf-8")
    return dt.lake_stems(lake)


def _gate(sym: str, fam: str) -> bool:
    from research.universe_policy import may_hypothesise
    return bool(may_hypothesise(sym, fam))


def _infer(**kw: Any) -> tuple[list[str], list[str]]:
    trad, ents, _ = dt.infer(dt._ds("t:1", "test", **kw), ONTO, REG)
    return trad, ents


# ------------------------------------------------------------------------------ ontology ---
def test_every_ontology_symbol_is_a_registry_symbol_and_never_a_share() -> None:
    raw = json.loads(dt.ONTOLOGY.read_text("utf-8"))
    seen: list[str] = []
    for sect in ("countries", "central_banks", "commodities", "sectors"):
        for row in raw[sect].values():
            for k in ("fx", "index", "proxy", "cfd", "producer_fx"):
                seen += row.get(k) or []
    for syms in raw["regions"].values():
        seen += syms
    assert seen, "the ontology names no tradable"
    bad = sorted({s for s in seen if s not in REG or REG[s] == "Equities"})
    assert not bad, f"ontology names symbols the registry lacks or share CFDs: {bad}"
    # The economics named some currencies the broker does not list: dropped, counted, never used.
    assert "USDCLP" in raw["dropped_not_in_registry"]
    assert "USDCLP" not in seen


def test_live_recheck_drops_and_counts_a_symbol_the_registry_lost(tmp_path: Path) -> None:
    onto = json.loads(dt.ONTOLOGY.read_text("utf-8"))
    onto["countries"]["SE"]["fx"].append("USDXYZ")
    p = tmp_path / "o.json"
    p.write_text(json.dumps(onto), "utf-8")
    got, dropped = dt.load_ontology(REG, p)
    assert "USDXYZ" not in got["countries"]["SE"]["fx"]
    assert dropped["USDXYZ"] == 1


def test_every_family_the_translator_emits_has_a_registered_builder() -> None:
    from research.miner_candidate_compiler import _registered_family
    for fam in dt.EMITTED_FAMILIES:
        assert _registered_family(fam), f"{fam} would land as NO_REGISTERED_BUILDER"


# ----------------------------------------------------------------------------- inference ---
def test_cbe_org_eg_is_egypt() -> None:
    trad, ents = _infer(title="Statistics", url="https://www.cbe.org.eg/en/economic-research")
    assert "central_bank:cbe" in ents and "country:EG" in ents
    assert trad and all(REG.get(s) for s in trad)
    assert "USDEGP" not in trad             # not in the registry: dropped, never invented


def test_riksbank_is_sweden_and_the_sek_pairs() -> None:
    trad, ents = _infer(title="Underlying inflation", url="https://www.riksbank.se/en-gb/x")
    assert "central_bank:riksbank" in ents and "country:SE" in ents
    assert trad[0] in ("USDSEK", "EURSEK")
    assert {"USDSEK", "EURSEK"} <= set(trad)


def test_cnx_dce_is_dalian_iron_ore_and_soy_and_therefore_aud_and_brl() -> None:
    trad, ents = _infer(title="DCE day quotes + member rankings (iron ore, coke, coking coal, "
                              "soy complex, palm oil, corn)", url="http://www.dce.com.cn/x",
                        region="cn", lang="zh")
    assert {"commodity:iron_ore", "commodity:soybeans", "country:CN"} <= set(ents)
    assert {"AUDUSD", "USDBRL", "SOYBEAN"} <= set(trad)


def test_declared_share_cfds_roll_up_to_an_index_and_are_never_tradables() -> None:
    trad, ents = _infer(title="insider filings", declared=["Apple", "NVIDIA"])
    assert "rollup:US_equities" in ents
    assert not {"Apple", "NVIDIA"} & set(trad)
    assert "US500" in trad


def test_a_theme_does_not_drag_a_foreign_dataset_onto_us_indices() -> None:
    trad, _ = _infer(title="Financial Soundness Indicators", url="https://www.cnb.cz/en/x")
    assert "USDCZK" in trad and "US30" not in trad


def test_word_aliases_do_not_fire_inside_other_words() -> None:
    _, ents = _infer(title="cotton harvest report", url="")
    assert "sector:positioning" not in ents      # "cot" must not match "cotton"


# --------------------------------------------------------------------------------- cells ---
def test_cells_land_only_on_symbols_the_lane_policy_allows(tmp_path: Path) -> None:
    stems = _lake(tmp_path, "fs_cnx_dce")
    ds = _datasets(tmp_path, stems=stems, free_stack=[{
        "id": "cnx_dce", "name": "DCE quotes (iron ore, soy complex)", "region": "cn",
        "language": "zh", "url": "http://www.dce.com.cn/x"}])
    refused = {"AUDUSD"}
    rows, cells, nxt = dt.translate(ds, ONTO, REG, stems, {},
                                    gate=lambda s, f: _gate(s, f) and s not in refused)
    assert len(cells) == 1, "one cell per dataset per pass"
    c = cells[0]
    assert c["family"] in dt.EMITTED_FAMILIES and _gate(c["symbol"], c["family"])
    assert c["symbol"] not in refused
    assert c["params"]["source"] == "fs_cnx_dce" and c["params"]["signal"] == "value"
    assert rows[0]["status"] == dt.CELL_EMITTED
    # The ring advances: the next pass takes the next (tradable, side), never the same one.
    _, cells2, _ = dt.translate(ds, ONTO, REG, stems, nxt, gate=_gate)
    first = (c["symbol"], c["params"]["side_when_high"])
    assert (cells2[0]["symbol"], cells2[0]["params"]["side_when_high"]) != first


def test_no_policy_mints_nothing(tmp_path: Path) -> None:
    stems = _lake(tmp_path, "fs_cn_weibo")
    ds = _datasets(tmp_path, stems=stems, free_stack=[{"id": "cn_weibo", "name": "Weibo",
                                                      "region": "cn", "url": "https://x.cn/"}])
    rows, cells, _ = dt.translate(ds, ONTO, REG, stems, {}, gate=None)
    assert cells == [] and rows[0]["status"] == dt.CELL_QUEUED


def test_mapped_awaiting_series_never_mints(tmp_path: Path) -> None:
    ds = _datasets(tmp_path, deep_forest=[{
        "title": "Notices and Press releases", "url": "https://www.riksbank.se/en-gb/press/",
        "host": "www.riksbank.se", "region": "se", "lang": "en", "source_hash": "abc"}])
    rows, cells, _ = dt.translate(ds, ONTO, REG, {}, {}, gate=_gate)
    assert cells == []
    assert rows[0]["status"] == dt.AWAITING and "USDSEK" in rows[0]["tradables"]
    # A series with no point-in-time stamp is not a series the family may read.
    stems = _lake(tmp_path, "df_www_riksbank_se", cols="date,value")
    rows, cells, _ = dt.translate(ds, ONTO, REG, stems, {}, gate=_gate)
    assert cells == [] and rows[0]["status"] == dt.AWAITING


def test_the_moment_a_series_lands_the_awaiting_mapping_is_judged(tmp_path: Path) -> None:
    stems = _lake(tmp_path, "df_www_riksbank_se")
    ds = _datasets(tmp_path, stems=stems, deep_forest=[{
        "title": "Statistics", "url": "https://www.riksbank.se/en-gb/statistics/",
        "host": "www.riksbank.se", "region": "se", "source_hash": "abc"}])
    _, cells, _ = dt.translate(ds, ONTO, REG, stems, {}, gate=_gate)
    assert len(cells) == 1 and "SEK" in cells[0]["symbol"]


def test_a_refused_host_is_blocked_on_terms_and_mints_nothing(tmp_path: Path) -> None:
    stems = _lake(tmp_path, "fs_reddit")
    ds = _datasets(tmp_path, stems=stems, free_stack=[{"id": "reddit", "name": "Reddit gold",
                                                      "url": "https://www.reddit.com/r/x"}])
    rows, cells, _ = dt.translate(ds, ONTO, REG, stems, {}, gate=_gate)
    assert cells == []
    assert rows[0]["status"] == dt.UNMAPPABLE
    assert rows[0]["reason"].startswith("BLOCKED_ON_TERMS") and rows[0]["missed_growth"]


def test_the_per_pass_cap_queues_the_rest_with_a_missed_growth_line(tmp_path: Path) -> None:
    stems: dict[str, Path] = {}
    for sid in ("cn_weibo", "cn_guba", "cn_xueqiu"):
        stems = _lake(tmp_path, f"fs_{sid}")
    ds = _datasets(tmp_path, stems=stems, free_stack=[
        {"id": s, "name": s, "region": "cn", "url": "https://x.cn/"}
        for s in ("cn_weibo", "cn_guba", "cn_xueqiu")])
    rows, cells, nxt = dt.translate(ds, ONTO, REG, stems, {}, gate=_gate, per_pass=2)
    assert len(cells) == 2
    queued = [r for r in rows if r["status"] == dt.CELL_QUEUED]
    assert len(queued) == 1 and queued[0]["missed_growth"]
    _, cells2, _ = dt.translate(ds, ONTO, REG, stems, nxt, gate=_gate, per_pass=2)
    got = {c["dataset_id"] for c in cells + cells2}
    assert len(got) == 3, "the rotating offset reaches the queued dataset on the next pass"


# ------------------------------------------------------------------------------- summary ---
def test_wired_share_is_mapped_over_all() -> None:
    rows = [{"kind": "a", "status": dt.AWAITING, "tradables": ["EURUSD"]},
            {"kind": "a", "status": dt.CELL_EMITTED, "tradables": ["USDJPY"],
             "declared_tradables": ["USDJPY"]},
            {"kind": "b", "status": dt.UNMAPPABLE, "tradables": [], "reason": "no evidence"},
            {"kind": "b", "status": dt.UNMAPPABLE, "tradables": [],
             "reason": "BLOCKED_ON_TERMS: x"}]
    s = dt.summarise(rows, Counter({"USDCLP": 2}))
    assert s["datasets"] == 4 and s["mapped"] == 2 and s["wired_share"] == 0.5
    assert s["wired_share_declared_only"] == 0.25
    assert s["by_status"] == {dt.AWAITING: 1, dt.CELL_EMITTED: 1, dt.UNMAPPABLE: 2}
    assert s["unmappable_reasons"] == {"no evidence": 1, "BLOCKED_ON_TERMS": 1}
    assert s["dropped_not_in_registry"] == {"symbols": 1, "count": 2, "names": ["USDCLP"]}


def test_a_dataset_added_to_a_roster_is_mapped_on_the_next_pass(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fs = _roster(tmp_path / "fs.json", [{"id": "cn_weibo", "name": "Weibo", "region": "cn",
                                         "url": "https://m.weibo.cn/"}])
    df = tmp_path / "df.jsonl"
    df.write_text("", "utf-8")
    for name, val in {"FREE_STACK": fs, "DEEP_FOREST": df, "AXES": tmp_path / "axes",
                      "KEYED": tmp_path / "k.json", "ENV_KEYS": tmp_path / "e.json",
                      "LAKE": tmp_path / "lake", "CURSOR": tmp_path / "cursor.json",
                      "REPORT": tmp_path / "DATASET_TRANSLATION.json"}.items():
        monkeypatch.setattr(dt, name, val)
    assert dt.main(["--once", "--dry-run"]) == 0
    rep = json.loads((tmp_path / "DATASET_TRANSLATION.json").read_text("utf-8"))
    assert [r["id"] for r in rep["rows"]] == ["free_stack:cn_weibo"]
    # A new source lands on the roster between passes. Nothing else changes.
    _roster(fs, [{"id": "cn_weibo", "name": "Weibo", "region": "cn", "url": "https://m.weibo.cn/"},
                 {"id": "no_norges", "name": "Norges Bank rate path",
                  "url": "https://www.norges-bank.no/en/"}])
    assert dt.main(["--once", "--dry-run"]) == 0
    rep = json.loads((tmp_path / "DATASET_TRANSLATION.json").read_text("utf-8"))
    row = {r["id"]: r for r in rep["rows"]}["free_stack:no_norges"]
    assert row["status"] == dt.AWAITING
    assert "central_bank:norges_bank" in row["entities"] and "USDNOK" in row["tradables"]
    assert rep["datasets"] == 2 and rep["wired_share"] == 1.0


def test_an_unclaimed_lake_series_is_a_dataset_of_its_own(tmp_path: Path) -> None:
    stems = _lake(tmp_path, "br_conab_soy_crop")
    ds = _datasets(tmp_path, stems=stems)
    assert [d["id"] for d in ds] == ["lake:br_conab_soy_crop"]
    rows, cells, _ = dt.translate(ds, ONTO, REG, stems, {}, gate=_gate)
    assert rows[0]["status"] == dt.CELL_EMITTED and "country:BR" in rows[0]["entities"]
    assert cells[0]["params"]["source"] == "br_conab_soy_crop"
