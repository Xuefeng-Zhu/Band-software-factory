"""Private startup timing and native cleanup; no BAND, provider or CLI calls."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from factorykit import harnesses as h
from factorykit import startup_telemetry as t
from factorykit.common import FactoryError


def config(root):
    return {'paths': {'runs': str(root), 'rehearsal': str(root), 'result': str(root)},
            'runtime': {'harness': 'opencode', 'opencode_command': str(root / 'opencode'),
                        'opencode_version': '1.18.34', 'model': 'test/model', 'sandbox': 'native-policy',
                        'native_permissions': {'read': True, 'write': False, 'bash': False, 'network': False}},
            'budgets': {'turn_timeout_seconds': 30, 'billing_mode': 'spend_cap'},
            'seats': [{'id': 'pm', 'harness': 'OpenCode', 'model': 'test/model',
                       'git_name': 'PM', 'git_email': 'pm@factory.invalid', 'reasoning_effort': None}]}


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


class StartupTelemetryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.config = config(self.root)

    def test_new_private_journals_exact_fields_and_inert_outside_scope(self):
        original = json.dumps(self.config, sort_keys=True)
        t.record_startup('not even consulted outside the scope', 'unknown')
        self.assertEqual(list(self.root.iterdir()), [])
        with t.startup_telemetry(self.config) as first:
            with t.startup_seat('pm'):
                t.record_startup('opencode_server_begin')
                with t.startup_telemetry(self.config) as nested:
                    self.assertIs(nested, first)
                    t.record_startup('opencode_route_verified')
            t.record_startup('opencode_all_servers_ready')
        before = first.path.read_bytes()
        with t.startup_telemetry(self.config) as second:
            t.record_startup('sdk_agent_start_complete', 'pm')
        self.assertNotEqual(first.path, second.path)
        self.assertEqual(first.path.read_bytes(), before)
        self.assertEqual(first.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(first.path.parent.stat().st_mode & 0o777, 0o700)
        recorded = rows(first.path)
        keys = {'schema_version', 'sequence', 'pid', 'phase', 'seat', 'observed_at', 'elapsed_seconds'}
        self.assertTrue(all(set(row) == keys for row in recorded))
        self.assertEqual([row['sequence'] for row in recorded], list(range(len(recorded))))
        self.assertEqual([row['seat'] for row in recorded], [None, 'pm', 'pm', None, None])
        elapsed = [row['elapsed_seconds'] for row in recorded]
        self.assertEqual(elapsed, sorted(elapsed))
        self.assertTrue(all(row['observed_at'].endswith('+00:00') for row in recorded))
        self.assertEqual(json.dumps(self.config, sort_keys=True), original)

    def test_no_freeform_secret_phase_seat_or_exception_can_enter_journal(self):
        secret = 'synthetic-secret-do-not-record'
        with self.assertRaisesRegex(RuntimeError, secret):
            with t.startup_telemetry(self.config) as journal:
                for phase, seat in ((secret, 'pm'), ('startup_ready', secret)):
                    with self.assertRaises(FactoryError):
                        t.record_startup(phase, seat)
                raise RuntimeError(secret)
        text = journal.path.read_text()
        self.assertNotIn(secret, text)
        self.assertEqual([row['phase'] for row in rows(journal.path)],
                         ['startup_begin', 'startup_failed', 'runtime_closed'])
        self.assertIsNone(t._CURRENT.get())
        with t.startup_telemetry(self.config) as after_ready:
            t.record_startup('startup_ready')
            try:
                raise RuntimeError('not propagated')
            except RuntimeError:
                pass
        self.assertNotIn('failed', after_ready.path.read_text())

    def test_failure_after_readiness_is_not_misreported_as_startup_failure(self):
        with self.assertRaises(RuntimeError):
            with t.startup_telemetry(self.config) as journal:
                t.record_startup('startup_ready')
                raise RuntimeError('private runtime failure')
        self.assertEqual([row['phase'] for row in rows(journal.path)],
                         ['startup_begin', 'startup_ready', 'runtime_failed', 'runtime_closed'])

    def test_unsafe_shared_or_symlink_journal_directory_is_rejected(self):
        parent = self.root / 'runtime'
        parent.mkdir()
        destination = parent / 'startup-telemetry'
        destination.mkdir(mode=0o755)
        with self.assertRaises(FactoryError):
            with t.startup_telemetry(self.config):
                self.fail('shared journal directory accepted')
        destination.rmdir()
        destination.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(FactoryError):
            with t.startup_telemetry(self.config):
                self.fail('symlink journal directory accepted')

    def test_exception_survives_journal_write_failure_during_teardown(self):
        with self.assertRaisesRegex(RuntimeError, 'original failure'):
            with t.startup_telemetry(self.config) as journal:
                with patch.object(journal, 'record', side_effect=OSError('synthetic storage failure')):
                    raise RuntimeError('original failure')
        self.assertIsNone(journal.fd)
        self.assertIsNone(t._CURRENT.get())


class OpenCodeTelemetryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.config = config(self.root)
        executable = self.root / 'opencode'
        executable.write_bytes(b'synthetic binary never executed')
        executable.chmod(0o700)
        self.config['runtime']['opencode_sha256'] = hashlib.sha256(executable.read_bytes()).hexdigest()

    def native_fakes(self):
        process = SimpleNamespace(returncode=None, terminate=Mock(), kill=Mock(), wait=AsyncMock())
        socket = Mock()
        socket.__enter__ = Mock(return_value=socket)
        socket.__exit__ = Mock(return_value=None)
        socket.getsockname.return_value = ('127.0.0.1', 12345)
        permissions = h.opencode_permissions(self.config['runtime']['native_permissions'])
        effective = {'model': 'test/model', 'small_model': 'test/model', 'default_agent': 'factory',
                     'enabled_providers': ['test'], 'share': 'disabled', 'permission': permissions,
                     'agent': {'factory': {'model': 'test/model', 'permission': permissions}}}
        agents = [{'name': 'factory', 'model': {'providerID': 'test', 'modelID': 'model'}}]
        catalog = {'connected': ['test'], 'all': [{'id': 'test', 'models': {'model': {
            'id': 'model', 'providerID': 'test', 'api': {'id': 'model'}}}}]}
        payloads = [{'healthy': True, 'version': '1.18.34'}, effective, agents, catalog, catalog]
        responses = []
        for payload in payloads:
            response = Mock()
            response.json.return_value = payload
            responses.append(response)
        client = SimpleNamespace(get=AsyncMock(side_effect=responses))
        context = Mock(__aenter__=AsyncMock(return_value=client), __aexit__=AsyncMock(return_value=None))
        return process, socket, context, client

    async def test_native_phase_order_and_seat_binding_do_not_claim_sdk_readiness(self):
        import httpx
        process, socket, client_context, client = self.native_fakes()
        with t.startup_telemetry(self.config) as journal, \
             patch.object(h.socket, 'socket', return_value=socket), \
             patch.object(h.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='1.18.34\n')) as version, \
             patch.object(asyncio, 'create_subprocess_exec', AsyncMock(return_value=process)) as spawn, \
             patch.object(httpx, 'AsyncClient', return_value=client_context):
            async with h.start_runtime(self.config, 'rehearsal', self.config['seats']):
                self.assertNotIn('startup_ready', journal.path.read_text())
        phases = [(row['phase'], row['seat']) for row in rows(journal.path)]
        self.assertEqual(phases, [('startup_begin', None),
            ('opencode_server_begin', 'pm'), ('opencode_binary_check_begin', 'pm'),
            ('opencode_version_verified', 'pm'), ('opencode_binary_verified', 'pm'),
            ('opencode_process_started', 'pm'), ('opencode_route_verified', 'pm'),
            ('opencode_seat_ready', 'pm'), ('opencode_all_servers_ready', None), ('runtime_closed', None)])
        self.assertEqual([call.args[0] for call in client.get.call_args_list],
                         ['/global/health', '/config', '/agent', '/provider', '/provider'])
        version.assert_called_once()
        spawn.assert_awaited_once()
        process.terminate.assert_called_once()
        process.wait.assert_awaited_once()
        self.assertNotIn('OPENCODE_SERVER_PASSWORD', journal.path.read_text())

    async def test_journal_failure_immediately_after_spawn_still_terminates_process(self):
        process, socket, _, _ = self.native_fakes()
        with t.startup_telemetry(self.config) as journal:
            original_record = journal.record
            def fail_after_spawn(phase, seat=None):
                if phase == 'opencode_process_started':
                    raise FactoryError('synthetic journal failure')
                original_record(phase, seat)
            with patch.object(journal, 'record', side_effect=fail_after_spawn), \
                 patch.object(h.socket, 'socket', return_value=socket), \
                 patch.object(h.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='1.18.34\n')), \
                 patch.object(asyncio, 'create_subprocess_exec', AsyncMock(return_value=process)):
                with self.assertRaisesRegex(FactoryError, 'synthetic journal failure'):
                    async with h.start_runtime(self.config, 'rehearsal', self.config['seats']):
                        self.fail('logging failure should not yield a server')
        process.terminate.assert_called_once()
        process.wait.assert_awaited_once()
        self.assertNotIn('opencode_route_verified', journal.path.read_text())
        self.assertNotIn('startup_ready', journal.path.read_text())
