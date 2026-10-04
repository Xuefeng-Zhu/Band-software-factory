# Toy rehearsal — README

Team: **MillieMoon**. Track: **toy (unscored rehearsal for the Tablekeeper factory)**.

**Rehearsal-only factual report, generated with assistant assistance; not a human-authored judged submission narrative.**

Updated after the genuine full-session export on **2026-10-04 at 03:18:07 UTC**. This report packages the accepted toy exercise for its official offline check. Bounded connectivity recovery is complete; final judged narrative authorship and launch authorization remain separate requirements.

The seven BAND seats built the official unscored toy exercise: a shared, memory-only counter API in `stage-1/`, followed by a local browser page in standalone `stage-2/`. The official starter/specification/harness checkout is [band-ai/dark-factory-wearedevs](https://github.com/band-ai/dark-factory-wearedevs/tree/803560d2a678ace1414465c098eb0ab5380ffade), pinned to `803560d2a678ace1414465c098eb0ab5380ffade`. Product implementation was written by BAND Backend and Frontend; these assistant-assisted reports and the operator's factory preparation are separate from that implementation.

Stage 1 was independently ACCEPTED at `bdfc842110f057ae4e9997d62f33196a6cbc03ed`, reviewer event `8e8ef1c3-fa8b-4c0b-8aff-73ffad557072` at 20:22:44 UTC. The reviewer ran the official isolated harness with **8/8 checks passed**, none skipped. PM acknowledged in event `3f10cd61-0ff0-4f44-8f7d-0bfc40c439ba`.

Stage 2 was independently ACCEPTED at `b042c4a73787521a0b98aa4aa7bf9cde5cba5d65`. Reviewer results are events `bcc14a52-d7d5-49be-aea1-127ce473bc08` and `89a320a4-3ebb-43f4-9880-a799aa6b5b73`; confirmation event `7c940278-afb6-4fd3-8958-bbcc83200a06` is timestamped 20:52:01 UTC. Its independent isolated run passed **12/12 checks**: eight inherited Stage 1 and four Stage 2 checks, none skipped. PM acknowledged the complete results at 20:53:11 UTC in event `b778fe8a-4280-4869-af3f-422b2c7a54c7`. Acceptance applies to this exact candidate and scope.

At 20:54:57 UTC the operator selected the guide-permitted stopping point after accepted Stage 2, event `3ac80ee4-1f41-4ba3-9356-2f127043c256` ([actual message](/Users/frank/mygit/Tablekeeper/runs/rehearsal-launch/stop-at-accepted-stage2-event.json)). Architect completed the assigned read-only visibility task. PM closed product work at 21:01:35 UTC in event `cca5683b-4a9f-4c7f-8af7-6a3768f8f0b1`, preserving the accepted Stage 1/2 revisions and releasing all leases. The room is idle. The supervisor stopped at 21:49:27 UTC after its conservative four-hour rehearsal window elapsed. Stage 3/4 implementation is outside this rehearsal scope and was not produced. This rehearsal includes operator recovery and scope selection, so it is not evidence of an uninterrupted autonomous full-toy run.

All seven seats have actual committed-checkout read evidence from their real assignments. The records bind individual seats to their observed Stage 1 or Stage 2 revision; they do not claim every seat reviewed the final candidate. Architect’s completed smoke compared the committed `stage-2/server.py` bytes at `b042c4a73787521a0b98aa4aa7bf9cde5cba5d65`.

Run either standalone stage from its existing directory, one at a time because both examples publish port 8080. These commands reproduce the committed RUN instructions; they were not executed while drafting this report.

```sh
cd /Users/frank/mygit/Tablekeeper/rehearsal/toy-result/stage-1
docker build -t toy-stage-1 . && docker run --rm -p 8080:8080 -e PORT=8080 toy-stage-1
```

```sh
cd /Users/frank/mygit/Tablekeeper/rehearsal/toy-result/stage-2
docker build -t toy-stage-2 . && docker run --rm -p 8080:8080 -e PORT=8080 toy-stage-2
```

Stage 2 serves its page at `http://localhost:8080/`. Both services read `PORT`, default 8080, bind all interfaces and keep one shared counter in process memory; restart resets it. For port 9000 use `-p 9000:9000 -e PORT=9000`. Dependencies are installed at build time; runtime needs no Internet. See the committed [Stage 1 RUN.md](stage-1/RUN.md) and [Stage 2 RUN.md](stage-2/RUN.md) for endpoints and local test commands.

Repository-relative stage links are portable. The `.evidence/` and absolute operator audit links refer to retained local evidence, which is not included by Git by default. The unchanged [full BAND session](room.json) contains the actual room messages and tool events.

Evidence:

- [Stage 1 reviewer decision text](/Users/frank/mygit/Tablekeeper/runs/rehearsal-observation/20261003T202308Z-text-events.json) and [isolated report](.evidence/reviewer-s1-20261003T201741Z/isolated/report.json).
- [Stage 2 reviewer decision text](/Users/frank/mygit/Tablekeeper/runs/rehearsal-observation/20261003T205229Z-text-events.json) and [isolated report](.evidence/reviewer-s2-20261003T204455Z/isolated/report.json).
- [Final PM outcome text](/Users/frank/mygit/Tablekeeper/runs/rehearsal-observation/20261003T210323Z-text-events.json), [closure artifacts](.evidence/pm-close-20261003T210030Z) and [all-seat visibility audit](/Users/frank/mygit/Tablekeeper/runs/rehearsal-observation/20261003T210300Z-all-seat-visibility.json), supplemented by [sanitized actual tool proof](/Users/frank/mygit/Tablekeeper/runs/rehearsal-observation/visibility-tool-proof.json).
- [Factory report](FACTORY.md) records roles, limits and retained failures.

The genuine [room.json](room.json) was refreshed through BAND’s **Download full session** control at 03:18:07 UTC on October 4: 1616 messages, SHA-256 `de97162536931c0bd647ae840bd9db02b6cbb914eafe71d0f983952c830ba572`. Its bytes are unchanged. Earlier full exports remain archived.

The first approved recovery attempt stopped before PM restoration because of a tool-instruction conflict; exact-ID clarification and the operator's cleanup remain recorded. After a reviewed recovery-only correction and explicit approval of a replacement window, PM restored the exact Architect member once and independently verified the roster. Its directed request `976a947a-bf87-4a86-b7da-1c438f786aa9` received Architect acknowledgment `7aebf4a2-8f03-4ce4-ae9e-d96936a91fa1`; PM receipt `e23c1783-0c93-4129-b948-2f1186178bb2` and outcome `7f2dd912-9a2a-47ed-8299-2b2e980e572c` completed the exchange. The independent operator audit confirms this scoped recovery. All workers stopped after the final turns at 22:55 UTC on October 3; no operator restoration was needed in the successful attempt.

Aggregate reported usage is 16,836,484 tokens. The original eight-hour budget expired at October 4 01:49:25 UTC; no time extension or clock/counter reset is claimed. The judged build has not started. The official offline check is recorded separately; this report does not preclaim its result. Later room activity requires a refreshed export and check. No later-stage, publication, submission or final human-authorship claim is made.
