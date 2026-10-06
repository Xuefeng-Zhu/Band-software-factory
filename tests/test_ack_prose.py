"""Receipt prose tolerance preserves identity, delivery and historical evidence."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from factorykit import workflow

from factorykit.workflow import WorkflowWatchdog, WorkflowError, parse_ack

ROOM = '00000000-0000-4000-8000-000000000001'
PM = '00000000-0000-4000-8000-000000000002'
QA = '00000000-0000-4000-8000-000000000003'
OTHER = '00000000-0000-4000-8000-000000000004'
DIGEST = 'a' * 64


def event(n):
    return f'00000000-0000-4000-8000-{n:012d}'


def ack():
    return f'HANDOFF-ACK delivery WORK-1; SHA-256 {DIGEST}; sender @[[{PM}]]'


class AckProseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'workflow.json'
        self.w = WorkflowWatchdog(self.path, ROOM, PM, [PM, QA, OTHER], 60,
                                  clock=lambda: 1000.0, balance_only=True)
        self.part = f'WORK-1 delivery WORK-1 part 1/1; SHA-256 {DIGEST}; recipient @[[{QA}]]\nComplete assigned requirements.\nEND OF HANDOFF'
        self.w.observe_outbound(event(10), PM, [QA], self.part)

    def data(self):
        return json.loads(self.path.read_bytes())

    def test_valid_first_line_plus_prose_acknowledges_without_rewriting_event(self):
        content = ack() + '\n\nReceived complete; sources verified. This confirms communication, not work acceptance.'
        self.assertIsNotNone(parse_ack(content))
        result = self.w.observe_outbound(event(20), QA, [PM], content)
        self.assertTrue(result['acknowledged'])
        data = self.data()
        self.assertEqual(data['events'][event(20)]['content_sha256'], hashlib.sha256(content.encode()).hexdigest())
        self.assertEqual(data['deliveries']['WORK-1']['acks'], {QA: event(20)})
        self.assertNotIn('accepted', self.path.read_text())
        self.assertEqual(self.w.health()['state'], 'idle')

    def test_additional_ack_or_multipart_headers_cannot_be_hidden_in_prose(self):
        for extra in (ack(), ack().replace('WORK-1', 'OTHER-DELIVERY'), '> ' + ack(),
                      self.part, 'Note: ' + self.part.splitlines()[0],
                      'INCOMPLETE: not received.', 'REJECTED: digest mismatch',
                      'INCOMPLETE', 'REJECTED'):
            with self.subTest(extra=extra[:35]), self.assertRaises(WorkflowError):
                parse_ack(ack() + '\n\n' + extra)
        result = self.w.observe_outbound(event(21), QA, [PM], ack() + '\n' + ack())
        self.assertTrue(result['blocked'])
        self.assertFalse(self.data()['deliveries']['WORK-1']['acknowledged'])

    def test_inline_prose_is_not_a_canonical_first_line(self):
        self.assertIsNone(parse_ack(ack() + '. Additional prose.'))
        self.assertIsNone(parse_ack('Receipt follows:\n' + ack()))
        self.assertTrue(self.w.observe_outbound(event(22), QA, [PM], ack() + '. Extra')['blocked'])

    def test_digest_original_sender_recipient_and_complete_delivery_remain_required(self):
        cases = [(QA, [PM], ack().replace(DIGEST, 'b'*64)),
                 (QA, [PM], ack().replace('WORK-1', 'UNKNOWN')),
                 (QA, [PM], ack().replace(PM, OTHER)),
                 (OTHER, [PM], ack()), (QA, [OTHER], ack())]
        for i, (actor, recipients, content) in enumerate(cases, 30):
            with self.subTest(index=i):
                self.assertTrue(self.w.observe_outbound(event(i), actor, recipients, content + '\nVerified inputs.')['blocked'])
        self.assertFalse(self.data()['deliveries']['WORK-1']['acknowledged'])
        self.w.observe_outbound(event(40), PM, [QA], self.part.replace('WORK-1','PARTIAL').replace('part 1/1','part 1/2'))
        self.assertTrue(self.w.observe_outbound(event(41), QA, [PM], ack().replace('WORK-1','PARTIAL') + '\nVerified inputs.')['blocked'])

    def test_only_confirmed_format_errors_are_balance_only_advisories(self):
        self.w.observe_outbound(event(50), QA, [PM], ack() + '. Invalid first line')
        health = self.w.health()
        self.assertEqual(health['state'], 'blocked')
        self.assertTrue(health['communication_advisory'])
        # Same confirmed event with changed bytes is conflicting provenance.
        self.w.observe_outbound(event(10), PM, [QA], self.part + '\nchanged')
        self.assertFalse(self.w.health()['communication_advisory'])
        finite = WorkflowWatchdog(Path(self.temp.name)/'finite.json', ROOM, PM, [PM,QA],60,clock=lambda:1000.0)
        finite.observe_outbound(event(51),QA,[PM],ack() + '. Invalid first line')
        self.assertFalse(finite.health().get('communication_advisory',False))

    def test_later_receipt_does_not_erase_old_incident_or_unknown_send(self):
        self.w.observe_outbound(event(60), QA, [PM], ack() + '. Invalid first line')
        before = self.data()['incidents']
        self.assertTrue(self.w.observe_outbound(event(61), QA, [PM], ack() + '\nInputs verified.')['acknowledged'])
        self.assertEqual(self.data()['incidents'], before)
        self.assertEqual(self.w.health()['state'],'blocked')
        self.w.begin_turn(QA, 'uncertain-turn', None)
        self.w.block_turn_delivery('uncertain-turn')
        self.assertFalse(self.w.health()['communication_advisory'])


    def historical_receipt(self):
        content = ack() + '\n\nReceived complete; separate result posted earlier.'
        self.w.begin_turn(QA, 'qa-turn', None)
        self.w.observe_outbound(event(70), QA, [PM], 'Substantive result.', 'qa-turn')
        with patch.object(workflow, 'parse_ack', lambda value: workflow._ACK.fullmatch(value.strip())):
            self.assertTrue(self.w.observe_outbound(event(71), QA, [PM], content, 'qa-turn')['blocked'])
        self.w.end_turn('qa-turn', 'completed')
        return content

    def test_explicit_exact_historical_receipt_replay_preserves_failed_evidence(self):
        content = self.historical_receipt()
        before = self.data()
        raw = self.path.read_bytes()
        self.assertEqual(self.w.observe_outbound(event(71), QA, [PM], content, 'qa-turn'), {'duplicate': True})
        self.assertEqual(self.path.read_bytes(), raw)
        result = self.w.observe_outbound(event(71), QA, [PM], content, 'qa-turn', revalidate_receipt=True)
        self.assertTrue(result['duplicate'] and result['revalidated'] and result['acknowledged'])
        after = self.data()
        for field in ('events', 'turns', 'notices'):
            self.assertEqual(after[field], before[field])
        incident = after['incidents']['turn:qa-turn']
        history = incident.pop('receipt_revalidations')
        self.assertEqual(incident, before['incidents']['turn:qa-turn'])
        self.assertEqual(history[0]['content_sha256'], before['events'][event(71)]['content_sha256'])
        self.assertEqual(after['deliveries']['WORK-1']['acks'], {QA: event(71)})
        health = self.w.health()
        self.assertEqual(health['state'], 'blocked')
        self.assertTrue(health['communication_advisory'])
        self.assertEqual(health['revalidated_receipt_event_ids'], [event(71)])
        final = self.path.read_bytes()
        self.w.observe_outbound(event(71), QA, [PM], content, 'qa-turn', revalidate_receipt=True)
        self.assertEqual(self.path.read_bytes(), final)
        reopened = WorkflowWatchdog(self.path, ROOM, PM, [PM,QA,OTHER],60,clock=lambda:1001.0,balance_only=True)
        self.assertEqual(reopened.health()['state'], 'blocked')
        self.assertTrue(reopened.health()['communication_advisory'])

    def test_historical_revalidation_never_changes_binding_or_creates_event(self):
        content = self.historical_receipt()
        with self.assertRaises(WorkflowError):
            self.w.observe_outbound(event(72), QA, [PM], content, 'qa-turn', revalidate_receipt=True)
        self.assertNotIn(event(72), self.data()['events'])
        baseline = self.path.read_bytes()
        original = self.data()['events'][event(71)]
        for actor, recipients, value, turn in [(OTHER,[PM],content,'qa-turn'),
                (QA,[OTHER],content,'qa-turn'), (QA,[PM],content+' changed','qa-turn'),
                (QA,[PM],content,None)]:
            self.path.write_bytes(baseline)
            self.assertTrue(self.w.observe_outbound(event(71),actor,recipients,value,turn,revalidate_receipt=True)['blocked'])
            self.assertEqual(self.data()['events'][event(71)], original)
        self.assertFalse(self.data()['deliveries']['WORK-1']['acknowledged'])
        self.assertFalse(self.w.health()['communication_advisory'])

    def test_second_invalid_event_and_unknown_provenance_remain_recorded(self):
        content = self.historical_receipt()
        self.w.observe_outbound(event(71),QA,[PM],content,'qa-turn',revalidate_receipt=True)
        self.w.observe_outbound(event(73),QA,[PM],ack()+'. Invalid','qa-turn')
        self.assertEqual(self.w.health()['state'],'blocked')
        self.assertEqual(self.w.health()['revalidated_receipt_event_ids'],[event(71)])
        # Replaying the original receipt again never clears this old incident.
        self.w.observe_outbound(event(71),QA,[PM],content,'qa-turn',revalidate_receipt=True)
        self.assertEqual(self.data()['incidents']['turn:qa-turn']['blocked'],'invalid_or_conflicting_multipart')
        self.w.block_turn_delivery('qa-turn')
        self.w.observe_outbound(event(71),QA,[PM],content,'qa-turn',revalidate_receipt=True)
        self.assertFalse(self.w.health()['communication_advisory'])
        self.assertEqual(self.data()['incidents']['turn:qa-turn']['blocked'],'outbound_delivery_unknown')

    def test_replay_rechecks_complete_delivery_and_exact_digest(self):
        content = self.historical_receipt()
        # The legacy failure must also be a valid receipt under all retained authority.
        for field, value in [('digest','b'*64), ('sender_id',OTHER), ('complete',False)]:
            with self.subTest(field=field):
                baseline=self.path.read_bytes(); data=self.data(); delivery=data['deliveries']['WORK-1']
                if field == 'sender_id':
                    delivery[field]=value
                    data['events'][event(10)]['sender_id']=value
                    data['incidents']['event:'+event(10)]['sender_id']=value
                elif field == 'complete':
                    delivery.update(total=2,complete=False)
                else: delivery[field]=value
                self.path.write_text(json.dumps(data))
                self.assertEqual(self.w.observe_outbound(event(71),QA,[PM],content,'qa-turn',revalidate_receipt=True),{'duplicate':True})
                self.assertFalse(self.data()['deliveries']['WORK-1']['acknowledged'])
                self.assertNotIn('receipt_revalidations',self.data()['incidents']['turn:qa-turn'])
                self.path.write_bytes(baseline)


if __name__ == '__main__':
    unittest.main()
