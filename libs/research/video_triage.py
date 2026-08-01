"""Rank quant-video candidates by the desk's MEASURED conversion record, not by taste.

WHAT THIS IS AND IS NOT. It is not a transcript miner -- it cannot be. Measured 2026-08-01 from
this box: the channel listing page is reachable and yields video IDs and titles (23 of 23 for one
channel), and EVERY caption path is blocked. The watch page carries no `captionTracks` block,
`api/timedtext` returns zero bytes, and `youtube-transcript-api` raises RequestBlocked. That is a
datacenter-IP block, not a bug, and no amount of retrying fixes it.

So this solves the half that is actually expensive for a human: not reading a transcript, but
deciding WHICH of several hundred videos is worth reading. A channel with 559 videos is not
scannable by hand, and the desk now has a measured record of what converts.

THE PRIOR IS A RECORD, NOT A MODEL. These weights are read off the 2026-08-01 batch, where
roughly thirty transcripts were mined and the outcome of each is known:

  CONVERTED into shipped, tested code or a measurement that changed a constant:
    neurotrader "permutation tests"        -> libs/validation/bar_permutation
    neurotrader "how I develop strategies" -> confirmed the construction defect + thresholds
    neurotrader "intramarket differences"  -> libs/research/intermarket
    neurotrader "trade dependence"         -> libs/research/overlays (conditional adoption)
    Algovibes  "350,000 BTC strategies"    -> the drawdown calibration landmine
    Algovibes  "regime detection tested"   -> libs/validation/lookahead_audit
    Algovibes  "volatility targeting"      -> the largest measured improvement in the batch
    Algovibes  "combined 51 strategies"    -> correlation-of-winners
    Kevin Davey book summaries             -> libs/validation/random_baseline, drawdown_metrics

  CONVERTED NOTHING, despite hours of runtime:
    IQ Capital trader profiles ("$102k/month trader", ex-hedge-fund scalper interview)
    IQ Capital 10,000-trader study (one corroboration, no code)
    AI-agent channels ("8 ways I make money with Claude", "$50k -> $500k with AI trading")

The separating feature is blunt and it is what the weights encode: a source that reports a
MEASUREMENT over many trials, or specifies a PROCEDURE, converts. A source that narrates what a
person does converts nothing. Personal-profit framing in a title is the single strongest negative
signal in the record -- not because such people are lying, but because a claim about one person's
returns contains no number this desk can check against its own data.

THE SCORE IS A QUEUE ORDER, NOT A VERDICT. It ranks what to spend attention on. A high score is
not a promise the video is good, and a low score is not proof it is worthless -- the books video
scored low on these features and still produced two useful pointers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

#: Title/description patterns that PREDICT conversion, with weights from the record above.
#: Large-N measurement is weighted highest because every single large-N source in the batch
#: produced something, and no narrative source did.
POSITIVE = {
    r"\b\d{1,3}[,.]?\d{3,}\s*(back-?tests?|strategies|strategy|trades|accounts|simulations)": 5.0,
    r"\b(permutation|monte[- ]carlo|walk[- ]forward|out[- ]of[- ]sample)\b": 5.0,
    r"\b(deflated sharpe|multiple testing|multiplicity|p-?value|statistical(ly)? significan)": 4.0,
    r"\b(overfit|curve[- ]fit|look[- ]ahead|survivorship|selection bias|data mining bias)\b": 4.0,
    r"\b(i tested|i ran|i back-?tested|does it (actually )?work|fact[- ]check|tested)\b": 3.0,
    r"\b(robust|stability|parameter (sweep|space)|sensitivity)\b": 3.0,
    r"\b(volatility target|position sizing|risk parity|kelly|drawdown|risk of ruin)\b": 3.0,
    r"\b(regime|hidden markov|structural break|non[- ]?stationar)": 2.0,
    r"\b(entropy|hawkes|self[- ]exciting|granger|cointegrat|order flow|microstructure)\b": 2.0,
    r"\b(python|code|implementation|from scratch|walkthrough)\b": 1.0,
}

#: Patterns that predict NOTHING converts. The profit-claim family is weighted hardest because it
#: has a perfect zero-conversion record across the batch.
NEGATIVE = {
    r"(\$[\d,]+\s*(/|per\s*)?(month|day|year|week))|\b(\d+%\s*(a|per)\s*(month|week|day))\b": -6.0,
    r"\b(made (me|him|her|\$)|turned \$|profit|rich|millionaire|income|payout)\b": -4.0,
    r"\b(secret|guru|insane|crazy|shocking|nobody tells|they don'?t want)\b": -3.0,
    r"\b(course|masterclass|blueprint|mentorship|signals? group|discord)\b": -3.0,
    r"\b(ai agent|agents?|automat\w+ (income|money)|claude code|chatgpt|gpt-?\d)\b": -3.0,
    r"\b(prop firm|funded account|challenge|scalping strategy ever)\b": -2.0,
    r"\b(best|ultimate|only|#1|top \d+)\b.*\b(strategy|indicator)\b": -2.0,
    r"\b(my (journey|story)|how i (started|quit)|interview|reveals?)\b": -2.0,
}

#: Below this, the queue does not surface it. Set so the batch's known non-converters fall out
#: while its known converters stay in -- an in-sample threshold, and labelled as such.
SURFACE_THRESHOLD = 3.0


@dataclass(frozen=True)
class Candidate:
    video_id: str
    title: str
    channel: str = ""
    score: float = 0.0
    hits: tuple[str, ...] = field(default_factory=tuple)

    @property
    def url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.video_id}"


def score_title(text: str) -> tuple[float, list[str]]:
    """Score one title/description. Returns (score, matched-pattern descriptions).

    HITS ARE RETURNED so the queue can show WHY something ranked, which is the difference between
    a list a human trusts and one they ignore. A ranking with no visible reason gets overridden by
    whatever the reader already believed.
    """
    t = text.lower()
    total = 0.0
    hits: list[str] = []
    for pat, w in POSITIVE.items():
        if re.search(pat, t):
            total += w
            hits.append(f"+{w:g} {_label(pat)}")
    for pat, w in NEGATIVE.items():
        if re.search(pat, t):
            total += w
            hits.append(f"{w:g} {_label(pat)}")
    return total, hits


def triage(
    videos: list[tuple[str, str]], *, channel: str = "", threshold: float = SURFACE_THRESHOLD
) -> list[Candidate]:
    """Score and rank (video_id, title) pairs, keeping only those above the threshold."""
    out = []
    for vid, title in videos:
        s, hits = score_title(title)
        if s >= threshold:
            out.append(Candidate(video_id=vid, title=title, channel=channel,
                                 score=s, hits=tuple(hits)))
    return sorted(out, key=lambda c: (-c.score, c.title))


def _label(pattern: str) -> str:
    """A short human tag for a regex, so the queue explains itself without printing regexes."""
    key = re.sub(r"[\\\\^$.|?*+()\[\]{}]", "", pattern)[:44]
    return key.replace(r"\b", "").replace("  ", " ").strip(" |")
