# Run 6 independent Stage 1 QA — 02:23 UTC receipt snapshot

QA independently checked exact product candidate [`7960081554f92cbe1a61d377b8dfd651ae90487b`](https://github.com/Xuefeng-Zhu/Tablekeeper/commit/7960081554f92cbe1a61d377b8dfd651ae90487b) in a [clean detached clone](setup.json). [Execution](execution.json) ran from 02:14:17 to 02:20:40 UTC and returned state **REVIEW**. QA found no definite product defect in the executed cases. This is not full-specification acceptance; Reviewer's official isolated gate remained pending.

The [complete QA report](review.md) preserves coverage and missing classes. These are independent QA results, separate from [Backend's owner-run 120/120 suite](../run6-stage1-owner-checkpoint-20261005/README.md):

| Evidence | Recorded result | Layer |
| --- | --- | --- |
| [Initial HTTP attempt](attempt-01-http.json) | 7 transport failures | QA attributed the failures to initial service process lifetime; no product defect established |
| [Second host attempt](host-http.json) | 7 selected groups passed | HTTP against a fresh host service |
| [Container driver](container-http.json) | 7 selected groups passed | Independently built application container; includes two 50-client booking races |
| [Extra results](extra-results.json) | 5 groups passed | Four host HTTP groups and one in-process Service group using an independent fixed clock |
| [Container login burst](container-auth50.json) | 50/50 responses were 200; maximum 1.858074 seconds | Clients and service inside the same constrained container |

[Observed container settings](container-limits.txt) were 2 CPUs, 2 GiB and network mode `none`, image `sha256:fe1557d050fa9d854543efdc68db147069bcbbc34f276cc86a4f23623b959a56`. These selected small-fixture tests do not establish every resource, cardinality or history-throughput requirement. Exact private-ledger times and cutoff equality were tested in-process, not as HTTP equality or later-stage migration. Correlated malformed ledger/receipt tampering, full boundary combinations, browser/UI and Stage 2–4 upgrades remained unverified.

Initial transport failures remain unchanged. The execution record also retains cleanup failures: a literal-path guard rejected the `/var` alias and a subsequent direct signal encountered `EPERM`. QA then ended its owned terminal sessions using Ctrl-C (expected exit 130) and stopped its container (exit 0). The stopped container and clone were retained. No source repair was made for these test-environment failures.

[Selected public events](public-events.json) preserve QA's final three-part handoff announcement `21fbaff6-7a01-4807-86cd-1870aba6815c` at **02:21:03.966755 UTC**, and PM's complete acknowledgment `a0c4e3b2-6c2b-46ed-a5dc-721cfc6cbc8b` at **02:23:05.478637 UTC**, for `S1-QA-RESULT-001`, digest `aaec1f1509775c4c71189a2a4263ee24b6b0508b6914a31b71941335315ed487`. That later public ACK establishes receipt without rewriting earlier local delivery metadata. The selection contains three texts from a page with `has_more=true`; it is not a full-session export. Receipt is not stage acceptance.

[The manifest](manifest.json) binds ten unchanged source copies. The original evidence is ignored/untracked; no tracked application or queue file changed during QA, according to its completed record. The compact archive records hashes/locations for the omitted `extra.py` and `container-load.py` reproduction dependencies; it is not a standalone replay package. No test, product command or BAND operation was executed while archiving, and all 34 frozen inputs remained unchanged. The bounded official-pattern, supplemental credential and content review found no matches or actionable findings. No state exports or credential values were copied. This supports private preservation, not exhaustive privacy assurance or public-release approval. Existing budgets, deadline and repair limits remain unchanged.
