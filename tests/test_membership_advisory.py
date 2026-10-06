"""Offline normal membership monitoring using concrete BAND SDK objects."""
import inspect
import json
import unittest
from unittest.mock import AsyncMock

from factorykit.membership_advisory import AdvisoryMembershipObserver, strict_membership_recovery
from factorykit.runtime import GateError
from tests import test_membership_gap as fixtures


class AdvisoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.f = fixtures.MembershipGapTests()
        await self.f.asyncSetUp()
        self.config = self.f.config
        self.config['budgets']['balance_only'] = True
        self.observer = AdvisoryMembershipObserver(self.f.root/'advisory.json', self.config,
            fixtures.ROOM, self.f.ledger, clock=lambda: self.f.now)
        self.original = self.f.observer.path.read_bytes()
        self.budget = self.f.ledger.path.read_bytes()

    async def asyncTearDown(self):
        while self.f._cleanups:
            fn, args, kwargs = self.f._cleanups.pop()
            value = fn(*args, **kwargs)
            if inspect.isawaitable(value): await value

    async def test_default_advisory_and_explicit_strict(self):
        self.assertFalse(strict_membership_recovery(self.config))
        self.assertTrue(strict_membership_recovery(dict(self.config, runtime={'strict_membership_recovery': True})))

    async def test_warm_start_authenticates_full_roster_without_incident_or_budget_writes(self):
        result = await self.observer.full_ready(self.f.agents)
        self.assertEqual(len(result['authenticated_roster']['members']), 8)
        self.assertEqual(len(result['contexts']), 7)
        self.f.rest.agent_api_identity.get_agent_me.assert_awaited_once()
        self.assertFalse(self.observer.path.exists())
        self.assertEqual(self.f.observer.path.read_bytes(), self.original)
        self.assertEqual(self.f.ledger.path.read_bytes(), self.budget)

    async def test_warm_start_rejects_absence_and_rest_error(self):
        self.f.remove()
        with self.assertRaises(GateError): await self.observer.full_ready(self.f.agents)
        self.f.restore_context(); self.f.readd_member()
        self.f.rest.agent_api_identity.get_agent_me = AsyncMock(side_effect=RuntimeError('secret'))
        with self.assertRaisesRegex(GateError, 'roster read failed'): await self.observer.full_ready(self.f.agents)
        self.assertFalse(self.observer.path.exists())

    async def test_multiple_absent_and_missing_pm_remain_advisory_past_old_deadline(self):
        self.f.remove(0); self.f.remove(1)
        for advance in (1, 61, 86400):
            self.f.now += advance
            result = await self.observer.snapshot(self.f.agents)
            self.assertTrue(result['busy'])
            self.assertEqual(result['membership_advisory']['unavailable_agent_ids'], sorted(self.f.ids[:2]))
            self.assertFalse(self.f.ledger.stop.is_set())
            self.assertIsNone(self.f.ledger.reason('pm'))
        self.assertEqual(self.f.observer.path.read_bytes(), self.original)
        self.assertEqual(self.f.ledger.path.read_bytes(), self.budget)
        data = json.loads(self.observer.path.read_text())
        self.assertFalse(data['remote_membership_verified'])
        self.assertFalse(data['automatic_stop'])
        self.assertNotIn('deadline', self.observer.path.read_text())
        self.f.rest.agent_api_identity.get_agent_me.assert_not_awaited()

    async def test_dead_control_or_context_defers_notices_without_halt(self):
        self.f.agents[1].runtime.link._is_connected = False
        result = await self.observer.snapshot(self.f.agents)
        self.assertTrue(result['busy']); self.assertIsNotNone(result['membership_advisory'])
        self.f.contexts[self.f.ids[2]]._process_loop_task = None
        result = await self.observer.snapshot(self.f.agents)
        self.assertIn(self.f.ids[2], result['membership_advisory']['unavailable_agent_ids'])
        self.assertFalse(self.f.ledger.stop.is_set())

    async def test_returned_local_context_is_not_remote_restoration_proof(self):
        self.f.remove()
        await self.observer.snapshot(self.f.agents)
        self.f.restore_context()
        result = await self.observer.snapshot(self.f.agents)
        self.assertIsNone(result['membership_advisory'])
        self.assertNotIn('membership_restored', result)
        self.f.rest.agent_api_identity.get_agent_me.assert_not_awaited()
        self.assertEqual(self.f.observer.path.read_bytes(), self.original)

    async def test_identity_and_room_integrity_still_rejected(self):
        with self.assertRaises(GateError): await self.observer.snapshot(self.f.agents[:-1]+[self.f.agents[0]])
        self.f.contexts[self.f.ids[1]].room_id = 'wrong-room'
        with self.assertRaises(GateError): await self.observer.snapshot(self.f.agents)

    async def test_old_failed_strict_journal_is_not_loaded_changed_or_cleared(self):
        failed = b'{"blocked_reason":"historical failure","episodes":["preserved"]}\n'
        self.f.observer.path.write_bytes(failed)
        await self.observer.full_ready(self.f.agents)
        self.f.remove()
        await self.observer.snapshot(self.f.agents)
        self.assertEqual(self.f.observer.path.read_bytes(), failed)
        self.assertEqual(self.f.ledger.path.read_bytes(), self.budget)

    async def test_valid_callback_can_reserve_after_open_despite_late_unknown_peer(self):
        from factorykit.startup_admission import AdmissionController
        config = dict(self.config, paths={'runs':str(self.f.root)},
                      band={'rehearsal_room_id':fixtures.ROOM})
        async def check(warm):
            return await (self.observer.full_ready(self.f.agents) if warm is True
                          else self.observer.snapshot(self.f.agents))
        admission = AdmissionController(config, 'rehearsal', 'offline-owner', self.f.ledger.stop,
                                        check, clock=lambda:self.f.now)
        await admission.ready()
        self.f.remove(); self.f.now += 86400
        await admission.wait()
        async with self.f.ledger.semaphore:
            await admission.before_reserve()
            self.assertTrue(self.f.ledger.reserve('pm'))
            admission.reserved()
        self.assertEqual(self.f.ledger.data['turns']['pm'],2)
        self.assertFalse(self.f.ledger.stop.is_set())
        self.assertEqual(self.f.observer.path.read_bytes(),self.original)
        await admission.close()


if __name__ == '__main__': unittest.main()
