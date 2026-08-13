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
