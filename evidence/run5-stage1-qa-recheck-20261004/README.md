# Run 5 Stage 1 QA recheck — host evidence only

This preserves the completed independent `QA-S1-RECHECK` evidence for candidate `4026ec71ac6cf5ae0ebe6e998d77fd4a475a8c4d`, Stage 1 tree `6000d94a5acbcab53438120b6d7f2624b4eceba4`. **No stage acceptance is established.** This is an operator archive of the QA seat's existing results, not a new test execution or review decision.

The QA seat independently closed `QA-S1-DATE-MAX` and `QA-S1-QUERY-DIGITS` in host HTTP verification. The five focused groups, eleven unchanged baseline groups and seven prior additional groups each passed; all three commands exited 0. These groups overlap in behavior and are not a count of distinct specification requirements. `coverage.json` records 26 representative classes PASS and one runtime class NOT_TESTED; it explicitly retains untested cases within the passing classes.

The execution used Python 3.13.5 and two distinct host services between `2026-10-04T22:45:49.499952Z` and `2026-10-04T22:45:55.494112Z`. The retained provenance reports clean shared/review checkouts before and after, unchanged candidate identity and cleanup of both QA-owned services. No claim is made about another process's cleanup or later live state.

## What is preserved

- `report.md`, `coverage.json`, `provenance.json`, `execution.json`, `completion.json` and `return-events.json`: original report, candidate/source relation, commands/timing/process records and delivery metadata.
- `focused-results.json`, `baseline.json`, `extra-results.json` and the three nonempty logs: original 5/11/7 group results.
- `verify.py`, `focused.py`, `prior-extra.py` and `endpoints.json`: original orchestration and assertions, including historical loopback addresses.
- `dependencies/qa_stage1_boundaries.py`: exact Git blob `2549ab4f85f0733b03dc3b74e424b67c5af0d1c3` from the tested candidate, required by the baseline and both additional scripts.
- `dependencies/repro-fixture.json`: unchanged earlier independent reproduction fixture used by the focused date-max check. It contains only synthetic test users, `example.test` addresses, a literal synthetic password, generated restaurant data and no reservations. It is not a raw application state export.
- `public-events.json` and `public-events-provenance.json`: two selected existing public text event objects retrieved through the supported read-only native CLI, with query time and pagination metadata. Event values are unchanged; the JSON envelope is operator-created. This is not the genuine full-session download.
- `credential-scan.json` and `manifest.json`: inspection/scan scope and SHA-256/byte provenance. The manifest covers every archived file except itself.

Original files are byte-identical. `completion.json` still says `receipt: PENDING`, as it did when QA saved it. The separately retained final QA public message `eb1a0344-5318-49df-b642-dd4367139c9b` was inserted at `2026-10-04T22:48:51.604927Z`. PM's later receipt `da610b06-becf-4e27-b68e-48fbd0853caf` was inserted at `2026-10-04T22:50:04.354683Z` and acknowledges delivery `QA-S1-RECHECK-R1`, digest `55b42848be78b9a165d280f08247e69af53a1c8ef2175f47b6089b59aa306b9e`. Receipt is not release acceptance. Native readback also contains later platform `updated_at` values, which are preserved without interpreting them as insertion times.

The 53,551-byte `handoff.json` repeats the full assignment/requirements and is omitted. Empty `server-0.log` and `server-1.log` are omitted. No credentials, raw state exports, product implementation, unrelated room events or private reasoning are copied.

## Reproduction and limits

Original source directory: `/Users/frank/mygit/Tablekeeper/result-run-5/.evidence/qa-s1-recheck-20261004T2244Z`. The earlier fixture lives under its sibling `qa-s1-20261004T2218Z`. The runner preserves historical absolute interpreter, clone and evidence paths; this archive is not a portable turnkey runner. `verify.py` launches synthetic services, runs checks and writes results, so do not execute it against an existing application or reuse these evidence destinations. Any separately authorized reproduction needs a disposable checkout of the full candidate and new output locations, with the preserved dependencies mapped explicitly. No such reproduction was performed for this archive.

The original prior-extra script was remapped only for clone path and revision. The archive compares those bytes against the earlier script and records the source hash; it does not import the production implementation as an oracle. The baseline source is a Git-blob copy, not a newly written test.

At the QA report's cutoff, Docker/Python 3.12 image execution, official isolated harness, 2 vCPU / 2 GiB conformance, no-outbound runtime, container readiness and 128/256/512 heavy-receipt performance remained BLOCKED/NOT_TESTED. Historical source-injection/exact-clock and old-to-repaired-process results at `68afbf8` were not rerun here; previous official passes do not transfer. Future stages and exhaustive concurrency/corrupt-import/timezone combinations remain untested. Later infrastructure changes do not retroactively turn these host checks into container evidence. The autonomous independent Reviewer retains the release gate.

Preservation performed no product test/review rerun, service start, BAND message, source/config/mandate change, commit or push. The official credential-pattern scan is only a pattern check; source/result/log/event inspection supplements it and does not constitute public-release authorization.
