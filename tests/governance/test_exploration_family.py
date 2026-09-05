"""L1.32 exploration family + L1.33 the second family as standing partner."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.check_exploration import _FAMILY, build_report

from libs.research.second_family import SecondOpinion, blindspot_prompt, merge_verdict


def _seed(root: Path, produced: list[str]) -> None:
    for name in produced:
        rel = _FAMILY[name][0]
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if rel.endswith(".json"):
            p.write_text("{}", "utf-8")
        else:
            p.mkdir(parents=True, exist_ok=True)
            (p / "x.md").write_text("x", "utf-8")


def test_dark_when_any_organ_never_produced(tmp_path):
    _seed(tmp_path, ["capability_hunt", "blindspot_max"])
    rep = build_report(tmp_path)
    assert rep["status"] == "DARK"
    assert "kimi_hunter" in rep["dark"]


def test_ok_when_whole_family_fresh(tmp_path):
    _seed(tmp_path, list(_FAMILY))
    assert build_report(tmp_path)["status"] == "OK"


def test_fence_never_recommends_less_exploration(tmp_path):
    _seed(tmp_path, list(_FAMILY))
    action = build_report(tmp_path)["next_action"].lower()
    assert "re-aim" in action and "never silence" in action
    # L1.8/L1.25a: no path in this organ may ever propose throttling a hunter.
    src = Path("scripts/check_exploration.py").read_text("utf-8").lower()
    assert "only ever demand more exploration" in src


def test_solo_is_never_reported_as_confirmed():
    op = SecondOpinion(False, reason="OpenRouter 402 -- unfunded")
    v = merge_verdict("my findings", op)
    assert v["verdict"] == "SOLO"
    assert "NOT cross-family corroboration" in v["note"]


def test_confirmed_requires_both_families():
    v = merge_verdict("my findings", SecondOpinion(True, text="they missed X"))
    assert v["verdict"] == "CONFIRMED"
    assert "DELTA" in v["note"]                    # the delta is the finding, not an average


def test_contested_when_only_partner_found_something():
    v = merge_verdict("", SecondOpinion(True, text="you missed X entirely"))
    assert v["verdict"] == "CONTESTED"


def test_partner_brief_hunts_the_miss_not_a_rerank():
    p = blindspot_prompt("blindspot_max", "finding one")
    assert "NOT TO REVIEW OR RE-RANK" in p
    assert "MISSED:" in p and "NOTHING MISSED" in p   # an honest null is a valid partner answer


def test_organs_import_the_shared_partner_not_a_copy():
    # R0114: the ask/merge/record pattern lives in EXACTLY one place -- the shared helper -- and
    # every family organ calls it, so there is no per-organ copy to drift. STRICTLY STRONGER than
    # the pre-R0114 form of this test, which fenced blindspot_max alone.
    helper = Path("libs/llm/second_opinion.py").read_text("utf-8")
    assert "from libs.research.second_family import" in helper
    # the partner must never be able to break the organ that calls it
    assert "the partner must never break the organ" in helper
    for organ in ("scripts/blindspot_max.py", "scripts/blindspot_prober.py",
                  "scripts/run_deep_sweep.py"):
        src = Path(organ).read_text("utf-8")
        assert "from libs.llm.second_opinion import consult_second_family" in src, organ
        assert "the partner must never break the organ" in src, organ
        # no organ re-imports the primitives directly -- that is how copies drift
        assert "from libs.research.second_family import" not in src, organ


def test_blindspot_dark_seat_is_recorded_solo_and_never_raises(tmp_path, monkeypatch, capsys):
    # The organ's dark path: an unfunded/blocked seat degrades to a RECORDED SOLO verdict in the
    # organ's own artifact -- never an exception, never a fake confirmation, exit-0 preserved.
    from libs.llm.second_opinion import consult_second_family

    monkeypatch.setattr(
        "libs.research.second_family.ask_second_family",
        lambda prompt, *, context, timeout=300.0: SecondOpinion(
            False, reason="OpenRouter 402 -- unfunded", context=context),
    )
    art = tmp_path / "blindspot_probes.json"
    art.write_text(json.dumps({"n_probes": 3}), "utf-8")
    block = consult_second_family("blindspot_prober", {"n_probes": 3}, artifact=art)
    assert block["verdict"] == "SOLO"
    recorded = json.loads(art.read_text("utf-8"))
    assert recorded["n_probes"] == 3                      # the organ's own output is untouched
    assert recorded["second_family"]["verdict"] == "SOLO"
    assert recorded["second_family"]["text"] == ""
    assert "second family: SOLO" in capsys.readouterr().out


def test_deep_sweep_partner_fault_skips_without_breaking_the_organ(tmp_path, monkeypatch, capsys):
    # A LOCAL fault (partner primitives blow up) must degrade to SKIPPED, not an exception:
    # the sweep's cadence never depends on the partner being alive.
    from libs.llm.second_opinion import consult_second_family

    def _boom(prompt, *, context, timeout=300.0):
        raise RuntimeError("partner exploded")

    monkeypatch.setattr("libs.research.second_family.ask_second_family", _boom)
    art = tmp_path / "20260804_second_family.json"       # deep_sweep sidecar: not yet on disk
    block = consult_second_family("deep_sweep", {"auditors": {}}, artifact=art)
    assert block["verdict"] == "SKIPPED" and "partner exploded" in block["reason"]
    assert not art.exists()                              # nothing half-written on the fault path
    assert "second family: SKIPPED" in capsys.readouterr().out


def test_blindspot_available_partner_is_recorded_into_a_fresh_artifact(tmp_path, monkeypatch):
    # deep_sweep's sidecar artifact does not pre-exist; the helper must create it rather than die.
    from libs.llm.second_opinion import consult_second_family

    monkeypatch.setattr(
        "libs.research.second_family.ask_second_family",
        lambda prompt, *, context, timeout=300.0: SecondOpinion(
            True, text="MISSED: x" * 4000, context=context),
    )
    art = tmp_path / "second_family.json"
    block = consult_second_family("deep_sweep", {"auditors": {"a": "COMPLETE"}}, artifact=art)
    assert block["verdict"] == "CONFIRMED"
    recorded = json.loads(art.read_text("utf-8"))
    assert recorded["second_family"]["verdict"] == "CONFIRMED"
    assert len(recorded["second_family"]["text"]) == 4000    # capped, same as blindspot_max


def test_laws_present_and_mapped():
    const = " ".join(Path("docs/CONSTITUTION.md").read_text("utf-8").replace("**", "").split())
    assert "L1.32 THE UNKNOWN-UNKNOWN ORGANS ARE ONE FAMILY" in const
    assert "L1.33 THE TWO FAMILIES WORK TOGETHER" in const
    # REPOINTED 2026-09-05: the organ-facing address for both laws is docs/LAWS.md since the
    # 2026-08-25 doctrine compaction ("the sprawling duty text that used to live here is compacted
    # there ... with zero law regression"). The doctrine still routes organs there by name, which
    # is asserted too, so the delegation cannot quietly break.
    laws = Path("docs/LAWS.md").read_text("utf-8")
    assert "L1.32" in laws and "L1.33" in laws
    assert "docs/LAWS.md" in Path("ops/principal_doctrine.txt").read_text("utf-8")
    mx = Path("scripts/build_enforcement_matrix.py").read_text("utf-8")
    assert '"L1.32"' in mx and '"L1.33"' in mx
    assert "check_exploration.py" in Path("ops/crontab.manifest").read_text("utf-8")
