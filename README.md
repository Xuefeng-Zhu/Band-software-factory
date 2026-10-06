# BAND software factory

Reusable preparation and runtime tools for a seven-seat BAND factory using Codex, Claude Code or OpenCode: PM, Architect, Designer, Backend, Frontend, QA and Reviewer. The toolkit pins official sources, generates complete task packets, enforces bounded execution, and retains rehearsal and run evidence.

The application lives in the separate [Tablekeeper repository](https://github.com/Xuefeng-Zhu/Tablekeeper), with one branch per attempt. This repository contains the factory and its records. Read [AGENTS.md](AGENTS.md) before changing it.

## Factory reliability and recorded runs

The [Run 8 launch record](docs/run8-launch-proof.md) preserves the dated dispatch and transport rehearsal evidence. Earlier attempts remain in the [factory history](docs/factory-history.md). These records describe their observation dates; they do not establish current process liveness or product acceptance.

The [factory reliability changes](docs/factory-reliability.md) batch complete handoffs before model admission, generate structured receipts, isolate future supervisor source, enforce runnable checkpoints, and bind rehearsal evidence to the exact factory source. Runtime profiles, task-board synchronization and terminal reconciliation retain the configured accounting and execution bounds. Fresh readiness evidence remains required before a new judged launch.

Use `scripts/runtime --config /absolute/path/to/factory.yaml factory-status` for a timestamped read of persisted runtime, budget, source, progress and product evidence. Historical launch documents are not live status.

## Local checks

From the factory directory, with its dependencies already installed:

```sh
.venv/bin/python -m unittest discover -s tests -v
scripts/factory --help
scripts/runtime --help
git diff --check
```

The tests verify factory utilities; they do not establish live BAND collaboration or product acceptance. For dependency installation, local configuration and source/task verification, use the [operator guide](docs/operator-guide.md). Preparation, rehearsal, freeze and dispatch each have separate prerequisites.

## Repository layout

| Path | Purpose |
| --- | --- |
| [`factorykit/`](factorykit/) | Validation, task generation, budgets, runtime and continuation controls |
| [`scripts/`](scripts/) | Factory/runtime entrypoints, pinned dependency bootstrap and permission probes |
| [`tests/`](tests/) | Offline utility and regression tests |
| [`config/`](config/) | Examples, source and dependency locks, historical attempt registry |
| [`mandates/`](mandates/), [`protocols/`](protocols/), [`agents/`](agents/) | Generic roles and collaboration rules |
| [`tasks/`](tasks/) | Generated packets and their manifest; verify instead of hand-editing |
| [`templates/`](templates/), [`submission-templates/`](submission-templates/) | Empty records and submission authoring aids |
| [`docs/`](docs/README.md) | Operator guides, integration notes and run history |
| [`evidence/`](evidence/) | Retained observations, failures, reviews and package artifacts |
| [`tooling/codex/`](tooling/codex/) | Pinned project-local Codex CLI dependency |

The parent workspace keeps `challenge/` read-only at commit `803560d2a678ace1414465c098eb0ab5380ffade`, `runs/` for local environments and evidence, `rehearsal/` for practice repositories, and `result-run-N/` for independent application attempts. See the [branch workflow](docs/attempt-branches.md).

## Documentation

- [Documentation index](docs/README.md): operating guides and each attempt's evidence.
- [Operator guide](docs/operator-guide.md): setup, identities, rehearsal, guarded launch and packaging.
- [Switch harness and model](docs/runtime-selection.md): inspect options and prepare an isolated Codex, Claude Code or OpenCode configuration.
- [Environment and permissions](docs/environment.md), [integration](docs/integration.md), and [Docker capacity](docs/docker-resources.md).
- [Factory history](docs/factory-history.md): the original roster, rehearsal observations and recorded run summaries.

Credentials remain outside repositories in owner-only storage. Local `config/factory.yaml`, environments and tool installations stay ignored. Preserve source locks, frozen configuration, generated packets and raw evidence; changing factory execution inputs invalidates their existing readiness bindings.
