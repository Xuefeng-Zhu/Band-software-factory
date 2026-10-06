"""Removing the fault fixture does not waive actual collaboration evidence."""
import json
from pathlib import Path
from factorykit.common import canonical, digest, write_json
from factorykit.validation import observations, REQUIRED_OBSERVATIONS
from tests import test_toolkit as fixtures

class BalanceOnlyReadinessTests(fixtures.Fixture):
    def setUp(self):
        super().setUp()
        self.config['budgets']['balance_only'] = True
        self.config['runtime']['strict_membership_recovery'] = False

    def save_report(self, recovery_status='FAIL'):
        write_json(Path(self.config['paths']['runs'])/'readiness/observations.json', {
            'configuration_sha256': digest(canonical(self.config)),
            'source_lock_sha256': digest(Path(self.config['paths']['factory'])/'config/source-lock.json'),
            'factory_source_sha256': self.source_binding(),
            'observations': [{'id':'toy_missing_peer_delayed_message','status':recovery_status,
                              'observed':True,'observer':'synthetic historical failed fixture',
                              'observed_at':'2026-10-05T00:00:00Z','evidence':[]}]})

    def test_failed_fixture_is_not_a_money_only_gate_or_a_pass(self):
        self.save_report(); records, blockers=observations(self.config)
        self.assertEqual(records, [])
        self.assertFalse(any('toy_missing_peer_delayed_message' in value for value in blockers))
        self.assertEqual(len(blockers),len(REQUIRED_OBSERVATIONS)-1)
        for name in REQUIRED_OBSERVATIONS:
            if name!='toy_missing_peer_delayed_message':
                self.assertTrue(any(name in value for value in blockers),name)

    def test_missing_report_still_requires_thirteen_real_checks(self):
        records, blockers=observations(self.config)
        self.assertEqual(records, [])
        self.assertEqual(len(blockers),len(REQUIRED_OBSERVATIONS)-1)
        self.assertTrue(any('toy_independent_fixed_candidate_review' in value for value in blockers))

    def test_explicit_strict_mode_retains_recovery_gate(self):
        self.config['runtime']['strict_membership_recovery']=True
        self.save_report(); _, blockers=observations(self.config)
        self.assertTrue(any('toy_missing_peer_delayed_message' in value for value in blockers))

    def test_legacy_policy_keeps_all_original_checks(self):
        self.config['budgets'].pop('balance_only')
        self.save_report(); _, blockers=observations(self.config)
        self.assertEqual(len(blockers),len(REQUIRED_OBSERVATIONS))
