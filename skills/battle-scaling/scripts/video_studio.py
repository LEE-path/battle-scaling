"""Thin local bridge to the optional Battle Video Studio, without rating dependencies."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys
import time
import secrets
import shutil
from datetime import datetime, timezone
import urllib.request
import urllib.error

SKILL = Path(__file__).resolve().parents[1]
BASE = 'http://127.0.0.1:3210'

class VideoStudioError(RuntimeError):
    """Keep useful editing gaps as data, without adding any rating gate."""
    def __init__(self, details):
        self.details = details
        super().__init__(details.get('error', 'Video Studio request failed'))

def studio_root():
    configured = os.environ.get('BATTLE_VIDEO_STUDIO_ROOT')
    settings = SKILL / 'runtime/video-studio.local.json'
    if not configured and settings.exists():
        configured = json.loads(settings.read_text(encoding='utf-8')).get('project_root')
    candidates = [Path(configured).expanduser()] if configured else [
        SKILL.parent / 'battle-video-studio',
        SKILL.parent.parent / 'tools/battle-video-studio',
        SKILL / 'tools/battle-video-studio',
    ]
    for candidate in candidates:
        if (candidate / 'scripts/server.mjs').is_file():
            return candidate.resolve()
    raise RuntimeError('未找到Battle Video Studio。请安装完整发布包，或配置BATTLE_VIDEO_STUDIO_ROOT／runtime/video-studio.local.json中的project_root。')

def api(route, data=None, timeout=10):
    request = urllib.request.Request(BASE + route,
        data=None if data is None else json.dumps(data,ensure_ascii=False).encode('utf-8'),
        headers={'Content-Type':'application/json'} if data is not None else {})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        try:
            detail = json.loads(error.read().decode('utf-8'))
        except (ValueError, UnicodeError):
            detail = {'error':str(error)}
        if not isinstance(detail, dict):detail={'error':str(error)}
        raise VideoStudioError(detail) from error

def open_studio(root, no_browser=False):
    args=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(root/'打开剪辑工作台.ps1')]
    if no_browser:
        args.append('-NoBrowser')
    subprocess.run(args,check=True,timeout=15)

def prepare_local(root, source, *, activate=True):
    """Use current on-disk code; a running workbench may have an older import."""
    runtime = SKILL/'runtime/media-tools.local.json'
    node = os.environ.get('BATTLE_VIDEO_NODE')
    if not node and runtime.is_file():
        node = json.loads(runtime.read_text(encoding='utf-8-sig')).get('node')
    node = node or shutil.which('node')
    if not node:raise RuntimeError('准备工程需要Node.js；请配置PATH或BATTLE_VIDEO_NODE。')
    command = [str(node),str(root/'scripts/prepare-job.mjs'),str(source),'--json']
    if not activate:command.append('--no-activate')
    result = subprocess.run(command,cwd=root,capture_output=True,text=True,encoding='utf-8',timeout=120)
    try:detail=json.loads(result.stdout)
    except (ValueError,TypeError):raise RuntimeError('工程准备未返回JSON：'+(result.stderr or result.stdout)[-400:]) from None
    if result.returncode:raise VideoStudioError(detail if isinstance(detail,dict) else {'error':'工程准备失败'})
    return detail

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['select-template','open','status','prepare','render'])
    parser.add_argument('--template',help='指定V01—V09；省略则从九个默认方案等概率抽取')
    parser.add_argument('--job',help='任务JSON路径')
    parser.add_argument('--project',help='已准备的工程ID')
    parser.add_argument('--scale',type=float,default=1)
    parser.add_argument('--no-browser',action='store_true')
    parser.add_argument('--no-activate',action='store_true',help='准备独立工程，不替换当前预览')
    args=parser.parse_args()
    if args.action=='select-template':
        folder=SKILL/'assets/media/video-presets'
        defaults=json.loads((folder/'defaults.json').read_text(encoding='utf-8'))
        explicit=bool(args.template and args.template!='random')
        if explicit and args.template not in defaults['presetPool']:
            parser.error('模板须为'+', '.join(defaults['presetPool']))
        template_id=args.template if explicit else secrets.choice(defaults['presetPool'])
        timing=json.loads((folder/'timelines'/f'{template_id}.json').read_text(encoding='utf-8'))
        print(json.dumps({'templateId':template_id,'templateSelection':{'mode':'explicit' if explicit else 'random','pool':defaults['presetPool'],'selectedAt':datetime.now(timezone.utc).isoformat()},
            'comparisonSlots':timing['comparison_slot_count'],'durationSeconds':timing['duration_s'],'audioFile':timing['audio_file'],
            'timingFile':str(folder/'timelines'/f'{template_id}.json'),'defaults':defaults},ensure_ascii=False,indent=2))
        return
    root=studio_root()
    if args.action=='open':
        open_studio(root,args.no_browser)
        return
    if args.action=='status':
        try:
            templates=api('/api/templates',timeout=2)
            result={'running':True,'workbench':BASE,'project_root':str(root),
                    'templates':[{'id':t['id'],'slots':t['slots'],'verdict':t['verdict']} for t in templates]}
            if args.project:
                import urllib.parse
                result['render']=api('/api/progress?id='+urllib.parse.quote(args.project))
        except (OSError,urllib.error.URLError):
            result={'running':False,'project_root':str(root),'message':'工作台尚未启动，使用open命令。'}
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return
    if args.action=='prepare':
        if not args.job:parser.error('prepare需要--job')
        source=Path(args.job).resolve(strict=True)
        print(json.dumps(prepare_local(root,source,activate=not args.no_activate),ensure_ascii=False,indent=2))
        return
    try:
        api('/api/templates',timeout=2)
    except (OSError,urllib.error.URLError):
        open_studio(root,no_browser=True)
        for attempt in range(10):
            try:
                api('/api/templates',timeout=1)
                break
            except (OSError,urllib.error.URLError):
                if attempt==9:
                    raise RuntimeError('工作台启动未完成，请查看工程data目录中的server.stderr.log。')
                time.sleep(.5)
    if not args.project:parser.error('render需要--project')
    print(json.dumps(api('/api/render',{'id':args.project,'scale':args.scale}),ensure_ascii=False))
    print('已提交导出；用status --project查看进度。')

if __name__=='__main__':
    try:
        main()
    except VideoStudioError as error:
        print(json.dumps(error.details,ensure_ascii=False),file=sys.stderr)
        sys.exit(1)
    except Exception as error:
        print(str(error),file=sys.stderr)
        sys.exit(1)
