"""The principal page is APPEND-SAFE or it is a data-loss channel.

ORIGIN (2026-07-29). ``data/PRINCIPAL_ACTION.md`` is the desk's ONLY human-escalation channel and
the pager delivers **line 1**. Two organs write it:

  * ``max_audit`` strips its own escalation block and preserves every other line -- correct, and
    it is correct because exactly this bug was found and fixed there on 2026-07-28.
  * ``run_external_panel`` called ``Path(...).write_text(...)`` twice, bare. A total clobber.

So when the panel ran out of credits it wrote "PURCHASE DECISION: OpenRouter credits exhausted"
over the top of a pending **Tier-3 YES/NO ask** (the pbo/rc campaign-constant gate fix -- GAP #71,
the #1 item on the register, the gate blocking the entire discovery pipeline). The register still
recorded it as "paged, awaiting a ruling". It was never on the page the principal read. A decision
the desk was blocked on was deleted by an unrelated organ's budget notice.

This is the SAME failure shape as the 07-28 max_audit fix, one organ over -- and the adjacency
sweep that should have caught it is itself a written lesson ("a lesson that stays in the file
where it was learned is half a lesson", institutional_knowledge 2026-07-29). Hence a shared
helper rather than a second hand-rolled strip: the next organ that needs to page inherits the
preservation property instead of re-deriving it, correctly or otherwise.

CONTRACT
  * Never destroys text it did not write. Only the caller's OWN prior block (matched by
    ``marker``) is replaced, so repeated pages update in place instead of stacking forever.
  * The new message owns line 1, because that is the only line the pager sends.
  * Writes are verified by reading the file back -- the 07-28 bug was found precisely by
    re-reading after writing rather than trusting the write.
"""

from __future__ import annotations

from pathlib import Path

PAGE = Path("data/PRINCIPAL_ACTION.md")


def _strip_block(existing: str, marker: str) -> str:
    """Drop a previous block written by this same caller, keeping everyone else's text.

    A block is its ``marker`` line plus the indented/blank continuation lines beneath it. Any
    line that is neither is somebody else's message and ends the block.
    """
    kept: list[str] = []
    skipping = False
    for ln in existing.splitlines():
        if ln.startswith(marker):
            skipping = True
            continue
        if skipping and (ln.startswith(("  ", "\t")) or not ln.strip()):
            continue
        skipping = False
        kept.append(ln)
    return "\n".join(kept).strip()


def page(message: str, *, marker: str, path: Path | None = None) -> str:
    """Put ``message`` at line 1 of the principal page, preserving every other message.

    ``marker`` must be a stable prefix of ``message`` (e.g. "PURCHASE DECISION:") so a repeat
    page replaces its own prior copy rather than accumulating duplicates. Returns the text
    actually on disk after the write.
    """
    p = path or PAGE
    existing = p.read_text("utf-8") if p.exists() else ""
    body = _strip_block(existing, marker)
    out = message.rstrip("\n") + "\n" + (f"\n{body}\n" if body else "")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(out, "utf-8")
    return p.read_text("utf-8")            # verify by fresh read, never trust the write
