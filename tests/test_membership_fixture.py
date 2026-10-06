"""Truthful second REST absence keeps count/deadline even before SDK startup."""
import inspect
import json
import unittest
from unittest.mock import patch

from factorykit.membership_fixture import fixture_path, seed_absence
from factorykit.membership_reconcile import create_once, encoded, sha
from factorykit.runtime import GateError
from tests import test_membership_reconcile as recovery


class SecondFixtureTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        support = recovery.ReconciliationTests()
        await support.asyncSetUp()
        async def cleanup():
            while support._cleanups:
                fn,args,kwargs=support._cleanups.pop()
                result=fn(*args,**kwargs)
                if inspect.isawaitable(result): await result
        self.addAsyncCleanup(cleanup)
        support.commit()
        self.f=support.f
        self.prior=self.f.observer.path.read_bytes()
        self.f.now+=1
        self.before=json.loads(json.dumps(support.proof))
        self.before['observed_epoch']=self.f.now
        self.files=dict(support.files,membership=sha(self.prior))
        self.plan={'configuration_sha256':self.f.observer.binding['configuration_sha256'],
            'room_id':self.f.observer.binding['room_id'],'agent_id':self.f.ids[6],
            'files':self.files,'reconciled_journal_sha256':sha(self.prior)}
        self.claim={'status':'CLAIMED_SECOND_REMOVAL_NO_RETRY','attempt_index':2,
            'room_id':self.plan['room_id'],'agent_id':self.f.ids[6],
            'plan':self.plan,'plan_sha256':sha(encoded(self.plan)),
            'roster_before':self.before,'claimed_epoch':self.f.now}
        create_once(fixture_path(self.f.observer.path,'claim'),encoded(self.claim))
        self.f.now+=1
        self.f.remove(6)
        self.absence=json.loads(json.dumps(self.before))
        self.absence.update(observed_epoch=self.f.now,missing_agent_id=self.f.ids[6])
        self.absence['members']=[r for r in self.absence['members'] if r['id']!=self.f.ids[6]]
        snapshot=patch('factorykit.membership_fixture.no_admission_snapshot',return_value=self.files)
        snapshot.start();self.addCleanup(snapshot.stop)

    def seed(self):
        return seed_absence(self.f.observer,self.plan,self.absence)

    async def test_real_rest_absence_consumes_second_slot_before_any_sdk_snapshot(self):
        deadline=self.seed()
        episode=self.f.retained()['episodes'][1]
        self.assertEqual(deadline,self.absence['observed_epoch']+60)
        self.assertEqual(episode['absence_source'],'operator_authenticated_rest')
        self.assertFalse(episode['sdk_absence_observed'])
        self.assertEqual(len(self.f.retained()['episodes']),2)
        self.assertEqual(self.f.ledger.path.read_bytes(),self.f.original_budget)

    async def test_pm_repair_before_first_snapshot_is_not_fabricated_sdk_absence(self):
        self.seed()
        self.f.now+=1
        self.f.readd_member(6);self.f.restore_context(6)
        result=await self.f.observer.snapshot(self.f.agents)
        self.assertEqual(result['membership_restored']['absence_source'],'operator_authenticated_rest')
        self.assertFalse(result['membership_restored']['sdk_absence_observed'])
        self.assertEqual(self.f.retained()['episodes'][1]['state'],'restored')

    async def test_actual_sdk_absence_observation_is_marked_only_after_snapshot(self):
        self.seed()
        await self.f.observer.snapshot(self.f.agents)
        self.assertTrue(self.f.retained()['episodes'][1]['sdk_absence_observed'])
        self.f.now+=1;self.f.readd_member(6);self.f.restore_context(6)
        await self.f.observer.snapshot(self.f.agents)
        self.assertTrue(self.f.retained()['episodes'][1]['sdk_absence_observed'])

    async def test_late_start_never_gets_a_fresh_sixty_seconds(self):
        deadline=self.seed()
        self.f.now=deadline
        self.f.readd_member(6);self.f.restore_context(6)
        with self.assertRaisesRegex(GateError,'deadline expired'):
            await self.f.observer_new().snapshot(self.f.agents)
        self.assertEqual(self.f.retained()['episodes'][1]['deadline_epoch'],deadline)
        self.assertEqual(self.f.ledger.path.read_bytes(),self.f.original_budget)

    async def test_third_absence_refused_even_if_sdk_never_saw_second_absence(self):
        self.seed();self.f.now+=1
        self.f.readd_member(6);self.f.restore_context(6)
        await self.f.observer.snapshot(self.f.agents)
        self.f.remove(6)
        with self.assertRaisesRegex(GateError,'transition cap'):
            await self.f.observer.snapshot(self.f.agents)

    async def test_claim_and_seed_cannot_replay(self):
        self.seed()
        with self.assertRaises(FileExistsError):
            create_once(fixture_path(self.f.observer.path,'claim'),encoded(self.claim))
        with self.assertRaisesRegex(GateError,'no remaining'):
            self.seed()

    async def test_claim_tamper_prevents_runtime_start(self):
        self.seed()
        path=fixture_path(self.f.observer.path,'claim')
        path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaisesRegex(GateError,'hash changed'):
            self.f.observer_new()

    async def test_fake_sdk_flag_without_observation_time_is_rejected(self):
        self.seed()
        self.f.observer.state['episodes'][1]['sdk_absence_observed']=True
        self.f.observer._save()
        with self.assertRaisesRegex(GateError,'falsely claims'):
            self.f.observer_new()

    async def test_previously_missing_member_cannot_be_a_distinct_fixture(self):
        self.claim['roster_before']=self.absence
        fixture_path(self.f.observer.path,'claim').write_bytes(encoded(self.claim))
        with self.assertRaises(GateError):
            self.seed()
        self.assertEqual(self.f.observer.path.read_bytes(),self.prior)


    async def test_partial_removal_claim_blocks_unseeded_runtime_restart(self):
        with self.assertRaisesRegex(GateError,'no complete bound absence'):
            self.f.observer_new()
        self.assertEqual(self.f.observer.path.read_bytes(),self.prior)


if __name__=='__main__':
    unittest.main()
