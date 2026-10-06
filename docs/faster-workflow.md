# Faster factory workflow

Use the selected attempt's configuration throughout preparation. Put `--config`
before the command, for example:

```sh
scripts/factory --config /absolute/path/to/attempt/factory.yaml runtime-show
scripts/factory --config /absolute/path/to/attempt/factory.yaml verify-tasks
scripts/runtime --config /absolute/path/to/attempt/factory.yaml seat-status
```

Generate packets for the actual configured stages. A two-stage practice now says
stages 1 through 2 and carries those stage inputs; the default four-stage packet
remains unchanged. Regenerate and verify fresh preparation artifacts after a
configuration change. Retain already dispatched packets and failed evidence.

## Read once, then work on the assigned item

These are agent tool calls during an admitted turn, not shell commands:

| Tool | Arguments | Result |
| --- | --- | --- |
| `factory_task_board` | `{}` | Compact index of versions, owners, confirmed states, candidates and pending writes |
| `factory_task_board` | `{"id":"WORK-1"}` | Complete authoritative record at `items["WORK-1"]` |
| `factory_turn_budget` | `{}` | Effective consumption policy for this turn |

Use the index to find the assignment, then fetch its ID before implementing or
reviewing it. The complete item is under `.item`; `.pending.item` is an unconfirmed
proposal. The read accepts only optional `id`, with `null` equivalent to omission.
The admitted room and actor are supplied by the runtime.

Publish the complete item with `factory_work_item {item, expected_version}`.
All required fields remain required, including list fields such as `results`;
an empty results list is valid before implementation, while REVIEW needs actual
results. New large BAND board details use a bounded projection when necessary;
the full record remains available through the targeted read. See the
[task-board guide](task-board.md) for versions, reviewer gates and reconciliation.

## Keep handoffs focused and complete

Include the task, applicable requirement IDs, owner, absolute paths, revisions,
acceptance conditions and evidence. Include complete new or changed requirements
inline. Unchanged inherited requirements may use exact absolute read-only paths,
SHA-256 digests and applicable sections. The recipient must read and verify those
sources before acknowledging complete inputs. A task ID or room-history reference
alone does not supply requirements.

A receipt may put its canonical `HANDOFF-ACK` line first and add an ordinary
explanation below it. The sender, delivery ID and digest must still match the
complete delivery. Extra conflicting protocol headers or an explicit
`INCOMPLETE:` / `REJECTED:` marker are not valid receipts.

In balance-only sessions, a confirmed message with a formatting problem remains
recorded as rejected, but agents continue and can correct it. Complete the
assigned work, send a focused handoff, and end the turn so the next role can work.
Use real product tests and a fixed candidate for acceptance; communication
formatting does not establish a product result.

The OpenCode native read policy permits the selected public specification,
protocol, template and mandate directories while keeping native edits in the
assigned workspace. It does not grant the whole factory, configuration or run
directory. Enabled shell access remains trusted shell access, not an OS sandbox.
Check real native input reads in the selected environment before relying on them.

## Use the approved consumption policy

An approved balance-only session keeps the cumulative dollar cap and one active
writer. Historical time, token, turn and repair counters do not impose execution
stops in that mode. Normal membership observations are advisory; an artificial
missing-member fixture is not part of ordinary practice. Other configurations
retain their explicit limits.

Independent review, exact-candidate evidence and confirmed delivery still apply.
An uncertain board write retains its claim: read the full item, locate the exact
BAND task and use `factory_reconcile_task {id, task_id}` when matching evidence
exists. It never resends a mutation. Do not create a replacement to bypass an
unknown outcome or reset accounting to continue.
