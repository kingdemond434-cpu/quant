"""COMMITMENT PRESERVATION, and the doctrine-bloat check that now depends on it.

THE FINDING THAT DROVE THIS. max_audit fired `prompt-doctrine-bloat` on file size past 16k and
prescribed "consolidate the stacked axiom blocks into tighter prose (preserve every commitment,
cut the repetition)". Measured against the actual file that advice is false in its premise:

    near-duplicate sentence pairs   1 out of 17,955 compared
    distinct commitments            247
    density                         ~140 chars per commitment

There is nothing to consolidate. The file is long because it contains a great deal of distinct
law, so "cut the repetition" resolves in practice to "cut law" -- and an audit that prescribes a
harmful remedy is worse than one that says nothing, because the remedy carries the audit's
authority.

So bloat is redefined as what it actually means -- prose that carries no commitment -- and any
edit to the doctrine is gated on a mechanical proof that no obligation was lost. Prose may be
rewritten freely; commitments may not vanish. That asymmetry makes cutting waffle safe and
cutting law impossible.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import scripts.max_audit as M

from libs.doctrine.commitments import diff, extract, preserved, report

DOCTRINE = Path("ops/principal_doctrine.txt")


# ------------------------------------------------------------------ extraction


def test_every_kind_of_commitment_is_found() -> None:
    """Each kind is something an organ can ACT ON or be CHECKED AGAINST. Prose that merely
    explains is not a commitment and is free to be rewritten."""
    t = ("§33 says data/mine_generation_priors.json must be read every cycle; below 25% the "
         "class is starved. T1=8 outranks T4=1. NO-CEILING AXIOM binds. Emit [§33: wired] or "
         "mine-law-ineffective fires.")
    e = extract(t)
    assert "§33" in e["section"]
    assert "data/mine_generation_priors.json" in e["path"]
    assert "25%" in e["threshold"]
    assert "T1=8" in e["tier_weight"]
    assert "NO-CEILING AXIOM" in e["named_law"]
    assert "mine-law-ineffective" in e["defect"]
    assert "[§33: wired" in e["disposition"]


def test_ordinary_hyphenated_english_is_not_mistaken_for_a_check_name() -> None:
    """The defect pattern matches hyphenated identifiers, and English is full of them. Freezing
    'read-only' as a commitment would block harmless rewording forever and train everyone to
    ignore the guarantee."""
    e = extract("This is a read-only, up-to-date, end-to-end summary of long-term work.")
    assert e["defect"] == set()


# ------------------------------------------------------------------ the guarantee


def test_rewriting_prose_while_keeping_the_law_is_permitted() -> None:
    """The whole point: consolidation must remain POSSIBLE, or the guarantee is just a freeze."""
    before = ("You should really always remember, as a matter of standing practice and general "
              "temperament, that §35 requires every finding to get a register row.")
    after = "§35: every finding gets a register row."
    assert preserved(before, after)
    assert len(after) < len(before) / 2


def test_dropping_a_law_is_caught_and_named() -> None:
    """The failure this exists to prevent. A shorter doctrine that lost an obligation is strictly
    worse than a long one that kept it -- the context tax is paid per call and is small, a missing
    law is paid once, in full, at an unknown later date."""
    before = "§33 governs mining. §35 governs findings. Read data/priors.json every cycle."
    after = "§33 governs mining."
    d = diff(before, after)
    assert "§35" in d["section"]
    assert "data/priors.json" in d["path"]
    assert not preserved(before, after)


def test_adding_a_commitment_is_never_flagged() -> None:
    """One-directional on purpose. The doctrine GROWS when the principal decides something new;
    only removal needs a proof."""
    assert preserved("§33 binds.", "§33 binds. §41 binds too, per data/new.json.")


def test_the_report_refuses_to_call_a_lossy_edit_a_saving() -> None:
    """A consolidation that dropped a law must not be reported as a 40% win. The size delta is
    real and irrelevant when the content changed."""
    r = report("§33 and §35 and §36 bind, see data/a.json", "§33 binds")
    assert r["safe"] is False
    assert r["chars_saved"] > 0, "it really did get shorter -- that is exactly the trap"
    assert "strictly worse" in r["note"]


# ------------------------------------------------------------------ against the LIVE doctrine


def test_the_live_doctrine_is_dense_not_repetitive() -> None:
    """The measurement that falsified the old check's premise, asserted so a future edit that
    genuinely pads the file is caught rather than argued about."""
    if not DOCTRINE.exists():
        return
    t = DOCTRINE.read_text("utf-8")
    n = sum(len(v) for v in extract(t).values())
    assert n > 150, f"only {n} commitments found -- the extractor or the doctrine changed shape"
    assert len(t) / n < M._DOCTRINE_CHARS_PER_COMMITMENT


def test_removing_the_constitution_block_is_detected_as_loss() -> None:
    """The block is code-synced and immutable. If a consolidation ever clipped it, this is what
    notices -- and it is the single most expensive thing in the file to lose."""
    if not DOCTRINE.exists():
        return
    t = DOCTRINE.read_text("utf-8")
    without = t.split("=== END CONSTITUTION ===", 1)[-1]
    assert not preserved(t, without)


# ------------------------------------------------------------------ the check itself


def test_the_bloat_check_is_currently_clean() -> None:
    d: list = []
    M.check_prompt_layer(d)
    assert "prompt-doctrine-bloat" not in {k for k, _ in d}, [v for _, v in d]


def test_padding_the_doctrine_with_exhortation_goes_RED(tmp_path) -> None:
    """A bar that cannot fire is decoration. Bloat is now DEFINED as prose carrying no
    commitment, so this is the exact shape it must catch."""
    p = tmp_path / "doc.txt"
    p.write_text("§33 binds. " + ("Push harder and never be satisfied with good enough. " * 400),
                 "utf-8")
    d: list = []
    M._check_doctrine_density(p, d)
    keys = {k for k, _ in d}
    assert "prompt-doctrine-bloat" in keys
    assert "cut the exhortation, keep every obligation" in dict(d)["prompt-doctrine-bloat"]


def test_a_dense_but_enormous_doctrine_still_trips_the_ceiling(tmp_path) -> None:
    """Density must not license unbounded growth -- this is a context bill every organ pays on
    every call. And the remedy named is SPLITTING, never deleting."""
    p = tmp_path / "doc.txt"
    dense = "".join(f"§{i} binds, see data/f{i}.json at {i}% every {i}d. " for i in range(1400))
    p.write_text(dense, "utf-8")
    d: list = []
    M._check_doctrine_density(p, d)
    msg = dict(d).get("prompt-doctrine-oversized", "")
    assert msg, [k for k, _ in d]
    assert "never deleting it" in msg


def test_a_doctrine_of_pure_exhortation_is_its_own_defect(tmp_path) -> None:
    """Zero commitments is not 'infinitely dense', it is a system prompt with no instruction in
    it. Dividing by it would have made the emptiest possible doctrine look perfect."""
    p = tmp_path / "doc.txt"
    p.write_text("Be excellent. Try hard. Do your best work always.", "utf-8")
    d: list = []
    M._check_doctrine_density(p, d)
    assert "prompt-doctrine-empty" in {k for k, _ in d}
