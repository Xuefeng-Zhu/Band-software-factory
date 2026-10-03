# One-use rehearsal connectivity recovery

This command is an explicit exception to an already expired rehearsal stage timer. It is not ordinary continuation and must be authorized by the human after reviewing its exact scope. Creating an allowance does not start seats, remove a participant, or send a message. The implementation does not interpret an earlier “continue” as approval of the exception.

The exception lasts at most 600 seconds **from allowance creation**, including policy probes, connection startup, queued events and active turns. It applies only to the configured rehearsal room and its existing PM and Architect identities. The original subscription ledger, eight-hour origin, 100-million reported-token ceiling, per-seat turn limits and one-active-seat limit remain authoritative. Actual recovery turns/tokens accumulate in that same ledger. The old rehearsal stage-stop reason and both time origins remain unchanged. Ordinary `start-seats` still rejects the expired room; judged recovery is prohibited. A token, overall-time, turn, ownership or other failure cannot be overridden by this exception.

After explicit approval, the operator can create the reviewable manifest:

```sh
scripts/factory authorize-recovery \
  --operator-id 7f9319c7-ef4f-4c9b-88aa-97e1edb15c60 \
  --approval-reference '<exact human approval message or evidence reference>' \
  --duration-seconds 600 \
  --confirm-stage-limit-exception
```

The printed manifest has a random allowance ID, exact room and seat UUIDs, human UUID, approval reference, creation/expiry epoch, duration, canonical configuration hash, ledger snapshot hash, original time origins, preserved stop reason, fixed connectivity scope and a unique `FACTORY-RECOVERY-<id>` marker. It is written mode 0600 inside an owned mode-0700 `runs/runtime/recovery` directory. The ledger hash excludes only the cosmetic `updated_at` field. Configuration or accounting drift invalidates the unused allowance.

Review that manifest, then use its ID once:

```sh
scripts/factory start-recovery --allowance '<32-character allowance id>'
scripts/factory seat-status
# Stop early immediately after the observed outcome:
scripts/factory stop-seats
```

Start consumes an exclusive mode-0600 claim before spawning. The claim binds the allowance file digest to the owned supervisor token. A failed startup also consumes it; there is no retry/reset command. The unchanged manifest, claim, execution events, room history and cumulative ledger are retained. A new exception would require new human approval and a new manifest within the original global limits.

The operator separately obtains explicit human authorization for temporarily removing the exact Architect identity from the exact rehearsal room, using the supported BAND UI or maintained SDK participant endpoint. If the drill fails, restore that same identity and member role as cleanup under the same authorization; record the failure rather than claiming success. The runtime cannot remove participants. Use the prepared connectivity-only message, replacing its marker and expiry with the issued manifest values; do not send the earlier committed-blob drill. The observable sequence is:

1. Human sends the marked packet directed to PM after the separately authorized temporary absence.
2. PM lists participants, confirms Architect absent and restores exactly its frozen UUID with member role once.
3. PM re-lists participants, then directs a marked connectivity request to Architect.
4. Architect sends a real marked acknowledgement to PM. PM records the observed receipt/outcome and uses `no_reply` when finished.

No product implementation, shell command, file read, test run, commit, or stage continuation is assigned. Completion is an observed absence→restoration→re-list→Architect acknowledgement→PM outcome, not merely successful command startup. Preserve the actual event IDs and timestamps; missing evidence remains blocked.

Only fresh, in-window marked text from the exact human UUID (sender type `User`) or the two frozen agent UUIDs (type `Agent`) enters preprocessing or turn reservation. Duplicate event IDs are durably ignored. Outgoing mentions resolve directly to those UUIDs. Model-facing BAND tools are restricted to send-message, get-participants, add-participant and no-reply at both schema and execution boundaries. Only PM can attempt the exact Architect restoration; its attempt is persisted before the generated SDK endpoint is called with zero automatic retries and a timeout bounded by the remaining window. An ambiguous result cannot trigger another restoration attempt. Trusted adapter task/tool/usage telemetry remains enabled; thoughts remain suppressed.

Recovery uses the maintained SDK's history-converter seam to start new Codex threads, leaving old sessions and room history intact. Memory use/generation remain disabled. Each recovery workspace undergoes bounded, non-inference `config/read` checks; every inherited MCP server is explicitly disabled and the final effective configuration must show zero enabled servers. Shell, multi-agent, apps, plugins and web search are disabled. Recovery drops the development permission profile and Docker environment; read-only sandbox policy is applied to thread creation and every turn, with approvals declined. The app-server still needs its existing account/network connection, but commands receive the read-only/no-network sandbox. No credentials are moved and `CODEX_HOME` is unchanged.

Offline tests cover authority, replay, accounting, expiry, real SDK dispatch, exact UUID routing, fresh-thread behavior and configuration restrictions. A real non-inference proof at `runs/recovery-permissions-probe-20261003T222117Z-6db9aaa320/result.json` additionally verified the actual PM/Architect configurations, reading the assigned checkout, denied scratch writes and denied network with EPERM; the real budget and global Codex configuration stayed byte-identical. This proof does not authorize or execute the recovery.

The factory configuration and source/task hashes stay unchanged by this operational allowance. The implementation changes factory file hashes, so the final launch freeze must be regenerated against the reviewed code and real recovery outcome. Do not claim readiness solely from these tests or the restriction probe.

## First bounded attempt and schema correction

The approved allowance `d9bfcea7e1ca1480da210a6728679272` was consumed on October 3 at 22:36 UTC and stopped early after PM reported a tool-contract conflict. The SDK add-participant schema still demanded an unavailable peer lookup; the recovery guard itself already used the exact frozen UUID. An earlier operator-handle error had been resolved with exact-ID messaging. PM made no restoration attempt. The operator restored the same member as approved cleanup and retained both failures.

Recovery now deep-copies and supplies descriptions for all four permitted tools, including the nested parameter descriptions. The add schema accepts only the frozen Architect UUID and member role, with no peer search prerequisite. Send-message advertises the three exact allowed UUIDs. Actual SDK-to-Codex schema tests verify these contracts and that ordinary SDK schemas remain unchanged. The SDK base instructions contained the same unavailable prerequisite, so recovery alone supplies a specific communication/security instruction section; normal-mode base instructions remain enabled. Actual PM/Architect assembled prompts and dynamic tools are verified offline. All 128 utility tests pass. Execution guards and original limits are unchanged. The consumed allowance stays closed; creating a replacement window requires explicit approval.
