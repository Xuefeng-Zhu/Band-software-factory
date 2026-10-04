# Workflow timeout repair

This page preserves the Run 2 repair and its original verification. The later [Run 3 queued-receipt repair](run3-queue-repair.md) supersedes the self-notice limitation only for coordinator deliveries with a bound original recipient; Run 2 and Run 3 evidence remain unchanged.

Run 2 stopped after Backend's 600-second Codex turn expired while sending a five-part implementation handoff. BAND accepted parts 1–4, but not part 5 or `END OF HANDOFF`. PM correctly waited for the missing part. The supervisor stayed alive because it tracked process health and budgets, without an executable acknowledgment timer or a notification path for the SDK's reported-turn-failure exception.

The timeout event is `5c4a4579-9088-4abb-a051-ab0400574fb8` at `2026-10-04T04:56:02.933600Z` in room `7ceee003-80f3-4dbc-abc1-d3a8a13d1800`. The retained diagnosis and pre-repair snapshots live in `../runs/judged-stall/20261004T0517Z/`. The owned supervisor and children were stopped at `2026-10-04T05:22:17.198454Z` before editing the factory.

## What changed

- Every admitted turn has a persistent operational outcome, even if the SDK's best-effort lifecycle event cannot be posted. The SDK's reported failure now reaches the watchdog.
- Agents can read their conservative admission deadline using `factory_turn_budget`. The standing protocol reserves up to 60 seconds for checkpointing and a complete handoff, without extending any limit.
- Numbered handoffs retain exact event, sender, recipient, part and declared-digest bindings. Transport completion and recipient acknowledgment are separate. Only a complete, canonically acknowledged delivery clears its receipt wait; that still does not establish acceptance.
- An executable acknowledgment timer can produce at most two notices to PM per incident, or the lower configured cap. Failed recovery turns and restarts share that allowance. A notice contains operational identifiers and missing-part facts, never replacement product requirements or a replayed payload.
- Notification sends hold the same semaphore as model turns. Durable claims precede sending; the budget is checked again afterward. The supported generated BAND message endpoint uses `max_retries: 0`, and its request window is capped by the remaining room and overall time. Ambiguous delivery is retained and never retried automatically, including a second tool call in the same turn.
- Notice-cap exhaustion waits for an already active turn to finish within its existing deadline. Unknown delivery and conflicting protocol state block immediately. Process status and workflow health are reported separately.

The SDK ignores an agent's own messages. A coordinator failure therefore becomes `blocked_coordinator_self_notice`, rather than attempting an ineffective self-message or substituting another identity. Restarting with an unresolved incident but no bound original SDK sender context also blocks. These are explicit recovery limits.

## Verification and preserved evidence

All **211 offline factory utility tests passed**, including 32 watchdog regressions and 15 runtime/SDK integration tests. The integration tests replay the observed four-of-five timeout shape through the real SDK tool dispatcher, response schema and lifecycle emitter, with network connections prohibited. They verify receipt binding, durable restart behavior, no automatic POST retry, the claim-to-send budget race, the active-writer gate, the coordinator self-message limitation and cumulative-counter preservation. They do not establish live BAND delivery or model behavior for the repaired factory.

`verify-tasks` still passes for all six original packets. Structural/source validation passes. The current product checkout is unchanged and clean at `86ad17c600fd994bcb55c222049b7d0546f2e472`; its original owner-run isolated Stage 1 report records 120/120 passing checks. Independent QA/reviewer acceptance has not occurred, and stages 2–4 remain unimplemented.

The cumulative budget, ignored configuration, original freeze and original dispatch ledger remain byte-identical to the pre-repair snapshots. Consumption remains 24,009,633 reported tokens, with 70 cumulative PM turns. The existing cap is 100 turns per seat, leaving PM 30; the repair grants no new allowance. No model calls, BAND messages, room creation or task re-dispatch occurred while implementing or testing the repair.

## Applying the repair

The old frozen run correctly rejects restart because its runtime and standing protocols changed. Do not edit its freeze or dispatch record to bypass that gate, and do not manually send the missing handoff part.

The [pinned participant guide](https://github.com/band-ai/dark-factory-wearedevs/blob/803560d2a678ace1414465c098eb0ab5380ffade/docs/participant-guide.md#build-and-check-each-stage) permits intervention while developing the factory, then requires a fresh room and fresh result repository for the chosen submitted run. The initial stage task is its only human input. Preserve Run 2 as development evidence, validate the repaired factory before selecting a new run, and resolve its finite budget and room scope before dispatch. A transparently assisted continuation could be used for development, but must not be described as an untouched autonomous submission run.

The full-session export must still be downloaded using BAND's console action. The API event snapshot used to diagnose this stall is not a substitute for that export.
