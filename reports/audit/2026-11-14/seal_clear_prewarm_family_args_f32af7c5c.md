# SEAL CLEAR: external_gauntlet.py, prewarm family args (Judge, commit f32af7c5cc891f98141abf16efb8cef92d614451)

Auditor, 2026-11-14T06:45Z. Base: LIVE c532fa92d. The sealed file's base blob d44204ad9 is unchanged on LIVE 8fe5c0428, and merge-tree is clean.
Patch sha256 c123fcb9a0bae3d8e7a677d58e5927849836025fff752d417ff4cd9b61b4af91. Bundle sha256 7219cbcc222132f943e2b1a592e11ac8998697baf6fb9be11e9246cf0145e370.

1. build_cell applies strip_identity_keys(family, call_params, preserve_session=True) after every consuming branch (fx_symbol :584, input_source :586-689, peer_symbol :592, factor_symbols :626). Nothing after the strip reads an identity key. Every key in IDENTITY_KEYS is absent from all family signatures, and session is preserved for the filter that follows. The cell identity is unchanged.
2. modifier_preflight refuses, by name, any cell missing a required keyword-only family argument, before bars are loaded. An AST sweep of families.py and families_orthogonal.py finds required kw-only args only on calendar_month (active_month, side_bias), plus seasonal_window as stated. No injected runtime argument (peer, factors and the like) is required kw-only. The refusal is NOT_RUN_MODIFIER, so no trial count, gate or FDR moves.
3. Tests: 3 new preflight tests. Run locally by the Judge; not re-run in this seat.

Verdict: CLEAR to seal desks/mt5/scripts/external_gauntlet.py at sha256 9c2d8dd412a057c9c7fee6cd9477212212053edd14f694a7fc1cc01a1b8a7d19.
