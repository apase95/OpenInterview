"""Cookie-authorized, durable synthetic preparation. No live interview consent.

Account assignments and confirmed grants must be provisioned by a trusted
operator. Nothing here binds an invitation by email or grants permissions.
"""
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from backend import auth

router = APIRouter(prefix='/workspace')
ROLES = [{'role_id': key, 'name': name} for key, name in (
    ('ba', 'BA'), ('devops', 'DevOps'), ('fullstack', 'Fullstack'),
    ('frontend', 'Frontend'), ('backend', 'Backend'), ('ai', 'AI Engineer'))]


class Store:
    def run(self, action):
        return auth.store.run(action)

    def rooms(self, user):
        return self.run(lambda c: c.execute('''SELECT r.*, s.id AS session_id, s.ended_at,
            r.opens_at <= now() AS ready FROM web_room_previews r
            LEFT JOIN web_session_previews s ON s.room_id=r.id
            WHERE candidate_id=%s AND revoked_at IS NULL AND closes_at>now()
            ORDER BY opens_at, r.id LIMIT 100''', (user['id'],)).fetchall())

    def room(self, user, room_id):
        def action(c):
            row = c.execute('''SELECT r.*, s.id AS session_id, s.ended_at,
                r.opens_at <= now() AS ready FROM web_room_previews r
                LEFT JOIN web_session_previews s ON s.room_id=r.id
                WHERE r.id=%s AND candidate_id=%s AND revoked_at IS NULL AND closes_at>now()''',
                (room_id, user['id'])).fetchone()
            if not row:
                raise HTTPException(404, 'Room unavailable')
            return row
        return self.run(action)

    def join(self, user, room_id):
        def action(c):
            # Lock the assignment before checking schedule and allocating one session.
            room = c.execute('''SELECT id, opens_at <= now() AS ready FROM web_room_previews
                WHERE id=%s AND candidate_id=%s AND revoked_at IS NULL AND closes_at>now()
                FOR UPDATE''', (room_id, user['id'])).fetchone()
            if not room:
                raise HTTPException(404, 'Room unavailable')
            if not room['ready']:
                raise HTTPException(409, 'Not available yet')
            return c.execute('''INSERT INTO web_session_previews(id,room_id) VALUES (%s,%s)
                ON CONFLICT(room_id) DO UPDATE SET room_id=EXCLUDED.room_id
                RETURNING id,room_id,acknowledged_at,ended_at''',
                (secrets.token_urlsafe(24), room_id)).fetchone()
        return self.run(action)

    def session(self, user, session_id, end=False):
        def action(c):
            # End remains possible after revocation/expiry; it cannot resume media.
            gate = '' if end else ' AND r.revoked_at IS NULL AND r.opens_at<=now() AND r.closes_at>now()'
            row = c.execute('''SELECT s.* FROM web_session_previews s
                JOIN web_room_previews r ON r.id=s.room_id
                WHERE s.id=%s AND r.candidate_id=%s''' + gate + ' FOR UPDATE OF s',
                (session_id, user['id'])).fetchone()
            if not row:
                raise HTTPException(404, 'Session unavailable')
            if end:
                row = c.execute('''UPDATE web_session_previews SET ended_at=COALESCE(ended_at,now())
                    WHERE id=%s RETURNING *''', (session_id,)).fetchone()
            return row
        return self.run(action)

    def hr(self, user):
        scopes = [g['campaign_id'] for g in user.get('grants', []) if g['permission'] == 'hr']
        return self.run(lambda c: c.execute('''SELECT id,campaign_id,campaign_name,role_id,
            opens_at,closes_at,timezone,revoked_at FROM web_room_previews
            WHERE campaign_id=ANY(%s) ORDER BY opens_at LIMIT 100''', (scopes,)).fetchall())

    def admin(self):
        def action(c):
            accounts = c.execute('SELECT id,email,name,role FROM auth_accounts ORDER BY email LIMIT 100').fetchall()
            grants = c.execute('''SELECT id,account_id,permission,campaign_id,granted_by,
                created_at,confirmed_at,revoked_at FROM web_access_grants ORDER BY created_at DESC LIMIT 100''').fetchall()
            return {'users': accounts, 'grants': grants, 'database': 'reachable',
                    'jobs': 'unknown', 'checked_at': datetime.now(timezone.utc)}
        return self.run(action)


store = Store()


async def query(method, *args):
    try:
        return await run_in_threadpool(method, *args)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, 'Workspace unavailable') from None


@router.get('/roles')
async def roles(request: Request):
    await auth.require_user(request)
    return ROLES


@router.get('/rooms')
async def rooms(request: Request):
    user = await auth.require_user(request)
    return await query(store.rooms, user)


@router.get('/rooms/{room_id}')
async def room(room_id: str, request: Request):
    user = await auth.require_user(request)
    return await query(store.room, user, room_id)


@router.post('/rooms/{room_id}/sessions')
async def join(room_id: str, request: Request):
    user = await auth.require_user(request, mutation=True)
    try:
        body = await request.json()
    except ValueError:
        raise HTTPException(422, 'Explicit preparation acknowledgement required') from None
    if body != {'acknowledged': True} or type(body.get('acknowledged')) is not bool:
        raise HTTPException(422, 'Explicit preparation acknowledgement required')
    return await query(store.join, user, room_id)


@router.get('/sessions/{session_id}')
async def session(session_id: str, request: Request):
    user = await auth.require_user(request)
    return await query(store.session, user, session_id)


@router.post('/sessions/{session_id}/end')
async def end(session_id: str, request: Request):
    user = await auth.require_user(request, mutation=True)
    return await query(store.session, user, session_id, True)


@router.get('/hr')
async def hr(request: Request):
    user = await auth.require_user(request, 'hr')
    return {'rooms': await query(store.hr, user), 'reports': [], 'mode': 'preparation_only'}


@router.get('/admin')
async def admin(request: Request):
    await auth.require_user(request, 'admin')
    return await query(store.admin)
