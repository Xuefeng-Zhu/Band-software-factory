# Shared task board

Newly prepared factory sessions project structured work items onto the room's BAND
Work board through the installed SDK's public task API. No native Desktop worker,
`band attach`, extra identity, chat dispatch, or separate inference process is needed.
The board complements the complete addressed room handoffs and their receipts.

The separate Desktop **Agent tasks** section is a private list tied to a native
runtime session. The installed Python SDK does not expose that binding or list API.
This integration populates the **shared board** and makes no private-lane claim.

## Agent workflow

The admitted tools expose three operations:

- `factory_task_board {}` returns a compact local index: version, BAND task ID,
  owner, confirmed state, candidate commit, pending-write status and
  `owner_sync_pending`. `sync_error` reports deferred automatic updates.
- `factory_task_board {"id":"WORK-1"}` returns that complete authoritative
  record in `items["WORK-1"]`, including requirements and evidence. Read this
  before acting on an assignment. A pending write retains its proposed complete
  record under `pending.item`; it is not a confirmed version. The only optional
  read argument is `id`; omitting it or passing `null` selects the index.
- `factory_work_item {item, expected_version}` publishes a complete work-item
  record. Use version `0` for a new ID and the latest returned version for updates.
  The `item.state` is the desired state. Repeating an already confirmed identical
  record is a no-op; changed records require a valid transition.
- `factory_reconcile_task {id, task_id}` reads one exact BAND task to confirm an
  uncertain write. It does not resend. For an uncertain create, find the task's
  exact UUID with `band_list_tasks`, then reconcile it. A mismatch stays blocked.

The coordinator creates a PROPOSED or READY item with a nominated independent
reviewer, an actual roster owner, and the complete requirements. READY freezes
the scope and ownership; dependencies must already be ACCEPTED. The coordinator
sends the complete addressed assignment in the room. Board creation itself does
not join or message the owner. The owner's next admitted turn joins its pending
items automatically, and the owner publishes IN_PROGRESS before implementation.

The owner publishes REVIEW with a full candidate SHA, commands, results, and
absolute evidence paths. The nominated reviewer sends its actual verdict to the
owner in the room, beginning with `WORK-REVIEW WORK-ID version N ACCEPTED candidate
<full SHA>` (or `REJECTED`), followed by its review findings. `N` is the current
REVIEW record version. It then publishes ACCEPTED
or REJECTED with the confirmed returned message ID in `room_event` and separate
nonempty `review_commands`, `review_results`, and `review_evidence_paths` lists.
Review cannot replace the delivered candidate or implementation evidence.
An old verdict cannot accept another work item, another review version, or a
different verdict. Rejected work needs a changed repair commit before another REVIEW.

Only the authenticated owner may change its own BAND assignment. Reviewer
decisions update the shared detail without joining the task as a second assignee.
On the owner's next admitted turn, synchronization applies the recorded verdict
using that owner's context. Thus acceptance may temporarily show
`owner_sync_pending: true`; it is not proof the remote board already shows Done.
The owner should send its final acknowledgement after this synchronization.

| Factory state | Owner's BAND assignment |
| --- | --- |
| PROPOSED, READY | `pending` |
| IN_PROGRESS | `in_progress` |
| REVIEW | `in_review` |
| REJECTED, BLOCKED | `blocked` |
| ACCEPTED | `completed` |

The server supplies the aggregate `overall_status`; the factory does not infer
its rollup or Desktop column rendering. BLOCKED and ACCEPTED are terminal. A
resolved blocker requires a new item that preserves the original evidence.
REJECTED permits the owner to resume IN_PROGRESS under the active consumption
policy. Balance-only mode does not impose a repair-count ceiling.

## Persistence and failure behavior

The mapping lives at `runs/runtime/task-board-<room UUID>.json` beneath the selected
profile's runs directory, bound to the exact room and roster. It retains pending
operation details before each write, verifies the response's room, task identity,
detail and applicable owner status, and commits the confirmed version atomically.
Concurrent local changes are serialized. No operation resets budgets or deadlines.

New writes store their exact BAND subject/detail separately from the complete
local work item. Details up to 10,000 characters keep the original formatting;
larger items use compact JSON if it fits, otherwise a compact projection with
the complete item's SHA-256 and a targeted `factory_task_board` read instruction.
The complete requirements remain in the authoritative record and addressed
handoff. Previously stored projections and legacy pending writes retain their
original bytes during reconciliation. Python callers of `TaskBoard.snapshot()`
still receive the complete board.

The underlying SDK convenience methods default to retries. This integration uses
their public generated REST methods with `max_retries=0` and a transport timeout.
Finite policies also apply the remaining turn, session and room time;
balance-only mode does not impose those execution deadlines. Cancellation,
timeout, missing responses,
or mismatched readback leave a durable pending claim. Restarting cannot retry that
write. Reconciliation confirms only an exact matching task; an absent or changed
task requires investigation, not a guessed replacement or automatic resend.
Future write diagnostics preserve the sanitized error class and HTTP status
when available. A recorded rejection or unknown transport outcome never clears
the pending claim automatically.

Board changes do not call the room-message API. Service-side notification behavior
still needs live verification. Credentials and full chat text are not copied into
the mapping. It stores complete work items intended for the board, plus confirmed
review-message IDs, actor/recipient IDs and candidate hashes.

Raw `band_create_task`, `band_update_task`, and `band_set_board` model tools are
blocked so retained tool definitions cannot bypass the work-item gates. BAND's
read tools remain available. Direct human or external board edits are not silently
overwritten: the next write checks the previous detail and requires reconciliation
when it differs. Such conflicting edits cannot be auto-resolved by the read-only
reconciliation operation.
An automatic sync failure is retained as `sync_error` and is not retried on each
turn. It does not prevent the owner from reading the board or reporting a blocker.
An explicit matching reconciliation or successful publication clears the error;
an external conflicting edit must first be resolved against the preserved record.

## Activation and verification

The change is part of the factory source and standing collaboration protocol.
Prepare fresh source/task integrity evidence, rehearsal evidence and a matching
freeze before launching the next judged session. Do not restart an existing
frozen run merely to display tasks, or rewrite its retained freeze/configuration.
No historical tasks are inferred from prose, receipts, turn completion or process
presence. A future live rehearsal must verify the actual board rendering and
notification behavior; offline SDK tests establish neither of those layers.

Run the focused checks from the factory directory:

```sh
.venv/bin/python -m unittest discover -s tests -p 'test_task_board*.py' -v
.venv/bin/python -m unittest discover -s tests -p 'test_workflow_runtime.py' -v
```
