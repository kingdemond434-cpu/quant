"""The bar never rises with a trial count (principal, 2026-10-13), and the fence keeping it so."""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import check_trial_inflation as fence  # noqa: E402

from libs.research import trial_count_guard as tcg  # noqa: E402

NOW = datetime(2026, 10, 14, tzinfo=UTC)


def _tree(tmp_path: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, "utf-8")
    return tmp_path


def _check(doc: dict, metric: str) -> dict:
    return next(c for c in doc["checks"] if c["metric"] == metric)


def test_bar_n_is_fixed_whatever_it_is_handed() -> None:
    assert tcg.BAR_N == 5
    assert {tcg.bar_n(n) for n in (1, 5, 109, 597, 234_977, None)} == {5}


def test_the_same_spec_is_one_trial_however_it_is_rerun() -> None:
    a = {"family": "Carry", "sym": "eurusd", "tf": "h1", "params": {"lb": 20, "z": 1.5}}
    b = {"family": "carry", "symbol": "EURUSD", "timeframe": "H1",
         "params": {"z": 1.5, "lb": 20.0, "sweep": 7, "run_id": "x"}, "at": "2026-10-13"}
    assert tcg.canonical_trial_id(a) == tcg.canonical_trial_id(b)
    assert tcg.canonical_trial_id(a) != tcg.canonical_trial_id({**a, "params": {"lb": 21}})


def test_a_new_file_with_its_own_trial_count_fails(tmp_path: Path) -> None:
    root = _tree(tmp_path, {"desks/mt5/research/new_miner.py": (
        "from libs.validation.dsr import deflated_sharpe_ratio\n"
        "def judge(arr, n):\n"
        "    return deflated_sharpe_ratio(arr, n_trials=len(arr) * 40)\n")})
    doc = fence.judge(root, now=NOW)
    assert doc["verdict"] == "FAIL"
    site = _check(doc, "unpinned_bar_calls")["sites"][0]
    assert site["file"] == "desks/mt5/research/new_miner.py"


def test_pinned_calls_pass_including_locals_and_conditionals(tmp_path: Path) -> None:
    root = _tree(tmp_path, {"libs/x.py": (
        "from libs.research.trial_count_guard import bar_n, BAR_N\n"
        "def a(arr, n, pc):\n"
        "    k = 1 if pc else bar_n(n)\n"
        "    deflated_sharpe_ratio(arr, n_trials=k)\n"
        "    deflate_t(2.0, bar_n(n))\n"
        "    expected_max_z(BAR_N)\n"
        "    return expected_max_sharpe(1, 0.1)\n"
        "def expected_max_z(n):\n"
        "    return n and expected_max_t(n)\n")})
    assert fence.judge(root, now=NOW)["verdict"] == "PASS"


def test_a_function_that_pins_inside_frees_its_callers_only_if_every_definition_does(
        tmp_path: Path) -> None:
    pinned = ("def trials_penalty(effective_trials):\n"
              "    return bar_n(effective_trials)\n")
    caller = "def f(n):\n    return trials_penalty(n * 9)\n"
    root = _tree(tmp_path, {"a.py": pinned, "b.py": caller})
    assert fence.judge(root, now=NOW)["verdict"] == "PASS"
    _tree(tmp_path, {"c.py": ("def trials_penalty(effective_trials):\n"
                              "    return effective_trials\n")})
    assert fence.judge(root, now=NOW)["verdict"] == "FAIL"


def test_sealed_sites_are_owed_until_the_deadline_then_fail(tmp_path: Path) -> None:
    root = _tree(tmp_path, {"desks/mt5/scripts/external_gauntlet.py": (
        "def charged_lifetime_trials(campaign, family, lifetime, raw):\n"
        "    return max(campaign, lifetime['lifetime_trials'])\n")})
    owed = _check(fence.judge(root, now=NOW), "sealed_trial_charge")
    assert owed["state"] == "WARN" and owed["owner"] == fence.T8_PATCH
    late = _check(fence.judge(root, now=fence.SEALED_DEADLINE), "sealed_trial_charge")
    assert late["state"] == "FAIL"


def test_an_unowned_lifetime_union_fails_at_once(tmp_path: Path) -> None:
    root = _tree(tmp_path, {"libs/elsewhere.py": (
        "def charged_lifetime_trials(c, f, l, r):\n    return l\n")})
    assert _check(fence.judge(root, now=NOW), "sealed_trial_charge")["state"] == "FAIL"


def test_the_rerun_share_is_published_and_ratchets_only_after_the_dedupe(tmp_path: Path) -> None:
    import json
    d = tmp_path / "desks/mt5/data/intelligence/seat"
    d.mkdir(parents=True)
    for i in range(3):                       # the same pass written three times
        (d / f"discoveries_{i}.json").write_text(json.dumps(
            {"tests_run": 100, "discoveries": [{"family": "carry", "sym": "EURUSD"}]}), "utf-8")
    rr = _check(fence.judge(tmp_path, now=NOW, prior={"rerun_share": 0.1}), "ledger_rerun_share")
    assert rr["state"] == "OK" and rr["n_charged"] == 300 and rr["n_distinct"] == 100
    (tmp_path / "desks/mt5/data/TRIAL_DEDUPE_LANDED").write_text("", "utf-8")
    rr = _check(fence.judge(tmp_path, now=NOW, prior={"rerun_share": 0.1}), "ledger_rerun_share")
    assert rr["state"] == "FAIL"


def test_the_live_tree_passes_its_own_fence() -> None:
    doc = fence.judge(ROOT, now=NOW)
    assert _check(doc, "unpinned_bar_calls")["state"] == "OK", \
        _check(doc, "unpinned_bar_calls")["sites"][:5]


# ---- 1b: len(...)-scaled multiplicity written as arithmetic (principal 2026-10-14) -----------

def _one(tmp_path: Path, body: str) -> dict:
    root = _tree(tmp_path, {"desks/mt5/research/screen.py": body})
    return _check(fence.judge(root, now=NOW), "unpinned_bar_calls")


def test_bonferroni_over_len_fails_unpinned(tmp_path: Path) -> None:
    got = _one(tmp_path, "def f(cells, alpha=0.05):\n    return alpha / len(cells)\n")
    assert got["state"] == "FAIL" and got["sites"][0]["call"] == "bonferroni_len"


def test_bonferroni_through_a_local_count_and_a_p_adjustment_fail(tmp_path: Path) -> None:
    got = _one(tmp_path, ("def f(rows, p_raw):\n"
                          "    cells = len(rows)\n"
                          "    crit = 0.025 / cells\n"
                          "    return crit, min(1.0, p_raw * cells)\n"))
    assert got["state"] == "FAIL"
    assert [s["call"] for s in got["sites"]] == ["bonferroni_len", "bonferroni_len"]


def test_sidak_over_len_fails_unpinned(tmp_path: Path) -> None:
    got = _one(tmp_path, "def f(xs, a):\n    return 1 - (1 - a) ** (1 / len(xs))\n")
    assert got["state"] == "FAIL" and got["sites"][0]["call"] == "sidak_len"


def test_holm_over_a_growing_count_fails_unpinned(tmp_path: Path) -> None:
    got = _one(tmp_path, ("def f(pvals, alpha):\n"
                          "    m = len(pvals)\n"
                          "    return [alpha / (m - i) for i in range(m)]\n"))
    assert got["state"] == "FAIL" and got["sites"][0]["call"] == "holm_len"


def test_a_release_gate_charged_over_its_cells_fails(tmp_path: Path) -> None:
    got = _one(tmp_path, ("def f(cells, ev, close):\n"
                          "    return release_gain(ev, close, n_cells=len(cells))\n"))
    assert got["state"] == "FAIL" and got["sites"][0]["call"] == "release_gain"


def test_pinned_multiplicity_sites_pass(tmp_path: Path) -> None:
    got = _one(tmp_path, (
        "from libs.research.trial_count_guard import bar_n, BAR_N\n"
        "def f(rows, p_raw, alpha, xs, a, ev, close):\n"
        "    cells = len(rows)\n"
        "    charged = min(cells, bar_n(cells))\n"
        "    crit = 0.025 / charged\n"
        "    adj = min(1.0, p_raw * charged)\n"
        "    sid = 1 - (1 - a) ** (1 / bar_n(len(xs)))\n"
        "    holm = [alpha / (BAR_N - i) for i in range(BAR_N)]\n"
        "    g = release_gain(ev, close, n_cells=min(len(rows), bar_n(len(rows))))\n"
        "    return crit, adj, sid, holm, g\n"))
    assert got["state"] == "OK", got["sites"]


def test_a_mean_or_a_quantile_is_not_a_correction(tmp_path: Path) -> None:
    got = _one(tmp_path, ("def f(v, p, total):\n"
                          "    mean = total / len(v)\n"
                          "    return mean, v[min(len(v) - 1, int(p * len(v)))]\n"))
    assert got["state"] == "OK", got["sites"]


# ---- no site's bar can rise (auditor ruling 2026-10-14: the min form everywhere) -------------

def _bar_n_sites(root: Path) -> list[tuple[str, int, str, str]]:
    """Every bar_n(X) call in scanned, unsealed code: (file, line, X, enclosing call)."""
    import ast
    out: list[tuple[str, int, str, str]] = []
    for p in fence._files(root):
        rel = p.relative_to(root).as_posix()
        if rel in fence.SEALED_OWED or rel in {"libs/research/trial_count_guard.py",
                                              "scripts/check_trial_inflation.py"}:
            continue
        text = p.read_text("utf-8", errors="replace")
        if "bar_n(" not in text:
            continue
        tree = ast.parse(text)
        parent = {id(c): n for n in ast.walk(tree) for c in ast.iter_child_nodes(n)}
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "bar_n" and n.args:
                par = parent.get(id(n))
                ctx = ast.unparse(par) if isinstance(par, ast.Call) else ""
                if (isinstance(par, ast.BinOp) and isinstance(par.op, ast.Div)
                        and par.right is n):
                    # c / bar_n(X) directly inside max(...) / np.maximum(...): a floor on a
                    # per-rank LEVEL at c/BAR_N, i.e. that rank's charge is min(own, BAR_N)
                    gp = parent.get(id(par))
                    if isinstance(gp, ast.Call) and getattr(gp.func, "id", getattr(
                            gp.func, "attr", "")) in {"max", "maximum"}:
                        ctx = f"LEVEL_FLOOR {ast.unparse(gp)}"
                out.append((rel, n.lineno, ast.unparse(n.args[0]), ctx))
    return out


#: Per-rank charges of a step-up / step-down family (re-audit of 6de7b1a99, 2026-10-20): rank i
#: is charged min(its own LIVE charge, BAR_N), never min(m, BAR_N) for the family. Each first
#: argument here is LIVE's charge for that rank -- BH/e-BH m/i, Holm m - r + 1 -- reviewed by name.
RANK_CHARGES = ("m / ranks", "max(1, m - min(rank, m) + 1)")


def test_no_site_can_raise_its_bar_above_its_own_count() -> None:
    """Every bar_n(X) in the live tree sits inside min(X', bar_n(X)) where X' is X or a floor
    of it (generation_roi keeps its historic max(2, X)). So the N a bar charges is never above
    the count it charged before the pin, and never above the fixed bar: no bar rises."""
    sites = _bar_n_sites(ROOT)
    assert len(sites) > 30, "the scan lost the pinned sites"
    bad = []
    for rel, line, x, ctx in sites:
        # the historic floors the callee already applied: generation_roi's max(2, X) and
        # release_gain's max(1, int(X)), campaign_window's max(1, X) -- each the exact count
        # charged before the pin
        ok = any(ctx.startswith(f"min({lo}, bar_n(")
                 for lo in (x, f"max(2, {x})", f"max(1, int({x}))", f"max(1, {x})"))
        # a rank's own charge capped at the fixed bar, or a level floored at alpha / BAR_N
        ok = ok or any(ctx.startswith(f"{f}({c}, bar_n(") for f in ("min", "np.minimum")
                       for c in RANK_CHARGES)
        ok = ok or ctx.startswith("LEVEL_FLOOR ")
        if not ok:
            bad.append(f"{rel}:{line} bar_n({x}) inside {ctx[:60]!r}")
    assert not bad, bad


def test_the_min_form_never_rises_numerically() -> None:
    from libs.validation.dsr import expected_max_sharpe
    for n in range(1, 50):
        pinned = expected_max_sharpe(min(n, tcg.bar_n(n)), 0.01)
        assert pinned <= expected_max_sharpe(n, 0.01) + 1e-15      # never above today
        assert pinned <= expected_max_sharpe(tcg.BAR_N, 0.01) + 1e-15  # never above the bar


# ---- fence widening (auditor, 2026-10-14): forms the pre-filter skipped, more count sources,
# ---- multipletests, np.minimum, BH via arange, partial and **kwargs ---------------------------

def _calls(got: dict) -> list[str]:
    return [s["call"] for s in got["sites"]]


def test_the_prefilter_no_longer_hides_these_forms(tmp_path: Path) -> None:
    got = _one(tmp_path, ("def f(x, p, a):\n"
                          "    m = len(x)\n"
                          "    return (min(1, len(x) * p), 0.1 / len(x), a / m,\n"
                          "            1 - (1 - p) ** m)\n"))
    assert got["state"] == "FAIL"
    assert sorted(_calls(got)) == ["bonferroni_len", "bonferroni_len", "bonferroni_len",
                                   "sidak_len"], got["sites"]


def test_size_shape_and_counted_generators_are_growing_counts(tmp_path: Path) -> None:
    got = _one(tmp_path, ("def f(p, arr, rows, alpha):\n"
                          "    return (alpha / p.size, alpha / arr.shape[0],\n"
                          "            alpha / sum(1 for r in rows if r))\n"))
    assert _calls(got) == ["bonferroni_len"] * 3, got["sites"]


def test_multipletests_and_np_minimum_are_seen(tmp_path: Path) -> None:
    got = _one(tmp_path, ("import numpy as np\n"
                          "from statsmodels.stats.multitest import multipletests\n"
                          "def f(pv, p):\n"
                          "    return multipletests(pv, method='holm'), "
                          "np.minimum(1.0, p * pv.size)\n"))
    assert sorted(_calls(got)) == ["bonferroni_len", "multipletests"], got["sites"]


def test_bh_and_ebh_written_with_arange_fail(tmp_path: Path) -> None:
    got = _one(tmp_path, ("import numpy as np\n"
                          "def bh(p, q):\n"
                          "    return q * (np.arange(1, p.size + 1) / p.size)\n"
                          "def ebh(e, alpha):\n"
                          "    m = len(e)\n"
                          "    ranks = np.arange(1, m + 1)\n"
                          "    return m / (alpha * ranks)\n"))
    assert _calls(got) == ["bh_len", "bh_len"], got["sites"]


def test_bh_pinned_at_the_fixed_bar_passes_and_an_ecdf_is_not_bh(tmp_path: Path) -> None:
    got = _one(tmp_path, ("import numpy as np\n"
                          "from libs.research.trial_count_guard import bar_n\n"
                          "def bh(p, q):\n"
                          "    m_bar = min(p.size, bar_n(p.size))\n"
                          "    return q * (np.arange(1, p.size + 1) / m_bar)\n"
                          "def ks(arr):\n"
                          "    n = arr.size\n"
                          "    i = np.arange(1, n + 1)\n"
                          "    return max(i / n - arr)\n"))
    assert got["state"] == "OK", got["sites"]


def test_partial_and_kwargs_cannot_smuggle_a_count(tmp_path: Path) -> None:
    got = _one(tmp_path, ("from functools import partial\n"
                          "from libs.validation.dsr import deflated_sharpe_ratio\n"
                          "def f(arr, cells, kw):\n"
                          "    g = partial(deflated_sharpe_ratio, n_trials=len(cells))\n"
                          "    return g(arr), deflated_sharpe_ratio(arr, **kw)\n"))
    assert _calls(got) == ["deflated_sharpe_ratio", "deflated_sharpe_ratio"], got["sites"]
    assert "**kwargs" in got["sites"][1]["trials_arg"]


# ---- rule 4: a written-down Tier S t (auditor's proposal, coordinator's ruling 2026-10-14) ----

def _lit(tmp_path: Path, files: dict[str, str]) -> dict:
    return _check(fence.judge(_tree(tmp_path, files), now=NOW), "tier_s_t_literal")


def test_a_named_tier_s_t_constant_fails(tmp_path: Path) -> None:
    """GD's release_gain.TIER_S_T_BAR on portwatch-live f5dff2a44 is this exact shape."""
    got = _lit(tmp_path, {"desks/mt5/research/release_gain.py":
                          "TIER_S_T_BAR = 2.84\nSOME_T_BAR: float = 2.8\n"})
    assert got["state"] == "FAIL"
    assert sorted(s["value"] for s in got["sites"]) == [2.8, 2.84]


def test_a_compared_tier_s_t_fails_in_either_sign_and_band(tmp_path: Path) -> None:
    got = _lit(tmp_path, {"desks/mt5/research/cluster_judge.py":
                          "def ok(t):\n    return t >= 2.79 or -2.89 > t or t > 2.8436\n"})
    assert got["state"] == "FAIL" and len(got["sites"]) == 3
    assert {s["use"] for s in got["sites"]} == {"comparison"}


def test_a_keyword_or_dict_key_holding_it_fails(tmp_path: Path) -> None:
    got = _lit(tmp_path, {"libs/x.py": "f(tier_s_t=2.84)\nd = {'TIER_S_T': 2.85}\n"})
    assert got["state"] == "FAIL" and len(got["sites"]) == 2


def test_numbers_outside_the_band_prose_and_unbarred_uses_pass(tmp_path: Path) -> None:
    got = _lit(tmp_path, {"libs/x.py": ('"""t of about 2.84 in prose."""\n'
                                        "VOL = 2.84\nTIER_S_T_BAR = 2.95\n"
                                        "def g(t):\n    return t > 2.7 and t < 3.0\n")})
    assert got["state"] == "OK", got["sites"]


def test_the_helper_is_the_one_home_and_the_live_tree_is_clean(tmp_path: Path) -> None:
    got = _lit(tmp_path, {"libs/research/tier_s_threshold.py": "X_T_BAR = 2.84\n"})
    assert got["state"] == "OK"
    assert fence.tier_s_literals(ROOT) == []
