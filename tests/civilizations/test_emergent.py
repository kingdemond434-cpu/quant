"""The ontology frontier: recurring unknown concepts become classes and new search ground."""
from __future__ import annotations

import json
import re
from pathlib import Path

from libs.civilizations import emergent as EM
from libs.civilizations import ontology as O


def test_terms_skip_known_vocabulary_and_stopwords() -> None:
    t = EM.terms("The monsoon rainfall index drives sugar futures. buy when the RSI is low",
                 topics=["weather-alpha"])
    assert "monsoon rainfall" in t and "rainfall index" in t and "weather alpha" in t
    assert not any(w.startswith("the ") for w in t)
    assert all(not EM._known(x) for x in t)
    # a sentence about nothing market-related contributes nothing
    assert EM.terms("pandas dataframe helpers. numpy array tricks") == set()


def test_recurring_concept_is_born_and_routes_the_residue(tmp_path: Path) -> None:
    lex = EM.EmergentLexicon(tmp_path, exclude=re.compile("binance"))
    for i in range(EM.MIN_DF):
        lex.observe(f"note {i}: monsoon rainfall shifts the crush spread; binance listing",
                    source_id=f"lane{i % 2}", uri=f"https://x/{i}")
    born = lex.promote()
    assert "monsoon rainfall" in born
    assert not any("binance" in b for b in born)
    lex.observe("only one lane says glacier melt moves oil", source_id="lane0", uri="u")
    assert "glacier melt" not in lex.promote()
    assert lex.match("A new monsoon rainfall study") == ["monsoon rainfall"]
    lex.save()
    again = EM.EmergentLexicon(tmp_path)
    assert "monsoon rainfall" in again.classes            # classes are durable, never deleted
    qs = again.queries([{"query": "man ahl trend data"}])
    assert "monsoon rainfall trading" in qs and "man ahl trend data" in qs
    doc = again.report(born, 0)
    assert doc["classes"] == len(again.classes) and doc["emergent_classes"]


def test_lexicon_is_bounded_and_keeps_classes(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(EM, "MAX_TERMS", 3)
    lex = EM.EmergentLexicon(tmp_path)
    lex.classes = {"zz kept": {"born_at": "x"}}
    lex.lex = {k: {"df": d, "sources": [], "first_seen": "a", "examples": []}
               for k, d in (("zz kept", 1), ("a b", 9), ("c d", 1), ("e f", 5), ("g h", 2))}
    assert lex.prune() == 2
    assert set(lex.lex) == {"zz kept", "a b", "e f"}


def test_emergent_class_is_a_consumed_outcome() -> None:
    assert O.EMERGENT_CLASS in O.OUTCOMES and O.CONSUMERS[O.EMERGENT_CLASS]
    row = O.Outcome(O.EMERGENT_CLASS, 1.0, ["monsoon rainfall"]).as_row()
    assert json.dumps(row)
