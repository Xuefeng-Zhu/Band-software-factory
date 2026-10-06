"""Real SDK dispatch for human task receipts versus canonical peer receipts.

Only the BAND REST boundary is fake. No clients, sockets, model or live room.
"""
import json
from pathlib import Path
import socket
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from band.client.rest import MessageSentResponse
from band.runtime.tools.agent import AgentTools

from factorykit.runtime import BudgetLedger
from factorykit.workflow import WorkflowWatchdog
from factorykit.workflow_runtime import WorkflowTools, protocol_header

ROOM='00000000-0000-4000-8000-000000000001'
PM='00000000-0000-4000-8000-000000000002'
PEER='00000000-0000-4000-8000-000000000003'
HUMAN='00000000-0000-4000-8000-000000000004'
EVENT='00000000-0000-4000-8000-000000000005'
DIGEST='a'*64
ROSTER=[dict(id='pm',agent_id=PM,handle='owner/pm'),dict(id='backend',agent_id=PEER,handle='owner/backend')]


class HumanTaskReceiptTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.ledger=BudgetLedger(dict(balance_only=True,spend_cap_usd=25,max_active_seats=1,
            overall_timeout_seconds=1,stage_timeout_seconds=1,max_turns_per_seat=1,
            max_total_tokens=1,turn_timeout_seconds=1,max_repairs=1),self.root/'budget.json',ROOM)
        self.watchdog=WorkflowWatchdog(self.root/'workflow.json',ROOM,PM,[PM,PEER],60,balance_only=True)
        participants=[dict(id=s['agent_id'],name=s['id'],handle=s['handle'],type='Agent') for s in ROSTER]
        participants.append(dict(id=HUMAN,name='Human owner',handle='owner',type='User'))
        self.post=AsyncMock(side_effect=self.fake_post)
        rest=SimpleNamespace(agent_api_messages=SimpleNamespace(create_agent_chat_message=self.post))
        self.base=AgentTools(ROOM,rest,participants,agent_id=PM)
        self.tools=WorkflowTools(self.base,self.ledger,'pm',self.root/'audit.jsonl',ROSTER,
            watchdog=self.watchdog,actor_id=PM,turn_id='pm-turn',deadline_at=None)
        self.watchdog.begin_turn(PM,'pm-turn',None)
        no_network=patch.object(socket.socket,'connect',side_effect=AssertionError('Offline receipt test'))
        no_network.start();self.addCleanup(no_network.stop)

    async def fake_post(self,**kwargs):
        self.assertEqual(kwargs['chat_id'],ROOM)
        mentions=kwargs['message'].mentions
        return SimpleNamespace(data=MessageSentResponse(id=EVENT,success=True,
            recipients=[dict(id=m.id,handle=m.handle) for m in mentions]))

    async def test_plain_exact_human_receipt_uses_sdk_schema_and_posts_untracked(self):
        schemas=self.tools.get_openai_tool_schemas()
        self.assertTrue(any(row.get('function',row).get('name')=='band_send_message' for row in schemas))
        content=f'TASK-RECEIPT id=NORMAL-DISPATCH; received=4/4; SHA-256 {DIGEST}'
        self.assertFalse(protocol_header(content))
        original=(self.ledger.path.read_bytes(),self.watchdog.path.read_bytes())
        outcome=await self.tools.execute_tool_call_structured('band_send_message',
            {'content':content,'mentions':['@owner']})
        self.assertTrue(outcome.ok)
        self.post.assert_awaited_once()
        message=self.post.await_args.kwargs['message']
        self.assertEqual(message.content,content)
        self.assertEqual([(m.id,m.handle) for m in message.mentions],[(HUMAN,'owner')])
        self.assertNotIn(HUMAN,[s['agent_id'] for s in ROSTER])
        self.assertEqual((self.ledger.path.read_bytes(),self.watchdog.path.read_bytes()),original)
        self.assertFalse(self.ledger.stop.is_set())

    async def test_canonical_handoff_ack_to_human_is_rejected_before_post(self):
        content=f'HANDOFF-ACK delivery NORMAL-DISPATCH; SHA-256 {DIGEST}; sender @[[{HUMAN}]]'
        self.assertTrue(protocol_header(content))
        original=(self.ledger.path.read_bytes(),self.watchdog.path.read_bytes())
        outcome=await self.tools.execute_tool_call_structured('band_send_message',
            {'content':content,'mentions':[HUMAN]})
        self.assertFalse(outcome.ok)
        self.post.assert_not_awaited()
        self.assertEqual((self.ledger.path.read_bytes(),self.watchdog.path.read_bytes()),original)

    async def test_canonical_peer_ack_still_updates_only_confirmed_delivery_receipt(self):
        source_event='00000000-0000-4000-8000-000000000006'
        self.watchdog.begin_turn(PEER,'peer-turn',None)
        original=f'WORK-1 delivery PEER-1 part 1/1; SHA-256 {DIGEST}; recipient @[[{PM}]]\nOriginal requirements\nEND OF HANDOFF'
        result=self.watchdog.observe_outbound(source_event,PEER,[PM],original,'peer-turn')
        self.assertTrue(result['complete']);self.watchdog.end_turn('peer-turn','completed')
        content=f'HANDOFF-ACK delivery PEER-1; SHA-256 {DIGEST}; sender @[[{PEER}]]'
        outcome=await self.tools.execute_tool_call_structured('band_send_message',
            {'content':content,'mentions':['@owner/backend']})
        self.assertTrue(outcome.ok);self.post.assert_awaited_once()
        state=json.loads(self.watchdog.path.read_text())
        self.assertTrue(state['deliveries']['PEER-1']['acknowledged'])
        self.assertEqual(state['deliveries']['PEER-1']['acks'],{PM:EVENT})
        self.assertEqual(self.post.await_args.kwargs['request_options']['max_retries'],0)
        self.assertNotIn('accepted',self.watchdog.path.read_text())
        self.assertFalse(self.ledger.stop.is_set())


if __name__=='__main__':unittest.main()
