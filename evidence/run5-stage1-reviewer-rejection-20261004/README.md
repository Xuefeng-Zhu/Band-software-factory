# Run 5 Stage 1 release-reviewer rejection

Status at the recorded reviewer outcome: **REJECTED**, not accepted. Work item `GATE-S1`; reviewed integrated candidate `4026ec71ac6cf5ae0ebe6e998d77fd4a475a8c4d`, stage tree `6000d94a5acbcab53438120b6d7f2624b4eceba4`.

The actual [public final event](public-final-event.json), `7f7848d9-1ce3-4f34-8f94-4f43643abf0c`, was inserted at **2026-10-04T23:01:56.714437Z** by Factory Reviewer, `@frankzhu94/factory-reviewer`. Its later server `updated_at` is retained separately. The reviewer sent the three-part `GATE-S1-R1` handoff; [return-events.json](return-events.json) records receipt as pending at that historical point. This archive does not upgrade that receipt to acknowledged or claim a later repair result. PM owned the next bounded repair dispatch; no Stage 2 advancement was accepted.

The independent [decision](decision.md) identifies three reproduced defect families:

- Ordinary fixture numeric fields returned the wrong error status/code for invalid JSON types: **20 failed assertions**. The companion 20 unchanged-state assertions passed.
- Three invalid imported receipt-response variants were accepted and corrupted subsequent replay: **9 failed assertions**, covering rejection, state preservation and original-response replay.
- A valid unquoted 5,000-digit fixture capacity returned 400 instead of successful reset: **1 failed assertion**. This was an approximately 5 KB input, not a memory stress probe.

[results.json](results.json) contains **61 focused HTTP assertions: 31 PASS, 30 FAIL**. These are three defect families, not 30 independent defects. [execution.json](execution.json) records two real source-entrypoint processes from a clean exact-candidate clone, Python **3.13.5 on macOS**, UTC times, ports, owned PIDs and cleanup. The scripts are retained unchanged as historical evidence, not executed during packaging.

[mechanisms-results.json](mechanisms-results.json) separately records **two PASS groups** using controlled host in-process scheduling/failure injection. Those groups do not establish HTTP concurrency or container behavior. The evidence does not provide a single combined official-suite pass count.

The reviewer separately left the current clean Docker build, official isolated suite, Python 3.12 runtime, actual 2 CPU/2 GiB allowance, no-outbound execution and load/latency gates **BLOCKED/NOT_TESTED**. The reproduced product rejection is independent of that infrastructure limitation. Earlier official-suite passes apply to older candidates. Historical statements about Docker availability and container cleanup in decision.md remain the reviewer's as-observed account; later operator resource-repair evidence is recorded separately in [the infrastructure archive](../run5-orbstack-memory-repair-20261004/README.md), without retroactively converting this review into a container pass.

[provenance.json](provenance.json) binds source blob hashes, stage tree, inherited QA references and historical checkout cleanliness. Packaging independently matched all nine recorded source-file SHA-256 values against Git objects at the exact reviewed candidate. It did not run application tests, modify product files, or send BAND messages. [manifest.json](manifest.json) records all selected original file hashes and exclusions. The selected source files are byte-for-byte copies; no corrections to their historical statements were made.

Privacy inspection and the pinned official harness credential-pattern scanner passed for the archive. The scripts use an explicitly synthetic fixture password and keep live session tokens/private export snapshots in memory; the saved assertion data contains neither raw private exports nor session credentials. The duplicate requirements handoff and empty server logs were excluded. The scan is an evidence-packaging check, not application acceptance or a full repository/hackathon check. This package does not claim the broader run was uninterrupted or autonomous-compliant.
