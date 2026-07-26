"""§42(5)(d): the parity guard must actually catch the failure that caused §42 in the first place.

The original defect was five copies of one policy that drifted apart, so the guard checks the
SHAPE OF THE DEPENDENCY (does this scorer import the shared policy?) rather than the value of any
threshold -- otherwise it would fire on every legitimate re-tune and be acknowledged into silence.
These lock that it fires on a re-inlined constant and on a dropped import, and stays quiet on the
real tree."""

from __future__ import annotations

import scripts.max_audit as m


def _defects(monkeypatch, root) -> list[tuple[str, str]]:
    monkeypatch.setattr(m, "ROOT", root)
    out: list[tuple[str, str]] = []
    m.check_capacity_single_source(out)
    return out


class TestGuard:
    def test_the_real_tree_is_clean(self) -> None:
        out: list[tuple[str, str]] = []
        m.check_capacity_single_source(out)
        assert out == [], f"§42 parity guard is firing on the live tree: {out}"

    def test_a_reinlined_fund_constant_is_caught(self, tmp_path, monkeypatch) -> None:
        for rel in m._CAPACITY_CONSUMERS:
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("from libs.research.capacity_policy import capacity_fit\n", "utf-8")
        bad = tmp_path / m._CAPACITY_CONSUMERS[0]
        bad.write_text("from libs.research.capacity_policy import capacity_fit\n"
                       "capacity_pass = capacity_usd >= 1e5\n", "utf-8")
        ids = [d[0] for d in _defects(monkeypatch, tmp_path)]
        assert "capacity-constant-reinlined" in ids

    def test_dropping_the_shared_import_is_caught(self, tmp_path, monkeypatch) -> None:
        for rel in m._CAPACITY_CONSUMERS:
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("from libs.research.capacity_policy import capacity_fit\n", "utf-8")
        (tmp_path / m._CAPACITY_CONSUMERS[1]).write_text("x = 1\n", "utf-8")
        ids = [d[0] for d in _defects(monkeypatch, tmp_path)]
        assert "capacity-policy-not-imported" in ids

    def test_a_consumer_that_vanished_is_reported_not_skipped(self, tmp_path, monkeypatch) -> None:
        # a moved file must not silently make the guard blind to wherever the logic went
        ids = [d[0] for d in _defects(monkeypatch, tmp_path)]
        assert "capacity-consumer-missing" in ids

    def test_a_comment_mentioning_the_old_floor_is_not_a_defect(
        self, tmp_path, monkeypatch
    ) -> None:
        # the modules DOCUMENT the bug they fixed; the guard must not punish that
        for rel in m._CAPACITY_CONSUMERS:
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("from libs.research.capacity_policy import capacity_fit\n"
                         "# capacity was a flat 1e5 floor until 2026-07-26\n", "utf-8")
        assert _defects(monkeypatch, tmp_path) == []


class TestOrphanDetectionIsTransitive:
    """A one-hop reachability proxy both cries wolf and misses real orphans.

    It reported libs/features as idle while `run_event_study -> listing_events -> features.labels`
    genuinely ran it, and it counted a package reachable when its only importer was ITSELF an
    orphan. A check that fires on healthy code gets acknowledged into silence, which costs more
    than the check ever earned."""

    def _tree(self, tmp_path, scripts: dict[str, str], pkgs: dict[str, str]):
        (tmp_path / "scripts").mkdir(parents=True, exist_ok=True)
        for name, body in scripts.items():
            (tmp_path / "scripts" / name).write_text(body, "utf-8")
        for pkg, body in pkgs.items():
            d = tmp_path / "libs" / pkg
            d.mkdir(parents=True, exist_ok=True)
            (d / "__init__.py").write_text("", "utf-8")
            (d / "a.py").write_text(body, "utf-8")
            (d / "b.py").write_text("", "utf-8")
            (d / "c.py").write_text("", "utf-8")
        return tmp_path

    def _run(self, root, monkeypatch) -> str:
        monkeypatch.setattr(m, "ROOT", root)
        out: list[tuple[str, str]] = []
        m.check_orphan_code(out)
        return out[0][1] if out else ""

    def test_a_transitively_reached_package_is_not_an_orphan(self, tmp_path, monkeypatch) -> None:
        root = self._tree(
            tmp_path,
            {"run.py": "from libs.mid import a\n"},
            {"mid": "from libs.deep import b\n", "deep": ""},
        )
        assert "deep" not in self._run(root, monkeypatch)

    def test_a_genuinely_unreached_package_is_still_caught(self, tmp_path, monkeypatch) -> None:
        root = self._tree(tmp_path, {"run.py": "from libs.mid import a\n"},
                          {"mid": "", "lonely": ""})
        assert "lonely" in self._run(root, monkeypatch)

    def test_reachable_only_from_an_orphan_is_still_an_orphan(self, tmp_path, monkeypatch) -> None:
        # the one-hop version called this "used" -- two dead packages importing each other
        root = self._tree(tmp_path, {"run.py": "print(1)\n"},
                          {"dead_a": "from libs.dead_b import b\n", "dead_b": ""})
        msg = self._run(root, monkeypatch)
        assert "dead_a" in msg and "dead_b" in msg
