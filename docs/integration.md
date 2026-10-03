# Official BAND and Codex integration

This package pins **band-sdk 4.0.0** and project-local **Codex CLI 0.160.0**
for the stdio app server. The npm package and integrity lock live in
`tooling/codex/`; `scripts/codex-local` selects that local executable without
changing the user's global CLI or configuration.

All seven seats explicitly select **gpt-6-astra**, the current flagship identified
by OpenAI's [latest-model guidance](https://developers.openai.com/api/docs/guides/latest-model). Fresh authenticated
`initialize` + `model/list` confirmed Astra and support for the existing medium/high
role efforts; see `runs/model-upgrade/models-0.160.0.json`. No inference turn was
started. The same catalog lists gpt-6.1-sol as its default, so this is a deliberate
flagship selection rather than a newest-chronological-model or default claim.

Earlier CLI 0.133.0 discovery offered gpt-5.5 as its default and did not list Astra.
That observation and its initial configuration workaround remain historical evidence.
The app's displayed model is not substituted for the fresh CLI catalog, and model
availability is not a proof of live BAND execution or tool permissions. The native parked templates also persist the new local executable and model without restart; supported settings reads verified the default and both rooms for every seat. The SDK selects the current model explicitly from its configuration.

```sh
./scripts/factory discover-models
./scripts/factory probe-registration --mode rehearsal
./scripts/factory start-seats --mode rehearsal
./scripts/factory seat-status
./scripts/factory stop-seats
```

The equivalent standalone entrypoint is `scripts/runtime`. Supply global
`--config /absolute/config.yaml` before the command to use a relocated workspace.
No command here dispatches the judged task. Never interpret `start-seats` as a
successful collaboration rehearsal: it reports connected identities, and actual
addressed replies, handoffs, fixed-candidate reviews and isolated checks still need
observed evidence.

## Supported extension points and a documentation discrepancy

The official Codex tutorial advertises `CodexAdapterConfig.cwd`. The installed,
pinned 4.0.0 implementation rejects that field in `CodexAdapter.__init__`, rejects
WebSocket transport, and rejects a custom `client_factory`. The integration uses
the supported `workspace_for_room` callable, which resolves an absolute checkout
only for the configured allowlisted room. The installed source is authoritative
for the package actually run. No patching of SDK internals is used.

`Agent.create(preprocessor=...)` rejects other rooms and slash commands before
history hydration and adapter handling. Blocking all slash commands closes
`/model`, `/reasoning`, `/sandbox`, `/approve-session`, and thread mutation paths;
`enable_self_config_tools=False` closes the separate model-callable configuration
path. Constructor values explicitly override all `CODEX_*` environment settings.
The public `CodexAdapter.on_event` extension serializes turns under a shared
semaphore and wraps `AgentInput.tools` for budgeting and event auditing. Generic
protocols, the role mandate, verified roster, and finite limits form
`custom_section`. Product tasks and preparation `AGENTS.md` are not injected.

All seven seats initially share the actual checkout. Configuration permits one
active turn in that state: this is an enforced single-writer fallback. A later
team-created worktree must be outside result directories, configured explicitly
as a seat's `rehearsal_cwd`/`judged_cwd`, and based on a real team-authored commit.
At most two turns may run with distinct assigned checkout paths. The runner never
creates commits, worktrees, or result implementation during setup.

## Registration without fabricated identities

Seven actual owned identities and both rooms already exist. Obtain SDK keys for
those identities through a supported BAND dashboard flow. If that flow is unavailable,
use the official Remote Agent flow as an explicit roster and room-membership replacement,
then regenerate tasks and verification; never silently substitute identities. Place
each verified UUID and key in the owner-only credentials file outside repositories, using the
seat ids `pm`, `architect`, `designer`, `backend`, `frontend`, `qa`, `reviewer` as
YAML keys. Each key maps to `agent_id` and `api_key`. Set actual room UUIDs in the
configuration; rehearsal and judged rooms must differ.

`probe-registration` uses the documented `Agent.start()`/`agent.agent_name` path
with a silent adapter and all message processing rejected. It disables existing
room auto-subscription and working-state events, performs no model calls, and
sends no room messages. Official REST identity and participant reads supply the
actual id, handle and membership. It does not create or register agents. Copy the
observed ids/handles into configuration, verify names, set the per-seat
registration flag, then rerun the probe. Its proof is bound to the complete
configuration hash. A missing key or mismatch fails closed. SDK log output is
suppressed in live workers; exceptions are reported without raw response headers,
authentication content, or credential values.

Only PM can restore a missing **exact configured** identity using the official
`band_add_participant`. Existing membership is read first, retries are bounded to
two (or the lower repair limit), and arbitrary identities, privilege changes,
participant removal and room creation are unavailable. All other seats lack the
add-participant tool. Room discussion and directed receipt evidence remain BAND
operations, not a parallel messaging service.

## Events, continuity, budgets and shutdown

The adapter enables `Emit.TOOL_CALLS`, `Emit.TASK_EVENTS`, and `Emit.USAGE`. Task
metadata carries real Codex thread IDs for the SDK's history converter to resume
sessions. Turn lifecycle, token counts and diff events remain supported; thoughts,
reasoning summaries, reasoning streams and thought event calls are suppressed.
Local audit JSONL retains only selected execution identifiers/counters. It does
not copy message content or arbitrary tool metadata. The authoritative room still
contains ordinary supported tool events; agents must not print secrets there.

The persistent local ledger counts every admitted turn per seat and cumulative
reported token deltas per seat/thread; duplicate lifecycle reports do not double
count. It survives restarts. Token enforcement is based on observed provider
notifications, so an in-flight turn can exceed the threshold before cancellation.
It is **not a provider-side hard dollar cap**. Monetary spend remains UNAVAILABLE
unless independently reported; `spend_cap_usd` records explicit approved authority,
and does not manufacture cost accounting. The optional [subscription-only policy](budget-policy.md)
uses verified existing ChatGPT authentication and a shared rehearsal/judged
ledger without a dollar-cap claim. It remains unapproved. The constrained
authentication probe passed without inference; see
`runs/build-start/subscription-auth-probe.json`. No inference starts until budgets are approved
and finite and all other launch prerequisites pass.

The SDK turn timeout and an outer deadline bound work. A persistent whole-session
deadline conservatively applies `stage_timeout_seconds` across the supervisor
session, even in all-stages mode; it does not infer stage changes from prose and
does not reset on restart. The overall timer also persists. For a longer all-stage
session, an approved pre-dispatch configuration must account for this stricter
bound. Exhausted ledgers are not silently reset. Select a new run directory only
for a separately approved new run, then regenerate matching evidence and freeze.

`start-seats` validates registered room identity, available CLI models/reasoning,
actual hash-bound **agent** Git/write, browser, Docker and development-network
permission evidence, and approved budgets before spawning. A rehearsal start does
not require completed rehearsal evidence. A judged start additionally checks the
READY freeze, exact configuration, source and instruction hashes, generated tasks,
and pristine first-start result or a matching recorded dispatch for resumption.

The owned supervisor registry records PID, creation time, exact command line and a
random ownership token. Status and stop revalidate these to avoid PID-reuse errors.
Only descendants captured from the verified owner are candidates for cleanup;
there is no process-name kill. SIGTERM requests SDK cleanup, then identity-checked
remaining owned processes are terminated if needed. Shutdown preserves room
continuity and local ledger evidence. Unexpected process exits are never reported
as successful connections.

## Current observed boundary

The earlier CLI 0.133.0 host `workspace-write` sandbox passed file writes but blocked
Git index writes, development networking and loopback bind. Those failures remain
historical evidence; permissions with the changed 0.160.0 CLI are NOT_TESTED until
revalidated in the actual chosen environment. Host Chromium success
outside that sandbox does not prove agent browser permission. Seven BAND identities and both room memberships are now verified through the native CLI; their workers are stopped and templates detached. SDK credentials, SDK room access and approved consumption authority remain unavailable. The
runner therefore remains blocked for real seat startup. No host
`danger-full-access` or falsely labeled `external-sandbox` fallback is provided.
The adapter structure and 63 local utility/guard tests are verified
(`runs/build-start/verification-00.json`); the new CLI model
catalog is observed without an inference turn, while live BAND seat
collaboration, provider turns, isolated agent Git/browser/Docker behavior and a
complete toy rehearsal are not claimed.
