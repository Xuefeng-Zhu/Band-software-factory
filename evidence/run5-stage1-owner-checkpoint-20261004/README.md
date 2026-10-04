# Run 5: first runnable Stage 1 candidate

The Backend agent committed the service at `db1954a5df3cabcfb3419d8ea3748e1604b7b90c` and its owner report at `12e43a92dd6e037ac27dfb2189f18eed35a32fbc`; both commits have the same Stage 1 tree. The latter was observed on the canonical private `run-5` remote branch.

Owner verification recorded a successful container build, six unit tests, eleven QA-authored HTTP groups and 120/120 supplied isolated Stage 1 checks. The reports retained here are unmodified. The HTTP report names its QA author; **Backend performed this run**, so it is not independent QA acceptance. The official report is working-tree provenance, not the final fresh-clone gate.

Independent QA/release acceptance remains pending. The owner explicitly asks for architecture review of document storage in SQLite and serialization within the transaction. Broader input/import/concurrency/latency coverage and all later stages remain unfinished or unverified. No Run5 stage acceptance is established here.

The [accounting audit](accounting-audit.json) reconciles the authoritative ledger at its stated snapshot and preserves the cap/deadline. It documents a separate pinned SDK display-telemetry mismatch; that mapping is not used by the factory budget. Its token/cache totals are historical and do not establish dollars or subscription quota use. No live configuration or SDK code was changed.

See [manifest](manifest.json), [Backend owner report](backend-stage-1.md), and [official isolated report](official-isolated-report.json).
