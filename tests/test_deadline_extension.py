"""Offline amendment/admission tests. No processes, Docker, BAND or model calls."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import psutil
import yaml

from factorykit.common import FactoryError, canonical, digest
from factorykit import deadline_extension as de


class DeadlineExtensionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="deadline ' quoted ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.runs = self.root / 'runs'; self.factory = self.root / 'factory'
        self.room = '11111111-1111-4111-8111-111111111111'
        self.rehearsal = '22222222-2222-4222-8222-222222222222'
        self.archived = '33333333-3333-4333-8333-333333333333'
        self.event = '44444444-4444-4444-8444-444444444444'
        self.start = 1000.5; self.room_start = 1200.5; self.now = 1700.5
        self.base = {'schema_version': 1, 'paths': {
            'factory': str(self.factory), 'runs': str(self.runs),
            'challenge': str(self.root / 'challenge'), 'result': str(self.root / 'result')},
            'artifacts': {'source_lock': str(self.runs / 'source-lock.json')},
            'band': {'judged_room_id': self.room, 'rehearsal_room_id': self.rehearsal,
                     'archived_room_ids': [self.archived]},
            'runtime': {'model': 'gpt-6-astra', 'version': '0.160.0'},
            'seats': [{'id': 'pm', 'model': 'gpt-6-astra', 'reasoning_effort': 'high'},
                      {'id': 'backend', 'model': 'gpt-6-astra', 'reasoning_effort': 'medium'}],
            'budgets': {'approved': True, 'billing_mode': 'subscription_only', 'spend_cap_usd': None,
                        'api_billing_allowed': False, 'paid_provisioning_allowed': False,
                        'max_active_seats': 1, 'max_total_tokens': 1000, 'max_turns_per_seat': 100,
                        'turn_timeout_seconds': 30, 'stage_timeout_seconds': 600,
                        'overall_timeout_seconds': 600, 'max_repairs': 3, 'ack_timeout_seconds': 10}}
        self.write(self.factory / 'factorykit/runtime.py', b'original runtime\n')
        self.write(self.factory / 'mandates/pm.md', b'generic mandate\n')
        self.write(self.root / 'challenge/spec.md', b'exact spec\n')
        self.write(self.root / 'guide.md', b'pinned guide\n')
        self.global_config = self.root / 'global.toml'
        self.write(self.global_config, b'model = "example"\n')
        self.lock = {'challenge': {'commit': 'a' * 40, 'files': {'spec.md': digest(self.root / 'challenge/spec.md')}},
                     'documents': [{'path': str(self.root / 'guide.md'), 'sha256': digest(self.root / 'guide.md')}],
                     'instruction_inputs': [{'path': str(self.global_config), 'sha256': digest(self.global_config)}]}
        self.write_json(self.runs / 'source-lock.json', self.lock)
        self.write(self.runs / 'factory.yaml', yaml.safe_dump(self.base).encode())
        self.task = self.runs / 'tasks/judged-all-stages.md'; self.write(self.task, b'original one-time task\n')
        self.freeze = {'status': 'READY_TO_LAUNCH', 'configuration_sha256': digest(canonical(self.base)),
                       'source_lock_sha256': digest(self.runs / 'source-lock.json'),
                       'seats': self.base['seats'], 'budgets': self.base['budgets'],
                       'files': {n: digest(self.factory / n) for n in ['factorykit/runtime.py', 'mandates/pm.md']},
                       'tasks': {'judged-all-stages.md': {'sha256': digest(self.task)}}}
        self.write_json(self.runs / 'freeze/latest.json', self.freeze)
        self.launch = {'schema_version': 1, 'mode': 'all', 'entries': [{'state': 'DISPATCHED',
            'room_event': self.event, 'stages': [1, 2, 3, 4], 'freeze_sha256': digest(self.runs / 'freeze/latest.json'),
            'task': str(self.task), 'task_sha256': digest(self.task)}]}
        self.write_json(self.runs / 'launch/ledger.json', self.launch)
        self.ledger = {'room_id': None, 'room_ids': sorted([self.room, self.rehearsal, self.archived]),
                       'started_epoch': self.start, 'tokens': 100, 'turns': {'pm': 7}, 'token_threads': {'old-thread': 100},
                       'stopped_reason': de.OVERALL_STOP, 'room_started_epochs': {self.room: self.room_start, self.archived: 1100.5},
                       'room_turns': {self.room: {'pm': 2}, self.archived: {'pm': 5}},
                       'room_stopped_reasons': {self.archived: 'closed'}, 'updated_at': 'unchanged'}
        self.write_json(self.runs / 'runtime/budget-subscription.json', self.ledger)
        self.write_json(self.runs / f'runtime/workflow-{self.room}.json', {'history': 'preserved'})
        self.owner = {'status': 'stopped', 'mode': 'judged', 'token': 'old', 'parent': {
            'pid': 99999999, 'created': 1000.5, 'cmdline': ['owned-test']}, 'children': []}
        self.write_json(self.runs / 'runtime/owner.json', self.owner)
        self.saved = self.runs / 'amendment'
        self.auth_path = self.saved / 'authorization.json'; self.status_path = self.saved / 'stopped.json'
        self.write_json(self.status_path, {'status': 'stopped', 'mode': 'judged', 'owned_parent_alive': False, 'owned_children_alive': 0})
        entries = []
        for name in ['factory.yaml', 'freeze/latest.json', 'launch/ledger.json', 'source-lock.json',
                     'runtime/budget-subscription.json', f'runtime/workflow-{self.room}.json']:
            src = self.runs / name; dst = self.saved / ('before-' + name.replace('/', '--'))
            self.write(dst, src.read_bytes()); entries.append({'source': str(src), 'preserved': str(dst), 'sha256': digest(src)})
        self.write_json(self.saved / 'before-manifest.json', {'files': entries})
        self.auth = {key: None for key in de._AUTH_KEYS}
        self.auth.update(schema_version=1, recorded_at_utc=de._utc(self.now), status='APPROVED_NOT_APPLIED',
            authorization_source='Direct user answer in current Codex chat', user_answer='Add 8 hours', scope='time only',
            room_id=self.room, additional_seconds=28800, old_deadline_utc=de._utc(1600.5), new_deadline_utc=de._utc(30400.5),
            old_overall_timeout_seconds=600, new_overall_timeout_seconds=29400, old_stage_timeout_seconds=600,
            minimum_run6_stage_timeout_seconds=29200, max_total_tokens=1000, tokens_preserved=100,
            remaining_reported_tokens=900, original_started_epoch=self.start, run6_started_epoch=self.room_start,
            orbstack_cap_mib=2048, initial_dispatch_event=self.event,
            original_configuration_sha256=digest(self.runs / 'factory.yaml'),
            original_freeze_sha256=digest(self.runs / 'freeze/latest.json'),
            budget_sha256_at_halt=digest(self.runs / 'runtime/budget-subscription.json'), limitations=['not applied'])
        self.write_json(self.auth_path, self.auth)
        helpers = []
        for name in ('continuation_guard', 'continuation_platform', 'continuation_runner'):
            helper = self.factory / ('factorykit/' + name + '.py')
            self.write(helper, b'fixture helper only\n')
            helpers.append({'path': str(helper), 'sha256': digest(helper)})
        audit = self.saved / 'platform-audit.json'; self.write_json(audit, {'offline_fixture': True})
        self.continuity_path = self.saved / 'continuity.json'
        self.continuity = {'schema_version': 1, 'room_id': self.room, 'cutoff_utc': de._utc(self.now),
            'platform_audit': {'path': str(audit), 'sha256': digest(audit)}, 'helpers': helpers,
            'completed': [['pm', self.event]], 'blocked': [], 'pending': [],
            'processed_without_admission': [], 'expected_thread_ids': {'pm': self.event, 'backend': None}}
        self.write_json(self.continuity_path, self.continuity)
        self.process_patch = patch.object(de.psutil, 'Process', side_effect=psutil.NoSuchProcess(99999999))
        self.process_patch.start(); self.addCleanup(self.process_patch.stop)
        def fake_git(argv, cwd, timeout):
            self.assertEqual(Path(cwd), self.root / 'challenge')
            self.assertEqual(timeout, 5)
            return {'exit_code': 0, 'stdout': 'a' * 40 + '\n' if argv[1] == 'rev-parse' else ''}
        self.git_patch = patch.object(de, 'run_command', side_effect=fake_git)
        self.git_patch.start(); self.addCleanup(self.git_patch.stop)

    def write(self, path, raw):
        path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)

    def write_json(self, path, value):
        self.write(path, canonical(value))

    def proposal(self, **kwargs):
        return de.prepare_amendment(self.base, authorization_path=self.auth_path,
            stopped_status_path=self.status_path, continuity_path=self.continuity_path, now=self.now, **kwargs)

    def approved(self, proposal=None):
        proposal = self.proposal() if proposal is None else proposal
        review = {'schema_version': 1, 'status': 'PASS', 'scope': 'same-room deadline extension',
                  'independent': True, 'reviewer': 'offline reviewer', 'reviewed_at_utc': de._utc(self.now),
                  'proposal_sha256': digest(canonical(proposal)), 'source_deltas': proposal['source_deltas']}
        review_path = self.saved / 'review.json'; self.write_json(review_path, review)
        amendment = de.approve_amendment(self.base, proposal, review_path=review_path, now=self.now)
        path = self.saved / 'amendment.json'; self.write_json(path, amendment)
        return path

    def test_pure_proposal_and_validation_only_change_effective_clocks(self):
        before = {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        proposal = self.proposal()
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        effective = de.validate_amendment(self.base, self.approved(proposal), now=self.now)
        expected = copy.deepcopy(self.base); expected['budgets'].update(overall_timeout_seconds=29400, stage_timeout_seconds=29200)
        self.assertEqual(effective, expected); self.assertEqual(self.base['budgets']['overall_timeout_seconds'], 600)
        self.assertEqual(json.loads((self.runs / 'runtime/budget-subscription.json').read_text()), self.ledger)

    def test_proposal_cannot_admit_without_hash_bound_independent_review(self):
        proposal = self.proposal(); path = self.saved / 'unapproved.json'; self.write_json(path, proposal)
        with self.assertRaises(FactoryError): de.validate_amendment(self.base, path, now=self.now)
        path = self.approved(proposal); record = json.loads(path.read_text()); record['changes']['additional_seconds'] = 1
        self.write_json(path, record)
        self.assertTrue(de.amendment_errors(self.base, path, now=self.now))

    def test_unknown_fields_and_duplicate_json_keys_fail_closed(self):
        path = self.approved(); value = json.loads(path.read_text()); value['bypass'] = True
        self.write_json(path, value)
        with self.assertRaises(FactoryError): de.validate_amendment(self.base, path, now=self.now)
        self.write(path, b'{"schema_version":1,"schema_version":1}')
        with self.assertRaises(FactoryError): de.validate_amendment(self.base, path, now=self.now)

    def test_config_packet_freeze_dispatch_and_source_tampering_rejected(self):
        path = self.approved()
        for target in [self.runs / 'factory.yaml', self.task, self.runs / 'freeze/latest.json',
                       self.runs / 'launch/ledger.json', self.runs / 'source-lock.json',
                       self.factory / 'mandates/pm.md', self.root / 'challenge/spec.md', self.root / 'guide.md']:
            with self.subTest(target=target):
                original = target.read_bytes(); target.write_bytes(original + b'changed')
                with self.assertRaises(FactoryError): de.validate_amendment(self.base, path, now=self.now)
                target.write_bytes(original)

    def test_no_stop_reason_counter_epoch_room_history_or_workflow_mutation_allowed(self):
        path = self.approved(); budget = self.runs / 'runtime/budget-subscription.json'
        for field, value in [('stopped_reason', None), ('tokens', 0), ('tokens', 1000), ('started_epoch', 1100.5),
                             ('token_threads', {}), ('room_stopped_reasons', {}), ('room_ids', [self.room])]:
            with self.subTest(field=field, value=value):
                changed = copy.deepcopy(self.ledger); changed[field] = value; self.write_json(budget, changed)
                with self.assertRaises(FactoryError): de.validate_amendment(self.base, path, now=self.now)
        self.write_json(budget, self.ledger)
        self.write_json(self.runs / f'runtime/workflow-{self.room}.json', {})
        with self.assertRaises(FactoryError): de.validate_amendment(self.base, path, now=self.now)

    def test_active_worker_or_unknown_process_visibility_blocks(self):
        path = self.approved()
        with patch.object(de, '_process_alive', return_value=True):
            with self.assertRaisesRegex(FactoryError, 'active'): de.validate_amendment(self.base, path, now=self.now)
        with patch.object(de.psutil, 'Process', side_effect=psutil.AccessDenied(99999999)):
            with self.assertRaisesRegex(FactoryError, 'whether'): de.validate_amendment(self.base, path, now=self.now)

    def test_expiration_and_new_deadline_not_from_restart_time(self):
        path = self.approved()
        self.assertEqual(de.validate_amendment(self.base, path, now=2000.5)['budgets']['overall_timeout_seconds'], 29400)
        with self.assertRaises(FactoryError): de.validate_amendment(self.base, path, now=30400.5)

    def test_only_exact_reviewed_runtime_delta_is_allowed(self):
        target = self.factory / 'factorykit/runtime.py'; before = digest(target); self.write(target, b'reviewed runtime amendment\n')
        delta = {'path': 'factorykit/runtime.py', 'before_sha256': before, 'after_sha256': digest(target)}
        path = self.approved(self.proposal(source_deltas=[delta]))
        de.validate_amendment(self.base, path, now=self.now)
        self.write(target, b'unreviewed runtime\n')
        with self.assertRaises(FactoryError): de.validate_amendment(self.base, path, now=self.now)
        with self.assertRaises(FactoryError): self.proposal(source_deltas=[dict(delta, path='factorykit/workflow.py')])

    def test_exact_audited_trust_addition_only_and_no_file_rewrite(self):
        old = self.global_config.read_bytes(); stanza = ('\n[projects."' + self.base['paths']['result'] + '"]\ntrust_level = "trusted"\n').encode()
        self.write(self.global_config, old + stanza)
        audit_path = self.saved / 'trust-audit.json'
        audit = {'global_configuration': {'classification': 'EXACT_NEW_RESULT_TRUST_STANZA_ONLY',
            'path': str(self.global_config), 'locked_sha256': digest(old), 'observed_sha256': digest(old + stanza),
            'reconstruction': {'matches_locked_sha256': True, 'reconstructed_sha256': digest(old),
                'removed_section_key': 'projects.' + self.base['paths']['result'], 'section_keys': ['trust_level'], 'sections_removed': 1}}}
        self.write_json(audit_path, audit)
        path = self.approved(self.proposal(trust_audit_path=audit_path))
        de.validate_amendment(self.base, path, now=self.now); self.assertEqual(self.global_config.read_bytes(), old + stanza)
        self.write(self.global_config, old + stanza + b'network = true\n')
        with self.assertRaises(FactoryError): de.validate_amendment(self.base, path, now=self.now)

    def test_claim_phase_clears_only_halt_and_requires_exact_owner(self):
        path = self.approved(); token = 'a' * 48
        package = de.prepare_claim(self.base, path, owner_token=token, now=self.now)
        expected = copy.deepcopy(self.ledger); expected['stopped_reason'] = None
        self.assertEqual(package['cleared_budget'], expected)
        self.assertEqual(json.loads((self.runs / 'runtime/budget-subscription.json').read_text()), self.ledger)
        claim_path = self.saved / 'claim.json'; self.write_json(claim_path, package['claim'])
        self.write_json(self.runs / 'runtime/budget-subscription.json', package['cleared_budget'])
        owner = copy.deepcopy(self.owner); owner.update(status='starting', token=token); owner['parent']['pid'] = 42
        self.write_json(self.runs / 'runtime/owner.json', owner)
        with patch.object(de.os, 'getpid', return_value=42), patch.object(de, '_process_alive', return_value=True):
            effective = de.validate_claimed_amendment(self.base, path, claim_path, owner_token=token, now=self.now)
            self.assertEqual(effective['budgets']['max_total_tokens'], 1000)
            with self.assertRaises(FactoryError): de.validate_claimed_amendment(self.base, path, claim_path, owner_token='b' * 48, now=self.now)
            expected['tokens'] = 0; self.write_json(self.runs / 'runtime/budget-subscription.json', expected)
            with self.assertRaises(FactoryError): de.validate_claimed_amendment(self.base, path, claim_path, owner_token=token, now=self.now)
        with self.assertRaises(FactoryError): de.validate_amendment(self.base, path, now=self.now)

    def model_evidence(self):
        catalog = {'checked_at': de._utc(self.now), 'method': 'initialize + model/list',
                   'inference_started': False, 'sdk_version': '4.0.0', 'codex_version': '0.160.0',
                   'models': [{'model': 'gpt-6.1-sol', 'supportedReasoningEfforts':
                               [{'reasoningEffort': 'high'}, {'reasoningEffort': 'medium'}]}]}
        path = self.saved / 'model-catalog.json'; self.write_json(path, catalog)
        auth = {'schema_version': 1, 'status': 'APPROVED_NOT_APPLIED',
                'authorization_source': 'Direct user answer in current Codex chat',
                'user_answer': 'Can you change the factory agent model to sol6.1', 'room_id': self.room,
                'resolved_model': 'gpt-6.1-sol', 'seat_ids': ['backend', 'pm'],
                'catalog_sha256': digest(path), 'recorded_at_utc': de._utc(self.now),
                'base_configuration_sha256': digest(canonical(self.base))}
        auth_path = self.saved / 'model-authorization.json'; self.write_json(auth_path, auth)
        return auth_path, path

    def test_explicit_model_switch_changes_only_advertised_models_and_clocks(self):
        auth, catalog = self.model_evidence()
        proposal = self.proposal(model_authorization_path=auth, model_catalog_path=catalog)
        result = de.validate_amendment(self.base, self.approved(proposal), now=self.now)
        expected = copy.deepcopy(self.base)
        expected['budgets'].update(overall_timeout_seconds=29400, stage_timeout_seconds=29200)
        expected['runtime']['model'] = 'gpt-6.1-sol'
        for seat in expected['seats']: seat['model'] = 'gpt-6.1-sol'
        self.assertEqual(result, expected)
        self.assertEqual(self.base['runtime']['model'], 'gpt-6-astra')

    def test_unapproved_unavailable_or_unsupported_model_switch_fails_closed(self):
        auth_path, catalog_path = self.model_evidence()
        with self.assertRaises(FactoryError): self.proposal(model_catalog_path=catalog_path)
        auth = json.loads(auth_path.read_text()); catalog = json.loads(catalog_path.read_text())
        for change in ('other_model', 'missing_model', 'reasoning', 'inference', 'different_seats'):
            with self.subTest(change=change):
                a, c = copy.deepcopy(auth), copy.deepcopy(catalog)
                if change == 'other_model': a['resolved_model'] = 'another-model'
                if change == 'missing_model': c['models'] = []
                if change == 'reasoning': c['models'][0]['supportedReasoningEfforts'] = [{'reasoningEffort': 'low'}]
                if change == 'inference': c['inference_started'] = True
                if change == 'different_seats': a['seat_ids'] = ['pm']
                self.write_json(catalog_path, c); a['catalog_sha256'] = digest(catalog_path); self.write_json(auth_path, a)
                with self.assertRaises(FactoryError): self.proposal(model_authorization_path=auth_path, model_catalog_path=catalog_path)

    def test_model_evidence_tampering_invalidates_approved_amendment(self):
        auth, catalog = self.model_evidence()
        path = self.approved(self.proposal(model_authorization_path=auth, model_catalog_path=catalog))
        self.write(catalog, catalog.read_bytes() + b'\n')
        with self.assertRaises(FactoryError): de.validate_amendment(self.base, path, now=self.now)

    def test_challenge_git_head_cleanliness_and_inspection_fail_closed(self):
        path = self.approved()
        cases = [([{'exit_code': 0, 'stdout': 'b' * 40}], 'commit'),
                 ([{'exit_code': 0, 'stdout': 'a' * 40}, {'exit_code': 0, 'stdout': '?? added.txt'}], 'dirty'),
                 ([{'exit_code': 0, 'stdout': 'a' * 40}, {'exit_code': 124, 'stdout': ''}], 'inspected'),
                 ([{'exit_code': 127, 'stdout': ''}], 'commit')]
        for results, text in cases:
            with self.subTest(results=results), patch.object(de, 'run_command', side_effect=results):
                with self.assertRaisesRegex(FactoryError, text): de.validate_amendment(self.base, path, now=self.now)

    def test_helper_audit_and_continuity_bytes_are_review_bound(self):
        path = self.approved()
        for target in [self.continuity_path, self.saved / 'platform-audit.json',
                       self.factory / 'factorykit/continuation_guard.py',
                       self.factory / 'factorykit/continuation_platform.py',
                       self.factory / 'factorykit/continuation_runner.py']:
            with self.subTest(target=target):
                old = target.read_bytes(); self.write(target, old + b'changed')
                with self.assertRaises(FactoryError): de.validate_amendment(self.base, path, now=self.now)
                self.write(target, old)

    def test_continuity_categories_and_helper_inventory_fail_closed(self):
        for field, value in [('pending', [['pm', self.event]]), ('extra', True),
                             ('expected_thread_ids', {'pm': self.event}),
                             ('helpers', self.continuity['helpers'][:2]),
                             ('room_id', self.archived)]:
            with self.subTest(field=field):
                changed = copy.deepcopy(self.continuity); changed[field] = value
                self.write_json(self.continuity_path, changed)
                with self.assertRaises(FactoryError): self.proposal()
        self.write_json(self.continuity_path, self.continuity)

    def test_symlink_or_wrong_room_evidence_cannot_be_used(self):
        path = self.approved(); link = self.saved / 'link.json'; link.symlink_to(path)
        with self.assertRaises(FactoryError): de.validate_amendment(self.base, link, now=self.now)
        base = copy.deepcopy(self.base); base['band']['judged_room_id'] = self.archived
        with self.assertRaises(FactoryError): de.validate_amendment(base, path, now=self.now)


if __name__ == '__main__':
    unittest.main()
