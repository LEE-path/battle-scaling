"""Install the full distribution into an isolated environment, or check it.

No action is performed without the explicit install/run subcommand. Account
login, paid providers, system packages and large models are never installed.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MODULES = {'media': ['PIL', 'requests', 'qrcode', 'yt_dlp', 'gallery_dl', 'bilibili_api'],
           'research': ['pypdf', 'sympy', 'pint', 'aiotieba']}
OPTIONAL_MODULES = {'ocr': ['pymupdf', 'numpy', 'rapidocr_onnxruntime'],
                    'formula': ['PIL', 'numpy', 'onnxruntime', 'rapid_latex_ocr']}


def python_path(root=ROOT):
    return root/'.venv'/('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def optional_python(name, root=ROOT):
    if name not in OPTIONAL_MODULES:
        raise ValueError('Unknown optional environment.')
    return root/('.venv-'+name)/('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def tool_python(tool, root=ROOT):
    optional = {'ocr_pdf': 'ocr', 'formula_adapter': 'formula'}.get(tool)
    if optional and optional_python(optional, root).is_file():
        return optional_python(optional, root)
    return python_path(root) if python_path(root).is_file() else Path(sys.executable)


def install_optional(name, skill_dir=None, model_dir=None, root=ROOT):
    """Explicit optional OCR install; upstream packages may include model assets."""
    if not (3,11) <= sys.version_info[:2] < (3,13):
        raise RuntimeError('These compatibility OCR packages need Python 3.11 or 3.12. Run this optional command with that interpreter.')
    interpreter = optional_python(name, root)
    if model_dir is not None:
        if name != 'formula':
            raise ValueError('--model-dir is only used by formula recognition.')
        from pathlib import Path as LocalPath
        folder = LocalPath(model_dir).expanduser().resolve()
        if not all((folder/f).is_file() for f in ('image_resizer.onnx','encoder.onnx','decoder.onnx','tokenizer.json')):
            raise ValueError('Provide all four existing formula model files; the installer does not download them.')
    if not interpreter.is_file():
        subprocess.run([sys.executable,'-m','venv',str(interpreter.parents[1])],check=True)
    subprocess.run([str(interpreter),'-m','pip','install','-r',str(root/'tools/requirements'/('optional-'+name+'.txt'))],check=True)
    if skill_dir and name == 'formula':
        config = Path(skill_dir).expanduser()/'runtime/local-tools.json'
        settings = json.loads(config.read_text(encoding='utf-8-sig')) if config.exists() else {}
        settings['formula_python'] = str(interpreter)
        if model_dir is not None: settings['formula_model_dir'] = str(folder)
        _write_json(config,settings)
    return {'environment': name, 'python': str(interpreter),
            'models': 'existing local files only' if model_dir else 'not configured',
            'note': 'This explicit optional install can fetch upstream OCR model assets as part of its packages. Generative model repositories are not downloaded.'}


def npm_command():
    node = shutil.which('node')
    npm = shutil.which('npm')
    if not node or not npm:
        raise RuntimeError('Node.js 22.18+ and npm are required. Install them, then rerun setup.')
    if os.name == 'nt':
        for base in (Path(npm).parent, Path(node).parent):
            cli = base/'node_modules/npm/bin/npm-cli.js'
            if cli.is_file():
                return [node, str(cli)]
        raise RuntimeError('Cannot locate npm-cli.js; run npm ci in tools/battle-video-studio.')
    return [npm]


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def verify_static(root=ROOT):
    """Installation checks shipped files; user runtime files are not uploads.

    The release verifier remains stricter and inventories every upload
    candidate. Do not use this installer check to approve a public archive.
    """
    from publication_guard import linked, safe_relative, scan_payload
    errors=[];payload={}
    try:
        path=root/'docs/distribution-manifest.json'
        if linked(path,root):raise ValueError()
        manifest=json.loads(path.read_text(encoding='utf-8-sig'))['files']
        if not isinstance(manifest,dict):raise ValueError()
        payload['docs/distribution-manifest.json']=path.read_bytes()
        for rel,expected in manifest.items():
            path=root/rel
            if not safe_relative(rel) or linked(path,root) or not path.resolve().is_relative_to(root):
                errors.append({'path':rel,'error':'unsafe_static_path'});continue
            data=path.read_bytes();payload[rel]=data
            if len(data)!=expected['bytes'] or hashlib.sha256(data).hexdigest()!=expected['sha256']:
                errors.append({'path':rel,'error':'static_hash_or_size_mismatch'})
        skill=json.loads(payload['skills/battle-scaling/package-manifest.json'])
        for rel,expected in skill['files'].items():
            if manifest.get('skills/battle-scaling/'+rel)!=expected:
                errors.append({'path':rel,'error':'skill_manifest_mismatch'})
        errors.extend(scan_payload(payload))
    except (OSError,ValueError,KeyError,TypeError):
        errors.append({'path':'.','error':'invalid_static_distribution'})
    return {'valid':not errors,'errors':errors}


def install_skill(source, destination, *, upgrade=False):
    from publication_guard import linked, safe_relative
    source = Path(source).resolve()
    destination = Path(destination).expanduser().absolute()
    if destination.is_symlink() or (destination.exists() and getattr(destination.lstat(), 'st_file_attributes', 0) & 0x400):
        raise ValueError('The skill destination must not be a directory link.')
    destination = destination.resolve()
    if source == destination or source.is_relative_to(destination) or destination.is_relative_to(source):
        raise ValueError('Choose a skill destination separate from the distribution source.')
    files = json.loads((source/'package-manifest.json').read_text(encoding='utf-8-sig'))['files']
    static = sorted(set(files)|{'package-manifest.json'})
    for rel in static:
        path = destination/rel
        if not safe_relative(rel) or not path.resolve().is_relative_to(destination) or linked(path,destination):
            raise ValueError('The destination contains a linked or unsafe static path.')
    if destination.exists() and any(destination.iterdir()) and not upgrade:
        raise ValueError('Skill destination exists. Use --upgrade to back up replaced static files and preserve runtime data.')
    backup = destination/'runtime/install-backups'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    changed = 0
    for rel in static:
        src = source/rel; dst = destination/rel
        if dst.is_file() and dst.read_bytes() == src.read_bytes():
            continue
        if dst.exists():
            old = backup/rel; old.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dst, old)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst); changed += 1
    return {'skill_dir': str(destination), 'changed_files': changed,
            'backup': str(backup) if backup.exists() else None}


def bind_runtime(skill, root=ROOT, *, research=False):
    # Preserve unrelated settings and existing credentials; this file stores
    # tool locations only. It is ignored by Git and excluded from distribution.
    folder = skill/'runtime'; folder.mkdir(parents=True, exist_ok=True)
    video = folder/'video-studio.local.json'
    settings = json.loads(video.read_text(encoding='utf-8-sig')) if video.exists() else {}
    settings['project_root'] = str(root/'tools/battle-video-studio')
    _write_json(video, settings)
    tools = folder/'media-tools.local.json'
    settings = json.loads(tools.read_text(encoding='utf-8-sig')) if tools.exists() else {}
    settings.update({'python': str(python_path(root)), 'node': shutil.which('node'),
                     'ffmpeg': shutil.which('ffmpeg'), 'ffprobe': shutil.which('ffprobe')})
    _write_json(tools, settings)
    if research:
        local = folder/'local-tools.json'
        settings = json.loads(local.read_text(encoding='utf-8-sig')) if local.exists() else {}
        settings['tieba_python'] = str(python_path(root))
        _write_json(local, settings)


def check(root=ROOT, skill_dir=None):
    interpreter = python_path(root)
    selected = interpreter if interpreter.is_file() else Path(sys.executable)
    probe = 'import importlib.util,json; print(json.dumps({m:importlib.util.find_spec(m) is not None for m in '+repr(sorted({m for group in MODULES.values() for m in group}))+'}))'
    result = subprocess.run([str(selected), '-c', probe], capture_output=True, text=True, timeout=20)
    packages = json.loads(result.stdout) if result.returncode == 0 else {}
    executables = {name: shutil.which(name) for name in ('node', 'npm', 'ffmpeg', 'ffprobe')}
    node_ok = False
    if executables['node']:
        r = subprocess.run([executables['node'], '--version'], capture_output=True, text=True, timeout=5)
        version = tuple(int(n) for n in r.stdout.strip().lstrip('v').split('.')[:3]) if r.returncode == 0 else ()
        node_ok = version >= (22,18,0)
    browser_paths = [shutil.which(n) for n in ('google-chrome', 'chromium', 'chromium-browser', 'msedge', 'chrome')]
    if os.name == 'nt':
        for envname in ('PROGRAMFILES','PROGRAMFILES(X86)','LOCALAPPDATA'):
            if os.environ.get(envname):
                browser_paths += [str(Path(os.environ[envname])/p) for p in ('Microsoft/Edge/Application/msedge.exe','Google/Chrome/Application/chrome.exe')]
    elif sys.platform == 'darwin':
        browser_paths += ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome']
    browser = next((p for p in browser_paths if p and Path(p).is_file()), None)
    video = root/'tools/battle-video-studio'
    result = {'python': str(selected), 'isolated_environment': interpreter.is_file(),
              'packages': packages, 'executables': executables, 'node_supported': node_ok,
              'browser': browser, 'video_dependencies': (video/'node_modules/remotion').is_dir(),
              'templates': len(list((video/'templates').glob('V*.json'))),
              'skill_installed': bool(skill_dir and (Path(skill_dir).expanduser()/'SKILL.md').is_file()),
              'user_setup': ['Provide permitted character assets, a matching audio edit and any surrender sticker.',
                             'Connect image/video/search tools in your host Agent, or configure an optional backend.',
                             'Bilibili HD requires your own QR login and the quality entitlement of your account.']}
    result['optional_environments'] = {name: optional_python(name, root).is_file() for name in OPTIONAL_MODULES}
    result['shipped_tools'] = {name: (root/'skills/battle-scaling/scripts'/(name+'.py')).is_file()
                              for name in ('battle','novel_refpack','tieba','media_acquire','bili_media','poster','one_image','video_studio','vision_adapter','ocr_pdf','formula_adapter')}
    result['video_frame_review'] = (video/'scripts/review-video.mjs').is_file()
    result['host_requirements'] = ['Reasoning, research/search, source reading and visual judgment are supplied by your Agent.',
                                   'Image/video generation needs your own working host tool or API/MCP/CLI/local backend.']
    result['media_ready'] = (all(packages.get(m) for m in MODULES['media']) and node_ok
        and bool(executables['ffmpeg'] and executables['ffprobe'] and browser) and result['video_dependencies'])
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('check'); p.add_argument('--skill-dir', type=Path)
    sub.add_parser('verify-static',help='Check shipped installation files only; not a release/upload audit.')
    p = sub.add_parser('install')
    p.add_argument('--profile', choices=['core','media','research','full'], default='full')
    p.add_argument('--skill-dir', type=Path, default=Path.home()/'.codex/skills/battle-scaling')
    p.add_argument('--upgrade', action='store_true')
    p.add_argument('--skip-npm', action='store_true')
    p = sub.add_parser('run')
    p.add_argument('tool', help='Skill script name, e.g. battle, bili_media, one_image or video_studio')
    p.add_argument('arguments', nargs=argparse.REMAINDER)
    p = sub.add_parser('optional', help='Explicitly install OCR/formula packages in a separate environment; no standalone model download.')
    p.add_argument('name', choices=sorted(OPTIONAL_MODULES))
    p.add_argument('--skill-dir', type=Path)
    p.add_argument('--model-dir', type=Path)
    args = parser.parse_args(argv)
    if args.action=='verify-static':
        result=verify_static();print(json.dumps(result,ensure_ascii=False,indent=2));return 0 if result['valid'] else 1
    if args.action == 'check':
        print(json.dumps(check(skill_dir=args.skill_dir), ensure_ascii=False, indent=2)); return 0
    if args.action == 'run':
        if not args.tool.replace('_','').isalnum(): parser.error('Tool must be a script name, not a path.')
        script = ROOT/'skills/battle-scaling/scripts'/(args.tool+'.py')
        if not script.is_file(): parser.error('Unknown Skill script.')
        python = tool_python(args.tool)
        return subprocess.run([str(python),str(script),*args.arguments], cwd=ROOT).returncode
    if args.action == 'optional':
        verified = verify_static()
        if not verified['valid']:
            print(json.dumps(verified, ensure_ascii=False, indent=2)); return 1
        print(json.dumps(install_optional(args.name,args.skill_dir,args.model_dir),ensure_ascii=False,indent=2));return 0
    if sys.version_info < (3,11): parser.error('Python 3.11+ is required.')
    verified = verify_static()
    # A fresh Python may lack Pillow. Only this explicit inspection dependency
    # may be deferred until the isolated environment exists; all other findings
    # stop immediately. The complete scan runs before copying any Skill files.
    if any(e['error']!='image_scan_requires_Pillow' for e in verified['errors']):
        print(json.dumps(verified, ensure_ascii=False, indent=2)); return 1
    target=args.skill_dir.expanduser()
    if target.exists() and any(target.iterdir()) and not args.upgrade:
        parser.error('Skill destination exists; choose another directory or use --upgrade.')
    selected = [args.profile] if args.profile in MODULES else list(MODULES) if args.profile == 'full' else []
    if not python_path().is_file():
        subprocess.run([sys.executable,'-m','venv',str(ROOT/'.venv')], check=True)
    if 'media' not in selected:
        subprocess.run([str(python_path()),'-m','pip','install','Pillow>=13,<14','-c',str(ROOT/'tools/requirements/constraints-tested.txt')],check=True)
    for profile in selected:
        subprocess.run([str(python_path()),'-m','pip','install','-r',str(ROOT/'tools/requirements'/(profile+'.txt')),'-c',str(ROOT/'tools/requirements/constraints-tested.txt')], check=True)
    validation=subprocess.run([str(python_path()),str(ROOT/'tools/setup.py'),'verify-static'],capture_output=True,text=True,encoding='utf-8',check=True)
    if not json.loads(validation.stdout)['valid']:raise RuntimeError('Distribution verification failed.')
    if args.profile in {'media','full'} and not args.skip_npm:
        subprocess.run([*npm_command(),'ci'], cwd=ROOT/'tools/battle-video-studio', check=True)
    installed = install_skill(ROOT/'skills/battle-scaling',args.skill_dir,upgrade=args.upgrade)
    if selected: bind_runtime(Path(installed['skill_dir']),research='research' in selected)
    print(json.dumps({'installed': installed, 'capabilities': check(skill_dir=args.skill_dir)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(type(error).__name__+': '+str(error), file=sys.stderr)
        raise SystemExit(1)
