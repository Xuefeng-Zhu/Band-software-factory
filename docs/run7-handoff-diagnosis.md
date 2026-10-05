# Run7 handoff bottleneck: observed diagnosis

Snapshot read: **2026-10-05T07:59:27.782192+00:00** through **2026-10-05T07:59:27.783131+00:00**. This is a read-only observation, not a model run, product test, repair, or acceptance.

The current factory admits each addressed multipart fragment as a full model turn. In this exact snapshot, **169 admissions** include **110 multipart-fragment triggers**, of which **97 are nonfinal fragments**. There are also **12 canonical receipt triggers** and **47 other public-event triggers.** The last category is not classified as wasted work. Counts concern admissions, not completion, distinct tasks, token costs, or product acceptance. A first complete handoff still requires work after transport arrives.

The safe selected-metadata snapshot is `run7-handoff-snapshot.json`. Its original workflow source is `/Users/frank/mygit/Tablekeeper/runs/run7-preparation-20261005/runtime/workflow-7f255b86-3e14-44ab-a9cb-7cacdacf4515.json` with SHA-256 `cbe76a8c7f0abd8f70a2ff7d32beff542f04a4df392254c8d7b8ba025621831a`. The live file can change after this observation. An earlier unsaved read counted 155 admissions (99 multipart, 87 nonfinal, 11 ACK, 45 other); its exact wall-clock timestamp was not retained, so the new bound snapshot is authoritative.

## Source-backed cause

Reviewed frozen sources were reconstructed read-only from factory Git revision `22eb40f` and each hash matched the Run7 freeze. This avoids treating concurrent changes in the shared factory checkout as launched code.

- Frozen `factorykit/runtime.py:563–574`: `RoomPreprocessor.process` passes every in-room non-slash message to the SDK `DefaultPreprocessor`; there is no deterministic multipart completeness gate.
- Frozen `factorykit/runtime.py:1218–1265`: `GuardedCodexAdapter.on_event` serializes ingress and calls `ledger.reserve_event` before the SDK model callback, including partial fragments.
- Frozen `protocols/collaboration.md:25–31`: complete applicable requirements are sent in numbered parts; recipients may not execute until the full count/digest/final marker is verified. The waiting rule currently lives in model instructions. Canonical ACK confirms transport only, not work acceptance.
- The observed assignments/results contain seven to twelve parts. Repeating complete applicable requirements is required; the defect is repeatedly waking models while the payload is incomplete.

These facts establish a transport/admission overhead. They do not prove all elapsed time or reported tokens were caused by fragmentation, nor that a batching fix would make the application correct.

## Agent-owned repair at the snapshot time

`ARCH-REPAIR-A1-001` has **11/11 parts**, complete=true, acknowledged=false; its first part was observed at **2026-10-05T07:56:16.297428+00:00**. This is a real PM-issued architecture repair handoff, not an operator instruction. The snapshot records the latest Architect admission and original part UUIDs. Receipt/work completion must not be inferred from send completeness alone.

Product HEAD is `73211923b9f940385036cebcf9d0bb4454d28314`. Stage-directory presence is `{"stage-1": false, "stage-2": false, "stage-3": false, "stage-4": false}`. Architecture/planning progress is not a product stage gate.

A later observation found the team had pushed architecture correction `c1da398ef05700ae6e3846a9249d2ff2032648b7`. Run 7 subsequently stopped during its re-review because an invalid receipt had been posted before validation. The separate [stop diagnosis and outbound fix](outbound-protocol-validation.md) supersede the live status above, while this earlier snapshot remains the evidence for fragment admission overhead.

## Smallest factory-only correction to review offline

Add a durable multipart ingress assembler before model admission. Persist exact original fragments under room/sender/recipient/delivery identity before allowing the SDK to mark a fragment handled. Release exactly one original trigger only when all numbered parts, exact canonical payload digest and terminal marker validate. Preserve original raw public evidence and sender identity; reject conflicting duplicates. Never use a summary, stale room history, operator product hints, fake ACK, or synthetic replacement task as the complete payload.

Keep the existing independent review, repair/time/token limits and canonical full-receipt semantics. Missing-part and checksum conflicts must remain visible and bounded. Test out-of-order arrival, duplicates, conflict, final-before-earlier, restart between persistence/admission, failed or uncertain model turn, wrong recipient/room/sender, UTF-8 boundaries, and SDK receipt ordering. A model-admission claim must survive a crash and prevent replay; a partial-fragment receipt must never imply work acceptance.

Build and verify this only in the isolated future factory worktree. Preserve Run7's original dispatch, source freeze, ledger and product history. Do not hotpatch its workers, replay its stage, or repair application code by hand. The pinned participant guide's autonomy rule (lines481–495) permits development iterations, but the submitted run receives only the original stage dispatch; no operator debugging hints or reruns until it passes.
