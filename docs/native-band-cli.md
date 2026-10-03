# BAND Desktop 0.4.12: registration path and runtime boundary

Read-only inspection of `/Applications/Band.app/Contents/MacOS/band` command help
and the bundled `Contents/Resources/user-guide.md` confirms that Desktop can create
persistent identities with **parked** native Codex runtime templates. This adds a
supported identity-creation path; the factory's execution runtime remains the
pinned Python SDK adapter.

The current selected runtime is project-local Codex CLI **0.160.0** and the
explicit model is **gpt-6-astra**, selected as the current flagship through OpenAI's
[latest-model guidance](https://developers.openai.com/api/docs/guides/latest-model). Existing medium/high role efforts remain
unchanged. Fresh SDK discovery confirms Astra is available; the catalog default is
gpt-6.1-sol. This selection does not imply a working native runtime, a completed
model turn or new permissions. All seven parked default templates were updated through supported native configuration
to the project-local 0.160.0 executable. Model-settings reads confirmed gpt-6-astra
for each default and both existing rooms (21 settings), preserving the role efforts.
All workers remained stopped with host PID 0. No `--apply-and-restart`, wake or model
turn occurred. Evidence: `runs/model-upgrade/native-template-summary.json` and
`band-{seat}.json`. Dormant cached thread metadata may still display the initial
gpt-5.5; use the documented runtime-settings reads for the persisted selection.
The SDK runner uses its own explicit current model configuration.

Useful supported CLI surfaces:

- `band agent create`: persistent agent identity and parked template;
  `--name`, `--description`, `--session`, `--cwd`, `--transport codex-app-server`,
  `--spawn-command`, repeatable `--spawn-arg`, `--runtime-auth subscription`,
  `--runtime-model`, `--runtime-effort`, `--runtime-approval never`,
  `--runtime-sandbox workspace-write`, `--codex-channel stdio`,
  `--runtime-web-search false`, owner instructions and structured `--json` output.
- `band agent instructions show` reports metadata; `--reveal` is an explicit
  additional request for stored text/path. `set --instructions-stdin` stores
  copied instructions; `set --instructions-file` uses a live-linked file.
- `band runtime template show` reads the parked template. `template set` preserves
  omitted settings; `--apply-and-restart` is a separate mutating option.
- `band runtime settings` without setting flags reads per-thread configuration;
  `configuration` and `policy` show desired/effective settings and isolation.
- `band runtime models` queries a **live** native runtime. The factory's existing
  `discover-models` command instead starts only a temporary local app server and
  calls initialize/model-list without a model turn.
- `band runtime room-activity tools` selects tool telemetry without the `full`
  reasoning level. Native owned runtimes default to **full**, so accepting the
  native default would not meet this factory's no-thoughts policy.
- `band runtime sandbox-support` checks Docker Sandboxes availability without
  creating a sandbox. Managed isolation and network readiness have separate
  read-only commands. They are not evidence of a working development environment
  until actually run and validated for the exact runtime.

The public CLI help has no supported agent-key export command. `band adopt
--agent-key` is the opposite direction: it imports a pre-existing agent key
(`band_a_...`) such as one generated through the official UI. No keychain,
encrypted database, environment, or private daemon-state extraction was attempted.
Agent creation returning a real handle/UUID does not by itself give the Python SDK
the credential pair required by `Agent.create(agent_id=..., api_key=...)`.

For CLI-created identities, obtain keys only through the supported agent dashboard
flow and put them directly into the owner-only private credential file. Stop the
native peer/runtime before starting the same identity in the SDK; simultaneous
receivers could compete for messages. Do not restart or invite parked native
runtimes as a workaround for the factory's budget and permission gates.

A native runtime is also an official integration, but inspected public settings
are not equivalent to this factory's tested restrictions. The inspected help does
not expose shared concurrency leases, per-seat finite turn limits, a persistent
aggregate token threshold, a whole-session deadline, an allowlist for every
incoming room, or the factory's slash-command and exact PM membership guards.
Changing the factory to native execution would therefore require a separate,
evidence-backed implementation and rehearsal, not only different launch flags.

Creating parked identities is registration preparation. It does not prove a
connected seat, a directed response, SDK authentication, shared checkout visibility,
Git/browser/Docker/development-network permissions, or a complete toy rehearsal.
The initial inspection was read-only. Subsequent preparation created seven persistent identities and two rooms, saved generic mandates, selected tools-only telemetry, verified native room membership and stopped only the factory peer workers. See `runs/preparation/band-roster.json` and `band-*-participants.json`. No task message or model turn was started; no SDK key was returned. Earlier native initialize probes with CLI 0.133.0 failed and their logs are retained under `runs/preparation/`; they do not establish the behavior of 0.160.0. Fresh no-turn SDK model discovery is recorded at `runs/model-upgrade/models-0.160.0.json`. Native runtime execution and required permissions for the new CLI remain unverified.
