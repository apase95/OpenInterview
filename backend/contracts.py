"""Offline v1 contract source. No routes, credentials, or provider imports."""
import json
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, AfterValidator, model_validator


def utc(value):
    if value.utcoffset() is None or value.utcoffset().total_seconds() != 0:
        raise ValueError('UTC timestamp required')
    return value


ID = Annotated[str, Field(pattern=r'^[a-z][a-z0-9_\-]{2,79}$')]
Text = Annotated[str, Field(min_length=1, max_length=4000)]
Email = Annotated[str, Field(pattern=r'^[^@\s]+@[^@\s]+\.[^@\s]+$', max_length=254)]
UTC = Annotated[datetime, AfterValidator(utc)]
Version = Annotated[int, Field(ge=1)]
Refs = Annotated[list[ID], Field(max_length=100)]
Collection = Literal['not_collected', 'refused', 'insufficient_evidence', 'supported']


class Model(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Resource(Model):
    schema_version: Literal['1.0'] = '1.0'
    id: ID
    tenant_id: ID


class Tenant(Model):
    id: ID
    name: Text


class User(Resource):
    email: Email
    name: Text
    app_role: Literal['candidate', 'recruiter', 'operator']
    campaign_ids: Refs


class Criterion(Model):
    id: ID
    description: Text


class CoreQuestion(Model):
    id: ID
    criterion_id: ID
    text: Text


class FAQSource(Model):
    id: ID
    version: Version
    content: Text
    effective_from: UTC
    effective_to: UTC

    @model_validator(mode='after')
    def window(self):
        if self.effective_to <= self.effective_from:
            raise ValueError('invalid FAQ window')
        return self


class Campaign(Resource):
    version: Version
    career: Literal['BA', 'DevOps', 'Fullstack', 'Frontend', 'Backend', 'AI Engineer']
    jd: Annotated[str, Field(min_length=1, max_length=16000)]
    status: Literal['draft', 'proposed', 'approved']
    questions: Annotated[list[CoreQuestion], Field(max_length=20)]
    rubric: Annotated[list[Criterion], Field(max_length=20)]
    faq: Annotated[list[FAQSource], Field(max_length=20)]
    approved_by: ID | None
    approved_at: UTC | None
    time_budget_seconds: Annotated[int, Field(ge=480, le=720)] = 600
    followups_per_topic: Annotated[int, Field(ge=0, le=2)] = 2
    clarifications_per_session: Annotated[int, Field(ge=0, le=5)] = 3

    @model_validator(mode='after')
    def snapshot(self):
        for values in (self.questions, self.rubric, self.faq):
            if len({v.id for v in values}) != len(values):
                raise ValueError('duplicate snapshot IDs')
        if any(q.criterion_id not in {r.id for r in self.rubric} for q in self.questions):
            raise ValueError('question criterion missing')
        if (self.status == 'approved') != (self.approved_by is not None and self.approved_at is not None):
            raise ValueError('approval required only for approved snapshot')
        if self.status in ('proposed', 'approved') and (not self.questions or not self.rubric):
            raise ValueError('proposal/approval needs questions and rubric')
        if self.status != 'approved' and (self.approved_by is not None or self.approved_at is not None):
            raise ValueError('unapproved snapshot cannot carry approval')
        return self


class CVBinding(Model):
    """Metadata only; uploading/storage/scanning are not implemented."""
    id: ID
    version: Version
    sha256: Annotated[str, Field(pattern='^[a-f0-9]{64}$')]
    size_bytes: Annotated[int, Field(gt=0, le=5242880)]
    mime_type: Literal['application/pdf']
    scan_status: Literal['quarantined', 'scanning', 'available', 'rejected', 'scan_failed']
    authority_notice_ref: Text


class Room(Resource):
    candidate_id: ID
    campaign_id: ID
    campaign_version: Version
    status: Literal['draft', 'published', 'revoked', 'completed']
    opens_at: UTC
    closes_at: UTC
    timezone: Literal['UTC']
    contact: Email
    cv_attachment: CVBinding | None
    published_at: UTC | None

    @model_validator(mode='after')
    def publish(self):
        if self.closes_at <= self.opens_at:
            raise ValueError('invalid room window')
        if self.status != 'draft' and self.published_at is None:
            raise ValueError('publication timestamp required')
        if self.status != 'draft' and self.cv_attachment and self.cv_attachment.scan_status != 'available':
            raise ValueError('scan required')
        return self


class Consent(Model):
    notice_version: Text
    choice: bool
    recorded_at: UTC


class Session(Resource):
    room_id: ID
    consent: Consent
    phase: Literal['consent', 'basic_info', 'experience', 'light_technical', 'candidate_qa', 'wrap']
    status: Literal['active', 'interrupted', 'ended']
    end_reason: Literal['completed', 'candidate_end', 'refused', 'timeout', 'connection_failed'] | None
    input_version: Version
    started_at: UTC | None
    ended_at: UTC | None
    recording_status: Literal['disabled']

    @model_validator(mode='after')
    def lifecycle(self):
        if self.started_at and (not self.consent.choice or self.started_at < self.consent.recorded_at):
            raise ValueError('consent before start')
        if self.status == 'ended' and (self.ended_at is None or self.end_reason is None):
            raise ValueError('terminal state mismatch')
        if self.status != 'ended' and (self.ended_at is not None or self.end_reason is not None):
            raise ValueError('nonterminal session has terminal fields')
        if self.ended_at and self.ended_at < self.consent.recorded_at:
            raise ValueError('end before consent choice')
        if self.started_at and self.ended_at and self.ended_at < self.started_at:
            raise ValueError('end before start')
        if not self.consent.choice:
            if self.status != 'ended' or self.end_reason != 'refused' or self.phase != 'consent' or self.started_at is not None:
                raise ValueError('refusal must end before interview start')
        elif self.end_reason == 'refused':
            raise ValueError('refused outcome requires refused consent')
        if self.started_at is None and (self.phase != 'consent' or self.end_reason == 'completed'):
            raise ValueError('unstarted interview must remain in consent phase and cannot complete')
        return self


class Turn(Resource):
    session_id: ID
    event_id: ID
    sequence: Annotated[int, Field(ge=1)]
    occurred_at: UTC
    input_version: Version
    speaker: Literal['candidate', 'assistant']
    kind: Literal['answer', 'question', 'correction', 'refusal', 'faq']
    finalized_text: Text
    delivery_status: Literal['stt_final', 'confirmed_delivered', 'partial']
    audio_start_ms: Annotated[int, Field(ge=0)]
    audio_end_ms: Annotated[int, Field(ge=0)]

    @model_validator(mode='after')
    def final(self):
        if self.audio_end_ms < self.audio_start_ms:
            raise ValueError('invalid offsets')
        if (self.speaker == 'candidate') != (self.delivery_status == 'stt_final'):
            raise ValueError('speaker/delivery mismatch')
        return self


class Correction(Resource):
    session_id: ID
    target_turn_id: ID
    replacement_turn_id: ID
    input_version: Version
    created_at: UTC
    reason: Text


class Fact(Model):
    field: ID
    value: Text | None
    collection_status: Collection
    evidence_turn_ids: Refs

    @model_validator(mode='after')
    def evidence(self):
        if self.collection_status == 'supported' and (self.value is None or not self.evidence_turn_ids):
            raise ValueError('supported fact needs value and evidence')
        if self.collection_status != 'supported' and self.value is not None:
            raise ValueError('missing/refused value must be null')
        if self.collection_status == 'not_collected' and self.evidence_turn_ids:
            raise ValueError('not collected has no evidence')
        return self


class CandidateQuestion(Resource):
    session_id: ID
    turn_id: ID
    text: Text
    topic: ID
    # Guardrail metadata does not overload FAQ status or controller action.
    disposition: Literal['answer', 'restricted', 'deferred']
    reason: Literal['source_available', 'source_missing', 'source_conflict', 'source_expired',
                    'private_information', 'candidate_agreed_defer']
    action: Literal['answer_faq', 'advance', 'end']

    @model_validator(mode='after')
    def disposition_mapping(self):
        if self.disposition == 'answer':
            valid = self.action == 'answer_faq' and self.reason in ('source_available', 'source_missing', 'source_conflict', 'source_expired')
        else:
            expected_reason = 'private_information' if self.disposition == 'restricted' else 'candidate_agreed_defer'
            valid = self.action in ('advance', 'end') and self.reason == expected_reason
        if not valid:
            raise ValueError('inconsistent question disposition/action/reason')
        return self


class SourceRef(Model):
    id: ID
    version: Version


class FAQAnswer(Resource):
    session_id: ID
    question_id: ID
    status: Literal['answered', 'unknown', 'conflict', 'expired']
    confirmed_answer_turn_id: ID | None
    source_versions: list[SourceRef]
    followup_status: Literal['none', 'pending_recruiter']


class ReportJob(Resource):
    session_id: ID
    input_version: Version
    status: Literal['pending', 'processing', 'done', 'failed']
    attempts: Annotated[int, Field(ge=0, le=3)]
    lease_until: UTC | None

    @model_validator(mode='after')
    def lease(self):
        if (self.status == 'processing') != (self.lease_until is not None):
            raise ValueError('processing alone has a lease')
        return self


class Assessment(Fact):
    requirement_status: Literal['fulfilled', 'partial', 'missing']
    note: Text

    @model_validator(mode='after')
    def missing(self):
        if self.collection_status != 'supported' and self.requirement_status != 'missing':
            raise ValueError('missing evidence cannot imply ability')
        return self


class Report(Resource):
    session_id: ID
    input_version: Version
    report_version: Version
    status: Literal['draft', 'reviewed', 'superseded']
    summary: Text
    criteria: list[Assessment]
    facts: list[Fact]
    reviewer_id: ID | None
    reviewed_at: UTC | None
    created_at: UTC
    config_version: Text

    @model_validator(mode='after')
    def review(self):
        if self.status == 'reviewed' and (not self.reviewer_id or not self.reviewed_at):
            raise ValueError('review needs actor and time')
        if self.status == 'draft' and (self.reviewer_id or self.reviewed_at):
            raise ValueError('draft has no reviewer')
        return self


class Bundle(Model):
    schema_version: Literal['1.0']
    synthetic: Literal[True]
    description: Text
    tenants: list[Tenant]
    users: list[User]
    campaigns: list[Campaign]
    rooms: list[Room]
    sessions: list[Session]
    turns: list[Turn]
    corrections: list[Correction]
    questions: list[CandidateQuestion]
    answers: list[FAQAnswer]
    jobs: list[ReportJob]
    reports: list[Report]

    @model_validator(mode='after')
    def relationships(self):
        groups = ('tenants', 'users', 'campaigns', 'rooms', 'sessions', 'turns',
                  'corrections', 'questions', 'answers', 'jobs', 'reports')
        maps = {}
        for group in groups:
            rows = getattr(self, group)
            if len({r.id for r in rows}) != len(rows):
                raise ValueError('duplicate resource ID')
            maps[group] = {r.id: r for r in rows}
            for row in rows:
                if not row.id.startswith('syn_'):
                    raise ValueError('synthetic ID prefix required')
                if group != 'tenants' and row.tenant_id not in maps['tenants']:
                    raise ValueError('tenant missing')

        def ref(group, key, owner):
            target = maps[group].get(key)
            if target is None or target.tenant_id != owner.tenant_id:
                raise ValueError('missing/cross-tenant reference')
            if hasattr(owner, 'session_id') and hasattr(target, 'session_id') and owner.session_id != target.session_id:
                raise ValueError('cross-session reference')
            return target

        def campaign(session):
            room = ref('rooms', session.room_id, session)
            return ref('campaigns', room.campaign_id, room)

        def evidence(ids, owner, version):
            for key in ids:
                turn = ref('turns', key, owner)
                if turn.speaker != 'candidate' or turn.input_version > version:
                    raise ValueError('not finalized candidate evidence in input snapshot')
                if any(c.tenant_id == owner.tenant_id and c.session_id == owner.session_id
                       and c.target_turn_id == key and c.input_version <= version for c in self.corrections):
                    raise ValueError('evidence superseded by correction')

        for user in self.users:
            if not user.email.endswith('@example.com'):
                raise ValueError('synthetic emails must use example.com')
            for key in user.campaign_ids:
                ref('campaigns', key, user)
        for item in self.campaigns:
            if any(not value.id.startswith('syn_') for value in [*item.questions, *item.rubric, *item.faq]):
                raise ValueError('synthetic snapshot ID prefix required')
            if item.approved_by:
                actor = ref('users', item.approved_by, item)
                if actor.app_role != 'recruiter' or item.id not in actor.campaign_ids:
                    raise ValueError('approval scope missing')
        for room in self.rooms:
            if not room.contact.endswith('@example.com'):
                raise ValueError('synthetic contact emails must use example.com')
            candidate = ref('users', room.candidate_id, room)
            snapshot = ref('campaigns', room.campaign_id, room)
            if candidate.app_role != 'candidate' or room.campaign_version != snapshot.version:
                raise ValueError('room binding invalid')
            if room.status != 'draft' and snapshot.status != 'approved':
                raise ValueError('unapproved room')
            # Fixture deliberately contains no CV, object, token or real notice.
            if room.cv_attachment is not None:
                raise ValueError('synthetic baseline uses explicit CV absence')
        if len({(s.tenant_id, s.room_id) for s in self.sessions}) != len(self.sessions):
            raise ValueError('duplicate session for tenant/room')
        for session in self.sessions:
            room = ref('rooms', session.room_id, session)
            if room.status not in ('published', 'completed'):
                raise ValueError('session room not published')
            if session.started_at and not (room.opens_at <= session.started_at < room.closes_at):
                raise ValueError('session outside window')
            if not session.consent.notice_version.startswith('notice_demo_'):
                raise ValueError('demo notice required')
            if room.status == 'completed' and (session.status != 'ended' or session.end_reason != 'completed'):
                raise ValueError('completed room needs completed session')
        for key in ('event_id', 'sequence'):
            if len({(t.tenant_id, t.session_id, getattr(t, key)) for t in self.turns}) != len(self.turns):
                raise ValueError('duplicate event/sequence')
        for turn in self.turns:
            if not turn.event_id.startswith('syn_'):
                raise ValueError('synthetic event ID prefix required')
            session = ref('sessions', turn.session_id, turn)
            if not session.started_at or turn.occurred_at < session.started_at or turn.input_version > session.input_version:
                raise ValueError('turn outside session snapshot')
            if session.ended_at and turn.occurred_at > session.ended_at:
                raise ValueError('turn after end')
        for correction in self.corrections:
            session = ref('sessions', correction.session_id, correction)
            original = ref('turns', correction.target_turn_id, correction)
            replacement = ref('turns', correction.replacement_turn_id, correction)
            if (original.speaker != 'candidate' or replacement.speaker != 'candidate'
                    or original.sequence >= replacement.sequence or replacement.kind != 'correction'
                    or original.input_version >= correction.input_version
                    or replacement.input_version != correction.input_version
                    or correction.input_version > session.input_version):
                raise ValueError('invalid correction version/provenance')
        for question in self.questions:
            turn = ref('turns', question.turn_id, question)
            if turn.speaker != 'candidate' or turn.finalized_text != question.text:
                raise ValueError('question must cite original candidate text')
            if question.disposition != 'answer' and any(a.question_id == question.id for a in self.answers):
                raise ValueError('restricted/deferred uses metadata, not fabricated FAQ status')
        for answer in self.answers:
            question = ref('questions', answer.question_id, answer)
            session = ref('sessions', answer.session_id, answer)
            sources = {(s.id, s.version): s for s in campaign(session).faq}
            for source in answer.source_versions:
                if (source.id, source.version) not in sources:
                    raise ValueError('unknown FAQ source version')
            if answer.status == 'answered':
                if not answer.source_versions or not answer.confirmed_answer_turn_id or answer.followup_status != 'none':
                    raise ValueError('answered requires delivered source-backed answer')
                turn = ref('turns', answer.confirmed_answer_turn_id, answer)
                if turn.speaker != 'assistant' or turn.delivery_status != 'confirmed_delivered':
                    raise ValueError('answer not confirmed')
                if any(not (sources[(s.id, s.version)].effective_from <= turn.occurred_at < sources[(s.id, s.version)].effective_to) for s in answer.source_versions):
                    raise ValueError('FAQ source expired')
            elif answer.confirmed_answer_turn_id is not None or answer.followup_status != 'pending_recruiter':
                raise ValueError('unconfirmed answer needs followup')
        for group in ('jobs', 'reports'):
            rows = getattr(self, group)
            if len({(r.tenant_id, r.session_id, r.input_version) for r in rows}) != len(rows):
                raise ValueError('duplicate job/report input')
            for row in rows:
                session = ref('sessions', row.session_id, row)
                if session.status != 'ended' or not session.started_at or row.input_version > session.input_version:
                    raise ValueError('job/report needs terminal input snapshot')
        for report in self.reports:
            session = ref('sessions', report.session_id, report)
            matching = [j for j in self.jobs if (j.tenant_id, j.session_id, j.input_version) == (report.tenant_id, report.session_id, report.input_version)]
            if not matching or matching[0].status != 'done':
                raise ValueError('persisted report needs done job')
            if report.reviewer_id:
                actor = ref('users', report.reviewer_id, report)
                if actor.app_role != 'recruiter' or campaign(session).id not in actor.campaign_ids:
                    raise ValueError('review scope missing')
            for fact in [*report.criteria, *report.facts]:
                evidence(fact.evidence_turn_ids, report, report.input_version)
            if any(c.field not in {r.id for r in campaign(session).rubric} for c in report.criteria):
                raise ValueError('unknown report criterion')
            if report.input_version != session.input_version and report.status != 'superseded':
                raise ValueError('old report must be superseded')
        for job in self.jobs:
            if job.status == 'done' and not any((r.tenant_id, r.session_id, r.input_version) == (job.tenant_id, job.session_id, job.input_version) for r in self.reports):
                raise ValueError('done job missing report')
        return self


class Error(Model):
    schema_version: Literal['1.0'] = '1.0'
    code: Literal['unauthenticated', 'forbidden', 'not_found', 'version_conflict',
                  'invalid_state', 'validation_error', 'rate_limited', 'unavailable']
    message: Text
    request_id: ID


class ConsentRequest(Model):
    notice_version: Text
    choice: bool


class TokenResponse(Model):
    schema_version: Literal['1.0'] = '1.0'
    session_id: ID
    room_id: ID
    identity: ID
    token: Text
    expires_at: UTC


class EndRequest(Model):
    reason: Literal['candidate_end']


class ReviewRequest(Model):
    note: Text


class Me(Model):
    schema_version: Literal['1.0'] = '1.0'
    id: ID
    tenant_id: ID
    app_role: Literal['candidate', 'recruiter', 'operator']
    campaign_ids: Refs
    csrf_token: Text


class RoomCreate(Model):
    candidate_email: Email
    candidate_name: Text
    campaign_id: ID
    campaign_version: Version
    opens_at: UTC
    closes_at: UTC
    timezone: Literal['UTC']
    contact: Email
    cv_attachment: CVBinding | None


class CampaignCreate(Model):
    career: Literal['BA', 'DevOps', 'Fullstack', 'Frontend', 'Backend', 'AI Engineer']
    jd: Annotated[str, Field(min_length=1, max_length=16000)]


class ApprovalRequest(Model):
    version: Version


class CorrectionRequest(Model):
    target_turn_id: ID
    replacement_turn_id: ID
    input_version: Version
    reason: Text


class ReportDetail(Model):
    schema_version: Literal['1.0'] = '1.0'
    report: Report
    session: Session
    room: Room
    campaign: Campaign
    turns: list[Turn]
    corrections: list[Correction]
    questions: list[CandidateQuestion]
    answers: list[FAQAnswer]


class Event(Model):
    schema_version: Literal['1.0'] = '1.0'
    event_id: ID
    tenant_id: ID
    session_id: ID
    sequence: Annotated[int, Field(ge=1)]
    occurred_at: UTC
    event_type: Literal['turn_finalized', 'state_changed', 'delivery_unknown', 'generation_cancelled', 'guardrail']
    turn_id: ID | None
    generation_id: ID | None
    reason: Literal['private_information', 'source_missing', 'source_conflict', 'source_expired',
                    'candidate_agreed_defer', 'candidate_end', 'connection_failed'] | None


# method, path, request, response, scope; all domain operations remain unimplemented.
ROUTES = [
    ('get', '/v1/me', None, Me, 'signed-in account'),
    ('get', '/v1/rooms', None, list[Room], 'candidate own rooms or assigned recruiter campaigns'),
    ('get', '/v1/rooms/{room_id}', None, Room, 'candidate own room or assigned recruiter campaign'),
    ('post', '/v1/campaigns', CampaignCreate, Campaign, 'recruiter tenant create grant'),
    ('post', '/v1/campaigns/{campaign_id}/proposal', None, Campaign, 'assigned recruiter campaign'),
    ('post', '/v1/campaigns/{campaign_id}/approval', ApprovalRequest, Campaign, 'assigned recruiter campaign'),
    ('post', '/v1/rooms', RoomCreate, Room, 'assigned recruiter campaign'),
    ('post', '/v1/rooms/{room_id}/publication', None, Room, 'assigned recruiter campaign'),
    ('post', '/v1/rooms/{room_id}/revocation', None, Room, 'assigned recruiter campaign'),
    ('post', '/v1/rooms/{room_id}/consent', ConsentRequest, Session, 'candidate own published room'),
    ('post', '/v1/sessions/{session_id}/join-token', None, TokenResponse, 'candidate own consented active session'),
    ('get', '/v1/sessions/{session_id}', None, Session, 'candidate own session or assigned recruiter campaign'),
    ('post', '/v1/sessions/{session_id}/end', EndRequest, Session, 'candidate own session'),
    ('post', '/v1/sessions/{session_id}/corrections', CorrectionRequest, Correction, 'assigned recruiter; candidate correction through controller'),
    ('get', '/v1/reports', None, list[Report], 'assigned recruiter campaigns only'),
    ('get', '/v1/reports/{report_id}', None, ReportDetail, 'assigned recruiter campaign only'),
    ('post', '/v1/reports/{report_id}/review', ReviewRequest, Report, 'assigned recruiter campaign only'),
]


def openapi_document():
    from pydantic import TypeAdapter
    components = {}

    def schema(kind):
        result = TypeAdapter(kind).json_schema(ref_template='#/components/schemas/{model}')
        components.update(result.pop('$defs', {}))
        return result

    components['Bundle'] = schema(Bundle)
    components['Event'] = schema(Event)
    error = schema(Error)
    paths = {}
    for method, path, request, response, scope in ROUTES:
        operation = {
            'operationId': method + '_' + path.replace('/', '_').replace('{', '').replace('}', '').replace('-', '_'),
            'summary': scope, 'x-implementation-state': 'specified-only',
            'security': [{'sessionCookie': []}],
            'parameters': [],
            'responses': {'200': {'description': 'Success; schema_version is the contract version, not an ETag',
                                   'content': {'application/json': {'schema': schema(response)}}}},
        }
        for part in path.split('/'):
            if part.startswith('{'):
                operation['parameters'].append({'name': part[1:-1], 'in': 'path', 'required': True, 'schema': {'type': 'string'}})
        if method != 'get':
            for name in ('X-CSRF-Token', 'Idempotency-Key', 'If-Match'):
                operation['parameters'].append({'name': name, 'in': 'header', 'required': name != 'If-Match' or '{' in path,
                                                'schema': {'type': 'string', 'maxLength': 128}})
        if request:
            operation['requestBody'] = {'required': True, 'content': {'application/json': {'schema': schema(request)}}}
        for code in ('401', '403', '404', '409', '422', '429', '503'):
            operation['responses'][code] = {'description': 'Stable error code; no private resource details',
                                           'content': {'application/json': {'schema': error}}}
        if method == 'get':
            for result in operation['responses'].values():
                result.setdefault('headers', {})['X-Contract-Version'] = {
                    'description': 'Non-secret wire contract version', 'schema': {'type': 'string', 'const': '1.0'}}
        if method != 'get' or path not in ('/v1/rooms', '/v1/reports'):
            operation['responses']['200'].setdefault('headers', {})['ETag'] = {
                'description': 'Opaque affected row revision (session revision for join-token)',
                'schema': {'type': 'string'}}
        operation['responses']['429']['headers'] = {'Retry-After': {
            'description': 'Delay in seconds before a bounded retry', 'schema': {'type': 'integer', 'minimum': 0}}}
        paths.setdefault(path, {})[method] = operation
    for path, status in (('/health', 'ok'), ('/ready', 'ready')):
        paths[path] = {'get': {'operationId': path[1:], 'security': [], 'x-implementation-state': 'implemented',
                               'responses': {'200': {'description': status}, **({'503': {'description': 'DB unavailable'}} if path == '/ready' else {})}}}
    return {'openapi': '3.1.0', 'info': {'title': 'OpenInterview technical baseline', 'version': '1.0'},
            'paths': paths, 'components': {'schemas': components, 'securitySchemes': {
                'sessionCookie': {'type': 'apiKey', 'in': 'cookie', 'name': '__Host-oi_session'}}}}


if __name__ == '__main__':
    # Explicit offline code generation; committed artifact checked byte-structurally in tests.
    target = Path(__file__).resolve().parents[1] / 'docs/contracts/openapi-v1.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(openapi_document(), ensure_ascii=False, indent=2) + '\n')
