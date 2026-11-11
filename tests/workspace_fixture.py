"""Offline identity/repository stand-ins. Never imported by application code."""
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException

NOW = datetime.now(timezone.utc)
USERS = {
    'candidate-a': {'id': '00000000-0000-0000-0000-000000000001', 'email': 'a@example.test', 'name': 'Candidate A', 'role': 'candidate', 'grants': []},
    'candidate-b': {'id': '00000000-0000-0000-0000-000000000002', 'email': 'b@example.test', 'name': 'Candidate B', 'role': 'candidate', 'grants': []},
    'hr': {'id': '00000000-0000-0000-0000-000000000003', 'email': 'hr@example.test', 'role': 'candidate', 'grants': [{'permission': 'hr', 'campaign_id': 'web'}]},
    'admin': {'id': '00000000-0000-0000-0000-000000000004', 'email': 'admin@example.test', 'role': 'candidate', 'grants': [{'permission': 'admin', 'campaign_id': None}]},
}


class MemoryAuth:
    def session(self, settings, token):
        return USERS.get(token)


class MemoryWorkspace:
    def __init__(self):
        self.assigned = {'room-one': dict(id='room-one', candidate_id=USERS['candidate-a']['id'], role_id='frontend', campaign_name='Web team', campaign_id='web', opens_at=(NOW-timedelta(minutes=5)).isoformat(), closes_at=(NOW+timedelta(minutes=30)).isoformat(), timezone='Asia/Ho_Chi_Minh', contact='hr@example.test', ready=True, session_id=None, ended_at=None, revoked_at=None)}
        self.sessions = {}

    def room(self, user, room_id):
        room = self.assigned.get(room_id)
        if not room or room['candidate_id'] != user['id'] or room['revoked_at'] or datetime.fromisoformat(room['closes_at']) <= datetime.now(timezone.utc):
            raise HTTPException(404, 'Room unavailable')
        return dict(room)

    def rooms(self, user):
        return [dict(r) for r in self.assigned.values() if r['candidate_id'] == user['id'] and not r['revoked_at']]

    def join(self, user, room_id):
        room = self.room(user, room_id)
        if not room['ready']:
            raise HTTPException(409, 'Not available yet')
        if not room['session_id']:
            self.assigned[room_id]['session_id'] = 'session-one'
            self.sessions['session-one'] = dict(id='session-one', room_id=room_id, ended_at=None)
        return self.sessions[self.assigned[room_id]['session_id']]

    def session(self, user, session_id, end=False):
        session = self.sessions.get(session_id)
        room = self.assigned.get(session['room_id']) if session else None
        if not room or room['candidate_id'] != user['id']:
            raise HTTPException(404, 'Session unavailable')
        if not end:
            self.room(user, room['id'])
        if end and not session['ended_at']:
            session['ended_at'] = datetime.now(timezone.utc).isoformat()
            room['ended_at'] = session['ended_at']
        return dict(session)

    def hr(self, user):
        scopes = {g['campaign_id'] for g in user['grants'] if g['permission'] == 'hr'}
        return [r for r in self.assigned.values() if r['campaign_id'] in scopes]

    def admin(self):
        return dict(users=list(USERS.values()), grants=[], database='reachable', jobs='unknown', checked_at=NOW.isoformat())
