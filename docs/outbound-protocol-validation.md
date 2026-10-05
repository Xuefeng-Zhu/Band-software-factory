# Validate protocol text before posting

Run 7 stopped during its architecture re-review because the Reviewer sent a canonical receipt followed by an explanatory sentence on the same line. The strict receipt parser rejected that text. The factory had already posted the message before applying that parser, so the incident became blocked and the admitted turn was interrupted.

The selected public event is retained in [run7-stop-event.json](run7-stop-event.json). It was posted at `2026-10-05T08:18:49.733838Z`; its content SHA-256 is `2d0597924bd1f5cde19fa4face3a52d46fdd067c100237d4440b53e48c1d79d6`. The rejection occurred at `08:18:49.850987Z` and the turn ended at `08:18:54.873948Z`, before its `08:27:54Z` deadline. This was a protocol-validation failure, not an exhausted budget or turn timeout.

`WorkflowTools.send_message` now previews protocol input before the network call and before entering the uncertain-send handler. The preview uses the same strict validation as confirmed outbound observation. It checks canonical receipt syntax, completed delivery identity, multipart syntax, recipient binding and conflicting existing fragments. It creates no event, incident, ACK, notice, or execution claim, and does not modify retained workflow state.

Invalid local input returns a structured tool error through the maintained SDK. The admitted agent may correct it within the existing time and token limits. A corrected receipt is still sent by that agent and recorded only after a confirmed response. The factory does not synthesize receipts, loosen the parser, or resend automatically. Failures after an actual send attempt retain the existing stop-and-preserve behavior because delivery may be uncertain.

Four new regression tests cover the observed extra-prose ACK, a corrected ACK in the same turn, malformed multipart numbering/final markers, mismatched recipients, conflicting retained payload/digest/count, and unchanged blocking after a real posted conflict. The full offline utility suite passes 416 tests. An [independent review](outbound-validation-independent-review.json) reran all 62 workflow tests with no findings. These tests use mocked transport and do not establish live BAND or provider operation.

## Run 7 and activation

The product team pushed architecture repair `c1da398ef05700ae6e3846a9249d2ff2032648b7` before the stop. Its independent re-review did not finish. No product stage is accepted (0/4), and this infrastructure patch does not establish product correctness.

Neither this fix nor the multipart batcher was applied to Run 7. The original dispatch, frozen source, blocked incident and accounting remain intact. Restarting the old run unchanged would retain the blockage; replacing its frozen code or clearing the incident is not a recovery procedure. Activation requires a new reviewed freeze and fresh rehearsal. Any future judged attempt must preserve the previous attempt and obtain its own launch authorization.

A [read-only integrity check](source-task-integrity-after-fix.json) verified all six original task packets. One locked `config.toml` reference has changed since the original source lock; that drift must be reconciled in preparation for a new freeze. No existing source lock was overwritten or treated as current launch approval.
