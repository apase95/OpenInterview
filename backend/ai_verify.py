# %%
"""Repeatable synthetic verification. Import/default execution never loads dotenv.

The default run writes fixture decisions and a pending listening review locally.
Only --live loads server configuration and permits paid, bounded HTTPS probes:
three TTS clips, three batch STT calls and two LLM calls, without retries.
Passing cases does not approve audio quality or browser/media integration.
"""
import argparse
import asyncio
from dataclasses import fields, asdict, is_dataclass
from datetime import date, datetime, timedelta, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import subprocess
import time
import unicodedata
import uuid

from backend.contracts import Bundle
from backend.controller import State, Input, decide

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'fixtures/ai/cases.json'
BASE = ROOT / 'fixtures/synthetic/v1.json'


# %%
def json_default(value):
    """Encode supported evidence dates and dataclasses; reject other objects."""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if is_dataclass(value):
        return asdict(value)
    raise TypeError('Unsupported evidence value type')


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=json_default) + '\n', encoding='utf-8')


def listening_review(output, audio):
    """Write review placeholders, linking only WAV files already present locally."""
    lines = ['# Listening review', '', 'Reviewer: PENDING', 'Date: PENDING',
             'Human listening: PENDING — no listening or quality approval claimed.', '']
    for clip in audio:
        wav = clip.get('wav')
        link = f"[Open WAV]({wav})" if wav and (output / wav).is_file() else 'WAV: PENDING (not generated)'
        lines += [f"## {clip['id']}", link, '', 'Gold: ' + clip['gold'],
                  '- Name pronunciation: PENDING', '- Number/time accuracy: PENDING',
                  '- Negation (chưa/không): PENDING', '- Intelligibility/truncation: PENDING',
                  '- Notes: PENDING', '']
    (output / 'listening-review.md').write_text('\n'.join(lines), encoding='utf-8')


# %%
def campaign():
    """Load the synthetic campaign and replace FAQ wording with approved content."""
    c = Bundle.model_validate_json(BASE.read_text()).campaigns[0]
    # Separate fixture content approval: never use arbitrary campaign wording.
    from backend.controller import FAQ
    c.faq[0].content = FAQ['syn_faq']
    return c


def normalize(text):
    return re.findall(r'\w+', unicodedata.normalize('NFC', text).casefold())


def error_rate(gold, actual):
    """Return word edit distance per reference word, not a quality acceptance gate."""
    a, b = normalize(gold), normalize(actual)
    row = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        new = [i]
        for j, y in enumerate(b, 1):
            new.append(min(new[-1] + 1, row[j] + 1, row[j-1] + (x != y)))
        row = new
    return row[-1] / max(1, len(a))


def execute(case, proposal_override=None):
    """Compare a deterministic controller result with the case's explicit expectations.

    An override tests proposal handling, not a live model or hiring outcome.
    """
    c = campaign()
    now = case.get('now', '2026-01-02T09:00:00+00:00')
    if isinstance(now, str):
        now = datetime.fromisoformat(now)
    options = dict(case.get('state', {}))
    expired = options.pop('expired', False)
    deadline = options.pop('deadline', now + timedelta(seconds=-1 if expired else c.time_budget_seconds))
    if isinstance(deadline, str):
        deadline = datetime.fromisoformat(deadline)
    s = State(deadline=deadline, **options)
    if case.get('jd'):
        c.jd = case['jd']
    if case.get('conflict'):
        c.faq.append(c.faq[0].model_copy(update={'id':'syn_other', 'content':'Mẫu làm thứ Bảy.'}))
    event = Input(turn_id='syn_' + case['id'], **case['input'])
    result = decide(c, s, event, now, proposal_override if proposal_override is not None else case.get('proposal'))
    actual = {'action':result.action, 'reason':result.reason, 'text':result.text,
              'source_refs':result.source_refs, 'state':{f.name:getattr(result.state, f.name) for f in fields(result.state) if f.name != 'results'}}
    actual['state']['deadline'] = result.state.deadline.isoformat()
    expected = case['expected']
    passed = all(actual[k] == v for k,v in expected.items()) and 'SYNTHETIC_FORBIDDEN' not in result.text
    return {'id':case['id'], 'input':case, 'expected':expected, 'actual':actual, 'passed':passed}


def offline():
    return [execute(c) for c in json.loads(FIXTURE.read_text())['cases']]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


# %%
async def live(output):
    """Load live configuration only on request and return safe setup failure metadata."""
    # Only this explicit server-side path may read the real env file.
    from backend.config import load_config
    from backend.ai_verify_live import probe
    try:
        config = load_config()
    except ValueError:
        return {'status':'failed', 'error':'configuration_invalid', 'attempts':0}
    return await probe(config, output, json.loads(FIXTURE.read_text()))


# %%
def main():
    """Run offline checks first, then optional probes, and write checksummed evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    start = time.perf_counter()
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    output = args.output_dir or ROOT / 'artifacts/ai' / run_id
    output.mkdir(parents=True, exist_ok=False)
    print('Run directory: ' + str(output), flush=True)
    rows = offline()
    provider = {'status':'not_requested'}
    if args.live and all(r['passed'] for r in rows):
        print('Live limit: 3 short TTS clips, 3 batch STT requests, 2 LLM requests; no retries. Human listening pending.', flush=True)
        try:
            provider = asyncio.run(live(output))
        except Exception:
            provider = {'status':'failed', 'error':'runner_failure; inspect safe provider checkpoint if present'}
    versions = {}
    for name in ('livekit-agents','livekit-plugins-google','livekit-plugins-deepgram','livekit-plugins-elevenlabs','pydantic'):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = 'not_installed'
    write_json(output / 'cases.json', rows)
    listening_review(output, [{**clip, **next((r for r in provider.get('audio', []) if r['id'] == clip['id']), {})}
                              for clip in json.loads(FIXTURE.read_text())['audio']])
    from backend.config import Config
    safe_config = {f.name:f.default for f in fields(Config) if f.repr}
    manifest = {'schema_version':'1.0', 'run_id':run_id, 'timestamp':datetime.now(timezone.utc).isoformat(),
                'git_revision':subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip(),
                'working_tree':'uncommitted changes included; fixture checksums identify inputs',
                'sdk_versions':versions, 'fixtures':{str(p.relative_to(ROOT)):sha(p) for p in (BASE,FIXTURE)},
                'source_checksums':{name:sha(ROOT / name) for name in ('backend/controller.py', 'backend/config.py', 'backend/ai_verify.py', 'backend/ai_verify_live.py')},
                'configuration':{'offline_defaults':safe_config, 'live_configured':provider.get('configured', 'not_requested'),
                                 'max_requests':{'tts':3, 'stt':3, 'llm':2}, 'timeout_seconds':45, 'retries':0},
                'offline':{'passed':sum(r['passed'] for r in rows), 'total':len(rows)},
                'live_requested':args.live, 'providers':provider, 'human_listening':'pending',
                'duration_seconds':round(time.perf_counter()-start,3),
                'artifacts':{p.name:sha(p) for p in output.iterdir() if p.is_file()}}
    write_json(output / 'manifest.json', manifest)
    summary = f"# AI verification {run_id}\n\nOffline: {manifest['offline']['passed']}/{len(rows)}.\nLive: {provider['status']}.\nHuman listening: pending.\n\nNo NLU, browser/media integration, report model, accents or production approval verified.\n"
    (output / 'summary.md').write_text(summary)
    print(summary + '\nArtifacts: ' + str(output))
    return 0 if all(r['passed'] for r in rows) and provider['status'] in ('not_requested','passed') else 1


# %%
if __name__ == '__main__':
    raise SystemExit(main())
