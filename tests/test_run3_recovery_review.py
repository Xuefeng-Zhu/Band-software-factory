"""Independent offline review of the Run 3 SDK-ingress recovery seam.

Use the installed SDK's real queue ingress, without starting an Agent or model.
The synthetic delivery mirrors the recorded complete twelve-part/no-receipt case.
"""
import asyncio
import json
from pathlib import Path
import socket
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from band.client.rest import MessageSentResponse
from band.client.streaming import MessageCreatedPayload
from band.platform.event import MessageEvent
from band.runtime.execution import ExecutionContext, ExecutionState
from band.runtime.tools.agent import AgentTools

from factorykit.runtime import BudgetLedger
from factorykit.workflow import WorkflowWatchdog
from factorykit.workflow_runtime import sdk_execution_activity, send_due_notice


ROOM = '10000000-0000-4000-8000-000000000001'
PM = '10000000-0000-4000-8000-000000000002'
BACKEND = '10000000-0000-4000-8000-000000000003'
ROSTER = [dict(id='pm', agent_id=PM, handle='review/pm'),
          dict(id='backend', agent_id=BACKEND, handle='review/backend')]
DIGEST = 'b' * 64


def eid(n):
    return f'10000000-0000-4000-8000-{n:012d}'


class Run3RecoveryReviewTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.now = time.time()
        self.watchdog = WorkflowWatchdog(self.root / 'workflow.json', ROOM, PM,
            [PM, BACKEND], 120, clock=lambda: self.now)
        self.ledger = BudgetLedger(dict(max_active_seats=1,
            overall_timeout_seconds=10000, stage_timeout_seconds=10000,
            max_turns_per_seat=300, max_total_tokens=100000000,
            turn_timeout_seconds=600, max_repairs=2), self.root / 'budget.json', ROOM)
        self.ledger.data.update(tokens=84080166, turns={'pm':178, 'backend':37})
        self.ledger.save()
        self.post = AsyncMock(return_value=SimpleNamespace(data=MessageSentResponse(
            id=eid(900), success=True,
            recipients=[dict(id=BACKEND, handle='review/backend')])))
        self.tools = AgentTools(ROOM, None, [])
        self.tools.rest = SimpleNamespace(agent_api_messages=SimpleNamespace(
            create_agent_chat_message=self.post))
        self.callback = AsyncMock()
        self.contexts = {}
        self.agents = []
        # Only the task liveness marker is synthetic; ingress and queue are the
        # installed SDK implementation. No SDK runtime/start method is invoked.
        self.parked = asyncio.create_task(asyncio.Event().wait())
        self.addAsyncCleanup(self.stop_parked)
        for agent_id in [PM, BACKEND]:
            context = ExecutionContext(ROOM, SimpleNamespace(), self.callback,
                                       agent_id=agent_id)
            context._process_loop_task = self.parked
            context.state = ExecutionState.IDLE
            self.contexts[agent_id] = context
            self.agents.append(SimpleNamespace(runtime=SimpleNamespace(
                agent_id=agent_id, runtime=SimpleNamespace(active_sessions={ROOM: context}))))
        blocker = patch.object(socket.socket, 'connect',
            side_effect=AssertionError('Independent review must remain offline'))
        blocker.start()
        self.addCleanup(blocker.stop)
        self.watchdog.begin_turn(PM, 'pm-original-completed', self.now + 600)
        for n in range(1, 13):
            text = (f'WORK delivery COMPLETE-TWELVE part {n}/12; SHA-256 {DIGEST}; '
                    f'recipient @[[{BACKEND}]]\nPayload {n}.'
                    + ('\nEND OF HANDOFF' if n == 12 else ''))
            self.watchdog.observe_outbound(eid(n), PM, [BACKEND], text, 'pm-original-completed')
        self.watchdog.end_turn('pm-original-completed', 'completed')
        self.now += 121

    async def stop_parked(self):
        self.parked.cancel()
        try:
            await self.parked
        except asyncio.CancelledError:
            pass

    def activity(self):
        return sdk_execution_activity(self.agents, ROOM, [PM, BACKEND])

    async def send(self):
        return await send_due_notice(self.watchdog, self.ledger, {PM:self.tools},
                                     ROSTER, execution_activity=self.activity)

    async def test_actual_sdk_ingress_defers_complete_pm_delivery_until_queue_and_processing_drain(self):
        before_budget = self.ledger.path.read_bytes()
        backend = self.contexts[BACKEND]
        for n in range(1, 13):
            payload = MessageCreatedPayload(id=eid(n), content=f'Original part {n}',
                message_type='text', sender_id=PM, sender_type='agent',
                inserted_at='2026-10-04T08:44:47Z', updated_at='2026-10-04T08:44:47Z')
            await backend.on_event(MessageEvent(room_id=ROOM, payload=payload))
        self.callback.assert_not_awaited()
        self.assertEqual(backend.queue.qsize(), 12)
        self.assertTrue(self.activity()['busy'])
        self.assertEqual(await self.send(), 'deferred')
        self.assertEqual(self.watchdog.health()['notice_attempts'], 0)
        self.post.assert_not_awaited()
        while not backend.queue.empty():
            backend.queue.get_nowait()
        # The SDK retains PROCESSING through its post-callback mark_processed;
        # adapter completion does not mean that this serial ingress has drained.
        backend.state = ExecutionState.PROCESSING
        self.assertTrue(self.activity()['busy'])
        self.assertEqual(await self.send(), 'deferred')
        self.post.assert_not_awaited()
        backend.state = ExecutionState.IDLE
        self.assertFalse(self.activity()['busy'])
        self.assertEqual(await self.send(), 'sent')
        request = self.post.await_args.kwargs
        self.assertEqual(request['chat_id'], ROOM)
        self.assertEqual([m.id for m in request['message'].mentions], [BACKEND])
        self.assertEqual(request['request_options']['max_retries'], 0)
        self.assertNotIn(f'@[[{PM}]] WORKFLOW NOTICE', request['message'].content)
        self.assertIn('COMPLETE-TWELVE', request['message'].content)
        state = json.loads(self.watchdog.path.read_text())
        self.assertTrue(state['deliveries']['COMPLETE-TWELVE']['complete'])
        self.assertFalse(state['deliveries']['COMPLETE-TWELVE']['acknowledged'])
        self.assertEqual(state['turns']['pm-original-completed']['status'], 'completed')
        self.assertEqual(self.ledger.path.read_bytes(), before_budget)
        self.assertEqual(self.post.await_count, 1)

    async def test_drained_ingress_does_not_authorize_expired_cumulative_budget(self):
        self.ledger.limits['stage_timeout_seconds'] = 20000
        self.ledger.data['started_epoch'] = time.time() - 10001
        self.assertEqual(self.ledger.reason(), 'overall time budget exhausted')
        self.ledger.save()
        before_budget = self.ledger.path.read_bytes()
        self.assertFalse(self.activity()['busy'])
        self.assertEqual(await self.send(), 'deferred')
        self.post.assert_not_awaited()
        self.assertEqual(self.watchdog.health()['notice_attempts'], 0)
        self.assertEqual(self.ledger.path.read_bytes(), before_budget)


if __name__ == '__main__':
    unittest.main()
