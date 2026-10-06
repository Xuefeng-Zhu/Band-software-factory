"""Offline synthetic token approval fixtures; never live authorization."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import yaml
import test_deadline_extension as fixtures
from factorykit import deadline_extension as de, token_extension as te
from factorykit.common import FactoryError, canonical, digest

class TokenExtensionTests(unittest.TestCase):
    def setUp(self):
        f=self.f=fixtures.DeadlineExtensionTests();f.setUp();self.addCleanup(f.doCleanups)
        self.locked_defaults = b'model = "gpt-6.1-sol"\nmodel_reasoning_effort = "high"\n'
        f.write(f.global_config,self.locked_defaults)
        f.lock['instruction_inputs'][0]['sha256']=digest(self.locked_defaults)
        f.write_json(f.runs/'source-lock.json',f.lock)
        f.freeze['source_lock_sha256']=digest(f.runs/'source-lock.json')
        f.base['budgets']['max_total_tokens']=te.OLD_LIMIT
        f.write(f.runs/'factory.yaml',yaml.safe_dump(f.base).encode())
        f.freeze['configuration_sha256']=digest(canonical(f.base));f.write_json(f.runs/'freeze/latest.json',f.freeze)
        f.launch['entries'][0]['freeze_sha256']=digest(f.runs/'freeze/latest.json');f.write_json(f.runs/'launch/ledger.json',f.launch)
        f.auth.update(max_total_tokens=te.OLD_LIMIT,remaining_reported_tokens=te.OLD_LIMIT-100,
                      original_configuration_sha256=digest(f.runs/'factory.yaml'),original_freeze_sha256=digest(f.runs/'freeze/latest.json'))
        f.write_json(f.auth_path,f.auth)
        manifest=json.loads((f.saved/'before-manifest.json').read_text())
        for row in manifest['files']:
            source=Path(row['source']);f.write(Path(row['preserved']),source.read_bytes());row['sha256']=digest(source)
        f.write_json(f.saved/'before-manifest.json',manifest)
        self.audited_defaults = self.locked_defaults + ('\n[projects."'+f.base['paths']['result']+'"]\ntrust_level = "trusted"\n').encode()
        f.write(f.global_config,self.audited_defaults)
        self.trust_audit=f.saved/'trust-audit.json'
        f.write_json(self.trust_audit,{'global_configuration':{'classification':'EXACT_NEW_RESULT_TRUST_STANZA_ONLY',
            'path':str(f.global_config),'locked_sha256':digest(self.locked_defaults),'observed_sha256':digest(self.audited_defaults),
            'reconstruction':{'matches_locked_sha256':True,'reconstructed_sha256':digest(self.locked_defaults),
            'removed_section_key':'projects.'+f.base['paths']['result'],'section_keys':['trust_level'],'sections_removed':1}}})
        model_auth,model_catalog=f.model_evidence()
        self.parent=f.approved(f.proposal(model_authorization_path=model_auth,model_catalog_path=model_catalog,trust_audit_path=self.trust_audit))
        self.old_token='a'*48
        claim=de.prepare_claim(f.base,self.parent,owner_token=self.old_token,now=f.now)['claim']
        self.parent_claim=f.saved/'consumed-parent-claim.json';f.write_json(self.parent_claim,claim)
        self.now=f.now+100
        self.trigger='55555555-5555-4555-8555-555555555555'
        self.turn_id='backend:1:'+self.trigger
        self.current=copy.deepcopy(f.ledger);self.current.update(tokens=286079113,stopped_reason=te.CLEANUP_STOP)
        self.current['turns']['backend']=1;self.current['token_threads']['backend-current']=286079013
        self.current['room_turns'][f.room]['backend']=1
        f.write_json(f.runs/'runtime/budget-subscription.json',self.current)
        self.turn={'agent_id':'offline-backend','trigger_event_id':self.trigger,'status':'interrupted','reason_code':'interrupted','started_at':1750,'ended_at':1760}
        self.workflow={'turns':{self.turn_id:self.turn}}
        f.write_json(f.runs/f'runtime/workflow-{f.room}.json',self.workflow)
        f.write(f.runs/'runtime/execution-events.jsonl',b'{"offline_fixture":true}\n')
        self.owner=copy.deepcopy(f.owner);self.owner.update(token=self.old_token,continuation={'claim_path':str(self.parent_claim),'amendment_sha256':digest(self.parent)})
        f.write_json(f.runs/'runtime/owner.json',self.owner)
        self.fresh=f.runs/'token-proposal';self.manifest=self.fresh/'baseline-manifest.json'
        entries=[]
        for name in ('runtime/budget-subscription.json',f'runtime/workflow-{f.room}.json','runtime/execution-events.jsonl','runtime/owner.json'):
            source=f.runs/name;dest=self.fresh/('before-'+name.replace('/','--'))
            f.write(dest,source.read_bytes());entries.append({'source':str(source),'preserved':str(dest),'sha256':digest(source)})
        f.write_json(self.manifest,{'files':entries})
        self.summary={'schema_version':1,'status':'STOPPED_AT_TOKEN_CEILING','room_id':f.room,'all_recorded_owned_processes_absent':True,
            'reported_tokens':self.current['tokens'],'max_total_tokens':te.OLD_LIMIT,'reported_overage':self.current['tokens']-te.OLD_LIMIT,
            'persisted_stop_reason':te.CLEANUP_STOP,'observed_at':de._utc(self.now),'last_turn_id':self.turn_id,'last_turn':self.turn,
            'runtime_evidence':[{'path':r['source'],'sha256':r['sha256']} for r in entries[:3]]}
        self.summary_path=self.fresh/'stop-summary.json';f.write_json(self.summary_path,self.summary)
        self.continuity=copy.deepcopy(f.continuity);self.continuity['blocked']=[['backend',self.trigger]]
        self.continuity['cutoff_utc']=de._utc(self.now)
        self.continuity_path=self.fresh/'continuity.json';f.write_json(self.continuity_path,self.continuity)
        self.kwargs=dict(parent_amendment_path=self.parent,preservation_manifest_path=self.manifest,
                         stopped_status_path=f.status_path,stop_summary_path=self.summary_path,continuity_path=self.continuity_path,now=self.now)

    def defaults_proof(self, raw=None):
        f=self.f
        if raw is None:
            raw=self.audited_defaults.replace(b'model = "gpt-6.1-sol"',b'model = "gpt-6-astra"').replace(b'model_reasoning_effort = "high"',b'model_reasoning_effort = "xhigh"')
        f.write(f.global_config,raw)
        proof={'schema_version':1,'status':'PASS_EXACT_INHERITED_DEFAULTS_RECONSTRUCTION','path':str(f.global_config),
            'observed_sha256':digest(raw),'prior_audited_sha256':digest(self.audited_defaults),'locked_sha256':digest(self.locked_defaults),
            'trust_audit':de._reference(self.trust_audit),'observed_defaults':{'model':'gpt-6-astra','model_reasoning_effort':'xhigh'},
            'prior_audited_defaults':{'model':'gpt-6.1-sol','model_reasoning_effort':'high'},
            'seat_overrides':[{'seat_id':s['id'],'model':'gpt-6.1-sol','reasoning_effort':s['reasoning_effort']} for s in f.base['seats']]}
        path=self.fresh/'defaults-proof.json';f.write_json(path,proof)
        self.kwargs['inherited_defaults_reconciliation_path']=path
        return path

    def test_exact_defaults_reconstruction_is_pure_and_retains_all_other_source_checks(self):
        self.defaults_proof()
        before={str(p):p.read_bytes() for p in self.f.root.rglob('*') if p.is_file()}
        proposal=self.proposal()
        self.assertEqual(before,{str(p):p.read_bytes() for p in self.f.root.rglob('*') if p.is_file()})
        path=self.approve(self.proposal(True))
        effective=te.validate_amendment(self.f.base,path,now=self.now)
        self.assertEqual(effective['runtime']['model'],'gpt-6.1-sol')
        for seat,original in zip(effective['seats'],self.f.base['seats']):
            self.assertEqual(seat['reasoning_effort'],original['reasoning_effort'])
        self.assertEqual(te.prepare_claim(self.f.base,path,owner_token='b'*48,now=self.now)['cleared_budget']['tokens'],self.current['tokens'])
        self.assertEqual(self.f.lock['instruction_inputs'][0]['sha256'],digest(self.locked_defaults))
        for target in (self.f.root/'guide.md',self.f.factory/'mandates/pm.md',self.f.root/'challenge/spec.md'):
            original=target.read_bytes();target.write_bytes(original+b'changed')
            with self.assertRaises(FactoryError):te.validate_amendment(self.f.base,path,now=self.now)
            target.write_bytes(original)

    def test_later_overridden_defaults_do_not_change_effective_factory(self):
        proof_path=self.defaults_proof();proof_before=proof_path.read_bytes()
        path=self.approve(self.proposal(True));expected=te.validate_amendment(self.f.base,path,now=self.now)
        raw=self.f.global_config.read_bytes()
        for model,effort in [('gpt-6-astra','ultra'),('gpt-6.1-sol','medium')]:
            current=raw.replace(b'model = "gpt-6-astra"',f'model = "{model}"'.encode()).replace(b'model_reasoning_effort = "xhigh"',f'model_reasoning_effort = "{effort}"'.encode())
            self.f.global_config.write_bytes(current)
            self.assertEqual(te.validate_amendment(self.f.base,path,now=self.now),expected)
            self.assertEqual(self.f.global_config.read_bytes(),current)
            self.assertEqual(proof_path.read_bytes(),proof_before)
        self.f.global_config.write_bytes(current+b'\nmodel_provider = "other"\n')
        with self.assertRaises(FactoryError):te.validate_amendment(self.f.base,path,now=self.now)

    def test_recorded_projection_snapshot_and_current_value_shapes_remain_bound(self):
        proof_path=self.defaults_proof();proof=de._read(proof_path)
        proof['observed_sha256']='0'*64;self.f.write_json(proof_path,proof)
        with self.assertRaisesRegex(FactoryError,'snapshot'):self.proposal()
        self.defaults_proof();raw=self.f.global_config.read_bytes()
        for current in (raw.replace(b'model_reasoning_effort = "xhigh"',b'model_reasoning_effort = "unexpected"'),
                        raw.replace(b'model = "gpt-6-astra"',b'model = "invalid model"')):
            self.f.global_config.write_bytes(current)
            with self.assertRaises(FactoryError):self.proposal()

    def test_missing_or_unbound_defaults_proof_is_rejected(self):
        proof=self.defaults_proof();self.kwargs.pop('inherited_defaults_reconciliation_path')
        with self.assertRaises(FactoryError):self.proposal()
        self.kwargs['inherited_defaults_reconciliation_path']=proof
        path=self.approve(self.proposal(True));proof.write_bytes(proof.read_bytes()+b'\n')
        with self.assertRaises(FactoryError):te.validate_amendment(self.f.base,path,now=self.now)

    def test_other_ambient_permission_or_instruction_drift_cannot_be_reconciled(self):
        self.defaults_proof();raw=self.f.global_config.read_bytes()
        for changed in (b'network_access = true\n'+raw,raw.replace(b'trust_level = "trusted"',b'trust_level = "untrusted"'),
                        raw+b'\n[permissions.extra]\nnetwork_access = true\n',raw+b'# new instruction\n'):
            with self.subTest(changed_digest=digest(changed)):
                self.defaults_proof(changed)
                with self.assertRaisesRegex(FactoryError,'prior audited input'):self.proposal()

    def test_duplicate_non_top_level_or_non_exact_default_lines_are_rejected(self):
        self.defaults_proof();raw=self.f.global_config.read_bytes()
        for changed in (b'model = "gpt-6-astra"\n'+raw,b'[nested]\n'+raw,
                        raw.replace(b'model = "gpt-6-astra"',b'"model" = "gpt-6-astra"'),
                        raw+b'\n[nested]\nmodel = "gpt-6-astra"\n'):
            with self.subTest(changed_digest=digest(changed)):
                self.defaults_proof(changed)
                with self.assertRaises(FactoryError):self.proposal()

    def test_defaults_proof_requires_exact_trust_chain_and_explicit_seat_overrides(self):
        proof_path=self.defaults_proof();proof=de._read(proof_path)
        for field,value in (('prior_audited_sha256','0'*64),('locked_sha256','0'*64),
                            ('seat_overrides',list(reversed(proof['seat_overrides'])))):
            changed=copy.deepcopy(proof);changed[field]=value;self.f.write_json(proof_path,changed)
            with self.assertRaises(FactoryError):self.proposal()
        self.f.write_json(proof_path,proof)
        proposal=self.proposal();effective=copy.deepcopy(self.f.base);effective['runtime']['model']='gpt-6.1-sol'
        for seat in effective['seats']:seat['model']='gpt-6.1-sol'
        for changed in ({'model':'gpt-6-astra'},{'reasoning_effort':'xhigh'},{'reasoning_effort':None}):
            invalid=copy.deepcopy(effective);invalid['seats'][0].update(changed)
            with self.assertRaises(FactoryError):te._reconciled_sources(self.f.base,invalid,self.f.lock,proposal)
        other=copy.deepcopy(proof);other['trust_audit']={'path':str(proof_path),'sha256':'0'*64};self.f.write_json(proof_path,other)
        with self.assertRaises(FactoryError):self.proposal()


    def proposal(self,approved=False):
        kwargs=dict(self.kwargs)
        if approved:
            auth={k:None for k in te._AUTH_KEYS}
            auth.update(schema_version=1,status='APPROVED_NOT_APPLIED',authorization_source='Direct user answer in current Codex chat',
                user_answer='Synthetic offline approval fixture only',room_id=self.f.room,additional_tokens=te.ADDITIONAL_TOKENS,
                old_max_total_tokens=te.OLD_LIMIT,new_max_total_tokens=te.NEW_LIMIT,deadline_utc=de._utc(30400.5),
                current_budget_sha256=digest(self.f.runs/'runtime/budget-subscription.json'),parent_amendment_sha256=digest(self.parent),
                base_configuration_sha256=digest(canonical(self.f.base)),recorded_at_utc=de._utc(self.now))
            path=self.fresh/'offline-approval.json';self.f.write_json(path,auth);kwargs['authorization_path']=path
        return te.prepare_amendment(self.f.base,**kwargs)

    def approve(self,proposal):
        review={'schema_version':1,'status':'PASS','scope':'same-room token extension','independent':True,
                'reviewer':'offline fixture','reviewed_at_utc':de._utc(self.now),'proposal_sha256':digest(canonical(proposal)),
                'source_deltas':proposal['source_deltas']}
        path=self.fresh/'offline-review.json';self.f.write_json(path,review)
        value=te.approve_amendment(self.f.base,proposal,review_path=path,now=self.now)
        target=self.fresh/'offline-amendment.json';self.f.write_json(target,value);return target

    def test_pending_proposal_is_pure_and_never_admitted(self):
        before={str(p):p.read_bytes() for p in self.f.root.rglob('*') if p.is_file()}
        proposal=self.proposal()
        self.assertEqual(before,{str(p):p.read_bytes() for p in self.f.root.rglob('*') if p.is_file()})
        self.assertIsNone(proposal['authorization']);self.assertEqual(proposal['status'],'PROPOSED')
        path=self.fresh/'pending.json';self.f.write_json(path,proposal)
        for action in (lambda:te.validate_amendment(self.f.base,path,now=self.now),
                       lambda:te.prepare_claim(self.f.base,path,owner_token='b'*48,now=self.now),lambda:self.approve(proposal)):
            with self.assertRaises(FactoryError):action()

    def test_exact_authorized_delta_preserves_clocks_models_counters_and_old_claim(self):
        claim_before=self.parent_claim.read_bytes();budget_before=(self.f.runs/'runtime/budget-subscription.json').read_bytes()
        proposal=self.proposal(True);path=self.approve(proposal)
        result=te.validate_amendment(self.f.base,path,now=self.now)
        prior=de._read(self.parent)
        expected=copy.deepcopy(self.f.base);expected['budgets'].update(overall_timeout_seconds=29400,stage_timeout_seconds=29200,max_total_tokens=te.NEW_LIMIT)
        expected['runtime']['model']='gpt-6.1-sol'
        for seat in expected['seats']:seat['model']='gpt-6.1-sol'
        self.assertEqual(result,expected);self.assertEqual(te.NEW_LIMIT,786011577)
        self.assertEqual(te.NEW_LIMIT-self.current['tokens'],499932464)
        self.assertEqual(proposal['changes']['new_deadline_utc'],prior['changes']['new_deadline_utc'])
        self.assertEqual(claim_before,self.parent_claim.read_bytes());self.assertEqual(budget_before,(self.f.runs/'runtime/budget-subscription.json').read_bytes())

    def test_unbound_changes_unknown_fields_or_review_tamper_rejected(self):
        path=self.approve(self.proposal(True));original=path.read_bytes()
        for field,value in [('kind','deadline'),('authorization',None),('effective_configuration_sha256','0'*64),('unreviewed',True)]:
            with self.subTest(field=field):
                record=json.loads(original);record[field]=value;self.f.write_json(path,record)
                with self.assertRaises(FactoryError):te.validate_amendment(self.f.base,path,now=self.now)
        path.write_bytes(original)
        approval=self.fresh/'offline-approval.json';record=json.loads(approval.read_text());record['new_max_total_tokens']+=1;self.f.write_json(approval,record)
        with self.assertRaises(FactoryError):te.validate_amendment(self.f.base,path,now=self.now)

    def test_current_evidence_and_consumed_parent_claim_are_immutable(self):
        path=self.approve(self.proposal(True))
        for target in [self.parent,self.parent_claim,self.summary_path,self.continuity_path,self.f.runs/'runtime/owner.json',
                       self.f.runs/'runtime/budget-subscription.json',self.f.runs/f'runtime/workflow-{self.f.room}.json',
                       self.f.runs/'runtime/execution-events.jsonl',self.f.task]:
            with self.subTest(target=target):
                old=target.read_bytes();target.write_bytes(old+b'\n')
                with self.assertRaises(FactoryError):te.validate_amendment(self.f.base,path,now=self.now)
                target.write_bytes(old)

    def test_generic_interruption_below_cap_or_replay_of_interrupted_trigger_rejected(self):
        changed=copy.deepcopy(self.continuity);changed['blocked']=[];self.f.write_json(self.continuity_path,changed)
        with self.assertRaisesRegex(FactoryError,'Interrupted trigger'):self.proposal()
        self.f.write_json(self.continuity_path,self.continuity)
        original=self.current['tokens'];self.current['tokens']=te.OLD_LIMIT-1
        self.rebind_budget()
        with self.assertRaisesRegex(FactoryError,'accounting'):self.proposal()
        self.current['tokens']=original

    def rebind_budget(self):
        p=self.f.runs/'runtime/budget-subscription.json';self.f.write_json(p,self.current)
        manifest=json.loads(self.manifest.read_text())
        row=next(r for r in manifest['files'] if r['source']==str(p));self.f.write(Path(row['preserved']),p.read_bytes());row['sha256']=digest(p)
        self.f.write_json(self.manifest,manifest)

    def test_preserved_epochs_closed_rooms_and_counts_cannot_regress(self):
        original=copy.deepcopy(self.current)
        for field,value in [('started_epoch',1001.5),('room_stopped_reasons',{}),('turns',{'pm':0}),('token_threads',{}),('tokens',te.NEW_LIMIT)]:
            with self.subTest(field=field):
                self.current=copy.deepcopy(original);self.current[field]=value;self.rebind_budget()
                with self.assertRaises(FactoryError):self.proposal()
        self.current=original;self.rebind_budget()

    def test_fresh_owner_must_be_stopped_and_deadline_remains_absolute(self):
        path=self.approve(self.proposal(True))
        with patch.object(de,'_process_alive',return_value=True):
            with self.assertRaises(FactoryError):te.validate_amendment(self.f.base,path,now=self.now)
        with self.assertRaises(FactoryError):te.validate_amendment(self.f.base,path,now=30400.5)

    def test_consumed_parent_claim_cannot_rebind_its_original_accounting(self):
        original=self.parent_claim.read_bytes()
        for field in ('original_budget_sha256','cleared_budget_sha256','effective_configuration_sha256'):
            with self.subTest(field=field):
                claim=json.loads(original);claim[field]='0'*64;self.f.write_json(self.parent_claim,claim)
                with self.assertRaisesRegex(FactoryError,'consumed claim'):self.proposal()
        self.parent_claim.write_bytes(original)

    def test_parent_budget_requires_explicit_subscription_approval(self):
        for change in ({'approved':False},{'billing_mode':'spend_cap','spend_cap_usd':1}):
            with self.subTest(change=change):
                base=copy.deepcopy(self.f.base);base['budgets'].update(change)
                with self.assertRaisesRegex(FactoryError,'approved and subscription-only'):
                    te.prepare_amendment(base,**self.kwargs)
        self.current['room_stopped_reasons'][self.f.room]='independent room stop';self.rebind_budget()
        with self.assertRaises(FactoryError):self.proposal()

    def test_claim_clears_only_halt_and_child_binds_exact_owner_and_ledger(self):
        path=self.approve(self.proposal(True));token='b'*48
        package=te.prepare_claim(self.f.base,path,owner_token=token,now=self.now)
        expected=copy.deepcopy(self.current);expected['stopped_reason']=None
        self.assertEqual(package['cleared_budget'],expected)
        self.assertEqual(package['claim']['kind'],'token_amendment')
        claim_path=self.fresh/'new-claim.json';self.f.write_json(claim_path,package['claim'])
        self.f.write_json(self.f.runs/'runtime/budget-subscription.json',expected)
        owner=copy.deepcopy(self.owner);owner.update(status='starting',token=token);owner['parent']['pid']=42
        self.f.write_json(self.f.runs/'runtime/owner.json',owner)
        with patch.object(te.os,'getpid',return_value=42),patch.object(de,'_process_alive',return_value=True):
            self.assertEqual(te.validate_claimed_amendment(self.f.base,path,claim_path,owner_token=token,now=self.now)['budgets']['max_total_tokens'],te.NEW_LIMIT)
            with self.assertRaises(FactoryError):te.validate_claimed_amendment(self.f.base,path,claim_path,owner_token='c'*48,now=self.now)
            expected['tokens']=0;self.f.write_json(self.f.runs/'runtime/budget-subscription.json',expected)
            with self.assertRaises(FactoryError):te.validate_claimed_amendment(self.f.base,path,claim_path,owner_token=token,now=self.now)

if __name__=='__main__':unittest.main()
