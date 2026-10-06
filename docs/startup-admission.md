# Startup admission and rehearsal hold

Normal seven-seat startup connects and verifies every configured harness and
BAND seat before factory turn reservation or model execution. Startup readiness
requires seven supported live SDK contexts and a fresh authenticated roster of
those seven agents plus their human owner. Healthy SDK contexts may already be
processing queued events while their adapter callbacks wait at this barrier.

For an independently approved rehearsal, the operator can hold that barrier:

```sh
scripts/runtime --config /absolute/prepared/factory.yaml start-seats --mode rehearsal --hold-admission
scripts/runtime --config /absolute/prepared/factory.yaml seat-status
scripts/runtime --config /absolute/prepared/factory.yaml release-admission
```

`ready_held` means that the real initial full-roster check passed. It does not
mean BAND messages are untouched: the SDK may have claimed messages or emitted
working status. Held callbacks await without taking a factory semaphore slot,
reserving a turn, invoking a provider, or returning an empty successful result.
Ordinary shutdown cancels them; it does not synthesize an ACK. Platform interrupt
controls have their own SDK receipt behavior.

The initial SDK startup window is at most 325 seconds. A manual hold expires
60 seconds after verified readiness, bounded by the original startup-plus-hold
window and the unchanged session/stage deadlines. Both wall and monotonic clocks
bound waiting. Status records these deadlines. Only the SDK outer cycle watchdog
receives the finite waiting allowance; the existing factory/provider turn limit,
shared tokens, spend cap, and session clocks remain unchanged.

Release creates one private durable claim tied to the current owned process,
configuration, and rehearsal room. The supervisor rechecks ownership, budgets,
controls, and membership before opening. A later genuine single missing-member
gap may be admitted only through the existing authenticated observer, under its
original repair deadline and transition cap, after the initial full-roster
readiness proof. No membership mutation or fixture is part of these commands.
Repeated or ambiguous release claims are preserved for inspection, not retried.

Retained failed or active membership journals block warm startup before native
servers or BAND agents start. The two failed Hermes fixture episodes remain
failed and consumed; this change neither clears them nor authorizes a third
fixture, a fresh room, a new run, or retransmission of queued task packets.

Private phase timing journals under `runtime/startup-telemetry` distinguish
native server checks, SDK starts, readiness, and admission release. They contain
no credentials, message bodies, or provider responses. Admission state and claims
are private files under `runtime/admission`.
