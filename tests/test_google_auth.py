# %%
"""Offline auth checks; run exactly: python -m unittest tests.test_google_auth.

Routes use a memory DB stand-in and provider identity mocks. Signed-token checks
use real validation with an HTTP mock transport, not live Google OAuth or SQL.
"""
import os
import asyncio
import base64
import hashlib
import logging
import secrets
import time
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from types import SimpleNamespace

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client
from authlib.jose import JsonWebKey, JsonWebToken

from fastapi.testclient import TestClient
from backend.api import app
from backend import auth


ENV = dict(APP_ENV='development', APP_ORIGIN='http://127.0.0.1:3000',
           GOOGLE_OAUTH_REDIRECT_URI='http://127.0.0.1:8000/auth/google/callback',
           GOOGLE_OAUTH_CLIENT_ID='synthetic-client', GOOGLE_OAUTH_CLIENT_SECRET='synthetic-secret',
           AUTH_SESSION_SECRET='synthetic-session-secret-at-least-32-characters')


# %%
class MemoryStore:
    """External DB stand-in only; real SQL covered by verify_auth.py."""
    def __init__(self):
        self.flows, self.sessions = {}, {}

    def create_flow(self, s, state, browser, nonce, verifier, target):
        self.flows[state] = dict(browser=browser, nonce=nonce, verifier=verifier, return_to=target)

    def consume(self, s, state, browser):
        flow = self.flows.get(state)
        return self.flows.pop(state) if flow and flow['browser'] == browser else None

    def login(self, s, claims, token, old):
        self.sessions.pop(old, None)
        self.sessions[token] = dict(id='synthetic-account', email=claims['email'], name=claims.get('name'), role='candidate')

    def session(self, s, token):
        return self.sessions.get(token)

    def logout(self, s, token):
        self.sessions.pop(token, None)


# %%
class AuthSmoke(unittest.TestCase):
    """Check auth trust boundaries, replay protection and sanitized failures."""
    def test_cli_check_validates_settings_before_database(self):
        """Mock DB access and require settings validation before a connection."""
        with patch.dict(os.environ, {}, clear=True), patch('sys.argv', ['auth', 'check']), patch.object(auth, 'connect') as connect:
            with self.assertRaises(SystemExit):
                auth.main()
            connect.assert_not_called()
        with patch.dict(os.environ, ENV, clear=True), patch('sys.argv', ['auth', 'check']), patch.object(auth, 'connect') as connect, patch.object(auth, 'check') as check:
            auth.main()
            check.assert_called_once_with(connect.return_value.__enter__.return_value)

    def test_disabled_health_and_auth(self):
        """Keep liveness available while unconfigured auth fails closed."""
        with patch.dict(os.environ, {}, clear=True), TestClient(app) as client:
            self.assertEqual(client.get('/health').status_code, 200)
            self.assertEqual(client.get('/auth/me').status_code, 503)

    def test_config_and_return_boundary(self):
        """Reject unsafe return targets and insecure production settings."""
        with patch.dict(os.environ, ENV, clear=True):
            settings = auth.settings()
            self.assertEqual(settings.cookie, 'oi_session_dev')
            self.assertEqual(auth.return_path('/roles'), '/roles')
            for value in ('//evil.test', 'https://evil.test', '/%2f/evil', '/roles?next=evil'):
                self.assertEqual(auth.return_path(value), '/')
        with patch.dict(os.environ, {**ENV, 'APP_ENV': 'production'}, clear=True):
            with self.assertRaises(ValueError):
                auth.settings()

    def test_route_flow_rotation_replay_and_logout(self):
        """Use fake identity/storage to check PKCE, browser binding and CSRF logout."""
        from unittest.mock import AsyncMock
        memory = MemoryStore()
        async def authorize(s, state, nonce, verifier):
            async with auth.provider.client(s) as oauth:
                return oauth.create_authorization_url(auth.AUTHORIZE, state=state, nonce=nonce, code_verifier=verifier)[0]
        with patch.dict(os.environ, ENV, clear=True), patch.object(auth, 'store', memory), \
                patch.object(auth.provider, 'authorization', side_effect=authorize), \
                patch.object(auth.provider, 'identity', new=AsyncMock(return_value={'sub': '1', 'email': 'candidate@example.test'})), \
                TestClient(app) as client:
            self.assertEqual(client.get('/auth/me').status_code, 401)
            def begin(target='/roles'):
                response = client.get('/auth/google/start', params={'return_to': target, 'intent': 'signup'}, follow_redirects=False)
                self.assertEqual(response.status_code, 303)
                self.assertIn('HttpOnly', response.headers['set-cookie'])
                query = parse_qs(urlsplit(response.headers['location']).query)
                flow = memory.flows[query['state'][0]]
                expected = base64.urlsafe_b64encode(hashlib.sha256(flow['verifier'].encode()).digest()).rstrip(b'=').decode()
                self.assertEqual(query['code_challenge'], [expected])
                self.assertEqual(query['code_challenge_method'], ['S256'])
                self.assertEqual(query['scope'], ['openid email profile'])
                self.assertNotIn(flow['verifier'], response.headers['location'])
                return query['state'][0]
            state = begin('//evil.test')
            # Another browser cannot consume the flow.
            with TestClient(app) as other:
                response = other.get('/auth/google/callback', params={'state': state, 'code': 'synthetic'}, follow_redirects=False)
                self.assertTrue(response.headers['location'].endswith('error=state_invalid'))
            response = client.get('/auth/google/callback', params={'state': state, 'code': 'synthetic'}, follow_redirects=False)
            self.assertEqual(response.headers['location'], ENV['APP_ORIGIN'] + '/')
            old = client.cookies.get('oi_session_dev')
            self.assertEqual(client.get('/auth/me').json()['user']['role'], 'candidate')
            response = client.get('/auth/google/callback', params={'state': state, 'code': 'synthetic'}, follow_redirects=False)
            self.assertTrue(response.headers['location'].endswith('error=state_invalid'))
            state = begin()
            client.get('/auth/google/callback', params={'state': state, 'code': 'synthetic'}, follow_redirects=False)
            self.assertNotEqual(old, client.cookies.get('oi_session_dev'))
            self.assertNotIn(old, memory.sessions)
            csrf = client.get('/auth/me').json()['csrf_token']
            for headers in ({}, {'Origin': 'https://evil.test', 'X-CSRF-Token': csrf},
                            {'Origin': ENV['APP_ORIGIN'], 'X-CSRF-Token': 'bad'}):
                self.assertEqual(client.post('/auth/logout', headers=headers).status_code, 403)
            self.assertEqual(client.post('/auth/logout', headers={'Origin': ENV['APP_ORIGIN'], 'X-CSRF-Token': csrf}).status_code, 204)
            self.assertEqual(client.get('/auth/me').status_code, 401)
            state = begin()
            response = client.get('/auth/google/callback', params={'state': state, 'error': 'access_denied', 'error_description': 'PRIVATE'}, follow_redirects=False)
            self.assertTrue(response.headers['location'].endswith('error=access_denied'))
            self.assertNotIn('PRIVATE', str(response.headers))

    def test_signed_oidc_through_mock_transport(self):
        """Validate locally signed tokens and bad claims over fake discovery/JWKS HTTP."""
        key = JsonWebKey.generate_key('RSA', 2048, is_private=True, options={'kid': 'offline'})
        wrong_key = JsonWebKey.generate_key('RSA', 2048, is_private=True, options={'kid': 'offline'})
        with patch.dict(os.environ, ENV, clear=True):
            s = auth.settings()
        flow = {'nonce': secrets.token_urlsafe(32), 'verifier': secrets.token_urlsafe(32)}
        base = dict(iss=auth.ISSUER, sub='google-subject', aud=s.client_id, exp=int(time.time())+300,
                    iat=int(time.time()), nonce=flow['nonce'], email='candidate@example.test', email_verified=True)
        async def check(changes=None, signing_key=key, algorithm='RS256', network=False):
            claims = {**base, **(changes or {})}
            signed = JsonWebToken([algorithm]).encode({'alg': algorithm, 'kid': 'offline'}, claims, signing_key).decode()
            def handler(request):
                if network:
                    raise httpx.ConnectError('synthetic-private-provider-error', request=request)
                if str(request.url) == auth.TOKEN:
                    body = parse_qs(request.content.decode())
                    self.assertEqual(body['code_verifier'], [flow['verifier']])
                    self.assertEqual(body['redirect_uri'], [s.redirect])
                    self.assertNotIn('access_type', body)
                    return httpx.Response(200, json={'access_token': 'synthetic-unused', 'token_type': 'Bearer', 'id_token': signed})
                if str(request.url) == auth.JWKS:
                    return httpx.Response(200, json={'keys': [key.as_dict(is_private=False)]})
                self.assertEqual(str(request.url), auth.DISCOVERY)
                return httpx.Response(200, json={'issuer': auth.ISSUER, 'authorization_endpoint': auth.AUTHORIZE,
                                               'token_endpoint': auth.TOKEN, 'jwks_uri': auth.JWKS})
            transport = httpx.MockTransport(handler)
            p = auth.Provider()
            original_http = httpx.AsyncClient
            with patch.object(auth, 'httpx', SimpleNamespace(AsyncClient=lambda **kw: original_http(transport=transport, **kw))), \
                    patch.object(p, 'client', side_effect=lambda cfg: AsyncOAuth2Client(
                        cfg.client_id, cfg.client_secret, redirect_uri=cfg.redirect,
                        token_endpoint_auth_method='client_secret_post', transport=transport, timeout=5)):
                return await p.identity(s, 'synthetic-code', flow)
        self.assertEqual(asyncio.run(check())['sub'], base['sub'])
        for changes in ({'iss': 'https://evil.test'}, {'aud': 'other'}, {'nonce': 'wrong'},
                        {'exp': int(time.time())-60}, {'email_verified': False}, {'email_verified': 'true'},
                        {'sub': ''}, {'azp': 'other'}):
            with self.subTest(claims=list(changes)), self.assertRaises(Exception):
                asyncio.run(check(changes))
        with self.assertRaises(Exception):
            asyncio.run(check(signing_key=wrong_key))
        with self.assertRaises(Exception):
            asyncio.run(check(algorithm='RS512'))
        with self.assertRaises(httpx.ConnectError):
            asyncio.run(check(network=True))

    def test_hash_separation_and_access_log(self):
        """Separate token hash purposes and remove callback secrets from access logs."""
        with patch.dict(os.environ, ENV, clear=True):
            s = auth.settings()
        token = secrets.token_urlsafe(32)
        self.assertNotEqual(s.digest('session', token), token)
        self.assertNotEqual(s.digest('session', token), s.digest('csrf', token))
        record = logging.LogRecord('uvicorn.access', logging.INFO, '', 0, '%s %s %s %s %s',
                                   ('127.0.0.1', 'GET', '/auth/google/callback?code=PRIVATE&state=PRIVATE', '1.1', 303), None)
        auth.AuthAccessFilter().filter(record)
        self.assertNotIn('PRIVATE', record.getMessage())

    def test_faults_fail_closed_and_production_cookie(self):
        """Mock provider/DB faults and check safe errors and secure cookie attributes."""
        from unittest.mock import AsyncMock
        with patch.dict(os.environ, ENV, clear=True), TestClient(app) as client:
            with patch.object(auth.provider, 'authorization', new=AsyncMock(side_effect=httpx.ConnectError('PRIVATE'))):
                response = client.get('/auth/google/start', follow_redirects=False)
                self.assertTrue(response.headers['location'].endswith('error=provider_unavailable'))
                self.assertNotIn('PRIVATE', str(response.headers))
            with patch.object(auth.provider, 'authorization', new=AsyncMock(return_value='https://accounts.google.com/')), \
                    patch.object(auth.store, 'create_flow', side_effect=RuntimeError('PRIVATE')):
                response = client.get('/auth/google/start', follow_redirects=False)
                self.assertTrue(response.headers['location'].endswith('error=service_unavailable'))
            client.cookies.set('oi_session_dev', 'synthetic-session')
            with patch.object(auth.store, 'session', side_effect=RuntimeError('PRIVATE')):
                response = client.get('/auth/me')
                self.assertEqual(response.json(), {'detail': 'service_unavailable'})
                self.assertEqual(response.status_code, 503)
            csrf = auth.settings().digest('csrf', 'synthetic-session')
            with patch.object(auth.store, 'logout', side_effect=RuntimeError('PRIVATE')):
                response = client.post('/auth/logout', headers={'Origin': ENV['APP_ORIGIN'], 'X-CSRF-Token': csrf})
                self.assertEqual(response.status_code, 503)
                self.assertNotIn('set-cookie', response.headers)
        production = {**ENV, 'APP_ENV': 'production', 'APP_ORIGIN': 'https://example.test',
                      'GOOGLE_OAUTH_REDIRECT_URI': 'https://example.test/auth/google/callback'}
        with patch.dict(os.environ, production, clear=True):
            s = auth.settings()
            response = auth.Response()
            auth.cookie(response, s, s.cookie, 'synthetic', s.ttl)
            header = response.headers['set-cookie']
            for value in ('__Host-oi_session=', 'Secure', 'HttpOnly', 'SameSite=lax', 'Path=/'):
                self.assertIn(value, header)
            self.assertNotIn('Domain=', header)


if __name__ == '__main__':
    unittest.main()
