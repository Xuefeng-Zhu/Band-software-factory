"""Real cumulative policy/ledger migration checks; no provider or BAND calls."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

import yaml

from tests import test_allowance_renewal as renewal_fixtures
from factorykit.allowance_renewal import reconcile_accounting, validate_renewal_config
from factorykit.allowance_scope import reconcile_balance_scope
from factorykit.budgets import budget_errors, persisted_budget_blockers
from factorykit.common import FactoryError
from factorykit.featherless import MODEL_IDS
from factorykit.featherless_guard import _charge, _Ledger, _policy, FeatherlessGuard, GuardError


class BalanceFixture(unittest.TestCase):
    def setUp(self):
        fixture = self.f = renewal_fixtures.RenewalTests(); fixture.setUp(); self.addCleanup(fixture.doCleanups)
        self.root, self.models, self.now = fixture.root, fixture.models, fixture.now
        self.before = copy.deepcopy(fixture.config)
        self.factory, self.guard = reconcile_accounting(self.before, fixture.factory, fixture.guard, self.models, now=self.now)
        for index in range(4):
            model = MODEL_IDS[0 if index < 2 else 1]; m = self.guard['policy']['models'][model]
            prompt, completion = (20039 if index == 0 else 20000), 1000
            self.guard['requests'][str(index + 5).zfill(32)] = {'model':model,'status':'settled','output_ceiling':m['output_ceiling'],
                'reserved_tokens':m['input_ceiling']+m['output_ceiling'], 'reserved_nano_usd':_charge(m,m['input_ceiling'],m['output_ceiling']),
                'prompt_tokens':prompt,'completion_tokens':completion,'charged_nano_usd':_charge(m,prompt,completion)}
        self.factory.update(tokens=108804, turns={'pm':3,'designer':1})
        self.factory['token_threads'][fixture.new_rooms[0]+':pm:paid'] = 84039
        self.factory['room_started_epochs'][fixture.new_rooms[0]] = self.now - 100
        self.factory['room_turns'][fixture.new_rooms[0]] = {'pm':2}
        self.factory['room_stopped_reasons'][fixture.new_rooms[0]] = 'membership recovery failed'
        self.factory_path = self.root/'runtime/budget-session.json'
        self.guard_path = self.root/'runtime/featherless-requests.json'
        fixture.save(self.factory_path,self.factory); fixture.save(self.guard_path,self.guard)
        self.newroom = str(uuid4())
        self.authority = {'schema_version':1,'kind':'BALANCE_ONLY_AMENDMENT','status':'APPROVED',
            'authorization_source':'direct_user_chat','user_answer':'Keep only the $25 cap','approved_epoch':self.now,
            'prior_time_renewal':self.before['runtime']['featherless_budget_guard']['time_renewal'],
            'before_configuration':fixture.save(self.root/'balance-before/config.json',self.before),
            'before_factory_budget':fixture.save(self.root/'balance-before/budget.json',self.factory),
            'before_request_ledger':fixture.save(self.root/'balance-before/requests.json',self.guard),
            'active_room_ids':[self.newroom,fixture.new_rooms[1]],
            'cumulative_room_ids':sorted(self.factory['room_ids']+[self.newroom])}
        self.reference = fixture.save(self.root/'balance-approval.json',self.authority)
        self.config = copy.deepcopy(self.before)
        self.config['band'].update(rehearsal_room_id=self.newroom, archived_room_ids=sorted(set(self.factory['room_ids'])-{fixture.new_rooms[1]}))
        self.config['budgets']['balance_only'] = True
        self.config['runtime']['strict_membership_recovery'] = False
        self.config['runtime']['featherless_budget_guard'].update(balance_only=True,time_renewal=self.reference)
        self.block = patch.object(socket.socket,'connect',side_effect=AssertionError('Balance tests are offline'))
        self.block.start();self.addCleanup(self.block.stop)

    def migrate(self):
        return reconcile_balance_scope(self.config,self.factory,self.guard,self.models,now=self.now)


class BalancePolicyTests(BalanceFixture):
    def test_migration_changes_only_exact_scope_and_policy_and_preserves_all_eight_requests(self):
        original=copy.deepcopy((self.before,self.factory,self.guard,self.authority))
        factory,guard=self.migrate()
        self.assertEqual((self.before,self.factory,self.guard,self.authority),original)
        self.assertEqual(factory['tokens'],108804); self.assertEqual(len(guard['requests']),8)
        self.assertEqual(guard['requests'],self.guard['requests'])
        self.assertEqual({k:v for k,v in factory.items() if k!='room_ids'},{k:v for k,v in self.factory.items() if k!='room_ids'})
        self.assertTrue(guard['policy']['balance_only'])
        self.assertEqual(len(guard['policy']['time_renewal']['retained_requests_sha256']),8)
        for key in ('approved_credit_nano_usd','models','max_total_tokens','overall_timeout_seconds'):
            self.assertEqual(guard['policy'][key],self.guard['policy'][key])
        effective=validate_renewal_config(self.config,now=self.now)
        self.assertEqual(effective['renewal_deadline_epoch'],self.f.authority['renewal_deadline_epoch'])

    def test_expired_original_time_and_future_usage_above_two_million_do_not_block_restart(self):
        factory,guard=self.migrate(); self.f.save(self.factory_path,factory);self.f.save(self.guard_path,guard)
        ledger=_Ledger(self.guard_path,guard['policy']);ledger.open()
        try:
            with patch('time.time',return_value=self.now+100000):
                for _ in range(9):
                    key=ledger.reserve(MODEL_IDS[1],16);ledger.settle(key,250000,1)
            self.assertGreater(ledger.totals()['observed_tokens'],2000000)
            self.assertEqual(ledger.remaining_seconds(),float('inf'))
        finally:ledger.close()
        factory['tokens']=ledger.totals()['observed_tokens'];factory['turns']['pm']=1000
        self.f.save(self.factory_path,factory)
        self.assertEqual(persisted_budget_blockers(self.config,now=self.now+100000,require_existing=True),[])
        reopened=_Ledger(self.guard_path,guard['policy']);reopened.open()
        self.addCleanup(reopened.close)
        self.assertGreater(reopened.totals()['observed_tokens'],2000000)
        self.assertEqual(reopened.data['started_epoch'],self.guard['started_epoch'])
        self.assertEqual({k:reopened.data['requests'][k] for k in self.guard['requests']},self.guard['requests'])

    def test_money_reservations_include_all_carried_charges_and_never_exceed_25(self):
        factory,guard=self.migrate();self.f.save(self.guard_path,guard)
        ledger=_Ledger(self.guard_path,guard['policy']);ledger.open();self.addCleanup(ledger.close)
        with patch('time.time',return_value=self.now+100000):
            for _ in range(100):
                try:key=ledger.reserve(MODEL_IDS[0],32768)
                except GuardError:break
                ledger.settle(key,262144,32768)
            else:self.fail('Dollar cap was never enforced')
        self.assertEqual(ledger.data['stopped_reason'],'money reservation would exceed the approved cap')
        self.assertLessEqual(ledger.totals()['charged_nano_usd'],25000000000)
        self.assertGreater(len(ledger.data['requests']),8)
        self.assertEqual({k:ledger.data['requests'][k] for k in self.guard['requests']},self.guard['requests'])

    def test_restart_rejects_any_deleted_carried_request_or_reduced_factory_consumption(self):
        factory,guard=self.migrate()
        guard['requests'].pop(max(guard['requests']))
        ledger=_Ledger(self.guard_path,guard['policy']);ledger.data=guard
        with self.assertRaises(GuardError):ledger._validate()
        factory['tokens']=108803;self.f.save(self.factory_path,factory)
        self.assertTrue(persisted_budget_blockers(self.config,require_existing=True))

    def test_authority_must_be_exact_and_cannot_change_money_roles_room_or_origin(self):
        for field,value in (('user_answer','approve'),('active_room_ids',[self.newroom,str(uuid4())]),('cumulative_room_ids',[self.newroom])):
            authority=copy.deepcopy(self.authority);authority[field]=value
            reference=self.f.save(self.root/(field+'.json'),authority)
            config=copy.deepcopy(self.config);config['runtime']['featherless_budget_guard']['time_renewal']=reference
            with self.subTest(field=field),self.assertRaises(FactoryError):validate_renewal_config(config,now=self.now)
        for change in ('dollar','seat','origin'):
            config=copy.deepcopy(self.config)
            if change=='dollar':config['budgets']['spend_cap_usd']=26
            elif change=='seat':config['seats'][0]['agent_id']=str(uuid4())
            else:
                guard=copy.deepcopy(self.guard);guard['started_epoch']+=1
                authority=copy.deepcopy(self.authority);authority['before_request_ledger']=self.f.save(self.root/'reset.json',guard)
                config['runtime']['featherless_budget_guard']['time_renewal']=self.f.save(self.root/'reset-authority.json',authority)
            with self.subTest(change=change),self.assertRaises(FactoryError):validate_renewal_config(config,now=self.now)

    def test_flag_without_bound_approval_or_mismatched_flag_is_rejected(self):
        with self.assertRaises(GuardError):_policy(self.models,25000000000,2000000,21600,balance_only=True)
        with self.assertRaises(GuardError):_policy(self.models,25000000000,2000000,21600,balance_only='yes')
        options=self.config['runtime']['featherless_budget_guard']
        with self.assertRaises(GuardError):_policy(self.models,25000000000,options['max_total_tokens'],options['overall_timeout_seconds'],time_renewal=self.reference)
        self.assertEqual(budget_errors(self.config['budgets']),[])

    def test_provider_forwarding_has_no_historical_request_timeout_in_balance_mode(self):
        options=self.config['runtime']['featherless_budget_guard']
        guard=FeatherlessGuard(api_key='offline-synthetic',models=self.models,ledger_path=self.guard_path,
            overall_timeout_seconds=options['overall_timeout_seconds'],time_renewal=self.reference,balance_only=True)
        self.assertIsNone(guard._request_timeout);self.assertIsNone(guard._server)

    def test_unknown_usage_or_global_stop_is_never_cleared_by_amendment(self):
        for change in ('unknown','stopped'):
            guard=copy.deepcopy(self.guard)
            if change=='unknown':guard['requests'][max(guard['requests'])]['status']='unknown'
            else:guard['stopped_reason']='provider request failed or was interrupted'
            authority=copy.deepcopy(self.authority)
            authority['before_request_ledger']=self.f.save(self.root/(change+'-guard.json'),guard)
            config=copy.deepcopy(self.config)
            config['runtime']['featherless_budget_guard']['time_renewal']=self.f.save(self.root/(change+'-approval.json'),authority)
            with self.subTest(change=change),self.assertRaises(FactoryError):validate_renewal_config(config,now=self.now)

    def test_permissions_endpoints_binary_and_model_settings_are_preserved(self):
        for field,value in (('native_permissions',{'network':True}),('approval_mode','unsafe'),('reasoning_effort','high'),('opencode_sha256','0'*64)):
            config=copy.deepcopy(self.config);config['runtime'][field]=value
            with self.subTest(field=field),self.assertRaises(FactoryError):validate_renewal_config(config,now=self.now)
        config=copy.deepcopy(self.config);config['band']['rest_url']='https://different.invalid'
        with self.assertRaises(FactoryError):validate_renewal_config(config,now=self.now)


class BalanceHelperTests(BalanceFixture):
    def setUp(self):
        super().setUp()
        spec=importlib.util.spec_from_file_location('balance_helper',Path(__file__).resolve().parents[1]/'tooling/reconcile-balance-only.py')
        self.helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.helper)
        self.before_path=self.root/'attempts/old/factory.yaml';self.target=self.root/'attempts/normal/factory.yaml'
        for path in (self.before_path,self.target):path.parent.mkdir(parents=True,exist_ok=True)
        self.before_path.write_text(yaml.safe_dump(self.before));self.before_path.chmod(0o600)
        seed=copy.deepcopy(self.config);seed['runtime']['featherless_budget_guard']=copy.deepcopy(self.before['runtime']['featherless_budget_guard'])
        seed['budgets']['approved']=False
        self.target.write_text(yaml.safe_dump(seed));self.target.chmod(0o600)
        self.folder=self.target.parent/'accounting-balance-only'
        self.f.save(self.root/'runtime/owner.json',{'status':'stopped','parent':{'pid':99999999,'created':1.0},'children':[]})
        self.failed=self.root/'runtime'/('membership-'+self.f.new_rooms[0]+'.json');self.f.save(self.failed,{'state':'original failure'})
        self.failed_raw=self.failed.read_bytes()
        self.argv=['--factory',str(Path(__file__).resolve().parents[1]),'--before-config',str(self.before_path),'--config',str(self.target),
            '--evidence-dir',str(self.folder),'--rehearsal-room',self.newroom,'--approved-epoch',str(self.now)]
        self.load=patch('factorykit.common.load_config',side_effect=lambda p:yaml.safe_load(Path(p).read_text()))
        self.load.start();self.addCleanup(self.load.stop)

    def run_helper(self,extra=()):
        with patch('sys.stdout',new=io.StringIO()) as output:
            status=self.helper.main(self.argv+list(extra))
        return status,json.loads(output.getvalue())

    def test_production_loader_accepts_final_policy_after_new_room_seed_with_old_authority(self):
        # This deliberately exercises the real parser/guard selection, rather
        # than the minimal-fixture parser used by transaction fault tests.
        self.load.stop()
        from factorykit.common import load_config
        workspace = tempfile.TemporaryDirectory(prefix='balance-workspaces-')
        self.addCleanup(workspace.cleanup)
        outside = Path(workspace.name).resolve()
        before = copy.deepcopy(self.before)
        before['schema_version'] = 1
        before['paths'].update({name: str(outside / name)
                               for name in ('challenge', 'factory', 'rehearsal', 'result')})
        before['artifacts'] = {name: str(self.before_path.parent / relative) for name, relative in
                               (('source_lock', 'source-lock.json'), ('tasks', 'tasks'), ('mandates', 'mandates'))}
        before['launch'] = {'mode': 'all', 'practice_mode': True, 'registration_verified': True,
                            'submission_open_verified': False}
        before['band']['credentials_file'] = str(outside / 'private-credentials.yaml')
        before['runtime'].update(python=sys.executable, harness_python=sys.executable,
                                 opencode_command=str(outside / 'opencode'), browser_path=str(outside / 'browsers'),
                                 approval_mode='auto_decline', approval_policy='never', sandbox='workspace-write',
                                 native_permissions={'read': True, 'write': True, 'bash': True, 'network': False})
        for seat in before['seats']:
            role = seat['id']
            seat.update(display_name='Factory ' + role, handle='factory-' + role, harness='opencode',
                        git_name='Factory ' + role, git_email=role + '@example.invalid',
                        mandate=str(self.before_path.parent / 'mandates' / ('factory-' + role + '.md')))
        self.before_path.write_text(yaml.safe_dump(before))
        self.assertEqual(load_config(self.before_path), before)
        seed = copy.deepcopy(before)
        seed['budgets'].update(approved=False, balance_only=True)
        seed['runtime']['strict_membership_recovery'] = False
        seed['band']['rehearsal_room_id'] = self.newroom
        seed['paths'].update(rehearsal=str(outside / 'normal-rehearsal'), result=str(outside / 'normal-result'))
        seed['artifacts'] = {name: str(self.target.parent / relative) for name, relative in
                            (('source_lock', 'source-lock.json'), ('tasks', 'tasks'), ('mandates', 'mandates'))}
        for seat in seed['seats']:
            seat['mandate'] = str(self.target.parent / 'mandates' / Path(seat['mandate']).name)
        self.target.write_text(yaml.safe_dump(seed))
        with self.assertRaises(FactoryError):
            load_config(self.target)  # New room and unminted authority are not ready to run.
        old = {path: path.read_bytes() for path in (self.before_path, self.target, self.factory_path, self.guard_path, self.failed)}
        status, review = self.run_helper()
        self.assertEqual(status, 0); self.assertEqual(review['writes'], 0)
        self.assertEqual({path: path.read_bytes() for path in old}, old)
        status, result = self.run_helper(('--execute', '--review-sha256', review['review_sha256']))
        self.assertEqual(status, 0); self.assertEqual(result['status'], 'PASS')
        final = load_config(self.target)
        self.assertTrue(final['budgets']['approved']); self.assertTrue(final['budgets']['balance_only'])
        self.assertTrue(final['runtime']['featherless_budget_guard']['balance_only'])
        self.assertEqual(final['band']['rehearsal_room_id'], self.newroom)
        self.assertEqual(final['runtime']['native_permissions'], before['runtime']['native_permissions'])
        self.assertEqual(final['seats'], seed['seats'])
        self.assertEqual(json.loads(self.factory_path.read_text())['tokens'], 108804)
        self.assertEqual(json.loads(self.guard_path.read_text())['requests'], self.guard['requests'])
        self.assertEqual(self.before_path.read_bytes(), old[self.before_path])
        self.assertEqual(self.failed.read_bytes(), old[self.failed])

    def test_dry_run_writes_nothing_and_execute_preserves_evidence_and_accounting(self):
        old=tuple(path.read_bytes() for path in (self.before_path,self.target,self.factory_path,self.guard_path))
        status,review=self.run_helper()
        self.assertEqual(status,0);self.assertEqual(review['writes'],0);self.assertFalse(self.folder.exists())
        self.assertEqual(old,tuple(path.read_bytes() for path in (self.before_path,self.target,self.factory_path,self.guard_path)))
        status,result=self.run_helper(('--execute','--review-sha256',review['review_sha256']))
        self.assertEqual(status,0);self.assertEqual(result['status'],'PASS')
        self.assertEqual(result['tokens_preserved'],108804);self.assertEqual(result['request_count_preserved'],8)
        self.assertEqual(self.before_path.read_bytes(),old[0]);self.assertEqual(self.failed.read_bytes(),self.failed_raw)
        self.assertTrue((self.folder/'claim.json').is_file());self.assertTrue((self.folder/'commit-report.json').is_file())

    def test_changed_review_rejected_before_any_file_or_lock_write(self):
        _,review=self.run_helper();self.target.write_bytes(self.target.read_bytes()+b'\n')
        with self.assertRaises(ValueError):self.run_helper(('--execute','--review-sha256',review['review_sha256']))
        self.assertFalse(self.folder.exists());self.assertFalse((self.root/'runtime/launch.lock').exists())

    def test_partial_commit_retains_claim_before_images_and_blocks_retry(self):
        _,review=self.run_helper();real=self.helper.replace;calls=[]
        def interrupted(path,raw):
            calls.append(path);real(path,raw)
            if len(calls)==1:raise OSError('offline injected crash')
        with patch.object(self.helper,'replace',side_effect=interrupted):
            with self.assertRaises(OSError):self.run_helper(('--execute','--review-sha256',review['review_sha256']))
        self.assertTrue((self.folder/'claim.json').exists());self.assertTrue((self.folder/'before/request_ledger.json').exists())
        self.assertEqual(self.failed.read_bytes(),self.failed_raw)
        with self.assertRaises(ValueError):self.run_helper(('--execute','--review-sha256',review['review_sha256']))

    def test_durable_before_images_and_claim_precede_first_ledger_replacement(self):
        _,review=self.run_helper();events=[]
        real_create,real_sync,real_replace=self.helper.create,self.helper.sync,self.helper.replace
        def create(path,raw):events.append(('create',path));return real_create(path,raw)
        def sync(path):events.append(('sync',path));return real_sync(path)
        def replace(path,raw):events.append(('replace',path));return real_replace(path,raw)
        with patch.object(self.helper,'create',side_effect=create),patch.object(self.helper,'sync',side_effect=sync),patch.object(self.helper,'replace',side_effect=replace):
            self.run_helper(('--execute','--review-sha256',review['review_sha256']))
        first=next(index for index,event in enumerate(events) if event[0]=='replace')
        prior=events[:first]
        self.assertIn(('create',self.folder/'claim.json'),prior)
        self.assertIn(('sync',self.folder),prior);self.assertIn(('sync',self.folder/'before'),prior)
        self.assertIn(('create',self.folder/'before/request_ledger.json'),prior)
        self.assertIn(('create',self.folder/'before/factory_budget.json'),prior)


if __name__=='__main__':unittest.main()
