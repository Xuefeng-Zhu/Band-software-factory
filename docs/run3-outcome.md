# Run 3 outcome and submission evidence

Team MillieMoon selected Tablekeeper. Seven configured BAND identities used Codex CLI 0.160.0, BAND SDK 4.0.0 and gpt-6-astra, with one active model turn. The judged room `9b059f6b-ee17-44bd-99cd-0277cf602a81` received one human dispatch (`c3b8119d-d1e5-45eb-87a8-9d861f7741ec`) at 2026-10-04 06:38:46.779750 UTC. Its repository began empty and received no application source from prior attempts.

## Accepted output

Reviewer rejected candidate `739b1bf79c631dedb528d503800b954fbd3e61d9` for accepting malformed imported credential fields. Backend committed the repair as `52a179d778b3052acf68c8aafeec62aac8ae6ecd`. Reviewer independently accepted that exact revision after official isolated Stage 1 checks passed 120/120, with independent F1 and QA regressions. Acceptance event: `a75434a1-4acb-48a6-acc9-e9cfbe82b0a5`. PM recorded acceptance at 08:12:11 UTC.

The accepted and current Stage 1 Git tree is `4917af2a996c6e3327933deb84281ad29a30c1f1`. Eleven BAND-authored commits remain intact through `8093befdf1525a7e200ab651a5946f49bbc54bd8`. Architecture and design planning for Stage 2 followed, but no Stage 2 application exists. Only `stage-1/` is included. Official checks are the shipped subset, not the organizers' final full evaluation.

## Stopped handoff

PM turn 176 completed normally after sending all twelve parts of `TK-S2-BACKEND-D1`; all have BAND event IDs. The 120-second ACK deadline matured while Backend was processing part 6; by shutdown it had processed only parts 1–8. Four confirmed parts had not reached a recorded Backend turn. SDK serialization supports the queued-callback diagnosis, but the old runtime did not record queue depth or distinguish local pending callbacks from the remote backlog. The heartbeat saw an unlocked active-turn semaphore and tried its existing coordinator-notice path. The SDK filters self messages, so the runtime stopped at 08:47:13 UTC with `blocked_coordinator_self_notice` rather than posting under another identity. This was not an incomplete outbound send or a failed PM model turn.

Run 3 used 58,265,038 reported tokens (including cached input) across 174 admitted turns. Retained cumulative consumption across preparation and runs is 84,080,166 / 100,000,000. Reported tokens are not measured monetary spend or subscription quota. Monetary cost is unavailable. The original overall deadline, October 4 at 13:29:59.700437 UTC, has expired; the 300-turn seat cap and every cumulative counter remain unchanged.

## Preserved evidence

All paths below are relative to `/Users/frank/mygit/Tablekeeper` and remain local evidence unless explicitly in the private result repository.

- `runs/run3-preservation-20261004T164154Z/manifest.json`: original runtime, budget, freeze, dispatch ledger and source/configuration hashes, taken before offline repair.
- `runs/run3-preservation-20261004T164154Z/band-full-session-original.json`: actual console **Download full session**, exported at 16:42:55.109 UTC. It contains 4,088 unique events and exactly one human text event (the dispatch); the other human event is membership.
- `runs/run3-preservation-20261004T164154Z/full-session-export-provenance.json`: export provenance, byte-equality check and credential review. Export SHA-256: `2008460d0d1cff521027f03d974ff24c718aed8708584223638f6b754aa7ccae`.
- `result-run-3/room.json`: byte-identical export, pushed privately in operator evidence-only commit `27f677a9ca93ba1f4e80aa6fdb87392e7f89ec84`; no stage source changed.
- `result-run-3/.evidence/reviewer-s1-f1-20261004T080315Z/`: original independent acceptance and verification; ignored local artifacts also appear in the genuine room's tool output.
- `runs/run3-fresh-clone-check-20261004T164501Z/`: clone from the private remote, official offline check, and one `--all --mode isolated` invocation. At that evidence-only revision the check reported absent README/FACTORY; isolated Stage 1 completed 120/120, claimed stage 1, exit 0. This is post-run operator verification, not a new judged dispatch or substituted seat acceptance.

The same clean-clone Stage 1 image also built and served `/health` successfully following RUN.md, with host binding restricted to localhost; `manual-run-verification.json` records the image, commands and HTTP 200 response. After the complete disclosed documentation drafts were pushed, `runs/run3-final-docs-check-20261004/` verified the final package from a second fresh remote clone: offline check exit 0 and identical accepted Stage 1 tree. No unchanged application test was repeated for documentation-only changes.

## Remaining submission work

The [pinned participant guide](https://github.com/band-ai/dark-factory-wearedevs/blob/803560d2a678ace1414465c098eb0ab5380ffade/docs/participant-guide.md#check-and-submit) says to write README.md and FACTORY.md yourself. The participant subsequently requested assistant-written narratives. Complete factual README/FACTORY drafts were committed with explicit AI-assistance disclosure; they do not establish participant authorship. Separate authoring aids and presentation materials are stored outside the judged repository. A real recording must show the BAND room, an actual handoff and its result. No video, public repository or final submission is claimed.

Offline factory repair applies only to future development. Its changed source/protocol needs fresh readiness evidence and a new finite live allowance before any rehearsal or fresh judged run. Do not overwrite the old freeze, extend the existing ledger silently, restart the submitted room or seed a fresh judged application with this Stage 1 code.
