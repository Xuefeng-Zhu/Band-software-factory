"""Focused subsequent-room continuations; original $25 approval is reused."""
import copy
import hashlib
import json
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch
import yaml

from tests.test_balance_only import BalanceFixture, BalanceHelperTests
from factorykit.allowance_renewal import validate_renewal_config
from factorykit.allowance_scope import reconcile_balance_scope
from factorykit.common import FactoryError
from factorykit.featherless import MODEL_IDS
from factorykit.featherless_guard import _charge, _Ledger, GuardError

class ScopeChainTests(BalanceFixture):
    def current(self):
        factory, guard = self.migrate()
        model = guard['policy']['models'][MODEL_IDS[0]]
        guard['requests']['9'.zfill(32)] = {'model':MODEL_IDS[0], 'status':'settled',
            'output_ceiling':model['output_ceiling'], 'reserved_tokens':model['input_ceiling']+model['output_ceiling'],
            'reserved_nano_usd':_charge(model,model['input_ceiling'],model['output_ceiling']),
            'prompt_tokens':500,'completion_tokens':277,'charged_nano_usd':_charge(model,500,277)}
        factory['tokens'] += 777;factory['turns']['pm'] += 1
        factory['token_threads'][self.newroom+':pm:after-balance-approval'] = 777
        factory['room_started_epochs'][self.newroom] = self.now-1
        factory['room_turns'][self.newroom] = {'pm':1}
        factory['room_stopped_reasons'][self.newroom] = 'unconfirmed old room task write'
        return factory,guard

    def child(self,factory,guard):
        authority=copy.deepcopy(self.authority)
        room=str(uuid4())
        authority.update(prior_time_renewal=self.reference,
            before_configuration=self.f.save(self.root/'next-before/config.json',self.config),
            before_factory_budget=self.f.save(self.root/'next-before/budget.json',factory),
            before_request_ledger=self.f.save(self.root/'next-before/requests.json',guard),
            active_room_ids=[room,self.config['band']['judged_room_id']],
            cumulative_room_ids=sorted(factory['room_ids']+[room]))
        config=copy.deepcopy(self.config)
        config['band'].update(rehearsal_room_id=room,archived_room_ids=sorted(set(factory['room_ids'])-{config['band']['judged_room_id']}))
        config['runtime']['featherless_budget_guard']['time_renewal']=self.f.save(self.root/'next-approval.json',authority)
        return config,authority

    def test_subsequent_room_reuses_original_approval_and_all_current_consumption(self):
        factory,guard=self.current();factory['tokens']=2000001;factory['turns']['pm']=1000
        before=copy.deepcopy((factory,guard,self.config,self.authority))
        config,authority=self.child(factory,guard)
        updated_factory,updated_guard=reconcile_balance_scope(config,factory,guard,self.models,now=self.now+100000)
        self.assertEqual((factory,guard,self.config,self.authority),before)
        self.assertEqual(authority['approved_epoch'],self.authority['approved_epoch'])
        self.assertEqual(authority['user_answer'],'Keep only the $25 cap')
        self.assertEqual(updated_guard['requests'],guard['requests']);self.assertEqual(len(updated_guard['requests']),9)
        self.assertEqual(len(updated_guard['policy']['time_renewal']['retained_requests_sha256']),9)
        self.assertEqual({k:v for k,v in updated_factory.items() if k!='room_ids'},{k:v for k,v in factory.items() if k!='room_ids'})
        self.assertEqual(updated_factory['started_epoch'],factory['started_epoch'])
        self.assertEqual(updated_guard['started_epoch'],guard['started_epoch'])
        self.assertEqual(updated_factory['room_stopped_reasons'],factory['room_stopped_reasons'])
        self.assertEqual(updated_guard['policy']['approved_credit_nano_usd'],25000000000)
        checked=_Ledger(self.guard_path,updated_guard['policy']);checked.data=updated_guard;checked._validate()
        updated_guard['requests'].pop('9'.zfill(32))
        with self.assertRaises(GuardError):checked._validate()
        effective=validate_renewal_config(config,now=self.now+100000)
        self.assertEqual(effective['renewal_deadline_epoch'],self.f.authority['renewal_deadline_epoch'])

    def test_new_approval_epoch_or_scope_permission_model_drift_is_rejected(self):
        factory,guard=self.current();config,authority=self.child(factory,guard)
        for fault in ('epoch','room','native','model','cap','result'):
            changed=copy.deepcopy(config);approval=copy.deepcopy(authority)
            if fault=='epoch':approval['approved_epoch']+=1
            elif fault=='room':approval['active_room_ids'][1]=str(uuid4())
            elif fault=='native':changed['runtime']['native_permissions']={'write':False}
            elif fault=='model':changed['seats'][0]['model']='different-model'
            elif fault=='result':changed['paths']['result']=changed['paths'].get('result','/tmp/result')+'/changed'
            else:changed['budgets']['spend_cap_usd']=26
            changed['runtime']['featherless_budget_guard']['time_renewal']=self.f.save(self.root/('bad-'+fault+'.json'),approval)
            with self.subTest(fault=fault),self.assertRaises(FactoryError):validate_renewal_config(changed,now=self.now+10)

    def test_current_unknown_request_or_stop_cannot_be_cleared(self):
        factory,guard=self.current()
        for fault in ('unknown','money-stop'):
            bad=copy.deepcopy(guard)
            if fault=='unknown':bad['requests']['9'.zfill(32)]['status']='unknown'
            else:bad['stopped_reason']='money reservation would exceed the approved cap'
            config,_=self.child(factory,bad)
            with self.subTest(fault=fault),self.assertRaises(FactoryError):validate_renewal_config(config,now=self.now)

class ScopeChainHelperTests(BalanceHelperTests):
    # Inherited first finite->balance tests remain the legacy regression suite.
    def test_second_room_commit_uses_real_full_schema_loader(self):
        super().test_production_loader_accepts_final_policy_after_new_room_seed_with_old_authority()
        from factorykit.common import load_config
        previous = self.target
        previous_raw = previous.read_bytes()
        before = load_config(previous)
        room = str(uuid4())
        self.before_path = previous
        self.target = self.root / 'attempts/real-compact/factory.yaml'
        self.target.parent.mkdir()
        seed = copy.deepcopy(before)
        seed['band']['rehearsal_room_id'] = room
        seed['band']['archived_room_ids'] = sorted(
            set(json.loads(self.factory_path.read_text())['room_ids']) - {before['band']['judged_room_id']})
        seed['paths']['rehearsal'] += '-compact'
        seed['artifacts'] = {name: str(self.target.parent / relative) for name, relative in
                            (('source_lock', 'source-lock.json'), ('tasks', 'tasks'), ('mandates', 'mandates'))}
        for seat in seed['seats']:
            seat['mandate'] = str(self.target.parent / 'mandates' / Path(seat['mandate']).name)
        self.target.write_text(yaml.safe_dump(seed)); self.target.chmod(0o600)
        self.folder = self.target.parent / 'accounting-balance-only'
        self.argv = ['--factory', str(Path(__file__).resolve().parents[1]), '--before-config', str(previous),
                     '--config', str(self.target), '--evidence-dir', str(self.folder),
                     '--rehearsal-room', room, '--approved-epoch', str(self.now)]
        with self.assertRaises(FactoryError):
            load_config(self.target)  # Existing authority cannot authenticate the uncommitted new room.
        _, review = self.run_helper()
        self.assertEqual(review['writes'], 0)
        self.assertTrue(review['review']['original_balance_approval_reused'])
        _, result = self.run_helper(('--execute', '--review-sha256', review['review_sha256']))
        self.assertEqual(result['status'], 'PASS')
        final = load_config(self.target)
        self.assertEqual(final['band']['rehearsal_room_id'], room)
        self.assertEqual(final['band']['judged_room_id'], before['band']['judged_room_id'])
        self.assertEqual(previous.read_bytes(), previous_raw)
        self.assertEqual(json.loads(self.guard_path.read_text())['requests'], self.guard['requests'])

    def test_second_helper_dryrun_and_commit_preserve_unknown_task_board_and_old_config(self):
        _,review=self.run_helper();self.run_helper(('--execute','--review-sha256',review['review_sha256']))
        old_target=self.target
        old_bytes=old_target.read_bytes();first_approval=(self.folder/'approval.json').read_bytes()
        board=self.root/'runtime'/('task-board-'+self.newroom+'.json')
        self.f.save(board,{'items':{'uncertain-old':{'version':0,'task_id':None,'pending':{'operation':'create'}}}})
        board_before=board.read_bytes()
        before=yaml.safe_load(old_bytes);second=str(uuid4())
        self.before_path=old_target;self.target=self.root/'attempts/compact/factory.yaml';self.target.parent.mkdir()
        seed=copy.deepcopy(before);seed['band']['rehearsal_room_id']=second
        seed['band']['archived_room_ids']=sorted(set(json.loads(self.factory_path.read_text())['room_ids'])-{before['band']['judged_room_id']})
        self.target.write_text(yaml.safe_dump(seed));self.target.chmod(0o600)
        self.folder=self.target.parent/'accounting-balance-only'
        self.argv=['--factory',str(Path(__file__).resolve().parents[1]),'--before-config',str(self.before_path),
            '--config',str(self.target),'--evidence-dir',str(self.folder),'--rehearsal-room',second,'--approved-epoch',str(self.now)]
        _,review=self.run_helper();self.assertTrue(review['review']['original_balance_approval_reused'])
        self.assertEqual(review['writes'],0);self.assertEqual(self.before_path.read_bytes(),old_bytes)
        self.assertIn(str(board),review['review']['protected_sha256'])
        _,result=self.run_helper(('--execute','--review-sha256',review['review_sha256']))
        self.assertEqual(result['status'],'PASS');self.assertEqual(result['request_count_preserved'],8)
        self.assertEqual(board.read_bytes(),board_before);self.assertEqual(self.before_path.read_bytes(),old_bytes)
        self.assertEqual((old_target.parent/'accounting-balance-only/approval.json').read_bytes(),first_approval)
        final=yaml.safe_load(self.target.read_text());effective=validate_renewal_config(final,now=self.now)
        self.assertEqual(effective['active_room_ids'],[second,before['band']['judged_room_id']])
        child=json.loads((self.folder/'approval.json').read_text())
        parent=json.loads(first_approval)
        self.assertEqual(child['approved_epoch'],parent['approved_epoch'])
