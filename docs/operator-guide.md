# Factory operator guide

All shell commands run from `/Users/frank/mygit/Tablekeeper/factory`. For another checkout, adjust absolute paths first. This guide describes preparation and separately authorized operations; it does not reopen a stopped attempt. The [Run 6 continuation record](run-6-continuation.md) contains the latest recorded state.

## Reproduce and inspect

```sh
python3 scripts/bootstrap.py --install-browser
.venv/bin/python -m unittest discover -s tests -v
scripts/factory --help
scripts/runtime --help
```

The local `config/factory.yaml` already records the created identities and rooms and is intentionally ignored by Git. For a fresh clone, first copy `config/factory.example.yaml` to `config/factory.yaml` **only if absent**, resolve its absolute paths, and configure the existing verified roster; examples do not register agents. Under the parent workspace, create `../runs/`, `../rehearsal/toy-result/` and `../result/`, then initialize the latter two as separate empty Git repositories. Never reinitialize, clean or overwrite an existing run to manufacture pristine state. Restore SDK keys separately through the restricted credential path.

`bootstrap.py` restores local dependencies from `uv.lock`, the hash-locked official harness requirements and the pinned Codex package lock at `tooling/codex/package-lock.json`. The Codex runtime is project-local; no global CLI installation or global configuration replacement is required. It clones the pinned challenge only if absent; an existing different revision is rejected. Existing sources are never refreshed. Python 3.13.5 is used (the guide requires 3.12+). On another machine, explicitly update every absolute path and the local Codex executable wrapper, regenerate packets and invalidate/rebuild readiness evidence. Do not carry over registration or permission attestations.

Future readiness requires explicit [Docker capacity minima](docker-resources.md). Doctor and an otherwise-ready runtime launch check the selected daemon's CPU count and total memory; a responding daemon alone is insufficient. Existing frozen attempts are not updated automatically.

After configuring a fresh preparation, `scripts/factory doctor` records prerequisites, `scripts/factory validate` checks configuration, and `scripts/factory verify-tasks` reads the existing packets. Task generation and freeze belong to the preparation procedure below.

`validate` checks structural correctness; a PASS may still have launch blockers. `validate --ready` fails on those blockers. `freeze` records a blocked manifest when live prerequisites are missing. `launch-prepare` never sends a message; when ready it reserves the chosen mode/stages under a locked ledger. A reserved dispatch must not be repeated on uncertainty. `dispatch-record` records the real room event reference after the authorized UI action. Separate mode is `launch-prepare --mode separate --stage N` and requires prior independent acceptance; mixing modes or duplicating stages is rejected.

`submission-check` runs the official offline check and marks missing pre-build artifacts `EXPECTED_MISSING`. This is not a passing submission. The final form, `submission-check --final`, includes additional manual evidence gates and must be reviewed by a person.

## Identities and credentials

Use the [faster workflow](faster-workflow.md) for compact task-board reads,
verified source references in handoffs and balance-only operation.

The seven registered roles are PM, Architect, Designer, Backend, Frontend, QA and Reviewer. The [original roster and rehearsal observations](factory-history.md#original-frozen-roster-and-rehearsal-observations) preserve the launch model and identity history. Run 6’s [continuation record](run-6-continuation.md) documents the later Sol selection. Resolve the selected model and identities from the configuration and matching evidence before preparing a new run.

Credentials belong at the configured absolute `band.credentials_file`, outside every repository. A non-secret shape is in `config/agent-credentials.example.yaml`; private parent mode must be `0700`, file mode `0600`. Do not paste keys into the room or chat. Non-secret identity/model/room settings belong in `config/factory.yaml` (ignored by factory Git). Confirm SDK REST and websocket endpoints refer to the same BAND environment.

```sh
scripts/runtime discover-models
scripts/runtime probe-registration --mode rehearsal
scripts/runtime seat-status
scripts/runtime start-seats --mode rehearsal
scripts/runtime stop-seats
```

These actions fail closed until credentials, model discovery, room binding, permission evidence and an approved consumption policy are valid. A balance-only policy retains its cumulative dollar cap without time, token, turn or repair-count stops. `probe-registration` reads actual identity/membership and starts no model turn. `start-seats` connects seven independent adapters under a factory-owned supervisor; a process-wide single active-turn lease prevents concurrent writes in the shared checkout. No worktree is created before the first BAND-authored commit. The supported adapter transports BAND messages; this project does not implement a replacement messaging system. Only matching owned processes may be stopped.

## Practice before the judged run

Once rehearsal preflight passes, start the seats in rehearsal mode and send the complete `tasks/rehearsal-toy.md` to the actual PM handle in the rehearsal room. Rehearsal does not require the judged READY freeze. Verify every seat receives directed messages and replies, sees the assigned checkout and a real committed change, and participates meaningfully. Observe a PM assignment, complete peer handoffs and independent exact-candidate review. Normal balance-only practice does not require an induced missing-peer fixture; record naturally occurring membership and delivery issues truthfully. Strict recovery testing is a separate explicitly configured exercise. Keep real evidence; never force a rejection or invent recovery.

```sh
scripts/factory harness --track toy --stage 1 --mode host
scripts/factory harness --track toy --all --mode isolated
```

Each invocation has its own evidence directory and propagates the official exit code. Failed logs remain. The wrapper invokes only options observed in official `--help`. The full-session export and successful official offline toy check are separate hash-bound launch gates; follow the [finish-loop procedure](rehearsal-finish-loop.md). The [historical practice and permission observations](factory-history.md#toy-practice-and-permission-observations) retain earlier results.

Read [environment.md](environment.md) before configuring execution access. Prepare and verify a disposable environment or a narrowly supported permission profile with explicit host and socket allowlists. Historical browser and adapter probes do not establish permissions for a new configuration.

## Freeze, then dispatch once later

After real rehearsal and all readiness evidence is recorded, rerun doctor, validation, task generation and freeze. `runs/readiness/observations.json` binds real evidence files/hashes to the configuration and source lock; see [factorykit/validation.py](../factorykit/validation.py) for required observations. Never mark unobserved items PASS. Unknown handles, budget, runtime metadata or capabilities keep the freeze blocked.

```sh
scripts/factory validate --ready
scripts/factory generate-tasks
scripts/factory freeze
scripts/factory launch-prepare --mode all
scripts/runtime start-seats --mode judged
```

Only after READY: open the configured judged room in BAND Desktop, address the verified PM handle, and send the complete generated file **`tasks/judged-all-stages.md` once**. If BAND requires splitting, number all parts and require full-set receipt before work. The task carries exact specifications, absolute paths, hashes, roster, limits and stage gates. During the judged run do not steer, approve, debug, or rerun from outside the band. Stop rather than invent a success if a required gate cannot pass.

The alternative mode uses `tasks/judged-stage-1.md` through `judged-stage-4.md` one stage at a time; prior specs remain included as inherited requirements, not a request to rebuild or redispatch those stages.

## Evidence and eventual submission

`templates/` contains empty records; the judged PM, Architect, Designer, engineers and QA create actual decisions, implementation, rendered designs and tests after dispatch. `submission-templates/` contains human authoring aids for README, FACTORY, demo, slides, description and checklist. No presentation outcomes are invented.

Follow [rules-review.md](rules-review.md) for the official full-room download and narrow credential-incident exception. Never synthesize `room.json`; retain failures and history. Final packaging includes only genuinely completed independent stage folders, mandates, human-written README/FACTORY, full room export and real room video. Run official offline and isolated checks against a fresh clone and inspect the export for private content before public release. The user authorized private GitHub repositories and incremental progress commits. Public visibility, entry submission and unrelated uploads still require separate authorization.
