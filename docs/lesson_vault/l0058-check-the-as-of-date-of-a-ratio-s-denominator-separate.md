---
id: L0058
cost: blind
tags: ["data-hygiene"]
---

# L0058

Check the as-of date of a ratio's DENOMINATOR separately from its numerator. A vendor field named *_now (pct_circ_now, *_current, *_latest) joined to historical events is a silent look-ahead in the CONDITIONING variable even when the return series is spotless -- and it fails toward a FALSE NULL, the one direction no gate here catches, because a killed axis produces no alert.

## Evidence

data/unlock_event_screen.json: pct_circ_now is % of TODAY's circulating supply applied to events back to 2016. Supply grows, so old unlocks that were huge shares of float record as small ones -- the >=10% insider bucket holds 14 events and >=30% holds 0, structurally, not empirically. 0/27 cells 'failed' partly because the conditioning variable was unmeasurable, and the axis would have been graveyarded as dead.

## Tags

#data-hygiene

## Related

- [[l0059-a-guard-that-enumerates-a-hardcoded-subset-of-its-inpu]]
- [[l0063-run-a-leak-detector-on-data-you-know-is-clean-before-y]]
- [[l0065-a-green-local-gate-proves-nothing-unless-the-installed]]
- [[l0072-a-gate-that-must-execute-an-artifact-to-judge-it-is-no]]
- [[l0074-an-alarm-must-name-the-cause-its-data-supports-never-t]]
- [[l0076-counting-dated-rows-is-not-counting-observations-and-t]]
- [[l0080-libs-ops-input-provenance-inputs-read-json-records-a-s]]
- [[l0082-a-positive-control-is-not-enough-add-a-no-treatment-co]]
