# Run 5 post-run verification plan

**Preparation only — no checks in this plan have been run.** Execute after the coordinator's final report and closure of the active run. Do not send these notes or debugging hints into the judged room, alter its product code, or change frozen factory inputs. A failed check is retained as a failed outcome; it is not permission to repair the judged result manually or redispatch it.

This extends the existing [final checklist](/Users/frank/mygit/Tablekeeper/factory/submission-templates/final-checklist.md), [candidate acceptance record](/Users/frank/mygit/Tablekeeper/factory/templates/candidate-acceptance.md), [verification plan template](/Users/frank/mygit/Tablekeeper/factory/templates/verification-plan.md) and [rendered design review](/Users/frank/mygit/Tablekeeper/factory/templates/design-review.md). Fill those records rather than inventing another acceptance format. The [completion baseline](/Users/frank/mygit/Tablekeeper/runs/run5-preparation-20261004/observation/goal-completion-baseline.json) distinguishes existing preparation proof from unfinished product work.

## Preconditions and candidate

- Preserve the final coordinator report, exact accepted/rejected commits, failed attempts, complete handoffs and closed consumption ledger. Keep original per-stage outputs and commit history; do not squash, amend, rebase or copy the final solution backward.
- Assemble the selected attempt's real completed stage folders, seven actual mandates, final narratives and genuine full-session export. A missing or unfinished stage remains incomplete. The user's all-four-stage goal is not satisfied by a lower-stage partial result.
- Inspect for credentials/private values before pushing new artifacts. Existing private progress pushes are authorized; public visibility and final submission are separate actions.
- Select the full final package commit on the canonical `run-5` branch. Use a new clone and clean detached checkout; record its full SHA, not only a mutable branch name. Do not import product code from prior attempts.
- Use the existing Python 3.13 harness environment, pinned challenge commit `803560d2a678ace1414465c098eb0ab5380ffade`, running Docker daemon and prepared browser prerequisites. The current Docker socket is `unix:///Users/frank/.orbstack/run/docker.sock`. Installation/model authentication proof is not application proof. Do not refresh upstream tests/specs while validating this frozen result.

The following are **future commands**, not execution evidence. Set `RUN5_CANDIDATE_SHA` to the final reviewed full commit before running them. `mktemp` supplies a fresh directory; the harness output directory must not already exist.

```sh
set -eu
RUN5_CANDIDATE_SHA='REPLACE_WITH_FINAL_FULL_COMMIT'
RUN5_VERIFY_ROOT="$(mktemp -d '/Users/frank/mygit/Tablekeeper/runs/run5-final-XXXXXX')"
RUN5_CHECKOUT="$RUN5_VERIFY_ROOT/result"
RUN5_HARNESS_PY='/Users/frank/mygit/Tablekeeper/runs/harness-venv/bin/python'

git clone --single-branch --branch run-5 \
  https://github.com/Xuefeng-Zhu/Tablekeeper.git "$RUN5_CHECKOUT"
git -C "$RUN5_CHECKOUT" checkout --detach "$RUN5_CANDIDATE_SHA"
test "$(git -C "$RUN5_CHECKOUT" rev-parse HEAD)" = "$RUN5_CANDIDATE_SHA"
test -z "$(git -C "$RUN5_CHECKOUT" status --porcelain)"

cd '/Users/frank/mygit/Tablekeeper/challenge'
"$RUN5_HARNESS_PY" -m harness check "$RUN5_CHECKOUT" --track tablekeeper
DOCKER_HOST='unix:///Users/frank/.orbstack/run/docker.sock' \
  "$RUN5_HARNESS_PY" -m harness run --track tablekeeper \
  --repo "$RUN5_CHECKOUT" --all --mode isolated \
  --out "$RUN5_VERIFY_ROOT/isolated-all"
```

Stop if HEAD is not the selected SHA or the checkout is dirty. For a separately necessary stage-specific verification, use the documented form below with a new output path and the actual stage number; do not redundantly rerun successful checks without a changed candidate or unresolved concern.

```sh
DOCKER_HOST='unix:///Users/frank/.orbstack/run/docker.sock' \
  "$RUN5_HARNESS_PY" -m harness run --track tablekeeper \
  --repo "$RUN5_CHECKOUT" --stage 2 --mode isolated \
  --out "$RUN5_VERIFY_ROOT/isolated-stage-2"
```

`--repo` automatically uses the repository's own preceding stage folders for upgrade sources. Do not substitute `--previous-build`, `--previous-base-url`, `--stages`, another attempt, or a host service. These forms are grounded in [the participant guide](/Users/frank/mygit/Tablekeeper/challenge/docs/participant-guide.md:557) and [the pinned CLI parser](/Users/frank/mygit/Tablekeeper/challenge/harness/cli.py:515).

## Automated gates and their limits

| Check | Actual evidence required | What it does not establish |
|---|---|---|
| Official `harness check` | Exit status and captured output from final clone; valid layout, stage Dockerfile/RUN.md, full-room shape, matching mandate names and Harness/Model metadata, reciprocal mentions, generic vocabulary and credential-pattern scan | Builds nothing; cannot establish product behavior, participant authorship, all private values or semantic genericity |
| Official `harness run --repo … --all --mode isolated` | Unique report directory, `report.json`, stage logs/counts, actual collected tests, build/startup/exit results and claimed-stage chain at selected SHA | Shipped tests are partial; green results do not prove the entire specification or hidden judging outcome |
| Independent band-authored checks and Reviewer gate | Exact candidate, complete applicable requirements, independent expected results, reproductions, all defects resolved or explicitly rejected; distinct Reviewer did not repair its own candidate | A passing subset, self-review or changed checkout cannot stand for release acceptance |
| Stage provenance | Separate complete buildable folders, sequential band-authored commits and inherited suites; no nested `.git`, symlinks or submodules | A later implementation copied into earlier folders does not demonstrate stages |

No skipped/deselected/empty suite, missing browser or startup error is a pass. Preserve failures. Record argv, working directory, UTC start/end, environment, full candidate SHA, exit code, counts and absolute artifact paths. Keep reports outside the clone so checks do not silently change the candidate. The organizer's stage-credit threshold is not the user's full-behavior completion standard.

## Required independent behavior coverage

Use the exact linked specifications as the oracle, not this condensed matrix. Review the team's requirement map and tests for missing classes before claiming completion.

| Stage | Behaviors requiring evidence beyond a sample-suite claim |
|---|---|
| [1](/Users/frank/mygit/Tablekeeper/challenge/tablekeeper/spec/stage-1.md) | Authentication and owner isolation; reset/fixtures/errors; restaurant discovery, availability, booking/read/cancel/amend; concurrent occupancy and atomic moves; complete idempotency scope, equality, error precedence and original receipts; valid calendar range, IANA offsets, DST gaps/folds and absolute duration; atomic read-only export, replacement import, independent-process portability and unchanged destination on invalid import |
| [2](/Users/frank/mygit/Tablekeeper/challenge/tablekeeper/spec/stage-2.md) | All stage1 behavior; approved pairs and ordering/capacity/occupancy; single/pair create/amend/cancel/moves under concurrency; real signup/login/search/booking/confirmation/lookup; out-of-order search, conflict refresh preserving form inputs, lost committed responses and same-key/body retry; retained sessions/reference/pending retry across stage1→2 import |
| [3](/Users/frank/mygit/Tablekeeper/challenge/tablekeeper/spec/stage-3.md) | All prior behavior/UI; availability explanations; owner-only truthful ordered history/decisions; manager-only immutable effective-dated policies and tie selection; frozen accepted terms, no-op/replay invariants and stale revisions; atomic recurring adoption, calendar/DST progression, individual exceptions/cancellations, combined-table history and collective moves; imports from stages1–2 |
| [4](/Users/frank/mygit/Tablekeeper/challenge/tablekeeper/spec/stage-4.md) | All prior behavior/UI; authorized closure preview without occupancy/history changes; deterministic objective order (fewest moved bookings, unused seats, option-rank vector); atomic apply preserving accepted terms/times/identities, stale/already-applied/replay rules and concurrency; closures in future decisions; atomic recurring amendment with revision/error precedence, exclusions/no-ops/exception preservation; imports from stages1–3 |

For every stage independently prove the container contract: self-contained single image, `PORT`/default8080 on `0.0.0.0`, readiness within 60 s, 2 vCPU / 2 GiB, up to 50 concurrent requests and specified 5 s / 10 s timeouts. Runtime has no outbound network; fonts/scripts/styles and other dependencies must be bundled. Build-time downloads and the factory's allowed development networking are distinct. Use the official isolated network, which permits tester-to-service access, rather than improvised isolation that prevents all HTTP access.

## Manual startup, browser and upgrade checks

These remain **unverified until performed and recorded**, even if automation passes.

1. Follow each completed stage's own `RUN.md` from the clean clone, with fresh stage-specific resources and no undocumented host services or manual setup. Record build/run commands, health timing, environment and cleanup. All required services must live in the image; Compose is not used by the judge. Do not reuse another stage's running container or data.
2. For stage2 and later, use actual `/`, `/signup`, `/login` and `/lookup` routes. Exercise signup/login/logout, single/pair availability, booking, repeat submission, confirmation, lookup/cancel and refused operations. Confirm human-readable labels and server-authoritative outcomes. Retain exact required testids from the source.
3. Inspect 375 CSS-pixel and conventional desktop viewports: no horizontal page scrolling, coherent hierarchy, visible labels and focus, keyboard operation, adequate contrast and clear available/unavailable/selected/loading/empty/success/refusal/uncertainty states. Use the existing design-review record and real screenshots/footage of the tested candidate.
4. Reproduce late search responses, a table taken after the form opens, and a response lost after commit. Confirm no false success, preserved inputs, nonempty uncertainty feedback, identical retry identity/body and recovery of the original reference. Prefer the team's attributable independent browser checks; record any manual network fault method and its scope.
5. Use populated exports from the same team's actual earlier-stage images, not hand-recreated fixtures. Verify old sessions/password login, references, receipts/retries and histories survive import; then exercise the new stage's operations. Keep a browser/form alive through the documented stage1→2 import between requests. Later-stage policy/series/history/closure state must remain truthful. Missing shipped coverage remains an explicit gap until independently checked.
6. Treat exported product accounts/session tokens as private test artifacts. Use synthetic data and keep raw state exports out of public evidence unless reviewed. Export/import is not a live external-service or persistence-across-restart requirement.

## Evidence and final package

After the run ends, use the documented [full-room workflow](/Users/frank/mygit/Tablekeeper/factory/docs/rules-review.md) and [official steps](/Users/frank/mygit/Tablekeeper/challenge/docs/participant-guide.md:645): Band console → room menu → Download → Download full session. Save the genuine download unchanged as root `room.json`; preserve download time/hash. Native paginated snapshots and filtered downloads do not substitute. Refresh if later room activity occurs. Do not delete failures or substantive collaboration evidence.

Inspect all tracked content, history and the export for private values; the official scanner is only a pattern check. If a credential is exposed, follow the guide's rotation and narrow `[REDACTED]` incident procedure with a record, not a silent history rewrite.

Complete the existing README/FACTORY, demo, slide and description templates with actual run facts: seven seats/runtime, reproducible setup, design choices, observed failure handling, completed stage scope, exact evidence, measured elapsed time and reported-token deltas. Mark unmeasured USD cost unavailable. User-authorized drafting must not invent participant experiences or claim unreviewed participant authorship. The guide's participant-written narrative requirement remains visible for review.

The presentation and video must show the real room, meaningful handoff/review and produced result; check playback and legibility. Final file layout is defined by the existing [repository layout template](/Users/frank/mygit/Tablekeeper/factory/submission-templates/REPOSITORY-LAYOUT.md), not by invented placeholders.

Conclude with an exact-candidate result: VERIFIED scope, failed/untested requirements and next authorized action. Public visibility, public judge-access confirmation and final submission/receipt follow only after their respective authority and a concrete reviewable package. The current one-dispatch approval does not authorize them. Preserve the observed event deadline of October 5, 2026, 23:59 PDT separately from the factory's earlier runtime cutoff, October 4, 19:35:03.700437 PDT.


Prepared at 2026-10-04T21:25:04.966265+00:00. No harness, product test, message, publication or live-file edit performed.
