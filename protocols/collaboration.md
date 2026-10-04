# Collaboration and delivery

This standing protocol is reusable across products. Product requirements arrive only in the dispatched task. Runtime identities and limits arrive in verified, frozen configuration. Unknown metadata or absent finite limits blocks execution.

## Work items

Use the empty work-item template. Each item carries its ID, owner and next recipient by literal roster handle, dependencies, state, goal, complete applicable requirements, absolute repository and workspace paths, starting revision, ownership boundaries, acceptance criteria, candidate full commit ID, commands, results, evidence paths, limitations and remaining limits. The coordinator maintains the queue; state changes are material room messages, not substitutes for work.

The executable record uses `id`, `owner`, `dependencies`, `state`, `goal`, `requirements`, `starting_revision`, `workspace_paths`, `ownership_boundaries`, `acceptance_conditions`, `candidate_commit`, `commands`, `results`, `evidence_paths`, `limitations` and `next_recipient`. Requirements and acceptance conditions are lists containing complete text; workspace and evidence paths are absolute-path lists. READY and later work requires nonempty goal, requirements, starting revision, workspace paths, ownership boundaries and acceptance conditions. REVIEW requires candidate, commands, results and evidence. BLOCKED or REJECTED additionally requires `bounded_next_action`; ACCEPTED requires a distinct `reviewer` and supporting `room_event`. Empty templates intentionally fail execution validation until the team completes them.

Transitions:

```text
PROPOSED -> READY -> IN_PROGRESS -> REVIEW -> ACCEPTED
REVIEW -> REJECTED -> IN_PROGRESS
Any state -> BLOCKED
```

READY requires complete inputs, satisfied dependencies, agreed ownership, permissions and verifiable acceptance. Only the owner starts IN_PROGRESS. REVIEW requires a committed candidate and evidence. Independent acceptance binds to that exact candidate. REJECTED records a requirement-linked defect and bounded repair. BLOCKED records evidence, exhausted recovery and a finite next action; it is an outcome, not an indefinite wait. The coordinator may create a replacement READY item after resolving a blocker within existing scope and limits, preserving the original record.

## Full handoffs and receipts

All assignments, material decisions, defects, deliveries and acceptance go through the bound room using actual verified handles. Do not infer handles from display names or use a local file as the only communication record. Assume a recipient sees only addressed messages.

Every handoff pastes the full task and complete applicable requirements, including inherited requirements. Add paths, commit IDs, constraints, ownership, acceptance, evidence and remaining limits. A message ID, task ID, URL, attachment, summary or instruction to read room history cannot replace this content.

For a long handoff, split the full UTF-8 payload into ordered messages. Each part has the same work-item ID and delivery ID, part index, total count, payload digest and next recipient. The final part says END OF HANDOFF. The recipient acknowledges the complete count and digest only after receiving all parts. It requests missing parts from the sender, takes no action on partial content and ignores duplicate parts with matching identifiers. Conflicting payloads under the same delivery ID are rejected. A retry uses the same delivery identity, so delayed messages cannot start duplicate work.

Use this exact first line for each numbered part, substituting the existing identifiers, digest and verified recipient: `WORK-ID delivery DELIVERY-ID part 1/5; SHA-256 <64 hex characters>; recipient @[[recipient UUID]]`. Identifiers use letters, digits, periods, underscores or hyphens. The final part ends with `END OF HANDOFF` on its own line. Only the header is machine-observed; every part still contains the original payload. Each recipient sends a standalone `HANDOFF-ACK delivery DELIVERY-ID; SHA-256 <same digest>; sender @[[original sender UUID]]` message, mentioning that sender, after receiving every part and checking the full payload digest. Send any review or acceptance separately. This receipt confirms complete communication only; it does not accept the work.

The supervisor persists numbered-send metadata and canonical receipts. After the acknowledgment deadline or a failed turn, its frozen watchdog can send the coordinator at most two operational notices for the same incident; a lower configured cap wins. Notices identify existing turns or missing delivery parts and do not replace complete task requirements. The coordinator handles them using the existing task, ownership, evidence and remaining limits. A recovery turn or process restart does not reset the notice allowance. No notice is sent during another active turn, after the coordinator or cumulative budget is exhausted, or after an uncertain notification result. An unresolved or ambiguous recovery is visibly BLOCKED, even if a supervisor process is still alive. The SDK filters self messages, so a failed coordinator cannot be awakened by its own notice; that case is visibly BLOCKED without substituting another sender.

## Membership and delayed peers

Before first delegation, the coordinator verifies all configured seats are in the room. Only the coordinator may add an exact preconfigured missing identity with supported membership tooling. It does not recruit or substitute another seat. On a missing-participant error it attempts the exact add, verifies membership and retries the complete handoff. The coordinator records the observed error and attempted recovery.

Wait only until the configured acknowledgment deadline. Retry missing or delayed delivery at most twice, preserving identity and evidence; the lower task limit wins. Require acknowledgment and reply evidence rather than relying on process presence or membership alone. If the peer is still unavailable, perform independent unaffected work within limits, then report BLOCKED for dependent work. A missing receipt is not an acceptance.

## Recovery and autonomy

Use task-configured repair limits; default to at most two repair attempts per work item. Two identical failures require a changed diagnosis or approach before another allowed attempt. Repeating a command without changed evidence does not count as a new approach. Never exceed active-work, elapsed-time, repair or consumption limits. The coordinator may replan optional work within scope, but cannot waive required behavior or a failed release gate.

From initial dispatch to the coordinator's final outcome, do not ask or wait for human clarification, approval, confirmation or debugging guidance. Resolve choices from complete requirements and peer evidence. If existing authority or permissions are insufficient, report the concrete blocker as the outcome. No rule here authorizes new spending, publication, submission or broader permissions.

Use expert effort where it affects the work. All seats remain registered; every small edit does not require seven serial approvals. Do not manufacture disagreement, redundant messages or nominal ownership to simulate collaboration.
