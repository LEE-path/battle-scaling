"""Auditable type/token arithmetic and annotated dewatering; no semantic claims."""
from __future__ import annotations
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unicodedata

ROOT=Path(__file__).resolve().parents[1]


def token_metrics(tokens, casefold=False):
    if not isinstance(tokens,list) or not tokens or any(not isinstance(t,str) or not t.strip() for t in tokens):
        raise ValueError('tokens must be a nonempty explicit list of word tokens')
    normalized=[unicodedata.normalize('NFC',t.casefold() if casefold else t) for t in tokens]
    frequencies=Counter(normalized)
    a,b=len(frequencies),len(normalized)
    return {'A_types':a,'B_tokens':b,'E_2A_minus_B':2*a-b,
            'casefold':casefold,'normalization':'NFC',
            'tokens_sha256':hashlib.sha256(json.dumps(normalized,ensure_ascii=False,separators=(',',':')).encode()).hexdigest(),
            'frequencies':dict(frequencies.most_common()),
            'scope':'Counts depend on the declared segmentation; not a mathematical/combat strength theorem.'}


def segment_local(text):
    if not isinstance(text,str) or not text.strip() or len(text)>5_000_000:
        raise ValueError('text must contain 1..5000000 characters')
    try:
        import jieba
    except ImportError:
        configured=os.environ.get('BATTLE_SEGMENTER_PYTHON')
        config=ROOT/'runtime/local-tools.json'
        if not configured and config.exists():
            configured=json.loads(config.read_text(encoding='utf-8')).get('nlp_python')
        if not configured or not Path(configured).is_file():
            return {'status':'needs_configuration','needs':['Provide explicit word tokens or configure an isolated Python with jieba via BATTLE_SEGMENTER_PYTHON.'],
                    'warning':'Chinese characters are not silently substituted for word tokens.'}
        result=subprocess.run([configured,'-X','utf8',str(Path(__file__).resolve()),'--segment-stdin'],
                              input=text,capture_output=True,text=True,encoding='utf-8',timeout=90)
        if result.returncode:
            return {'status':'error','error':'Configured local segmenter failed; inspect the declared environment.'}
        return json.loads(result.stdout)
    dictionary=Path(jieba.__file__).parent/'dict.txt'
    tokenizer=jieba.Tokenizer(dictionary=str(dictionary))
    tokenizer.tmp_dir=os.environ.get('TEMP')
    raw=list(tokenizer.cut(text,cut_all=False,HMM=False))
    tokens=[t for t in raw if any(unicodedata.category(c)[0] in ('L','N') for c in t)]
    return {'status':'ok','tokens':tokens,'tokenizer':{'project':'jieba','version':jieba.__version__,
            'mode':'accurate','HMM':False,'dictionary_sha256':hashlib.sha256(dictionary.read_bytes()).hexdigest(),
            'filter':'exclude tokens with no Unicode letters or numbers',
            'source_text_sha256':hashlib.sha256(text.encode('utf-8')).hexdigest()},
            'warning':'The handbook does not fix a Chinese dictionary/tokenizer; this is a reproducible implementation choice, not certified AntConc equivalence.'}


def manual_dewater(source_text,segments):
    if not isinstance(source_text,str) or not isinstance(segments,list) or not segments:
        raise ValueError('manual review needs the full source_text and ordered annotated segments')
    cursor,kept,seen,notes=0,[],set(),[]
    for number,s in enumerate(segments,1):
        if not isinstance(s,dict) or s.get('start')!=cursor or isinstance(s.get('end'),bool) or not isinstance(s.get('end'),int) or not cursor<s['end']<=len(source_text):
            raise ValueError('manual segments must cover the entire source exactly, in order, without gaps or overlap')
        if s.get('decision') not in ('keep','drop') or not s.get('reason'):
            raise ValueError('every manual segment needs keep/drop and a substantive reason')
        original=source_text[cursor:s['end']]
        if 'original' in s and s['original']!=original:
            raise ValueError('manual segment original does not match source span')
        canonical=s.get('canonical',original)
        if not isinstance(canonical,str):
            raise ValueError('canonical text must be a string')
        key=s.get('dedupe_key') or unicodedata.normalize('NFC',canonical).strip()
        included=s['decision']=='keep' and key not in seen
        if included:
            if not canonical.strip():
                raise ValueError('kept text cannot be empty')
            kept.append(canonical);seen.add(key)
        notes.append({**s,'original':original,'counted':included,'duplicate':s['decision']=='keep' and not included})
        cursor=s['end']
    if cursor!=len(source_text):
        raise ValueError('manual review omitted the source tail')
    effective='\n'.join(kept)
    count=sum(unicodedata.category(c)[0] in ('L','N') for c in effective)
    return {'effective_text':effective,'effective_characters':count,'count_policy':'Unicode letters/numbers only; exclude whitespace, punctuation and symbol-only positions',
            'source_text_sha256':hashlib.sha256(source_text.encode()).hexdigest(),
            'effective_text_sha256':hashlib.sha256(effective.encode()).hexdigest(),
            'annotations':notes,'validation_scope':'span coverage and arithmetic; semantic dewatering is the host reviewer\'s explicit judgment'}


def li_band(value,thresholds):
    hits=[t for t in thresholds if value>=t['minimum']]
    return max(hits,key=lambda t:t['minimum'])['label'] if hits else None


def assess_li(request,rule):
    facts=request.get('scope_facts',{})
    supported_math=facts.get('transcends_existing_mathematics') is True
    supported_philosophy=facts.get('transcends_philosophy') is True
    qualified=bool(facts.get('evidence_ids')) and (supported_math or supported_philosophy)
    tokens=request.get('tokens')
    segmentation=None
    if tokens is None and request.get('text'):
        segmentation=segment_local(request['text'])
        if segmentation['status']=='ok':tokens=segmentation['tokens']
    machine=None
    if tokens is not None:
        metrics=token_metrics(tokens,request.get('casefold',False))
        a,e=metrics['A_types'],metrics['E_2A_minus_B']
        boundary=a in rule['ambiguous_A_boundaries']
        e_boundary=(a<rule['small_A_boundary'] and e==0) or (a>rule['large_A_boundary'] and e==rule['large_A_floor_score'])
        floor=rule['large_A_floor'] if a>rule['large_A_boundary'] else None
        label=li_band(e,rule['score_thresholds'])
        if e<0 and a<rule['small_A_boundary']:label='无量级（该机评口径）'
        elif e<0 and rule['small_A_boundary']<a<rule['large_A_boundary']:
            label=rule['mid_negative_label']
        if floor and (label is None or e<rule['large_A_floor_score']):label=floor
        if boundary:label=None
        machine={'metrics':metrics,'label':label,'floor':floor,'boundary_ambiguity':boundary,
                 'E_boundary_ambiguity':e_boundary,
                 'status':'conditional_segmentation_estimate','segmentation':segmentation.get('tokenizer') if segmentation else request.get('tokenizer_provenance'),
                 'preliminary_dewatering':request.get('preliminary_dewatering','not_certified'),
                 'warnings':['The handbook leaves exact A=4000/A=10000, E=0/E=4000 endpoint cases and the middle negative-score adjustment underspecified; a stated A>10000 floor can remain valid.'] if boundary or e_boundary or (e<0 and a>rule['small_A_boundary']) else []}
    manual=None
    if request.get('manual_segments') is not None:
        manual=manual_dewater(request.get('source_text'),request['manual_segments'])
        manual['label']=li_band(manual['effective_characters'],rule['manual_thresholds'])
        manual['status']='conditional_on_semantic_annotations_and_count_policy'
    selected=manual or machine
    basal=rule['philosophy_label'] if supported_philosophy else rule['mathematics_label'] if supported_math else None
    label=selected.get('label') if selected else basal
    if not label:label=basal
    if not qualified:
        label=None
    return {'status':'conditional' if qualified and label else 'needs_scope_evidence' if not qualified else 'underdetermined',
            'standard':rule['id'],'label':label,'basal_scope_label':basal,'manual':manual,'machine':machine,
            'priority':'manual_over_machine' if manual else 'machine_only' if machine else 'scope_only',
            'scope_facts':facts,'qualified_scope_evidence_supplied':qualified,'sources':rule['sources'],
            'segmentation_gap':segmentation if segmentation and segmentation.get('status')!='ok' else None,
            'warning':'This is the handbook\'s declared nonconstructive text-evaluation convention; it is not cardinal arithmetic, physical energy or an automatic character AP/durability transfer.'}


if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8');sys.stderr.reconfigure(encoding='utf-8')
    if sys.argv[1:]!=['--segment-stdin']:
        raise SystemExit('Only --segment-stdin is exposed; use handbook high requests for assessment.')
    print(json.dumps(segment_local(sys.stdin.read()),ensure_ascii=False))
