# Operator digest

_generated 2026-09-30T14:43+00:00 by `python scripts/context.py digest`; derived, never edit by hand_

## Control room

- Control room: UNMEASURED on this host

## Research memory health

- Journal: 8 decision(s); verify PASS
- Sleeve rationale: 66 live/standby sleeve(s), thesis written for 38 (0.5758); no file for 0 -- run `python scripts/context.py rationale --sync` on origin

## Last 20 decisions

- **D-20260930-008** Regime-first gating of the weekend-gap trade refused (Live control room layer; owner Control room): Keep the ungated gap fade. On 12 FX and metals, 2018-2026: fading the weekend gap earns +0.48R (n=3902); switching to follow it in trending regimes drops the gated book to +0.00R; fading only in ranges earns +0.53R vs +0.44R in trends (Welch t 1.64), a tilt at most, never a gate Evidence: `desks/mt5/research/control_room_mechanisms.py`, `docs/research/control_room/MECHANISMS_2026-09-30.json`
- **D-20260930-007** Live gold-HMM world conditioning flagged (Live control room layer; owner Control room): On the same bench the allocator's live recipe (gold daily HMM conditioning every sleeve's worlds) lost 0.10 log/yr to the unconditioned solve (CI90 per day -0.00096 to +0.00017). Not removed: the box's real-sleeve contract run decides, and a removal would go through the desktop pass Evidence: `desks/mt5/research/pf_allocator.py:522`, `docs/research/control_room/REGIME_CONTRACT_BARS_2026-09-30.json`
- **D-20260930-006** Per-instrument regime kernel: built, not admitted on the bars bench (Live control room layer; owner Control room): libs/regime/control_room.py labels vol, trend/range and liquidity per instrument. On the bars bench (24 trend/range sleeves, 2021-07 to 2026-09, 65 monthly re-solves of the live solver) it lost 0.11 log/yr to the plain solve (CI90 spans 0). The allocator consumes it only if the box's run on the desk's real sleeves says GAIN Evidence: `libs/regime/control_room.py`, `desks/mt5/research/regime_allocation_contract.py`, `docs/research/control_room/REGIME_CONTRACT_BARS_2026-09-30.json`
- **D-20260930-005** Delegation protocol and repo research memory adopted (Live control room layer; owner Control room): context/ holds the delegation protocol, the decision journal and per-sleeve rationale; the box publishes the operator digest daily Evidence: `context/DELEGATION_PROTOCOL.md`, `scripts/context.py`, `desks/mt5/research/daily_cycle.py`
- **D-20260930-004** Subsystem admission rule (zuck (principal); owner all lanes): A new subsystem ships only with a measured contract showing gain; for anything that moves capital the contract is out-of-sample E[log W] Evidence: `context/DELEGATION_PROTOCOL.md`, `desks/mt5/research/regime_allocation_contract.py`
- **D-20260930-003** Autonomy: no approval asks (zuck (principal); owner all lanes): Lanes validate and merge their own PRs when CI failures are a subset of live's, pick the recommended default on forks, and raise only what is physically impossible without the principal Evidence: `context/DELEGATION_PROTOCOL.md`
- **D-20260930-002** Single-name equities: cross-sectional books and the news lane (zuck (principal); owner Breadth and throughput): Share CFDs mint hypotheses only in the cross-sectional class-book families, plus the news and earnings lane Evidence: `CLAUDE.md`, `desks/mt5/research/universe_policy.py`
- **D-20260930-001** Sizing rule: maximum aggressiveness within survival (zuck (principal); owner Sizing and losses): Size by the maximum ruin-counted E[log W]; the survival limit (P(lose 80% in 60 days) <= 5%) is the only thing allowed to cut size Evidence: `/mnt/project-files/sizing/SURVIVAL_VS_KELLY_2026-09-30.md`, `/mnt/project-files/sizing/kelly_survival.py`, `docs/GROWTH_GOVERNANCE.md`
