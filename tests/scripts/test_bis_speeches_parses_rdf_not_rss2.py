"""A 200 with a parse that matches nothing is indistinguishable from a source with nothing to say.

WHAT HAPPENED (gap-fixer 2026-08-28). `mine_bis_speeches` anchored on a literal `<item>`. The BIS
central-bank speech feed is **RSS 1.0 (RDF)**, where every entry is `<item rdf:about="...">`, so
the anchor matched none of them. `fetch` returned a healthy 35,776-byte 200, the regex found
nothing, and the miner returned `[]` -- for **75 sweeps across 7 days, 0 rows and 0 fetch_errors**.
In `data/research_facts.json` that is a `usable_rate` of 0.0 sitting beside genuinely walled
sources, which is how a live feed of 25 dated speeches gets read as barren ground. It is the
desk's recorded class: an empty artifact asserts absence.

The fixture is the real feed's shape, reduced: the RDF header, the channel's own
`<items><rdf:Seq>` index that sits ABOVE the entries, three `<item rdf:about=...>` blocks, and
one entry with no description. Each pins a separate way this parser can silently under-deliver.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MINERS = ROOT / "desks" / "mt5" / "side_channels" / "seed_miners.py"

FEED = """<?xml version="1.0" encoding="utf-8"?>
<rdf:RDF xmlns="http://purl.org/rss/1.0/" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
         xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel rdf:about="https://www.bis.org/doclist/cbspeeches.rss">
    <title>BIS central bank speeches</title>
    <items>
      <rdf:Seq>
        <rdf:li resource="https://www.bis.org/review/r260813i.htm"/>
        <rdf:li resource="https://www.bis.org/review/r260813j.htm"/>
      </rdf:Seq>
    </items>
  </channel>
  <item rdf:about="https://www.bis.org/review/r260813i.htm">
    <title>Lesetja Kganyago: Remarks - annual dinner</title>
    <link>https://www.bis.org/review/r260813i.htm</link>
    <description>Remarks by the Governor of the South African Reserve Bank.</description>
    <dc:creator>Lesetja Kganyago</dc:creator>
    <dc:date>2026-08-17T08:22:00Z</dc:date>
  </item>
  <item rdf:about="https://www.bis.org/review/r260813j.htm">
    <title>Christine Lagarde: Monetary policy statement</title>
    <link>https://www.bis.org/review/r260813j.htm</link>
    <description>Statement by the President of the ECB.</description>
    <dc:creator>Christine Lagarde</dc:creator>
    <dc:date>2026-08-16T10:00:00Z</dc:date>
  </item>
  <item rdf:about="https://www.bis.org/review/r260813k.htm">
    <title>Kazuo Ueda: Speech with no description element</title>
    <link>https://www.bis.org/review/r260813k.htm</link>
    <dc:creator>Kazuo Ueda</dc:creator>
    <dc:date>2026-08-15T01:00:00Z</dc:date>
  </item>
</rdf:RDF>
"""


@pytest.fixture
def miners(monkeypatch):
    """Import the module by path and stub `fetch` -- the test must never touch the network."""
    saved = list(sys.path)
    sys.path.insert(0, str(MINERS.parent))
    spec = importlib.util.spec_from_file_location("_seed_miners_under_test", MINERS)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sys.path[:] = saved
    monkeypatch.setattr(mod, "fetch", lambda *a, **k: FEED)
    return mod


def test_rdf_items_carrying_attributes_are_parsed(miners) -> None:
    """The bug: `<item rdf:about=...>` is still an item. Zero rows here is the 75-sweep silence."""
    rows = miners.mine_bis_speeches()
    assert len(rows) == 3, f"expected 3 RDF items, got {len(rows)}"
    assert rows[0]["title"].startswith("Lesetja Kganyago")
    assert rows[0]["url"] == "https://www.bis.org/review/r260813i.htm"


def test_the_channel_items_index_is_not_mistaken_for_an_entry(miners) -> None:
    """`<items><rdf:Seq>` sits above the entries; a character class would swallow
    it as a fourth row."""
    titles = [r["title"] for r in miners.mine_bis_speeches()]
    assert "BIS central bank speeches" not in titles, "the channel index was parsed as a speech"


def test_an_entry_missing_a_middle_element_is_still_returned(miners) -> None:
    """One `.*?` chain across every field drops such an entry silently -- the same class, hidden."""
    rows = miners.mine_bis_speeches()
    ueda = [r for r in rows if "Ueda" in r["title"]]
    assert len(ueda) == 1, "an item with no <description> was dropped instead of returned"
    assert ueda[0]["text"] == ""
    assert ueda[0]["url"].endswith("r260813k.htm")


def test_speaker_and_date_are_carried_so_a_row_can_be_point_in_time_aligned(miners) -> None:
    """An undated speech cannot be joined to a bar without inventing its timestamp."""
    rows = miners.mine_bis_speeches()
    assert all(r.get("date") for r in rows), "a row reached the corpus with no date"
    assert rows[1]["speaker"] == "Christine Lagarde"
    assert rows[1]["date"] == "2026-08-16T10:00:00Z"
