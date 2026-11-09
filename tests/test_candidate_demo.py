# %%
"""Check synthetic demo routes through an in-process API client.

Environment flags and expiry time are controlled here. No browser, provider
session or real candidate interview is exercised.
"""
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend.api import app


# %%
class CandidateDemoTests(unittest.TestCase):
    """Check demo lifecycle idempotency and local development access gates."""
    def setUp(self):
        """Enable demo mode temporarily and create a loopback-origin client."""
        self.env = patch.dict(os.environ, {'APP_ENV': 'development', 'CANDIDATE_DEMO_ENABLED': 'true'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.client = TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 1234))
        self.headers = {'Origin': 'http://127.0.0.1:3000'}

    def room(self):
        """Create a synthetic frontend room through the demo route."""
        return self.client.post('/demo/rooms', headers=self.headers, json={'role_id': 'frontend'})

    def test_lifecycle(self):
        """Require stable session creation and repeated end responses."""
        self.assertEqual(self.client.get('/demo/roles', headers=self.headers).status_code, 200)
        room = self.room().json()
        path = '/demo/rooms/' + room['room_id']
        self.assertEqual(self.client.get(path, headers=self.headers).status_code, 200)
        session = self.client.post(path + '/sessions', headers=self.headers, json={'acknowledged': True}).json()
        self.assertEqual(session, self.client.post(path + '/sessions', headers=self.headers, json={'acknowledged': True}).json())
        path = '/demo/sessions/' + session['session_id']
        self.assertEqual(self.client.get(path, headers=self.headers).json()['status'], 'active')
        ended = self.client.post(path + '/end', headers=self.headers)
        self.assertEqual(ended.json()['status'], 'ended')
        self.assertEqual(ended.json(), self.client.post(path + '/end', headers=self.headers).json())

    def test_validation_and_boundary(self):
        """Reject invalid consent, origins, expired rooms and production access."""
        room = self.room().json()
        path = '/demo/rooms/' + room['room_id'] + '/sessions'
        for body in ({'acknowledged': False}, {'acknowledged': 1}, {'acknowledged': True, 'consent': True}, []):
            self.assertEqual(self.client.post(path, headers=self.headers, json=body).status_code, 422)
        self.assertEqual(self.client.post('/demo/rooms', headers=self.headers, json={'role_id': 'private'}).status_code, 422)
        self.assertEqual(self.client.get('/demo/sessions/unknown', headers=self.headers).status_code, 404)
        self.assertEqual(self.client.get('/demo/roles', headers={'Origin': 'https://evil.example'}).status_code, 403)
        with patch('backend.api.time.time', return_value=room['expires_at'] + 1):
            self.assertEqual(self.client.post(path, headers=self.headers, json={'acknowledged': True}).status_code, 404)
        with patch.dict(os.environ, {'APP_ENV': 'production'}):
            self.assertEqual(self.client.get('/demo/roles', headers=self.headers).status_code, 404)
