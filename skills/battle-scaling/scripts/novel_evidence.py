"""Bounded, offline book snapshots and literal reading; never authenticates a work.

run({op: inventory/index/search/read/verify, ...}) uses only the standard library.
Extracted offsets are Unicode character positions in that source's text snapshot,
not source bytes, printed pages, or another chunk's coordinate system.
"""
import hashlib
from html.parser import HTMLParser
import io
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import uuid
import xml.etree.ElementTree as ET
import zipfile

ENGINE = 'novel_evidence'
VERSION = 1
MAX_FILE = 64 * 1024 * 1024
MAX_ZIP_TOTAL = 128 * 1024 * 1024
MAX_MEMBER = 32 * 1024 * 1024
MAX_FILES = 2048
MAX_WINDOW_CHARS = 16000
DERIVED = {'notes', 'canon', 'out', 'stylefit'}
CHAPTER = re.compile(r'^\s*(?:#{1,6}\s+)?((?:第[0-9０-９零〇一二三四五六七八九十百千万两]+[章节回话卷部集][^\r\n]{0,100}|(?:终章|尾声|后记|番外|序章|楔子)[^\r\n]{0,100}))\s*$')


def _base(op, status='ok', **extra):
    return dict(schema_version=VERSION, engine=ENGINE, operation=op, status=status,
                authentication='provided_not_authenticated', original_verified=False, **extra)


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _integer(value, name, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f'{name} must be an integer from {minimum} to {maximum}')
    return value


def _path(value, exists=True):
    if not isinstance(value, str) or not value or '://' in value or value.startswith(('\\\\', '//')):
        raise ValueError('Provide an explicit local path, not a URL or network share')
    try:
        return Path(value).expanduser().resolve(strict=exists)
    except OSError as exc:
        raise ValueError('Local path does not exist or cannot be read') from exc


def _natural(path):
    return [int(x) if i % 2 else x.casefold() for i, x in enumerate(re.split(r'(\d+)', str(path)))]


def _role(path):
    parts = {x.casefold() for x in path.parts}
    return 'derived_navigation_only' if parts & DERIVED else 'original_text_candidate'


def _candidate(path):
    return {'path': str(path), 'role': _role(path), 'authentication': 'provided_not_authenticated'}


def _inventory(request):
    root = _path(request.get('source'))
    warnings = ['Local files are supplied evidence candidates; paths, labels and hashes do not authenticate an author or edition.']
    derived, candidates = [], []
    if root.is_file():
        if root.suffix.lower() not in ('.txt', '.md', '.epub', '.docx'):
            raise ValueError('Supported local inputs: TXT/MD/EPUB/DOCX or a refpack/chunks directory')
        candidates = [_candidate(root)]
    elif root.is_dir():
        if root.name.casefold() == 'chunks':
            candidates = [_candidate(p) for p in sorted(root.glob('chunk_*.txt'), key=_natural) if p.is_file()]
        else:
            raw = root / 'raw' / '_all.txt'
            if raw.is_file():
                candidates = [_candidate(raw)]
            elif (root / 'chunks').is_dir():
                candidates = [_candidate(p) for p in sorted((root/'chunks').glob('chunk_*.txt'), key=_natural) if p.is_file()]
            for folder in sorted(DERIVED):
                nav = root/folder
                if nav.is_dir():
                    for p in sorted(nav.rglob('*'), key=_natural):
                        if p.is_file():
                            derived.append({'path': str(p), 'role': 'derived_navigation_only'})
                            if len(derived) > MAX_FILES:
                                raise ValueError('Too many derived navigation files; supply an explicit book path')
            if derived:
                warnings.append('canon/notes/out/stylefit are derived navigation. Project canon, deleted chapters and continuations cannot redefine the original edition; inspect boundaries against source text.')
            if (root/'book.json').is_file():
                warnings.append('book.json configuration and external source paths are not executed or followed. Original extraction completeness and project edits require host review.')
        if not candidates:
            raise ValueError('Directory has no raw/_all.txt or chunk_*.txt; no recursive manuscript guessing')
    else:
        raise ValueError('Source must be a regular file or book directory')
    if len(candidates) > MAX_FILES:
        raise ValueError('Too many source chunks')
    if any(x['role'] == 'derived_navigation_only' for x in candidates):
        warnings.append('Explicitly selected derivative text remains derived_navigation_only, even when its title claims canon or author confirmation.')
    return _base('inventory', source=str(root), candidates=candidates,
                 derived_navigation=derived, warnings=warnings,
                 coverage={'indexed_sources': 0, 'whole_book_read': False, 'semantic_read_verified': False})


def _read_bytes(path, limit=MAX_FILE):
    if not path.is_file() or path.stat().st_size > limit:
        raise ValueError('Source exceeds size limit or is not a regular file')
    with path.open('rb') as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Source exceeds size limit')
    return data


def _decode(raw, encoding=None):
    enc = encoding or ('utf-16' if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig')
    try:
        return raw.decode(enc), enc
    except (UnicodeError, LookupError) as exc:
        raise ValueError('Text decoding failed; provide an explicit encoding instead of dropping bytes') from exc


def _xml(raw):
    if b'<!ENTITY' in raw.upper():
        raise ValueError('XML entity declarations are unsupported')
    try:
        return ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError('Malformed book XML') from exc


def _local_tag(tag):
    return tag.rsplit('}', 1)[-1]


def _member(name):
    if not isinstance(name, str) or '\\' in name or ':' in name:
        raise ValueError('Unsafe archive member')
    p = PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts:
        raise ValueError('Unsafe archive member traversal')
    return str(p)


class _HtmlText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lines, self.buf, self.hidden = [], [], 0

    def flush(self):
        s = ''.join(self.buf).strip()
        if s:
            self.lines.append(s)
        self.buf = []

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1
        elif not self.hidden and tag in ('p','div','h1','h2','h3','h4','li','br'):
            self.flush()

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden-1)
        elif not self.hidden and tag in ('p','div','h1','h2','h3','h4','li'):
            self.flush()

    def handle_data(self, data):
        if not self.hidden:
            self.buf.append(data)


def _extract(path, raw, encoding):
    ext = path.suffix.lower()
    if ext in ('.txt', '.md'):
        text, used_encoding = _decode(raw, encoding)
        return text, [], used_encoding
    try:
        z = zipfile.ZipFile(io.BytesIO(raw))
    except (OSError, zipfile.BadZipFile) as exc:
        raise ValueError('Invalid EPUB/DOCX ZIP container') from exc
    with z:
        entries = z.infolist()
        if len(entries) > 10000 or sum(x.file_size for x in entries) > MAX_ZIP_TOTAL:
            raise ValueError('Book archive exceeds entry or expanded size limit')
        names = set()
        for entry in entries:
            _member(entry.filename)
            if entry.filename in names or entry.file_size > MAX_MEMBER:
                raise ValueError('Duplicate or oversized book archive member')
            names.add(entry.filename)
        def get(name):
            name = _member(name)
            if name not in names:
                raise ValueError('Required archive member is missing: ' + name)
            return z.read(name)
        lines, locators = [], []
        if ext == '.docx':
            doc = _xml(get('word/document.xml'))
            for n, p in enumerate((x for x in doc.iter() if _local_tag(x.tag) == 'p'), 1):
                parts = []
                for node in p.iter():
                    tag = _local_tag(node.tag)
                    if tag == 't': parts.append(node.text or '')
                    elif tag == 'tab': parts.append('\t')
                    elif tag in ('br', 'cr'): parts.append('\n')
                content = ''.join(parts)
                paragraph_lines = content.split('\n')
                start = len(lines) + 1
                lines.extend(paragraph_lines)
                locators.append({'line_start':start, 'line_end':len(lines),
                                 'member':'word/document.xml','paragraph':n})
        else:
            container = _xml(get('META-INF/container.xml'))
            rootfile = next((x.attrib.get('full-path') for x in container.iter() if _local_tag(x.tag)=='rootfile'), None)
            if not rootfile:
                raise ValueError('EPUB container has no rootfile')
            rootfile = _member(rootfile)
            opf = _xml(get(rootfile)); parent = PurePosixPath(rootfile).parent
            items = {x.attrib.get('id'):x.attrib.get('href') for x in opf.iter() if _local_tag(x.tag)=='item'}
            refs = [x.attrib.get('idref') for x in opf.iter() if _local_tag(x.tag)=='itemref']
            if not refs:
                raise ValueError('EPUB spine is empty')
            for n, ref in enumerate(refs, 1):
                href = items.get(ref)
                if not href:
                    raise ValueError('EPUB spine references unknown member')
                member = _member(str(parent / href.split('#',1)[0]))
                parsed = _HtmlText()
                parsed.feed(get(member).decode('utf-8-sig', errors='strict'))
                parsed.flush()
                for paragraph, line in enumerate(parsed.lines, 1):
                    lines.append(line)
                    locators.append({'line_start':len(lines),'line_end':len(lines),
                                     'member':member,'spine_index':n,'paragraph':paragraph})
        return '\n'.join(lines) + ('\n' if lines else ''), locators, 'zip_xml_utf8_extraction'


def _lines(text):
    values = text.splitlines(keepends=True)
    starts, pos = [], 0
    for line in values:
        starts.append(pos)
        pos += len(line)
    return values, starts


def _chapters(text):
    lines, starts = _lines(text)
    marks = []
    for i, line in enumerate(lines):
        match = CHAPTER.fullmatch(line.rstrip('\r\n'))
        if match:
            marks.append((i+1, starts[i], match.group(1)))
    if not marks or marks[0][0] > 1:
        marks.insert(0,(1,0,'(prelude)'))
    result = []
    for i,(line,char,title) in enumerate(marks):
        next_line,next_char = marks[i+1][:2] if i+1<len(marks) else (len(lines)+1,len(text))
        result.append({'chapter_index':i+1,'title':title,'line_start':line,
                       'line_end':max(line-1,next_line-1),'char_start':char,'char_end':next_char})
    return result


def _index(request):
    inv = _inventory(request)
    for key in ('work_id','edition_id'):
        if not isinstance(request.get(key),str) or not request[key].strip():
            raise ValueError(key + ' is required; editions must remain separate')
    destination = _path(request.get('output_dir'), exists=False)
    original_root = _path(request['source'])
    protected = [original_root] if original_root.is_dir() else []
    for ancestor in original_root.parents:
        if (ancestor/'book.json').is_file() or ((ancestor/'raw').is_dir() and (ancestor/'chunks').is_dir()):
            protected.append(ancestor)
            break
    if any(destination == root or root in destination.parents for root in protected):
        raise ValueError('Output directory must be outside the original book/refpack project')
    prepared, total, extracted_total = [], 0, 0
    for i, item in enumerate(inv['candidates'],1):
        path = _path(item['path'])
        raw = _read_bytes(path)
        total += len(raw)
        if total > MAX_ZIP_TOTAL:
            raise ValueError('Combined source snapshot size exceeds limit')
        text, locators, used_encoding = _extract(path, raw, request.get('encoding'))
        encoded = text.encode('utf-8')
        extracted_total += len(encoded)
        if extracted_total > MAX_ZIP_TOTAL:
            raise ValueError('Extracted text exceeds limit')
        sid = f'source_{i:04d}'
        entry = {'id':sid,'origin_path':str(path),'role':item['role'],
                 'authentication':'provided_not_authenticated','original_verified':False,
                 'source_sha256':_hash(raw),'text_sha256':_hash(encoded),
                 'raw_snapshot':f'sources/{sid}.original','text_snapshot':f'sources/{sid}.txt',
                 'encoding':used_encoding,'line_count':len(_lines(text)[0]),'char_count':len(text),
                 'chapters':_chapters(text),'unit_locators':locators,
                 'offset_space':'extracted_text_unicode_characters'}
        prepared.append((entry, raw, encoded))
    new_name = 'novel-' + uuid.uuid4().hex
    bundle = destination / new_name
    bundle.mkdir(parents=True, exist_ok=False)
    try:
        (bundle/'sources').mkdir()
        for entry,raw,text in prepared:
            (bundle/entry['raw_snapshot']).write_bytes(raw)
            (bundle/entry['text_snapshot']).write_bytes(text)
        manifest = {'schema_version':VERSION,'engine':ENGINE,'work_id':request['work_id'],
                    'edition_id':request['edition_id'],'sources':[x[0] for x in prepared],
                    'derived_navigation':inv['derived_navigation'],'warnings':inv['warnings'],
                    'authentication':'provided_not_authenticated','offset_space':'extracted_text_unicode_characters'}
        data = json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False).encode('utf-8')
        (bundle/'manifest.json').write_bytes(data)
        (bundle/'manifest.sha256').write_text(_hash(data)+'\n',encoding='ascii')
    except BaseException:
        # Never recursively remove a computed Windows path without checking the
        # final absolute target against the newly created task directory.
        final_target = bundle.resolve()
        if final_target.parent == destination.resolve() and final_target.name == new_name and re.fullmatch(r'novel-[0-9a-f]{32}', new_name):
            shutil.rmtree(final_target)
        raise
    return _base('index','indexed',bundle=str(bundle),manifest=str(bundle/'manifest.json'),
                 manifest_sha256=_hash(data),sources=manifest['sources'],
                 derived_navigation=inv['derived_navigation'],warnings=inv['warnings'],
                 coverage={'indexed_sources':len(prepared),'displayed_windows':[],
                           'whole_book_read':False,'semantic_read_verified':False})


def _inside(bundle, name):
    if not isinstance(name,str) or not name:
        raise ValueError('Invalid snapshot path')
    child = (bundle/name).resolve(strict=True)
    if bundle not in child.parents or not child.is_file():
        raise ValueError('Snapshot path escapes bundle')
    return child


def _load(request):
    path = _path(request.get('bundle'))
    bundle = path.parent if path.is_file() and path.name=='manifest.json' else path
    if not bundle.is_dir():
        raise ValueError('bundle must be a snapshot directory or its manifest.json')
    try:
        raw = _read_bytes(bundle/'manifest.json',MAX_MEMBER)
        expected = (bundle/'manifest.sha256').read_text(encoding='ascii').strip()
        if not re.fullmatch('[0-9a-f]{64}',expected) or _hash(raw)!=expected:
            return bundle,None,['Manifest digest mismatch']
        manifest = json.loads(raw.decode('utf-8'))
        if manifest.get('engine')!=ENGINE or manifest.get('schema_version')!=VERSION:
            return bundle,None,['Unsupported manifest schema']
        entries = manifest.get('sources')
        if not isinstance(entries,list) or not 1 <= len(entries) <= MAX_FILES:
            return bundle,None,['Invalid source manifest']
        seen=set()
        for source in entries:
            sid=source.get('id')
            if not sid or sid in seen:
                return bundle,None,['Invalid or duplicate source ID']
            seen.add(sid)
            for key,hashkey in (('raw_snapshot','source_sha256'),('text_snapshot','text_sha256')):
                file=_inside(bundle,source[key])
                if _hash(_read_bytes(file,MAX_ZIP_TOTAL))!=source[hashkey]:
                    return bundle,None,['Snapshot digest mismatch: '+sid+' '+key]
        return bundle,manifest,[]
    except (OSError,ValueError,KeyError,TypeError,AttributeError) as exc:
        return bundle,None,['Invalid or missing snapshot: '+str(exc)]


def _verify(request):
    bundle, manifest, errors = _load(request)
    if errors:
        return _base('verify','tampered',bundle=str(bundle),errors=errors,snapshot_integrity=False,
                     limitation='Hashes detect accidental alteration; they are not signed proof of authenticity.')
    originals=[]
    if request.get('check_originals') is True:
        for source in manifest['sources']:
            try:
                path=_path(source['origin_path'])
                state='unchanged' if _hash(_read_bytes(path))==source['source_sha256'] else 'changed'
            except (OSError,ValueError):state='unavailable'
            originals.append({'source_id':source['id'],'origin_path':source['origin_path'],'status':state})
    return _base('verify',bundle=str(bundle),snapshot_integrity=True,originals=originals,
                 manifest_sha256=_hash((bundle/'manifest.json').read_bytes()),
                 limitation='Only saved byte/text integrity is checked, not official identity, extraction completeness or semantic truth.')


def _window(bundle, source, first, last, focus=None, text=None):
    if text is None:
        text=(bundle/source['text_snapshot']).read_bytes().decode('utf-8')
    lines,starts=_lines(text)
    if not lines:
        return None
    first,last=max(1,first),min(len(lines),last)
    start=starts[first-1]; end=starts[last-1]+len(lines[last-1])
    truncated=end-start>MAX_WINDOW_CHARS
    if truncated:
        if focus is not None and focus>=start+MAX_WINDOW_CHARS:
            start=max(start,focus-MAX_WINDOW_CHARS//2)
        end=min(end,start+MAX_WINDOW_CHARS)
        first=next((i+1 for i,p in enumerate(starts) if p>start),len(lines)+1)-1
        first=max(1,first)
        last=next((i+1 for i,p in enumerate(starts) if p>=end),len(lines)+1)-1
    chapter=next((x for x in reversed(source['chapters']) if x['line_start']<=first),None)
    units=[x for x in source.get('unit_locators',[]) if x['line_start']<=last and x['line_end']>=first]
    return {'source_id':source['id'],'role':source['role'],
            'authentication':'provided_not_authenticated','original_verified':False,
            'source_sha256':source['source_sha256'],'text_sha256':source['text_sha256'],
            'exact_text':text[start:end],'line_start':first,'line_end':last,
            'char_start':start,'char_end':end,'offset_space':'extracted_text_unicode_characters',
            'chapter':chapter,'unit_locators':units,'truncated':truncated,
            'locator':{'snapshot':source['text_snapshot'],'source_id':source['id'],
                       'line_start':first,'line_end':last,'char_start':start,'char_end':end}}


def _search(request):
    bundle, manifest, errors=_load(request)
    if errors:
        return _base('search','tampered',results=[],errors=errors,snapshot_integrity=False)
    terms=request.get('keywords')
    if terms is None:terms=[request.get('query')]
    if not isinstance(terms,list) or not 1<=len(terms)<=100 or any(not isinstance(x,str) or not x.strip() or len(x)>2000 for x in terms):
        raise ValueError('Provide a nonempty query or keywords list of literal terms')
    limit=_integer(request.get('limit',20),'limit',1,200)
    context=_integer(request.get('context_lines',10),'context_lines',0,50)
    order=request.get('order','ending_backward')
    if order not in ('ending_backward','forward'):
        raise ValueError('order must be ending_backward or forward')
    matches=[]; scanned=0
    sources=manifest['sources']
    indexed_lines=sum(x['line_count'] for x in sources)
    for source in (reversed(sources) if order=='ending_backward' else sources):
        text=(bundle/source['text_snapshot']).read_bytes().decode('utf-8')
        lines,starts=_lines(text)
        sequence=range(len(lines)-1,-1,-1) if order=='ending_backward' else range(len(lines))
        for i in sequence:
            scanned+=1
            hits=[(lines[i].find(term),term) for term in terms if term in lines[i]]
            if not hits:continue
            pos,term=min(hits)
            if len(matches)>=limit:
                return _base('search',bundle=str(bundle),results=matches,order=order,truncated=True,
                             snapshot_integrity=True,coverage={'indexed_sources':len(sources),'scanned_lines':scanned,
                              'indexed_lines':indexed_lines,
                              'displayed_windows':_displayed(matches),'whole_book_read':False,'semantic_read_verified':False},
                             limitation='Literal matches and displayed windows do not prove the latest feat, complete semantic coverage or official provenance.')
            window=_window(bundle,source,i+1-context,i+1+context,starts[i]+pos,text=text)
            window['chapter']=next((x for x in reversed(source['chapters']) if x['line_start']<=i+1),None)
            window['match']={'line':i+1,'term':term,'char_start':starts[i]+pos,'char_end':starts[i]+pos+len(term)}
            matches.append(window)
    return _base('search',bundle=str(bundle),results=matches,order=order,truncated=False,
                 snapshot_integrity=True,coverage={'indexed_sources':len(sources),'scanned_lines':scanned,
                  'indexed_lines':indexed_lines,
                  'displayed_windows':_displayed(matches),'whole_book_read':False,'semantic_read_verified':False},
                 limitation='Search does not infer feats or certify semantic reading; no hit is not evidence of absence.')


def _displayed(windows):
    return [{key:x[key] for key in ('source_id','line_start','line_end','char_start','char_end','truncated')} for x in windows]


def _read(request):
    bundle,manifest,errors=_load(request)
    if errors:
        return _base('read','tampered',window=None,errors=errors,snapshot_integrity=False)
    source=next((x for x in manifest['sources'] if x['id']==request.get('source_id')),None)
    if source is None:raise ValueError('Unknown source_id')
    first=_integer(request.get('line_start'),'line_start',1,max(1,source['line_count']))
    last=_integer(request.get('line_end',first),'line_end',first,max(1,source['line_count']))
    if last-first+1>500:raise ValueError('Read at most 500 explicit lines per call')
    context=_integer(request.get('context_lines',0),'context_lines',0,50)
    window=_window(bundle,source,first-context,last+context)
    return _base('read',bundle=str(bundle),window=window,snapshot_integrity=True,
                 coverage={'indexed_sources':len(manifest['sources']),
                  'displayed_windows':_displayed([window]) if window else [],
                  'whole_book_read':False,'semantic_read_verified':False},
                 limitation='Only the returned window was displayed; host semantic reading is a separate claim.')


def run(request):
    if not isinstance(request,dict):raise ValueError('Request must be an object')
    op=request.get('op')
    functions={'inventory':_inventory,'index':_index,'search':_search,'read':_read,'verify':_verify}
    if op not in functions:raise ValueError('op must be inventory/index/search/read/verify')
    return functions[op](request)
