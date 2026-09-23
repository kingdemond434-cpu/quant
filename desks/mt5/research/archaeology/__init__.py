"""TRADING ARCHAEOLOGY -- the whole observable history of trading systems, turned into priors.

THE PRINCIPAL'S ORDER (2026-09-17, permanent): every trading system, trader, bot, competition,
product, repository and failed experiment whose OUTPUTS the world can lawfully see is ground for
mechanism hypotheses. Copy-trading is five to ten percent of it. The other ninety is the part
nobody digs: the mediocre accounts, the delisted ones, the dead forum threads, the abandoned
branch, the version that changed three parameters the month before the curve bent.

FOUR MODULES, ONE LAW.

`snapshots`  -- the POPULATION ARCHIVE. Per platform a declared `Platform` row carrying its
                `machine_use_allowed` and its verification class, periodic snapshots of the WHOLE
                accessible population (winners, mediocre, failed, removed), immutable captures
                under `data/moat/raw_intel/archaeology/<platform>/<date>/`, a population table at
                `data/archaeology/population.jsonl`, and `diff()` -- the watchtower that turns a
                disappearance into a measurement instead of a silence. It also holds the ARCHIVE
                LAYER (`archive_layer()`): eleven archive kinds x every region -- dead forums,
                historical pages, broker education portals, retired EA listings, delisted
                strategies, old research blogs, abandoned repositories, archived competition
                results, vanished newsletters, fund failures, public performance archives -- where
                every cell is a NAMED GROUND or a NAMED ABSENCE and never a blank.
`phenotype`  -- phi: what a system BEHAVES like, from whatever is observable. Stats only when the
                trades are hidden, the trade path when timestamps exist and can be aligned to the
                desk's own PIT bars. Then archetypes (k-means with a stability check), survivorship
                P(survive | phi) from PROSPECTIVE snapshots, negative space, crowding.
`decompiler` -- the MECHANISM DECOMPILER. Every archetype gets COMPETING explanations, never the
                glamorous one alone: mean reversion, grid exposure, short vol, session reversal and
                plain leverage each explain the same curve, and the falsifier is what separates
                them. Counterfactual reconstruction strips leverage, martingale and concentration
                and asks whether the INFORMATION still carries expectancy -- steal the alpha,
                reject the leverage. Every surviving mechanism becomes a registry DISCOVERY for
                the discovery compiler. Never a copied trade.
`civilization` -- the organ. Twenty families a pass inside a budget, platform budgets set by
                measured source ROI, the permanent source scout, and one report.

THE THREE RULES THIS PACKAGE IS BUILT ON.

**THREE INDEPENDENT LABELS ON EVERYTHING RECOVERED.** `access_label` (PUBLIC, PUBLIC_WITH_TERMS,
LICENSED, OPEN_DATA, PUBLIC_ARCHIVE, PUBLIC_SOCIAL, USER_SUBMITTED, ACCESS_UNCLEAR, PRIVATE,
CONFIDENTIAL_MNPI, STOLEN_UNAUTHORIZED), `credibility` (AUTHORITATIVE, RELIABLE, UNRELIABLE,
FRINGE, CONTRADICTED, UNKNOWN) and `predictive_state` (UNTESTED, PREDICTIVE, NOT_PREDICTIVE,
NARRATIVE_FEATURE). They are independent because they answer different questions: fringe,
contradictory and false-looking PUBLIC material is preserved as an evidence object at low weight
and never discarded; ACCESS_UNCLEAR IS MINED AND TESTED with its label attached (the quarantine
was deleted on 2026-09-23, LAWS 5e); and nothing private, confidential or unauthorised is
recorded, fetched or used at all.

**EVERY RECOVERED SOURCE EXPANDS, AND THE STOP IS RECORDED.** source -> people -> papers ->
datasets -> apps -> forums -> code -> new sources, recursively, until the marginal information
value falls below what else the hour could buy -- with one of four NAMED stopping reasons per
branch, because "ran out of budget" and "ran out of value" imply opposite next actions and look
identical in an output that does not say which happened.

**EVERYTHING VISIBLE IS MINED; FIVE ACTS ARE REFUSED (LAWS 5e, 2026-09-23).** A platform whose
robots or terms restrict automated extraction is registered WITH THAT NOTE AS A LABEL and mined;
"unknown" is a label too, because absence of a readable policy is not a prohibition. The old
reading -- robots or terms forbid it, therefore UNAVAILABLE and never fetched, and unknown
resolves to not fetched -- was a DISCOVERY BRAKE the desk imposed on itself and it is deleted.
What is still refused is exactly `snapshots.BOUNDARY_MARKERS`: nothing here defeats a challenge,
a paywall, a login or an access control, and nothing holds stolen or private data. The desk's
measured walls (`side_channels/seed_miners`) are read rather than restated, so one ledger owns
the access boundary.

**A WINNER IS A LEAD, NOT EVIDENCE.** Leaderboards are maximally survivorship-biased, competition
standings doubly so, and a product page is marketing. Everything mined here enters the gauntlet as
an unprivileged hypothesis in the desk's own families and is judged by the same ten gates.

**THE GRAVEYARD IS HALF THE CORPUS.** Blown accounts, delisted signals, abandoned repositories and
dead threads cost other people's capital and are free to the desk. A system that disappeared is a
measurement of P(survive | phi), which no winners-only table can ever produce.

NEVER A CRYPTO-EXCHANGE UNIVERSE (mandate 2026-08-18). Fusion-executable crypto CFDs are part of
the MT5 universe; a crypto exchange's own leaderboard is not ground and is never hunted.
"""
from __future__ import annotations

#: The four modules are imported by NAME rather than re-exported here: each one pulls the desk's
#: http client, the registry and numpy, and a package import that dragged all four in would make
#: `from archaeology import snapshots` cost the whole civilization.
MODULES: tuple[str, ...] = ("snapshots", "phenotype", "decompiler", "civilization")

RULE = ("public trading history is a prior generator for the gauntlet: phenotypes, archetypes "
        "and decompiled mechanisms, never copied trades; winners and graveyards alike; every "
        "source earns its budget by measured survivors")
