# Rules review and future submission procedure

This is preparation documentation, not a standing instruction loaded into a judged seat. It records the authoritative rules; it does not implement the product or prove registration, a connected seat, a rehearsal, a successful stage or submission eligibility.

## Sources and deadline

The [participant guide](https://github.com/band-ai/dark-factory-wearedevs/blob/803560d2a678ace1414465c098eb0ab5380ffade/docs/participant-guide.md) is authoritative for procedure. The exact files under `challenge/tablekeeper/spec/` are authoritative for product behavior. The checkout is pinned to `803560d2a678ace1414465c098eb0ab5380ffade`. `factory/config/source-lock.json` records hashes, source locations, retrieval times, redirects, tools and the observed clock. Do not refresh sources during a frozen run.

The guide says submissions close **Monday, October 5, 2026 at 23:59 PDT (America/Los_Angeles)**, equivalent to October 6 at 06:59 UTC. The preparation clock record was October 3 at 06:05:35 UTC, or October 2 at 23:05:35 PDT; the deadline was in the future then. This does not establish registration or an open account-specific submission UI. Recheck the clock and account status before launch; if closed, use practice mode without claiming eligibility. The [event page](https://lablab.ai/ai-hackathons/wearedevelopers-hackathon) was recorded separately and found consistent on the date.

Read during preparation: challenge README, participant guide in full, all four Tablekeeper specifications, all four toy specifications and the toy mandate examples. The official CLI help was executed for `harness`, `harness run` and `harness check`; exit status was 0 for each. No product suite is claimed from reading the help.

## What must remain separate

The official checkout is input only. The reusable factory is preparation. The rehearsal is the unscored toy with its own room, source, history and evidence. The judged output is a fresh separate repository, initially empty except Git metadata. No scaffold, application schema, prototype, behavior test, stage Dockerfile or invented room export belongs in it during preparation.

The guide expressly forbids using source code, API documentation or schemas from existing products in this domain. The team builds from the supplied specifications after dispatch. Technical and visual preferences are proposals inside the task packets and cannot override required behavior.

Only factory mandates and domain-neutral protocols are standing seat instructions. Track names, endpoints, fields, error codes, test identifiers, product proposals and exact specifications belong in dispatched tasks and subsequently team-authored artifacts. Do not smuggle product instructions through shared hooks, global configuration or skills. The factory-only AGENTS.md must not become an ancestor of the judged checkout.

## Eligibility and gates

The entry needs at least three configured distinct BAND Desktop seat identities; this preparation plans seven meaningful seats. Native preparation subagents do not satisfy that requirement. Each actual seat appearing in the room needs a matching mandate file named after its displayed name, ignoring case and punctuation. The seven planned display names therefore correspond to `factory-pm.md`, `factory-architect.md`, `factory-designer.md`, `factory-backend.md`, `factory-frontend.md`, `factory-qa.md` and `factory-reviewer.md`.

Every final mandate begins with the actual harness name as BAND displays it and exact model identifier:

```text
Harness: <actual displayed harness>
Model: <actual authenticated model id>
```

Unknown identities or runtime metadata block launch. Discovering a model in the local authenticated runtime supports model selection; it does not prove any BAND seat is registered or executing it. Verify every configured identity, room visibility, directed message/reply, assigned checkout and committed-change visibility during rehearsal.

The four disqualification gates are: distinct configured identities and corresponding runtime-named mandates; reciprocal addressed messages between at least two own seats; a clean-container stage-1 service following RUN.md; and generic mandates plus code written to specifications rather than tests. All seven seats should be exercised during this factory's rehearsal even though the rule's minimum reciprocal exchange is two. The offline check covers gates 1, 2 and the mandate half of gate 4; it does not build stage 1.

The rubric weights factory 50%, application 25% and agent teamwork 25%. Seat count, message volume, mandate length and manufactured conflict are not evidence of quality. Ownership must be real; independent review may accept correct work the first time. Evidence comes from the room and attributable Git history.

## Dispatch and stage inheritance

All four specifications are already released. The team can receive all four once or each stage separately once; do not mix modes or dispatch a stage twice. In the judged run, the initial task for a stage is the only human input until the coordinator's outcome. No human clarification, approval, debugging hint, encouragement, rerun or wait-for-human flow is allowed. Resolve account, event, specification, permission and budget questions before dispatch.

Use one fresh judged room and repository for the submitted run. The coordinator adds every preconfigured seat before first handoff. All handoffs paste complete task and specification content, including inherited requirements, using actual handles; references to message IDs or instructions to read the room are insufficient. Long messages use numbered complete sets. The reviewer receives complete requirements and independently verifies the reported full revision.

| Output | Full required specifications | Stage boundary |
|---|---|---|
| stage-1 | stage 1 | Must not already solve all of stage 2 |
| stage-2 | stages 1 and 2 | Must not already solve all of stage 3 |
| stage-3 | stages 1, 2 and 3 | Must not already solve all of stage 4 |
| stage-4 | stages 1, 2, 3 and 4 | Final cumulative output |

Every completed directory is an independent full service with source, Dockerfile and RUN.md. Copy an accepted earlier directory forward and extend the copy; preserve genuine earlier outputs. Remove copied nested Git metadata before committing files. No symlinks or submodules. Do not copy the final answer backward. Submit only actually completed stage directories.

Each folder is graded against every suite up to its number and normally probed against the next full suite to reject overshoot. Passing the next suite completely means that folder claims no earlier stage. The toy alone skips the stage-2 to stage-3 probe because its third stage adds load rather than new surface. The contiguous chain determines the attained stage; a failure below a later passing folder caps the result.

The shipped graded checks are partial (the guide gives Tablekeeper coverage of 83%, 41%, 11% and 21% by stage). Their green results are directional evidence, never full-stage proof. QA derives actual behavior checks from all requirements after dispatch. Do not reduce requirements to public checks or tune behavior to test fixtures. At least half of every applicable full suite is needed for a folder to claim its stage, with the overshoot rule still applying.

## Task preference compatibility

The user's proposed TypeScript, React/Vite, Node, SQLite and timezone adapter are compatible starting proposals, not mandated implementation choices. The specifications leave language, framework and storage unrestricted. The architect must decide after dispatch and record consequential assumptions. No implementation or schema follows from the preparation choice.

The requested warm hospitality direction, clear hierarchy, human-readable labels, keyboard focus and 375 CSS-pixel layout match stage 2's explicit product requirements. Required routes and test attributes still come from the exact specification. Decorative assets are optional. Required unsuccessful and uncertain feedback is part of the behavior contract, not a later styling enhancement.

Stage 1 already includes atomic multi-item moves, retry behavior and portable export/import; it is not a minimal endpoint stub. Stage 2 adds approved table pairs and browser recovery as well as cross-stage import continuity. Stage 3 adds policy/history/recurring behavior while retaining the stage-2 UI; stage 4 adds deterministic replanning and recurring amendments. Stages 3 and 4 require no new screens. These are scope reminders for complete task inclusion, not prepared product designs or acceptance tests.

Prioritizing verified required behavior and a polished stage 2 is consistent with the rules as long as all required behavior is attempted in order and incomplete later work is never labeled complete. Optional dashboards and integrations cannot substitute for specified behavior. Later task packets must include the complete earlier texts, not these summaries.

## Deployment and official commands

The service runs as one image. The harness ignores Compose and communicates over HTTP; it does not require the implementation language on the judge host. Runtime has 2 vCPU, 2 GiB, a 60-second healthy-start limit, up to 50 concurrent requests, a 5-second ordinary request timeout and 10 seconds for test controls. It binds 0.0.0.0, honors PORT and bundles runtime dependencies and browser assets. Builds can download dependencies; runtime has no outbound network. Do not confuse model connectivity during development with application networking during judgment.

The following are **future commands after team-authored outputs exist**, not claims they were run successfully. They use this preparation's exact paths and verified official CLI flags. Run from the pinned challenge directory. Every `--out` directory must be new; choose a new suffix for repeat checks and keep failures.

```sh
cd '/Users/frank/mygit/Tablekeeper/challenge'
'/Users/frank/mygit/Tablekeeper/runs/harness-venv/bin/python' -m harness run --track tablekeeper --repo '/Users/frank/mygit/Tablekeeper/result' --stage 1 --mode isolated --out '/Users/frank/mygit/Tablekeeper/runs/checks/judged-s1-final-001'
'/Users/frank/mygit/Tablekeeper/runs/harness-venv/bin/python' -m harness run --track tablekeeper --repo '/Users/frank/mygit/Tablekeeper/result' --all --mode isolated --out '/Users/frank/mygit/Tablekeeper/runs/checks/judged-all-final-001'
'/Users/frank/mygit/Tablekeeper/runs/harness-venv/bin/python' -m harness check '/Users/frank/mygit/Tablekeeper/result' --track tablekeeper
```

For the rehearsal use `--track toy` and its separate actual repository path, never the judged result. Host mode is the default and useful during iteration, but does not block outbound networking. Final validation must use `--mode isolated`, which places service and tester on the harness's internal network. Do not improvise isolation that makes the service unreachable to the tester. The harness runs as a local command executed by a reviewer; it is not a seat and never posts messages itself.

`harness check` validates metadata, whole-room export, corresponding mandate files, runtime lines, reciprocal mentions, mandate vocabulary and credential shapes. It builds nothing. Before the run, missing application and room artifacts are EXPECTED_MISSING, not a valid submission. A placeholder room export is prohibited. Skipped/deselected/empty suites, missing browser dependencies and startup errors are never passing evidence.

## Full-room export and credential incidents

After the work is complete, open the actual room in BAND Desktop, use its top-right `⋮` menu and select **Open in Band**. In the web console under **Sessions**, open that same room. Use the room's `⋮` menu, then **Download → Download full session**. Never choose **Download filtered**. UI sender/event filters do not matter for a full-session download.

Save the complete downloaded file at the actual result root as `room.json`, renaming only. No harness command fetches it. Never synthesize it, concatenate partial logs, hide failures, remove substantive collaboration or fabricate events. If later work was added, download the full room again after it finishes and replace the earlier complete export. Record download time and hash.

Read the whole export locally before any public commit or push. Tool calls and outputs are included, and nothing automatically redacts private information. Do not echo private contents into a room or chat while inspecting them. Automated credential-shape scans help but cannot recognize every private value.

The guide's normal rule is unchanged content. Its explicit credential-incident exception says to **rotate the credential and replace the value in room.json with `[REDACTED]`**. Apply only that narrow exception when necessary; record incident category, locations, time and rotation evidence without the secret. Do not redact failed attempts or meaningful collaboration. If a credential was already pushed, deleting a line does not undo exposure: revoke or rotate it and document the incident. If another private value requires a change outside the explicit exception, hold public release and resolve the issue before publication rather than silently rewriting evidence.

## Final packaging and human actions

The final repository contains the human-authored README.md and FACTORY.md, final per-seat mandates, actual full room export, and completed contiguous stage directories. The presentation and video accompany the public repository URL in the event submission. Video must show the factory working: real room, actual seat handoff and resulting software. A slideshow explaining the idea is insufficient.

The human writes the final README and FACTORY narrative under the guide. Empty templates supplied here require real outcomes, costs, choices and failure evidence before use. Keep measured costs separate from estimates and say UNAVAILABLE for absent measurements. Do not fabricate a failure to make the presentation more dramatic.

After explicit user authorization to publish, push attributable history without amending, rebasing or squashing. Clone the public repository into a new directory and repeat offline validation, all-stage isolated validation and each RUN.md manually in a clean environment. Inspect the actual UI where applicable. A fresh clone detects uncommitted or nested-repository omissions. Check that judges can clone without BAND membership. Obtain explicit user authorization before submitting the URL, presentation and video, and preserve the actual receipt.

## Apparent conflicts and resolutions

1. The general BAND Desktop walkthrough suggests asking humans for decisions. The participant guide's judged-run autonomy rule is stricter and controls this run. All seven mandates prohibit that interaction during a dispatched stage.
2. Generic mandate examples in the guide mention asking about ambiguity, while the judged-run section forbids human clarification. Ask configured peers or report a blocker; resolve event/specification questions publicly before launch.
3. The guide says full-room exports stay unchanged and also gives the explicit credential-rotation/redaction exception. The narrow exception above resolves the wording; it never authorizes editing substantive evidence.
4. The general Codex adapter web examples use a `cwd` configuration field. The installed SDK may expose a different supported API; use the inspected, version-pinned SDK surface, with verification, rather than assuming example fields work. Likewise example model IDs are not selections; use authenticated discovery.
5. The original OpenAI security URL redirects to a broader security product page. The source lock also includes the current linked agent-approvals/security guidance actually used for execution permissions.
6. Stage 3 mentions a restaurant-level revision in cumulative operations, and stage 4 supplies its comprehensive definition. Preserve exact full stage text and let the team reason about cumulative requirements; do not silently replace source text with a setup-time interpretation. If a genuine ambiguity remains material before dispatch, the official BAND Discord is the public clarification channel.

No product implementation decision is made by this review. No unresolved contradiction was found that justifies overriding an exact specification. Registration, actual seat configuration, required permissions, live rehearsal and authorized finite consumption must still be evidenced before readiness.

## Historical preparation-only review observations (before the model upgrade)

Seven mandate headers now identify the selected authenticated runtime as `Harness: Codex` and `Model: gpt-5.5`; their handle metadata remains UNRESOLVED and each explains that active seat execution is unverified. Display-name/file correspondence was inspected for the planned roster. The official harness mandate structural/vocabulary routine reported PASS. A second scan across every mandate and standing protocol using both official graded-track vocabularies reported PASS. One preliminary audit invocation failed because its interpreter path was relative to the wrong directory; the corrected absolute-path invocation exited 0. Neither invocation altered challenge files or ran product checks.

A semantic review separately checked that each mandate defines purpose, authority, inputs, outputs, complete handoffs, rejection, bounded recovery and limits, with meaningful independent ownership. The mandates and protocols contain no product-specific routes, field names, error codes, screen design or implementation decisions. Vocabulary scans alone are not a compliance guarantee; review final resolved mandates again before freeze and before publication. This review does not establish the seat-identity or room-exchange gates.
