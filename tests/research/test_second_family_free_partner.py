"""The cross-family check runs on a FREE model, never on a paid id the guard refuses."""
from __future__ import annotations

from libs.research import second_family as sf

FREE = ["qwen/qwen3-235b:free", "google/gemma-3-27b-it:free", "openai/gpt-oss-120b:free"]


def test_a_paid_pin_is_replaced_by_a_free_partner_by_vendor_preference() -> None:
    assert sf.partner_model("openai/gpt-5.6-sol-pro", FREE) == "openai/gpt-oss-120b:free"
    assert sf.partner_model("openai/x", ["qwen/a:free"]) == "qwen/a:free"


def test_a_free_pin_is_kept_and_no_free_model_is_none() -> None:
    assert sf.partner_model("meta-llama/l:free", FREE) == "meta-llama/l:free"
    assert sf.partner_model("openai/gpt-5.6-sol-pro", []) is None


def test_every_partner_is_callable_under_the_paid_guard() -> None:
    for pin in ("openai/gpt-5.6-sol-pro", "anthropic/x", "z:free"):
        got = sf.partner_model(pin, FREE)
        assert got is not None and got.endswith(":free")


def test_the_partner_avoids_the_callers_own_vendor_while_another_exists() -> None:
    got = sf.partner_model("openai/gpt-5.6-sol-pro", FREE, avoid_vendors=("openai",))
    assert got == "google/gemma-3-27b-it:free"
    assert sf.partner_model("openai/x:free", FREE, avoid_vendors=("openai",)) != "openai/x:free"
    # only the caller's vendor is free: still answer, and the vendor is recorded on the opinion
    assert sf.partner_model("p", ["openai/a:free"], avoid_vendors=("openai",)) == "openai/a:free"
    assert sf.SecondOpinion(True, model="openai/a:free").to_dict()["partner_vendor"] == "openai"
