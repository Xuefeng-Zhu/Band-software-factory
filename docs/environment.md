# Observed environment and permissions

Observed on 2026-10-02 PDT (UTC evidence timestamps are 2026-10-03).

The current directory was empty before preparation. Everything new is under the dedicated `outputs/hackathon-workspace` directory. `factory/AGENTS.md` is deliberately a sibling of the judged repository. `result/` contains only a freshly initialized `.git` directory with no commit, tracked files, stage folders or product code. `rehearsal/toy-result/` is a separate empty repository.

macOS 26.6.2 arm64; Git 2.54.0; system Python 3.14.3; factory/harness Python 3.13.5; uv 0.11.2; Node 24.14.1; npm 11.11.0; Codex CLI 0.133.0; band-sdk 4.0.0; Docker client 29.4.0; Playwright 1.63.0 / Chromium 153.0.8010.12.

## Inherited configuration

Read-only inspection found `/Users/frank/.codex/AGENTS.md` with generic Git workflow preferences. `/Users/frank/AGENTS.md` contains unrelated InsForge guidance. According to the pinned Codex discovery guide, an independent Git root bounds project instruction discovery, so that ancestor is outside result's project instruction chain. No global file was changed. Factory instructions are never injected into seats; runners inject the selected mandate and generic protocols only.

Global Codex config selects gpt-6-astra and reasoning `ultra`; the installed CLI rejects `ultra` before authentication. `scripts/codex-local` supplies a process-local `medium` override. With it, `codex login status` reports ChatGPT login. An authenticated app-server `model/list` query advertised gpt-5.5 as its default; gpt-6-astra was absent. All seven configured roles select gpt-5.5. Discovery created no model inference turn. Each seat's actual model execution remains unverified.

Global MCP configurations exist (names only inspected). Their live access was not exercised. Inspect effective tools and instruction inheritance in the chosen isolated environment before a judged run. No credentials were printed, copied or added to a repository.

## Observed permission boundaries

`runs/permissions-ae77662dc9/evidence.json` records a real Codex `sandbox macos --permissions-profile :workspace` probe against a disposable scratch repository:

- Workspace file write: PASS.
- Git empty commit: FAIL; the sandbox denies `.git/index.lock`.
- Development package network: FAIL.
- Loopback server binding: FAIL.

The CLI's sandbox subcommand required an explicit permissions profile despite help presenting it as optional. An earlier failed invocation and an earlier configuration error remain in separate evidence directories.

Chromium was installed in `runs/browsers`. `runs/preparation/browser-host-smoke.json` records a real headless launch, 375px viewport and keyboard focus on a synthetic setup page. It passed outside the outer preparation sandbox. The earlier sandboxed launch failure is retained in `browser-smoke.json`. This proves host browser availability only; it does not prove the judged seat can run browser checks.

Docker targets the existing OrbStack context, whose socket is absent. The daemon is stopped. OrbStack is installed, but its documented `start` command resumes all previously running machines; preparation did not restart that unrelated set. Start the intended Docker environment explicitly. No container was built and no isolated harness result is claimed.

BAND Desktop 0.4.12 is installed at `/Applications/Band.app`; its daemon is running and the supported `preflight --json` confirms a configured account. The CLI is now `/Users/frank/.local/bin/band`. The mounted DMG also contains the same bundle ID; the installed absolute executable was used. Native UI automation timed out, so supported CLI operations were used instead.

Seven persistent identities were created with copied generic mandates and actual handles recorded in `runs/preparation/band-roster.json`. Their native Codex templates remain parked/detached; no model turn was started. Tool-only native telemetry is configured. Creation returned no SDK API keys. Native connection dry-runs timed out during `initialize` at 30 seconds with both the wrapper and direct Codex executable; the maintained SDK model-discovery path succeeded independently. Never interpret native identity creation as working SDK execution.

Separate rehearsal and judged rooms were created without binding runtimes or sending tasks. Native membership reads verify seven configured identities. BAND 0.4.12 sometimes reports a decoding error after successfully adding a member; each mutation was reconciled by reading the same room before continuing. A newly created room also needed a later membership read. No duplicate room was created to hide an uncertain result. Only the seven factory peer workers were stopped afterward, preserving identities and rooms. SDK credential, websocket, directed-message, execution and room-access checks remain unverified.

## Remaining environment action

Provide a disposable development environment with a verified supported adapter connection, narrow writable checkout/Git paths, localhost/browser execution and dependency download policy. Docker socket access grants broad container-host control and must be an explicit part of that environment. Do not relabel this host as an external sandbox or use a host-wide unrestricted setting. The conservative runner currently supports workspace-write only and deliberately blocks readiness until real capability evidence is supplied; broader environment support needs a separately verified integration change.

Model/BAND connections and development downloads are separate from submitted service runtime networking. The official `--mode isolated` harness establishes the latter with its internal Docker network (reachable by the harness, no outbound access), 2 vCPU and 2 GiB. Do not substitute `--network none`, which prevents the harness reaching the service.
