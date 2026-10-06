"""Offline ownership and admission barriers, using real SDK health fixtures."""
import asyncio
import json
import inspect
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from factorykit.runtime import GateError, fingerprint
from factorykit.startup_admission import AdmissionController, binding, paths, read, request_release, write
from tests import test_membership_gap as fixtures


class AdmissionControllerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.config = {'paths': {'runs': str(self.root)}, 'band': {'rehearsal_room_id': fixtures.ROOM}}
        self.stop = asyncio.Event()
        self.check = AsyncMock(return_value={'contexts': {}, 'authenticated_roster': {'complete': True}})
        self.controller = AdmissionController(self.config, 'rehearsal', 'private-owner-token', self.stop, self.check, hold=True)
        self.record = {'token': 'private-owner-token', 'mode': 'rehearsal', 'status': 'ready_held',
                       'config_sha256': fingerprint(self.config), 'parent': {'pid': 123, 'created': 9.5}}

    async def turn(self, semaphore, calls):
        await self.controller.wait()
        async with semaphore:
            await self.controller.before_reserve()
            self.controller.reserved()
            calls.append('reserved/provider')

    async def test_waiting_callback_does_not_take_slot_or_admit_and_release_once(self):
        semaphore, calls = asyncio.Semaphore(1), []
        task = asyncio.create_task(self.turn(semaphore, calls))
        await asyncio.sleep(0)
        self.assertFalse(task.done()); self.assertFalse(semaphore.locked()); self.assertEqual(calls, [])
        await self.controller.ready()
        self.assertTrue(self.controller.state['warm_ready'])
        self.assertFalse(task.done()); self.assertEqual(self.controller.state['factory_admissions'], 0)
        request_release(self.config, self.record)
        await self.controller.poll_release(self.record['parent'])
        await task
        self.assertEqual(calls, ['reserved/provider'])
        self.assertEqual(self.check.await_args_list[0].args, (True,))
        self.assertEqual([x.args[0] for x in self.check.await_args_list], [True, False, None])
        with self.assertRaises(GateError): request_release(self.config, self.record)
        await self.controller.poll_release(self.record['parent'])
        self.assertEqual(self.controller.state['factory_admissions'], 1)

    async def test_automatic_barrier_waits_for_all_ready_proof(self):
        config = {'paths': {'runs': str(self.root/'automatic')}, 'band': self.config['band']}
        proof = asyncio.Event()
        async def check(warm):
            if warm: await proof.wait()
            return {'real': True}
        controller = AdmissionController(config, 'rehearsal', 'automatic', self.stop, check)
        waiter = asyncio.create_task(controller.wait())
        ready = asyncio.create_task(controller.ready())
        await asyncio.sleep(0)
        self.assertFalse(waiter.done()); self.assertFalse(ready.done())
        proof.set(); await ready; await waiter
        self.assertEqual(controller.state['state'], 'open')

    async def test_stop_cancels_held_callback_without_success_or_admission(self):
        calls = []
        task = asyncio.create_task(self.turn(asyncio.Semaphore(1), calls))
        await asyncio.sleep(0); await self.controller.close()
        with self.assertRaises(asyncio.CancelledError): await task
        self.assertEqual(calls, []); self.assertEqual(self.controller.state['factory_admissions'], 0)

    async def test_stop_racing_release_proof_never_opens(self):
        await self.controller.ready(); request_release(self.config, self.record)
        async def stop_during_check(warm):
            self.stop.set(); return {}
        self.controller.check = stop_during_check
        with self.assertRaises(asyncio.CancelledError):
            await self.controller.poll_release(self.record['parent'])
        self.assertFalse(self.controller.opened.is_set())
        self.assertEqual(self.controller.state['release_outcome'], 'blocked')

    async def test_blocked_budget_or_membership_during_release_retains_claim(self):
        await self.controller.ready(); request_release(self.config, self.record)
        self.check.side_effect = GateError('retained failed episode two')
        with self.assertRaises(GateError): await self.controller.poll_release(self.record['parent'])
        self.assertTrue(self.controller.claim.exists()); self.assertTrue(self.stop.is_set())
        self.assertEqual(self.controller.state['factory_admissions'], 0)

    async def test_state_drift_and_stale_config_cannot_claim(self):
        await self.controller.ready()
        bad = dict(self.record, config_sha256='changed')
        with self.assertRaises(GateError): request_release(self.config, bad)
        self.assertFalse(self.controller.claim.exists())
        state = dict(read(self.controller.path), warm_ready=False)
        write(self.controller.path, state)
        with self.assertRaises(GateError): request_release(self.config, self.record)
        with self.assertRaises(GateError): await self.controller.before_reserve()

    async def test_stale_parent_claim_fails_before_open(self):
        await self.controller.ready(); request_release(self.config, self.record)
        with self.assertRaises(GateError):
            await self.controller.poll_release({'pid': 123, 'created': 10})
        self.assertFalse(self.controller.opened.is_set())

    async def test_crash_between_claim_and_request_stays_held_and_no_retry(self):
        await self.controller.ready()
        original = write
        def crash(path, value, **kwargs):
            if path == self.controller.request: raise OSError('simulated crash')
            return original(path, value, **kwargs)
        with patch('factorykit.startup_admission.write', side_effect=crash):
            with self.assertRaises(OSError): request_release(self.config, self.record)
        await self.controller.poll_release(self.record['parent'])
        self.assertEqual(self.controller.state['state'], 'ready_held')
        with self.assertRaises(GateError): request_release(self.config, self.record)

    async def test_recheck_after_semaphore_wait_catches_exhausted_allowance(self):
        await self.controller.ready(); request_release(self.config, self.record)
        await self.controller.poll_release(self.record['parent'])
        semaphore, calls = asyncio.Semaphore(0), []
        task = asyncio.create_task(self.turn(semaphore, calls)); await asyncio.sleep(0)
        self.check.side_effect = GateError('original deadline expired')
        semaphore.release()
        with self.assertRaises(GateError): await task
        self.assertEqual(calls, []); self.assertEqual(self.controller.state['factory_admissions'], 0)

    async def test_private_complete_publication_and_no_raw_owner_token(self):
        await self.controller.ready(); request_release(self.config, self.record)
        for path in (self.controller.path, self.controller.claim, self.controller.request):
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertNotIn('private-owner-token', path.read_text())
        self.assertEqual(read(self.controller.claim), read(self.controller.request))


    async def test_shutdown_cancellation_survives_journal_cleanup_failure(self):
        task = asyncio.create_task(self.controller.wait())
        await asyncio.sleep(0)
        with patch.object(self.controller, '_save', side_effect=OSError('disk failed')):
            self.stop.set()
            with self.assertRaises(asyncio.CancelledError): await task
        self.assertEqual(self.controller.state['factory_admissions'], 0)

    def test_release_cli_checks_live_owner_before_and_after_publication(self):
        from factorykit import runtime
        from types import SimpleNamespace
        args = SimpleNamespace()
        with patch.object(runtime, 'get_config', return_value=self.config), \
             patch.object(runtime, 'read_registry', return_value=self.record), \
             patch.object(runtime, 'is_owned', side_effect=[True, False]), \
             patch('factorykit.startup_admission.request_release') as request:
            with self.assertRaisesRegex(GateError, 'changed after publication'):
                runtime.cmd_release_admission(args)
            request.assert_called_once()
        with patch.object(runtime, 'get_config', return_value=self.config), \
             patch.object(runtime, 'read_registry', return_value=self.record), \
             patch.object(runtime, 'is_owned', return_value=False), \
             patch('factorykit.startup_admission.request_release') as request:
            with self.assertRaisesRegex(GateError, 'exact live owned'):
                runtime.cmd_release_admission(args)
            request.assert_not_called()

    async def test_startup_wait_expiry_cancels_without_admission(self):
        now = [1000.0]
        c = AdmissionController(self.config, 'rehearsal', 'timed', self.stop, self.check,
                                hold=True, clock=lambda: now[0], monotonic=lambda: now[0])
        self.assertEqual(c.state['startup_deadline_epoch'], 1325)
        self.assertEqual(c.state['latest_wait_deadline_epoch'], 1385)
        now[0] = 1325
        with self.assertRaises(asyncio.CancelledError): await c.wait()
        self.assertTrue(self.stop.is_set()); self.assertEqual(c.state['factory_admissions'], 0)

    async def test_ready_hold_gets_only_sixty_seconds_and_original_outer_bound(self):
        now = [1000.0]
        c = AdmissionController(self.config, 'rehearsal', 'timed', self.stop, self.check,
                                hold=True, clock=lambda: now[0], monotonic=lambda: now[0])
        now[0] = 1050
        await c.ready()
        self.assertEqual(c.state['wait_deadline_epoch'], 1110)
        now[0] = 1110
        with self.assertRaises(asyncio.CancelledError): await c.poll_release(self.record['parent'])
        self.assertFalse(c.opened.is_set())

    async def test_approved_session_deadline_caps_hold_without_extending_clock(self):
        now = [1000.0]
        c = AdmissionController(self.config, 'rehearsal', 'timed', self.stop, self.check,
                                hold=True, budget_deadline=1070, clock=lambda: now[0], monotonic=lambda: now[0])
        self.assertEqual(c.wait_allowance, 70)
        now[0] = 1050; await c.ready()
        self.assertEqual(c.state['wait_deadline_epoch'], 1070)
        now[0] = 1070
        with self.assertRaises(asyncio.CancelledError): await c.wait()

    async def test_monotonic_timeout_cannot_be_extended_by_wall_clock_rollback(self):
        wall, monotonic = [1000.0], [100.0]
        c = AdmissionController(self.config, 'rehearsal', 'timed', self.stop, self.check,
                                clock=lambda: wall[0], monotonic=lambda: monotonic[0])
        wall[0] = 500; monotonic[0] = 425
        with self.assertRaises(asyncio.CancelledError): await c.wait()


class AdmissionRealSdkHealthTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.fixture = fixtures.MembershipGapTests()
        await self.fixture.asyncSetUp()
        async def clean_fixture():
            while self.fixture._cleanups:
                fn, args, kwargs = self.fixture._cleanups.pop()
                result = fn(*args, **kwargs)
                if inspect.isawaitable(result): await result
        self.addAsyncCleanup(clean_fixture)
        self.f = self.fixture

    async def test_full_ready_reads_authenticated_full8_without_repair_episode(self):
        proof = await self.f.observer.full_ready(self.f.agents)
        self.assertEqual(len(proof['authenticated_roster']['members']), 8)
        self.assertEqual(len(proof['contexts']), 7)
        self.assertEqual(self.f.observer.state['episodes'], [])
        self.assertEqual(self.f.ledger.path.read_bytes(), self.f.original_budget)

    async def test_initial_missing_context_cannot_become_warm_ready_or_create_episode(self):
        self.f.remove()
        with self.assertRaises(GateError): await self.f.observer.full_ready(self.f.agents)
        self.assertEqual(self.f.observer.state['episodes'], [])
        self.f.rest.agent_api_identity.get_agent_me.assert_not_awaited()

    async def test_warm_ready_requires_human_owner_and_rechecks_contexts_after_read(self):
        self.f.rows = [row for row in self.f.rows if row.type != 'User']
        with self.assertRaises(GateError): await self.f.observer.full_ready(self.f.agents)
        self.assertEqual(self.f.observer.state['episodes'], [])

    async def test_sdk_state_changes_during_rest_read_blocks_ready(self):
        original = self.f.roster
        async def changed(**kwargs):
            result = await original(**kwargs)
            self.f.remove()
            return result
        self.f.rest.agent_api_participants.list_agent_chat_participants.side_effect = changed
        with self.assertRaises(GateError): await self.f.observer.full_ready(self.f.agents)

    async def test_genuine_gap_allowed_only_after_warm_proof_and_original_deadline(self):
        cfg = dict(self.f.config, paths={'runs': str(self.f.root)}, band={'rehearsal_room_id': fixtures.ROOM})
        async def check(warm):
            return await (self.f.observer.full_ready(self.f.agents) if warm else self.f.observer.snapshot(self.f.agents))
        c = AdmissionController(cfg, 'rehearsal', 'owned', self.f.ledger.stop, check, hold=True)
        await c.ready(); self.f.remove()
        record = {'token': 'owned', 'mode': 'rehearsal', 'status': 'ready_held',
                  'config_sha256': fingerprint(cfg), 'parent': {'pid': 12, 'created': 5}}
        request_release(cfg, record); await c.poll_release(record['parent'])
        self.assertEqual(c.state['release_proof']['membership_gap']['deadline_epoch'], self.f.now+60)
        self.f.now += 60
        with self.assertRaises(GateError): await c.before_reserve()
        self.assertEqual(c.state['factory_admissions'], 0)
        self.assertEqual(self.f.ledger.path.read_bytes(), self.f.original_budget)

    async def test_retained_failed_episode_cannot_be_warm_or_admit(self):
        self.f.remove(); await self.f.observer.snapshot(self.f.agents)
        self.f.now += 60
        with self.assertRaises(GateError): await self.f.observer.snapshot(self.f.agents)
        self.f.readd_member(); self.f.restore_context()
        with self.assertRaises(GateError): await self.f.observer.full_ready(self.f.agents)
        with self.assertRaises(GateError): await self.f.observer.snapshot(self.f.agents)
        self.assertEqual(len(self.f.observer.state['episodes']), 1)


    async def test_second_failed_episode_blocks_before_native_or_band_start(self):
        from factorykit import runtime
        from factorykit.membership_gap import MembershipGapObserver
        from band import Agent
        self.f.config.update(paths={'runs': str(self.f.root)}, band={'rehearsal_room_id': fixtures.ROOM},
                             runtime={'strict_membership_recovery': True})
        self.f.observer.path.unlink()
        self.f.observer = self.f.observer_new()
        self.f.remove(); await self.f.observer.snapshot(self.f.agents)
        self.f.now += 1; self.f.readd_member(); self.f.restore_context()
        await self.f.observer.snapshot(self.f.agents)
        self.f.now += 1; self.f.remove(); await self.f.observer.snapshot(self.f.agents)
        self.f.now += 60
        with self.assertRaises(GateError): await self.f.observer.snapshot(self.f.agents)
        runtime_path = self.f.root/'runtime'/f'membership-{fixtures.ROOM}.json'
        runtime_path.parent.mkdir(); runtime_path.write_bytes(self.f.observer.path.read_bytes())
        before = runtime_path.read_bytes()
        with patch('factorykit.harnesses.start_runtime') as native, patch.object(Agent, 'create') as create:
            with self.assertRaises(GateError): await runtime.serve(self.f.config, 'rehearsal', 'owned', hold_admission=True)
            native.assert_not_called(); create.assert_not_called()
        self.assertEqual(runtime_path.read_bytes(), before)
        self.assertEqual(self.f.ledger.path.read_bytes(), self.f.original_budget)


if __name__ == '__main__': unittest.main()
