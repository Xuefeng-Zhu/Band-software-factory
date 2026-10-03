# Toy finish-loop evidence before judged dispatch

The pinned participant guide explicitly permits stopping the toy at any completed stage (lines 746–749). It also directs the participant to finish the toy submission loop: download the full room and run the official offline check, fixing its findings before the real repository matters (lines 817–830). These are preparation instructions, not an extra claim that all four toy stages are an eligibility gate. The factory now requires both observations before a judged freeze or launch preparation can succeed. Existing isolated-harness and collaboration observations remain required.

The two new IDs are `toy_full_room_export` and `toy_offline_submission_check`. Their structural format is in [the JSON schema](../schemas/readiness-observations.schema.json); the [pending example](../templates/readiness-observations.example.json) contains no passing evidence. Merge newly observed records into the existing `runs/readiness/observations.json`, preserving other records and archiving the previous version. Do not replace real history with the example. Bind the report to the current canonical configuration SHA-256 and source-lock file SHA-256.

## Actual full-session export

After the rehearsal finishes, use the guide's console workflow (lines 645–673): open the rehearsal room, select its menu, then **Download → Download full session**. Save that complete download as the configured rehearsal repository's `room.json`. Do not synthesize it from event pages, filter it, or relabel an API response as a full-session download. A locked Mac does not prevent SDK work or local checks, but if the authenticated console cannot be operated, this export remains blocked until the supported download is available.

For `toy_full_room_export`, record `status: PASS`, `observed: true`, actual `observer` and `observed_at`, plus:

```json
{
  "evidence": [{"path": "/absolute/rehearsal/room.json", "sha256": "ACTUAL_SHA256"}],
  "room_export": {
    "file": {"path": "/absolute/rehearsal/room.json", "sha256": "ACTUAL_SHA256"},
    "room_id": "ACTUAL_CONFIGURED_REHEARSAL_ROOM",
    "method": "band_console_full_session",
    "downloaded_at": "ACTUAL_UTC_TIMESTAMP",
    "after_work_complete": true,
    "contents": "unchanged"
  }
}
```

These values must describe an observed download. The validator checks the exact configured path and room, hash, full scope and nonempty message-object array. It cannot cryptographically establish the download's origin or completeness; operator provenance and the guide's workflow remain necessary. The official offline check supplies the seat/mandate and reciprocal-message checks.

Read the complete export privately before committing it. The guide's sole content-edit exception is credential rotation and replacement with `[REDACTED]`. For that exception, use `contents: credential_redaction_only` and attach a `redaction_incident` path/hash reference also present in `evidence`. The incident must record rotation and the limited redaction without retaining the credential value. Its truth is reviewed by the operator; no automatic scanner can establish every private value or credential rotation.

## Retain the actual official offline check

Complete the rehearsal's human-authored `README.md` and `FACTORY.md`, final `mandates/`, genuinely completed stage folders and actual export first. Invoke the configured harness interpreter from the pinned challenge checkout:

```sh
cd /absolute/challenge
/absolute/harness/python -m harness check /absolute/rehearsal --track toy
```

The required invocation JSON is the actual `factorykit.common.run_command` result: `argv`, `cwd`, `started_at`, `finished_at`, integer `exit_code`, `stdout` and `stderr`. Add `repository_before_sha256` and `repository_after_sha256` from `factorykit.validation.toy_repository_digest(config)`, computed immediately before and after the command. Store the invocation outside the toy repository, in a unique operator evidence directory. The digest covers repository files other than the harness's ignored cache/Git directories, including rehearsal evidence. Do not fabricate output or overwrite a prior failure. A failed invocation remains failure evidence.

Once the command actually succeeds, the `toy_offline_submission_check` observation supplies an `invocation` path/hash reference, also present in its `evidence` list. Both snapshots must equal the current repository digest. The validator requires exactly the configured interpreter, `-m harness check`, the configured rehearsal checkout, `--track toy`, the challenge working directory and integer exit code 0. A Docker test, a check of the judged checkout, a claimed pass, or a stale invocation cannot satisfy it. Repository changes after the check require a new successful check; later room activity requires refreshing the full download as the guide directs.

Neither a green offline check nor this observation proves a stage's behavior. Independent fixed-candidate review and final isolated harness evidence remain separate requirements. No GUI availability, export success, live collaboration or stage pass is inferred from the utility tests.
