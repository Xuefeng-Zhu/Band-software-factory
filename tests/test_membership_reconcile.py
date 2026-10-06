"""No-network reconciliation preserves a failed episode and all consumption."""
import json
import inspect
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from factorykit.membership_gap import MembershipGapObserver
from factorykit.membership_reconcile import (DEADLINE_FAILURE, TERMINAL, archived_path,
    commit_reconciliation, create_once, encoded, no_admission_snapshot, sha)
from factorykit.runtime import GateError
from tests import test_membership_gap as gap_fixtures


class ReconciliationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.f = gap_fixtures.MembershipGapTests()
        await self.f.asyncSetUp()
        async def clean_fixture():
            while self.f._cleanups:
                fn, args, kwargs = self.f._cleanups.pop()
                result = fn(*args, **kwargs)
                if inspect.isawaitable(result):
                    await result
        self.addAsyncCleanup(clean_fixture)
        f = self.f
        f.remove(6)
        await f.observer.snapshot(f.agents)
        f.now += 60
        with self.assertRaisesRegex(GateError, 'deadline expired'):
            await f.observer.snapshot(f.agents)
        self.before = f.observer.path.read_bytes()
        self.original = json.loads(self.before)
        self.files = {'membership': sha(self.before), 'budget': sha(f.ledger.path.read_bytes()),
                      'guard': '2'*64, 'workflow': '3'*64, 'owner': '4'*64,
                      'task_board': None, 'execution_events': None}
        f.readd_member(6); f.restore_context(6)
        self.proof = {'observed_epoch': f.now, 'room_id': gap_fixtures.ROOM,
            'authenticated_pm_id': f.ids[0], 'owner_uuid': gap_fixtures.OWNER, 'missing_agent_id': None,
            'members': sorted([{'id':r.id, 'type':r.type, 'role':r.role, 'status':r.status} for r in f.rows], key=lambda r:r['id'])}
        self.plan = {'schema_version': 1, 'configuration_sha256': f.observer.binding['configuration_sha256'],
            'room_id': gap_fixtures.ROOM, 'agent_id': f.ids[6], 'owner_uuid': gap_fixtures.OWNER,
            'files': self.files, 'guard_requests': 4, 'guard_tokens':24765, 'helper_sha256':'f'*64, 'failed_reason':DEADLINE_FAILURE, 'failure_cause':'unknown'}
        self.plan_raw = encoded(self.plan)
        self.claim = {'plan_sha256':sha(self.plan_raw), 'agent_id':f.ids[6], 'room_id':gap_fixtures.ROOM,
            'helper_sha256':'f'*64, 'status':'CLAIMED_ONE_RESTORE_NO_RETRY', 'claimed_epoch':f.now}
        self.claim_path = f.observer.path.with_name(f.observer.path.name+'.operator-restore.claim.json')
        create_once(self.claim_path, encoded(self.claim))
        self.snapshot = patch('factorykit.membership_reconcile.no_admission_snapshot', return_value=self.files)
        self.snapshot_mock = self.snapshot.start()
        self.addCleanup(self.snapshot.stop)

    def commit(self):
        return commit_reconciliation(self.f.observer, self.plan_raw, self.proof,
                                     helper_sha256='f'*64, clock=lambda:self.f.now)

    async def test_failure_retained_and_new_episode_consumes_only_remaining_slot(self):
        f = self.f
        result = self.commit()
        self.assertEqual(result['status'], 'FAILED_EPISODE_OPERATOR_RESTORED')
        saved = f.retained()
        episode = saved['episodes'][0]
        self.assertEqual(episode['state'], TERMINAL)
        self.assertEqual(episode['outcome'], 'FAILED')
        self.assertEqual(episode['failed_reason'], DEADLINE_FAILURE)
        for key, value in self.original['episodes'][0].items():
            if key != 'state':
                self.assertEqual(episode[key], value)
        self.assertEqual(archived_path(f.observer.path, sha(self.before), 'failed').read_bytes(), self.before)
        self.assertEqual(f.ledger.path.read_bytes(), f.original_budget)
        f.observer = f.observer_new()
        self.assertIsNone((await f.observer.snapshot(f.agents))['membership_gap'])
        f.now += 1
        f.remove(6)
        activity = await f.observer.snapshot(f.agents)
        self.assertEqual(activity['membership_gap']['transitions_observed'], 2)
        self.assertEqual(activity['membership_gap']['deadline_epoch'], f.now+60)
        f.now += 1
        f.readd_member(6); f.restore_context(6)
        await f.observer.snapshot(f.agents)
        f.remove(6)
        with self.assertRaisesRegex(GateError, 'transition cap'):
            await f.observer.snapshot(f.agents)
        self.assertEqual(f.ledger.path.read_bytes(), f.original_budget)

    async def test_new_absence_must_follow_post_failure_full_roster(self):
        self.commit()
        self.f.remove(6)
        with self.assertRaisesRegex(GateError, 'must follow'):
            await self.f.observer.snapshot(self.f.agents)

    async def test_cannot_clear_non_deadline_blocker(self):
        self.f.observer.state['blocked_reason'] = 'different or multiple missing members'
        self.f.observer._save()
        with self.assertRaises(GateError):
            self.commit()
        self.assertEqual(self.f.retained()['blocked_reason'], 'different or multiple missing members')

    async def test_cannot_reconcile_twice(self):
        self.commit()
        after = self.f.observer.path.read_bytes()
        with self.assertRaises(GateError):
            self.commit()
        self.assertEqual(self.f.observer.path.read_bytes(), after)

    async def test_changed_evidence_before_commit_refuses_without_journal_write(self):
        self.snapshot_mock.return_value = dict(self.files, guard='e'*64)
        with self.assertRaisesRegex(GateError, 'evidence changed'):
            self.commit()
        self.assertEqual(self.f.observer.path.read_bytes(), self.before)

    async def test_evidence_change_at_atomic_boundary_refuses(self):
        self.snapshot_mock.side_effect = [self.files, dict(self.files, budget='e'*64)]
        with self.assertRaisesRegex(GateError, 'atomic commit'):
            self.commit()
        self.assertEqual(self.f.observer.path.read_bytes(), self.before)

    async def test_incomplete_or_stale_post_failure_roster_refused(self):
        self.proof['members'].pop()
        with self.assertRaises(GateError):
            self.commit()
        self.assertEqual(self.f.observer.path.read_bytes(), self.before)

    async def test_proof_before_original_deadline_is_not_operator_restoration(self):
        self.proof['observed_epoch'] -= 1
        with self.assertRaisesRegex(GateError, 'post-failure'):
            self.commit()

    async def test_archive_tampering_or_missing_archive_blocks_restart(self):
        self.commit()
        archive = archived_path(self.f.observer.path, sha(self.before), 'failed')
        archive.write_bytes(self.before + b' ')
        with self.assertRaisesRegex(GateError, 'hash changed'):
            self.f.observer_new()

    async def test_deadline_tamper_after_commit_blocks_restart(self):
        self.commit()
        self.f.observer.state['episodes'][0]['deadline_epoch'] += 60
        self.f.observer._save()
        with self.assertRaisesRegex(GateError, 'deadline invalid'):
            self.f.observer_new()

    async def test_claim_cannot_be_recreated_or_changed(self):
        with self.assertRaises(FileExistsError):
            create_once(self.claim_path, encoded(self.claim))
        self.claim['agent_id'] = self.f.ids[2]
        self.claim_path.write_bytes(encoded(self.claim))
        with self.assertRaisesRegex(GateError, 'claim binding'):
            self.commit()

    async def test_second_episode_error_never_inherits_old_operator_clearance(self):
        f = self.f
        self.commit()
        f.now += 1
        f.remove(6)
        f.rest.agent_api_participants.list_agent_chat_participants.side_effect = RuntimeError('network failed')
        with self.assertRaisesRegex(GateError, 'roster read failed'):
            await f.observer.snapshot(f.agents)
        self.assertEqual(f.retained()['blocked_reason'], 'authenticated roster read failed')
        with self.assertRaisesRegex(GateError, 'retained failure requires review'):
            await f.observer_new().snapshot(f.agents)
        self.assertEqual(len(f.retained()['episodes']), 2)

    async def test_exact_reviewed_roster_failure_stays_unknown_failed(self):
        f = self.f
        self.original['blocked_reason'] = 'authenticated roster read failed'
        f.observer.state = self.original
        f.observer._save()
        self.before = f.observer.path.read_bytes()
        self.files['membership'] = sha(self.before)
        self.plan['failed_reason'] = 'authenticated roster read failed'
        self.plan_raw = encoded(self.plan)
        self.claim['plan_sha256'] = sha(self.plan_raw)
        self.claim_path.write_bytes(encoded(self.claim))
        self.commit()
        e = f.retained()['episodes'][0]
        self.assertEqual(e['failed_reason'], 'authenticated roster read failed')
        self.assertEqual(e['failure_cause'], 'unknown')
        self.assertEqual(e['outcome'], 'FAILED')
        self.assertEqual(e['deadline_epoch'], self.original['episodes'][0]['deadline_epoch'])



class NoAdmissionEvidenceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.runtime = self.root/'runtime'
        self.runtime.mkdir(mode=0o700)
        self.room = gap_fixtures.ROOM
        self.config = {'paths': {'runs': str(self.root)},
            'band': {'rehearsal_room_id': self.room},
            'budgets': {'billing_mode': 'spend_cap', 'accounting_scope':'session'},
            'runtime': {'featherless_budget_guard': {'ledger':str(self.runtime/'guard.json')}}}
        self.docs = {
            f'membership-{self.room}.json': {'preserved': True},
            'budget-session.json': {'tokens': 22000, 'turns': {'pm':1,'architect':1}, 'started_epoch':100},
            'guard.json': {'requests': {str(i):{'status':'settled', 'prompt_tokens':6000,
                            'completion_tokens':765 if i==0 else 0} for i in range(4)}},
            f'workflow-{self.room}.json': {'scope': {'room_id':self.room},
                'turns':{},'deliveries':{},'events':{},'incidents':{},'notices':{}},
            'owner.json': {'status':'stopped','parent':{},'children':[]}}
        for name,value in self.docs.items():
            create_once(self.runtime/name, encoded(value))
        self.guard_check = patch('factorykit.budgets.persisted_budget_blockers', return_value=[])
        self.guard_check.start()
        self.addCleanup(self.guard_check.stop)

    def write(self, name):
        (self.runtime/name).write_bytes(encoded(self.docs[name]))

    def test_prior_paid_verification_counts_and_clock_are_not_zeroed(self):
        before = (self.runtime/'budget-session.json').read_bytes()
        result = no_admission_snapshot(self.config, self.room)
        self.assertEqual(result['budget'], sha(before))
        self.assertEqual((self.runtime/'budget-session.json').read_bytes(), before)

    def test_any_workflow_admission_refuses(self):
        name = f'workflow-{self.room}.json'
        self.docs[name]['turns'] = {'pm:2:message': {'status':'running'}}
        self.write(name)
        with self.assertRaisesRegex(GateError, 'already admitted'):
            no_admission_snapshot(self.config, self.room)

    def test_actual_task_or_tool_evidence_refuses(self):
        create_once(self.runtime/'execution-events.jsonl', b'{}\n')
        with self.assertRaisesRegex(GateError, 'event evidence'):
            no_admission_snapshot(self.config, self.room)

    def test_guard_new_request_or_unknown_state_refuses(self):
        self.docs['guard.json']['requests']['0']['status'] = 'unknown'
        self.write('guard.json')
        with self.assertRaisesRegex(GateError, 'consumption differs'):
            no_admission_snapshot(self.config, self.room)

    def test_active_supervisor_refuses(self):
        self.docs['owner.json']['status'] = 'running'
        self.write('owner.json')
        with self.assertRaisesRegex(GateError, 'confirmed stopped'):
            no_admission_snapshot(self.config, self.room)

    def test_existing_budget_blocker_refuses(self):
        with patch('factorykit.budgets.persisted_budget_blockers', return_value=['stopped']):
            with self.assertRaisesRegex(GateError, 'consumption budget'):
                no_admission_snapshot(self.config, self.room)

    def test_world_readable_or_symlink_evidence_refused(self):
        (self.runtime/'owner.json').chmod(0o644)
        with self.assertRaisesRegex(GateError, 'private regular'):
            no_admission_snapshot(self.config, self.room)


if __name__ == '__main__':
    unittest.main()
