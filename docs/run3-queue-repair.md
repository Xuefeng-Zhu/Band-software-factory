# Run 3 queued receipt repair

Run 3 stopped after Stage 1 acceptance with twelve outbound parts confirmed but only eight recipient callbacks completed. Its receipt timer had matured while part 6 was running. Inspection of SDK serialization identified a missing queue barrier; the old runtime did not measure queue depth, so the exact local-versus-remote location of the four still-pending parts is unverified. PM's original turn completed; this was not a 600-second turn failure. The old recovery route could only send to PM and blocked a PM-authored self-notice.

## Changes for future runs

The runner now reads the pinned SDK's local room execution state before emitting a recovery notice. `Agent.runtime`, `PlatformRuntime.runtime` and `AgentRuntime.active_sessions` expose the maintained `ExecutionContext`; its `queue`, `state`, `is_processing` and `is_running` describe work owned before the adapter's callback. The heartbeat and locked send path both consult that state. Queue activity defers only recovery notices and exhausted-notice decisions. It does not reset the receipt timestamp, shorten or extend a model turn, increase a token/turn allowance, or override room/global deadlines. Unknown sends and conflicting protocol evidence still block immediately.

A PM-originated unresolved delivery now uses PM's own SDK sender context to address only original unacknowledged recipient identities. The notice requests receipt/reassembly: ACK the verified original complete payload, or ask PM for missing original parts. Their real BAND response can wake PM. It does not inject an adapter event, impersonate another agent, send a synthetic human message, copy product requirements from outside the room, or grant an implementation lease. A PM failure with no original recipient remains explicitly blocked.

Durable claims still precede POST; the generated SDK endpoint has retries disabled. Both sender and recipient limits are checked before and after the claim. Confirmation must contain the exact expected recipient set and a real unique event UUID. Ambiguous outcomes are retained without a retry. Recipients handling a notice share the original incident's two-notice cap; a restart cannot reset it. Multi-recipient handling is tracked per bound recipient, and only an actual canonical delivery ACK resolves its receipt wait.

The application, original mandates, room export and eleven seat-authored commits are untouched. Only the separate reusable factory source and future standing protocol change. Do not present this repair as part of the factory that produced Run 3.

## Compatibility and limitations

This integration is pinned to BAND SDK 4.0.0 and its default ExecutionContext. Missing, duplicate, custom or stopped execution contexts fail closed. The helper reads local ingress without popping queue items or mutating SDK state. A drained local queue does not establish that remote `/next` has no backlog during an idle poll; the receipt mechanism remains bounded by the existing notice and global limits. This is not a new messaging implementation.

Offline regression tests use the installed SDK's real queue ingress, tool dispatcher and response schemas, with network disabled. They cover the observed completed twelve-part PM handoff, queued callbacks before adapter admission, processing after callback completion, exact recipient routing, shared retry budget, durable restart/unknown-send behavior and expired cumulative limits. Their fake providers are utility-test evidence only. Live BAND delivery and model response for this revised path remain unverified until a separately authorized rehearsal.

## Evidence preservation and launch state

`../runs/run3-preservation-20261004T164154Z/` holds the pre-edit runtime, workflow, cumulative budget, freeze and source hashes. The single judged dispatch and original configuration are retained. Structural validation and original task integrity are separate from runtime readiness; an old READY manifest cannot authorize changed source.

The overall deadline expired at 2026-10-04 13:29:59.700437 UTC. No supervisor was restarted, no message was sent and no model turn was requested during repair. A renewed finite allowance, fresh communication rehearsal, new evidence binding and a fresh freeze are required before future live work. Run 3 must remain intact; a new judged attempt begins in a new room and an empty result repository.

## Verified offline result

All **224 factory utility tests passed** on October 4 at 16:58:59 UTC, including 39 watchdog, 19 SDK/runtime and 2 independently authored real-SDK queue-ingress tests. `../runs/run3-offline-repair-20261004/verification.json` binds the result to exact source hashes; `unit-tests.log` retains every case. Independent review found no actionable P1/P2 issue. `git diff --check`, structural validation and all six original task-integrity checks pass.

The installed SDK exposes the read path at `band/agent.py` (Agent.create/start), `band/runtime/platform_runtime.py` (runtime property and default AgentRuntime), `band/runtime/runtime.py` (active_sessions and awaited context creation), and `band/runtime/execution.py` (public queue/lifecycle state and on_event). SDK startup awaits admission of existing rooms. A failed subscription may return with a retry pending; missing contexts deliberately block this factory instead of assuming an empty queue.

Read-only judged launch validation still rejects this old run for the expired cumulative deadline and changed runtime/protocol hashes. The actual budget, ignored configuration and original freeze remain byte-identical to their preserved snapshots. The [proposed rehearsal](queue-repair-rehearsal-plan.md) is prepared but not dispatched.
