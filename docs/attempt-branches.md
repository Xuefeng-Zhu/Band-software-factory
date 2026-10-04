# One application repository, one branch per attempt

The participant chose this workflow on October 4, 2026: application attempts share [Xuefeng-Zhu/Tablekeeper](https://github.com/Xuefeng-Zhu/Tablekeeper); reusable factory tools stay in [Xuefeng-Zhu/Tablekeeper-factory](https://github.com/Xuefeng-Zhu/Tablekeeper-factory).

## Current branch map

| Attempt | Canonical branch | Head | Local checkout |
| --- | --- | --- | --- |
| Run 2 | `run-2` | `86ad17c600fd994bcb55c222049b7d0546f2e472` | `../result` contains the navigation `main`; the preserved original is branch `run-2` |
| Run 3 | `run-3` | `dc4cf0c4dcf8b96e155f156694960df7fc1f4745` | `../result-run-3` remains unchanged as the historical checkout |
| Run 4 | `run-4` | Final preserved head `13bc38fc1d4396c70c42b529eab369d6f84a0186`; BLOCKED with no accepted stage | `../result-run-4`; origin is the canonical repository |
| Run 5 | `run-5` | Remote head `0b193c068341b5e81f82b354e25eab12355e77dc` observed at `2026-10-04T21:08:57Z`; one dispatch, runtime in progress, no accepted stage claimed | `../result-run-5`; independently initialized empty before launch, same canonical origin |

Run 2 and Run 3 were copied as exact commit histories, without rewriting, merging or squashing. The old Run 3 GitHub repository remains available. The canonical `main` is an attempt index with retained Run 2 files; it is not the base for a fresh judged build.

## Prepare the next attempt

Use a new independent local Git directory with the chosen `run-N` as its initial branch and `origin` pointing to the same canonical repository. Do not check out, merge or pull another attempt or remote default branch into that empty checkout. Do not make a placeholder commit. The existing pristine gate requires `.git` to be a directory, an empty worktree/index and no resolvable `HEAD`; therefore a linked worktree and an empty setup commit are unsuitable before first dispatch.

Run 4 was initialized at `/Users/frank/mygit/Tablekeeper/result-run-4` with `push.default=current` and `remote.pushDefault=origin`. Its agents publish to the exact assigned branch with:

```sh
git push -u origin HEAD:refs/heads/run-4
```

A branch without any commit cannot exist on GitHub. Run 4 began empty, published attributable agent progress, and is now closed. Its final head preserves the rejected product and complete room export; it is not a base for another attempt. The exact destination and observed head are recorded in `config/attempts.json`; this operator registry is not itself runtime authorization.

Run 4 used its own scoped configuration, a new BAND room, fresh permission and registration checks, and deterministically generated complete task packets. The participant approved its finite allowance and one launch; the READY freeze and verified dispatch are retained in `evidence/run4-launch-20261004/`. Independent review ultimately rejected Stage 1 despite 120/120 official isolated checks, and all three repair cycles were exhausted. No stage was accepted and stages 2–4 were not started. All owned workers stopped and the allowance closed at `2026-10-04T20:32:48Z`. See [the final outcome](run4-outcome.md) and `evidence/run4-closure-20261004/`.

Preserve the original Run 3 configuration, packet bytes, source lock, dispatch ledger and room export. Run 4 retained the full reconciled cumulative history: 59,671,522 additional reported tokens and 145,683,099 cumulative. Repository organization and unused allowance never reopen a closed attempt. Run 5 received separate approval at `2026-10-04T20:59:53Z` and one verified task dispatch at `2026-10-04T21:06:55.943682Z`; its agents are now working within the unchanged cumulative ceiling and deadline. Its remote branch exists and may advance. See [the approved launch review](run-5-preparation.md); no accepted stage is implied by dispatch or publication.

The task generator now accepts the canonical GitHub URL and branch through optional `product` configuration and emits the explicit push destination in judged packets. The pristine gate checks both the assigned branch and every effective origin fetch/push URL. Do not manually edit a generated packet: deterministic task verification must still pass. Earlier attempt branches are archived evidence and must not seed the new implementation. The factory and challenge remain outside the application worktree. Once the agents create commits, normal worktrees may be used if the particular workflow permits them.

The pinned guide calls for a fresh room and fresh result repository after a restart. This arrangement retains a fresh independent local repository and publishes each attempt's independent history to one shared GitHub repository; the guide does not explicitly discuss branch-per-attempt hosting. For final submission, make the chosen completed branch the normal-clone default after selection, then run the official checks against a fresh clone and verify its files. Do not submit the navigation branch or infer submission approval.

## Verification and evidence

`../runs/repository-consolidation-20261004/` records original and canonical branch heads, the empty Run 4 checkout and migration checks. The factory now checks the exact branch and origin, and resolves optional attempt-owned source locks and tasks. Existing configurations retain their original paths and packet bytes. Run 3's source, room export, configuration, packets and original launch evidence remain unchanged.

## Scoped configuration

Optional attempt metadata is validated before task generation or launch:

```yaml
product:
  repository_url: https://github.com/Xuefeng-Zhu/Tablekeeper.git
  branch: run-4
artifacts:
  source_lock: /Users/frank/mygit/Tablekeeper/runs/run4-preparation-20261004/source-lock.json
  tasks: /Users/frank/mygit/Tablekeeper/runs/run4-preparation-20261004/tasks
```

Artifact overrides must stay beneath that configuration's `paths.runs`; lock and task paths cannot overlap or escape through symlinks. Omitting these fields preserves the original defaults. Freeze records the configured lock hash, and both launch preparation and direct judged start reject a changed lock.

The historical preparation and launch review lives in [run-4-preparation.md](run-4-preparation.md); [run4-outcome.md](run4-outcome.md) records the closed result. Preparation alone does not approve an allowance, open a closed usage ledger or send a task.
