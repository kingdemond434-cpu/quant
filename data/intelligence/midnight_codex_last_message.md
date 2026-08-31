Implementation ledger

- No commit created; preserved existing dirty work.
- Repaired remote-code drift: `scalp_shadow.py` was stale on the MT5 desk box. The verified drift service re-shipped and hash-verified it.
- Fresh remote shadow run and pull correctly quarantined all four gold-scalp rows: they lack exact current ten-gate certificates, so they cannot accrue/promote on invalid authority.
- Forward-clock fence now passes: healthy 27, churned 0, unrepairable 0.
- Tests passed: `tests/test_check_forward_clock.py`, `desks/mt5/tests/test_scalp_shadow.py` (6 tests).
- Checkpoint recorded at controller epoch 132; lease released.

Economic/safety effect: prevents uncertified scalp evidence from being represented as usable forward evidence; no capital authority changed.

Blockers/next dependency: re-certify eligible scalp candidates through the canonical gauntlet before fresh zero-capital enrollment. The ratchet still reports a separate 0.02-day silent rebase on an EURGBP discovered sleeve; its writer remains the repair owner.