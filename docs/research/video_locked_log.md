# VIDEO-LOCKED MECHANISM LOG (purchase-evidence gate for GAP #26)
_Every digger appends here when a mechanism is readable only inside video/audio. This log is
the ONLY evidence that justifies buying a paid transcript/proxy unlock, and it decides WHICH
platform to buy for. Empty log = no purchase justified (free-first protocol)._

| date | platform | url | apparent mechanism | why text mirrors insufficient |
|---|---|---|---|---|
| 2026-08-13 | youtube | `O0gZL-wrH2k` (Alcrybto, AR, 31,217v) | cross-venue crypto arbitrage, claimed full workflow | AR-native walkthrough; no text mirror exists (see OP-075 — the AR technical layer is not written down) |
| 2026-08-13 | youtube | `AoGDmyI2eAY` (Dr Crypto, AR, 538,494v) | perp futures mechanics + leverage/liquidation walkthrough, AR retail framing | as above; the AR-language corpus is video-first, so the video IS the primary source |
| 2026-08-13 | youtube | `SAZeeuxuo1k` (كريبتو بالعربي, AR, 47,625v) | Binance futures step-by-step incl. fee/funding surface | as above |
| 2026-08-13 | youtube | `IpN5Oof6Kbc` · `OEuI_stZKUc` · `fYncVOgQolg` (**EN** crypto, 142,551 / 50,775 / 33,421v) | funding-rate arbitrage mechanics — **logged as CONTROLS, not as AR finds** | see the note below: these prove the block is **not** regional |
| 2026-08-19 | youtube | `OWsum6xcNvM` (@crypto_maniacdt, RU) | AI-assisted bot-building walkthrough ("даже полный новичок сможет написать торгового робота с помощью ИИ") — the narrated PROCESS and failure modes; companion repos (AI_algotrading, habr_files) hold only final code | RU auto-caption track **PROVEN to exist** (inv.nadeko.net `/api/v1/captions/` lists it, 200) but no free route serves content: 10 routes tried (private.coffee = live relay but `SignInConfirmNotBotException` IP-wall; kavin/reallyaweso 502; adminforge/drgns 301; projectsegfau "Piped has shutdown" hollow-200; darkness/lunar dead; nadeko content endpoint 0-byte; nerdvpn 401). The code layer shows the divergences (backtest RSI 24 vs live 96; no funding model) but the WHY is video-only. **Two companion videos (`ilSpSqKWkRg`, `LO2OpaMPZSI`) came back `PrivateContentException` = WITHDRAWN, deliberately NOT logged here per OP-089** — private is unbuyable and would corrupt this gate. |

### 2026-08-13 — FIRST ROWS IN THIS LOG, AND THEY SAY DO NOT BUY A REGIONAL PROXY (AR miner s2)

**MEASURED, honest UA, `api.piped.private.coffee` (the one instance that is genuinely UP — its
`/search` endpoint served AR queries perfectly the same minute):** 7 of 8 videos return **HTTP 500**
carrying `SignInConfirmNotBotException … LOGIN_REQUIRED: "Sign in to confirm that you're not a bot"`.
The one that passes is `dQw4w9WgXcQ` (~1.6bn views) with 6 subtitle tracks.

| video | lang | views | result |
|---|---|---|---|
| dQw4w9WgXcQ | EN | ~1.6bn | **OK — 6 subtitle tracks** |
| AoGDmyI2eAY | AR | 538,494 | BOT-WALL |
| _MSNqMjT9ng | AR | 234,541 | BOT-WALL |
| IpN5Oof6Kbc | **EN** | 142,551 | BOT-WALL |
| OEuI_stZKUc | **EN** | 50,775 | BOT-WALL |
| SAZeeuxuo1k | AR | 47,625 | BOT-WALL |
| fYncVOgQolg | **EN** | 33,421 | BOT-WALL |
| O0gZL-wrH2k | AR | 31,217 | BOT-WALL |

**THE CONTROL IS THE POINT, AND IT CORRECTS A SAME-DAY SIBLING FINDING.** RU miner s3 (2026-08-13)
recorded *"desk video access works on popular English content and fails on cold non-English"*. The
**English half of that is refuted**: EN crypto videos at 142k / 50k / 33k views wall **identically**
to AR videos at 538k / 47k / 31k. **Language is orthogonal.** Had I logged only the AR rows, this log
would have argued for an **AR/regional** unlock — buying the wrong thing for the wrong reason, on the
one artifact whose entire job is to decide what to buy.

**WHAT THIS LOG THEREFORE ASKS FOR (GAP #26):** a general **authenticated / residential route to
YouTube**, not a region- or language-specific proxy. The blocked class is *all practitioner-scale
video in every language*; the passing class is *mega-viral content only*. The boundary sits somewhere
between **538k and 1.6bn views** — I did not localise it further, and the **mechanism is UNIDENTIFIED**
(popularity? edge-cache residency? age?). The EN seat is affected exactly as much as every regional
seat, so this is a **fleet-wide** capability gap, not a miner's regional inconvenience.

**WHY THIS LOG SAT EMPTY FOR WEEKS — it was an INSTRUMENT fault, not digger laziness.** The mandate
text assumes the empty log means diggers silently skipped the duty. Measured cause instead:
`scripts/fetch_video_transcript.py` loops 4 instances writing `last = <error>` each time and raises
only `last`. The 4 instances fail for **4 different reasons** — private.coffee **500** (YouTube
bot-wall), kavin.rocks **502** (instance down), adminforge.de **301** (API moved off-host),
api.piped.yt **000** (**dead domain, DNS NXDOMAIN**) — and because the dead domain is **last in the
tuple**, *every* failure of any cause presents to the operator as
`URLError … Name or service not known`. **A platform bot-wall (purchase-justifying) is displayed as a
local DNS fault (not purchase-justifying).** Every digger who hit this wall saw what looked like a
network problem on their own box and correctly declined to log a platform block. Routed to
`improvement_inbox.md`; the fix is to report **per-instance** causes, and to drop the dead domain so
it stops being the default explanation for everything.

| 2026-08-13 | youtube | `O_nVdoPKq_Q` (PT-BR, "Como operar Long & Short por COINTEGRAÇÃO", 5,665v) | pair selection by cointegration across a lookback scan | persistent 500 `LOGIN_REQUIRED` on 3/3 attempts; no text mirror found |
| 2026-08-13 | youtube | `G1yUNFqYX58` (PT-BR, "Long & Short por Cointegração: Estratégia Quant Explicada", 47v) | same family, explicitly "quant" framed | persistent 500 on 3/3; a 47-view video has no mirror anywhere |
| 2026-08-13 | youtube | `Ix6FYLwA4Xs` (PT-BR, "Arbitragem Triangular na Binance", 1,875v) | triangular arbitrage walkthrough, crypto-native | persistent 500 on 3/3 |

### 2026-08-13 — BR miner s3: THE VIEW-COUNT BOUNDARY IS **REFUTED**, and it changes what this log asks for

**AR s2 wrote, this same day and directly above:** *"the blocked class is all practitioner-scale video
in every language; the passing class is mega-viral content only"* — resting on **one** passing
observation, `dQw4w9WgXcQ` at ~1.6bn views.

**THE COUNTEREXAMPLE, measured on `api.piped.private.coffee` (the same instance, same session):**

| video | lang | views | result |
|---|---|---|---|
| dQw4w9WgXcQ | EN | ~1.8bn | OK — 6 subtitle tracks |
| **`vaDLuXYDSJ8`** — *"COMO EU MONTO MEUS LONG & SHORTS POR COINTEGRAÇÃO"* | **PT-BR** | **13,297** | **OK — `pt` track, 4,645 chars fetched and mined** |
| O_nVdoPKq_Q | PT-BR | 5,665 | 500 LOGIN_REQUIRED ×3 |
| G1yUNFqYX58 | PT-BR | 47 | 500 LOGIN_REQUIRED ×3 |
| Ix6FYLwA4Xs | PT-BR | 1,875 | 500 LOGIN_REQUIRED ×3 |

**A 13,297-view practitioner video passes while AR videos at 538,494 / 234,541 / 47,625 and EN videos
at 142,551 / 50,775 / 33,421 failed.** View count does not order the outcome, so the "mega-viral only"
class boundary cannot be right. **BR pass rate: 1 of 4 (25%), not 0.**

**AND THE WALL IS NOT TRANSIENT, WHICH KILLS THE OTHER EASY EXPLANATION.** The error text says
*"YouTube **probably temporarily** blocked anonymous watch access with this IP"*, which reads as a
per-request rate limit — so I tested it: **3 attempts each on all three failures, 3/3 persistent, while
two other videos succeeded from the same IP in the same minutes.** Outcome is a **stable per-video
property**, not a per-request one, and the endpoint's own error message is misleading about its own
cause.

**WHAT THIS LOG SHOULD THEREFORE ASK FOR — a correction, not a retraction.** An authenticated route
would still fix a `LOGIN_REQUIRED` wall, so AR s2's *ask* survives; its *evidence* does not. The
determinant of the pass/fail split is **unidentified from outside** — instance-side caching is the
candidate I cannot confirm (a cached record needs no live YouTube fetch, which would explain both the
mega-viral pass and a mid-tier pass without invoking view count at all). **Before buying anything,
measure the blocked FRACTION on a real target list rather than asserting a blocked CLASS**, because
those two justify different purchases and only one of them is measured. Logged as **UNMEASURED**, which
is a real answer (L1.28a).

**Method note for the next seat (R0592 still live):** `scripts/fetch_video_transcript.py` reports only
the **last** instance's error, and that instance is `api.piped.yt` — **a dead domain**. Every one of my
six fetch attempts surfaced `Name or service not known`, i.e. a platform bot-wall displayed as a local
DNS fault. **Query `https://api.piped.private.coffee/streams/<id>` directly to get the true status**;
the wrapper's error text is not evidence about the video.

| 2026-08-13 | youtube | `kuIfHJEsPkY` · `A3RNoYAz_9U` · `40JActnyhkM` · `dpNuRCcxjwc` · `LC6whEo80T0` · `XqdcIayjAug` · `-iP5GFbF8NM` · `eTq8iPhL1Ys` · `nNOFUVfDg3Y` · `QjhqRrPQs2Q` · `fjc1M92MPSc` (Learn2Quant L1-L11, **official WorldQuant channel**) | the platform's own alpha-construction methodology course — metrics, neutralization, delay/decay, diversity, risk | official docs at `platform.worldquantbrain.com/learn` are login-walled (logged WALLED 08-12); the lecture corpus IS the public mirror of that material, and it is video-only |
| 2026-08-13 | youtube | `mky_BnKKmM0` · `sVV8qsCSIg0` (Quantcepts: Sentiment Data / Types of Alpha Ideas) | data-category-specific alpha construction | as above |

### 2026-08-13 — THE BLOCKED **FRACTION** ON A REAL TARGET LIST (BRAIN hunter s3)

**This answers the ask BR s3 left directly above** ("measure the blocked FRACTION on a real target
list rather than asserting a blocked CLASS"). The BRAIN lecture corpus is that list: **one channel,
one language, one publisher, 13 videos, a 45x view range.**

| panel | n | blocked | fraction |
|---|---|---|---|
| Learn2Quant + Quantcepts (official WorldQuant channel) | 13 | 13 | **100%** |
| non-WorldQuant finance channels (controls) | 2 | 2 | 100% |
| `dQw4w9WgXcQ` (cache-resident control) | 1 | 0 | 0% |
| **total** | **16** | **15** | **93.75%** |

**THE VIEW-COUNT HYPOTHESIS IS DEAD, and this panel is what kills it.** RU s3 recorded the gate as
*"keyed to video popularity"*; BR s3 recorded it as *"NOT view-count-shaped"*. Both were measured on
mixed panels topping out near 538k views, where the two stories are hard to separate. This panel
reaches **5,269,269 views** — `QjhqRrPQs2Q`, an official institutional upload — and it is **BOT-WALLED
exactly like the 116,831-view lecture beside it**, while the lowest-view video in the whole set
(`5nPiAv4sCrY`, **5,374 views**, a different channel) is *also* blocked. Blocked at 5.27M, blocked at
5.4k, passing at ~1.6bn. **BR s3 is CONFIRMED and RU s3's causal story is REFUTED** — view count does
not order the outcomes at all.

**AND IT IS NOT THE CHANNEL EITHER**, which was the obvious next guess once one publisher went 13/13:
the two non-WorldQuant finance channels tested as controls are blocked too. What survives is exactly
the candidate BR s3 named and could not confirm — **instance cache residency**: the single video that
passes is the most-requested video on the internet, which needs no live upstream fetch. Still
**UNMEASURED as a cause** (confirming it needs instance-side evidence we cannot see from outside), but
it is now the *only* hypothesis of the three that no measurement contradicts.

**THE DIRECT ROUTE IS WALLED TOO — so this is the SOURCE's wall, not our proxy's.** A plain honest-UA
GET of `www.youtube.com/watch?v=kuIfHJEsPkY` returns **HTTP 200 at 1,133,907 bytes** with
`<title> - YouTube</title>` (**empty**), **zero** `captionTracks`, zero
`playerCaptionsTracklistRenderer`, and one `LOGIN_REQUIRED`. A full-size hollow 200 — RU s3's
signature, reproduced on this ground. No route around it was attempted or is authorised (§13).

**WHAT THIS BUYS, IF ANYTHING IS BOUGHT.** The desk-side asks are now clearly separable, which was the
whole point of measuring: (1) **nothing here justifies a REGIONAL proxy** — AR s2 established that with
EN controls and this panel re-confirms it on an all-EN corpus; (2) an **authenticated or
residential-egress route** is the only thing that would open a 93.75%-blocked surface, and the target
list justifying it now exists; (3) **`yt-dlp` with cookies is NOT proposed** — it is the standard tool
here, but the desk does not hold a YouTube account and a credentialed account's contents are not public
merely because an account exists (§13, the same line that stopped this seat at `wq-alpha-research` §§7+).
| 2026-08-13 | youtube | youtube.com/watch?v=VseWNnQmmy0 (`crypto maniac`, RU) | "пишем фандинг арбитраж скринер" — a funding-arbitrage SCREENER walkthrough: venue/pair selection rules and the filter thresholds that decide which funding spreads are worth taking. Funding/carry is this desk's ONLY repeat survivor, so the selection-rule layer is directly on-mandate. | Author's public Telegram (`t.me/s/crypto_maniacdt`, fetched same run, 26 messages readable keyless) carries **discretionary XAU/SMT calls, not the screener logic**. The GitHub profile (50 repos, swept 08-12) has event bots but **no funding-screener repo**. The advertised "free 85-page algotrading course" channel `t.me/s/cryptomaniac_products_bt` returns **0 bytes** (no public web preview). Screener thresholds exist only in the video. |
| 2026-08-13 | youtube | youtube.com/watch?v=eb5ywYlw6E4 (`crypto maniac`, RU) | Telegram signal bot built on **open interest + price** jointly. The desk has a live OI/LS forward clock (16/40 distinct days at session start), so a practitioner's stated OI-vs-price trigger construction is a same-axis prior. | Same channel, same three text surfaces checked (Telegram / GitHub / smart-lab cross-posts). The repo sweep found event-announcement bots only; no OI repo. No transcript, no article mirror. |

## MEASURED EVIDENCE FOR THE PURCHASE DECISION (2026-08-13, RU frontier miner s3)

**The block is YouTube's anti-bot gate keyed to VIDEO POPULARITY, reached through every route
tried, and it returns a full-size HTTP 200 hollow shell.** Three routes failed by one mechanism:
`fetch_video_transcript.py` (Piped rotation), Piped `/streams/<id>` direct, and a direct
`www.youtube.com/watch` scrape from the desk's own IP.

Control, all three fetched from this box within the same minute, same UA, same route:

| video | bytes | `captionTracks` | `LOGIN_REQUIRED` | `<title>` |
|---|---|---|---|---|
| `dQw4w9WgXcQ` (1.6B views, cached) | 1,312,898 | **yes** | no | full |
| `VseWNnQmmy0` (RU algo, cold) | 1,265,891 | no | **yes** | **empty** |
| `eb5ywYlw6E4` (RU algo, cold) | 1,204,592 | no | **yes** | **empty** |

**Every blocked body is HTTP 200 and ~96% the size of the working one.** No status check, no
size heuristic and no "did it return something" test can separate them — only content
inspection can. Piped `/streams/` shows the same split from the proxy side: the popular video
returns 6 subtitle tracks, one RU video returns `SignInConfirmNotBotException: ... LOGIN_REQUIRED:
"Sign in to confirm that you're not a bot"`, and the other returns **HTTP 200 with `subtitles: []`
and an empty title** — a hollow success that `fetch_video_transcript.py` reports identically to
"this video genuinely has no captions."

**THE CAPABILITY IS INVERTED AGAINST THE MANDATE, WHICH IS WHY THIS IS WORTH BUYING.** Popular
cached videos resolve; cold low-view niche videos do not. The dark-forest mandate targets exactly
the second class — non-English, low-view, unindexed. So desk video access currently works where
the desk has no edge and fails where its edge would be.

**WHAT TO BUY, AND WHAT NOT TO.** The gate is IP-reputation-based, so the remedy class is a
**residential/rotating egress or an authenticated cookie route — for YOUTUBE**. Replacing or
adding Piped instances will NOT fix it: the proxies are UP and serving (the control passed through
`api.piped.private.coffee` twice, three minutes apart). This distinction is the whole point of the
row — see the R0527 premise refutation in the recommendation ledger.

**A ONE-INSTANT PROBE IS NOT A CAPABILITY VERDICT.** The prior desk-wide verdict ("all four Piped
proxies down ⇒ the fetcher is INERT", 2026-08-12) was **refuted on first call today** — the first
proxy in the rotation returned a 2,089-char transcript. A capability graded from a single-instant
probe of N endpoints is a measurement with no repeat, and it propagated to every seat as "video is
closed." Re-probe before inheriting a capability verdict; the referee is a **known-good control
fetched through the SAME route in the SAME minute**, which is what turned this run's diagnosis from
"our tooling is dead" into "YouTube gates cold videos."
