"""Bounded anonymous Tieba collection with page receipts and honest coverage.

The optional aiotieba worker reads public client APIs. This module uses only the
standard library; it never imports browser cookies or installs dependencies.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
VERSION = '1.0.0'
OPS = {'forum', 'search', 'thread', 'comments'}


def _now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def _bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False) + '\n').encode('utf-8')


def _write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Replace only this generated file; interrupted runs retain completed pages.
    temporary = path.with_name(path.name + '.writing')
    temporary.write_bytes(_bytes(value))
    temporary.replace(path)


def _integer(value, name, minimum=1, maximum=100000):
    if isinstance(value, bool) or not re.fullmatch(r'[0-9]+', str(value)):
        raise ValueError(f'{name} must be an integer')
    value = int(value)
    if not minimum <= value <= maximum:
        raise ValueError(f'{name} must be between {minimum} and {maximum}')
    return value


def _tid(request):
    if request.get('url'):
        parsed = urlsplit(request['url'])
        host = parsed.hostname or ''
        if (parsed.scheme != 'https' or parsed.username or parsed.password
                or parsed.port not in (None, 443)
                or not (host == 'tieba.baidu.com' or host.endswith('.tieba.baidu.com'))):
            raise ValueError('thread URL must be an HTTPS Baidu Tieba URL without credentials')
        match = re.fullmatch(r'/p/([0-9]+)/?', parsed.path)
        if not match:
            raise ValueError('thread URL must have /p/<numeric thread ID>')
        result = match[1]
        if request.get('tid') and str(request['tid']) != result:
            raise ValueError('tid and URL refer to different threads')
    else:
        result = str(request.get('tid', ''))
    return str(_integer(result, 'tid', maximum=10**18))


def _text(value, name, maximum=200):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f'{name} must be a nonempty string of at most {maximum} characters')
    if any(ord(c) < 32 for c in value):
        raise ValueError(f'{name} contains control characters')
    return value.strip()


def _python(request):
    configured = request.get('python') or os.environ.get('BATTLE_TIEBA_PYTHON')
    if not configured:
        config = ROOT / 'runtime' / 'local-tools.json'
        if config.is_file():
            configured = json.loads(config.read_text(encoding='utf-8-sig')).get('tieba_python')
    executable = Path(configured or sys.executable).expanduser()
    if not executable.is_file():
        raise ValueError('Tieba Python does not exist; configure BATTLE_TIEBA_PYTHON')
    return str(executable.resolve())


def _call_worker(request, python, timeout):
    # No shell interpolation or credentials in arguments. One read request/page.
    completed = subprocess.run(
        [python, '-X', 'utf8', str(ROOT / 'scripts' / 'tieba_aiotieba.py')],
        input=json.dumps(request, ensure_ascii=False), text=True, encoding='utf-8',
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout + 10,
        env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
    try:
        payload = json.loads(completed.stdout)
    except (ValueError, TypeError) as exc:
        # Worker stderr is intentionally not copied into evidence: SDK logs may
        # contain fields unrelated to the public response.
        raise ValueError('Tieba worker did not return a JSON response') from exc
    if not isinstance(payload, dict):
        raise ValueError('Tieba worker returned a non-object response')
    return payload


def _items(payload, op):
    key = {'forum': 'threads', 'search': 'threads', 'thread': 'posts', 'comments': 'comments'}[op]
    result = payload.get(key, payload.get('items', []))
    if not isinstance(result, list) or any(not isinstance(x, dict) for x in result):
        raise ValueError('Tieba response items are malformed')
    return result


def _pagination(payload):
    return payload.get('pagination') or payload.get('page') or {}


def _identity(item, op):
    key = 'tid' if op in ('forum', 'search') else 'pid'
    identity = item.get(key) or item.get('id')
    if not identity or not str(identity).isdigit():
        raise ValueError(f'Tieba {op} item has no numeric {key}')
    if op == 'search' and item.get('pid'):
        pid = str(item['pid'])
        if not pid.isdigit():
            raise ValueError('Tieba search item has no numeric pid')
        return str(identity) + ':' + pid
    return str(identity)


def _error(payload):
    status = payload.get('status')
    if payload.get('ok') is False or status in ('error', 'blocked', 'not_found', 'needs_configuration'):
        return status or 'error'
    if payload.get('error'):
        return 'error'
    return None


def _source_url(request):
    op = request['op']
    if op in ('thread', 'comments'):
        result = f"https://tieba.baidu.com/p/{request['tid']}?pn={request['pn']}"
        if op == 'comments':
            result += f"&pid={request['pid']}"
        return result
    # Search terms are recorded as task metadata, not appended to saved URLs.
    return f"https://tieba.baidu.com/f?pn={request['pn']}"


def _media(items, op):
    found = []
    by_url = {}
    def walk(value, context):
        if isinstance(value, str):
            if value.startswith(('https://', 'http://')):
                parsed = urlsplit(value)
                # Public image addresses only; no inferred 'original' rewrite.
                if parsed.hostname and (parsed.hostname.endswith('.baidu.com')
                        or parsed.hostname.endswith('.bdimg.com')
                        or parsed.hostname in ('imgsa.baidu.com', 'tiebapic.baidu.com')):
                    if value not in by_url:
                        by_url[value] = {**context, 'url': value, 'usages': []}
                        found.append(by_url[value])
                    if context not in by_url[value]['usages']:
                        by_url[value]['usages'].append(dict(context))
        elif isinstance(value, dict):
            for key, entry in value.items():
                if key.lower().endswith(('url', 'src')) or isinstance(entry, (dict, list)):
                    walk(entry, {**context, 'field': key})
        elif isinstance(value, list):
            for entry in value:
                walk(entry, context)
    for item in items:
        context = {'op': 'comments' if item.get('kind') == 'comment' else op,
                   'post_id': item.get('pid'), 'thread_id': item.get('tid'),
                   'floor': item.get('floor'), 'source_id': item.get('source_id')}
        walk(item.get('media', item.get('images', [])), context)
    return found


def _record(snapshot_path, receipt, request, db=None):
    from site_registry import run as record
    payload = receipt['response']
    state = _error(payload)
    outcome = 'blocked' if state == 'blocked' else ('error' if state else 'fetched_unreviewed')
    observation = {'event_id': receipt['source_id'], 'url': _source_url(request),
                   'method': 'python.tieba.aiotieba', 'outcome': outcome,
                   'observed_at': receipt['captured_at'], 'categories': ['community', 'tieba'],
                   'works': [(payload.get('forum') or {}).get('name') or request.get('forum') or '贴吧（吧名未核）'],
                   'notes': ['Decoded SDK response snapshot; not original HTTP bytes. '
                             'Extraction does not certify community claims or full historical coverage.'],
                   'evidence': {'kind': 'local_receipt', 'locator': str(snapshot_path),
                                'sha256': hashlib.sha256(snapshot_path.read_bytes()).hexdigest(),
                                'checked_by': 'tieba.collector'}}
    return record({'op': 'record', 'db': db, 'event': observation})


class Collector:
    def __init__(self, request, output):
        self.request = request
        self.output = output
        self.python = _python(request)
        self.timeout = _integer(request.get('timeout', 25), 'timeout', 5, 60)
        self.limit = _integer(request.get('max_requests', 100), 'max_requests', 1, 1000)
        self.delay = float(request.get('delay', 1.0))
        if not 0.5 <= self.delay <= 30:
            raise ValueError('delay must be between 0.5 and 30 seconds')
        self.count = 0
        self.resumed = 0
        self.last_request = None
        self.halted = False
        self.sources = []
        self.warnings = []

    def page(self, request):
        key = hashlib.sha256(_bytes(request)).hexdigest()
        folder = self.output / 'pages'
        folder.mkdir(parents=True, exist_ok=True)
        index_path = folder / (key + '.latest.json')
        path = folder / (key + '.json')  # Compatibility with the first capture format.
        hash_path = folder / (key + '.sha256')
        expected_digest = None
        if index_path.is_file():
            index = json.loads(index_path.read_text(encoding='utf-8'))
            name = index.get('capture', '')
            if not isinstance(name, str) or Path(name).name != name or not name.startswith(key + '.capture-'):
                raise ValueError('Invalid Tieba cache capture locator')
            path = folder / name
            expected_digest = index.get('sha256')
        elif hash_path.is_file():
            expected_digest = hash_path.read_text(encoding='ascii').strip()
        if self.request.get('resume', True) and path.is_file() and expected_digest:
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != expected_digest:
                raise ValueError('Saved Tieba page hash mismatch; do not resume changed evidence')
            receipt = json.loads(raw)
            if receipt.get('request') != request:
                raise ValueError('Saved Tieba page request mismatch')
            if not _error(receipt['response']):
                self.resumed += 1
                self.sources.append({'id': receipt['source_id'], 'path': str(path),
                                     'sha256': hashlib.sha256(raw).hexdigest(),
                                     'url': _source_url(request), 'resumed': True,
                                     'captured_at': receipt['captured_at'], 'live_revalidated': False})
                return receipt['response'], receipt['source_id']
        if self.halted:
            raise RequestBudget('stopped after a blocked or failed response')
        if self.count >= self.limit:
            raise RequestBudget('max_requests reached')
        if self.last_request is not None:
            remaining = self.delay - (time.monotonic() - self.last_request)
            if remaining > 0:
                time.sleep(remaining)
        try:
            response = _call_worker(request, self.python, self.timeout)
        except (subprocess.TimeoutExpired, OSError, ValueError) as exc:
            response = {'ok': False, 'status': 'error',
                        'error': {'type': type(exc).__name__, 'message': str(exc)}}
        self.count += 1
        if _error(response):
            self.halted = True
        self.last_request = time.monotonic()
        captured = _now()
        receipt = {'schema_version': 1, 'capture_kind': 'sdk_decoded_response',
                   'parser_version': VERSION, 'captured_at': captured,
                   'source_id': 'tieba-' + key[:16] + '-' + str(time.time_ns()),
                   'request': request, 'response': response}
        # Every capture gets an immutable path; old site-ledger locators stay valid.
        path = folder / (key + '.capture-' + str(time.time_ns()) + '.json')
        _write(path, receipt)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        _write(index_path, {'capture': path.name, 'sha256': digest})
        self.sources.append({'id': receipt['source_id'], 'path': str(path), 'sha256': digest,
                             'url': _source_url(request), 'resumed': False,
                             'captured_at': captured, 'live_revalidated': True})
        try:
            _record(path, receipt, request, self.request.get('db'))
        except (ValueError, OSError) as exc:
            self.warnings.append('site registry pending: ' + str(exc))
        return response, receipt['source_id']

    def collect(self, base, max_pages):
        start = _integer(base.get('pn', 1), 'pn')
        items = []
        seen = set()
        signatures = set()
        pages = []
        total = None
        complete = False
        reason = 'max_pages reached'
        latest = {}
        for pn in range(start, start + max_pages):
            request = {**base, 'pn': pn}
            try:
                payload, source_id = self.page(request)
            except RequestBudget as exc:
                reason = str(exc)
                break
            latest = payload
            state = _error(payload)
            if state:
                reason = state
                break
            page = _pagination(payload)
            actual = page.get('current_page', page.get('current', page.get('pn')))
            if actual is not None and int(actual) != pn:
                reason = 'returned page does not match requested page'
                break
            batch = _items(payload, base['op'])
            batch_ids = tuple(_identity(x, base['op']) for x in batch)
            if batch_ids and batch_ids in signatures:
                reason = 'repeated page response'
                break
            if batch_ids:
                signatures.add(batch_ids)
            if not batch and page.get('has_more') is True:
                reason = 'empty page with has_more=true'
                break
            for index, item in enumerate(batch):
                identity = _identity(item, base['op'])
                if identity not in seen:
                    seen.add(identity)
                    items.append({**item, 'source_id': source_id,
                                  'source_locator': f"page={pn}; item={index}; {identity}"})
            pages.append(pn)
            total = page.get('total_page', page.get('total_pages', total))
            if total is not None:
                total = _integer(total, 'returned total_page', 0, 10**12)
            more = page.get('has_more')
            conflict = total is not None and (
                (pn < total and more is False) or (pn >= total and more is True)
                or (total == 0 and bool(batch)) or (total > 0 and pn > total))
            if conflict:
                reason = 'pagination_conflict'
                break
            at_end = more is False or (total is not None and pn == total)
            if at_end:
                complete = start == 1
                reason = 'all currently API-visible pages fetched' if complete else 'started after page 1'
                break
            if not batch:
                reason = 'empty page without a confirmed end'
                break
        return items, {'pages': pages, 'reported_total_pages': total, 'complete': complete,
                       'reason': reason, 'scope': 'currently API-visible records; deleted or inaccessible records excluded'}, latest


class RequestBudget(Exception):
    pass


def run(request: dict[str, Any]):
    if not isinstance(request, dict):
        raise ValueError('Tieba request must be an object')
    if any(key.lower() in {'cookie', 'bduss', 'stoken', 'token', 'password'} for key in request):
        raise ValueError('This reader accepts no credentials; use anonymous public reads')
    for key in ('resume', 'include_subreplies', 'only_thread', 'only_thread_author'):
        if key in request and not isinstance(request[key], bool):
            raise ValueError(key + ' must be a JSON boolean')
    op = request.get('op')
    if op == 'doctor':
        python = _python(request)
        check = subprocess.run([python, '-c',
            "import importlib.metadata,json; print(json.dumps({'aiotieba':importlib.metadata.version('aiotieba')}))"],
            capture_output=True, text=True, encoding='utf-8', timeout=10)
        return {'status': 'ok' if check.returncode == 0 else 'needs_configuration',
                'python': python, 'dependencies': json.loads(check.stdout) if check.returncode == 0 else {},
                'network_tested': False, 'authentication': 'anonymous',
                'setup': 'Install aiotieba==4.8.1 in an isolated Python 3.11+ environment; set BATTLE_TIEBA_PYTHON'}
    if op not in OPS:
        raise ValueError('op must be doctor, forum, search, thread or comments')
    output = Path(_text(request.get('output_dir'), 'output_dir', 4096)).expanduser().resolve()
    if output == ROOT or output.is_relative_to(ROOT):
        raise ValueError('Save collected data outside the installed Skill directory')
    max_pages = _integer(request.get('max_pages', 3), 'max_pages', 1, 1000)
    base = {'op': op, 'pn': _integer(request.get('pn', 1), 'pn'),
            'rn': _integer(request.get('rn', 30), 'rn', 2,
                           30 if op == 'thread' else (50 if op == 'search' else 100)),
            'timeout': _integer(request.get('timeout', 25), 'timeout', 5, 60)}
    if op in ('thread', 'comments'):
        base['tid'] = _tid(request)
    if op in ('forum', 'search'):
        base['forum'] = _text(request.get('forum', '汪峰在'), 'forum', 100)
    if op == 'search':
        base['query'] = _text(request.get('query'), 'query')
        base['only_thread'] = bool(request.get('only_thread', False))
    if op == 'comments':
        base['pid'] = str(_integer(request.get('pid'), 'pid', maximum=10**18))
    if op == 'thread':
        base['only_thread_author'] = bool(request.get('only_thread_author', False))
    output.mkdir(parents=True, exist_ok=True)
    identity = {key: value for key, value in base.items() if key not in ('pn', 'timeout')}
    job_path = output / 'job.json'
    if job_path.is_file() and json.loads(job_path.read_text(encoding='utf-8')) != identity:
        raise ValueError('Output directory belongs to a different Tieba job; choose a new directory')
    _write(job_path, identity)
    collector = Collector(request, output)
    items, coverage, last = collector.collect(base, max_pages)
    comments = []
    comment_coverage = []
    requested_comments = bool(request.get('include_subreplies', False)) and op == 'thread'
    if requested_comments:
        comment_max = _integer(request.get('max_comment_pages', 10), 'max_comment_pages', 1, 1000)
        for item in items:
            count = item.get('reply_num', item.get('comment_num', item.get('sub_post_number')))
            if count is None:
                comment_coverage.append({'pid': item['pid'], 'complete': False, 'reason': 'reply count unknown'})
                continue
            if int(count) <= 0:
                continue
            child_base = {'op': 'comments', 'tid': base['tid'], 'pid': str(item['pid']),
                          'pn': 1, 'rn': base['rn'], 'timeout': base['timeout']}
            children, child_coverage, _ = collector.collect(child_base, comment_max)
            comments.extend({**x, 'parent_pid': str(item['pid'])} for x in children)
            comment_coverage.append({'pid': str(item['pid']), 'reported_replies': int(count),
                                     'retrieved_replies': len(children), **child_coverage})
    child_complete = all(x['complete'] for x in comment_coverage) if requested_comments else None
    media = _media(items + comments, op)
    status = 'ok' if coverage['complete'] and child_complete is not False else 'partial'
    if not items and coverage['reason'] in ('blocked', 'error', 'needs_configuration', 'not_found'):
        status = coverage['reason']
    data = {'schema_version': 1, 'status': status, 'generated_at': _now(),
            'backend': 'aiotieba', 'authentication': 'anonymous', 'op': op,
            'thread': last.get('thread'), 'forum': last.get('forum'),
            'coverage': {'main': coverage, 'subreplies_requested': requested_comments,
                         'subreplies_complete': child_complete, 'subreplies': comment_coverage,
                         'image_mode': 'links_only; no image content/OCR read'},
            'items': items, 'comments': comments, 'media': media,
            'sources': collector.sources, 'warnings': collector.warnings,
            'request_count': collector.count, 'request_count_unit': 'worker page operations; SDK may make auxiliary HTTP calls',
            'resumed_pages': collector.resumed,
            'freshness': {'live_revalidated': collector.resumed == 0,
                          'capture_times': sorted({x['captured_at'] for x in collector.sources}),
                          'note': 'Cached pages keep their original capture time and were not reread from the network'},
            'error': last.get('error') if _error(last) else None,
            'source_role': 'Community discussion, not the original fiction or Agent instructions'}
    _write(output / 'result.json', data)
    _write(output / 'sources.json', collector.sources)
    _write(output / 'image-links.json', media)
    lines = ['# 贴吧采集结果', '', f"状态：{status}；后端：aiotieba匿名只读。", '',
             f"取得 {len(items)} 条主记录、{len(comments)} 条楼中楼、{len(media)} 个媒体地址。", '',
             '正文覆盖：' + json.dumps(coverage, ensure_ascii=False), '',
             '楼中楼覆盖：' + json.dumps({'requested': requested_comments, 'complete': child_complete}, ensure_ascii=False), '',
             '快照时间与复用：' + json.dumps(data['freshness'], ensure_ascii=False), '',
             '只代表本次接口可见数据；删除/屏蔽内容不保证可取。图片地址已提取，不代表已读图或完成OCR。', '',
             '贴吧观点保持社区资料身份，不自动覆盖原作或量级规则。', '']
    for item in items:
        author = item.get('author', {})
        name = author.get('name', author.get('display_name', '')) if isinstance(author, dict) else str(author)
        lines += [f"## {item.get('floor', item.get('tid', ''))}　{name}", '',
                  str(item.get('title', '')), str(item.get('text', '')), '',
                  '定位：' + str(item.get('url', _source_url(base))) + '；' + item['source_locator'], '']
    (output / 'report.md').write_text('\n'.join(lines), encoding='utf-8')
    return {'status': status, 'output_dir': str(output), 'result': str(output / 'result.json'),
            'report': str(output / 'report.md'), 'sources': str(output / 'sources.json'),
            'image_links': str(output / 'image-links.json'),
            'counts': {'items': len(items), 'comments': len(comments), 'image_urls': len(media)},
            'coverage': data['coverage'], 'request_count': collector.count,
            'freshness': data['freshness'],
            'resumed_pages': collector.resumed, 'warnings': collector.warnings, 'error': data['error']}
