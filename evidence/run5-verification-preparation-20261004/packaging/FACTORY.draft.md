# MillieMoon factory — Run 5

> AI-assisted factual draft for participant review. Evidence cutoff: October 4, 2026, 2:14 PM PDT (`2026-10-04T21:14:01.903528Z`). Not a final outcome, human-authored claim or submission-ready artifact.

## Seats and execution

Seven distinct BAND identities use the supported Codex adapter. The frozen roster configures **Codex CLI 0.160.0**, **BAND SDK 4.0.0**, and **gpt-6-astra** throughout. Registration and connection are evidenced; the early launch receipts do not prove every seat has completed material Run 5 work.

| Seat | Responsibility | Exact BAND handle | Harness / model | Effort |
| --- | --- | --- | --- | --- |
| Factory PM | Scope, dependencies and integration | @frankzhu94/factory-pm | Codex / gpt-6-astra | medium |
| Factory Architect | Architecture and contracts | @frankzhu94/factory-architect | Codex / gpt-6-astra | high |
| Factory Designer | Journeys, interaction states and design review | @frankzhu94/factory-designer | Codex / gpt-6-astra | medium |
| Factory Backend | Service behavior, persistence and packaging | @frankzhu94/factory-backend | Codex / gpt-6-astra | medium |
| Factory Frontend | Client behavior and rendered implementation | @frankzhu94/factory-frontend | Codex / gpt-6-astra | medium |
| Factory QA | Independent requirement and boundary checks | @frankzhu94/factory-qa | Codex / gpt-6-astra | high |
| Factory Reviewer | Fixed-candidate release acceptance | @frankzhu94/factory-reviewer | Codex / gpt-6-astra | high |

## Design rationale and tradeoffs

Separate implementation, QA and release-review roles give required behavior an independent test and acceptance path. One active model seat limits shared-checkout write conflicts, at the cost of serial progress. Self-contained addressed handoffs carry requirements, revisions, paths and limits; multipart delivery needs complete-set acknowledgment. A receipt proves delivery, not correctness. The reviewer inspects a clean exact candidate and returns repairs to its owner.

Run 4 showed why supplied green checks are insufficient: 120/120 official isolated checks passed, but independent review rejected valid dates below year 1000 because generated year strings lost required leading zeros. The run stopped after three repairs. No accepted stage or later-stage completion is carried into Run 5.

The revised generic workflow asks QA to derive boundary classes before implementation, engineers to test shared parsing/formatting/comparison/serialization in the target environment, and reviewers to collect independently reproducible findings within the review budget. It specifies a process, not application code or expected hidden-test answers. The PM's initial QA assignment and its complete receipt are observed; the effect on final product quality is not yet established. The revised workflow was not separately live-rehearsed before Run 5.

## Setup and reproducibility

The official challenge is pinned at `803560d2a678ace1414465c098eb0ab5380ffade`. Reuse the factory's locked dependencies, absolute workspace configuration and seven seat mandates; keep credentials in restricted storage outside every repository. Prepare an empty independent checkout and a fresh room, bind the exact canonical repository/attempt branch, verify registration and actual-adapter permissions, then generate deterministic full-spec packets and require a READY freeze with finite approved limits. Historical permission or rehearsal observations are not a substitute for new environment checks.

Run 5 uses `/Users/frank/mygit/Tablekeeper/result-run-5`, branch `run-5`, and room `12cde259-0fcd-4551-84c7-52c443cb5600`. Factory tools remain outside the product checkout. A clean checkout is required for every reviewed candidate. Product reproduction instructions and final artifact hashes must be added only after the final evidence is available.

## Approved limits, start and cost reporting

Approval was observed at **2026-10-04T20:59:53Z**. Exactly one initial task was dispatched at **2026-10-04T21:06:55.943682Z**, event `d5861cdd-0b57-4393-a97f-0dfb9201cec2`. Its frozen packet SHA-256 is `85ceb4e9574bf3e63355017708eff69b9894688732082e2f3c4af142ff9f9178`.

| Limit or measurement | Recorded value |
| --- | --- |
| Preserved cumulative baseline | 145,683,099 reported tokens |
| Remaining tokens authorized for Run 5 | 140,328,478 at approval |
| Unchanged cumulative ceiling | 286,011,577 reported tokens |
| Unchanged deadline | October 4, 2026, 7:35:03.700437 PM PDT; `2026-10-05T02:35:03.700437Z` |
| Original accounting origin | Epoch `1791049765.700437`; retained, not restarted |
| Concurrency | One active model seat |
| Turn / acknowledgment limit | 600 seconds / 120 seconds |
| Repairs / seat turns | Three repairs per work item / 1,000 cumulative turns per seat |
| Room limit | 28,800 seconds, also bounded by the earlier unchanged overall deadline |
| Billing authority | Existing ChatGPT subscription; API billing and paid provisioning disabled |

Reported tokens include cached input and do not measure subscription quota or dollars. The initial `21:09:12Z` snapshot recorded 272,421 Run 5 tokens; it is not a final total. Final elapsed time, total Run 5 usage and monetary cost are not established in this draft. The observed baseline and every prior room stop remain preserved.

## Failure handling and unfinished evidence

Required failures remain rejecting even if a supplied suite passes. Repair, time and consumption ceilings do not renew themselves. The historical transport repair checks local SDK queue activity before issuing a notice and routes genuine missing-part recovery through the original recipient; its separate rehearsal is transport evidence, not Run 5 product acceptance. An unknown or unavailable required operation must produce an evidenced blocker.

Still needed: final exact candidate and independent stage decisions; completed stage reproduction and isolated reports; full-session export with provenance/privacy review; final usage reconciliation; final packaging checks; real-room video and presentation; participant authorship resolution; and explicit public-release/submission authorization. These drafts make no final acceptance or submission claim.
