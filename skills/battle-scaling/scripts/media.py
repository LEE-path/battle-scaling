#!/usr/bin/env python3
"""Local evidence inspection, pixel measurement and timestamped frame extraction.

API: run(request:dict)->dict. CLI: --input request.json [--output result.json].
No built-in semantic vision or invented OCR. Pillow is optional; video operations
need ffmpeg/ffprobe on PATH. See references/media-reading.md for the VLM contract.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


def _number(v, name, *, minimum=None, positive=False):
    if isinstance(v,bool) or not isinstance(v,(int,float)):
        raise ValueError(f'{name}: numeric value required')
    try:
        v = float(v)
    except OverflowError:
        raise ValueError(f'{name}: finite value required') from None
    if not math.isfinite(v) or (positive and v<=0) or (minimum is not None and v<minimum):
        raise ValueError(f'{name}: invalid nonfinite or out-of-range value')
    return v


def _local_file(value):
    if not isinstance(value,str) or not value.strip():
        raise ValueError('path must name an existing local file')
    # URL input is intentionally not passed to ffmpeg/network protocols.
    if '://' in value:
        raise ValueError('Only local files are accepted; obtain authorized source media separately')
    p = Path(value).resolve()
    if not p.is_file():
        raise ValueError(f'Local file not found: {p}')
    return p


def _sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):
            h.update(block)
    return h.hexdigest()


def _destination(request, source=None):
    value = request.get('output')
    if not isinstance(value,str) or not value:
        raise ValueError('output file path is required for this operation')
    path = Path(value).resolve()
    if source and path==source:
        raise ValueError('Output must not overwrite the original evidence file')
    if not isinstance(request.get('overwrite',False),bool):
        raise ValueError('overwrite must be boolean')
    if path.exists() and request.get('overwrite') is not True:
        raise ValueError(f'Output exists; choose another path or explicitly set overwrite=true: {path}')
    if path.exists() and not path.is_file():
        raise ValueError('output must be a file path')
    path.parent.mkdir(parents=True,exist_ok=True)
    return path


def _pillow():
    try:
        from PIL import Image, ImageOps, ImageDraw
    except ImportError:
        raise ValueError('This operation requires Pillow; use agent image tools or install Pillow explicitly') from None
    return Image,ImageOps,ImageDraw


def _image(path):
    Image,ImageOps,_ = _pillow()
    try:
        with Image.open(path) as im:
            im.load()
            stored_size = list(im.size)
            orientation = im.getexif().get(274,1)
            fmt = im.format
            oriented = ImageOps.exif_transpose(im).copy()
    except (OSError,ValueError) as exc:
        raise ValueError(f'Cannot decode image: {exc}') from None
    return oriented,{'stored_size':stored_size,'exif_orientation':orientation,
                     'format':fmt,'width':oriented.width,'height':oriented.height,
                     'coordinate_space':'EXIF-oriented full image; no perspective warp or resize'}


def _save_image(image,path):
    allowed = {'.png':'PNG','.jpg':'JPEG','.jpeg':'JPEG','.webp':'WEBP','.tif':'TIFF','.tiff':'TIFF'}
    fmt = allowed.get(path.suffix.lower())
    if not fmt:
        raise ValueError('Image output extension must be png, jpg, webp or tif')
    if fmt=='JPEG' and image.mode not in ('RGB','L'):
        image = image.convert('RGB')
    # No original-file mutations and no partial output on encoder failure.
    with tempfile.NamedTemporaryFile(prefix='.battle-media-',suffix=path.suffix,dir=path.parent,delete=False) as handle:
        temporary = Path(handle.name)
    try:
        image.save(temporary,format=fmt)
        os.replace(temporary,path)
    finally:
        temporary.unlink(missing_ok=True)


def _segment(value,name,width,height):
    if not isinstance(value,list) or len(value)!=2:
        raise ValueError(f'{name}: use [[x1,y1],[x2,y2]]')
    pts = []
    for pair in value:
        if not isinstance(pair,list) or len(pair)!=2:
            raise ValueError(f'{name}: each point requires x,y')
        x = _number(pair[0],f'{name}.x',minimum=0)
        y = _number(pair[1],f'{name}.y',minimum=0)
        if x>width-1 or y>height-1:
            raise ValueError(f'{name}: points must be inside the oriented full image')
        pts.append((x,y))
    distance = math.dist(*pts)
    if distance<=0:
        raise ValueError(f'{name}: segment must have nonzero length')
    return pts,distance


def _timeout(request):
    timeout = _number(request.get('timeout_seconds',30),'timeout_seconds',positive=True)
    if timeout>60:
        raise ValueError('timeout_seconds must be <= 60; use smaller media segments if necessary')
    return timeout


def _invoke(command,timeout):
    try:
        p = subprocess.run(command,capture_output=True,text=True,encoding='utf-8',
                           errors='replace',timeout=timeout,check=False)
    except subprocess.TimeoutExpired:
        raise ValueError(f'Media process exceeded {timeout:g} seconds; narrow the requested operation') from None
    except OSError as exc:
        raise ValueError(f'Media process could not start: {exc}') from None
    if p.returncode:
        raise ValueError(f'Media process failed ({p.returncode}): {p.stderr[-2500:]}')
    return p


def _probe(path,timeout):
    exe = shutil.which('ffprobe')
    if not exe:
        raise ValueError('ffprobe not found on PATH; external video tool required')
    p = _invoke([exe,'-v','error','-protocol_whitelist','file,pipe','-print_format','json',
                 '-show_format','-show_streams',str(path)],timeout)
    try:
        data = json.loads(p.stdout)
    except json.JSONDecodeError:
        raise ValueError('ffprobe did not return valid JSON') from None
    videos = [s for s in data.get('streams',[]) if s.get('codec_type')=='video' and not s.get('disposition',{}).get('attached_pic')]
    if not videos:
        raise ValueError('No regular video stream found')
    chosen = videos[0]
    keys = ('index','codec_name','width','height','pix_fmt','r_frame_rate','avg_frame_rate','time_base','start_pts','start_time','duration','nb_frames','tags','side_data_list')
    video = {k:chosen[k] for k in keys if k in chosen}
    fmt = data.get('format',{})
    return {'video_stream':video,'format':{k:fmt[k] for k in ('format_name','start_time','duration','size') if k in fmt},
            'video_streams':len(videos),'timing_note':'avg_frame_rate is descriptive; use actual frame PTS for variable-rate video and motion timing.'}


def _measure(request,path):
    if request.get('same_plane') is not True or request.get('equal_projected_scale') is not True:
        raise ValueError('Measurement requires justified same_plane=true AND equal_projected_scale=true; otherwise rectify/calibrate perspective first')
    image,geometry = _image(path)
    ref,ref_px = _segment(request.get('reference_segment'),'reference_segment',image.width,image.height)
    target,target_px = _segment(request.get('target_segment'),'target_segment',image.width,image.height)
    ref_m = _number(request.get('reference_length_m'),'reference_length_m',positive=True)
    error = _number(request.get('pixel_error',0),'pixel_error',minimum=0)
    ref_error = _number(request.get('reference_length_error_m',0),'reference_length_error_m',minimum=0)
    if ref_px<=2*error or ref_error>=ref_m:
        raise ValueError('Measurement uncertainty reaches zero reference length; scale cannot be bounded')
    value = target_px/ref_px*ref_m
    lo = max(0,target_px-2*error)/(ref_px+2*error)*(ref_m-ref_error)
    hi = (target_px+2*error)/(ref_px-2*error)*(ref_m+ref_error)
    result = {'quantity':'estimated_length','value':value,'unit':'m',
              'reference_pixels':ref_px,'target_pixels':target_px,'metres_per_pixel':ref_m/ref_px,
              'interval_m':[lo,hi],'geometry':geometry,
              'segments':{'reference':[list(p) for p in ref],'target':[list(p) for p in target]}}
    if request.get('output'):
        destination = _destination(request,path)
        _,_,ImageDraw = _pillow()
        annotated = image.convert('RGB')
        draw = ImageDraw.Draw(annotated)
        stroke = max(1,round(min(image.size)/300))
        for pts,color,label in ((ref,'#0066ff',f'ref {ref_px:.2f} px = {ref_m:g} m'),
                                (target,'#dd2200',f'target {target_px:.2f} px ~ {value:.5g} m')):
            draw.line(pts,fill=color,width=stroke)
            for x,y in pts:
                draw.ellipse((x-2,y-2,x+2,y+2),outline=color,width=1)
            draw.text((pts[0][0]+3,pts[0][1]+3),label,fill=color)
        _save_image(annotated,destination)
        result['annotation'] = str(destination)
    return {'model':'pixel_ratio','inputs':{'path':str(path),'reference_length_m':ref_m,
        'reference_source':request.get('reference_source'),'pixel_error':error,
        'reference_length_error_m':ref_error},
        'steps':[{'formula':'L_target = pixels_target / pixels_reference * L_reference',
                  'substitution':f'{target_px}/{ref_px}*{ref_m}','value':value,'unit':'m'}],
        'result':result,'assumptions':['Reference and target are on a plane with equal projected local scale; foreshortening, lens distortion and stylization are negligible or separately corrected.',
                                    'pixel_error bounds each endpoint radial position error; segment-length error is bounded conservatively by twice that value.'],
        'limitations':['Same-plane alone does not establish equal projected scale under perspective.',
                       'Interval bounds only the stated endpoint/reference errors; unknown depth, anatomy, artwork scale changes and model error are excluded.',
                       'No object identity, body height, material, action or force is inferred by this geometric tool.'],
        'sources':['https://docs.opencv.org/4.x/d9/dab/tutorial_homography.html'],
        'source_sha256':_sha256(path)}


def _extract(request,path):
    timestamp = _number(request.get('timestamp_seconds'),'timestamp_seconds',minimum=0)
    timeout = _timeout(request)
    exe = shutil.which('ffmpeg')
    if not exe:
        raise ValueError('ffmpeg not found on PATH; external extraction tool required')
    probe = _probe(path,timeout)
    stream = probe['video_stream']
    try:
        duration = float(stream.get('duration',probe['format'].get('duration','nan')))
        start = float(stream.get('start_time',probe['format'].get('start_time',0)))
    except (TypeError,ValueError):
        duration,start = float('nan'),0
    if math.isfinite(duration) and timestamp>=duration:
        raise ValueError(f'timestamp_seconds is outside reported video duration ({duration:g} s)')
    if not math.isfinite(start):
        start = 0
    destination = _destination(request,path)
    if destination.suffix.lower() not in ('.png','.jpg','.jpeg'):
        raise ValueError('Extracted frame output must use png or jpg')
    with tempfile.NamedTemporaryFile(prefix='.battle-frame-',suffix=destination.suffix,
                                     dir=destination.parent,delete=False) as handle:
        temporary = Path(handle.name)
    command = [exe,'-hide_banner','-nostdin','-loglevel','info','-protocol_whitelist','file,pipe',
               '-ss',format(timestamp,'.17g'),'-copyts','-i',str(path),
               '-map',f'0:{stream["index"]}','-vf','showinfo','-frames:v','1','-an',
               '-fps_mode','passthrough','-update','1','-y',str(temporary)]
    try:
        p = _invoke(command,timeout)
        matches = re.findall(r'\bn:\s*0\s+pts:\s*([-+\d]+)\s+pts_time:\s*([-+\d.eE]+)',p.stderr)
        if not matches or not temporary.is_file() or temporary.stat().st_size==0:
            raise ValueError('No frame/PTS obtained; timestamp may be beyond the decodable stream')
        timebases = re.findall(r'config in time_base:\s*(\d+/\d+)',p.stderr)
        timebase = timebases[0] if timebases else stream.get('time_base')
        source_pts = int(matches[0][0])
        if timebase:
            actual = _number(float(source_pts*Fraction(timebase)),'actual frame PTS')
        else:
            raise ValueError('No filter/stream time base available; cannot report exact original frame PTS')
        if 'start_pts' in stream and stream.get('time_base'):
            start = float(int(stream['start_pts'])*Fraction(stream['time_base']))
        playback = actual-start
        if playback+1e-6<timestamp:
            raise ValueError('Extracted PTS predates requested playback time; inspect stream timestamps manually')
        os.replace(temporary,destination)
    finally:
        temporary.unlink(missing_ok=True)
    return {'model':'video_frame_extraction','inputs':{'path':str(path),'timestamp_seconds':timestamp},
            'steps':[{'operation':'accurate input seek with original PTS, showinfo and one-frame output',
                      'requested_playback_seconds':timestamp,'stream_start_pts_seconds':start}],
            'result':{'path':str(destination),'actual_source_pts_seconds':actual,
                      'actual_playback_seconds':playback,'requested_playback_seconds':timestamp,
                      'source_pts':source_pts,'source_time_base':timebase,
                      'sha256':_sha256(destination),'video_stream':stream},
            'assumptions':['timestamp_seconds is playback time relative to the selected video stream start; original frame PTS is recorded.'],
            'limitations':['The next decoded frame at/after the requested time is returned, not an invented subframe.',
                           'Video edits, slow motion and variable narrative time must be interpreted by a vision-capable agent before estimating in-world speed.'],
            'sources':['https://ffmpeg.org/ffmpeg.html','https://ffmpeg.org/ffmpeg-filters.html#showinfo']}


def _vision_contract(request,path):
    image,geometry = _image(path)
    task = request.get('task')
    if not isinstance(task,str) or not task.strip():
        raise ValueError('vision-request requires a specific task string')
    return {'operation':'vision-request','status':'requires_external_vision',
        'image':{'path':str(path),'sha256':_sha256(path),'geometry':geometry},'task':task,
        'instructions':['A vision-capable agent or explicitly configured external adapter must inspect the actual image.',
                        'Report visible facts separately from interpretations and assumptions; do not infer off-panel events.',
                        'Use the EXIF-oriented full image coordinates and cite bounding boxes for every key observation.',
                        'OCR is provisional; transcribe original script and mark unreadable/ambiguous text.',
                        'Establish page/panel order and preceding/following context before making combat claims.'],
        'required_response_schema':{'inspector':'model/tool and actual invocation identifier',
            'observations':[{'id':'obs-001','bbox_xyxy':[0,0,image.width,image.height],
                'kind':'text|entity|action|effect|panel_order','visible_fact':'',
                'original_text':None,'speaker':None,'confidence':'high|medium|low'}],
            'interpretations':[{'claim':'','observation_ids':[],'assumptions':[]}],
            'unreadable_regions':[],'missing_context':[]},
        'limitations':['This command prepares a request contract only; no image understanding has been performed.']}


def run(request: dict) -> dict:
    if not isinstance(request,dict):
        raise ValueError('request must be an object')
    operation = request.get('operation')
    if operation=='doctor':
        return {'operation':'doctor','capabilities':{'python':sys.version.split()[0],
            'Pillow':importlib.util.find_spec('PIL') is not None,
            'numpy':importlib.util.find_spec('numpy') is not None,
            'manga_ocr':importlib.util.find_spec('manga_ocr') is not None,
            'tesseract':shutil.which('tesseract'),'ffprobe':shutil.which('ffprobe'),
            'ffmpeg':shutil.which('ffmpeg'),'semantic_vision_builtin':False},
            'limitations':['Installed OCR packages/binaries are detected, not loaded or assumed operational.',
                           'An external vision-capable agent/adapter is required for manga and action interpretation.']}
    known = ('image-info','crop','measure','video-probe','video-extract','vision-request')
    if operation not in known:
        raise ValueError(f'Unknown operation; choose doctor or {", ".join(known)}')
    path = _local_file(request.get('path'))
    if operation=='image-info':
        im,geometry = _image(path)
        return {'operation':operation,'path':str(path),'sha256':_sha256(path),
                'result':{**geometry,'mode':im.mode},
                'limitations':['Metadata and dimensions only; no semantic reading has been performed.']}
    if operation=='crop':
        im,geometry = _image(path)
        box = request.get('box')
        if not isinstance(box,list) or len(box)!=4 or any(isinstance(v,bool) or not isinstance(v,int) for v in box):
            raise ValueError('box must be integer [left,top,right,bottom] in oriented full image coordinates')
        left,top,right,bottom = box
        if not(0<=left<right<=im.width and 0<=top<bottom<=im.height):
            raise ValueError('crop box must be nonempty and inside original oriented image')
        destination = _destination(request,path)
        cropped = im.crop(box)
        _save_image(cropped,destination)
        return {'operation':operation,'path':str(path),'source_sha256':_sha256(path),
                'result':{'path':str(destination),'size':list(cropped.size),'box':box,
                          'source_geometry':geometry,'source_offset':[left,top],
                          'sha256':_sha256(destination)},
                'limitations':['Crop coordinates map back by adding source_offset; original evidence is retained.']}
    if operation=='measure':
        return _measure(request,path)
    if operation=='video-probe':
        return {'operation':operation,'path':str(path),'result':_probe(path,_timeout(request)),
                'sources':['https://ffmpeg.org/ffprobe.html']}
    if operation=='video-extract':
        return _extract(request,path)
    return _vision_contract(request,path)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',required=True,help='JSON request file, or - for stdin')
    parser.add_argument('--output',help='Result JSON path; default stdout. Media artifact output belongs inside request JSON.')
    args = parser.parse_args(argv)
    try:
        text = sys.stdin.read() if args.input=='-' else Path(args.input).read_text(encoding='utf-8-sig')
        req = json.loads(text,parse_constant=lambda s: (_ for _ in ()).throw(ValueError(f'Invalid JSON constant: {s}')))
        result = run(req)
        rendered = json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
        if args.output:
            output = Path(args.output).resolve()
            if args.input!='-' and output==Path(args.input).resolve():
                raise ValueError('Result JSON must not overwrite the request JSON')
            if isinstance(req.get('path'),str) and output==Path(req['path']).resolve():
                raise ValueError('Result JSON must not overwrite the original evidence file')
            output.parent.mkdir(parents=True,exist_ok=True)
            output.write_text(rendered,encoding='utf-8')
        else:
            print(rendered,end='')
        return 0
    except (ValueError,OSError) as exc:
        print(json.dumps({'error':str(exc)},ensure_ascii=False),file=sys.stderr)
        return 2


if __name__=='__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    raise SystemExit(main())
