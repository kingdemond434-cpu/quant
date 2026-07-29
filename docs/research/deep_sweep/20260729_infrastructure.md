# AUDITOR FAILED (infrastructure)

WHY: BRAIN_AUTH_FAILED -- no model in the chain answered (pool drained or session limit). This is RETRYABLE: the catch-up re-fires the sweep and the resume logic skips every report already >=1200b, so only the failures re-run
partial report bytes before overwrite: 0 (floor is 1200 -- below it the auditor re-runs on resume)

--stdout(tail)--
BRAIN_AUTH_FAILED: no model in _BRAIN_MODEL_CHAIN answered -- pool drained or session limit

--stderr(tail)--

