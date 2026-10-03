# Build start status

The user authorized starting the Tablekeeper build on October 3, 2026. The
implementation must still be produced by the seven real BAND seats after the
required toy rehearsal. The current status is **BLOCKED_WITH_ACTIONS**; no judged
task or application code has been dispatched or generated.

## Current observed blockers

1. **BAND execution.** The native BAND 0.4.12 integration still times out during
   Codex 0.160.0 initialization, before inference. The maintained SDK can discover
   the model catalog, but the seven identities lack usable SDK credentials.
   Details and the supported Remote Agent alternative are recorded in
   `runs/build-start/native-integration-status.md` and its JSON evidence. Existing
   identities remain stopped; no silent roster substitution was made.
2. **Desktop access.** Computer control reports that the Mac is locked. Unlock it
   to inspect the signed-in BAND settings and complete the supported credential
   flow. Do not paste keys into chat or put them in the repository. The private
   credentials path is specified by `band.credentials_file` in the local config.
3. **Approved consumption.** The requested approval is for existing ChatGPT
   subscription access, no API billing or paid provisioning, one active seat,
   100,000 reported tokens and two hours across rehearsal and judged work.
   Approval has not been received, so `budgets.approved` remains false. Reported
   token accounting can overshoot within an in-flight turn; it is not a provider
   billing meter or a guarantee about remaining subscription quota.
4. **Execution environment.** A narrow Codex 0.160 named permission profile passed
   workspace writes, a Git commit, allowlisted dependency networking and localhost
   binding. It also denied an outside-workspace write. Chromium failed at macOS
   Mach bootstrap under Seatbelt. This candidate profile has not been adopted by
   the SDK runner and is not evidence that the seats have working permissions.
   See `runs/permissions-0160-541a77f31f/evidence.json` and `request.json`.
5. **Docker and rehearsal.** The configured OrbStack Docker daemon is stopped.
   Its installed CLI exposes no verified Docker-only start route; a general start
   may resume unrelated machines. Start the desired Docker service, then verify
   the exact seat environment, browser capability and isolated official toy
   harness. The toy rehearsal has not run.

## Completed preparation in this build-start attempt

- Retested the new native runtime without starting inference or changing seats.
- Exercised the candidate permission profile against real disposable probes,
  retaining both successful checks and failures.
- Updated the permission-probe command for the installed Codex 0.160 CLI syntax;
  the default remains the narrow built-in workspace profile.
- Prepared subscription budget enforcement with an approval gate and aggregate
  rehearsal/judged accounting. Local regression verification is recorded under
  `runs/build-start/`; it does not establish authenticated live model execution.
- Verified existing ChatGPT authentication and effective OpenAI provider settings
  through a non-inference account/config probe. The initial attempt was blocked
  by the outer preparation sandbox's access to Codex's local state database; the
  reviewed retry passed. Evidence: `runs/build-start/subscription-auth-probe.json`.
  No account sign-in, budget approval, saved configuration change or model turn
  was performed.

## Resume sequence

The full local utility suite passed **63 tests**. Structural validation and all
six task-packet checks passed. Doctor, freeze and launch preparation correctly
remain blocked, and the SDK supervisor reports `not_started`. See
`runs/build-start/verification-index.json`, `final-freeze.json` and
`final-launch.json`. The final budget fixture regression also passed 11 tests
using the versioned example, without requiring the ignored local config.

Resolve the credential flow and approve a finite budget. Configure and prove the
actual seat permission boundary, including the container/browser route. Regenerate
the exact task packets and matching observations after any configuration change.
Run the seven-seat toy rehearsal and record directed replies, attributable commits,
handoffs, fixed-candidate review, recovery and isolated harness evidence. Only after
a matching `READY_TO_LAUNCH` freeze may the PM receive the full Tablekeeper packet
once. The build authorization does not authorize repository publication or entry
submission.

The public event page still gives October 5, 2026, 23:59 PDT as the closing time;
account registration and submission access remain unverified. Source:
[official event page](https://lablab.ai/ai-hackathons/wearedevelopers-hackathon),
rechecked October 3, 2026. The pinned challenge was not refreshed.
