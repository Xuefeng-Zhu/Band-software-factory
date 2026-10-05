# Seven-seat BAND factory preparation

**Status: Run 5 is running after one approved dispatch; no accepted stage is claimed.** Its task was sent once on October 4, 2026 at 2:06 PM PDT, with all seven seats connected and at most one active model seat. The original cumulative token ceiling and 7:35 PM PDT deadline remain unchanged. See [the approved launch and dispatch record](docs/run-5-preparation.md).

Run 4 is stopped and closed with a BLOCKED outcome and no accepted stage. Independent review rejected candidate `7edd47cccf839e8ec175c1e7e7252f40d80cf191` after valid dates below year 1000 failed required behavior. The official isolated suite passed 120/120, but that result did not waive the independently reproduced defect. All three repair cycles were exhausted; stages 2–4 were not started. See [Run 4 outcome and evidence](docs/run4-outcome.md).

The private [Tablekeeper `run-4` branch](https://github.com/Xuefeng-Zhu/Tablekeeper/tree/run-4) ends at `13bc38fc1d4396c70c42b529eab369d6f84a0186`. Its unchanged full BAND export contains 3,774 events and exactly one human task dispatch. Final packaging preserved the acknowledgment receipt and room export without changing the rejected Stage 1 product tree. All owned workers stopped on October 4, 2026 at 1:32:48 PM Pacific.

Run 3 remains preserved after independent Stage 1 acceptance. Its accepted BAND-authored candidate is `52a179d778b3052acf68c8aafeec62aac8ae6ecd`: 120/120 official isolated checks passed. A fresh clone of the pushed evidence commit `27f677a9ca93ba1f4e80aa6fdb87392e7f89ec84` passed the same 120 checks through `--all --mode isolated`; Stage 1 source is unchanged. Stage 2 reached architecture/design planning only; stages 2–4 have no implementation folders.

The full BAND session is committed unchanged as `room.json` on the private [Tablekeeper `run-3` branch](https://github.com/Xuefeng-Zhu/Tablekeeper/tree/run-3): 4,088 messages and one human task dispatch. Complete `README.md` and `FACTORY.md` drafts were added at the participant's request with explicit AI-assistance disclosure. The official offline packaging check passes, including a fresh remote clone. Participant authorship review, a real-room video, public-release approval and final submission remain separate requirements. See [Run 3 outcome and evidence](docs/run3-outcome.md).

Run 3 stopped at `2026-10-04T08:47:13Z` with `blocked_coordinator_self_notice` while Backend was still processing a twelve-part handoff. The repaired runtime passes **224 offline factory tests** and now also passes a separately authorized **live communication rehearsal**: overdue local SDK processing deferred a false notice, and one genuine PM→Backend notice recovered a deliberately missing original part. The rehearsal used **1,931,411 additional reported tokens**, stopped all owned workers within ten minutes, and preserved Run 3. See the [live result and evidence](docs/queue-repair-live-result.md).

Run 4 used **59,671,522 reported tokens**, ending with preserved cumulative usage of **145,683,099 tokens**, including cached input. Its allowance remains closed. Original Run 3 configuration/freeze remain preserved; the closed Run 4 ledger records all prior counters and blocks further model work for that attempt. Run 4 preparation passed 240 offline factory utility tests; those tests establish factory behavior, not product acceptance.

Run 5 was approved at `2026-10-04T20:59:53Z` to use the **140,328,478 reported tokens remaining at authorization**, within the unchanged cumulative ceiling of **286,011,577**. No accounting or elapsed-time origin was reset. Its initially empty independent checkout has published [the `run-5` branch](https://github.com/Xuefeng-Zhu/Tablekeeper/tree/run-5); remote head `0b193c068341b5e81f82b354e25eab12355e77dc` was observed at 2:08 PM PDT. The live branch may advance. The revised early-QA workflow was not separately live-rehearsed; initial execution is not product acceptance.

Workspace: `/Users/frank/mygit/Tablekeeper`

The `challenge/` sibling is pinned read-only to commit `803560d2a678ace1414465c098eb0ab5380ffade`. `factory/` holds the reusable tools; `runs/` holds evidence and environments. The completed queue rehearsal used the empty `rehearsal/queue-repair-result/`; the earlier repair practice remains in `rehearsal/repair-result/`. `rehearsal/toy-result/` retains the original toy application and history. The initially empty `result-run-3/` is independent of prior `result/`. The canonical `run-2` branch preserves four BAND-authored progress commits ending at `86ad17c600fd994bcb55c222049b7d0546f2e472`, with 120/120 owner-run isolated Stage 1 checks but no independent stage acceptance. Its stages 2–4 remain unimplemented. No prior application source was seeded into the fresh Run 3 repository. The `result/` checkout now holds the navigation `main` branch; `result-run-4/` retains Run 4's rejected implementation, attributable history and full room export on the same application remote.

All commands below run from the absolute factory directory:

```sh
cd '/Users/frank/mygit/Tablekeeper/factory'
```

## Repositories and progress

Application attempts now share **[Xuefeng-Zhu/Tablekeeper](https://github.com/Xuefeng-Zhu/Tablekeeper)**, with one branch per try. Factory tools remain separate. See [the branch workflow](docs/attempt-branches.md) and `config/attempts.json`.

- `run-3`: exact preserved application history and full room export; independently accepted Stage 1.
- `run-2`: exact preserved prior application history.
- `run-4`: closed rejected Stage 1 checkpoint at `13bc38fc1d4396c70c42b529eab369d6f84a0186`, with the full room export; no accepted stage.
- `run-5`: one verified dispatch, runtime in progress; remote head `0b193c068341b5e81f82b354e25eab12355e77dc` observed at `2026-10-04T21:08:57Z`, with no accepted stage claimed.
- Factory tools: https://github.com/Xuefeng-Zhu/Tablekeeper-factory — this separate repository, committed and pushed at verified milestones.
- Challenge: the pinned official upstream checkout; never refreshed during the frozen build.
- Earlier standalone repositories remain historical copies. Future attempts use the shared application repository.

The workspace was moved to `/Users/frank/mygit/Tablekeeper`. Historical logs retain their original paths and are not current permission attestations. Credentials remain outside this workspace. Run 4 was authorized for 200,000,000 additional reported tokens and eight hours, one active seat, 1,000 cumulative turns per seat, a 600-second turn limit and three repairs, using the existing subscription without API billing or paid provisioning. The original accounting clock began at 17:49:25 UTC on October 3 and was not reset. Run 4 closed at its terminal product rejection before reaching its time or token ceilings; unused allowance does not reopen the failed attempt. The checked-in example stays unapproved by default.

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

Future readiness requires explicit [Docker capacity minima](docs/docker-resources.md). Doctor and an otherwise-ready runtime launch check the selected daemon's CPU count and total memory; a responding daemon alone is insufficient. Existing frozen attempts are not updated automatically.

`validate` checks structural correctness; a PASS may still have launch blockers. `validate --ready` fails on those blockers. `freeze` records a blocked manifest when live prerequisites are missing. `launch-prepare` never sends a message; when ready it reserves the chosen mode/stages under a locked ledger. A reserved dispatch must not be repeated on uncertainty. `dispatch-record` records the real room event reference after the authorized UI action. Separate mode is `launch-prepare --mode separate --stage N` and requires prior independent acceptance; mixing modes or duplicating stages is rejected.

`submission-check` runs the official offline check and marks missing pre-build artifacts `EXPECTED_MISSING`. This is not a passing submission. The final form, `submission-check --final`, includes additional manual evidence gates and must be reviewed by a person.

## Seven real identities; accepted toy stages

| Seat ID | Stable requested display name | Intended harness/model | Actual handle/registration |
|---|---|---|---|
| pm | Factory PM | Codex / gpt-6-astra | @frankzhu94/factory-pm / SDK identity and rehearsal membership verified |
| architect | Factory Architect | Codex / gpt-6-astra | @frankzhu94/factory-architect / SDK identity and rehearsal membership verified |
| designer | Factory Designer | Codex / gpt-6-astra | @frankzhu94/factory-designer / SDK identity and rehearsal membership verified |
| backend | Factory Backend | Codex / gpt-6-astra | @frankzhu94/factory-backend / SDK identity and rehearsal membership verified |
| frontend | Factory Frontend | Codex / gpt-6-astra | @frankzhu94/factory-frontend / SDK identity and rehearsal membership verified |
| qa | Factory QA | Codex / gpt-6-astra | @frankzhu94/factory-qa / SDK identity and rehearsal membership verified |
| reviewer | Factory Reviewer | Codex / gpt-6-astra | @frankzhu94/factory-reviewer / SDK identity and rehearsal membership verified |

The mandates' first two lines record the selected harness/model. Registration and actual execution are evidenced separately. All seven seats now select **gpt-6-astra**, the current flagship resolved through OpenAI's [latest-model guidance](https://developers.openai.com/api/docs/guides/latest-model), using project-local **Codex CLI 0.160.0** and band-sdk 4.0.0. The authenticated fresh `initialize` + `model/list` check confirmed gpt-6-astra with both the existing medium and high role efforts; no inference turn was started. The catalog's default is gpt-6.1-sol, so this is an explicit flagship selection, not a claim that Astra is the newest chronological model or the runtime default. Evidence: `runs/model-upgrade/models-0.160.0.json`. Earlier CLI 0.133.0 discovery selected gpt-5.5; that observation remains historical evidence, not the current selection. Native identity creation and room membership are recorded separately. All seven configured seats have now executed real rehearsal turns and produced directed replies. Actual committed-change visibility is now recorded for every seat at its listed Stage 1 or Stage 2 revision; bounded missing-peer recovery and natural incomplete-message handling have now been observed. Preparation subagents are not BAND seats.

BAND Desktop 0.4.12 is installed and signed in. Initial preparation created seven real identities and two rooms through its supported CLI; that history is in `runs/preparation/`. The new approved repair-rehearsal and Run 3 rooms reuse those same seven identities plus Frank; their exact membership records are in `runs/judged-attempts/attempt-3/`. The seven factory native workers have been stopped while preserving their identities and parked templates. Their project-local 0.160.0 templates and gpt-6-astra settings were updated without restart; the default plus both room settings were verified for all seven seats. See `runs/model-upgrade/native-template-summary.json`. See `docs/native-band-cli.md` for the integration boundary.

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

Each invocation has its own evidence directory and propagates the official exit code. Failed logs remain. The wrapper invokes only options observed in official `--help`. The first BAND-authored toy candidate is `bdfc842110f057ae4e9997d62f33196a6cbc03ed`. Backend and the independent Reviewer each observed 8/8 Stage 1 checks passing through the official isolated harness. QA reports 30 passing check groups across five host/container environments after retaining and correcting two invalid test attempts. The Reviewer subsequently accepted this exact candidate in event `8e8ef1c3-fa8b-4c0b-8aff-73ffad557072`; no later-stage acceptance is implied. All-seat checkout/reply evidence and bounded recovery are recorded separately. The guide's full-session export and successful official offline toy check are now enforced as separate hash-bound launch gates; see [the finish-loop procedure](docs/rehearsal-finish-loop.md).

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
