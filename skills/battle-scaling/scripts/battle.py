#!/usr/bin/env python3
"""Portable tools used by the battle-scaling host Agent. No API key required."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from evidence import MODES, analyze_case, validate_case
from rating_modes import LEGACY_MODES, applies, selected_modes
from rule_profiles import resolve as resolve_profile, snapshot_content
from pk_modes import PRESENTATIONS,select_presentation,format_estimate

ROOT = Path(__file__).resolve().parents[1]
SKILL_VERSION = '1.17.1'


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write_json(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def output_summary(data, command, output):
    """Bound console output without changing the complete saved result."""
    summary = {'command': command, 'output': str(Path(output).resolve()),
               'stdout': 'summary', 'full_result_saved': True}
    if not isinstance(data, dict):
        summary.update(status='completed', item_count=len(data) if isinstance(data, list) else 1)
        return summary
    summary['status'] = data.get('status', 'ok' if data.get('valid') is True else
                                 'invalid' if data.get('valid') is False else 'completed')
    for key in ('valid', 'operation', 'stage', 'case_id', 'skill_version', 'report', 'manifest',
                'narrative_generated', 'semantic_rating_verified', 'host_semantic_review_required'):
        value = data.get(key)
        if key in data and (value is None or isinstance(value, (str, bool, int, float))):
            summary[key] = value if not isinstance(value, str) else value[:500]
    # Read diagnostics only; never traverse potentially huge source/author/artifact packs.
    for key, label in (('errors', 'error'), ('needs', 'need'), ('warnings', 'warning'),
                       ('revision_tasks', 'revision_task')):
        items = data.get(key, [])
        if not isinstance(items, list):
            items = [items] if items else []
        if key == 'errors' and data.get('error'):
            items = [data['error'], *items]
        summary[label + '_count'] = len(items)
        if items:
            summary[label + '_preview'] = [str(item)[:240] for item in items[:3]]
    for key in ('rating_preflight', 'rating_execution'):
        gate = data.get(key)
        if isinstance(gate, dict) and 'status' in gate:
            needs = gate.get('needs', [])
            summary[key] = {'status': gate['status'],
                            'need_count': len(needs) if isinstance(needs, list) else int(bool(needs))}
    return summary


def emit_result(data, args):
    output = getattr(args, 'output', None)
    console = (output_summary(data, args.command, output)
               if output and not args.full_output else data)
    print(json.dumps(console, ensure_ascii=False, indent=2, allow_nan=False))


def doctor(standard=None):
    local_tools = ROOT/'runtime/local-tools.json'
    configured = load_json(local_tools) if local_tools.exists() else {}
    optional_local = {k: {'path': configured.get(k), 'exists': bool(configured.get(k) and Path(configured[k]).exists())}
                      for k in ('formula_python', 'formula_model_dir', 'nlp_python')}
    return {'schema_version': 1, 'python': sys.version.split()[0], 'executable': sys.executable,
            'platform': platform.platform(), 'skill_root': str(ROOT),
            'optional_packages': {p: importlib.util.find_spec(p) is not None for p in
               ('PIL', 'numpy', 'sympy', 'pint', 'scipy', 'fitz', 'pypdf', 'manga_ocr')},
            'executables': {p: shutil.which(p) for p in ('ffmpeg', 'ffprobe', 'tesseract')},
            'host_capabilities': {'search': 'host must supply and verify', 'vision': 'host must supply or configure an external VLM',
                                  'manga_reasoning': 'image interpretation is not provided by pixel/OCR utilities'},
            'external_vision_configured': bool(os.environ.get('BATTLE_VISION_BASE_URL') and os.environ.get('BATTLE_VISION_MODEL')),
            'rule_profile': resolve_profile(standard=standard), 'local_optional_tools': optional_local,
            'rating_standards': {'default':'wangba','available':['wangba','vsb'],'default_rating_mode':'integrated','independent_evidence_modes':list(MODES),'legacy_modes':list(LEGACY_MODES),'independent_presentations':list(PRESENTATIONS)},
            'handbook_corpus_installed': (ROOT/'data/wangba-handbook-2026-07-30/pages.jsonl').is_file(),
            'skill_version':SKILL_VERSION,
            'pk_presentations':{'default':'overview','on_explicit_request':'process','default_rating_mode':'integrated','independent_evidence_modes':list(MODES),'legacy_modes':list(LEGACY_MODES),
                                'independent_rating_required':True,'rating_workflow':'references/character-rating-workflow.md'},
            'writing_assistance':{'purpose':'writing','command':'writing','separate_from_evidence_modes_and_pk':True,
                                  'author_may_fix':['skills','events','outcome'],
                                  'independent_rating_required':True,
                                  'rating_pipeline':{'command':'rating-pipeline','operations':['plan','assemble','assemble-and-prepare'],
                                                     'actual_artifacts_required':True,'local_analysis_replayed':True,
                                                     'verification_reuse':'process-local; current bytes, rules and implementation must match',
                                                     'semantic_rating_verified':False},
                                  'mandatory_media_steps':[],
                                  'interaction_reasoning':'recover evidence chains and match attributes before asking about an irreducible outcome-changing conflict',
                                  'canon_fidelity':{'flag':'canon_fidelity','host_default':'existing canon characters unless explicitly adapted',
                                                    'reference':'references/writing-canon-and-systems.md',
                                                    'structural_checker':(ROOT/'scripts/writing_fidelity.py').is_file(),
                                                    'semantic_verification':False},
                                  'implementation':'host authors prose; local tool checks declared inputs and draft constraint coverage'},
            'core_tools': {'evidence': True, 'physics': (ROOT/'scripts/physics.py').exists(),
                           'high_tier': (ROOT/'scripts/high_tier.py').exists(), 'sources': (ROOT/'scripts/sources.py').exists(),
                           'media': (ROOT/'scripts/media.py').exists(),
                           **{name:(ROOT/'scripts'/f'{name}.py').exists() for name in ('research','derivation_audit','combat_trace','feat_audit','hax_policy','hax_gate','site_registry','novel_evidence','tieba','rating_preflight','rating_pipeline')}},
            'site_experience':{'default_db':os.environ.get('BATTLE_SITE_DB') or str(ROOT/'data/site-experience/registry.sqlite3'),
                               'source_cli_auto_records':'transport receipt; readable content requires host confirmation',
                               'reuse_policy':'lookup experience, then recheck current target page'},
            'external_project_models_required':False,
            'dependency_policy': 'Use built-in tools first. Install optional packages or models only for a task that needs them.'}


def compute_case(case, mode='integrated', profile=None):
    case = json.loads(json.dumps(case, allow_nan=False))
    from standards import family,validate_case_standard
    profile=profile or resolve_profile(case.get('ruleset_profile'),case.get('standard'))
    validate_case_standard(case,profile)
    computed = []
    for c in case.get('computations', []):
        if 'request' not in c:
            computed.append(c)
            continue
        if c.get('type') == 'high':
            if family(profile)=='vsb':
                from vsb_high import run as analyze
            else:
                from high_tier import analyze
            requested = selected_modes(mode)
            for current in requested:
                if not applies(c, current):
                    continue
                item = {**c, 'id': str(c.get('id', 'high')) + ':' + current,
                        'mode': current, 'request': {**c['request'], 'mode': current}}
                if not item['request'].get('ruleset') and profile and profile.get('high_default'):
                    kind=item['request'].get('kind')
                    defaults=profile.get('high_by_kind',{})
                    item['request']['ruleset']=defaults.get(kind,profile['high_default'])
                    item['ruleset_selection']='profile_default_for_kind'
                elif item['request'].get('ruleset'):
                    item['ruleset_selection']='explicit_computation_request'
                if family(profile)=='vsb':
                    item['request']['sources']=case.get('sources',[])
                result = analyze(item['request'])
                if result.get('status') in ('invalid', 'error'):
                    raise ValueError(f'computation {item["id"]}: {result.get("errors", result.get("error"))}')
                computed.append({**item, 'output': result})
                if c.get('attach'):
                    if family(profile)=='vsb' and (result.get('status') not in ('supported_by_packet','conditional') or not result.get('classification')):
                        computed[-1]['attachment_review']={'status':'withheld','reason':'VSB structural criteria were not established; no tier anchor attached.'}
                        continue
                    attach = attach_dependencies(c)
                    selector = attach.pop('result_path', None)
                    if not selector:
                        raise ValueError('attach requires explicit dot-separated result_path')
                    if family(profile)=='vsb':
                        if selector!='classification':
                            raise ValueError('VSB high attachment must select classification; raw criteria are not tier quantities')
                        from standards import vsb_tier_quantity
                        value=vsb_tier_quantity(result['classification'],result['ruleset_id'])
                        if result['status']=='conditional':
                            attach['assumptions']=list(dict.fromkeys(attach.get('assumptions',[])+[
                                row.get('assumption','Locally assumed structural criterion: '+row.get('criterion',row.get('parameter','unknown')))
                                for row in result.get('criteria_review',[])+result.get('parameter_review',[]) if row.get('outcome')=='assumed']))
                    else:
                        value = result
                        for part in selector.split('.'):
                            value = value[int(part)] if isinstance(value, list) else value[part]
                    attach['id'] = str(attach.get('id', c.get('id', 'high-anchor'))) + ':' + current
                    attach['modes'] = [current]
                    if isinstance(value, dict):
                        attach['quantity'] = value
                    elif isinstance(value, (int, float)) and attach.get('unit'):
                        attach['quantity'] = {'value': value, 'unit': attach.pop('unit')}
                    else:
                        raise ValueError('selected result must be a quantity object or scalar with explicit unit')
                    case.setdefault('anchors', []).append(attach)
            continue
        if c.get('type') == 'physics':
            if family(profile)=='vsb':
                from vsb_physics import calculate
                result = calculate(c['request'],sources=case.get('sources',[]))
            else:
                from physics import calculate
                result = calculate(c['request'])
        else:
            raise ValueError(f'unknown computation type: {c.get("type")}')
        if result.get('status') in ('invalid', 'error'):
            raise ValueError(f'computation {c.get("id")}: {result.get("errors", result.get("error"))}')
        computed.append({**c, 'output': result})
        if c.get('attach'):
            if family(profile)=='vsb' and (result.get('status')!='ok' or result.get('eligible_for_attachment') is not True):
                computed[-1]['attachment_review']={'status':'withheld','reason':'VSB physics policy did not admit this calculation; mathematical references cannot anchor a rating.'}
                continue
            attach = attach_dependencies(c)
            selector = attach.pop('result_path', None)
            if not selector:
                raise ValueError('attach requires explicit dot-separated result_path')
            if family(profile)=='vsb' and selector!='result' and not selector.startswith('result.'):
                raise ValueError('VSB physics attachment must select the admitted result; raw audit paths cannot anchor a rating')
            value = result
            for part in selector.split('.'):
                value = value[int(part)] if isinstance(value, list) else value[part]
            if isinstance(value, dict):
                attach['quantity'] = value
            elif isinstance(value, (int, float)) and attach.get('unit'):
                attach['quantity'] = {'value': value, 'unit': attach.pop('unit')}
            else:
                raise ValueError('selected result must be a quantity object or scalar with explicit unit')
            case.setdefault('anchors', []).append(attach)
    case['computations'] = computed
    if case.get('derivation_requests'):
        from derivation_audit import run
        case['derivation_audits']=[{'id':item['id'],'output':run(item['request'])} for item in case['derivation_requests']]
    validate_case_standard(case,profile)
    return case


def attach_dependencies(computation):
    """A generated anchor cannot discard the ability premise of its calculation."""
    from hax_gate import ids
    attach=dict(computation['attach'])
    dependencies=ids(computation.get('hax_requirements',[]))+ids(attach.get('hax_requirements',[]))
    if dependencies:attach['hax_requirements']=list(dict.fromkeys(dependencies))
    if computation.get('is_hax'):attach['is_hax']=True
    for key in ('ability_owner','affected_target'):
        if key in computation:attach.setdefault(key,computation[key])
    return attach


def render_process(process):
    lines=['### 具体战斗过程','','以下是所列前提下的推演分支；不当作原作已发生事实，也不以分支数量计算胜率。','',
           '过程状态：'+str(process.get('status'))+'。','']
    def cell(value):
        if isinstance(value,(dict,list)):value=json.dumps(value,ensure_ascii=False,separators=(',',':'))
        return str(value).replace('|','\\|').replace('\n',' ')
    if process.get('trace'):
        lines += ['| 步骤 | 行动 | 发动／命中 | 防御／反制 | 伤势／状态 | 后续 | 依据／假设 |',
                  '|---|---|---|---|---|---|---|']
        for step in process['trace']:
            for action in step.get('actions',[]):
                row=[step.get('id',step.get('step')),f"{action['actor']} → {action['target']}：{action['intent']}",
                     {'activation':action.get('activation'),'hit':action.get('hit')},
                     {'defense':action.get('defense'),'outcome':action.get('outcome')},
                     {'同组共享变化':action.get('state_changes',[])},action.get('follow_up'),
                     {'evidence_ids':action.get('evidence_ids'),'assumptions':action.get('assumptions')}]
                lines.append('| '+' | '.join(cell(value) for value in row)+' |')
        lines += ['','完整逐步记录：','']
    for step in process.get('trace',[]):
        lines += ['```json',json.dumps(step,ensure_ascii=False,indent=2),'```','']
    if process.get('terminal') is not None:
        lines += ['终局／恢复窗口：','','```json',json.dumps(process['terminal'],ensure_ascii=False,indent=2),'```','']
    if process.get('final_state') is not None:
        lines += ['结束状态：','','```json',json.dumps(process['final_state'],ensure_ascii=False,indent=2),'```','']
    if process.get('needs'):
        lines += ['待补条件：','','```json',json.dumps(process['needs'],ensure_ascii=False,indent=2),'```','']
    if process.get('narrative'):
        narrative=process['narrative']
        lines += ['战况叙述（推演）：','',narrative if isinstance(narrative,str) else json.dumps(narrative,ensure_ascii=False,indent=2),'']
    return lines


def render_report(result):
    names = {'integrated': '综合评定', 'normal': '历史常态复算', 'highest': '历史最高复算', 'lowball': '历史扒下限复算'}
    chars = {c['id']: c for c in result['characters']}
    lines = [f'# {result["case_id"]}：论战评定', '',
             '生成时间：' + datetime.now(timezone.utc).isoformat(), '',
             '本报告依据所列资料及前提；数字验证、来源引用验证与原作语义审核是不同步骤。', '']
    if result.get('legacy_mode'):
        lines += ['**历史三态复算：不代表已按当前综合主档规则重新审查。**', '']
    if result.get('rating_completion'):
        gate = result['rating_completion']
        lines += ['综合评级完成性：**' + gate['status'] + '**。局部计算与高低表现仅为依据，不自动成为角色主档。', '']
        for row in result.get('integrated_ratings', []):
            name = chars[row['character_id']]['name']
            lines += ['**' + name + '量级：' + row['main_tier']['label'] + '**', '',
                      '| 属性 | 综合判定 | 来源与叠法 |', '|---|---|---|']
            for field, node in row['dimensions'].items():
                detail = node.get('reasoning', '') + '；' + ', '.join(node.get('evidence_ids', []))
                lines.append('| ' + field + ' | ' + str(node.get('label', '')) + ' | ' + detail.replace('|', '\|').replace('\n', ' ') + ' |')
            lines.append('')
        if gate.get('needs'):
            lines += ['尚未完成综合主档验收：', '', *['- ' + need for need in gate['needs']], '']
    if result.get('ruleset_profile'):
        profile=result['ruleset_profile']
        lines += ['评级体系：**'+profile.get('standard','wangba')+'**。',
                  '规则配置：**'+profile['id']+'**；选择：'+profile.get('selection_source','case')+'。',
                  '有限规则与原件指纹保存在 rules-snapshot.json；各高层计算若明确指定其他具名标准，其实际规则另列，不合并同名档位。','']
    if result.get('fixture_kind') == 'synthetic':
        lines += ['**本文件使用合成或用户给定规则；结果不能作为其他作品的原作战绩引用。**', '']
    if result.get('matchup'):
        assessment = result['matchup'].get('assessment')
        if assessment and assessment.get('winner'):
            lines += ['当前口径机制判断：**' + str(assessment['winner']) + '**，性质 ' + assessment['status'] + '。依据与条件见下。', '']
        else:
            lines += ['获胜路径审核：**' + str(result['matchup']['verdict']) + '**。以下列出条件和反例，无校准胜率。', '']
    for c in result['characters']:
        lines += [f'- {c["name"]}：版本 {c["version"]}；状态 {c["state"]}；角色记录 {c["id"]}。']
    lines.append('')
    for mode, report in result['modes'].items():
        lines += [f'## {names[mode]}', '']
        if report.get('feat_reviews'):
            lines += ['### 单次表现审查','','| 事件 | 用途 | 审查结果 | 依据与条件 |','|---|---|---|---|']
            for rid,review in report['feat_reviews'].items():
                for use,admission in review.get('admissions',{}).items():
                    details={'reasons':admission.get('reasons',[]),'assumptions':admission.get('assumptions',[]),
                             'source_ids':admission.get('source_ids',[])}
                    lines.append('| '+ ' | '.join(str(x).replace('|','\\|').replace('\n',' ') for x in
                        (rid,use,admission.get('status'),json.dumps(details,ensure_ascii=False)))+' |')
            lines += ['','审查完整账本、原始条件和补证任务见 feat-reviews.json；此表不表示工具独立核实了作者身份或原作语义。','']
        if report.get('hax_reviews'):
            vsb=result.get('standard',result.get('ruleset_profile',{}).get('standard'))=='vsb'
            if vsb:
                lines += ['### VSB 特能机制审查','','依机制、作用对象、发动条件、抗性和无上限谬误审查；每项须绑定实际表现或可支持的机制证据。','',
                          '| 检查 | 结果 | 依据与缺口 |','|---|---|---|']
            else:
                lines += ['### 特殊能力上限审查','','按用户确认口径：默认取该能力表现内影响上限，最高不得超过原世界观最强角色已达量级。','',
                          '| 检查 | 结果 | 自身影响上限内 | 角色天花板内 | 依据与缺口 |','|---|---|---|---|---|']
            for rid,review in report['hax_reviews'].items():
                details={key:review.get(key,[]) for key in ('source_ids','reasons','assumptions','research_tasks')}
                values=(rid,review.get('status'),json.dumps(details,ensure_ascii=False)) if vsb else (rid,review.get('status'),review.get('within_observed_limit'),review.get('within_world_ceiling'),json.dumps(details,ensure_ascii=False))
                lines.append('| '+' | '.join(str(value).replace('|','\\|').replace('\n',' ') for value in values)+' |')
            lines += ['','原始条件、比较过程和覆盖范围见 hax-checks.json；通过上限审查不等于必定命中或必胜。','']
        matchup = result.get('matchups', {}).get(mode)
        if matchup:
            lines += ['PK 呈现：'+('宏观推演' if matchup.get('presentation')=='overview' else '具体过程')+'。','']
            lines += ['证据路径审核：' + str(matchup['verdict']) + '。', '']
            if matchup.get('assessment'):
                lines += [format_estimate(matchup['assessment'].get('win_estimate')),'',
                          '宿主机制判断（仅检验引用元数据与数值一致性，原作语义须由宿主审核）：', '', '```json',
                          json.dumps(matchup['assessment'], ensure_ascii=False, indent=2), '```', '']
            if matchup.get('presentation')=='process':
                lines += render_process(matchup['process'])
        if report.get('high_results'):
            summaries = []
            for computation in report['high_results']:
                data = computation.get('output', {})
                summaries.append({'id': computation.get('id'), **{k: data[k] for k in
                    ('status', 'mode', 'ruleset', 'ruleset_id', 'classification', 'criteria_review', 'parameter_review', 'required_criteria', 'validation_scope', 'result', 'mappings', 'assumptions', 'structured_gaps', 'warnings', 'limits') if k in data}})
            lines += ['高层构造与具名规则映射：', '', '```json',
                      json.dumps(summaries, ensure_ascii=False, indent=2), '```',
                      '原始构造、参数、来源和逐步运算见末尾“全部计算与中间步骤”及 analysis.json。', '']
        if report.get('hax_computations'):
            lines += ['本模式通过特能门槛后保留的计算（含原始输入、中间值及条件）：','','```json',
                      json.dumps(report['hax_computations'],ensure_ascii=False,indent=2),'```','']
        if report.get('qualitative_claims'):
            lines += ['定性结论：', '', '```json',
                      json.dumps(report['qualitative_claims'], ensure_ascii=False, indent=2), '```', '']
        if not report['conclusions']:
            lines += ['此评定没有有限数值属性锚点；高层及定性结论见本节，覆盖缺口见末尾。', '']
        for c in report['conclusions']:
            q = c['quantity']
            label = q.get('label', f'{q["best"]:.8g} {q["unit"]}')
            name = chars[c['subject']]['name']
            lines += [f'### {name} · {c["attribute"]}', '',
                      f'- 结果：{label}；区间 {q["min"]:.8g}～{q["max"]:.8g} {q["unit"]}；约束 {c["bound"]}。',
                      '- 依据：' + ', '.join(c['evidence_ids']) + '。',
                      '- 推导链：' + ' → '.join(c['trace']) + '。']
            if c.get('context'):
                lines.append('- 当时条件：' + c['context'])
            if c.get('claim_scope')=='event':
                lines.append('- 范围：仅约束本次事件；不能自动作为角色全力或该状态最大能力。')
            if c.get('review_trace'):
                lines.append('- 表现审查：'+json.dumps(c['review_trace'],ensure_ascii=False)+'。')
            if c.get('hax_trace'):
                lines.append('- 特能审查：'+json.dumps(c['hax_trace'],ensure_ascii=False)+'。')
            if c.get('mapping'):
                m = c['mapping']
                if m.get('best_reference'):
                    lines += [f'- 映射：{m["best_reference"]}；规则 {m["ruleset_id"]}。',
                              '- 映射性质：' + m['qualifier'] + '。']
                    if m.get('table_ceiling_exceeded'):
                        lines.append('- 数值超出本表最高参考点；更高有限层级需另查，不能把表顶当作角色上限。')
                if m.get('handbook_assessment'):
                    lines += ['- 新册逐条评定（包含能量／尺度条件、未定义项及页码）：','',
                              '```json',json.dumps(m['handbook_assessment'],ensure_ascii=False,indent=2),'```']
            lines += ['- 前提：' + ('；'.join(c['assumptions']) if c['assumptions'] else '未增加跨证据假设；仍以输入参数及原作审核为条件。'), '']
        if report['excluded']:
            lines += ['未采用的证据或边：', '', '```json', json.dumps(report['excluded'], ensure_ascii=False, indent=2), '```', '']
        if report['search_truncated']:
            lines += ['**传播达到资源上限，不能声称已穷尽全部推导路径。**', '']
    if result.get('qualitative_claims'):
        lines += ['## 定性结论与角色能力', '', '```json',
                  json.dumps(result['qualitative_claims'], ensure_ascii=False, indent=2), '```', '']
    if result.get('computations'):
        lines += ['## 全部计算与中间步骤', '', '```json',
                  json.dumps(result['computations'], ensure_ascii=False, indent=2), '```', '']
    if result.get('derivation_audits'):
        lines += ['## 推导审查与待补证据','','```json',json.dumps(result['derivation_audits'],ensure_ascii=False,indent=2),'```','']
    if result.get('matchup'):
        lines += ['## 获胜路径、条件与反例', '', '```json',
                  json.dumps(result['matchup'], ensure_ascii=False, indent=2), '```', '']
    lines += ['## 资料出处', '']
    for s in result['sources']:
        uri = s.get('url', s.get('path', ''))
        title = f'[{s["title"]}]({uri})' if uri else s['title']
        lines.append(f'- {s["id"]}：{title}；位置：{s["locator"]}；性质：{s["origin"]}；读取：{s["access"]}。')
    lines += ['', '## 覆盖范围与限制', '', '```json', json.dumps(
        {'coverage': result.get('coverage'), 'limitations': result.get('limitations'),
         'hax_review_coverage':{mode:report.get('hax_review_coverage') for mode,report in result['modes'].items()},
         'matchup_hax_review_coverage':{mode:report.get('hax_review_coverage') for mode,report in result.get('matchups',{}).items()},
         'validation_scope': result['validation_scope']}, ensure_ascii=False, indent=2), '```', '']
    return '\n'.join(lines)


def export_case(result, output, input_path=None, input_bytes=None):
    out = Path(output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if input_path:
        original=Path(input_path).resolve()
        if original==(out/'CASE.json').resolve():
            raise ValueError('report CASE.json must not overwrite the original input')
        (out/'CASE.json').write_bytes(input_bytes if input_bytes is not None else original.read_bytes())
    write_json(out/'analysis.json', result)
    write_json(out/'sources.json', result['sources'])
    write_json(out/'derivations.json', result['modes'])
    reviews={mode:report['feat_reviews'] for mode,report in result['modes'].items() if report.get('feat_reviews')}
    if reviews:write_json(out/'feat-reviews.json',reviews)
    hax_reviews={mode:{'checks':report.get('hax_reviews',{}),'rating_coverage':report.get('hax_review_coverage',{}),
                       'matchup_coverage':result.get('matchups',{}).get(mode,{}).get('hax_review_coverage',{}),
                       'process_admissions':result.get('matchups',{}).get(mode,{}).get('process',{}).get('hax_admissions',[]),
                       'process_coverage':result.get('matchups',{}).get(mode,{}).get('process',{}).get('hax_review_coverage',{})}
                 for mode,report in result['modes'].items()}
    write_json(out/'hax-checks.json',hax_reviews)
    input_digest=hashlib.sha256(input_bytes).hexdigest() if input_bytes is not None else None
    condition_packet={'characters':result['characters'],'matchups':
                      {mode:{k:v for k,v in matchup.items() if k not in ('assessment','process','verdict')}
                       for mode,matchup in result.get('matchups',{}).items()},
                      'process_input_sha256':result.get('process_input_sha256',{}),
                      'feat_review_inputs_sha256':{mode:{rid:review.get('effective_request_sha256') for rid,review in items.items()}
                                                  for mode,items in reviews.items()},
                      'hax_check_inputs_sha256':{mode:{rid:review.get('effective_request_sha256') for rid,review in data['checks'].items()}
                                                 for mode,data in hax_reviews.items()}}
    ledger={'schema_version':1,'skill_version':SKILL_VERSION,'generated_at_utc':datetime.now(timezone.utc).isoformat(),
            'case_id':result['case_id'],'input_sha256':input_digest,'evidence_modes':list(result['modes']),
            'presentation':result.get('matchup',{}).get('presentation'),
            'conditions_sha256':hashlib.sha256(json.dumps(condition_packet,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
            'declared_host_metadata':result.get('run_metadata',{}),
            'feat_review_ids':{mode:list(items) for mode,items in reviews.items()},
            'standard':result.get('standard','wangba'),
            'hax_policy_id':result.get('standard_audit',{}).get('hax_policy_id','user_confirmed_hax_ceiling_20261020'),
            'hax_check_ids':{mode:list(data['checks']) for mode,data in hax_reviews.items()},
            'probability_method':'host reasoned estimate; not branch-count frequency or empirical calibration'}
    write_json(out/'run-ledger.json',ledger)
    if result.get('rule_snapshot'):
        write_json(out/'rules-snapshot.json',result['rule_snapshot'])
    (out/'report.md').write_text(render_report(result), encoding='utf-8')
    manifest = {'case_id': result['case_id'], 'files': {}}
    for name in ('analysis.json', 'sources.json', 'derivations.json', 'report.md','run-ledger.json','hax-checks.json'):
        p = out/name
        manifest['files'][name] = {'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
    if (out/'rules-snapshot.json').exists():
        p=out/'rules-snapshot.json'
        manifest['files'][p.name]={'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    if input_path:
        p=out/'CASE.json'
        manifest['files'][p.name]={'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    if reviews:
        p=out/'feat-reviews.json'
        manifest['files'][p.name]={'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    manifest['ruleset_profile']=result.get('ruleset_profile')
    write_json(out/'manifest.json', manifest)
    return {'case_id': result['case_id'], 'report': str(out/'report.md'), 'manifest': str(out/'manifest.json')}


def select_profile(request,args):
    """An explicit CLI selector overrides case defaults, never foreign evidence."""
    cli_profile=getattr(args,'ruleset_profile',None)
    cli_standard=getattr(args,'standard',None)
    if cli_profile:
        profile=resolve_profile(cli_profile,cli_standard)
        profile['selection_source']='explicit_cli_profile'
    elif cli_standard:
        profile=resolve_profile(standard=cli_standard)
        profile['selection_source']='explicit_cli_standard'
    else:
        profile=resolve_profile(request.get('ruleset_profile'),request.get('standard'))
        if request.get('ruleset_profile'):profile['selection_source']='case_locked_profile'
        elif request.get('standard'):profile['selection_source']='case_standard'
    return profile


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    for command in ('doctor','rules'):
        p=subs.add_parser(command)
        p.add_argument('--standard',choices=('wangba','vsb'))
    for command in ('physics', 'high', 'finite', 'vsb', 'validate', 'vision', 'handbook', 'formula','research','derivation','process','feat','hax','sites','novel','tieba','writing','rating-pipeline'):
        p = subs.add_parser(command)
        p.add_argument('--input', required=True)
        p.add_argument('--output')
        if command in ('physics','high','finite','hax','process'):
            p.add_argument('--standard',choices=('wangba','vsb'))
            p.add_argument('--ruleset-profile')
    p = subs.add_parser('analyze')
    p.add_argument('--input', required=True)
    p.add_argument('--mode', choices=MODES+('all',), default='integrated', help='integrated main rating; normal/highest/lowball/all are explicit historical replay')
    p.add_argument('--output', required=True)
    p.add_argument('--ruleset-profile', help='Named installed rule profile; default comes from the case or installed profile')
    p.add_argument('--standard',choices=('wangba','vsb'),help='Rating standard, independent of evidence mode and PK presentation; installed default wangba')
    p.add_argument('--pk',choices=PRESENTATIONS,help='PK presentation, independent of evidence mode; default overview unless case explicitly selects process')
    p = subs.add_parser('sources')
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument('--url')
    src.add_argument('--file')
    p.add_argument('--output', required=True)
    p = subs.add_parser('media', help='Delegate JSON requests to media.py; use python media.py --help for options')
    p.add_argument('--input', required=True)
    p.add_argument('--output')
    for child in subs.choices.values():
        child.add_argument('--full-output', action='store_true',
                           help='Print the complete JSON result even when --output saves it; default is a short receipt')
    args = parser.parse_args(argv)
    try:
        if getattr(args, 'input', None) and getattr(args, 'output', None):
            source = Path(args.input).resolve()
            output = Path(args.output).resolve()
            if args.command == 'analyze':
                if source in [output/name for name in ('analysis.json', 'sources.json', 'derivations.json', 'report.md', 'manifest.json','rules-snapshot.json','CASE.json','run-ledger.json','feat-reviews.json','hax-checks.json')]:
                    raise ValueError('report output would overwrite the input case; choose another output directory')
            elif args.command in ('physics', 'high', 'finite', 'vsb', 'validate', 'media', 'vision','handbook','formula','research','derivation','process','feat','hax','sites','novel','tieba','writing','rating-pipeline') and source == output:
                raise ValueError('output must not overwrite the input request')
        if args.command == 'doctor':
            data = doctor(args.standard)
        elif args.command == 'rules':
            if args.standard:
                data=snapshot_content(resolve_profile(standard=args.standard))
            else:
                data = [load_json(p) for p in sorted((ROOT/'rulesets').glob('*.json'))]
        elif args.command == 'validate':
            errors = validate_case(load_json(args.input))
            data = {'valid': not errors, 'errors': errors}
            if errors:
                if args.output:
                    write_json(args.output, data)
                emit_result(data, args)
                return 2
        elif args.command == 'physics':
            packet=load_json(args.input)
            profile=select_profile(packet,args)
            if profile['standard']=='vsb':
                from vsb_physics import calculate
                request=packet.get('request',{k:v for k,v in packet.items() if k!='sources'})
                data=calculate(request,sources=packet.get('sources',[]))
            else:
                from physics import calculate
                data=calculate(packet.get('request',packet))
            data['ruleset_profile']=profile
        elif args.command == 'high':
            request=load_json(args.input)
            profile=select_profile(request,args)
            if profile['standard']=='vsb':
                from vsb_high import run as analyze
                if request.get('ruleset') and not str(request['ruleset']).startswith('vsb'):
                    raise ValueError('VSB high-tier review cannot use another standard ruleset')
            else:
                from high_tier import analyze
                if str(request.get('ruleset','')).startswith('vsb'):
                    raise ValueError('Select --standard vsb for a VSB high-tier request')
            if not request.get('ruleset') and profile.get('high_default'):
                request['ruleset']=profile.get('high_by_kind',{}).get(request.get('kind'),profile['high_default'])
            data = analyze(request)
            data['ruleset_profile']=profile
        elif args.command == 'finite':
            request=load_json(args.input)
            profile=select_profile(request,args)
            if profile['standard']=='vsb':
                from vsb_rules import run
                data=run({**request,'operation':'energy'})
            else:
                from evidence import classify_energy
                from rule_profiles import finite_path
                rules=load_json(finite_path(profile))
                if rules.get('engine')=='handbook_finite':
                    from handbook_finite import classify
                    data=classify(request,ruleset=rules)
                else:
                    data=classify_energy(request['quantity'],finite_path(profile),request.get('context'))
            data['ruleset_profile']=profile
        elif args.command == 'vsb':
            from vsb_rules import run
            data=run(load_json(args.input))
        elif args.command == 'writing':
            from writing_battle import run
            data=run(load_json(args.input))
            data['skill_version']=SKILL_VERSION
        elif args.command == 'rating-pipeline':
            from rating_pipeline import run
            data=run(load_json(args.input))
            data['skill_version']=SKILL_VERSION
        elif args.command == 'media':
            from media import run
            data = run(load_json(args.input))
        elif args.command == 'vision':
            from vision_adapter import run
            data = run(load_json(args.input))
        elif args.command == 'handbook':
            from handbook import run
            data = run(load_json(args.input))
        elif args.command == 'formula':
            from formula_adapter import run,validate_output,AdapterError
            request=load_json(args.input)
            if args.output:
                try:validate_output(request,args.output)
                except AdapterError as exc:raise ValueError(str(exc)) from exc
            data = run(request)
        elif args.command in ('research','derivation','process','feat','hax','sites','novel','tieba'):
            if args.command=='research':
                from research import run
            elif args.command=='derivation':
                from derivation_audit import run
            elif args.command=='feat':
                from feat_audit import run
            elif args.command=='hax':
                request=load_json(args.input)
                profile=select_profile(request,args)
                if profile['standard']=='vsb':
                    from vsb_hax_policy import run
                else:
                    from hax_policy import run
            elif args.command=='sites':
                from site_registry import run
            elif args.command=='novel':
                from novel_evidence import run
            elif args.command=='tieba':
                from tieba import run
            else:
                from combat_trace import run
            request=load_json(args.input)
            if args.command in ('hax','process'):
                profile=select_profile(request,args)
                request={**request,'standard':profile['standard'],'ruleset_profile':profile['id']}
            data=run(request)
            if args.command in ('hax','process'):data['ruleset_profile']=profile
        elif args.command == 'sources':
            from sources import fetch_and_record
            data = fetch_and_record(args.url or args.file, args.output)
        else:
            raw_bytes=Path(args.input).read_bytes()
            raw_case=json.loads(raw_bytes.decode('utf-8-sig'))
            if args.pk:
                if not raw_case.get('matchup'):raise ValueError('--pk requires a matchup case')
                raw_case['matchup']['presentation']=select_presentation(raw_case['matchup'],args.pk)
            profile=select_profile(raw_case,args)
            case = compute_case(raw_case, args.mode,profile)
            result=analyze_case(case, args.mode, profile=profile)
            result['rule_snapshot']=snapshot_content(profile,case.get('computations',[]))
            data = export_case(result, args.output,args.input,raw_bytes)
        if getattr(args, 'output', None) and args.command in ('physics', 'high', 'finite', 'vsb', 'validate', 'media', 'vision','handbook','formula','research','derivation','process','feat','hax','sites','novel','tieba','writing','rating-pipeline'):
            write_json(args.output, data)
        emit_result(data, args)
        if args.command == 'sources':
            return 0 if data.get('status') == 'ok' else 2
        return 2 if isinstance(data, dict) and data.get('status') in ('invalid', 'error', 'blocked', 'tampered', 'needs_extractor', 'needs_configuration', 'source_gap', 'missing_source', 'hash_mismatch', 'not_found', 'unsupported_quantity') else 0
    except (ValueError, KeyError, TypeError, OSError, ImportError) as exc:
        print(json.dumps({'status': 'error', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    raise SystemExit(main())
