S1-QA REVIEW. Owner @frankzhu94/factory-qa; next recipient @frankzhu94/factory-pm; independent release authority @frankzhu94/factory-reviewer. No product acceptance claimed.
Complete input S1-QA-001 all3 parts verified SHA-256b6b0ff1fda95064a745409bb7c1a45aa6c4db8b5beba8b97f8e685d194f164d4; receipt4ec185f9-6b60-4603-8d72-5659a18dbd02; IN_PROGRESS e71e9e91-421c-435f-b60e-9203b2e408d6. Final summary roomd50d873a-dbb1-4e9f-8826-882c679d2337.
Fixed product candidate 7960081554f92cbe1a61d377b8dfd651ae90487b; original starting/current shared HEAD9d02432fcbd94a2f4558a355394ecb2a482a26a2 is queue-only with identical stage1. Repository /Users/frank/mygit/Tablekeeper/result-run-6. Separate clean exact detached clone /var/folders/0k/rqgj4mxn54j3_78wyykw4xnh0000gn/T/tablekeeper-qa-s1-tqlr4ju1/candidate; verified full SHA/clean before and after. Evidence-only execution, no production/QA tracked files or queue records changed, no new commit. Sole QA artifact lease RELEASED on delivery. Author setting not needed because no commit. No attributable history rewritten.
Goal/acceptance: independently execute existing requirement-based boundaries on exact S1; add auth/privacy/error/ID/key scope/cutoff/moves/import/ledger probes, prioritize first runnable gaps, retain failures, distinguish real constrained-container/host/internal-clock layers. Return exact commands/results/evidence and missing behavior. Owner120/120 was not used as independent evidence. Reviewer still must execute official isolated gate and decide exact-candidate acceptance. Complete applicable assignment and S1 specification follow.
Observed outcome: no definite product defect found in executed cases. Existing7 selected HTTP groups PASS on fresh host service and on independently built constrained container. Additional5 groups PASS (4host HTTP,1in-process fixed clock). Container50 concurrent logins all200,max1.858073805s. These are example/invariant probes,not exhaustive proof. No stage2+ service/browser/upgrade was run or accepted.
Requirements/evidence map:
S1 sections5/7, Q03/Q04/Q06/Q08: digit-only queries,type overrides,1/255/256 key boundaries,typed JSON metadata,original receipt replay after cancellation and fractional1.0000000000000001 vs1.0 before/after raw import: PASS in http.json and container-http.json.
S1 sections1/7/11,Q09/Q17/Q18: 50 identical requests one201+49replays and50distinct keys one201+49conflicts;atomic swaps,unchanged listed occupancy,nonoccupancy-before-overlap and failed-key reuse: PASS on host/container existing driver. Container concurrent group total0.1775s (group duration,not per-request maximum).
S1 sections4/8/9,Q12/Q13/Q14: Berlin/NewYork mandatory2026 spring gaps and first folds,exact absolute90min ends;Berlin02:15 gap opening retains03:15/03:45/04:15 and all3 creates with correct end;gap/off-grid refusals: PASS host/container.
S1 sections3/5/6/7/8,Q02/Q03/Q05/Q07:64/65 fixture IDs;malformed/nonobject/missing/impossible inputs;signup7/8password boundary,duplicate email,wrong login,owner privacy,public access,concurrent-valid session tokens,same key across users and exact same body/key across reservations/moves: PASS extra-results.json.
S1 sections1/8/11,Q10/Q11/Q16/Q17/Q18:half-open touching vs overlapping intervals,editable no-op,invalid0/9/duplicate/malformed moves,past creation,current cutoff beating changed fields,ordered nonoccupancy failures: PASS extra-results.json.
S1 section10,Q19/Q20/Q06:actual distinct source process creates/amends/cancels,export held only in memory;source terminated before destination import;repeat replacement,old credentials/tokens/live records and original fractional receipt preserved;destination credentials removed;invalid import variants retain complete snapshot;reset clears import: PASS extra-results.json. No source filesystem/network dependence observed for this sequence. No export/token printed or saved.
Private factual-ledger obligation,Q32 and internal Q16: instantiated exact candidate Service with independent clock;ledger returns detached facts;created t1,changed t1->t2,cancelled empty changes at exact supplied separate times;revisions1/2/3;no-op/replay/repeated cancel preserve facts;fresh Service import retains exact facts. One microsecond before cutoff allowed;exact equality refuses before invalid proposed party. PASS in-process,not HTTP equality or S3 migration evidence. Actual S1 private schema now safely exercised without credential dump.
S1 deployment/resource: independently built image sha256:fe1557d050fa9d854543efdc68db147069bcbbc34f276cc86a4f23623b959a56;container0c04bc56ed81d2ee78ab207dc7ab58b61852f773c6a20214a7ff57456ef31c5b had NanoCpus2000000000,Memory2147483648,NetworkMode none. Clients ran inside same constrained container. Seven driver groups and50login burst PASS. Fixture size2tables/1user/small reservation counts. This is not the official harness or a100/1000-history throughput claim.
Failure preservation and recovery: first host launch used Popen children from a completed setup command; subsequent7groups all failed URLError because those processes did not remain connected. Preserved attempt-01/http.json (exit1). Changed diagnosis/approach: launch fresh services in persistent exec sessions1774/68678,rerun in new attempt-02 output=>7PASS exit0. Not a product fix. Cleanup literal cwd guard failed on /var vs/private/var alias; canonical-path retry hit PermissionError EPERM on direct os.kill. Did not broaden permissions; owned exec sessions were successfully stopped via write_stdin Ctrl-C (expected130),container stopped via docker stop(exit0),portable source terminated by its own running test process. cleanup.json preserves these failures. Stopped container/clone/evidence retained.
Evidence root /Users/frank/mygit/Tablekeeper/result-run-6/.evidence/qa-s1-20261005. attempt-01/setup.json binds revision/clone/start/room events; attempt-01/http.json preserves transport failures; attempt-01/docker-build.log records build. attempt-02/http.json,container-http.json,extra.py,extra-results.json,container-load.py,container-auth50.json,container-limits.txt,cleanup.json,execution.json contain reproducible commands/results and UTC timestamps. execution started 2026-10-05T02:14:17.543197+00:00;finished 2026-10-05T02:20:40.406403+00:00. Extra script responsible QA; no test code committed because evidence-only authority was preferred.
Exact command/status inventory follows in JSON; credential values excluded:
[
  {
    "command": "git fetch origin",
    "exit_status": 0
  },
  {
    "command": "git clone --no-hardlinks /Users/frank/mygit/Tablekeeper/result-run-6 /var/folders/0k/rqgj4mxn54j3_78wyykw4xnh0000gn/T/tablekeeper-qa-s1-tqlr4ju1/candidate; git -C /var/folders/0k/rqgj4mxn54j3_78wyykw4xnh0000gn/T/tablekeeper-qa-s1-tqlr4ju1/candidate checkout --detach 7960081554f92cbe1a61d377b8dfd651ae90487b; git status/rev-parse",
    "exit_status": 0,
    "observed": "clean exact candidate; clone outside submission"
  },
  {
    "command": "/Users/frank/mygit/Tablekeeper/runs/harness-venv/bin/python /var/folders/0k/rqgj4mxn54j3_78wyykw4xnh0000gn/T/tablekeeper-qa-s1-tqlr4ju1/candidate/qa/stage1_http.py --base-url http://127.0.0.1:19091 --candidate 7960081554f92cbe1a61d377b8dfd651ae90487b --out /Users/frank/mygit/Tablekeeper/result-run-6/.evidence/qa-s1-20261005/attempt-01/http.json",
    "exit_status": 1,
    "observed": "all7 transport failures; initial Popen child services did not remain connected; output preserved; not product defect"
  },
  {
    "command": "PORT=19091/19092 PYTHONDONTWRITEBYTECODE=1 /Users/frank/mygit/Tablekeeper/runs/harness-venv/bin/python server.py (two separate persistent exec sessions; cwd /var/folders/0k/rqgj4mxn54j3_78wyykw4xnh0000gn/T/tablekeeper-qa-s1-tqlr4ju1/candidate/stage-1)",
    "exit_status": null,
    "observed": "sessions1774/68678 active during tests; intentionally ended130 afterward"
  },
  {
    "command": "/Users/frank/mygit/Tablekeeper/runs/harness-venv/bin/python /var/folders/0k/rqgj4mxn54j3_78wyykw4xnh0000gn/T/tablekeeper-qa-s1-tqlr4ju1/candidate/qa/stage1_http.py --base-url http://127.0.0.1:19091 --candidate 7960081554f92cbe1a61d377b8dfd651ae90487b --out /Users/frank/mygit/Tablekeeper/result-run-6/.evidence/qa-s1-20261005/attempt-02/http.json",
    "exit_status": 0,
    "observed": "7/7 selected HTTP groups PASS"
  },
  {
    "command": "docker build -t tablekeeper-qa-s1-7960081 /var/folders/0k/rqgj4mxn54j3_78wyykw4xnh0000gn/T/tablekeeper-qa-s1-tqlr4ju1/candidate/stage-1",
    "exit_status": 0
  },
  {
    "command": "docker run -d --name tablekeeper-qa-s1-7960081 --cpus=2 --memory=2g --network none tablekeeper-qa-s1-7960081",
    "exit_status": 0,
    "observed": "container0c04bc56ed81d2ee78ab207dc7ab58b61852f773c6a20214a7ff57456ef31c5b; image sha256:fe1557d050fa9d854543efdc68db147069bcbbc34f276cc86a4f23623b959a56"
  },
  {
    "command": "docker cp /var/folders/0k/rqgj4mxn54j3_78wyykw4xnh0000gn/T/tablekeeper-qa-s1-tqlr4ju1/candidate/qa/stage1_http.py tablekeeper-qa-s1-7960081:/tmp/stage1_http.py; docker exec tablekeeper-qa-s1-7960081 python /tmp/stage1_http.py --base-url http://127.0.0.1:8080 --candidate 7960081554f92cbe1a61d377b8dfd651ae90487b --out /tmp/qa-http.json; docker cp result to /Users/frank/mygit/Tablekeeper/result-run-6/.evidence/qa-s1-20261005/attempt-02/container-http.json",
    "exit_status": 0,
    "observed": "7/7 groups PASS, includes two50-client booking races"
  },
  {
    "command": "PYTHONDONTWRITEBYTECODE=1 /Users/frank/mygit/Tablekeeper/runs/harness-venv/bin/python /Users/frank/mygit/Tablekeeper/result-run-6/.evidence/qa-s1-20261005/attempt-02/extra.py",
    "exit_status": 0,
    "observed": "5/5 groups PASS;4 host HTTP groups,1 fixed-clock in-process group"
  },
  {
    "command": "docker cp /Users/frank/mygit/Tablekeeper/result-run-6/.evidence/qa-s1-20261005/attempt-02/container-load.py tablekeeper-qa-s1-7960081:/tmp/container-load.py; docker exec tablekeeper-qa-s1-7960081 python /tmp/container-load.py; docker cp /tmp/qa-auth50.json to /Users/frank/mygit/Tablekeeper/result-run-6/.evidence/qa-s1-20261005/attempt-02/container-auth50.json",
    "exit_status": 0,
    "observed": "50/50 logins200;max1.858073805s; each<=5s"
  },
  {
    "command": "docker inspect --format NanoCpus,Memory,NetworkMode,Image tablekeeper-qa-s1-7960081",
    "exit_status": 0,
    "observed": "2000000000,2147483648,none,expected image"
  },
  {
    "command": "git status --short in shared checkout and exact clone; clone git rev-parse HEAD",
    "exit_status": 0,
    "observed": "both clean; clone fixed at7960081554f92cbe1a61d377b8dfd651ae90487b"
  }
]
Missing/NOT_TESTED: official independent isolated harness gate; full request/cardinality bounds beyond selected fixtures;100/1000history throughput;mass signup/mixed read-write linearizability;every move count1..8 and all cross-restaurant fault combinations;all auth/email/ID permutations;correlated malformed private ledger/receipt-state tampering;all list ordering and availability-empty/closed extremes;exact HTTP cutoff equality (only in-process observed);wall closing conventions beyond mandatory opening case;source-to-later-stage history projection and real browser/session upgrades;S2–S4/UI/design/performance planner. These missing classes are not labelled PASS by their mapped group. No observed definite defect to repair; owner has used1of3 product repairs,2remain.
Next action PM: send fixed 7960081554f92cbe1a61d377b8dfd651ae90487b plus this complete evidence to Reviewer for official isolated S1 gate immediately; no copy into S2 before acceptance. Lease released; no new source commits. Remaining limits one active writer/seat,ack120s,max2delivery retries,600s turn with reserve; current turn finish-work2026-10-05T02:22:25.531789+00:00,end02:23:25.531789+00:00,cumulative2026-10-05T02:35:03.700437+00:00. Subscription only,no API billing/paid provisioning/human steering/operator mutation. Measured consumption UNAVAILABLE. Delivery receipt is not release acceptance.
