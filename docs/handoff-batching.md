# Multipart handoff admission

A long BAND handoff contains several numbered messages, but represents one assignment. Previously each fragment reached the coding adapter and consumed a model turn, even when the recipient could only wait for the remaining parts. With one active seat, these waiting turns also delayed useful work by other seats.

The factory now collects authenticated fragments through BAND's supported preprocessor before model admission. It binds their event IDs, sender, recipients and content hashes to confirmed outbound records; a bounded wait accommodates an inbound callback arriving before the sender receives its response. It retains original event identities and complete payload bytes in private run-owned state. Only a complete, consistent delivery can reach the adapter. Identical duplicates do not repeat the assignment. Conflicting fragments, invalid digests and ambiguous execution claims remain visible failures; they do not silently start a new attempt.

The wire format is exact: one header line, one newline, then the original payload slice. The final fragment adds one newline followed by `END OF HANDOFF`. Concatenate the slices without inserting or stripping whitespace. The SHA-256 describes those concatenated UTF-8 payload bytes. Transport headers and the final marker are excluded. Ordinary room messages and explicit human kickoff tasks retain their existing path.

The recipient must still send the canonical `HANDOFF-ACK` through BAND. A complete delivery or a receipt is not work acceptance. Existing budgets, ownership, deadlines, repair limits and independent review requirements still apply.

## Activation and evidence

This change belongs to a new factory freeze and a fresh rehearsal. It is not a hot patch for an active judged run. Existing approved continuations without batching journals retain their recorded event semantics. A continuation or recovery for a room that already has batching journals is rejected until a journal-aware reconciliation path is implemented. Do not overwrite a live run's source lock, ledger, task packet or admission state to enable it.

Local utility tests exercise transport and admission behavior without sending BAND messages or invoking a model. A passing local suite does not establish live SDK delivery, a successful rehearsal or product correctness. Keep private fragment journals outside committed evidence: they contain the complete handoff payloads.

Validation: **412 utility tests pass**, including 23 focused batching cases. A 12-part synthetic handoff reaches the adapter once; partial and duplicate fragments consume no model reservations. Restart, conflicting identities, routing authority, budget refusal, timeout and cancellation cases are covered. See the [test receipt](handoff-batching-validation.json) and [independent review](handoff-batching-independent-review.json).

A read-only comparison of 56 existing public handoff fragments found their bodies byte-identical to the existing outbound slices. The message-list response did not provide recipient IDs in `metadata.mentions`, so routing authority comes from the factory's confirmed send records. This comparison is transport compatibility evidence, not a live test of the new batcher. The maintained SDK's ordinary history hydration remains unchanged; a bootstrap may still contain prior fragments. Canonical ACK messages also retain their existing processing path.

See [the Run 7 diagnosis](run7-handoff-diagnosis.md) for the observed cost of the previous behavior. Product corrections remain owned by the dispatched agent team.
