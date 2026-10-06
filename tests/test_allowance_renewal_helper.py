"""One-use filesystem transaction tests with local fake Hermes accounting."""
import copy
from contextlib import redirect_stdout
import fcntl
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import yaml

import test_allowance_renewal as renewal_fixtures


class RenewalHelperTests(unittest.TestCase):
    def setUp(self):
        self.fixture = renewal_fixtures.RenewalTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.temp.cleanup)
        self.run = self.fixture.root
        self.attempt = self.run / 'attempts/fresh'
        self.attempt.mkdir(parents=True, mode=0o700)
        spec = importlib.util.spec_from_file_location('approved_renewal_helper',
            Path(__file__).resolve().parents[1] / 'tooling/reconcile-approved-renewal.py')
        self.helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.helper)
        self.helper.ROOT, self.helper.RUN, self.helper.ATTEMPT = self.run.parent, self.run, self.attempt
        self.helper.FOLDER, self.helper.RENEWAL_STARTED = self.attempt / 'accounting-renewal', self.fixture.now
        self.base = copy.deepcopy(self.fixture.base)
        self.fresh = copy.deepcopy(self.fixture.base)
        self.fresh['budgets']['approved'] = False
        self.fresh['band'].update(rehearsal_room_id=self.fixture.new_rooms[0], judged_room_id=self.fixture.new_rooms[1])
        for seat in self.fresh['seats']:
            from uuid import uuid4
            seat['agent_id'] = str(uuid4())
        self.original = self.run / 'factory.yaml'
        self.config = self.attempt / 'factory.yaml'
        for path, data in ((self.original, self.base), (self.config, self.fresh)):
            path.write_text(yaml.safe_dump(data))
            path.chmod(0o600)
        self.fixture.save(self.run / 'runtime/budget-session.json', self.fixture.factory)
        self.fixture.save(self.run / 'runtime/featherless-requests.json', self.fixture.guard)
        self.fixture.save(self.run / 'runtime/owner.json',
                          {'status': 'stopped', 'parent': {'pid': 987654321, 'created': 1.0}, 'children': []})
        self.journal = self.run / 'runtime' / ('membership-' + self.fixture.old_rooms[0] + '.json')
        self.fixture.save(self.journal, {'episodes': [{'outcome': 'FAILED'}, {'outcome': None, 'deadline_epoch': 1}]})
        self.protected = {str(p): p.read_bytes() for p in (self.original, self.journal, self.run / 'runtime/owner.json')}

    def args(self, execute=True):
        args = ['helper', '--config', str(self.config)]
        if execute:
            args.append('--execute')
            for name, path in (('configuration', self.config), ('original-configuration', self.original),
                               ('factory-budget', self.run / 'runtime/budget-session.json'),
                               ('request-ledger', self.run / 'runtime/featherless-requests.json')):
                args += ['--' + name + '-sha256', self.helper.sha(path.read_bytes())]
        return args

    def run_helper(self, args):
        output = io.StringIO()
        def load(path):
            return yaml.safe_load(Path(path).read_bytes())
        with patch.object(sys, 'argv', args), patch('factorykit.common.load_config', side_effect=load), \
                patch.object(self.helper.psutil, 'process_iter', return_value=[]), redirect_stdout(output):
            result = self.helper.main()
        return result, json.loads(output.getvalue())

    def test_full_commit_preserves_old_config_failures_and_24765_tokens(self):
        result, report = self.run_helper(self.args())
        self.assertEqual(result, 0)
        self.assertEqual(report['status'], 'PASS')
        self.assertTrue(report['protected_unchanged'])
        self.assertTrue(report['requests_unchanged'])
        for path, raw in self.protected.items():
            self.assertEqual(Path(path).read_bytes(), raw)
        config = yaml.safe_load(self.config.read_bytes())
        self.assertEqual(config['band']['archived_room_ids'], sorted(self.fixture.old_rooms))
        self.assertIn('time_renewal', config['runtime']['featherless_budget_guard'])
        self.assertIs(config['budgets']['approved'], True)
        guard = json.loads((self.run / 'runtime/featherless-requests.json').read_bytes())
        self.assertEqual(guard['requests'], self.fixture.guard['requests'])
        self.assertEqual(guard['started_epoch'], self.fixture.origin)
        self.assertEqual(json.loads((self.run / 'runtime/budget-session.json').read_bytes())['tokens'], 24765)

    def test_review_is_read_only_and_reports_exact_input_bindings(self):
        before = {str(p): p.read_bytes() for p in (self.config, self.original,
                  self.run / 'runtime/budget-session.json', self.run / 'runtime/featherless-requests.json')}
        result, report = self.run_helper(self.args(execute=False))
        self.assertEqual(report['status'], 'REVIEW_ONLY')
        self.assertEqual(report['ledger_writes'], 0)
        self.assertFalse(self.helper.FOLDER.exists())
        for path, raw in before.items():
            self.assertEqual(Path(path).read_bytes(), raw)

    def test_duplicate_reconciliation_is_refused_without_reset(self):
        self.run_helper(self.args())
        before = (self.run / 'runtime/featherless-requests.json').read_bytes()
        with self.assertRaises(ValueError):
            self.run_helper(self.args())
        self.assertEqual((self.run / 'runtime/featherless-requests.json').read_bytes(), before)

    def test_stale_hash_does_not_create_claim_or_change_accounting(self):
        args = self.args()
        args[-1] = '0' * 64
        before = (self.run / 'runtime/budget-session.json').read_bytes()
        with self.assertRaises(ValueError):
            self.run_helper(args)
        self.assertFalse(self.helper.FOLDER.exists())
        self.assertEqual((self.run / 'runtime/budget-session.json').read_bytes(), before)

    def test_launch_or_request_lock_contention_blocks_without_evidence_writes(self):
        for name in ('launch.lock', 'featherless-requests.json.lock'):
            path = self.run / 'runtime' / name
            fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaises(BlockingIOError):
                    self.run_helper(self.args())
                self.assertFalse(self.helper.FOLDER.exists())
            finally:
                os.close(fd)

    def test_retained_failure_status_is_not_eligible_to_clear(self):
        data = copy.deepcopy(self.fixture.factory)
        data['stopped_reason'] = 'some non-time failure'
        self.fixture.save(self.run / 'runtime/budget-session.json', data)
        original = (self.run / 'runtime/budget-session.json').read_bytes()
        with self.assertRaises(ValueError):
            self.run_helper(self.args())
        self.assertTrue(self.helper.FOLDER.exists())
        self.assertFalse((self.helper.FOLDER / 'claim.json').exists())
        self.assertEqual((self.run / 'runtime/budget-session.json').read_bytes(), original)

    def test_durable_approval_claim_and_before_images_precede_first_ledger_replace(self):
        original_replace = self.helper.replace
        first_replace = []
        with patch.object(self.helper, 'fsync_directory', wraps=self.helper.fsync_directory) as sync:
            def checked_replace(path, raw):
                if not first_replace:
                    first_replace.append(path)
                    before = self.helper.FOLDER / 'before'
                    calls = [call.args[0] for call in sync.call_args_list]
                    self.assertIn(self.attempt, calls)
                    self.assertGreaterEqual(calls.count(self.helper.FOLDER), 4)
                    self.assertGreaterEqual(calls.count(before), 7)
                    self.assertTrue((self.helper.FOLDER / 'claim.json').is_file())
                    self.assertTrue((self.helper.FOLDER / 'approval.json').is_file())
                    self.assertEqual(len(list(before.iterdir())), 6)
                return original_replace(path, raw)
            with patch.object(self.helper, 'replace', side_effect=checked_replace):
                result, report = self.run_helper(self.args())
        self.assertEqual(result, 0)
        self.assertEqual(report['status'], 'PASS')
        self.assertEqual(first_replace, [self.run / 'runtime/featherless-requests.json'])
