"""Claude-local miner budget: Opus default, earned Fable, and zero novelty = zero tokens.

Principal directive 2026-08-12. The scope tests matter as much as the behaviour tests: this
optimisation must not reach the hypothesis generator, OpenRouter, DeepSeek, Codex, GPT, Kimi or
Qwen, and a boundary maintained only by everyone remembering it lasts until the first busy
afternoon.
"""
from __future__ import annotations

from pathlib import Path

from libs.ops.miner_roi import (
    CHINESE_MINERS,
    FABLE,
    OPUS,
    MinerStats,
    assert_external_untouched,
    cadence_hours,
    model_for,
    rank_elite,
    roi_score,
    tier_for,
)
from libs.ops.novelty_gate import (
    buffer_add,
    decide,
    delta_context,
    fingerprint,
    mark_analysed,
)


def _s(name, **kw):
    return MinerStats(name=name, **kw)


# ------------------------------------------------------------------ §2 Opus is the default
def test_an_ordinary_miner_gets_opus_not_fable() -> None:
    """§2: do not use Fable merely because it is available."""
    out = model_for(_s("litminer"))
    assert out["model"] == OPUS and out["state"] == "OPUS_STANDARD"


def test_every_non_chinese_unranked_miner_defaults_to_opus() -> None:
    for m in ("litminer", "prospector", "dataaxis", "blindrediscovery", "frontier", "moatminer"):
        assert model_for(_s(m))["model"] == OPUS, m


# ------------------------------------------------------------------ §3 the Fable exception
def test_chinese_miners_are_fable_eligible() -> None:
    for m in ("cn_sources", "bilibili", "juejin", "wechat"):
        out = model_for(_s(m))
        assert out["model"] == FABLE and out["state"] == "FABLE_ELITE", m


def test_a_non_chinese_miner_earns_fable_only_by_measurement() -> None:
    """§3B: Fable for a non-Chinese miner requires empirical telemetry, not a nomination."""
    assert model_for(_s("litminer"))["model"] == OPUS
    assert model_for(_s("litminer"), elite_names={"litminer"})["model"] == FABLE


def test_elite_is_ranked_on_downstream_value_never_scrape_volume() -> None:
    """A miner fetching 1,600 rows with no intake is not productive."""
    loud = _s("loud", new_items=1600, input_tokens=90_000, output_tokens=10_000)
    quiet = _s("quiet", new_items=40, input_tokens=9_000, output_tokens=1_000,
               edge_intake_items=6, high_value_findings=2, downstream_tests=1)
    out = rank_elite([loud, quiet])
    assert out["elite"] == ["quiet"], out["ranked"]


def test_a_miner_with_zero_downstream_value_never_becomes_elite() -> None:
    out = rank_elite([_s("dud", new_items=999, input_tokens=50_000, output_tokens=5_000)])
    assert out["elite"] == []


def test_an_unrun_miner_is_unmeasured_not_scored_zero() -> None:
    """Scoring it 0 would rank it beneath a miner measured as useless -- backwards."""
    r = roi_score(_s("fresh"))
    assert r["status"] == "UNMEASURED" and r["score"] is None
    assert "Unknown is not zero" in r["why"]


def test_elite_is_capped_so_everyone_cannot_be_elite() -> None:
    stats = [_s(f"m{i}", input_tokens=1000, output_tokens=100, downstream_tests=10 - i)
             for i in range(6)]
    assert len(rank_elite(stats)["elite"]) <= 2


# ------------------------------------------------------------------ §4 Fable is revocable
def test_a_dry_chinese_miner_cools_despite_fable_eligibility() -> None:
    """THE ORDERING THAT MATTERS. Eligibility decides WHICH model when it runs -- never whether
    a dry run deserves a model at all."""
    out = tier_for(_s("bilibili", consecutive_low_yield=3))
    assert out["state"] == "COOLDOWN"


def test_sustained_zero_yield_hibernates_even_an_elite_miner() -> None:
    out = tier_for(_s("juejin", consecutive_zero_yield=5))
    assert out["state"] == "HIBERNATED"


def test_hibernation_preserves_exploration_and_never_blacklists() -> None:
    """§32: a weak miner cools, it is not deleted."""
    why = tier_for(_s("odd", consecutive_zero_yield=9))["why"]
    assert "NOT deleted" in why and "reactivates" in why


# ------------------------------------------------------------------ §9/§10 cadence follows refill
def test_default_cadence_is_one_substantive_cycle_per_day() -> None:
    assert cadence_hours(_s("m"))["interval_hours"] == 24.0


def test_measured_refill_overrides_the_base_cadence() -> None:
    assert cadence_hours(_s("slow", estimated_refill_h=72.0))["interval_hours"] == 72.0


def test_repeated_low_yield_stretches_the_interval() -> None:
    assert cadence_hours(_s("m", consecutive_low_yield=3))["interval_hours"] == 48.0


def test_hibernation_floors_the_interval_at_a_week() -> None:
    assert cadence_hours(_s("m", consecutive_zero_yield=5))["interval_hours"] >= 168.0


# ------------------------------------------------------------------ §12 zero novelty = zero tokens
def test_no_new_data_suppresses_the_model_call(tmp_path: Path) -> None:
    d = decide(miner="m", root=tmp_path)
    assert not d.invoke and d.status == "NO_NEW_DATA"


def test_a_soft_refusal_never_buys_premium_reasoning(tmp_path: Path) -> None:
    """§23: nothing about a 429 becomes clearer by paying a model to describe it."""
    for st in ("SOFT_REFUSAL", "RATE_LIMIT", "ANTI_BOT", "PARSER_FAILURE", "SIGNATURE_GATE"):
        d = decide(miner="m", source_status=st, root=tmp_path)
        assert not d.invoke and d.status == st, st


def test_a_full_batch_fires_one_call(tmp_path: Path) -> None:
    buffer_add("m", [{"video_id": f"v{i}", "title": f"t{i}"} for i in range(20)], root=tmp_path)
    d = decide(miner="m", root=tmp_path)
    assert d.invoke and d.n_novel == 20 and d.batch is not None


def test_a_partial_batch_is_held_not_dropped(tmp_path: Path) -> None:
    buffer_add("m", [{"video_id": "v1", "title": "t"}], root=tmp_path)
    d = decide(miner="m", root=tmp_path)
    assert not d.invoke and d.n_novel == 1
    assert "HELD, not dropped" in d.why


def test_the_staleness_floor_stops_batching_becoming_a_memory_hole(tmp_path: Path) -> None:
    """THE GUARD ON THE OPTIMISATION. A slow source's evidence must not wait forever for a batch
    it will never fill."""
    buffer_add("m", [{"video_id": "v1", "title": "t"}], root=tmp_path)
    d = decide(miner="m", max_age_h=0.0, root=tmp_path)
    assert d.invoke and "memory hole" in d.why


def test_an_unparseable_buffer_stamp_reads_as_infinitely_old(tmp_path: Path) -> None:
    """L1.41 again: unknown age must not read as fresh, or a row sits in the buffer forever."""
    p = tmp_path / "data"
    p.mkdir(parents=True, exist_ok=True)
    (p / "novelty_buffer.jsonl").write_text(
        '{"video_id":"v1","title":"t","_buffered_utc":"not-a-date"}\n', "utf-8")
    assert decide(miner="m", root=tmp_path).invoke


# ------------------------------------------------------------------ §17 cross-miner dedup
def test_the_same_article_found_by_three_miners_is_reasoned_about_once(tmp_path: Path) -> None:
    item = {"video_id": "BV1", "title": "同一篇文章"}
    buffer_add("miner_a", [item], root=tmp_path)
    mark_analysed([fingerprint(item)], root=tmp_path)
    out = buffer_add("miner_b", [item], root=tmp_path)
    assert out["buffered"] == 0 and out["duplicates_filtered"] == 1


def test_dedup_ignores_the_url_so_mirrors_collapse() -> None:
    a = {"ident": "x", "title": "Same Title", "url": "https://a.example/1"}
    b = {"ident": "x", "title": "same   title", "url": "https://mirror.example/9"}
    assert fingerprint(a) == fingerprint(b)


def test_filtering_removes_from_the_buffer_never_from_intake(tmp_path: Path) -> None:
    item = {"video_id": "BV1", "title": "t"}
    mark_analysed([fingerprint(item)], root=tmp_path)
    assert "never from canonical intake" in buffer_add("m", [item], root=tmp_path)["why"]


# ------------------------------------------------------------------ §18 delta-only context
def test_only_changed_state_is_resent() -> None:
    prev = {"policy": "long unchanged text " * 200, "queue": [1, 2], "hash": "abc"}
    cur = {"policy": "long unchanged text " * 200, "queue": [1, 2, 3], "hash": "abc"}
    d = delta_context(current=cur, previous=prev)
    assert d["changed_keys"] == ["queue"] and d["added_keys"] == []
    assert d["reduction"] > 0.9, d["reduction"]


def test_unchanged_context_produces_an_empty_delta() -> None:
    same = {"a": 1, "b": 2}
    assert delta_context(current=same, previous=same)["delta"] == {}


# ------------------------------------------------------------------ THE SCOPE BOUNDARY
def test_no_external_provider_is_a_local_claude_routing_target() -> None:
    """The directive's hard boundary, as a test rather than a promise."""
    out = assert_external_untouched()
    assert out["ok"] and out["leaked"] == []
    assert set(out["routing_targets"]) == {OPUS, FABLE}


def test_the_out_of_scope_list_names_every_protected_system() -> None:
    out = assert_external_untouched()
    for ext in ("hypothesis_generator", "openrouter", "deepseek", "codex", "gpt", "kimi", "qwen"):
        assert ext in out["external_systems_out_of_scope"], ext


def test_chinese_miner_set_is_explicit_and_non_empty() -> None:
    assert CHINESE_MINERS and "bilibili" in CHINESE_MINERS
