# Run 5 post-run official isolated harness check

The operator ran the pinned official **published** harness after the BAND attempt had stopped. Stage 1 recorded **120 collected, 120 passed, zero failed/errors/skipped**. This result covers the shipped suite on the unchanged rejected product tree; it does **not** overturn the independent receipt-consistency rejection or retroactively pass the BAND acceptance gate.

A fresh GitHub clone was detached at record-only closeout `350e3d95855a7b10eacafd59fca67ffaf48a348e`, Stage 1 tree `13192852a7341f8d7e6b2bc6076c9e59cfa3843b`, and remained clean. See [clone receipt](clone-receipt.json), [command](isolated-command.json), [command log](isolated-command.log), [report](isolated-all/stage-1/report.json) and [summary](isolated-all/summary.json). The run used `harness run --track tablekeeper --repo <fresh clone> --all --mode isolated`; it ran from **23:38:15.483787 to 23:38:56.297110 UTC**, exit 0, after PM final at 23:29:24.626626 and owned-runtime closure at 23:33:07.598829.

| Scope | Observed result |
|---|---|
| Existing `stage-1/` published suite | [120 passed](isolated-all/stage-1/stage-1.counts.json), [log](isolated-all/stage-1/stage-1.log); one harmless read-only pytest-cache warning |
| Automatic next-stage overshoot probe against the same Stage 1 service | [25 collected, 0 passed, 1 failed](isolated-all/stage-1/stage-2.counts.json); [log](isolated-all/stage-1/stage-2.log) shows `-x`, stopping on missing search-button UI; remaining 24 cases did not execute |
| Stage 2, 3 and 4 implementations | No folders existed; no implementation or stage credit |

The official `--all` path enumerates existing stage folders; here it found only Stage 1. The separate Stage 2 probe checks whether a later answer was placed in the Stage 1 folder. Its expected early failure does not make this an all-four-stages pass or a Stage 2 suite result. The official output explicitly says these public checks are only a portion of the tests applied before judging; `preview:true` remains preserved.

Pinned harness source sets the service's `--cpus 2 --memory 2g`, performs health checking with a 60-second deadline, creates a unique `--internal` runtime network and places both service and runner on it. The archived runner log identifies that same network. Image building may access the network by design. This archive verifies source and retained command/result evidence; it adds no live network/egress probe or sustained resource benchmark.

The recorded OrbStack global ceiling was **2048 MiB**. Existing operator metadata measured Docker MemTotal **2,073,866,240 bytes** (about 1977.79 MiB), below 2 GiB because the shared VM has overhead. The exact timestamp and source hash are retained in [archive provenance](archive-provenance.json); the [fresh post-run resource observation](resource-observation.json) independently records that same value at 23:42:13.822255 UTC using the explicit OrbStack Docker socket. It was measured after the suite, not as a peak or continuous measurement. A configured container ceiling does not guarantee exclusive access to a full 2 GiB, and this passing sample suite does not establish every heavy resource distribution.

The known historical receipt request/response contradictions remain independently rejected at the same product tree, with repair 3/3 exhausted. See the separate [final rejection archive](../run5-stage1-final-rejection-20261004/README.md). The reviewer decision's historical missing-container evidence is preserved; these later operator results add a separate verification layer, not an autonomous acceptance or final submission claim.

Ten selected source records/logs are copied byte for byte. The full clone and duplicated requirements are not included. Logs contain public synthetic fixture examples, not private service exports or generated session credentials. The archivist ran no product tests, Docker probes, model work or BAND messages and made no product/configuration/process changes. Privacy scanning was limited to the official credential-pattern function and inspection; it is not a full submission check. See [manifest](manifest.json) and [privacy scan](privacy-scan.json).
