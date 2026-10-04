# QA-S1 — independent host/source review; defects found

Owner @frankzhu94/factory-qa; next recipient @frankzhu94/factory-pm. Work state REVIEW (QA report delivered); product disposition REJECTED for two boundary defects. Isolated/resource acceptance remains BLOCKED. No stage acceptance or architecture resource waiver.

Starting and tested full revision: `68afbf86127ae9b2b5dc8ecc56a0e9c78e6a69f1`. Review clone: `/private/tmp/qa-s1-20261004T2218Z`. Shared repository: `/Users/frank/mygit/Tablekeeper/result-run-5`. Both were verified clean at this exact revision before/after checks. Product tree matches owner implementation `249e5712624d20ca02c9680eb6ec60ff3865bcb8` as dispatched; no production or tracked test/map changes made. Evidence root: `/Users/frank/mygit/Tablekeeper/result-run-5/.evidence/qa-s1-20261004T2218Z`.

Complete incoming 3/3 digest `62c3e2101fb37761f96e3c67d8ff2b78efa13ae39764c070df57c6cfebb1d809` verified. Receipt event `d00bafb7-19d4-4f31-924d-e33f2b7ea1db`; IN_PROGRESS `2cf99cd8-8487-4523-a100-4551207f337d`; initial defect notification `3eb83170-475c-4f14-b719-a2e5389876cb`. These records are independent of owner checks.

## Defect QA-S1-DATE-MAX

Requirements: stage-1 §4 allows any calendar date, §8 availability emits every grid slot whose absolute end is at/before close; §5 errors must follow their specified cause. A valid date must not be rejected because a later, non-emittable candidate slot would run beyond the calendar representation.

Minimal reproduction: reset to `repro-fixture.json` (two synthetic users; restaurant `r`, timezone UTC; all weekdays open 18:00–23:00; grid30; duration90; capacities2 and4; empty reservations). Anonymous `GET /availability?restaurant_id=r&date=9999-12-31&party_size=2` returns **422 validation_failed**. Expected **200**, eight local labels `18:00,18:30,19:00,19:30,20:00,20:30,21:00,21:30`, both tables available. A direct valid `POST /reservations` for `9999-12-31T18:00` returns201, independently demonstrating the date is accepted by booking.

Evidence: `extra-results.json` preserves the original failing group and trace; `calendar-diagnosis.json` isolates which date failed; `remaining-http-results.json` confirms direct creation succeeds. Source diagnosis (not a substitute for HTTP evidence): `stage-1/tablekeeper/core.py:123` computes absolute end before comparison with close, catches overflow as generic validation at127; `service.py:161–166` iterates through22:30 and propagates that validation instead of discarding the outside-hours candidate. Repair recommendation: exclude provably beyond-close candidates safely without rejecting the valid availability query; preserve DST absolute-duration semantics. No fix performed.

## Defect QA-S1-QUERY-DIGITS

Requirements: §5 integer query representation accepts plain decimal digits and reserves malformed_request for unparseable bodies/wrong body field types; §8 availability takes positive party size and returns every slot with tables whose capacity suffices. No numeric maximum or query digit-count bound is stated.

Same reset. Construct the exact request with `'/availability?restaurant_id=r&date=2096-09-24&party_size=' + ('9' * 5000)`. This is one ordinary ~5KB request, not a load/stress test. Observed **400 malformed_request**. Expected **200** with eight slots and empty `available_table_ids`, because the positive party count exceeds both capacities. `calendar-diagnosis.py` is the executable reproduction; `calendar-diagnosis.json` preserves status/code. The body is absent and the query contains only decimal digits.

Source diagnosis: `service.py:157–158` calls Python `int` on unbounded query text; the host runtime's decimal conversion guard raises ValueError, caught as malformed_request by the HTTP handler. Repair recommendation: validate/compare a decimal count without exposing implementation conversion limits or adding an unstated product bound; retain rejection of exponent/decimal-point/plus representations. No fix performed. This observation is host Python3.13; equivalent container behavior has not been claimed.

## Observations by layer

- Unchanged original HTTP suite: **11/11 PASS**, two separate real host entrypoints, `baseline.json`, `baseline.log`. Includes50 simultaneous identical requests (one201/rest200),50 conflicting keys (one201/rest409), reused failed keys, all four required DST transitions, cutoff margins, swap/rollback, independent destination import and original receipts.
- New HTTP groups: **6 PASS, 1 FAIL**, `extra-results.json`. PASS: ID64 acceptance/65 rejection and failed reset unchanged; malformed bearer/signup fields/type/email; moves key0/1/255/256 and nested JSON/array/bool equality; failed amendment full-state snapshots plus batch owner/restaurant/no-op conflict and late validation; malformed/invalid import unchanged destination;12 simultaneous successful/rejected batches and exports, each observed snapshot imported/replayed coherently. Calendar group failed on9999-12-31 before later assertions; the failure was preserved.
- Focused diagnosis: valid leap dates2000/2400 and0001 accepted; invalid1900/2100 leap dates/year0000/April31 rejected422;9999-12-31 availability rejected422;5000-digit query rejected400. Separate continuation `remaining-http-results.json`: **6/6 PASS** for direct creations on2000/2400/0001/9999 dates, all-occupied slot retention and ignored query equality. No failing evidence overwritten or silently converted green.
- In-process source seams: **3/3 PASS**, `storage-results.json`: independent SQL trace/index assertions, append-only history, no-op/replay/repeated-cancel no mutation, no-op batch receipt-only insert; separate injected failures before receipts/history/core persistence rollback complete state and permit same-key retry; injected replacement failure restores all tables; cutoff one second before/equal/after gives200/409/409 using a deterministic supplied clock. Password records were independently checked by recomputing synthetic scrypt digests; no hash/token/export value written to evidence.
- Actual legacy process import: **PASS**, `legacy-results.json`. Old revision `12e43a92dd6e037ac27dfb2189f18eed35a32fbc` source archived under `/private/tmp/qa-s1-legacy-20261004T2218Z`, launched as a third real process. Unchanged old export imported into repaired destination; exact logical state preserved, old token/password login and create/move receipts worked, failed key remained reusable, later source cancellation did not alter saved snapshot. All three own process handles were stopped; `processes.json` and `legacy-results.json` confirm cleanup.

The SQL implementation removes unrelated historical receipt/history parsing from normal routes and uses a unique indexed user/method/path/key address. Health performs a scalar query. Atomic rollback was observed at three persistence points, not merely inferred from source. Ordinary requests still deserialize all mutable core users/sessions/config/reservations under a global lock; real changes reserialize core; occupancy scans reservations. Export materializes full receipts/histories under that lock. Scale-independent latency is NOT established.

## Exact commands and status

`git fetch origin` exit0; no merge/branch movement because candidate is frozen. `git clone --no-hardlinks --no-checkout /Users/frank/mygit/Tablekeeper/result-run-5 /private/tmp/qa-s1-20261004T2218Z` and `git -C /private/tmp/qa-s1-20261004T2218Z checkout --detach 68afbf86127ae9b2b5dc8ecc56a0e9c78e6a69f1` exit0. Status porcelain empty; rev-parse exact before/after. No commit/push authorized or made.

Let P=`/Users/frank/mygit/Tablekeeper/runs/harness-venv/bin/python`, E=`/Users/frank/mygit/Tablekeeper/result-run-5/.evidence/qa-s1-20261004T2218Z`, C=`/private/tmp/qa-s1-20261004T2218Z`:

1. `P E/manage.py` exit0; exact subprocess argv, dynamic ports, PIDs, start/end UTC and baseline exit0 in `processes.json`. Services used `PYTHONPATH=C/stage-1`, `PORT=<recorded-port>`, `PYTHONDONTWRITEBYTECODE=1`, and `P -m tablekeeper.server`. Baseline used unchanged `C/tests/qa_stage1_boundaries.py` with both actual URLs, full revision and `--out E/baseline.json` (full argv in record).
2. `P E/extra.py > E/extra.log 2>&1` then `cat E/extra.log`: shell exit0 is the final cat status, not a passing suite. The script's preserved result is six PASS/one FAIL; do not label the compound command green verification.
3. `P E/calendar_diagnosis.py` exit0 (diagnostic collecting actual statuses, not asserting pass).
4. `PYTHONDONTWRITEBYTECODE=1 P E/storage.py > E/storage.log 2>&1` then cat: shell exit0; result file independently reports3/3 PASS.
5. `PYTHONDONTWRITEBYTECODE=1 P E/legacy.py` exit0; exact legacy archive/start details in script and result.
6. `PYTHONDONTWRITEBYTECODE=1 P E/remaining_http.py` exit0,6/6 PASS.
7. `touch E/stop`; manager completed exit0 and stopped only its own two children. Legacy process stopped by its own finally block.

## Explicit NOT_TESTED and remaining limits

Docker unresponsive/cleanup unresolved was inherited; no Docker operation attempted. Official isolated run, Python3.12 image, no-outbound runtime, 2CPU/2GiB behavior, custom/default PORT across Docker,60s container boot and128/256/512 heavy-receipt/resource measurements remain **NOT_TESTED/BLOCKED**. No unchanged missing-socksio harness retry or installation. Host tests do not substitute for these gates.

`coverage.json` maps every original Stage1 boundary class to evidence and untested residue; PASS means only named observed cases. Remaining non-exhaustive classes include arbitrary additional zones/historical transitions, arbitrary nested receipt structures/number magnitudes, every malformed reset/import tree, cancellation/PATCH plus read serial histories beyond tested create/batch races, and unusual cutoff/date/offset combinations. No dedicated list-order tie test, full50-way mixed batch/read/export race, or exhaustive import-corruption validation was run. Future-stage behavior remains NOT_TESTED.

Bounded next action: PM dispatches a new attributable product repair for the two reproduced defects (repair1/3 was already used; QA made no repair), preserving this frozen candidate and failure evidence. Then independently rerun failing probes plus affected grid/query regression against the replacement full revision; do not move an active reviewed candidate. Continue architecture resource verification and independent GATE-S1 only when the existing authorized environment permits. No stage2 advance/copy, infrastructure repair, human clarification or spending.

One active evidence writer; no subagents. Work deadline2026-10-04T22:27:22.491494Z; handoff deadline22:28:22.491494Z; acknowledgment120s and<=2 identical-delivery retries. Global2026-10-05T02:35:03.700437Z. Current measured consumption/cost UNAVAILABLE. Full canonical dispatched requirements accompany the return handoff.
