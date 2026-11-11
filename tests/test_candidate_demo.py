"""Routing authorization checks with offline identity/repository stand-ins."""
import os
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.api import app
from backend import auth, workspace
from tests.test_google_auth import ENV
from tests.workspace_fixture import MemoryAuth, MemoryWorkspace, USERS

class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.repo = MemoryWorkspace()
        for patcher in (patch.dict(os.environ, ENV, clear=True), patch.object(auth, 'store', MemoryAuth()), patch.object(workspace, 'store', self.repo)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def login(self, identity='candidate-a'):
        self.client.cookies.set('oi_session_dev', identity)
        return {'Origin': ENV['APP_ORIGIN'], 'X-CSRF-Token': auth.settings().digest('csrf', identity)}

    def test_auth_required_on_every_endpoint(self):
        for path in ('/roles', '/rooms', '/rooms/room-one', '/sessions/session-one', '/hr', '/admin'):
            self.assertEqual(self.client.get('/workspace'+path).status_code, 401, path)
        for path in ('/rooms/room-one/sessions', '/sessions/session-one/end'):
            self.assertEqual(self.client.post('/workspace'+path, json={'acknowledged': True}).status_code, 401)
        self.client.cookies.set('oi_session_dev', 'forged-cookie')
        self.assertEqual(self.client.get('/workspace/rooms').status_code, 401)

    def test_identity_and_csrf_and_idempotency(self):
        headers = self.login()
        self.assertEqual(len(self.client.get('/workspace/rooms').json()), 1)
        path='/workspace/rooms/room-one/sessions'
        for h in ({}, {'Origin': 'https://evil.test', 'X-CSRF-Token': headers['X-CSRF-Token']}, {**headers, 'X-CSRF-Token': 'invalid'}):
            self.assertEqual(self.client.post(path, headers=h, json={'acknowledged': True}).status_code, 403)
        for value in ({'acknowledged': False}, {'acknowledged': 1}, {'acknowledged': True, 'candidate_id': USERS['candidate-a']['id']}, []):
            self.assertEqual(self.client.post(path, headers=headers, json=value).status_code, 422)
        first = self.client.post(path, headers=headers, json={'acknowledged': True}).json()
        self.assertEqual(first, self.client.post(path, headers=headers, json={'acknowledged': True}).json())
        self.assertEqual(self.client.get('/workspace/sessions/session-one').json(), first)
        other = self.login('candidate-b')
        self.assertEqual(self.client.get('/workspace/rooms').json(), [])
        for target in ('/rooms/room-one','/rooms/unknown','/sessions/session-one'):
            self.assertEqual(self.client.get('/workspace'+target).status_code,404)
        self.assertEqual(self.client.post(path,headers=other,json={'acknowledged':True}).status_code,404)
        self.assertEqual(self.client.post('/workspace/sessions/session-one/end',headers=other).status_code,404)
        headers = self.login()
        self.repo.assigned['room-one']['revoked_at'] = 'revoked'
        self.assertEqual(self.client.get('/workspace/sessions/session-one').status_code,404)
        ended = self.client.post('/workspace/sessions/session-one/end',headers=headers).json()
        self.assertIsNotNone(ended['ended_at'])
        self.assertEqual(ended,self.client.post('/workspace/sessions/session-one/end',headers=headers).json())

    def test_schedule_grants_and_removed_capabilities(self):
        headers=self.login()
        self.repo.assigned['room-one']['ready']=False
        self.assertEqual(self.client.post('/workspace/rooms/room-one/sessions',headers=headers,json={'acknowledged':True}).status_code,409)
        for path in ('/hr','/admin'):
            self.assertEqual(self.client.get('/workspace'+path).status_code,403)
        self.login('hr')
        self.assertEqual(self.client.get('/workspace/hr').status_code,200)
        self.assertEqual(self.client.get('/workspace/admin').status_code,403)
        USERS['hr']['grants'][0]['campaign_id']='another-campaign'
        try: self.assertEqual(self.client.get('/workspace/hr').json()['rooms'],[])
        finally: USERS['hr']['grants'][0]['campaign_id']='web'
        self.login('admin')
        self.assertEqual(self.client.get('/workspace/admin').status_code,200)
        self.assertEqual(self.client.get('/workspace/hr').status_code,403)
        self.assertEqual(self.client.get('/demo/roles').status_code,404)
        self.assertEqual(self.client.post('/demo/rooms',json={'role_id':'frontend'}).status_code,404)
        self.assertEqual(self.client.post('/workspace/rooms/room-one/sessions',content='x'*2049).status_code,413)
        self.assertEqual(self.client.get('/workspace/admin').headers['cache-control'],'no-store')

    def test_return_destinations_and_errors(self):
        from unittest.mock import AsyncMock
        for path in ('/rooms/room-one','/sessions/session-one/interview','/hr','/admin'):
            self.assertEqual(auth.return_path(path),path)
        for path in ('//evil.test','/rooms/%2fattack','/rooms/abc?x=1','/rooms/abc#x','/rooms/../admin','/rooms/abc\\admin','/rooms/abc\n','/sessions/abc','/login'):
            self.assertEqual(auth.return_path(path),'/')
        with patch.object(auth.provider,'authorization',new=AsyncMock(side_effect=RuntimeError('PRIVATE'))):
            result=self.client.get('/auth/google/start?return_to=/rooms/room-one',follow_redirects=False)
            self.assertIn('return_to=/rooms/room-one',result.headers['location'])
            self.assertNotIn('PRIVATE',str(result.headers))
        with patch.object(self.repo,'rooms',side_effect=RuntimeError('PRIVATE')):
            self.login()
            result=self.client.get('/workspace/rooms')
            self.assertEqual(result.status_code,503)
            self.assertNotIn('PRIVATE',result.text)
