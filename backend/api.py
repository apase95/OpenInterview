# %%
"""Serve health probes and opt-in local demo and voice routes.

Demo capabilities contain synthetic, process-local state. Voice uses remote room
leases, but its lock and rate counter remain local to each process. The auth
router is independent; specified v1 domain operations are not mounted here.
"""
import asyncio
from collections import deque
from contextlib import asynccontextmanager, suppress
from datetime import timedelta
import hmac
import ipaddress
import json
import os
import secrets
import time
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from backend.database import ping

AGENT_NAME = 'local-voice-test'
PREFIX = 'local_voice_'
voice_lock = asyncio.Lock()
attempts = deque()


# %%
# Validate the development gate, loopback origins and bounded lease settings.
# This checks configuration shape, not whether remote credentials work.
def voice_settings():
    if os.getenv('LOCAL_VOICE_ENABLED') != 'true' or os.getenv('APP_ENV') != 'development':
        raise HTTPException(404, 'Not found')
    secret = os.getenv('LOCAL_VOICE_SECRET', '')
    origins = os.getenv('LOCAL_VOICE_ORIGINS', '').split(',')
    try:
        for origin in origins:
            url = urlsplit(origin)
            if (url.scheme not in ('http', 'https') or url.hostname not in ('localhost', '127.0.0.1', '::1')
                    or url.username or url.password or url.path or url.query or url.fragment or not url.port):
                raise ValueError()
        ttl = int(os.getenv('LOCAL_VOICE_TOKEN_TTL', '60'))
        duration = int(os.getenv('LOCAL_VOICE_DURATION', '300'))
        limit = int(os.getenv('LOCAL_VOICE_MAX_SESSIONS', '1'))
        if not (15 <= ttl <= 120 and ttl <= duration <= 600 and 1 <= limit <= 3):
            raise ValueError()
        credentials = [os.getenv(n, '') for n in ('LIVEKIT_URL', 'LIVEKIT_API_KEY', 'LIVEKIT_API_SECRET')]
        if len(secret) < 32 or secret in credentials or not all(credentials):
            raise ValueError()
    except ValueError:
        raise HTTPException(503, 'Local voice configuration invalid') from None
    return secret, origins, ttl, duration, limit


# Callers own this short-timeout client and must close it after remote operations.
def voice_api():
    import aiohttp
    from livekit.api import LiveKitAPI
    return LiveKitAPI(os.environ['LIVEKIT_URL'], os.environ['LIVEKIT_API_KEY'],
                      os.environ['LIVEKIT_API_SECRET'], timeout=aiohttp.ClientTimeout(total=5))


# Limit the JWT to one room and microphone publishing, without agent management.
def voice_token(room, identity, ttl):
    from livekit.api import AccessToken, VideoGrants
    return (AccessToken(os.environ['LIVEKIT_API_KEY'], os.environ['LIVEKIT_API_SECRET'])
            .with_identity(identity).with_ttl(timedelta(seconds=ttl))
            .with_grants(VideoGrants(room_join=True, room=room, can_publish=True,
                                     can_subscribe=True, can_publish_data=False,
                                     can_publish_sources=['microphone'], can_update_own_metadata=False,
                                     can_manage_agent_session=False)).to_jwt())


# Cleanup failures propagate so issuance cannot assume uncertain capacity is free.
# Only prefixed rooms are managed; their metadata must contain a valid lease.
async def clean_rooms(client):
    """Room metadata is the lease; retain ended reservations until JWT expiry."""
    from livekit import api
    rooms = (await client.room.list_rooms(api.ListRoomsRequest())).rooms
    remaining = []
    for room in rooms:
        if not room.name.startswith(PREFIX):
            continue
        lease = json.loads(room.metadata)
        if time.time() >= lease['deadline']:
            await client.room.delete_room(api.DeleteRoomRequest(room=room.name))
        else:
            if lease.get('ended'):
                for dispatch in await client.agent_dispatch.list_dispatch(room.name):
                    await client.agent_dispatch.delete_dispatch(dispatch.id, room.name)
                participants = await client.room.list_participants(api.ListParticipantsRequest(room=room.name))
                for participant in participants.participants:
                    await client.room.remove_participant(api.RoomParticipantIdentity(
                        room=room.name, identity=participant.identity))
            remaining.append(room)
    return remaining


# %%
# Best-effort cleanup supplements mandatory reconciliation during issuance.
async def reap_voice():
    while True:
        await asyncio.sleep(1)
        try:
            voice_settings()
            async with voice_lock:
                client = voice_api()
                try:
                    await clean_rooms(client)
                finally:
                    await client.aclose()
        except Exception:
            # No provider exception text: it can contain credentials or private data.
            # Issuance also reconciles leases and fails closed on cleanup failure.
            pass


# Own the optional reaper task and cancel it on application shutdown.
@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(reap_voice()) if os.getenv('LOCAL_VOICE_ENABLED') == 'true' else None
    try:
        yield
    finally:
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


# %%
app = FastAPI(lifespan=lifespan)
from backend.auth import router as auth_router, boundary as auth_boundary
app.include_router(auth_router)
app.middleware('http')(auth_boundary)

# Synthetic, process-local capabilities only. Never used by voice or v1 routes.
demo_rooms = {}
demo_sessions = {}
DEMO_ROLES = [{'role_id': key, 'name': name} for key, name in (
    ('ba', 'Business Analyst'), ('devops', 'DevOps'), ('fullstack', 'Fullstack'),
    ('frontend', 'Frontend'), ('backend', 'Backend'), ('ai', 'AI Engineer'))]


# %%
# Restrict synthetic routes to explicit development mode, loopback and fixed
# frontend origins. Bodies are bounded before downstream JSON parsing.
@app.middleware('http')
async def candidate_demo_boundary(request: Request, call_next):
    if not request.url.path.startswith('/demo/'):
        return await call_next(request)
    headers = {'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer'}
    try:
        if os.getenv('APP_ENV') != 'development' or os.getenv('CANDIDATE_DEMO_ENABLED') != 'true':
            raise HTTPException(404, 'Not found')
        if (not request.client or not ipaddress.ip_address(request.client.host).is_loopback
                or request.url.hostname not in ('localhost', '127.0.0.1', '::1')):
            raise HTTPException(403, 'Local access required')
        origin = request.headers.get('origin', '')
        if origin not in ('http://127.0.0.1:3000', 'http://localhost:3000'):
            raise HTTPException(403, 'Origin denied')
        headers.update({'Access-Control-Allow-Origin': origin, 'Vary': 'Origin'})
        if request.method == 'OPTIONS':
            if (request.headers.get('access-control-request-method') not in ('GET', 'POST')
                    or request.headers.get('access-control-request-headers', '').lower() not in ('', 'content-type')):
                raise HTTPException(403, 'Preflight denied')
            return Response(status_code=204, headers={**headers, 'Access-Control-Allow-Methods': 'GET, POST',
                                                      'Access-Control-Allow-Headers': 'Content-Type'})
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 1024:
                raise HTTPException(413, 'Body too large')
        request._body = bytes(body)
        response = await call_next(request)
        response.headers.update(headers)
        return response
    except (ValueError, HTTPException) as error:
        return JSONResponse({'detail': error.detail if isinstance(error, HTTPException) else 'Local access required'},
                            status_code=error.status_code if isinstance(error, HTTPException) else 403, headers=headers)


# An unexpired random ID is a demo capability, not an account identity.
def demo_resource(store, key):
    resource = store.get(key)
    if not resource or resource['expires_at'] <= time.time():
        raise HTTPException(404, 'Demo expired or not found')
    return resource


# Require a JSON object; routes separately check the exact allowed fields.
async def demo_body(request):
    try:
        body = await request.json()
        if not isinstance(body, dict):
            raise ValueError()
        return body
    except ValueError:
        raise HTTPException(422, 'Invalid demo input') from None


# Return the fixed synthetic catalog without database or provider access.
@app.get('/demo/roles')
async def demo_roles():
    return DEMO_ROLES


# Remove expired capabilities before enforcing the process-local room limit.
@app.post('/demo/rooms')
async def create_demo_room(request: Request):
    body = await demo_body(request)
    if set(body) != {'role_id'} or body['role_id'] not in [r['role_id'] for r in DEMO_ROLES]:
        raise HTTPException(422, 'Choose a demo role')
    for store in (demo_rooms, demo_sessions):
        for key in list(store):
            if store[key]['expires_at'] <= time.time():
                del store[key]
    if len(demo_rooms) >= 100:
        raise HTTPException(429, 'Demo capacity reached; try later')
    room = {'room_id': secrets.token_urlsafe(32), 'role_id': body['role_id'], 'expires_at': time.time() + 1800}
    demo_rooms[room['room_id']] = room
    return room


# Missing and expired room capabilities share the same lookup failure.
@app.get('/demo/rooms/{room_id}')
async def get_demo_room(room_id: str):
    return demo_resource(demo_rooms, room_id)


# Require acknowledgement and reuse any session already bound to this room,
# including an ended one. No real media or interview service is started.
@app.post('/demo/rooms/{room_id}/sessions')
async def create_demo_session(room_id: str, request: Request):
    body = await demo_body(request)
    if set(body) != {'acknowledged'} or body['acknowledged'] is not True:
        raise HTTPException(422, 'Explicit demo acknowledgement required')
    room = demo_resource(demo_rooms, room_id)
    for session in demo_sessions.values():
        if session['room_id'] == room_id:
            return session
    session = {'session_id': secrets.token_urlsafe(32), 'room_id': room_id, 'status': 'active',
               'acknowledged_at': time.time(), 'expires_at': room['expires_at'], 'ended_at': None}
    demo_sessions[session['session_id']] = session
    return session


# Session visibility ends at its inherited room expiry.
@app.get('/demo/sessions/{session_id}')
async def get_demo_session(session_id: str):
    return demo_resource(demo_sessions, session_id)


# Repeatable termination preserves the first synthetic end time.
@app.post('/demo/sessions/{session_id}/end')
async def end_demo_session(session_id: str):
    session = demo_resource(demo_sessions, session_id)
    if session['status'] != 'ended':
        session.update(status='ended', ended_at=time.time())
    return session


# %%
# Voice requests add a separate bearer secret to loopback and origin checks.
# This is a local testing boundary, not Google session authorization.
@app.middleware('http')
async def local_voice_boundary(request: Request, call_next):
    if not request.url.path.startswith('/local/voice/'):
        return await call_next(request)
    try:
        secret, origins, *_ = voice_settings()
        host = request.client.host if request.client else ''
        if not ipaddress.ip_address(host).is_loopback or request.url.hostname not in ('localhost', '127.0.0.1', '::1'):
            raise HTTPException(403, 'Local access required')
        origin = request.headers.get('origin', '')
        if origin not in origins:
            raise HTTPException(403, 'Origin denied')
        headers = {'Access-Control-Allow-Origin': origin, 'Vary': 'Origin', 'Cache-Control': 'no-store'}
        if request.method == 'OPTIONS':
            if (request.headers.get('access-control-request-method') != 'POST'
                    or not set(request.headers.get('access-control-request-headers', '').lower().replace(' ', '').split(',')) <= {'authorization', 'content-type'}):
                raise HTTPException(403, 'Preflight denied')
            return Response(status_code=204, headers={**headers,
                'Access-Control-Allow-Methods': 'POST', 'Access-Control-Allow-Headers': 'Authorization, Content-Type'})
        if not hmac.compare_digest(request.headers.get('authorization', '').encode(), ('Bearer ' + secret).encode()):
            raise HTTPException(403, 'Access denied')
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 1024:
                raise HTTPException(413, 'Body too large')
        request._body = bytes(body)
        response = await call_next(request)
        response.headers.update(headers)
        return response
    except (ValueError, HTTPException) as error:
        return JSONResponse({'detail': error.detail if isinstance(error, HTTPException) else 'Local access required'},
                            status_code=error.status_code if isinstance(error, HTTPException) else 403,
                            headers={'Cache-Control': 'no-store'})


# Consent fields must exactly match recording mode. Reconcile remote leases
# under the local lock before creating a room; reject caller-controlled metadata.
@app.post('/local/voice/sessions')
async def start_voice(request: Request):
    from livekit import api
    _, _, ttl, duration, limit = voice_settings()
    try:
        body = await request.json()
    except ValueError:
        raise HTTPException(422, 'Consent required') from None
    recording = os.getenv('LOCAL_VOICE_RECORDING') == 'true'
    expected = {'consent': True, 'recording_consent': True} if recording else {'consent': True}
    if body != expected or any(type(value) is not bool for value in body.values()):
        raise HTTPException(422, 'Consent true required; no other fields accepted')
    async with voice_lock:
        now = time.time()
        while attempts and attempts[0] <= now - 60:
            attempts.popleft()
        if len(attempts) >= 10:
            raise HTTPException(429, 'Try later')
        attempts.append(now)
        client = voice_api()
        room = PREFIX + secrets.token_hex(16)
        identity = 'participant_' + secrets.token_hex(16)
        lease = {'deadline': now + duration, 'identity': identity, 'ended': False}
        lease['recording'] = 'local-pipeline-v1' if recording else False
        try:
            if len(await clean_rooms(client)) >= limit:
                raise HTTPException(429, 'Local session capacity reached')
            # Create room + named dispatch atomically. No caller room/agent/metadata input.
            await client.room.create_room(api.CreateRoomRequest(
                name=room, empty_timeout=3600, departure_timeout=3600, max_participants=2,
                metadata=json.dumps(lease), agents=[api.RoomAgentDispatch(
                    agent_name=AGENT_NAME, metadata=json.dumps(lease))]))
            # Remote calls consumed part of the lease. Never issue a JWT that can
            # recreate its room after the reservation has been released.
            issued_at = time.time()
            effective_ttl = min(ttl, int(lease['deadline'] - issued_at) - 1)
            if effective_ttl <= 0:
                raise HTTPException(503, 'Session lease expired before issuance')
            token = voice_token(room, identity, effective_ttl)
            return {'session_id': room, 'room': room, 'identity': identity, 'token': token,
                    'url': os.environ['LIVEKIT_URL'], 'expires_at': issued_at + effective_ttl,
                    'ends_at': lease['deadline'], 'recording': recording}
        except HTTPException:
            raise
        except Exception:
            # Ambiguous create failures retain the remote lease, never free capacity blindly.
            raise HTTPException(503, 'Voice service unavailable') from None
        finally:
            await client.aclose()


# Disconnect participants but retain the ended reservation until its deadline.
# A remote failure cannot confirm termination; the caller is told to stop media.
@app.post('/local/voice/sessions/{session_id}/end')
async def end_voice(session_id: str):
    from livekit import api
    async with voice_lock:
        client = voice_api()
        try:
            rooms = await clean_rooms(client)
            room = next((r for r in rooms if r.name == session_id), None)
            if room:
                lease = json.loads(room.metadata)
                lease['ended'] = True
                await client.room.update_room_metadata(api.UpdateRoomMetadataRequest(
                    room=room.name, metadata=json.dumps(lease)))
                await clean_rooms(client)
            return {'status': 'ended'}
        except Exception:
            raise HTTPException(503, 'End not confirmed; stop local media and retry') from None
        finally:
            await client.aclose()


# %%
# Process liveness is intentionally separate from database readiness.
@app.get('/health')
def health():
    """Liveness only; does not check DB or providers."""
    return {'status': 'ok', 'service': 'api'}


# Probe only the database, withholding connection exception details from clients.
@app.get('/ready')
def ready():
    try:
        ping()
    except Exception:
        return JSONResponse({'status': 'unavailable'}, status_code=503)
    return {'status': 'ready', 'service': 'api'}
