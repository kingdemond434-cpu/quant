"""kimi_hunter's findings go where the compiler reads, or they were never produced.

MEASURED 2026-09-08. The hunter's own docstring names its one path -- "kimi_hunter -> suggestion
ledger -> mechanism board -> measurement gate -> Stage-A -> clock" -- and the first link was the
last: data/suggestion_ledger.jsonl is gitignored (`data/*`), and its only readers
(scripts/research_exchange.py, scripts/meta_architect.py) are on no timer and in no manifest
row. The candidate compiler walks data/intelligence/** and nothing else. So every finding the
Deep Forest protocol admitted stayed on the VPS in a file no scheduled organ opens.

`_donate` writes each admitted finding into data/intelligence/kimi/ in the miner discovery
contract -- the same door libs/ops/deepseek_cycle.py opened for the second brain. These tests pin
that door and the two properties that make it safe: a mock finding never enters the intelligence
tree, and the write happens in `main` AFTER the ledger append, so the audit trail is never
shorter than what was donated.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import scripts.kimi_hunter as K

_SRC = Path("scripts/kimi_hunter.py")


def _finding(**over) -> dict:
    base = {"date": "2026-09-08", "source": "kimi_k3_deep_forest", "wave": 2,
            "model": "deepseek/deepseek-r1:free", "claim_class": "INFERRED",
            "problem": "Month-end WMR fix forces real-money FX rebalancing",
            "evidence": "https://www.lseg.com/en/ftse-russell/wmr-fix methodology + own bars",
            "benefit": "forced-flow lead time", "cost": "2d", "dependencies": "own bars",
            "success_metric": "pre-fix drift share > 0.4", "kill_condition": "no drift after 90d",
            "status": "proposed"}
    base.update(over)
    return base


class TestTheDonationContract:
    def test_the_donation_directory_is_the_tree_the_compiler_reads(self) -> None:
        rel = K.DONATE_DIR.relative_to(K.ROOT).as_posix()
        assert rel == "data/intelligence/kimi", (
            "anywhere else under data/ is gitignored and unread by the compiler")

    def test_a_finding_is_written_in_the_miner_discovery_contract(self, tmp_path, monkeypatch):
        monkeypatch.setattr(K, "DONATE_DIR", tmp_path / "kimi")
        path = K._donate([_finding()])
        assert path is not None and path.name.startswith("discoveries_")
        doc = json.loads(path.read_text("utf-8"))
        assert doc["source"] == "kimi_k3_deep_forest"
        (row,) = doc["discoveries"]
        assert row["kind"] == "hypothesis"
        assert row["title"] == "Month-end WMR fix forces real-money FX rebalancing"
        assert row["model"] == "deepseek/deepseek-r1:free" and row["wave"] == 2
        assert row["claim_class"] == "INFERRED"
        for piece in ("forced-flow lead time", "pre-fix drift share > 0.4",
                      "no drift after 90d"):
            assert piece in row["text"], "the charter's fields are the prose the compiler reads"

    def test_the_same_finding_donated_twice_is_one_docket_row(self, tmp_path, monkeypatch):
        """The compiler keys rows on their exact content; the url must therefore be a function
        of the finding, not of the clock."""
        monkeypatch.setattr(K, "DONATE_DIR", tmp_path / "kimi")
        a = json.loads(K._donate([_finding()]).read_text("utf-8"))["discoveries"][0]
        b = json.loads(K._donate([_finding()]).read_text("utf-8"))["discoveries"][0]
        assert a == b

    def test_a_mock_finding_never_enters_the_intelligence_tree(self, tmp_path, monkeypatch):
        """`--mock` proves the chain on synthetic rows tagged mock=true. A synthetic finding in
        the intelligence tree would be compiled, deepened and billed like evidence."""
        monkeypatch.setattr(K, "DONATE_DIR", tmp_path / "kimi")
        assert K._donate([_finding(mock=True)]) is None
        assert not (tmp_path / "kimi").exists()
        path = K._donate([_finding(mock=True), _finding()])
        assert len(json.loads(path.read_text("utf-8"))["discoveries"]) == 1

    def test_nothing_to_donate_writes_nothing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(K, "DONATE_DIR", tmp_path / "kimi")
        assert K._donate([]) is None


class TestMainDonatesAfterTheLedger:
    def _main(self) -> ast.FunctionDef:
        tree = ast.parse(_SRC.read_text("utf-8"))
        return next(n for n in ast.walk(tree)
                    if isinstance(n, ast.FunctionDef) and n.name == "main")

    def test_main_calls_donate_after_appending_the_ledger(self) -> None:
        main = self._main()
        ledger_writes = [n.lineno for n in ast.walk(main)
                         if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                         and n.func.attr == "open"
                         and ast.unparse(n.func.value) == "LEDGER"]
        donates = [n.lineno for n in ast.walk(main)
                   if isinstance(n, ast.Call) and ast.unparse(n.func) == "_donate"]
        assert ledger_writes and donates, "main must both append the ledger and donate"
        assert min(donates) > max(ledger_writes), (
            "the audit trail is written first; a donation with no ledger row is unattributable")

    def test_the_artifact_records_where_the_findings_went(self) -> None:
        # ast.unparse renders string constants with single quotes.
        assert "'donated_to'" in ast.unparse(self._main())

    def test_every_finding_carries_the_model_that_produced_it(self) -> None:
        """The chain doctrine promised this attribution from the start and never wrote it."""
        assert "'model': used" in ast.unparse(self._main())
