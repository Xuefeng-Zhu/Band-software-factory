# Practice (unscored; eligibility not claimed) dispatch packet — toy

Packet state: REQUIRES_REHEARSAL_PREFLIGHT
Dispatch mode: practice-all; stages: 1, 2, 3, 4.
Execute stages 1 through 4 once in increasing order, with an independent gate before advancing.
Operator dispatch prerequisite: rehearsal runtime preflight must pass and finite live budgets must be approved before the launcher connects seats. A judged freeze is not required for rehearsal. Seats do not rerun operator preflight.
Pinned challenge commit: 803560d2a678ace1414465c098eb0ab5380ffade
Configuration SHA-256: 1434400dfbbda37a4b8ea21b29f4db785b898b1d3055845e0d6abd9ec21fb691

## Absolute workspace paths
- challenge: `/Users/frank/mygit/Tablekeeper/challenge`
- factory: `/Users/frank/mygit/Tablekeeper/factory`
- rehearsal: `/Users/frank/mygit/Tablekeeper/rehearsal/repair-result`
- runs: `/Users/frank/mygit/Tablekeeper/runs`
- result: `/Users/frank/mygit/Tablekeeper/result-run-3`
- Assigned output checkout: `/Users/frank/mygit/Tablekeeper/rehearsal/repair-result`

## Launcher admission and seat execution
The launcher checks authentication, approved finite budgets, registered identities
and recorded permission evidence before connecting seats. For a seat connected by
this launcher, those admission gates have already been enforced by the operator;
do not repeat them inside the task sandbox.
Do not run operator-only doctor, preflight, registration/authentication probes,
freeze, launch, start-seats or stop-seats commands; do not call
subscription_auth_probe or preflight_runtime or create nested Codex app servers.
Use the injected roster, limits and workspace metadata to execute the delivered
task. Test required operations in your assigned workspace and report any actual
denied operation with evidence; do not reinterpret an operator probe's sandbox
failure as a failed task prerequisite or try to repair operator infrastructure.
Admission does not establish product correctness, seat smoke results, peer
collaboration or stage acceptance. Perform those assigned checks and retain their
actual evidence within the existing permissions and limits.

## Execution environment
- Writable product checkout and Git metadata: `/Users/frank/mygit/Tablekeeper/rehearsal/repair-result`. One active writer is enforced.
- Store team test logs, screenshots and results under `/Users/frank/mygit/Tablekeeper/rehearsal/repair-result/.evidence` in unique run directories; keep generated caches out of commits.
- Use the platform temporary directory for clean exact-candidate review clones outside stage folders and for dependency caches. Read-only access to sources and factory tools does not grant write access to their directories.
- The runs directory contains operator-owned control records. Do not alter launcher, usage, dispatch or readiness files or attempt to broaden permissions.
- Pinned harness interpreter: `/Users/frank/mygit/Tablekeeper/runs/harness-venv/bin/python`. Run the official `-m harness run` from the challenge directory, with `--track toy`, an absolute `--repo` and `--out` inside your writable evidence directory. Use `--mode isolated` for acceptance; inspect its `--help` for the exact stage options.
- The factory harness wrapper writes operator evidence under runs; use the official harness directly for seat-owned checks.
- Docker uses the pinned local socket and private temporary buildx state supplied by the launcher. Do not override them or mount host credentials, broaden host access, or run privileged containers.
- Browser execution on this Mac uses Chromium inside the official harness Docker image. Native macOS Chromium is blocked by the seat sandbox. For rendered checks, use an isolated test network and copy screenshots back into your evidence directory; the final service must still satisfy the official no-outbound-network harness.
- Put npm/pip/uv dependency caches inside the writable checkout or temporary directory. No global package or system configuration changes are needed.

## Required repository packaging
The submission repository root contains README.md, FACTORY.md, mandates/, room.json, and only genuinely completed stage-1/ through stage-4/ directories.
Each completed stage is an independent full service containing its own Dockerfile, RUN.md and source. Do not nest the result repository under a factory directory or copy a final implementation backwards into earlier stages.
After dispatch, copy the seven final seat mandates into the output root's mandates/ directory under their existing matching filenames; preserve Harness and Model metadata.
README.md and FACTORY.md are final human-authored narratives. room.json is the actual complete BAND room download after the run. Do not fabricate these artifacts or treat missing post-run metadata as a passing submission check.
Keep challenge and factory inputs outside the submitted repository. The official harness check validates final packaging; isolated harness run validates each actual stage. Final metadata assembly and public release happen after the autonomous run.

## Actual roster
- pm: Factory PM; handle: @frankzhu94/factory-pm; identity: 7d26ccf7-2921-4b38-9e16-ca8ebfa2a448; harness: Codex; model: gpt-6-astra
- architect: Factory Architect; handle: @frankzhu94/factory-architect; identity: 974df2f1-b5e8-4873-a1ce-93658e0404a4; harness: Codex; model: gpt-6-astra
- designer: Factory Designer; handle: @frankzhu94/factory-designer; identity: a6ee2e58-62bd-4ba9-b573-f164bb3e41d2; harness: Codex; model: gpt-6-astra
- backend: Factory Backend; handle: @frankzhu94/factory-backend; identity: b2f43e4e-7727-44bb-9154-6cdc2b781749; harness: Codex; model: gpt-6-astra
- frontend: Factory Frontend; handle: @frankzhu94/factory-frontend; identity: 5ba8923d-b3d9-4b56-818f-3bef60ea617d; harness: Codex; model: gpt-6-astra
- qa: Factory QA; handle: @frankzhu94/factory-qa; identity: 8e450576-69cd-416c-bc2a-a3a771f020d3; harness: Codex; model: gpt-6-astra
- reviewer: Factory Reviewer; handle: @frankzhu94/factory-reviewer; identity: 02e4a78d-7d9d-4c77-bf32-b3810a9cfacb; harness: Codex; model: gpt-6-astra

## Finite work limits
```json
{
  "ack_timeout_seconds": 120,
  "api_billing_allowed": false,
  "approved": true,
  "billing_mode": "subscription_only",
  "max_active_seats": 1,
  "max_repairs": 3,
  "max_total_tokens": 100000000,
  "max_turns_per_seat": 300,
  "overall_timeout_seconds": 70834,
  "paid_provisioning_allowed": false,
  "spend_cap_usd": null,
  "stage_timeout_seconds": 14400,
  "turn_timeout_seconds": 600
}
```

Budgets are ceilings, never permission to spend; approved must be true before live work.
Work stages in increasing order with an independent release gate for each exact commit.
Every later stage inherits every earlier specification included below.
PM assigns material work in the BAND room using the verified actual handles. Handoffs
carry requirements, owner, revision, paths, evidence, limitations and next recipient.
For oversized packets, number every part and obtain complete-set receipt before execution.
Keep all seven identities registered; keep implementation concurrency within the limit.
Use the assigned shared checkout with one active writer. Use separate worktrees only
after the operator has provisioned their writable roots and enabled parallel mode;
do not create worktrees under operator-owned runs. PM integrates attributable commits
without rewriting history.
Reviewer independently verifies a clean checkout of an exact integrated candidate.
Retain failed evidence; stop/replan after the repair ceiling or repeated identical failure.
This is unscored practice; eligibility is not claimed. Simulate an autonomous run:
use stage dispatch as the only human input, and do not solicit
steering, approvals or debugging hints. Report a blocker if unattended permissions fail.
Required outcome: genuine stage-N outputs, independent Dockerfile/RUN.md, requirement
coverage, own QA checks, designer evidence where applicable, official isolated harness
evidence, candidate acceptance, room event provenance, timing and available usage data.
The factory must never label an unobserved check successful or fabricate room exports.

## Toy rehearsal scope
Build only the official toy track in the assigned rehearsal checkout.
Exercise PM assignment, peer handoffs, engineer commits and fixed-candidate review.
Observe missing-peer and delayed-message handling without manufacturing a rejection.
Check every seat can see its assigned checkout and a committed change; preserve
directed replies for every seat and isolated final-container evidence.

## Exact official specification — toy/spec/stage-1.md
Source: /Users/frank/mygit/Tablekeeper/challenge/toy/spec/stage-1.md
SHA-256: b3fa4b5341480bc76e4d44a914e4503cbe96460a3d89504a5dd5e1d8fab42d2d

<!-- BEGIN EXACT SPEC toy/spec/stage-1.md -->
# `toy` — stage 1: a shared counter

Build a tiny HTTP service that stores one number. This practice exercise is unscored; it
exists to run the whole build-and-deliver loop once on something small.

## Deliverable

Create the service source, a `Dockerfile`, and a short `RUN.md` in one directory.
The command in `RUN.md` must build and start the service with no manual steps.
Stage 1 needs only an API. Any language or framework is fine; memory-only storage is
fine. The counter starts at **0** when the service starts.

Bind `0.0.0.0` and read the listening port from `PORT`, defaulting to `8080`.
Your `Dockerfile` is built and the container started, with up to 60 seconds to become
healthy. Limits: 2 CPUs, 2 GiB memory, 5 seconds per request (10 for reset).
Install dependencies during the Docker build; no internet is available at run time.

## Four endpoints

All endpoints are public. JSON responses use `Content-Type: application/json`;
adding `charset=utf-8` is fine.

| Request | Response | Effect |
|---|---|---|
| `GET /health` | `200 {"status":"ok"}` | None |
| `GET /counter` | `200 {"value":0}` | Returns the current value; does not change it |
| `POST /counter/increment` | `200 {"value":1}` | Adds exactly 1 and returns the new value |
| `POST /_test/reset` with `{"value":7}` | `204`, empty body | Replaces the value with 7 |

The numbers above are examples. All clients share the same counter. Two successive
increments from 7 return 8, then 9; the next read returns 9.

Increment accepts an empty request body or `{}`. Every request is a new increment.
Reset is synchronous: once it returns, the next read must see the seeded value.
Reset fixtures are always valid: an object with an integer `value` between 0 and
1,000,000. Reset is called repeatedly, and no earlier state may remain.

There are no accounts, passwords, tokens, idempotency keys, or database requirements.

<!-- END EXACT SPEC toy/spec/stage-1.md -->

## Exact official specification — toy/spec/stage-2.md
Source: /Users/frank/mygit/Tablekeeper/challenge/toy/spec/stage-2.md
SHA-256: 8b4800455e681bedcdded8407fb170766d5a73aa91de6feed65782ac3379b493

<!-- BEGIN EXACT SPEC toy/spec/stage-2.md -->
# `toy` — stage 2: one page, one button

Keep the stage 1 API working. The deliverable is unchanged: the service source, a
`Dockerfile`, and a short `RUN.md` in one directory, and the command in `RUN.md`
builds and starts the service with no manual steps.

Add a page at `/` with these two elements:

| `data-testid` | Element |
|---|---|
| `counter-value` | Visible text containing only the current integer, e.g. `7` |
| `increment-button` | A button that adds 1 |

On page load, read the value from `GET /counter`. Clicking the button calls
`POST /counter/increment` once and displays the returned value. Reloading the page
shows the server's current value, including increments made by another client.

Any layout is fine. Serve all assets from the container; no CDN is available at run
time. Elements are located by the exact `data-testid` values above and by nothing else.

Stage 1 must still pass.

<!-- END EXACT SPEC toy/spec/stage-2.md -->

## Exact official specification — toy/spec/stage-3.md
Source: /Users/frank/mygit/Tablekeeper/challenge/toy/spec/stage-3.md
SHA-256: 2b4e208b30ec0d505f8703bfec1dd38051d7b229868da37b13bab44abdaa485c

<!-- BEGIN EXACT SPEC toy/spec/stage-3.md -->
# `toy` — stage 3: no lost increments

No new endpoints and no new page elements. Stages 1 and 2 must still pass, unchanged.
What changes is the load: the same API is now called by many clients at the same
moment, and every call has to count.

## Concurrent increments

When 20 clients increment together, all 20 requests must return 200 and the counter
must increase by exactly 20. Each response returns the value immediately after its
own increment: starting at 7, the responses contain each integer from 8 through 27
exactly once, in any arrival order. No transport errors or 5xx responses are allowed.

The burst is repeated three times, from both zero and a nonzero seed.

Reading the value, adding one, and storing it is one operation, not three. Protect it
with a lock or use an atomic database update. Two requests that read the same number
and write the same number have lost an increment, and the final read will show it.

<!-- END EXACT SPEC toy/spec/stage-3.md -->

## Exact official specification — toy/spec/stage-4.md
Source: /Users/frank/mygit/Tablekeeper/challenge/toy/spec/stage-4.md
SHA-256: f27a23a7cad8f6fbfc67856ab1dab829b6b91908928ae32f4d41b0263525c955

<!-- BEGIN EXACT SPEC toy/spec/stage-4.md -->
# `toy` — stage 4: increment by a chosen amount

Stages 1, 2 and 3 must still pass, and that is most of the work.

`POST /counter/increment` accepts an optional `by` in its request body:

| Request body | Response | Effect |
|---|---|---|
| `{"by": 5}` from 7 | `200 {"value":12}` | Adds 5 |
| absent, `{}`, or `{"by": 1}` | `200 {"value":8}` | Adds 1, exactly as before |
| `{"by": 0}`, `{"by": -1}`, `{"by": "5"}` | `400`, any body | None — the value does not move |

`by` is an integer of 1 or more. Zero, a negative number, a string and a fraction are
all rejected with `400` and change nothing; the next request works normally. A request
with no body, or with `{}`, still means 1, which is why stages 1 to 3 keep behaving
identically.

The page from stage 2 is unchanged: its button still adds 1.

> **The stage-3 rule is the same in words and wider in effect:** nothing may be lost
> when 20 clients increment together. It now covers amounts, not just counts. Twenty
> clients sending `by` of 1 through 20 move the counter by exactly 210, and no two of
> them may be told the same value.

If the amount is added outside the lock, or read before the lock and written after it,
this is where it shows.

<!-- END EXACT SPEC toy/spec/stage-4.md -->

