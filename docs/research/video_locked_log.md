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
