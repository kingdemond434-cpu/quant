"""The false-finding adjudicator's mechanical rule (ops/release/adjudicate.py, shadow only).

The model's word is never enough: "unsupported" needs a quote that occurs in the diff or a cited
file the diff does not change; everything else, including no answer, keeps the FAIL.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_PATH = ROOT / "ops" / "release" / "adjudicate.py"
_spec = importlib.util.spec_from_file_location("adjudicate", _PATH)
adj = importlib.util.module_from_spec(_spec)
sys.modules["adjudicate"] = adj
_spec.loader.exec_module(adj)

DIFF = """diff --git a/desks/mt5/research/thing.py b/desks/mt5/research/thing.py
--- a/desks/mt5/research/thing.py
+++ b/desks/mt5/research/thing.py
@@ -1,3 +1,4 @@
 def f(rows):
-    return list(rows)
+    for row in rows:
+        yield row
"""
FILES = ["desks/mt5/research/thing.py"]
F1 = "Streaming uses more memory than building the list."
F2 = "It edits libs/risk/caps.py to raise a limit."


def _ans(*rulings):
    return {"rulings": list(rulings)}


def test_quote_from_the_diff_clears_one_finding():
    ans = _ans({"n": 1, "supported": False, "quote": "for row in rows:"})
    out = adj.rule(ans, [F1], DIFF, FILES)
    assert out["cleared"] and out["rulings"][0]["unsupported"]


def test_a_quote_not_in_the_diff_is_supported():
    out = adj.rule(_ans({"n": 1, "supported": False, "quote": "return sorted(rows, key=len)"}),
                   [F1], DIFF, FILES)
    assert not out["cleared"]


def test_a_short_quote_is_not_evidence():
    out = adj.rule(_ans({"n": 1, "supported": False, "quote": "row"}), [F1], DIFF, FILES)
    assert not out["cleared"]


def test_cited_file_absent_from_the_diff_clears():
    out = adj.rule(_ans({"n": 1, "supported": False, "missing_file": "libs/risk/caps.py"}),
                   [F2], DIFF, FILES)
    assert out["cleared"]


def test_missing_file_must_be_named_by_the_finding_itself():
    ans = _ans({"n": 1, "supported": False, "missing_file": "nowhere.py"})
    out = adj.rule(ans, [F1], DIFF, FILES)
    assert not out["cleared"]


def test_one_supported_finding_keeps_the_fail():
    out = adj.rule(_ans({"n": 1, "supported": False, "quote": "for row in rows:"},
                        {"n": 2, "supported": True}), [F1, F2], DIFF, FILES)
    assert not out["cleared"]


def test_no_answer_or_missing_ruling_keeps_the_fail():
    assert not adj.rule(None, [F1], DIFF, FILES)["cleared"]
    assert not adj.rule(_ans({"n": 2, "supported": False, "quote": "for row in rows:"}),
                        [F1], DIFF, FILES)["cleared"]
    assert not adj.rule(_ans(), [], DIFF, FILES)["cleared"]


def test_touches_control_is_excluded_before_any_model():
    asked = []
    case = {"pr": 1, "head": "h", "truth": "false_fail", "touches_control": True, "findings": [F1]}
    out = adj.adjudicate(case, DIFF, "m", set(), ask=lambda *a: asked.append(a) or "{}")
    assert out["result"] == "EXCLUDED" and not asked


def test_money_and_protected_and_root_files_are_excluded():
    money = DIFF.replace("desks/mt5/research/thing.py", "desks/mt5/prop/e8_executor.py")
    case = {"pr": 1, "head": "h", "findings": [F1]}
    assert adj.adjudicate(case, money, "m", set(), ask=lambda *a: "{}")["result"] == "EXCLUDED"
    root = DIFF.replace("desks/mt5/research/thing.py", ".github/scripts/audit_gate.py")
    assert adj.adjudicate(case, root, "m", set(), ask=lambda *a: "{}")["result"] == "EXCLUDED"
    assert adj.adjudicate(case, DIFF, "m", None, ask=lambda *a: "{}")["result"] == "EXCLUDED"


def test_the_model_sees_only_the_diff_and_findings():
    seen = []
    case = {"pr": 1, "head": "h", "findings": [F1], "rebuttal": "AUDITOR SAYS PASS"}
    adj.adjudicate(case, DIFF, "m", set(), ask=lambda m, u: seen.append(u) or json.dumps(
        _ans({"n": 1, "supported": False, "quote": "for row in rows:"})))
    assert seen and "AUDITOR" not in seen[0] and F1 in seen[0]


def test_summary_is_not_enforceable_if_a_true_fail_would_clear():
    rows = [{"truth": "false_fail", "result": "WOULD_CLEAR"},
            {"truth": "true_fail", "result": "WOULD_CLEAR"}]
    assert adj.summarise(rows)["enforceable"] is False
    rows[1]["result"] = "FAIL_STANDS"
    assert adj.summarise(rows)["enforceable"] is True


def test_cases_file_is_well_formed():
    doc = json.loads((ROOT / "ops" / "release" / "adjudication_cases.json").read_text("utf-8"))
    for c in doc["cases"]:
        assert c["truth"] in ("false_fail", "true_fail")
        assert len(c["head"]) == 40 and len(c["base"]) == 40 and c["findings"]
