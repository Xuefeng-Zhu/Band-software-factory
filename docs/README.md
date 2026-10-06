# Factory documentation

Use [factory reliability](factory-reliability.md) for the runtime changes and `factory-status` command. Dated run records preserve historical observations; read saved runtime state separately for a current status report.

Start with the [repository overview](../README.md) and [operator guide](operator-guide.md). See the [Run 8 launch record](run8-launch-proof.md) for the dated dispatch and transport rehearsal evidence. Preparation snapshots describe the approvals and evidence available at their own dates.

## Operating the factory

| Guide | Contents |
| --- | --- |
| [Operator guide](operator-guide.md) | Dependencies, configuration, identities, rehearsal, launch and packaging |
| [Faster workflow](faster-workflow.md) | Stage-scoped packets, compact task reads, source-backed handoffs and the effective spending policy |
| [Switch harness and model](runtime-selection.md) | Codex, Claude Code and OpenCode selection, model discovery, permissions and retained evidence |
| [Environment](environment.md) | Execution permissions and isolated checks |
| [BAND/Codex integration](integration.md) | Pinned SDK, adapter behavior and registration |
| [Shared task board](task-board.md) | Work-item ownership, reviewer gates, durable synchronization and reconciliation |
| [Native BAND CLI](native-band-cli.md) | Desktop integration boundary and native worker handling |
| [Budgets](budget-policy.md) | Cumulative accounting and bounded execution |
| [Docker resources](docker-resources.md) | Capacity preflight and the recorded VM cap |
| [Recovery](recovery.md) | Bounded handoff and receipt recovery |
| [Rehearsal finish loop](rehearsal-finish-loop.md) | Full-session export and offline toy packaging |
| [Branch workflow](attempt-branches.md) | Independent application checkouts and one branch per attempt |
| [Rules review](rules-review.md) | Pinned requirements and submission evidence |

## Attempts and outcomes

| Record | Recorded outcome |
| --- | --- |
| [Run 3](run3-outcome.md) | Independent Stage 1 acceptance; Stage 2 planning only |
| [Run 4](run4-outcome.md) / [preparation](run-4-preparation.md) | Closed after independent rejection; no accepted stage |
| [Run 5](run-5-preparation.md) | Closed after independent rejection; private package retained |
| [Run 6 launch](run-6-preparation.md) | One verified initial dispatch; historical launch snapshot |
| [Run 6 continuation](run-6-continuation.md) | Token-ceiling stop; operator checks passed, independent acceptance pending |
| [Run 6 verification evidence](../evidence/run6-sol-repair-verification-20261005/README.md) | Exact repaired candidate, checks and stop accounting |
| [Run 7](run-7-preparation.md) / [handoff diagnosis](run7-handoff-diagnosis.md) | Historical launch and stopped handoff incident |
| [Run 8 preparation](run8-preparation.md) / [launch proof](run8-launch-proof.md) | Initial rehearsal failure, envelope repair and later verified dispatch; dated observations |

[`config/attempts.json`](../config/attempts.json) retains operator registry checkpoints. Its Run 6 entry predates launch; it is not current runtime state or authorization. Use the dated launch, continuation and verification records above for later events.

## Historical preparation and repairs

- [Factory history and original roster](factory-history.md)
- [Build-start checkpoints](BUILD-START.md) and [initial readiness snapshot](READINESS.md)
- [Run 3 queue diagnosis](run3-queue-repair.md)
- [Queue repair rehearsal plan](queue-repair-rehearsal-plan.md) and [live result](queue-repair-live-result.md)
- [Workflow timeout repair](workflow-timeout-repair.md)

[`sources/`](sources/) contains the pinned reference copies. [`../evidence/`](../evidence/) preserves raw records and failures. Their hashes and original paths are part of the audit trail; retain them when reorganizing documentation.
