# VIDEO-LOCKED MECHANISM LOG (purchase-evidence gate for GAP #26)
_Every digger appends here when a mechanism is readable only inside video/audio. This log is
the ONLY evidence that justifies buying a paid transcript/proxy unlock, and it decides WHICH
platform to buy for. Empty log = no purchase justified (free-first protocol)._

| date | platform | url | apparent mechanism | why text mirrors insufficient |
|---|---|---|---|---|
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
