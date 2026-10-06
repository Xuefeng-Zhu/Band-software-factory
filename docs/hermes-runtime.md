# Hermes OpenCode factory

The Hermes attempt uses a separate Linux ARM workspace under
`/home/azureuser/Tablekeeper-hermes`. Its source snapshot includes the reviewed
factory changes; cloning an older remote commit alone is insufficient. Existing
Hermes services, OpenCode installations, local runs and result repositories are
outside this attempt.

The current normal attempt is `hermes-glm-normal-20261005T215631Z`, with
configuration SHA-256
`6684a00de0f8a40b69495c556e74aa8f02b28c33b6e5427268e56a6b726e0704`.
The user approved only the existing $25 cumulative allowance as the consumption
cap. Set both `budgets.balance_only: true` and
`runtime.featherless_budget_guard.balance_only: true`, with
`runtime.strict_membership_recovery: false`. Retain the approved, hash-bound
allowance amendment and all accumulated usage and original accounting epochs.
Do not purchase credits, enable automatic top-up, reset ledgers or discard the
earlier failed rehearsal evidence.

The latest recorded provider charge is $0.091985580 and the remaining balance is
$24.908014420. These provider values are separate from the guard's conservative
charge calculation. This preparation record does not establish that the paid
normal rehearsal or the full task has been dispatched.

## Runtime and roles

Install the latest stable official Linux ARM64 OpenCode archive into a versioned
directory, verify its published SHA-256, and record the executable's own SHA-256
and `--version` in `runtime-install.json`. Keep BAND SDK 4.0.0 and the locked Python
dependencies. Set `runtime.opencode_version`, `runtime.opencode_sha256`, and a
private `runtime.opencode_state_root` within the new run directory. The factory
checks the actual server version and resolved model routing before use.

Use GLM-5.3 for PM, Architect, Backend and Reviewer; use GLM-5.3-Flash for Designer,
Frontend and QA. Prepare these with the repeatable `--seat-model` options in
[runtime-selection.md](runtime-selection.md). Each seat's main and auxiliary
model must remain on its assigned Featherless route. Do not enable fallback.

Set `runtime.execution_platform: linux` before generating task packets. Rebuild
dependencies on Hermes; do not copy Mac virtual environments or browser binaries.
Preserve pinned challenge and reference-document bytes in a new host-specific
source lock. Do not import Mac global configuration or refresh historical locks.

## Credentials and provider evidence

Use fresh external BAND identities and distinct rehearsal/full-attempt rooms.
Keep the result repository empty until dispatch. Store credentials only in an
owner-only directory outside the configured workspaces, with files mode 0600.
Never put keys in configuration YAML, terminal arguments, logs or run evidence.

`factorykit.featherless.preflight` performs read-only authenticated checks for the
plan, both model IDs, current credits and usage. Pin the observed plan ID only
after reviewing the account's request-pricing terms. Account evidence must also
establish that automatic top-up is disabled and only existing credit is allowed.
The helper deliberately does not infer these terms from a plan name or ID.

Populate provider model metadata from authenticated results, including positive
context/output limits and prices. Missing tools, model access, concurrency,
limits or billing evidence blocks inference. Sanitized evidence is suitable for
the run directory; raw provider responses and credentials are not.

Save the complete sanitized, passing preflight result as
`<paths.runs>/readiness/featherless-model-metadata.json`. Its `models` object must
contain exactly `zai-org/GLM-5.3` and `zai-org/GLM-5.3-Flash`. Do not substitute
public model-card limits or advertised prices for authenticated results. A
discovery result with an unreviewed plan ID is still `BLOCKED` and cannot be used
as this evidence file. The API does not verify auto-top-up; retain the separate
account-setting evidence supporting the caller's billing attestation.

## Bind the request guard

Merge the following structure into the attempt's configuration before regenerating
packets or collecting configuration-bound readiness evidence. Placeholder values
below must be replaced with the observed values; they are not model defaults.

```yaml
budgets:
  billing_mode: spend_cap
  accounting_scope: session
  approved: true
  spend_cap_usd: 25
  balance_only: true
  # Historical finite-mode fields remain required schema values; they do not
  # impose consumption stops in the approved balance-only mode.
  max_total_tokens: 2000000
  overall_timeout_seconds: 21600
  max_active_seats: 1
  turn_timeout_seconds: 900
  # Keep the other required historical schema fields in the configuration.

runtime:
  harness: opencode
  execution_platform: linux
  strict_membership_recovery: false
  model: featherless/zai-org/GLM-5.3
  opencode_state_root: /absolute/new-run/attempts/new-attempt/runtime/opencode
  opencode_provider:
    id: featherless
    npm: '@ai-sdk/openai-compatible'
    base_url: https://api.featherless.ai/v1
    api_key_env: FEATHERLESS_API_KEY
    models:
      zai-org/GLM-5.3:
        id: zai-org/GLM-5.3
        limit:
          context: <effective_context_length from this model's evidence>
          output: <effective_max_completion_tokens from this model's evidence>
      zai-org/GLM-5.3-Flash:
        id: zai-org/GLM-5.3-Flash
        limit:
          context: <effective_context_length from this model's evidence>
          output: <effective_max_completion_tokens from this model's evidence>
  featherless_budget_guard:
    balance_only: true
    time_renewal:
      path: <absolute path to the approved cumulative allowance amendment>
      sha256: <SHA-256 of the exact approved amendment bytes>
    ledger: /absolute/new-run/runtime/featherless-requests.json
    model_metadata: /absolute/new-run/readiness/featherless-model-metadata.json
    model_metadata_sha256: <SHA-256 of the exact saved evidence file bytes>
    approved_credit_nano_usd: 25000000000
    max_total_tokens: 2000000
    overall_timeout_seconds: 21600
    request_timeout_seconds: 900
```

Replace `/absolute/new-run` with the same absolute `paths.runs` value throughout.
For this normal attempt, `paths.runs` and both accounting ledgers retain the
original shared run; fresh task artifacts and private OpenCode state live under
the new attempt directory. Do not create an empty replacement accounting ledger.
The ledger must be below its `runtime` directory; the evidence must be below the
run directory. The private OpenCode state directory must have mode 0700. Copy
each model's effective context/output limits exactly into `limit`; the loader
rejects mismatches. The metadata binding is the SHA-256 of the file bytes, not a
hash of parsed or reformatted JSON. For example, compute it without opening any
credential file:

```sh
sha256sum /absolute/new-run/readiness/featherless-model-metadata.json
```

For a new allowance, `approved_credit_nano_usd` must not exceed the authenticated
available credit, the approved factory spend cap, or 25,000,000,000. For the
existing shared allowance, preserve its original cumulative $25 ceiling and
include every prior charge and outstanding reservation. A lower current balance
does not reset the allowance or authorize more credit. In optional finite mode,
request token/time limits may be lower than factory limits but cannot exceed
them. In balance-only mode, those historical fields do not stop work. Changing
prices or the ledger filename does not renew authorization. A used or uncertain
request ledger cannot be cloned with `runtime-select`.

The runtime owns one guard around all seven OpenCode servers. The configured
HTTPS upstream is replaced in child configuration by a random-port loopback
route. Children receive a random guard credential; the real Featherless key
stays with the parent proxy. Main, small, title, summary and compaction model
routes remain on the seat's assigned model through this same guard. A separate
catalog-discovery context reuses the ledger and starts no inference clock.
Do not configure a direct provider route or fallback for auxiliary calls.

## Shared accounting and conservative stops

Use `budgets.billing_mode: spend_cap`, `budgets.accounting_scope: session`, and
both balance-only flags for the current normal attempt. The earlier six-hour,
2,000,000-token and 900-second-turn settings describe historical or optional
finite mode. Elapsed time, token totals, turn and repair counts, and recovery/ACK
windows do not stop the approved normal practice. Role identities, permissions,
model routes and authenticated provider concurrency still apply. Charge all paid
verification, rehearsal and execution to the same retained ledgers. Restarts
preserve accumulated consumption and original epochs, without using those epochs
to expire balance-only work.

Two ledgers describe overlapping consumption. `runtime/budget-session.json`
records admitted factory turns and SDK-reported tokens by room and seat. The
configured request ledger accounts for every proxied HTTP inference request,
including auxiliary requests absent from SDK turn telemetry. Do not add their
token totals together. Both survive phase changes and restarts. In balance-only
mode, dollar enforcement and unresolved accounting can stop work; historical
time, token and turn thresholds cannot. The factory clock begins at first
admitted turn; the guard clock begins at the first durably reserved request,
before forwarding. Paid
verification must use both paths; a direct standalone provider smoke call would
escape this combined accounting and is not part of the workflow.

For each accepted request, the guard reserves the model's entire effective
context length plus the bounded completion allowance for usage accounting and,
in finite mode, against the token cap.
Its money reservation is the sum of the full-context prompt cost, maximum
completion cost, and any flat request fee. Each component is calculated exactly
and rounded upward to whole nano-USD. The outgoing `max_tokens` is the minimum
of the pinned ceiling and either caller-supplied output bound; the alternate
`max_completion_tokens` spelling is removed. Only the two exact model IDs and
one completion per request are accepted.

After complete, valid usage arrives, the guard replaces the reservation with
reported prompt/completion tokens and a conservative charge at the pinned
uncached prompt rate. It does not claim the provider invoice equals
`charged_nano_usd`: cached input discounts and provider settlement may make the
actual charge lower. Held amounts represent possible liabilities, not measured
charges. The guard may stop below $25 of calculated charges when the next
worst-case money reservation no longer fits. Optional finite mode can also stop
before its token ceiling. Preserve the cumulative dollar ceiling; do not bypass
it with a smaller fresh ledger.

Streaming requests force `include_usage: true`. Duplicate usage reports within
one request are accounted once, using the largest reported counts. A request
error, disconnect, timeout, missing final usage, incomplete stream or unfinished
record on restart retains the full reservation and persistently stops further
forwarding. Do not retry, delete the record or treat the request as free; retain
the evidence for reconciliation. The proxy itself makes no provider retries.
Preflight, freeze and launch inspect the persisted guard as well as the factory
ledger. The supervisor checks it before admitting a turn and on every heartbeat;
a guard stop, including one caused by an auxiliary request, halts owned seats.
`seat-status` includes `request_guard_blockers` even before a supervisor starts.

This is enforcement against the authenticated prices and token ceilings pinned
for this attempt. It assumes the provider honors those rates, context limits,
output limits and usage semantics; it cannot prevent a provider changing its
prices or spending by unrelated account clients. Keep account-wide billing
observations separate. The provider documents credit reservations and settlement
windows of up to five minutes, so a balance snapshot alone cannot enforce the
run's dollar cap. See [Featherless credit accounting](https://featherless.ai/docs/api-reference-credits)
and [usage accounting](https://featherless.ai/docs/api-reference-usage-activity).

## Visual capability boundary

The current guard accepts text and tools and rejects image, video and audio
inputs before forwarding; it never silently drops them. This is a guard
limitation, not a claim that both models lack vision. The official
[GLM-5.3 model card](https://huggingface.co/zai-org/GLM-5.3/blob/main/README.md)
describes text generation. The official
[GLM-5.3-Flash model card](https://huggingface.co/zai-org/GLM-5.3-Flash/blob/main/README.md)
describes a multimodal model and demonstrates image input.

[Featherless's vision documentation](https://featherless.ai/docs/vision)
describes `image_url` requests, but it does not establish that this route's image
consumption is included in the returned `prompt_tokens` under the same pinned
context bound. A zero `pricing.image` field alone does not prove that accounting
contract. Vision requires that proof and authenticated model capability evidence
before extending the guard. Browser automation, screenshots saved to disk, DOM
assertions and textual test results do not establish that a model inspected the
pixels. Do not report visual-review acceptance from this text-only guarded run.

## Acceptance

Host checks establish installation and capability only. Actual agent permission
checks, both-model tool use, directed replies, complete handoffs, independent toy
review, official isolated tests and the full toy room export are required before
freeze. Dispatch the full practice attempt once after readiness, then preserve
actual usage, failed checks and independently accepted stage results.
