# %%
"""Pure text policy gate. Confirmed intents come from a trusted upstream adapter.

No NLU, media, persistence or production content approval is implemented here.
Only the bounded, reviewed wording catalog is spoken; proposal text is never used.
"""
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json
from typing import Literal

from pydantic import Field
from backend.contracts import Model, ID, Text, SourceRef, Campaign

Action = Literal['ask_core', 'ask_followup', 'clarify', 'answer_faq', 'advance', 'wrap', 'end']

# Content approval is deliberately separate from a campaign's structural approval.
CORE = {'syn_core': 'Bạn từng xử lý yêu cầu hỗ trợ như thế nào?'}
FAQ = {'syn_faq': 'Vị trí mẫu làm việc từ thứ Hai đến thứ Sáu.'}
FOLLOWUP = 'Trong ví dụ đó, bạn trực tiếp phụ trách phần nào?'
UNKNOWN = 'Mình chưa có thông tin được xác nhận. Mình ghi câu hỏi để tuyển dụng kiểm tra. Bạn muốn tiếp tục hay dừng?'


# %%
# Intent classification and source selection are trusted adapter inputs, not NLU
# performed here. Text alone does not establish a confirmed intent.
class Input(Model):
    turn_id: ID
    text: Text
    intent: Literal['continue', 'skip', 'clarify', 'correction', 'end', 'faq', 'restricted', 'sensitive'] = 'continue'
    target_turn_id: ID | None = None
    source_refs: list[SourceRef] = Field(default_factory=list, max_length=20)


# A schema-valid proposal still needs policy checks before it can affect output.
class Proposal(Model):
    action: Action
    criterion: ID | None = None
    evidence_turn_ids: list[ID] = Field(default_factory=list, max_length=100)
    source_refs: list[SourceRef] = Field(default_factory=list, max_length=20)
    question: Text | None = None


# %%
# Caller-owned session state is copied per decision; persistence and concurrent
# update control belong to the caller, not this in-memory policy gate.
@dataclass
class State:
    deadline: datetime
    phase: str = 'experience'
    campaign_version: int = 1
    index: int = 0
    followups: int = 0
    clarifications: int = 0
    ended: bool = False
    turns: dict = field(default_factory=dict)
    corrections: list = field(default_factory=list)
    refused: list = field(default_factory=list)
    results: dict = field(default_factory=dict, repr=False, compare=False)


# Return selected wording and next state, not proof of media delivery.
@dataclass
class Decision:
    action: Action
    text: str
    reason: str
    source_refs: list
    state: State


# %%
# Safety and lifecycle gates precede cached replay. Reused turn IDs with different
# payloads fail when replay is reached. Only reviewed catalog text may be spoken;
# a structurally approved campaign alone does not approve arbitrary wording.
def decide(c: Campaign, state: State, event: Input, now: datetime, proposal=None):
    import copy
    s = copy.deepcopy(state)
    digest = hashlib.sha256(json.dumps(event.model_dump(mode='json'), sort_keys=True,
                                      ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest()

    def emit(action, text, reason, refs=None):
        result = Decision(action, text, reason, refs or [], s)
        # Only a canonical payload digest and safe output; never retain raw private input.
        s.results[event.turn_id] = (digest, (action, text, reason, refs or []))
        return result

    if event.intent == 'end' or s.ended:
        s.ended = True
        return emit('end', '', 'candidate_end' if event.intent == 'end' else 'already_ended')
    if c.status != 'approved' or s.campaign_version != c.version:
        return emit('wrap', 'Phiên chưa sẵn sàng.', 'snapshot_invalid')
    if now >= s.deadline:
        s.phase = 'wrap'
        return emit('wrap', 'Thời gian phỏng vấn đã hết. Cảm ơn bạn.', 'deadline')
    if s.phase not in ('basic_info', 'experience', 'light_technical', 'candidate_qa', 'wrap'):
        return emit('wrap', 'Phiên chưa sẵn sàng.', 'phase_invalid')
    if s.phase == 'wrap':
        s.ended = True
        return emit('end', '', 'completed')
    if event.turn_id in s.results:
        old_digest, cached = s.results[event.turn_id]
        if old_digest != digest:
            raise ValueError('turn payload conflict')
        return Decision(*cached, s)
    # Sensitive voluntary text is not retained or echoed by this minimal controller.
    if event.intent == 'sensitive':
        return emit('advance', 'Bạn không cần chia sẻ chi tiết riêng tư. Bạn muốn tiếp tục hay dừng?', 'data_minimization')
    if event.intent == 'restricted':
        return emit('advance', 'Mình không thể chia sẻ dữ liệu riêng tư hoặc nội dung bảo mật. Bạn muốn tiếp tục hay dừng?', 'private_information')
    if event.intent == 'correction':
        if event.target_turn_id not in s.turns or any(x['target'] == event.target_turn_id for x in s.corrections):
            return emit('advance', 'Mình chưa xác nhận được lượt cần sửa.', 'invalid_correction')
        s.turns[event.turn_id] = event.text
        s.corrections.append({'target': event.target_turn_id, 'replacement': event.turn_id})
        return emit('advance', 'Mình đã ghi nhận phần sửa của bạn.', 'correction_appended')
    s.turns[event.turn_id] = event.text
    if event.intent == 'skip':
        s.refused.append({'turn_id': event.turn_id, 'collection_status': 'refused', 'value': None})
        s.index += 1
        s.followups = 0
        return emit('advance', 'Bạn có thể bỏ qua và không bị đánh giá bất lợi. Bạn muốn tiếp tục không?', 'refused')
    if event.intent == 'faq':
        sources = {(x.id, x.version): x for x in c.faq}
        refs = [(x.id, x.version) for x in event.source_refs]
        selected = [sources[x] for x in refs if x in sources]
        reason = 'source_missing'
        if refs and len(selected) == len(refs):
            if any(not (x.effective_from <= now < x.effective_to) for x in selected):
                reason = 'source_expired'
            elif len({x.content for x in selected}) > 1:
                reason = 'source_conflict'
            elif all(x.id in FAQ and x.content == FAQ[x.id] for x in selected):
                return emit('answer_faq', selected[0].content + ' Bạn muốn tiếp tục không?', 'source_available', refs)
        texts = {'source_expired': 'Nguồn đã hết hiệu lực. ', 'source_conflict': 'Các nguồn hiện chưa thống nhất. '}
        return emit('answer_faq', texts.get(reason, '') + UNKNOWN, reason, refs)
    question_index = s.index - 1 if (proposal is not None or event.intent == 'clarify') and s.index > 0 else s.index
    q = c.questions[question_index] if question_index < len(c.questions) else None
    if event.intent == 'clarify':
        if s.clarifications < c.clarifications_per_session and q and CORE.get(q.id) == q.text:
            s.clarifications += 1
            return emit('clarify', q.text, 'clarification')
        return emit('advance', 'Mình chưa có đủ bằng chứng. Bạn có muốn bỏ qua không?', 'clarification_limit')
    reason = 'core'
    if proposal is not None:
        try:
            p = Proposal.model_validate(proposal)
            valid = (q is not None and p.criterion == q.criterion_id
                     and all(t in s.turns and not any(x['target'] == t for x in s.corrections) for t in p.evidence_turn_ids)
                     and not p.source_refs)
            if valid and p.evidence_turn_ids and p.action == 'ask_followup' and p.question == FOLLOWUP and s.followups < c.followups_per_topic:
                s.followups += 1
                return emit('ask_followup', FOLLOWUP, 'followup')
            if not (valid and p.action == 'ask_core' and p.question in (None, q.text)):
                reason = 'proposal_policy_fallback'
        except ValueError:
            reason = 'proposal_schema_fallback'
    # An invalid proposal must not re-ask a core question already selected.
    q = c.questions[s.index] if s.index < len(c.questions) else None
    if q and CORE.get(q.id) == q.text:
        s.index += 1
        s.followups = 0
        return emit('ask_core', q.text, reason)
    s.phase = 'wrap'
    return emit('wrap', 'Cảm ơn bạn đã tham gia.', 'questions_complete' if q is None else 'content_not_approved')
