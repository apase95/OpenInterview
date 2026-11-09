# %%
"""Google OIDC, independent server-side identity. No dotenv loading at import.

Cookies hold opaque capabilities; PostgreSQL stores their keyed hashes.
Identity validation does not grant tenant or campaign access to domain routes.
Public failures use fixed codes rather than private provider exception details.
"""
import argparse
import asyncio
from dataclasses import dataclass
import hashlib
import hmac
import logging
import os
from pathlib import Path
import secrets
import time
from urllib.parse import urlsplit
import uuid

import httpx
import psycopg
from psycopg.rows import dict_row
from authlib.integrations.httpx_client import AsyncOAuth2Client
from authlib.jose import JsonWebToken
from authlib.oidc.core import CodeIDToken
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from starlette.concurrency import run_in_threadpool

ISSUER = 'https://accounts.google.com'
DISCOVERY = ISSUER + '/.well-known/openid-configuration'
AUTHORIZE = ISSUER + '/o/oauth2/v2/auth'
TOKEN = 'https://oauth2.googleapis.com/token'
JWKS = 'https://www.googleapis.com/oauth2/v3/certs'
MIGRATION = Path(__file__).with_name('migrations') / '002_auth.sql'
router = APIRouter(prefix='/auth')


# %%
# Redaction covers the expected Uvicorn argument shape, not all deployment logs.
class AuthAccessFilter(logging.Filter):
    """Uvicorn otherwise records authorization codes in callback query strings."""
    def filter(self, record):
        if isinstance(record.args, tuple) and len(record.args) == 5:
            client, method, path, version, status = record.args
            if isinstance(path, str) and path.split('?', 1)[0].startswith('/auth/'):
                record.args = (client, method, path.split('?', 1)[0], version, status)
        return True


logging.getLogger('uvicorn.access').addFilter(AuthAccessFilter())


# Keep secret-bearing settings out of their generated representation.
@dataclass(frozen=True, repr=False)
class Settings:
    client_id: str
    client_secret: str
    redirect: str
    origin: str
    secret: str
    secure: bool
    ttl: int

    @property
    def cookie(self):
        return '__Host-oi_session' if self.secure else 'oi_session_dev'

    @property
    def flow_cookie(self):
        return '__Host-oi_flow' if self.secure else 'oi_flow_dev'

    def digest(self, purpose, value):
        return hmac.new(self.secret.encode(), (purpose + ':' + value).encode(), hashlib.sha256).hexdigest()


# %%
# Require matching callback/frontend hosts and schemes for host-scoped cookies.
# Validation checks local configuration, not Google availability or credentials.
def settings():
    names = ('GOOGLE_OAUTH_CLIENT_ID', 'GOOGLE_OAUTH_CLIENT_SECRET',
             'GOOGLE_OAUTH_REDIRECT_URI', 'APP_ORIGIN', 'AUTH_SESSION_SECRET')
    values = [os.getenv(n, '') for n in names]
    if not all(values) or len(values[4]) < 32:
        raise ValueError('Auth configuration missing or invalid')
    dev = os.getenv('APP_ENV') == 'development'
    for value, callback in ((values[2], True), (values[3], False)):
        url = urlsplit(value)
        if (url.scheme not in ('https', 'http') or not url.hostname or url.username or url.password
                or url.query or url.fragment or '*' in url.netloc
                or url.path != ('/auth/google/callback' if callback else '')):
            raise ValueError('Auth URLs invalid')
        _ = url.port
        if url.scheme != 'https' and (not dev or url.hostname not in ('127.0.0.1', 'localhost', '::1')):
            raise ValueError('HTTPS required outside loopback development')
    # Callback and frontend share a host cookie, not a port. Cross-host is unsupported.
    if urlsplit(values[2]).hostname != urlsplit(values[3]).hostname:
        raise ValueError('Auth hosts must match')
    secure = urlsplit(values[3]).scheme == 'https'
    if secure != (urlsplit(values[2]).scheme == 'https'):
        raise ValueError('Auth schemes must match')
    ttl = int(os.getenv('AUTH_SESSION_TTL', '28800'))
    if not 300 <= ttl <= 86400:
        raise ValueError('Auth session TTL invalid')
    return Settings(*values, secure, ttl)


# Only fixed local destinations survive the login round trip.
def return_path(value):
    return value if value in ('/', '/roles') else '/'


# %%
# Open a timeout-bounded connection without provisioning a database or user.
def connect():
    names = ('DATABASE_HOST', 'DATABASE_PORT', 'DATABASE_NAME', 'DATABASE_USER', 'DATABASE_PASSWORD')
    if any(not os.getenv(n) for n in names):
        raise ValueError('Set all DATABASE_* fields, then run python -m backend.auth migrate')
    return psycopg.connect(host=os.environ[names[0]], port=os.environ[names[1]],
                          dbname=os.environ[names[2]], user=os.environ[names[3]],
                          password=os.environ[names[4]], connect_timeout=3,
                          options='-c search_path=public -c statement_timeout=3000 -c lock_timeout=3000',
                          row_factory=dict_row)


# Bind the recorded migration version to the exact SQL file bytes.
def checksum():
    return hashlib.sha256(MIGRATION.read_bytes()).hexdigest()


# Reject three admin flags and require the recorded checksum. This is not a full
# privilege audit; inherited grants and schema permissions still need review.
def check(connection):
    role = connection.execute('SELECT rolsuper OR rolcreatedb OR rolcreaterole AS admin FROM pg_roles WHERE rolname=current_user').fetchone()
    if not role or role['admin']:
        raise ValueError('Use a non-admin application DB role')
    row = connection.execute('SELECT sha256 FROM auth_migrations WHERE version=1').fetchone()
    if not row or row['sha256'] != checksum():
        raise ValueError('Run explicit auth migration; checksum must match')


# Serialize explicit migration attempts with a transaction-scoped advisory lock.
# A recorded version is reusable only if its source checksum still matches.
def migrate(connection):
    with connection.transaction():
        role = connection.execute('SELECT rolsuper OR rolcreatedb OR rolcreaterole AS admin FROM pg_roles WHERE rolname=current_user').fetchone()
        if not role or role['admin']:
            raise ValueError('Use a non-admin application DB role')
        connection.execute('SELECT pg_advisory_xact_lock(704193002)')
        connection.execute('CREATE TABLE IF NOT EXISTS auth_migrations (version integer PRIMARY KEY, sha256 text NOT NULL)')
        row = connection.execute('SELECT sha256 FROM auth_migrations WHERE version=1').fetchone()
        if row:
            if row['sha256'] != checksum():
                raise ValueError('Auth migration checksum mismatch')
            return False
        connection.execute(MIGRATION.read_text())
        connection.execute('INSERT INTO auth_migrations VALUES (1,%s)', (checksum(),))
        return True


# %%
# Each action owns a checked connection context. HTTP callers move this blocking
# work to a thread pool; no connection is shared between requests here.
class Store:
    def run(self, action):
        with connect() as c:
            check(c)
            return action(c)

    def create_flow(self, s, state, browser, nonce, verifier, target):
        """Store a ten-minute flow with hashed state/browser and server-only PKCE data."""
        def action(c):
            c.execute('DELETE FROM auth_flows WHERE expires_at <= now()')
            c.execute('DELETE FROM auth_sessions WHERE expires_at <= now()')
            c.execute("INSERT INTO auth_flows VALUES (%s,%s,%s,%s,%s,now()+interval '10 minutes')",
                      (s.digest('state', state), s.digest('browser', browser), nonce, verifier, target))
        self.run(action)

    def consume(self, s, state, browser):
        """Delete and return one unexpired browser-bound flow to prevent reuse."""
        return self.run(lambda c: c.execute(
            'DELETE FROM auth_flows WHERE state_hash=%s AND browser_hash=%s AND expires_at>now() RETURNING nonce,verifier,return_to',
            (s.digest('state', state), s.digest('browser', browser))).fetchone())

    def login(self, s, claims, token, old):
        """Upsert issuer/subject identity and replace the presented old session."""
        def action(c):
            account = c.execute('''INSERT INTO auth_accounts (id,issuer,subject,email,name)
                VALUES (%s,%s,%s,%s,%s) ON CONFLICT (issuer,subject)
                DO UPDATE SET email=EXCLUDED.email,name=EXCLUDED.name RETURNING id''',
                (uuid.uuid4(), ISSUER, claims['sub'], claims['email'], claims.get('name'))).fetchone()
            if old:
                c.execute('DELETE FROM auth_sessions WHERE token_hash=%s', (s.digest('session', old),))
            c.execute("INSERT INTO auth_sessions VALUES (%s,%s,now()+%s*interval '1 second')",
                      (s.digest('session', token), account['id'], s.ttl))
        self.run(action)

    def session(self, s, token):
        """Resolve an unexpired session and current account role, or return no row."""
        row = self.run(lambda c: c.execute('''SELECT a.id,a.email,a.name,a.role FROM auth_sessions s
            JOIN auth_accounts a ON a.id=s.account_id WHERE s.token_hash=%s AND s.expires_at>now()''',
            (s.digest('session', token),)).fetchone())
        if row:
            row['id'] = str(row['id'])
        return row

    def logout(self, s, token):
        """Revoke only the supplied session hash."""
        self.run(lambda c: c.execute('DELETE FROM auth_sessions WHERE token_hash=%s', (s.digest('session', token),)))


store = Store()


# %%
class Provider:
    """Fixed endpoints, bounded per-worker metadata/key cache, no token persistence."""
    def __init__(self):
        self.cache = {}
        self.lock = asyncio.Lock()

    async def document(self, url):
        async with self.lock:
            cached = self.cache.get(url)
            if cached and cached[0] > time.monotonic():
                return cached[1]
            async with httpx.AsyncClient(timeout=5, follow_redirects=False, trust_env=False) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                ttl = 300
                for item in response.headers.get('cache-control', '').split(','):
                    if item.strip().startswith('max-age='):
                        ttl = min(3600, max(0, int(item.strip().split('=')[1])))
                if 'no-store' in response.headers.get('cache-control', ''):
                    ttl = 0
                self.cache[url] = (time.monotonic() + ttl, data)
                return data

    async def metadata(self):
        data = await self.document(DISCOVERY)
        if (data.get('issuer') != ISSUER or data.get('authorization_endpoint') != AUTHORIZE
                or data.get('token_endpoint') != TOKEN or data.get('jwks_uri') != JWKS):
            raise ValueError('Unexpected OIDC metadata')
        return data

    def client(self, s):
        return AsyncOAuth2Client(s.client_id, s.client_secret, redirect_uri=s.redirect,
                                scope='openid email profile', code_challenge_method='S256',
                                token_endpoint_auth_method='client_secret_post', timeout=5,
                                follow_redirects=False, trust_env=False)

    async def authorization(self, s, state, nonce, verifier):
        await self.metadata()
        async with self.client(s) as client:
            url, _ = client.create_authorization_url(AUTHORIZE, state=state, nonce=nonce, code_verifier=verifier)
            return url

    async def identity(self, s, code, flow):
        """Exchange with PKCE and validate signature, claims, nonce and verified email.

        The caller must first consume the matching browser-bound flow. Provider
        access and refresh tokens are not persisted by this adapter.
        """
        await self.metadata()
        async with self.client(s) as client:
            token = await client.fetch_token(TOKEN, code=code, grant_type='authorization_code', code_verifier=flow['verifier'])
        keys = await self.document(JWKS)
        claims = JsonWebToken(['RS256']).decode(token['id_token'], keys, claims_cls=CodeIDToken,
            claims_options={'iss': {'essential': True, 'value': ISSUER},
                            'aud': {'essential': True, 'value': s.client_id},
                            'exp': {'essential': True}, 'sub': {'essential': True},
                            'iat': {'essential': True}},
            claims_params={'nonce': flow['nonce'], 'client_id': s.client_id,
                           'access_token': token.get('access_token')})
        claims.validate(leeway=30)
        if (claims.get('email_verified') is not True or not isinstance(claims.get('email'), str)
                or not 1 <= len(claims['email']) <= 320 or not isinstance(claims.get('sub'), str)
                or not 1 <= len(claims['sub']) <= 255
                or ('name' in claims and (not isinstance(claims['name'], str) or len(claims['name']) > 512))):
            raise ValueError('Invalid identity')
        return claims


provider = Provider()


# %%
# Host-scoped HttpOnly cookies use Secure for the HTTPS configuration.
def cookie(response, s, name, value, age):
    response.set_cookie(name, value, max_age=age, httponly=True, secure=s.secure, samesite='lax', path='/')


# Clear the flow capability and redirect using a caller-selected fixed error code.
def failure(s, error):
    response = RedirectResponse(s.origin + '/login?error=' + error, status_code=303)
    cookie(response, s, s.flow_cookie, '', 0)
    return response


# %%
# Generate separate state, browser binding, nonce and PKCE verifier values.
# Persist the flow before redirecting so a failed store cannot start a usable flow.
@router.get('/google/start')
async def start(request: Request):
    s = request.state.auth
    state, browser, nonce, verifier = (secrets.token_urlsafe(32) for _ in range(4))
    target = return_path(request.query_params.get('return_to', '/'))
    try:
        location = await provider.authorization(s, state, nonce, verifier)
    except Exception:
        return failure(s, 'provider_unavailable')
    try:
        await run_in_threadpool(store.create_flow, s, state, browser, nonce, verifier, target)
    except Exception:
        return failure(s, 'service_unavailable')
    response = RedirectResponse(location, status_code=303)
    cookie(response, s, s.flow_cookie, browser, 600)
    return response


# Consume the one-use flow before provider exchange, including denial callbacks.
# Duplicate query keys fail; verified identity does not select an application role.
@router.get('/google/callback')
async def callback(request: Request):
    s = request.state.auth
    params = request.query_params
    state, browser = params.get('state', ''), request.cookies.get(s.flow_cookie, '')
    if (not state or not browser or len(state) > 128 or len(browser) > 128
            or any(len(params.getlist(key)) != 1 for key in params)):
        return failure(s, 'state_invalid')
    try:
        flow = await run_in_threadpool(store.consume, s, state, browser)
    except Exception:
        return failure(s, 'service_unavailable')
    if not flow:
        return failure(s, 'state_invalid')
    if params.get('error'):
        return failure(s, 'access_denied' if params['error'] == 'access_denied' else 'identity_invalid')
    code = params.get('code', '')
    if not code or len(code) > 4096:
        return failure(s, 'identity_invalid')
    try:
        claims = await provider.identity(s, code, flow)
    except httpx.HTTPError:
        return failure(s, 'provider_unavailable')
    except Exception:
        return failure(s, 'identity_invalid')
    token = secrets.token_urlsafe(32)
    try:
        await run_in_threadpool(store.login, s, claims, token, request.cookies.get(s.cookie, ''))
    except Exception:
        return failure(s, 'service_unavailable')
    response = RedirectResponse(s.origin + return_path(flow['return_to']), status_code=303)
    cookie(response, s, s.cookie, token, s.ttl)
    cookie(response, s, s.flow_cookie, '', 0)
    return response


# Return current identity and a session-bound CSRF digest, not the cookie token.
@router.get('/me')
async def me(request: Request):
    s = request.state.auth
    token = request.cookies.get(s.cookie, '')
    if not token or len(token) > 128:
        return JSONResponse({'detail': 'unauthenticated'}, status_code=401)
    try:
        user = await run_in_threadpool(store.session, s, token)
    except Exception:
        return JSONResponse({'detail': 'service_unavailable'}, status_code=503)
    if not user:
        return JSONResponse({'detail': 'unauthenticated'}, status_code=401)
    return JSONResponse({'user': user, 'csrf_token': s.digest('csrf', token)})


# Require exact Origin and the session-bound CSRF header before revocation.
# Keep the cookie on database failure so the browser can retry.
@router.post('/logout')
async def logout(request: Request):
    s = request.state.auth
    token = request.cookies.get(s.cookie, '')
    csrf = request.headers.get('x-csrf-token', '')
    if (request.headers.get('origin') != s.origin or not token or len(token) > 128
            or not hmac.compare_digest(csrf.encode(), s.digest('csrf', token).encode())):
        return JSONResponse({'detail': 'csrf_invalid'}, status_code=403)
    try:
        await run_in_threadpool(store.logout, s, token)
    except Exception:
        return JSONResponse({'detail': 'service_unavailable'}, status_code=503)
    response = Response(status_code=204)
    cookie(response, s, s.cookie, '', 0)
    return response


# %%
# Settings and privacy headers apply only to /auth/ paths. This middleware does
# not authenticate or authorize unrelated application routes.
async def boundary(request, call_next):
    if not request.url.path.startswith('/auth/'):
        return await call_next(request)
    try:
        request.state.auth = settings()
    except (ValueError, TypeError):
        response = JSONResponse({'detail': 'auth_unavailable'}, status_code=503)
    else:
        try:
            response = await call_next(request)
        except Exception:
            response = JSONResponse({'detail': 'service_unavailable'}, status_code=503)
    response.headers.update({'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer'})
    return response


# %%
# Explicit setup never provisions roles or contacts Google. Production migration
# needs extra confirmation; dotenv loading happens only when requested by CLI.
def main():
    parser = argparse.ArgumentParser(description='Explicit independent auth migration/check; never provisions DB/users.')
    parser.add_argument('command', choices=('migrate', 'check'))
    parser.add_argument('--env-file', help='Load only this explicitly requested dotenv file')
    parser.add_argument('--confirm-production', action='store_true')
    args = parser.parse_args()
    if args.env_file:
        from dotenv import load_dotenv
        load_dotenv(args.env_file, override=False)
    try:
        if args.command == 'check':
            settings()
        if args.command == 'migrate' and os.getenv('APP_ENV') not in ('development', 'test') and not args.confirm_production:
            raise ValueError('Explicit production confirmation required')
        with connect() as c:
            result = migrate(c) if args.command == 'migrate' else check(c)
        print(f'auth {args.command}: verified; changes={int(bool(result))}')
    except Exception:
        parser.exit(1, 'Auth setup unavailable: check Google OAuth, APP_ORIGIN and AUTH_SESSION_SECRET; set all DATABASE_* fields, use a non-admin app role with schema CREATE permission, apply/check auth migration checksum; production migration needs --confirm-production. Details withheld.\n')


if __name__ == '__main__':
    main()
