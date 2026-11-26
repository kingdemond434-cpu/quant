# Box governance planes (2026-11-26)

zuck 14:24-14:33Z: owner, not system administrator. Protected changes queue; everything else runs unattended.

- **Emergency plane (off the box, owner):** Contabo customer panel, prop-firm client areas, MT5 mobile, the firms'
  own loss limits, GitLab account ownership.
- **Protected core (on the box, owner-installed, rarely changes):** the boot mover (QuantForge-BootMove), the pinned
  trust folder (trust_check.py, TRUST_SET.json), D1. Silence is never approval: a change here queues in
  /mnt/project-files/autonomy/PROTECTED_QUEUE.md and blocks nothing else.
- **Operational plane (autonomous):** research, strategies, desk code and tasks through the forge train (Auditor CLEAR,
  trust_check classes); boot changes outside the trust set through the mover (Audit CLEAR, fast-forward, verified
  rewrite, rollback). A change that would need protected authority is re-routed to a compliant implementation in
  this plane first.
