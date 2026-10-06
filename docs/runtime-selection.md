# Switch the agent harness and model

The factory supports **Codex**, **Claude Code** and **OpenCode** through their maintained BAND adapters. A selection applies one harness to all seven seats, with a default model and optional per-role model overrides. Each selection creates a new preparation directory; it does not edit the original configuration, connect seats or send a task.

These commands run from `/Users/frank/mygit/Tablekeeper/factory`. Adjust the example configuration's absolute paths on another machine. Put the global `--config` option **before** the subcommand. Both `scripts/factory` and `scripts/runtime` accept the selection and discovery commands below.

## Restore dependencies and inspect the choices

Restore the factory's locked Python dependencies, including all three BAND adapter extras:

```sh
uv sync --frozen
scripts/factory --config config/factory.example.yaml runtime-options
scripts/factory --config config/factory.example.yaml runtime-show
```

For the complete local setup, `python3 scripts/bootstrap.py --install-browser` also restores the pinned project-local Codex CLI, official acceptance-harness environment and browser. It does not install or log in to Claude Code or OpenCode. Install those CLIs separately when needed; `runtime-options` reports configured or PATH-discovered command locations. Use `--command` to choose a specific absolute executable path.

`runtime-show` lists the selected harness, executable, default model and each seat's model and effort. `runtime-options` lists supported harnesses and command locations; it does not claim a model is available or authenticated. The existing `harness` subcommand still runs the organizer's application acceptance checks.

## Prepare a selection

Start from `config/factory.example.yaml` for a fresh preparation template, or supply an existing **stopped** configuration to retain its roster, room scope and accounting. Each `--output` must be a new absolute directory. The names below are examples; choose another name if one already exists.

Codex uses the project-local executable from the source configuration:

```sh
scripts/factory --config config/factory.example.yaml runtime-select \
  --harness codex \
  --model gpt-6.1-sol \
  --output /Users/frank/mygit/Tablekeeper/runs/profiles/codex-sol
```

The Codex model above matches the example configuration. Verify availability with discovery before launching. To change the model again, use the generated `factory.yaml` as the next `--config` and choose a new output directory.

For Claude Code, set `FACTORY_CLAUDE_MODEL` to the model ID you intend to use. The shell expression fails with an instruction when it is unset, avoiding an invented model selection. Omit `--command` to use a CLI found on PATH:

```sh
scripts/factory --config config/factory.example.yaml runtime-select \
  --harness claude-code \
  --model "${FACTORY_CLAUDE_MODEL:?Set FACTORY_CLAUDE_MODEL to your Claude model ID}" \
  --reasoning-effort high \
  --output /Users/frank/mygit/Tablekeeper/runs/profiles/claude
```

For OpenCode, set `FACTORY_OPENCODE_MODEL` to a complete `provider/model` identifier. Add `--variant` only for a variant advertised by that model:

```sh
scripts/factory --config config/factory.example.yaml runtime-select \
  --harness opencode \
  --model "${FACTORY_OPENCODE_MODEL:?Set FACTORY_OPENCODE_MODEL to provider/model}" \
  --output /Users/frank/mygit/Tablekeeper/runs/profiles/opencode
```

An explicit CLI path can be added to any selection, for example `--command /absolute/path/to/claude`. Selection may prepare a profile before that executable is installed; discovery and readiness require the real selected installation.

### Choose models by role

`--model` sets the default for every seat. Repeat `--seat-model ROLE=MODEL` for roles that need a different model. Use the configured seat IDs: `pm`, `architect`, `designer`, `backend`, `frontend`, `qa`, and `reviewer`. Unknown roles, duplicate overrides and malformed identifiers are rejected before a profile is created. Omitting all overrides keeps the original all-seat selection behavior; previous per-role models are not implicitly retained.

This selection assigns GLM-5.3 to PM, Architect, Backend and Reviewer, and GLM-5.3-Flash to Designer, Frontend and QA:

```sh
scripts/factory --config config/factory.example.yaml runtime-select \
  --harness opencode \
  --model featherless/zai-org/GLM-5.3 \
  --seat-model designer=featherless/zai-org/GLM-5.3-Flash \
  --seat-model frontend=featherless/zai-org/GLM-5.3-Flash \
  --seat-model qa=featherless/zai-org/GLM-5.3-Flash \
  --output /Users/frank/mygit/Tablekeeper/runs/profiles/opencode-mixed
```

The selected YAML stores an explicit model for every seat. Each copied mandate, packet roster and selection receipt records those same choices. All seats retain one harness. Discovery must advertise every selected model under that harness and connect its provider; model selection does not establish account eligibility or billing permission. OpenCode's owned server uses the seat's selected model for both its main and small-model setting.

Effort controls follow the selected harness:

| Harness | Optional selection argument | When omitted |
| --- | --- | --- |
| Codex | `--reasoning-effort LEVEL` | Preserves each role's existing effort for a Codex-to-Codex switch; defaults all roles to `medium` when switching back from another harness |
| Claude Code | `--reasoning-effort LEVEL` | Maps to Claude's effort setting; preserves existing Claude role efforts, otherwise leaves effort unset |
| OpenCode | `--variant NAME` | Maps to the provider model's variant; preserves existing OpenCode role variants, otherwise leaves it unset |

Supplying an effort or variant sets it for every seat, including model overrides, and every selected model must advertise that value. Without an explicit effort, a `--seat-model` override that changes the role's model resets its effort to `medium` for Codex or leaves it unset for Claude Code/OpenCode. Other same-harness selections preserve existing role efforts; discovery and preflight validate them against each selected model. `--variant` is rejected for Codex/Claude, and OpenCode rejects `--reasoning-effort`. The GLM example leaves variants unset.

## Discover and verify the selected model

Always use the generated configuration for subsequent commands:

```sh
scripts/factory --config /Users/frank/mygit/Tablekeeper/runs/profiles/claude/factory.yaml runtime-show
scripts/factory --config /Users/frank/mygit/Tablekeeper/runs/profiles/claude/factory.yaml discover-models
scripts/factory --config /Users/frank/mygit/Tablekeeper/runs/profiles/claude/factory.yaml validate
scripts/factory --config /Users/frank/mygit/Tablekeeper/runs/profiles/claude/factory.yaml verify-tasks
```

Substitute the Codex or OpenCode output directory to inspect those selections. Discovery reads the selected harness's model catalog and stores it under that profile's `runtime/models.json`. Codex uses app-server initialization and `model/list`; Claude uses SDK initialization; OpenCode starts and stops an owned local catalog server. No prompt or model turn is sent by discovery. Authentication, an installed compatible CLI and its catalog are still required.

If the catalog uses a different model ID, select again into another new directory with that exact ID. No catalog, registration or permission proof is inherited from an earlier configuration. `validate` may report structural PASS while still listing launch blockers; `validate --ready` fails until those blockers are resolved. A selection does not repair or rehash a changed locked reference document.

To switch back, choose the prior prepared profile as the source and another new directory:

```sh
scripts/factory --config /Users/frank/mygit/Tablekeeper/runs/profiles/claude/factory.yaml runtime-select \
  --harness codex \
  --model gpt-6.1-sol \
  --output /Users/frank/mygit/Tablekeeper/runs/profiles/back-to-codex
```

The source retains its original Codex command path for this return. Pass `--command` if the intended installation differs.

## Check an OpenCode upgrade without inference

Before adopting a new executable, run the protocol probe with the approved version and the SHA-256 of the extracted executable (not the downloaded archive):

```sh
.venv/bin/python scripts/probe-opencode.py \
  --command /absolute/path/to/pinned/opencode \
  --version 1.18.34 \
  --sha256 "$APPROVED_OPENCODE_EXECUTABLE_SHA256" \
  --output /absolute/existing/evidence-directory/opencode-protocol.json
```

The output path must be new. The probe starts an owned loopback server with a synthetic provider, synthetic credentials and temporary private state. It checks effective routing, binary/server identity, authenticated BAND transport, an empty session's create/read/abort/delete cycle and live session SSE. It also validates the installed BAND SDK's request serialization and seven typed event fixtures against the server's `/doc` schema. Prompt, permission, question and MCP request fixtures stay inside a mock transport; a live request allowlist forbids prompt and shell endpoints. The server and temporary state are removed afterward.

The report distinguishes live protocol checks from schema/fixture checks. A PASS does not establish provider authentication, inference, tool execution or billing. Preserve the prior executable until the candidate passes both this probe and the separately authorized provider checks. When selecting another profile, an existing `opencode_state_root` is rebound under its new `runtime/opencode` directory; executable and provider pins remain unchanged.

## What the preparation contains

| Path in the new output | Contents |
| --- | --- |
| `factory.yaml` | Selected runtime, unchanged product/rehearsal paths, retained room scope, and cleared readiness/budget approval |
| `mandates/` | Seven copied role mandates with only anchored `Harness:` and `Model:` metadata rewritten |
| `tasks/` | Six regenerated packets and a manifest bound to the new configuration and exact source payloads |
| `source-lock.json` | Byte-for-byte copy of the selected source lock |
| `selection.json` | Default model, complete seat/model map, source/configuration hashes and inherited-file provenance; records that no inference or dispatch occurred |
| `runtime/budget-*.json`, `launch/` | Existing consumption and dispatch records, when present, copied without clearing counters, clocks or stops |
| `inherited-runtime/` | Retained receipt and workflow history for inspection; earlier inherited receipts remain under `previous/` on another switch |

Publication is atomic and refuses an existing output directory. Source configuration, mandates, lock and control records are checked again before publication. A live owned supervisor or child process prevents the snapshot. Original evidence remains at its original paths. Supervisor ownership, old model catalogs, registration proofs and ready freezes are not installed as current proof for the new selection.

A configured Featherless request guard has an additional boundary: only a proven-unused, unowned ledger can be copied. Its exact ledger bytes, pinned model metadata and metadata hash are carried into the new profile, and approvals are cleared. Any prior request, pending reservation, unknown usage, started clock or stop blocks selection. A used guard requires separately reviewed transfer and reconciliation; `runtime-select` cannot fork or renew the remaining prepaid allowance. Missing or malformed guard accounting also blocks selection, and the originals remain untouched.

## Permissions, billing and launch

Codex retains its explicit Codex permission configuration for a same-harness selection. Switching back from another harness starts with `workspace-write`, `approval_policy: never` and `approval_mode: auto_decline`.

Claude Code and OpenCode start with `sandbox: native-policy` and this conservative native-tool policy:

```yaml
native_permissions:
  read: true
  write: false
  bash: false
  network: false
```

Review these four values in the new configuration before obtaining fresh permission evidence. Direct file-tool access is constrained by the adapter's workspace policy. Enabling `bash` grants trust to shell commands on the host; it is not an operating-system sandbox. The `network` toggle controls supported built-in web tools, not every possible network request from an enabled shell. BAND communication has its own transport. Codex sandbox settings and socket grants do not transfer to the other harnesses.

All selections set `budgets.approved: false` and clear launch and seat registration verification. Finite counters, deadlines, room scope and existing stops remain intact. Authentication and billing requirements differ:

| Harness | Billing gate |
| --- | --- |
| Codex | `subscription_only` requires verified ChatGPT authentication and rejects API/provider overrides; otherwise use an explicitly approved provider-enforced spend cap |
| Claude Code | `subscription_only` requires the selected CLI's verified `claude.ai` OAuth login and subscription type, with API/provider environment overrides absent; other billing requires an approved spend cap |
| OpenCode | `subscription_only` is blocked because the factory cannot verify it; use `billing_mode: spend_cap` with a positive `spend_cap_usd` and actual provider-side enforcement, then explicitly approve the finite budget |

The configured spend cap is a readiness requirement, not a provider billing control installed by this command. Keep credentials in the provider's supported login storage and the existing external BAND credential file; never add keys to the selected YAML or mandates.

Token totals reflect observed adapter usage. Interrupted turns can leave incomplete totals: the SDK may omit usage during cancellation or discard a Claude timeout result. If a Claude Code or OpenCode turn finishes without valid usage being recorded, the factory retains its existing counters, marks the accounting incomplete, and persistently blocks further turns until consumption is reconciled. It never fills that gap with an estimated or zero-token result; late usage is retained without clearing the stop.

Follow the [operator guide](operator-guide.md) for current registration, permission evidence, rehearsal, freeze and separately authorized dispatch. After editing a selected configuration, regenerate its task packets and rebuild matching evidence. A profile inherited from a consumed room cannot launch against that room; a genuinely fresh attempt requires explicit room and accounting reconciliation.

**Runtime selection does not migrate a frozen continuation in place.** Existing Codex recovery and same-room continuation preserve their original bindings and remain Codex-specific. Switching harness or model does not reopen a stopped attempt, clear a budget, create a room, reset receipt history or grant another dispatch.
