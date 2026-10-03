# Subscription-only consumption policy

This optional policy is implemented but **not approved or enabled** in the local configuration. It permits only existing ChatGPT authentication for model work; API billing and paid provisioning are outside its authority. It does not promise zero charges, a subscription entitlement, remaining quota, or a measured dollar spend.

After the human explicitly approves the limits, the operator may select these fields alongside the existing finite limits. The example deliberately remains unapproved:

```yaml
budgets:
  billing_mode: subscription_only
  approved: false
  api_billing_allowed: false
  paid_provisioning_allowed: false
  spend_cap_usd: null
  max_active_seats: 1
  max_repairs: 2
  ack_timeout_seconds: 60
  turn_timeout_seconds: 180
  stage_timeout_seconds: 1800
  overall_timeout_seconds: 7200
  max_turns_per_seat: 20
  max_total_tokens: 100000
```

Omitting `billing_mode` retains the existing `spend_cap` policy, which needs an approved positive numeric `spend_cap_usd` and independent provider billing enforcement. Neither mode accepts open-ended token/time/turn limits. Approval must be a boolean; strings cannot grant authority.

Subscription runtime first runs plain `login status`, requiring the existing ChatGPT login before applying forced authentication settings. It then performs only `initialize`, `account/read` with `refreshToken:false`, and `config/read` for all configured workspaces. It verifies the effective OpenAI provider and ChatGPT authentication; no account email, token, full config, or raw provider exception is logged. API-key, external-token, workload-identity and endpoint environment overrides are rejected. The subprocess command uses `/usr/bin/env -u` to remove those variables because BAND merges its environment with the parent environment. It pins `forced_login_method="chatgpt"`, `model_provider="openai"`, and `openai_base_url=""`. Discovery remains an unconstrained read of the existing account; it cannot authorize a launch.

These config pins are supported by [the official config reference](https://developers.openai.com/codex/config-reference/) and the exact [CLI 0.160.0 configuration source](https://raw.githubusercontent.com/openai/codex/rust-v0.160.0/codex-rs/core/src/config/mod.rs). The pinned version preserves the built-in OpenAI provider rather than replacing it from `model_providers.openai`; managed provider differences still fail the effective-config check. Revalidate on any CLI update. No sign-in, logout, token-refresh request, purchase or billing-setting mutation is part of the probe.

`runs/runtime/budget-subscription.json` aggregates observed tokens and per-seat admitted turns across both rehearsal and judged rooms. Its overall clock starts with the first admitted turn and persists across room changes and restarts, including idle wall time. Each room has its own persistent conservative stage clock starting on its first turn; all stages in that room share that ceiling. A room stage timeout cannot renew the aggregate allowance. Old per-mode ledgers or changed room scope fail closed pending explicit consumption reconciliation. `seat-status` reports the shared counters and room clocks. Do not delete or move ledgers to renew approved limits.

The runner stops admitting turns when observed tokens reach the cap; delayed usage events and an in-flight turn can overshoot it. Turn and supervisor timeouts include bounded shutdown grace. These are local consumption controls, not provider billing controls. Existing `workspace-write`, network denial and auto-declined approvals remain prerequisites; the policy does not grant cloud provisioning or spending authority.

Verification: ` .venv/bin/python -m unittest tests.test_budgets tests.test_runtime tests.test_toolkit` passed **61 tests**. Tests use mocked authentication responses and temporary ledgers; they cover missing approval, forbidden auth paths, effective provider mismatch, redacted failures, cross-room/restart accounting and independent room stage clocks. The first constrained probe could not initialize Codex state under the outer preparation sandbox. A reviewed retry with access to Codex local state passed the existing-login, account and effective-provider checks without inference; see `runs/build-start/subscription-auth-probe.json` (2026-10-03 07:38:48 UTC). The full utility suite subsequently passed 63 tests; its evidence is `runs/build-start/verification-00.json`. No subscription model turn has been verified, no actual configuration approval was changed, and spend remains unavailable.
