# Judged dispatch packet — tablekeeper

Packet state: REQUIRES_READY_FREEZE
Dispatch mode: separate; stages: 1.
Execute only stage 1. Earlier specifications are inherited requirements, not new dispatches. Do not execute a future stage until its own separate dispatch.
This file is preparation only. Do not dispatch before the freeze reports READY_TO_LAUNCH.
Pinned challenge commit: 803560d2a678ace1414465c098eb0ab5380ffade
Configuration SHA-256: 854b7a57d6f48adbb6580f42c101f18fb171e9be490c47ed6237d03179122600

## Absolute workspace paths
- challenge: `/Users/frank/mygit/Tablekeeper/challenge`
- factory: `/Users/frank/mygit/Tablekeeper/factory`
- rehearsal: `/Users/frank/mygit/Tablekeeper/rehearsal/toy-result`
- runs: `/Users/frank/mygit/Tablekeeper/runs`
- result: `/Users/frank/mygit/Tablekeeper/result`
- Assigned output checkout: `/Users/frank/mygit/Tablekeeper/result`

## Execution environment
- Writable product checkout and Git metadata: `/Users/frank/mygit/Tablekeeper/result`. One active writer is enforced.
- Store team test logs, screenshots and results under `/Users/frank/mygit/Tablekeeper/result/.evidence` in unique run directories; keep generated caches out of commits.
- Use the platform temporary directory for clean exact-candidate review clones outside stage folders and for dependency caches. Read-only access to sources and factory tools does not grant write access to their directories.
- The runs directory contains operator-owned control records. Do not alter launcher, usage, dispatch or readiness files or attempt to broaden permissions.
- Pinned harness interpreter: `/Users/frank/mygit/Tablekeeper/runs/harness-venv/bin/python`. Run the official `-m harness run` from the challenge directory, with `--track tablekeeper`, an absolute `--repo` and `--out` inside your writable evidence directory. Use `--mode isolated` for acceptance; inspect its `--help` for the exact stage options.
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
  "max_total_tokens": 1000000,
  "max_turns_per_seat": 100,
  "overall_timeout_seconds": 28800,
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
Use separate worktrees under runs only after the first BAND-authored commit; otherwise
enforce one writer. PM integrates attributable commits without rewriting history.
Reviewer independently verifies a clean checkout of an exact integrated candidate.
Retain failed evidence; stop/replan after the repair ceiling or repeated identical failure.
Human stage dispatch is the only human input during the judged run. Do not solicit

steering, approvals or debugging hints. Report a blocker if unattended permissions fail.
Required outcome: genuine stage-N outputs, independent Dockerfile/RUN.md, requirement
coverage, own QA checks, designer evidence where applicable, official isolated harness
evidence, candidate acceptance, room event provenance, timing and available usage data.
The factory must never label an unobserved check successful or fabricate room exports.

## Task preferences and ownership
Product proposal: Tablekeeper, a coherent restaurant reservation experience.
Starting technical proposal: TypeScript, React/Vite, a small Node HTTP API, SQLite,
and a tested timezone adapter. The Architect may choose a better compliant option
and record why. The official specifications always take priority.
Package one self-contained container per completed stage. No hosted authentication,
database, CDN, or AI API is allowed as an application runtime dependency.
Stage 1: complete API behavior, atomic changes, retry correctness, time handling,
and portability. Stage 2: polished search/booking/lookup, approved table pairs,
delayed-response handling, and reliable uncertain-submission recovery.
Stage 3: policy selection, accepted-term history, revisions, recurring agreements,
and upgrade continuity. Stage 4: deterministic seating replanning, atomic application,
and series amendments. Preserve genuine incremental earlier stage outputs; do not
copy a final implementation backwards. Attempt only this dispatched stage and label incomplete work.
Prioritize required behavior and a polished Stage 2 over optional dashboards,
integrations, or decorative assets.
The PM creates the actual product brief and requirement map from the exact specs.
The Architect records implementable architecture decisions before corresponding
implementation. The Designer creates journeys, screen hierarchy, interaction states,
responsive specifications and design reviews before corresponding UI implementation.
Use the empty templates as record formats; they contain no preselected decisions.
Designer direction: warm hospitality, clear hierarchy and human-readable labels;
inspect desktop and 375px rendered layouts, keyboard focus and detailed feedback
states. Required routes and test attributes come only from the exact official spec.
Clearly mark optional visual ideas. QA independently authors actual behavior tests
covering late search responses, conflicts, lost responses, retries and upgrades.

## Exact official specification — tablekeeper/spec/stage-1.md
Source: /Users/frank/mygit/Tablekeeper/challenge/tablekeeper/spec/stage-1.md
SHA-256: 9460189eac83802ce158f16ee90989af728a489b32a6147e2dc8e320f383055f

<!-- BEGIN EXACT SPEC tablekeeper/spec/stage-1.md -->
# Tablekeeper — Stage 1: reservations

This stage defines the initial service and its API.

Build from the supplied requirements. Source code, API documentation and schemas from
existing products in this domain must not be used.

## 1. Scope

Diners can search restaurant availability, book a table and receive a confirmation
reference. They can cancel or amend their bookings, including changing several bookings
together. Each restaurant has its own table capacities, opening hours and cancellation policy.
Only the HTTP API is required.

Two `confirmed` reservations must never occupy the same table at overlapping times,
including during concurrent requests. Occupancy is the half-open interval
`[starts_at, starts_at + reservation_duration)`. A 90-minute booking at 19:00 therefore
does not overlap a booking starting at 20:30. Retries and rejected requests must not
create duplicate or partial bookings.

## 2. Delivery and deployment

Deliver an HTTP service, a `Dockerfile` and a `RUN.md` with a command that builds and
starts the service without manual setup. Language, framework and storage are unrestricted.
A `docker-compose.yml` is optional.

The submission is a containerized HTTP service, not a Python package. Python is not
required in the implementation. TypeScript/JavaScript, Go, Rust, Java, Python and any
other language are equally valid. The harness builds the submitted `Dockerfile`, starts
the resulting image and tests only its HTTP behavior; it does not import or execute the
submission's source files on the judge host.

The image must run on its own with `-e PORT=<port>` and a port mapping. Runtime networking
has no outbound access. All runtime dependencies, initialization and seed data must work
within that single container. Compose configuration is not used to start the service.

### Resource limits

The service must operate within these limits:

| Limit | Value |
|---|---|
| CPU | 2 vCPU |
| Memory | 2 GiB |
| Start to first healthy response | 60 s |
| Concurrent requests | up to 50 in flight |
| Per-request timeout | 5 s (10 s for `POST /_test/reset`) |
| Outbound network | available during `docker build`, **none at run time** |
| Disk | ephemeral; state need not survive a container restart |

Runtime assets and dependencies must be included in the image. This includes fonts,
scripts and stylesheets; external services are unavailable at runtime.

## 3. Runtime contract

### 3.1 Listening

Listen on `0.0.0.0` using the `PORT` environment variable, default `8080`.

### 3.2 Health

```http
GET /health  ->  200  {"status": "ok"}
```

Return 200 once the service and its data store can serve requests, within 60 seconds
of container start. Non-200 responses are permitted before the service is ready.

### 3.3 Reset and seed

```http
POST /_test/reset
Content-Type: application/json

{ ...fixture... }

->  204 No Content
```

Replace all service state with the fixture in the request body (§4). When reset returns
204, subsequent requests must see only that fixture. Repeated resets are supported.
This test endpoint must be enabled in the delivered image and requires no authentication.

### 3.4 Conventions

- Requests and responses are `application/json; charset=utf-8`.
- Timestamps in responses are RFC 3339 with an explicit offset, e.g. `2026-09-24T19:00:00+02:00`.
- Unknown fields in a request body are ignored, never an error.
- Unknown query parameters are ignored.
- IDs are opaque strings of at most 64 characters. Their format is yours. This limit
  also applies to IDs supplied in reset fixtures.

## 4. Model

Restaurants and tables are supplied through `POST /_test/reset` only. Restaurant and
table creation endpoints are out of scope.

| Field | On | Meaning |
|---|---|---|
| `timezone` | Restaurant | IANA zone name, e.g. `Europe/Berlin`. All of the restaurant's times are local to this |
| `slot_minutes` | Restaurant | Bookings start on a grid of this many minutes from opening time |
| `reservation_duration_minutes` | Restaurant | How long every reservation occupies its table |
| `cancellation_cutoff_minutes` | Restaurant | A booking cannot be cancelled or changed within this many minutes of its start |
| `opening_hours` | Restaurant | Per weekday. A day with no entry is closed |
| `capacity` | Table | Maximum party size |

### Fixture format

```json
{
  "users": [
    { "id": "u_ada", "email": "ada@example.com",
      "password": "correct horse", "display_name": "Ada" }
  ],
  "restaurants": [
    {
      "id": "r_anker",
      "name": "Zum Anker",
      "timezone": "Europe/Berlin",
      "slot_minutes": 30,
      "reservation_duration_minutes": 90,
      "cancellation_cutoff_minutes": 120,
      "opening_hours": [
        { "weekday": "thu", "opens": "18:00", "closes": "23:00" },
        { "weekday": "fri", "opens": "18:00", "closes": "23:30" }
      ],
      "tables": [
        { "id": "t_1", "label": "1", "capacity": 2 },
        { "id": "t_2", "label": "2", "capacity": 4 }
      ]
    }
  ],
  "reservations": []
}
```

- `weekday` is one of `mon tue wed thu fri sat sun`.
- `opens` and `closes` are local `HH:MM`, 24-hour. `closes` is always later than `opens` on the
  same local day — opening hours never cross midnight.
- Seeded users must be able to log in with the given password immediately.
- `reservations` may seed confirmed bookings, with the same fields as a `POST /reservations`
  body plus `id`, `reference` and `user_id`.

Fixtures may use any calendar date. A booking must not be rejected solely because its
start is in the past; the cancellation and amendment cutoff rules still apply.

## 5. Errors

Every 4xx and 5xx response carries this body:

```json
{ "error": { "code": "table_unavailable", "message": "human readable, any wording" } }
```

Use the specified HTTP status and `code`. The human-readable `message` may use any wording.
Endpoint-specific errors are listed with each endpoint.

| Status | `code` | When |
|---|---|---|
| 400 | `malformed_request` | Unparseable body, or a field of the wrong JSON type |
| 400 | `missing_idempotency_key` | Required `Idempotency-Key` header absent or empty |
| 401 | `unauthenticated` | Missing, malformed or unknown bearer token |
| 403 | `forbidden` | Authenticated, but not permitted to touch this resource |
| 404 | `not_found` | No such resource, or not visible to this caller |
| 409 | `idempotency_key_reuse` | Key already used by this caller with a different request body |
| 422 | `validation_failed` | A required field or query parameter is missing, or a stated rule is violated with no more specific code |

A field of the correct JSON type with an invalid format or out-of-range value gives
422 `validation_failed`, unless an endpoint specifies a different error. This includes
invalid dates, negative counts and values exceeding a stated maximum or length. In addition:

- Endpoint-specific field rules take precedence: invalid `party_size` values (including strings
  and booleans) and `starts_at_local` strings that are not a bare local `YYYY-MM-DDTHH:MM` are
  422 `validation_failed`. Other wrong JSON types follow the rule below.
- An integer-valued **query parameter** is written as plain decimal digits: `1e9`, `4.0` and `+4`
  are 422 `validation_failed` whatever their numeric value.
- Reserve 400 `malformed_request` for a body that does not parse or a field of the wrong type.

Shared ranges, enforced on every endpoint that takes them:

| Field | Valid | Otherwise |
|---|---|---|
| `Idempotency-Key` | 1 to 255 characters | 422 `validation_failed` |

Requests must not produce 5xx responses, including under concurrent load.

## 6. Authentication

Authentication supports signup and login. Email verification, password reset, refresh
tokens and role-management endpoints are out of scope. Permissions specified elsewhere
in these requirements still apply.

```http
POST /auth/signup
{ "email": "a@example.com", "password": "correct horse", "display_name": "Ada" }

->  201  { "user_id": "u_1", "display_name": "Ada", "token": "..." }
```

```http
POST /auth/login
{ "email": "a@example.com", "password": "correct horse" }

->  200  { "user_id": "u_1", "display_name": "Ada", "token": "..." }
```

| Case | Response |
|---|---|
| Email already registered | 409 `email_taken` |
| Password shorter than 8 characters | 422 `validation_failed` |
| `email` not of the form `local@domain` | 422 `validation_failed` |
| Wrong password or unknown email on login | 401 `unauthenticated` |

Every other endpoint requires a bearer token, except `/health`, `/_test/reset`, the two above, and
the three public endpoints named at the top of §8 — `GET /restaurants`, `GET /restaurants/{id}` and
`GET /availability`:

```http
Authorization: Bearer <token>
```

Tokens do not expire. An account may have multiple valid tokens and concurrent sessions.

Passwords must be stored using a password-hashing function such as bcrypt, scrypt or
Argon2, or an equivalent. Plaintext password storage is not permitted.

## 7. Idempotency

Two write paths require an idempotency key: **`POST /reservations`** (§8) and
**`POST /reservation-moves`** (§11).

```http
Idempotency-Key: <client-chosen string, 1..255 characters>
```

The key is scoped to **the authenticated user**. Two different users may use the same key string
with no interaction between them.

A replay means the same user sending the **same method, the same path and the same body**. The
same key with the same body on a different path is a different request, not a replay, and must
succeed normally.

After the body has been parsed as a JSON object and the caller authenticated, idempotency
is resolved before endpoint-specific field validation or current-resource checks. Thus a
used key with a different JSON body returns `409 idempotency_key_reuse` even when that new
body would otherwise be invalid.

| Situation | Response |
|---|---|
| Header absent or empty | 400 `missing_idempotency_key` |
| First use of the key | The normal response, **201** |
| Replay: same key, same body | **200**, body identical to the original response as a JSON value |
| Same key, different body | 409 `idempotency_key_reuse` |
| Key reused after the original request failed with 4xx | Treated as a first use |

"Same body" means the same JSON value after parsing — key order and whitespace do not matter.

For concurrent identical requests with an unused key, exactly one returns 201.
The others return 200 with the same body. The operation takes effect only once.

A successful replay returns the original response, even after the resource changes or
is cancelled. It makes no further state changes.

## 8. API

`GET /restaurants`, `GET /restaurants/{id}` and `GET /availability` are **public** — no bearer
token. Everything else needs one. Diners browse before they sign in.

### `GET /restaurants`

```json
{ "restaurants": [ { "id": "r_anker", "name": "Zum Anker", "timezone": "Europe/Berlin" } ] }
```

### `GET /restaurants/{id}`

The restaurant with its `slot_minutes`, `reservation_duration_minutes`,
`cancellation_cutoff_minutes`, `opening_hours` and `tables`, in the fixture's shape. 404 if
unknown.

### `GET /availability`

```http
GET /availability?restaurant_id=r_anker&date=2026-09-24&party_size=4
```

All three parameters are required; a missing one is 422 `validation_failed`. `date` is a local
calendar date at the restaurant.

```json
{
  "restaurant_id": "r_anker",
  "date": "2026-09-24",
  "timezone": "Europe/Berlin",
  "slots": [
    { "starts_at_local": "2026-09-24T18:00",
      "starts_at": "2026-09-24T18:00:00+02:00",
      "available_table_ids": ["t_2"] }
  ]
}
```

`starts_at_local` is the full `YYYY-MM-DDTHH:MM` and goes into `POST /reservations` unchanged.

A slot appears for every `slot_minutes` step from `opens` such that
`slot + reservation_duration_minutes <= closes`. `available_table_ids` lists the tables of that
restaurant with `capacity >= party_size` and no overlapping confirmed reservation, in fixture
order. A slot with no available table still appears, with an empty list.

A closed day returns `"slots": []`.

### `POST /reservations`

`Idempotency-Key` is required; see §7.

```http
POST /reservations
Authorization: Bearer <token>
Idempotency-Key: 2f9c1a...

{ "restaurant_id": "r_anker", "table_id": "t_2",
  "starts_at_local": "2026-09-24T19:00", "party_size": 4 }
```

`starts_at_local` is wall-clock at the restaurant, with no offset and no `Z`. Resolve it against
the restaurant's `timezone`.

```json
201
{
  "reservation_id": "res_7",
  "reference": "K3P7QW",
  "restaurant_id": "r_anker",
  "table_id": "t_2",
  "party_size": 4,
  "status": "confirmed",
  "starts_at_local": "2026-09-24T19:00",
  "starts_at": "2026-09-24T19:00:00+02:00",
  "ends_at": "2026-09-24T20:30:00+02:00",
  "created_at": "2026-09-21T11:04:03+00:00"
}
```

`reference` is 6 to 12 characters of `A-Z0-9`, unique across all reservations, and never changes.

| Case | Response |
|---|---|
| The table is taken for an overlapping interval | 409 `table_unavailable` |
| `starts_at_local` is not on the slot grid | 422 `not_on_slot_grid` |
| Slot outside opening hours, or the reservation would end after `closes` | 422 `outside_opening_hours` |
| `party_size` exceeds the table's `capacity` | 422 `party_exceeds_capacity` |
| `party_size` below 1, or not an integer | 422 `validation_failed` |
| `starts_at_local` is a local time that does not exist (see §9) | 422 `invalid_local_time` |
| Unknown restaurant, unknown table, or the table belongs to another restaurant | 404 `not_found` |

### `GET /reservations`

The caller's reservations, `starts_at` descending, confirmed and cancelled alike.
Return `200` with `{"reservations": [...]}`; each entry has the same shape as the
create response. An empty list is `{"reservations": []}`.

### `GET /reservations/{reference}`

One reservation. **404 if it is not the caller's** — do not leak the existence of other people's
bookings.

### `POST /reservations/{reference}/cancel`

```json
200
{ "reference": "K3P7QW", "status": "cancelled", ... }
```

Frees the table immediately: the next `GET /availability` must offer that slot again.

| Case | Response |
|---|---|
| Already cancelled | 200 with the current state — cancelling twice is not an error |
| Now is within `cancellation_cutoff_minutes` of `starts_at`, or later | 409 `cutoff_passed` |
| Not the caller's reservation | 404 `not_found` |

### `PATCH /reservations/{reference}`

Change the time, the table or the party size. Any subset of `table_id`, `starts_at_local`,
`party_size`. No idempotency key is required here.

Validation is identical to `POST /reservations`, and the same cutoff rule as cancel applies
(409 `cutoff_passed`), measured against the **current** start time. A cancelled reservation is
409 `reservation_cancelled`. A successful amendment releases the old slot and reserves the
new one together. A failed amendment leaves the original booking and its occupancy unchanged.

`reference` and `reservation_id` survive a change.

## 9. Time and DST

Local dates and times follow the restaurant's `timezone`, including daylight-saving transitions.

**Spring forward.** Local times in the skipped hour do not exist. They never appear in
availability, and booking one is 422 `invalid_local_time`.

**Fall back.** Local times in the repeated hour occur twice. **Always resolve to the first
occurrence — the one before the clocks change.** The slot appears once in availability, and the
second occurrence is not bookable.

`reservation_duration_minutes` is **absolute time**, not wall-clock. A 90-minute reservation
starting at 01:30 on a fall-back night ends 90 real minutes later, and its local `ends_at` will
read 02:00, not 03:00.

The transitions that must be handled:

| Zone | Spring forward | Fall back |
|---|---|---|
| `Europe/Berlin` | 2026-03-29, 02:00 → 03:00 | 2026-10-25, 03:00 → 02:00 |
| `America/New_York` | 2026-03-08, 02:00 → 03:00 | 2026-11-01, 02:00 → 01:00 |

Offsets must follow the IANA rules for the specified zone and date.

## 10. Export and import

The service must support `GET /_test/export` and `POST /_test/import`. Like reset, these
are unauthenticated test endpoints.
Exports may contain credentials and session tokens; handle them as private test artifacts.
Return 200 from export with a JSON object containing `track: "tablekeeper"`,
`format_version: 1` and `state` (an implementation-defined JSON object). The state format
is opaque to the caller and must be accepted unchanged by import.

Import takes that entire object and atomically replaces the service's state, returning
204. It must accept an unchanged export produced by this service. No dependency on the
source process, files, volume, port or network address is allowed. Import is replacement,
not merge; repeating it restores the exported state without duplicating anything. Invalid
JSON follows §5; missing fields, wrong track/version or an invalid state give 422
`validation_failed` without changing the destination. Test control calls have a 10-second
timeout. Export is an atomic, read-only snapshot; subsequent source writes do not change it.

Preserve accounts and hashed-password login, existing bearer tokens, fixture configuration,
reservations, references, all completed idempotent request bodies and original responses.
Identities, statuses and timestamps must not be regenerated. Failed request keys remain
reusable. Existing receipts, references, tokens and retries must remain valid after import;
replacing the state with a fresh fixture does not satisfy this requirement. Import removes
all previous destination data and credentials. Reset continues to clear all state, including
imported state. State need not survive an abrupt container restart.

## 11. Atomic reservation moves

A diner may change several bookings in one request.

`POST /reservation-moves` requires authentication and an idempotency key. Body:

```json
{"moves": [{"reference": "BOOK01", "table_id": "t_2"},
           {"reference": "BOOK02", "table_id": "t_1"}]}
```

`moves` contains 1..8 objects with distinct string references. Invalid shape or duplicate
references gives 422 `validation_failed`. Every booking must belong to the caller and the
same restaurant. Unknown/another owner's reference gives 404 `not_found`; different
restaurants give 422 `validation_failed`. No token gives 401.

Each item accepts the ordinary PATCH fields `table_id`, `starts_at_local`, `party_size`;
omitted fields retain their current values and unknown fields are ignored. The booking's
identity, owner and creation time never change. Cancelled bookings give 409
`reservation_cancelled`. Each booking's existing cutoff applies. Non-occupancy errors use
ordinary amendment codes and take precedence in input order, with cutoff errors preceding
other changes for that booking. An overlap among resulting bookings or with an unlisted
booking gives 409 `table_unavailable`. Unchanged listed bookings retain their occupancy.

Either every move commits or nothing changes: occupancy, reservation records and retry
keys. On success return 201 with `{"reservations": [...]}` in input order, including
unchanged items.
Replays return that original response with 200, even after amendments or cancellations.
No-op moves retain all existing values. Export/import preserves successful batch receipts
as well as the resulting bookings. No batch UI is required.

<!-- END EXACT SPEC tablekeeper/spec/stage-1.md -->

