"""One approved Hermes fresh-room/time reconciliation. No network or inference.

Run without --execute to read the required raw input hashes. --execute is one-use
and requires those exact four input bindings. Any partial commit retains its
claim and blocks retry; inspect its before-images and report manually.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import time

import psutil
import yaml

ROOT = Path('/home/azureuser/Tablekeeper-hermes')
RUN = ROOT / 'runs/hermes-glm-mix-20261005T072314Z'
ATTEMPT = RUN / 'attempts/hermes-glm-mix-fresh-20261005T185759Z'
RENEWAL_STARTED = int(datetime(2026, 10, 5, 18, 57, 59, tzinfo=timezone.utc).timestamp())
FOLDER = ATTEMPT / 'accounting-renewal'
sys.path.insert(0, str(ROOT / 'factory'))


def need(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def raw_file(path):
    path = Path(path)
    need(path.is_absolute() and not any(p.is_symlink() for p in (path, *path.parents)),
         'unsafe input path')
    info = path.stat()
    need(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1
         and not info.st_mode & 0o022 and info.st_size <= 16 * 1024 * 1024, 'unsafe input file')
    return path.read_bytes()


def encoded(data):
    return (json.dumps(data, indent=2, sort_keys=True) + '\n').encode()


def fsync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def create(path, raw):
    need(path.parent.is_dir() and not path.parent.is_symlink(), 'missing private evidence directory')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    fsync_directory(path.parent)
    return {'path': str(path), 'sha256': sha(raw)}


def replace(path, raw):
    name = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.renewal-', delete=False) as stream:
            name = stream.name
            os.chmod(name, 0o600)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if name is not None and Path(name).exists():
            Path(name).unlink()


def locks():
    handles = []
    try:
        for path in (RUN / 'runtime/launch.lock', RUN / 'runtime/featherless-requests.json.lock'):
            need(not path.is_symlink(), 'unsafe runtime lock')
            fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            handles.append(fd)
            info = os.fstat(fd)
            need(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1,
                 'unsafe runtime lock identity')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return handles
    except BaseException:
        for fd in handles:
            os.close(fd)
        raise


def stopped(owner):
    need(owner.get('status') == 'stopped', 'original runtime is not stopped')
    for identity in [owner.get('parent', {}), *owner.get('children', [])]:
        need(type(identity.get('pid')) is int and type(identity.get('created')) in (int, float),
             'missing historical process identity')
        try:
            process = psutil.Process(identity['pid'])
            if abs(process.create_time() - identity['created']) <= .001:
                need(not process.is_running() or process.status() == psutil.STATUS_ZOMBIE,
                     'original owned process remains alive')
        except psutil.NoSuchProcess:
            pass
        except psutil.Error:
            raise ValueError('original owner status cannot be established') from None
    binary = str(ROOT / 'tooling/opencode/1.18.34/opencode')
    for process in psutil.process_iter(['username', 'cmdline']):
        try:
            if process.info['username'] == 'azureuser':
                need(binary not in (process.info['cmdline'] or []), 'a pinned OpenCode process is still active')
        except psutil.NoSuchProcess:
            pass
        except psutil.Error:
            raise ValueError('native process status cannot be established') from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--execute', action='store_true')
    for name in ('configuration-sha256', 'original-configuration-sha256', 'factory-budget-sha256', 'request-ledger-sha256'):
        parser.add_argument('--' + name)
    args = parser.parse_args()
    config_path = Path(args.config)
    need(config_path.parent == ATTEMPT and config_path.name == 'factory.yaml', 'unexpected fresh configuration path')
    original_path = RUN / 'factory.yaml'
    budget_path = RUN / 'runtime/budget-session.json'
    requests_path = RUN / 'runtime/featherless-requests.json'
    inputs = {'configuration': (config_path, raw_file(config_path)),
              'original_configuration': (original_path, raw_file(original_path)),
              'factory_budget': (budget_path, raw_file(budget_path)),
              'request_ledger': (requests_path, raw_file(requests_path))}
    current = {name: sha(raw) for name, (_, raw) in inputs.items()}
    if not args.execute:
        print(json.dumps({'status': 'REVIEW_ONLY', 'required_input_sha256': current,
                          'renewal_started_epoch': RENEWAL_STARTED,
                          'deadline_utc': '2026-10-06T00:57:59+00:00',
                          'ledger_writes': 0, 'network_calls': 0, 'inference_calls': 0}, indent=2))
        return 0
    for name, expected in current.items():
        supplied = getattr(args, name + '_sha256')
        need(isinstance(supplied, str) and re.fullmatch(r'[a-f0-9]{64}', supplied)
             and supplied == expected, 'explicit accounting input binding changed')
    need(time.time() < RENEWAL_STARTED + 21600 and time.time() >= RENEWAL_STARTED,
         'renewed six-hour allowance is outside its approved interval')
    handles = locks()
    try:
        need(not FOLDER.exists(), 'renewal is already prepared or claimed; do not retry')
        need(all(raw_file(path) == raw for path, raw in inputs.values()), 'accounting changed before lock')
        owner_path = RUN / 'runtime/owner.json'
        owner_raw = raw_file(owner_path)
        stopped(json.loads(owner_raw))
        from factorykit.common import load_config
        from factorykit.allowance_renewal import reconcile_accounting, renewal_durations
        from factorykit.harnesses import _featherless_metadata
        base, config = load_config(original_path), load_config(config_path)
        need(config['paths']['runs'] == str(RUN), 'fresh configuration selected another accounting directory')
        original_budgets = copy.deepcopy(base['budgets'])
        prepared_budgets = copy.deepcopy(config['budgets'])
        need(original_budgets.pop('approved') is True
             and type(prepared_budgets.pop('approved')) is bool
             and prepared_budgets == original_budgets,
             'fresh configuration altered the original non-time allowance')
        need('time_renewal' not in config['runtime']['featherless_budget_guard'], 'renewal already installed')
        need(config['runtime']['featherless_budget_guard'] == base['runtime']['featherless_budget_guard'],
             'fresh request guard must initially retain the exact original binding')
        need(not {s['agent_id'] for s in config['seats']}.intersection(s['agent_id'] for s in base['seats'])
             and len({s['agent_id'] for s in config['seats']}) == 7, 'fresh agents must be distinct from all old agents')
        for mode in ('rehearsal', 'judged'):
            room = config['band'][mode + '_room_id']
            need(not any((RUN / 'runtime' / (prefix + room + '.json')).exists()
                         for prefix in ('membership-', 'workflow-', 'admission-')),
                 'fresh room already contains runtime evidence')
        factory, guard = json.loads(inputs['factory_budget'][1]), json.loads(inputs['request_ledger'][1])
        need(factory['tokens'] == 24765 and len(guard['requests']) == 4,
             'original four verification requests must remain the only prior paid usage')
        protected = [original_path, RUN / 'source-lock.json', RUN / 'selection.json', owner_path,
                     *sorted((RUN / 'runtime').glob('membership-*.json')),
                     *sorted((RUN / 'runtime').glob('workflow-*.json')),
                     *sorted((RUN / 'tasks').glob('*')), *sorted((RUN / 'mandates').glob('*.md')),
                     RUN / 'readiness/rehearsal-dispatch-claim.json',
                     RUN / 'readiness/rehearsal-dispatch-equivalence.json']
        protected_hashes = {str(p): sha(raw_file(p)) for p in protected if p.is_file()}
        FOLDER.mkdir(mode=0o700, exist_ok=False)
        fsync_directory(ATTEMPT)
        fsync_directory(FOLDER)
        before = FOLDER / 'before'
        before.mkdir(mode=0o700, exist_ok=False)
        fsync_directory(FOLDER)
        fsync_directory(before)
        for name, (_, raw) in inputs.items():
            create(before / (name + ('.yaml' if 'configuration' in name else '.json')), raw)
        create(before / 'owner.json', owner_raw)
        original_config_ref = create(before / 'original_configuration.parsed.json', encoded(base))
        factory_ref = {'path': str(before / 'factory_budget.json'), 'sha256': current['factory_budget']}
        guard_ref = {'path': str(before / 'request_ledger.json'), 'sha256': current['request_ledger']}
        active = [config['band'][mode + '_room_id'] for mode in ('rehearsal', 'judged')]
        old_rooms = factory['room_ids']
        authority = {'schema_version': 1, 'status': 'APPROVED', 'authorization_source': 'direct_user_chat',
            'user_answer': 'approve and continue', 'renewal_started_epoch': RENEWAL_STARTED,
            'renewal_deadline_epoch': RENEWAL_STARTED + 21600, 'renewed_seconds': 21600,
            'original_factory_started_epoch': factory['started_epoch'],
            'original_guard_started_epoch': guard['started_epoch'],
            'original_configuration': original_config_ref, 'original_factory_budget': factory_ref,
            'original_request_ledger': guard_ref, 'active_room_ids': active,
            'cumulative_room_ids': sorted(old_rooms + active),
            'role_models': {s['id']: s.get('model') or base['runtime']['model'] for s in base['seats']}}
        renewal_ref = create(FOLDER / 'approval.json', encoded(authority))
        config['band']['archived_room_ids'] = sorted(old_rooms)
        durations = renewal_durations(authority)
        config['budgets']['approved'] = True
        config['budgets']['overall_timeout_seconds'] = durations['factory']
        config['runtime']['featherless_budget_guard'].update(overall_timeout_seconds=durations['guard'],
                                                            time_renewal=renewal_ref)
        new_factory, new_guard = reconcile_accounting(config, factory, guard, _featherless_metadata(base))
        new_raw = {'configuration': yaml.safe_dump(config, sort_keys=False).encode(),
                   'factory_budget': encoded(new_factory), 'request_ledger': encoded(new_guard)}
        target_hashes = {name: sha(raw) for name, raw in new_raw.items()}
        claim = {'schema_version': 1, 'status': 'CLAIMED',
                 'claimed_at_utc': datetime.now(timezone.utc).isoformat(),
                 'approval': renewal_ref, 'before_sha256': current, 'after_sha256': target_hashes,
                 'helper_sha256': sha(raw_file(Path(__file__).resolve()))}
        create(FOLDER / 'claim.json', encoded(claim))
        need(all(raw_file(path) == raw for path, raw in inputs.values())
             and all(sha(raw_file(Path(p))) == expected for p, expected in protected_hashes.items()),
             'protected inputs changed before commit')
        # The original config becomes blocked once its scope/policy no longer matches.
        # The new config receives authority last, under both original runtime locks.
        replace(requests_path, new_raw['request_ledger'])
        replace(budget_path, new_raw['factory_budget'])
        replace(config_path, new_raw['configuration'])
        need(all(sha(raw_file(inputs[name][0])) == expected for name, expected in target_hashes.items()),
             'renewal commit hash mismatch')
        need(all(sha(raw_file(Path(p))) == expected for p, expected in protected_hashes.items()),
             'historical evidence changed')
        from factorykit.budgets import persisted_budget_blockers
        need(not persisted_budget_blockers(config, require_existing=True), 'renewed accounting did not pass production inspectors')
        result = {'schema_version': 1, 'status': 'PASS', 'configuration': str(config_path),
                  'completed_at_utc': datetime.now(timezone.utc).isoformat(), 'approval': renewal_ref,
                  'before_sha256': current, 'after_sha256': target_hashes,
                  'original_started_epoch_preserved': True, 'protected_unchanged': True,
                  'tokens_preserved': 24765, 'request_count_preserved': 4,
                  'requests_unchanged': new_guard['requests'] == guard['requests'],
                  'factory_turns_preserved': new_factory['turns'] == factory['turns'],
                  'deadline_utc': '2026-10-06T00:57:59+00:00',
                  'network_calls': 0, 'inference_calls': 0, 'full_dispatch_count': 0}
        create(FOLDER / 'commit-report.json', encoded(result))
        print(json.dumps(result, indent=2))
        return 0
    finally:
        for fd in reversed(handles):
            os.close(fd)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        message = str(error) if isinstance(error, ValueError) else 'renewal failed; details suppressed'
        print(json.dumps({'status': 'BLOCKED_PRESERVE_CLAIM_AND_BEFORE_IMAGES', 'reason': message,
                          'network_calls': 0, 'inference_calls': 0}), file=sys.stderr)
        raise SystemExit(1)
