"""The E8 prop account: a second venue, its own rules, and nothing that touches the live book.

`tradelocker_venue` resolves, quotes and sends. `e8_guard` is the only thing that may refuse an
order for a prop reason. Sizing stays in `mt5desk.decision_core` for both venues, because two
sites computing "the lot" from two expressions is the defect class this desk has already paid for.
"""
