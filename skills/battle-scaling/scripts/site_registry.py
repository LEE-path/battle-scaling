"""Append-only local observations of public source-reading methods.

This module does not browse, execute site text, authenticate evidence, or infer
that an entire site is available. A saved URL is only a candidate for rechecking.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import sqlite3
from typing import Any
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import uuid

SKILL_ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = SKILL_ROOT / 'assets' / 'site-experience-seeds.json'
OUTCOMES = {'readable', 'partial', 'blocked', 'error', 'fetched_unreviewed', 'not_found', 'indexed_only'}
EVIDENCE_KINDS = {'local_receipt', 'host_tool_result', 'historical_ledger'}
PUBLIC_QUERY_KEYS = {'chapternumber', 'chapter', 'chapterid', 'page', 'p', 'id', 'sn', 'book', 'bookid',
    'volume', 'vol', 'cid', 'aid', 'index', 'part', 'episode', 'ep', 'v'}
EVENT_KEYS = {'event_id', 'url', 'method', 'outcome', 'observed_at', 'observed_precision', 'categories',
    'works', 'issues', 'notes', 'query_examples', 'path_pattern', 'evidence'}
LIST_KEYS = ('categories', 'works', 'issues', 'notes', 'query_examples')
SCHEMA = '''
CREATE TABLE IF NOT EXISTS site_events (
    event_id TEXT PRIMARY KEY,
    domain TEXT NOT NULL,
    method TEXT NOT NULL,
    url TEXT NOT NULL,
    outcome TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS site_events_domain_method ON site_events(domain, method, observed_at);
CREATE TRIGGER IF NOT EXISTS site_events_no_update BEFORE UPDATE ON site_events
BEGIN SELECT RAISE(ABORT, 'site events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS site_events_no_delete BEFORE DELETE ON site_events
BEGIN SELECT RAISE(ABORT, 'site events are append-only'); END;
'''


def default_db() -> Path:
    """Dynamic experience is independent of immutable package assets."""
    override = os.environ.get('BATTLE_SITE_DB')
    return Path(override).expanduser() if override else SKILL_ROOT / 'data' / 'site-experience' / 'registry.sqlite3'


def _text(value: Any, name: str, maximum: int = 10000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f'{name} must be a nonempty string of at most {maximum} characters')
    if any(ord(char) < 32 and char not in '\n\r\t' for char in value) or '\x7f' in value:
        raise ValueError(f'{name} contains control characters')
    return value.strip()


def _host(host: str) -> str:
    host = host.rstrip('.').lower()
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        try:
            host = host.encode('idna').decode('ascii')
        except UnicodeError as error:
            raise ValueError('Invalid hostname') from error
        if not host or len(host) > 253 or not re.fullmatch(r'[a-z0-9.-]+', host):
            raise ValueError('Invalid hostname')
        labels = host.split('.')
        if any(not label or len(label) > 63 or label.startswith('-') or label.endswith('-') for label in labels):
            raise ValueError('Invalid hostname')
        if len(labels) < 2 or labels[-1].isdigit() or host in {'localhost', 'localhost.localdomain'} or host.endswith(('.localhost', '.localdomain', '.local', '.internal')):
            raise ValueError('Local or ambiguous hosts are not source sites')
        return host
    if not address.is_global:
        raise ValueError('Only public HTTP(S) addresses are recorded')
    return str(address)


def normalize_url(value: Any) -> tuple[str, str]:
    """Validate literal host without DNS; drop fragments and nonpublic queries."""
    if not isinstance(value, str) or not value or len(value) > 8192 or any(ord(char) <= 32 or unicodedata.category(char) == 'Cc' for char in value):
        raise ValueError('URL must be HTTP(S), with no whitespace or control characters')
    try:
        parsed = urlsplit(value)
        if parsed.scheme.lower() not in {'https', 'http'} or not parsed.hostname:
            raise ValueError('Only HTTP(S) URLs are recorded')
        if parsed.username is not None or parsed.password is not None:
            raise ValueError('URLs containing credentials are refused')
        domain = _host(parsed.hostname)
        port = parsed.port
        if port is not None and not (1 <= port <= 65535):
            raise ValueError('Invalid URL port')
    except (ValueError, UnicodeError) as error:
        raise ValueError(f'Invalid source URL: {error}') from error
    netloc = '[' + domain + ']' if ':' in domain else domain
    if port is not None and port != (443 if parsed.scheme.lower() == 'https' else 80):
        netloc += ':' + str(port)
    public = []
    for key, val in parse_qsl(parsed.query, keep_blank_values=False, max_num_fields=200):
        # Known locator keys are the only retained fields. Tokens, session IDs,
        # search strings, signatures and unfamiliar fields are not persisted.
        if key.lower() in PUBLIC_QUERY_KEYS and 0 < len(val) <= 128 and re.fullmatch(r'[\w.,:@~-]+', val, re.UNICODE):
            public.append((key, val))
    return urlunsplit((parsed.scheme.lower(), netloc, parsed.path or '/', urlencode(public), '')), domain


def _timestamp(value: Any) -> str:
    value = _text(value, 'observed_at', 80)
    try:
        observed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as error:
        raise ValueError('observed_at must be timezone-aware ISO 8601') from error
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise ValueError('observed_at must include UTC or a timezone offset')
    return observed.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _event(raw: Any, seed: bool = False) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError('event must be an object')
    unknown = set(raw) - EVENT_KEYS
    if unknown:
        raise ValueError('Unknown event fields: ' + ', '.join(sorted(unknown)))
    url, domain = normalize_url(raw.get('url'))
    method = _text(raw.get('method'), 'method', 160)
    if any(char.isspace() for char in method):
        raise ValueError('method is a stable identifier, without whitespace')
    outcome = raw.get('outcome')
    if not isinstance(outcome, str) or outcome not in OUTCOMES:
        raise ValueError('Unknown outcome')
    result = {'url': url, 'domain': domain, 'method': method, 'outcome': outcome,
        'observed_at': _timestamp(raw.get('observed_at'))}
    if 'observed_precision' in raw:
        if not isinstance(raw['observed_precision'], str) or raw['observed_precision'] not in {'day', 'instant'}:
            raise ValueError('observed_precision must be day or instant')
        result['observed_precision'] = raw['observed_precision']
    for key in LIST_KEYS:
        values = raw.get(key, [])
        if not isinstance(values, list) or len(values) > 100:
            raise ValueError(f'{key} must be an array of at most 100 strings')
        result[key] = list(dict.fromkeys(_text(value, key, 4000) for value in values))
    if 'path_pattern' in raw:
        result['path_pattern'] = _text(raw['path_pattern'], 'path_pattern', 2048)
    evidence = raw.get('evidence')
    if not isinstance(evidence, dict) or not isinstance(evidence.get('kind'), str) or evidence.get('kind') not in EVIDENCE_KINDS:
        raise ValueError('evidence.kind must identify a receipt, host tool result, or historical ledger')
    if set(evidence) - {'kind', 'locator', 'ref', 'sha256', 'checked_by'}:
        raise ValueError('Unknown evidence fields')
    proof = {'kind': evidence['kind']}
    for key in ('locator', 'ref', 'checked_by'):
        if key in evidence:
            proof[key] = _text(evidence[key], 'evidence.' + key, 4096)
    if not (proof.get('locator') or proof.get('ref')):
        raise ValueError('evidence needs a nonempty locator or ref')
    if 'sha256' in evidence:
        if not isinstance(evidence['sha256'], str) or not re.fullmatch(r'[a-fA-F0-9]{64}', evidence['sha256']):
            raise ValueError('evidence.sha256 must be a 64-digit hex digest')
        proof['sha256'] = evidence['sha256'].lower()
    result['evidence'] = proof
    if 'event_id' in raw:
        event_id = _text(raw['event_id'], 'event_id', 200)
    elif seed:
        event_id = 'seed-' + hashlib.sha256(_canonical(result).encode('utf-8')).hexdigest()
    else:
        event_id = str(uuid.uuid4())
    result['event_id'] = event_id
    return result


def _insert(conn: sqlite3.Connection, event: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    old = conn.execute('SELECT payload_json FROM site_events WHERE event_id = ?', (event['event_id'],)).fetchone()
    if old:
        saved = json.loads(old[0])
        comparable = {key: value for key, value in saved.items() if key != 'recorded_at'}
        if comparable != event:
            raise ValueError('event_id already exists with different observation data; append a new event instead')
        return saved, False
    saved = {**event, 'recorded_at': _now()}
    conn.execute('INSERT INTO site_events (event_id,domain,method,url,outcome,observed_at,recorded_at,payload_json) VALUES (?,?,?,?,?,?,?,?)',
        (saved['event_id'], saved['domain'], saved['method'], saved['url'], saved['outcome'],
         saved['observed_at'], saved['recorded_at'], _canonical(saved)))
    return saved, True


def _connect(db: Path, include_seeds: bool) -> sqlite3.Connection:
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db), timeout=30, isolation_level=None)
    conn.execute('PRAGMA busy_timeout = 30000')
    try:
        conn.executescript(SCHEMA)
        if include_seeds and SEED_PATH.is_file():
            data = json.loads(SEED_PATH.read_text(encoding='utf-8-sig'))
            if not isinstance(data, dict) or data.get('schema_version') != 1 or not isinstance(data.get('events'), list):
                raise ValueError('Invalid site-experience seed asset')
            seeds = [_event(item, seed=True) for item in data['events']]
            conn.execute('BEGIN IMMEDIATE')
            try:
                for seed in seeds:
                    _insert(conn, seed)
                conn.commit()
            except BaseException:
                conn.rollback()
                raise
        return conn
    except BaseException:
        conn.close()
        raise


def _domain_filter(value: Any) -> str:
    value = _text(value, 'domain', 1024)
    if '://' in value:
        return normalize_url(value)[1]
    return _host(value.strip('[]'))


def _limit(request: dict[str, Any], default: int = 20) -> int:
    limit = request.get('limit', default)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
        raise ValueError('limit must be an integer from 1 to 1000')
    return limit


def _rows(conn: sqlite3.Connection, domain: str | None = None, method: str | None = None) -> list[dict[str, Any]]:
    clause, args = [], []
    if domain is not None:
        clause.append('(domain = ? OR domain LIKE ? ESCAPE \'\\\')')
        args.extend((domain, '%.' + domain.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')))
    if method is not None:
        clause.append('method = ?')
        args.append(method)
    sql = 'SELECT payload_json FROM site_events'
    if clause:
        sql += ' WHERE ' + ' AND '.join(clause)
    # ISO UTC strings are normalized, but datetime comparison also handles
    # presence/absence of subsecond precision consistently.
    rows = [json.loads(row[0]) for row in conn.execute(sql, args)]
    return sorted(rows, key=lambda item: (datetime.fromisoformat(item['observed_at'].replace('Z', '+00:00')), item['recorded_at'], item['event_id']), reverse=True)


def _find(conn: sqlite3.Connection, request: dict[str, Any]) -> dict[str, Any]:
    limit = _limit(request)
    event_limit = request.get('event_limit', 20)
    if isinstance(event_limit, bool) or not isinstance(event_limit, int) or not 1 <= event_limit <= 200:
        raise ValueError('event_limit must be an integer from 1 to 200')
    domain = _domain_filter(request['domain']) if request.get('domain') is not None else None
    method = _text(request['method'], 'method', 160) if request.get('method') is not None else None
    filters = {key: _text(request[key], key, 4000).casefold() for key in ('query', 'category', 'work') if request.get(key) is not None}
    matching = []
    for item in _rows(conn, domain, method):
        if filters.get('category') and filters['category'] not in [value.casefold() for value in item['categories']]:
            continue
        if filters.get('work') and filters['work'] not in [value.casefold() for value in item['works']]:
            continue
        if filters.get('query') and filters['query'] not in _canonical(item).casefold():
            continue
        matching.append(item)
    groups = {}
    for item in matching:
        key = (item['domain'], item['method'])
        if key not in groups:
            if len(groups) >= limit:
                continue
            groups[key] = []
        groups[key].append(item)
    results = []
    for (host, read_method), events in groups.items():
        successes = [item['observed_at'] for item in events if item['outcome'] == 'readable']
        failures = [item['observed_at'] for item in events if item['outcome'] in {'blocked', 'error', 'not_found'}]
        outcome_times = {state: next((item['observed_at'] for item in events if item['outcome'] == state), None) for state in sorted(OUTCOMES)}
        all_experiences = {key: list(dict.fromkeys(value for item in events for value in item.get(key, []))) for key in LIST_KEYS}
        all_experiences['path_patterns'] = list(dict.fromkeys(item['path_pattern'] for item in events if item.get('path_pattern')))
        experiences = {key: values[:20] for key, values in all_experiences.items()}
        displayed_events = events[:event_limit]
        results.append({'domain': host, 'method': read_method, 'events': displayed_events,
            'event_count': len(events), 'events_truncated': len(events) > event_limit,
            'candidate_urls': list(dict.fromkeys(item['url'] for item in displayed_events)),
            'last_success_at': successes[0] if successes else None,
            'last_failure_at': failures[0] if failures else None,
            'last_observed_by_outcome': outcome_times,
            'experiences': experiences,
            'experience_counts': {key: len(values) for key, values in all_experiences.items()},
            'experience_truncated': {key: len(values) > 20 for key, values in all_experiences.items()},
            'history_refs': [item['event_id'] for item in displayed_events],
            'scope': 'matching_observed_pages_works_and_method_only', 'recheck_required': True})
    return {'status': 'ok', 'results': results, 'group_count': len(results),
        'matching_event_count': len(matching), 'recheck_required': True,
        'validation_scope': 'recorded_metadata_only; not source authenticity or semantic verification'}


def run(request: dict[str, Any]) -> dict[str, Any]:
    """Record, find, inspect history, or export. No update/delete operation."""
    if not isinstance(request, dict):
        raise ValueError('request must be an object')
    op = request.get('op')
    if not isinstance(op, str) or op not in {'record', 'find', 'history', 'export'}:
        raise ValueError('op must be record, find, history, or export')
    include_seeds = request.get('include_seeds', True)
    if not isinstance(include_seeds, bool):
        raise ValueError('include_seeds must be boolean')
    raw_db = request.get('db')
    if raw_db is not None and not isinstance(raw_db, (str, Path)):
        raise ValueError('db must be a filesystem path')
    db = Path(raw_db).expanduser() if raw_db is not None else default_db()
    event = _event(request.get('event')) if op == 'record' else None
    if op == 'export':
        output = Path(_text(request.get('output'), 'output', 4096)).expanduser()
        if output.resolve() == db.resolve():
            raise ValueError('Export must not overwrite the registry database')
    conn = _connect(db, include_seeds)
    try:
        if op == 'record':
            conn.execute('BEGIN IMMEDIATE')
            try:
                saved, appended = _insert(conn, event)
                conn.commit()
            except BaseException:
                conn.rollback()
                raise
            result = {'status': 'ok', 'event': saved, 'appended': appended}
        elif op == 'find':
            result = _find(conn, request)
        elif op == 'history':
            domain = _domain_filter(request.get('domain'))
            method = _text(request['method'], 'method', 160) if request.get('method') is not None else None
            rows = _rows(conn, domain, method)
            result = {'status': 'ok', 'domain': domain, 'events': rows[:_limit(request, 1000)],
                'total_event_count': len(rows), 'recheck_required': True}
        else:
            rows = _rows(conn)
            snapshot = {'schema_version': 1, 'exported_at': _now(), 'events': rows,
                'recheck_required': True, 'validation_scope': 'recorded_metadata_only'}
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            result = {'status': 'ok', 'output': str(output), 'event_count': len(rows)}
        return {**result, 'db': str(db)}
    finally:
        conn.close()


def record_fetch(result: dict[str, Any], db: str | Path | None = None) -> dict[str, Any]:
    """Log a real sources receipt; successful transport remains unreviewed."""
    if not isinstance(result, dict):
        raise ValueError('fetch result must be an object')
    url = result.get('final_url') or result.get('original_url')
    if result.get('source_kind') == 'local_file' or not isinstance(url, str) or urlsplit(url).scheme.lower() not in {'http', 'https'}:
        return {'status': 'skipped', 'reason': 'Only HTTP(S) source fetches contribute site observations'}
    state = result.get('status')
    mapped = {'ok': 'fetched_unreviewed', 'partial': 'partial', 'blocked': 'blocked', 'error': 'error',
        'needs_extractor': 'partial'}
    if not isinstance(state, str) or state not in mapped:
        raise ValueError('Unknown sources fetch status')
    paths = result.get('paths')
    if not isinstance(paths, dict):
        raise ValueError('Fetch result needs receipt paths')
    proof = {'kind': 'local_receipt', 'locator': paths.get('metadata'), 'checked_by': 'sources.fetch_source'}
    if result.get('sha256') is not None:
        proof['sha256'] = result['sha256']
    issues = []
    for key in ('needs', 'warnings', 'errors'):
        values = result.get(key, [])
        if isinstance(values, list):
            issues.extend(value for value in values if isinstance(value, str) and value.strip())
    event = {'url': url, 'method': 'python.sources', 'outcome': mapped[state],
        'observed_at': result.get('accessed_at'), 'evidence': proof, 'issues': issues[:100],
        'notes': ['Transport/extraction receipt only; readable requires host review of the requested original text.']}
    return run({'op': 'record', 'db': db, 'event': event})
