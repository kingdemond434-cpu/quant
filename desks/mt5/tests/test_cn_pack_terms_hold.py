"""THE CFETS AND SAFE TERMS HOLD, PINNED FROM THE PACK TO EVERY ORGAN THAT READS IT.

The ruling (PR #229, terms read 2026-10-06): CFETS -- chinamoney.com.cn and shibor.org -- forbids
any use of its market data without written permission, so it is `refused`; SAFE grants no use of
its statistics, so it is `to_confirm` and held fail-closed. These tests pin both halves of what
that means: the rows are NOT deleted (the gap is named, with the clause, the ruling and the lawful
substitute), and NOTHING downstream fetches them, mints a cell from them or credits coverage to
them -- each is counted BLOCKED, never fed and never covered.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import countries.cn.pack as CN  # noqa: E402

from libs.data import terms_fence as TF  # noqa: E402
from libs.research import country_lab as CL  # noqa: E402

CFETS_DATASETS = ("cfets_central_parity", "cfets_onshore_close", "cn_cnh_cny_basis", "cn_shibor")
CLAUSE_WORDS = "without written permission from CFETS"


# ------------------------------------------------------------------------------- the pack
def test_cfets_and_shibor_datasets_read_blocked_on_terms_refused_and_stay_in_the_pack() -> None:
    rows = {d["name"]: d for d in CN.DATASETS}
    for name in CFETS_DATASETS:
        row = rows[name]                                   # never deleted
        assert row["terms_status"] == "BLOCKED_ON_TERMS:refused", name
        assert row["licence"].startswith("BLOCKED_ON_TERMS:refused"), name
        assert row["how_to_fetch"].startswith("BLOCKED_ON_TERMS:refused"), name
        assert CLAUSE_WORDS in row["terms_clause"] and CLAUSE_WORDS in row["licence"], name
        assert "#229" in row["terms_ruling"] and "#229" in row["licence"], name
        assert row["lawful_substitute"].strip(), name
        assert "covered" not in row["licence"].lower(), name
    # The rest of the catalogue is untouched: nothing else is held by this ruling.
    held = {d["name"] for d in CN.DATASETS if CN.is_terms_blocked(d)}
    assert held == set(CFETS_DATASETS)


def test_the_typed_pack_still_carries_the_hold_and_every_row() -> None:
    pk = CN.pack()
    if isinstance(pk, dict):
        pytest.skip("country_lab absent: the rich shape is pinned above")
    names = [d.name for d in pk.datasets]
    assert len(names) == len(CN.DATASETS)
    for d in pk.datasets:
        state, why = TF.row_hold(d)
        assert (state == "refused") == (d.name in CFETS_DATASETS), d.name
        if state:
            assert CLAUSE_WORDS in why and "#229" in why
    fixes = {f.name: TF.row_hold(f)[0] for f in pk.fixing_conventions}
    assert fixes["人民币汇率中间价 (CFETS central parity)"] == "refused"
    assert fixes["CFETS 收盘价 (the 16:30 Beijing reference close)"] == "refused"
    assert fixes["CNH HIBOR (TMA, Hong Kong)"] == ""        # not a CFETS reference
    assert CL.validate_pack(pk) == []


def test_cfets_and_safe_roots_left_the_open_official_class_and_are_held_by_name() -> None:
    by_id = {sc["id"]: sc for sc in CN.SOURCE_CLASSES}
    assert not {"chinamoney.com.cn", "shibor.org", "safe.gov.cn"} & set(by_id["cn_official"]["roots"])
    cfets, safe = by_id["cn_cfets_market_data"], by_id["cn_safe_official"]
    assert set(cfets["roots"]) == {"chinamoney.com.cn", "shibor.org"}
    assert cfets["licence"].startswith("BLOCKED_ON_TERMS:refused")
    assert safe["licence"].startswith("BLOCKED_ON_TERMS:to_confirm")
    # A held class is named, never coverage: it counts toward no layer.
    assert CN.layer_counts([cfets, safe])["official"] == 0
    assert CN.layer_counts(CN.SOURCE_CLASSES)["official"] >= 1


def test_safe_rows_are_to_confirm_and_name_cot_as_the_lawful_positioning_read() -> None:
    by_id = {p["id"]: p for p in CN.POSITIONING_SOURCES}
    for pid in ("safe_fx_settlement", "pboc_reserves"):
        assert by_id[pid]["terms_status"] == "BLOCKED_ON_TERMS:to_confirm"
        assert TF.row_hold(by_id[pid])[0] == "to_confirm"
    assert "COT" in by_id["safe_fx_settlement"]["lawful_substitute"]
    assert "COT" in by_id["cftc_cot_absent"]["note"]
    assert CN.terms_held_rows()["positioning_sources"] == ("safe_fx_settlement", "pboc_reserves")


def test_the_pack_and_the_fence_carry_the_same_ruling() -> None:
    assert CN.TERMS_BLOCKED == TF.TERMS_BLOCKED
    assert CN.TERMS_RULING == TF.RULING
    for ref, (state, clause) in TF.TERMS_REFS.items():
        assert CN.TERMS_RULINGS[ref]["terms"] == state
        assert CN.TERMS_RULINGS[ref]["clause"] == clause


# ------------------------------------------------------------------------------- the fence
@pytest.mark.parametrize(("url", "state"), [
    ("https://www.chinamoney.com.cn/r/cms/www/chinamoney/data/fx/ccpr.json", "refused"),
    ("https://www.chinamoney.com.cn/r/cms/www/chinamoney/data/shibor/shibor.json", "refused"),
    ("http://www.shibor.org/shibor/web/html/index.html", "refused"),
    ("https://www.safe.gov.cn/safe/whxsdsj/index.html", "to_confirm"),
    ("https://www.stats.gov.cn/sj/", ""),
    ("https://notchinamoney.com.cn.example.org/", ""),
])
def test_the_fence_holds_the_named_hosts_and_only_them(url: str, state: str) -> None:
    assert TF.hold_of(url)[0] == state


def test_a_registry_row_is_held_by_its_url_or_its_terms_ref() -> None:
    assert TF.row_hold({"id": "x", "url": "https://www.chinamoney.com.cn/a"})[0] == "refused"
    assert TF.row_hold({"id": "x", "terms_ref": "cn_safe_official"})[0] == "to_confirm"
    assert TF.row_hold({"id": "x", "root": "pbc.gov.cn, safe.gov.cn"})[0] == "to_confirm"
    assert TF.row_hold({"id": "x", "url": "https://www.cftc.gov/dea"}) == ("", "")


# ------------------------------------------------------------------------------- the organs
class _Ctx:
    """A LabCtx stand-in: bars always present, every record captured."""

    def __init__(self) -> None:
        self.recorded: list[dict[str, Any]] = []
        self.notes: dict[str, str] = {}
        self.dry_run = True

    def remaining_s(self) -> float:
        return 60.0

    def note(self, key: str, why: str) -> None:
        self.notes[key] = why

    def bars(self, sym: str, tf: str) -> Any:
        return None

    def rng(self, salt: str = "") -> Any:
        import numpy as np
        return np.random.default_rng(0)

    def record(self, **fields: Any) -> tuple[str, bool]:
        self.recorded.append(fields)
        return "dry-run", False


def _typed_pack() -> Any:
    pk = CN.pack()
    if isinstance(pk, dict):
        pytest.skip("country_lab absent")
    return pk


def test_the_fixing_lab_counts_the_cfets_fixings_blocked_and_measures_nothing_from_them() -> None:
    pk = _typed_pack()
    ctx = _Ctx()
    out = CL.generic_calendar_settlement(pk, ctx)  # type: ignore[arg-type]
    held = {r["fixing"] for r in out["blocked_on_terms"]}
    assert held == {"人民币汇率中间价 (CFETS central parity)",
                    "CFETS 收盘价 (the 16:30 Beijing reference close)"}
    assert all(r["status"] == "BLOCKED_ON_TERMS:refused" for r in out["blocked_on_terms"])
    assert not any("CFETS" in str(r.get("fixing")) for r in out.get("readings") or [])


def test_positioning_and_institutional_miners_mint_no_lead_from_safe() -> None:
    pk = _typed_pack()
    ctx = _Ctx()
    pos = CL.generic_positioning(pk, ctx)  # type: ignore[arg-type]
    assert set(pos["blocked_on_terms"]) == {"safe_fx_settlement", "pboc_reserves"}
    inst = CL.generic_institutional_flow(pk, ctx)  # type: ignore[arg-type]
    assert len(inst["blocked_on_terms"]) == 1 and "SAFE" in inst["blocked_on_terms"][0]
    for rec in ctx.recorded:
        blob = " ".join(str(v) for v in rec.values())
        assert "safe.gov.cn" not in blob and "BLOCKED_ON_TERMS" not in blob, rec


def test_the_acquirer_never_requests_a_held_url(monkeypatch: pytest.MonkeyPatch,
                                                tmp_path: Path) -> None:
    from research import acquire_datasets as AD
    urls = [("https://www.chinamoney.com.cn/r/cms/www/chinamoney/data/fx/ccpr.json", "cm"),
            ("https://www.safe.gov.cn/safe/whxsdsj/index.html", "safe")]
    fetched: list[str] = []
    monkeypatch.setattr(AD, "STORE", tmp_path)
    monkeypatch.setattr(AD, "REGISTRY", tmp_path / "registry.json")
    monkeypatch.setattr(AD, "REPORT", tmp_path / "report.json")
    monkeypatch.setattr(AD, "_endpoints", lambda limit: list(urls))
    monkeypatch.setattr(AD, "_fetch", lambda url: (fetched.append(url), (None, "html"))[1])
    rep = AD.acquire(limit=5)
    assert fetched == []                                   # fail-closed: nothing requested
    assert rep["endpoints_tried"] == 0 and rep["refusals"] == {}
    assert rep["blocked_on_terms"] == {urls[0][0]: "BLOCKED_ON_TERMS:refused",
                                       urls[1][0]: "BLOCKED_ON_TERMS:to_confirm"}


def test_the_acquisition_scientist_files_no_request_for_a_held_row() -> None:
    from research import data_acquisition_scientist as DAS
    rich = dict(CN._rich())
    # Make every held row look ABSENT, which is what would otherwise make it a request.
    rich["datasets"] = tuple({**d, "coverage": d["coverage"] + " (absent here)"}
                             for d in CN.DATASETS)
    rich["positioning_sources"] = tuple({**p, "name": p["name"] + " not collected"}
                                        for p in CN.POSITIONING_SOURCES)
    out, note = DAS.from_country_packs({"cn": rich})
    refs = {c.get("ref") for c in out}
    for name in CFETS_DATASETS:
        assert f"cn.datasets:{name}" not in refs
        assert f"cn.datasets:{name}" in note["blocked_on_terms"]
    assert "cn.positioning_sources:safe_fx_settlement" in note["blocked_on_terms"]
    assert "cn.positioning_sources:safe_fx_settlement" not in refs


def test_the_census_names_the_hold_as_the_blocker_and_credits_nothing(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from research import source_experiment_census as census
    monkeypatch.setattr(census, "ACQUIRED", tmp_path / "none.json")
    monkeypatch.setattr(census, "_codes", lambda: ["cn"])
    doc = census.build()
    rows = {r["source_id"]: r for r in doc["rows"]}
    for name in CFETS_DATASETS:
        row = rows[f"cn:dataset:{name}"]
        assert row["blocker"] == "BLOCKED_ON_TERMS:refused"
        assert row["disposition"] == "UNRESOLVED" and row["urls"] == []
        assert row["coverage"] == "BLOCKED_ON_TERMS:refused"
    assert rows["cn_safe_official"]["blocker"] == "BLOCKED_ON_TERMS:to_confirm"


def test_regional_parity_counts_held_datasets_blocked_never_as_depth() -> None:
    from libs.research import regional_parity as RP
    pk = _typed_pack()
    d = RP.pack_depth(pk, "cn")
    assert d.datasets_blocked_on_terms == len(CFETS_DATASETS)
    assert d.datasets == len(CN.DATASETS) - len(CFETS_DATASETS)
    assert d.as_row()["datasets_blocked_on_terms"] == len(CFETS_DATASETS)


def test_the_forest_tensor_holds_no_cell_for_a_held_source() -> None:
    from research import coverage_tensor as CT
    pk = _typed_pack()
    seen: list[dict[str, str]] = []

    class _Forest:
        def observe(self, values: Any, state: str, evidence: Any, *, at: str) -> None:
            seen.append({"state": state, "why": str(evidence.get("why"))})

    class _Absent:
        def __init__(self) -> None:
            self.notes: dict[str, str] = {}

        def note(self, k: str, why: str) -> None:
            self.notes[k] = why

    class _Conn:
        def execute(self, *a: Any, **k: Any) -> Any:
            raise RuntimeError("no registry here")

    absent = _Absent()
    counts = CT.observe_forest(_Forest(), _Conn(), absent,  # type: ignore[arg-type]
                               {"cn": {"pack": pk, "languages": ["zh-hans"]}}, "2026-10-06")
    assert counts["blocked_on_terms_pack_sources"] == 2
    assert "pack_sources_blocked_on_terms" in absent.notes
    assert not any("cn_cfets_market_data" in s["why"] or "cn_safe_official" in s["why"]
                   for s in seen)


def test_pack_cells_never_makes_a_held_registry_pack_eligible(monkeypatch: pytest.MonkeyPatch,
                                                              tmp_path: Path) -> None:
    from research import pack_cells as PC
    rows = [{"id": "cfets_fixing",
             "url": "https://www.chinamoney.com.cn/r/cms/www/chinamoney/data/fx/ccpr.json",
             "targets": ["USDCNH"]},
            {"id": "safe_fx_settlement", "url": "https://www.safe.gov.cn/safe/whxsdsj/",
             "targets": ["USDCNH"]}]
    emitted: list[str] = []
    monkeypatch.setattr(PC, "packs", lambda: rows)
    monkeypatch.setattr(PC, "chain", lambda: {r["id"]: {"stage_reached": "represented"}
                                              for r in rows})
    monkeypatch.setattr(PC, "series_path", lambda pid: tmp_path / f"{pid}.csv")
    monkeypatch.setattr(PC, "signals_of", lambda p: (["a", "b"], 50, ""))
    monkeypatch.setattr(PC, "emit_for",
                        lambda p, *a, **k: (emitted.append(p["id"]), {"id": p["id"]})[1])
    monkeypatch.setattr(PC, "world_rows", lambda *a, **k: ([], "no world here"))
    monkeypatch.setattr(PC, "_registry_counts", lambda: ({}, "none"))
    monkeypatch.setattr(PC, "judged_registers", lambda: {})
    monkeypatch.setattr(PC, "judged_by_stamped_region", lambda: {})
    monkeypatch.setattr(PC, "drain_reachability", lambda st: {})
    monkeypatch.setattr(PC, "CURSOR", tmp_path / "cursor.json")
    doc = PC.build(budget_s=5.0, dry_run=True)
    assert emitted == []
    assert doc["n_eligible"] == 0
    assert doc["blocked_on_terms"] == ["cfets_fixing", "safe_fx_settlement"]


def test_source_drain_hands_no_held_source_to_the_collector_and_enqueues_none(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from research import source_drain as SD
    srcs = [{"id": "cfets_fixing", "cadence": "daily",
             "url": "https://www.chinamoney.com.cn/r/cms/www/chinamoney/data/fx/ccpr.json"},
            {"id": "safe_reserves", "cadence": "monthly",
             "url": "https://www.safe.gov.cn/safe/whcb/index.html"},
            {"id": "nbs_pmi", "cadence": "monthly", "url": "https://data.stats.gov.cn/x"}]
    handed: list[list[str]] = []
    for name in ("STATE", "RATCHET", "TASKS", "CHAIN_STATE", "OUT", "VAULT", "SERIES"):
        monkeypatch.setattr(SD, name, tmp_path / name.lower())
    monkeypatch.setattr(SD, "_sources", lambda: srcs)
    monkeypatch.setattr(SD, "_credited", lambda: ({}, ""))
    monkeypatch.setattr(SD, "_registry_cells", lambda: ({}, ""))

    def _drain(pending: list[str], budget_s: float, **k: Any) -> dict[str, Any]:
        handed.append(list(pending) + list(k.get("oldest_first") or []))
        return {"attempted": [], "n_attempted": 0}

    monkeypatch.setattr(SD, "drain", _drain)
    monkeypatch.setattr(SD, "repair", lambda rows, order, **k: {
        "parsed_attempted": [r["id"] for r in rows if not r.get("terms")]})
    doc = SD.build(budget_s=5.0, fetch=True)
    assert handed and all(sid == "nbs_pmi" for sid in handed[0])
    assert doc["blocked_on_terms"] == ["cfets_fixing", "safe_reserves"]
    rows = [SD.chain_for(s, {}, {}) for s in srcs]
    assert {r["id"]: r["terms"] for r in rows} == {
        "cfets_fixing": "BLOCKED_ON_TERMS:refused",
        "safe_reserves": "BLOCKED_ON_TERMS:to_confirm", "nbs_pmi": None}


def test_source_drain_repair_parses_and_enqueues_no_held_source(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from research import source_drain as SD
    rows = [{"id": "cfets_fixing", "collected": True, "represented": True, "cells_emitted": 0,
             "targets": ["USDCNH"], "terms": "BLOCKED_ON_TERMS:refused"},
            {"id": "safe_reserves", "collected": True, "represented": False,
             "cells_emitted": 0, "targets": [], "terms": "BLOCKED_ON_TERMS:to_confirm"}]
    import research.asia_parser as AP
    called: list[Any] = []
    monkeypatch.setattr(AP, "parse_all", lambda only=None: called.append(only) or {})
    out = SD.repair(rows, ["cfets_fixing", "safe_reserves"], budget_s=5.0)
    assert out["parsed_attempted"] == [] and out["enqueued"] == [] and called == []
