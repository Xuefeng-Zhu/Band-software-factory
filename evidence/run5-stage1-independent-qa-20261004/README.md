# Independent QA of Run 5 Stage 1 repair 1 — rejected

Factory QA independently reviewed the fixed, clean candidate `68afbf86127ae9b2b5dc8ecc56a0e9c78e6a69f1` on host Python 3.13. Its Stage 1 product tree matches implementation `249e5712624d20ca02c9680eb6ec60ff3865bcb8`.

Two requirement-linked defects were reproduced: valid `9999-12-31` availability returned 422 instead of 200/eight slots, and a valid 5,000-digit decimal party-size query returned 400 instead of 200 with no available tables. Diagnostic commands that exited zero recorded these failures; their exit status is not a passing assertion. The additional-suite compound command's zero status came from its final `cat`.

| Recorded group | Result |
| --- | --- |
| Original HTTP suite, independently executed | 11/11 PASS |
| Additional HTTP groups | 6 PASS, 1 FAIL |
| Continuation HTTP checks | 6/6 PASS |
| In-process storage checks | 3/3 PASS |
| Real legacy-process export/import | PASS |
| Coverage classes | 24 PASS, 2 FAIL, 1 NOT_TESTED |

Groups overlap; do not sum them into a total. Coverage is not exhaustive. Docker, official isolation and specified resource-limit gates remain BLOCKED/NOT_TESTED in this snapshot. No accepted stage is claimed.

The original `completion.json` records receipt PENDING at its creation time and is retained unchanged. The separate actual room receipt establishes PM's ACK at `2026-10-04T22:31:47.790276Z` and its acceptance of both defects for repair 2 of 3 at `22:31:48.528483Z`. The complete requirements-bearing return is represented by its original event references and digest; duplicated handoff specification text is omitted here.

These are copied historical artifacts, not a portable test runner: reproduction scripts retain historical absolute paths and depend on `tests/qa_stage1_boundaries.py` at the reviewed candidate. Fixture credentials are synthetic. No test was rerun by the operator to create this package. Source hashes and exact paths are recorded in [manifest.json](manifest.json); the full QA narrative is [report.md](report.md).
