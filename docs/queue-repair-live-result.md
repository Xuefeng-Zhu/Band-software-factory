# Queue repair live rehearsal — October 4, 2026

**Result: both communication scenarios passed in the real BAND room.** This is an unscored synthetic rehearsal of factory revision `c53ea314f21ab37f36e927ab503c086bd2ecced9`. It does not resume Run 3 or establish new application acceptance.

The participant approved one new 30-minute allowance, up to 2,000,000 additional reported tokens within the original 100,000,000 cumulative cap, subscription only. The operator created a new room with the same seven seats and Frank, bound a separate empty practice checkout, completed fresh registration/authentication/permission preflight, and sent the complete task exactly once. No human follow-up was sent.

- Room: `4ec4749d-5dff-4d41-ae9b-5a5bc82462ac` — [MillieMoon · Queue Repair Rehearsal](https://app.band.ai/sessions/4ec4749d-5dff-4d41-ae9b-5a5bc82462ac).
- Initial dispatch: `dcb6d175-0b5a-41cc-8abf-c89b18c59559`; send began 17:22:12.648744 UTC.
- Task SHA-256: `a3101534d02f5d86c24399c2d50dde84dac0fee6ef149744679943996dacc871`; actual room text matched exactly.
- PM final: `ae15b3c2-c8ae-4130-a539-1610114221bd`, `QUEUE-REHEARSAL COMPLETE`, at 17:29:39.374619 UTC.
- Owned workers stopped at 17:30:15.829285 UTC, 483.18 seconds after dispatch, inside the ten-minute exercise limit. Fresh process identity checks found no surviving owned parent or recorded child.

## What happened

PM sent Backend a complete ordinary assignment. Backend's separate readiness reply preceded every numbered fixture part. Only PM and Backend took model turns; the other five seats remained idle.

| Scenario | Actual observation | Result |
| --- | --- | --- |
| A: twelve promptly sent parts | All twelve original payload lines were delivered in order. Backend computed the 216-byte payload's SHA-256 and sent canonical ACK `87995659-f1fa-4267-bf5f-48c3229e40c2` at 17:26:17.738568 UTC. | Complete receipt verified. |
| A: deadline while callbacks were busy | The original ACK deadline was 17:25:59.671707 UTC. There were 36 captured SDK-busy observations between that deadline and the ACK, including two with no admitted model turn. The original incident remained unresolved and notice count stayed zero. | The local SDK processing barrier was exercised live, including the gap the old runtime missed. |
| B: deliberately missing original part 2 | PM sent only part 1 after A's actual ACK. Backend yielded without a premature ACK or missing-part request. The supervisor sent one notice from original PM to original Backend after the 120-second wait. | Genuine bounded recovery routing verified. |
| B: complete the existing delivery | Backend requested original part 2, PM sent it with the same identity/digest, Backend recomputed the 36-byte payload's digest and sent canonical ACK `4029c172-0886-477e-b7af-85ef29af4d5c`. | The original incident resolved after one notice, within its two-notice cap. |

B's evidence chain is: part 1 `098f5c50-04fa-4990-9260-51c6801a44d1` → notice `a8dddf6d-0c1f-4726-bca3-b1f96ea4fd3e` → actual peer request `a9e9d3d9-4092-4201-9cd9-b784c0e2824e` → original part 2 `d701d5d2-e6d4-43a9-9200-c0bfc8f1256e` → ACK above. The notice appeared at 17:28:29.442030 UTC, 120.548 seconds after the room's B part-1 event. No fabricated human message, self-message bypass, replacement payload or unknown-send retry was used.

The early observer file collected 55 samples after A's deadline but included later B activity. Final audits correctly restrict the A claim to the 36 samples before A's actual ACK. The raw observation stream is preserved.

## Limits and cumulative accounting

There were 22 completed, non-overlapping model turns: PM 5, Backend 17. The longest lasted 83.65 seconds, below the 600-second ceiling. The final PM message caused one last Backend callback; that callback ended without another text message. All work was idle before shutdown.

| Accounting | Reported tokens |
| --- | ---: |
| Previous cumulative usage | 84,080,166 |
| This rehearsal | 1,931,411 |
| New cumulative usage | 86,011,577 |
| Rehearsal's cumulative ceiling | 86,080,166 |

These are reported tokens including cached input, not measured monetary cost. Authentication remained subscription-only; no API billing or paid provisioning was authorized. All 28 historical thread high-water marks and the original cumulative clock origin `1791049765.700437` were retained. Two new thread totals account for the entire increase.

After verified shutdown, the raw final ledger was preserved and its full cumulative contents promoted to the canonical ledger. The only subsequent changes were explicit global/rehearsal closure markers and an updated timestamp. Both current copies contain the same complete accounting. The original configuration still has its prior room scope and correctly rejects the expanded ledger; the scoped rehearsal configuration also rejects its closed ledger. No future launch can rely on the old lower total. Further live work requires fresh explicit authorization and reconciliation; the unused 68,589 tokens are not a standing permission to restart.

## Evidence and preservation

The unchanged BAND console **Download full session** export contains 392 events and exactly one human text message. Its SHA-256 is `f34276e8fe262c2c9cc2b7cc08242d4b0f4f279f72ca46859a77574b5dff9c26`. API snapshots were used for observation only; they did not replace the export.

Selected evidence is committed under [`evidence/queue-repair-20261004/`](../evidence/queue-repair-20261004/), with a file-hash manifest. The full operator record remains at `/Users/frank/mygit/Tablekeeper/runs/queue-repair-live-20261004/`. The exact dispatch packet, actual export, queue samples, workflow state, independent audits, raw final usage and reconciliation record are retained.

Run 3 remains at application HEAD `dc4cf0c4dcf8b96e155f156694960df7fc1f4745`, Stage 1 tree `4917af2a996c6e3327933deb84281ad29a30c1f1`. Its original `room.json` SHA-256 remains `2008460d0d1cff521027f03d974ff24c718aed8708584223638f6b754aa7ccae`. Its original configuration, source lock, freeze and dispatch ledger were not rewritten. The new practice checkout remains unborn and contains only `.git`.

A fresh permission probe automatically added one trust entry for its neutral scratch directory to the global Codex configuration. The retained trust audit proved that removing only this entry in memory reconstructed the pinned configuration hash exactly. The source lock was not silently updated: the old strict source check still flags the changed global config bytes. A future judged freeze must explicitly account for that drift and the repaired runtime; this rehearsal alone does not make it READY.

## Scope of the result

The existing 224 offline factory tests passed before this run. This live exercise adds actual BAND delivery, digest receipts, overdue local processing and original-sender recovery evidence. Local SDK idle does not prove absence of remote backlog. The test uses synthetic text fixtures and does not establish Stage 2–4 implementation, new product acceptance, participant authorship, public release or submission readiness.
