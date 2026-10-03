# Seven-seat BAND factory preparation

**Status: BLOCKED_WITH_ACTIONS. No judged task was dispatched.** The user has authorized starting the build; [current build-start findings](docs/BUILD-START.md) explain the remaining execution requirements. The model/runtime selects gpt-6-astra on project-local Codex CLI 0.160.0. The toolkit is locally tested, the official challenge is pinned, and seven BAND identities exist. All seven SDK identities and rehearsal room memberships have been verified without inference. The PM completed one live rehearsal turn, then stopped at a nested operator-preflight error. The complete seven-seat rehearsal remains unverified; owned runtime processes are stopped. See `docs/READINESS.md` for the preparation and model-upgrade evidence.

Workspace: `/Users/frank/mygit/Tablekeeper`

The `challenge/` sibling is pinned read-only to commit `803560d2a678ace1414465c098eb0ab5380ffade`. `factory/` holds the reusable tools. `rehearsal/toy-result/` is an empty independent practice repository. `runs/` holds evidence, environments, browser binaries and future worktrees. `result/` is a fresh Git repository with **zero commits and no product files**. No stage Dockerfiles, schemas, product prototypes or domain behavior tests have been seeded.

All commands below run from the absolute factory directory:

```sh
cd '/Users/frank/mygit/Tablekeeper/factory'
```

## Repositories and progress

- Application: https://github.com/Xuefeng-Zhu/Tablekeeper — local `../result`, currently empty pending the first BAND-authored product commit.
- Factory tools: https://github.com/Xuefeng-Zhu/Tablekeeper-factory — this repository, committed and pushed at verified milestones.
- Challenge: the pinned official upstream checkout; never refreshed during the frozen build.

The workspace was moved to `/Users/frank/mygit/Tablekeeper`. Historical logs retain their original paths and are not current permission attestations. Credentials remain outside this workspace. The approved local ceiling is 1,000,000 reported tokens and eight hours across rehearsal and build, one active seat, with no API billing or paid provisioning. The checked-in example stays unapproved by default.

## Reproduce and inspect

```sh
python3 scripts/bootstrap.py --install-browser
.venv/bin/python -m unittest discover -s tests -v
scripts/factory doctor
scripts/factory validate
scripts/factory generate-tasks
scripts/factory verify-tasks
scripts/factory submission-check
scripts/factory freeze
scripts/factory launch-prepare --mode all
```

The local `config/factory.yaml` already records the created identities and rooms and is intentionally ignored by Git. For a fresh clone, first copy `config/factory.example.yaml` to `config/factory.yaml` **only if absent**, resolve its absolute paths, and configure the existing verified roster; examples do not register agents. Create `runs/`, `rehearsal/toy-result/` and `result/`, then initialize the latter two as separate empty Git repositories. Never reinitialize, clean or overwrite an existing run to manufacture pristine state. Restore SDK keys separately through the restricted credential path.

`bootstrap.py` restores local dependencies from `uv.lock`, the hash-locked official harness requirements and the pinned Codex package lock at `tooling/codex/package-lock.json`. The Codex runtime is project-local; no global CLI installation or global configuration replacement is required. It clones the pinned challenge only if absent; an existing different revision is rejected. Existing sources are never refreshed. Python 3.13.5 is used (the guide requires 3.12+). On another machine, explicitly update every absolute path and the local Codex executable wrapper, regenerate packets and invalidate/rebuild readiness evidence. Do not carry over registration or permission attestations.

`validate` checks structural correctness; a PASS may still have launch blockers. `validate --ready` fails on those blockers. `freeze` records a blocked manifest when live prerequisites are missing. `launch-prepare` never sends a message; when ready it reserves the chosen mode/stages under a locked ledger. A reserved dispatch must not be repeated on uncertainty. `dispatch-record` records the real room event reference after the authorized UI action. Separate mode is `launch-prepare --mode separate --stage N` and requires prior independent acceptance; mixing modes or duplicating stages is rejected.

`submission-check` runs the official offline check and marks missing pre-build artifacts `EXPECTED_MISSING`. This is not a passing submission. The final form, `submission-check --final`, includes additional manual evidence gates and must be reviewed by a person.

## Seven real identities verified; live execution pending

| Seat ID | Stable requested display name | Intended harness/model | Actual handle/registration |
|---|---|---|---|
| pm | Factory PM | Codex / gpt-6-astra | @frankzhu94/factory-pm / SDK identity and rehearsal membership verified |
| architect | Factory Architect | Codex / gpt-6-astra | @frankzhu94/factory-architect / SDK identity and rehearsal membership verified |
| designer | Factory Designer | Codex / gpt-6-astra | @frankzhu94/factory-designer / SDK identity and rehearsal membership verified |
| backend | Factory Backend | Codex / gpt-6-astra | @frankzhu94/factory-backend / SDK identity and rehearsal membership verified |
| frontend | Factory Frontend | Codex / gpt-6-astra | @frankzhu94/factory-frontend / SDK identity and rehearsal membership verified |
| qa | Factory QA | Codex / gpt-6-astra | @frankzhu94/factory-qa / SDK identity and rehearsal membership verified |
| reviewer | Factory Reviewer | Codex / gpt-6-astra | @frankzhu94/factory-reviewer / SDK identity and rehearsal membership verified |

The mandates' first two lines record the selected harness/model, not observed seat execution. All seven seats now select **gpt-6-astra**, the current flagship resolved through OpenAI's [latest-model guidance](https://developers.openai.com/api/docs/guides/latest-model), using project-local **Codex CLI 0.160.0** and band-sdk 4.0.0. The authenticated fresh `initialize` + `model/list` check confirmed gpt-6-astra with both the existing medium and high role efforts; no inference turn was started. The catalog's default is gpt-6.1-sol, so this is an explicit flagship selection, not a claim that Astra is the newest chronological model or the runtime default. Evidence: `runs/model-upgrade/models-0.160.0.json`. Earlier CLI 0.133.0 discovery selected gpt-5.5; that observation remains historical evidence, not the current selection. Native identity creation and room membership are recorded separately; actual SDK seat execution and model usage remain live prerequisites. Preparation subagents are not BAND seats.

BAND Desktop 0.4.12 is installed and signed in. Seven real identities and two rooms were created through its supported CLI; actual UUIDs and room IDs are in the local configuration and `runs/preparation/`. The seven factory native workers have been stopped while preserving their identities and parked templates. Their project-local 0.160.0 templates and gpt-6-astra settings were updated without restart; the default plus both room settings were verified for all seven seats. See `runs/model-upgrade/native-template-summary.json`. See `docs/native-band-cli.md` for the integration boundary.

Supported SDK keys for all seven existing identities were retrieved through the BAND Desktop Info panel and saved privately. A real SDK registration probe matched every configured UUID, handle and rehearsal membership. No identities were replaced and no keys are stored in Git. Re-run registration after local configuration changes.

Credentials belong at the configured absolute `band.credentials_file`, outside every repository. A non-secret shape is in `config/agent-credentials.example.yaml`; private parent mode must be `0700`, file mode `0600`. Do not paste keys into the room or chat. Non-secret identity/model/room settings belong in `config/factory.yaml` (ignored by factory Git). Confirm SDK REST and websocket endpoints refer to the same BAND environment.

```sh
scripts/runtime discover-models
scripts/runtime probe-registration --mode rehearsal
scripts/runtime seat-status
scripts/runtime start-seats --mode rehearsal
scripts/runtime stop-seats
```

These actions fail closed until credentials, model discovery, room binding, permission evidence and a finite approved consumption policy are valid. `probe-registration` reads actual identity/membership and starts no model turn. `start-seats` connects seven independent adapters under a factory-owned supervisor; a process-wide single active-turn lease prevents concurrent writes in the shared checkout. No worktree is created before the first BAND-authored commit. The supported adapter transports BAND messages; this project does not implement a replacement messaging system. Only matching owned processes may be stopped.

## Practice before the judged run

Once rehearsal preflight passes, start the seats in rehearsal mode and send the complete `tasks/rehearsal-toy.md` to the actual PM handle in the rehearsal room. Rehearsal does not require the judged READY freeze. Verify every seat receives directed messages and replies, sees the assigned checkout and a real committed change, and participates meaningfully. Observe a PM assignment, complete peer handoffs, independent exact-candidate review, missing-peer and delayed-message behavior. Keep real evidence; never force a rejection or invent recovery.

```sh
scripts/factory harness --track toy --stage 1 --mode host
scripts/factory harness --track toy --all --mode isolated
```

Each invocation has its own evidence directory and propagates the official exit code. Failed logs remain. The wrapper invokes only options observed in official `--help`. The actual toy build and isolated check have **not** run. Credentials and the finite subscription budget are configured; OrbStack Docker 29.4.0 is running. The common SDK permission boundary has passed; seven-seat checkout/reply evidence and the full toy rehearsal remain required.

Read `docs/environment.md` before configuring execution access. The earlier Codex CLI 0.133.0 disposable sandbox probe allowed file writes but denied Git commits, development networking and localhost binding. Those failures are retained. A current 0.160.0 SDK probe confirmed inherited named permissions for Git writes, exact-domain dependency networking and localhost binding; the Docker build and containerized Chromium interaction now pass through the actual adapter configuration. The version/model change does not establish new permissions. The runner does not enable unrestricted host access. Prepare and verify a disposable environment or a narrowly supported permission profile; the named profile is validated through explicit host and socket allowlists. Docker socket access is significant privilege. Host browser smoke success does not prove agent browser permissions.

## Freeze, then dispatch once later

After real rehearsal and all readiness evidence is recorded, rerun doctor, validation, task generation and freeze. `runs/readiness/observations.json` binds real evidence files/hashes to the configuration and source lock; see `factorykit/validation.py` for required observations. Never mark unobserved items PASS. Unknown handles, budget, runtime metadata or capabilities keep the freeze blocked.

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

Follow `docs/rules-review.md` for the official full-room download and narrow credential-incident exception. Never synthesize `room.json`; retain failures and history. Final packaging includes only genuinely completed independent stage folders, mandates, human-written README/FACTORY, full room export and real room video. Run official offline and isolated checks against a fresh clone and inspect the export for private content before public release. The user authorized private GitHub repositories and incremental progress commits. Public visibility, entry submission and unrelated uploads still require separate authorization.
