# Run 8 preparation

Status: **PREPARING — no model task has been dispatched**.

The user continued the proposed eight-hour rehearsal and Run 8 plan at `2026-10-05T16:12:31Z`. The effective runtime deadline is `2026-10-06T00:12:30.700437Z` (October 5 at 5:12 PM Pacific). The cumulative token ceiling remains 786,011,577, with 352,490,036 already reported. The original accounting epoch and all per-seat, per-room and per-thread counters are retained. GPT-6.1 Sol, one active seat, subscription-only access, no API billing or paid provisioning, and the 2,048 MiB VM cap remain the selected policy.

Factory repair [PR #3](https://github.com/Xuefeng-Zhu/Tablekeeper-factory/pull/3) was merged at `da755fb`. It batches complete authenticated handoffs before model admission and validates protocol text before sending. Its 416 passing offline tests and independent reviews are preparation evidence; live operation still requires the focused rehearsal.

The separately scoped **MillieMoon · Handoff Regression** room (`1d029d57-a8fb-4b52-9d50-2c7493d09f5f`) contains Frank and the seven existing seats. Only PM and Backend have test assignments. The synthetic drill is capped at ten minutes from dispatch and 2,000,000 additional reported tokens within the outer allowance. A complete twelve-part assignment, an identical duplicate and one deliberately invalid local ACK tool input exercise the two fixes. The malformed input must never become a room message; the actual recipient must correct it in the same admitted turn. This establishes communication behavior only, not product acceptance.

The empty Run 8 room is `bc239798-6ec2-4fc0-a4a6-dedc6c7b6713`. Its product checkout is `/Users/frank/mygit/Tablekeeper/result-run-8`, on an unborn `run-8` branch with the existing `Xuefeng-Zhu/Tablekeeper` origin. A fresh remote read found no published `run-8` branch. No prior product implementation was copied into it. The factory is isolated from the shared checkout's unrelated work.

Fresh current permission, registration, model and resource evidence must pass before rehearsal. A passing rehearsal, reconciled accounting, source integrity, generated packets and independent readiness review must then precede the one authorized judged dispatch. The historical completed toy checkout/export remain separate; this drill must not be relabeled as a completed toy or product stage.

Run 7 is preserved unchanged at its stopped incident and consumed dispatch. Local preparation records are under `runs/run8-preparation-20261005` and `runs/handoff-regression-20261005`; they are not a passing freeze or completed run.
