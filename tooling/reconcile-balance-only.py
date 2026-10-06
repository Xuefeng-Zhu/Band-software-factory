"""Review-bound, offline balance-only room/accounting amendment.

Dry-run by default. Explicit execute preserves before-images, current accounting
and original failures while changing only the new configuration, ledger room
scope and authorized guard policy. No network, inference, room creation or spend.
"""
from __future__ import annotations

import argparse
import copy
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import sys
import tempfile
import time
from uuid import UUID

import psutil
import yaml


def need(value, reason):
    if not value:
        raise ValueError(reason)


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def raw_file(path):
    need(path.is_absolute() and not any(p.is_symlink() for p in (path, *path.parents)), 'unsafe input path')
    info = path.stat()
    need(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1
         and not info.st_mode & 0o022 and info.st_size <= 16 * 1024 * 1024, 'unsafe input file')
    return path.read_bytes()


def sync(path):
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0) | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def create(path, raw):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    sync(path.parent)
    return {'path': str(path), 'sha256': sha(raw)}


def replace(path, raw):
    name = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.balance-', delete=False) as stream:
            name = stream.name; os.chmod(name, 0o600)
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        os.replace(name, path); sync(path.parent)
    finally:
        if name is not None:
            Path(name).unlink(missing_ok=True)


def stopped(owner):
    need(owner.get('status') in ('stopped', 'failed'), 'runtime is not stopped')
    for identity in [owner.get('parent', {}), *owner.get('children', [])]:
        need(type(identity.get('pid')) is int and type(identity.get('created')) in (int, float), 'missing process identity')
        try:
            process = psutil.Process(identity['pid'])
            if abs(process.create_time() - identity['created']) <= .001:
                need(not process.is_running() or process.status() == psutil.STATUS_ZOMBIE, 'owned process remains alive')
        except psutil.NoSuchProcess:
            pass
        except psutil.Error:
            raise ValueError('process ownership is unavailable') from None


def locks(run, request_path):
    handles = []
    try:
        for path in (run / 'runtime/launch.lock', request_path.with_suffix(request_path.suffix + '.lock')):
            need(not path.is_symlink(), 'unsafe runtime lock')
            fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            handles.append(fd)
            info = os.fstat(fd)
            need(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1, 'unsafe runtime lock identity')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return handles
    except BaseException:
        for fd in handles:
            os.close(fd)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('factory', 'before-config', 'config', 'evidence-dir', 'rehearsal-room'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--approved-epoch', type=float, required=True)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--review-sha256')
    args = parser.parse_args(argv)
    factory_root, before_path, target, folder = map(Path, (args.factory, args.before_config, args.config, args.evidence_dir))
    for path in (factory_root, before_path, target, folder):
        need(path.is_absolute() and not any(p.is_symlink() for p in (path, *path.parents)), 'unsafe configuration/evidence path')
    need(before_path != target and folder.parent.is_dir() and not folder.exists(), 'fresh configuration/evidence required')
    need(math.isfinite(args.approved_epoch) and 0 < args.approved_epoch <= time.time(), 'invalid explicit approval epoch')
    need(str(UUID(args.rehearsal_room)) == args.rehearsal_room, 'canonical rehearsal UUID required')
    sys.path.insert(0, str(factory_root))
    from factorykit.common import contains_secret, load_config
    from factorykit.allowance_renewal import validate_renewal_config, validate_retained_factory_accounting
    from factorykit.allowance_scope import preserve_configuration_policy, reconcile_balance_scope
    from factorykit.budgets import budget_ledger_path, room_scope
    from factorykit.featherless_guard import _Ledger, _policy
    from factorykit.harnesses import _featherless_metadata
    configuration_inputs = {'before_configuration': raw_file(before_path), 'configuration': raw_file(target)}
    before = load_config(before_path)
    need(not contains_secret(configuration_inputs['configuration'].decode()), 'prepared seed contains a possible credential')
    config = yaml.safe_load(configuration_inputs['configuration'])
    need(isinstance(config, dict), 'prepared seed is not a configuration mapping')
    need(raw_file(before_path) == configuration_inputs['before_configuration']
         and raw_file(target) == configuration_inputs['configuration'], 'configuration changed while parsing')
    prior = validate_renewal_config(before)
    need(prior is not None, 'previous cumulative accounting required')
    already_balance = prior.get('balance_only') is True
    if already_balance:
        from factorykit.allowance_renewal import _read
        parent = _read(before['runtime']['featherless_budget_guard']['time_renewal'])
        need(parent.get('kind') == 'BALANCE_ONLY_AMENDMENT'
             and parent.get('approved_epoch') == args.approved_epoch,
             'room continuation must reuse the original balance-only approval epoch')
    run = Path(before['paths']['runs'])
    need(run in target.parents and run in folder.parents and config['paths']['runs'] == str(run), 'same shared accounting root required')
    old_active, old_rooms = room_scope(before)
    need(args.rehearsal_room not in old_rooms and config['band']['rehearsal_room_id'] == args.rehearsal_room
         and config['band']['judged_room_id'] == old_active[1], 'new rehearsal must retain judged room')
    preserve_configuration_policy(config, before)
    expected = copy.deepcopy(before['budgets']); expected['balance_only'] = True
    actual = copy.deepcopy(config['budgets']); actual['approved'] = True; actual['balance_only'] = True
    need(actual == expected, 'new seed changed historical allowance or $25 ceiling')
    guard_options = copy.deepcopy(config['runtime']['featherless_budget_guard']); guard_options.pop('balance_only', None)
    previous_guard = copy.deepcopy(before['runtime']['featherless_budget_guard']); previous_guard.pop('balance_only', None)
    need(guard_options == previous_guard, 'seed changed shared guard binding')
    budget_path = budget_ledger_path(before)
    request_path = Path(before['runtime']['featherless_budget_guard']['ledger'])
    owner_path = run / 'runtime/owner.json'
    paths = {'before_configuration': before_path, 'configuration': target,
             'factory_budget': budget_path, 'request_ledger': request_path, 'owner': owner_path}
    inputs = {name: configuration_inputs[name] if name in configuration_inputs else raw_file(path) for name, path in paths.items()}
    factory, guard = (json.loads(inputs[name]) for name in ('factory_budget', 'request_ledger'))
    stopped(json.loads(inputs['owner']))
    validate_retained_factory_accounting(before, factory)
    need(factory['room_ids'] == old_rooms and factory.get('stopped_reason') is None
         and guard.get('stopped_reason') is None, 'global accounting is stopped or scope changed')
    models = _featherless_metadata(before)
    options = before['runtime']['featherless_budget_guard']
    checked = _Ledger(request_path, _policy(models, options['approved_credit_nano_usd'], options['max_total_tokens'],
                                           options['overall_timeout_seconds'], time_renewal=options['time_renewal'],
                                           balance_only=already_balance))
    checked.data = guard; checked._validate()
    need(all(value['status'] == 'settled' for value in guard['requests'].values()), 'provider usage is unresolved')
    source = {str(factory_root / 'factorykit' / name): sha(raw_file(factory_root / 'factorykit' / name))
              for name in ('allowance_renewal.py', 'allowance_scope.py', 'budgets.py', 'featherless_guard.py')}
    protected = {str(path): sha(raw_file(path)) for path in (before_path, owner_path,
        *sorted((run / 'runtime').glob('membership-*.json')), *sorted((run / 'runtime').glob('workflow-*.json')),
        *sorted((run / 'runtime').glob('task-board-*.json')))}
    review = {'schema_version': 1, 'kind': 'BALANCE_ONLY_AMENDMENT', 'user_answer': 'Keep only the $25 cap',
              'approved_epoch': args.approved_epoch, 'original_balance_approval_reused': already_balance, 'active_room_ids': [args.rehearsal_room, old_active[1]],
              'cumulative_room_ids': sorted(old_rooms + [args.rehearsal_room]),
              'inputs_sha256': {name: sha(raw) for name, raw in inputs.items()}, 'paths': {name: str(path) for name, path in paths.items()},
              'evidence_directory': str(folder), 'source_sha256': source, 'protected_sha256': protected,
              'helper_sha256': sha(raw_file(Path(__file__).resolve())), 'tokens_preserved': factory['tokens'],
              'request_count_preserved': len(guard['requests']), 'conservative_accounting': checked.totals(),
              'original_factory_started_epoch': factory['started_epoch'], 'original_guard_started_epoch': guard['started_epoch'],
              'historical_renewal_deadline_epoch': prior['renewal_deadline_epoch'],
              'hard_cap_nano_usd': options['approved_credit_nano_usd'], 'network_calls': 0, 'inference_calls': 0}
    binding = sha(encoded(review))
    if not args.execute:
        print(json.dumps({'status': 'REVIEW_ONLY', 'review_sha256': binding, 'review': review, 'writes': 0}, indent=2))
        return 0
    need(args.review_sha256 == binding, 'review binding changed; repeat dry-run')
    handles = locks(run, request_path)
    try:
        need(not folder.exists() and all(raw_file(paths[name]) == raw for name, raw in inputs.items()), 'input changed before lock')
        stopped(json.loads(raw_file(owner_path)))
        folder.mkdir(mode=0o700); sync(folder.parent); sync(folder)
        archive = folder / 'before'; archive.mkdir(mode=0o700); sync(folder); sync(archive)
        refs = {name: create(archive / (name + ('.yaml' if 'configuration' in name else '.json')), raw) for name, raw in inputs.items()}
        config_ref = create(archive / 'before_configuration.parsed.json', encoded(before))
        authority = {'schema_version': 1, 'kind': 'BALANCE_ONLY_AMENDMENT', 'status': 'APPROVED',
                     'authorization_source': 'direct_user_chat', 'user_answer': 'Keep only the $25 cap',
                     'approved_epoch': args.approved_epoch, 'prior_time_renewal': options['time_renewal'],
                     'before_configuration': config_ref, 'before_factory_budget': refs['factory_budget'],
                     'before_request_ledger': refs['request_ledger'], 'active_room_ids': review['active_room_ids'],
                     'cumulative_room_ids': review['cumulative_room_ids']}
        authority_ref = create(folder / 'approval.json', encoded(authority))
        config['budgets'] = expected
        config['band']['archived_room_ids'] = sorted(set(old_rooms) - {old_active[1]})
        config['runtime']['featherless_budget_guard'].update(balance_only=True, time_renewal=authority_ref)
        new_factory, new_guard = reconcile_balance_scope(config, factory, guard, models)
        targets = {'configuration': yaml.safe_dump(config, sort_keys=False).encode(),
                   'factory_budget': encoded(new_factory), 'request_ledger': encoded(new_guard)}
        reviewed_config = folder / 'final-configuration.yaml'
        create(reviewed_config, targets['configuration'])
        need(load_config(reviewed_config) == config, 'final amended configuration failed production validation')
        create(folder / 'claim.json', encoded({'schema_version': 1, 'status': 'CLAIMED', 'review_sha256': binding,
               'approval': authority_ref, 'before_sha256': review['inputs_sha256'],
               'after_sha256': {name: sha(raw) for name, raw in targets.items()}}))
        need(all(raw_file(paths[name]) == raw for name, raw in inputs.items())
             and all(sha(raw_file(Path(path))) == expected for path, expected in {**source, **protected}.items()), 'protected input/source changed before commit')
        for name in ('request_ledger', 'factory_budget', 'configuration'):
            replace(paths[name], targets[name])
        from factorykit.budgets import persisted_budget_blockers
        need(not persisted_budget_blockers(config, require_existing=True), 'amended accounting failed production inspectors')
        need(all(raw_file(paths[name]) == raw for name, raw in targets.items())
             and all(sha(raw_file(Path(path))) == expected for path, expected in protected.items()), 'commit or original evidence hash changed')
        result = {'status': 'PASS', 'review_sha256': binding, 'approval': authority_ref,
                  'after_sha256': {name: sha(raw) for name, raw in targets.items()},
                  'tokens_preserved': factory['tokens'], 'request_count_preserved': len(guard['requests']),
                  'conservative_accounting_preserved': checked.totals(), 'only_cumulative_dollar_cap_enforced': True,
                  'prior_evidence_unchanged': True, 'network_calls': 0, 'inference_calls': 0}
        create(folder / 'commit-report.json', encoded(result)); print(json.dumps(result, indent=2))
        return 0
    finally:
        for fd in reversed(handles): os.close(fd)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        print(json.dumps({'status': 'BLOCKED_PRESERVE_BEFORE_IMAGES_AND_CLAIM', 'reason': 'balance-only amendment failed; inspect immutable local evidence',
                          'network_calls': 0, 'inference_calls': 0}), file=sys.stderr)
        raise SystemExit(1)
