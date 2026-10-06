"""Offline membership transitions using maintained SDK context/control objects."""
import asyncio
import json
from pathlib import Path
import socket
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from band.client.rest import ChatParticipant
from band.runtime.execution import ExecutionContext, ExecutionState

from factorykit.membership_gap import MembershipGapObserver
from factorykit.runtime import BudgetLedger, GateError
from factorykit.workflow import WorkflowWatchdog
from factorykit.workflow_runtime import sdk_execution_activity, send_due_notice
from tests import test_membership_liveness as fixtures

ROOM = '10000000-0000-4000-8000-000000000001'
OWNER = '10000000-0000-4000-8000-000000000009'


class MembershipGapTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.fixture = fixtures.MembershipLivenessTests()
        await self.fixture.asyncSetUp()
        self.addAsyncCleanup(self.fixture.asyncTearDown)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.now = time.time()
        self.agents, self.ids = self.fixture.agents, self.fixture.ids
        self.config = {'seats': [dict(id=name, agent_id=identity, display_name=name,
            handle='@owner/' + name) for name, identity in zip(
                ('pm', 'architect', 'designer', 'backend', 'frontend', 'qa', 'reviewer'), self.ids)],
            'budgets': dict(max_active_seats=1, overall_timeout_seconds=21600,
                stage_timeout_seconds=21600, max_turns_per_seat=30, max_total_tokens=2000000,
                turn_timeout_seconds=900, ack_timeout_seconds=60, max_repairs=2)}
        self.ledger = BudgetLedger(self.config['budgets'], self.root/'budget.json', ROOM)
        self.ledger.data['tokens'] = 1000
        self.ledger.data['turns'] = {'pm': 1}
        self.ledger.save()
        self.original_budget = self.ledger.path.read_bytes()
        self.contexts = {}
        for agent, identity in zip(self.agents, self.ids):
            context = ExecutionContext(ROOM, agent.runtime.link, AsyncMock(), agent_id=identity)
            context._process_loop_task = self.fixture.task()
            context.state = ExecutionState.IDLE
            agent.runtime.runtime.executions[ROOM] = context
            self.contexts[identity] = context
        self.rows = [ChatParticipant(id=row['agent_id'], name=row['display_name'],
            handle=row['handle'].removeprefix('@'), type='Agent',
            role='owner' if row['id']=='pm' else 'member', status='active') for row in self.config['seats']]
        self.rows.append(ChatParticipant(id=OWNER, name='Owner', type='User', role='member', status='active'))
        self.rest = self.agents[0].runtime.link.rest
        self.rest.agent_api_identity.get_agent_me = AsyncMock(return_value=SimpleNamespace(data=SimpleNamespace(
            id=self.ids[0], name='pm', handle='owner/pm', owner_uuid=OWNER)))
        self.rest.agent_api_chats.get_agent_chat = AsyncMock(return_value=SimpleNamespace(data=SimpleNamespace(id=ROOM)))
        self.rest.agent_api_participants.list_agent_chat_participants = AsyncMock(side_effect=self.roster)
        self.rest.agent_api_messages.create_agent_chat_message = AsyncMock()
        self.observer = self.observer_new()
        self.blocker = patch.object(socket.socket, 'connect', side_effect=AssertionError('All membership tests are offline'))
        self.blocker.start()
        self.addCleanup(self.blocker.stop)

    def observer_new(self, config=None):
        return MembershipGapObserver(self.root/'membership.json', config or self.config, ROOM,
                                     self.ledger, clock=lambda: self.now)

    async def roster(self, **kwargs):
        self.assertEqual(kwargs['chat_id'], ROOM)
        self.assertEqual(kwargs['request_options']['max_retries'], 0)
        return SimpleNamespace(data=list(self.rows))

    def remove(self, index=1):
        identity = self.ids[index]
        self.agents[index].runtime.runtime.executions.pop(ROOM)
        self.rows = [row for row in self.rows if row.id != identity]

    def readd_member(self, index=1):
        row = self.config['seats'][index]
        self.rows.append(ChatParticipant(id=row['agent_id'], name=row['display_name'],
            handle=row['handle'].removeprefix('@'), type='Agent', role='member', status='inactive'))

    def restore_context(self, index=1):
        self.agents[index].runtime.runtime.executions[ROOM] = self.contexts[self.ids[index]]

    def retained(self):
        return json.loads(self.observer.path.read_text())

    async def test_healthy_strict_state_no_rest_and_no_budget_write(self):
        self.assertEqual((await self.observer.snapshot(self.agents))['contexts'],
                         sdk_execution_activity(self.agents, ROOM, self.ids)['contexts'])
        self.rest.agent_api_identity.get_agent_me.assert_not_awaited()
        self.assertEqual(self.retained()['episodes'], [])
        self.assertEqual(self.ledger.path.read_bytes(), self.original_budget)

    async def test_real_absence_readd_then_actual_context_restores_under_original_deadline(self):
        self.remove()
        activity = await self.observer.snapshot(self.agents)
        self.assertTrue(activity['busy'])
        deadline = activity['membership_gap']['deadline_epoch']
        self.assertEqual(len(activity['contexts']), 6)
        self.now += 10
        self.readd_member()
        pending = await self.observer.snapshot(self.agents)
        self.assertEqual(pending['membership_gap']['state'], 'awaiting_context')
        self.assertEqual(pending['membership_gap']['deadline_epoch'], deadline)
        self.now += 3
        self.restore_context()
        final = await self.observer.snapshot(self.agents)
        self.assertIsNone(final['membership_gap'])
        self.assertEqual(final['membership_restored']['elapsed_seconds'], 13)
        episode = self.retained()['episodes'][0]
        self.assertEqual(episode['absence']['missing_agent_id'], self.ids[1])
        self.assertIsNone(episode['restoration']['missing_agent_id'])
        self.assertEqual(episode['deadline_epoch'], deadline)
        self.assertEqual(self.ledger.path.read_bytes(), self.original_budget)
        self.rest.agent_api_messages.create_agent_chat_message.assert_not_awaited()

    async def test_initial_missing_context_with_present_member_is_not_tolerated(self):
        self.agents[1].runtime.runtime.executions.pop(ROOM)
        with self.assertRaisesRegex(GateError, 'no authenticated absence'):
            await self.observer.snapshot(self.agents)

    async def test_missing_pm_or_two_contexts_fail_without_rest(self):
        self.remove(0)
        with self.assertRaises(GateError):
            await self.observer.snapshot(self.agents)
        self.rest.agent_api_identity.get_agent_me.assert_not_awaited()

    async def test_two_missing_contexts_fail_without_rest(self):
        self.remove(1); self.remove(2)
        with self.assertRaises(GateError):
            await self.observer.snapshot(self.agents)
        self.rest.agent_api_identity.get_agent_me.assert_not_awaited()

    async def test_dead_existing_context_is_not_membership_absence(self):
        self.contexts[self.ids[1]]._process_loop_task = None
        with self.assertRaises(GateError):
            await self.observer.snapshot(self.agents)
        self.rest.agent_api_identity.get_agent_me.assert_not_awaited()

    async def test_custom_existing_context_is_not_membership_absence(self):
        self.agents[1].runtime.runtime.executions[ROOM] = SimpleNamespace()
        with self.assertRaises(GateError):
            await self.observer.snapshot(self.agents)
        self.rest.agent_api_identity.get_agent_me.assert_not_awaited()

    async def test_execution_context_subclass_is_not_default_sdk_context(self):
        class CustomExecution(ExecutionContext):
            pass
        custom = CustomExecution(ROOM, self.agents[1].runtime.link, AsyncMock(), agent_id=self.ids[1])
        custom._process_loop_task = self.fixture.task()
        custom.state = ExecutionState.IDLE
        self.agents[1].runtime.runtime.executions[ROOM] = custom
        with self.assertRaisesRegex(GateError, 'custom'):
            await self.observer.snapshot(self.agents)
        self.rest.agent_api_identity.get_agent_me.assert_not_awaited()

    async def test_duplicate_agent_and_dead_control_fail_closed(self):
        with self.assertRaises(GateError):
            await self.observer.snapshot(self.agents[:-1] + [self.agents[0]])

    async def test_rest_error_retains_original_deadline_and_redacts_exception(self):
        self.remove()
        self.rest.agent_api_participants.list_agent_chat_participants.side_effect = RuntimeError('private-value-never-copy')
        with self.assertRaisesRegex(GateError, 'roster read failed'):
            await self.observer.snapshot(self.agents)
        state = self.retained()
        self.assertEqual(state['episodes'][0]['deadline_epoch'], self.now + 60)
        self.assertNotIn('private-value-never-copy', self.observer.path.read_text())
        self.assertEqual(self.ledger.path.read_bytes(), self.original_budget)
        with self.assertRaises(GateError):
            await self.observer_new().snapshot(self.agents)

    async def test_rest_latency_cannot_extend_first_deadline(self):
        self.remove()
        async def slow(**kwargs):
            saved = self.retained()['episodes'][0]
            self.assertEqual(saved['deadline_epoch'], self.now + 60)
            self.now += 61
            return SimpleNamespace(data=list(self.rows))
        self.rest.agent_api_participants.list_agent_chat_participants.side_effect = slow
        with self.assertRaisesRegex(GateError, 'deadline expired'):
            await self.observer.snapshot(self.agents)

    async def test_restart_preserves_first_deadline_then_expires_without_budget_reset(self):
        self.remove()
        await self.observer.snapshot(self.agents)
        first = self.retained()['episodes'][0]['deadline_epoch']
        self.now += 25
        restarted = self.observer_new()
        self.assertEqual((await restarted.snapshot(self.agents))['membership_gap']['deadline_epoch'], first)
        self.now = first
        with self.assertRaisesRegex(GateError, 'deadline expired'):
            await self.observer_new().snapshot(self.agents)
        self.assertEqual(self.ledger.path.read_bytes(), self.original_budget)

    async def test_repeated_cycles_consume_persisted_transition_cap(self):
        for _ in range(2):
            self.remove(); await self.observer.snapshot(self.agents)
            self.now += 1; self.readd_member(); self.restore_context()
            await self.observer.snapshot(self.agents)
        self.observer = self.observer_new()
        self.remove()
        with self.assertRaisesRegex(GateError, 'transition cap'):
            await self.observer.snapshot(self.agents)
        self.assertEqual(len(self.retained()['episodes']), 2)

    async def test_different_identity_after_await_is_not_ignored(self):
        self.remove()
        async def changed(**kwargs):
            self.agents[2].runtime.runtime.executions.pop(ROOM)
            return SimpleNamespace(data=list(self.rows))
        self.rest.agent_api_participants.list_agent_chat_participants.side_effect = changed
        with self.assertRaises(GateError):
            await self.observer.snapshot(self.agents)

    async def test_duplicate_or_partial_roster_is_blocked(self):
        self.remove()
        self.rows.append(self.rows[0])
        with self.assertRaisesRegex(GateError, 'duplicate'):
            await self.observer.snapshot(self.agents)

    async def test_paginated_roster_is_not_full_absence_evidence(self):
        self.remove()
        self.rest.agent_api_participants.list_agent_chat_participants.side_effect = None
        self.rest.agent_api_participants.list_agent_chat_participants.return_value = SimpleNamespace(
            data=list(self.rows), metadata={'total_pages': 2})
        with self.assertRaisesRegex(GateError, 'pagination'):
            await self.observer.snapshot(self.agents)

    async def test_changed_config_binding_cannot_reopen_state(self):
        config = json.loads(json.dumps(self.config))
        config['budgets']['ack_timeout_seconds'] = 120
        with self.assertRaisesRegex(GateError, 'binding changed'):
            self.observer_new(config)

    async def test_verified_gap_defers_async_notice_without_claim_or_send(self):
        self.remove()
        watchdog = WorkflowWatchdog(self.root/'workflow.json', ROOM, self.ids[0], self.ids, 60, clock=lambda:self.now)
        watchdog.begin_turn(self.ids[1], 'failed-turn', self.now+900)
        watchdog.end_turn('failed-turn', 'failed', 'provider_failure')
        result = await send_due_notice(watchdog, self.ledger, {}, self.config['seats'],
            execution_activity=lambda: self.observer.snapshot(self.agents))
        self.assertEqual(result, 'deferred')
        self.assertEqual(watchdog.health()['notice_attempts'], 0)
        self.rest.agent_api_messages.create_agent_chat_message.assert_not_awaited()
        self.assertEqual(self.ledger.path.read_bytes(), self.original_budget)


if __name__ == '__main__':
    unittest.main()
