import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock

from factorykit.common import FactoryError
from factorykit.continuation_guard import BoundCodexClient, EventAdmissionJournal

ROOM='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
THREAD='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'
OTHER='cccccccc-cccc-4ccc-8ccc-cccccccccccc'
E1='11111111-1111-4111-8111-111111111111'
E2='22222222-2222-4222-8222-222222222222'
E3='33333333-3333-4333-8333-333333333333'
E4='44444444-4444-4444-8444-444444444444'

class ThreadGuardTests(unittest.IsolatedAsyncioTestCase):
    async def test_resume_then_turn(self):
        client=AsyncMock(); client.request.return_value={'thread':{'id':THREAD}}
        guard=BoundCodexClient(client,THREAD,lambda _:None)
        await guard.request('thread/resume',{'threadId':THREAD})
        await guard.request('turn/start',{'threadId':THREAD})
        self.assertEqual(client.request.await_count,2)

    async def test_refuse_start_and_unresumed_turn_before_transport(self):
        client=AsyncMock(); guard=BoundCodexClient(client,THREAD,lambda _:None)
        for method in ['thread/start','turn/start','turn/steer']:
            with self.assertRaises(FactoryError): await guard.request(method,{'threadId':THREAD})
        client.request.assert_not_awaited()

    async def test_resume_error_cannot_fall_back(self):
        client=AsyncMock(); client.request.side_effect=RuntimeError('provider error')
        guard=BoundCodexClient(client,THREAD,lambda _:None)
        with self.assertRaises(FactoryError): await guard.request('thread/resume',{'threadId':THREAD})
        with self.assertRaises(FactoryError): await guard.request('thread/start',{})
        self.assertEqual(client.request.await_count,1)

    async def test_mismatched_response_blocks_turn(self):
        client=AsyncMock(); client.request.return_value={'thread':{'id':OTHER}}
        guard=BoundCodexClient(client,THREAD,lambda _:None)
        with self.assertRaises(FactoryError): await guard.request('thread/resume',{'threadId':THREAD})
        with self.assertRaises(FactoryError): await guard.request('turn/start',{'threadId':THREAD})
        self.assertEqual(client.request.await_count,1)

    async def test_second_failed_resume_invalidates_prior_readiness(self):
        client=AsyncMock();client.request.return_value={'thread':{'id':THREAD}}
        guard=BoundCodexClient(client,THREAD,lambda _:None)
        await guard.request('thread/resume',{'threadId':THREAD})
        client.request.side_effect=RuntimeError('resume failure')
        with self.assertRaises(FactoryError):await guard.request('thread/resume',{'threadId':THREAD})
        with self.assertRaises(FactoryError):await guard.request('turn/start',{'threadId':THREAD})
        self.assertEqual(client.request.await_count,2)

    async def test_second_mismatched_resume_invalidates_prior_readiness(self):
        client=AsyncMock();client.request.return_value={'thread':{'id':THREAD}}
        guard=BoundCodexClient(client,THREAD,lambda _:None)
        await guard.request('thread/resume',{'threadId':THREAD})
        client.request.return_value={'thread':{'id':OTHER}}
        with self.assertRaises(FactoryError):await guard.request('thread/resume',{'threadId':THREAD})
        with self.assertRaises(FactoryError):await guard.request('turn/start',{'threadId':THREAD})
        self.assertEqual(client.request.await_count,2)

    async def test_unused_seat_records_first_thread_before_turn(self):
        client=AsyncMock(); client.request.return_value={'thread':{'id':THREAD}}; recorded=[]
        guard=BoundCodexClient(client,None,recorded.append)
        await guard.request('thread/start',{})
        self.assertEqual(recorded,[THREAD])
        await guard.request('turn/start',{'threadId':THREAD})
        with self.assertRaises(FactoryError): await guard.request('thread/start',{})

    async def test_failed_identity_persistence_prevents_model_work(self):
        client=AsyncMock();client.request.return_value={'thread':{'id':THREAD}}
        def broken(_): raise OSError('disk full')
        guard=BoundCodexClient(client,None,broken)
        with self.assertRaises(OSError):await guard.request('thread/start',{})
        with self.assertRaises(FactoryError):await guard.request('turn/start',{'threadId':THREAD})
        self.assertEqual(client.request.await_count,1)

class EventGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'events.json'
        self.args=dict(room_id=ROOM,cutoff_utc='2026-10-05T02:40:00Z',completed=[('pm',E1)],blocked=[('pm',E2)],pending=[('pm',E3)],seats=['pm'],save_json=lambda p,d:p.write_text(json.dumps(d)))
        self.j=EventAdmissionJournal(self.path,**self.args)
    def claim(self,event,at='2026-10-05T02:41:00Z'):
        return self.j.claim('pm',event,room_id=ROOM,created_at=at)
    def test_completed_never_replayed(self):self.assertFalse(self.claim(E1))
    def test_failed_never_replayed(self):
        with self.assertRaises(FactoryError):self.claim(E2)
    def test_reconciled_pending_once_and_persisted(self):
        self.assertTrue(self.claim(E3,'2026-10-05T02:30:00Z'))
        self.j.finish('pm',E3,completed=True)
        self.j=EventAdmissionJournal(self.path,**self.args)
        self.assertFalse(self.claim(E3))
    def test_unknown_old_event_refused(self):
        with self.assertRaises(FactoryError):self.claim(E4,'2026-10-05T02:30:00Z')
    def test_crashed_claim_refuses_replay_after_reopen(self):
        self.assertTrue(self.claim(E4));self.j=EventAdmissionJournal(self.path,**self.args)
        with self.assertRaises(FactoryError):self.claim(E4)
    def test_failed_execution_refuses_replay(self):
        self.claim(E4);self.j.finish('pm',E4,completed=False)
        with self.assertRaises(FactoryError):self.claim(E4)
    def test_room_mismatch_refused(self):
        with self.assertRaises(FactoryError):self.j.claim('pm',E4,room_id=OTHER,created_at='2026-10-05T02:41:00Z')
    def test_baseline_cannot_change_on_reopen(self):
        changed=dict(self.args,completed=[])
        with self.assertRaises(FactoryError):EventAdmissionJournal(self.path,**changed)
    def test_historical_completion_cannot_be_rewritten(self):
        d=json.loads(self.path.read_text());d['events']['pm:'+E1]='pending';self.path.write_text(json.dumps(d))
        with self.assertRaises(FactoryError):EventAdmissionJournal(self.path,**self.args)

    def test_restored_nonbaseline_pending_refused(self):
        d=json.loads(self.path.read_text());d['events']['pm:'+E4]='pending';self.path.write_text(json.dumps(d))
        with self.assertRaises(FactoryError):EventAdmissionJournal(self.path,**self.args)
    def test_restored_wrong_seat_or_uuid_refused(self):
        original=self.path.read_text()
        for key in ['other:'+E4,'pm:broken']:
            d=json.loads(original);d['events'][key]='claimed';self.path.write_text(json.dumps(d))
            with self.assertRaises((FactoryError,ValueError)):EventAdmissionJournal(self.path,**self.args)
    def test_unknown_event_invalid_times_and_cutoff_equality_refused(self):
        for when in [None,'bad','2026-10-05T02:41:00','2026-10-05T02:40:00Z']:
            with self.assertRaises((FactoryError,ValueError)):self.claim(E4,when)
    def test_claim_write_failure_does_not_allow_execution_or_retry(self):
        def broken(p,d):raise OSError('disk full')
        self.j.save_json=broken
        with self.assertRaises(OSError):self.claim(E4)
        with self.assertRaises(FactoryError):self.claim(E4)

class ActualSdkThreadTests(unittest.IsolatedAsyncioTestCase):
    def adapter(self, client):
        from types import SimpleNamespace as NS
        return NS(_room_threads={},_client=client,_raw_history_by_room={},
            config=NS(personality=None,inject_history_on_resume_failure=False,approval_policy='never'),
            features=NS(emit=[]),_selected_model='test-model',
            _build_dynamic_tools=lambda tools:[],_room_client=lambda room:NS(workspace='/tmp'),
            _apply_thread_sandbox=lambda params,**kwargs:None)
    async def test_pinned_sdk_resumes_exact_existing_thread(self):
        from band.adapters.codex import CodexAdapter
        from types import SimpleNamespace as NS
        transport=AsyncMock();transport.request.return_value={'thread':{'id':THREAD}}
        adapter=self.adapter(BoundCodexClient(transport,THREAD,lambda _:None))
        result=await CodexAdapter._ensure_thread(adapter,room_id=ROOM,
            history=NS(has_thread=lambda:True,thread_id=THREAD),tools=None,is_session_bootstrap=True)
        self.assertEqual(result,THREAD)
        self.assertEqual(adapter._room_threads,{ROOM:THREAD})
    async def test_pinned_sdk_rpc_resume_error_cannot_create_replacement(self):
        from band.adapters.codex import CodexAdapter
        from band.integrations.codex.rpc_base import CodexJsonRpcError
        from types import SimpleNamespace as NS
        transport=AsyncMock();transport.request.side_effect=CodexJsonRpcError(code=-1,message='synthetic missing thread')
        adapter=self.adapter(BoundCodexClient(transport,THREAD,lambda _:None))
        with self.assertRaises(FactoryError):
            await CodexAdapter._ensure_thread(adapter,room_id=ROOM,
                history=NS(has_thread=lambda:True,thread_id=THREAD),tools=None,is_session_bootstrap=True)
        self.assertEqual(transport.request.await_count,1)
        self.assertEqual(adapter._room_threads,{})
    async def test_pinned_sdk_missing_history_cannot_start_existing_seat(self):
        from band.adapters.codex import CodexAdapter
        from types import SimpleNamespace as NS
        transport=AsyncMock();adapter=self.adapter(BoundCodexClient(transport,THREAD,lambda _:None))
        with self.assertRaises(FactoryError):
            await CodexAdapter._ensure_thread(adapter,room_id=ROOM,
                history=NS(has_thread=lambda:False,thread_id=None),tools=None,is_session_bootstrap=True)
        transport.request.assert_not_awaited()

class RequestedModelTests(unittest.IsolatedAsyncioTestCase):
    async def test_resumed_sdk_turn_sends_requested_model_and_preserved_effort(self):
        from band.adapters.codex import CodexAdapter
        from types import SimpleNamespace as NS
        for effort in ('medium', 'high'):
            transport = AsyncMock()
            transport.request.return_value = {'thread': {'id': THREAD}}
            guard = BoundCodexClient(transport, THREAD, lambda _: None)
            adapter = ActualSdkThreadTests().adapter(guard)
            adapter.config.model = 'gpt-6.1-sol'
            adapter.config.reasoning_effort = effort
            adapter.config.reasoning_summary = 'none'
            state = NS(model_override=None, workspace='/tmp', reasoning_effort=None, reasoning_summary=None)
            adapter._require_active_client_state = lambda: state
            adapter._apply_turn_sandbox = lambda params, **kwargs: None
            adapter._selected_model = await CodexAdapter._select_model(adapter)
            resumed = await CodexAdapter._ensure_thread(adapter, room_id=ROOM,
                history=NS(has_thread=lambda: True, thread_id=THREAD), tools=None, is_session_bootstrap=True)
            params = {'threadId': resumed, 'input': []}
            CodexAdapter._apply_turn_overrides(adapter, params, room_id=ROOM)
            await CodexAdapter._start_turn(adapter, params)
            self.assertEqual(transport.request.await_args.args[1]['model'], 'gpt-6.1-sol')
            self.assertEqual(transport.request.await_args.args[1]['effort'], effort)
            self.assertEqual(transport.request.await_args.args[1]['threadId'], THREAD)

class ContinuationOwnershipTests(unittest.TestCase):
    def test_only_exact_serve_module_and_token_are_owned(self):
        from factorykit.runtime import is_owned
        from unittest.mock import Mock,patch
        for module,valid in [('factorykit.runtime',True),('factorykit.continuation_runner',True),('unrelated',False)]:
            command=['python','-m',module,'_serve','--owner-token','owner']
            p=Mock();p.create_time.return_value=12.0;p.cmdline.return_value=command;p.is_running.return_value=True;p.status.return_value='running'
            with patch('factorykit.runtime.psutil.Process',return_value=p):
                self.assertEqual(is_owned({'pid':123,'created':12.0,'cmdline':command},'owner'),valid)
                self.assertFalse(is_owned({'pid':123,'created':12.0,'cmdline':command},'different'))

if __name__=='__main__':unittest.main()
