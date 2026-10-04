@[[7d26ccf7-2921-4b38-9e16-ca8ebfa2a448]]
# Approved queue-repair communication rehearsal

This is the one initial human task for a new, unscored synthetic communication rehearsal. Human approved the prepared plan on October4; approval observed2026-10-04T17:12:53Z, absolute overall deadline2026-10-04T17:42:53Z (runtime conservatively rounds earlier). The proposal-status text in docs/queue-repair-rehearsal-plan.md is historical; this packet records actual authorization. No later human steering is allowed. The operator will stop workers at completion or no later than10minutes from this dispatch.

Room: 4ec4749d-5dff-4d41-ae9b-5a5bc82462ac
Factory revision: c53ea314f21ab37f36e927ab503c086bd2ecced9
Factory: /Users/frank/mygit/Tablekeeper/factory
Assigned neutral practice checkout: /Users/frank/mygit/Tablekeeper/rehearsal/queue-repair-result
Starting revision: UNBORN (zero commits, only .git). This is communication-only, so no application candidate or acceptance is applicable. Do not write implementation, create commits or touch any judged result. Evidence is the real room plus supervisor state; final outcome is a room message.
Scoped config: /Users/frank/mygit/Tablekeeper/runs/queue-repair-live-20261004/factory.yaml
Operator evidence: /Users/frank/mygit/Tablekeeper/runs/queue-repair-live-20261004
Config SHA256: cef8e193a0cec8d89016339aa63630ae0e76a6411988c648252dc633e119dbe2

Approved scope: same seven configured seats plus Frank; only PM and Backend need turns. Other seats remain idle. One active seat, 600-second maximum turn, 120-second ACK interval, at most two operational notices per incident, 300 cumulative turns per seat. Baseline tokens84,080,166; stop at86,080,166 reported tokens, preserving all prior consumption within the100,000,000 ceiling. Subscription only; no API billing or paid provisioning. Stop earlier at any timer, unknown-send or binding conflict. Read factory_turn_budget before doing work. A missing turn limit is a blocker.

The operator has already verified authentication, registration and permissions without model turns. Do not launch another runtime, perform login, alter any limit or run nested operator probes. Use supported current-room messaging tools, the read-only factory_turn_budget tool, and local no-network commands solely to verify fixture bytes and digests; no files, commits or product work. There is no Docker/browser/application work. Native assignment/reply messages are allowed; never forge user/peer identities or inject synthetic model callbacks.

PM handle: @frankzhu94/factory-pm ; UUID 7d26ccf7-2921-4b38-9e16-ca8ebfa2a448
Backend handle: @frankzhu94/factory-backend ; UUID b2f43e4e-7727-44bb-9154-6cdc2b781749

## Sequence and full recipient assignment

PM first sends Backend one complete ordinary assignment containing this entire exercise specification, exact IDs/digests, reconstruction and waiting rules, paths, finite limits and roles. This setup is not a numbered fixture part. Backend sends PM a single ordinary directed `ASSIGNMENT-READY QUEUE-REHEARSAL` reply confirming complete instructions, then ends its turn. No other setup acknowledgment can satisfy fixture A or B. PM must wait by ending its turn, not by sleeping or polling. Only after that actual reply may PM begin A.

Each fixture's payload consists of ASCII lines ending in one LF byte(0x0a). Hash only their ordered concatenation; exclude all header text and END OF HANDOFF marker. The backslash-n notation below means LF, not two literal characters. Knowing a payload line from setup is not receipt of its original numbered transport part. Track actual numbered message events and refuse incomplete/conflicting/duplicate execution.

A: work-item `QUEUE-A`; delivery `QUEUE-A-D1`; Backend recipient. Complete payload216bytes, SHA256 `96f11730eea33e816c0ea745e4592b713c971785d73b7160719c6a673fb79e81`. Twelve lines `fixture-A-part-01` through `fixture-A-part-12`, each plus LF, one original line per corresponding numbered message. Use exact firstline `QUEUE-A delivery QUEUE-A-D1 part i/12; SHA-256 96f11730eea33e816c0ea745e4592b713c971785d73b7160719c6a673fb79e81; recipient @[[b2f43e4e-7727-44bb-9154-6cdc2b781749]]`. Parts1–11 have only header/newline/payloadline; part12 additionally ends with END OF HANDOFF on its own line outside hashedpayload. PM sends all12 promptly in one turn then ends. Backend consumes partials with no_reply; do not sleep, poll, repeatedly request remaining in-flight A parts or ACK incomplete data. After12actualparts, independently calculate digest with a local no-network command and send standalone `HANDOFF-ACK delivery QUEUE-A-D1; SHA-256 96f11730eea33e816c0ea745e4592b713c971785d73b7160719c6a673fb79e81; sender @[[7d26ccf7-2921-4b38-9e16-ca8ebfa2a448]]`, mentioning PM. End the turn. PM must receive this actual canonical A ACK before B.

B: work-item `QUEUE-B`; delivery `QUEUE-B-D1`; Backend recipient. Complete payload36bytes: `fixture-B-part-01\nfixture-B-part-02\n`. SHA256 `cfe87bdc467cf8f1ec05fbb71bce3369517c57759441ca3a5ae3dc7c7fe3f9c5`. Header shape `QUEUE-B delivery QUEUE-B-D1 part i/2; SHA-256 cfe87bdc467cf8f1ec05fbb71bce3369517c57759441ca3a5ae3dc7c7fe3f9c5; recipient @[[b2f43e4e-7727-44bb-9154-6cdc2b781749]]`. PM intentionally sends only part1 with `fixture-B-part-01` plus LF, retains originalpart2, then ends its turn. This is an explicit synthetic rehearsal exception to complete-send practice, not permission to truncate judged assignments.

Backend records B1 as partial, sends no ACK and no missing-part request yet, and ends the turn with no_reply. Neither actor may sleep, poll, hold the active-seat lease, manufacture part2 from these instructions or proactively retry B. The ordinary120-second ACK deadline must elapse. Wait for the automatic supervisor WORKFLOW NOTICE actually sent from PM to Backend for the original B delivery. Only that real notice authorizes Backend's ordinary directed request to PM for the missing original B part2. This task-specific waiting exception exists solely to test the watchdog.

PM replies only to that actual Backend request after notice, sending originalpart2/2 with line `fixture-B-part-02` plus LF and END OF HANDOFF. SameworkID, deliveryID,digest and originalrecipient; no replacement task or newattemptidentity. Backend verifies2actualparts and full36bytepayload before standalone `HANDOFF-ACK delivery QUEUE-B-D1; SHA-256 cfe87bdc467cf8f1ec05fbb71bce3369517c57759441ca3a5ae3dc7c7fe3f9c5; sender @[[7d26ccf7-2921-4b38-9e16-ca8ebfa2a448]]`, mentioning PM. This receipt never accepts a product.

PM posts `QUEUE-REHEARSAL COMPLETE` after both actual canonical ACKs, or `QUEUE-REHEARSAL BLOCKED` with evidence and smallest bounded action. Include both deliveryIDs, observed send/notice/request/ACK eventIDs where available, originaldigest checks and honest unresolvedfacts. Do not invent unavailableeventIDs or claim measured queue depths. No further work after final outcome. No human followup, self-messaging bypass, resending the initial task, unknown-send retry or model reset is authorized.

## Verification boundary

Success requires twelve confirmed A originals and matchingcanonicalACK; then a genuine PM-to-original-Backend operational B notice, real Backend-to-PM missingpartrequest, originalpart2 and matchingcanonicalACK resolving the existingincident withinitscap. Operator observes actual queue state and budgets separately. If A drains before its deadline, live overdue-queue behavior remains UNVERIFIED; offline tests cover it. The original run did not measure queue depth, and localqueue idle does not prove remote backlog empty. These are synthetic messages, not product work.
