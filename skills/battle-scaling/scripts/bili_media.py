"""Bilibili media adapter: user-confirmed QR login, actual formats, local download.

No GUI, passwords, embedded JiJiDown code, or third-party parsing service.
Dependencies: requests, qrcode[pil], yt-dlp; ffmpeg and ffprobe on PATH.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import ctypes
import http.cookiejar
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import requests

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140.0.0.0 Safari/537.36'
BASE = 'https://passport.bilibili.com/x/passport-login/web/qrcode/'


def emit(value):
    print(json.dumps(value, ensure_ascii=False), flush=True)


def state_root():
    override = os.environ.get('BATTLE_BILI_STATE_DIR')
    p = Path(override) if override else Path(os.environ.get('LOCALAPPDATA', Path.home()/'.local/share'))/'BattleScaling'/'Bilibili'
    p.mkdir(parents=True, exist_ok=True, mode=0o700)
    return p


def secret_path(name):
    return state_root()/(name + ('.dpapi' if os.name == 'nt' else '.private.json'))


def dpapi(data, decrypt=False):
    class Blob(ctypes.Structure):
        _fields_ = [('length', ctypes.c_ulong), ('data', ctypes.POINTER(ctypes.c_ubyte))]
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    result = Blob()
    fn = ctypes.windll.crypt32.CryptUnprotectData if decrypt else ctypes.windll.crypt32.CryptProtectData
    description = None if decrypt else 'Battle Scaling Bilibili session'
    if not fn(ctypes.byref(source), description, None, None, None, 1, ctypes.byref(result)):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(result.data, result.length)
    finally:
        ctypes.windll.kernel32.LocalFree(result.data)


def save_secret(name, value):
    data = json.dumps(value, ensure_ascii=False).encode('utf-8')
    if os.name == 'nt':
        data = dpapi(data)
    p = secret_path(name)
    with p.open('wb') as f:
        f.write(data)
    if os.name != 'nt':
        p.chmod(0o600)


def load_secret(name):
    p = secret_path(name)
    if not p.exists():
        return {}
    data = p.read_bytes()
    if os.name == 'nt':
        data = dpapi(data, decrypt=True)
    return json.loads(data)


def session(auth=True):
    s = requests.Session()
    # Domestic Bilibili endpoints failed through this machine's inherited
    # overseas proxy. Scope the route to this adapter; never change global proxy.
    s.trust_env = False
    s.headers.update({'User-Agent': UA, 'Referer': 'https://www.bilibili.com/'})
    if auth:
        for name, value in load_secret('credential').get('cookies', {}).items():
            s.cookies.set(name, value, domain='.bilibili.com', path='/')
    return s


def api(s, url, **params):
    r = s.get(url, params=params, timeout=(8, 20))
    r.raise_for_status()
    j = r.json()
    if j.get('code') != 0:
        raise RuntimeError(f'Bilibili API returned {j.get("code")}: {str(j.get("message", ""))[:120]}')
    return j.get('data', {})


def qr_start(args):
    import qrcode
    data = api(session(False), BASE+'generate', source='main-fe-header')
    # Pending QR key is also private. Never echo the key or callback URL.
    save_secret('pending-login', {'key': data['qrcode_key'], 'started': time.time()})
    p = Path(args.out).resolve();p.parent.mkdir(parents=True, exist_ok=True)
    qrcode.make(data['url']).save(p)
    return {'state': 'waiting_for_scan', 'qr_image': str(p), 'note': '请用B站App扫码并在手机上确认；本工具不接收密码或验证码'}


def qr_status(args):
    p = load_secret('pending-login')
    if not p:
        raise RuntimeError('No pending login. Run qr-start first.')
    s = session(False)
    data = api(s, BASE+'poll', qrcode_key=p['key'], source='main-fe-header')
    code = data.get('code')
    states = {86101: 'waiting_for_scan', 86090: 'waiting_for_phone_confirmation', 86038: 'expired'}
    if code in states:
        return {'state': states[code]}
    if code != 0:
        return {'state': 'not_completed', 'code': code}
    cookies = s.cookies.get_dict()
    for name, values in parse_qs(urlsplit(data.get('url', '')).query).items():
        if name in {'SESSDATA', 'bili_jct', 'DedeUserID', 'DedeUserID__ckMd5', 'sid'}:
            cookies.setdefault(name, values[-1])
    if not cookies.get('SESSDATA'):
        raise RuntimeError('Login response did not include a usable session cookie.')
    save_secret('credential', {'cookies': cookies, 'refresh_token': data.get('refresh_token'), 'saved_at': time.time()})
    # Invalidate the pending state without exposing the original login key.
    save_secret('pending-login', {})
    return {'state': 'logged_in', 'storage': 'Windows current-user DPAPI' if os.name == 'nt' else 'private local file, mode 0600'}


def status(args):
    try:
        data = api(session(), 'https://api.bilibili.com/x/web-interface/nav')
    except RuntimeError as error:
        if 'returned -101:' not in str(error):
            raise
        data = {'isLogin': False}
    return {'logged_in': bool(data.get('isLogin')), 'vip_active': data.get('vipStatus') == 1,
            'credential_present': bool(load_secret('credential').get('cookies', {}).get('SESSDATA'))}


def login(args):
    """A localhost QR display, not computer-use or browser automation."""
    display = {'state': 'starting', 'version': 0}
    image = state_root()/'login-qr.png'
    lock = threading.Lock()
    stopped = threading.Event()

    def worker():
        deadline = time.monotonic()+args.timeout
        fresh = True
        while time.monotonic() < deadline and not stopped.is_set():
            try:
                result = qr_start(argparse.Namespace(out=str(image))) if fresh else qr_status(argparse.Namespace())
                with lock:
                    display['state'] = result['state']
                    if fresh:
                        display['version'] += 1
                if result['state'] == 'logged_in':
                    emit({'stage': 'login_complete', 'logged_in': True})
                    return
                fresh = result['state'] == 'expired'
            except Exception as e:
                with lock:
                    display['state'] = 'network_error'
                emit({'stage': 'login_network_error', 'type': type(e).__name__})
            stopped.wait(3)
        with lock:
            if display['state'] != 'logged_in':
                display['state'] = 'stopped'

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *unused): pass
        def do_GET(self):
            if self.path.startswith('/state'):
                with lock:
                    body = json.dumps(display).encode('utf-8')
                mime = 'application/json'
            elif self.path.startswith('/qr.png'):
                body = image.read_bytes() if image.exists() else b''
                mime = 'image/png'
            else:
                body = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Battle Scaling · B站扫码登录</title><style>body{margin:0;background:#101520;color:#eef3ff;font:18px/1.7 system-ui,"Microsoft YaHei";text-align:center}main{max-width:600px;margin:9vh auto;padding:25px}img{width:300px;max-width:80vw;border:12px solid white;border-radius:10px}p{color:#b6c6dd}h1{font-size:28px}.ok{color:#64e5b0}</style><main><h1>B站扫码登录</h1><p>请用B站App扫码，在手机上确认登录。</p><img id="qr"><h2 id="state">正在生成二维码…</h2><p>二维码过期会自动刷新。凭据仅在本机保存，<br>Windows使用当前用户加密，不发送给解析网站。</p></main><script>let v=-1;const words={starting:'正在生成二维码…',waiting_for_scan:'等待扫码',waiting_for_phone_confirmation:'已扫描，请在手机确认',logged_in:'登录成功，可以关闭此页',network_error:'网络暂不可用，正在重试',stopped:'等待已结束，请重新启动登录'};async function tick(){try{let s=await(await fetch('/state',{cache:'no-store'})).json();document.querySelector('#state').textContent=words[s.state]||'正在刷新';if(s.version!==v){v=s.version;document.querySelector('#qr').src='/qr.png?v='+v}if(s.state==='logged_in'){document.querySelector('#qr').style.display='none';document.querySelector('#state').className='ok';return}}catch(e){}setTimeout(tick,1500)}tick()</script></html>'''.encode('utf-8')
                mime = 'text/html; charset=utf-8'
            self.send_response(200);self.send_header('Content-Type', mime)
            self.send_header('Cache-Control', 'no-store');self.send_header('Content-Length', str(len(body)))
            self.end_headers();self.wfile.write(body)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    threading.Thread(target=worker, daemon=True).start()
    emit({'stage': 'login_display', 'url': f'http://127.0.0.1:{args.port}', 'timeout_seconds': args.timeout})
    try:
        server.serve_forever()
    finally:
        stopped.set();server.server_close()


@contextmanager
def cookie_file():
    cookies = load_secret('credential').get('cookies', {})
    if not cookies:
        yield None
        return
    fd, name = tempfile.mkstemp(prefix='bili-cookies-', suffix='.txt', dir=state_root())
    os.close(fd)
    jar = http.cookiejar.MozillaCookieJar(name)
    try:
        for key, value in cookies.items():
            jar.set_cookie(http.cookiejar.Cookie(0, key, value, None, False, '.bilibili.com', True, True, '/', True, True,
                int(time.time()+86400), False, None, None, {}, False))
        jar.save(ignore_discard=True, ignore_expires=True)
        if os.name != 'nt':
            Path(name).chmod(0o600)
        yield name
    finally:
        Path(name).unlink(missing_ok=True)


class QuietLogger:
    def debug(self, message): pass
    def info(self, message): pass
    def warning(self, message):
        if not any(x in message.lower() for x in ('cookie', 'sessdata', 'sign=', 'http')):
            print('yt-dlp: '+message[:200], file=sys.stderr, flush=True)
    def error(self, message): pass


def canonical(value, page=None, *, _redirects=0):
    """An explicit page wins; otherwise preserve the supplied (or resolved) URL."""
    def positive_page(number):
        if isinstance(number, bool) or not re.fullmatch(r'[1-9][0-9]*', str(number)):
            raise ValueError('Bilibili page must be a positive integer.')
        return int(number)

    override = positive_page(page) if page is not None else None
    value = str(value).strip()
    identifier = value if re.fullmatch(r'BV[0-9A-Za-z]{10}|av\d+', value, re.I) else None
    url_page = None
    if identifier is None:
        u = urlsplit(value)
        if (u.scheme not in {'http', 'https'} or u.username or u.password or
                u.hostname not in {'b23.tv', 'www.bilibili.com', 'bilibili.com', 'm.bilibili.com'}):
            raise ValueError('Use a BV/av identifier, canonical Bilibili video URL or b23.tv link.')
        if u.hostname == 'b23.tv':
            if _redirects >= 5:
                raise ValueError('Bilibili short link did not resolve to a video.')
            response = session(False).get(value, allow_redirects=True, timeout=(8, 20))
            return canonical(response.url, override, _redirects=_redirects+1)
        match = re.fullmatch(r'/video/(BV[0-9A-Za-z]{10}|av\d+)/?', u.path, re.I)
        if not match:
            raise ValueError('Bilibili URL must identify a video.')
        identifier = match.group(1)
        if override is None:
            pages = parse_qs(u.query, keep_blank_values=True).get('p', [])
            if len(pages) > 1:
                raise ValueError('Bilibili URL contains ambiguous page parameters.')
            url_page = positive_page(pages[0]) if pages else None
    if identifier.lower().startswith('av'):
        identifier = 'av'+identifier[2:]
    return f'https://www.bilibili.com/video/{identifier}?p={override or url_page or 1}'


def ydl_options(cookie):
    return {'quiet': True, 'no_warnings': False, 'logger': QuietLogger(), 'noplaylist': True,
            'proxy': '', 'socket_timeout': 20, 'retries': 1, 'fragment_retries': 1,
            'cookiefile': cookie, 'http_headers': {'User-Agent': UA, 'Referer': 'https://www.bilibili.com/'}}


def summarize_formats(data):
    return [{'id': f.get('format_id'), 'width': f.get('width'), 'height': f.get('height'),
             'fps': f.get('fps'), 'video_codec': f.get('vcodec'), 'audio_codec': f.get('acodec'),
             'bitrate_kbps': f.get('tbr'), 'note': f.get('format_note')}
            for f in data.get('formats', []) if f.get('vcodec') != 'none']


def search(args):
    """Small keyword search; the agent changes query angle to match the gap."""
    from yt_dlp import YoutubeDL
    limit = max(1, min(10, args.limit))
    with cookie_file() as cookie:
        options = ydl_options(cookie)
        options.update({'extract_flat': True, 'noplaylist': False, 'playlistend': limit})
        with YoutubeDL(options) as ydl:
            data = ydl.extract_info(f'bilisearch{limit}:{args.query}', download=False)
            entries = list(data.get('entries') or [])[:limit]
    found = []
    s = session()
    for e in entries:
        item = {'title': e.get('title'), 'url': e.get('webpage_url') or e.get('url'),
                'duration': e.get('duration'), 'view_count': e.get('view_count')}
        # Some yt-dlp Bilibili search entries only contain an av URL. Resolve
        # their public metadata so the agent can actually compare the hits.
        if not item['title']:
            bv = re.search(r'BV[0-9A-Za-z]{10}', item['url'] or '')
            av = re.search(r'/av(\d+)', item['url'] or '')
            if bv or av:
                try:
                    params = {'bvid': bv.group(0)} if bv else {'aid': av.group(1)}
                    metadata = api(s, 'https://api.bilibili.com/x/web-interface/view', **params)
                    item.update(title=metadata.get('title'), duration=metadata.get('duration'),
                        view_count=metadata.get('stat', {}).get('view'),
                        url='https://www.bilibili.com/video/'+metadata['bvid'])
                except (requests.RequestException, RuntimeError, KeyError):
                    item['note'] = '公共标题暂未取到，请从发布页查看'
        found.append(item)
    result = {'query': args.query, 'results': found}
    if args.out:
        p = Path(args.out);p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return result


def formats(args):
    from yt_dlp import YoutubeDL
    with cookie_file() as cookie, YoutubeDL(ydl_options(cookie)) as ydl:
        data = ydl.extract_info(canonical(args.url, args.page), download=False)
    fs = summarize_formats(data)
    result = {'bvid': data.get('id'), 'title': data.get('title'), 'duration': data.get('duration'),
              'maximum_actual_height': max((f.get('height') or 0 for f in fs), default=0), 'formats': fs}
    if args.out:
        p = Path(args.out);p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return result


def download(args):
    from yt_dlp import YoutubeDL
    out = Path(args.out).resolve();out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        raise FileExistsError('Output exists; reuse it or choose another filename.')
    last = [-1]
    def progress(info):
        if info.get('status') == 'downloading':
            total = info.get('total_bytes') or info.get('total_bytes_estimate')
            if total:
                bucket = int(info.get('downloaded_bytes', 0)/total*10)
                if bucket != last[0]:
                    last[0] = bucket
                    emit({'stage': 'downloading', 'percent': min(100, bucket*10)})
    with cookie_file() as cookie:
        opts = ydl_options(cookie)
        opts.update({'format': f'bv*[height<={args.height}]+ba/b[height<={args.height}]',
                     'outtmpl': str(out.with_suffix(''))+'.%(ext)s', 'merge_output_format': 'mp4',
                     'overwrites': False, 'format_sort': ['res', 'fps', 'br', 'codec:h264'], 'progress_hooks': [progress]})
        with YoutubeDL(opts) as ydl:
            data = ydl.extract_info(canonical(args.url, args.page), download=False)
            if (data.get('height') or 0) < args.min_height:
                raise RuntimeError(f'当前登录会话实际最高选中 {data.get("height")}p，未达到要求的 {args.min_height}p。不会将低清文件标成高清；先核登录、账号权限及源片本身画质。')
            emit({'stage': 'resolved', 'title': data.get('title'), 'height': data.get('height'), 'width': data.get('width')})
            ydl.process_info(data)
    if not out.exists():
        raise RuntimeError('Expected merged MP4 was not produced; keep partial files for resume.')
    metadata = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(out)]))
    videos = [s for s in metadata.get('streams', []) if s.get('codec_type') == 'video']
    if not videos:
        raise RuntimeError('Downloaded result has no video stream.')
    v = videos[0]
    return {'stage': 'done', 'path': str(out), 'width': v.get('width'), 'height': v.get('height'),
            'duration': metadata.get('format', {}).get('duration'), 'bytes': out.stat().st_size,
            'has_audio': any(s.get('codec_type') == 'audio' for s in metadata.get('streams', []))}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='op', required=True)
    a = sub.add_parser('login');a.add_argument('--port', type=int, default=3212);a.add_argument('--timeout', type=int, default=600)
    a = sub.add_parser('qr-start');a.add_argument('--out', required=True)
    sub.add_parser('qr-status');sub.add_parser('status')
    a = sub.add_parser('search');a.add_argument('query');a.add_argument('--limit', type=int, default=6);a.add_argument('--out')
    for op in ['formats', 'download']:
        a = sub.add_parser(op);a.add_argument('url');a.add_argument('--page', type=int, default=None,
            help='Override the URL page; otherwise retain its p parameter (default P1).')
        a.add_argument('--out', required=op == 'download')
        if op == 'download':
            a.add_argument('--height', type=int, default=2160);a.add_argument('--min-height', type=int, default=1080)
    args = p.parse_args()
    try:
        emit({'login': login, 'qr-start': qr_start, 'qr-status': qr_status, 'status': status, 'search': search, 'formats': formats, 'download': download}[args.op](args))
    except Exception as e:
        # Avoid echoing URLs or cookie values from a third-party network exception.
        msg = str(e)
        if any(x in msg.lower() for x in ('sessdata', 'qrcode_key=', 'cookie=', 'access_key=', 'sign=')):
            msg = type(e).__name__+'; private request details omitted'
        emit({'stage': 'error', 'error': msg[:350]});sys.exit(1)


if __name__ == '__main__':
    main()
