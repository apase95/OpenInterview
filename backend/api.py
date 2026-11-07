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


def voice_api():
    import aiohttp
    from livekit.api import LiveKitAPI
    return LiveKitAPI(os.environ['LIVEKIT_URL'], os.environ['LIVEKIT_API_KEY'],
                      os.environ['LIVEKIT_API_SECRET'], timeout=aiohttp.ClientTimeout(total=5))


def voice_token(room, identity, ttl):
    from livekit.api import AccessToken, VideoGrants
    return (AccessToken(os.environ['LIVEKIT_API_KEY'], os.environ['LIVEKIT_API_SECRET'])
            .with_identity(identity).with_ttl(timedelta(seconds=ttl))
            .with_grants(VideoGrants(room_join=True, room=room, can_publish=True,
                                     can_subscribe=True, can_publish_data=False,
                                     can_publish_sources=['microphone'], can_update_own_metadata=False,
                                     can_manage_agent_session=False)).to_jwt())


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


app = FastAPI(lifespan=lifespan)


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


@app.post('/local/voice/sessions')
async def start_voice(request: Request):
    from livekit import api
    _, _, ttl, duration, limit = voice_settings()
    try:
        body = await request.json()
    except ValueError:
        raise HTTPException(422, 'Consent required') from None
    if body != {'consent': True} or type(body.get('consent')) is not bool:
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
                    'ends_at': lease['deadline'], 'recording': False}
        except HTTPException:
            raise
        except Exception:
            # Ambiguous create failures retain the remote lease, never free capacity blindly.
            raise HTTPException(503, 'Voice service unavailable') from None
        finally:
            await client.aclose()


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


@app.get('/health')
def health():
    """Liveness only; does not check DB or providers."""
    return {'status': 'ok', 'service': 'api'}


@app.get('/ready')
def ready():
    try:
        ping()
    except Exception:
        return JSONResponse({'status': 'unavailable'}, status_code=503)
    return {'status': 'ready', 'service': 'api'}
