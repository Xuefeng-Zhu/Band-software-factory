"""Offline privacy/propagation tests; no SDK connection or model work."""
import json
import logging
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import AsyncMock

from factorykit.common import FactoryError
from factorykit.continuation_guard import BoundCodexClient
from factorykit.exception_diagnostics import MAX_CHAIN, MAX_FILE_BYTES, MAX_FRAMES, exception_locations, record_exception

THREAD = '00000000-0000-4000-8000-000000000001'
SECRET = 'synthetic-private-prompt-and-credential-must-never-be-recorded'


class UnprintableError(RuntimeError):
    def __str__(self):
        raise AssertionError('Exception formatting is forbidden')


def captured_failure():
    private_local = SECRET
    try:
        raise ValueError(private_local)
    except ValueError as cause:
        try:
            raise UnprintableError(SECRET, {'response_body': SECRET}) from cause
        except UnprintableError as error:
            return error


class ExceptionLocationsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(tempfile.gettempdir()).resolve())
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.directory = self.root / 'diagnostics'

    def test_exception_messages_arguments_locals_and_source_are_never_formatted(self):
        report = exception_locations(captured_failure())
        text = json.dumps(report)
        self.assertNotIn(SECRET, text)
        self.assertNotIn('response_body', text)
        self.assertEqual([item['type']['name'] for item in report['exceptions']], ['UnprintableError', 'ValueError'])
        for item in report['exceptions']:
            self.assertEqual(set(item), {'type', 'frames', 'frames_truncated'})
            for frame in item['frames']:
                self.assertEqual(set(frame), {'module', 'function', 'line'})
                self.assertIsInstance(frame['line'], int)

    def test_dynamic_filename_and_invalid_symbol_are_omitted(self):
        namespace = {'__name__': SECRET + '/private'}
        try:
            exec(compile('raise RuntimeError("hidden")', '/private/' + SECRET, 'exec'), namespace)
        except RuntimeError as error:
            report = exception_locations(error)
        self.assertNotIn(SECRET, json.dumps(report))
        self.assertEqual(report['exceptions'][0]['frames'][-1]['module'], 'unknown')

    def test_depth_limits_and_cause_cycle_are_bounded(self):
        error = ValueError(SECRET)
        for _ in range(MAX_CHAIN + 3):
            parent = RuntimeError(SECRET); parent.__cause__ = error; error = parent
        report = exception_locations(error)
        self.assertEqual(len(report['exceptions']), MAX_CHAIN)
        self.assertTrue(report['chain_truncated'])
        error.__cause__ = error
        self.assertEqual(len(exception_locations(error)['exceptions']), 1)
        def recurse(depth):
            if depth: return recurse(depth-1)
            raise ValueError(SECRET)
        try: recurse(MAX_FRAMES + 4)
        except ValueError as error: report = exception_locations(error)
        self.assertEqual(len(report['exceptions'][0]['frames']), MAX_FRAMES)
        self.assertTrue(report['exceptions'][0]['frames_truncated'])

    def test_private_append_works_with_logging_disabled(self):
        disabled = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        try:
            self.assertTrue(record_exception(self.directory, captured_failure(), seat='pm', phase='request_thread_resume'))
            self.assertTrue(record_exception(self.directory, captured_failure(), seat='pm', phase='adapter_event'))
        finally: logging.disable(disabled)
        path = self.directory / 'exceptions.jsonl'
        self.assertEqual(stat.S_IMODE(self.directory.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertEqual(len(rows), 2)
        self.assertEqual(set(rows[0]), {'schema_version', 'recorded_at_utc', 'seat', 'phase', 'exceptions', 'chain_truncated'})
        self.assertNotIn(SECRET, path.read_text())

    def test_dynamic_labels_are_rejected_without_writes(self):
        self.assertFalse(record_exception(self.directory, captured_failure(), seat=SECRET, phase='client_build'))
        self.assertFalse(record_exception(self.directory, captured_failure(), seat='pm', phase=SECRET))
        self.assertFalse(self.directory.exists())

    def test_symlink_directory_or_file_does_not_write(self):
        target = self.root / 'other'; target.mkdir()
        self.directory.symlink_to(target, target_is_directory=True)
        self.assertFalse(record_exception(self.directory, captured_failure(), seat='pm', phase='client_build'))
        self.assertEqual(list(target.iterdir()), [])
        self.directory.unlink(); self.directory.mkdir(mode=0o700)
        protected = self.root / 'protected'; protected.write_text('unchanged')
        (self.directory/'exceptions.jsonl').symlink_to(protected)
        self.assertFalse(record_exception(self.directory, captured_failure(), seat='pm', phase='client_build'))
        self.assertEqual(protected.read_text(), 'unchanged')

    def test_limit_and_nonprivate_file_fail_without_replacing_data(self):
        self.directory.mkdir(mode=0o700)
        path = self.directory/'exceptions.jsonl'
        path.write_bytes(b'x' * MAX_FILE_BYTES); path.chmod(0o600)
        self.assertFalse(record_exception(self.directory, captured_failure(), seat='pm', phase='client_build'))
        self.assertEqual(path.stat().st_size, MAX_FILE_BYTES)
        path.write_text('unchanged'); path.chmod(0o644)
        self.assertFalse(record_exception(self.directory, captured_failure(), seat='pm', phase='client_build'))
        self.assertEqual(path.read_text(), 'unchanged')

    def test_missing_parent_is_diagnostic_failure_only(self):
        self.assertFalse(record_exception(self.root/'missing'/'diagnostics', captured_failure(), seat='pm', phase='client_build'))
        self.assertFalse((self.root/'missing').exists())


class BoundRequestDiagnosticsTests(unittest.IsolatedAsyncioTestCase):
    async def test_resume_cause_is_retained_without_fresh_thread_fallback(self):
        client = AsyncMock(); cause = ValueError(SECRET); client.request.side_effect = cause
        captured = []
        guard = BoundCodexClient(client, THREAD, lambda thread: self.fail('No new thread'),
                                 on_exception=lambda phase, error: captured.append((phase, exception_locations(error))))
        with self.assertRaises(FactoryError) as result:
            await guard.request('thread/resume', {'threadId': THREAD, 'prompt': SECRET})
        self.assertIs(result.exception.__cause__, cause)
        self.assertIsNone(guard.ready_thread)
        self.assertEqual(client.request.await_count, 1)
        self.assertEqual(captured[0][0], 'request_thread_resume')
        self.assertNotIn(SECRET, json.dumps(captured[0][1]))
        self.assertEqual([x['type']['name'] for x in captured[0][1]['exceptions']], ['FactoryError', 'ValueError'])

    async def test_fresh_start_guard_is_observed_without_client_request_or_admission(self):
        client = AsyncMock(); captured = []
        guard = BoundCodexClient(client, THREAD, lambda thread: self.fail('No new thread'),
                                 on_exception=lambda phase, error: captured.append((phase, exception_locations(error))))
        with self.assertRaises(FactoryError): await guard.request('thread/start', {'input': SECRET})
        self.assertEqual(captured[0][0], 'request_thread_start')
        client.request.assert_not_awaited()
        self.assertNotIn(SECRET, json.dumps(captured))

    async def test_diagnostic_failure_never_replaces_original_exception(self):
        original = ValueError(SECRET)
        client = AsyncMock(); client.request.side_effect = original
        def broken(phase, error): raise RuntimeError('Diagnostic disk unavailable')
        guard = BoundCodexClient(client, THREAD, lambda thread: None, on_exception=broken)
        guard.ready_thread = THREAD
        with self.assertRaises(ValueError) as result:
            await guard.request('turn/start', {'threadId': THREAD, 'input': SECRET})
        self.assertIs(result.exception, original)
        self.assertEqual(client.request.await_count, 1)

    async def test_success_and_default_constructor_keep_existing_behavior(self):
        client = AsyncMock(); client.request.return_value = {'thread': {'id': THREAD}}
        captured = []
        guard = BoundCodexClient(client, THREAD, lambda thread: None,
                                 on_exception=lambda *args: captured.append(args))
        self.assertEqual(await guard.request('thread/resume', {'threadId': THREAD}), {'thread': {'id': THREAD}})
        self.assertEqual(captured, [])
        self.assertEqual(guard.ready_thread, THREAD)
        ordinary = BoundCodexClient(client, THREAD, lambda thread: None)
        self.assertEqual(await ordinary.request('thread/resume', {'threadId': THREAD}), {'thread': {'id': THREAD}})


if __name__ == '__main__':
    unittest.main()
