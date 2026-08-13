"""A GATE THAT REFUSES A PUSH MUST SAY WHICH REGISTRY, AND MUST NOT TRUNCATE THE LIST (R0427).

This refusal blocked pushes for everyone on a shared branch twice in four commits -- c8983b1
(check_paywalls_registered) and cc28734 (check_blocked_routes_hunted +
check_verified_alternatives_promoted), different authors, three commits apart. Both times the fix
was one line in a registry the failure message never named, while the edit it is naturally
mistaken for -- adding the SCRIPT PATH to `_MAP` -- reads as equivalent in review and does
nothing, because the orphan set is computed only over refs starting with `check_`.

Every test here pins a property of the MESSAGE, because the message is the fix. The exit code was
never the defect: the gate was right to fail and unable to say how to stop failing.
"""

from __future__ import annotations

import scripts.build_enforcement_matrix as bem


class TestOrphanRemediationNamesTheRegistryAndTheLine:
    def test_names_the_registry_by_file_and_symbol(self):
        """"Map the fence" is not actionable; the author's whole problem is WHERE."""
        msg = bem._orphan_remediation(["check_something_new"])
        assert "_FENCE_OWNERS" in msg
        assert "scripts/build_enforcement_matrix.py" in msg

    def test_emits_a_copy_pasteable_line_for_the_actual_fence(self):
        """Prose the reader must translate is prose they can translate into the failing edit."""
        msg = bem._orphan_remediation(["check_something_new"])
        assert '"check_something_new": "L1.x"' in msg

    def test_warns_that_the_script_path_form_does_nothing(self):
        """The trap is that the wrong fix looks right in review. Say so at the point of failure."""
        msg = bem._orphan_remediation(["check_something_new"])
        assert "_MAP" in msg and "does nothing" in msg

    def test_every_orphan_is_listed_with_no_silent_truncation(self):
        """`first 5:` over six orphans reads as "that is all of them" (L1.60).

        The author fixes the five they were shown, pushes, and is refused again by the sixth --
        which is how a one-line fix becomes three round trips on a shared branch.
        """
        orphans = [f"check_fence_{i}" for i in range(9)]
        msg = bem._orphan_remediation(orphans)
        for name in orphans:
            assert f'"{name}"' in msg, f"{name} was dropped from the remediation"

    def test_says_what_to_do_when_no_law_covers_the_fence(self):
        """The dead end this gate has: a real fence no principle claims. Retire, or raise a law."""
        msg = bem._orphan_remediation(["check_something_new"])
        assert "retire it" in msg and "missing a principle" in msg


class TestBrokenRefExplainsTheShortCircuit:
    def test_a_bare_check_script_that_exists_on_disk_is_explained(self):
        """`check_foo.py` resolves against the FUNCTION table, so a present file reads as missing.

        Without the hint the author goes hunting a file that is sitting right there, which is a
        different and much longer search than "write the ref path-first".
        """
        [hint] = bem._broken_ref_hints(["check_campaign_retention.py"])
        assert "scripts/check_campaign_retention.py" in hint
        assert "FUNCTION table" in hint

    def test_a_path_first_ref_needs_no_hint(self):
        """The correct form must not be annotated -- noise on a healthy line trains it away."""
        assert bem._broken_ref_hints(["scripts/check_campaign_retention.py"]) == []

    def test_a_genuinely_absent_script_gets_no_misleading_hint(self):
        """"It exists, write it path-first" would be a lie about a file that is actually gone."""
        assert bem._broken_ref_hints(["check_this_never_existed.py"]) == []

    def test_a_function_ref_is_not_mistaken_for_a_script(self):
        """A bare function name has no `.py` and must never be told to become a path."""
        assert bem._broken_ref_hints(["check_phantom_paths"]) == []


class TestTheGateItselfStillHolds:
    def test_the_repo_currently_has_no_orphan_fence(self):
        """The ratchet this message serves: zero orphans is the committed state (L1.0)."""
        m = bem.build()
        assert m["fences_without_a_principle"] == [], (
            "a new max_audit check_* function needs a row in "
            f"{bem._OWNERS_REGISTRY}")

    def test_the_orphan_set_is_computed_over_a_non_empty_fence_scan(self):
        """Zero orphans over zero fences is a vacuous pass (L1.57): the denominator must be real."""
        m = bem.build()
        assert m["n_fences"] > 50, "the fence scan found nothing -- the regex or path is broken"
