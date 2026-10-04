# Run 5 Stage 1 repair 2 — owner checks pass, independent gates pending

Backend fixed the two independent QA findings in `7e82648b4f4feb1c74015f9c551626ba3a36851c`. Record-only candidate `4026ec71ac6cf5ae0ebe6e998d77fd4a475a8c4d` has the identical Stage 1 tree and was pushed to the canonical private `run-5` branch.

Original responses are retained: valid maximum-year availability returned 422, and a valid 5,000-digit decimal query returned 400. The same probes against the repair return 200/eight slots with the appropriate table availability. The verification runner asserts those responses; the diagnostic collector's exit zero alone is not passing proof.

Owner verification passed on **host Python 3.13**: 14 unit tests, 11 unchanged QA-authored HTTP groups, and adjacent date/query/closing cases. These groups overlap; their counts are not a single aggregate. Two independent host service processes were stopped by their owner. These are owner checks, not independent review or Docker/Python 3.12/no-outbound/resource acceptance. Prior candidates' 120 official checks do not apply to this repair.

The actual public return names the fixed candidate. PM acknowledged its complete four-part digest at `2026-10-04T22:41:21.572593Z`. Independent QA and Reviewer GATE-S1 remain pending, and no later stage has advanced. The owner's inherited Docker-block statement is preserved unchanged; the separate operator infrastructure repair did not rerun these tests or establish application acceptance.

The copied scripts retain historical absolute paths and the exact candidate's QA-suite dependency. They are historical evidence, not a portable standalone test package. [Owner record](backend-stage-1-repair2.md) and [manifest](manifest.json) retain commands, attribution, layer, hashes and timing. The operator did not rerun tests or alter the candidate to preserve this package.
