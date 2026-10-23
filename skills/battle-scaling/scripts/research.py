"""On-demand research planning and provenance-preserving local discovery (stdlib).

This module does not search original works autonomously, infer truth, or run models.
Call run(request) or `python research.py --request request.json`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlencode, urlsplit

import sources

DIMENSIONS = ('output', 'durability', 'intelligence', 'battle_iq', 'experience',
              'hax', 'destruction', 'speed', 'body_size')
LABELS = dict(zip(DIMENSIONS, ('输出', '体防', '智力', '战斗智商', '经验', '特殊技能', '破坏', '速度', '体量')))
SCOPE_FIELDS = ('entity_id', 'work_id', 'continuity', 'period', 'state')
SOURCE_ORIGINS = {'primary', 'official', 'paper', 'community', 'unknown', 'synthetic'}
SOURCE_ACCESS = {'verified', 'read', 'provided', 'indexed', 'unread', 'blocked', 'unknown'}
TEXT_KINDS = {'verbatim_source', 'community_summary', 'model_paraphrase', 'host_observation', 'unknown'}
MAX_RECORDS = 5000
MAX_IMPORT_BYTES = 16 * 1024 * 1024
CITED_DATA_URL = 'https://citedfeats.com/data/'
CITED_LICENSES = {
    'CC-BY-4.0': 'https://creativecommons.org/licenses/by/4.0/',
    'CC-BY-SA-3.0': 'https://creativecommons.org/licenses/by-sa/3.0/',
}


def _base(op, status='ok', **values):
    return {'schema_version': 1, 'operation': op, 'status': status,
            'needs': [], 'warnings': [], **values}


def _positive_int(value, name, maximum):
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
        raise ValueError(f'{name} must be an integer from 1 to {maximum}')
    return value


def _text(value, name, allow_none=False, maximum=200000):
    if allow_none and value is None:
        return value
    if not isinstance(value, str) or len(value) > maximum:
        raise ValueError(f'{name} must be a string up to {maximum} characters')
    return value


def _strings(value, name):
    if not isinstance(value, list) or any(not isinstance(x, str) or not x for x in value):
        raise ValueError(f'{name} must be a list of nonempty string identifiers')
    return value


def _discovery_routes(target,name,is_novel):
    """Expand known source carriers and relations without inventing feats or allies."""
    related=target.get('related_entities',[])
    if not isinstance(related,list) or len(related)>32:
        raise ValueError('related_entities must contain at most 32 explicit discovery nodes')
    nodes=[{'entity_id':target.get('entity_id'),'name':name,'relation':'character',
            'work_id':target.get('work_id'),'version':target.get('version'),'state':target.get('state')}]
    seen={target.get('entity_id')}
    roles={'equipment','ability','opponent','organization','location','document'}
    for item in related:
        if not isinstance(item,dict):raise ValueError('Each related entity must be an object')
        entity_id=_text(item.get('entity_id'),'related entity_id',maximum=2000).strip()
        label=_text(item.get('name'),'related name',maximum=2000).strip()
        if not entity_id or not label or entity_id in seen or item.get('relation') not in roles:
            raise ValueError('Related nodes need distinct IDs, names and a supported relation')
        seen.add(entity_id);nodes.append(dict(item))
    terms={
        'character':(('positive','表现 输出 承受 发动'),('counter','失败 破防 受限 代价')),
        'equipment':(('positive','持有 授予 招式 能力'),('counter','借用 失去 失效 限制')),
        'ability':(('positive','作用对象 发动 范围 持续'),('counter','免疫 无效化 反制 代价')),
        'opponent':(('positive','交战 命中 战果 配置'),('counter','克制 偷袭 留手 中断 败因')),
        'organization':(('positive','成员 科技 资源 调用'),('counter','外援 不在场 所有权 权限')),
        'location':(('positive','正文 环境 规模 结构'),('counter','局部 范围 例外 误读')),
        'document':(('positive','日志 附录 术语 条目'),('counter','版本 改写 摘要 转述'))}
    work=target.get('work',target.get('work_id',''))
    for node in nodes:
        node.update(declared_scope={key:node.get(key) for key in ('work_id','version','state')},
                    requires_attribution_bridge=node['relation']!='character',search_executed=False,
                    queries=[{'polarity':polarity,'query_hint':f'{work} {node["name"]} {words}',
                              'status':'planned','node_id':node['entity_id']}
                             for polarity,words in terms[node['relation']]])
    return {'nodes':nodes,'admission':'discovery_only','node_identity_verified':False,
        'carrier_order':(['ending_chapters','chapter_context','appendices_when_present','equipment_and_ability_entries']
                         if is_novel else ['original_scenes','official_entries','logs_and_appendices_when_present']),
        'evidence_axes':['carrier','evidence_nature','attribution','relationship','world_structure'],
        'interaction_questions':['actual_effect_and_object','activation_and_hit','own_effect_limit',
                                 'world_strongest_achieved','resistance_and_counterexamples','recovery_and_victory_window'],
        'coverage_rule':'Suggested queries are not completed attempts; log actual queries, providers, ranges and source IDs.'}


def plan(request):
    target = request.get('target', {})
    if not isinstance(target, dict):
        raise ValueError('target must be an object')
    missing = [field for field in SCOPE_FIELDS if not target.get(field)]
    modes = request.get('modes', ['integrated'])
    if not isinstance(modes, list) or not modes or any(x not in ('integrated', 'normal', 'highest', 'lowball') for x in modes):
        raise ValueError('modes must select integrated; legacy lenses require an explicit historical request')
    name = _text(target.get('name', target.get('entity_id', 'unresolved character')), 'name')
    is_novel = target.get('medium') == 'novel' or target.get('continuity') == 'novel'
    discovery_routes=_discovery_routes(target,name,is_novel)
    tasks = []
    for attribute in DIMENSIONS:
        for family, polarity, purpose in (
            ('original', 'positive', '取得原作实际表现、定位、完整上下文与配置'),
            ('original', 'counter', '查破防、失手、受限、免疫、代价及相冲突表现'),
            ('official', 'context', '核对官方身份、版本、时间、装备及设定适用范围'),
            ('community', 'discovery', '跨百科、论坛、书评或战报找线索，再回原作核验')):
            task_id = f'{attribute}:{family}:{polarity}'
            tasks.append({'task_id': task_id, 'attribute': attribute, 'source_family': family,
                'polarity': polarity, 'purpose': purpose, 'status': 'pending',
                'query_hint': f'{name} {LABELS[attribute]} ' + ('反例 失败 限制' if polarity == 'counter' else '章节 页码 集数'),
                'scope': dict(target), 'reading_order': 'ending_backward_per_attribute' if is_novel else 'locked_version_timeline',
                'start_locator': target.get('ending_locator') if is_novel else target.get('start_locator'),
                'continuity_required_for_earlier_evidence': True})
        if attribute in ('output', 'durability', 'destruction', 'speed', 'body_size'):
            tasks.append({'task_id': f'{attribute}:paper:parameters', 'attribute': attribute,
                'source_family': 'paper', 'polarity': 'parameters', 'status': 'conditional',
                'purpose': '仅需物理推算或动物资料时查物性、公式、实测/估计范围；不把论文直接当角色表现',
                'query_hint': '由已观察表现确定材质、物种、尺寸、时间及候选模型后再生成科学检索式',
                'scope': dict(target), 'activation_condition': 'physical_or_biological_parameter_needed'})
    return _base('plan', 'needs_scope' if missing else 'ok', target=target, modes=modes,
        dimensions=list(DIMENSIONS), dimension_labels=LABELS, tasks=tasks,
        rating_policy=('integrated_main_tier' if modes == ['integrated'] else 'explicit_legacy_context_research'),
        performance_contexts=['high_showing','typical_showing','low_showing'],
        legacy_mode=any(mode != 'integrated' for mode in modes),
        discovery_routes=discovery_routes,
        reading_order='ending_backward_per_attribute' if is_novel else 'locked_version_timeline',
        search_executed=False, needs=[f'Lock {field}; names alone do not establish identity or same state' for field in missing],
        site_experience={'lookup_request':{'op':'find',**({'category':'novel'} if is_novel else {}),
                                          **({'work':target['work']} if target.get('work') else {})},
                         'register_after_actual_attempts':True,'recheck_current_target':True,
                         'scope':'Host uses historical site/method/page experience to choose sources; this plan has not accessed any site.'},
        host_duties=['execute searches using available host tools', 'read original images/text and surrounding context',
                     'record positive and counter evidence', 'verify continuity before reusing older feats',
                     'send supported anchors/conditions to existing evidence and high-tier tools'],
        stop_rule='Budget or task completion may stop discovery; neither proves web exhaustion or claim truth',
        high_tier_discovery={'enabled_when': 'cosmology_or_scaling_needed',
            'collect': ['exact original wording and locator', 'entities, structures and quantified relations',
                        'scope, exclusions and counterexamples', 'same-state scaling bridges and their evidence'],
            'forbidden_shortcuts': ['Wiki rank to Wangba tier', 'adjective to mathematical infinity',
                                   'same name to composite identity', 'defeated to unrestricted superiority']})


def _validate_record(item):
    if not isinstance(item, dict):
        raise ValueError('Every record must be an object')
    for field in ('record_id', 'entity_id', 'work_id', 'source_id'):
        if not _text(item.get(field), field, maximum=2000):
            raise ValueError(f'{field} must be a nonempty stable identifier')
    for field in ('continuity', 'period', 'state'):
        _text(item.get(field), field, allow_none=True, maximum=2000)
    _strings(item.get('equipment', []), 'equipment')
    _strings(item.get('attributes', []), 'attributes')
    if item.get('source_origin') not in SOURCE_ORIGINS:
        raise ValueError('source_origin must be primary/official/paper/community/unknown/synthetic')
    if item.get('source_access') not in SOURCE_ACCESS:
        raise ValueError('Invalid source_access')
    if item.get('text_kind') not in TEXT_KINDS:
        raise ValueError('Invalid text_kind; keep quotes, summaries and paraphrases distinct')
    _text(item.get('exact_text'), 'exact_text')
    if 'locator' not in item or not isinstance(item['locator'], (dict, str, type(None))):
        raise ValueError('locator must be retained as an object, string or explicit null')
    sha = item.get('snapshot_sha256')
    if sha is not None and (not isinstance(sha, str) or not re.fullmatch(r'[a-fA-F0-9]{64}', sha)):
        raise ValueError('snapshot_sha256 must be a 64-hex digest of actual source bytes, or null')
    if item['text_kind'] == 'community_summary' and item['source_origin'] != 'community':
        raise ValueError('A community summary cannot be promoted to primary/official/paper')
    if item['source_access'] == 'verified':
        if item['source_origin'] in ('community', 'unknown', 'synthetic'):
            raise ValueError('Community/indexed clues cannot become primary or verified by indexing')
        verification = item.get('verification', {})
        if not isinstance(verification, dict) or verification.get('original_checked') is not True or not verification.get('checked_by') or not sha:
            raise ValueError('verified requires explicit original_checked, checked_by and original snapshot hash; indexer never verifies')
    # Roundtrip through JSON before any writes; reject NaN/Infinity and non-JSON payloads.
    return json.dumps(item, ensure_ascii=False, sort_keys=True, allow_nan=False)


def _fts_available(connection):
    try:
        connection.execute('CREATE VIRTUAL TABLE IF NOT EXISTS research_fts USING fts5(record_id UNINDEXED, content)')
        return True
    except sqlite3.OperationalError:
        return False


def _connect(db, *, create=False):
    if not isinstance(db, str) or not db:
        raise ValueError('An explicit local db path is required')
    path = Path(db).expanduser().resolve()
    if create:
        path.parent.mkdir(parents=True, exist_ok=True)
    elif not path.is_file():
        raise ValueError('Research index does not exist; call index explicitly first')
    connection = sqlite3.connect(str(path))
    connection.execute('CREATE TABLE IF NOT EXISTS research_records (record_id TEXT PRIMARY KEY, entity_id TEXT NOT NULL, work_id TEXT NOT NULL, continuity TEXT, period TEXT, state TEXT, content TEXT NOT NULL, payload TEXT NOT NULL)')
    connection.execute('CREATE TABLE IF NOT EXISTS research_attributes (record_id TEXT, attribute TEXT, PRIMARY KEY(record_id, attribute))')
    connection.execute('CREATE TABLE IF NOT EXISTS research_equipment (record_id TEXT, equipment TEXT, PRIMARY KEY(record_id, equipment))')
    return connection


def _cited_rights(entry):
    """Apply the site's row exception, without certifying an arbitrary local file.

    Policy: https://citedfeats.com/data/ (checked 2026-10-23). SCP rows use
    CC BY-SA 3.0; the general CC BY 4.0 notice is not a whole-dataset licence.
    A retained row URL establishes the claimed source, not its authenticity or
    the rights to any original work named in the row.
    """
    source_url = entry.get('discovery_url')
    claimed_source = False
    url_scp = None
    if isinstance(source_url, str):
        try:
            parsed = urlsplit(source_url)
            parts = [part.casefold() for part in parsed.path.split('/') if part]
            claimed_source = (parsed.scheme in ('http', 'https') and
                parsed.hostname in ('citedfeats.com', 'www.citedfeats.com') and
                not parsed.username and not parsed.password and bool(parts) and
                parts[0] not in ('about', 'data', 'rules'))
            if claimed_source:
                url_scp = parts[0] == 'scp'
        except ValueError:
            pass
    franchise = entry.get('franchise_slug', entry.get('franchise'))
    normalized = re.sub(r'[\s_-]+', '', franchise.casefold()) if isinstance(franchise, str) else ''
    row_scp = normalized in ('scp', 'scpfoundation')
    conflict = claimed_source and row_scp != url_scp
    license_id = ('CC-BY-SA-3.0' if row_scp else 'CC-BY-4.0') if claimed_source and not conflict else None
    reasons = []
    if not claimed_source:
        reasons.append('Missing or unrecognized Cited Feats entry URL; confirm provenance before licensed redistribution')
    if conflict:
        reasons.append('SCP franchise and source URL disagree; resolve the row identity and share-alike exception before redistribution')
    changes = 'Normalized into the battle-scaling discovery schema; the submitted source row is retained unchanged in foreign_record.'
    credit = f'Data: Cited Feats ({CITED_DATA_URL})'
    if license_id:
        credit += f', licensed {license_id} ({CITED_LICENSES[license_id]}).'
    else:
        credit += '; licence unresolved for this submitted row; no reuse permission inferred.'
    if isinstance(source_url, str) and source_url:
        credit += f' Submitted source: {source_url}.'
    credit += ' Changes: ' + changes
    return {
        'license': license_id, 'license_url': CITED_LICENSES.get(license_id),
        'license_status': 'upstream_policy_applied_to_claimed_source' if license_id else 'unresolved',
        'license_scope': "Cited Feats' own data and wording only; no rights in the cited original works are granted or verified.",
        'license_policy_source': CITED_DATA_URL,
        'license_basis': 'scp_row_exception' if license_id == 'CC-BY-SA-3.0' else 'general_data_policy' if license_id else 'provenance_or_scope_unresolved',
        'attribution': credit,
        'attribution_details': {'publisher': 'Cited Feats', 'data_url': CITED_DATA_URL,
            'submitted_entry_url': source_url, 'changes': changes,
            'source_authenticity_verified': False},
        'rights_needs': reasons,
    }


def _cited_license_summary(records):
    counts = {}
    for record in records:
        key = record.get('license') or 'unresolved'
        counts[key] = counts.get(key, 0) + 1
    return {'scope': 'this_batch_imported_cited_rows_only', 'counts': counts,
        'mixed_license': len([key for key in counts if key != 'unresolved']) > 1,
        'unresolved_records': [row['record_id'] for row in records if not row.get('license')],
        'policy_source': CITED_DATA_URL,
        'notice': 'Retain each row attribution and licence; SCP rows are CC-BY-SA-3.0, not CC-BY-4.0. Unresolved rows carry no inferred reuse permission. This does not license the original fictional works.'}


def _cited_records(path, limit):
    source = Path(path).expanduser().resolve(strict=True)
    if not source.is_file() or source.stat().st_size > MAX_IMPORT_BYTES:
        raise ValueError('Cited import must be an explicit JSON file no larger than 16 MiB')
    raw = source.read_bytes()
    data = json.loads(raw.decode('utf-8-sig'))
    if not isinstance(data, list):
        raise ValueError('Cited import must contain a list of character discovery records')
    sha = hashlib.sha256(raw).hexdigest()
    result, quarantined = [], []
    for row, entry in enumerate(data[:limit]):
        if not isinstance(entry, dict) or not entry.get('id') or not entry.get('franchise'):
            quarantined.append({'row': row, 'record': entry,
                'reason': 'Missing foreign id/franchise; retained for review, not invented as a character'})
            continue
        key = f"citedfeats:{entry['franchise']}:{entry['id']}"
        rights = _cited_rights(entry)
        result.append({'record_id': key, 'entity_id': 'external:' + key,
            'name': entry.get('name'), 'work_id': 'external:citedfeats:' + entry['franchise'],
            'continuity': entry.get('continuity'), 'period': None, 'state': None, 'equipment': [], 'attributes': [],
            'source_id': 'citedfeats:' + (entry.get('discovery_url') or key),
            'source_url': entry.get('discovery_url'), 'source_origin': 'community', 'source_access': 'indexed',
            'text_kind': 'community_summary', 'exact_text': entry.get('feat') or '',
            'locator': {'community_url': entry.get('discovery_url'), 'original_locators': [x.get('locator') for x in entry.get('citations', [])]},
            'snapshot_sha256': sha, 'snapshot_scope': 'explicit_import_file', 'original_source_sha256': None,
            'original_source_verified': False, 'citations': entry.get('citations', []), 'foreign_record': entry,
            **rights,
            'needs': ['Resolve original identity/state and verify original cited work before upgrading evidence'] + rights['rights_needs']})
    return result, len(data), quarantined


def index(request):
    records = request.get('records', [])
    if not isinstance(records, list):
        raise ValueError('records must be a list')
    available, quarantined, imported_count, import_limit = None, [], 0, None
    imported = []
    if request.get('import_cited'):
        import_limit = _positive_int(request.get('limit', 100), 'limit', MAX_RECORDS)
        imported, available, quarantined = _cited_records(request['import_cited'], import_limit)
        imported_count = len(imported)
        records = records + imported
    if not records or len(records) > MAX_RECORDS:
        raise ValueError(f'Provide 1 to {MAX_RECORDS} explicit records (no implicit external database import)')
    payloads = [_validate_record(item) for item in records]
    ids = [item['record_id'] for item in records]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate record_id in batch; preserve distinct observations with distinct IDs')
    connection = _connect(request.get('db'), create=True)
    added = 0
    try:
        with connection:
            fts = _fts_available(connection)
            for item, payload in zip(records, payloads):
                existing = connection.execute('SELECT payload FROM research_records WHERE record_id=?', (item['record_id'],)).fetchone()
                if existing:
                    if existing[0] != payload:
                        raise ValueError(f"record_id {item['record_id']} already has different content; use a new revision ID")
                    continue
                # Search text is derived; original payload and every locator remain untouched.
                content = ' '.join(str(x or '') for x in (item.get('name'), item.get('aliases'), item['exact_text'],
                    json.dumps(item['locator'], ensure_ascii=False), json.dumps(item.get('citations', []), ensure_ascii=False)))
                connection.execute('INSERT INTO research_records VALUES (?,?,?,?,?,?,?,?)',
                    tuple(item.get(k) for k in ('record_id', *SCOPE_FIELDS)) + (content, payload))
                for attribute in set(item.get('attributes', [])):
                    connection.execute('INSERT INTO research_attributes VALUES (?,?)', (item['record_id'], attribute))
                for equipment in set(item.get('equipment', [])):
                    connection.execute('INSERT INTO research_equipment VALUES (?,?)', (item['record_id'], equipment))
                if fts:
                    connection.execute('INSERT INTO research_fts VALUES (?,?)', (item['record_id'], content))
                added += 1
            # Backfill if SQLite gained FTS5 after the database was created using fallback.
            if fts:
                connection.execute('INSERT INTO research_fts SELECT record_id, content FROM research_records WHERE record_id NOT IN (SELECT record_id FROM research_fts)')
            count = connection.execute('SELECT COUNT(*) FROM research_records').fetchone()[0]
    finally:
        connection.close()
    return _base('index', added=added, supplied=len(records), total_records=count,
        import_available=available, import_limit_applied=available is not None and available > import_limit,
        imported_records=imported_count, quarantined=quarantined,
        import_license_summary=_cited_license_summary(imported) if request.get('import_cited') else None,
        backend='sqlite_fts5' if fts else 'sqlite_like_fallback',
        warnings=([] if fts else ['FTS5 unavailable; bounded parameterized LIKE search is used']) +
                 (['Malformed external rows were quarantined, not merged or promoted'] if quarantined else []) +
                 (['Some imported Cited Feats rows have unresolved provenance or licence scope; review their rights_needs before redistribution']
                  if any(not item.get('license') for item in imported) else []),
        truth_verified=False, identity_merged=False,
        provenance_policy='Stored labels describe submitted provenance; indexing neither verifies sources nor upgrades discovery clues')


def search(request):
    query = _text(request.get('query', ''), 'query', maximum=2000).strip()
    limit = _positive_int(request.get('limit', 20), 'limit', 200)
    filters = request.get('filters', {})
    if not isinstance(filters, dict):
        raise ValueError('filters must be an object')
    unknown = set(filters) - set(SCOPE_FIELDS) - {'attribute', 'equipment', 'source_origin', 'source_access', 'polarity'}
    if unknown:
        raise ValueError('Unsupported filters: ' + ', '.join(sorted(unknown)))
    clauses, values = [], []
    for key in SCOPE_FIELDS:
        if key in filters:
            _text(filters[key], key)
            clauses.append('r.' + key + '=?')
            values.append(filters[key])
    if 'attribute' in filters:
        _text(filters['attribute'], 'attribute')
        clauses.append('EXISTS (SELECT 1 FROM research_attributes a WHERE a.record_id=r.record_id AND a.attribute=?)')
        values.append(filters['attribute'])
    for equipment in _strings(filters.get('equipment', []), 'equipment'):
        clauses.append('EXISTS (SELECT 1 FROM research_equipment e WHERE e.record_id=r.record_id AND e.equipment=?)')
        values.append(equipment)
    # JSON filtering after fetch avoids a dependency on the optional SQLite JSON extension.
    extra_filters = {k: filters[k] for k in ('source_origin', 'source_access', 'polarity') if k in filters}
    for key, value in extra_filters.items():
        _text(value, key)
    connection = _connect(request.get('db'))
    warnings = []
    try:
        fts = _fts_available(connection)
        backend = 'sqlite_fts5' if fts else 'sqlite_like_fallback'
        def fetch(use_fts):
            where, params = list(clauses), list(values)
            if query:
                if use_fts:
                    where.append('r.record_id IN (SELECT record_id FROM research_fts WHERE research_fts MATCH ?)')
                    params.append('"' + query.replace('"', '""') + '"')
                else:
                    where.append("r.content LIKE ? ESCAPE '\\'")
                    params.append('%' + query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%')
            sql = 'SELECT r.payload FROM research_records r' + (' WHERE ' + ' AND '.join(where) if where else '') + ' ORDER BY r.record_id'
            found = []
            cursor = connection.execute(sql, params)
            # At most index size is visited, but only limit matching payloads are returned.
            for row in cursor:
                item = json.loads(row[0])
                if all(item.get(k) == v for k, v in extra_filters.items()):
                    found.append(item)
                    if len(found) >= limit:
                        break
            return found
        results = fetch(fts)
        if query and fts and not results:
            results = fetch(False)
            backend = 'sqlite_like_fallback'
            warnings.append('FTS phrase found no rows; literal substring fallback was tried (useful for unsegmented CJK)')
        elif not fts:
            warnings.append('FTS5 unavailable; bounded parameterized LIKE search is used')
    finally:
        connection.close()
    return _base('search', query=query, filters=filters, limit=limit, results=results,
        backend=backend, warnings=warnings, truth_verified=False,
        needs=['No matching local discovery records; this is not evidence of absence'] if not results else [],
        ranking='literal phrase/substring discovery, stable record order; no semantic relevance or truth score')


def coverage(request):
    plan_data, attempts = request.get('plan', {}), request.get('attempts', [])
    if not isinstance(plan_data, dict) or not isinstance(plan_data.get('tasks'), list) or not isinstance(attempts, list):
        raise ValueError('coverage requires a plan.tasks list and an attempts list')
    tasks = plan_data['tasks']
    if any(not isinstance(task, dict) or not task.get('task_id') for task in tasks):
        raise ValueError('Each planned task requires task_id')
    checked, warnings = set(), []
    known = {task['task_id'] for task in tasks}
    for attempt in attempts:
        if not isinstance(attempt, dict):
            raise ValueError('Every attempt must be an object')
        if attempt.get('task_id') not in known:
            warnings.append('Ignored attempt with unplanned task_id: ' + str(attempt.get('task_id')))
        elif attempt.get('status') in ('completed', 'no_results'):
            if all(attempt.get(k) for k in ('query', 'provider', 'checked_at')):
                checked.add(attempt['task_id'])
            else:
                warnings.append('Not counted: completed attempt lacks query/provider/checked_at')
    gaps = [dict(task, gap='conditional_not_activated' if task.get('status') == 'conditional' else 'not_documented_as_checked')
            for task in tasks if task['task_id'] not in checked]
    rows = []
    for attribute in plan_data.get('dimensions', DIMENSIONS):
        selected = [task for task in tasks if task.get('attribute') == attribute]
        rows.append({'attribute': attribute, 'planned_tasks': len(selected),
            'checked_tasks': sum(task['task_id'] in checked for task in selected),
            'positive_checked': any(task['task_id'] in checked and task.get('polarity') == 'positive' for task in selected),
            'counter_checked': any(task['task_id'] in checked and task.get('polarity') == 'counter' for task in selected),
            'conclusion': 'coverage_only'})
    return _base('coverage', planned_tasks=len(tasks), checked_tasks=len(checked), dimensions=rows,
        gaps=gaps, attempts=attempts, warnings=warnings, truth_verified=False, exhaustive=False,
        needs=['Review remaining tasks, blocked providers, contradictory evidence and original-source verification'],
        limitation='Counts documented attempts only; no-results is not zero ability, disproof, or complete web coverage')


def papers(request):
    query = _text(request.get('query'), 'query', maximum=1000).strip()
    if not query:
        raise ValueError('papers requires a nonempty query')
    limit = _positive_int(request.get('limit', 10), 'limit', 25)
    if not request.get('output_dir'):
        raise ValueError('papers requires output_dir for original response and provenance')
    url = 'https://www.ebi.ac.uk/europepmc/webservices/rest/search?' + urlencode({
        'query': query, 'format': 'json', 'pageSize': limit, 'resultType': 'core'})
    bundle = sources.fetch_source(url, request['output_dir'], max_bytes=2 * 1024 * 1024)
    if bundle.get('status') != 'ok':
        return _base('papers', 'needs_source', acquisition=bundle, results=[],
            needs=['Paper discovery response was blocked, partial or unreadable; do not treat it as no matching literature'],
            truth_verified=False)
    data = json.loads(Path(bundle['paths']['raw']).read_text(encoding='utf-8-sig'))
    results = []
    for item in data.get('resultList', {}).get('result', [])[:limit]:
        results.append({'paper_id': item.get('id'), 'database': item.get('source'),
            'title': item.get('title'), 'authors': item.get('authorString'), 'year': item.get('pubYear'),
            'doi': item.get('doi'), 'pmcid': item.get('pmcid'), 'abstract': item.get('abstractText'),
            'source_origin': 'paper', 'source_access': 'indexed', 'original_source_verified': False,
            'discovery_sha256': bundle.get('sha256'), 'doi_url': 'https://doi.org/' + item['doi'] if item.get('doi') else None,
            'needs': ['Read methods/results and verify units, population/material and model applicability before using parameters']})
    return _base('papers', query=query, results=results, reported_hit_count=data.get('hitCount'),
        acquisition=bundle, truth_verified=False,
        warnings=['Metadata/abstract discovery only; papers do not establish fictional feats or universal parameter applicability'])


def run(request):
    """Return JSON-compatible results; all operations are explicit and on demand."""
    op = request.get('op', 'plan') if isinstance(request, dict) else None
    try:
        if not isinstance(request, dict):
            raise ValueError('request must be an object')
        functions = {'plan': plan, 'index': index, 'search': search, 'coverage': coverage, 'papers': papers}
        if op not in functions:
            raise ValueError('op must be plan/index/search/coverage/papers')
        return functions[op](request)
    except (ValueError, TypeError, KeyError, OSError, sqlite3.Error) as error:
        return _base(op, 'error', errors=[f'{type(error).__name__}: {error}'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', required=True, help='UTF-8 JSON request path')
    args = parser.parse_args()
    result = run(json.loads(Path(args.request).read_text(encoding='utf-8-sig')))
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
