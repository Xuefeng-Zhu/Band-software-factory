# Final Tablekeeper repository contract

Authoritative source: [The repository you submit](https://github.com/band-ai/dark-factory-wearedevs/blob/main/docs/participant-guide.md#the-repository-you-submit).

The Git root `/Users/frank/mygit/Tablekeeper/result` maps directly to https://github.com/Xuefeng-Zhu/Tablekeeper. Judges must see this layout at the repository root:

```text
README.md       # human entrant: MillieMoon, track, navigation and reproduction
FACTORY.md      # human entrant: actual seats, choices, costs, failures and recovery
mandates/       # seven real seat files, each naming its harness and model
room.json       # genuine full-session BAND download after the judged run
stage-1/        # completed stage: Dockerfile, RUN.md and source
stage-2/        # include only when genuinely completed
stage-3/        # include only when genuinely completed
stage-4/        # include only when genuinely completed
```

Each included stage is independently buildable and preserves its original stage scope. No nested repositories, submodules or symlink shortcuts. The factory tooling, pinned challenge checkout, credentials and operator control records stay outside this Git root. Do not create empty stage placeholders or synthetic room exports to satisfy layout checks.

The checked-in factory tools live separately at https://github.com/Xuefeng-Zhu/Tablekeeper-factory. That repository is not the entry submitted to judges.

Final validation runs the official offline `harness check` and the isolated `harness run` against an exact committed candidate, then repeats checks from a fresh public clone. Both GitHub repositories are private during development; the final submission repository must become public before submission, with user authorization for that visibility change. No entry is submitted by this template.
