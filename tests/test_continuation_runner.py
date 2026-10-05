import copy
from contextlib import nullcontext
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import textwrap
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from factorykit.common import FactoryError, canonical, digest
from factorykit import continuation_runner as cr

ROOM = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
AGENT = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'
UNUSED = 'cccccccc-cccc-4ccc-8ccc-cccccccccccc'
THREAD = 'dddddddd-dddd-4ddd-8ddd-dddddddddddd'
NEW_THREAD = 'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee'
EVENTS = [f'{i:08d}-1111-4111-8111-111111111111' for i in range(1, 6)]
CUTOFF = '2026-10-05T02:45:00+00:00'


class ContinuationFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir='/private/tmp')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.factory = self.root / 'factory'
        self.runs = self.root / 'runs'
        (self.factory / 'factorykit').mkdir(parents=True)
        (self.runs / 'runtime').mkdir(parents=True)
        self.base = {'paths': {'factory': str(self.factory), 'runs': str(self.runs)},
                     'band': {'judged_room_id': ROOM},
                     'seats': [{'id': 'pm', 'agent_id': AGENT, 'model': 'old'},
                               {'id': 'frontend', 'agent_id': UNUSED, 'model': 'old'}],
                     'budgets': {'max_active_seats': 1}, 'runtime': {'python': '/offline/python'}}
        self.helpers = []
        for name in ('continuation_guard', 'continuation_platform', 'continuation_runner'):
            path = self.factory / 'factorykit' / (name + '.py')
            path.write_text('# inert fixture\n')
            self.helpers.append(self.ref(path))
        turn = {'agent_id': AGENT, 'trigger_event_id': EVENTS[0], 'status': 'completed',
                'started_at': 100, 'ended_at': 110, 'reason_code': ''}
        failed = dict(turn, trigger_event_id=EVENTS[1], status='failed', reason_code='provider_failure')
        self.workflow = {'scope': {'room_id': ROOM, 'participant_ids': [AGENT, UNUSED]},
                         'turns': {'pm:1': turn, 'pm:2': failed}}
        self.workflow_path = self.root / 'workflow-before.json'
        self.write(self.workflow_path, self.workflow)
        self.receipts = []
        self.rows = []
        for seat, agent in [('pm', AGENT), ('frontend', UNUSED)]:
            events = []
            if seat == 'pm':
                for event, status in zip(EVENTS[:4], ['processed', 'failed', None, 'processed']):
                    events.append({'event_id': event, 'inserted_at': '2026-10-05T02:30:00+00:00',
                                   'own_delivery': {'status': status} if status else None})
            public = {'sender_id': agent, 'event_id': EVENTS[0], 'inserted_at': CUTOFF,
                      'metadata': {'codex_thread_id': THREAD, 'codex_room_id': ROOM}} if events else None
            receipt = {'room_id': ROOM, 'seat': seat, 'agent_id': agent, 'complete_cursor_pagination': True,
                       'observed_start': '2026-10-05T02:44:00+00:00', 'observed_end': CUTOFF,
                       'all_receipts': events, 'actionable_receipts': events[1:3],
                       'actionable_with_recorded_admission': events[1:2],
                       'processed_without_recorded_admission': events[3:4],
                       'admission_comparisons': [], 'latest_public_thread_binding': public,
                       'latest_local_thread_binding': {'codex_thread_id': THREAD, 'codex_room_id': ROOM} if events else None,
                       'public_matches_latest_local_thread': True if events else None,
                       'thread_task_metadata': [public] if events else []}
            if events:
                for index, (turn_id, value) in enumerate(self.workflow['turns'].items()):
                    receipt['admission_comparisons'].append({
                        **{k: value[k] for k in ('trigger_event_id', 'status', 'started_at', 'ended_at', 'reason_code')},
                        'turn_id': turn_id, 'server_event_found': True, 'server_actionable': index == 1,
                        'server_delivery_status': events[index]['own_delivery']['status']})
            path = self.root / (seat + '.receipts.json')
            self.write(path, receipt)
            self.receipts.append((path, receipt))
            self.rows.append({'seat': seat, 'agent_id': agent, 'file': str(path), 'sha256': digest(path.read_bytes()),
                              'actionable_event_ids': [x['event_id'] for x in receipt['actionable_receipts']],
                              'admitted_actionable_event_ids': [x['event_id'] for x in receipt['actionable_with_recorded_admission']],
                              'processed_without_admission_event_ids': [x['event_id'] for x in receipt['processed_without_recorded_admission']],
                              'admissions': len(receipt['admission_comparisons']), 'all_receipts': len(events),
                              'latest_public_thread_binding': public})
        hashes = {'workflow_sha256': digest(self.workflow_path.read_bytes())}
        self.audit = {'schema_version': 1, 'room_id': ROOM, 'read_only': True, 'model_calls': False,
                      'mutations': False, 'input_hashes_unchanged': True, 'before_hashes': hashes,
                      'after_hashes': hashes.copy(), 'created_at': CUTOFF, 'local_admissions': 2, 'seats': self.rows}
        self.audit_path = self.root / 'audit.json'
        self.write(self.audit_path, self.audit)
        self.manifest = {'schema_version': 1, 'room_id': ROOM, 'cutoff_utc': CUTOFF,
                         'platform_audit': self.ref(self.audit_path), 'helpers': self.helpers,
                         'completed': [['pm', EVENTS[0]]], 'blocked': [['pm', EVENTS[1]]],
                         'pending': [['pm', EVENTS[2]]], 'processed_without_admission': [['pm', EVENTS[3]]],
                         'expected_thread_ids': {'pm': THREAD, 'frontend': None}}
        self.manifest_path = self.root / 'continuity.json'
        self.write(self.manifest_path, self.manifest)
        self.amendment = {'room_id': ROOM, 'created_at_utc': CUTOFF, 'continuity': self.ref(self.manifest_path),
                          'bindings': {'workflow': {'path': str(self.workflow_path), 'preserved_path': str(self.workflow_path),
                                                    'sha256': digest(self.workflow_path.read_bytes())}},
                          'changes': {'additional_seconds': 28800, 'old_deadline_utc': CUTOFF,
                                      'new_deadline_utc': '2026-10-05T10:45:00+00:00'}}
        self.amendment_path = self.root / 'amendment.json'
        self.write(self.amendment_path, self.amendment)
        self.effective = copy.deepcopy(self.base)
        for seat in self.effective['seats']:
            seat['model'] = 'gpt-6.1-sol'

    @staticmethod
    def ref(path):
        return {'path': str(path), 'sha256': digest(path.read_bytes())}

    @staticmethod
    def write(path, value):
        path.write_bytes(canonical(value))

    def rebind(self):
        for row, (path, data) in zip(self.rows, self.receipts):
            self.write(path, data); row['sha256'] = digest(path.read_bytes())
        self.write(self.audit_path, self.audit)
        self.manifest['platform_audit'] = self.ref(self.audit_path)
        self.write(self.manifest_path, self.manifest)
        self.amendment['continuity'] = self.ref(self.manifest_path)
        self.write(self.amendment_path, self.amendment)

    def context(self):
        root, claim, _ = cr.continuation_paths(self.base, self.amendment_path)
        cr._private_directory(root)
        if not claim.exists():
            cr.durable_json(claim, {'claim': 'offline'}, exclusive=True)
        self.write(self.runs / 'runtime/owner.json', {'token': 'offline', 'parent': {'pid': os.getpid()},
                                                    'mode': 'judged', 'status': 'starting'})
        with patch.object(cr.de, 'validate_claimed_amendment', return_value=self.effective):
            return cr.ContinuityContext(self.base, self.amendment_path, claim, 'offline')

    def test_exact_derivation_preserves_suppression_category(self):
        actual = cr.validate_continuity(self.base, self.amendment)
        self.assertEqual(actual['processed_without_admission'], [['pm', EVENTS[3]]])
        self.assertNotIn(['pm', EVENTS[3]], actual['completed'])

    def test_reviewed_invented_pending_event_refused(self):
        self.manifest['pending'] = [['pm', EVENTS[4]]]; self.rebind()
        with self.assertRaises(FactoryError): cr.validate_continuity(self.base, self.amendment)

    def test_missing_receipt_page_refused(self):
        self.receipts[0][1]['complete_cursor_pagination'] = False; self.rebind()
        with self.assertRaises(FactoryError): cr.validate_continuity(self.base, self.amendment)

    def test_model_completed_relabel_of_suppression_refused(self):
        self.manifest['completed'].append(self.manifest['processed_without_admission'].pop()); self.rebind()
        with self.assertRaises(FactoryError): cr.validate_continuity(self.base, self.amendment)

    def test_changed_original_admission_refused(self):
        self.receipts[0][1]['admission_comparisons'][0]['status'] = 'failed'; self.rebind()
        with self.assertRaises(FactoryError): cr.validate_continuity(self.base, self.amendment)

    def test_missing_thread_for_used_seat_refused(self):
        self.manifest['expected_thread_ids']['pm'] = None; self.rebind()
        with self.assertRaises(FactoryError): cr.validate_continuity(self.base, self.amendment)

    def test_source_hash_change_blocks_before_state_writes(self):
        Path(self.helpers[0]['path']).write_text('# changed\n')
        with self.assertRaises(FactoryError): self.context()
        self.assertFalse(any((self.runs / 'runtime/continuation').glob('*/events.json')))

    def test_thread_binding_is_persisted_and_not_replaceable(self):
        ctx = self.context(); ctx.record_thread('frontend', NEW_THREAD)
        reopened = self.context()
        self.assertEqual(reopened.expected_thread('frontend'), NEW_THREAD)
        with self.assertRaises(FactoryError): reopened.record_thread('pm', NEW_THREAD)
        self.assertEqual(reopened.metadata()['effective_models']['pm'], 'gpt-6.1-sol')

    def test_old_pending_once_and_all_terminal_events_excluded(self):
        ctx = self.context()
        self.assertEqual(ctx.excluded_event_ids('pm'), {EVENTS[0], EVENTS[1], EVENTS[3]})
        msg = SimpleNamespace(id=EVENTS[2], room_id=ROOM, created_at=datetime(2026, 10, 5, 2, 30, tzinfo=timezone.utc))
        self.assertTrue(ctx.claim_event('pm', msg))
        ctx.finish_event('pm', msg.id, completed=True)
        self.assertFalse(self.context().claim_event('pm', msg))

    def test_claim_crash_blocks_replay_after_context_reopen(self):
        ctx = self.context()
        msg = SimpleNamespace(id=EVENTS[2], room_id=ROOM, created_at=CUTOFF)
        ctx.claim_event('pm', msg)
        with self.assertRaises(FactoryError): self.context().claim_event('pm', msg)

    def test_pending_notice_gate_is_read_only_until_completion(self):
        ctx = self.context()
        msg = SimpleNamespace(id=EVENTS[2], room_id=ROOM, created_at=CUTOFF)
        for expected in (True, True, False):
            before = ctx.journal.path.read_bytes()
            in_memory = copy.deepcopy(ctx.journal.data)
            self.assertEqual(ctx.pending_events_unsettled(), expected)
            self.assertEqual(ctx.journal.path.read_bytes(), before)
            self.assertEqual(ctx.journal.data, in_memory)
            if ctx.journal.data['events']['pm:' + msg.id] == 'pending':
                ctx.claim_event('pm', msg)
            elif ctx.journal.data['events']['pm:' + msg.id] == 'claimed':
                ctx.finish_event('pm', msg.id, completed=True)
        self.assertFalse(self.context().pending_events_unsettled())

    def test_blocked_original_pending_event_keeps_notice_gate_without_relabel(self):
        ctx = self.context()
        msg = SimpleNamespace(id=EVENTS[2], room_id=ROOM, created_at=CUTOFF)
        ctx.claim_event('pm', msg); ctx.finish_event('pm', msg.id, completed=False)
        before = ctx.journal.path.read_bytes()
        self.assertTrue(ctx.pending_events_unsettled())
        self.assertEqual(ctx.journal.data['events']['pm:' + msg.id], 'blocked')
        self.assertEqual(ctx.journal.path.read_bytes(), before)

    def test_missing_original_pending_state_fails_closed_without_rewrite(self):
        ctx = self.context()
        ctx.journal.data['events'].pop('pm:' + EVENTS[2])
        before = ctx.journal.path.read_bytes()
        self.assertTrue(ctx.pending_events_unsettled())
        self.assertNotIn('pm:' + EVENTS[2], ctx.journal.data['events'])
        self.assertEqual(ctx.journal.path.read_bytes(), before)

    def test_new_claim_does_not_prolong_original_pending_notice_gate(self):
        ctx = self.context()
        old = SimpleNamespace(id=EVENTS[2], room_id=ROOM, created_at=CUTOFF)
        ctx.claim_event('pm', old); ctx.finish_event('pm', old.id, completed=True)
        new = SimpleNamespace(id=EVENTS[4], room_id=ROOM, created_at='2026-10-05T02:46:00+00:00')
        ctx.claim_event('pm', new)
        self.assertFalse(ctx.pending_events_unsettled())
        self.assertEqual(ctx.journal.data['events']['pm:' + new.id], 'claimed')

    def test_owner_change_blocks_admission(self):
        ctx = self.context()
        self.write(self.runs / 'runtime/owner.json', {'token': 'other'})
        with self.assertRaises(FactoryError):
            ctx.claim_event('pm', SimpleNamespace(id=EVENTS[2], room_id=ROOM, created_at=CUTOFF))

    def test_private_permissions_and_exclusive_claim(self):
        ctx = self.context()
        self.assertEqual(stat.S_IMODE(ctx.directory.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(ctx.thread_path.stat().st_mode), 0o600)
        with self.assertRaises(FileExistsError): cr.durable_json(ctx.claim_path, {}, exclusive=True)

    def test_symlink_state_directory_refused(self):
        target = self.root / 'elsewhere'; target.mkdir()
        (self.runs / 'runtime/continuation').symlink_to(target, target_is_directory=True)
        with self.assertRaises(FactoryError): self.context()
        self.assertEqual(list(target.iterdir()), [])

    def test_fsync_file_and_directory(self):
        path = self.root / 'durable.json'
        with patch.object(cr.os, 'fsync', wraps=os.fsync) as sync:
            cr.durable_json(path, {'saved': True}, exclusive=True)
        self.assertEqual(sync.call_count, 2)

    def test_only_exact_global_halt_is_eligible(self):
        with patch.object(cr.de, 'validate_amendment', return_value=self.effective), \
             patch('factorykit.runtime.preflight_runtime', return_value=[cr.GLOBAL_HALT_ERROR, 'Token exhausted']), \
             patch('factorykit.validation.docker_resource_check') as docker:
            with self.assertRaises(FactoryError): cr.check_resume(self.base, self.amendment_path)
        docker.assert_not_called()
        self.assertFalse((self.runs / 'runtime/continuation').exists())

    def test_check_is_read_only_and_requires_resource_probe(self):
        with patch.object(cr.de, 'validate_amendment', return_value=self.effective), \
             patch('factorykit.runtime.preflight_runtime', return_value=[cr.GLOBAL_HALT_ERROR]) as preflight, \
             patch('factorykit.validation.docker_resource_check', return_value={'errors': []}) as docker:
            self.assertEqual(cr.check_resume(self.base, self.amendment_path), self.effective)
        preflight.assert_called_once_with(self.base, 'judged', effective_budgets=self.effective['budgets'],
                                         effective_models={'pm': 'gpt-6.1-sol', 'frontend': 'gpt-6.1-sol'},
                                         model_catalog=None)
        docker.assert_called_once()
        self.assertFalse((self.runs / 'runtime/continuation').exists())

    def test_bound_catalog_reaches_initial_preflight(self):
        catalog = self.root / 'catalog.json'
        self.write(catalog, {'models': [{'model': 'gpt-6.1-sol'}]})
        self.amendment['model_catalog'] = self.ref(catalog); self.rebind()
        with patch.object(cr.de, 'validate_amendment', return_value=self.effective), \
             patch('factorykit.runtime.preflight_runtime', return_value=[cr.GLOBAL_HALT_ERROR]) as preflight, \
             patch('factorykit.validation.docker_resource_check', return_value={'errors': []}):
            cr.check_resume(self.base, self.amendment_path)
        self.assertEqual(preflight.call_args.kwargs['model_catalog'], {'models': [{'model': 'gpt-6.1-sol'}]})

    def test_spawn_failure_consumes_claim_after_exact_ledger_write_and_cannot_retry(self):
        budget = self.runs / 'runtime/budget.json'
        original = {'stopped_reason': 'overall time budget exhausted', 'reported_tokens': 123}
        cleared = dict(original, stopped_reason=None)
        self.write(budget, original)
        self.amendment['bindings']['budget'] = {'path': str(budget)}; self.rebind()
        _, claim_path, _ = cr.continuation_paths(self.base, self.amendment_path)
        claim = {'amendment_sha256': digest(self.amendment_path.read_bytes())}
        writes = []
        durable = cr.durable_json
        def save(path, value, **kwargs):
            writes.append(Path(path))
            return durable(path, value, **kwargs)
        def failed_spawn(*args, **kwargs):
            self.assertEqual(writes, [claim_path, budget])
            self.assertEqual(json.loads(budget.read_text()), cleared)
            self.assertEqual(json.loads(claim_path.read_text()), claim)
            raise OSError('synthetic spawn failure')
        with patch('factorykit.runtime.launch_lock', return_value=nullcontext()), \
             patch.object(cr.de, 'validate_amendment', return_value=self.effective), \
             patch('factorykit.runtime.preflight_runtime', return_value=[cr.GLOBAL_HALT_ERROR]), \
             patch('factorykit.validation.docker_resource_check', return_value={'errors': []}), \
             patch.object(cr.de, 'prepare_claim', return_value={'claim': claim, 'cleared_budget': cleared}), \
             patch.object(cr, 'durable_json', side_effect=save), \
             patch.object(cr.subprocess, 'Popen', side_effect=failed_spawn) as spawn:
            with self.assertRaises(OSError): cr.resume(self.base, self.root / 'config.yaml', self.amendment_path)
            with self.assertRaisesRegex(FactoryError, 'already claimed'):
                cr.resume(self.base, self.root / 'config.yaml', self.amendment_path)
        spawn.assert_called_once()
        self.assertEqual(writes, [claim_path, budget])

    def test_failed_ledger_write_consumes_claim_without_spawning(self):
        budget = self.runs / 'runtime/budget.json'
        original = {'stopped_reason': 'overall time budget exhausted', 'reported_tokens': 456}
        self.write(budget, original)
        self.amendment['bindings']['budget'] = {'path': str(budget)}; self.rebind()
        _, claim_path, _ = cr.continuation_paths(self.base, self.amendment_path)
        durable = cr.durable_json
        def save(path, value, **kwargs):
            if Path(path) == budget: raise OSError('synthetic disk failure')
            return durable(path, value, **kwargs)
        with patch('factorykit.runtime.launch_lock', return_value=nullcontext()), \
             patch.object(cr.de, 'validate_amendment', return_value=self.effective), \
             patch('factorykit.runtime.preflight_runtime', return_value=[cr.GLOBAL_HALT_ERROR]), \
             patch('factorykit.validation.docker_resource_check', return_value={'errors': []}), \
             patch.object(cr.de, 'prepare_claim', return_value={'claim': {}, 'cleared_budget': {}}), \
             patch.object(cr, 'durable_json', side_effect=save), \
             patch.object(cr.subprocess, 'Popen') as spawn:
            with self.assertRaises(OSError): cr.resume(self.base, self.root / 'config.yaml', self.amendment_path)
        self.assertTrue(claim_path.exists())
        self.assertEqual(json.loads(budget.read_text()), original)
        spawn.assert_not_called()

    def test_real_module_entrypoint_uses_canonical_context_and_exposes_safe_gate(self):
        # Exercise the actual python -m entrypoint and runtime isinstance guard.
        # Only temp-fixture validation/preflight are stubbed; no SDK is connected.
        self.amendment['model_catalog'] = None; self.rebind()
        ctx = self.context()
        fixture_config = self.root / 'base.json'
        self.write(fixture_config, self.base)
        hook = self.root / 'sitecustomize.py'
        hook.write_text(textwrap.dedent("""
            import json, os, socket
            from pathlib import Path
            from factorykit import common, deadline_extension as de, runtime
            base = json.loads(Path(os.environ['CONTINUATION_OFFLINE_BASE']).read_text())
            def no_network(*args, **kwargs):
                raise AssertionError('offline entrypoint test forbids network')
            socket.socket.connect = no_network
            socket.create_connection = no_network
            common.load_config = lambda path: base
            de.validate_claimed_amendment = lambda *args, **kwargs: base
            owner = {'token': 'offline', 'parent': {'pid': os.getpid()},
                     'mode': 'judged', 'status': 'starting'}
            Path(base['paths']['runs'], 'runtime/owner.json').write_bytes(common.canonical(owner))
            def stopped_before_sdk(*args, **kwargs):
                raise runtime.GateError('Offline sentinel: canonical context verified before SDK startup')
            runtime.preflight_runtime = stopped_before_sdk
        """))
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
                   PYTHONPATH=os.pathsep.join([str(self.root), str(Path(cr.__file__).parents[1])]),
                   CONTINUATION_OFFLINE_BASE=str(fixture_config))
        result = subprocess.run(
            [sys.executable, '-B', '-m', 'factorykit.continuation_runner',
             '--config', str(fixture_config), '--amendment', str(self.amendment_path),
             '_serve', '--claim', str(ctx.claim_path), '--owner-token', 'offline'],
            cwd=self.root, env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 2, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['error_type'], 'GateError')
        self.assertEqual(report['detail'], 'Offline sentinel: canonical context verified before SDK startup')

    def test_pid_or_partial_handshake_is_not_ready(self):
        record = {'token': 't', 'status': 'running', 'seats': ['pm', 'frontend'],
                  'workflow': {'sdk_execution_contexts': [{'agent_id': AGENT, 'running': True}]}}
        self.assertFalse(cr._running_handshake(record, self.base, 't'))
        record['workflow']['sdk_execution_contexts'].append({'agent_id': UNUSED, 'running': True})
        self.assertTrue(cr._running_handshake(record, self.base, 't'))


if __name__ == '__main__':
    unittest.main()
