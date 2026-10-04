# One application repository, one branch per attempt

The participant chose this workflow on October 4, 2026: application attempts share [Xuefeng-Zhu/Tablekeeper](https://github.com/Xuefeng-Zhu/Tablekeeper); reusable factory tools stay in [Xuefeng-Zhu/Tablekeeper-factory](https://github.com/Xuefeng-Zhu/Tablekeeper-factory).

## Current branch map

| Attempt | Canonical branch | Head | Local checkout |
| --- | --- | --- | --- |
| Run 2 | `run-2` | `86ad17c600fd994bcb55c222049b7d0546f2e472` | `../result` contains the navigation `main`; the preserved original is branch `run-2` |
| Run 3 | `run-3` | `dc4cf0c4dcf8b96e155f156694960df7fc1f4745` | `../result-run-3` remains unchanged as the historical checkout |
| Run 4 | `run-4` | `UNBORN` until its first real agent commit | `../result-run-4`, empty except `.git`, origin is the canonical repository |

Run 2 and Run 3 were copied as exact commit histories, without rewriting, merging or squashing. The old Run 3 GitHub repository remains available. The canonical `main` is an attempt index with retained Run 2 files; it is not the base for a fresh judged build.

## Prepare the next attempt

Use a new independent local Git directory with the chosen `run-N` as its initial branch and `origin` pointing to the same canonical repository. Do not check out, merge or pull another attempt or remote default branch into that empty checkout. Do not make a placeholder commit. The existing pristine gate requires `.git` to be a directory, an empty worktree/index and no resolvable `HEAD`; therefore a linked worktree and an empty setup commit are unsuitable before first dispatch.

Run 4 is already prepared at `/Users/frank/mygit/Tablekeeper/result-run-4`. It has `push.default=current` and `remote.pushDefault=origin`; no default-branch upstream is configured. Its first agent-authored commit can be published with:

```sh
git push -u origin HEAD:refs/heads/run-4
```

A branch without any commit cannot exist on GitHub yet. Its current local name and exact future remote destination are recorded in `config/attempts.json`. This metadata is an operator registry, not runtime authorization or a READY result.

A future Run 4 launch needs its own scoped configuration, a new BAND room, fresh permission/config/source checks, generated complete task and a new freeze. Preserve the original Run 3 configuration, packet bytes, source lock, dispatch ledger and room export. Carry forward the full reconciled cumulative usage and obtain a new finite allowance before starting model work. The approved repository organization does not reopen the closed rehearsal budget.

Add the canonical GitHub URL, branch name and explicit push destination through the task generator and new scoped configuration before generating and freezing the complete future dispatch. Do not manually edit a generated packet: deterministic task verification must still pass. Earlier attempt branches are archived evidence and must not seed the new implementation. The factory and challenge remain outside the application worktree. Once the agents create commits, normal worktrees may be used if the particular workflow permits them.

The pinned guide calls for a fresh room and fresh result repository after a restart. This arrangement retains a fresh independent local repository and publishes each attempt's independent history to one shared GitHub repository; the guide does not explicitly discuss branch-per-attempt hosting. For final submission, make the chosen completed branch the normal-clone default after selection, then run the official checks against a fresh clone and verify its files. Do not submit the navigation branch or infer submission approval.

## Verification and evidence

`../runs/repository-consolidation-20261004/` records original and canonical branch heads, the empty Run 4 checkout and migration checks. The factory runtime code and its pristine gate are unchanged. Run 3's source, room export and original launch evidence are unchanged; only references for future repository organization have changed.
