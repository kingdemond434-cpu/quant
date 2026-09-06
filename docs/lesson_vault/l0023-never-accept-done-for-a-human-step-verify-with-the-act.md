---
id: L0023
cost: blind
tags: ["ops", "verification"]
---

# L0023

Never accept 'done' for a human step. Verify with the actual call the step exists to enable, and record the observed reply.

## Evidence

the principal twice believed VPS auth was complete when it was not; ~/.claude_token.env contained the CLI's 'Not logged in' error text, which the service then sourced as a token

## Tags

#ops #verification

## Related

- [[l0114-a-resourcewarning-fired-from-a-deallocator-is-unraisab]]
- [[l0225-a-date-stamp-that-records-that-a-job-ran-never-what-it]]
