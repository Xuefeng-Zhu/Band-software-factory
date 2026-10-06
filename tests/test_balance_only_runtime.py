"""Dollar-only runtime mode; no server/provider/transport is started."""
import asyncio
from contextlib import ExitStack, nullcontext
import inspect
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from factorykit import harnesses, runtime
from tests import test_opencode_tool_policy as tools_fixture
from tests import test_runtime_harness_integration as integration


class BalanceLedgerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/'ledger.json'
        self.limits = dict(balance_only=True, max_active_seats=1, overall_timeout_seconds=1,
            stage_timeout_seconds=1, max_turns_per_seat=1, max_total_tokens=1, max_repairs=1)
        self.ledger = runtime.BudgetLedger(self.limits, self.path, 'room')

    async def test_retains_old_epochs_counts_and_accepts_more_accounted_work(self):
        self.ledger.data.update(started_epoch=1, tokens=2000001, turns={'pm': 100})
        self.ledger.save()
        self.assertIsNone(self.ledger.reason('pm'))
        self.assertTrue(self.ledger.reserve('pm'))
        self.assertEqual(self.ledger.data['started_epoch'], 1)
        self.assertEqual(self.ledger.data['tokens'], 2000001)
        self.assertEqual(self.ledger.data['turns']['pm'], 101)
        reloaded = runtime.BudgetLedger(self.limits, self.path, 'room')
        self.assertEqual(reloaded.data['turns']['pm'], 101)
        self.assertIsNone(reloaded.reason('pm'))
        await self.ledger.semaphore.acquire()
        self.assertTrue(self.ledger.semaphore.locked())
        self.ledger.semaphore.release()

    async def test_actual_stop_reasons_and_original_room_stops_are_preserved(self):
        self.ledger.data['stopped_reason'] = 'dollar cap exhausted'
        self.assertEqual(self.ledger.reason(), 'dollar cap exhausted')
        self.assertFalse(self.ledger.reserve('pm'))
        self.ledger.data['stopped_reason'] = None
        self.ledger.allowed_rooms = ['old', 'room']
        self.ledger.data['room_stopped_reasons'] = {'old': runtime.STAGE_STOP}
        self.assertIsNone(self.ledger.reason())
        self.ledger.data['room_stopped_reasons']['room'] = runtime.STAGE_STOP
        self.assertEqual(self.ledger.reason(), runtime.STAGE_STOP)

    async def test_legacy_limits_still_apply_without_mode(self):
        self.ledger.limits['balance_only'] = False
        self.ledger.data['started_epoch'] = 1
        self.assertEqual(self.ledger.reason(), 'overall time budget exhausted')

    async def test_normal_membership_add_counts_without_artificial_attempt_cap(self):
        peer = {'id':'reviewer', 'agent_id':'peer', 'display_name':'Reviewer', 'handle':'owner/reviewer'}
        raw = SimpleNamespace(get_participants=AsyncMock(return_value=[]), add_participant=AsyncMock(return_value={'id':'peer'}))
        tools = runtime.AuditedTools(raw, self.ledger, 'pm', self.path.with_suffix('.jsonl'), [peer])
        self.ledger.data['membership_attempts'] = {'peer': 20}
        await tools.add_participant('peer')
        self.assertEqual(self.ledger.data['membership_attempts']['peer'], 21)
        raw.add_participant.assert_awaited_once_with('peer', role='member')
        tools.strict_membership_recovery = True
        with self.assertRaisesRegex(runtime.GateError, 'exhausted'): await tools.add_participant('peer')
        self.assertEqual(raw.add_participant.await_count, 1)

    async def test_effective_guidance_omits_inactive_limits_without_changing_config(self):
        cfg = {'budgets':dict(self.limits, approved=True, billing_mode='spend_cap', spend_cap_usd=25,
                             api_billing_allowed=True, infrastructure_provisioning_allowed=False)}
        original=json.dumps(cfg,sort_keys=True)
        value=runtime.effective_budget_metadata(cfg)
        self.assertEqual(value['spend_cap_usd'],25)
        self.assertEqual(value['max_active_seats'],1)
        self.assertTrue(value['api_billing_allowed'])
        self.assertNotIn('max_turns_per_seat',value)
        self.assertNotIn('overall_timeout_seconds',value)
        self.assertEqual(json.dumps(cfg,sort_keys=True),original)


class BalanceHarnessTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_maintained_opencode_wait_has_no_timer_and_preserves_cancel(self):
        adapter = tools_fixture.adapter()
        adapter.config = adapter.config.model_copy(update={"turn_timeout_s":None})
        future = asyncio.get_running_loop().create_future()
        turn = SimpleNamespace(turn_future=future)
        with patch('asyncio.wait_for', side_effect=AssertionError('No execution timeout in balance-only')):
            task=asyncio.create_task(adapter._await_turn(turn)); await asyncio.sleep(0)
            self.assertFalse(task.done()); future.set_result(None); await task
            future=asyncio.get_running_loop().create_future(); turn.turn_future=future
            task=asyncio.create_task(adapter._await_turn(turn)); await asyncio.sleep(0); task.cancel()
            with self.assertRaises(asyncio.CancelledError): await task
            self.assertFalse(future.cancelled()); future.cancel()

    async def test_legacy_opencode_wait_is_delegated_unchanged(self):
        from band.adapters import OpencodeAdapter
        adapter=tools_fixture.adapter(); turn=object()
        with patch.object(OpencodeAdapter, '_await_turn', AsyncMock()) as wait:
            await adapter._await_turn(turn)
            wait.assert_awaited_once_with(turn)

    async def test_actual_http_client_allows_unlimited_read_without_starting_it(self):
        adapter=tools_fixture.adapter(); adapter.config = adapter.config.model_copy(update={"turn_timeout_s":None})
        client=adapter._default_client_factory(adapter.config)
        self.assertIsNone(client._client.timeout.read)
        self.assertEqual(client._client.timeout.connect,30)
        await client._client.aclose()

    async def test_real_supervisor_uses_none_timers_and_still_accounts_once(self):
        f=integration.SupervisorHarnessTests(); f.setUp()
        self._cleanups.extend(f._cleanups); f._cleanups.clear()
        original=f.configuration
        def cfg(harness):
            value=original(harness); value['budgets']['balance_only']=True
            return value
        f.configuration=cfg
        original_config=runtime.adapter_config
        def config(*args,**kwargs):
            result=original_config(*args,**kwargs)
            self.assertIsNone(result.turn_timeout_s)
            return result
        from band import Agent
        create=Agent.create
        captured=[]
        # The integration fixture patches Agent.create itself; observe the actual
        # SessionConfig constructor instead, without changing transport behavior.
        from band.runtime.types import SessionConfig
        def session(**kwargs):
            captured.append(kwargs)
            self.assertIsNone(kwargs['max_cycle_seconds'])
            return SessionConfig(**kwargs)
        timeout=asyncio.timeout
        timers=[]
        def timer(delay):
            timers.append(delay)
            return timeout(delay)
        with patch.object(runtime, 'adapter_config', side_effect=config), \
             patch('band.runtime.types.SessionConfig', side_effect=session), \
             patch.object(runtime.asyncio,'timeout',side_effect=timer):
            await f.exercise('opencode')
        self.assertEqual(len(captured),1)
        self.assertIn(None,timers)

    async def test_advisory_normal_does_not_precheck_historical_strict_journal(self):
        config={'seats':[{}]*7,'runtime':{'harness':'opencode'},'paths':{'runs':str(Path(tempfile.gettempdir()).resolve())}}
        with patch('factorykit.membership_gap.retained_startup_check',side_effect=AssertionError('old journal untouched')), \
             patch('factorykit.startup_telemetry.startup_telemetry', return_value=nullcontext()), \
             patch.object(runtime,'_serve_with_harness',AsyncMock(return_value='offline')):
            self.assertEqual(await runtime.serve(config,'rehearsal','test'), 'offline')
        config['runtime']['strict_membership_recovery']=True
        with patch('factorykit.membership_gap.retained_startup_check',side_effect=runtime.GateError('retained')) as check:
            with self.assertRaisesRegex(runtime.GateError,'retained'): await runtime.serve(config,'rehearsal','test')
            check.assert_called_once()

    async def test_balance_supervisor_preserves_inactive_progress_journal_and_tools(self):
        f=integration.SupervisorHarnessTests(); f.setUp()
        self._cleanups.extend(f._cleanups); f._cleanups.clear()
        original=f.configuration
        progress_path=f.root/'opencode'/'runtime'/f'progress-{integration.ROOM}.json'
        progress_path.parent.mkdir(parents=True)
        prior=b'{"historical": "exhausted progress allowance"}\n'
        progress_path.write_bytes(prior)
        def cfg(harness):
            value=original(harness); value['budgets']['balance_only']=True
            value['progress']={'historical_unusable_policy':True}
            return value
        f.configuration=cfg
        from factorykit.workflow_runtime import WorkflowTools
        original_accounted=runtime.accounted_adapter_turn
        async def accounted(callback, inp, tools):
            self.assertIs(type(tools), WorkflowTools)
            schemas=tools.get_openai_tool_schemas()
            self.assertFalse(any(item['function']['name'].startswith('factory_progress')
                                 or item['function']['name']=='factory_verify_checkpoint' for item in schemas))
            return await original_accounted(callback, inp, tools)
        with patch('factorykit.progress.progress_policy',side_effect=AssertionError('Inactive policy read')), \
             patch('factorykit.progress.ProgressGuard.__init__',side_effect=AssertionError('Inactive guard created')), \
             patch('factorykit.progress_tools.ProgressWorkflowTools.__init__',side_effect=AssertionError('Inactive tools created')), \
             patch.object(runtime,'accounted_adapter_turn',side_effect=accounted):
            await f.exercise('opencode')
        self.assertEqual(progress_path.read_bytes(),prior)

    async def test_launcher_skips_only_inactive_progress_preflight(self):
        config={'budgets':{'balance_only':True},'seats':[{}], 'runtime':{}}
        args=SimpleNamespace(loaded_config=config,mode='rehearsal')
        with patch.object(runtime,'require_ready',side_effect=runtime.GateError('actual readiness boundary')) as ready:
            with self.assertRaisesRegex(runtime.GateError,'actual readiness boundary'):
                runtime.start_supervisor(args)
            ready.assert_called_once_with(config,'rehearsal')
        config['budgets']['balance_only']=False
        with patch.object(runtime,'require_ready') as ready:
            with self.assertRaisesRegex(runtime.GateError,'finite runnable-checkpoint'):
                runtime.start_supervisor(args)
            ready.assert_not_called()


class BalanceGuardConfigurationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from tests import test_opencode_verification as fixture
        self.f=fixture.OpenCodeGuardTests(); await self.f.asyncSetUp()
        self._cleanups.extend(self.f._cleanups); self.f._cleanups.clear()
        self.config=self.f.config
        self.config['budgets']['balance_only']=True
        self.guard=self.config['runtime']['featherless_budget_guard']
        self.guard.update(balance_only=True,time_renewal={'path':'/offline/amendment','sha256':'0'*64})

    async def test_amendment_flags_required_and_dollar_cap_unchanged(self):
        with patch('factorykit.allowance_renewal.validate_renewal_config',return_value={}) as approval:
            self.assertEqual(harnesses.featherless_guard_errors(self.config),[])
            approval.assert_called_once_with(self.config)
            self.guard['approved_credit_nano_usd']+=1
            self.assertTrue(harnesses.featherless_guard_errors(self.config))
            self.guard['approved_credit_nano_usd']-=1
            self.guard['balance_only']=False
            self.assertTrue(harnesses.featherless_guard_errors(self.config))
            self.guard['balance_only']=True
            self.guard.pop('time_renewal')
            self.assertTrue(harnesses.featherless_guard_errors(self.config))

    async def test_unapproved_amendment_missing_guard_and_other_harness_are_rejected(self):
        with patch('factorykit.allowance_renewal.validate_renewal_config',side_effect=ValueError('changed')):
            self.assertTrue(harnesses.featherless_guard_errors(self.config))
        self.config['runtime'].pop('featherless_budget_guard')
        self.assertTrue(harnesses.featherless_guard_errors(self.config))
        self.config['runtime']['harness']='codex'
        self.assertTrue(any('guarded OpenCode' in error for error in harnesses.validate_selection(self.config)))

    async def test_forwarded_guard_keeps_key_private_and_receives_mode(self):
        from contextlib import asynccontextmanager
        captured={}
        @asynccontextmanager
        async def fake_guard(**kwargs):
            captured.update(kwargs)
            yield self.f.guard
        with patch('factorykit.featherless_guard.FeatherlessGuard',fake_guard), \
             patch.object(harnesses,'_featherless_metadata',return_value=self.f.evidence['models']), \
             patch.dict('os.environ',{self.config['runtime']['opencode_provider']['api_key_env']:'offline-secret'}):
            async with harnesses._featherless_runtime(self.config): pass
        self.assertIs(captured['balance_only'],True)
        self.assertEqual(captured['approved_credit_nano_usd'],25_000_000_000)
        self.assertEqual(captured['time_renewal'],self.guard['time_renewal'])


if __name__=='__main__': unittest.main()
