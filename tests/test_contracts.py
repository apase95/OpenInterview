import copy
import json
from pathlib import Path
import re
import unittest

from backend.contracts import Bundle, CandidateQuestion, Room, RoomCreate, Session, openapi_document

ROOT = Path(__file__).resolve().parents[1]


class ContractTests(unittest.TestCase):
    def fixture(self):
        return json.loads((ROOT / 'fixtures/synthetic/v1.json').read_text())

    def test_fixture_and_generated_contract(self):
        bundle = Bundle.model_validate(self.fixture())
        self.assertTrue(bundle.synthetic)
        self.assertEqual(openapi_document(), json.loads(
            (ROOT / 'docs/contracts/openapi-v1.json').read_text()))

    def test_bad_references_and_states(self):
        for mutate in (
            lambda b: b['reports'][0]['criteria'][0].update(evidence_turn_ids=['syn_missing']),
            lambda b: b['turns'][0].update(tenant_id='syn_other'),
            lambda b: b['turns'][1].update(session_id='syn_other'),
            lambda b: b['sessions'][0]['consent'].update(choice=False),
            lambda b: b['reports'][0].update(reviewer_id='syn_hr'),
            lambda b: b['turns'][0].update(delivery_status='unknown'),
            lambda b: b['reports'][0]['criteria'][0].update(evidence_turn_ids=['syn_ask']),
            lambda b: b['reports'][0]['criteria'][0].update(evidence_turn_ids=['syn_answer']),
            lambda b: b['rooms'][0].update(cv_attachment={'id': 'syn_cv'}),
        ):
            data = copy.deepcopy(self.fixture())
            mutate(data)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                Bundle.model_validate(data)

    def test_openapi_local_references(self):
        document = openapi_document()

        def walk(value):
            if isinstance(value, dict):
                if '$ref' in value:
                    target = document
                    self.assertTrue(value['$ref'].startswith('#/'))
                    for part in value['$ref'][2:].split('/'):
                        target = target[part]
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)
        walk(document)
        implemented = {path for path, methods in document['paths'].items()
                       for op in methods.values() if op['x-implementation-state'] == 'implemented'}
        self.assertEqual(implemented, {'/health', '/ready'})

    def test_contact_email_boundary(self):
        data = self.fixture()
        room = {**data['rooms'][0], 'contact': 'hr@company.org'}
        self.assertEqual(Room.model_validate(room).contact, 'hr@company.org')
        request = {key: room[key] for key in ('campaign_id', 'campaign_version', 'opens_at',
                   'closes_at', 'timezone', 'contact', 'cv_attachment')}
        request.update(candidate_email='candidate@company.org', candidate_name='Candidate')
        RoomCreate.model_validate(request)
        for model, value in ((Room, room), (RoomCreate, request)):
            with self.assertRaises(ValueError):
                model.model_validate({**value, 'contact': 'not-an-email'})
        data['rooms'][0]['contact'] = 'hr@company.org'
        with self.assertRaises(ValueError):
            Bundle.model_validate(data)

    def test_response_headers(self):
        for path, methods in openapi_document()['paths'].items():
            if not path.startswith('/v1/'):
                continue
            for method, operation in methods.items():
                headers = operation['responses']['200'].get('headers', {})
                if method == 'get':
                    self.assertIn('X-Contract-Version', headers)
                is_row = path not in ('/v1/rooms', '/v1/reports') or method != 'get'
                self.assertEqual('ETag' in headers, is_row)
                self.assertIn('Retry-After', operation['responses']['429'].get('headers', {}))

    def test_session_consent_and_time(self):
        original = self.fixture()['sessions'][0]
        prejoin = {**original, 'phase': 'consent', 'status': 'active', 'started_at': None,
                   'ended_at': None, 'end_reason': None}
        Session.model_validate(prejoin)
        refused = {**prejoin, 'status': 'ended', 'end_reason': 'refused',
                   'ended_at': '2026-01-02T09:00:00Z',
                   'consent': {**original['consent'], 'choice': False}}
        Session.model_validate(refused)
        for invalid in (
            {**refused, 'end_reason': 'completed'},
            {**refused, 'ended_at': '2026-01-02T08:59:59Z'},
            {**refused, 'started_at': original['started_at']},
            {**original, 'started_at': '2026-01-02T08:59:59Z'},
            {**original, 'ended_at': '2026-01-02T09:00:00Z'},
            {**prejoin, 'ended_at': original['ended_at']},
            {**prejoin, 'end_reason': 'completed'},
            {**prejoin, 'phase': 'experience'},
            {**prejoin, 'status': 'ended', 'end_reason': 'completed', 'ended_at': original['ended_at']},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                Session.model_validate(invalid)
        data = self.fixture()
        data['rooms'][0]['status'] = 'published'
        data['sessions'][0] = refused
        with self.assertRaises(ValueError):
            Bundle.model_validate(data)  # Existing turns cannot belong to a refused session.
        for state in (prejoin, refused):
            data['sessions'][0] = state
            for group in ('turns', 'corrections', 'questions', 'answers', 'jobs', 'reports'):
                data[group] = []
            Bundle.model_validate(data)

    def test_one_session_per_room(self):
        data = self.fixture()
        data['sessions'].append({**data['sessions'][0], 'id': 'syn_duplicate_session'})
        with self.assertRaisesRegex(ValueError, 'duplicate.*room'):
            Bundle.model_validate(data)

    def test_question_disposition_mapping(self):
        question = self.fixture()['questions'][0]
        for disposition, reason, action in (
            ('answer', 'source_missing', 'answer_faq'),
            ('restricted', 'private_information', 'advance'),
            ('deferred', 'candidate_agreed_defer', 'end'),
        ):
            valid = {**question, 'disposition': disposition, 'reason': reason, 'action': action}
            CandidateQuestion.model_validate(valid)
            for field, value in (('reason', 'source_available' if disposition != 'answer' else 'private_information'),
                                 ('action', 'answer_faq' if disposition != 'answer' else 'advance')):
                with self.subTest(disposition=disposition, field=field), self.assertRaises(ValueError):
                    CandidateQuestion.model_validate({**valid, field: value})
            if disposition != 'answer':
                data = self.fixture()
                data['questions'][0] = valid
                with self.assertRaisesRegex(ValueError, 'no.*FAQ|fabricated FAQ'):
                    Bundle.model_validate(data)

    def test_changed_document_links_and_fences(self):
        names = ('docs/architecture/api-data-contract.md', 'docs/architecture/io-contracts.md',
                 'docs/README.md', 'docs/contributing/development.md',
                 'docs/planning/sprint-plan.md', 'docs/planning/implementation-checklist.md')
        for name in names:
            path = ROOT / name
            text = path.read_text()
            self.assertEqual(sum(line.startswith('```') for line in text.splitlines()) % 2, 0, name)
            for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)', text):
                if not link.startswith(('http:', 'https:', '#')):
                    self.assertTrue((path.parent / link.split('#')[0]).exists(), (name, link))
        sprint = (ROOT / 'docs/planning/sprint-plan.md').read_text()
        parents = re.findall(r'^- \[ \] \*\*(S\d-\d\d)', sprint, re.M)
        self.assertEqual(len(parents), 24)
        self.assertIn('S0-03', parents)
        self.assertIn('S1-02', parents)


if __name__ == '__main__':
    unittest.main()
