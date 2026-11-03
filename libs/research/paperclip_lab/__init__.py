"""The Paperclip research company: an isolated, free, always-on lab that DONATES cells.

It owns no truth and no capital. Its agents run on an isolated GitHub Actions runner against free
GitHub Models, read only this public repository, and emit one JSON bundle per hour. The box pulls
that bundle through `desks/mt5/research/paperclip_intake.py`, which re-checks every row with
`contract.py` (the narrow donation gateway) and writes survivors to the seat door
`data/intelligence/paperclip/`, where the existing compiler and the sealed gauntlet take over.
"""
